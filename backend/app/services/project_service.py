from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models import Project, User
from app.repositories.project_repository import (
    add_project,
    find_project_by_id,
    find_project_by_id_and_owner,
    list_all_projects,
    list_projects_by_owner,
)
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate, PROJECT_DETAIL_FIELDS,ProjectDetailsValidation
from app.models.client_workflow import ProjectAssignment
from app.repositories.user_repository import find_user_by_id_with_role
from app.services.local_accounts import account_enabled, credential_for


class ProjectNotFoundError(RuntimeError):
    """Raised when a project is absent or inaccessible to the current user."""


class ProjectDetailsConflictError(RuntimeError):
    """The submitted edit was based on obsolete project metadata."""


def create_project(
    database_session: Session,
    *,
    current_user: User,
    project_data: ProjectCreate,
) -> Project:
    if current_user.role.name != 'ADMIN':
        raise PermissionError('Only Admin can create projects.')
    from app.services.intake_schema import require_fields
    require_fields(database_session,(ProjectAssignment,'intake_details'))
    designer = find_user_by_id_with_role(database_session, user_id=project_data.designer_id)
    client = find_user_by_id_with_role(database_session, user_id=project_data.client_id)
    if not designer or designer.role.name != 'DESIGNER' or not client or client.role.name != 'CLIENT' or not account_enabled(database_session, designer.id) or not account_enabled(database_session, client.id):
        raise ValueError('Choose a client and an assigned designer.')
    if credential_for(database_session, designer.id) is None or credential_for(database_session, client.id) is None:
        raise ValueError('Configure managed sign-in for the selected client and designer first.')
    project = Project(
        owner_id=designer.id,
        **(project_data.model_dump(exclude={'client_id','designer_id','service_types','layout_type','allocated_budget'}) | {'client_name': client.display_name}),
    )
    add_project(database_session, project)
    database_session.add(ProjectAssignment(project_id=project.id, client_id=client.id, created_by_user_id=current_user.id,
        intake_details={'status':'assigned','service_types':project_data.service_types,'layout_type':project_data.layout_type,'allocated_budget':str(project_data.allocated_budget)}))
    database_session.flush()
    from app.services.activity_log import record
    record(database_session, current_user, 'PROJECT_CREATED', 'project', project.id, 'Created project information and assigned a Client and Designer.')
    return project


def update_project_details(database_session: Session, *, current_user: User,
                           project_id: int, project_data: ProjectUpdate) -> Project:
    if current_user.role.name != 'ADMIN':
        raise PermissionError('Only Admin can edit project intake details.')
    from app.services.intake_schema import require_fields
    require_fields(database_session,(ProjectAssignment,'intake_details'))
    get_accessible_project(database_session, current_user=current_user, project_id=project_id)
    project = database_session.scalar(select(Project).where(Project.id == project_id)
        .with_for_update().execution_options(populate_existing=True))
    if project is None:
        raise ProjectNotFoundError
    changes = project_data.model_dump(exclude_unset=True, exclude={'expected_details_revision'})
    assignment = database_session.get(ProjectAssignment,project.id)
    intake = dict(assignment.intake_details or {}) if assignment else {}
    current_services = intake.get('service_types') or ([project.service_type] if project.service_type else [])
    merged = {key: getattr(project, key) for key in PROJECT_DETAIL_FIELDS if key not in ('service_types','layout_type','allocated_budget')} | {'service_types':current_services,'layout_type':intake.get('layout_type'),'allocated_budget':intake.get('allocated_budget')} | changes
    # Changing away from Other deliberately clears its no-longer-applicable description.
    if ('service_type' in changes or 'service_types' in changes) and 'other' not in merged['service_types'] and merged['service_type'] != 'other' and 'service_type_other' not in changes:
        merged['service_type_other'] = None
        changes['service_type_other'] = None
    ProjectDetailsValidation.model_validate(merged)
    response = ProjectResponse.model_validate(project)
    response.service_types = current_services
    response.layout_type = intake.get('layout_type')
    from app.services.project_budget import allocated
    response.allocated_budget=allocated(database_session,project.id)
    if response.details_revision != project_data.expected_details_revision:
        # A lost successful response can be retried, but never overwrite a newer edit.
        if all((current_services if key=='service_types' else allocated(database_session,project.id) if key=='allocated_budget' else intake.get(key) if key=='layout_type' else getattr(project,key)) == value for key,value in changes.items()):
            return project
        raise ProjectDetailsConflictError
    for key, value in changes.items():
        if key in ('service_types','layout_type','allocated_budget'):
            if assignment:
                intake[key]=str(value) if key=='allocated_budget' and value is not None else value
                assignment.intake_details = dict(intake)
        else: setattr(project, key, value)
    database_session.flush()
    from app.services.activity_log import record
    record(database_session, current_user, 'PROJECT_UPDATED', 'project', project.id, 'Updated project intake details.')
    return project


def list_accessible_projects(
    database_session: Session,
    *,
    current_user: User,
) -> list[Project]:
    if current_user.role.name == "DESIGNER":
        return list_projects_by_owner(
            database_session,
            owner_id=current_user.id,
        )
    if current_user.role.name == "ADMIN":
        return list_all_projects(database_session)

    raise ValueError("The current role cannot access projects.")


def get_accessible_project(
    database_session: Session,
    *,
    current_user: User,
    project_id: int,
) -> Project:
    if current_user.role.name == "DESIGNER":
        project = find_project_by_id_and_owner(
            database_session,
            project_id=project_id,
            owner_id=current_user.id,
        )
    elif current_user.role.name == "ADMIN":
        project = find_project_by_id(
            database_session,
            project_id=project_id,
        )
    else:
        raise ValueError("The current role cannot access projects.")

    if project is None:
        raise ProjectNotFoundError
    return project
