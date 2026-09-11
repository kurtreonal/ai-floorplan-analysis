from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import FloorPlanInterpretationReview, FloorPlanInterpretationRun


def find_by_processing_job(
    session: Session,
    *,
    processing_job_id: int,
) -> FloorPlanInterpretationRun | None:
    return session.scalar(
        select(FloorPlanInterpretationRun).where(
            FloorPlanInterpretationRun.processing_job_id == processing_job_id
        )
    )


def find_latest_for_floor_plan(
    session: Session,
    *,
    floor_plan_id: int,
) -> FloorPlanInterpretationRun | None:
    return session.scalar(
        select(FloorPlanInterpretationRun)
        .where(FloorPlanInterpretationRun.floor_plan_id == floor_plan_id)
        .order_by(FloorPlanInterpretationRun.id.desc())
        .limit(1)
    )


def add_run(
    session: Session,
    run: FloorPlanInterpretationRun,
) -> FloorPlanInterpretationRun:
    session.add(run)
    session.flush()
    return run


def find_latest_review(
    session: Session,
    *,
    interpretation_run_id: int,
) -> FloorPlanInterpretationReview | None:
    return session.scalar(
        select(FloorPlanInterpretationReview)
        .where(
            FloorPlanInterpretationReview.interpretation_run_id
            == interpretation_run_id
        )
        .order_by(FloorPlanInterpretationReview.revision_number.desc())
        .limit(1)
    )


def find_review_revision(
    session: Session,
    *,
    interpretation_run_id: int,
    revision_number: int,
) -> FloorPlanInterpretationReview | None:
    return session.scalar(
        select(FloorPlanInterpretationReview).where(
            FloorPlanInterpretationReview.interpretation_run_id
            == interpretation_run_id,
            FloorPlanInterpretationReview.revision_number == revision_number,
        )
    )


def next_review_revision(session: Session, *, interpretation_run_id: int) -> int:
    return (
        session.scalar(
            select(func.max(FloorPlanInterpretationReview.revision_number)).where(
                FloorPlanInterpretationReview.interpretation_run_id
                == interpretation_run_id
            )
        )
        or 0
    ) + 1


def add_review(
    session: Session,
    review: FloorPlanInterpretationReview,
) -> FloorPlanInterpretationReview:
    session.add(review)
    session.flush()
    return review
