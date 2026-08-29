from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.detection import (
    CanonicalWallDetectionResponse,
    DetectionBoundingBoxResponse,
    DetectionPixelPointResponse,
    DetectionPointResponse,
    DetectionResultsResponse,
    RawWallDetectionResponse,
    SymbolClassResponse,
    SymbolDetectionResponse,
    WallDetectionResponse,
)
from app.services.detection_result_service import (
    DetectionResults,
    DetectionResultServiceError,
    retrieve_detection_results,
)


router = APIRouter(prefix="/api/floor-plans", tags=["detection results"])


def _api_error(*, status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code,
                "message": message,
                "details": {},
            }
        },
    )


def _response(result: DetectionResults) -> DetectionResultsResponse:
    walls = [
        WallDetectionResponse(
            id=wall.id,
            floor_plan_id=wall.floor_plan_id,
            processing_job_id=wall.processing_job_id,
            candidate_id=wall.candidate_id,
            status=wall.status,
            pixels_per_meter=float(wall.pixels_per_meter),
            raw_pixels=RawWallDetectionResponse(
                start=DetectionPixelPointResponse(
                    x=wall.raw_start_x,
                    y=wall.raw_start_y,
                ),
                end=DetectionPixelPointResponse(
                    x=wall.raw_end_x,
                    y=wall.raw_end_y,
                ),
                length_pixels=float(wall.raw_length_pixels),
                angle_degrees=float(wall.angle_degrees),
            ),
            canonical=CanonicalWallDetectionResponse(
                start=DetectionPointResponse(
                    x=float(wall.canonical_start_x),
                    y=float(wall.canonical_start_y),
                ),
                end=DetectionPointResponse(
                    x=float(wall.canonical_end_x),
                    y=float(wall.canonical_end_y),
                ),
                length_meters=float(wall.canonical_length_meters),
                angle_degrees=float(wall.angle_degrees),
            ),
            created_at=wall.created_at,
            updated_at=wall.updated_at,
        )
        for wall in result.walls
    ]
    symbols = [
        SymbolDetectionResponse(
            id=symbol.id,
            floor_plan_id=symbol.floor_plan_id,
            processing_job_id=symbol.processing_job_id,
            prediction_index=symbol.prediction_index,
            status=symbol.status,
            original_class=SymbolClassResponse(
                id=symbol.original_class_id,
                name=symbol.original_class_name,
            ),
            original_confidence=symbol.original_confidence,
            confidence_threshold=symbol.confidence_threshold,
            image_width_pixels=symbol.image_width_pixels,
            image_height_pixels=symbol.image_height_pixels,
            bounding_box=DetectionBoundingBoxResponse(
                x_min=symbol.bounding_box_x_min_pixels,
                y_min=symbol.bounding_box_y_min_pixels,
                x_max=symbol.bounding_box_x_max_pixels,
                y_max=symbol.bounding_box_y_max_pixels,
            ),
            center=DetectionPointResponse(
                x=symbol.center_x_pixels,
                y=symbol.center_y_pixels,
            ),
            maximum_detections=symbol.maximum_detections,
            detection_limit_reached=symbol.detection_limit_reached,
            created_at=symbol.created_at,
            updated_at=symbol.updated_at,
        )
        for symbol in result.symbols
    ]
    return DetectionResultsResponse(
        floor_plan_id=result.floor_plan_id,
        symbol_processing_job_id=result.symbol_processing_job_id,
        walls=walls,
        symbols=symbols,
    )


@router.get(
    "/{floor_plan_id}/detections",
    response_model=DetectionResultsResponse,
    status_code=status.HTTP_200_OK,
)
def get_detection_results(
    floor_plan_id: Annotated[int, Path(gt=0)],
    processing_job_id: Annotated[int, Query(gt=0)],
    current_user: User = Depends(require_roles("ADMIN", "DESIGNER")),
    database_session: Session = Depends(get_db),
) -> DetectionResultsResponse:
    try:
        result = retrieve_detection_results(
            database_session,
            current_user=current_user,
            floor_plan_id=floor_plan_id,
            processing_job_id=processing_job_id,
        )
    except DetectionResultServiceError as error:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if error.code == "DETECTION_RESULTS_NOT_FOUND"
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        raise _api_error(
            status_code=status_code,
            code=(
                error.code
                if error.code
                in {
                    "DETECTION_RESULTS_NOT_FOUND",
                    "DETECTION_RESULTS_RETRIEVAL_FAILED",
                }
                else "DETECTION_RESULTS_RETRIEVAL_FAILED"
            ),
            message=(
                error.message
                if error.code
                in {
                    "DETECTION_RESULTS_NOT_FOUND",
                    "DETECTION_RESULTS_RETRIEVAL_FAILED",
                }
                else "The detection results could not be retrieved."
            ),
        ) from None

    return _response(result)
