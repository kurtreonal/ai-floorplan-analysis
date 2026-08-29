from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories.symbol_legend_repository import list_active_symbol_legends


ERROR_MESSAGES = {
    "SYMBOL_LEGENDS_RETRIEVAL_FAILED": (
        "The approved symbol legend library could not be retrieved."
    ),
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
