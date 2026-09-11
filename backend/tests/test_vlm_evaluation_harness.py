"""Tests for U6 Local VLM Bake-Off Evaluation Harness."""

from __future__ import annotations

import hashlib
import json
import socket
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ai.floor_plan_interpretation.candidate import (
    FloorPlanInterpretationPayload,
    parse_candidate_payload_json,
)
from app.ai.floor_plan_interpretation.evaluation_harness import (
    EgressSecurityViolation,
    EvaluationHarness,
    EvaluationHarnessError,
    MockModelProviderAdapter,
    ModelBakeOffResult,
    ModelEvaluationConfig,
    OfflineEgressGuard,
    ResourceTracker,
)
from app.ai.floor_plan_interpretation.gold_evaluation import (
    HARD_GATES,
    REQUIRED_METRICS,
    ApproverAuthoritySnapshot,
    CompletenessMarkers,
    GeometryTruth,
    GoldAnnotationDocument,
    GoldManifestRequest,
    GoldRecordRequest,
    MetricContract,
    MetricDeclaration,
    PixelPoint,
    ReviewDecision,
    SymbolTruth,
    build_gold_manifest,
)

NOW = datetime(2026, 9, 11, 2, 0, tzinfo=UTC)
FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "floor_plan_interpretation_candidate_v1.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _authority(**changes) -> ApproverAuthoritySnapshot:
    val = dict(
        assignment_id=7,
        assignee_user_id=22,
        assigned_by_user_id=11,
        authority_scope="VED_AI_DATASET_APPROVER",
        active_from=NOW - timedelta(days=1),
        inactive_at=None,
        is_active=True,
    )
    val.update(changes)
    return ApproverAuthoritySnapshot(**val)


def _setup_gold_dataset(root: Path, *, split: str = "development_validation") -> tuple[Path, str]:
    source = root / "page_1.png"
    source.write_bytes(b"mock-page-pixels")
    source_hash = _sha(source)

    annotation = GoldAnnotationDocument(
        schema_version=1,
        source_id="page-1",
        source_sha256=source_hash,
        page_number=1,
        width_pixels=1000,
        height_pixels=800,
        sheet_type="electrical_plan",
        symbols=(
            SymbolTruth(symbol_id="symbol-0001", class_id=7, x_min=240.0, y_min=170.0, x_max=260.0, y_max=190.0),
        ),
        geometry=(
            GeometryTruth(
                entity_id="wall-0001",
                kind="wall",
                points=(PixelPoint(x=100.0, y=100.0), PixelPoint(x=700.0, y=100.0)),
            ),
            GeometryTruth(
                entity_id="room-0001",
                kind="room",
                points=(
                    PixelPoint(x=100.0, y=100.0),
                    PixelPoint(x=700.0, y=100.0),
                    PixelPoint(x=700.0, y=600.0),
                    PixelPoint(x=100.0, y=600.0),
                ),
            ),
            GeometryTruth(
                entity_id="opening-0001",
                kind="opening",
                points=(PixelPoint(x=300.0, y=100.0), PixelPoint(x=380.0, y=100.0)),
            ),
            GeometryTruth(
                entity_id="panel-0001",
                kind="panel",
                points=(PixelPoint(x=150.0, y=300.0), PixelPoint(x=150.0, y=300.0)),
            ),
        ),
        observed_wiring=(),
        text_dimensions=(),
        completeness=CompletenessMarkers(
            symbols="complete",
            geometry="complete",
            observed_wiring="not_applicable",
            text_dimensions="not_applicable",
        ),
    )
    annotation_path = root / "page_1.annotation.json"
    annotation_path.write_text(annotation.model_dump_json(), encoding="utf-8")
    annotation_hash = _sha(annotation_path)

    record = GoldRecordRequest(
        record_id="rec-dev-1",
        source_id="page-1",
        page_number=1,
        project_group_id="proj-a",
        drawing_set_id="set-a",
        split=split,
        permission_purpose="sealed_evaluation" if split == "sealed_test" else "development_evaluation",
        source_relative_path=source.name,
        source_sha256=source_hash,
        annotation_relative_path=annotation_path.name,
        annotation_sha256=annotation_hash,
        annotation_author_user_id=33,
        review=ReviewDecision(
            decision="approved",
            assignment_id=7,
            approver_user_id=22,
            decided_at=NOW,
            reviewed_annotation_sha256=annotation_hash,
        ),
    )

    manifest_path = root / "gold" / "v0001" / "manifest.json"
    manifest_req = GoldManifestRequest(
        dataset_id="ved-gold",
        revision=1,
        records=(record,),
    )
    result = build_gold_manifest(
        private_root=root,
        manifest_path=manifest_path,
        request=manifest_req,
        authorities=(_authority(),),
    )
    return result.manifest_path, result.manifest_sha256


def _contract() -> MetricContract:
    unsupported = {
        "wiring_topology_error", "wiring_length_error", "peak_vram_bytes",
    }
    declarations = tuple(
        MetricDeclaration(
            name=name,
            status="not_applicable",
            unit="not_applicable",
            reason="Unused in 2D layout evaluation.",
        )
        if name in unsupported
        else MetricDeclaration(
            name=name,
            status="threshold",
            direction="minimum" if "rate" in name or "precision" in name or "recall" in name or "f1" in name or "iou" in name or "accuracy" in name else "maximum",
            threshold=0.5 if "rate" in name or "f1" in name else 1000.0,
            unit="ratio" if "rate" in name or "f1" in name else "units",
        )
        for name in REQUIRED_METRICS
    )
    return MetricContract(
        contract_id="contract-u6",
        revision=1,
        authored_by_user_id=33,
        approved=False,
        declarations=declarations,
        hard_gates=HARD_GATES,
        box_iou_threshold=0.5,
    )


def _config(**changes) -> ModelEvaluationConfig:
    val = dict(
        model_id="qwen3-vl-4b",
        model_revision="v1.0.0",
        model_license="apache-2.0",
        weights_path=None,
        runtime="mock",
        execution_mode="gpu",
        max_tokens=2048,
        timeout_seconds=30.0,
        vram_budget_bytes=4 * 1024 * 1024 * 1024,
    )
    val.update(changes)
    return ModelEvaluationConfig(**val)


def test_offline_egress_guard_blocks_external_and_allows_loopback():
    with OfflineEgressGuard():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with pytest.raises(EgressSecurityViolation, match="EGRESS_SECURITY_VIOLATION"):
                s.connect(("8.8.8.8", 53))
            with pytest.raises(EgressSecurityViolation, match="EGRESS_SECURITY_VIOLATION"):
                s.connect(("api.openai.com", 443))
        finally:
            s.close()


def test_resource_tracker_measures_latency_and_memory():
    with ResourceTracker() as tracker:
        # Allocate some memory
        data = [i for i in range(50_000)]
        usage = tracker.measure()
        assert usage.latency_ms >= 0.0
        assert usage.peak_ram_bytes > 0
        assert usage.peak_vram_bytes >= 0


def test_model_evaluation_config_validation():
    cfg = _config()
    assert cfg.model_id == "qwen3-vl-4b"
    assert cfg.execution_mode == "gpu"

    with pytest.raises(ValidationError):
        _config(max_tokens=-1)
    with pytest.raises(ValidationError):
        _config(runtime="hosted_api")  # forbidden runtime


def test_mock_provider_lifecycle():
    provider = MockModelProviderAdapter()
    with pytest.raises(EvaluationHarnessError, match="MODEL_NOT_LOADED"):
        provider.predict(b"bytes", "prompt", ())
    assert provider.load(_config()) is True
    payload = provider.predict(b"bytes", "prompt", ())
    assert payload.schema_version == 1
    provider.unload()
    assert provider.loaded is False


def test_evaluation_harness_end_to_end_on_development_gold(tmp_path):
    manifest_path, manifest_sha = _setup_gold_dataset(tmp_path)
    contract = _contract()

    canned_payload = parse_candidate_payload_json(FIXTURE_PATH.read_bytes())

    harness = EvaluationHarness(
        private_root=tmp_path,
        manifest_path=manifest_path,
        manifest_sha256=manifest_sha,
        contract=contract,
    )
    provider = MockModelProviderAdapter(canned_payload=canned_payload)
    result = harness.run_evaluation(provider, _config())

    assert isinstance(result, ModelBakeOffResult)
    assert result.evaluated_records_count == 1
    assert result.schema_valid_rate == 1.0
    assert result.retry_rate == 0.0
    assert result.observations["symbol_precision"] == 1.0
    assert result.observations["symbol_recall"] == 1.0
    assert result.observations["wall_segment_match_rate"] == 1.0
    assert result.observations["room_polygon_iou"] == 1.0
    assert result.observations["opening_f1"] == 1.0
    assert result.observations["panel_f1"] == 1.0
    assert len(result.report_entries) == len(REQUIRED_METRICS)

    # Legacy YOLO comparison must honestly report unavailable
    assert result.legacy_yolo_comparison == {
        "status": "unavailable",
        "reason": "Legacy YOLO weights are not available in repository.",
    }


def test_evaluation_harness_egress_violation_aborts(tmp_path):
    manifest_path, manifest_sha = _setup_gold_dataset(tmp_path)
    contract = _contract()

    harness = EvaluationHarness(
        private_root=tmp_path,
        manifest_path=manifest_path,
        manifest_sha256=manifest_sha,
        contract=contract,
    )
    provider = MockModelProviderAdapter(should_fail_egress=True)
    with pytest.raises(EgressSecurityViolation, match="EGRESS_SECURITY_VIOLATION"):
        harness.run_evaluation(provider, _config())


def test_evaluation_harness_excludes_sealed_test_records(tmp_path):
    manifest_path, manifest_sha = _setup_gold_dataset(tmp_path, split="sealed_test")
    contract = _contract()

    harness = EvaluationHarness(
        private_root=tmp_path,
        manifest_path=manifest_path,
        manifest_sha256=manifest_sha,
        contract=contract,
    )
    provider = MockModelProviderAdapter()
    with pytest.raises(EvaluationHarnessError, match="NO_DEVELOPMENT_RECORDS"):
        harness.run_evaluation(provider, _config())


def test_evaluation_harness_handles_timeouts_and_retries(tmp_path):
    manifest_path, manifest_sha = _setup_gold_dataset(tmp_path)
    contract = _contract()

    harness = EvaluationHarness(
        private_root=tmp_path,
        manifest_path=manifest_path,
        manifest_sha256=manifest_sha,
        contract=contract,
    )
    timeout_provider = MockModelProviderAdapter(should_timeout=True)
    result = harness.run_evaluation(timeout_provider, _config())
    assert result.observations["timeout_rate"] == 1.0
    assert result.schema_valid_rate == 0.0
