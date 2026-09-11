from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, model_validator

from app.ai.floor_plan_interpretation import FloorPlanInterpretationCandidate


Finite = Annotated[StrictInt | StrictFloat, Field(ge=0, le=1_000_000, allow_inf_nan=False)]
Positive = Annotated[StrictInt | StrictFloat, Field(gt=0, le=1_000, allow_inf_nan=False)]
EntityId = Annotated[
    str,
    Field(pattern=r"^(wall|room|symbol|manual-wall|manual-room|manual-symbol)-[0-9]{4}$"),
]


class DemoSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DemoPoint(DemoSchema):
    x: Finite
    y: Finite


class DemoWallReview(DemoSchema):
    id: EntityId
    disposition: Literal["accepted", "rejected"]
    start: DemoPoint
    end: DemoPoint

    @model_validator(mode="after")
    def nonzero(self):
        if self.start == self.end:
            raise ValueError("Wall endpoints must differ.")
        return self


class DemoRoomReview(DemoSchema):
    id: EntityId
    disposition: Literal["accepted", "rejected"]
    name: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    boundary: Annotated[list[DemoPoint], Field(min_length=3, max_length=256)]


class DemoSymbolReview(DemoSchema):
    id: EntityId
    disposition: Literal["accepted", "rejected"]
    center: DemoPoint
    symbol_legend_id: Annotated[StrictInt, Field(gt=0)] | None = None


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

    @model_validator(mode="after")
    def approval_is_explicit(self):
        if self.approved_for_layout and not self.review_complete:
            raise ValueError("Layout approval requires completed review.")
        dimensions = (self.wall_thickness_meters, self.wall_height_meters)
        if self.approved_for_layout and any(value is None for value in dimensions):
            raise ValueError("Layout approval requires explicit wall dimensions.")
        return self


class DemoReviewedSymbol(DemoSymbolReview):
    class_id: int | None
    class_name: str | None


class DemoReviewResponse(DemoSchema):
    id: int
    candidate_run_id: str
    revision_number: int
    reviewed_by_user_id: int
    review_complete: bool
    approved_for_layout: bool
    wall_thickness_meters: float | None
    wall_height_meters: float | None
    evidence_notes: str
    walls: list[DemoWallReview]
    rooms: list[DemoRoomReview]
    symbols: list[DemoReviewedSymbol]
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
