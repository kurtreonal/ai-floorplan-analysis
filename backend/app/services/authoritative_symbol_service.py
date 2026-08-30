from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories.detection_class_correction_repository import (
    list_latest_class_corrections,
)
from app.repositories.detection_result_repository import (
    find_detection_context,
    list_versioned_symbols,
)
from app.repositories.detection_review_repository import list_latest_reviews
from app.repositories.manual_symbol_repository import list_manual_symbols


ERROR_MESSAGE = "Authoritative symbol candidates could not be retrieved."
MAXIMUM_BIGINT = 9_223_372_036_854_775_807


class AuthoritativeSymbolServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthoritativeSymbolCandidate:
    source_type: str
    source_record_id: int
    floor_plan_id: int
    processing_job_id: int
    class_id: int
    class_name: str
    center_x_pixels: float
    center_y_pixels: float
    image_width_pixels: int
    image_height_pixels: int
    status: str


def _positive_identifier(value: object) -> int:
    if type(value) is not int or value <= 0 or value > MAXIMUM_BIGINT:
        raise AuthoritativeSymbolServiceError(ERROR_MESSAGE)
    return value


def retrieve_authoritative_symbol_candidates(
    database_session: Session,
    *,
    floor_plan_id: int,
    processing_job_id: int,
) -> tuple[AuthoritativeSymbolCandidate, ...]:
    floor_plan_id = _positive_identifier(floor_plan_id)
    processing_job_id = _positive_identifier(processing_job_id)
    try:
        context = find_detection_context(
            database_session,
            floor_plan_id=floor_plan_id,
            processing_job_id=processing_job_id,
        )
        if context is None:
            raise AuthoritativeSymbolServiceError(ERROR_MESSAGE)
        detected = list_versioned_symbols(
            database_session,
            floor_plan_id=floor_plan_id,
            processing_job_id=processing_job_id,
        )
        detected_ids = tuple(symbol.id for symbol in detected)
        reviews = {
            review.detected_symbol_id: review
            for review in list_latest_reviews(
                database_session,
                detected_symbol_ids=detected_ids,
            )
        }
        corrections = {
            correction.detected_symbol_id: correction
            for correction in list_latest_class_corrections(
                database_session,
                detected_symbol_ids=detected_ids,
            )
        }
        manual = list_manual_symbols(
            database_session,
            floor_plan_id=floor_plan_id,
            processing_job_id=processing_job_id,
        )
    except AuthoritativeSymbolServiceError:
        raise
    except SQLAlchemyError:
        database_session.rollback()
        raise AuthoritativeSymbolServiceError(ERROR_MESSAGE) from None

    candidates = []
    for symbol in detected:
        review = reviews.get(symbol.id)
        if review is None or review.decision != "confirmed":
            continue
        correction = corrections.get(symbol.id)
        candidates.append(
            AuthoritativeSymbolCandidate(
                source_type="detected",
                source_record_id=symbol.id,
                floor_plan_id=symbol.floor_plan_id,
                processing_job_id=symbol.processing_job_id,
                class_id=(
                    correction.new_class_id
                    if correction is not None
                    else symbol.original_class_id
                ),
                class_name=(
                    correction.new_class_name
                    if correction is not None
                    else symbol.original_class_name
                ),
                center_x_pixels=symbol.center_x_pixels,
                center_y_pixels=symbol.center_y_pixels,
                image_width_pixels=symbol.image_width_pixels,
                image_height_pixels=symbol.image_height_pixels,
                status="confirmed",
            )
        )
    candidates.extend(
        AuthoritativeSymbolCandidate(
            source_type="manual",
            source_record_id=symbol.id,
            floor_plan_id=symbol.floor_plan_id,
            processing_job_id=symbol.processing_job_id,
            class_id=symbol.class_id,
            class_name=symbol.class_name,
            center_x_pixels=symbol.center_x_pixels,
            center_y_pixels=symbol.center_y_pixels,
            image_width_pixels=symbol.image_width_pixels,
            image_height_pixels=symbol.image_height_pixels,
            status="manually_added",
        )
        for symbol in manual
    )
    return tuple(candidates)
