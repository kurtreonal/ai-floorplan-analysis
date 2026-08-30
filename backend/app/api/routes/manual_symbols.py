from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.config import ProcessedDirectoryConfigurationError, get_processed_directory
from app.core.database import get_db
from app.models import User
from app.schemas.detection import DetectionPointResponse, SymbolClassResponse
from app.schemas.manual_symbol import ManualSymbolCreateRequest, ManualSymbolResponse
from app.services.manual_symbol_service import (
    ManualSymbolRecord,
    ManualSymbolServiceError,
    create_manual_symbol,
)


router = APIRouter(prefix="/api/floor-plans", tags=["manual symbols"])
MAXIMUM_BIGINT = 9_223_372_036_854_775_807


def _api_error(*, status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "details": {}}},
    )


def manual_symbol_response(record: ManualSymbolRecord) -> ManualSymbolResponse:
    return ManualSymbolResponse(
        id=record.id,
        floor_plan_id=record.floor_plan_id,
        processing_job_id=record.processing_job_id,
        status="manually_added",
        authoritative_class=SymbolClassResponse(
            id=record.class_id,
            name=record.class_name,
        ),
        center=DetectionPointResponse(
            x=record.center_x_pixels,
            y=record.center_y_pixels,
        ),
        image_width_pixels=record.image_width_pixels,
        image_height_pixels=record.image_height_pixels,
        created_at=record.created_at,
    )


@router.post(
    "/{floor_plan_id}/manual-symbols",
    response_model=ManualSymbolResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_manual_symbol(
    payload: ManualSymbolCreateRequest,
    response: Response,
    request: Request,
    floor_plan_id: Annotated[int, Path(gt=0, le=MAXIMUM_BIGINT)],
    processing_job_id: Annotated[int, Query(gt=0, le=MAXIMUM_BIGINT)],
    current_user: User = Depends(require_roles("DESIGNER")),
    database_session: Session = Depends(get_db),
) -> ManualSymbolResponse:
    try:
        processed_directory = get_processed_directory(request.app.state.settings)
        result = create_manual_symbol(
            database_session,
            current_user=current_user,
            processed_directory=processed_directory,
            floor_plan_id=floor_plan_id,
            processing_job_id=processing_job_id,
            placement_request_id=payload.placement_request_id,
            symbol_legend_id=payload.symbol_legend_id,
            center_x=payload.center.x,
            center_y=payload.center.y,
        )
    except ProcessedDirectoryConfigurationError:
        raise _api_error(
            status_code=status.HTTP_409_CONFLICT,
            code="MANUAL_SYMBOL_PLACEMENT_UNAVAILABLE",
            message="Manual symbol placement is unavailable for this review context.",
        ) from None
    except ManualSymbolServiceError as error:
        status_code = {
            "AUTHORIZATION_DENIED": status.HTTP_403_FORBIDDEN,
            "MANUAL_SYMBOL_CONTEXT_NOT_FOUND": status.HTTP_404_NOT_FOUND,
            "SYMBOL_LEGEND_UNAVAILABLE": status.HTTP_409_CONFLICT,
            "MANUAL_SYMBOL_PLACEMENT_UNAVAILABLE": status.HTTP_409_CONFLICT,
            "PLACEMENT_REQUEST_CONFLICT": status.HTTP_409_CONFLICT,
            "INVALID_MANUAL_SYMBOL_POSITION": status.HTTP_422_UNPROCESSABLE_CONTENT,
        }.get(error.code, status.HTTP_503_SERVICE_UNAVAILABLE)
        safe_codes = {
            "AUTHORIZATION_DENIED",
            "MANUAL_SYMBOL_CONTEXT_NOT_FOUND",
            "SYMBOL_LEGEND_UNAVAILABLE",
            "MANUAL_SYMBOL_PLACEMENT_UNAVAILABLE",
            "PLACEMENT_REQUEST_CONFLICT",
            "INVALID_MANUAL_SYMBOL_POSITION",
            "MANUAL_SYMBOL_PERSISTENCE_FAILED",
        }
        code = error.code if error.code in safe_codes else "MANUAL_SYMBOL_PERSISTENCE_FAILED"
        raise _api_error(
            status_code=status_code,
            code=code,
            message=(
                error.message
                if code == error.code
                else "The manual symbol could not be saved."
            ),
        ) from None

    response.status_code = (
        status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    )
    return manual_symbol_response(result.record)
