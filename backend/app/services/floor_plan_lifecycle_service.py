from datetime import UTC, datetime

from sqlalchemy import func, select

from app.models import (DetectedSymbol, DetectionReview, DetectionClassCorrection,
                        FloorPlan, FloorPlanInterpretationReview, FloorPlanInterpretationRun,
                        FloorPlanLifecycleEvent, InterpretationPageOutcome, LayoutVersion,
                        ProcessingJob, ProcessingJobAttempt, ProcessingJobCancellation, ProjectFloor)
from app.repositories.floor_plan_lifecycle_repository import active_floor_plan, latest_event, lock_plan
from app.schemas.floor_plan_lifecycle import FloorPlanLifecycleResponse
from app.services.project_service import get_accessible_project


class FloorPlanLifecycleError(RuntimeError):
    def __init__(self, code, message, status=404):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def _plan(session, user, project_id, plan_id, *, lock=False):
    get_accessible_project(session, current_user=user, project_id=project_id)
    # Authorize the exact project/plan combination before taking the parent lock.
    plan = session.scalar(select(FloorPlan).join(ProjectFloor).where(
        FloorPlan.id == plan_id, ProjectFloor.project_id == project_id))
    if plan is None:
        raise FloorPlanLifecycleError("FLOOR_PLAN_NOT_FOUND", "The floor plan was not found.")
    if lock:
        plan = lock_plan(session, plan_id)
    return plan


def describe_plan(session, plan, *, locked=False):
    event = latest_event(session, plan.id, lock=locked)
    def count(model, *conditions):
        return session.scalar(select(func.count()).select_from(model).where(*conditions)) or 0
    reviews = session.scalar(select(func.count()).select_from(FloorPlanInterpretationReview)
        .join(FloorPlanInterpretationRun, FloorPlanInterpretationReview.interpretation_run_id == FloorPlanInterpretationRun.id)
        .where(FloorPlanInterpretationRun.floor_plan_id == plan.id)) or 0
    for model in (DetectionReview, DetectionClassCorrection):
        reviews += session.scalar(select(func.count()).select_from(model).join(
            DetectedSymbol, model.detected_symbol_id == DetectedSymbol.id).where(
                DetectedSymbol.floor_plan_id == plan.id)) or 0
    return FloorPlanLifecycleResponse(id=plan.id, project_floor_id=plan.project_floor_id,
        original_filename=plan.original_filename, revision=event.revision if event else 0,
        removed=bool(event and event.action == "removed"),
        active_jobs=count(ProcessingJob, ProcessingJob.floor_plan_id == plan.id,
                          ProcessingJob.status.in_(("queued", "processing"))),
        saved_layouts=count(LayoutVersion, LayoutVersion.floor_plan_id == plan.id), saved_reviews=reviews)


def inspect_plan(session, *, current_user, project_id, floor_plan_id):
    return describe_plan(session, _plan(session, current_user, project_id, floor_plan_id))


def list_removed(session, *, current_user, project_id):
    get_accessible_project(session, current_user=current_user, project_id=project_id)
    plans = session.scalars(select(FloorPlan).join(ProjectFloor).where(
        ProjectFloor.project_id == project_id, ~active_floor_plan()).order_by(FloorPlan.id)).all()
    return [describe_plan(session, plan) for plan in plans]


def change_plan_state(session, *, current_user, project_id, floor_plan_id, request, remove):
    if current_user.role.name != "DESIGNER":
        raise FloorPlanLifecycleError("FLOOR_PLAN_WRITE_FORBIDDEN", "A Designer account is required.", 403)
    plan = _plan(session, current_user, project_id, floor_plan_id, lock=True)
    event = latest_event(session, plan.id, lock=True)
    revision = event.revision if event else 0
    removed = bool(event and event.action == "removed")
    request_id = str(request.request_id)
    action = "removed" if remove else "restored"
    # An identical uncertain request is safe to retry, but not after a later transition.
    if (event and event.request_id == request_id and event.action == action
            and request.expected_revision == event.revision - 1):
        result = describe_plan(session, plan, locked=True)
        session.commit()
        return result
    used = session.scalar(select(FloorPlanLifecycleEvent.id).where(
        FloorPlanLifecycleEvent.floor_plan_id == plan.id, FloorPlanLifecycleEvent.request_id == request_id))
    if used or request.expected_revision != revision or remove == removed:
        raise FloorPlanLifecycleError("FLOOR_PLAN_CHANGED", "This floor plan changed. Reload before trying again.", 409)
    if remove:
        _cancel_unfinished_jobs(session, plan.id, current_user.id)
    session.add(FloorPlanLifecycleEvent(floor_plan_id=plan.id, revision=revision + 1,
        action=action, actor_user_id=current_user.id, request_id=request_id))
    session.flush()
    result = describe_plan(session, plan, locked=True)
    session.commit()
    return result


def _cancel_unfinished_jobs(session, plan_id, actor_id):
    now = datetime.now(UTC).replace(tzinfo=None)
    jobs = session.scalars(select(ProcessingJob).where(ProcessingJob.floor_plan_id == plan_id,
        ProcessingJob.status.in_(("queued", "processing"))).order_by(ProcessingJob.id)
        .with_for_update().execution_options(populate_existing=True)).all()
    for job in jobs:
        cancellation = session.scalar(select(ProcessingJobCancellation).where(
            ProcessingJobCancellation.processing_job_id == job.id).with_for_update())
        if cancellation is None:
            cancellation = ProcessingJobCancellation(processing_job_id=job.id, requested_by_user_id=actor_id,
                mode="queued_cancelled" if job.status == "queued" else "cooperative_requested")
            session.add(cancellation)
        cancellation.resolved_at = now
        job.status = "cancelled"
        job.error_message = None
        attempts = session.scalars(select(ProcessingJobAttempt).where(
            ProcessingJobAttempt.processing_job_id == job.id, ProcessingJobAttempt.active_marker.is_(True))
            .with_for_update()).all()
        for attempt in attempts:
            attempt.status, attempt.active_marker = "cancelled", None
            attempt.finished_at, attempt.failure_code = now, "FLOOR_PLAN_REMOVED"
        outcomes = session.scalars(select(InterpretationPageOutcome).where(
            InterpretationPageOutcome.processing_job_id == job.id,
            InterpretationPageOutcome.status.in_(("queued", "processing"))).with_for_update()).all()
        for outcome in outcomes:
            outcome.status, outcome.failure_code = "cancelled", "FLOOR_PLAN_REMOVED"
