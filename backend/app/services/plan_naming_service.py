"""Display names never rename or replace the immutable uploaded file."""
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from app.models import FloorPlan, ProjectFloor
from app.services.project_service import get_accessible_project,ProjectNotFoundError


class NameChange(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    name:str=Field(min_length=1,max_length=100)
    expected_name:str|None=Field(...,max_length=255)


def rename(db,user,project_id,item_id,data,*,floor=False):
    from app.services.intake_schema import require_fields
    if not floor:require_fields(db,(FloorPlan,'display_name'))
    try:get_accessible_project(db,current_user=user,project_id=project_id)
    except ProjectNotFoundError:raise HTTPException(404,'Project not found.') from None
    if floor:
        item=db.scalar(select(ProjectFloor).where(ProjectFloor.project_id==project_id,ProjectFloor.id==item_id).with_for_update())
    else:
        item=db.scalar(select(FloorPlan).join(ProjectFloor).where(ProjectFloor.project_id==project_id,FloorPlan.id==item_id).with_for_update())
    if item is None:raise HTTPException(404,'Floor or plan not found.')
    field='name' if floor else 'display_name'
    previous=getattr(item,field)
    if previous!=data.expected_name and previous!=data.name:raise HTTPException(409,'This name changed. Reload before renaming.')
    setattr(item,field,data.name)
    from app.services.activity_log import record
    record(db,user,'FLOOR_RENAMED' if floor else 'FLOOR_PLAN_RENAMED','floor' if floor else 'floor_plan',item.id,'Designer updated the display name.')
    db.commit()
    return {'id':item.id,'name':data.name,'display_name':data.name}
