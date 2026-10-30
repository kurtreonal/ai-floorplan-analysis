"""Review saved planning drafts without promoting unmeasured geometry to canonical."""
from fastapi import HTTPException
from sqlalchemy import select
from app.models import FloorPlan, ProjectFloor, Project, FloorPlanInterpretationRun as Run, FloorPlanInterpretationReview as Review
from app.models.account_security import AdminActivity
from app.repositories.floor_plan_lifecycle_repository import lock_active_plan, active_floor_plan
from app.repositories.floor_plan_interpretation_repository import find_latest_review, find_latest_for_floor_plan
from app.services.project_service import get_accessible_project, ProjectNotFoundError
from app.services.activity_log import record

ACTIONS = ('DRAFT_SUBMITTED', 'DRAFT_APPROVED', 'DRAFT_RETURNED')


def latest_action(db, review_id):
    return db.scalar(select(AdminActivity).where(AdminActivity.target_type == 'review',
        AdminActivity.target_id == review_id, AdminActivity.action.in_(ACTIONS))
        .order_by(AdminActivity.id.desc()).limit(1))


def latest_plan_decision(db,plan_id):
    return db.scalar(select(AdminActivity).join(Review,AdminActivity.target_id==Review.id)
        .join(Run,Review.interpretation_run_id==Run.id)
        .where(AdminActivity.target_type=='review',Run.floor_plan_id==plan_id,
            AdminActivity.action.in_(('DRAFT_APPROVED','DRAFT_RETURNED')))
        .order_by(AdminActivity.id.desc()).limit(1))


def returned_after(db,project_id,published_at):
    plans=db.scalars(select(FloorPlan.id).join(ProjectFloor,FloorPlan.project_floor_id==ProjectFloor.id)
        .where(ProjectFloor.project_id==project_id,active_floor_plan())).all()
    return any((action:=latest_plan_decision(db,plan_id)) is not None
        and action.action=='DRAFT_RETURNED' and action.created_at>=published_at for plan_id in plans)


def context(db, user, project_id, plan_id, *, lock=False):
    try:
        get_accessible_project(db, current_user=user, project_id=project_id)
    except ProjectNotFoundError:
        raise HTTPException(404, 'Project not found.') from None
    plan = lock_active_plan(db, plan_id) if lock else db.scalar(select(FloorPlan).where(FloorPlan.id==plan_id, active_floor_plan()))
    floor = db.get(ProjectFloor, plan.project_floor_id) if plan else None
    if not floor or floor.project_id != project_id:
        raise HTTPException(404, 'Plan not found.')
    run = find_latest_for_floor_plan(db, floor_plan_id=plan_id)
    review = find_latest_review(db, interpretation_run_id=run.id) if run else None
    return run, review


def status(db, user, project_id, plan_id):
    run, review = context(db, user, project_id, plan_id)
    action = latest_action(db, review.id) if review else None
    decision=latest_plan_decision(db,plan_id)
    if decision and decision.action=='DRAFT_RETURNED' and (not action or decision.id>action.id):action=decision
    return {'status': action.action.removeprefix('DRAFT_').lower() if action else 'not_submitted',
        'revision_number': review.revision_number if review else None,
        'candidate_run_id': run.candidate_run_id if run else None,
        'message': action.summary if action else None}


def submit(db, user, project_id, plan_id, data):
    run, review = context(db, user, project_id, plan_id, lock=True)
    if not review or run.candidate_run_id != data.candidate_run_id or review.revision_number != data.revision_number:
        raise HTTPException(409, 'The saved draft changed. Save and submit the current revision.')
    previous = latest_action(db, review.id)
    decision=latest_plan_decision(db,plan_id)
    if not previous or previous.action == 'DRAFT_RETURNED' or (decision and decision.action=='DRAFT_RETURNED' and decision.id>previous.id):
        record(db, user, 'DRAFT_SUBMITTED', 'review', review.id,
            f'Submitted planning draft revision {review.revision_number} for Admin review.')
        db.commit()
    return status(db, user, project_id, plan_id)


def listing(db):
    # Latest action per immutable review; old revisions are retained in the activity log.
    rows = db.execute(select(Review, Run, FloorPlan, ProjectFloor, Project)
        .join(Run, Review.interpretation_run_id == Run.id)
        .join(FloorPlan, Run.floor_plan_id == FloorPlan.id)
        .join(ProjectFloor, FloorPlan.project_floor_id == ProjectFloor.id)
        .join(Project, ProjectFloor.project_id == Project.id)
        .where(Project.status != 'archived',active_floor_plan(),
            select(AdminActivity.id).where(AdminActivity.target_type == 'review',
                AdminActivity.target_id == Review.id, AdminActivity.action.in_(ACTIONS)).exists())
        .order_by(Review.id.desc()).limit(200)).all()
    result = [];decisions={}
    for review, run, plan, floor, project in rows:
        action = latest_action(db, review.id)
        if not action or action.action=='DRAFT_RETURNED':
            continue
        if plan.id not in decisions:decisions[plan.id]=latest_plan_decision(db,plan.id)
        if action.action=='DRAFT_SUBMITTED' and decisions[plan.id] and decisions[plan.id].action=='DRAFT_RETURNED' and decisions[plan.id].id>action.id:continue
        current_run = find_latest_for_floor_plan(db, floor_plan_id=plan.id)
        current_review = find_latest_review(db, interpretation_run_id=current_run.id)
        if action.action=='DRAFT_APPROVED':
            if not decisions[plan.id] or decisions[plan.id].id!=action.id:continue
        elif current_run.id != run.id or current_review.id != review.id:
            continue
        result.append(dict(review_id=review.id, revision_number=review.revision_number,
            status=action.action.removeprefix('DRAFT_').lower(), project_id=project.id,
            project_name=project.name, floor_id=floor.id, floor_name=floor.name,
            floor_plan_id=plan.id, processing_job_id=current_run.processing_job_id, message=action.summary,
            action_id=action.id,decided_at=action.created_at,latest_revision_number=current_review.revision_number))
    return result


def decide(db, user, review_id, data):
    review = db.get(Review, review_id)
    run = db.get(Run, review.interpretation_run_id) if review else None
    plan = db.get(FloorPlan, run.floor_plan_id) if run else None
    floor = db.get(ProjectFloor, plan.project_floor_id) if plan else None
    if not floor:
        raise HTTPException(404, 'Saved draft not found.')
    active_run, active_review = context(db, user, floor.project_id, plan.id, lock=True)
    action = latest_action(db, review_id)
    decision = 'DRAFT_APPROVED' if data.approve else 'DRAFT_RETURNED'
    if not action:
        raise HTTPException(409, 'This draft is not awaiting that decision.')
    note=data.note.strip()
    if not note:raise HTTPException(422,'Add a comment for the Designer.')
    if action.action==decision and action.summary==note:return status(db,user,floor.project_id,plan.id)
    if data.expected_action_id is not None and data.expected_action_id!=action.id:
        raise HTTPException(409,'This proposal changed. Refresh the review list before deciding.')
    if data.approve and (not active_run or not active_review or active_run.id!=run.id or active_review.id!=review_id):
        raise HTTPException(409,'A newer draft exists. Review the latest submission instead.')
    plan_decision=latest_plan_decision(db,plan.id)
    if plan_decision and plan_decision.action=='DRAFT_RETURNED' and plan_decision.id>action.id:
        raise HTTPException(409,'This plan was returned. Wait for the Designer to submit it again.')
    if action.action not in (('DRAFT_SUBMITTED',) if data.approve else ('DRAFT_SUBMITTED','DRAFT_APPROVED')):
        raise HTTPException(409,'This proposal has already been returned to the Designer.')
    if action.action=='DRAFT_APPROVED' and latest_plan_decision(db,plan.id).id!=action.id:
        raise HTTPException(409,'A newer decision exists. Refresh the review list.')
    if action.action != decision:
        record(db, user, decision, 'review', review_id, note)
        db.flush()
        if data.approve:
            db.flush()
            from app.services.approved_bom_publication import publish
            publish(db,user,floor.project_id)
        else:
            from app.services.approved_draft_presentation import approved_drafts
            if approved_drafts(db,floor.project_id):
                from app.services.approved_bom_publication import publish
                publish(db,user,floor.project_id)
        db.commit()
    # Deliberately do not set approved_for_layout or rewrite the saved review.
    return status(db, user, floor.project_id, plan.id)
