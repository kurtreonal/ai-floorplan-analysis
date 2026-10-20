from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FloorPlanLifecycleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0, strict=True)
    request_id: UUID


class FloorPlanLifecycleResponse(BaseModel):
    id: int
    project_floor_id: int
    original_filename: str
    revision: int
    removed: bool
    active_jobs: int
    saved_layouts: int
    saved_reviews: int
