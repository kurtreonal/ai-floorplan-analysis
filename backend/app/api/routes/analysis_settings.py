from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.analysis_settings import AnalysisSettingsResponse, ElevationInput, ElevationResponse, ScaleInput, ScaleResponse
from app.services.analysis_settings_service import AnalysisSettingsError, approve_elevation, approve_scale, retrieve_settings


router = APIRouter(prefix="/api/projects/{project_id}/floors/{floor_id}/analysis-settings", tags=["analysis settings"])
Id = Annotated[int, Path(gt=0, le=9_007_199_254_740_991)]


def _operation(session, operation, *, write=False, **kwargs):
    try:
        result = operation(session, **kwargs)
        if write:
            session.commit()
        return result
    except (AnalysisSettingsError, SQLAlchemyError) as error:
        session.rollback()
        code = error.code if isinstance(error, AnalysisSettingsError) else "ANALYSIS_SETTINGS_UNAVAILABLE"
        status = 403 if code == "AUTHORIZATION_DENIED" else 404 if code == "ANALYSIS_SETTINGS_NOT_FOUND" else 503
        raise HTTPException(status_code=status, detail={"error": {
            "code": code, "message": "The analysis settings operation could not be completed.", "details": {},
        }}) from None


@router.get("", response_model=AnalysisSettingsResponse)
def get_settings(project_id: Id, floor_id: Id, current_user: User = Depends(require_roles("DESIGNER", "ADMIN")), session: Session = Depends(get_db)):
    return _operation(session, retrieve_settings, current_user=current_user, project_id=project_id, floor_id=floor_id)


@router.put("/elevation", response_model=ElevationResponse)
def put_elevation(project_id: Id, floor_id: Id, data: ElevationInput, current_user: User = Depends(require_roles("DESIGNER")), session: Session = Depends(get_db)):
    return _operation(session, approve_elevation, write=True, current_user=current_user, project_id=project_id, floor_id=floor_id, data=data)


@router.put("/pages/{page_id}/scale", response_model=ScaleResponse)
def put_scale(project_id: Id, floor_id: Id, page_id: Id, data: ScaleInput, current_user: User = Depends(require_roles("DESIGNER")), session: Session = Depends(get_db)):
    return _operation(session, approve_scale, write=True, current_user=current_user, project_id=project_id, floor_id=floor_id, page_id=page_id, data=data)
