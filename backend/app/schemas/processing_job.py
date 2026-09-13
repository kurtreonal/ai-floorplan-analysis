from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, PositiveInt


class ProcessingJobStartRequest(BaseModel):
    """Optional explicit page selection; omitted means all known pages."""

    page_numbers: list[PositiveInt] | None = Field(default=None, max_length=128)


class ProcessingPageOutcomeResponse(BaseModel):
    page_number: PositiveInt
    selection_state: Literal["selected", "skipped"]
    status: Literal["queued", "processing", "completed", "failed", "cancelled", "timeout", "skipped"]
    progress: int = Field(ge=0, le=100)
    failure_code: str | None = None
    candidate_run_id: str | None = None


class ProcessingJobStartResponse(BaseModel):
    job_id: PositiveInt
    status: Literal["queued"]


class ProcessingJobStatusResponse(BaseModel):
    job_id: PositiveInt
    type: Annotated[str, Field(min_length=1, max_length=64)]
    status: Literal[
        "queued",
        "processing",
        "completed",
        "failed",
        "cancelled",
    ]
    progress: Annotated[int, Field(ge=0, le=100)]
    error_message: str | None
    page_outcomes: list[ProcessingPageOutcomeResponse] = Field(
        default_factory=list,
        exclude_if=lambda value: value == [],
    )


class ProcessingJobHistoryItemResponse(ProcessingJobStatusResponse):
    created_at: datetime
    updated_at: datetime


class ProcessingJobCancellationResponse(BaseModel):
    job_id: PositiveInt
    status: Literal["processing", "cancelled"]
    cancellation_mode: Literal["queued_cancelled", "cooperative_requested"]
