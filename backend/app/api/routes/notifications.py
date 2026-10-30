from typing import Literal
from fastapi import APIRouter,Depends,Request
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy.orm import Session
from app.api.dependencies import require_roles
from app.core.database import get_db
from app.services.local_accounts import require_same_origin
from app.services import designer_notifications as service

router=APIRouter(prefix='/api/notifications',tags=['notifications'])

class ReadNotifications(BaseModel):
    model_config=ConfigDict(extra='forbid')
    kind:Literal['system','comments']
    through_id:int=Field(ge=0,strict=True)

@router.get('')
def listing(user=Depends(require_roles('DESIGNER')),db:Session=Depends(get_db)):
    return service.feed(db,user)

@router.post('/read')
def read(data:ReadNotifications,request:Request,user=Depends(require_roles('DESIGNER')),db:Session=Depends(get_db)):
    require_same_origin(request)
    return service.mark_read(db,user,data.kind,data.through_id)

@router.get('/{identity}')
def detail(identity:int,user=Depends(require_roles('DESIGNER')),db:Session=Depends(get_db)):
    return service.detail(db,user,identity)
