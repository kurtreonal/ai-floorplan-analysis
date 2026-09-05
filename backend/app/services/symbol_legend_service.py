from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import SymbolLegend, SymbolLegendHistory, User
from app.repositories import symbol_legend_repository as repository
from app.repositories.symbol_legend_repository import list_active_symbol_legends
from app.schemas.symbol_legend import SymbolLegendWrite


ERROR_MESSAGES = {
    "SYMBOL_LEGENDS_RETRIEVAL_FAILED": (
        "The approved symbol legend library could not be retrieved."
    ),
    "SYMBOL_LEGEND_NOT_FOUND": "The symbol legend was not found.",
    "SYMBOL_LEGEND_CONFLICT": "The class ID or name is already in use.",
    "SYMBOL_LEGEND_WRITE_FAILED": "The symbol legend change could not be saved.",
}


class SymbolLegendServiceError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        self.message = ERROR_MESSAGES[code]
        super().__init__(self.message)


@dataclass(frozen=True)
class ActiveSymbolLegend:
    id: int
    class_id: int
    name: str


@dataclass(frozen=True)
class ManagedSymbolLegend:
    id: int
    class_id: int
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


def _managed(legend: SymbolLegend) -> ManagedSymbolLegend:
    return ManagedSymbolLegend(
        id=legend.id,
        class_id=legend.class_id,
        name=legend.name,
        is_active=legend.is_active,
        created_at=legend.created_at,
        updated_at=legend.updated_at,
    )


def _history(
    *,
    legend: SymbolLegend,
    actor: User,
    sequence: int,
    action: str,
    old=None,
) -> SymbolLegendHistory:
    return SymbolLegendHistory(
        symbol_legend_id=legend.id,
        sequence=sequence,
        action=action,
        old_class_id=old[0] if old else None,
        old_name=old[1] if old else None,
        old_is_active=old[2] if old else None,
        new_class_id=legend.class_id,
        new_name=legend.name,
        new_is_active=legend.is_active,
        actor_user_id=actor.id,
    )


def retrieve_active_symbol_legends(
    database_session: Session,
) -> tuple[ActiveSymbolLegend, ...]:
    try:
        return tuple(
            ActiveSymbolLegend(
                id=legend.id,
                class_id=legend.class_id,
                name=legend.name,
            )
            for legend in list_active_symbol_legends(database_session)
        )
    except SQLAlchemyError:
        database_session.rollback()
        raise SymbolLegendServiceError(
            "SYMBOL_LEGENDS_RETRIEVAL_FAILED"
        ) from None


def retrieve_all_symbol_legends(
    database_session: Session,
) -> tuple[ManagedSymbolLegend, ...]:
    try:
        return tuple(
            _managed(legend)
            for legend in repository.list_all_symbol_legends(database_session)
        )
    except SQLAlchemyError:
        database_session.rollback()
        raise SymbolLegendServiceError("SYMBOL_LEGENDS_RETRIEVAL_FAILED") from None


def create_symbol_legend(
    database_session: Session,
    *,
    current_user: User,
    data: SymbolLegendWrite,
) -> ManagedSymbolLegend:
    try:
        if repository.find_conflict(
            database_session,
            class_id=data.class_id,
            name=data.name,
        ):
            raise SymbolLegendServiceError("SYMBOL_LEGEND_CONFLICT")
        legend = repository.add_and_flush(database_session, SymbolLegend(**data.model_dump()))
        repository.add_and_flush(database_session, _history(
            legend=legend, actor=current_user, sequence=1, action="created"
        ))
        database_session.commit()
        database_session.refresh(legend)
        return _managed(legend)
    except SymbolLegendServiceError:
        database_session.rollback()
        raise
    except IntegrityError:
        database_session.rollback()
        raise SymbolLegendServiceError("SYMBOL_LEGEND_CONFLICT") from None
    except SQLAlchemyError:
        database_session.rollback()
        raise SymbolLegendServiceError("SYMBOL_LEGEND_WRITE_FAILED") from None


def update_symbol_legend(
    database_session: Session,
    *,
    current_user: User,
    legend_id: int,
    data: SymbolLegendWrite,
) -> ManagedSymbolLegend:
    try:
        legend = repository.find_symbol_legend(database_session, legend_id, lock=True)
        if legend is None:
            raise SymbolLegendServiceError("SYMBOL_LEGEND_NOT_FOUND")
        if repository.find_conflict(
            database_session, class_id=data.class_id, name=data.name, exclude_id=legend.id
        ):
            raise SymbolLegendServiceError("SYMBOL_LEGEND_CONFLICT")
        old = (legend.class_id, legend.name, legend.is_active)
        new = (data.class_id, data.name, data.is_active)
        if old == new:
            database_session.rollback()
            return _managed(legend)
        legend.class_id, legend.name, legend.is_active = new
        action = "updated"
        if old[:2] == new[:2]:
            action = "activated" if data.is_active else "deactivated"
        repository.add_and_flush(database_session, _history(
            legend=legend,
            actor=current_user,
            sequence=repository.next_history_sequence(database_session, legend.id),
            action=action,
            old=old,
        ))
        database_session.commit()
        database_session.refresh(legend)
        return _managed(legend)
    except SymbolLegendServiceError:
        database_session.rollback()
        raise
    except IntegrityError:
        database_session.rollback()
        raise SymbolLegendServiceError("SYMBOL_LEGEND_CONFLICT") from None
    except SQLAlchemyError:
        database_session.rollback()
        raise SymbolLegendServiceError("SYMBOL_LEGEND_WRITE_FAILED") from None
