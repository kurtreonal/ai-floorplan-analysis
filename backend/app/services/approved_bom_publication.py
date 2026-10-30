"""Immutable client BOMs captured from explicitly Admin-approved draft revisions."""
from datetime import datetime,timezone
from decimal import Decimal,ROUND_CEILING
import json
from pathlib import Path
from fastapi import HTTPException
from sqlalchemy import select
from app.core.config import get_settings,REPOSITORY_ROOT
from app.models import FloorPlanInterpretationReview as Review,FloorPlanInterpretationRun as Run
from app.models.account_security import AdminActivity

ACTION='DRAFT_BOM_PUBLISHED'


def location(identity):
    configured=get_settings().report_dir or Path('storage/reports')
    root=configured if configured.is_absolute() else REPOSITORY_ROOT/configured
    return root/'client-bom'/f'publication-{int(identity)}.json'


def latest(db,project_id,*,verify_approvals=False):
    action=db.scalar(select(AdminActivity).where(AdminActivity.action==ACTION,AdminActivity.target_type=='project',AdminActivity.target_id==project_id).order_by(AdminActivity.id.desc()).limit(1))
    if not action:return None
    try:
        data=json.loads(location(action.id).read_text(encoding='utf-8'))
        if data.get('project_id')!=project_id:return None
        if verify_approvals:
            from app.services.approved_draft_presentation import approved_drafts
            approved={int(item['id'].removeprefix('review-')) for item in approved_drafts(db,project_id)}
            if {plan['review_id'] for plan in data.get('plans',[])}!=approved:return None
        return data
    except (OSError,ValueError,AttributeError,TypeError):return None


def preview(review,run):
    from app.schemas import demo_interpretation as schema
    from app.services.demo_interpretation_service import _review_document
    saved=_review_document(review)
    data={key:value for key,value in saved.items() if key in schema.DemoReviewRequest.model_fields}
    for key,model in [('walls',schema.DemoWallReview),('rooms',schema.DemoRoomReview),('symbols',schema.DemoSymbolReview),('observed_wiring',schema.DemoObservedWiringReview),('generated_wiring',schema.DemoGeneratedWiringReview)]:
        data[key]=[{k:v for k,v in item.items() if k in model.model_fields} for item in saved.get(key,[])]
    data.update(candidate_run_id=run.candidate_run_id,expected_revision_number=review.revision_number,review_complete=False,approved_for_layout=False,dataset_approval=None,evidence_notes='BOM captured from an Admin-approved saved draft.')
    return schema.DemoReviewRequest.model_validate(data)


def summary(rows):
    """Combine captured purchases by floor, SKU and captured price; no live repricing."""
    from app.services.bom_export import supplier_rows
    values=[dict(row) for row in rows]
    packages={}
    for row in values:
        if row.get('line_total') is not None and row.get('unit') in ('roll','length') and row.get('purchase_meters_per_unit') and row.get('measured_meters') is not None:
            key=(row.get('floor_id'),row.get('material_id'),row['unit'],row.get('currency'),str(row.get('unit_price')),str(row['purchase_meters_per_unit']))
            packages.setdefault(key,[]).append(row)
    for group in packages.values():
        metres=sum((Decimal(str(row['measured_meters'])) for row in group),Decimal(0))
        quantity=(metres/Decimal(str(group[0]['purchase_meters_per_unit']))).to_integral_value(rounding=ROUND_CEILING)
        for index,row in enumerate(group):
            row['quantity']=quantity if index==0 else Decimal(0)
            row['line_total']=row['quantity']*Decimal(str(row['unit_price']))
    totals={}
    items=[]
    for cat,name,brand,code,spec,qty,unit,price,currency,amount in supplier_rows(values):
        items.append(dict(category=cat,name=name,brand=brand,item_number=code,specification=spec,quantity=str(qty) if unit!='source pixel' else None,unit=unit if unit!='source pixel' else 'Not measured',unit_price=str(price) if price!='' else None,currency=currency or None,cost=str(amount) if amount!='' else None))
        if amount!='' and currency:totals[currency]=totals.get(currency,Decimal(0))+amount
    incomplete=any(row.get('line_total') is None or row.get('missing_vertical_inputs') or row.get('trace_incomplete') or row.get('assembly_scope_incomplete') or row.get('scale_approved') is False for row in values)
    estimated=any(row.get('estimated') for row in values)
    currency=next(iter(totals)) if len(totals)==1 else None
    return dict(kind='approved_bom',items=items,totals={key:str(value) for key,value in totals.items()},currency=currency,total=str(totals[currency]) if currency else None,incomplete=incomplete,estimated=estimated)


def publish(db,admin,project_id,*,refresh_prices=False):
    from app.services.approved_draft_presentation import approved_drafts
    from app.services.draft_bom_service import planning_bom
    from app.services.activity_log import record
    drafts=approved_drafts(db,project_id)
    if not drafts:raise HTTPException(422,'Approve a saved Designer proposal first.')
    previous=latest(db,project_id)
    previous_plans={p['review_id']:p for p in (previous or {}).get('plans',[])}
    plans=[]
    for draft in drafts:
        review_id=int(draft['id'].removeprefix('review-'))
        if not refresh_prices and review_id in previous_plans:
            plans.append(previous_plans[review_id]);continue
        review=db.get(Review,review_id)
        run=db.get(Run,review.interpretation_run_id)
        from app.services.demo_interpretation_service import DemoInterpretationError
        try:
            # Use this saved draft directly. Canonical-layout lookup is unrelated
            # and its legacy failure handler can roll back an approval transaction.
            planning=planning_bom(db,admin,project_id,components=[],layouts=[],floor_plan_id=run.floor_plan_id,processing_job_id=run.processing_job_id,draft_preview=preview(review,run))
        except (ValueError,DemoInterpretationError):
            raise HTTPException(422,'Open the saved proposal in its workspace and save its current revision before publishing the BOM.') from None
        allowed={'kind','name','material_kind','material_id','material_name','material_code','brand','product_identity','client_product_name','client_product_code','client_product_brand','client_product_specification','material_category','layout_category','quantity','unit','unit_price','currency','line_total','floor_id','floor_plan_id','purchase_meters_per_unit','measured_meters','estimated','scale_approved','trace_incomplete','assembly_scope_incomplete','missing_vertical_inputs'}
        allowed.update({'conductor_count','conductor_count_assumed','wire_quantity_basis','route_meters'})
        plans.append(dict(review_id=review_id,floor_plan_id=run.floor_plan_id,source_items=[{k:v for k,v in item.items() if k in allowed} for item in planning['items']]))
    # Normalize Decimals before comparing against an earlier serialized revision.
    plans=json.loads(json.dumps(plans,default=str))
    from app.models.client_workflow import ProjectPublication
    from sqlalchemy import func
    after_formal=db.scalar(select(func.max(ProjectPublication.id)).where(ProjectPublication.project_id==project_id)) or 0
    if previous and previous.get('plans')==plans and previous.get('after_formal_publication_id',0)==after_formal:return previous
    estimate=summary([row for plan in plans for row in plan['source_items']])
    record(db,admin,ACTION,'project',project_id,'Published the approved project BOM with captured quantities and prices.')
    db.flush()
    action=db.scalar(select(AdminActivity).where(AdminActivity.actor_id==admin.id,AdminActivity.action==ACTION,AdminActivity.target_id==project_id).order_by(AdminActivity.id.desc()).limit(1))
    estimate.update(id=f'approved-bom-{action.id}',version=action.id,calculated_at=datetime.now(timezone.utc).isoformat())
    result=dict(project_id=project_id,publication_id=action.id,after_formal_publication_id=after_formal,published_at=action.created_at.isoformat(),plans=plans,estimate=estimate)
    path=location(action.id)
    try:
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x',encoding='utf-8') as output:json.dump(result,output,ensure_ascii=False)
    except OSError:
        raise HTTPException(503,'The approved BOM could not be stored. Retry publication; your saved proposal is unchanged.') from None
    return result
