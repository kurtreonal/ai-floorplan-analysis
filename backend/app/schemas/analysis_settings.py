from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, model_validator


Elevation = Annotated[StrictInt | StrictFloat, Field(ge=-10000, le=10000, allow_inf_nan=False)]
Scale = Annotated[StrictInt | StrictFloat, Field(ge=0.000001, le=1000000, allow_inf_nan=False)]
Dimension = Annotated[StrictInt, Field(ge=1, le=100000)]


class ApprovalInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    evidence_notes: str = Field(min_length=1, max_length=1000)


class ElevationInput(ApprovalInput):
    elevation_meters: Elevation | None


class ScaleInput(ApprovalInput):
    pixels_per_meter: Scale | None
    reference_width_pixels: Dimension | None
    reference_height_pixels: Dimension | None

    @model_validator(mode="after")
    def complete_reference(self):
        values = (self.pixels_per_meter, self.reference_width_pixels, self.reference_height_pixels)
        if any(value is None for value in values) and not all(value is None for value in values):
            raise ValueError("Scale and both reference dimensions must be supplied together.")
        return self


class ApprovalMetadata(BaseModel):
    revision_id: int | None
    state: Literal["unresolved", "approved"]
    evidence_notes: str | None
    reviewed_by_user_id: int | None
    created_at: datetime | None


class ElevationResponse(ApprovalMetadata):
    unit: Literal["meter"] = "meter"
    elevation_meters: float | None


class ScaleResponse(ApprovalMetadata):
    unit: Literal["pixels_per_meter"] = "pixels_per_meter"
    pixels_per_meter: float | None
    reference_width_pixels: int | None
    reference_height_pixels: int | None


class PageSettingsResponse(BaseModel):
    floor_plan_id: int
    floor_plan_page_id: int
    page_number: int
    scale: ScaleResponse


class AnalysisSettingsResponse(BaseModel):
    project_floor_id: int
    elevation: ElevationResponse
    pages: list[PageSettingsResponse]
