"""Matching and audit semantics; no private test drawing or accuracy claim."""
import pytest

from evaluate_reviewed_plan_detector import (
    center_inside, transform_targets, match_reviewed, fusion_rejections,
    restore_trace_row,
    run_scope,
)


def target(box, allowed, name="one"):
    return dict(record_id=name, bbox=box, allowed_class_ids=allowed)


def prediction(box, cls):
    return dict(bbox=box, class_id=cls, score=.9, tile_origin=(0, 0))


def test_exact_affine_annotation_mapping_and_region_center():
    source = [dict(record_id="box", source_box=[1, 2, 11, 12])]
    result = transform_targets(source, [2, 3])
    assert result[0]["bbox"] == [2, 6, 22, 36]
    assert source[0]["source_box"] == [1, 2, 11, 12]
    assert center_inside(result[0]["bbox"], [0, 0, 15, 25])


def test_allowed_subtype_matches_without_coercing_saved_label():
    report = match_reviewed([target([0, 0, 10, 10], [52, 80])], [prediction([0, 0, 10, 10], 80)])
    assert report["matched"] == 1
    assert not report["confusions"]
    assert report["precision"] is None


def test_one_prediction_cannot_match_two_adjacent_reviewed_targets():
    report = match_reviewed([target([0, 0, 10, 10], [0], "a"), target([0, 0, 10, 10], [0], "b")],
                            [prediction([0, 0, 10, 10], 0)])
    assert report["matched"] == 1
    assert len(report["misses"]) == 1


def test_maximum_cardinality_avoids_greedy_allowed_set_loss():
    # Ambiguous target can use either prediction, exact target only class0.
    report = match_reviewed([target([0, 0, 10, 10], [0, 1], "a"), target([0, 0, 10, 10], [0], "b")],
                            [prediction([0, 0, 10, 10], 0), prediction([0, 0, 10, 10], 1)])
    assert report["matched"] == 2


def test_wrong_class_is_reported_as_confusion_not_true_match():
    report = match_reviewed([target([0, 0, 10, 10], [0])], [prediction([0, 0, 10, 10], 3)])
    assert report["matched"] == 0
    assert report["confusions"][0]["predicted"] == 3
    assert report["unmatched_proposals"] == [0]
    assert report["per_class"] == [dict(allowed_class_ids=[0], reviewed_positives=1, matched=0, missed=1)]


def test_wrong_location_and_uncovered_prediction_do_not_become_precision_gold():
    report = match_reviewed([target([0, 0, 10, 10], [0])], [prediction([50, 50, 60, 60], 0)])
    assert report["matched"] == 0
    assert not report["confusions"]
    assert report["precision"] is None


def test_fusion_diagnostics_distinguish_duplicate_observation_from_retained_box():
    first = prediction([0, 0, 10, 10], 0)
    duplicate = dict(first, score=.8, tile_origin=(1, 0))
    rejected = fusion_rejections([first, duplicate], [first])
    assert len(rejected) == 1
    assert rejected[0]["tile_origin"] == (1, 0)
    assert "duplicate" in rejected[0]["rejection_reason"]


def test_two_box_fusion_evidence_is_preserved_not_reported_as_unseen_rejection():
    first = prediction([0, 0, 10, 10], 0)
    second = dict(first, score=.8)
    merged = dict(first, bbox=[.1, 0, 10.1, 10], localization_observations=[first, second])
    assert not fusion_rejections([first, second], [merged])


def test_scoped_fusion_observations_restore_exactly_to_same_source_plane():
    first = prediction([0, 0, 10, 10], 0)
    second = dict(first, score=.8)
    merged = dict(first, bbox=[.1, 0, 10.1, 10], localization_observations=[first, second])
    raw = [restore_trace_row(r, (100, 200)) for r in [first, second]]
    fused = [restore_trace_row(merged, (100, 200))]
    assert not fusion_rejections(raw, fused)
    assert first["bbox"] == [0, 0, 10, 10]


def test_scope_report_uses_shared_observed_route_schema(monkeypatch):
    from types import SimpleNamespace
    import numpy as np
    from app.ai.floor_plan_interpretation.candidate import ObservedRoutes
    from app.services import interpretation_processing_service as worker
    import evaluate_reviewed_plan_detector as evaluator

    def interpret(image, **_kwargs):
        worker.multiclass.locate(image)
        return SimpleNamespace(symbols=SimpleNamespace(items=()),
            walls=SimpleNamespace(items=()), regions=(),
            observed_routes=ObservedRoutes(state="empty"),
            model_dump=lambda **_kwargs: {"observed_routes": {"state": "empty", "segments": [], "connections": []}})

    monkeypatch.setattr(worker, "_interpret_cv_scope", interpret)
    monkeypatch.setattr(evaluator, "locate_with_trace", lambda *_args, **_kwargs: ([], False, [], []))
    result = run_scope(np.zeros((20, 30, 3), dtype=np.uint8), None, object(), {}, "a" * 64)
    assert result["wire_paths_count"] == 0
    assert result["walls_count"] == 0
    assert result["retained"] == []
    assert result["device_connections_count"] == 0
    assert result["candidate_payload"]["observed_routes"]["segments"] == []


def test_evaluation_captures_real_dense_policy_and_correct_training_provenance(monkeypatch):
    from types import SimpleNamespace
    import numpy as np
    from app.ai.floor_plan_interpretation.candidate import ObservedRoutes
    from app.services import interpretation_processing_service as worker
    import evaluate_reviewed_plan_detector as evaluator

    rows = [prediction([20+i*20, 20, 30+i*20, 30], 0) for i in range(8)]
    observed = []
    def capture(_pixels, *_args, catalog, **_kwargs):
        observed.append(catalog.get("tile_size", evaluator.shared.TILE_SIZE))
        return rows, False, rows, rows

    def interpret(image, **_kwargs):
        worker.multiclass.locate(image)
        assert worker.multiclass.TRAINING_DATASET_SHA256 == "b" * 64
        return SimpleNamespace(symbols=SimpleNamespace(items=()), walls=SimpleNamespace(items=()),
            regions=(), observed_routes=ObservedRoutes(state="empty"), model_dump=lambda **_kwargs: {})

    monkeypatch.setattr(worker, "_interpret_cv_scope", interpret)
    monkeypatch.setattr(evaluator, "locate_with_trace", capture)
    monkeypatch.setattr(evaluator.multiclass, "PROFILE", "power80")
    result = run_scope(np.zeros((640, 640, 3), dtype=np.uint8), None, object(),
        {0: ("LED downlight", "approved:L1")}, "b" * 64)
    assert observed == [256, 320]
    assert [p["tile_size"] for p in result["localization_passes"]] == [256, 320]
    assert result["tile_size"] == 320
