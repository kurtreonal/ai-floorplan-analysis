from sqlalchemy import select
from sqlalchemy.orm import Session, load_only, raiseload

from app.models import SymbolLegend


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
