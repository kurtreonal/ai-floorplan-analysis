"""Assignments and immutable, Admin-approved client publications."""
from fastapi import HTTPException
from sqlalchemy import select, delete

from app.models import User, Project, LayoutVersion
from app.models.estimate import Estimate, EstimateItem
from app.models.estimate_source import EstimateSource
from app.models.client_workflow import LocalCredential, ProjectAssignment, ProjectPublication
from app.repositories.user_repository import find_user_by_id_with_role
from app.services.local_accounts import account_enabled, access_for, invalidate_sessions, hash_password, credential_for
from app.repositories.user_repository import find_role_by_name
from app.services.intake_schema import details,require_fields


def account_summary(db, user):
    credential = db.get(LocalCredential, user.id)
    access = access_for(db, user.id)
    from app.models.client_workflow import LinkedIdentity
    linked = db.scalar(select(LinkedIdentity.id).where(LinkedIdentity.user_id == user.id).limit(1))
    return {'id': user.id, 'display_name': user.display_name, 'email': user.email,
            **details(db,user,'profile_details'),
            'label': user.display_name or (credential.username if credential else None) or user.email or f'{user.role.name.title()} #{user.id}',
            'role': user.role.name, 'username': credential.username if credential else None,
            'disabled': bool(access and access.disabled), 'revision': access.session_revision if access else 0,
            'google_linked': bool(linked or (user.role.name == 'ADMIN' and user.oauth_provider != 'local')),
            'assigned_projects': len(db.scalars(select(Project.id).where(Project.status != 'archived',
                Project.owner_id == user.id)).all()) + len(db.scalars(select(ProjectAssignment.project_id)
                    .join(Project, Project.id == ProjectAssignment.project_id)
                    .where(Project.status != 'archived', ProjectAssignment.client_id == user.id)).all())}


def update_account(db, user_id, data, admin, *, deleting=False):
    if not deleting:require_fields(db,(User,'profile_details'))
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if not user:
        raise HTTPException(404, 'User not found.')
    access = access_for(db, user_id)
    if data.expected_revision != (access.session_revision if access else 0):
        raise HTTPException(409, 'This account changed. Reload the list before editing again.')
    if user_id == admin.id or user.role.name == 'ADMIN':
        raise HTTPException(409, 'Administrator accounts are protected. Use your own Sign-in methods to change your credentials.')
    if not deleting:
        if data.role == 'ADMIN':
            raise HTTPException(422, 'This screen creates and manages Designer and Client roles only.')
        summary = account_summary(db, user)
        if data.role != user.role.name and summary['assigned_projects']:
            raise HTTPException(409, 'Reassign this user’s active projects before changing their role.')
        role = find_role_by_name(db, name=data.role)
        if not role:
            raise HTTPException(422, 'Choose an available role.')
        credential = db.get(LocalCredential, user_id)
        if data.username:
            from app.services.local_accounts import username_taken
            if username_taken(db,data.username,exclude_user_id=user_id):
                raise HTTPException(409, 'This username is already in use.')
            if credential is None:
                if not data.password:
                    raise HTTPException(422, 'Provide an initial password to activate this existing account.')
                credential = LocalCredential(user_id=user_id, username=data.username, password_hash='')
                db.add(credential)
            credential.username = data.username
        elif data.password:
            raise HTTPException(422, 'Provide a username with the password.')
        if data.password:
            credential.password_hash = hash_password(data.password)
            credential.failed_attempts = 0
            credential.locked_until = None
        user.display_name, user.email, user.role_id = data.display_name, data.email, role.id
        user.profile_details = {key:getattr(data,key) for key in ('first_name','middle_name','last_name','phone_number','location')}
        user.role = role
    access = invalidate_sessions(db, user_id, admin.id)
    access.disabled = True if deleting else data.disabled
    if deleting:
        # Preserve the authorship key, not reusable sign-in/profile information.
        from app.models.client_workflow import LinkedIdentity
        from app.models.account_security import EmailChallenge, TrustedDevice, AccountEmail
        for model in (EmailChallenge, TrustedDevice, AccountEmail, LinkedIdentity, LocalCredential):
            db.execute(delete(model).where(model.user_id == user_id))
        user.display_name, user.email = f'Removed user #{user_id}', None
        from app.services.intake_schema import available
        if available(db,User,'profile_details'):user.profile_details = None
        user.avatar_url = None
        user.oauth_provider, user.oauth_subject = 'removed', f'removed-{user_id}'
    from app.services.local_accounts import flush_credentials
    flush_credentials(db)
    return account_summary(db, user)


def allocate(db, project, data, admin):
    if admin.role.name!='ADMIN':raise HTTPException(403,'Only Admin can edit the allocated budget.')
    db.scalar(select(Project).where(Project.id==project.id).with_for_update().execution_options(populate_existing=True))
    from app.services.project_budget import allocated
    from app.schemas.project import ProjectResponse
    current=ProjectResponse.model_validate(project)
    intake=details(db,db.get(ProjectAssignment,project.id),'intake_details')
    current.layout_type=intake.get('layout_type')
    current.service_types=intake.get('service_types') or ([project.service_type] if project.service_type else [])
    current.allocated_budget=allocated(db,project.id)
    if data.expected_details_revision and data.expected_details_revision!=current.details_revision:
        assignment=db.get(ProjectAssignment,project.id)
        if current.allocated_budget is not None and assignment and intake.get('status')=='assigned' and assignment.client_id==data.client_id and project.owner_id==data.designer_id and (data.allocated_budget is None or data.allocated_budget==current.allocated_budget):return
        raise HTTPException(409,'Project details changed. Reload before assigning or changing its budget.')
    budget=data.allocated_budget if data.allocated_budget is not None else allocated(db,project.id)
    if budget is None:raise HTTPException(422,'Enter an allocated budget before assigning this project.')
    client = find_user_by_id_with_role(db, user_id=data.client_id)
    designer = find_user_by_id_with_role(db, user_id=data.designer_id)
    if not client or client.role.name != 'CLIENT' or not designer or designer.role.name != 'DESIGNER' or not account_enabled(db, client.id) or not account_enabled(db, designer.id):
        raise HTTPException(422, 'Select an existing client and designer.')
    if credential_for(db, client.id) is None or credential_for(db, designer.id) is None:
        raise HTTPException(422, 'Configure the client and designer username/password in Users before assigning them.')
    assignment = db.scalar(select(ProjectAssignment).where(ProjectAssignment.project_id==project.id).with_for_update().execution_options(populate_existing=True))
    if assignment is None:
        assignment = ProjectAssignment(project_id=project.id, client_id=client.id, created_by_user_id=admin.id)
        db.add(assignment)
    assignment.client_id = client.id
    from app.services.intake_schema import available
    if available(db,ProjectAssignment,'intake_details'):assignment.intake_details = {**details(db,assignment,'intake_details'), 'status':'assigned','allocated_budget':str(budget)}
    if project.owner_id!=designer.id:
        from app.services.activity_log import record
        record(db,admin,'DESIGNER_ASSIGNMENT_CHANGED','user',project.owner_id,'Admin changed one of your project assignments. Your available projects have been updated.')
    project.owner_id = designer.id
    project.client_name = client.display_name
    db.flush()


def publication_choices(db, project_id):
    layouts = db.scalars(select(LayoutVersion).where(LayoutVersion.project_id == project_id)
        .order_by(LayoutVersion.project_floor_id, LayoutVersion.version_number.desc())).all()
    estimates = db.scalars(select(Estimate).where(Estimate.project_id == project_id).order_by(Estimate.version_number.desc())).all()
    latest = db.scalar(select(ProjectPublication).where(ProjectPublication.project_id == project_id)
                       .order_by(ProjectPublication.id.desc()).limit(1))
    sources = {x.estimate_id: x for x in db.scalars(select(EstimateSource).where(EstimateSource.project_id == project_id)).all()}
    return {'layouts': [{'id': x.id, 'floor_id': x.project_floor_id, 'version': x.version_number,
                         'created_at': x.created_at} for x in layouts],
            'estimates': [{'id': x.id, 'version': x.version_number, 'total': x.total,
                           'currency': x.currency, 'created_at': x.created_at,
                           'layout_version_ids': captured_layout_ids(sources.get(x.id))} for x in estimates],
            'approved_at': latest.approved_at if latest else None}


def captured_layout_ids(source):
    layouts = (source.snapshot or {}).get('layouts', {}) if source else {}
    values = layouts.values() if isinstance(layouts, dict) else layouts if isinstance(layouts, list) else []
    return sorted({x['layout_version_id'] for x in values if isinstance(x, dict) and type(x.get('layout_version_id')) is int})


def publish(db, project, data, admin):
    if db.get(ProjectAssignment, project.id) is None:
        raise HTTPException(422, 'Associate a client before publishing.')
    layouts = db.scalars(select(LayoutVersion).where(LayoutVersion.id.in_(set(data.layout_version_ids)),
                                                    LayoutVersion.project_id == project.id)).all()
    estimate = db.get(Estimate, data.estimate_id)
    if len(layouts) != len(set(data.layout_version_ids)) or not estimate or estimate.project_id != project.id:
        raise HTTPException(422, 'Every selected saved layout and estimate must belong to this project.')
    if len({x.project_floor_id for x in layouts}) != len(layouts):
        raise HTTPException(422, 'Select one saved layout version per floor.')
    source = db.get(EstimateSource, estimate.id)
    captured = set(captured_layout_ids(source))
    if not captured:
        raise HTTPException(422, 'Save an estimate with captured layout versions before publishing. A draft BOM is not a saved estimate.')
    if captured != {x.id for x in layouts}:
        raise HTTPException(422, 'Choose the saved layout versions captured by this estimate.')
    publication = ProjectPublication(project_id=project.id, approved_by_user_id=admin.id,
        layout_version_ids=sorted({x.id for x in layouts}), estimate_id=estimate.id)
    db.add(publication)
    db.flush()
    return {'id': publication.id, 'approved_at': publication.approved_at}


def client_projects(db, client):
    from app.services.project_budget import allocated
    from app.services.approved_draft_presentation import approved_drafts
    projects = db.scalars(select(Project).join(ProjectAssignment, ProjectAssignment.project_id == Project.id)
        .where(ProjectAssignment.client_id == client.id, Project.status != 'archived')
        .order_by(Project.updated_at.desc())).all()
    from app.services.approved_bom_publication import latest
    costs={};approved_projects=set()
    from app.services.draft_approval_service import returned_after
    for project in projects:
        captured=latest(db,project.id,verify_approvals=True)
        publication=db.scalar(select(ProjectPublication).where(ProjectPublication.project_id==project.id).order_by(ProjectPublication.id.desc()).limit(1))
        if publication and returned_after(db,project.id,publication.approved_at):publication=None
        if publication or approved_drafts(db,project.id):approved_projects.add(project.id)
        if publication and (not captured or publication.id>captured.get('after_formal_publication_id',0)):
            estimate=db.get(Estimate,publication.estimate_id)
            costs[project.id]={'totals':{estimate.currency:str(estimate.total)},'estimated':False,'incomplete':False} if estimate else None
        else:
            costs[project.id]={key:captured['estimate'][key] for key in ('totals','estimated','incomplete')} if captured else None
    return [{'id': x.id, 'name': x.name, 'location': x.location,'created_at':x.created_at,
             'approved_bom':costs[x.id], 'allocated_budget':allocated(db,x.id),
             'intake_status':details(db,db.get(ProjectAssignment,x.id),'intake_details').get('status','assigned'),
             'approved': x.id in approved_projects}
            for x in projects]


def client_publication(db, client, project_id):
    from app.services.project_budget import comparison
    project = db.scalar(select(Project).join(ProjectAssignment, ProjectAssignment.project_id == Project.id)
        .where(Project.id == project_id, ProjectAssignment.client_id == client.id, Project.status != 'archived'))
    if project is None:
        raise HTTPException(404, 'Project not found.')
    publication = db.scalar(select(ProjectPublication).where(ProjectPublication.project_id == project.id)
                           .order_by(ProjectPublication.id.desc()).limit(1))
    from app.services.draft_approval_service import returned_after
    if publication and returned_after(db,project_id,publication.approved_at):publication=None
    from app.services.approved_bom_publication import latest
    cost=latest(db,project_id,verify_approvals=True)
    if publication is None or cost and publication.id<=cost.get('after_formal_publication_id',0):
        from app.services.approved_draft_presentation import approved_drafts
        drafts = approved_drafts(db, project_id, documents=True)
        if not drafts:
            raise HTTPException(404, 'Admin has not approved a layout for this project yet.')
        if cost:
            from app.services.project_budget import comparison
            cost={**cost,'estimate':{**cost['estimate'],'budget_comparison':comparison(db,project_id,cost['estimate'].get('totals',{}),incomplete=cost['estimate'].get('incomplete',False))}}
        return {'project': {'id': project.id, 'name': project.name, 'location': project.location},
            'approved_at': cost['published_at'] if cost else max(x['approved_at'] for x in drafts), 'layouts': drafts, 'estimate': cost['estimate'] if cost else None}
    layouts = db.scalars(select(LayoutVersion).where(LayoutVersion.id.in_(publication.layout_version_ids),
                                                    LayoutVersion.project_id == project_id)).all()
    from app.services.canonical_extension_storage import retrieve_canonical_extension
    from app.models import ProjectFloor
    floor_names={floor.id:floor.name for floor in db.scalars(select(ProjectFloor).where(ProjectFloor.project_id==project_id)).all()}
    extensions={x.id:retrieve_canonical_extension(x.id) for x in layouts}
    estimate = db.get(Estimate, publication.estimate_id)
    if estimate is None or estimate.project_id != project_id:
        raise HTTPException(404, 'Published estimate is unavailable.')
    items = db.scalars(select(EstimateItem).where(EstimateItem.estimate_id == estimate.id).order_by(EstimateItem.line_number)).all()
    # Only the approved canonical document and captured estimate leave this boundary.
    return {'project': {'id': project.id, 'name': project.name, 'location': project.location},
            'approved_at': publication.approved_at,
            'layouts': [{'id': x.id, 'floor_id': x.project_floor_id, 'version': x.version_number,
                         'floor_name':floor_names.get(x.project_floor_id),
                         'geometry': x.geometry_document,
                         'extension': extensions[x.id].to_dict() if extensions[x.id] else None} for x in layouts],
            'estimate': {'id': estimate.id, 'version': estimate.version_number, 'total': estimate.total,
                         'currency': estimate.currency,'budget_comparison':comparison(db,project_id,{estimate.currency:estimate.total}), 'items': [{'name': x.material_name, 'quantity': x.quantity,
                            'unit': x.unit, 'unit_price': x.captured_unit_price, 'cost': x.line_total} for x in items]}}
