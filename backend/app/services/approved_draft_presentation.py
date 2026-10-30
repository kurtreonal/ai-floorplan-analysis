"""Read-only, immutable Admin-reviewed drafts for the assigned Client."""
from sqlalchemy import select
from app.models import FloorPlan, ProjectFloor, FloorPlanInterpretationRun as Run, FloorPlanInterpretationReview as Review
from app.models.account_security import AdminActivity
from app.repositories.floor_plan_lifecycle_repository import active_floor_plan
from app.services.draft_approval_service import latest_action, latest_plan_decision

FIELDS = {
    'walls': {'id','disposition','start','end','thickness_meters','height_meters','estimated_thickness_pixels'},
    'rooms': {'id','disposition','name','boundary'},
    'symbols': {'id','disposition','center','class_name','class_id','symbol_legend_id','mounting_height_meters',
        'mounting_wall_id','mounting_reference','mounting_height_source','terminal_offset_meters'},
}
WIRE_FIELDS = {'id','disposition','points','completeness','elevation_meters','height_above_floor_meters',
    'line_style','installation_method','wiring_legend_id','wiring_legend_name','device_attachments',
    'junction_attachments','circuit_id','vertex_ids','network_lineage','path_origin','suppression_reason','assignment_state'}


def geometry_document(saved):
    result = {}
    for key in ('walls','rooms','symbols','observed_wiring','generated_wiring'):
        result[key] = [{k:v for k,v in row.items() if k in FIELDS.get(key,WIRE_FIELDS)} for row in saved.get(key,[])]
    for wire in result['observed_wiring'] + result['generated_wiring']:
        wire['device_attachments'] = [{k:v for k,v in a.items() if k in ('symbol_id','point_index','terminal_id')}
            for a in wire.get('device_attachments',[])]
    return result


def approved_drafts(db, project_id, *, documents=False):
    rows = db.execute(select(Review, Run, FloorPlan, ProjectFloor)
        .join(Run, Review.interpretation_run_id == Run.id)
        .join(FloorPlan, Run.floor_plan_id == FloorPlan.id)
        .join(ProjectFloor, FloorPlan.project_floor_id == ProjectFloor.id)
        .where(ProjectFloor.project_id == project_id, active_floor_plan(),
            select(AdminActivity.id).where(AdminActivity.target_type == 'review',
                AdminActivity.target_id == Review.id, AdminActivity.action == 'DRAFT_APPROVED').exists())
        .order_by(Review.id.desc())).all()
    result, seen = [], set()
    for review, run, plan, floor in rows:
        if plan.id in seen:
            continue
        action = latest_action(db, review.id)
        if not action or action.action != 'DRAFT_APPROVED':
            continue
        current=latest_plan_decision(db,plan.id)
        if not current or current.id!=action.id:continue
        seen.add(plan.id)
        item = dict(id=f'review-{review.id}', floor_id=floor.id, floor_name=floor.name,
            version=review.revision_number, approved_at=action.created_at, kind='approved_draft')
        if documents:
            from app.services.demo_interpretation_service import _candidate, _review_document
            candidate, saved = _candidate(run), _review_document(review)
            # Never send candidate diagnostics, storage paths or an unapproved
            # newer revision. Pricing remains a separate captured publication.
            item.update(width=candidate.payload.source_plane.width_pixels,
                height=candidate.payload.source_plane.height_pixels,
                draft=geometry_document(saved))
        result.append(item)
    return result
