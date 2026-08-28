from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, load_only, raiseload

from app.models import FloorPlan, ProcessingJob, Wall


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


def has_verified_walls(
    database_session: Session,
    *,
    floor_plan_id: int,
) -> bool:
    return database_session.scalar(
        select(Wall.id)
        .where(
            Wall.floor_plan_id == floor_plan_id,
            Wall.status == "verified",
        )
        .limit(1)
    ) is not None


def delete_detected_walls(
    database_session: Session,
    *,
    floor_plan_id: int,
) -> None:
    database_session.execute(
        delete(Wall).where(
            Wall.floor_plan_id == floor_plan_id,
            Wall.status == "detected",
        )
    )


def add_detected_walls(
    database_session: Session,
    walls: Sequence[Wall],
) -> None:
    database_session.add_all(walls)
    database_session.flush()


def list_walls(
    database_session: Session,
    *,
    floor_plan_id: int,
) -> tuple[Wall, ...]:
    return tuple(
        database_session.scalars(
            select(Wall)
            .options(
                load_only(
                    Wall.id,
                    Wall.floor_plan_id,
                    Wall.processing_job_id,
                    Wall.candidate_id,
                    Wall.status,
                    Wall.pixels_per_meter,
                    Wall.raw_start_x,
                    Wall.raw_start_y,
                    Wall.raw_end_x,
                    Wall.raw_end_y,
                    Wall.raw_length_pixels,
                    Wall.canonical_start_x,
                    Wall.canonical_start_y,
                    Wall.canonical_end_x,
                    Wall.canonical_end_y,
                    Wall.canonical_length_meters,
                    Wall.angle_degrees,
                    Wall.created_at,
                    Wall.updated_at,
                ),
                raiseload("*"),
            )
            .where(Wall.floor_plan_id == floor_plan_id)
            .order_by(Wall.candidate_id.asc(), Wall.id.asc())
            .execution_options(populate_existing=True)
        ).all()
    )
