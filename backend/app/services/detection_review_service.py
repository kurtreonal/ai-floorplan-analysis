from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import DetectionReview, User
from app.repositories.detection_review_repository import (
    add_review,
    find_latest_review,
    lock_owned_detection,
)


ERROR_MESSAGES = {
    "AUTHORIZATION_DENIED": "The authenticated user is not authorized for this action.",
    "DETECTION_NOT_FOUND": "The requested detection was not found.",
    "REVIEW_PERSISTENCE_FAILED": "The detection review could not be saved.",
}
ALLOWED_DECISIONS = frozenset(("confirmed", "deleted"))
MAXIMUM_BIGINT = 9_223_372_036_854_775_807


class DetectionReviewServiceError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        self.message = ERROR_MESSAGES[code]
        super().__init__(self.message)


@dataclass(frozen=True)
class DetectionReviewRecord:
    detected_symbol_id: int
    floor_plan_id: int
    processing_job_id: int
    decision: str
    sequence_number: int
    created_at: datetime


def _positive_identifier(value: object) -> int:
    if type(value) is not int or value <= 0 or value > MAXIMUM_BIGINT:
        raise DetectionReviewServiceError("DETECTION_NOT_FOUND")
    return value


def review_detection(
    database_session: Session,
    *,
    current_user: User,
    floor_plan_id: int,
    processing_job_id: int,
    detected_symbol_id: int,
    decision: str,
) -> DetectionReviewRecord:
    floor_plan_id = _positive_identifier(floor_plan_id)
    processing_job_id = _positive_identifier(processing_job_id)
    detected_symbol_id = _positive_identifier(detected_symbol_id)
    if decision not in ALLOWED_DECISIONS:
        raise DetectionReviewServiceError("REVIEW_PERSISTENCE_FAILED")
    if getattr(getattr(current_user, "role", None), "name", None) != "DESIGNER":
        raise DetectionReviewServiceError("AUTHORIZATION_DENIED")
    owner_id = _positive_identifier(getattr(current_user, "id", None))

    try:
        symbol = lock_owned_detection(
            database_session,
            floor_plan_id=floor_plan_id,
            processing_job_id=processing_job_id,
            detected_symbol_id=detected_symbol_id,
            owner_id=owner_id,
        )
        if symbol is None:
            raise DetectionReviewServiceError("DETECTION_NOT_FOUND")
        latest = find_latest_review(
            database_session,
            detected_symbol_id=detected_symbol_id,
        )
        if latest is not None and latest.decision == decision:
            database_session.commit()
            review = latest
        else:
            review = DetectionReview(
                detected_symbol_id=detected_symbol_id,
                reviewer_user_id=owner_id,
                sequence_number=(latest.sequence_number + 1 if latest else 1),
                decision=decision,
            )
            add_review(database_session, review)
            database_session.commit()
        return DetectionReviewRecord(
            detected_symbol_id=detected_symbol_id,
            floor_plan_id=floor_plan_id,
            processing_job_id=processing_job_id,
            decision=review.decision,
            sequence_number=review.sequence_number,
            created_at=review.created_at,
        )
    except DetectionReviewServiceError:
        database_session.rollback()
        raise
    except SQLAlchemyError:
        database_session.rollback()
        raise DetectionReviewServiceError("REVIEW_PERSISTENCE_FAILED") from None
