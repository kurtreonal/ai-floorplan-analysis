from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.demo_interpretation import (
    DemoInterpretationResponse,
    DemoLayoutSaveRequest,
    DemoReviewRequest,
    DemoReviewResponse,
)
from app.schemas.layout import LayoutResponse
from app.services.demo_interpretation_service import (
    DemoInterpretationError,
    DemoInterpretationRecord,
    append_interpretation_review,
    retrieve_interpretation,
    save_approved_interpretation_layout,
)


router = APIRouter(tags=["demo floor-plan interpretation"])


def _error(error: DemoInterpretationError) -> HTTPException:
    status_code = {
        "AUTHORIZATION_DENIED": status.HTTP_403_FORBIDDEN,
        "INTERPRETATION_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "STALE_INTERPRETATION_RUN": status.HTTP_409_CONFLICT,
        "STALE_REVIEW_REVISION": status.HTTP_409_CONFLICT,
        "METRIC_INPUTS_UNRESOLVED": status.HTTP_409_CONFLICT,
        "SCALE_REFERENCE_MISMATCH": status.HTTP_409_CONFLICT,
        "SYMBOL_MAPPING_REQUIRED": status.HTTP_409_CONFLICT,
        "LAYOUT_REVIEW_NOT_APPROVED": status.HTTP_409_CONFLICT,
    }.get(error.code, status.HTTP_422_UNPROCESSABLE_CONTENT)
    public_codes = {
        "AUTHORIZATION_DENIED",
        "INTERPRETATION_NOT_FOUND",
        "STALE_INTERPRETATION_RUN",
        "STALE_REVIEW_REVISION",
        "REVIEW_INCOMPLETE",
        "REVIEW_COORDINATE_OUT_OF_BOUNDS",
        "UNKNOWN_CANDIDATE_IDENTITY",
        "DUPLICATE_WALL_IDENTITY",
        "DUPLICATE_ROOM_IDENTITY",
        "DUPLICATE_SYMBOL_IDENTITY",
        "SYMBOL_MAPPING_REQUIRED",
        "APPROVED_GEOMETRY_EMPTY",
        "LAYOUT_REVIEW_NOT_APPROVED",
        "METRIC_INPUTS_UNRESOLVED",
        "SCALE_REFERENCE_MISMATCH",
        "STALE_LAYOUT_VERSION",
        "IDEMPOTENCY_KEY_CONFLICT",
    }
    code = error.code if error.code in public_codes else "DEMO_INTERPRETATION_FAILED"
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code,
                "message": "The demo interpretation operation could not be completed.",
                "details": {},
            }
        },
    )


def _review(record: DemoInterpretationRecord) -> DemoReviewResponse | None:
    if record.review is None or record.review_document is None:
        return None
    document = dict(record.review_document)
    candidate_run_id = document.pop("candidate_run_id", None)
    if candidate_run_id != record.run.candidate_run_id:
        raise DemoInterpretationError("REVIEW_INTEGRITY_FAILED")
    return DemoReviewResponse(
        id=record.review.id,
        candidate_run_id=record.run.candidate_run_id,
        revision_number=record.review.revision_number,
        reviewed_by_user_id=record.review.reviewed_by_user_id,
        created_at=record.review.created_at,
        **document,
    )


def _response(record: DemoInterpretationRecord) -> DemoInterpretationResponse:
    return DemoInterpretationResponse(
        candidate_run_id=record.run.candidate_run_id,
        processing_job_id=record.run.processing_job_id,
        floor_plan_id=record.run.floor_plan_id,
        floor_plan_page_id=record.run.floor_plan_page_id,
        candidate=record.candidate,
        review=_review(record),
    )


@router.get(
    "/api/floor-plans/{floor_plan_id}/interpretation",
    response_model=DemoInterpretationResponse,
)
def get_interpretation(
    floor_plan_id: Annotated[int, Path(gt=0)],
    current_user: User = Depends(require_roles("ADMIN", "DESIGNER")),
    session: Session = Depends(get_db),
) -> DemoInterpretationResponse:
    try:
        return _response(
            retrieve_interpretation(
                session,
                current_user=current_user,
                floor_plan_id=floor_plan_id,
            )
        )
    except DemoInterpretationError as error:
        raise _error(error) from None


@router.post(
    "/api/floor-plans/{floor_plan_id}/interpretation/reviews",
    response_model=DemoInterpretationResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_interpretation_review(
    payload: DemoReviewRequest,
    floor_plan_id: Annotated[int, Path(gt=0)],
    current_user: User = Depends(require_roles("DESIGNER")),
    session: Session = Depends(get_db),
) -> DemoInterpretationResponse:
    try:
        return _response(
            append_interpretation_review(
                session,
                current_user=current_user,
                floor_plan_id=floor_plan_id,
                payload=payload,
            )
        )
    except DemoInterpretationError as error:
        raise _error(error) from None


@router.post(
    "/api/projects/{project_id}/floors/{project_floor_id}/floor-plans/{floor_plan_id}/interpretation/layout",
    response_model=LayoutResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_interpretation_layout(
    payload: DemoLayoutSaveRequest,
    project_id: Annotated[int, Path(gt=0)],
    project_floor_id: Annotated[int, Path(gt=0)],
    floor_plan_id: Annotated[int, Path(gt=0)],
    current_user: User = Depends(require_roles("DESIGNER")),
    session: Session = Depends(get_db),
) -> LayoutResponse:
    try:
        record = save_approved_interpretation_layout(
            session,
            current_user=current_user,
            project_id=project_id,
            project_floor_id=project_floor_id,
            floor_plan_id=floor_plan_id,
            candidate_run_id=payload.candidate_run_id,
            review_revision_number=payload.review_revision_number,
            expected_layout_version_number=payload.expected_layout_version_number,
            idempotency_key=payload.idempotency_key,
        )
    except DemoInterpretationError as error:
        raise _error(error) from None
    return LayoutResponse(
        id=record.id,
        project_id=record.project_id,
        project_floor_id=record.project_floor_id,
        floor_plan_id=record.floor_plan_id,
        version_number=record.version_number,
        schema_version=record.schema_version,
        is_current=True,
        created_at=record.created_at,
        geometry=record.geometry.to_dict(),
    )
