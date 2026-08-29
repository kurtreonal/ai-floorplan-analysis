from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session, load_only, raiseload

from app.models import (
    DetectedSymbol,
    DetectionClassCorrection,
    FloorPlan,
    Project,
    ProjectFloor,
    SymbolLegend,
)


def lock_owned_detection_for_classification(
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
        .where(DetectedSymbol.id == accessible_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def lock_symbol_legend(
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


def find_symbol_legend_for_snapshot(
    database_session: Session,
    *,
    class_id: int,
    class_name: str,
) -> SymbolLegend | None:
    return database_session.scalar(
        select(SymbolLegend)
        .options(load_only(SymbolLegend.id), raiseload("*"))
        .where(
            SymbolLegend.class_id == class_id,
            SymbolLegend.name == class_name,
        )
        .limit(1)
    )


def find_latest_class_correction(
    database_session: Session,
    *,
    detected_symbol_id: int,
) -> DetectionClassCorrection | None:
    columns = tuple(
        getattr(DetectionClassCorrection, column.name)
        for column in DetectionClassCorrection.__table__.columns
    )
    return database_session.scalar(
        select(DetectionClassCorrection)
        .options(load_only(*columns), raiseload("*"))
        .where(
            DetectionClassCorrection.detected_symbol_id == detected_symbol_id
        )
        .order_by(
            DetectionClassCorrection.sequence_number.desc(),
            DetectionClassCorrection.id.desc(),
        )
        .limit(1)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def add_class_correction(
    database_session: Session,
    correction: DetectionClassCorrection,
) -> None:
    database_session.add(correction)
    database_session.flush()


def list_latest_class_corrections(
    database_session: Session,
    *,
    detected_symbol_ids: Sequence[int],
) -> tuple[DetectionClassCorrection, ...]:
    if not detected_symbol_ids:
        return ()
    latest_sequences = (
        select(
            DetectionClassCorrection.detected_symbol_id.label(
                "detected_symbol_id"
            ),
            func.max(DetectionClassCorrection.sequence_number).label(
                "sequence_number"
            ),
        )
        .where(
            DetectionClassCorrection.detected_symbol_id.in_(
                tuple(detected_symbol_ids)
            )
        )
        .group_by(DetectionClassCorrection.detected_symbol_id)
        .subquery()
    )
    columns = tuple(
        getattr(DetectionClassCorrection, column.name)
        for column in DetectionClassCorrection.__table__.columns
    )
    return tuple(
        database_session.scalars(
            select(DetectionClassCorrection)
            .join(
                latest_sequences,
                (
                    DetectionClassCorrection.detected_symbol_id
                    == latest_sequences.c.detected_symbol_id
                )
                & (
                    DetectionClassCorrection.sequence_number
                    == latest_sequences.c.sequence_number
                ),
            )
            .options(load_only(*columns), raiseload("*"))
            .order_by(DetectionClassCorrection.detected_symbol_id.asc())
            .execution_options(populate_existing=True)
        ).all()
    )
