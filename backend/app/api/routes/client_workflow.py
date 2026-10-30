import logging
from uuid import UUID
from fastapi import APIRouter, Depends, Request, File, Form, UploadFile, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.client_workflow import ManagedAccountCreate, ManagedAccountUpdate, AccountDelete, ProjectAllocation, PublicationCreate
from app.services.local_accounts import require_same_origin, create_client, create_account
from app.services.project_service import get_accessible_project
from app.services import client_workflow_service as service
from app.services.activity_log import record
from app.models.account_security import AdminActivity
from app.models.client_workflow import AccountAccess
from app.services.layout_materials import LayoutType

router = APIRouter(prefix='/api', tags=['client workflow'])
logger = logging.getLogger(__name__)

from app.services import client_intake_service as intake


@router.get('/client/designers')
def preferred_designers(user: User = Depends(require_roles('CLIENT')), db: Session = Depends(get_db)):
    return intake.designers(db)


@router.post('/client/projects', status_code=201)
def submit_project(data: intake.ClientProjectRequest, request: Request,
                   user: User = Depends(require_roles('CLIENT')), db: Session = Depends(get_db)):
    require_same_origin(request)
    project = intake.submit(db,user,data)
    return {'id':project.id,'name':project.name,'intake_status':'pending_admin'}


@router.get('/client/projects/{project_id}/files')
def submitted_files(project_id:int,user:User=Depends(require_roles('CLIENT')),db:Session=Depends(get_db)):
    return intake.submission_files(db,user,project_id)


@router.post('/client/projects/{project_id}/floor-plans',status_code=201)
async def endorse_file(project_id:int,request:Request,file:UploadFile=File(...),request_id:UUID=Form(...),floor_id:int|None=Form(default=None,gt=0),
                       layout_types:list[LayoutType]|None=Form(default=None,min_length=1,max_length=3),
                       user:User=Depends(require_roles('CLIENT')),db:Session=Depends(get_db)):
    require_same_origin(request)
    from app.core.config import get_upload_directory,get_max_upload_size_bytes
    from app.services.upload_validation import UploadValidationError
    from app.services.floor_plan_storage import FloorPlanStorageError
    from app.schemas.floor_plan import FloorPlanUploadResponse
    try:
        limit=get_max_upload_size_bytes(request.app.state.settings)
        plan=intake.upload(db,user,project_id,floor_id,await file.read(limit+1),file.filename or '',file.content_type or '',
            get_upload_directory(request.app.state.settings),limit,request_id,layout_types=layout_types)
        return FloorPlanUploadResponse.model_validate(plan)
    except UploadValidationError as error:
        raise HTTPException(422,error.message) from None
    except FloorPlanStorageError:
        raise HTTPException(503,'The original could not be stored. Please retry this file.') from None
    finally:
        await file.close()


@router.get('/admin/accounts')
def accounts(user: User = Depends(require_roles('ADMIN')), db: Session = Depends(get_db)):
    return [service.account_summary(db, x) for x in db.scalars(select(User).outerjoin(AccountAccess, AccountAccess.user_id == User.id)
        .where((AccountAccess.disabled.is_(False)) | (AccountAccess.user_id.is_(None)))
        .options(joinedload(User.role)).order_by(User.display_name.is_(None), User.display_name, User.id)).all()]


@router.get('/admin/activity')
def activity(user: User = Depends(require_roles('ADMIN')), db: Session = Depends(get_db)):
    rows = db.scalars(select(AdminActivity).order_by(AdminActivity.id.desc()).limit(200)).all()
    return [{'id': x.id, 'action': x.action, 'target_type': x.target_type, 'target_id': x.target_id,
             'actor_id': x.actor_id, 'summary': x.summary, 'created_at': x.created_at} for x in rows]


@router.post('/admin/clients', status_code=201)
def new_client(data: ManagedAccountCreate, request: Request, user: User = Depends(require_roles('ADMIN')),
               db: Session = Depends(get_db)):
    require_same_origin(request)
    client = create_client(db, data)
    db.flush()
    result = service.account_summary(db, client)
    record(db, user, 'USER_CREATED', 'user', client.id, 'Created a Client account.')
    db.commit()
    logger.info('CLIENT_CREATED user_id=%s admin_id=%s', client.id, user.id)
    return result


@router.post('/admin/accounts', status_code=201)
def new_account(data: ManagedAccountCreate, request: Request, user: User = Depends(require_roles('ADMIN')),
                db: Session = Depends(get_db)):
    require_same_origin(request)
    account = create_account(db, data)
    db.flush()
    result = service.account_summary(db, account)
    record(db, user, 'USER_CREATED', 'user', account.id, f'Created a {result["role"].title()} account.')
    db.commit()
    logger.info('USER_CREATED user_id=%s admin_id=%s role=%s', account.id, user.id, result['role'])
    return result


@router.put('/admin/accounts/{user_id}')
def edit_account(user_id: int, data: ManagedAccountUpdate, request: Request,
                 user: User = Depends(require_roles('ADMIN')), db: Session = Depends(get_db)):
    require_same_origin(request)
    result = service.update_account(db, user_id, data, user)
    record(db, user, 'USER_UPDATED', 'user', user_id, 'Updated user profile or account access.')
    db.commit()
    logger.info('USER_UPDATED user_id=%s admin_id=%s', user_id, user.id)
    return result


@router.delete('/admin/accounts/{user_id}')
def delete_account(user_id: int, data: AccountDelete, request: Request,
                   user: User = Depends(require_roles('ADMIN')), db: Session = Depends(get_db)):
    require_same_origin(request)
    result = service.update_account(db, user_id, data, user, deleting=True)
    record(db, user, 'USER_REMOVED', 'user', user_id, 'Deleted sign-in details, linked identities and recovery addresses. Saved work and authorship ID retained.')
    db.commit()
    logger.info('USER_ACCESS_REMOVED user_id=%s admin_id=%s', user_id, user.id)
    return result


@router.put('/projects/{project_id}/assignment')
def assign(project_id: int, data: ProjectAllocation, request: Request,
           user: User = Depends(require_roles('ADMIN')), db: Session = Depends(get_db)):
    require_same_origin(request)
    project = get_accessible_project(db, current_user=user, project_id=project_id)
    service.allocate(db, project, data, user)
    record(db, user, 'PROJECT_ASSIGNED', 'project', project_id, 'Changed Client and Designer assignment.')
    db.commit()
    logger.info('PROJECT_ASSIGNED project_id=%s admin_id=%s', project.id, user.id)
    return {'status': 'saved'}


@router.get('/projects/{project_id}/approval')
def choices(project_id: int, user: User = Depends(require_roles('ADMIN')), db: Session = Depends(get_db)):
    get_accessible_project(db, current_user=user, project_id=project_id)
    return service.publication_choices(db, project_id)


@router.post('/projects/{project_id}/approval', status_code=201)
def approve(project_id: int, data: PublicationCreate, request: Request,
            user: User = Depends(require_roles('ADMIN')), db: Session = Depends(get_db)):
    require_same_origin(request)
    project = get_accessible_project(db, current_user=user, project_id=project_id)
    result = service.publish(db, project, data, user)
    record(db, user, 'PROJECT_PUBLISHED', 'project', project_id, 'Published a saved estimate and its captured layouts.')
    db.commit()
    logger.info('PROJECT_APPROVED project_id=%s admin_id=%s publication_id=%s', project.id, user.id, result['id'])
    return result


@router.get('/client/projects')
def portal(user: User = Depends(require_roles('CLIENT')), db: Session = Depends(get_db)):
    return service.client_projects(db, user)


@router.post('/projects/{project_id}/approved-bom')
def publish_approved_bom(project_id:int,request:Request,user:User=Depends(require_roles('ADMIN')),db:Session=Depends(get_db)):
    require_same_origin(request)
    from app.models import Project
    get_accessible_project(db,current_user=user,project_id=project_id)
    db.scalar(select(Project).where(Project.id==project_id).with_for_update())
    from app.services.approved_bom_publication import publish
    result=publish(db,user,project_id,refresh_prices=True)
    db.commit()
    return {'published_at':result['published_at'],'estimate':result['estimate']}


@router.get('/client/projects/{project_id}/publication')
def publication(project_id: int, user: User = Depends(require_roles('CLIENT')), db: Session = Depends(get_db)):
    return service.client_publication(db, user, project_id)
