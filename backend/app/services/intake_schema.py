"""Keep existing work readable while Admin provisions additive prototype fields."""
from fastapi import HTTPException
from sqlalchemy import inspect


def available(db,model,field):
    key=('intake_columns',model.__tablename__)
    if key not in db.info:
        db.info[key]={column['name'] for column in inspect(db.connection()).get_columns(model.__tablename__)}
    return field in db.info[key]


def details(db,instance,field):
    return (getattr(instance,field) or {}) if instance is not None and available(db,type(instance),field) else {}


def require_fields(db,*fields):
    if any(not available(db,model,field) for model,field in fields):
        raise HTTPException(503,'Admin must finish the client-intake database setup before using this feature. Existing projects remain available.')


def floor_plan_data(db,plan):
    from app.models import FloorPlan
    return {key:getattr(plan,key) for key in ('id','project_floor_id','original_filename','mime_type','file_size','processing_status')} | {
        'display_name':plan.display_name if available(db,FloorPlan,'display_name') else None}
