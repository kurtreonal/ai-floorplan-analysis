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
from app.ai.floor_plan_interpretation.stroke_centerlines import stroke_paths


class ObservedWiringConfig(BaseModel):
    """Configuration for observed wiring extraction and fusion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_segments: int = Field(default=200, ge=1, le=1000)
    connection_radius_pixels: float = Field(default=30.0, ge=1.0, le=100.0)
    dash_merge_tolerance_pixels: float = Field(default=15.0, ge=1.0, le=50.0)
    tile_seam_tolerance_pixels: float = Field(default=10.0, ge=1.0, le=50.0)


def _merge_source_overlaps(groups, local_keys):
    """Union exactly collinear overlapping observations, never nearby wires.

    No gap tolerance, endpoint-only joins, style changes or crossing junctions.
    Source coordinates have already been transformed. Decimal tolerance only
    absorbs affine arithmetic, not a spatial snapping radius.
    """
    changed = True
    while changed:
        changed = False
        keys = sorted(groups)
        for i, first in enumerate(keys):
            if len(first) != 2:
                continue
            a, b = first
            dx, dy = b[0]-a[0], b[1]-a[1]
            length = math.hypot(dx, dy)
            if not length:
                continue
            for second in keys[i+1:]:
                if len(second) != 2 or groups[first]['styles'] != groups[second]['styles']:
                    continue
                c, d = second
                if any(abs((p[0]-a[0])*dy-(p[1]-a[1])*dx)/length > 1e-7 for p in second):
                    continue
                projections = [((p[0]-a[0])*dx+(p[1]-a[1])*dy)/length for p in second]
                if min(length, max(projections))-max(0, min(projections)) <= 1e-7:
                    continue
                ordered = sorted((a, b, c, d), key=lambda p: (p[0]*dx+p[1]*dy, p))
                key = min((ordered[0], ordered[-1]), (ordered[-1], ordered[0]))
                merged = {field: groups[first][field] | groups[second][field]
                          for field in ('evidence', 'ambiguities', 'styles')}
                if len(merged['evidence']) > 32:
                    continue  # Keep provenance complete rather than truncate it.
                del groups[first], groups[second]
                groups[key] = merged
                for identity, old in local_keys.items():
                    if old in (first, second):
                        local_keys[identity] = key
                changed = True
                break
            if changed:
                break


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

    # Auxiliary geometry is deliberately ambiguous: thickness alone cannot
    # distinguish a wall from a broad wire. Semantic/source-context validation
    # remains the interpreter's responsibility. Never trace both stroke edges.
    paths = stroke_paths(binary, maximum_paths=config.max_segments)

    segments: list[ObservedRouteSegment] = []
    connections: list[ObservedRouteConnection] = []
    segment_idx = 1

    for path in paths:
        if len(segments) >= config.max_segments:
            break
            
        points: list[PixelPoint] = []
        for x, y in path:
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
    """Deduplicate identical/collinear overlapping source observations.

    Tile identities scope local segment IDs. Endpoint proximity is insufficient
    evidence for continuity, so distinct fragments and crossings remain separate.
    """
    if len(tile_segments) > config.max_segments:
        raise ValueError("Wiring fusion input exceeds the segment budget.")
    groups = {}
    local_keys = {}
    local_points = {}
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
        local_points[identity] = points
        group = groups.setdefault(key, {"evidence": set(), "ambiguities": set(), 'styles':set()})
        group["evidence"].update(segment.evidence_refs)
        group["evidence"].add(f"region:{region_id}")
        group["ambiguities"].add(segment.ambiguity)
        group['styles'].add(segment.line_style)

    _merge_source_overlaps(groups, local_keys)

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
            line_style=next(iter(group['styles'])) if len(group['styles'])==1 else 'unknown',
        ))

    connections = set()
    contacts = {}
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
        if connection.evidence_kind is not None:
            key=local_keys[(region_id,connection.from_ref.split(':',1)[1])]
            points=local_points[(region_id,connection.from_ref.split(':',1)[1])]
            edge = (0 if len(key) == 2 else connection.source_edge_index if points == key
                    else len(points)-2-connection.source_edge_index)
            transform=region_transforms[region_id]
            path=local_to_source_coords(transform,connection.path_anchor.x,connection.path_anchor.y)
            anchor=local_to_source_coords(transform,connection.device_anchor.x,connection.device_anchor.y)
            signature=(left,right,edge,path,anchor,connection.evidence_kind)
            item=contacts.setdefault(signature,dict(evidence=set(),ambiguous=False))
            item['evidence'].update(connection.evidence_refs);item['evidence'].add(f'region:{region_id}')
            item['ambiguous'] |= connection.ambiguity=='ambiguous'
        elif left != right:
            connections.add(tuple(sorted((left, right))))
    result=list(
        ObservedRouteConnection(id=f"connection-{i:04d}", from_ref=a, to_ref=b)
        for i, (a, b) in enumerate(sorted(connections), 1)
    )
    for (left,right,edge,path,anchor,kind),item in sorted(contacts.items()):
        result.append(ObservedRouteConnection(id=f'connection-{len(result)+1:04d}',from_ref=left,to_ref=right,
            source_edge_index=edge,path_anchor=PixelPoint(x=path[0],y=path[1]),
            device_anchor=PixelPoint(x=anchor[0],y=anchor[1]),evidence_kind=kind,
            evidence_refs=tuple(sorted(item['evidence'])),ambiguity='ambiguous' if item['ambiguous'] else 'unambiguous'))
    return tuple(segments),tuple(result)


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
