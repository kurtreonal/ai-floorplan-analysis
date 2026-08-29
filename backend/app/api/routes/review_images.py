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
from app.services.review_image_service import (
    MAXIMUM_BIGINT,
    ReviewImageServiceError,
    retrieve_review_image,
)


router = APIRouter(prefix="/api/floor-plans", tags=["detection review images"])


def _api_error(*, status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "details": {}}},
    )


@router.get(
    "/{floor_plan_id}/review-image",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    responses={200: {"content": {"image/png": {}}}},
)
def get_review_image(
    request: Request,
    floor_plan_id: Annotated[int, Path(gt=0, le=MAXIMUM_BIGINT)],
    processing_job_id: Annotated[int, Query(gt=0, le=MAXIMUM_BIGINT)],
    current_user: User = Depends(require_roles("ADMIN", "DESIGNER")),
    database_session: Session = Depends(get_db),
) -> Response:
    try:
        processed_directory = get_processed_directory(request.app.state.settings)
        result = retrieve_review_image(
            database_session,
            current_user=current_user,
            processed_directory=processed_directory,
            floor_plan_id=floor_plan_id,
            processing_job_id=processing_job_id,
        )
    except ProcessedDirectoryConfigurationError:
        raise _api_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="REVIEW_IMAGE_UNAVAILABLE",
            message="The review image could not be retrieved.",
        ) from None
    except ReviewImageServiceError as error:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if error.code == "REVIEW_IMAGE_NOT_FOUND"
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        code = error.code if error.code in {
            "REVIEW_IMAGE_NOT_FOUND",
            "REVIEW_IMAGE_UNAVAILABLE",
        } else "REVIEW_IMAGE_UNAVAILABLE"
        raise _api_error(
            status_code=status_code,
            code=code,
            message=(
                error.message
                if code == error.code
                else "The review image could not be retrieved."
            ),
        ) from None

    return Response(
        content=result.content,
        media_type=result.media_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
