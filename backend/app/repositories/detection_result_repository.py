from sqlalchemy import select
from sqlalchemy.orm import Session, load_only, raiseload

from app.models import DetectedSymbol, FloorPlan, ProcessingJob, Project, ProjectFloor, Wall


def _context_statement(*, floor_plan_id: int, processing_job_id: int):
    return (
        select(ProcessingJob)
        .join(FloorPlan, ProcessingJob.floor_plan_id == FloorPlan.id)
        .join(ProjectFloor, FloorPlan.project_floor_id == ProjectFloor.id)
        .join(Project, ProjectFloor.project_id == Project.id)
        .options(
            load_only(
                ProcessingJob.id,
                ProcessingJob.floor_plan_id,
                ProcessingJob.job_type,
            ),
            raiseload("*"),
        )
        .where(
            ProcessingJob.id == processing_job_id,
            ProcessingJob.floor_plan_id == floor_plan_id,
            ProcessingJob.job_type == "floor_plan_analysis",
        )
        .execution_options(populate_existing=True)
    )


def find_detection_context(
    database_session: Session,
    *,
    floor_plan_id: int,
    processing_job_id: int,
) -> ProcessingJob | None:
    return database_session.scalar(
        _context_statement(
            floor_plan_id=floor_plan_id,
            processing_job_id=processing_job_id,
        )
    )


def find_owned_detection_context(
    database_session: Session,
    *,
    floor_plan_id: int,
    processing_job_id: int,
    owner_id: int,
) -> ProcessingJob | None:
    return database_session.scalar(
        _context_statement(
            floor_plan_id=floor_plan_id,
            processing_job_id=processing_job_id,
        ).where(Project.owner_id == owner_id)
    )


def list_current_walls(
    database_session: Session,
    *,
    floor_plan_id: int,
) -> tuple[Wall, ...]:
    columns = tuple(getattr(Wall, column.name) for column in Wall.__table__.columns)
    return tuple(
        database_session.scalars(
            select(Wall)
            .options(load_only(*columns), raiseload("*"))
            .where(Wall.floor_plan_id == floor_plan_id)
            .order_by(Wall.candidate_id.asc(), Wall.id.asc())
            .execution_options(populate_existing=True)
        ).all()
    )


def list_versioned_symbols(
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
