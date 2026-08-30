from sqlalchemy import select
from sqlalchemy.orm import Session, load_only, raiseload

from app.models import (
    FloorPlan,
    ManualSymbol,
    ProcessingJob,
    Project,
    ProjectFloor,
    SymbolLegend,
)


def lock_owned_manual_symbol_context(
    database_session: Session,
    *,
    floor_plan_id: int,
    processing_job_id: int,
    owner_id: int,
) -> ProcessingJob | None:
    return database_session.scalar(
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
            Project.owner_id == owner_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def lock_manual_symbol_legend(
    database_session: Session,
    *,
    symbol_legend_id: int,
) -> SymbolLegend | None:
    return database_session.scalar(
        select(SymbolLegend)
        .options(
            load_only(
                SymbolLegend.id,
                SymbolLegend.class_id,
                SymbolLegend.name,
                SymbolLegend.is_active,
            ),
            raiseload("*"),
        )
        .where(SymbolLegend.id == symbol_legend_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def find_manual_symbol_by_request(
    database_session: Session,
    *,
    created_by_user_id: int,
    placement_request_id: str,
    lock: bool = False,
) -> ManualSymbol | None:
    columns = tuple(
        getattr(ManualSymbol, column.name)
        for column in ManualSymbol.__table__.columns
    )
    statement = (
        select(ManualSymbol)
        .options(load_only(*columns), raiseload("*"))
        .where(
            ManualSymbol.created_by_user_id == created_by_user_id,
            ManualSymbol.placement_request_id == placement_request_id,
        )
        .execution_options(populate_existing=True)
    )
    if lock:
        statement = statement.with_for_update()
    return database_session.scalar(statement)


def add_manual_symbol(
    database_session: Session,
    manual_symbol: ManualSymbol,
) -> None:
    database_session.add(manual_symbol)
    database_session.flush()


def list_manual_symbols(
    database_session: Session,
    *,
    floor_plan_id: int,
    processing_job_id: int,
) -> tuple[ManualSymbol, ...]:
    columns = tuple(
        getattr(ManualSymbol, column.name)
        for column in ManualSymbol.__table__.columns
    )
    return tuple(
        database_session.scalars(
            select(ManualSymbol)
            .options(load_only(*columns), raiseload("*"))
            .where(
                ManualSymbol.floor_plan_id == floor_plan_id,
                ManualSymbol.processing_job_id == processing_job_id,
            )
            .order_by(ManualSymbol.id.asc())
            .execution_options(populate_existing=True)
        ).all()
    )


def processing_job_has_manual_symbols(
    database_session: Session,
    *,
    processing_job_id: int,
) -> bool:
    return (
        database_session.scalar(
            select(ManualSymbol.id)
            .where(ManualSymbol.processing_job_id == processing_job_id)
            .limit(1)
        )
        is not None
    )
