from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, load_only, raiseload

from app.models import SymbolLegend, SymbolLegendHistory


def list_active_symbol_legends(
    database_session: Session,
) -> tuple[SymbolLegend, ...]:
    return tuple(
        database_session.scalars(
            select(SymbolLegend)
            .options(
                load_only(
                    SymbolLegend.id,
                    SymbolLegend.class_id,
                    SymbolLegend.name,
                ),
                raiseload("*"),
            )
            .where(SymbolLegend.is_active.is_(True))
            .order_by(SymbolLegend.class_id.asc(), SymbolLegend.id.asc())
            .execution_options(populate_existing=True)
        ).all()
    )


def list_all_symbol_legends(database_session: Session) -> tuple[SymbolLegend, ...]:
    return tuple(
        database_session.scalars(
            select(SymbolLegend)
            .options(raiseload("*"))
            .order_by(SymbolLegend.class_id, SymbolLegend.id)
            .execution_options(populate_existing=True)
        ).all()
    )


def find_symbol_legend(
    database_session: Session,
    legend_id: int,
    *,
    lock: bool = False,
) -> SymbolLegend | None:
    query = (
        select(SymbolLegend)
        .where(SymbolLegend.id == legend_id)
        .options(raiseload("*"))
    )
    if lock:
        query = query.with_for_update()
    return database_session.scalar(query)


def find_conflict(
    database_session: Session,
    *,
    class_id: int,
    name: str,
    exclude_id: int | None = None,
) -> SymbolLegend | None:
    query = select(SymbolLegend).where(
        or_(SymbolLegend.class_id == class_id, SymbolLegend.name == name)
    )
    if exclude_id is not None:
        query = query.where(SymbolLegend.id != exclude_id)
    return database_session.scalar(query.limit(1))


def next_history_sequence(database_session: Session, legend_id: int) -> int:
    return int(database_session.scalar(
        select(func.coalesce(func.max(SymbolLegendHistory.sequence), 0)).where(
            SymbolLegendHistory.symbol_legend_id == legend_id
        )
    )) + 1


def add_and_flush(database_session: Session, record):
    database_session.add(record)
    database_session.flush()
    return record
