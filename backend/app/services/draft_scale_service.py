"""One read model for draft 2D, 3D and takeoff; no calibration writes."""
from sqlalchemy import inspect
from pypdf.errors import PdfReadError
from app.geometry.draft_scale import resolve_draft_scale


def source_scale(session, run, plane, calibration, *, multiple_views=False):
    from app.models import FloorPlan, FloorPlanPage
    from app.repositories.plan_measurement_repository import current
    from app.services.plan_measurement_service import source_metadata
    plan = session.get(FloorPlan, run.floor_plan_id)
    page = session.get(FloorPlanPage, run.floor_plan_page_id)
    record = current(session, plan.id) if inspect(session.connection()).has_table('plan_measurement_settings') else None
    document = record.document if record else {}
    metadata = next((p for p in document.get('source_pages', []) if p['page_number'] == page.page_number), None)
    if metadata is None and plan.mime_type == 'application/pdf' and calibration is None:
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
    if multiple_views:
        metadata=dict(metadata or {}, multiple_scaled_views=True)
    return resolve_draft_scale(plane.width_pixels, plane.height_pixels, calibration=calibration,
                               page=metadata, settings=document.get('settings'))
