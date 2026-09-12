"""U12: Extract and distinguish observed wiring without electrical design.

This module extracts visibly drawn electrical wiring, merging tiles deterministically
without hallucinating missing routes or resolving uncertain endpoints to distant symbols.
"""

from __future__ import annotations

import math
from typing import Sequence

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from app.ai.floor_plan_interpretation.candidate import (
    AffineTransform,
    ObservedRouteConnection,
    ObservedRoutes,
    ObservedRouteSegment,
    PanelCandidate,
    PixelPoint,
    SymbolCandidate,
)
from app.ai.floor_plan_interpretation.preparation import (
    local_to_source_coords,
)


class ObservedWiringConfig(BaseModel):
    """Configuration for observed wiring extraction and fusion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_segments: int = Field(default=200, ge=1, le=1000)
    connection_radius_pixels: float = Field(default=30.0, ge=1.0, le=100.0)
    dash_merge_tolerance_pixels: float = Field(default=15.0, ge=1.0, le=50.0)
    tile_seam_tolerance_pixels: float = Field(default=10.0, ge=1.0, le=50.0)


def extract_observed_wiring_from_image(
    image_rgb: np.ndarray,
    region_id: str,
    symbols: Sequence[SymbolCandidate],
    panels: Sequence[PanelCandidate],
    config: ObservedWiringConfig,
) -> tuple[Sequence[ObservedRouteSegment], Sequence[ObservedRouteConnection]]:
    """Extract strictly visible wiring routes without connecting unrelated fragments."""
    if (
        not isinstance(image_rgb, np.ndarray) or image_rgb.dtype != np.uint8
        or image_rgb.ndim != 3 or image_rgb.shape[2] != 3
        or min(image_rgb.shape[:2]) < 16 or max(image_rgb.shape[:2]) > 1536
    ):
        raise ValueError("Wiring extraction requires a bounded RGB uint8 tile.")
    # Convert to grayscale and threshold
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    # Use morphological operations to isolate thin lines/curves (wiring)
    # Walls are typically thicker parallel lines. We remove thick structures.
    kernel_thick = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    thick_elements = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_thick)
    thin_lines = cv2.subtract(binary, thick_elements)

    # Filter out very short noise
    kernel_clean = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    thin_lines = cv2.morphologyEx(thin_lines, cv2.MORPH_OPEN, kernel_clean)

    # Find contours for wiring traces
    contours, hierarchy = cv2.findContours(thin_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Deterministic sort: length descending, then top-left bounding box
    sorted_contours = sorted(
        contours,
        key=lambda c: (-cv2.arcLength(c, False), cv2.boundingRect(c)[1], cv2.boundingRect(c)[0])
    )

    segments: list[ObservedRouteSegment] = []
    connections: list[ObservedRouteConnection] = []
    segment_idx = 1

    for contour in sorted_contours:
        if len(segments) >= config.max_segments:
            break
            
        length = cv2.arcLength(contour, False)
        if length < 15.0:
            continue

        # Approximate contour to polyline
        epsilon = 0.015 * length
        approx = cv2.approxPolyDP(contour, epsilon, False)

        # Ensure we have at least 2 points
        if len(approx) < 2:
            continue

        points: list[PixelPoint] = []
        for pt in approx:
            x, y = map(float, pt[0])
            # Avoid consecutive duplicate points
            if not points or not (math.isclose(points[-1].x, x) and math.isclose(points[-1].y, y)):
                points.append(PixelPoint(x=round(x, 2), y=round(y, 2)))
        
        if len(points) < 2 or len(points) > 512:
            continue

        segment_id = f"segment-{segment_idx:04d}"
        segments.append(
            ObservedRouteSegment(
                id=segment_id,
                route_kind="observed",
                points=tuple(points),
                evidence_refs=(f"region:{region_id}",),
                ambiguity="ambiguous"
            )
        )
        
        # Thin-line contours alone cannot establish electrical connectivity.
        # Retain ambiguous fragments for review, even beside a known device.

        segment_idx += 1

    # In a full implementation, we'd also detect dash continuity here, 
    # but bounding within constraints: we preserve what is strictly continuous.
    
    return tuple(segments), tuple(connections)


def fuse_observed_routes(
    tile_segments: Sequence[tuple[str, ObservedRouteSegment]],
    tile_connections: Sequence[tuple[str, ObservedRouteConnection]],
    region_transforms: dict[str, AffineTransform],
    config: ObservedWiringConfig,
) -> tuple[Sequence[ObservedRouteSegment], Sequence[ObservedRouteConnection]]:
    """Deduplicate identical source polylines without bridging unseen gaps.

    Tile identities scope local segment IDs. Endpoint proximity is insufficient
    evidence for continuity, so distinct fragments and crossings remain separate.
    """
    if len(tile_segments) > config.max_segments:
        raise ValueError("Wiring fusion input exceeds the segment budget.")
    groups = {}
    local_keys = {}
    for region_id, segment in tile_segments:
        identity = (region_id, segment.id)
        if identity in local_keys:
            raise ValueError("Duplicate segment identity within a tile.")
        if region_id not in region_transforms:
            raise ValueError("Missing wiring source transform.")
        transform = region_transforms[region_id]
        points = tuple(
            local_to_source_coords(transform, float(p.x), float(p.y))
            for p in segment.points
        )
        # Validate transformed coordinates before grouping or emitting output.
        tuple(PixelPoint(x=x, y=y) for x, y in points)
        key = min(points, tuple(reversed(points)))
        local_keys[identity] = key
        group = groups.setdefault(key, {"evidence": set(), "ambiguities": set()})
        group["evidence"].update(segment.evidence_refs)
        group["evidence"].add(f"region:{region_id}")
        group["ambiguities"].add(segment.ambiguity)

    segments = []
    ids = {}
    for index, key in enumerate(sorted(groups), 1):
        group = groups[key]
        segment_id = f"segment-{index:04d}"
        ids[key] = segment_id
        ambiguity = (
            "unknown" if "unknown" in group["ambiguities"]
            else "ambiguous" if "ambiguous" in group["ambiguities"] else "clear"
        )
        segments.append(ObservedRouteSegment(
            id=segment_id, route_kind="observed",
            points=tuple(PixelPoint(x=x, y=y) for x, y in key),
            evidence_refs=tuple(sorted(group["evidence"])), ambiguity=ambiguity,
        ))

    connections = set()
    def remap(region_id, reference):
        kind, identity = reference.split(":", 1)
        if kind != "segment":
            return reference
        key = local_keys.get((region_id, identity))
        if key is None:
            raise ValueError("Dangling tile segment connection.")
        return f"segment:{ids[key]}"

    for region_id, connection in tile_connections:
        left = remap(region_id, connection.from_ref)
        right = remap(region_id, connection.to_ref)
        if left != right:
            connections.add(tuple(sorted((left, right))))
    return tuple(segments), tuple(
        ObservedRouteConnection(id=f"connection-{i:04d}", from_ref=a, to_ref=b)
        for i, (a, b) in enumerate(sorted(connections), 1)
    )


def build_observed_routes_payload(
    segments: Sequence[ObservedRouteSegment],
    connections: Sequence[ObservedRouteConnection],
    is_supported_page: bool,
    wiring_visible: bool | None,
) -> ObservedRoutes:
    """Construct a strictly validated ObservedRoutes candidate model."""
    if not is_supported_page:
        return ObservedRoutes(state="unavailable")

    if wiring_visible is None:
        return ObservedRoutes(
            state="partial", segments=tuple(segments), connections=tuple(connections)
        )
        
    if not wiring_visible:
        if segments or connections:
            raise ValueError("No-wiring evidence conflicts with extracted routes.")
        return ObservedRoutes(state="empty", segments=(), connections=())
        
    if not segments:
        if connections:
            raise ValueError("Connections require visible route segments.")
        return ObservedRoutes(
            state="failed", failure_reason="Visible wiring could not be extracted."
        )
        
    return ObservedRoutes(
        state="partial" if any(segment.ambiguity != "clear" for segment in segments) else "completed",
        segments=tuple(segments),
        connections=tuple(connections),
    )


def prepare_observed_wiring_evidence(context, config: ObservedWiringConfig | None = None) -> ObservedRoutes:
    """Bounded U7-to-U8 auxiliary evidence, never semantic electrical truth.

    Thin lines may be structural lines or text. Empty CV extraction therefore
    remains partial/unknown, not proof of no wiring. Tile images are read only.
    Oversized tiles are not rescaled silently: omitted evidence is flagged.
    """
    config = config or ObservedWiringConfig()
    observations = []
    transforms = {}
    truncated = False
    for tile in sorted(context.tiles, key=lambda item: item.region_id):
        if tile.region_id in transforms:
            raise ValueError("Duplicate wiring tile identity.")
        transforms[tile.region_id] = tile.local_to_source
        if max(tile.image_rgb.shape[:2]) > 1536:
            truncated = True
            continue
        segments, _ = extract_observed_wiring_from_image(
            tile.image_rgb, tile.region_id, (), (), config,
        )
        if len(segments) >= config.max_segments:
            truncated = True
        remaining = config.max_segments - len(observations)
        if len(segments) > remaining:
            truncated = True
        observations.extend((tile.region_id, segment) for segment in segments[:remaining])
    segments, connections = fuse_observed_routes(observations, (), transforms, config)
    width, height = context.source_plane.width_pixels, context.source_plane.height_pixels
    if any(p.x >= width or p.y >= height for s in segments for p in s.points):
        raise ValueError("Wiring evidence exceeds its source plane.")
    return ObservedRoutes(state="partial", segments=segments, connections=connections, truncated=truncated)
