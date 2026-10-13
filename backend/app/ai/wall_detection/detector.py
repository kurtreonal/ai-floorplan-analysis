from __future__ import annotations

import math
import heapq
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
from app.ai.wall_detection.junctions import snap_observed_junctions,unique_wall_spans
from app.ai.wall_detection.band_geometry import refine_filled_bands

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
            distance_limit=max(6.0,canon[i][4]*.4) if evidence_mask is None else max(1.0,max(canon[i][4],canon[j][4])*.6)
            if max(d1, d2) > distance_limit:
                continue

            p2_start = x1j * tx + y1j * ty
            p2_end = x2j * tx + y2j * ty
            if p2_start > p2_end:
                p2_start, p2_end = p2_end, p2_start

            gap = max(0.0, max(p1_start, p2_start) - min(p1_end, p2_end))

            if evidence_mask is not None:
                # Spatial tolerance is not proof of a common wall band. Prevent
                # averaging separate parallel walls or closing white openings.
                low,high=max(p1_start,p2_start),min(p1_end,p2_end)
                if high>=low:
                    projections=np.linspace(low,high,max(3,min(128,round(high-low)+1)))
                    anchor_projection=canon[i][0]*tx+canon[i][1]*ty
                    left=np.array(canon[i][:2])+((projections-anchor_projection)[:,None]*np.array([tx,ty]))
                    normal=np.array([a1,b1])
                    offset=np.mean([a1*x1j+b1*y1j+c1,a1*x2j+b1*y2j+c1])
                    corridor=np.array([left+normal*offset*t for t in np.linspace(0,1,5)])
                    xy=np.rint(corridor).astype(int)
                    if ((xy<0).any() or (xy[...,0]>=width).any() or (xy[...,1]>=height).any()
                            or np.mean(evidence_mask[xy[...,1],xy[...,0]]>0)<.95):continue
                elif gap>.5:
                    sample=np.linspace(p1_end,p2_start,max(3,math.ceil(gap)+1)) if p2_start>p1_end else np.linspace(p2_end,p1_start,max(3,math.ceil(gap)+1))
                    anchor_projection=canon[i][0]*tx+canon[i][1]*ty
                    xy=np.rint(np.array(canon[i][:2])+(sample-anchor_projection)[:,None]*np.array([tx,ty])).astype(int)
                    if ((xy<0).any() or (xy[:,0]>=width).any() or (xy[:,1]>=height).any()
                            or np.mean(evidence_mask[xy[:,1],xy[:,0]]>0)<.95):continue

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


def _thinning_removal_tables():
    """Encode the unchanged Zhang-Suen predicates for all eight neighbors."""
    codes = np.arange(256, dtype=np.uint16)
    n = tuple(((codes >> bit) & 1).astype(np.uint8) for bit in range(8))
    neighbors = sum(n)
    transitions = sum(((n[i] == 0) & (n[(i + 1) % 8] == 1)).astype(np.uint8)
                      for i in range(8))
    common = (neighbors >= 2) & (neighbors <= 6) & (transitions == 1)
    tables = (common & (n[0] * n[2] * n[4] == 0) & (n[2] * n[4] * n[6] == 0),
              common & (n[0] * n[2] * n[6] == 0) & (n[0] * n[4] * n[6] == 0))
    for table in tables:
        table.setflags(write=False)
    return tables


_THINNING_REMOVAL_TABLES = _thinning_removal_tables()


def _thin_connected_strokes(mask: np.ndarray) -> np.ndarray:
    """Same synchronous thinning and 128-round bound; avoid inactive pixels."""
    work = np.pad((mask > 0).astype(np.uint8), 1)
    height, width = mask.shape
    x, y, box_width, box_height = cv2.boundingRect(work[1:-1, 1:-1])
    if not box_width:
        return np.zeros_like(mask, dtype=np.uint8)
    x0, x1, y0, y1 = x+1, x+box_width+1, y+1, y+box_height+1
    for _ in range(128):
        changed = False
        bx0, by0, bx1, by1 = width+1, height+1, 1, 1
        for phase in (0, 1):
            center = work[y0:y1, x0:x1]
            n = (work[y0-1:y1-1, x0:x1], work[y0-1:y1-1, x0+1:x1+1],
                 work[y0:y1, x0+1:x1+1], work[y0+1:y1+1, x0+1:x1+1],
                 work[y0+1:y1+1, x0:x1], work[y0+1:y1+1, x0-1:x1-1],
                 work[y0:y1, x0-1:x1-1], work[y0-1:y1-1, x0-1:x1-1])
            code = n[0].copy()
            for bit in range(1, 8):
                code |= n[bit] << bit
            remove = _THINNING_REMOVAL_TABLES[phase][code] & (center == 1)
            if np.any(remove):
                center[remove] = 0
                changed = True
                rows, cols = np.any(remove, axis=1), np.any(remove, axis=0)
                by0 = min(by0, y0+int(np.argmax(rows)))
                by1 = max(by1, y1-int(np.argmax(rows[::-1])))
                bx0 = min(bx0, x0+int(np.argmax(cols)))
                bx1 = max(bx1, x1-int(np.argmax(cols[::-1])))
        if not changed:
            return work[1:-1, 1:-1] * 255
        # Only neighbors of deletions can change eligibility. Two phase steps
        # can propagate two pixels; keep that halo and synchronous deletion.
        x0, x1 = max(1, bx0-2), min(width+1, bx1+2)
        y0, y1 = max(1, by0-2), min(height+1, by1+2)
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


def _parallel_ink_runs(segment, image: np.ndarray):
    """Bounded original-pixel transverse profile for sustained parallel ink."""
    x1, y1, x2, y2, thickness = segment
    height, width = image.shape
    length = math.hypot(x2 - x1, y2 - y1)
    if length <= 0:
        return np.array([]), np.array([]), np.array([])
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
    centers = (offsets[starts] + offsets[ends]) / 2
    gaps = starts[1:] - ends[:-1] - 1
    return widths, centers, gaps


def _regular_thin_parallel_bars(segment, image: np.ndarray) -> bool:
    widths, centers, gaps = _parallel_ink_runs(segment, image)
    if len(widths) < 3:
        return False
    spacing = np.diff(centers)
    return bool(max(widths) <= max(2, segment[4] * .3)
                and max(widths) <= min(widths) * 2
                and np.all(gaps >= min(widths))
                and max(spacing) <= min(spacing) * 1.25
                and centers[0] < 0 < centers[-1])


def _has_compact_parallel_bars(segment, image: np.ndarray) -> bool:
    """Reject compact bar glyphs, not short solid or double-outline wall strokes."""
    x1, y1, x2, y2, thickness = segment
    length = math.hypot(x2 - x1, y2 - y1)
    if length <= 0 or length > min(image.shape) * .16:
        return False
    widths, centers, gaps = _parallel_ink_runs(segment, image)
    # Three equally thin, separated bars are a compact fixture pattern. Closing
    # can fill their gaps into one apparent wall band; inspect original pixels,
    # not that manufactured band. A solid stroke or two wall outlines do not
    # satisfy this evidence, and long parallel partitions remain untouched.
    if len(widths) == 3:
        spacing = np.diff(centers)
        if (abs(centers[1]) <= thickness * .5
                and max(widths) <= max(2, length * .05)
                and max(widths) <= min(widths) * 2
                and np.all(gaps >= min(widths))
                and max(spacing) <= min(spacing) * 1.25):
            return True
        # Scanned fluorescent/troffer glyphs can have one dark filled body and
        # only one thin outline on each side, rather than two companion bars.
        # Require a compact, centered, symmetric three-stripe pattern; a plain
        # solid wall and an empty double-outline wall still lack this evidence.
        if (abs(centers[1]) <= thickness * .5
                and widths[1] >= max(8, thickness * .4)
                and max(widths[0], widths[2]) <= widths[1] / 3
                and np.all(gaps >= 1)
                and max(spacing) <= min(spacing) * 1.25
                and length <= thickness * 6):
            return True
    # A fixture does not change identity when the surrounding drawing is cropped
    # more tightly. Beyond the old page-relative limit, require a compact body
    # aspect ratio as well as the full two-companion-on-each-side evidence.
    if length > min(image.shape) * .10 and length > thickness * 6:
        return False
    if len(widths) < 5:
        return False
    main = int(np.argmax(widths))
    if main < 2 or main > len(widths) - 3:
        return False
    center = centers[main]
    companions = np.r_[widths[main - 2:main], widths[main + 1:main + 3]]
    # One-pixel outer strokes survive native scan thresholding; requiring two
    # made the same visible glyph pass at 2x but fail at its original resolution.
    return bool(abs(center) <= thickness * 0.5 and widths[main] >= 8
                and np.all(companions >= 1) and np.all(companions <= widths[main] / 3))


def _has_compact_annotated_outline(segment, image: np.ndarray) -> bool:
    """Identify a short closed glyph box using its observed interior mark.

    Plain hollow walls and full-width wiring crossings lack a localized partial-
    width mark. Inspect original pixels after wall fitting so rejecting a glyph
    cannot change the votes or thickness statistics of surrounding walls.
    """
    x1, y1, x2, y2, thickness = segment
    length = math.hypot(x2-x1, y2-y1)
    if length <= 0 or length > min(image.shape) * .16:
        return False
    widths, centers, _ = _parallel_ink_runs(segment, image)
    if len(widths) != 2 or not centers[0] < 0 < centers[1]:
        return False
    separation = centers[1]-centers[0]
    if (not 3 <= length/separation <= 12 or max(widths) > separation*.3
            or max(widths) > min(widths)*2):
        return False
    low = centers[0]+widths[0]/2+.5
    high = centers[1]-widths[1]/2-.5
    if high-low < 2:
        return False
    across = np.linspace(low, high, max(3, math.floor(high-low)+1))
    padding = max(2, math.ceil(min(thickness*.6,length*.2)))
    along = np.arange(-padding, math.ceil(length)+padding+1, dtype=float)
    dx, dy = (x2-x1)/length, (y2-y1)/length
    xs = np.rint(x1+along[:,None]*dx-across[None,:]*dy).astype(int)
    ys = np.rint(y1+along[:,None]*dy+across[None,:]*dx).astype(int)
    if ((xs<0)|(xs>=image.shape[1])|(ys<0)|(ys>=image.shape[0])).any():
        return False
    occupied = np.mean(image[ys,xs]==0, axis=1)
    # A rasterized transverse cap can stagger by a pixel along the axis. Search
    # that small ORIGINAL-pixel neighborhood at caps only; keep interior marks
    # undilated so plain wiring crossings do not acquire glyph-like texture.
    cap_ink = image[ys,xs]==0
    jitter = max(1, math.floor(max(widths)/2))
    cap_support = cap_ink.copy()
    for offset in range(1, jitter+1):
        cap_support[offset:] |= cap_ink[:-offset]
        cap_support[:-offset] |= cap_ink[offset:]
    cap_occupied = np.mean(cap_support, axis=1)
    first = np.flatnonzero((np.abs(along)<=padding)&(cap_occupied>=.8))
    last = np.flatnonzero((np.abs(along-length)<=padding)&(cap_occupied>=.8))
    if first.size == 0 or last.size == 0:
        return False
    start_cap = along[first[np.argmin(np.abs(along[first]))]]
    end_cap = along[last[np.argmin(np.abs(along[last]-length))]]
    margin = max(2, math.ceil(max(widths)))
    interior = (along>start_cap+margin)&(along<end_cap-margin)
    # Isolated raster-edge pixels are insufficient interior glyph evidence.
    partial = along[interior&(occupied>=.2)&(occupied<.8)]
    minimum_mark = max(3, math.ceil(max(widths)*2))
    if len(partial) < minimum_mark:
        return False
    # A small number/mark occupies one bounded part of the box. Repeated or
    # continuous hatching and dispersed crossings are insufficient evidence.
    clusters = np.split(partial,
        np.flatnonzero(np.diff(partial)>max(2,math.ceil(max(widths)*1.5)))+1)
    clusters = [cluster for cluster in clusters if len(cluster)>=max(2,max(widths))]
    marked_rows = sum(len(cluster) for cluster in clusters)
    for cluster in clusters:
        mark_span = cluster[-1]-cluster[0]+1
        if (len(cluster) >= minimum_mark and len(cluster) >= marked_rows*.65
                and mark_span <= min(length*.45,separation*2.5)
                and len(cluster)/mark_span >= .5):
            # Rasterized wires crossing a hollow wall also leave partial rows.
            # An interior glyph must include ink beyond those observed straight
            # crossings. Check both exterior flanks with one-pixel scan jitter.
            crossing = np.ones(cluster.shape, dtype=bool)
            for edge, side in ((centers[0],-1),(centers[1],1)):
                flank = edge + side*np.linspace(separation*.5,separation*2,
                                               min(64,max(3,math.ceil(separation*1.5))))
                observed = np.zeros((len(cluster),len(flank)), dtype=bool)
                for jitter_offset in (-1,0,1):
                    lx = np.rint(x1+(cluster[:,None]+jitter_offset)*dx-flank[None,:]*dy).astype(int)
                    ly = np.rint(y1+(cluster[:,None]+jitter_offset)*dy+flank[None,:]*dx).astype(int)
                    valid = (lx>=0)&(lx<image.shape[1])&(ly>=0)&(ly<image.shape[0])
                    if not valid.all():
                        return False
                    observed |= image[ly,lx]==0
                crossing &= observed.mean(axis=1)>=.65
            if not crossing.all():
                return True
    return False


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


def _without_detached_enclosing_bands(pairs):
    """Exclude paired frame rules only when they bracket a joined wall network.

    Disconnection alone is insufficient: preserve isolated walls, parallel
    partitions, and any band with an observed perpendicular wall junction.
    Projections along each band keep this evidence independent of page rotation.
    """
    # A dense drawing may offer thousands of overlapping pair hypotheses. Keep
    # this optional enclosure check bounded and retain evidence on budget exit.
    if len(pairs) > 512:
        return pairs
    geometry = []
    for (start, end), thickness in pairs:
        start, end = np.asarray(start, dtype=float), np.asarray(end, dtype=float)
        length = float(np.linalg.norm(end - start))
        geometry.append((start, end, (end - start) / length, thickness))
    joined = set()
    for index, (start, end, direction, thickness) in enumerate(geometry):
        for other in range(index + 1, len(geometry)):
            a, b, transverse, other_thickness = geometry[other]
            if abs(float(direction @ transverse)) > .5:
                continue
            tolerance = (thickness + other_thickness) / 2 + 2
            # An endpoint meeting the body of the other band is an L/T junction.
            for point, origin, finish, axis in ((start, a, b, transverse), (end, a, b, transverse),
                                               (a, start, end, direction), (b, start, end, direction)):
                delta = point - origin
                projection = float(delta @ axis)
                distance = abs(float(delta[0] * axis[1] - delta[1] * axis[0]))
                if distance <= tolerance and -tolerance <= projection <= np.linalg.norm(finish - origin) + tolerance:
                    joined.update((index, other))
                    break
    if len(joined) < 4:
        return pairs
    network = np.asarray([point for index in joined for point in geometry[index][:2]])
    rejected = set()
    for index, (start, end, direction, thickness) in enumerate(geometry):
        if index in joined:
            continue
        normal = np.array([-direction[1], direction[0]])
        along, across = network @ direction, network @ normal
        lo, hi = float(along.min()), float(along.max())
        low, high = float(across.min()), float(across.max())
        margin = thickness + 2
        span = sorted((float(start @ direction), float(end @ direction)))
        side = float(((start + end) / 2) @ normal)
        if span[0] > lo + margin or span[1] < hi - margin:
            continue
        if not (side < low - margin or side > high + margin):
            continue
        for other, (a, b, axis, other_thickness) in enumerate(geometry):
            if other == index or other in joined or abs(float(direction @ axis)) < math.cos(math.radians(2)):
                continue
            other_span = sorted((float(a @ direction), float(b @ direction)))
            other_side = float(((a + b) / 2) @ normal)
            if (other_span[0] <= lo + other_thickness + 2 and other_span[1] >= hi - other_thickness - 2
                    and ((side < low - margin and other_side > high + other_thickness + 2)
                         or (side > high + margin and other_side < low - other_thickness - 2))):
                rejected.update((index, other))
    return [pair for index, pair in enumerate(pairs) if index not in rejected]


def _recover_paired_band_ends(pairs, ink, continuity_ink, minimum):
    """Recover an established band from observed mates, never project through air."""
    if len(pairs) > 512:
        return []
    height, width = ink.shape
    limit = max(2, round(min(width, height) * .15))
    nearby = cv2.dilate(ink, np.ones((3, 3), dtype=np.uint8))
    continuity_nearby = (cv2.dilate(continuity_ink, np.ones((3, 3), dtype=np.uint8))
                         if continuity_ink is not None else None)
    geometry = []
    for (start, end), thickness in pairs:
        start, end = np.asarray(start, dtype=float), np.asarray(end, dtype=float)
        length = float(np.linalg.norm(end-start))
        if length > 0:
            geometry.append((start, end, (end-start)/length, thickness, length))
    recovered = []
    for start, end, axis, thickness, length in geometry:
        normal = np.array([-axis[1], axis[0]])
        edge_offset = (thickness-1)/2
        for origin, direction in ((start,-1), (end,1)):
            # One surviving outline is sufficient only between two already
            # established collinear bands of the same observed width.
            brackets = []
            for a,b,other_axis,other_thickness,other_length in geometry:
                if (other_length < minimum or abs(float(axis @ other_axis)) < math.cos(math.radians(2))
                        or abs(thickness-other_thickness) > max(1,thickness*.25)
                        or max(abs(float((a-start) @ normal)),abs(float((b-start) @ normal))) > max(1,thickness*.2)):
                    continue
                projections = sorted((float((a-origin) @ axis)*direction,
                                      float((b-origin) @ axis)*direction))
                if 0 < projections[0] <= limit:
                    brackets.append(projections[0])
            bracket = min(brackets) if brackets else 0
            last = origin
            for step in range(1,limit+1):
                point = origin + axis*direction*step
                edges = [np.rint(point+normal*side*edge_offset).astype(int) for side in (-1,1)]
                center = np.rint(point).astype(int)
                if any(not (0 <= p[0] < width and 0 <= p[1] < height) for p in (*edges,center)):
                    break
                primary = [bool(nearby[p[1],p[0]]) for p in edges]
                primary_cavity = ink[center[1],center[0]] == 0
                paired = all(primary) and primary_cavity
                bracketed_mate = bracket and step <= math.ceil(bracket) and any(primary) and primary_cavity
                faint_pair = (continuity_nearby is not None
                              and all(continuity_nearby[p[1],p[0]] for p in edges)
                              and continuity_ink[center[1],center[0]] == 0)
                if not (paired or bracketed_mate or faint_pair):
                    break
                last = point
            if float(np.linalg.norm(last-origin)) > 1:
                recovered.append(((tuple(np.rint(origin).astype(int)),tuple(np.rint(last).astype(int))),thickness))
    return recovered


def _has_intermittent_middle_bar(segment,image):
    """Three stripes qualify only when the observed middle stroke has real gaps."""
    widths,centers,_ = _parallel_ink_runs(segment,image)
    if len(widths) != 3:
        return False
    x1,y1,x2,y2,_ = segment
    length = math.hypot(x2-x1,y2-y1)
    nx,ny = -(y2-y1)/length,(x2-x1)/length
    t = np.linspace(.1,.9,64)
    middle_ink = np.zeros(t.shape,dtype=bool)
    for offset in (centers[1]-1,centers[1],centers[1]+1):
        xs = np.rint(x1+t*(x2-x1)+nx*offset).astype(int)
        ys = np.rint(y1+t*(y2-y1)+ny*offset).astype(int)
        if ((xs<0)|(xs>=image.shape[1])|(ys<0)|(ys>=image.shape[0])).any():
            return False
        middle_ink |= image[ys,xs]==0
    return float(np.mean(~middle_ink)) >= .1


def _has_repeated_band_ties(pair, ink, minimum):
    """Original transverse ties distinguish a subdivided hollow band from bars.

    Require three separated ties distributed across a long narrow band. Two
    end caps of a glyph/bundle, closing-created ink and missing mates cannot
    qualify. This remains geometric evidence, not architectural approval.
    """
    (a, b), thickness = pair
    length = math.dist(a, b)
    if length < max(minimum * 2, min(ink.shape) * .14) or length < thickness * 12:
        return False
    axis = (np.asarray(b, float) - a) / length
    normal = np.array([-axis[1], axis[0]])
    along = np.arange(math.ceil(length) + 1)
    across = np.linspace(-(thickness-1)*.35, (thickness-1)*.35,
                         max(3, min(64, math.ceil(thickness))))
    points = np.asarray(a)[None,None,:] + along[:,None,None]*axis + across[None,:,None]*normal
    xy = np.rint(points).astype(int)
    valid = ((xy[:,:,0]>=0)&(xy[:,:,0]<ink.shape[1])
             &(xy[:,:,1]>=0)&(xy[:,:,1]<ink.shape[0]))
    if not valid.all():
        return False
    tied = np.mean(ink[xy[:,:,1],xy[:,:,0]]>0,axis=1) >= .85
    rows = np.flatnonzero(tied)
    if not rows.size:
        return False
    clusters = np.split(rows,np.flatnonzero(np.diff(rows)>1)+1)
    positions = [float(np.mean(cluster)) for cluster in clusters]
    separated = []
    for position in positions:
        if not separated or position-separated[-1] >= max(minimum,thickness*3):
            separated.append(position)
    return len(separated)>=3 and separated[-1]-separated[0]>=length*.6


def _has_tied_axis_band(lines, ink, minimum):
    """Qualify supplemental voting before changing the established scan path."""
    binary = cv2.bitwise_not(ink)
    maximum = min(64,max(4,min(ink.shape)*.03))
    directions = set()
    for index,(x1,y1,x2,y2) in enumerate(lines):
        horizontal = y1 == y2
        if horizontal in directions:
            continue
        if not horizontal and x1 != x2:
            continue
        for ax,ay,bx,by in lines[index+1:]:
            if horizontal and ay == by:
                separation = abs(ay-y1)
                lo,hi = max(x1,ax),min(x2,bx)
                pair = (((lo,(y1+ay)/2),(hi,(y1+ay)/2)),separation+1)
            elif not horizontal and ax == bx:
                separation = abs(ax-x1)
                lo,hi = max(y1,ay),min(y2,by)
                pair = ((((x1+ax)/2,lo),((x1+ax)/2,hi)),separation+1)
            else:
                continue
            if (2<=separation<=maximum and hi-lo>=max(minimum*2,min(ink.shape)*.14)
                    and _regular_thin_parallel_bars((*pair[0][0],*pair[0][1],pair[1]),binary)
                    and _has_repeated_band_ties(pair,ink,minimum)):
                directions.add(horizontal)
                if len(directions)==2:
                    return True
                break
    return False


def _has_observed_side_cavities(ink,px,py,qx,qy):
    """White original pixels on both interior sides despite raster jitter."""
    support = []
    for fractions in ((1/4,1/3,5/12),(7/12,2/3,3/4)):
        white = np.zeros(px.shape,dtype=bool)
        for fraction in fractions:
            ix = np.rint(px+(qx-px)*fraction).astype(int)
            iy = np.rint(py+(qy-py)*fraction).astype(int)
            white |= ink[iy,ix]==0
        support.append(float(np.mean(white)))
    return min(support) >= .45 and max(support) >= .8


def _extend_observed_pair(pair,nearby_ink):
    """Follow both observed mates, stopping at the first unsupported raster step."""
    (start,end),thickness = pair
    start,end = np.asarray(start,dtype=float),np.asarray(end,dtype=float)
    axis = (end-start)/np.linalg.norm(end-start)
    normal = np.array([-axis[1],axis[0]])
    height,width = nearby_ink.shape
    steps = np.arange(1,math.ceil(math.hypot(width,height))+1)
    endpoints = []
    for origin,direction in ((start,-1),(end,1)):
        points = origin[None,:]+steps[:,None]*direction*axis
        supported = np.ones(steps.shape,dtype=bool)
        for side in (-1,1):
            edges = np.rint(points+normal*side*(thickness-1)/2).astype(int)
            xs,ys = edges[:,0],edges[:,1]
            valid = (xs>=0)&(xs<width)&(ys>=0)&(ys<height)
            supported &= valid & (nearby_ink[np.clip(ys,0,height-1),np.clip(xs,0,width-1)]>0)
        stops = np.flatnonzero(~supported)
        last = int(stops[0]) if stops.size else len(steps)
        endpoints.append(tuple(np.rint(origin+last*direction*axis).astype(int)))
    return (tuple(endpoints),thickness)


def _has_two_observed_wall_junctions(pair, supports, minimum_span, *, minimum_support_span=None):
    """Both endpoints must meet independently established transverse wall bands."""
    if len(supports) > 512:
        return False
    (start,end),thickness = pair
    start,end = np.asarray(start,dtype=float),np.asarray(end,dtype=float)
    length = float(np.linalg.norm(end-start))
    if length < minimum_span:
        return False
    axis = (end-start)/length
    support_span = minimum_span if minimum_support_span is None else minimum_support_span
    joined = [False,False]
    for (a,b),other_thickness in supports:
        a,b = np.asarray(a,dtype=float),np.asarray(b,dtype=float)
        other_length = float(np.linalg.norm(b-a))
        if other_length < support_span:
            continue
        transverse = (b-a)/other_length
        if abs(float(axis @ transverse)) > .2:
            continue
        tolerance = (thickness+other_thickness)/2+2
        for index,point in enumerate((start,end)):
            delta = point-a
            projection = float(delta @ transverse)
            distance = abs(float(delta[0]*transverse[1]-delta[1]*transverse[0]))
            if distance <= tolerance and -tolerance <= projection <= other_length+tolerance:
                joined[index] = True
        if all(joined):
            return True
    return False


def _recover_junction_backed_bands(candidates, supports, minimum_span, minimum_support_span):
    """Two anchored waves; unsupported bands cannot mutually approve a corner."""
    remaining = list(dict.fromkeys(candidates))
    recovered = []
    if len(remaining) > 512 or len(supports) > 512:
        return recovered
    for _ in range(2):
        established = tuple(supports) + tuple(recovered)
        accepted = [pair for pair in remaining if _has_two_observed_wall_junctions(
            pair, established, minimum_span, minimum_support_span=minimum_support_span)]
        if not accepted:
            break
        # Assess the whole wave before adding supports: iteration order cannot
        # let two initially unsupported hypotheses validate each other.
        recovered.extend(accepted)
        accepted_set = set(accepted)
        remaining = [pair for pair in remaining if pair not in accepted_set]
    return recovered


def _axis_boundary_segments(ink, minimum):
    """Bound deterministic straight-edge proposals on a dense raster.

    Dense Hough voting can choose opposing halves of parallel outlines at a
    doorway. These native pixel runs supplement only an overflowing Hough
    pool; the ordinary paired-cavity checks still decide wall membership.
    """
    result = []
    for horizontal, raster in ((True, ink), (False, ink.T)):
        retained = []
        # Stream rows with a fixed-size heap. A noisy high-resolution image
        # must not materialize millions of start/end coordinate pairs.
        for row, values in enumerate(raster):
            active = np.r_[False, values > 0, False]
            transitions = np.flatnonzero(active[1:] != active[:-1])
            for low, stop in zip(transitions[::2], transitions[1::2]):
                if stop-low < minimum:
                    continue
                # Longest first; ties retain the smallest source coordinates.
                entry = (int(stop-low), -row, -int(low), int(stop-1))
                if len(retained) < 128:
                    heapq.heappush(retained, entry)
                elif entry > retained[0]:
                    heapq.heapreplace(retained, entry)
        runs = [(-row, -low, high) for _, row, low, high
                in sorted(retained, reverse=True)]
        result.extend((int(lo), int(row), int(hi), int(row)) if horizontal
                      else (int(row), int(lo), int(row), int(hi))
                      for row, lo, hi in runs)
    return result


def _outlined_wall_evidence(ink, parameters, continuity_ink=None, *, partial_pairs=None):
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
    canonical = _canonical_segments(raw, width=width, height=height)
    axis_segments = set()
    if len(canonical) > 256:
        # On dense weighted scans many pixels of the same stroke crowd other
        # edges out of the 256-line pool. Retry voting on rising ink boundaries
        # only when that pool is exceeded. Sparse drawings keep their exact
        # existing votes; all width/cavity checks still use ORIGINAL ink.
        vote_ink = ink.copy()
        duplicate = ((ink[1:, 1:] > 0) & (ink[:-1, 1:] > 0) & (ink[1:, :-1] > 0))
        vote_ink[1:, 1:][duplicate] = 0
        try:
            raw = cv2.HoughLinesP(vote_ink, 1, math.pi / 180, max(12, minimum // 2),
                                  minLineLength=minimum, maxLineGap=round(parameters.maximum_line_gap))
        except Exception:
            raise _error("HOUGH_DETECTION_FAILED") from None
        if raw is None:
            return None
        canonical = _canonical_segments(raw, width=width, height=height)
        axis_segments = set(_axis_boundary_segments(vote_ink, minimum))
        canonical += list(axis_segments)
    # Reserve evidence in both axes: horizontal duplicates on a wide page must
    # not crowd vertical wall mates out of the bounded pool. Native runs only
    # propose pixels; cavity, width, bundle and tie checks below still qualify.
    native_axes = sorted(set(_axis_boundary_segments(ink, minimum)))
    balanced_axes = _has_tied_axis_band(native_axes,ink,minimum)
    if balanced_axes:
        canonical += native_axes
        axis_segments.update(native_axes)
    lines = []
    for x1, y1, x2, y2 in canonical:
        length = math.hypot(x2 - x1, y2 - y1)
        if length >= minimum:
            lines.append((length, x1, y1, x2, y2))
    ranked = sorted(set(lines), key=lambda row: (-row[0], row[1:]))
    if balanced_axes:
        groups = [[], [], []]
        for row in ranked:
            _, x1, y1, x2, y2 = row
            group = 0 if abs(y2-y1) <= 1 else 1 if abs(x2-x1) <= 1 else 2
            groups[group].append(row)
        reserved = set(groups[0][:96] + groups[1][:96] + groups[2][:64])
        for row in ranked:
            if len(reserved) >= 256:
                break
            reserved.add(row)
        lines = sorted(reserved, key=lambda row: (-row[0], row[1:]))
    else:
        lines = ranked[:256]
    # Native-resolution outlines scale with the drawing. A fixed 32px cap
    # makes the same hollow wall lose its evidence on a higher-resolution
    # upload, then falls back to treating bold circuit strokes as walls. Keep
    # the search page-scaled and bounded; pair cavity/width checks still decide
    # whether the wider gap is observed architectural evidence.
    maximum_separation = min(64, max(4, min(width, height) * .03))
    long_span = max(minimum * 2, min(width, height) * .14)
    nearby_ink = cv2.dilate(ink, np.ones((3, 3), dtype=np.uint8))
    original_binary = cv2.bitwise_not(ink)
    pairs = []
    axis_pairs = []
    tied_pairs = []
    center_obscured = []
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
            if np.mean((nearby_ink[sy, sx] > 0) & (nearby_ink[ey, ex] > 0)) < .8:
                continue
            center_white = float(np.mean(ink[cy,cx]==0))
            obscured = center_white < .45
            if obscured:
                # A construction/hatch stroke can occupy the exact center of a
                # hollow wall. Require white ORIGINAL pixels in both interior
                # lanes, one sustained >=80%; defer acceptance until both ends
                # meet independently established transverse wall bands. This
                # does not accept the filled interior of a thick single wire.
                if center_white < .1 or not _has_observed_side_cavities(ink,px,py,qx,qy):
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
            # A repeated bundle of equally thin strokes is not a two-outline
            # wall cavity. Do not fill each neighboring pair into a solid wall.
            band = (*endpoints[0],*endpoints[1],separation+1)
            if _regular_thin_parallel_bars(band,original_binary):
                # Only an intermittent center stroke between two outer outlines
                # may be rescued by TWO observed wall junctions. Continuous
                # three-wire bundles and all wider repeated bundles stay out.
                if _has_repeated_band_ties((endpoints,separation+1),ink,minimum):
                    tied_pairs.append((endpoints,separation+1))
                elif (not _has_intermittent_middle_bar(band,original_binary)
                        or not _has_observed_side_cavities(ink,px,py,qx,qy)):
                    continue
                else:
                    obscured = True
            if obscured:
                center_obscured.append((endpoints,separation+1))
                continue
            pairs.append((endpoints, separation + 1))
            if ((x1, y1, x2, y2) in axis_segments
                    and (ax, ay, bx, by) in axis_segments and end-start >= long_span):
                axis_pairs.append((endpoints, separation + 1))
            if end - start >= long_span:
                strong_directions.add('horizontal' if abs(tx) > abs(ty) else 'vertical')
    # Mixed-style drawings may provide clear hollow evidence in only one
    # direction. Preserve those observed pairs for bracketed recovery without
    # switching the page-wide solid/outline inference mode.
    if partial_pairs is not None and len(pairs) <= 512:
        partial_pairs.extend(pairs)
    if len(strong_directions) != 2:
        return None
    # Bound recovery and require an independently established first wave.
    recovered_bands = []
    if len(center_obscured) <= 512:
        supports = tuple(pairs)
        # A compact fixture cannot acquire structural identity merely because
        # its short edges connect to longer circuit strokes. It must be long
        # BEFORE observed-edge recovery as well as after it.
        extended = dict.fromkeys(_extend_observed_pair(pair,nearby_ink)
                                 for pair in dict.fromkeys(center_obscured)
                                 if math.dist(*pair[0]) >= long_span)
        recovered_bands = _recover_junction_backed_bands(extended,supports,long_span,minimum)
    qualified = set(_without_detached_enclosing_bands(pairs))
    rejected = [pair for pair in pairs if pair not in qualified]
    mask = np.zeros_like(ink)
    for (start, end), thickness in pairs:
        cv2.line(mask, start, end, 255, max(2, round(thickness)))
    recovery = _recover_paired_band_ends(pairs,ink,continuity_ink,minimum)
    # Retain independently qualified long axis bands if skeleton voting later
    # misses one door-separated half. This only supplements dense-pool cases.
    axis_pairs = [pair for pair in dict.fromkeys(axis_pairs + tied_pairs) if pair in qualified]
    return mask, float(np.median([thickness for _, thickness in pairs])), rejected, recovery, recovered_bands, axis_pairs, balanced_axes


def _add_verified_outline_bands(segments,bands):
    """Add observed recovery without reseeding Hough votes or unrelated geometry."""
    result = list(segments)
    for (start,end),thickness in bands:
        start,end = np.asarray(start,dtype=float),np.asarray(end,dtype=float)
        length = float(np.linalg.norm(end-start))
        axis = (end-start)/length
        normal = np.array([-axis[1],axis[0]])
        covered = []
        present = False
        for index,segment in enumerate(result):
            a,b = np.asarray(segment[:2]),np.asarray(segment[2:4])
            other_length = float(np.linalg.norm(b-a))
            if (other_length == 0 or abs(float(axis @ ((b-a)/other_length))) < math.cos(math.radians(2))
                    or max(abs(float((p-start) @ normal)) for p in (a,b)) > max(2,thickness*.25)):
                continue
            low,high = sorted(float((point-start) @ axis) for point in (a,b))
            if low <= 1 and high >= length-1:
                present = True
                break
            if low >= -1 and high <= length+1:
                covered.append(index)
        if not present:
            result = [segment for index,segment in enumerate(result) if index not in covered]
            result.append((*map(int,start),*map(int,end),float(thickness)))
    return result


def _bracketed_pair_hypotheses(segments, minimum, maximum_gap, limit):
    """Bound hypotheses from existing compatible fragment ends, not new ink."""
    hypotheses = []
    for first in segments:
        a,b = np.asarray(first[:2],dtype=float),np.asarray(first[2:4],dtype=float)
        span = float(np.linalg.norm(b-a))
        if span < minimum:
            continue
        axis = (b-a)/span
        normal = np.array([-axis[1],axis[0]])
        for second in segments:
            c,d = np.asarray(second[:2],dtype=float),np.asarray(second[2:4],dtype=float)
            other_span = float(np.linalg.norm(d-c))
            band_width = (first[4]+second[4])/2
            if (other_span < minimum or abs(float(axis @ ((d-c)/other_span))) < math.cos(math.radians(2))
                    or abs(first[4]-second[4]) > max(2,band_width*.3)
                    or max(abs(float((p-a) @ normal)) for p in (c,d)) > max(2,band_width*.3)):
                continue
            if float((c-a) @ axis) > float((d-a) @ axis):
                c,d = d,c
            gap = float((c-b) @ axis)
            if not max(minimum,band_width*6) <= gap <= maximum_gap:
                continue
            hypotheses.append(((tuple(map(int,b)),tuple(map(int,c))),band_width))
            if len(hypotheses) >= limit:
                return hypotheses
    return hypotheses


def _recover_bracketed_paired_gaps(segments, pairs, ink, minimum, *, accept_merge=None):
    """Join existing wall fragments only where both observed mates survive.

    This cannot seed a wall, extend an unbracketed end, alter global Hough votes,
    or cross a step where both outlines disappear at a doorway. Thick column
    intersections retain both mate positions and can stay within one wall.
    """
    if len(pairs) > 512 or len(segments) > 512:
        return segments
    height, width = ink.shape
    maximum_gap = min(width, height) * .4
    nearby = cv2.dilate(ink, np.ones((3, 3), dtype=np.uint8))
    result = list(segments)
    candidates = list(dict.fromkeys(pairs))
    if len(candidates) < 512:
        candidates.extend(_bracketed_pair_hypotheses(segments, minimum, maximum_gap,
                                                    min(128,512-len(candidates))))
    for (start, end), band_width in dict.fromkeys(candidates):
        origin = np.asarray(start, dtype=float)
        delta = np.asarray(end, dtype=float)-origin
        length = float(np.linalg.norm(delta))
        if length < minimum or band_width < 3 or length < band_width*6:
            continue
        axis = delta/length
        normal = np.array([-axis[1], axis[0]])
        related = []
        for index, segment in enumerate(result):
            a, b = np.asarray(segment[:2], dtype=float), np.asarray(segment[2:4], dtype=float)
            span = float(np.linalg.norm(b-a))
            if (span < minimum or abs(float(axis @ ((b-a)/span))) < math.cos(math.radians(2))
                    or abs(segment[4]-band_width) > max(2,band_width*.3)
                    or max(abs(float((p-origin) @ normal)) for p in (a,b)) > max(2,band_width*.3)):
                continue
            low, high = float((a-origin) @ axis), float((b-origin) @ axis)
            if low > high:
                a,b,low,high = b,a,high,low
            related.append((low,high,index,a,b))
        related.sort(key=lambda row: (row[0],row[1],row[2]))
        for first, second in zip(related, related[1:]):
            low, high = first[1], second[0]
            gap = high-low
            if (not 1 < gap <= maximum_gap
                    or min(length,high)-max(0,low) < minimum):
                continue
            a,b = first[4],second[3]
            steps = np.linspace(0,1,max(2,math.ceil(np.linalg.norm(b-a))+1))
            points = a[None,:]+steps[:,None]*(b-a)
            supported = np.ones(steps.shape,dtype=bool)
            for side in (-1,1):
                edges = np.rint(points+normal*side*(band_width-1)/2).astype(int)
                xs,ys = edges[:,0],edges[:,1]
                valid = (xs>=0)&(xs<width)&(ys>=0)&(ys<height)
                supported &= valid & (nearby[np.clip(ys,0,height-1),np.clip(xs,0,width-1)]>0)
            if not supported.all():
                continue
            # The two sides of a single filled wire are insufficient. Original
            # white cavity evidence must survive over the recovered interval;
            # occasional column intersections may occupy its center.
            center = np.rint(points).astype(int)
            left,right = points-normal*(band_width-1)/2,points+normal*(band_width-1)/2
            if (np.mean(ink[center[:,1],center[:,0]]==0) < .45
                    or not _has_observed_side_cavities(ink,left[:,0],left[:,1],right[:,0],right[:,1])):
                continue
            begin, finish = first[3], second[4]
            merged = (*map(int,begin),*map(int,finish),max(result[first[2]][4],result[second[2]][4]))
            if accept_merge is not None and not accept_merge(merged):
                # A longer band may reveal grid/glyph evidence unavailable on
                # short fragments. Preserve both accepted anchors on rejection.
                continue
            result = [row for index,row in enumerate(result) if index not in (first[2],second[2])]+[merged]
            # Rebuild indices on the next distinct observed pair; stale indices
            # must never remove an unrelated candidate after this replacement.
            break
    return result


def _detect_structural_wall_lines(
    image: np.ndarray,
    parameters: WallDetectionParameters,
    continuity_image: np.ndarray | None = None,
) -> list[tuple[int, int, int, int, float]]:
    height, width = image.shape
    if np.all(image == image.flat[0]):
        return []

    ink = np.where(image == 0, 255, 0).astype(np.uint8)
    original_ink = ink
    if cv2.countNonZero(ink) == 0:
        return []
    partial_pairs = []
    outlined = _outlined_wall_evidence(ink, parameters,
                                     cv2.bitwise_not(continuity_image) if continuity_image is not None else None,
                                     partial_pairs=partial_pairs)

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
        outline_mask, outline_width = outlined[:2]
        # Keep broad solid/hatched structure as well. On an outlined plan a
        # thinner single stroke is insufficient wall evidence, even if long.
        solid_radius = max(2.5, outline_width * .5)
        # Closing bridges scan gaps but must not manufacture solid-wall evidence
        # from closely packed circuit/fixture strokes.
        solid_core = cv2.distanceTransform(original_ink, cv2.DIST_L2, 5) >= solid_radius
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
    if outlined is not None and outlined[2]:
        # Keep the original stroke statistics, skeleton and Hough votes intact.
        # Excluding the frame before those stages would change unrelated walls.
        retained = []
        for segment in consolidated:
            start, end = np.asarray(segment[:2]), np.asarray(segment[2:4])
            excluded = False
            for (a, b), thickness in outlined[2]:
                a, b = np.asarray(a), np.asarray(b)
                axis = (b - a) / np.linalg.norm(b - a)
                normal = np.array([-axis[1], axis[0]])
                distances = [abs(float((point - a) @ normal)) for point in (start, end)]
                projections = sorted(float((point - a) @ axis) for point in (start, end))
                if (max(distances) <= thickness + 2 and projections[0] >= -thickness - 2
                        and projections[1] <= np.linalg.norm(b - a) + thickness + 2):
                    excluded = True
                    break
            if not excluded:
                retained.append(segment)
        consolidated = retained
    if outlined is not None and outlined[3]:
        # Recovery is endpoint-only. Never alter stroke statistics, skeleton or
        # Hough votes: additional mask ink can otherwise seed panel/wiring walls.
        unchanged, changed = [], []
        recovery_mask = np.zeros_like(ink)
        for (a, b), band_width in outlined[3]:
            cv2.line(recovery_mask,a,b,255,max(2,round(band_width)))
        combined = cv2.bitwise_or(clean_structural,recovery_mask)
        for segment in consolidated:
            x1,y1,x2,y2,thickness = segment
            origin = np.array([x1,y1],dtype=float)
            length = math.hypot(x2-x1,y2-y1)
            axis = np.array([x2-x1,y2-y1],dtype=float)/length
            normal = np.array([-axis[1],axis[0]])
            relevant = np.zeros_like(ink)
            for (a,b),band_width in outlined[3]:
                a,b = np.asarray(a),np.asarray(b)
                other_length = float(np.linalg.norm(b-a))
                if (other_length and abs(float(axis @ ((b-a)/other_length))) >= math.cos(math.radians(2))
                        and max(abs(float((p-origin) @ normal)) for p in (a,b)) <= max(2,thickness*.35)):
                    cv2.line(relevant,tuple(a),tuple(b),255,max(2,round(band_width)))
            endpoints = []
            for point,direction in ((origin,-1),(np.array([x2,y2],dtype=float),1)):
                last = point
                for step in range(1,max(2,round(min(width,height)*.15))+1):
                    next_point = point+axis*direction*step
                    px,py = np.rint(next_point).astype(int)
                    if not (0<=px<width and 0<=py<height and relevant[py,px]):
                        break
                    last = next_point
                endpoints.append(tuple(np.rint(last).astype(int)))
            (a,b),(c,d) = endpoints
            if (a,b,c,d) == segment[:4]:
                unchanged.append(segment)
            else:
                changed.append((a,b,c,d,thickness,math.hypot(c-a,d-b)))
        consolidated = unchanged + _consolidate_wall_segments(changed,width,height,max_gap,evidence_mask=combined)
    if outlined is not None and len(outlined) > 4 and outlined[4]:
        # New mask ink changes global thickness statistics and randomized Hough
        # voting, which can seed fixture/wiring artifacts. Recovery therefore
        # changes only its independently verified band and covered fragments.
        consolidated = _add_verified_outline_bands(consolidated,outlined[4])
    if outlined is not None and len(outlined) > 5 and outlined[5]:
        consolidated = _add_verified_outline_bands(consolidated, outlined[5])
    def passes_final_guards(segment):
        return (not _is_repeated_grid_member(segment, image)
                and not _has_compact_parallel_bars(segment, image)
                and not _has_compact_annotated_outline(segment, image))

    retained = [segment for segment in consolidated if passes_final_guards(segment)]
    if outlined is None:
        # Rejected fixture/grid fragments cannot acquire wall identity merely
        # by joining into a longer band that escapes the compact-glyph guard.
        retained = _recover_bracketed_paired_gaps(retained, partial_pairs,
                                                  original_ink, min_wall_length,
                                                  accept_merge=passes_final_guards)
    if outlined is not None and len(outlined)>6 and outlined[6]:
        # Supplemental original bands can describe the same cavity from its
        # adjacent outline pairs. Collapse overlapping centreline hypotheses;
        # observed evidence still gates any short-gap merge.
        # A shorter native fragment can be 'qualified' while its encompassing
        # frame rule was rejected. Apply that same exclusion AFTER supplements.
        without_frames = []
        for segment in retained:
            start,end = np.asarray(segment[:2]),np.asarray(segment[2:4])
            excluded = False
            for (a,b),thickness in outlined[2]:
                a,b = np.asarray(a),np.asarray(b)
                length = float(np.linalg.norm(b-a))
                axis = (b-a)/length
                normal = np.array([-axis[1],axis[0]])
                projections = sorted(float((p-a)@axis) for p in (start,end))
                if (max(abs(float((p-a)@normal)) for p in (start,end))<=thickness+2
                        and projections[0]>=-thickness-2 and projections[1]<=length+thickness+2):
                    excluded = True
                    break
            if not excluded:
                without_frames.append(segment)
        retained = _consolidate_wall_segments(
            [(*s, math.hypot(s[2]-s[0],s[3]-s[1])) for s in without_frames],
            width, height, max_gap, evidence_mask=outlined[0])
        retained = [s for s in retained if passes_final_guards(s)]
    if outlined is None:
        # Previously qualified faint continuation must not be trimmed against
        # the stronger seed mask alone. No new segment is seeded here.
        refinement_mask=cv2.bitwise_not(continuity_image) if continuity_dist is not None else clean_structural
        retained=refine_filled_bands(retained,refinement_mask)
    snapped = snap_observed_junctions(retained, original_ink, max_gap)
    return unique_wall_spans([after if passes_final_guards(after) else before
            for before, after in zip(retained, snapped)])


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
