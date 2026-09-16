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
            d2 = abs(a1 * x2j + b2 * y2j + c1)
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
            elif evidence_mask is not None and gap <= max_gap * 4:
                # Check if image evidence supports continuity across the gap
                gap_start = min(p1_end, p2_end)
                gap_end = max(p1_start, p2_start)
                num_gap_pts = max(3, int(round(gap)))
                t_samples = np.linspace(gap_start, gap_end, num_gap_pts)
                gx = np.round(canon[i][0] + (t_samples - p1_start) * tx).astype(int)
                gy = np.round(canon[i][1] + (t_samples - p1_start) * ty).astype(int)
                gx = np.clip(gx, 0, width - 1)
                gy = np.clip(gy, 0, height - 1)
                ink_support = np.mean(evidence_mask[gy, gx] > 0)
                if ink_support >= 0.6:
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


def _detect_structural_wall_lines(
    image: np.ndarray,
    parameters: WallDetectionParameters,
) -> list[tuple[int, int, int, int, float]]:
    height, width = image.shape
    if np.all(image == image.flat[0]):
        return []

    ink = np.where(image == 0, 255, 0).astype(np.uint8)
    if cv2.countNonZero(ink) == 0:
        return []

    dist = cv2.distanceTransform(ink, cv2.DIST_L2, 5)
    ink_dist = dist[ink > 0]
    if len(ink_dist) == 0:
        return []

    max_radius = float(np.max(ink_dist))
    if parameters.min_stroke_radius is not None:
        min_stroke_radius = float(parameters.min_stroke_radius)
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

    min_span = max(min_wall_length * 0.6, min(width, height) * 0.015)
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

    skeleton = np.zeros_like(clean_structural)
    element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    temp = clean_structural.copy()
    while True:
        eroded = cv2.erode(temp, element)
        opened = cv2.morphologyEx(eroded, cv2.MORPH_OPEN, element)
        cv2.bitwise_or(skeleton, cv2.subtract(eroded, opened), skeleton)
        temp = eroded.copy()
        if cv2.countNonZero(temp) == 0:
            break

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
        raw_segments.append((x1, y1, x2, y2, thickness, length))

    consolidated = _consolidate_wall_segments(
        raw_segments, width, height, max_gap, evidence_mask=clean_structural
    )
    return consolidated


def detect_wall_lines(
    source: "PreprocessedImage | np.ndarray",
    *,
    parameters: WallDetectionParameters | None = None,
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
    height, width = image.shape
    if np.all(image == image.flat[0]):
        return _empty_result(width, height)

    if selected.structural_mode:
        algorithm_name = "structural_stroke_centerline"
        segments_with_th = _detect_structural_wall_lines(image, selected)
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
