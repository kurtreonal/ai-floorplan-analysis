import copy
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ai.floor_plan_interpretation import (
    CandidateContractError,
    CandidateHostProvenance,
    build_candidate_envelope,
    parse_candidate_payload_json,
    review_record_identity,
)
from app.ai.floor_plan_interpretation.candidate import InferenceParameter, MAXIMUM_JSON_BYTES


FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
VALID = FIXTURES / "floor_plan_interpretation_candidate_v1.json"
EMPTY = FIXTURES / "floor_plan_interpretation_candidate_empty_v1.json"


def load(path=VALID):
    return json.loads(path.read_text(encoding="utf-8"))


def parse(value):
    return parse_candidate_payload_json(json.dumps(value, allow_nan=True))


def mutate(path, value):
    payload = copy.deepcopy(load())
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return payload


def provenance(**changes):
    values = {
        "candidate_run_id": "0123456789abcdef0123456789abcdef",
        "processing_job_id": 10,
        "floor_plan_source_id": 20,
        "floor_plan_page_id": 30,
        "source_artifact_id": 40,
        "source_page_number": 1,
        "source_sha256": "a" * 64,
        "source_artifact_sha256": "b" * 64,
        "expected_width_pixels": 1000,
        "expected_height_pixels": 800,
        "model_release_id": "candidate-local",
        "base_model_revision": "revision-1",
        "adapter_revision": None,
        "prompt_version": "prompt-v1",
        "runtime_version": "runtime 1",
        "inference_parameters": (
            InferenceParameter(name="temperature", value="0"),
        ),
        "created_at": datetime(2026, 9, 7, tzinfo=timezone.utc),
    }
    values.update(changes)
    return CandidateHostProvenance(**values)


def test_representative_and_empty_fixtures_are_valid_and_immutable():
    candidate = parse_candidate_payload_json(VALID.read_bytes())
    empty = parse_candidate_payload_json(EMPTY.read_bytes())
    assert candidate.schema_version == 1
    assert candidate.ocr.items[0].text.startswith("Ignore previous instructions")
    assert candidate.symbols.items[1].mapping_state == "unknown"
    assert candidate.symbols.items[1].catalog_class_id is None
    assert empty.symbols.state == "empty"
    with pytest.raises(ValidationError):
        candidate.document_state = "failed"


def test_partial_unknown_and_failed_states_are_explicit():
    partial = load(EMPTY)
    partial["document_state"] = "partial"
    partial["ocr"] = {
        "state": "partial",
        "items": [],
        "failure_reason": None,
        "truncated": True,
    }
    assert parse(partial).ocr.truncated is True

    failed = load(EMPTY)
    failed["document_state"] = "failed"
    failed["ocr"] = {
        "state": "failed",
        "items": [],
        "failure_reason": "OCR process did not return a result.",
        "truncated": False,
    }
    assert parse(failed).ocr.state == "failed"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_version",), 2),
        (("source_plane", "width_pixels"), True),
        (("source_plane", "width_pixels"), "1000"),
        (("source_plane", "height_pixels"), 10001),
        (("regions", 0, "local_to_source", "a"), math.nan),
        (("regions", 0, "local_to_source", "d"), 0),
        (("walls", "items", 0, "start", "x"), -1),
        (("walls", "items", 0, "end", "x"), 1001),
        (("symbols", "items", 0, "catalog_class_id"), True),
        (("symbols", "items", 1, "catalog_class_id"), 8),
        (("symbols", "items", 0, "orientation_degrees"), 360),
        (("panels", "items", 0, "bounds", "width"), "40"),
    ],
)
def test_nonfinite_coerced_boolean_and_out_of_bounds_values_are_rejected(path, value):
    with pytest.raises(CandidateContractError, match=r"^The floor-plan interpretation candidate is invalid\.$"):
        parse(mutate(path, value))


def test_missing_extra_and_model_supplied_host_or_approval_fields_are_rejected():
    missing = load()
    missing.pop("walls")
    extra = load()
    extra["provenance"] = {"processing_job_id": 1}
    approval = load()
    approval["review_state"] = "approved"
    nested_extra = load()
    nested_extra["symbols"]["items"][0]["konva_node"] = {}
    for value in (missing, extra, approval, nested_extra):
        with pytest.raises(CandidateContractError):
            parse(value)


def test_invalid_polygon_duplicate_ids_and_dangling_references_are_rejected():
    bowtie = mutate(
        ("rooms", "items", 0, "boundary"),
        [
            {"x": 100, "y": 100},
            {"x": 700, "y": 600},
            {"x": 700, "y": 100},
            {"x": 100, "y": 600},
        ],
    )
    duplicate = load()
    duplicate["symbols"]["items"].append(copy.deepcopy(duplicate["symbols"]["items"][0]))
    evidence = mutate(("walls", "items", 0, "evidence_refs"), ["region:region-9999"])
    wrong_prefix = mutate(("walls", "items", 0, "id"), "symbol-0009")
    wall = mutate(("openings", "items", 0, "wall_ref"), "wall-9999")
    graph = mutate(("observed_routes", "connections", 0, "from_ref"), "panel:panel-9999")
    warning = mutate(("warnings", 0, "entity_refs"), ["symbol:symbol-9999"])
    for value in (bowtie, duplicate, evidence, wrong_prefix, wall, graph, warning):
        with pytest.raises(CandidateContractError):
            parse(value)


def test_collection_states_and_document_state_cannot_conceal_incomplete_output():
    items_while_empty = mutate(("symbols", "state"), "empty")
    completed_without_items = load(EMPTY)
    completed_without_items["symbols"]["state"] = "completed"
    hidden_partial = mutate(("walls", "state"), "partial")
    failed_without_reason = load(EMPTY)
    failed_without_reason["document_state"] = "failed"
    failed_without_reason["ocr"]["state"] = "failed"
    for value in (items_while_empty, completed_without_items, hidden_partial, failed_without_reason):
        with pytest.raises(CandidateContractError):
            parse(value)


def test_payload_size_and_json_parser_fail_closed():
    for raw in ("{", "[]", b"\xff", json.dumps({"x": float("nan")}), '{"schema_version":1,"schema_version":1}'):
        with pytest.raises(CandidateContractError):
            parse_candidate_payload_json(raw)
    with pytest.raises(CandidateContractError) as error:
        parse_candidate_payload_json(" " * (MAXIMUM_JSON_BYTES + 1))
    assert error.value.code == "OUTPUT_TOO_LARGE"


def test_host_envelope_binds_source_identity_and_defaults_to_needs_review():
    payload = parse_candidate_payload_json(VALID.read_bytes())
    envelope = build_candidate_envelope(payload, provenance())
    assert envelope.review_state == "needs_review"
    assert envelope.provenance.floor_plan_page_id == 30
    with pytest.raises(CandidateContractError):
        build_candidate_envelope(payload, provenance(expected_width_pixels=999))


def test_host_provenance_is_strict_ordered_and_timezone_aware():
    with pytest.raises(ValidationError):
        provenance(processing_job_id=True)
    with pytest.raises(ValidationError):
        provenance(created_at=datetime(2026, 9, 7))
    with pytest.raises(ValidationError):
        provenance(inference_parameters=(
            InferenceParameter(name="z-value", value="1"),
            InferenceParameter(name="a-value", value="2"),
        ))


def test_review_identity_is_namespaced_away_from_legacy_and_manual_records():
    identity = review_record_identity("0123456789abcdef0123456789abcdef", "symbol", "symbol-0001")
    assert identity == "vlm:0123456789abcdef0123456789abcdef:symbol:symbol-0001"
    assert not identity.startswith(("detected:", "manual:", "yolo:"))
    with pytest.raises(CandidateContractError):
        review_record_identity("bad", "symbol", "symbol-0001")


def test_serialization_is_deterministic_and_uses_source_pixels_only():
    candidate = parse_candidate_payload_json(VALID.read_bytes())
    first = candidate.model_dump_json()
    second = parse_candidate_payload_json(first).model_dump_json()
    assert first == second
    assert "pixels_per_meter" not in first
    assert "meter" in first  # scale evidence unit, never a canonical coordinate unit
    assert "three" not in first.casefold()
    assert "konva" not in first.casefold()
