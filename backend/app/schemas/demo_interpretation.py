from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, model_validator, model_serializer

from app.ai.floor_plan_interpretation import FloorPlanInterpretationCandidate
from app.geometry.device_mounting import VED_CENTER_HEIGHTS


Finite = Annotated[StrictInt | StrictFloat, Field(ge=0, le=1_000_000, allow_inf_nan=False)]
Positive = Annotated[StrictInt | StrictFloat, Field(gt=0, le=1_000, allow_inf_nan=False)]
EntityId = Annotated[
    str,
    Field(
        pattern=r"^(wall|room|symbol|opening|panel|scale|route|wiring|segment|manual-wall|manual-room|manual-symbol|manual-opening|manual-panel|manual-scale|manual-route|manual-wiring)-[0-9]{4}$"
    ),
]
ReviewDisposition = Literal["accepted", "corrected", "added", "rejected", "unresolved"]
MarkerState = Literal["complete", "pending", "not_applicable"]


class DemoSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DemoPoint(DemoSchema):
    x: Finite
    y: Finite


class DemoWallReview(DemoSchema):
    id: EntityId
    disposition: ReviewDisposition
    start: DemoPoint
    end: DemoPoint
    estimated_thickness_pixels: Positive | None = None
    thickness_meters: Positive | None = None
    height_meters: Positive | None = None

    @model_serializer(mode='wrap')
    def optional_width(self,handler):
        value=handler(self)
        if self.estimated_thickness_pixels is None:value.pop('estimated_thickness_pixels',None)
        for key in ('thickness_meters','height_meters'):
            if getattr(self,key) is None:value.pop(key,None)
        return value

    @model_validator(mode="after")
    def nonzero(self):
        if self.start == self.end:
            raise ValueError("Wall endpoints must differ.")
        return self


class DemoRoomReview(DemoSchema):
    id: EntityId
    disposition: ReviewDisposition
    name: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    boundary: Annotated[list[DemoPoint], Field(min_length=3, max_length=256)]


class DemoSymbolReview(DemoSchema):
    id: EntityId
    disposition: ReviewDisposition
    center: DemoPoint
    symbol_legend_id: Annotated[StrictInt, Field(gt=0)] | None = None
    custom_unit_price: Annotated[StrictInt | StrictFloat, Field(ge=0, le=1_000_000_000, allow_inf_nan=False)] | None = None
    mounting_height_meters: Annotated[StrictInt | StrictFloat, Field(ge=0, le=100, allow_inf_nan=False)] | None = None
    mounting_wall_id: EntityId | None = None
    mounting_reference: Literal['device_center','box_bottom','connection_terminal','legacy_unspecified'] | None = None
    mounting_height_source: Literal['ved_default','drawing','designer'] | None = None
    terminal_offset_meters: Annotated[StrictInt | StrictFloat, Field(ge=-10, le=10, allow_inf_nan=False)] | None = None
    gang_count_confirmed: StrictBool = False

    @model_serializer(mode='wrap')
    def omit_unset_gang_confirmation(self, handler):
        value=handler(self)
        if not self.gang_count_confirmed:value.pop('gang_count_confirmed',None)
        for key in ('mounting_reference','mounting_height_source','terminal_offset_meters'):
            if getattr(self,key) is None:value.pop(key,None)
        return value


class DemoOpeningReview(DemoSchema):
    id: EntityId
    disposition: ReviewDisposition
    kind: Literal["door", "window"]
    points: Annotated[list[DemoPoint], Field(min_length=2, max_length=256)]


class DemoPanelReview(DemoSchema):
    id: EntityId
    disposition: ReviewDisposition
    name: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    points: Annotated[list[DemoPoint], Field(min_length=2, max_length=256)]


class DemoScaleEvidenceReview(DemoSchema):
    id: EntityId
    disposition: ReviewDisposition
    text: Annotated[str, Field(min_length=1, max_length=1000)]
    measured_pixels: Annotated[StrictInt | StrictFloat, Field(gt=0, le=100_000)]
    real_world_meters: Annotated[StrictInt | StrictFloat, Field(gt=0, le=10_000)]


class DemoDeviceAttachment(DemoSchema):
    symbol_id: EntityId
    terminal_id: Annotated[str, Field(pattern=r'^[A-Za-z0-9_.:-]{1,128}$')] | None = None
    point_index: Annotated[StrictInt, Field(ge=0, le=2047)]
    provenance: Literal['designer_attachment', 'source_supported_proposal'] = 'designer_attachment'
    source_connection_id: Annotated[str, Field(pattern=r'^connection-[0-9]{4,}$')] | None = None
    source_candidate_run_id: Annotated[str, Field(pattern=r'^[0-9a-f]{32}$')] | None = None
    evidence_kind: Literal['boundary_contact', 'symbol_occlusion', 'inline_device'] | None = None
    observed_anchor: DemoPoint | None = None
    geometry_version: Literal['center_replace_v0','source_preserving_v1'] = 'center_replace_v0'

    @model_validator(mode='after')
    def source_contact(self):
        if self.provenance == 'source_supported_proposal' and any(value is None for value in (
            self.source_connection_id,self.source_candidate_run_id,self.evidence_kind,self.observed_anchor)):
            raise ValueError('Source proposals require retained run, contact and anchor evidence.')
        return self

    @model_serializer
    def serialize_attachment(self):
        result=dict(symbol_id=self.symbol_id,point_index=self.point_index)
        if self.terminal_id is not None: result['terminal_id'] = self.terminal_id
        if self.provenance == 'source_supported_proposal':
            result.update(provenance=self.provenance,source_connection_id=self.source_connection_id,
                source_candidate_run_id=self.source_candidate_run_id,evidence_kind=self.evidence_kind,
                observed_anchor=self.observed_anchor.model_dump())
            if self.geometry_version != 'center_replace_v0':result['geometry_version']=self.geometry_version
        return result


class DemoJunctionAttachment(DemoSchema):
    junction_id: Annotated[str, Field(pattern=r'^junction-[0-9]{4}$')]
    point_index: Annotated[StrictInt, Field(ge=0, le=2047)]
    source_candidate_run_id: Annotated[str, Field(pattern=r'^[0-9a-f]{32}$')] | None = None
    source_junction_id: Annotated[str, Field(pattern=r'^junction-[0-9]{4}$')] | None = None
    observed_anchor: DemoPoint | None = None

    @model_validator(mode='after')
    def complete_source_evidence(self):
        fields=(self.source_candidate_run_id,self.source_junction_id,self.observed_anchor)
        if any(v is not None for v in fields) and any(v is None for v in fields):
            raise ValueError('Source junction proposals require their run, junction and observed anchor.')
        return self

    @model_serializer(mode='wrap')
    def compatible_shape(self,handler):
        value=handler(self)
        return {key:item for key,item in value.items() if item is not None}


class DemoObservedWiringReview(DemoSchema):
    id: EntityId
    disposition: ReviewDisposition
    points: Annotated[list[DemoPoint], Field(min_length=2, max_length=2048)]
    completeness: Literal["complete", "partial", "unreadable"]
    elevation_meters: Annotated[StrictInt | StrictFloat, Field(ge=-1000, le=10000, allow_inf_nan=False)] | None = None
    line_style: Literal["solid", "dashed", "unknown"] = "unknown"
    installation_method: Literal["concealed_under_floor", "concealed_in_ceiling", "unknown"] = "unknown"
    wiring_legend_id: Annotated[StrictInt, Field(gt=0)] | None = None
    wiring_legend_name: Annotated[str, Field(max_length=255)] | None = None
    device_attachments: Annotated[list[DemoDeviceAttachment], Field(max_length=512)] = []
    junction_attachments: Annotated[list[DemoJunctionAttachment], Field(max_length=512)] = []
    circuit_id: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    vertex_ids: Annotated[list[Annotated[str, Field(pattern=r'^[A-Za-z0-9_.:-]{1,160}$')]], Field(max_length=2048)] | None = None
    network_lineage: Annotated[list[EntityId], Field(max_length=2048)] | None = None
    path_origin: Literal['manual'] | None = None
    source_evidence_required: StrictBool = False
    auto_connect_disabled_endpoints: Annotated[list[Annotated[StrictInt, Field(ge=0, le=2047)]], Field(max_length=512)] = []

    @model_validator(mode="after")
    def endpoint_attachments(self):
        if self.vertex_ids is not None:
            if len(self.vertex_ids) != len(self.points): raise ValueError('Vertex identities must match the path.')
            positions={}
            for identity,point in zip(self.vertex_ids,self.points):
                if identity in positions and positions[identity] != point: raise ValueError('A shared vertex requires one position.')
                positions[identity]=point
        indices = [a.point_index for a in self.device_attachments]
        if len(indices) != len(set(indices)) or any(i >= len(self.points) for i in indices):
            raise ValueError('Attachments require distinct wire vertices.')
        disabled = self.auto_connect_disabled_endpoints
        if len(disabled) != len(set(disabled)) or any(i >= len(self.points) for i in disabled) or set(disabled) & set(indices):
            raise ValueError('Disabled automatic contacts require unattached vertices.')
        junctions = [a.point_index for a in self.junction_attachments]
        if len(junctions) != len(set(junctions)) or any(i >= len(self.points) for i in junctions) or set(junctions) & set(indices):
            raise ValueError('Junctions require distinct vertices without device bindings.')
        return self

    @model_serializer(mode='wrap')
    def preserve_legacy_shape(self, handler):
        value = handler(self)
        if not self.junction_attachments: value.pop('junction_attachments', None)
        if self.circuit_id is None: value.pop('circuit_id', None)
        if self.vertex_ids is None: value.pop('vertex_ids', None)
        if self.network_lineage is None: value.pop('network_lineage', None)
        if self.path_origin is None: value.pop('path_origin', None)
        if value.get('assignment_state') is None: value.pop('assignment_state',None)
        return value


class DemoGeneratedWiringReview(DemoObservedWiringReview):
    """Editable, unmeasured routing draft; never an observed or approved circuit."""
    algorithm: Literal["astar"]
    source_device_id: EntityId
    target_id: EntityId
    target_kind: Literal["visible_trace", "device"]
    suppression_reason: Literal["redundant_observed_connection"] | None = None
    assignment_state: Literal['unresolved'] | None = None

    @model_validator(mode="after")
    def generated_identity(self):
        if self.path_origin is not None:
            raise ValueError('A generated route cannot be relabelled as manual wiring.')
        if not self.id.startswith("manual-route-"):
            raise ValueError("Generated draft wiring requires its own identity.")
        if any(a == b for a,b in zip(self.points,self.points[1:])):
            raise ValueError("Consecutive wiring points must differ.")
        return self


class DemoCompletenessChecklist(DemoSchema):
    symbols: MarkerState = "complete"
    walls: MarkerState = "complete"
    rooms: MarkerState = "complete"
    openings: MarkerState = "not_applicable"
    panels: MarkerState = "not_applicable"
    scale_evidence: MarkerState = "not_applicable"
    observed_wiring: MarkerState = "not_applicable"

    @property
    def complete(self) -> bool:
        return "pending" not in (
            self.symbols,
            self.walls,
            self.rooms,
            self.openings,
            self.panels,
            self.scale_evidence,
            self.observed_wiring,
        )


class DemoDatasetApprovalDecision(DemoSchema):
    decision: Literal["approved", "rejected"]
    assignment_id: Annotated[StrictInt, Field(gt=0)]
    approver_user_id: Annotated[StrictInt, Field(gt=0)]
    decided_at: datetime
    decision_notes: Annotated[str, Field(min_length=1, max_length=2000)]


class DemoReviewRequest(DemoSchema):
    candidate_run_id: Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
    expected_revision_number: Annotated[StrictInt, Field(gt=0)] | None
    review_complete: StrictBool
    approved_for_layout: StrictBool
    wall_thickness_meters: Positive | None
    wall_height_meters: Positive | None
    evidence_notes: Annotated[str, Field(min_length=1, max_length=1000)]
    walls: Annotated[list[DemoWallReview], Field(max_length=2048)]
    rooms: Annotated[list[DemoRoomReview], Field(max_length=2048)]
    symbols: Annotated[list[DemoSymbolReview], Field(max_length=2048)]
    openings: Annotated[list[DemoOpeningReview], Field(max_length=2048)] = []
    panels: Annotated[list[DemoPanelReview], Field(max_length=2048)] = []
    scale_evidence: Annotated[list[DemoScaleEvidenceReview], Field(max_length=2048)] = []
    observed_wiring: Annotated[list[DemoObservedWiringReview], Field(max_length=2048)] = []
    generated_wiring: Annotated[list[DemoGeneratedWiringReview], Field(max_length=2048)] = []
    checklist: DemoCompletenessChecklist | None = None
    dataset_approval: DemoDatasetApprovalDecision | None = None

    @model_validator(mode="after")
    def approval_is_explicit(self):
        from app.geometry.wire_network import wire_networks
        wire_networks([w.model_dump(mode='json') for w in self.observed_wiring]
            + [dict(w.model_dump(mode='json'),origin='generated') for w in self.generated_wiring])
        if self.approved_for_layout and not self.review_complete:
            raise ValueError("Layout approval requires completed review.")
        dimensions = (self.wall_thickness_meters, self.wall_height_meters)
        if self.approved_for_layout and any(value is None for value in dimensions):
            raise ValueError("Layout approval requires explicit wall dimensions.")
        return self


class DemoReviewedSymbol(DemoSymbolReview):
    class_id: int | None = None
    class_name: str | None = None


class DemoReviewResponse(DemoSchema):
    id: int
    candidate_run_id: str
    revision_number: int
    reviewed_by_user_id: int
    review_complete: bool
    approved_for_layout: bool
    wall_thickness_meters: float | None = None
    wall_height_meters: float | None = None
    evidence_notes: str
    walls: list[DemoWallReview] = []
    rooms: list[DemoRoomReview] = []
    symbols: list[DemoReviewedSymbol] = []
    openings: list[DemoOpeningReview] = []
    panels: list[DemoPanelReview] = []
    scale_evidence: list[DemoScaleEvidenceReview] = []
    observed_wiring: list[DemoObservedWiringReview] = []
    generated_wiring: list[DemoGeneratedWiringReview] = []
    checklist: DemoCompletenessChecklist | None = None
    dataset_approval: DemoDatasetApprovalDecision | None = None
    created_at: datetime


class DemoRoutingContext(DemoSchema):
    mounting_defaults: dict[str,float] = Field(default_factory=lambda:dict(VED_CENTER_HEIGHTS))
    pixels_per_meter: Annotated[StrictInt | StrictFloat, Field(gt=0, le=1_000_000, allow_inf_nan=False)] | None = None
    floor_elevation_meters: Annotated[float, Field(ge=-10000, le=10000, allow_inf_nan=False)] | None = None


class DemoInterpretationResponse(DemoSchema):
    candidate_run_id: str
    processing_job_id: int
    floor_plan_id: int
    floor_plan_page_id: int
    candidate: FloorPlanInterpretationCandidate
    review: DemoReviewResponse | None
    observed_wiring: list[DemoObservedWiringReview] = []
    generated_wiring: list[DemoGeneratedWiringReview] = []
    draft_wiring_limitations: list[str] = []
    draft_walls: list[DemoWallReview] | None = None
    draft_review: dict | None = None
    routing_context: DemoRoutingContext = DemoRoutingContext()


class DemoLayoutSaveRequest(DemoSchema):
    candidate_run_id: Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
    review_revision_number: Annotated[StrictInt, Field(gt=0)]
    expected_layout_version_number: Annotated[StrictInt, Field(gt=0)] | None
    idempotency_key: Annotated[
        str,
        Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"),
    ]
