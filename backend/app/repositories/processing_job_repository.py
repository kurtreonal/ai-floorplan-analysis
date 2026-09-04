from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.orm import Session, load_only, raiseload

from app.models import ProcessingJob


def _processing_job_read_options():
    return (
        load_only(
            ProcessingJob.id,
            ProcessingJob.job_type,
            ProcessingJob.status,
            ProcessingJob.progress,
            ProcessingJob.error_message,
            ProcessingJob.created_at,
            ProcessingJob.updated_at,
        ),
        raiseload("*"),
    )


def find_processing_job_by_id(
    database_session: Session,
    *,
    job_id: int,
) -> ProcessingJob | None:
    return database_session.scalar(
        select(ProcessingJob)
        .options(*_processing_job_read_options())
        .where(ProcessingJob.id == job_id)
        .execution_options(populate_existing=True)
    )


def find_processing_job_by_id_and_owner(
    database_session: Session,
    *,
    job_id: int,
    owner_id: int,
) -> ProcessingJob | None:
    from app.models import FloorPlan, Project, ProjectFloor

    return database_session.scalar(
        select(ProcessingJob)
        .join(FloorPlan, ProcessingJob.floor_plan_id == FloorPlan.id)
        .join(ProjectFloor, FloorPlan.project_floor_id == ProjectFloor.id)
        .join(Project, ProjectFloor.project_id == Project.id)
        .options(*_processing_job_read_options())
        .where(
            ProcessingJob.id == job_id,
            Project.owner_id == owner_id,
        )
        .execution_options(populate_existing=True)
    )


def find_active_processing_job(
    database_session: Session,
    *,
    floor_plan_id: int,
    job_type: str,
    active_statuses: Collection[str],
) -> ProcessingJob | None:
    return database_session.scalar(
        select(ProcessingJob)
        .options(
            load_only(ProcessingJob.id),
            raiseload("*"),
        )
        .where(
            ProcessingJob.floor_plan_id == floor_plan_id,
            ProcessingJob.job_type == job_type,
            ProcessingJob.status.in_(tuple(active_statuses)),
        )
        .order_by(
            ProcessingJob.created_at.desc(),
            ProcessingJob.id.desc(),
        )
        .limit(1)
    )


def list_processing_jobs_for_floor_plan(
    database_session: Session,
    *,
    floor_plan_id: int,
    job_type: str,
    limit: int,
) -> list[ProcessingJob]:
    return list(
        database_session.scalars(
            select(ProcessingJob)
            .options(*_processing_job_read_options())
            .where(
                ProcessingJob.floor_plan_id == floor_plan_id,
                ProcessingJob.job_type == job_type,
            )
            .order_by(
                ProcessingJob.created_at.desc(),
                ProcessingJob.id.desc(),
            )
            .limit(limit)
            .execution_options(populate_existing=True)
        ).all()
    )


def add_processing_job(
    database_session: Session,
    processing_job: ProcessingJob,
) -> ProcessingJob:
    database_session.add(processing_job)
    database_session.flush()
    return processing_job


def update_processing_job_to_failed(
    database_session: Session,
    *,
    processing_job: ProcessingJob,
    error_message: str,
) -> ProcessingJob:
    processing_job.status = "failed"
    processing_job.error_message = error_message
    database_session.flush()
    return processing_job
