"""No private uploads/references are needed for these regression gates."""
import cv2
import numpy as np

from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationPayload
from app.ai.floor_plan_interpretation.chromatic_walls import with_chromatic_wall_evidence, _suppress_same_band_duplicates
from app.ai.floor_plan_interpretation.automatic_wiring import with_automatic_wiring
from app.ai.floor_plan_interpretation.demo_cv import interpret_floor_plan_demo, preprocessing_configuration


def fixture_scene():
    image = np.full((400, 600, 3), 255, np.uint8)
    value = interpret_floor_plan_demo(image, selected_drawing=True).model_dump(mode='json')
    value['document_state'] = 'partial'
    for i, (x, y) in enumerate(((80, 100), (280, 100), (480, 100), (280, 300)), 1):
        cv2.rectangle(image, (x - 10, y - 25), (x + 10, y + 25), (0, 0, 0), 2)
        value['symbols']['items'].append(dict(
            id=f'symbol-{i:04d}', mapping_state='unknown', catalog_class_id=None,
            observed_label='Troffer lights', center=dict(x=x, y=y),
            bounds=dict(x=x - 10, y=y - 25, width=20, height=50),
            orientation_degrees=None, evidence_refs=('region:region-0001',), ambiguity='ambiguous'))
    value['symbols']['state'] = 'partial'
    return image, FloorPlanInterpretationPayload.model_validate(value)


def test_adjacent_fixture_ink_stays_observed_and_does_not_connect_crossings():
    image, payload = fixture_scene()
    cv2.line(image, (80, 100), (480, 100), (0, 0, 0), 1)
    cv2.line(image, (280, 100), (280, 300), (0, 0, 0), 1)
    before = image.copy(), payload.model_dump_json()
    result = with_automatic_wiring(payload, image)
    assert len(result.observed_routes.segments) == 3
    assert all(c.from_ref.startswith('segment:') and c.to_ref.startswith('symbol:')
               for c in result.observed_routes.connections) # contacts, not crossing junctions
    assert all(s.route_kind == 'observed' and s.ambiguity == 'ambiguous'
               for s in result.observed_routes.segments)
    assert max(abs(p.y - 100) for s in result.observed_routes.segments
               if abs(s.points[0].y - s.points[1].y) < 1 for p in s.points) <= 1
    assert with_automatic_wiring(payload, image) == result
    assert with_automatic_wiring(result, image) == result
    assert payload.model_dump_json() == before[1]
    np.testing.assert_array_equal(image, before[0])


def test_proximity_and_glyph_interiors_are_not_source_wire_evidence():
    image, payload = fixture_scene()
    assert not with_automatic_wiring(payload, image).observed_routes.segments
    # A grid grazing elongated fixture tips is not a centre-axis path.
    cv2.line(image, (80, 75), (480, 75), (0, 0, 0), 1)
    assert not with_automatic_wiring(payload, image).observed_routes.segments


def test_erased_wire_span_remains_unresolved_not_a_generated_shortcut():
    image, payload = fixture_scene()
    cv2.line(image, (80, 100), (480, 100), (0, 0, 0), 1)
    image[95:106, 170:190] = 255
    result = with_automatic_wiring(payload, image)
    assert len(result.observed_routes.segments) == 1
    assert min(p.x for p in result.observed_routes.segments[0].points) >= 280
    assert all(c.to_ref!='symbol:symbol-0001' for c in result.observed_routes.connections)


def test_rich_fixture_scene_still_keeps_regular_dashed_evidence():
    image, payload = fixture_scene()
    for x in range(90, 270, 20):
        cv2.line(image, (x, 100), (x + 11, 100), (0, 0, 0), 1)
    result = with_automatic_wiring(payload, image)
    assert result.observed_routes.segments
    assert all(s.line_style == 'dashed' for s in result.observed_routes.segments)


def wall_scene():
    image = np.full((600, 600, 3), 255, np.uint8)
    value = interpret_floor_plan_demo(image, selected_drawing=True).model_dump()
    # Faint structural fills with black edges; black one-pixel ceiling grid.
    for y in range(90, 520, 40):
        cv2.line(image, (60, y), (540, y), (0, 0, 0), 1)
    for x in range(90, 520, 40):
        cv2.line(image, (x, 60), (x, 540), (0, 0, 0), 1)
    color = (150, 130, 170)
    for a, b in (((55, 55), (545, 65)), ((55, 535), (545, 545)),
                 ((55, 55), (65, 545)), ((535, 55), (545, 545))):
        cv2.rectangle(image, a, b, color, -1)
    image[535:546, 260:320] = 255  # real door opening
    return image, FloorPlanInterpretationPayload.model_validate(value)


def test_structural_colour_bands_not_grid_and_opening_not_closed():
    image, payload = wall_scene()
    before = image.copy()
    result = with_chromatic_wall_evidence(payload, image)
    assert result != payload
    assert len(result.walls.items) >= 5
    for wall in result.walls.items:
        a, b = wall.start, wall.end
        assert (max(abs(a.x - 60), abs(b.x - 60)) < 10
                or max(abs(a.x - 540), abs(b.x - 540)) < 10
                or max(abs(a.y - 60), abs(b.y - 60)) < 10
                or max(abs(a.y - 540), abs(b.y - 540)) < 10)
        if abs(a.y - 540) < 10 and abs(b.y - 540) < 10:
            assert not (min(a.x, b.x) < 260 and max(a.x, b.x) > 320)
    assert with_chromatic_wall_evidence(payload, image) == result
    np.testing.assert_array_equal(image, before)


def test_monochrome_and_coloured_glyphs_retain_existing_walls():
    image, payload = wall_scene()
    mono = cv2.cvtColor(cv2.cvtColor(image, cv2.COLOR_RGB2GRAY), cv2.COLOR_GRAY2RGB)
    assert with_chromatic_wall_evidence(payload, mono) == payload
    plain = np.full_like(image, 255)
    cv2.rectangle(plain, (200, 200), (220, 240), (150, 130, 170), -1)
    assert with_chromatic_wall_evidence(payload, plain) == payload


def test_large_circuit_annotation_box_does_not_erase_a_structural_wall():
    image,payload=wall_scene()
    value=payload.model_dump();value['document_state']='partial'
    value['symbols']=dict(state='partial',truncated=False,items=[dict(id='symbol-0001',mapping_state='unknown',
        catalog_class_id=None,observed_label='Circuit homerun',center=dict(x=60,y=250),
        bounds=dict(x=25,y=200,width=80,height=100),orientation_degrees=None,
        evidence_refs=('region:region-0001',),ambiguity='ambiguous')])
    annotated=FloorPlanInterpretationPayload.model_validate(value)
    assert with_chromatic_wall_evidence(payload,image).walls==with_chromatic_wall_evidence(annotated,image).walls


def test_colour_refinement_never_breaks_known_opening_references():
    image, payload = wall_scene()
    value = payload.model_dump()
    value['document_state'] = 'partial'
    value['walls']['state'] = 'partial'
    value['walls']['items'] = [dict(id='wall-0001', start=dict(x=55, y=55), end=dict(x=55, y=545),
                                  evidence_refs=('region:region-0001',), ambiguity='ambiguous')]
    value['openings']['state'] = 'partial'
    value['openings']['items'] = [dict(id='opening-0001', opening_type='door',
        start=dict(x=55, y=250), end=dict(x=55, y=300), wall_ref='wall-0001',
        evidence_refs=('region:region-0001',), ambiguity='ambiguous')]
    protected = FloorPlanInterpretationPayload.model_validate(value)
    assert with_chromatic_wall_evidence(protected, image) == protected


def test_refinement_configuration_is_pinned_in_run_provenance():
    config = preprocessing_configuration(1340, 3264)
    assert config['chromatic_walls']['version'] == 'chromatic-structural-bands-v3'
    assert config['paired_wall_boundaries']['version']=='anchored-paired-boundaries-v1'
    assert config['switch_gang_policy']=='provisional-switch-gang-count-v1'
    assert config['fixture_wiring']['minimum_support'] == .95
    assert config == preprocessing_configuration(1340, 3264)


def test_parallel_walls_are_only_duplicate_when_same_filled_band():
    segments = [(50, 20, 50, 180, 12), (56, 30, 56, 170, 12)]
    filled = np.zeros((200, 100), np.uint8)
    filled[20:181, 44:63] = 255
    combined = _suppress_same_band_duplicates(segments, filled)
    assert len(combined) == 1 and combined[0][:4] == (53, 20, 53, 180)
    separate = np.zeros_like(filled)
    separate[20:181, 49:52] = 255
    separate[30:171, 55:58] = 255
    assert _suppress_same_band_duplicates(segments, separate) == segments
