"""Isotropic, provenance-labelled draft scale; never layout approval."""
import math

PAPER_MM = {'A4': (210, 297), 'A3': (297, 420), 'A2': (420, 594),
            'A1': (594, 841), 'A0': (841, 1189)}
ASPECT_TOLERANCE = .02  # Pixel rounding/small scan margins, not anisotropic stretching.


def resolve_draft_scale(width, height, *, calibration=None, page=None, settings=None):
    result = dict(pixels_per_meter=None, scale_basis='unresolved', scale_approved=False)
    if calibration is not None:
        if (calibration.reference_width_pixels, calibration.reference_height_pixels) != (width, height):
            return dict(result, scale_reason='saved_calibration_dimensions_changed')
        ppm = calibration.pixels_per_meter
        if ppm is None or not math.isfinite(ppm) or ppm <= 0:
            return dict(result, scale_reason='saved_calibration_unavailable')
        return dict(result, pixels_per_meter=float(ppm), scale_basis='measured_page', scale_approved=True)
    if any(not math.isfinite(v) or v <= 0 for v in (width, height)):
        return dict(result, scale_reason='invalid_source_dimensions')
    page, settings = page or {}, settings or {}
    if page.get('cropped') or page.get('multiple_scaled_views'):
        return dict(result, scale_reason='cropped_or_multiple_scale_views')
    paper = settings.get('paper_size') or page.get('paper_size') or 'A1'
    denominator = settings.get('scale_denominator', 100)
    dimensions = PAPER_MM.get(paper)
    # Reliable source page dimensions take priority over the A1 input default.
    if not settings.get('paper_size') and page.get('page_width_mm') and page.get('page_height_mm'):
        dimensions = sorted((page['page_width_mm'], page['page_height_mm']))
    if not dimensions or not math.isfinite(denominator) or denominator <= 0:
        return dict(result, scale_reason='paper_or_ratio_unavailable')
    short, long = sorted(dimensions)
    pixel_short, pixel_long = sorted((width, height))
    if abs((pixel_long / pixel_short) / (long / short) - 1) > ASPECT_TOLERANCE:
        return dict(result, scale_reason='paper_aspect_mismatch')
    return dict(result, pixels_per_meter=pixel_long / (long * denominator / 1000),
        scale_basis='ved_paper_ratio_draft', paper_size=paper, scale_denominator=denominator,
        scale_reason='nominal_full_sheet_not_independent_calibration')
