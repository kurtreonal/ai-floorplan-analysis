from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, model_validator

from app.ai.floor_plan_interpretation import FloorPlanInterpretationCandidate


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


class DemoObservedWiringReview(DemoSchema):
    id: EntityId
    disposition: ReviewDisposition
    points: Annotated[list[DemoPoint], Field(min_length=2, max_length=2048)]
    completeness: Literal["complete", "partial", "unreadable"]
    elevation_meters: Annotated[StrictInt | StrictFloat, Field(ge=-1000, le=10000, allow_inf_nan=False)] | None = None


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
    checklist: DemoCompletenessChecklist | None = None
    dataset_approval: DemoDatasetApprovalDecision | None = None

    @model_validator(mode="after")
    def approval_is_explicit(self):
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
    checklist: DemoCompletenessChecklist | None = None
    dataset_approval: DemoDatasetApprovalDecision | None = None
    created_at: datetime


class DemoInterpretationResponse(DemoSchema):
    candidate_run_id: str
    processing_job_id: int
    floor_plan_id: int
    floor_plan_page_id: int
    candidate: FloorPlanInterpretationCandidate
    review: DemoReviewResponse | None


class DemoLayoutSaveRequest(DemoSchema):
    candidate_run_id: Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
    review_revision_number: Annotated[StrictInt, Field(gt=0)]
    expected_layout_version_number: Annotated[StrictInt, Field(gt=0)] | None
    idempotency_key: Annotated[
        str,
        Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"),
    ]
