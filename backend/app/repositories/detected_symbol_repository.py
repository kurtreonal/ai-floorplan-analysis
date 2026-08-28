from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, load_only, raiseload

from app.models import DetectedSymbol, FloorPlan, ProcessingJob


def lock_floor_plan(
    database_session: Session,
    *,
    floor_plan_id: int,
) -> FloorPlan | None:
    return database_session.scalar(
        select(FloorPlan)
        .options(load_only(FloorPlan.id), raiseload("*"))
        .where(FloorPlan.id == floor_plan_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def find_processing_job(
    database_session: Session,
    *,
    processing_job_id: int,
) -> ProcessingJob | None:
    return database_session.scalar(
        select(ProcessingJob)
        .options(
            load_only(
                ProcessingJob.id,
                ProcessingJob.floor_plan_id,
                ProcessingJob.job_type,
                ProcessingJob.status,
            ),
            raiseload("*"),
        )
        .where(ProcessingJob.id == processing_job_id)
        .execution_options(populate_existing=True)
    )


def delete_processing_job_detections(
    database_session: Session,
    *,
    processing_job_id: int,
) -> None:
    database_session.execute(
        delete(DetectedSymbol).where(
            DetectedSymbol.processing_job_id == processing_job_id
        )
    )


def add_detected_symbols(
    database_session: Session,
    detected_symbols: Sequence[DetectedSymbol],
) -> None:
    database_session.add_all(detected_symbols)
    database_session.flush()


def list_detected_symbols(
    database_session: Session,
    *,
    floor_plan_id: int,
    processing_job_id: int,
) -> tuple[DetectedSymbol, ...]:
    columns = tuple(
        getattr(DetectedSymbol, column.name)
        for column in DetectedSymbol.__table__.columns
    )
    return tuple(
        database_session.scalars(
            select(DetectedSymbol)
            .options(load_only(*columns), raiseload("*"))
            .where(
                DetectedSymbol.floor_plan_id == floor_plan_id,
                DetectedSymbol.processing_job_id == processing_job_id,
            )
            .order_by(
                DetectedSymbol.prediction_index.asc(),
                DetectedSymbol.id.asc(),
            )
            .execution_options(populate_existing=True)
        ).all()
    )
