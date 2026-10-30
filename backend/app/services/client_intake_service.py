"""Client submissions are originals for Admin review, never designer publications."""
from uuid import UUID
from decimal import Decimal
import hashlib
import json
from fastapi import HTTPException
from pydantic import Field
from sqlalchemy import select
from app.models import User, Project, ProjectFloor, FloorPlan
from app.models.client_workflow import ProjectAssignment
from app.schemas.project import ProjectMetadata
from app.services.local_accounts import account_enabled, credential_for
from app.services.activity_log import record
from app.services.intake_schema import details,require_fields


class ClientProjectRequest(ProjectMetadata):
    allocated_budget: Decimal=Field(ge=0,max_digits=14,decimal_places=2)
    name: str = Field(min_length=1, max_length=255)
    contact_number: str = Field(min_length=7, max_length=64, pattern=r'^[+0-9() .\-]+$')
    location: str = Field(min_length=1, max_length=500)
    preferred_designer_id: int | None = Field(default=None, gt=0)
    request_id: UUID


def designers(db):
    from app.models.role import Role
    return [{'id':u.id,'name':u.display_name} for u in db.scalars(select(User).join(Role)
        .where(Role.name=='DESIGNER').order_by(User.display_name)).all()
        if account_enabled(db,u.id) and credential_for(db,u.id)]


def own_project(db, client, project_id, *, pending=False):
    project = db.scalar(select(Project).join(ProjectAssignment).where(Project.id==project_id,
        ProjectAssignment.client_id==client.id, Project.status!='archived').with_for_update())
    if project is None: raise HTTPException(404,'Project not found.')
    assignment = db.get(ProjectAssignment,project_id)
    if pending and details(db,assignment,'intake_details').get('status')!='pending_admin':
        raise HTTPException(409,'Admin has assigned this project. Contact Admin to submit additional files.')
    return project


def submit(db, client, data):
    require_fields(db,(ProjectAssignment,'intake_details'),(FloorPlan,'display_name'))
    db.scalar(select(User).where(User.id==client.id).with_for_update())
    fingerprint=hashlib.sha256(json.dumps(data.model_dump(mode='json'),sort_keys=True).encode()).hexdigest()
    for assignment in db.scalars(select(ProjectAssignment).where(ProjectAssignment.client_id==client.id)).all():
        if details(db,assignment,'intake_details').get('request_id')==str(data.request_id):
            if details(db,assignment,'intake_details').get('request_hash')!=fingerprint:
                raise HTTPException(409,'This request was already received with different details. Open the existing request instead.')
            return db.get(Project,assignment.project_id)
    if data.preferred_designer_id and data.preferred_designer_id not in {u['id'] for u in designers(db)}:
        raise HTTPException(422,'Choose an available preferred designer.')
    if 'other' in data.service_types and not data.service_type_other:
        raise HTTPException(422,'Describe the Other service.')
    from app.models.role import Role
    admin = next((u for u in db.scalars(select(User).join(Role).where(Role.name=='ADMIN').order_by(User.id)).all()
                  if account_enabled(db,u.id)),None)
    if not admin: raise HTTPException(503,'An Admin account is needed to receive your submission.')
    project = Project(owner_id=admin.id, client_name=client.display_name,
        **data.model_dump(exclude={'request_id','preferred_designer_id','service_types','client_name','layout_type','allocated_budget'}))
    db.add(project); db.flush()
    db.add(ProjectAssignment(project_id=project.id,client_id=client.id,created_by_user_id=client.id,
        intake_details={'status':'pending_admin','preferred_designer_id':data.preferred_designer_id,
            'service_types':data.service_types,'layout_type':data.layout_type,'allocated_budget':str(data.allocated_budget.quantize(Decimal('.01'))),'request_id':str(data.request_id),'request_hash':fingerprint}))
    record(db,client,'CLIENT_PROJECT_SUBMITTED','project',project.id,'Client endorsed a new project for Admin review.')
    db.commit()
    return project


def submission_files(db,client,project_id):
    require_fields(db,(ProjectAssignment,'intake_details'),(FloorPlan,'display_name'))
    own_project(db,client,project_id)
    floors=db.scalars(select(ProjectFloor).where(ProjectFloor.project_id==project_id).order_by(ProjectFloor.sort_order,ProjectFloor.id)).all()
    return [{'id':f.id,'name':f.name,'plans':[{'id':p.id,'display_name':p.display_name,
        'original_filename':p.original_filename} for p in db.scalars(select(FloorPlan).where(FloorPlan.project_floor_id==f.id)).all()]} for f in floors]


def upload(db,client,project_id,floor_id,content,filename,mime,upload_directory,max_size,request_id,*,layout_types=None):
    require_fields(db,(ProjectAssignment,'intake_details'),(FloorPlan,'display_name'))
    own_project(db,client,project_id,pending=True)
    assignment=db.get(ProjectAssignment,project_id)
    uploads=dict((assignment.intake_details or {}).get('uploads',{}))
    fingerprint=hashlib.sha256(content).hexdigest()
    previous=uploads.get(str(request_id))
    if previous:
        if previous['hash']!=fingerprint or previous['floor_id']!=floor_id or previous.get('layout_types')!=layout_types:raise HTTPException(409,'Retry this upload with its original file, floor and layout types.')
        return db.get(FloorPlan,previous['id'])
    if len(uploads)>=100:raise HTTPException(422,'This request already contains 100 files. Contact Admin for additional plans.')
    floor=db.scalar(select(ProjectFloor).where(ProjectFloor.id==floor_id,ProjectFloor.project_id==project_id)) if floor_id else None
    if floor_id and floor is None: raise HTTPException(404,'Floor not found in this project.')
    if floor is None:
        floors=db.scalars(select(ProjectFloor).where(ProjectFloor.project_id==project_id)).all()
        floor=ProjectFloor(project_id=project_id,name=f'Pending floor {len(floors)+1}',sort_order=len(floors))
        db.add(floor);db.flush()
    # The common storage service validates content, owns file cleanup and commits.
    from app.services.floor_plan_storage import store_floor_plan_upload
    record(db,client,'CLIENT_PLAN_ENDORSED','project',project_id,'Original floor-plan file sent for Admin review.')
    def bind(plan):
        uploads[str(request_id)]={'id':plan.id,'hash':fingerprint,'floor_id':floor_id,'layout_types':layout_types}
        assignment.intake_details={**(assignment.intake_details or {}),'uploads':uploads}
        if layout_types:
            from app.services.plan_material_setup import initialize_plan
            initialize_plan(db,client,project_id,plan,layout_types)
    return store_floor_plan_upload(db,project_floor_id=floor.id,filename=filename,declared_mime_type=mime,
        content=content,upload_directory=upload_directory,max_file_size_bytes=max_size,actor_user_id=client.id,on_stored=bind)
