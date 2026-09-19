from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from app.geometry.canonical import CanonicalGeometryError, canonical_geometry_from_dict
from app.services.material_quantity_service import component_quantities


def document():
    return canonical_geometry_from_dict(json.loads(
        (Path(__file__).resolve().parents[2] / "fixtures/canonical_geometry_v1.json").read_text()))


def test_confirmed_manual_corrected_classes_and_reproducibility():
    layout = document()
    confirmed, manual = layout.symbols
    corrected = replace(confirmed, id="detected:502", source_record_id=502,
                        class_id=manual.class_id, class_name=manual.class_name)
    layout = replace(layout, symbols=(*layout.symbols, corrected))
    original = deepcopy(layout.to_dict())
    quantities = component_quantities(layout)
    assert [(q.class_id, q.quantity) for q in quantities] == [(2, 2), (7, 1)]
    assert quantities[0].symbol_ids == ("detected:502", "manual:601")
    assert component_quantities(replace(layout, symbols=tuple(reversed(layout.symbols)))) == quantities
    assert layout.to_dict() == original


@pytest.mark.parametrize("status", ["deleted", "rejected", "detected", "needs_review"])
def test_unreviewed_or_excluded_records_cannot_enter_quantities(status):
    layout = document()
    invalid = replace(layout.symbols[0], status=status)
    with pytest.raises(CanonicalGeometryError):
        component_quantities(replace(layout, symbols=(invalid,)))


def test_empty_layout_and_duplicate_or_conflicting_identity():
    layout = document()
    assert component_quantities(replace(layout, symbols=())) == ()
    with pytest.raises(ValueError, match="Duplicate"):
        component_quantities(replace(layout, symbols=(layout.symbols[0],) * 2))
    other = replace(layout.symbols[0], id="detected:503", source_record_id=503, class_name="Conflict")
    with pytest.raises(ValueError, match="Conflicting"):
        component_quantities(replace(layout, symbols=(*layout.symbols, other)))
