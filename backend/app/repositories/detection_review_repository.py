from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session, load_only, raiseload

from app.models import (
    DetectedSymbol,
    DetectionReview,
    FloorPlan,
    Project,
    ProjectFloor,
)


def lock_owned_detection(
    database_session: Session,
    *,
    floor_plan_id: int,
    processing_job_id: int,
    detected_symbol_id: int,
    owner_id: int,
) -> DetectedSymbol | None:
    accessible_id = database_session.scalar(
        select(DetectedSymbol.id)
        .join(FloorPlan, DetectedSymbol.floor_plan_id == FloorPlan.id)
        .join(ProjectFloor, FloorPlan.project_floor_id == ProjectFloor.id)
        .join(Project, ProjectFloor.project_id == Project.id)
        .where(
            DetectedSymbol.id == detected_symbol_id,
            DetectedSymbol.floor_plan_id == floor_plan_id,
            DetectedSymbol.processing_job_id == processing_job_id,
            Project.owner_id == owner_id,
        )
    )
    if accessible_id is None:
        return None
    columns = tuple(
        getattr(DetectedSymbol, column.name)
        for column in DetectedSymbol.__table__.columns
    )
    return database_session.scalar(
        select(DetectedSymbol)
        .options(load_only(*columns), raiseload("*"))
        .where(
            DetectedSymbol.id == accessible_id,
            DetectedSymbol.floor_plan_id == floor_plan_id,
            DetectedSymbol.processing_job_id == processing_job_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def find_latest_review(
    database_session: Session,
    *,
    detected_symbol_id: int,
) -> DetectionReview | None:
    return database_session.scalar(
        select(DetectionReview)
        .options(
            load_only(
                DetectionReview.id,
                DetectionReview.detected_symbol_id,
                DetectionReview.reviewer_user_id,
                DetectionReview.sequence_number,
                DetectionReview.decision,
                DetectionReview.created_at,
            ),
            raiseload("*"),
        )
        .where(DetectionReview.detected_symbol_id == detected_symbol_id)
        .order_by(
            DetectionReview.sequence_number.desc(),
            DetectionReview.id.desc(),
        )
        .limit(1)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def add_review(
    database_session: Session,
    review: DetectionReview,
) -> None:
    database_session.add(review)
    database_session.flush()


def list_latest_reviews(
    database_session: Session,
    *,
    detected_symbol_ids: Sequence[int],
) -> tuple[DetectionReview, ...]:
    if not detected_symbol_ids:
        return ()
    latest_sequences = (
        select(
            DetectionReview.detected_symbol_id.label("detected_symbol_id"),
            func.max(DetectionReview.sequence_number).label("sequence_number"),
        )
        .where(DetectionReview.detected_symbol_id.in_(tuple(detected_symbol_ids)))
        .group_by(DetectionReview.detected_symbol_id)
        .subquery()
    )
    return tuple(
        database_session.scalars(
            select(DetectionReview)
            .join(
                latest_sequences,
                (
                    DetectionReview.detected_symbol_id
                    == latest_sequences.c.detected_symbol_id
                )
                & (
                    DetectionReview.sequence_number
                    == latest_sequences.c.sequence_number
                ),
            )
            .options(
                load_only(
                    DetectionReview.id,
                    DetectionReview.detected_symbol_id,
                    DetectionReview.sequence_number,
                    DetectionReview.decision,
                    DetectionReview.created_at,
                ),
                raiseload("*"),
            )
            .order_by(DetectionReview.detected_symbol_id.asc())
            .execution_options(populate_existing=True)
        ).all()
    )
