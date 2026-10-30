from uuid import UUID
from fastapi import APIRouter,Depends,Request
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy.orm import Session
from app.api.dependencies import require_roles
from app.core.database import get_db
from app.services.local_accounts import require_same_origin
from app.services import workspace_reset as service

router=APIRouter(prefix='/api/admin/workspace-reset',tags=['Admin workspace reset'])
class ResetRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmation:str=Field(max_length=40)
    expected_fingerprint:str=Field(pattern=r'^[a-f0-9]{64}$')
    request_id:UUID
    keep_admin_id:int=Field(gt=0)
    keep_designer_id:int=Field(gt=0)

@router.get('')
def preview(user=Depends(require_roles('ADMIN')),db:Session=Depends(get_db)):
    return service.preview(db,user)

@router.post('')
def schedule(data:ResetRequest,request:Request,user=Depends(require_roles('ADMIN')),db:Session=Depends(get_db)):
    require_same_origin(request)
    return service.request_reset(db,user,data)

@router.get('/status')
def status(user=Depends(require_roles('ADMIN')),db:Session=Depends(get_db)):
    return service.state(db)

@router.post('/{identity}/cancel')
def cancel(identity:int,request:Request,user=Depends(require_roles('ADMIN')),db:Session=Depends(get_db)):
    require_same_origin(request)
    return service.cancel(db,user,identity)
