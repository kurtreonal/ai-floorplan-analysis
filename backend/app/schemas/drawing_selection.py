from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ai.floor_plan_interpretation.drawing_region import DrawingRegion


class DrawingRegionProcessingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    intent: Literal["process_drawing_region"]
    candidate_run_id: Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
    expected_source_artifact_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    region: DrawingRegion
    request_id: Annotated[str, Field(min_length=36, max_length=36)]

    @field_validator("request_id")
    @classmethod
    def canonical_request_id(cls, value):
        parsed = UUID(value)
        if parsed.version != 4:
            raise ValueError("A version-4 request identity is required.")
        return str(parsed)
