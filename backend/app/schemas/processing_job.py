from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, PositiveInt


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


class ProcessingJobHistoryItemResponse(ProcessingJobStatusResponse):
    created_at: datetime
    updated_at: datetime


class ProcessingJobCancellationResponse(BaseModel):
    job_id: PositiveInt
    status: Literal["processing", "cancelled"]
    cancellation_mode: Literal["queued_cancelled", "cooperative_requested"]
