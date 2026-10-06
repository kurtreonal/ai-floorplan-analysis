from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import cv2
import numpy as np

from app.ai.wall_detection.config import (
    INVALID_CONFIGURATION_MESSAGE,
    WallDetectionConfigurationError,
    WallDetectionError,
    WallDetectionParameters,
)

if TYPE_CHECKING:
    from app.ai.preprocessing.pipeline import PreprocessedImage


MAXIMUM_IMAGE_EDGE = 4096
ALGORITHM = "probabilistic_hough"
ERROR_MESSAGES = {
    "INVALID_CONFIGURATION": INVALID_CONFIGURATION_MESSAGE,
    "INVALID_PROCESSED_IMAGE_RESULT": "The G3 processed-image result is invalid.",
    "INVALID_DTYPE_OR_SHAPE": "The wall-detection image type or shape is invalid.",
    "NONBINARY_IMAGE": "The wall-detection image must contain only binary pixels.",
    "UNSAFE_DIMENSIONS": "The wall-detection image dimensions are unsafe.",
    "EDGE_DETECTION_FAILED": "Candidate wall edges could not be detected.",
    "HOUGH_DETECTION_FAILED": "Candidate wall lines could not be detected.",
    "MALFORMED_OPENCV_RESULT": "The wall detector returned an invalid result.",
    "INVALID_COORDINATES": "A candidate wall segment has invalid coordinates.",
    "THINNING_BUDGET_EXCEEDED": "The wall mask exceeds the bounded thinning budget.",
}


def _error(code: str) -> WallDetectionError:
    return WallDetectionError(code, ERROR_MESSAGES[code])


@dataclass(frozen=True)
class PixelPoint:
    x: int
    y: int

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y}


@dataclass(frozen=True)
class WallLineCandidate:
    candidate_id: int
    start: PixelPoint
    end: PixelPoint
    length_pixels: float
    angle_degrees: float
    estimated_thickness_pixels: float | None = None

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "candidate_id": self.candidate_id,
            "start": self.start.to_dict(),
            "end": self.end.to_dict(),
            "length_pixels": self.length_pixels,
            "angle_degrees": self.angle_degrees,
        }
        if self.estimated_thickness_pixels is not None:
            data["estimated_thickness_pixels"] = self.estimated_thickness_pixels
        return data


@dataclass(frozen=True)
class CoordinateSpace:
    width: int
    height: int
    unit: str = "pixel"
    origin: str = "top_left"
    x_direction: str = "right"
    y_direction: str = "down"

    def to_dict(self) -> dict[str, object]:
        return {
            "unit": self.unit,
            "origin": self.origin,
            "x_direction": self.x_direction,
            "y_direction": self.y_direction,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True)
class WallDetectionResult:
    coordinate_space: CoordinateSpace
    algorithm: str
    truncated: bool
    candidates: tuple[WallLineCandidate, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "coordinate_space": self.coordinate_space.to_dict(),
            "algorithm": self.algorithm,
            "truncated": self.truncated,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


def _is_g3_result(value: object) -> bool:
    value_type = type(value)
    return (
        value_type.__name__ == "PreprocessedImage"
        and value_type.__module__ == "app.ai.preprocessing.pipeline"
    )


def _extract_binary_image(
    source: "PreprocessedImage | np.ndarray",
) -> np.ndarray:
    if isinstance(source, np.ndarray):
        image = source
    elif _is_g3_result(source):
        try:
            image = source.thresholded
            expected_width = source.width
            expected_height = source.height
        except Exception:
            raise _error("INVALID_PROCESSED_IMAGE_RESULT") from None
        if (
            not isinstance(expected_width, int)
            or isinstance(expected_width, bool)
            or not isinstance(expected_height, int)
            or isinstance(expected_height, bool)
            or not isinstance(image, np.ndarray)
            or image.ndim != 2
            or image.shape != (expected_height, expected_width)
        ):
            raise _error("INVALID_PROCESSED_IMAGE_RESULT")
    else:
        raise _error("INVALID_PROCESSED_IMAGE_RESULT")

    if image.dtype != np.uint8 or image.ndim != 2:
        raise _error("INVALID_DTYPE_OR_SHAPE")
    height, width = image.shape
    if width <= 0 or height <= 0:
        raise _error("INVALID_DTYPE_OR_SHAPE")
    if max(width, height) > MAXIMUM_IMAGE_EDGE:
        raise _error("UNSAFE_DIMENSIONS")
    if not np.isin(image, (0, 255)).all():
        raise _error("NONBINARY_IMAGE")
    return image


def _empty_result(width: int, height: int) -> WallDetectionResult:
    return WallDetectionResult(
        coordinate_space=CoordinateSpace(width=width, height=height),
        algorithm=ALGORITHM,
        truncated=False,
        candidates=(),
    )


def _canonical_segment(
    coordinates: object,
    *,
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    try:
        values = tuple(coordinates)
    except (TypeError, ValueError):
        raise _error("MALFORMED_OPENCV_RESULT") from None
    if len(values) != 4:
        raise _error("MALFORMED_OPENCV_RESULT")
    if any(
        not isinstance(value, (int, np.integer)) or isinstance(value, (bool, np.bool_))
        for value in values
    ):
        raise _error("MALFORMED_OPENCV_RESULT")
    x1, y1, x2, y2 = (int(value) for value in values)
    if not (
        0 <= x1 < width
        and 0 <= x2 < width
        and 0 <= y1 < height
        and 0 <= y2 < height
    ):
        raise _error("INVALID_COORDINATES")
    if (y2, x2) < (y1, x1):
        x1, y1, x2, y2 = x2, y2, x1, y1
    return x1, y1, x2, y2


def _canonical_segments(
    hough_lines: object,
    *,
    width: int,
    height: int,
) -> list[tuple[int, int, int, int]]:
    if hough_lines is None:
        return []
    if not isinstance(hough_lines, np.ndarray):
        raise _error("MALFORMED_OPENCV_RESULT")
    if hough_lines.size == 0:
        return []
    if hough_lines.ndim == 3 and hough_lines.shape[1:] == (1, 4):
        rows = hough_lines[:, 0, :]
    elif hough_lines.ndim == 2 and hough_lines.shape[1] == 4:
        rows = hough_lines
    else:
        raise _error("MALFORMED_OPENCV_RESULT")
    unique = {
        _canonical_segment(row, width=width, height=height)
        for row in rows
    }
    return sorted(unique, key=lambda value: (value[1], value[0], value[3], value[2]))


def _candidate(
    candidate_id: int,
    segment: tuple[int, int, int, int],
    estimated_thickness_pixels: float | None = None,
) -> WallLineCandidate:
    x1, y1, x2, y2 = segment
    delta_x = x2 - x1
    delta_y = y2 - y1
    angle = math.degrees(math.atan2(delta_y, delta_x)) % 180.0
    if math.isclose(angle, 0.0, abs_tol=0.5e-6) or math.isclose(
        angle,
        180.0,
        abs_tol=0.5e-6,
    ):
        angle = 0.0
    return WallLineCandidate(
        candidate_id=candidate_id,
        start=PixelPoint(x=x1, y=y1),
        end=PixelPoint(x=x2, y=y2),
        length_pixels=round(math.hypot(delta_x, delta_y), 6),
        angle_degrees=round(angle, 6),
        estimated_thickness_pixels=estimated_thickness_pixels,
    )


def _consolidate_wall_segments(
    segments: list[tuple[int, int, int, int, float, float]],
    width: int,
    height: int,
    max_gap: float,
    evidence_mask: np.ndarray | None = None,
) -> list[tuple[int, int, int, int, float]]:
    if not segments:
        return []

    def line_eq(s: tuple[int, int, int, int, float, float]) -> tuple[float, float, float, float, float]:
        x1, y1, x2, y2, th, l = s
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        angle = math.degrees(math.atan2(dy, dx)) % 180.0
        if length == 0:
            return angle, 0.0, 0.0, 0.0, 0.0
        a = -dy / length
        b = dx / length
        c = -(a * x1 + b * y1)
        return angle, a, b, c, length

    canon = []
    for x1, y1, x2, y2, th, l in segments:
        if (y2, x2) < (y1, x1):
            x1, y1, x2, y2 = x2, y2, x1, y1
        canon.append((x1, y1, x2, y2, th, l))

    used = [False] * len(canon)
    merged: list[tuple[int, int, int, int, float]] = []
    indices = sorted(range(len(canon)), key=lambda i: canon[i][5], reverse=True)

    for i in indices:
        if used[i]:
            continue
        used[i] = True
        group = [canon[i]]
        ang1, a1, b1, c1, _ = line_eq(canon[i])
        tx = b1
        ty = -a1

        p1_start = canon[i][0] * tx + canon[i][1] * ty
        p1_end = canon[i][2] * tx + canon[i][3] * ty
        if p1_start > p1_end:
            p1_start, p1_end = p1_end, p1_start

        for j in indices:
            if used[j]:
                continue
            ang2, a2, b2, c2, _ = line_eq(canon[j])
            ang_diff = abs(ang1 - ang2)
            if ang_diff > 90:
                ang_diff = 180 - ang_diff
            if ang_diff > 4.0:
                continue

            x1j, y1j, x2j, y2j, _, _ = canon[j]
            d1 = abs(a1 * x1j + b1 * y1j + c1)
            d2 = abs(a1 * x2j + b1 * y2j + c1)
            if max(d1, d2) > max(6.0, canon[i][4] * 0.4):
                continue

            p2_start = x1j * tx + y1j * ty
            p2_end = x2j * tx + y2j * ty
            if p2_start > p2_end:
                p2_start, p2_end = p2_end, p2_start

            gap = max(0.0, max(p1_start, p2_start) - min(p1_end, p2_end))

            can_merge = False
            if gap <= max_gap:
                can_merge = True
            elif evidence_mask is not None and gap <= max(max_gap * 4, min(width, height) * 0.12):
                # Check if image evidence supports continuity across the gap
                gap_start = min(p1_end, p2_end)
                gap_end = max(p1_start, p2_start)
                num_gap_pts = max(3, int(round(gap)))
                t_samples = np.linspace(gap_start, gap_end, num_gap_pts)
                anchor_projection = canon[i][0] * tx + canon[i][1] * ty
                gx = np.round(canon[i][0] + (t_samples - anchor_projection) * tx).astype(int)
                gy = np.round(canon[i][1] + (t_samples - anchor_projection) * ty).astype(int)
                gx = np.clip(gx, 0, width - 1)
                gy = np.clip(gy, 0, height - 1)
                ink_support = np.mean(evidence_mask[gy, gx] > 0)
                if ink_support >= 0.95:
                    can_merge = True

            if can_merge:
                group.append(canon[j])
                used[j] = True
                p1_start = min(p1_start, p2_start)
                p1_end = max(p1_end, p2_end)

        all_pts = []
        thicknesses = []
        for g in group:
            all_pts.append((g[0], g[1]))
            all_pts.append((g[2], g[3]))
            thicknesses.append(g[4])

        pts_arr = np.array(all_pts, dtype=np.float32)
        fit_line = cv2.fitLine(pts_arr, cv2.DIST_L2, 0, 0.01, 0.01)
        vx, vy, x0, y0 = (float(v) for v in fit_line.flatten())

        t_vals = [(px - x0) * vx + (py - y0) * vy for px, py in all_pts]
        t_min = min(t_vals)
        t_max = max(t_vals)

        x_start = int(round(x0 + t_min * vx))
        y_start = int(round(y0 + t_min * vy))
        x_end = int(round(x0 + t_max * vx))
        y_end = int(round(y0 + t_max * vy))

        x_start = max(0, min(width - 1, x_start))
        y_start = max(0, min(height - 1, y_start))
        x_end = max(0, min(width - 1, x_end))
        y_end = max(0, min(height - 1, y_end))

        if (y_end, x_end) < (y_start, x_start):
            x_start, y_start, x_end, y_end = x_end, y_end, x_start, y_start

        length = math.hypot(x_end - x_start, y_end - y_start)
        if length > 0:
            avg_thickness = round(float(np.mean(thicknesses)), 2)
            merged.append((x_start, y_start, x_end, y_end, avg_thickness))

    merged.sort(key=lambda item: (item[1], item[0], item[3], item[2]))
    return merged


def _thin_connected_strokes(mask: np.ndarray) -> np.ndarray:
    """Zhang-Suen thinning preserves connected strokes without a contrib dependency."""
    work = np.pad((mask > 0).astype(np.uint8), 1)
    for _ in range(128):
        changed = False
        for phase in (0, 1):
            center = work[1:-1, 1:-1]
            n = (work[:-2, 1:-1], work[:-2, 2:], work[1:-1, 2:],
                 work[2:, 2:], work[2:, 1:-1], work[2:, :-2],
                 work[1:-1, :-2], work[:-2, :-2])
            neighbors = sum(n)
            transitions = sum(((n[i] == 0) & (n[(i + 1) % 8] == 1)).astype(np.uint8)
                              for i in range(8))
            if phase == 0:
                preserve = (n[0] * n[2] * n[4] == 0) & (n[2] * n[4] * n[6] == 0)
            else:
                preserve = (n[0] * n[2] * n[6] == 0) & (n[0] * n[4] * n[6] == 0)
            remove = (center == 1) & (neighbors >= 2) & (neighbors <= 6) & (transitions == 1) & preserve
            if np.any(remove):
                center[remove] = 0
                changed = True
        if not changed:
            return work[1:-1, 1:-1] * 255
    raise _error("THINNING_BUDGET_EXCEEDED")


def _is_repeated_grid_member(
    segment: tuple[int, int, int, int, float], image: np.ndarray,
) -> bool:
    """Require three equally spaced observed parallels on EACH side, not a wall guess."""
    x1, y1, x2, y2, thickness = segment
    height, width = image.shape
    length = math.hypot(x2 - x1, y2 - y1)
    minimum_pitch = max(8, thickness * 2.5, min(width, height) * 0.015)
    maximum_pitch = min(length / 3, min(width, height) * 0.12)
    if maximum_pitch < minimum_pitch:
        return False
    radius = math.ceil(maximum_pitch * 3.2)
    offsets = np.arange(-radius, radius + 1)
    t = np.linspace(0.1, 0.9, min(256, max(16, round(length))))
    nx, ny = -(y2 - y1) / length, (x2 - x1) / length
    xs = np.rint(x1 + t[None, :] * (x2 - x1) + offsets[:, None] * nx).astype(int)
    ys = np.rint(y1 + t[None, :] * (y2 - y1) + offsets[:, None] * ny).astype(int)
    valid = (xs >= 0) & (xs < width) & (ys >= 0) & (ys < height)
    observed = valid & (image[np.clip(ys, 0, height - 1), np.clip(xs, 0, width - 1)] == 0)
    support = observed.mean(axis=1)
    active = support >= 0.55
    starts = np.flatnonzero(active & ~np.r_[False, active[:-1]])
    ends = np.flatnonzero(active & ~np.r_[active[1:], False])
    peaks = np.array([float(np.average(offsets[a:b + 1], weights=support[a:b + 1]))
                      for a, b in zip(starts, ends)])
    # Scanned lines wander by a few pixels; estimate pitch from both neighbors
    # instead of multiplying one side's offset error through the whole lattice.
    pitches = [float((right - left) / 2) for left in peaks if left < 0
               for right in peaks if right > 0
               if abs(right + left) <= (right - left) * 0.15]
    for pitch in pitches:
        if not minimum_pitch <= pitch <= maximum_pitch:
            continue
        tolerance = max(2.0, pitch * 0.15)
        if all(np.any(np.abs(peaks - multiple * pitch) <= tolerance)
               for multiple in (-3, -2, -1, 1, 2, 3)):
            # Parallel office partitions alone are not a ceiling grid. Require
            # multiple transverse strokes continuing through the candidate.
            left = (offsets < -thickness) & (offsets >= -pitch)
            right = (offsets > thickness) & (offsets <= pitch)
            if not left.any() or not right.any():
                continue
            crossings = ((observed[left].mean(axis=0) >= 0.55)
                         & (observed[right].mean(axis=0) >= 0.55))
            positions = t[crossings] * length
            if positions.size > 1 and positions[-1] - positions[0] >= pitch:
                return True
    return False


def _has_compact_parallel_bars(segment, image: np.ndarray) -> bool:
    """Reject compact bar glyphs, not short solid or double-outline wall strokes."""
    x1, y1, x2, y2, thickness = segment
    height, width = image.shape
    length = math.hypot(x2 - x1, y2 - y1)
    if length <= 0 or length > min(width, height) * 0.10:
        return False
    radius = max(2, round(thickness * 1.5))
    offsets = np.arange(-radius, radius + 1)
    t = np.linspace(0.2, 0.8, 64)
    dx, dy = (x2 - x1) / length, (y2 - y1) / length
    xs = np.rint(x1 + t[None, :] * (x2 - x1) - offsets[:, None] * dy).astype(int)
    ys = np.rint(y1 + t[None, :] * (y2 - y1) + offsets[:, None] * dx).astype(int)
    valid = (xs >= 0) & (xs < width) & (ys >= 0) & (ys < height)
    support = (valid & (image[np.clip(ys, 0, height - 1), np.clip(xs, 0, width - 1)] == 0)).mean(axis=1)
    active = support > 0.65
    starts = np.flatnonzero(active & ~np.r_[False, active[:-1]])
    ends = np.flatnonzero(active & ~np.r_[active[1:], False])
    widths = ends - starts + 1
    if len(widths) < 5:
        return False
    main = int(np.argmax(widths))
    if main < 2 or main > len(widths) - 3:
        return False
    center = (offsets[starts[main]] + offsets[ends[main]]) / 2
    companions = np.r_[widths[main - 2:main], widths[main + 1:main + 3]]
    return bool(abs(center) <= thickness * 0.5 and widths[main] >= 8
                and np.all(companions >= 2) and np.all(companions <= widths[main] / 3))


def _paired_edge_stroke_width(ink, xs, ys, nx, ny, radius):
    """Measure contiguous ink across an edge, not a thick wire's thin rim."""
    offsets = np.arange(-radius, radius + 1)
    px = np.rint(xs[:, None] + nx * offsets).astype(int)
    py = np.rint(ys[:, None] + ny * offsets).astype(int)
    height, width = ink.shape
    valid = (px >= 0) & (px < width) & (py >= 0) & (py < height)
    profiles = valid & (ink[np.clip(py, 0, height - 1), np.clip(px, 0, width - 1)] > 0)
    widths = []
    for profile in profiles:
        center = next((r for r in (radius, radius - 1, radius + 1) if profile[r]), None)
        if center is None:
            continue
        left = right = center
        while left > 0 and profile[left - 1]:
            left -= 1
        while right < radius * 2 and profile[right + 1]:
            right += 1
        widths.append(right - left + 1)
    return float(np.median(widths)) if widths else 0.0


def _outlined_wall_evidence(ink, parameters):
    """Bounded paired-ink evidence, not the two edges of one filled wire.

    Only activate the outlined drawing style when long observed pairs exist in
    two directions. Single strokes retain the legacy path on solid-wall plans.
    No sheet-specific coordinates or symbol classifications enter this test.
    """
    height, width = ink.shape
    minimum = max(16, round(parameters.minimum_line_length))
    try:
        raw = cv2.HoughLinesP(ink, 1, math.pi / 180, max(12, minimum // 2),
                              minLineLength=minimum, maxLineGap=round(parameters.maximum_line_gap))
    except Exception:
        raise _error("HOUGH_DETECTION_FAILED") from None
    if raw is None:
        return None
    lines = []
    for x1, y1, x2, y2 in _canonical_segments(raw, width=width, height=height):
        length = math.hypot(x2 - x1, y2 - y1)
        if length >= minimum:
            lines.append((length, x1, y1, x2, y2))
    lines = sorted(set(lines), key=lambda row: (-row[0], row[1:]))[:256]
    maximum_separation = min(32, max(4, min(width, height) * .03))
    long_span = max(minimum * 2, min(width, height) * .14)
    nearby_ink = cv2.dilate(ink, np.ones((3, 3), dtype=np.uint8))
    pairs = []
    strong_directions = set()
    for index, (length, x1, y1, x2, y2) in enumerate(lines):
        tx, ty = (x2 - x1) / length, (y2 - y1) / length
        for other_length, ax, ay, bx, by in lines[index + 1:]:
            alignment = abs(tx * (bx - ax) + ty * (by - ay)) / other_length
            if alignment < math.cos(math.radians(2)):
                continue
            da = -ty * (ax - x1) + tx * (ay - y1)
            db = -ty * (bx - x1) + tx * (by - y1)
            separation = abs((da + db) / 2)
            if not 2 <= separation <= maximum_separation or abs(da - db) > max(1, separation * .3):
                continue
            ta, tb = tx * (ax - x1) + ty * (ay - y1), tx * (bx - x1) + ty * (by - y1)
            start, end = max(0, min(ta, tb)), min(length, max(ta, tb))
            if end - start < max(minimum, min(length, other_length) * .6):
                continue
            samples = np.linspace(start + 1, end - 1, 64)
            distance = (da + db) / 2
            px, py = x1 + samples * tx, y1 + samples * ty
            qx, qy = px - ty * distance, py + tx * distance
            mx, my = (px + qx) / 2, (py + qy) / 2
            coordinates = [np.rint(v).astype(int) for v in (px, py, qx, qy, mx, my)]
            sx, sy, ex, ey, cx, cy = coordinates
            if (min(sx.min(), ex.min(), cx.min()) < 0 or max(sx.max(), ex.max(), cx.max()) >= width
                    or min(sy.min(), ey.min(), cy.min()) < 0 or max(sy.max(), ey.max(), cy.max()) >= height):
                continue
            # A wire's Canny edges enclose black, not a persistent white cavity.
            if (np.mean((nearby_ink[sy, sx] > 0) & (nearby_ink[ey, ex] > 0)) < .8
                    or np.mean(ink[cy, cx] == 0) < .45):
                continue
            radius = min(12, max(3, round(separation / 2)))
            edge_widths = [_paired_edge_stroke_width(ink, xx, yy, -ty, tx, radius)
                           for xx, yy in ((px, py), (qx, qy))]
            if min(edge_widths) == 0 or max(edge_widths) > min(edge_widths) * 2.2:
                # A bold circuit beside one thin wall outline is not a wall pair.
                continue
            if separation > max(edge_widths) * 4 and max(edge_widths) > min(edge_widths) * 1.6:
                # Widely separated, differently weighted strokes are weak pair
                # evidence (e.g. a circuit beside the building boundary). Allow
                # one-pixel scan differences on the close wall-outline pairs.
                continue
            center = (x1 - ty * distance / 2, y1 + tx * distance / 2)
            endpoints = tuple((round(center[0] + t * tx), round(center[1] + t * ty)) for t in (start, end))
            pairs.append((endpoints, separation + 1))
            if end - start >= long_span:
                strong_directions.add('horizontal' if abs(tx) > abs(ty) else 'vertical')
    if len(strong_directions) != 2:
        return None
    mask = np.zeros_like(ink)
    for (start, end), thickness in pairs:
        cv2.line(mask, start, end, 255, max(2, round(thickness)))
    return mask, float(np.median([thickness for _, thickness in pairs]))


def _detect_structural_wall_lines(
    image: np.ndarray,
    parameters: WallDetectionParameters,
    continuity_image: np.ndarray | None = None,
) -> list[tuple[int, int, int, int, float]]:
    height, width = image.shape
    if np.all(image == image.flat[0]):
        return []

    ink = np.where(image == 0, 255, 0).astype(np.uint8)
    if cv2.countNonZero(ink) == 0:
        return []
    outlined = _outlined_wall_evidence(ink, parameters)

    # Scans often depict walls as two dark outlines with a lighter fill. A small
    # page-scaled close restores that stroke before measuring its centerline.
    # Keep the radius below the configured continuity gap; door-sized gaps remain.
    close_size = max(1, min(round(min(width, height) * 0.008), round(parameters.maximum_line_gap * 2 + 1)))
    if close_size % 2 == 0:
        close_size += 1
    if close_size > 1:
        ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE,
                             cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_size, close_size)))

    if outlined is not None:
        outline_mask, outline_width = outlined
        # Keep broad solid/hatched structure as well. On an outlined plan a
        # thinner single stroke is insufficient wall evidence, even if long.
        solid_radius = max(2.5, outline_width * .5)
        solid_core = cv2.distanceTransform(ink, cv2.DIST_L2, 5) >= solid_radius
        solid_kernel = round(solid_radius) * 2 + 1
        solid_mask = cv2.dilate(solid_core.astype(np.uint8) * 255,
                               cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (solid_kernel, solid_kernel)))
        ink = cv2.bitwise_or(outline_mask, cv2.bitwise_and(ink, solid_mask))

    dist = cv2.distanceTransform(ink, cv2.DIST_L2, 5)
    continuity_dist = None
    if continuity_image is not None and outlined is None:
        continuity_ink = cv2.bitwise_not(continuity_image)
        if close_size > 1:
            continuity_ink = cv2.morphologyEx(
                continuity_ink, cv2.MORPH_CLOSE,
                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_size, close_size)),
            )
        continuity_dist = cv2.distanceTransform(continuity_ink, cv2.DIST_L2, 5)
    ink_dist = dist[ink > 0]
    if len(ink_dist) == 0:
        return []

    # Compact solid fixtures must not set the page-wide wall stroke cutoff.
    # Measure sustained strokes instead; retain the general fallback for scans
    # containing only diagonal evidence. This is still advisory CV, not semantics.
    span = max(3, round(max(parameters.minimum_line_length * 2, min(width, height) * 0.16)))
    horizontal = cv2.morphologyEx(ink, cv2.MORPH_OPEN,
                                 cv2.getStructuringElement(cv2.MORPH_RECT, (span, 1)))
    vertical = cv2.morphologyEx(ink, cv2.MORPH_OPEN,
                               cv2.getStructuringElement(cv2.MORPH_RECT, (1, span)))
    sustained = cv2.bitwise_or(horizontal, vertical)
    sustained_radii = dist[sustained > 0]
    max_radius = float(np.max(ink_dist))
    if parameters.min_stroke_radius is not None:
        min_stroke_radius = float(parameters.min_stroke_radius)
    elif sustained_radii.size:
        stroke_radius = float(np.percentile(sustained_radii, 90))
        min_stroke_radius = max(1.25, stroke_radius * 0.4) if stroke_radius >= 2 else max(0.5, stroke_radius * 0.6)
    elif max_radius >= 4.0:
        p90 = float(np.percentile(ink_dist, 90))
        min_stroke_radius = max(2.5, min(p90 * 0.6, max_radius * 0.25))
    else:
        min_stroke_radius = max(0.5, max_radius * 0.4)

    min_wall_length = float(parameters.minimum_line_length)
    max_gap = float(parameters.maximum_line_gap)

    core = (dist >= min_stroke_radius).astype(np.uint8) * 255
    if cv2.countNonZero(core) == 0:
        return []

    k_size = int(round(2 * min_stroke_radius + 1))
    if k_size % 2 == 0:
        k_size += 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_size, k_size))
    structural_ink = cv2.bitwise_and(cv2.dilate(core, kernel), ink)

    min_span = max(min_wall_length, min(width, height) * 0.12)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(structural_ink, 8)
    clean_structural = np.zeros_like(structural_ink)

    for label in range(1, num_labels):
        comp_w = int(stats[label, cv2.CC_STAT_WIDTH])
        comp_h = int(stats[label, cv2.CC_STAT_HEIGHT])
        area = int(stats[label, cv2.CC_STAT_AREA])
        span = max(comp_w, comp_h)
        if span < min_span:
            continue
        if span < min(width, height) * 0.05 and area < (min_span * min_stroke_radius * 4):
            continue
        clean_structural[labels == label] = 255

    if cv2.countNonZero(clean_structural) == 0:
        return []

    skeleton = _thin_connected_strokes(clean_structural)

    vote_threshold = max(10, int(round(min_wall_length * 0.35)))
    try:
        lines = cv2.HoughLinesP(
            skeleton,
            parameters.hough_rho,
            math.radians(parameters.hough_theta_degrees),
            vote_threshold,
            minLineLength=int(round(min_wall_length)),
            maxLineGap=int(round(max_gap)),
        )
    except Exception:
        raise _error("HOUGH_DETECTION_FAILED") from None

    if lines is None or len(lines) == 0:
        return []

    raw_segments = []
    for line in lines:
        row = line[0] if (line.ndim == 2 or line.shape[0] == 1) else line
        x1, y1, x2, y2 = (int(v) for v in row[:4])
        length = math.hypot(x2 - x1, y2 - y1)
        if length < min_wall_length:
            continue

        num_samples = max(2, int(round(length)))
        xs = np.linspace(x1, x2, num_samples).astype(int)
        ys = np.linspace(y1, y2, num_samples).astype(int)
        valid = (xs >= 0) & (xs < width) & (ys >= 0) & (ys < height)
        if not np.any(valid):
            continue

        radii = dist[ys[valid], xs[valid]]
        median_radius = float(np.median(radii))
        if median_radius < min_stroke_radius * 0.75:
            continue

        thickness = round(median_radius * 2.0, 2)
        # Hough voting can stop before an observed stroke ends. Recover only
        # contiguous structural pixels; never extrapolate across a white opening.
        dx, dy = (x2 - x1) / length, (y2 - y1) / length
        extension_limit = max(2, round(min_wall_length),
                              round(min(width, height) * .12) if outlined is not None else 0)
        extended = []
        for ox, oy, direction in ((x1, y1, -1), (x2, y2, 1)):
            last = (ox, oy)
            for step in range(1, extension_limit + 1):
                px, py = round(ox + direction * dx * step), round(oy + direction * dy * step)
                if not (0 <= px < width and 0 <= py < height):
                    break
                supported = bool(clean_structural[py, px])
                if outlined is not None and not supported:
                    # Follow slight raster centerline jitter only within already
                    # qualified wall ink; raw wiring cannot extend this stroke.
                    radius = min(2, max(1, round(thickness * .35)))
                    for offset in range(-radius, radius + 1):
                        qx, qy = round(px - dy * offset), round(py + dx * offset)
                        if 0 <= qx < width and 0 <= qy < height and clean_structural[qy, qx]:
                            supported = True
                            break
                if not supported:
                    break
                last = (px, py)
            extended.append(last)
        (x1, y1), (x2, y2) = extended
        length = math.hypot(x2 - x1, y2 - y1)
        raw_segments.append((x1, y1, x2, y2, thickness, length))

    consolidated = _consolidate_wall_segments(
        raw_segments, width, height, max_gap, evidence_mask=clean_structural
    )
    if outlined is not None:
        # After fitting the outline bands, merge duplicate centerlines that now
        # overlap. Still require the same observed mask across any actual gap.
        consolidated = _consolidate_wall_segments(
            [(x1, y1, x2, y2, thickness, math.hypot(x2 - x1, y2 - y1))
             for x1, y1, x2, y2, thickness in consolidated],
            width, height, max_gap, evidence_mask=clean_structural)
    if continuity_dist is not None:
        recovered = []
        for x1, y1, x2, y2, thickness in consolidated:
            length = math.hypot(x2 - x1, y2 - y1)
            if length >= min(width, height) * 0.15:
                dx, dy = (x2 - x1) / length, (y2 - y1) / length
                endpoints = []
                for ox, oy, direction in ((x1, y1, -1), (x2, y2, 1)):
                    last = (ox, oy)
                    for step in range(1, round(min(width, height) * 0.12) + 1):
                        px, py = round(ox + direction * dx * step), round(oy + direction * dy * step)
                        if not (0 <= px < width and 0 <= py < height):
                            break
                        if continuity_dist[py, px] < max(min_stroke_radius, thickness * 0.25):
                            break
                        last = (px, py)
                    endpoints.append(last)
                (x1, y1), (x2, y2) = endpoints
            recovered.append((x1, y1, x2, y2, thickness, math.hypot(x2 - x1, y2 - y1)))
        consolidated = _consolidate_wall_segments(recovered, width, height, max_gap)
    return [segment for segment in consolidated
            if not _is_repeated_grid_member(segment, image)
            and not _has_compact_parallel_bars(segment, image)]


def detect_wall_lines(
    source: "PreprocessedImage | np.ndarray",
    *,
    parameters: WallDetectionParameters | None = None,
    continuity_source: np.ndarray | None = None,
) -> WallDetectionResult:
    """Return deterministic candidate segments in raw top-left pixel space."""
    try:
        selected = (
            WallDetectionParameters()
            if parameters is None
            else parameters
        )
    except WallDetectionConfigurationError:
        raise _error("INVALID_CONFIGURATION") from None
    if not isinstance(selected, WallDetectionParameters):
        raise _error("INVALID_CONFIGURATION")
    image = _extract_binary_image(source)
    continuity_image = None
    if continuity_source is not None:
        continuity_image = _extract_binary_image(continuity_source)
        if continuity_image.shape != image.shape:
            raise _error("INVALID_DTYPE_OR_SHAPE")
    height, width = image.shape
    if np.all(image == image.flat[0]):
        return _empty_result(width, height)

    if selected.structural_mode:
        algorithm_name = "structural_stroke_centerline"
        segments_with_th = _detect_structural_wall_lines(image, selected, continuity_image)
        truncated = len(segments_with_th) > selected.maximum_candidates
        limited = segments_with_th[: selected.maximum_candidates]
        candidates = tuple(
            _candidate(
                candidate_id,
                (seg[0], seg[1], seg[2], seg[3]),
                estimated_thickness_pixels=seg[4],
            )
            for candidate_id, seg in enumerate(limited, start=1)
        )
        return WallDetectionResult(
            coordinate_space=CoordinateSpace(width=width, height=height),
            algorithm=algorithm_name,
            truncated=truncated,
            candidates=candidates,
        )

    try:
        edges = cv2.Canny(
            image.copy(),
            selected.canny_low_threshold,
            selected.canny_high_threshold,
            apertureSize=selected.canny_aperture_size,
        )
    except Exception:
        raise _error("EDGE_DETECTION_FAILED") from None
    if (
        not isinstance(edges, np.ndarray)
        or edges.dtype != np.uint8
        or edges.shape != image.shape
    ):
        raise _error("EDGE_DETECTION_FAILED")
    try:
        lines = cv2.HoughLinesP(
            edges,
            selected.hough_rho,
            math.radians(selected.hough_theta_degrees),
            selected.hough_vote_threshold,
            minLineLength=selected.minimum_line_length,
            maxLineGap=selected.maximum_line_gap,
        )
    except Exception:
        raise _error("HOUGH_DETECTION_FAILED") from None

    segments = _canonical_segments(lines, width=width, height=height)
    truncated = len(segments) > selected.maximum_candidates
    limited = segments[: selected.maximum_candidates]
    candidates = tuple(
        _candidate(candidate_id, segment)
        for candidate_id, segment in enumerate(limited, start=1)
    )
    return WallDetectionResult(
        coordinate_space=CoordinateSpace(width=width, height=height),
        algorithm=ALGORITHM,
        truncated=truncated,
        candidates=candidates,
    )
