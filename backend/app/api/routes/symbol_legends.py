from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.symbol_legend import SymbolLegendResponse
from app.services.symbol_legend_service import (
    SymbolLegendServiceError,
    retrieve_active_symbol_legends,
)


router = APIRouter(prefix="/api/symbol-legends", tags=["symbol legends"])


def _retrieval_error(error: SymbolLegendServiceError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "error": {
                "code": "SYMBOL_LEGENDS_RETRIEVAL_FAILED",
                "message": error.message,
                "details": {},
            }
        },
    )


@router.get(
    "",
    response_model=list[SymbolLegendResponse],
    status_code=status.HTTP_200_OK,
)
def get_symbol_legends(
    _current_user: User = Depends(require_roles("ADMIN", "DESIGNER")),
    database_session: Session = Depends(get_db),
) -> list[SymbolLegendResponse]:
    try:
        legends = retrieve_active_symbol_legends(database_session)
    except SymbolLegendServiceError as error:
        raise _retrieval_error(error) from None
    return [
        SymbolLegendResponse(
            id=legend.id,
            class_id=legend.class_id,
            name=legend.name,
        )
        for legend in legends
    ]
