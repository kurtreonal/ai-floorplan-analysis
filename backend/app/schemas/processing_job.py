from typing import Literal

from pydantic import BaseModel, PositiveInt


class ProcessingJobStartResponse(BaseModel):
    job_id: PositiveInt
    status: Literal["queued"]
