from __future__ import annotations

from dataclasses import dataclass
from math import hypot

import cv2
import numpy as np

from app.ai.floor_plan_interpretation.candidate import (
    AffineTransform,
    CandidateCollection,
    CandidateWarning,
    EvidenceRegion,
    FloorPlanInterpretationPayload,
    ObservedRoutes,
    PageAssessment,
    PageSignals,
    PixelBounds,
    PixelPoint,
    RoomCandidate,
    SCHEMA_VERSION,
    SourcePlane,
    SymbolCandidate,
    WallCandidate,
)
from app.ai.wall_detection.config import WallDetectionParameters
from app.ai.wall_detection.detector import detect_wall_lines


MAXIMUM_IMAGE_EDGE = 4096
MAXIMUM_IMAGE_PIXELS = 60_000_000
SAFE_ERROR_MESSAGE = "The local demo floor-plan interpretation failed."


class DemoCVError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(SAFE_ERROR_MESSAGE)


@dataclass(frozen=True)
class DemoCVParameters:
    maximum_walls: int = 300
    maximum_rooms: int = 100
    maximum_symbols: int = 500
    minimum_room_area_ratio: float = 0.002
    maximum_room_area_ratio: float = 0.80

    def __post_init__(self) -> None:
        if (
            any(
                not isinstance(value, int) or isinstance(value, bool) or value <= 0
                for value in (
                    self.maximum_walls,
                    self.maximum_rooms,
                    self.maximum_symbols,
                )
            )
            or not 0 < self.minimum_room_area_ratio < self.maximum_room_area_ratio < 1
        ):
            raise DemoCVError("INVALID_CONFIGURATION")


def _validate_image(source: object) -> np.ndarray:
    if (
        not isinstance(source, np.ndarray)
        or source.dtype != np.uint8
        or source.ndim != 3
        or source.shape[2] != 3
        or source.shape[0] <= 0
        or source.shape[1] <= 0
    ):
        raise DemoCVError("INVALID_IMAGE")
    height, width = source.shape[:2]
    if (
        max(width, height) > MAXIMUM_IMAGE_EDGE
        or width * height > MAXIMUM_IMAGE_PIXELS
    ):
        raise DemoCVError("UNSAFE_DIMENSIONS")
    return source


def _plan_bounds(ink: np.ndarray) -> tuple[int, int, int, int]:
    height, width = ink.shape
    working = ink.copy()
    margin = max(2, round(min(width, height) * 0.015))
    working[:margin, :] = 0
    working[-margin:, :] = 0
    working[:, :margin] = 0
    working[:, -margin:] = 0
    join_size = max(3, round(min(width, height) * 0.003))
    if join_size % 2 == 0:
        join_size += 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (join_size, join_size))
    joined = cv2.morphologyEx(working, cv2.MORPH_CLOSE, kernel)
    joined = cv2.dilate(joined, kernel, iterations=1)
    count, _, stats, _ = cv2.connectedComponentsWithStats(joined, 8)
    candidates: list[tuple[int, int, int, int, int]] = []
    minimum_component = max(64, round(width * height * 0.0005))
    for index in range(1, count):
        x, y, component_width, component_height, area = (
            int(value) for value in stats[index]
        )
        if area < minimum_component:
            continue
        candidates.append((area, x, y, component_width, component_height))
    if not candidates:
        return margin, margin, width - 2 * margin, max(1, height - 2 * margin)
    _, x, y, component_width, component_height = max(
        candidates,
        key=lambda item: (item[0], item[3] * item[4], -item[2], -item[1]),
    )
    padding = max(4, round(min(width, height) * 0.01))
    left = max(margin, x - padding)
    top = max(margin, y - padding)
    right = min(width - margin, x + component_width + padding)
    bottom = min(height - margin, y + component_height + padding)
    return left, top, max(1, right - left), max(1, bottom - top)


def _room_boundaries(
    ink: np.ndarray,
    plan_bounds: tuple[int, int, int, int],
    parameters: DemoCVParameters,
) -> tuple[tuple[tuple[tuple[int, int], ...], ...], bool]:
    x, y, width, height = plan_bounds
    plan_ink = ink[y : y + height, x : x + width]
    barrier_size = max(3, round(min(width, height) * 0.0025))
    if barrier_size % 2 == 0:
        barrier_size += 1
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (barrier_size, barrier_size),
    )
    # Prefer long wall-like strokes to short wiring dashes and text. Bridge short
    # doorway-sized gaps only in the advisory room mask, never observed wiring.
    span = max(12, round(min(width, height) * 0.12))
    horizontal = cv2.morphologyEx(plan_ink, cv2.MORPH_OPEN,
                                 cv2.getStructuringElement(cv2.MORPH_RECT, (span, 1)))
    vertical = cv2.morphologyEx(plan_ink, cv2.MORPH_OPEN,
                               cv2.getStructuringElement(cv2.MORPH_RECT, (1, span)))
    structural = cv2.bitwise_or(horizontal, vertical)
    span = max(12, round(min(width, height) * 0.16))
    # A rotated or thin-stroke drawing may not support the axis-aligned mask.
    if cv2.countNonZero(structural) >= width * height * 0.005:
        horizontal = cv2.morphologyEx(structural, cv2.MORPH_CLOSE,
                                     cv2.getStructuringElement(cv2.MORPH_RECT, (span, 1)))
        vertical = cv2.morphologyEx(structural, cv2.MORPH_CLOSE,
                                   cv2.getStructuringElement(cv2.MORPH_RECT, (1, span)))
        room_ink = cv2.bitwise_or(horizontal, vertical)
    else:
        room_ink = plan_ink
    barriers = cv2.morphologyEx(room_ink, cv2.MORPH_CLOSE, kernel)
    barriers = cv2.dilate(barriers, kernel, iterations=1)
    free_space = cv2.bitwise_not(barriers)
    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(
        free_space,
        8,
    )
    plan_area = width * height
    minimum_area = plan_area * parameters.minimum_room_area_ratio
    maximum_area = plan_area * parameters.maximum_room_area_ratio
    boundaries: list[tuple[tuple[int, int], ...]] = []
    for index in range(1, component_count):
        component_x, component_y, component_width, component_height, area = (
            int(value) for value in stats[index]
        )
        touches_edge = (
            component_x == 0
            or component_y == 0
            or component_x + component_width >= width
            or component_y + component_height >= height
        )
        if (touches_edge or not minimum_area <= area <= maximum_area
                or min(component_width, component_height) < min(width, height) * 0.06):
            continue
        component = np.where(labels == index, 255, 0).astype(np.uint8)
        contours, _ = cv2.findContours(
            component,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        if not contours:
            continue
        # Preserve L-shaped interiors rather than filling them with a convex hull.
        contour = max(contours, key=cv2.contourArea)
        epsilon = max(1.0, cv2.arcLength(contour, True) * 0.008)
        polygon = cv2.approxPolyDP(contour, epsilon, True).reshape(-1, 2)
        if len(polygon) < 3:
            continue
        points = tuple((int(px) + x, int(py) + y) for px, py in polygon)
        boundaries.append(points)
    unique = sorted(
        set(boundaries),
        key=lambda points: (
            min(point[1] for point in points),
            min(point[0] for point in points),
            -abs(cv2.contourArea(np.array(points, dtype=np.int32))),
            points,
        ),
    )
    truncated = len(unique) > parameters.maximum_rooms
    return tuple(unique[: parameters.maximum_rooms]), truncated


def _symbol_circles(
    grayscale: np.ndarray,
    plan_bounds: tuple[int, int, int, int],
    parameters: DemoCVParameters,
) -> tuple[tuple[tuple[int, int, int], ...], bool]:
    x, y, width, height = plan_bounds
    cropped = grayscale[y : y + height, x : x + width]
    _, ink = cv2.threshold(
        cropped,
        0,
        255,
        cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU,
    )
    contours, _ = cv2.findContours(ink, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    minimum_radius = max(4, round(min(width, height) * 0.0035))
    maximum_radius = max(
        minimum_radius + 1,
        min(48, round(min(width, height) * 0.08)),
    )
    candidates = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        perimeter = float(cv2.arcLength(contour, True))
        if area <= 0 or perimeter <= 0:
            continue
        center, radius_value = cv2.minEnclosingCircle(contour)
        center_x, center_y = (round(center[0]), round(center[1]))
        radius = round(radius_value)
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        contour_x, contour_y, contour_width, contour_height = cv2.boundingRect(contour)
        aspect_ratio = contour_width / contour_height
        if not (
            minimum_radius <= radius <= maximum_radius
            and circularity >= 0.55
            and 0.65 <= aspect_ratio <= 1.35
            and radius <= center_x < width - radius
            and radius <= center_y < height - radius
        ):
            continue
        candidates.append((center_x + x, center_y + y, radius))
    ordered = sorted(
        set(candidates),
        key=lambda value: (value[1], value[0], value[2]),
    )
    selected: list[tuple[int, int, int]] = []
    for candidate in ordered:
        if any(
            hypot(candidate[0] - other[0], candidate[1] - other[1])
            < max(candidate[2], other[2])
            for other in selected
        ):
            continue
        selected.append(candidate)
    truncated = len(selected) > parameters.maximum_symbols
    return tuple(selected[: parameters.maximum_symbols]), truncated


def _collection_state(items: tuple[object, ...], truncated: bool = False) -> str:
    if truncated:
        return "partial"
    return "completed" if items else "empty"


def interpret_floor_plan_demo(
    source_rgb: np.ndarray,
    *,
    parameters: DemoCVParameters | None = None,
) -> FloorPlanInterpretationPayload:
    """Produce review-only source-pixel proposals using local deterministic CV."""
    selected = parameters or DemoCVParameters()
    if not isinstance(selected, DemoCVParameters):
        raise DemoCVError("INVALID_CONFIGURATION")
    source = _validate_image(source_rgb)
    height, width = source.shape[:2]
    try:
        grayscale = cv2.cvtColor(source.copy(), cv2.COLOR_RGB2GRAY)
        _, ink = cv2.threshold(
            grayscale,
            0,
            255,
            cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU,
        )
        plan_bounds = _plan_bounds(ink)
        room_boundaries, rooms_truncated = _room_boundaries(
            ink,
            plan_bounds,
            selected,
        )
        symbol_circles, symbols_truncated = _symbol_circles(
            grayscale,
            plan_bounds,
            selected,
        )
        masked_binary = np.full_like(grayscale, 255)
        x, y, plan_width, plan_height = plan_bounds
        masked_binary[y : y + plan_height, x : x + plan_width] = cv2.bitwise_not(
            ink[y : y + plan_height, x : x + plan_width]
        )
        wall_result = detect_wall_lines(
            masked_binary,
            parameters=WallDetectionParameters(
                hough_vote_threshold=max(20, round(min(width, height) * 0.012)),
                minimum_line_length=max(24, min(width, height) * 0.02),
                maximum_line_gap=max(6, min(width, height) * 0.004),
                maximum_candidates=selected.maximum_walls,
            ),
        )
    except DemoCVError:
        raise
    except Exception:
        raise DemoCVError("INFERENCE_FAILED") from None

    evidence_ref = ("region:region-0001",)
    walls = tuple(
        WallCandidate(
            id=f"wall-{index:04d}",
            start=PixelPoint(x=item.start.x, y=item.start.y),
            end=PixelPoint(x=item.end.x, y=item.end.y),
            evidence_refs=evidence_ref,
            ambiguity="ambiguous",
        )
        for index, item in enumerate(wall_result.candidates, start=1)
    )
    rooms = tuple(
        RoomCandidate(
            id=f"room-{index:04d}",
            label=None,
            boundary=tuple(PixelPoint(x=px, y=py) for px, py in boundary),
            evidence_refs=evidence_ref,
            ambiguity="ambiguous",
        )
        for index, boundary in enumerate(room_boundaries, start=1)
    )
    symbols = tuple(
        SymbolCandidate(
            id=f"symbol-{index:04d}",
            mapping_state="unknown",
            catalog_class_id=None,
            observed_label="unclassified circular symbol",
            center=PixelPoint(x=center_x, y=center_y),
            bounds=PixelBounds(
                x=center_x - radius,
                y=center_y - radius,
                width=radius * 2,
                height=radius * 2,
            ),
            orientation_degrees=None,
            evidence_refs=evidence_ref,
            ambiguity="ambiguous",
        )
        for index, (center_x, center_y, radius) in enumerate(symbol_circles, start=1)
    )
    any_truncated = wall_result.truncated or rooms_truncated or symbols_truncated
    warnings = (
        CandidateWarning(
            code="review_only_cv",
            severity="warning",
            message="Deterministic CV proposals require designer review and symbol class mapping.",
        ),
    )
    return FloorPlanInterpretationPayload(
        schema_version=SCHEMA_VERSION,
        document_state="partial" if any_truncated else "completed",
        source_plane=SourcePlane(width_pixels=width, height_pixels=height),
        page=PageAssessment(
            page_type="electrical_plan" if symbols else "unknown",
            quality="unknown",
            signals=PageSignals(
                electrical_content="visible" if symbols else "unknown",
                legend="unknown",
                dimensions="unknown",
                scale_evidence="unknown",
                observed_wiring="unknown",
            ),
        ),
        regions=(
            EvidenceRegion(
                id="region-0001",
                kind="plan_region",
                bounds=PixelBounds(
                    x=plan_bounds[0],
                    y=plan_bounds[1],
                    width=plan_bounds[2],
                    height=plan_bounds[3],
                ),
                local_to_source=AffineTransform(a=1, b=0, c=0, d=1, e=0, f=0),
            ),
        ),
        ocr=CandidateCollection(state="unavailable"),
        scales=CandidateCollection(state="unavailable"),
        walls=CandidateCollection(
            state=_collection_state(walls, wall_result.truncated),
            items=walls,
            truncated=wall_result.truncated,
        ),
        rooms=CandidateCollection(
            state=_collection_state(rooms, rooms_truncated),
            items=rooms,
            truncated=rooms_truncated,
        ),
        openings=CandidateCollection(state="unavailable"),
        symbols=CandidateCollection(
            state=_collection_state(symbols, symbols_truncated),
            items=symbols,
            truncated=symbols_truncated,
        ),
        panels=CandidateCollection(state="unavailable"),
        observed_routes=ObservedRoutes(state="unavailable"),
        warnings=warnings,
    )
