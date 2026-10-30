"""Known-dimension calibration and explicit similarity-transform propagation."""
import math
import json

PAPER_RULER_PREFIX = 'PAPER_RULER_V1 '
MEASURED_RULER_PREFIX = 'MEASURED_RULER_V1 '


def paper_ruler_evidence(notes):
    """Read persisted draft ruler provenance without treating it as approval."""
    if not isinstance(notes, str) or not notes.startswith(PAPER_RULER_PREFIX):
        return None
    try:
        value = json.loads(notes.split('\n', 1)[0][len(PAPER_RULER_PREFIX):])
        return value if isinstance(value, dict) else None
    except (ValueError, TypeError):
        return None


def known_dimension_scale(pixel_length, real_length_meters):
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0
           for v in (pixel_length, real_length_meters)):
        raise ValueError('Calibration requires positive finite measured lengths.')
    value = pixel_length / real_length_meters
    if not math.isfinite(value) or not .000001 <= value <= 1_000_000:
        raise ValueError('Calibration scale is outside supported bounds.')
    return value


def transformed_scale(pixels_per_meter, local_to_reference):
    """Map a saved reference scale through a known local->reference affine map.

    Crop translation and rotation do not change scale. Uniform resizing does.
    Reject shear/nonuniform resize rather than inventing a single pixel scale.
    Transform provenance/identity must be established by the caller, never by
    guessing ratios from image dimensions or a printed 1:100 label.
    """
    a, b, c, d, e, f = (local_to_reference[k] for k in ('a', 'b', 'c', 'd', 'e', 'f'))
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in (a,b,c,d,e,f)):
        raise ValueError('Calibration transform must be finite.')
    sx, sy = math.hypot(a,b), math.hypot(c,d)
    if (sx <= 0 or not math.isclose(sx, sy, rel_tol=1e-9, abs_tol=1e-12)
            or not math.isclose(a*c+b*d, 0, abs_tol=1e-9*sx*sy)):
        raise ValueError('A scalar calibration requires an aspect-preserving transform.')
    return known_dimension_scale(pixels_per_meter, sx)


def measured_ruler_evidence(notes):
    if not isinstance(notes,str) or not notes.startswith(MEASURED_RULER_PREFIX):
        return None
    try:
        value=json.loads(notes.split('\n',1)[0][len(MEASURED_RULER_PREFIX):])
        return value if isinstance(value,dict) else None
    except (ValueError,TypeError):
        return None
