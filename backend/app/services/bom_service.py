"""Reviewed component takeoff, separate from unresolved detection proposals."""
import csv
from io import StringIO
from app.repositories.estimate_repository import floor_ids
from app.services.material_quantity_service import retrieve_component_quantities, retrieve_route_material_lengths
from app.services.project_service import get_accessible_project, ProjectNotFoundError
from app.services.layout_service import LayoutServiceError
from sqlalchemy import func, select
from app.models import FloorPlan, ProjectFloor, FloorPlanInterpretationRun, LayoutVersion
from app.repositories.floor_plan_interpretation_repository import find_latest_review
from app.services.demo_interpretation_service import _candidate, _review_document
from app.services.wiring_legend_service import annotate_wiring
from app.repositories.floor_plan_lifecycle_repository import active_floor_plan


def draft_wiring_types(session, project_id):
    """Catalog identities from latest source-page drafts, NOT final quantities."""
    latest=(select(FloorPlanInterpretationRun.floor_plan_id,
                   func.max(FloorPlanInterpretationRun.processing_job_id).label('job_id'))
        .group_by(FloorPlanInterpretationRun.floor_plan_id).subquery())
    rows=session.execute(select(FloorPlanInterpretationRun,ProjectFloor.id)
        .join(latest,(FloorPlanInterpretationRun.floor_plan_id==latest.c.floor_plan_id)
                     & (FloorPlanInterpretationRun.processing_job_id==latest.c.job_id))
        .join(FloorPlan,FloorPlan.id==FloorPlanInterpretationRun.floor_plan_id)
        .join(ProjectFloor,ProjectFloor.id==FloorPlan.project_floor_id)
        .where(ProjectFloor.project_id==project_id, active_floor_plan()).order_by(FloorPlanInterpretationRun.id))
    values={}
    for run,floor_id in rows:
        review=find_latest_review(session,interpretation_run_id=run.id)
        document=annotate_wiring(session,_candidate(run),_review_document(review) if review else None)
        for category in ('observed_wiring','generated_wiring'):
            for wire in document.get(category,[]):
                if wire.get('disposition')=='rejected' or not wire.get('wiring_legend_id'):
                    continue
                key=(run.floor_plan_id,wire['wiring_legend_id'])
                row=values.setdefault(key,dict(floor_id=floor_id,floor_plan_id=run.floor_plan_id,
                    wiring_legend_id=wire['wiring_legend_id'],name=wire['wiring_legend_name'],
                    installation_method=wire['installation_method'],observed_trace_count=0,
                    generated_path_count=0,quantity_meters=None,status='draft_unmeasured'))
                row['observed_trace_count' if category=='observed_wiring' else 'generated_path_count']+=1
    return list(values.values())


def reviewed_bom(session, user, project_id, *, floor_plan_id=None, processing_job_id=None,
                 conduit_material_id=None, wire_material_id=None, paper_size=None,
                 custom_width_mm=None, custom_height_mm=None, wire_meters_per_unit=None, wire_price_per_meter=None,
                 conduit_price_per_meter=None, scale_denominator=None,
                 draft_preview=None, device_materials=None, purchase_pricing=None):
    get_accessible_project(session, current_user=user, project_id=project_id)
    if processing_job_id is not None and floor_plan_id is None:
        raise ValueError('A plan is required for a job-scoped BOM.')
    if paper_size is not None and floor_plan_id is None:
        raise ValueError('Paper-size assumptions require one specific plan.')
    if paper_size != 'CUSTOM' and (custom_width_mm is not None or custom_height_mm is not None):
        raise ValueError('Custom dimensions require CUSTOM paper size.')
    if floor_plan_id is not None and session.scalar(select(FloorPlan.id).join(ProjectFloor)
        .where(FloorPlan.id == floor_plan_id, ProjectFloor.project_id == project_id, active_floor_plan())) is None:
        raise ProjectNotFoundError()
    if processing_job_id is not None and session.scalar(select(FloorPlanInterpretationRun.id).where(
        FloorPlanInterpretationRun.floor_plan_id == floor_plan_id,
        FloorPlanInterpretationRun.processing_job_id == processing_job_id).limit(1)) is None:
        raise ProjectNotFoundError()
    if draft_preview is not None:
        from app.services.draft_bom_service import validate_preview
        validate_preview(session, user, floor_plan_id, processing_job_id, draft_preview)
    components, layouts, missing = [], [], []
    for floor in floor_ids(session, project_id):
        try:
            values = retrieve_component_quantities(session, current_user=user, project_id=project_id, project_floor_id=floor)
        except LayoutServiceError as error:
            if error.code != 'LAYOUT_NOT_FOUND':
                raise
            missing.append(floor)
            continue
        layout = session.get(LayoutVersion, values.layout_version_id)
        layouts.append(dict(floor_id=floor, floor_plan_id=layout.floor_plan_id,
            layout_version_id=values.layout_version_id, version_number=values.version_number))
        components.extend(dict(floor_id=floor, class_id=row.class_id, name=row.class_name,
            quantity=row.quantity, symbol_ids=list(row.symbol_ids)) for row in values.components)
    try:
        route = retrieve_route_material_lengths(session, current_user=user, project_id=project_id)
        lengths = dict(route_version_id=route['route_version_id'], conduit_meters=route['lengths'].conduit_meters)
        route_state = 'measured'
    except ValueError:
        lengths, route_state = None, 'unavailable'
    from app.services.draft_bom_service import planning_bom
    planning = planning_bom(session, user, project_id, components=components, layouts=layouts,
        floor_plan_id=floor_plan_id, processing_job_id=processing_job_id,
        conduit_material_id=conduit_material_id, wire_material_id=wire_material_id, paper_size=paper_size,
        custom_width_mm=custom_width_mm, custom_height_mm=custom_height_mm,
        wire_meters_per_unit=wire_meters_per_unit, wire_price_per_meter=wire_price_per_meter,
        conduit_price_per_meter=conduit_price_per_meter, scale_denominator=scale_denominator,
        draft_preview=draft_preview,device_materials=device_materials,purchase_pricing=purchase_pricing)
    from app.services.bom_display import grouped_rows, cost_summary
    planning['display_groups'] = grouped_rows(planning['items'])
    planning['cost_summary'] = cost_summary(planning['items'])
    return dict(project_id=project_id, layouts=layouts, missing_layout_floors=missing,
        components=components, route_lengths=lengths, route_state=route_state,
        wiring_types=draft_wiring_types(session,project_id), planning=planning)


def planning_csv(bom, *, xlsx=False):
    if xlsx:
        from app.services.bom_spreadsheet import supplier_xlsx
        return supplier_xlsx(bom['planning']['items'], bom['planning']['priced_subtotals'])
    from app.services.bom_export import supplier_csv
    return supplier_csv(bom['planning']['items'], bom['planning']['priced_subtotals'])


def diagnostic_csv(bom):
    """Internal/on-demand diagnostics, deliberately not the normal BOM download."""
    stream = StringIO(newline='')
    writer = csv.writer(stream, quoting=csv.QUOTE_ALL)
    def safe(value):
        text = '' if value is None else str(value)
        return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text
    writer.writerow(['DRAFT BOM', 'Calculated at', bom['planning']['calculated_at']])
    if bom['planning'].get('cost_summary',{}).get('estimated'):
        writer.writerow(['ESTIMATED TOTAL','Includes assumed measurement inputs; not a calibrated or professionally verified estimate.'])
    for source in bom['planning'].get('sources', []):
        writer.writerow(['PAGE SCALE BASIS', source.get('floor_plan_id'), source.get('page_id'),
            source.get('scale_basis'), source.get('pixels_per_meter'), source.get('assumed_paper_size'),
            source.get('scale_denominator'), 'Nominal draft scale, not independently calibrated'
            if source.get('scale_basis') == 'ved_paper_ratio_draft' else source.get('scale_reason')])
    selected = next((m for m in bom['planning'].get('conduit_materials', [])
        if m['id'] == bom['planning'].get('selected_conduit_material_id')), None)
    if selected:
        writer.writerow(['DRAFT CONDUIT CHOICE', selected['id'], safe(selected['name']),
            'Purchase-unit conversion required for non-metre products; not a saved circuit specification.'])
    if bom['planning'].get('requested_paper_size'):
        writer.writerow(['REQUESTED PAPER ASSUMPTION', bom['planning']['requested_paper_size'],
            bom['planning'].get('custom_width_mm'), bom['planning'].get('custom_height_mm'),
            'Paper metadata only; not a pixel calibration. Reviewed source calibration is required.'])
    wire = next((m for m in bom['planning'].get('wire_materials', [])
        if m['id'] == bom['planning'].get('selected_wire_material_id')), None)
    if wire:
        writer.writerow(['DRAFT WIRE CHOICE', wire['id'], safe(wire['name']),
            'Draft cable route length, not conductor purchase quantity.'])
    if bom['planning'].get('wire_price_per_meter') is not None:
        writer.writerow(['CUSTOM WIRE PRICE PER METRE (PHP)',bom['planning']['wire_price_per_meter']])
    if bom['planning'].get('wire_meters_per_unit') is not None:
        writer.writerow(['WIRE METRES PER PURCHASE UNIT',bom['planning']['wire_meters_per_unit']])
    writer.writerow(['Floor', 'Plan', 'Item', 'Quantity', 'Unit', 'Material', 'Unit price', 'Currency', 'Line total', 'Status', 'Calculation basis'])
    for row in bom['planning']['items']:
        writer.writerow([safe(row.get('client_product_name') or row.get(key)) if key=='material_name' else safe(row.get(key)) for key in ('floor_id', 'floor_plan_id', 'name', 'quantity', 'unit',
            'material_name', 'unit_price', 'currency', 'line_total', 'pricing_state', 'basis')])
    for currency, amount in bom['planning']['priced_subtotals'].items():
        writer.writerow(['', '', 'PRICED SUBTOTAL ONLY', '', '', '', '', currency, amount])
    for note in bom['planning']['basis']:
        writer.writerow(['BASIS', safe(note)])
    for note in bom['planning'].get('missing_inputs', []):
        writer.writerow(['MISSING INPUT', safe(note)])
    return '\ufeff' + stream.getvalue()


def estimate_csv(estimate, *, xlsx=False):
    from app.services.bom_export import supplier_csv
    rows = [dict(kind='device', name=item.material_name, material_name=item.material_name,
        material_code=item.material_code, quantity=item.quantity, unit=item.unit,
        unit_price=item.captured_unit_price, line_total=item.line_total, currency=estimate['currency']) for item in estimate['items']]
    if xlsx:
        from app.services.bom_spreadsheet import supplier_xlsx
        return supplier_xlsx(rows, {estimate['currency']: estimate['total']})
    return supplier_csv(rows, {estimate['currency']: estimate['total']})
