"""Tests for observed wiring extraction and fusion (U12)."""

import pytest
import numpy as np
import cv2

from app.ai.floor_plan_interpretation.candidate import (
    AffineTransform,
    ObservedRoutes,
    PanelCandidate,
    PixelPoint,
    PixelBounds,
    SymbolCandidate,
)
from app.ai.floor_plan_interpretation.observed_wiring import (
    ObservedWiringConfig,
    build_observed_routes_payload,
    extract_observed_wiring_from_image,
    fuse_observed_routes,
)


@pytest.fixture
def sample_config() -> ObservedWiringConfig:
    return ObservedWiringConfig()


def test_extract_wiring_from_blank_image(sample_config):
    # Blank white image
    image = np.full((100, 100, 3), 255, dtype=np.uint8)
    segments, connections = extract_observed_wiring_from_image(
        image, "tile-1", [], [], sample_config
    )
    assert len(segments) == 0
    assert len(connections) == 0


def test_extract_wiring_with_visible_lines(sample_config):
    # Blank white image
    image = np.full((200, 200, 3), 255, dtype=np.uint8)
    
    # Draw a thin black line (wiring) - 2px to survive noise filtering
    cv2.line(image, (20, 20), (100, 100), (0, 0, 0), 2)
    
    # Draw a thick black line (should be filtered out as wall-like)
    cv2.line(image, (150, 20), (150, 180), (0, 0, 0), 10)
    
    symbols = [
        SymbolCandidate(
            id="symbol-0001",
            mapping_state="matched",
            catalog_class_id=1,
            observed_label=None,
            center=PixelPoint(x=18.0, y=18.0),
            bounds=PixelBounds(x=10.0, y=10.0, width=16.0, height=16.0),
            orientation_degrees=None,
            evidence_refs=("region:tile-0001",),
            ambiguity="clear"
        )
    ]
    
    panels = [
        PanelCandidate(
            id="panel-0001",
            label=None,
            center=PixelPoint(x=102.0, y=102.0),
            bounds=PixelBounds(x=90.0, y=90.0, width=24.0, height=24.0),
            orientation_degrees=None,
            evidence_refs=("region:tile-0001",),
            ambiguity="clear"
        )
    ]

    segments, connections = extract_observed_wiring_from_image(
        image, "tile-0001", symbols, panels, sample_config
    )
    
    assert len(segments) == 1
    assert segments[0].route_kind == "observed"
    
    # Check endpoints match roughly what we drew
    # The polyline approximation might yield endpoints slightly off exact (20,20)
    p_start, p_end = segments[0].points[0], segments[0].points[-1]
    
    assert connections == ()
    assert segments[0].ambiguity == "ambiguous"


def test_fuse_observed_routes(sample_config):
    from app.ai.floor_plan_interpretation.candidate import ObservedRouteSegment
    
    # Tile 1: Line from (10, 10) to (50, 50)
    seg1 = ObservedRouteSegment(
        id="segment-0001",
        route_kind="observed",
        points=(PixelPoint(x=10, y=10), PixelPoint(x=50, y=50)),
        evidence_refs=("region:tile-0001",),
        ambiguity="clear"
    )
    
    # Tile 2: Line from (50, 50) to (100, 10) in local coords.
    # We will simulate tile 2 having no offset but the segment matches exactly.
    seg2 = ObservedRouteSegment(
        id="segment-0002",
        route_kind="observed",
        points=(PixelPoint(x=51, y=51), PixelPoint(x=100, y=10)),
        evidence_refs=("region:tile-0002",),
        ambiguity="clear"
    )
    
    tile_segments = [("tile-0001", seg1), ("tile-0002", seg2)]
    
    # Identity transforms
    transforms = {
        "tile-0001": AffineTransform(a=1.0, b=0.0, c=0.0, d=1.0, e=0.0, f=0.0),
        "tile-0002": AffineTransform(a=1.0, b=0.0, c=0.0, d=1.0, e=0.0, f=0.0),
    }
    
    fused_segments, fused_conns = fuse_observed_routes(
        tile_segments, [], transforms, sample_config
    )
    
    assert len(fused_segments) == 2
    points = fused_segments[0].points
    assert points[0].x == 10.0
    assert points[0].y == 10.0
    assert points[-1].x == 50.0
    assert points[-1].y == 50.0


def test_exact_duplicate_fusion_preserves_evidence_and_ambiguity(sample_config):
    from app.ai.floor_plan_interpretation.candidate import ObservedRouteSegment
    first = ObservedRouteSegment(
        id="segment-0001", points=(PixelPoint(x=1, y=2), PixelPoint(x=5, y=6)),
        evidence_refs=("region:tile-0001",), ambiguity="ambiguous",
    )
    second = first.model_copy(update={"evidence_refs": ("region:tile-0002",)})
    identity = AffineTransform(a=1.0, b=0.0, c=0.0, d=1.0, e=0.0, f=0.0)
    tiles = [("tile-0001", first), ("tile-0002", second)]
    transforms = {key: identity for key, _ in tiles}
    result, _ = fuse_observed_routes(tiles, [], transforms, sample_config)
    reverse, _ = fuse_observed_routes(list(reversed(tiles)), [], transforms, sample_config)
    assert result == reverse
    assert len(result) == 1
    assert result[0].ambiguity == "ambiguous"
    assert result[0].evidence_refs == ("region:tile-0001", "region:tile-0002")
    with pytest.raises(ValueError, match="Missing wiring source transform"):
        fuse_observed_routes(tiles, [], {}, sample_config)
    

def test_build_observed_routes_payload(sample_config):
    # Unsupported page
    payload = build_observed_routes_payload([], [], False, True)
    assert payload.state == "unavailable"
    
    # No wiring visible
    payload = build_observed_routes_payload([], [], True, False)
    assert payload.state == "empty"
    
    # Completed with segments
    segments = extract_observed_wiring_from_image(
        np.full((100, 100, 3), 255, dtype=np.uint8), "t1", [], [], sample_config
    )[0]
    payload = build_observed_routes_payload(segments, [], True, True)
    assert payload.state == "failed"
    assert payload.failure_reason


def test_unknown_visibility_is_partial_not_empty():
    payload = build_observed_routes_payload([], [], True, None)
    assert payload.state == "partial"


@pytest.mark.parametrize("junction_dot", [False, True])
def test_crossing_pixels_never_automatically_confirm_electrical_connectivity(junction_dot):
    image = np.full((160, 160, 3), 255, dtype=np.uint8)
    cv2.line(image, (20, 80), (140, 80), (0, 0, 0), 2)
    cv2.line(image, (80, 20), (80, 140), (0, 0, 0), 2)
    if junction_dot:
        cv2.circle(image, (80, 80), 5, (0, 0, 0), -1)
    before = image.copy()
    segments, connections = extract_observed_wiring_from_image(
        image, "tile-0001", [], [], ObservedWiringConfig(),
    )
    assert segments
    assert not connections
    assert all(segment.ambiguity != "clear" for segment in segments)
    assert build_observed_routes_payload(segments, connections, True, True).state == "partial"
    np.testing.assert_array_equal(image, before)


def test_collinear_dashes_preserve_gaps_and_original_pixels():
    image = np.full((100, 200, 3), 255, dtype=np.uint8)
    for start, end in ((20, 50), (65, 95), (110, 140)):
        cv2.line(image, (start, 50), (end, 50), (0, 0, 0), 2)
    before = image.copy()
    segments, connections = extract_observed_wiring_from_image(
        image, "tile-0001", [], [], ObservedWiringConfig(),
    )
    assert len(segments) == 3
    assert not connections
    assert all(max(p.x for p in s.points) - min(p.x for p in s.points) < 35 for s in segments)
    np.testing.assert_array_equal(image, before)


def test_translated_reversed_seam_duplicates_preserve_source_identity():
    from app.ai.floor_plan_interpretation.candidate import ObservedRouteSegment
    first = ObservedRouteSegment(
        id="segment-0001", points=(PixelPoint(x=80, y=20), PixelPoint(x=100, y=20)),
        evidence_refs=("region:tile-0001",), ambiguity="clear",
    )
    second = ObservedRouteSegment(
        id="segment-0001", points=(PixelPoint(x=20, y=20), PixelPoint(x=0, y=20)),
        evidence_refs=("region:tile-0002",), ambiguity="unknown",
    )
    segments, connections = fuse_observed_routes(
        [("tile-0001", first), ("tile-0002", second)], [], {
            "tile-0001": AffineTransform(a=1., b=0., c=0., d=1., e=0., f=0.),
            "tile-0002": AffineTransform(a=1., b=0., c=0., d=1., e=80., f=0.),
        }, ObservedWiringConfig(),
    )
    assert len(segments) == 1
    assert segments[0].points == first.points
    assert segments[0].ambiguity == "unknown"
    assert segments[0].evidence_refs == ("region:tile-0001", "region:tile-0002")
    assert not connections


@pytest.mark.parametrize("connected", [False, True])
def test_crossing_fusion_preserves_only_explicit_junction_evidence(connected):
    from app.ai.floor_plan_interpretation.candidate import ObservedRouteSegment, ObservedRouteConnection
    horizontal = ObservedRouteSegment(
        id="segment-0001", points=(PixelPoint(x=10, y=50), PixelPoint(x=90, y=50)),
        evidence_refs=("region:tile-0001",), ambiguity="ambiguous",
    )
    vertical = ObservedRouteSegment(
        id="segment-0002", points=(PixelPoint(x=50, y=10), PixelPoint(x=50, y=90)),
        evidence_refs=("region:tile-0001",), ambiguity="ambiguous",
    )
    links = [("tile-0001", ObservedRouteConnection(
        id="connection-0001", from_ref="segment:segment-0001", to_ref="segment:segment-0002",
    ))] if connected else []
    segments, connections = fuse_observed_routes(
        [("tile-0001", horizontal), ("tile-0001", vertical)], links,
        {"tile-0001": AffineTransform(a=1., b=0., c=0., d=1., e=0., f=0.)},
        ObservedWiringConfig(),
    )
    assert len(segments) == 2
    assert len(connections) == int(connected)
    assert all(s.ambiguity == "ambiguous" for s in segments)
    if connected:
        assert {connections[0].from_ref, connections[0].to_ref} == {
            f"segment:{s.id}" for s in segments
        }


def test_fusion_rejects_dangling_segment_endpoint():
    from app.ai.floor_plan_interpretation.candidate import ObservedRouteConnection
    connection = ObservedRouteConnection(
        id="connection-0001", from_ref="segment:segment-0009", to_ref="symbol:symbol-0001",
    )
    with pytest.raises(ValueError, match="Dangling tile segment connection"):
        fuse_observed_routes([], [("tile-0001", connection)], {}, ObservedWiringConfig())


def test_prepared_evidence_is_bounded_unknown_and_preserves_pixels():
    from types import SimpleNamespace
    from app.ai.floor_plan_interpretation.observed_wiring import prepare_observed_wiring_evidence
    image = np.full((100, 200, 3), 255, dtype=np.uint8)
    for y in (20, 50, 80):
        cv2.line(image, (20, y), (150, y), (0, 0, 0), 2)
    before = image.copy()
    context = SimpleNamespace(
        source_plane=SimpleNamespace(width_pixels=200, height_pixels=100),
        tiles=(SimpleNamespace(region_id="tile-0001", image_rgb=image,
            local_to_source=AffineTransform(a=1., b=0., c=0., d=1., e=0., f=0.)),),
    )
    evidence = prepare_observed_wiring_evidence(context, ObservedWiringConfig(max_segments=2))
    assert evidence.state == "partial"
    assert evidence.truncated
    assert len(evidence.segments) == 2
    assert not evidence.connections
    np.testing.assert_array_equal(image, before)
    image[:] = 255
    empty = prepare_observed_wiring_evidence(context)
    assert empty.state == "partial"  # CV cannot establish electrical absence.
    assert not empty.segments


@pytest.mark.parametrize("approved,completeness,elevation,expected", [
    (False, "complete", 2.8, "LAYOUT_REVIEW_NOT_APPROVED"),
    (True, "partial", 2.8, "OBSERVED_WIRING_INCOMPLETE"),
    (True, "complete", None, "OBSERVED_WIRING_ELEVATION_REQUIRED"),
    (True, "complete", 2.8, None),
])
def test_review_roundtrip_and_canonical_wiring_gates(approved, completeness, elevation, expected):
    from datetime import UTC, datetime
    from types import SimpleNamespace
    from app.ai.floor_plan_interpretation.pseudo_labeling import (
        ReviewDocument, CompletenessChecklist, ObservedWiringReview,
    )
    from app.geometry.canonical_extension import adapt_reviewed_candidate_to_canonical
    from app.geometry.canonical import CanonicalGeometryError
    review = ReviewDocument(
        candidate_run_id="a" * 32, revision_number=1, reviewed_by_user_id=1,
        review_complete=True, approved_for_layout=approved,
        evidence_notes="Synthetic reviewed route", created_at=datetime.now(UTC),
        checklist=CompletenessChecklist(),
        observed_wiring=(ObservedWiringReview(
            id="wire-0001", disposition="corrected", completeness=completeness,
            points=({"x": 10.0, "y": 20.0}, {"x": 30.0, "y": 40.0}),
            elevation_meters=elevation,
        ),),
    )
    reloaded = ReviewDocument.model_validate_json(review.model_dump_json())
    assert reloaded == review
    arguments = dict(
        review_document=reloaded,
        candidate=SimpleNamespace(payload=SimpleNamespace(source_plane=SimpleNamespace(
            width_pixels=100, height_pixels=100))),
        project_id=1, project_floor_id=1, floor_name="Test", floor_sort_order=0,
        floor_elevation_meters=0.0, floor_plan_id=1, floor_plan_page_id=1,
        source_artifact_id=1, approved_scale_pixels_per_meter=10.0,
        symbol_legends_by_id={}, processing_job_id=1,
    )
    if expected:
        with pytest.raises(CanonicalGeometryError) as error:
            adapt_reviewed_candidate_to_canonical(**arguments)
        assert error.value.code == expected
    else:
        base, extension = adapt_reviewed_candidate_to_canonical(**arguments)
        assert base.routes[0].points[0].x == 1.0
        assert base.routes[0].points[0].elevation_meters == 2.8
        assert extension.route_details[0].route_kind == "observed"
