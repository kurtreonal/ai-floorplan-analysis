"""Assignment-scoped notification projections over the existing activity log."""
import json
from fastapi import HTTPException
from sqlalchemy import select, and_, or_
from app.models import User, Project, ProjectFloor, FloorPlan, Material
from app.models import FloorPlanInterpretationRun as Run, FloorPlanInterpretationReview as Review
from app.models.role import Role
from app.models.account_security import AdminActivity
from app.services.activity_log import record
from app.repositories.floor_plan_interpretation_repository import find_latest_for_floor_plan

COMMENTS=('DRAFT_APPROVED','DRAFT_RETURNED')
PRICES=('PRICE_UPDATED','ASSEMBLY_UPDATED','MATERIAL_CREATED')
PROJECT_EVENTS=('PROJECT_ASSIGNED','PROJECT_UPDATED','PROJECT_DETAILS_UPDATED','PROJECT_BUDGET_UPDATED')
RESET_EVENTS=('WORKSPACE_RESET_SCHEDULED','WORKSPACE_RESET_CANCELLED')


def read_state(db,user):
    row=db.scalar(select(AdminActivity).where(AdminActivity.actor_id==user.id,
        AdminActivity.action=='NOTIFICATIONS_READ',AdminActivity.target_type=='user',AdminActivity.target_id==user.id)
        .order_by(AdminActivity.id.desc()).limit(1))
    try:
        data=json.loads(row.summary) if row else {}
        return {key:max(0,int(data.get(key,0))) for key in ('system','comments')}
    except (TypeError,ValueError):return {'system':0,'comments':0}


def visible_events(db,user):
    projects=select(Project.id).where(Project.owner_id==user.id,Project.status!='archived')
    plans=select(FloorPlan.id).join(ProjectFloor,FloorPlan.project_floor_id==ProjectFloor.id).where(ProjectFloor.project_id.in_(projects))
    reviews=select(Review.id).join(Run,Review.interpretation_run_id==Run.id).where(Run.floor_plan_id.in_(plans))
    query=(select(AdminActivity).join(User,AdminActivity.actor_id==User.id).join(Role,User.role_id==Role.id)
        .where(Role.name=='ADMIN',or_(
            and_(AdminActivity.target_type=='review',AdminActivity.target_id.in_(reviews),AdminActivity.action.in_((*COMMENTS,'DRAFT_SAVED'))),
            and_(AdminActivity.target_type=='project',AdminActivity.target_id.in_(projects),AdminActivity.action.in_(PROJECT_EVENTS)),
            and_(AdminActivity.target_type=='material',AdminActivity.action.in_(PRICES)),
            and_(AdminActivity.target_type=='defaults',AdminActivity.action=='DEFAULTS_UPDATED'),
            and_(AdminActivity.target_type=='workspace_reset',AdminActivity.action.in_(RESET_EVENTS)),
            and_(AdminActivity.target_type=='user',AdminActivity.target_id==user.id,AdminActivity.action=='DESIGNER_ASSIGNMENT_CHANGED')))
        .order_by(AdminActivity.id.desc()))
    # Bulk price imports must not push review comments out of the inbox.
    return sorted([*db.scalars(query.where(AdminActivity.action.not_in(COMMENTS)).limit(100)).all(),
        *db.scalars(query.where(AdminActivity.action.in_(COMMENTS)).limit(50)).all()],key=lambda row:row.id,reverse=True)


def feed(db,user):
    seen=read_state(db,user);items=[];price_groups={};latest={'system':0,'comments':0}
    for action in visible_events(db,user):
        kind='comments' if action.action in COMMENTS else 'system'
        latest[kind]=max(latest[kind],action.id)
        item=dict(id=action.id,kind=kind,unread=action.id>seen[kind],created_at=action.created_at,
            title='Workspace updated',body=action.summary,href='#/app/clients')
        if action.target_type=='review':
            review=db.get(Review,action.target_id);run=db.get(Run,review.interpretation_run_id)
            plan=db.get(FloorPlan,run.floor_plan_id);floor=db.get(ProjectFloor,plan.project_floor_id);project=db.get(Project,floor.project_id)
            current=find_latest_for_floor_plan(db,floor_plan_id=plan.id)
            item.update(title='Proposal approved' if action.action=='DRAFT_APPROVED' else 'Changes requested' if action.action=='DRAFT_RETURNED' else 'Design updated by Admin',
                context=f'{project.name} · Plan {plan.id} · Revision {review.revision_number}',
                href=f'#/app/projects/{project.id}/floors/{floor.id}/floor-plans/{plan.id}/interpretation/{current.processing_job_id}')
        elif action.target_type=='material':
            material=db.get(Material,action.target_id)
            bucket=(action.actor_id,action.created_at.replace(second=0,microsecond=0))
            if bucket in price_groups:
                group=price_groups[bucket];group['count']+=1;group['unread']|=item['unread']
                group['body']=f"{group['count']} material price or product updates. Refresh your BOM when you continue."
                continue
            item.update(title='Material prices updated',body=f'{material.name if material else "Catalog material"}. Refresh your BOM when you continue.',count=1)
            price_groups[bucket]=item
        elif action.action=='DEFAULTS_UPDATED':item.update(title='Planning defaults updated',body='Admin changed shared defaults. Existing saved settings and estimates are kept.')
        elif action.action=='PROJECT_ASSIGNED':item.update(title='Project assignment updated')
        elif action.action in PROJECT_EVENTS:item.update(title='Project details updated')
        elif action.action in RESET_EVENTS:item.update(title='Workspace reset scheduled' if action.action.endswith('SCHEDULED') else 'Workspace reset cancelled',body='Admin scheduled workspace deletion after a five-minute cooldown. Editing is paused. Contact Admin to cancel.' if action.action.endswith('SCHEDULED') else 'Admin cancelled the reset. Workspace editing is available again.')
        if action.target_type=='project':
            project=db.get(Project,action.target_id)
            item.update(context=project.name,href=f'#/app/projects/{project.id}')
        items.append(item)
    return dict(items=items,unread={key:sum(item['unread'] for item in items if item['kind']==key) for key in seen},latest=latest)


def mark_read(db,user,kind,through_id):
    db.scalar(select(User).where(User.id==user.id).with_for_update())
    values=read_state(db,user)
    available=max((x.id for x in visible_events(db,user) if ('comments' if x.action in COMMENTS else 'system')==kind),default=0)
    value=max(values[kind],min(through_id,available))
    if value!=values[kind]:
        values[kind]=value
        record(db,user,'NOTIFICATIONS_READ','user',user.id,json.dumps(values,separators=(',',':')))
        db.commit()
    return feed(db,user)


def detail(db,user,identity):
    from app.models import MaterialPrice
    events=visible_events(db,user)
    event=next((e for e in events if e.id==identity),None)
    if event is None:raise HTTPException(404,'Notification is no longer available.')
    item=next((x for x in feed(db,user)['items'] if x['id']==identity),None)
    if item is None:raise HTTPException(404,'Open the grouped notification instead.')
    selected=[event]
    if event.action in PRICES:
        selected=[e for e in events if e.action in PRICES and e.actor_id==event.actor_id and e.created_at.replace(second=0,microsecond=0)==event.created_at.replace(second=0,microsecond=0)]
    changes=[]
    for action in selected:
        material=db.get(Material,action.target_id) if action.target_type=='material' else None
        price=db.scalar(select(MaterialPrice).where(MaterialPrice.material_id==material.id).order_by(MaterialPrice.version_number.desc()).limit(1)) if material else None
        changes.append(dict(id=action.id,title=material.name if material else item.get('context') or item['title'],
            item_number=material.code if material else None,description=item['body'] if action.action in RESET_EVENTS else action.summary,created_at=action.created_at,
            current_price=dict(amount=str(price.unit_price),currency=price.currency,unit=price.unit) if price else None))
    actor=db.get(User,event.actor_id)
    return dict(**item,author=actor.display_name or 'Admin',changes=changes,
        effect='Current catalog choices may change the next BOM calculation. Previously saved estimates keep their captured prices.' if event.action in PRICES else item['body'])
