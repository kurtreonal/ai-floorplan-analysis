from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.symbol_legend import (
    SymbolLegendAdminResponse,
    SymbolLegendResponse,
    SymbolLegendWrite,
)
from app.services.symbol_legend_service import (
    SymbolLegendServiceError,
    create_symbol_legend,
    retrieve_active_symbol_legends,
    retrieve_all_symbol_legends,
    update_symbol_legend,
)


router = APIRouter(prefix="/api/symbol-legends", tags=["symbol legends"])
admin_router = APIRouter(
    prefix="/api/admin/symbol-legends",
    tags=["symbol legend administration"],
)
LegendId = Annotated[int, Path(gt=0, le=9_223_372_036_854_775_807)]


def _retrieval_error(error: SymbolLegendServiceError) -> HTTPException:
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    if error.code == "SYMBOL_LEGEND_NOT_FOUND":
        status_code = status.HTTP_404_NOT_FOUND
    elif error.code == "SYMBOL_LEGEND_CONFLICT":
        status_code = status.HTTP_409_CONFLICT
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": error.code,
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


def _admin_response(legend) -> SymbolLegendAdminResponse:
    return SymbolLegendAdminResponse(
        id=legend.id,
        class_id=legend.class_id,
        name=legend.name,
        is_active=legend.is_active,
        created_at=legend.created_at,
        updated_at=legend.updated_at,
    )


@admin_router.get("", response_model=list[SymbolLegendAdminResponse])
def get_all_symbol_legends(
    _current_user: User = Depends(require_roles("ADMIN")),
    database_session: Session = Depends(get_db),
) -> list[SymbolLegendAdminResponse]:
    try:
        return [
            _admin_response(legend)
            for legend in retrieve_all_symbol_legends(database_session)
        ]
    except SymbolLegendServiceError as error:
        raise _retrieval_error(error) from None


@admin_router.post(
    "",
    response_model=SymbolLegendAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_symbol_legend(
    data: SymbolLegendWrite,
    current_user: User = Depends(require_roles("ADMIN")),
    database_session: Session = Depends(get_db),
) -> SymbolLegendAdminResponse:
    try:
        return _admin_response(
            create_symbol_legend(
                database_session,
                current_user=current_user,
                data=data,
            )
        )
    except SymbolLegendServiceError as error:
        raise _retrieval_error(error) from None


@admin_router.put("/{legend_id}", response_model=SymbolLegendAdminResponse)
def put_symbol_legend(
    legend_id: LegendId,
    data: SymbolLegendWrite,
    current_user: User = Depends(require_roles("ADMIN")),
    database_session: Session = Depends(get_db),
) -> SymbolLegendAdminResponse:
    try:
        return _admin_response(
            update_symbol_legend(
                database_session,
                current_user=current_user,
                legend_id=legend_id,
                data=data,
            )
        )
    except SymbolLegendServiceError as error:
        raise _retrieval_error(error) from None
