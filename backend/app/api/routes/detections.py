from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.detection import (
    CanonicalWallDetectionResponse,
    DetectionBoundingBoxResponse,
    ClassificationSnapshotResponse,
    DetectionClassificationRequest,
    DetectionClassificationResponse,
    DetectionClassCorrectionSummaryResponse,
    DetectionPixelPointResponse,
    DetectionPointResponse,
    DetectionResultsResponse,
    DetectionReviewRequest,
    DetectionReviewResponse,
    DetectionReviewSummaryResponse,
    RawWallDetectionResponse,
    ManualSymbolDetectionResponse,
    SymbolClassResponse,
    SymbolDetectionResponse,
    WallDetectionResponse,
)
from app.services.detection_classification_service import (
    ClassificationSnapshot,
    DetectionClassificationRecord,
    DetectionClassificationServiceError,
    correct_detection_classification,
)
from app.services.detection_review_service import (
    DetectionReviewRecord,
    DetectionReviewServiceError,
    review_detection,
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
            authoritative_class=SymbolClassResponse(
                id=(
                    result.latest_corrections[symbol.id].new_class_id
                    if symbol.id in result.latest_corrections
                    else symbol.original_class_id
                ),
                name=(
                    result.latest_corrections[symbol.id].new_class_name
                    if symbol.id in result.latest_corrections
                    else symbol.original_class_name
                ),
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
            review=(
                DetectionReviewSummaryResponse(
                    decision=result.latest_reviews[symbol.id].decision,
                    sequence_number=result.latest_reviews[symbol.id].sequence_number,
                    reviewed_at=result.latest_reviews[symbol.id].reviewed_at,
                )
                if symbol.id in result.latest_reviews
                else None
            ),
            correction=(
                DetectionClassCorrectionSummaryResponse(
                    sequence_number=(
                        result.latest_corrections[symbol.id].sequence_number
                    ),
                    old_class=SymbolClassResponse(
                        id=result.latest_corrections[symbol.id].old_class_id,
                        name=result.latest_corrections[symbol.id].old_class_name,
                    ),
                    new_class=SymbolClassResponse(
                        id=result.latest_corrections[symbol.id].new_class_id,
                        name=result.latest_corrections[symbol.id].new_class_name,
                    ),
                    corrected_at=(
                        result.latest_corrections[symbol.id].corrected_at
                    ),
                )
                if symbol.id in result.latest_corrections
                else None
            ),
            created_at=symbol.created_at,
            updated_at=symbol.updated_at,
        )
        for symbol in result.symbols
    ]
    manual_symbols = [
        ManualSymbolDetectionResponse(
            id=symbol.id,
            floor_plan_id=symbol.floor_plan_id,
            processing_job_id=symbol.processing_job_id,
            status="manually_added",
            authoritative_class=SymbolClassResponse(
                id=symbol.class_id,
                name=symbol.class_name,
            ),
            center=DetectionPointResponse(
                x=symbol.center_x_pixels,
                y=symbol.center_y_pixels,
            ),
            image_width_pixels=symbol.image_width_pixels,
            image_height_pixels=symbol.image_height_pixels,
            created_at=symbol.created_at,
        )
        for symbol in result.manual_symbols
    ]
    return DetectionResultsResponse(
        floor_plan_id=result.floor_plan_id,
        symbol_processing_job_id=result.symbol_processing_job_id,
        walls=walls,
        symbols=symbols,
        manual_symbols=manual_symbols,
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


def _review_response(review: DetectionReviewRecord) -> DetectionReviewResponse:
    return DetectionReviewResponse(
        detected_symbol_id=review.detected_symbol_id,
        floor_plan_id=review.floor_plan_id,
        processing_job_id=review.processing_job_id,
        decision=review.decision,
        sequence_number=review.sequence_number,
        reviewed_at=review.created_at,
    )


@router.put(
    "/{floor_plan_id}/detections/{detected_symbol_id}/review",
    response_model=DetectionReviewResponse,
    status_code=status.HTTP_200_OK,
)
def put_detection_review(
    payload: DetectionReviewRequest,
    floor_plan_id: Annotated[int, Path(gt=0)],
    detected_symbol_id: Annotated[int, Path(gt=0)],
    processing_job_id: Annotated[int, Query(gt=0)],
    current_user: User = Depends(require_roles("DESIGNER")),
    database_session: Session = Depends(get_db),
) -> DetectionReviewResponse:
    try:
        review = review_detection(
            database_session,
            current_user=current_user,
            floor_plan_id=floor_plan_id,
            processing_job_id=processing_job_id,
            detected_symbol_id=detected_symbol_id,
            decision=payload.decision,
        )
    except DetectionReviewServiceError as error:
        status_code = {
            "AUTHORIZATION_DENIED": status.HTTP_403_FORBIDDEN,
            "DETECTION_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        }.get(error.code, status.HTTP_503_SERVICE_UNAVAILABLE)
        code = (
            error.code
            if error.code in {
                "AUTHORIZATION_DENIED",
                "DETECTION_NOT_FOUND",
                "REVIEW_PERSISTENCE_FAILED",
            }
            else "REVIEW_PERSISTENCE_FAILED"
        )
        message = (
            error.message
            if code == error.code
            else "The detection review could not be saved."
        )
        raise _api_error(
            status_code=status_code,
            code=code,
            message=message,
        ) from None
    return _review_response(review)


def _classification_snapshot_response(
    snapshot: ClassificationSnapshot,
) -> ClassificationSnapshotResponse:
    return ClassificationSnapshotResponse(
        symbol_legend_id=snapshot.symbol_legend_id,
        id=snapshot.class_id,
        name=snapshot.class_name,
    )


def _classification_response(
    correction: DetectionClassificationRecord,
) -> DetectionClassificationResponse:
    return DetectionClassificationResponse(
        detected_symbol_id=correction.detected_symbol_id,
        floor_plan_id=correction.floor_plan_id,
        processing_job_id=correction.processing_job_id,
        sequence_number=correction.sequence_number,
        old_class=_classification_snapshot_response(correction.old_class),
        new_class=_classification_snapshot_response(correction.new_class),
        authoritative_class=_classification_snapshot_response(
            correction.authoritative_class
        ),
        corrected_at=correction.corrected_at,
    )


@router.put(
    "/{floor_plan_id}/detections/{detected_symbol_id}/classification",
    response_model=DetectionClassificationResponse,
    status_code=status.HTTP_200_OK,
)
def put_detection_classification(
    payload: DetectionClassificationRequest,
    floor_plan_id: Annotated[int, Path(gt=0)],
    detected_symbol_id: Annotated[int, Path(gt=0)],
    processing_job_id: Annotated[int, Query(gt=0)],
    current_user: User = Depends(require_roles("DESIGNER")),
    database_session: Session = Depends(get_db),
) -> DetectionClassificationResponse:
    try:
        correction = correct_detection_classification(
            database_session,
            current_user=current_user,
            floor_plan_id=floor_plan_id,
            processing_job_id=processing_job_id,
            detected_symbol_id=detected_symbol_id,
            symbol_legend_id=payload.symbol_legend_id,
        )
    except DetectionClassificationServiceError as error:
        status_code = {
            "AUTHORIZATION_DENIED": status.HTTP_403_FORBIDDEN,
            "DETECTION_NOT_FOUND": status.HTTP_404_NOT_FOUND,
            "SYMBOL_LEGEND_UNAVAILABLE": status.HTTP_409_CONFLICT,
        }.get(error.code, status.HTTP_503_SERVICE_UNAVAILABLE)
        code = (
            error.code
            if error.code
            in {
                "AUTHORIZATION_DENIED",
                "DETECTION_NOT_FOUND",
                "SYMBOL_LEGEND_UNAVAILABLE",
                "CLASSIFICATION_PERSISTENCE_FAILED",
            }
            else "CLASSIFICATION_PERSISTENCE_FAILED"
        )
        message = (
            error.message
            if code == error.code
            else "The symbol classification correction could not be saved."
        )
        raise _api_error(
            status_code=status_code,
            code=code,
            message=message,
        ) from None
    return _classification_response(correction)
