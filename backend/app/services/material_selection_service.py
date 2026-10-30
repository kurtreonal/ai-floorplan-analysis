"""Live material choices in the existing append-only item-price document."""
from copy import deepcopy
from sqlalchemy import select
from app.models import FloorPlan,ProjectFloor,SymbolLegend
from app.repositories import item_price_repository as repository
from app.repositories.estimate_repository import floor_ids
from app.repositories.routing_repository import lock_context
from app.services import project_pricing_service as pricing
from app.services.material_workbook import WorkbookError
from app.repositories.floor_plan_lifecycle_repository import active_floor_plan


def resolve(document,plan_id):
    scopes=document.get('material_selections',{})
    return {**scopes.get('project',{}),**scopes.get(str(plan_id),{})}


def save(session,user,project_id,request):
    pricing._access(session,user,project_id,write=True)
    if request.floor_plan_id is not None and session.scalar(select(FloorPlan.id).join(ProjectFloor).where(
            FloorPlan.id==request.floor_plan_id,ProjectFloor.project_id==project_id,active_floor_plan())) is None:
        raise WorkbookError('Choose a plan in this project.')
    lock_context(session,project_id,floor_ids(session,project_id))
    identity=pricing._hash(request.model_dump(mode='json',exclude={'request_id'}))
    retry=repository.retry(session,project_id,str(request.request_id))
    if retry:
        if retry.request_hash!=identity:raise pricing.PricingConflict('This retry contains different material choices.')
        session.commit()
        return dict(id=retry.id,version_number=retry.version_number)
    current=repository.current(session,project_id,lock=True)
    version=current.version_number if current else 0
    if version!=request.expected_version:raise pricing.PricingConflict('Material prices changed in another window. Reload before applying.')
    from app.services.material_price_service import catalog
    from app.services.draft_bom_service import wire_choices,conduit_choices
    from app.services.application_defaults_service import effective
    from app.services.wiring_material_pairing import allowed_conduits
    from app.services.draft_device_pricing import compatible
    materials=[m for m in catalog(session) if m['is_active']]
    by_id={m['id']:m for m in materials if m.get('is_active',True)}
    settings=request.settings
    from app.services.layout_materials import wire_allowed,default_wire,project_layout,layout_values
    previous=resolve(current.document if current else {},request.floor_plan_id)
    reset_wire=False
    if settings.layoutType and 'wire' not in settings.model_fields_set:
        existing=by_id.get(int(previous['wire'])) if previous.get('wire') else None
        selected=existing['id'] if existing and wire_allowed(existing,settings.layoutType) else default_wire(effective(session),settings.layoutType)
        if len(layout_values(settings.layoutType))>1 and default_wire(effective(session),settings.layoutType) is None:selected=None
        settings.wire=str(selected) if selected else ''
        reset_wire=str(previous.get('wire') or '')!=settings.wire
        if reset_wire:
            settings.conduit=''
            settings.purchasePricing={}
    wire_id=int(settings.wire) if settings.wire else None
    conduit_id=int(settings.conduit) if settings.conduit else None
    if wire_id and wire_id not in {m['id'] for m in wire_choices(materials)}:raise WorkbookError('Choose an available wire product.')
    from app.services.plan_material_setup import plan_layout
    layout=settings.layoutType or plan_layout(session,request.floor_plan_id,current.document if current else {}) or previous.get('layoutType') or project_layout(session,project_id)
    if wire_id and not wire_allowed(by_id[wire_id],layout):raise WorkbookError('Choose a wire product for the selected layout type.')
    rule=next((p for p in effective(session)['wire_conduit_pairs'] if p['wire_material_id']==wire_id),None)
    if conduit_id and (not rule or conduit_id not in allowed_conduits(rule) or conduit_id not in {m['id'] for m in conduit_choices(materials)}):
        raise WorkbookError('Choose wiring first, then one of its approved conduits.')
    for kind,override in settings.purchasePricing.items():
        if kind not in ('wire','conduit'):raise WorkbookError('Choose a wire or conduit price.')
        selected=wire_id if kind=='wire' else conduit_id
        allowed={selected} if selected else allowed_conduits(rule) if kind=='conduit' and rule else set()
        if override.material_id not in allowed or override.material_id not in by_id:raise WorkbookError('The edited price belongs to a different product.')
    from app.services.material_assembly_service import annotate_catalog
    from app.repositories.material_price_repository import last_revision
    for material in materials:
        if material.get('is_assembly'):
            price=last_revision(session,material['id'])
            material['price_revision_id']=price.id if price else None
    products={m['id']:m for m in annotate_catalog(session,materials)}
    from app.services.workspace_products import validate_choices
    changed_items={key:value for key,value in settings.itemMaterials.items() if value.model_dump(mode='json',exclude_none=True)!=previous.get('itemMaterials',{}).get(key)}
    validate_choices(session,request.floor_plan_id,changed_items,products,materials,effective(session),layout)
    for key,material_id in settings.deviceMaterials.items():
        legend=session.scalar(select(SymbolLegend).where(SymbolLegend.class_id==int(key),SymbolLegend.is_active.is_(True))) if key.isdigit() else None
        product=products.get(material_id)
        if legend is None or product is None or not compatible(dict(class_id=int(key),name=legend.name,unit='piece',kind='device'),product):
            raise WorkbookError('Choose an approved product for this device symbol.')
    document=deepcopy(current.document) if current else dict(assignments={})
    scopes=document.setdefault('material_selections',{})
    key=str(request.floor_plan_id) if request.floor_plan_id else 'project'
    updates=settings.model_dump(mode='json',exclude_none=True,exclude_unset=True)
    if settings.layoutType:
        from app.services.plan_material_setup import snapshot
        updates['automaticDefaults']=snapshot(session,settings.layoutType)['automaticDefaults']
    elif 'wire' in settings.model_fields_set and previous.get('automaticDefaults'):
        updates['automaticDefaults']={**previous['automaticDefaults'],'wire_material_id':None}
    if reset_wire:updates.update(wireMetersPerUnit=None,wirePricePerMeter=None)
    scopes[key]={**scopes.get(key,{}),**updates}
    document['application']=dict(kind='material_selection',floor_plan_id=request.floor_plan_id)
    record=repository.append(session,project_id=project_id,version_number=version+1,created_by_user_id=user.id,
        request_id=str(request.request_id),request_hash=identity,document=document)
    from app.services.activity_log import record as log_activity
    log_activity(session,user,'MATERIAL_SELECTION_UPDATED','project',project_id,'Updated live BOM material choices; historical estimates unchanged.')
    session.commit()
    return dict(id=record.id,version_number=record.version_number)
