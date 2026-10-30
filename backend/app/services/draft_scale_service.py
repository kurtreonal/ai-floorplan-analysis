"""One read model for draft 2D, 3D and takeoff; no calibration writes."""
from sqlalchemy import inspect
import json
from pypdf.errors import PdfReadError
from app.geometry.draft_scale import resolve_draft_scale
from app.services.measurement_bindings import settings_for_run


def source_scale(session, run, plane, calibration, *, multiple_views=False, overrides=None,document_override=None):
    from app.models import FloorPlan, FloorPlanPage
    from app.repositories.plan_measurement_repository import current
    from app.services.plan_measurement_service import source_metadata
    plan = session.get(FloorPlan, run.floor_plan_id)
    page = session.get(FloorPlanPage, run.floor_plan_page_id)
    record = current(session, plan.id) if inspect(session.connection()).has_table('plan_measurement_settings') else None
    document = document_override if document_override is not None else record.document if record else {}
    metadata = next((p for p in document.get('source_pages', []) if p['page_number'] == page.page_number), None)
    if plan.mime_type == 'application/pdf' and (metadata is None or 'rendered_width_mm' not in metadata or 'scale_markers' not in metadata):
        from app.core.config import get_upload_directory
        from app.services.source_identity import resolve_stored_original
        try:
            original = resolve_stored_original(get_upload_directory(), plan.storage_path)
            metadata = next((p for p in source_metadata(original.read_bytes(), plan.mime_type)
                             if p['page_number'] == page.page_number), None)
        except (OSError, ValueError, RuntimeError, PdfReadError):
            metadata = None
        if metadata is None:
            return dict(pixels_per_meter=None, scale_basis='unresolved', scale_approved=False,
                        scale_reason='source_page_metadata_unavailable')
    parameters=json.loads(run.candidate_json).get('provenance',{}).get('inference_parameters',[])
    selected_region=any(p.get('name')=='drawing-region' for p in parameters)
    only_nts=metadata and metadata.get('has_not_to_scale') and not metadata.get('drawing_scale_denominators')
    mixed_sheet=metadata and ((metadata.get('has_not_to_scale') and not only_nts) or len(metadata.get('drawing_scale_denominators',[]))>1)
    if only_nts and not selected_region:metadata=dict(metadata,view_not_to_scale=True)
    if multiple_views or (mixed_sheet and not selected_region):
        metadata=dict(metadata or {}, multiple_scaled_views=True)
    if selected_region and metadata:
        from app.services.measurement_bindings import run_binding
        region=run_binding(run)['region']
        # Captions may sit just below the selected drawing. Use proportional
        # bounds, never a known page's coordinates or a filename-specific rule.
        nearby=[m for m in metadata.get('scale_markers',[]) if region and
            region['x']<=m['x']<=region['x']+region['width'] and
            region['y']<=m['y']<=region['y']+region['height']*1.3]
        ratios=sorted({m['denominator'] for m in nearby if m['denominator'] is not None})
        metadata=dict(metadata,view_not_to_scale=any(m['not_to_scale'] for m in nearby),
                      drawing_scale_denominators=ratios)
        if len(ratios)>1:metadata['multiple_scaled_views']=True
    from app.services.application_defaults_service import effective
    defaults=effective(session)
    settings=dict(scale_denominator=defaults['scale_denominator'],source_paper_size=defaults['paper_size'])
    if not metadata or not metadata.get('page_width_mm'):
        settings['paper_size']=defaults['paper_size']
    bound_settings,binding=settings_for_run(document,run)
    settings.update({key:value for key,value in bound_settings.items() if value is not None})
    ratios=(metadata or {}).get('drawing_scale_denominators',[])
    if settings.get('measurement_method','auto')=='auto' and not settings.get('drawing_scale_confirmed') and len(ratios)==1:
        settings['scale_denominator']=ratios[0]
    settings.update({key:value for key,value in (overrides or {}).items() if value is not None})
    metric=resolve_draft_scale(plane.width_pixels, plane.height_pixels, calibration=calibration,
                               page=metadata, settings=settings)
    metric['display_sheet']=dict(paper_size=settings.get('display_paper_size','ORIGINAL'),
        orientation=settings.get('display_orientation'),width_mm=settings.get('display_width_mm'),height_mm=settings.get('display_height_mm'))
    metric['measurement_binding']=binding
    from app.services.automatic_plan_setup import height_context
    metric.update(height_context(settings))
    return metric
