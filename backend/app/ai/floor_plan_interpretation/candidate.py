from __future__ import annotations

import json
import math
import re
from datetime import datetime
from typing import Annotated, Literal, TypeVar, Generic

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    Strict,
    StringConstraints,
    field_validator,
    model_validator,
)


SCHEMA_VERSION = 1
MAXIMUM_JSON_BYTES = 256 * 1024
MAXIMUM_IDENTIFIER = 9_007_199_254_740_991
MAXIMUM_IMAGE_EDGE = 10_000
MAXIMUM_IMAGE_PIXELS = 60_000_000
MAXIMUM_ITEMS = 2_048
ERROR_MESSAGE = "The floor-plan interpretation candidate is invalid."

SafeText = Annotated[str, StringConstraints(min_length=1, max_length=2_000)]
SafeName = Annotated[str, StringConstraints(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_-]*$")]
EntityId = Annotated[str, StringConstraints(min_length=6, max_length=64, pattern=r"^[a-z]+-[0-9]{4,}$")]
Hash256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
PositiveId = Annotated[StrictInt, Field(gt=0, le=MAXIMUM_IDENTIFIER)]
FiniteNumber = Annotated[StrictInt | StrictFloat, Field(allow_inf_nan=False)]
PositiveNumber = Annotated[StrictInt | StrictFloat, Field(gt=0, allow_inf_nan=False)]
NonnegativeNumber = Annotated[StrictInt | StrictFloat, Field(ge=0, allow_inf_nan=False)]


class CandidateContractError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(ERROR_MESSAGE)


def _fail(code: str) -> None:
    raise CandidateContractError(code)


class StrictCandidateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=False)


def _validate_text(value: str) -> str:
    if value != value.strip() or "\x00" in value or any(ord(character) < 32 and character not in "\n\t" for character in value):
        raise ValueError("Text contains unsupported control or surrounding whitespace.")
    return value


class PixelPoint(StrictCandidateModel):
    x: NonnegativeNumber
    y: NonnegativeNumber


class PixelBounds(StrictCandidateModel):
    x: NonnegativeNumber
    y: NonnegativeNumber
    width: PositiveNumber
    height: PositiveNumber


class SourcePlane(StrictCandidateModel):
    coordinate_space: Literal["source_pixel_top_left"] = "source_pixel_top_left"
    width_pixels: Annotated[StrictInt, Field(gt=0, le=MAXIMUM_IMAGE_EDGE)]
    height_pixels: Annotated[StrictInt, Field(gt=0, le=MAXIMUM_IMAGE_EDGE)]

    @model_validator(mode="after")
    def bounded_allocation(self):
        if self.width_pixels * self.height_pixels > MAXIMUM_IMAGE_PIXELS:
            raise ValueError("Source plane exceeds the pixel budget.")
        return self


class AffineTransform(StrictCandidateModel):
    a: FiniteNumber
    b: FiniteNumber
    c: FiniteNumber
    d: FiniteNumber
    e: FiniteNumber
    f: FiniteNumber

    @model_validator(mode="after")
    def reversible(self):
        if math.isclose(float(self.a) * float(self.d) - float(self.b) * float(self.c), 0.0, abs_tol=1e-12):
            raise ValueError("Transform must be reversible.")
        return self


class EvidenceRegion(StrictCandidateModel):
    id: EntityId
    kind: Literal["overview", "legend", "plan_region", "tile"]
    bounds: PixelBounds | None
    local_to_source: AffineTransform


class PageSignals(StrictCandidateModel):
    electrical_content: Literal["visible", "not_visible", "unknown"]
    legend: Literal["visible", "not_visible", "unknown"]
    dimensions: Literal["visible", "not_visible", "unknown"]
    scale_evidence: Literal["visible", "not_visible", "unknown"]
    observed_wiring: Literal["visible", "not_visible", "unknown"]


class PageAssessment(StrictCandidateModel):
    page_type: Literal["electrical_plan", "architectural_plan", "legend", "schedule", "cover", "detail", "unknown"]
    quality: Literal["supported", "degraded", "unsupported", "unknown"]
    signals: PageSignals
    quality_issues: Annotated[tuple[SafeName, ...], Field(max_length=32)] = ()

    @field_validator("quality_issues")
    @classmethod
    def ordered_unique_issues(cls, value):
        if tuple(sorted(set(value))) != value:
            raise ValueError("Quality issues must be unique and ordered.")
        return value


class OcrEvidence(StrictCandidateModel):
    id: EntityId
    region_id: EntityId
    bounds: PixelBounds
    text: SafeText
    normalized_text: SafeText | None

    _safe_text = field_validator("text", "normalized_text")(
        classmethod(lambda cls, value: None if value is None else _validate_text(value))
    )


class EvidenceRefMixin(StrictCandidateModel):
    evidence_refs: Annotated[tuple[str, ...], Field(min_length=1, max_length=32)]
    ambiguity: Literal["clear", "ambiguous", "unknown"]

    @field_validator("evidence_refs")
    @classmethod
    def ordered_unique_evidence(cls, value):
        pattern = re.compile(r"^(region|ocr):[a-z]+-[0-9]{4,}$")
        if any(not pattern.fullmatch(item) for item in value) or tuple(sorted(set(value))) != value:
            raise ValueError("Evidence references must be safe, unique, and ordered.")
        return value


class ScaleProposal(EvidenceRefMixin):
    id: EntityId
    state: Literal["proposed", "unknown", "ambiguous"]
    pixel_distance: PositiveNumber | None
    real_distance: PositiveNumber | None
    real_unit: Literal["millimeter", "centimeter", "meter", "inch", "foot"] | None

    @model_validator(mode="after")
    def complete_measurement(self):
        measurement = (self.pixel_distance, self.real_distance, self.real_unit)
        if self.state == "proposed" and any(item is None for item in measurement):
            raise ValueError("A proposed scale requires a complete measurement.")
        if self.state != "proposed" and any(item is not None for item in measurement):
            raise ValueError("Unknown or ambiguous scale must not invent measurements.")
        return self


class WallCandidate(EvidenceRefMixin):
    id: EntityId
    start: PixelPoint
    end: PixelPoint

    @model_validator(mode="after")
    def nonzero(self):
        if self.start == self.end:
            raise ValueError("Wall endpoints must differ.")
        return self


class RoomCandidate(EvidenceRefMixin):
    id: EntityId
    label: SafeText | None
    boundary: Annotated[tuple[PixelPoint, ...], Field(min_length=3, max_length=256)]

    _safe_label = field_validator("label")(classmethod(lambda cls, value: None if value is None else _validate_text(value)))


class OpeningCandidate(EvidenceRefMixin):
    id: EntityId
    opening_type: Literal["door", "window", "opening", "unknown"]
    start: PixelPoint
    end: PixelPoint
    wall_ref: EntityId | None

    @model_validator(mode="after")
    def nonzero(self):
        if self.start == self.end:
            raise ValueError("Opening endpoints must differ.")
        return self


class SymbolCandidate(EvidenceRefMixin):
    id: EntityId
    mapping_state: Literal["matched", "unknown", "ambiguous"]
    catalog_class_id: PositiveId | None
    observed_label: SafeText | None
    center: PixelPoint
    bounds: PixelBounds | None
    orientation_degrees: Annotated[StrictInt | StrictFloat, Field(ge=0, lt=360, allow_inf_nan=False)] | None

    _safe_label = field_validator("observed_label")(classmethod(lambda cls, value: None if value is None else _validate_text(value)))

    @model_validator(mode="after")
    def class_mapping(self):
        if (self.mapping_state == "matched") != (self.catalog_class_id is not None):
            raise ValueError("Only matched symbols may carry a catalog class ID.")
        return self


class PanelCandidate(EvidenceRefMixin):
    id: EntityId
    label: SafeText | None
    center: PixelPoint
    bounds: PixelBounds | None
    orientation_degrees: Annotated[StrictInt | StrictFloat, Field(ge=0, lt=360, allow_inf_nan=False)] | None

    _safe_label = field_validator("label")(classmethod(lambda cls, value: None if value is None else _validate_text(value)))


class ObservedRouteSegment(EvidenceRefMixin):
    id: EntityId
    route_kind: Literal["observed"] = "observed"
    points: Annotated[tuple[PixelPoint, ...], Field(min_length=2, max_length=512)]

    @model_validator(mode="after")
    def nonzero_segments(self):
        if any(left == right for left, right in zip(self.points, self.points[1:])):
            raise ValueError("Route points must not repeat consecutively.")
        return self


class ObservedRouteConnection(StrictCandidateModel):
    id: EntityId
    from_ref: str
    to_ref: str

    @field_validator("from_ref", "to_ref")
    @classmethod
    def safe_graph_ref(cls, value):
        if not re.fullmatch(r"^(segment|symbol|panel):[a-z]+-[0-9]{4,}$", value):
            raise ValueError("Invalid graph reference.")
        return value


class ObservedRoutes(StrictCandidateModel):
    state: Literal["unavailable", "empty", "completed", "partial", "failed"]
    segments: Annotated[tuple[ObservedRouteSegment, ...], Field(max_length=MAXIMUM_ITEMS)] = ()
    connections: Annotated[tuple[ObservedRouteConnection, ...], Field(max_length=MAXIMUM_ITEMS)] = ()
    failure_reason: SafeText | None = None
    truncated: StrictBool = False

    @model_validator(mode="after")
    def state_matches_content(self):
        has_items = bool(self.segments or self.connections)
        if self.state in {"unavailable", "empty", "failed"} and has_items:
            raise ValueError("This route state cannot contain items.")
        if self.state == "completed" and not self.segments:
            raise ValueError("Use empty when route extraction found no segments.")
        if self.connections and not self.segments:
            raise ValueError("Route connections require segments.")
        if self.state == "failed" and self.failure_reason is None:
            raise ValueError("Failed route extraction requires a reason.")
        if self.state != "failed" and self.failure_reason is not None:
            raise ValueError("Only failed route extraction may carry a reason.")
        if self.truncated and self.state != "partial":
            raise ValueError("Only partial extraction may be truncated.")
        return self


class CandidateWarning(StrictCandidateModel):
    code: SafeName
    severity: Literal["info", "warning", "error"]
    message: SafeText
    entity_refs: Annotated[tuple[str, ...], Field(max_length=64)] = ()

    _safe_message = field_validator("message")(classmethod(lambda cls, value: _validate_text(value)))

    @field_validator("entity_refs")
    @classmethod
    def ordered_unique_refs(cls, value):
        if tuple(sorted(set(value))) != value:
            raise ValueError("Warning references must be unique and ordered.")
        return value


ItemT = TypeVar("ItemT")


class CandidateCollection(StrictCandidateModel, Generic[ItemT]):
    state: Literal["unavailable", "empty", "completed", "partial", "failed"]
    items: Annotated[tuple[ItemT, ...], Field(max_length=MAXIMUM_ITEMS)] = ()
    failure_reason: SafeText | None = None
    truncated: StrictBool = False

    @model_validator(mode="after")
    def state_matches_content(self):
        if self.state in {"unavailable", "empty", "failed"} and self.items:
            raise ValueError("This collection state cannot contain items.")
        if self.state == "completed" and not self.items:
            raise ValueError("Use empty when extraction completed with no items.")
        if self.state == "failed" and self.failure_reason is None:
            raise ValueError("Failed extraction requires a reason.")
        if self.state != "failed" and self.failure_reason is not None:
            raise ValueError("Only failed extraction may carry a failure reason.")
        if self.truncated and self.state != "partial":
            raise ValueError("Only partial extraction may be truncated.")
        return self


class FloorPlanInterpretationPayload(StrictCandidateModel):
    schema_version: Literal[SCHEMA_VERSION]
    document_state: Literal["completed", "partial", "failed"]
    source_plane: SourcePlane
    page: PageAssessment
    regions: Annotated[tuple[EvidenceRegion, ...], Field(min_length=1, max_length=128)]
    ocr: CandidateCollection[OcrEvidence]
    scales: CandidateCollection[ScaleProposal]
    walls: CandidateCollection[WallCandidate]
    rooms: CandidateCollection[RoomCandidate]
    openings: CandidateCollection[OpeningCandidate]
    symbols: CandidateCollection[SymbolCandidate]
    panels: CandidateCollection[PanelCandidate]
    observed_routes: ObservedRoutes
    warnings: Annotated[tuple[CandidateWarning, ...], Field(max_length=256)] = ()

    @model_validator(mode="after")
    def validate_document(self):
        _validate_candidate_document(self)
        return self


class InferenceParameter(StrictCandidateModel):
    name: SafeName
    value: SafeText

    _safe_value = field_validator("value")(classmethod(lambda cls, value: _validate_text(value)))


class CandidateHostProvenance(StrictCandidateModel):
    candidate_run_id: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")]
    processing_job_id: PositiveId
    floor_plan_source_id: PositiveId
    floor_plan_page_id: PositiveId
    source_artifact_id: PositiveId
    source_page_number: Annotated[StrictInt, Field(gt=0, le=50)]
    source_sha256: Hash256
    source_artifact_sha256: Hash256
    expected_width_pixels: Annotated[StrictInt, Field(gt=0, le=MAXIMUM_IMAGE_EDGE)]
    expected_height_pixels: Annotated[StrictInt, Field(gt=0, le=MAXIMUM_IMAGE_EDGE)]
    model_release_id: SafeName
    base_model_revision: SafeText
    adapter_revision: SafeText | None
    prompt_version: SafeName
    runtime_version: SafeText
    inference_parameters: Annotated[tuple[InferenceParameter, ...], Field(max_length=64)]
    created_at: Annotated[datetime, Strict()]

    _safe_versions = field_validator("base_model_revision", "adapter_revision", "runtime_version")(
        classmethod(lambda cls, value: None if value is None else _validate_text(value))
    )

    @field_validator("inference_parameters")
    @classmethod
    def ordered_parameters(cls, value):
        names = tuple(item.name for item in value)
        if tuple(sorted(set(names))) != names:
            raise ValueError("Inference parameters must be unique and ordered.")
        return value

    @field_validator("created_at")
    @classmethod
    def aware_timestamp(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timestamp must include a timezone.")
        return value


class FloorPlanInterpretationCandidate(StrictCandidateModel):
    provenance: CandidateHostProvenance
    review_state: Literal["needs_review"] = "needs_review"
    payload: FloorPlanInterpretationPayload

    @model_validator(mode="after")
    def matching_source_plane(self):
        expected = (self.provenance.expected_width_pixels, self.provenance.expected_height_pixels)
        actual = (self.payload.source_plane.width_pixels, self.payload.source_plane.height_pixels)
        if actual != expected:
            raise ValueError("Payload source plane does not match host provenance.")
        return self


def _ordered_unique(items, *, label: str) -> None:
    identifiers = tuple(item.id for item in items)
    if tuple(sorted(set(identifiers))) != identifiers:
        raise ValueError(f"{label} identifiers must be unique and ordered.")
    expected_prefix = {
        "regions": "region-", "ocr": "ocr-", "scales": "scale-",
        "walls": "wall-", "rooms": "room-", "openings": "opening-",
        "symbols": "symbol-", "panels": "panel-", "route segments": "segment-",
        "route connections": "connection-",
    }[label]
    if any(not identifier.startswith(expected_prefix) for identifier in identifiers):
        raise ValueError(f"{label} identifiers use the wrong type prefix.")


def _inside(point: PixelPoint, plane: SourcePlane) -> bool:
    return float(point.x) <= plane.width_pixels and float(point.y) <= plane.height_pixels


def _bounds_inside(bounds: PixelBounds, plane: SourcePlane) -> bool:
    return float(bounds.x) + float(bounds.width) <= plane.width_pixels and float(bounds.y) + float(bounds.height) <= plane.height_pixels


def _orientation(a: PixelPoint, b: PixelPoint, c: PixelPoint) -> float:
    return (float(b.y) - float(a.y)) * (float(c.x) - float(b.x)) - (float(b.x) - float(a.x)) * (float(c.y) - float(b.y))


def _segments_intersect(a, b, c, d) -> bool:
    return _orientation(a, b, c) * _orientation(a, b, d) < 0 and _orientation(c, d, a) * _orientation(c, d, b) < 0


def _valid_polygon(points: tuple[PixelPoint, ...]) -> bool:
    if points[0] == points[-1] or len(set((float(point.x), float(point.y)) for point in points)) != len(points):
        return False
    area = sum(float(point.x) * float(points[(index + 1) % len(points)].y) - float(points[(index + 1) % len(points)].x) * float(point.y) for index, point in enumerate(points))
    if math.isclose(area, 0.0, abs_tol=1e-9):
        return False
    edges = [(points[index], points[(index + 1) % len(points)]) for index in range(len(points))]
    for left_index, left in enumerate(edges):
        for right_index, right in enumerate(edges):
            if abs(left_index - right_index) <= 1 or {left_index, right_index} == {0, len(edges) - 1}:
                continue
            if _segments_intersect(*left, *right):
                return False
    return True


def _validate_candidate_document(document: FloorPlanInterpretationPayload) -> None:
    collections = (document.ocr, document.scales, document.walls, document.rooms, document.openings, document.symbols, document.panels)
    evidenced_items = tuple(
        item
        for collection in collections[1:]
        for item in collection.items
    )
    for label, items in (
        ("regions", document.regions), ("ocr", document.ocr.items), ("scales", document.scales.items),
        ("walls", document.walls.items), ("rooms", document.rooms.items), ("openings", document.openings.items),
        ("symbols", document.symbols.items), ("panels", document.panels.items),
        ("route segments", document.observed_routes.segments), ("route connections", document.observed_routes.connections),
    ):
        _ordered_unique(items, label=label)
    region_ids = {item.id for item in document.regions}
    ocr_ids = {item.id for item in document.ocr.items}
    evidence_refs = {f"region:{item}" for item in region_ids} | {f"ocr:{item}" for item in ocr_ids}
    entity_refs = {f"{kind}:{item.id}" for kind, values in (
        ("scale", document.scales.items), ("wall", document.walls.items), ("room", document.rooms.items),
        ("opening", document.openings.items), ("symbol", document.symbols.items), ("panel", document.panels.items),
        ("segment", document.observed_routes.segments), ("connection", document.observed_routes.connections),
    ) for item in values}
    for region in document.regions:
        if region.bounds is not None and not _bounds_inside(region.bounds, document.source_plane):
            raise ValueError("Evidence region is outside the source plane.")
    for item in document.ocr.items:
        if item.region_id not in region_ids or not _bounds_inside(item.bounds, document.source_plane):
            raise ValueError("OCR evidence has invalid source bounds or region.")
    for item in evidenced_items + document.observed_routes.segments:
        if any(reference not in evidence_refs for reference in item.evidence_refs):
            raise ValueError("Candidate has a dangling evidence reference.")
    for item in document.walls.items + document.openings.items:
        if not _inside(item.start, document.source_plane) or not _inside(item.end, document.source_plane):
            raise ValueError("Line candidate is outside the source plane.")
    wall_ids = {item.id for item in document.walls.items}
    for item in document.openings.items:
        if item.wall_ref is not None and item.wall_ref not in wall_ids:
            raise ValueError("Opening has a dangling wall reference.")
    for item in document.rooms.items:
        if any(not _inside(point, document.source_plane) for point in item.boundary) or not _valid_polygon(item.boundary):
            raise ValueError("Room polygon is invalid.")
    for item in document.symbols.items + document.panels.items:
        if not _inside(item.center, document.source_plane) or (item.bounds is not None and not _bounds_inside(item.bounds, document.source_plane)):
            raise ValueError("Device candidate is outside the source plane.")
    for item in document.observed_routes.segments:
        if any(not _inside(point, document.source_plane) for point in item.points):
            raise ValueError("Observed route is outside the source plane.")
    for connection in document.observed_routes.connections:
        if connection.from_ref not in entity_refs or connection.to_ref not in entity_refs:
            raise ValueError("Observed route has a dangling graph reference.")
        if connection.from_ref == connection.to_ref:
            raise ValueError("Observed route connection must join distinct references.")
    for warning in document.warnings:
        if any(reference not in entity_refs for reference in warning.entity_refs):
            raise ValueError("Warning has a dangling entity reference.")
    states = tuple(collection.state for collection in collections) + (document.observed_routes.state,)
    if document.document_state == "completed" and any(state in {"partial", "failed"} for state in states):
        raise ValueError("Completed document cannot contain partial or failed extraction.")
    if document.document_state == "failed" and "failed" not in states:
        raise ValueError("Failed document requires a failed extraction area.")


def parse_candidate_payload_json(raw: str | bytes) -> FloorPlanInterpretationPayload:
    if type(raw) not in (str, bytes):
        _fail("INVALID_JSON_TYPE")
    encoded = raw.encode("utf-8") if type(raw) is str else raw
    if len(encoded) > MAXIMUM_JSON_BYTES:
        _fail("OUTPUT_TOO_LARGE")
    try:
        text = encoded.decode("utf-8")
        def object_without_duplicates(pairs):
            result = {}
            for key, item in pairs:
                if key in result:
                    raise ValueError("Duplicate JSON key.")
                result[key] = item
            return result

        value = json.loads(
            text,
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
            object_pairs_hook=object_without_duplicates,
        )
        return FloorPlanInterpretationPayload.model_validate(value)
    except CandidateContractError:
        raise
    except Exception:
        _fail("INVALID_CANDIDATE")


def build_candidate_envelope(payload: FloorPlanInterpretationPayload, provenance: CandidateHostProvenance) -> FloorPlanInterpretationCandidate:
    if type(payload) is not FloorPlanInterpretationPayload or type(provenance) is not CandidateHostProvenance:
        _fail("INVALID_HOST_ENVELOPE")
    try:
        return FloorPlanInterpretationCandidate(provenance=provenance, payload=payload)
    except Exception:
        _fail("INVALID_HOST_ENVELOPE")


def review_record_identity(candidate_run_id: str, kind: str, local_id: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{32}", candidate_run_id) or kind not in {"wall", "room", "opening", "symbol", "panel", "segment", "connection", "scale"} or not re.fullmatch(r"[a-z]+-[0-9]{4,}", local_id):
        _fail("INVALID_REVIEW_IDENTITY")
    return f"vlm:{candidate_run_id}:{kind}:{local_id}"
