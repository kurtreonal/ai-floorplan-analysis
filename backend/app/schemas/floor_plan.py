from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FloorPlanUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_floor_id: int
    original_filename: str
    mime_type: str
    file_size: int
    processing_status: Literal["uploaded"]


class FloorPlanListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_floor_id: int
    original_filename: str
    mime_type: str
    file_size: int
    processing_status: str = Field(min_length=1, max_length=32)
