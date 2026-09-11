from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable, Literal

from app.geometry.canonical import (
    MAXIMUM_IDENTIFIER,
    MAXIMUM_NAME_LENGTH,
    CanonicalCoordinateSystem,
    CanonicalDocumentWall,
    CanonicalFloor,
    CanonicalGeometryDocument,
    CanonicalGeometryError,
    CanonicalPoint,
    CanonicalRoom,
    CanonicalRoute,
    CanonicalRoutePoint,
    CanonicalSymbol,
    _close,
    _exact_keys,
    _fail,
    _identifier,
    _integer,
    _name,
    _nullable_positive,
    _number,
    _point,
    canonical_geometry_from_dict,
)
from app.geometry.coordinates import rounded_metric

if TYPE_CHECKING:
    from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationCandidate
    from app.ai.floor_plan_interpretation.pseudo_labeling import ReviewDocument
    from app.models.symbol_legend import SymbolLegend

EXTENSION_SCHEMA_VERSION = 2
BASE_SCHEMA_VERSION = 1
MAXIMUM_IMAGE_EDGE = 10_000


@dataclass(frozen=True)
class SourcePlaneReference:
    floor_plan_page_id: int
    source_artifact_id: int
    width_pixels: int
    height_pixels: int

    def to_dict(self) -> dict[str, object]:
        return {
            "floor_plan_page_id": self.floor_plan_page_id,
            "source_artifact_id": self.source_artifact_id,
            "width_pixels": self.width_pixels,
            "height_pixels": self.height_pixels,
        }


@dataclass(frozen=True)
class CanonicalOpening:
    id: int
    source_candidate_id: str | None
    opening_type: str
    start: CanonicalPoint
    end: CanonicalPoint
    associated_wall_id: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "source_candidate_id": self.source_candidate_id,
            "opening_type": self.opening_type,
            "start": self.start.to_dict(),
            "end": self.end.to_dict(),
            "associated_wall_id": self.associated_wall_id,
        }


@dataclass(frozen=True)
class CanonicalPanelBounds:
    width_meters: float
    height_meters: float

    def to_dict(self) -> dict[str, object]:
        return {
            "width_meters": rounded_metric(self.width_meters),
            "height_meters": rounded_metric(self.height_meters),
        }


@dataclass(frozen=True)
class CanonicalPanel:
    id: int
    source_candidate_id: str | None
    name: str | None
    position: CanonicalPoint
    orientation_degrees: float | None = None
    bounds: CanonicalPanelBounds | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "source_candidate_id": self.source_candidate_id,
            "name": self.name,
            "position": self.position.to_dict(),
            "orientation_degrees": (
                None if self.orientation_degrees is None else rounded_metric(self.orientation_degrees)
            ),
            "bounds": None if self.bounds is None else self.bounds.to_dict(),
        }


@dataclass(frozen=True)
class CanonicalSymbolBounds:
    width_meters: float
    height_meters: float

    def to_dict(self) -> dict[str, object]:
        return {
            "width_meters": rounded_metric(self.width_meters),
            "height_meters": rounded_metric(self.height_meters),
        }


@dataclass(frozen=True)
class CanonicalSymbolDetail:
    symbol_id: str
    orientation_degrees: float | None = None
    bounds: CanonicalSymbolBounds | None = None
    provenance: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol_id": self.symbol_id,
            "orientation_degrees": (
                None if self.orientation_degrees is None else rounded_metric(self.orientation_degrees)
            ),
            "bounds": None if self.bounds is None else self.bounds.to_dict(),
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class CanonicalRouteDetail:
    route_id: int
    route_kind: str
    provenance_ref: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "route_id": self.route_id,
            "route_kind": self.route_kind,
            "provenance_ref": self.provenance_ref,
        }


@dataclass(frozen=True)
class CanonicalExtensionV2:
    extension_schema_version: int
    base_schema_version: int
    source_plane_reference: SourcePlaneReference
    openings: tuple[CanonicalOpening, ...]
    panels: tuple[CanonicalPanel, ...]
    symbol_details: tuple[CanonicalSymbolDetail, ...]
    route_details: tuple[CanonicalRouteDetail, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "extension_schema_version": self.extension_schema_version,
            "base_schema_version": self.base_schema_version,
            "source_plane_reference": self.source_plane_reference.to_dict(),
            "openings": [opening.to_dict() for opening in self.openings],
            "panels": [panel.to_dict() for panel in self.panels],
            "symbol_details": [detail.to_dict() for detail in self.symbol_details],
            "route_details": [detail.to_dict() for detail in self.route_details],
        }


def _source_plane_reference(value: object) -> SourcePlaneReference:
    data = _exact_keys(
        value,
        {"floor_plan_page_id", "source_artifact_id", "width_pixels", "height_pixels"},
        "INVALID_SOURCE_PLANE_REFERENCE",
    )
    page_id = _identifier(data["floor_plan_page_id"], "INVALID_SOURCE_PLANE_REFERENCE")
    artifact_id = _identifier(data["source_artifact_id"], "INVALID_SOURCE_PLANE_REFERENCE")
    width = _integer(data["width_pixels"], "INVALID_SOURCE_PLANE_REFERENCE")
    height = _integer(data["height_pixels"], "INVALID_SOURCE_PLANE_REFERENCE")
    if width <= 0 or height <= 0 or width > MAXIMUM_IMAGE_EDGE or height > MAXIMUM_IMAGE_EDGE:
        _fail("INVALID_SOURCE_PLANE_REFERENCE")
    return SourcePlaneReference(page_id, artifact_id, width, height)


def _canonical_point_unbound(value: object, code: str) -> CanonicalPoint:
    data = _exact_keys(value, {"x", "y"}, code)
    x = _number(data["x"], code, nonnegative=True)
    y = _number(data["y"], code, nonnegative=True)
    return CanonicalPoint(x, y)


def _opening(
    value: object,
    coordinate_system: CanonicalCoordinateSystem | None = None,
    valid_wall_ids: set[int] | None = None,
) -> CanonicalOpening:
    data = _exact_keys(
        value,
        {"id", "source_candidate_id", "opening_type", "start", "end", "associated_wall_id"},
        "INVALID_OPENING",
    )
    opening_id = _identifier(data["id"], "INVALID_OPENING")
    source_candidate_id = data["source_candidate_id"]
    if source_candidate_id is not None:
        source_candidate_id = _name(source_candidate_id, "INVALID_OPENING", maximum=128)
    opening_type = data["opening_type"]
    if opening_type not in {"door", "window", "opening", "unknown"}:
        _fail("INVALID_OPENING")
    if coordinate_system is not None:
        start = _point(data["start"], coordinate_system, "INVALID_OPENING")
        end = _point(data["end"], coordinate_system, "INVALID_OPENING")
    else:
        start = _canonical_point_unbound(data["start"], "INVALID_OPENING")
        end = _canonical_point_unbound(data["end"], "INVALID_OPENING")
    if _close(start.x, end.x) and _close(start.y, end.y):
        _fail("INVALID_OPENING")
    associated_wall_id = data["associated_wall_id"]
    if associated_wall_id is not None:
        associated_wall_id = _identifier(associated_wall_id, "INVALID_OPENING")
        if valid_wall_ids is not None and associated_wall_id not in valid_wall_ids:
            _fail("EXTENSION_CROSS_REFERENCE_FAILED")
    return CanonicalOpening(
        id=opening_id,
        source_candidate_id=source_candidate_id,
        opening_type=opening_type,
        start=start,
        end=end,
        associated_wall_id=associated_wall_id,
    )


def _panel(
    value: object,
    coordinate_system: CanonicalCoordinateSystem | None = None,
) -> CanonicalPanel:
    data = _exact_keys(
        value,
        {"id", "source_candidate_id", "name", "position", "orientation_degrees", "bounds"},
        "INVALID_PANEL",
    )
    panel_id = _identifier(data["id"], "INVALID_PANEL")
    source_candidate_id = data["source_candidate_id"]
    if source_candidate_id is not None:
        source_candidate_id = _name(source_candidate_id, "INVALID_PANEL", maximum=128)
    panel_name = _name(data["name"], "INVALID_PANEL", nullable=True)
    if coordinate_system is not None:
        position = _point(data["position"], coordinate_system, "INVALID_PANEL")
    else:
        position = _canonical_point_unbound(data["position"], "INVALID_PANEL")
    orientation_raw = data["orientation_degrees"]
    orientation: float | None = None
    if orientation_raw is not None:
        orientation = _number(orientation_raw, "INVALID_PANEL", nonnegative=True)
        if orientation >= 360:
            _fail("INVALID_PANEL")
    bounds_raw = data["bounds"]
    bounds: CanonicalPanelBounds | None = None
    if bounds_raw is not None:
        b_data = _exact_keys(bounds_raw, {"width_meters", "height_meters"}, "INVALID_PANEL")
        width_m = _number(b_data["width_meters"], "INVALID_PANEL", positive=True)
        height_m = _number(b_data["height_meters"], "INVALID_PANEL", positive=True)
        bounds = CanonicalPanelBounds(width_m, height_m)
    return CanonicalPanel(
        id=panel_id,
        source_candidate_id=source_candidate_id,
        name=panel_name,
        position=position,
        orientation_degrees=orientation,
        bounds=bounds,
    )


def _symbol_detail(
    value: object,
    valid_symbol_ids: set[str] | None = None,
) -> CanonicalSymbolDetail:
    data = _exact_keys(
        value,
        {"symbol_id", "orientation_degrees", "bounds", "provenance"},
        "INVALID_SYMBOL_DETAIL",
    )
    symbol_id = _name(data["symbol_id"], "INVALID_SYMBOL_DETAIL", maximum=128)
    if valid_symbol_ids is not None and symbol_id not in valid_symbol_ids:
        _fail("EXTENSION_CROSS_REFERENCE_FAILED")
    orientation_raw = data["orientation_degrees"]
    orientation: float | None = None
    if orientation_raw is not None:
        orientation = _number(orientation_raw, "INVALID_SYMBOL_DETAIL", nonnegative=True)
        if orientation >= 360:
            _fail("INVALID_SYMBOL_DETAIL")
    bounds_raw = data["bounds"]
    bounds: CanonicalSymbolBounds | None = None
    if bounds_raw is not None:
        b_data = _exact_keys(bounds_raw, {"width_meters", "height_meters"}, "INVALID_SYMBOL_DETAIL")
        width_m = _number(b_data["width_meters"], "INVALID_SYMBOL_DETAIL", positive=True)
        height_m = _number(b_data["height_meters"], "INVALID_SYMBOL_DETAIL", positive=True)
        bounds = CanonicalSymbolBounds(width_m, height_m)
    provenance = _name(data["provenance"], "INVALID_SYMBOL_DETAIL", nullable=True, maximum=255)
    return CanonicalSymbolDetail(
        symbol_id=symbol_id,
        orientation_degrees=orientation,
        bounds=bounds,
        provenance=provenance,
    )


def _route_detail(
    value: object,
    valid_route_ids: set[int] | None = None,
) -> CanonicalRouteDetail:
    data = _exact_keys(
        value,
        {"route_id", "route_kind", "provenance_ref"},
        "INVALID_ROUTE_DETAIL",
    )
    route_id = _identifier(data["route_id"], "INVALID_ROUTE_DETAIL")
    if valid_route_ids is not None and route_id not in valid_route_ids:
        _fail("EXTENSION_CROSS_REFERENCE_FAILED")
    route_kind = data["route_kind"]
    if route_kind not in {"observed", "generated"}:
        _fail("INVALID_ROUTE_DETAIL")
    provenance_ref = _name(data["provenance_ref"], "INVALID_ROUTE_DETAIL", nullable=True, maximum=255)
    return CanonicalRouteDetail(
        route_id=route_id,
        route_kind=route_kind,
        provenance_ref=provenance_ref,
    )


def canonical_extension_from_dict(
    value: object,
    base_document: CanonicalGeometryDocument | None = None,
) -> CanonicalExtensionV2:
    data = _exact_keys(
        value,
        {
            "extension_schema_version",
            "base_schema_version",
            "source_plane_reference",
            "openings",
            "panels",
            "symbol_details",
            "route_details",
        },
        "INVALID_EXTENSION_DOCUMENT",
    )
    if type(data["extension_schema_version"]) is not int or data["extension_schema_version"] != EXTENSION_SCHEMA_VERSION:
        _fail("UNSUPPORTED_EXTENSION_VERSION")
    if type(data["base_schema_version"]) is not int or data["base_schema_version"] != BASE_SCHEMA_VERSION:
        _fail("INVALID_EXTENSION_DOCUMENT")

    source_plane = _source_plane_reference(data["source_plane_reference"])
    cs: CanonicalCoordinateSystem | None = None
    valid_wall_ids: set[int] | None = None
    valid_symbol_ids: set[str] | None = None
    valid_route_ids: set[int] | None = None

    if base_document is not None:
        cs = base_document.coordinate_system
        if (
            source_plane.width_pixels != cs.image_width_pixels
            or source_plane.height_pixels != cs.image_height_pixels
        ):
            _fail("INVALID_SOURCE_PLANE_REFERENCE")
        valid_wall_ids = {wall.id for wall in base_document.walls}
        valid_symbol_ids = {symbol.id for symbol in base_document.symbols}
        valid_route_ids = {route.id for route in base_document.routes}

    if type(data["openings"]) is not list:
        _fail("INVALID_EXTENSION_DOCUMENT")
    openings = tuple(
        _opening(item, cs, valid_wall_ids)
        for item in data["openings"]
    )
    opening_ids = [op.id for op in openings]
    if len(opening_ids) != len(set(opening_ids)):
        _fail("INVALID_OPENING")

    if type(data["panels"]) is not list:
        _fail("INVALID_EXTENSION_DOCUMENT")
    panels = tuple(
        _panel(item, cs)
        for item in data["panels"]
    )
    panel_ids = [p.id for p in panels]
    if len(panel_ids) != len(set(panel_ids)):
        _fail("INVALID_PANEL")

    if type(data["symbol_details"]) is not list:
        _fail("INVALID_EXTENSION_DOCUMENT")
    symbol_details = tuple(
        _symbol_detail(item, valid_symbol_ids)
        for item in data["symbol_details"]
    )
    detail_ids = [d.symbol_id for d in symbol_details]
    if len(detail_ids) != len(set(detail_ids)):
        _fail("INVALID_SYMBOL_DETAIL")

    if type(data["route_details"]) is not list:
        _fail("INVALID_EXTENSION_DOCUMENT")
    route_details = tuple(
        _route_detail(item, valid_route_ids)
        for item in data["route_details"]
    )
    detail_route_ids = [d.route_id for d in route_details]
    if len(detail_route_ids) != len(set(detail_route_ids)):
        _fail("INVALID_ROUTE_DETAIL")

    return CanonicalExtensionV2(
        extension_schema_version=EXTENSION_SCHEMA_VERSION,
        base_schema_version=BASE_SCHEMA_VERSION,
        source_plane_reference=source_plane,
        openings=openings,
        panels=panels,
        symbol_details=symbol_details,
        route_details=route_details,
    )


def compose_canonical_view(
    base_document: CanonicalGeometryDocument,
    extension: CanonicalExtensionV2 | None = None,
) -> dict[str, object]:
    result = base_document.to_dict()
    result["extension"] = extension.to_dict() if extension is not None else None
    return result


def adapt_reviewed_candidate_to_canonical(
    *,
    review_document: ReviewDocument,
    candidate: FloorPlanInterpretationCandidate,
    project_id: int,
    project_floor_id: int,
    floor_name: str,
    floor_sort_order: int,
    floor_elevation_meters: float,
    floor_plan_id: int,
    floor_plan_page_id: int,
    source_artifact_id: int,
    approved_scale_pixels_per_meter: float,
    symbol_legends_by_id: dict[int, SymbolLegend],
    processing_job_id: int,
) -> tuple[CanonicalGeometryDocument, CanonicalExtensionV2]:
    if not review_document.review_complete or not review_document.approved_for_layout:
        _fail("LAYOUT_REVIEW_NOT_APPROVED")

    scale = _number(approved_scale_pixels_per_meter, "INVALID_COORDINATE_SYSTEM", positive=True)
    width_px = candidate.payload.source_plane.width_pixels
    height_px = candidate.payload.source_plane.height_pixels
    width_m = round(width_px / scale, 9)
    height_m = round(height_px / scale, 9)

    # 1. Coordinate system
    cs = CanonicalCoordinateSystem(
        pixels_per_meter=scale,
        image_width_pixels=width_px,
        image_height_pixels=height_px,
        width_meters=width_m,
        height_meters=height_m,
    )

    # 2. Floor
    floor = CanonicalFloor(
        project_floor_id=_identifier(project_floor_id),
        name=_name(floor_name, "INVALID_FLOOR", maximum=100),
        sort_order=_integer(floor_sort_order, "INVALID_FLOOR"),
        elevation_meters=_number(floor_elevation_meters, "INVALID_FLOOR"),
    )

    # 3. Walls (filtered for accepted, corrected, added)
    walls: list[CanonicalDocumentWall] = []
    for index, wall_rev in enumerate(
        (w for w in review_document.walls if w.disposition in ("accepted", "corrected", "added")),
        start=1,
    ):
        start_pt = CanonicalPoint(
            x=round(float(wall_rev.start.x) / scale, 9),
            y=round(float(wall_rev.start.y) / scale, 9),
        )
        end_pt = CanonicalPoint(
            x=round(float(wall_rev.end.x) / scale, 9),
            y=round(float(wall_rev.end.y) / scale, 9),
        )
        delta_x = end_pt.x - start_pt.x
        delta_y = end_pt.y - start_pt.y
        length = round(math.hypot(delta_x, delta_y), 9)
        angle = round(math.degrees(math.atan2(delta_y, delta_x)) % 180, 9)
        walls.append(
            CanonicalDocumentWall(
                id=index,
                source_candidate_id=None if wall_rev.id.startswith("manual-") else (
                    int(wall_rev.id.split("-")[-1]) if wall_rev.id.split("-")[-1].isdigit() else index
                ),
                processing_job_id=processing_job_id,
                status="verified",
                start=start_pt,
                end=end_pt,
                length_meters=length,
                angle_degrees=angle,
                thickness_meters=wall_rev.thickness_meters or review_document.wall_thickness_meters,
                height_meters=wall_rev.height_meters or review_document.wall_height_meters,
            )
        )

    # 4. Rooms (filtered for accepted, corrected, added)
    rooms: list[CanonicalRoom] = []
    for index, room_rev in enumerate(
        (r for r in review_document.rooms if r.disposition in ("accepted", "corrected", "added")),
        start=1,
    ):
        boundary = tuple(
            CanonicalPoint(
                x=round(float(pt.x) / scale, 9),
                y=round(float(pt.y) / scale, 9),
            )
            for pt in room_rev.boundary
        )
        rooms.append(
            CanonicalRoom(
                id=index,
                name=_name(room_rev.name, "INVALID_ROOM", nullable=True),
                boundary=boundary,
            )
        )

    # 5. Symbols & Symbol Details
    symbols: list[CanonicalSymbol] = []
    symbol_details: list[CanonicalSymbolDetail] = []
    for index, sym_rev in enumerate(
        (s for s in review_document.symbols if s.disposition in ("accepted", "corrected", "added")),
        start=1,
    ):
        if sym_rev.symbol_legend_id is None or sym_rev.symbol_legend_id not in symbol_legends_by_id:
            _fail("SYMBOL_MAPPING_REQUIRED")
        legend = symbol_legends_by_id[sym_rev.symbol_legend_id]
        if not legend.is_active:
            _fail("SYMBOL_MAPPING_REQUIRED")

        # Symbol ID format: preserve provenance
        sym_id = f"manual:{index}" if sym_rev.id.startswith("manual-") else f"detected:{index}"
        pos = CanonicalPoint(
            x=round(float(sym_rev.center.x) / scale, 9),
            y=round(float(sym_rev.center.y) / scale, 9),
        )
        status = "manually_added" if sym_rev.id.startswith("manual-") else "confirmed"
        source_type = "manual" if sym_rev.id.startswith("manual-") else "detected"
        symbols.append(
            CanonicalSymbol(
                id=sym_id,
                source_type=source_type,
                source_record_id=index,
                processing_job_id=processing_job_id,
                status=status,
                class_id=legend.class_id,
                class_name=legend.name,
                position=pos,
            )
        )

        bounds: CanonicalSymbolBounds | None = None
        if sym_rev.bbox is not None:
            xmin, ymin, xmax, ymax = sym_rev.bbox
            bw = round(abs(xmax - xmin) / scale, 9)
            bh = round(abs(ymax - ymin) / scale, 9)
            if bw > 0 and bh > 0:
                bounds = CanonicalSymbolBounds(bw, bh)

        symbol_details.append(
            CanonicalSymbolDetail(
                symbol_id=sym_id,
                orientation_degrees=None,
                bounds=bounds,
                provenance=f"vlm:{review_document.candidate_run_id}:symbol:{sym_rev.id}",
            )
        )

    # 6. Observed Routes & Route Details
    routes: list[CanonicalRoute] = []
    route_details: list[CanonicalRouteDetail] = []
    for index, wire_rev in enumerate(
        (w for w in review_document.observed_wiring if w.disposition in ("accepted", "corrected", "added")),
        start=1,
    ):
        route_points = tuple(
            CanonicalRoutePoint(
                project_floor_id=_identifier(project_floor_id),
                x=round(float(pt.x) / scale, 9),
                y=round(float(pt.y) / scale, 9),
                elevation_meters=floor.elevation_meters,
            )
            for pt in wire_rev.points
        )
        routes.append(CanonicalRoute(id=index, points=route_points))
        route_details.append(
            CanonicalRouteDetail(
                route_id=index,
                route_kind="observed",
                provenance_ref=f"vlm:{review_document.candidate_run_id}:wiring:{wire_rev.id}",
            )
        )

    # 7. Openings (in extension v2)
    openings: list[CanonicalOpening] = []
    for index, open_rev in enumerate(
        (o for o in review_document.openings if o.disposition in ("accepted", "corrected", "added")),
        start=1,
    ):
        if len(open_rev.points) >= 2:
            op_start = CanonicalPoint(
                x=round(float(open_rev.points[0].x) / scale, 9),
                y=round(float(open_rev.points[0].y) / scale, 9),
            )
            op_end = CanonicalPoint(
                x=round(float(open_rev.points[1].x) / scale, 9),
                y=round(float(open_rev.points[1].y) / scale, 9),
            )
            openings.append(
                CanonicalOpening(
                    id=index,
                    source_candidate_id=open_rev.id,
                    opening_type=open_rev.kind,
                    start=op_start,
                    end=op_end,
                    associated_wall_id=None,
                )
            )

    # 8. Panels (in extension v2)
    panels: list[CanonicalPanel] = []
    for index, pan_rev in enumerate(
        (p for p in review_document.panels if p.disposition in ("accepted", "corrected", "added")),
        start=1,
    ):
        pan_x = round(float(pan_rev.points[0].x) / scale, 9)
        pan_y = round(float(pan_rev.points[0].y) / scale, 9)
        panels.append(
            CanonicalPanel(
                id=index,
                source_candidate_id=pan_rev.id,
                name=_name(pan_rev.name, "INVALID_PANEL", nullable=True),
                position=CanonicalPoint(pan_x, pan_y),
                orientation_degrees=None,
                bounds=None,
            )
        )

    # 9. Source Plane Reference
    source_plane = SourcePlaneReference(
        floor_plan_page_id=_identifier(floor_plan_page_id),
        source_artifact_id=_identifier(source_artifact_id),
        width_pixels=width_px,
        height_pixels=height_px,
    )

    base_document = CanonicalGeometryDocument(
        schema_version=BASE_SCHEMA_VERSION,
        project_id=_identifier(project_id),
        floor=floor,
        floor_plan_id=_identifier(floor_plan_id),
        coordinate_system=cs,
        walls=tuple(walls),
        rooms=tuple(rooms),
        symbols=tuple(symbols),
        routes=tuple(routes),
    )

    extension = CanonicalExtensionV2(
        extension_schema_version=EXTENSION_SCHEMA_VERSION,
        base_schema_version=BASE_SCHEMA_VERSION,
        source_plane_reference=source_plane,
        openings=tuple(openings),
        panels=tuple(panels),
        symbol_details=tuple(symbol_details),
        route_details=tuple(route_details),
    )

    # Validate against strict schemas
    validated_base = canonical_geometry_from_dict(base_document.to_dict())
    validated_extension = canonical_extension_from_dict(extension.to_dict(), validated_base)

    return validated_base, validated_extension
