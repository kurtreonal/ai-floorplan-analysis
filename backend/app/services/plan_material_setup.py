"""Snapshot floor/plan material defaults in the existing append-only price document."""
from copy import deepcopy
import hashlib
import json
from uuid import uuid4
from sqlalchemy import select
from app.models import FloorPlan, ProjectFloor
from app.repositories import item_price_repository as repository
from app.repositories.routing_repository import lock_context
from app.services.layout_materials import project_layout,layout_values,default_wire


def snapshot(db,layout):
    from app.services.application_defaults_service import retrieve
    config=retrieve(db)
    defaults=config['settings']
    wire=default_wire(defaults,layout)
    return dict(layoutType=layout,wire=str(wire) if wire else '',
        automaticDefaults=dict(revision=config['revision'],conductor_count=defaults['planning_conductor_count'],assumed=True,wire_material_id=wire,
            wire_material_ids={value:defaults.get(f'{value}_wire_material_id') for value in layout_values(layout)}))


def apply_layout_wires(items,choice,materials,defaults):
    """Mixed sheets choose by connected load family, never one wire for every view."""
    if choice.get('wire') or len(layout_values(choice.get('layoutType')))<2:return
    from app.services.draft_bom_service import apply_wire_choice
    pinned=(choice.get('automaticDefaults') or {}).get('wire_material_ids',{})
    for category in layout_values(choice.get('layoutType')):
        group=[row for row in items if row.get('kind')=='path' and row.get('layout_category')==category and not row.get('saved_route_version_id')]
        wire=pinned.get(category,defaults.get(f'{category}_wire_material_id'))
        if not group or not any(m['id']==wire and m.get('is_active',True) for m in materials):continue
        apply_wire_choice(group,materials,wire)
        items[:]=[row for row in items if not (row.get('kind')=='path' and row.get('layout_category')==category and not row.get('saved_route_version_id'))]+group


def floor_settings(db,project_id,floor_id,document=None):
    if document is None:
        record=repository.current(db,project_id)
        document=record.document if record else {}
    return document.get('floor_material_defaults',{}).get(str(floor_id),{})


def plan_layout(db,plan_id,document=None):
    if plan_id is None:return None
    plan=db.get(FloorPlan,plan_id)
    if not plan:return None
    floor=db.get(ProjectFloor,plan.project_floor_id)
    if document is None:
        record=repository.current(db,floor.project_id)
        document=record.document if record else {}
    scopes=document.get('material_selections',{})
    return (scopes.get(str(plan_id),{}).get('layoutType')
        or floor_settings(db,floor.project_id,floor.id,document).get('layoutType')
        or scopes.get('project',{}).get('layoutType') or project_layout(db,floor.project_id))


def append(db,user,project_id,*,floor_id=None,plan_id=None,layout):
    lock_context(db,project_id,[])
    current=repository.current(db,project_id,lock=True)
    document=deepcopy(current.document) if current else dict(assignments={})
    settings=snapshot(db,layout)
    if plan_id is not None:
        scope=document.setdefault('material_selections',{})
        prior=scope.get(str(plan_id),{})
        scope[str(plan_id)]={**prior,**settings,**({'conduit':'','purchasePricing':{},'wireMetersPerUnit':None,'wirePricePerMeter':None} if prior.get('layoutType')!=layout else {})}
    else:document.setdefault('floor_material_defaults',{})[str(floor_id)]=settings
    request_id=str(uuid4())
    repository.append(db,project_id=project_id,version_number=(current.version_number if current else 0)+1,
        created_by_user_id=user.id,request_id=request_id,
        request_hash=hashlib.sha256(json.dumps(settings,sort_keys=True).encode()).hexdigest(),document=document)
    return settings


def initialize_plan(db,user,project_id,plan,layout=None):
    selected=layout or floor_settings(db,project_id,plan.project_floor_id).get('layoutType') or project_layout(db,project_id)
    if selected:append(db,user,project_id,plan_id=plan.id,layout=selected)


def read(db,user,project_id,plan_id):
    from app.services.project_service import get_accessible_project
    from fastapi import HTTPException
    get_accessible_project(db,current_user=user,project_id=project_id)
    plan=db.scalar(select(FloorPlan).join(ProjectFloor).where(FloorPlan.id==plan_id,ProjectFloor.project_id==project_id))
    if not plan:raise HTTPException(404,'Floor plan not found.')
    current=repository.current(db,project_id)
    return dict(layout_type=plan_layout(db,plan_id,current.document if current else {}),revision=current.version_number if current else 0)


def change(db,user,project_id,plan_id,data):
    from app.schemas.material_selection import MaterialSelection,MaterialSelectionWrite
    from app.services.material_selection_service import save
    read(db,user,project_id,plan_id)
    return save(db,user,project_id,MaterialSelectionWrite(request_id=data.request_id,expected_version=data.expected_version,
        floor_plan_id=plan_id,settings=MaterialSelection(layoutType=data.layout_type)))
