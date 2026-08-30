from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


NonNegativeFloat = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Confidence = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
DatabaseId = Annotated[int, Field(gt=0, le=9_223_372_036_854_775_807)]
NonNegativeInt = Annotated[int, Field(ge=0, le=2_147_483_647)]
PositivePixelDimension = Annotated[int, Field(gt=0, le=4096)]


class DetectionPointResponse(BaseModel):
    x: NonNegativeFloat
    y: NonNegativeFloat


class DetectionPixelPointResponse(BaseModel):
    x: NonNegativeInt
    y: NonNegativeInt


class DetectionBoundingBoxResponse(BaseModel):
    x_min: NonNegativeFloat
    y_min: NonNegativeFloat
    x_max: NonNegativeFloat
    y_max: NonNegativeFloat


class RawWallDetectionResponse(BaseModel):
    start: DetectionPixelPointResponse
    end: DetectionPixelPointResponse
    length_pixels: NonNegativeFloat
    angle_degrees: Annotated[float, Field(ge=0, lt=180, allow_inf_nan=False)]


class CanonicalWallDetectionResponse(BaseModel):
    start: DetectionPointResponse
    end: DetectionPointResponse
    length_meters: NonNegativeFloat
    angle_degrees: Annotated[float, Field(ge=0, lt=180, allow_inf_nan=False)]


class WallDetectionResponse(BaseModel):
    id: DatabaseId
    floor_plan_id: DatabaseId
    processing_job_id: DatabaseId
    candidate_id: Annotated[int, Field(gt=0, le=2_147_483_647)]
    status: Literal["detected", "verified"]
    pixels_per_meter: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    raw_pixels: RawWallDetectionResponse
    canonical: CanonicalWallDetectionResponse
    created_at: datetime
    updated_at: datetime


class SymbolClassResponse(BaseModel):
    id: NonNegativeInt
    name: Annotated[str, Field(min_length=1, max_length=255)]


class DetectionReviewSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["confirmed", "deleted"]
    sequence_number: Annotated[int, Field(gt=0, le=2_147_483_647)]
    reviewed_at: datetime


class DetectionClassCorrectionSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence_number: Annotated[int, Field(gt=0, le=2_147_483_647)]
    old_class: SymbolClassResponse
    new_class: SymbolClassResponse
    corrected_at: datetime


class SymbolDetectionResponse(BaseModel):
    id: DatabaseId
    floor_plan_id: DatabaseId
    processing_job_id: DatabaseId
    prediction_index: Annotated[int, Field(gt=0, le=300)]
    status: Literal["detected", "needs_review"]
    original_class: SymbolClassResponse
    authoritative_class: SymbolClassResponse
    original_confidence: Confidence
    confidence_threshold: Confidence
    image_width_pixels: PositivePixelDimension
    image_height_pixels: PositivePixelDimension
    bounding_box: DetectionBoundingBoxResponse
    center: DetectionPointResponse
    maximum_detections: Literal[300]
    detection_limit_reached: bool
    review: DetectionReviewSummaryResponse | None
    correction: DetectionClassCorrectionSummaryResponse | None
    created_at: datetime
    updated_at: datetime


class ManualSymbolDetectionResponse(BaseModel):
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


class DetectionResultsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    floor_plan_id: DatabaseId
    symbol_processing_job_id: DatabaseId
    walls: list[WallDetectionResponse]
    symbols: list[SymbolDetectionResponse]
    manual_symbols: list[ManualSymbolDetectionResponse]


class DetectionReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["confirmed", "deleted"]


class DetectionReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detected_symbol_id: DatabaseId
    floor_plan_id: DatabaseId
    processing_job_id: DatabaseId
    decision: Literal["confirmed", "deleted"]
    sequence_number: Annotated[int, Field(gt=0, le=2_147_483_647)]
    reviewed_at: datetime


class DetectionClassificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol_legend_id: DatabaseId


class ClassificationSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol_legend_id: DatabaseId | None
    id: NonNegativeInt
    name: Annotated[str, Field(min_length=1, max_length=255)]


class DetectionClassificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detected_symbol_id: DatabaseId
    floor_plan_id: DatabaseId
    processing_job_id: DatabaseId
    sequence_number: Annotated[int, Field(gt=0, le=2_147_483_647)] | None
    old_class: ClassificationSnapshotResponse
    new_class: ClassificationSnapshotResponse
    authoritative_class: ClassificationSnapshotResponse
    corrected_at: datetime | None
