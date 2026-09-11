import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.ai.floor_plan_interpretation.gold_evaluation import (
    HARD_GATES,
    REQUIRED_METRICS,
    ApproverAuthoritySnapshot,
    CompletenessMarkers,
    GoldAnnotationDocument,
    GoldEvaluationError,
    GoldManifestRequest,
    GoldRecordRequest,
    MetricContract,
    MetricDeclaration,
    ReviewDecision,
    SymbolTruth,
    build_gold_manifest,
    build_metric_report,
    evaluate_symbols,
    evaluate_symbols_by_class,
    load_development_gold,
    validate_metric_contract_authority,
)

NOW = datetime(2026, 9, 11, 2, 0, tzinfo=UTC)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _authority(**changes):
    value = dict(assignment_id=7, assignee_user_id=22, assigned_by_user_id=11,
                 authority_scope="VED_AI_DATASET_APPROVER", active_from=NOW - timedelta(days=1),
                 inactive_at=None, is_active=True)
    value.update(changes)
    return ApproverAuthoritySnapshot(**value)


def _record(root, *, record_id="record-1", source_id="source-1", page_number=1,
            project_group_id="project-a", drawing_set_id="drawing-a",
            split="development_validation", complete=True, decision="approved",
            approver_user_id=22, assignment_id=7):
    source = root / f"{record_id}.png"
    source.write_bytes(f"source:{record_id}".encode())
    source_hash = _sha(source)
    annotation = GoldAnnotationDocument(
        schema_version=1, source_id=source_id, source_sha256=source_hash,
        page_number=page_number, width_pixels=100, height_pixels=100,
        sheet_type="electrical_plan",
        symbols=(SymbolTruth(symbol_id=f"symbol-{record_id}", class_id=1,
                             x_min=10.0, y_min=10.0, x_max=20.0, y_max=20.0),),
        completeness=CompletenessMarkers(
            symbols="complete" if complete else "pending", geometry="not_applicable",
            observed_wiring="not_applicable", text_dimensions="not_applicable"),
    )
    annotation_path = root / f"{record_id}.annotation.json"
    annotation_path.write_text(annotation.model_dump_json(), encoding="utf-8")
    annotation_hash = _sha(annotation_path)
    return GoldRecordRequest(
        record_id=record_id, source_id=source_id, page_number=page_number,
        project_group_id=project_group_id, drawing_set_id=drawing_set_id,
        split=split, permission_purpose=("sealed_evaluation" if split == "sealed_test" else "development_evaluation"),
        source_relative_path=source.name, source_sha256=source_hash,
        annotation_relative_path=annotation_path.name, annotation_sha256=annotation_hash,
        annotation_author_user_id=33,
        review=ReviewDecision(decision=decision, assignment_id=assignment_id,
                              approver_user_id=approver_user_id, decided_at=NOW,
                              reviewed_annotation_sha256=annotation_hash),
    )


def _build(root, records, authorities=None, *, revision=1, parent=None):
    request = GoldManifestRequest(
        dataset_id="ved-gold", revision=revision,
        parent_manifest_relative_path=None if parent is None else parent.relative_to(root).as_posix(),
        parent_manifest_sha256=None if parent is None else _sha(parent), records=tuple(records))
    return build_gold_manifest(
        private_root=root, manifest_path=root / "gold" / f"v{revision:04d}" / "manifest.json",
        request=request, authorities=(_authority(),) if authorities is None else tuple(authorities))


def test_build_is_idempotent_and_keeps_source_bytes(tmp_path):
    record = _record(tmp_path)
    source = tmp_path / record.source_relative_path
    before = source.read_bytes()
    first = _build(tmp_path, (record,))
    second = _build(tmp_path, (record,))
    assert first.changed is True and second.changed is False
    assert first.eligible_development_count == 1 and source.read_bytes() == before


@pytest.mark.parametrize("authority,changes", [
    (None, {}), (_authority(is_active=False), {}),
    (_authority(inactive_at=NOW, is_active=False), {}),
    (_authority(assignee_user_id=33), {"approver_user_id": 33}),
    (_authority(assigned_by_user_id=22), {}),
    (_authority(active_from=NOW + timedelta(minutes=1)), {}),
])
def test_rejects_wrong_self_inactive_or_expired_authority(tmp_path, authority, changes):
    record = _record(tmp_path, **changes)
    with pytest.raises(GoldEvaluationError, match="INVALID_REVIEW_AUTHORITY"):
        _build(tmp_path, (record,), () if authority is None else (authority,))


def test_rejects_altered_source_annotation_and_review_hashes(tmp_path):
    source_record = _record(tmp_path, record_id="source-change")
    (tmp_path / source_record.source_relative_path).write_bytes(b"changed")
    with pytest.raises(GoldEvaluationError, match="GOLD_HASH_MISMATCH"):
        _build(tmp_path, (source_record,))
    annotation_record = _record(tmp_path, record_id="annotation-change")
    with (tmp_path / annotation_record.annotation_relative_path).open("a", encoding="utf-8") as stream:
        stream.write(" ")
    with pytest.raises(GoldEvaluationError, match="GOLD_HASH_MISMATCH"):
        _build(tmp_path, (annotation_record,))
    stale = _record(tmp_path, record_id="review-change").model_copy(update={
        "review": _record(tmp_path, record_id="review-change").review.model_copy(update={"reviewed_annotation_sha256": "0" * 64})})
    with pytest.raises(GoldEvaluationError, match="STALE_GOLD_REVIEW"):
        _build(tmp_path, (stale,))


def test_incomplete_and_rejected_are_inventoried_but_ineligible(tmp_path):
    result = _build(tmp_path, (_record(tmp_path, record_id="incomplete", complete=False), _record(tmp_path, record_id="rejected", decision="rejected")))
    records = json.loads(result.manifest_path.read_text(encoding="utf-8"))["records"]
    assert result.eligible_development_count == 0
    assert {item["record_id"]: item["eligible"] for item in records} == {"incomplete": False, "rejected": False}


def test_project_leakage_and_frozen_membership_are_rejected(tmp_path):
    dev = _record(tmp_path, record_id="dev", drawing_set_id="drawing-a")
    sealed = _record(tmp_path, record_id="sealed", drawing_set_id="drawing-b", split="sealed_test")
    with pytest.raises(GoldEvaluationError, match="PROJECT_SPLIT_LEAKAGE"):
        _build(tmp_path, (dev, sealed))
    first = _build(tmp_path, (dev,))
    extra = _record(tmp_path, record_id="extra", project_group_id="project-b", drawing_set_id="drawing-b")
    with pytest.raises(GoldEvaluationError, match="FROZEN_MEMBERSHIP_REMOVED"):
        _build(tmp_path, (extra,), revision=2, parent=first.manifest_path)


def test_sealed_records_are_not_exposed_and_manifest_tampering_fails(tmp_path):
    dev = _record(tmp_path, record_id="dev")
    sealed = _record(tmp_path, record_id="sealed", project_group_id="project-b", drawing_set_id="drawing-b", split="sealed_test")
    result = _build(tmp_path, (dev, sealed))
    assert [item["record_id"] for item in load_development_gold(result.manifest_path, expected_sha256=result.manifest_sha256)] == ["dev"]
    result.manifest_path.write_bytes(result.manifest_path.read_bytes() + b" ")
    with pytest.raises(GoldEvaluationError, match="INVALID_GOLD_MANIFEST"):
        load_development_gold(result.manifest_path, expected_sha256=result.manifest_sha256)


def _contract():
    unsupported = {"wall_endpoint_error_pixels", "wall_angle_error_degrees", "wall_segment_match_rate", "wall_duplicate_rate", "room_polygon_iou", "opening_f1", "panel_f1", "scale_absolute_error", "scale_relative_error", "wiring_presence_accuracy", "wiring_segment_f1", "wiring_topology_error", "wiring_length_error", "peak_vram_bytes"}
    declarations = tuple(MetricDeclaration(name=name, status="not_applicable", unit="not_applicable", reason="Current deterministic baseline has no validated output.") if name in unsupported else MetricDeclaration(name=name, status="threshold", direction="minimum", threshold=0.5, unit="ratio") for name in REQUIRED_METRICS)
    return MetricContract(contract_id="metrics", revision=1, authored_by_user_id=33, approved=False, declarations=declarations, hard_gates=HARD_GATES, box_iou_threshold=0.5)


def test_contract_requires_full_declaration_and_reports_na_pending():
    with pytest.raises(ValidationError, match="every required metric"):
        MetricContract(contract_id="metrics", revision=1, authored_by_user_id=33, approved=False, declarations=(), hard_gates=HARD_GATES, box_iou_threshold=0.5)
    report = {item.name: item for item in build_metric_report(_contract(), {"symbol_precision": 0.75})}
    assert len(report) == len(REQUIRED_METRICS)
    assert report["wall_endpoint_error_pixels"].status == "not_applicable" and report["wall_endpoint_error_pixels"].value is None
    assert report["symbol_precision"].status == "measured" and report["symbol_recall"].status == "pending"


def test_approved_metric_contract_uses_independent_authority():
    approved = _contract().model_copy(update={"approved": True, "approved_by_assignment_id": 7, "approved_by_user_id": 22, "approved_at": NOW})
    validate_metric_contract_authority(approved, (_authority(),))
    with pytest.raises(GoldEvaluationError, match="INVALID_REVIEW_AUTHORITY"):
        validate_metric_contract_authority(approved.model_copy(update={"approved_by_user_id": 33}), (_authority(assignee_user_id=33),))


def test_known_answer_symbol_metrics_and_per_class_results():
    truth = (SymbolTruth(symbol_id="truth-a", class_id=1, x_min=0, y_min=0, x_max=10, y_max=10), SymbolTruth(symbol_id="truth-b", class_id=2, x_min=20, y_min=20, x_max=30, y_max=30))
    predictions = (SymbolTruth(symbol_id="pred-a", class_id=1, x_min=0, y_min=0, x_max=10, y_max=10), SymbolTruth(symbol_id="pred-extra", class_id=1, x_min=40, y_min=40, x_max=50, y_max=50))
    result = evaluate_symbols(truth, predictions, iou_threshold=0.5)
    assert (result.true_positive, result.false_positive, result.false_negative) == (1, 1, 1)
    assert (result.precision, result.recall, result.f1, result.count_error, result.mean_iou, result.mean_center_error_pixels) == (0.5, 0.5, 0.5, 0, 1.0, 0.0)
    per_class = evaluate_symbols_by_class(truth, predictions, iou_threshold=0.5)
    assert (per_class[1].true_positive, per_class[1].false_positive) == (1, 1)
    assert (per_class[2].true_positive, per_class[2].false_negative) == (0, 1)
