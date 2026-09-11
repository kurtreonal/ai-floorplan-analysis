"""Private U5 gold-set bootstrap and deterministic metric contracts.

This module is deliberately offline: it reads only caller-selected files below a
private root and receives authority snapshots from the database-facing CLI.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

HASH = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
MAX_FILE_BYTES = 25 * 1024 * 1024

REQUIRED_METRICS = (
    "schema_valid_rate", "retry_rate", "sheet_classification_accuracy",
    "symbol_precision", "symbol_recall", "symbol_f1", "symbol_count_error",
    "symbol_box_iou", "symbol_center_error_pixels", "wall_endpoint_error_pixels",
    "wall_angle_error_degrees", "wall_segment_match_rate", "wall_duplicate_rate",
    "room_polygon_iou", "opening_f1", "panel_f1", "scale_absolute_error",
    "scale_relative_error", "wiring_presence_accuracy", "wiring_segment_f1",
    "wiring_topology_error", "wiring_length_error", "hallucination_rate",
    "unknown_handling_rate", "latency_milliseconds", "peak_ram_bytes",
    "peak_vram_bytes", "timeout_rate",
)
HARD_GATES = (
    "candidate_schema_validity", "bounded_geometry", "review_before_canonical",
    "original_bytes_unchanged", "private_egress_zero", "project_split_leakage_zero",
    "release_manifest_complete",
)


class GoldEvaluationError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _fail(code: str):
    raise GoldEvaluationError(code)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class PixelPoint(StrictModel):
    x: float = Field(ge=0, le=10_000)
    y: float = Field(ge=0, le=10_000)

    @model_validator(mode="after")
    def finite(self):
        if not math.isfinite(self.x) or not math.isfinite(self.y):
            raise ValueError("Coordinates must be finite.")
        return self


class SymbolTruth(StrictModel):
    symbol_id: str
    class_id: int = Field(ge=0, le=2_147_483_647)
    x_min: float = Field(ge=0, le=10_000)
    y_min: float = Field(ge=0, le=10_000)
    x_max: float = Field(gt=0, le=10_000)
    y_max: float = Field(gt=0, le=10_000)

    @model_validator(mode="after")
    def valid(self):
        if not SAFE_ID.fullmatch(self.symbol_id) or self.x_min >= self.x_max or self.y_min >= self.y_max:
            raise ValueError("Invalid symbol truth.")
        if not all(math.isfinite(v) for v in (self.x_min, self.y_min, self.x_max, self.y_max)):
            raise ValueError("Symbol bounds must be finite.")
        return self


class GeometryTruth(StrictModel):
    entity_id: str
    kind: Literal["wall", "room", "opening", "panel"]
    points: tuple[PixelPoint, ...] = Field(min_length=2, max_length=1_000)

    @model_validator(mode="after")
    def valid(self):
        if not SAFE_ID.fullmatch(self.entity_id) or (self.kind == "room" and len(self.points) < 3):
            raise ValueError("Invalid geometry truth.")
        return self


class ObservedWiringTruth(StrictModel):
    route_id: str
    points: tuple[PixelPoint, ...] = Field(min_length=2, max_length=2_000)
    completeness: Literal["complete", "partial", "unreadable"]

    @model_validator(mode="after")
    def valid(self):
        if not SAFE_ID.fullmatch(self.route_id):
            raise ValueError("Invalid route identity.")
        return self


class TextDimensionTruth(StrictModel):
    evidence_id: str
    text: str = Field(min_length=1, max_length=1_000)
    region: tuple[PixelPoint, PixelPoint]

    @model_validator(mode="after")
    def valid(self):
        if not SAFE_ID.fullmatch(self.evidence_id) or "\x00" in self.text:
            raise ValueError("Invalid text evidence.")
        return self


class CompletenessMarkers(StrictModel):
    symbols: Literal["complete", "pending", "not_applicable"]
    geometry: Literal["complete", "pending", "not_applicable"]
    observed_wiring: Literal["complete", "pending", "not_applicable"]
    text_dimensions: Literal["complete", "pending", "not_applicable"]

    @property
    def complete(self) -> bool:
        return "pending" not in (self.symbols, self.geometry, self.observed_wiring, self.text_dimensions)


class GoldAnnotationDocument(StrictModel):
    schema_version: Literal[1]
    source_id: str
    source_sha256: str
    page_number: int = Field(gt=0, le=10_000)
    width_pixels: int = Field(gt=0, le=10_000)
    height_pixels: int = Field(gt=0, le=10_000)
    sheet_type: Literal["electrical_plan", "legend", "schedule", "other", "unknown"]
    symbols: tuple[SymbolTruth, ...] = Field(default=(), max_length=10_000)
    geometry: tuple[GeometryTruth, ...] = Field(default=(), max_length=10_000)
    observed_wiring: tuple[ObservedWiringTruth, ...] = Field(default=(), max_length=10_000)
    text_dimensions: tuple[TextDimensionTruth, ...] = Field(default=(), max_length=10_000)
    completeness: CompletenessMarkers

    @model_validator(mode="after")
    def valid(self):
        if not SAFE_ID.fullmatch(self.source_id) or not HASH.fullmatch(self.source_sha256):
            raise ValueError("Invalid annotation source identity.")
        ids = [x.symbol_id for x in self.symbols]
        ids += [x.entity_id for x in self.geometry] + [x.route_id for x in self.observed_wiring]
        ids += [x.evidence_id for x in self.text_dimensions]
        if len(ids) != len(set(ids)):
            raise ValueError("Annotation identities must be unique across layers.")
        points = [point for item in self.geometry for point in item.points]
        points += [point for item in self.observed_wiring for point in item.points]
        points += [point for item in self.text_dimensions for point in item.region]
        if any(p.x > self.width_pixels or p.y > self.height_pixels for p in points):
            raise ValueError("Annotation geometry is outside the page frame.")
        if any(x.x_max > self.width_pixels or x.y_max > self.height_pixels for x in self.symbols):
            raise ValueError("Symbol truth is outside the page frame.")
        return self


class ReviewDecision(StrictModel):
    decision: Literal["approved", "rejected"]
    assignment_id: int = Field(gt=0)
    approver_user_id: int = Field(gt=0)
    decided_at: datetime
    reviewed_annotation_sha256: str

    @model_validator(mode="after")
    def valid(self):
        if self.decided_at.tzinfo is None or self.decided_at.utcoffset() is None or not HASH.fullmatch(self.reviewed_annotation_sha256):
            raise ValueError("Invalid review decision.")
        return self


class GoldRecordRequest(StrictModel):
    record_id: str
    source_id: str
    page_number: int = Field(gt=0, le=10_000)
    project_group_id: str
    drawing_set_id: str
    split: Literal["development_validation", "sealed_test"]
    permission_purpose: Literal["development_evaluation", "sealed_evaluation"]
    source_relative_path: str = Field(min_length=1, max_length=512)
    source_sha256: str
    annotation_relative_path: str = Field(min_length=1, max_length=512)
    annotation_sha256: str
    annotation_author_user_id: int = Field(gt=0)
    review: ReviewDecision | None = None

    @model_validator(mode="after")
    def valid(self):
        if any(not SAFE_ID.fullmatch(v) for v in (self.record_id, self.source_id, self.project_group_id, self.drawing_set_id)):
            raise ValueError("Invalid gold record identity.")
        if not HASH.fullmatch(self.source_sha256) or not HASH.fullmatch(self.annotation_sha256):
            raise ValueError("Invalid gold record hash.")
        for raw in (self.source_relative_path, self.annotation_relative_path):
            path = Path(raw)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Gold paths must be private-root relative.")
        expected = "sealed_evaluation" if self.split == "sealed_test" else "development_evaluation"
        if self.permission_purpose != expected:
            raise ValueError("Permission purpose does not match split.")
        return self


class ApproverAuthoritySnapshot(StrictModel):
    assignment_id: int = Field(gt=0)
    assignee_user_id: int = Field(gt=0)
    assigned_by_user_id: int = Field(gt=0)
    authority_scope: Literal["VED_AI_DATASET_APPROVER"]
    active_from: datetime
    inactive_at: datetime | None = None
    is_active: bool


class GoldManifestRequest(StrictModel):
    dataset_id: str
    revision: int = Field(gt=0)
    parent_manifest_relative_path: str | None = Field(default=None, max_length=512)
    parent_manifest_sha256: str | None = None
    records: tuple[GoldRecordRequest, ...] = Field(min_length=1, max_length=100_000)

    @model_validator(mode="after")
    def valid(self):
        if not SAFE_ID.fullmatch(self.dataset_id):
            raise ValueError("Invalid dataset identity.")
        if self.revision == 1 and (self.parent_manifest_relative_path or self.parent_manifest_sha256):
            raise ValueError("Initial revision cannot have a parent.")
        if self.revision > 1 and (not self.parent_manifest_relative_path or not self.parent_manifest_sha256 or not HASH.fullmatch(self.parent_manifest_sha256)):
            raise ValueError("Later revisions require a hashed parent.")
        return self


class MetricDeclaration(StrictModel):
    name: str
    status: Literal["threshold", "not_applicable"]
    direction: Literal["minimum", "maximum"] | None = None
    threshold: float | None = None
    unit: str = Field(min_length=1, max_length=64)
    reason: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def valid(self):
        if self.name not in REQUIRED_METRICS:
            raise ValueError("Unknown evaluation metric.")
        if self.status == "threshold":
            if self.direction is None or self.threshold is None or not math.isfinite(self.threshold) or self.reason is not None:
                raise ValueError("Threshold metrics require a finite threshold and direction.")
        elif self.direction is not None or self.threshold is not None or self.reason is None:
            raise ValueError("N/A metrics require only a reason.")
        return self


class MetricContract(StrictModel):
    contract_id: str
    revision: int = Field(gt=0)
    authored_by_user_id: int = Field(gt=0)
    approved: bool
    approved_by_assignment_id: int | None = Field(default=None, gt=0)
    approved_by_user_id: int | None = Field(default=None, gt=0)
    approved_at: datetime | None = None
    declarations: tuple[MetricDeclaration, ...]
    hard_gates: tuple[str, ...]
    box_iou_threshold: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def valid(self):
        if not SAFE_ID.fullmatch(self.contract_id):
            raise ValueError("Invalid metric contract identity.")
        names = tuple(x.name for x in self.declarations)
        if set(names) != set(REQUIRED_METRICS) or len(names) != len(set(names)):
            raise ValueError("Metric contract must declare every required metric exactly once.")
        if tuple(sorted(self.hard_gates)) != tuple(sorted(HARD_GATES)):
            raise ValueError("Metric contract must preserve every hard safety gate.")
        approval = (self.approved_by_assignment_id, self.approved_by_user_id, self.approved_at)
        if self.approved != all(value is not None for value in approval) or (not self.approved and any(value is not None for value in approval)):
            raise ValueError("Metric approval provenance is incomplete or unexpected.")
        if self.approved_at is not None and (self.approved_at.tzinfo is None or self.approved_at.utcoffset() is None):
            raise ValueError("Metric approval time must include a timezone.")
        return self


@dataclass(frozen=True)
class GoldManifestResult:
    manifest_path: Path
    manifest_sha256: str
    record_count: int
    eligible_development_count: int
    eligible_sealed_count: int
    changed: bool


@dataclass(frozen=True)
class SymbolMetricResult:
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float
    f1: float
    count_error: int
    mean_iou: float | None
    mean_center_error_pixels: float | None


@dataclass(frozen=True)
class MetricReportEntry:
    name: str
    status: Literal["measured", "not_applicable", "pending"]
    value: float | None
    unit: str
    reason: str | None


def _private_file(root: Path, relative: str) -> Path:
    candidate = root / relative
    if candidate.is_symlink():
        _fail("UNSAFE_PRIVATE_PATH")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError):
        _fail("UNSAFE_PRIVATE_PATH")
    if not resolved.is_file() or resolved.stat().st_size > MAX_FILE_BYTES:
        _fail("UNSAFE_PRIVATE_PATH")
    return resolved


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _authority_at(*, assignment_id: int, approver_user_id: int, decided_at: datetime, author_id: int, snapshots: dict[int, ApproverAuthoritySnapshot]):
    assignment = snapshots.get(assignment_id)
    if assignment is None or not assignment.is_active or assignment.inactive_at is not None or assignment.authority_scope != "VED_AI_DATASET_APPROVER" or assignment.assignee_user_id != approver_user_id or assignment.assigned_by_user_id == approver_user_id or author_id == approver_user_id:
        _fail("INVALID_REVIEW_AUTHORITY")
    active_from = assignment.active_from
    if active_from.tzinfo is None:
        active_from = active_from.replace(tzinfo=UTC)
    if decided_at < active_from:
        _fail("INVALID_REVIEW_AUTHORITY")


def _authority(decision: ReviewDecision, author_id: int, snapshots: dict[int, ApproverAuthoritySnapshot]):
    _authority_at(assignment_id=decision.assignment_id, approver_user_id=decision.approver_user_id, decided_at=decision.decided_at, author_id=author_id, snapshots=snapshots)


def validate_metric_contract_authority(contract: MetricContract, authorities: Sequence[ApproverAuthoritySnapshot]) -> None:
    if not contract.approved:
        return
    snapshots = {item.assignment_id: item for item in authorities}
    if len(snapshots) != len(authorities):
        _fail("DUPLICATE_AUTHORITY")
    _authority_at(assignment_id=contract.approved_by_assignment_id, approver_user_id=contract.approved_by_user_id, decided_at=contract.approved_at, author_id=contract.authored_by_user_id, snapshots=snapshots)


def build_gold_manifest(*, private_root: Path, manifest_path: Path, request: GoldManifestRequest, authorities: Sequence[ApproverAuthoritySnapshot]) -> GoldManifestResult:
    if private_root.is_symlink():
        _fail("INVALID_PRIVATE_ROOT")
    root = private_root.resolve(strict=True)
    if not root.is_dir() or manifest_path.is_symlink():
        _fail("INVALID_PRIVATE_ROOT")
    destination = manifest_path.resolve(strict=False)
    try:
        destination.relative_to(root)
    except ValueError:
        _fail("MANIFEST_OUTSIDE_PRIVATE_ROOT")
    authority_by_id = {item.assignment_id: item for item in authorities}
    if len(authority_by_id) != len(authorities):
        _fail("DUPLICATE_AUTHORITY")
    seen: set[str] = set(); group_splits: dict[str, str] = {}; stored = []
    for record in request.records:
        if record.record_id in seen:
            _fail("DUPLICATE_GOLD_RECORD")
        seen.add(record.record_id)
        prior_split = group_splits.setdefault(record.project_group_id, record.split)
        if prior_split != record.split:
            _fail("PROJECT_SPLIT_LEAKAGE")
        source = _private_file(root, record.source_relative_path)
        annotation_path = _private_file(root, record.annotation_relative_path)
        if _file_hash(source) != record.source_sha256 or _file_hash(annotation_path) != record.annotation_sha256:
            _fail("GOLD_HASH_MISMATCH")
        try:
            annotation = GoldAnnotationDocument.model_validate_json(annotation_path.read_bytes())
        except (UnicodeDecodeError, ValueError):
            _fail("INVALID_GOLD_ANNOTATION")
        if annotation.source_id != record.source_id or annotation.page_number != record.page_number or annotation.source_sha256 != record.source_sha256:
            _fail("GOLD_SOURCE_MISMATCH")
        eligible = False
        if record.review is not None:
            if record.review.reviewed_annotation_sha256 != record.annotation_sha256:
                _fail("STALE_GOLD_REVIEW")
            _authority(record.review, record.annotation_author_user_id, authority_by_id)
            eligible = record.review.decision == "approved" and annotation.completeness.complete
        item = record.model_dump(mode="json")
        item["eligible"] = eligible
        item["annotation_summary"] = {"page_number": annotation.page_number, "sheet_type": annotation.sheet_type, "symbols": len(annotation.symbols), "geometry": len(annotation.geometry), "observed_wiring": len(annotation.observed_wiring), "text_dimensions": len(annotation.text_dimensions), "complete": annotation.completeness.complete}
        stored.append(item)
    if request.revision > 1:
        parent = _private_file(root, request.parent_manifest_relative_path)
        if _file_hash(parent) != request.parent_manifest_sha256:
            _fail("PARENT_MANIFEST_HASH_MISMATCH")
        try:
            previous = json.loads(parent.read_bytes()); previous_records = previous["records"]
            if previous.get("dataset_id") != request.dataset_id or previous.get("revision") != request.revision - 1 or not isinstance(previous_records, list):
                raise TypeError
            previous_by_id = {item["record_id"]: item for item in previous_records}
            previous_splits = {item["project_group_id"]: item["split"] for item in previous_records}
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
            _fail("INVALID_PARENT_MANIFEST")
        if len(previous_by_id) != len(previous_records):
            _fail("INVALID_PARENT_MANIFEST")
        if any(previous_splits.get(group) not in (None, split) for group, split in group_splits.items()):
            _fail("FROZEN_SPLIT_CHANGED")
        current_by_id = {item["record_id"]: item for item in stored}
        immutable = ("source_id", "page_number", "project_group_id", "drawing_set_id", "split", "permission_purpose", "source_relative_path", "source_sha256")
        for record_id, prior in previous_by_id.items():
            current = current_by_id.get(record_id)
            if current is None:
                _fail("FROZEN_MEMBERSHIP_REMOVED")
            if any(current.get(field) != prior.get(field) for field in immutable):
                _fail("FROZEN_MEMBERSHIP_CHANGED")
    payload = request.model_dump(mode="json"); payload["schema_version"] = 1; payload["records"] = sorted(stored, key=lambda x: x["record_id"])
    raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    digest = hashlib.sha256(raw).hexdigest()
    if destination.exists():
        if destination.stat().st_size > MAX_FILE_BYTES or destination.read_bytes() != raw:
            _fail("IMMUTABLE_GOLD_REVISION")
        changed = False
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
        try:
            with temporary.open("xb") as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink()
        changed = True
    return GoldManifestResult(destination, digest, len(stored), sum(x["eligible"] and x["split"] == "development_validation" for x in stored), sum(x["eligible"] and x["split"] == "sealed_test" for x in stored), changed)


def load_development_gold(manifest_path: Path, *, expected_sha256: str) -> tuple[dict, ...]:
    if manifest_path.is_symlink() or not manifest_path.is_file() or manifest_path.stat().st_size > MAX_FILE_BYTES or not HASH.fullmatch(expected_sha256):
        _fail("INVALID_GOLD_MANIFEST")
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        _fail("INVALID_GOLD_MANIFEST")
    try:
        payload = json.loads(raw); records = payload["records"]
        if payload.get("schema_version") != 1 or not isinstance(records, list):
            raise TypeError
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
        _fail("INVALID_GOLD_MANIFEST")
    return tuple(item for item in records if item.get("eligible") is True and item.get("split") == "development_validation")


def _iou(left: SymbolTruth, right: SymbolTruth) -> float:
    width = max(0.0, min(left.x_max, right.x_max) - max(left.x_min, right.x_min)); height = max(0.0, min(left.y_max, right.y_max) - max(left.y_min, right.y_min))
    intersection = width * height; union = (left.x_max-left.x_min)*(left.y_max-left.y_min) + (right.x_max-right.x_min)*(right.y_max-right.y_min) - intersection
    return intersection / union if union else 0.0


def evaluate_symbols(truth: Sequence[SymbolTruth], predictions: Sequence[SymbolTruth], *, iou_threshold: float) -> SymbolMetricResult:
    if not 0 < iou_threshold <= 1:
        _fail("INVALID_IOU_THRESHOLD")
    candidates = sorted(((-_iou(a, b), a.symbol_id, b.symbol_id, a, b) for a in truth for b in predictions if a.class_id == b.class_id and _iou(a, b) >= iou_threshold), key=lambda x: x[:3])
    matched_truth: set[str] = set(); matched_predictions: set[str] = set(); overlaps = []; center_errors = []
    for negative_iou, _, _, expected, predicted in candidates:
        if expected.symbol_id in matched_truth or predicted.symbol_id in matched_predictions:
            continue
        matched_truth.add(expected.symbol_id); matched_predictions.add(predicted.symbol_id); overlaps.append(-negative_iou)
        center_errors.append(math.dist(((expected.x_min+expected.x_max)/2, (expected.y_min+expected.y_max)/2), ((predicted.x_min+predicted.x_max)/2, (predicted.y_min+predicted.y_max)/2)))
    tp = len(matched_truth); fp = len(predictions)-tp; fn = len(truth)-tp; precision = tp/(tp+fp) if tp+fp else 1.0; recall = tp/(tp+fn) if tp+fn else 1.0; f1 = 2*precision*recall/(precision+recall) if precision+recall else 0.0
    return SymbolMetricResult(tp, fp, fn, precision, recall, f1, len(predictions)-len(truth), sum(overlaps)/len(overlaps) if overlaps else None, sum(center_errors)/len(center_errors) if center_errors else None)


def evaluate_symbols_by_class(truth: Sequence[SymbolTruth], predictions: Sequence[SymbolTruth], *, iou_threshold: float) -> dict[int, SymbolMetricResult]:
    classes = sorted({x.class_id for x in truth} | {x.class_id for x in predictions})
    return {class_id: evaluate_symbols(tuple(x for x in truth if x.class_id == class_id), tuple(x for x in predictions if x.class_id == class_id), iou_threshold=iou_threshold) for class_id in classes}


def build_metric_report(contract: MetricContract, observations: dict[str, float]) -> tuple[MetricReportEntry, ...]:
    if set(observations) - set(REQUIRED_METRICS):
        _fail("UNKNOWN_METRIC_OBSERVATION")
    report = []
    for declaration in contract.declarations:
        if declaration.status == "not_applicable":
            if declaration.name in observations:
                _fail("UNSUPPORTED_METRIC_OBSERVED")
            report.append(MetricReportEntry(declaration.name, "not_applicable", None, declaration.unit, declaration.reason)); continue
        value = observations.get(declaration.name)
        if value is not None and not math.isfinite(value):
            _fail("INVALID_METRIC_OBSERVATION")
        report.append(MetricReportEntry(declaration.name, "measured" if value is not None else "pending", value, declaration.unit, None if value is not None else "Evaluation evidence is not available."))
    return tuple(report)
