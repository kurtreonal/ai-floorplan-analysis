from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Request, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from fastapi.responses import Response
from app.models import SymbolLegend
from app.services.legend_glyph_service import glyph_png
from app.schemas.symbol_legend import LegendReferenceArtworkWrite, LegendAvailabilityWrite, LegendReferenceImageResponse

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
    import_trained_symbol_legends,
)


router = APIRouter(prefix="/api/symbol-legends", tags=["symbol legends"])
admin_router = APIRouter(
    prefix="/api/admin/symbol-legends",
    tags=["symbol legend administration"],
)
LegendId = Annotated[int, Path(gt=0, le=9_223_372_036_854_775_807)]


@admin_router.get('/reference-images', response_model=list[LegendReferenceImageResponse])
def reference_images(_user: User = Depends(require_roles('ADMIN'))):
    from app.services.pec_legend_artwork import reference_images as images
    try:
        return images()
    except (OSError, ValueError, KeyError):
        raise HTTPException(503, 'PEC images are unavailable. You can still upload a symbol image.') from None


@router.get('/reference-images/{reference_id}.png')
def reference_image(reference_id: str, _user: User = Depends(require_roles('ADMIN', 'DESIGNER'))):
    from app.services.pec_legend_artwork import reference_png
    try:
        content = reference_png(reference_id)
    except (OSError, ValueError, KeyError):
        raise HTTPException(404, 'Reference image unavailable.') from None
    return Response(content, media_type='image/png', headers={'Cache-Control': 'private, max-age=3600'})


@admin_router.post('/{legend_id}/reference-artwork')
def save_reference_image(legend_id: LegendId, data: LegendReferenceArtworkWrite, request: Request,
        user: User = Depends(require_roles('ADMIN')), database_session: Session = Depends(get_db)):
    from app.services.local_accounts import require_same_origin
    from app.services.pec_legend_artwork import reference_png
    from app.services.legend_artwork_service import save
    require_same_origin(request)
    try:
        content = reference_png(data.reference_id)
    except (OSError, ValueError, KeyError):
        raise HTTPException(422, 'Choose an available PEC device symbol.') from None
    return save(database_session, user, legend_id, content, legend_ids=data.legend_ids, reference_id=data.reference_id)


@admin_router.put('/availability', response_model=list[SymbolLegendAdminResponse])
def update_availability(data: LegendAvailabilityWrite, request: Request,
        user: User = Depends(require_roles('ADMIN')), database_session: Session = Depends(get_db)):
    from app.services.local_accounts import require_same_origin
    from app.services.symbol_legend_service import set_legend_availability
    require_same_origin(request)
    try:
        return [_admin_response(row) for row in set_legend_availability(database_session, current_user=user, data=data)]
    except SymbolLegendServiceError as error:
        raise _retrieval_error(error) from None


@router.get('/{legend_id}/glyph.png')
def legend_glyph(legend_id: LegendId, _user: User = Depends(require_roles('ADMIN', 'DESIGNER')),
                 database_session: Session = Depends(get_db)):
    from app.services.legend_artwork_service import latest
    uploaded = latest(database_session, legend_id)
    if uploaded:
        return Response(uploaded.png, media_type='image/png', headers={'Cache-Control': 'private, no-cache', 'ETag': f'"{uploaded.sha256}"'})
    legend = database_session.get(SymbolLegend, legend_id)
    try:
        content = glyph_png(legend.name) if legend else None
    except (OSError, ValueError, KeyError):
        content = None
    if content is None:
        raise HTTPException(404, 'Source legend artwork is unavailable for this entry.')
    return Response(content, media_type='image/png', headers={'Cache-Control': 'private, max-age=3600'})


@admin_router.post('/{legend_id}/artwork')
async def upload_legend_artwork(legend_id: LegendId, request: Request, image: UploadFile = File(...),
        user: User = Depends(require_roles('ADMIN')), database_session: Session = Depends(get_db),
        legend_ids: list[int] | None = Form(None)):
    from app.services.local_accounts import require_same_origin
    from app.services.legend_artwork_service import save
    require_same_origin(request)
    content = await image.read(2 * 1024 * 1024 + 1)
    return save(database_session, user, legend_id, content, legend_ids=legend_ids)


def _retrieval_error(error: SymbolLegendServiceError) -> HTTPException:
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    if error.code == "SYMBOL_LEGEND_NOT_FOUND":
        status_code = status.HTTP_404_NOT_FOUND
    elif error.code == "SYMBOL_LEGEND_CONFLICT":
        status_code = status.HTTP_409_CONFLICT
    elif error.code in {"TRAINED_LEGENDS_DEVELOPMENT_ONLY", "SYMBOL_LEGEND_AUTHORITY_REQUIRED"}:
        status_code = status.HTTP_403_FORBIDDEN
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


@admin_router.post("/import-trained", response_model=list[SymbolLegendAdminResponse])
def post_trained_symbol_legends(
    catalog: Literal["trained", "approved-pdf"] = "trained",
    current_user: User = Depends(require_roles("ADMIN")),
    database_session: Session = Depends(get_db),
) -> list[SymbolLegendAdminResponse]:
    try:
        return [_admin_response(row) for row in import_trained_symbol_legends(
            database_session, current_user=current_user, catalog=catalog)]
    except SymbolLegendServiceError as error:
        raise _retrieval_error(error) from None
