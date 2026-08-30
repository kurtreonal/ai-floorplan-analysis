from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.detection import DetectionPointResponse, SymbolClassResponse


DatabaseId = Annotated[int, Field(gt=0, le=9_223_372_036_854_775_807)]
PositivePixelDimension = Annotated[int, Field(gt=0, le=4096)]
SourceCoordinate = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class ManualSymbolPointRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: SourceCoordinate
    y: SourceCoordinate


class ManualSymbolCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    placement_request_id: UUID
    symbol_legend_id: DatabaseId
    center: ManualSymbolPointRequest


class ManualSymbolResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: DatabaseId
    floor_plan_id: DatabaseId
    processing_job_id: DatabaseId
    status: Literal["manually_added"]
    authoritative_class: SymbolClassResponse
    center: DetectionPointResponse
    image_width_pixels: PositivePixelDimension
    image_height_pixels: PositivePixelDimension
    created_at: datetime
