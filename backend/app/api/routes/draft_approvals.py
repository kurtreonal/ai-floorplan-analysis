from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from sqlalchemy.orm import Session
from app.api.dependencies import require_roles
from app.core.database import get_db
from app.services.local_accounts import require_same_origin
from app.services import draft_approval_service as service

router = APIRouter(prefix='/api', tags=['draft approval'])


class Submission(BaseModel):
    model_config = ConfigDict(extra='forbid')
    candidate_run_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    revision_number: int = Field(gt=0, strict=True)


class Decision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    approve: StrictBool
    note: str = Field(min_length=1, max_length=500)
    expected_action_id: int | None = Field(default=None, gt=0, strict=True)

    @field_validator('note')
    @classmethod
    def meaningful_note(cls,value):
        if not value.strip():raise ValueError('Add a comment for the Designer.')
        return value.strip()


@router.get('/projects/{project_id}/floor-plans/{plan_id}/submission')
def status(project_id: int, plan_id: int, user=Depends(require_roles('ADMIN', 'DESIGNER')), db: Session = Depends(get_db)):
    return service.status(db, user, project_id, plan_id)


@router.post('/projects/{project_id}/floor-plans/{plan_id}/submission')
def submit(project_id: int, plan_id: int, data: Submission, request: Request,
           user=Depends(require_roles('DESIGNER')), db: Session = Depends(get_db)):
    require_same_origin(request)
    return service.submit(db, user, project_id, plan_id, data)


@router.get('/admin/draft-submissions')
def listing(user=Depends(require_roles('ADMIN')), db: Session = Depends(get_db)):
    return service.listing(db)


@router.post('/admin/draft-submissions/{review_id}')
def decide(review_id: int, data: Decision, request: Request,
           user=Depends(require_roles('ADMIN')), db: Session = Depends(get_db)):
    require_same_origin(request)
    return service.decide(db, user, review_id, data)
