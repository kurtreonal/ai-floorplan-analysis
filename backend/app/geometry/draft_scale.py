"""Physical source scale shared by draft views and takeoff; display paper is independent."""
import math
from app.geometry.calibration import paper_ruler_evidence, measured_ruler_evidence

PAPER_MM = {'A5': (148, 210), 'A4': (210, 297), 'A3': (297, 420), 'A2': (420, 594),
            'A1': (594, 841), 'A0': (841, 1189)}
ASPECT_TOLERANCE = .02  # Legacy import compatibility; physical mapping uses pixel rounding.


def resolve_draft_scale(width, height, *, calibration=None, page=None, settings=None):
    page,settings=page or {},settings or {}
    denominator=settings.get('scale_denominator',100)
    native_width,native_height=page.get('rendered_width_mm'),page.get('rendered_height_mm')
    if native_width is None and page.get('page_width_mm') and not page.get('cropped'):
        native_width,native_height=page['page_width_mm'],page['page_height_mm']
        if page.get('rotation_degrees',0) in (90,270):native_width,native_height=native_height,native_width
    result=dict(pixels_per_meter=None,scale_basis='unresolved',scale_approved=False,
                scale_denominator=denominator,source_width_mm=native_width,source_height_mm=native_height,
                multiple_scale_views=bool(page.get('multiple_scaled_views')),measurement_state='needs_reference',
                ratio_assumed=not(settings.get('drawing_scale_confirmed') or denominator in page.get('drawing_scale_denominators',[])),
                estimated=False)
    if any(not math.isfinite(v) or v<=0 for v in (width,height)):
        return dict(result,scale_reason='invalid_source_dimensions')
    if page.get('view_not_to_scale') or settings.get('measurement_method')=='not_to_scale':
        return dict(result,scale_reason='not_to_scale_view')
    if result['multiple_scale_views']:
        return dict(result,scale_reason='select_one_scaled_plan_view')
    method=settings.get('measurement_method','auto')
    if settings.get('_transform_invalid'):
        return dict(result,scale_reason='source_aspect_transform_required')
    reference=settings.get('reference') if method=='reference' or method=='auto' and settings.get('allow_estimated_scale') else None
    if reference:
        if any(not(0<=reference[key]['x']<=width and 0<=reference[key]['y']<=height) for key in ('start','end')):
            return dict(result,scale_reason='invalid_reference')
        length=math.hypot(reference['end']['x']-reference['start']['x'],reference['end']['y']-reference['start']['y'])
        if length<=0 or not .000001<=length/reference['length_meters']<=1_000_000:return dict(result,scale_reason='invalid_reference')
        return dict(result,pixels_per_meter=length/reference['length_meters'],scale_basis='measured_page',
                    measurement_state='known_reference',scale_approved=True,measured_ruler=reference,
                    ratio_assumed=False,scale_reason='known_distance_reference')
    if calibration is not None and method=='auto':
        if (calibration.reference_width_pixels, calibration.reference_height_pixels) != (width, height):
            return dict(result, scale_reason='saved_calibration_dimensions_changed')
        ppm = calibration.pixels_per_meter
        if ppm is None or not math.isfinite(ppm) or ppm <= 0:
            return dict(result, scale_reason='saved_calibration_unavailable')
        ruler = paper_ruler_evidence(getattr(calibration, 'evidence_notes', None))
        if ruler is not None:
            if settings.get('allow_estimated_scale'):
                # An explicit automatic reset replaces old paper-placement
                # guesses, but never a real known-distance calibration.
                return resolve_draft_scale(width,height,page=page,settings=settings)
            return dict(result,pixels_per_meter=float(ppm),scale_basis='paper_ruler_draft',paper_ruler=ruler,
                        measurement_state='estimated',estimated=True,scale_reason='designer_paper_ruler_not_independent_calibration')
        return dict(result,pixels_per_meter=float(ppm),scale_basis='measured_page',scale_approved=True,
                    measurement_state='known_reference',ratio_assumed=False,
                    measured_ruler=measured_ruler_evidence(getattr(calibration,'evidence_notes',None)))
    if method in ('estimated','full_sheet'):
        dimensions=PAPER_MM.get(settings.get('source_paper_size','A1'))
        if settings.get('source_paper_size')=='CUSTOM':dimensions=(settings.get('source_width_mm'),settings.get('source_height_mm'))
        if not dimensions or any(v is None or not math.isfinite(v) or v<=0 for v in dimensions):
            return dict(result,scale_reason='source_physical_dimensions_unavailable')
        orientation=settings.get('source_orientation') or ('landscape' if width>=height else 'portrait')
        short,long=sorted(dimensions)
        pw,ph=(long,short) if orientation=='landscape' else (short,long)
        if method=='full_sheet':
            if not settings.get('full_sheet_confirmed'):return dict(result,scale_reason='confirm_complete_sheet')
            if abs((width/height)/(pw/ph)-1)>.02:return dict(result,scale_reason='sheet_edges_or_reference_required')
            ppm=(width/pw)*1000/denominator
        else:
            # Uniform containment; the slider is an explicit physical-size assumption.
            ppm=max(width/pw,height/ph)*1000/denominator/(settings.get('image_size_percent',100)/100)
        estimated=method=='estimated' or result['ratio_assumed']
        return dict(result,pixels_per_meter=ppm,scale_basis='estimated_paper' if method=='estimated' else 'full_sheet_ratio',
                    measurement_state='estimated' if estimated else 'source_sheet',estimated=estimated,
                    scale_reason='assumed_paper_placement' if method=='estimated' else 'confirmed_complete_source_sheet',
                    assumed_paper_size=settings.get('source_paper_size','A1'))
    if native_width is None or native_height is None:
        if method=='auto' and settings.get('allow_estimated_scale'):
            return resolve_draft_scale(width,height,page=page,settings={**settings,'measurement_method':'estimated'})
        return dict(result,scale_reason='known_distance_required')
    if any(not math.isfinite(v) or v<=0 for v in (native_width,native_height,denominator)):
        return dict(result,scale_reason='source_physical_dimensions_unavailable')
    sx,sy=width/native_width,height/native_height
    if abs(sx/sy-1)>max(.0005,1.5/min(width,height)):
        return dict(result,scale_reason='source_aspect_transform_required')
    ppm=sx*1000/denominator
    if not .000001<=ppm<=1_000_000:
        return dict(result,scale_reason='source_scale_out_of_bounds')
    return dict(result,pixels_per_meter=ppm,scale_basis='pdf_page_ratio',
                measurement_state='estimated' if result['ratio_assumed'] else 'source_sheet',estimated=result['ratio_assumed'],
                scale_reason='source_page_dimensions_and_drawing_ratio')
