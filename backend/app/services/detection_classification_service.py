from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import DetectionClassCorrection, User
from app.repositories.detection_class_correction_repository import (
    add_class_correction,
    find_latest_class_correction,
    find_symbol_legend_for_snapshot,
    lock_owned_detection_for_classification,
    lock_symbol_legend,
)


ERROR_MESSAGES = {
    "AUTHORIZATION_DENIED": "The authenticated user is not authorized for this action.",
    "DETECTION_NOT_FOUND": "The requested detection was not found.",
    "SYMBOL_LEGEND_UNAVAILABLE": "The selected symbol legend is unavailable.",
    "CLASSIFICATION_PERSISTENCE_FAILED": (
        "The symbol classification correction could not be saved."
    ),
}
MAXIMUM_BIGINT = 9_223_372_036_854_775_807


class DetectionClassificationServiceError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        self.message = ERROR_MESSAGES[code]
        super().__init__(self.message)


@dataclass(frozen=True)
class ClassificationSnapshot:
    symbol_legend_id: int | None
    class_id: int
    class_name: str


@dataclass(frozen=True)
class DetectionClassificationRecord:
    detected_symbol_id: int
    floor_plan_id: int
    processing_job_id: int
    sequence_number: int | None
    old_class: ClassificationSnapshot
    new_class: ClassificationSnapshot
    authoritative_class: ClassificationSnapshot
    corrected_at: datetime | None


def _positive_identifier(value: object, code: str) -> int:
    if type(value) is not int or value <= 0 or value > MAXIMUM_BIGINT:
        raise DetectionClassificationServiceError(code)
    return value


def _snapshot_from_correction(
    correction: DetectionClassCorrection,
    *,
    use_new: bool,
) -> ClassificationSnapshot:
    prefix = "new" if use_new else "old"
    return ClassificationSnapshot(
        symbol_legend_id=getattr(correction, f"{prefix}_symbol_legend_id"),
        class_id=getattr(correction, f"{prefix}_class_id"),
        class_name=getattr(correction, f"{prefix}_class_name"),
    )


def correct_detection_classification(
    database_session: Session,
    *,
    current_user: User,
    floor_plan_id: int,
    processing_job_id: int,
    detected_symbol_id: int,
    symbol_legend_id: int,
) -> DetectionClassificationRecord:
    floor_plan_id = _positive_identifier(floor_plan_id, "DETECTION_NOT_FOUND")
    processing_job_id = _positive_identifier(
        processing_job_id,
        "DETECTION_NOT_FOUND",
    )
    detected_symbol_id = _positive_identifier(
        detected_symbol_id,
        "DETECTION_NOT_FOUND",
    )
    symbol_legend_id = _positive_identifier(
        symbol_legend_id,
        "SYMBOL_LEGEND_UNAVAILABLE",
    )
    if getattr(getattr(current_user, "role", None), "name", None) != "DESIGNER":
        raise DetectionClassificationServiceError("AUTHORIZATION_DENIED")
    owner_id = _positive_identifier(
        getattr(current_user, "id", None),
        "DETECTION_NOT_FOUND",
    )

    try:
        symbol = lock_owned_detection_for_classification(
            database_session,
            floor_plan_id=floor_plan_id,
            processing_job_id=processing_job_id,
            detected_symbol_id=detected_symbol_id,
            owner_id=owner_id,
        )
        if symbol is None:
            raise DetectionClassificationServiceError("DETECTION_NOT_FOUND")
        selected_legend = lock_symbol_legend(
            database_session,
            symbol_legend_id=symbol_legend_id,
        )
        if selected_legend is None or not selected_legend.is_active:
            raise DetectionClassificationServiceError(
                "SYMBOL_LEGEND_UNAVAILABLE"
            )
        latest = find_latest_class_correction(
            database_session,
            detected_symbol_id=detected_symbol_id,
        )
        selected_snapshot = ClassificationSnapshot(
            symbol_legend_id=selected_legend.id,
            class_id=selected_legend.class_id,
            class_name=selected_legend.name,
        )
        if latest is None:
            current_snapshot = ClassificationSnapshot(
                symbol_legend_id=None,
                class_id=symbol.original_class_id,
                class_name=symbol.original_class_name,
            )
        else:
            current_snapshot = _snapshot_from_correction(latest, use_new=True)

        if (
            current_snapshot.class_id == selected_snapshot.class_id
            and current_snapshot.class_name == selected_snapshot.class_name
        ):
            database_session.commit()
            if latest is None:
                return DetectionClassificationRecord(
                    detected_symbol_id=detected_symbol_id,
                    floor_plan_id=floor_plan_id,
                    processing_job_id=processing_job_id,
                    sequence_number=None,
                    old_class=selected_snapshot,
                    new_class=selected_snapshot,
                    authoritative_class=selected_snapshot,
                    corrected_at=None,
                )
            return DetectionClassificationRecord(
                detected_symbol_id=detected_symbol_id,
                floor_plan_id=floor_plan_id,
                processing_job_id=processing_job_id,
                sequence_number=latest.sequence_number,
                old_class=_snapshot_from_correction(latest, use_new=False),
                new_class=current_snapshot,
                authoritative_class=current_snapshot,
                corrected_at=latest.created_at,
            )

        if latest is None:
            mapped_old = find_symbol_legend_for_snapshot(
                database_session,
                class_id=current_snapshot.class_id,
                class_name=current_snapshot.class_name,
            )
            old_snapshot = ClassificationSnapshot(
                symbol_legend_id=(mapped_old.id if mapped_old is not None else None),
                class_id=current_snapshot.class_id,
                class_name=current_snapshot.class_name,
            )
        else:
            old_snapshot = current_snapshot
        correction = DetectionClassCorrection(
            detected_symbol_id=detected_symbol_id,
            reviewer_user_id=owner_id,
            sequence_number=(latest.sequence_number + 1 if latest else 1),
            old_symbol_legend_id=old_snapshot.symbol_legend_id,
            old_class_id=old_snapshot.class_id,
            old_class_name=old_snapshot.class_name,
            new_symbol_legend_id=selected_snapshot.symbol_legend_id,
            new_class_id=selected_snapshot.class_id,
            new_class_name=selected_snapshot.class_name,
        )
        add_class_correction(database_session, correction)
        database_session.commit()
        return DetectionClassificationRecord(
            detected_symbol_id=detected_symbol_id,
            floor_plan_id=floor_plan_id,
            processing_job_id=processing_job_id,
            sequence_number=correction.sequence_number,
            old_class=old_snapshot,
            new_class=selected_snapshot,
            authoritative_class=selected_snapshot,
            corrected_at=correction.created_at,
        )
    except DetectionClassificationServiceError:
        database_session.rollback()
        raise
    except SQLAlchemyError:
        database_session.rollback()
        raise DetectionClassificationServiceError(
            "CLASSIFICATION_PERSISTENCE_FAILED"
        ) from None
