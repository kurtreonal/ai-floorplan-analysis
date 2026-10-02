from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.estimate import EstimateOptions, EstimateResponse, EstimateWrite
from app.services import estimate_service as service
from app.services.layout_service import LayoutServiceError
from app.services.project_service import ProjectNotFoundError

router = APIRouter(prefix="/api/projects", tags=["estimates"])
ProjectId = Annotated[int, Path(gt=0)]


def execute(session, action):
    try:
        return action()
    except (service.EstimateError, LayoutServiceError, ProjectNotFoundError, SQLAlchemyError, ValueError) as error:
        session.rollback()
        if isinstance(error, SQLAlchemyError):
            code, status = "ESTIMATE_STORAGE_UNAVAILABLE", 503
        elif isinstance(error, ProjectNotFoundError):
            code, status = "PROJECT_NOT_FOUND", 404
        elif isinstance(error, (service.EstimateError, LayoutServiceError)):
            code = error.code
            status = 403 if code == "AUTHORIZATION_DENIED" else 404 if code.endswith("NOT_FOUND") else 409 if code in {"STALE_ROUTE", "ESTIMATE_RETRY_CONFLICT"} else 422
        else:
            code, status = "INVALID_ESTIMATE_SOURCE", 422
        raise HTTPException(status, detail={"error": {"code": code,
            "message": "The estimate operation could not be completed.", "details": {}}}) from None


@router.get("/{project_id}/estimate-options", response_model=EstimateOptions)
def options(project_id: ProjectId, user: User = Depends(require_roles("ADMIN", "DESIGNER")), session: Session = Depends(get_db)):
    return execute(session, lambda: service.estimate_options(session, user, project_id))


@router.get("/{project_id}/estimates", response_model=list[EstimateResponse])
def list_estimates(project_id: ProjectId, user: User = Depends(require_roles("ADMIN", "DESIGNER")), session: Session = Depends(get_db)):
    return execute(session, lambda: service.retrieve_estimates(session, user, project_id))


@router.get("/{project_id}/estimates/{estimate_id}", response_model=EstimateResponse)
def get_estimate(project_id: ProjectId, estimate_id: Annotated[int, Path(gt=0)], user: User = Depends(require_roles("ADMIN", "DESIGNER")), session: Session = Depends(get_db)):
    return execute(session, lambda: service.retrieve_estimate(session, user, project_id, estimate_id))


@router.post("/{project_id}/estimates", response_model=EstimateResponse, status_code=201)
def create_estimate(project_id: ProjectId, payload: EstimateWrite, user: User = Depends(require_roles("DESIGNER")), session: Session = Depends(get_db)):
    return execute(session, lambda: service.generate_estimate(session, user, project_id, payload))
