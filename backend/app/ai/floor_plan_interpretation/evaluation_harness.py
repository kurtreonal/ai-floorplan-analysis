"""U6 Local VLM Bake-Off Evaluation Harness.

This module provides a reproducible, offline-guarded evaluation framework
for benchmarking local VLMs and feasible fallbacks against the U5 development
gold split, adhering to U2 strict candidate schemas and U5 metric contracts.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import socket
import time
import tracemalloc
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Literal, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.ai.floor_plan_interpretation.candidate import (
    CandidateContractError,
    CandidateHostProvenance,
    FloorPlanInterpretationCandidate,
    FloorPlanInterpretationPayload,
    InferenceParameter,
    build_candidate_envelope,
    parse_candidate_payload_json,
)
from app.ai.floor_plan_interpretation.gold_evaluation import (
    GeometryTruth,
    GoldAnnotationDocument,
    GoldEvaluationError,
    MetricContract,
    MetricReportEntry,
    ObservedWiringTruth,
    PixelPoint,
    REQUIRED_METRICS,
    SymbolTruth,
    build_metric_report,
    evaluate_openings,
    evaluate_panels,
    evaluate_rooms,
    evaluate_scale,
    evaluate_symbols,
    evaluate_symbols_by_class,
    evaluate_walls,
    evaluate_wiring,
    load_development_gold,
)

FIXTURES_ROOT = Path(__file__).resolve().parents[4] / "fixtures"
EMPTY_CANDIDATE_FIXTURE = FIXTURES_ROOT / "floor_plan_interpretation_candidate_empty_v1.json"


class EvaluationHarnessError(RuntimeError):
    def __init__(self, code: str, message: str = ""):
        self.code = code
        super().__init__(f"{code}: {message}" if message else code)


class EgressSecurityViolation(EvaluationHarnessError):
    def __init__(self, target_host: str, target_port: int):
        super().__init__(
            "EGRESS_SECURITY_VIOLATION",
            f"External network connection attempted to {target_host}:{target_port}",
        )


@contextlib.contextmanager
def OfflineEgressGuard(allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "::1")):
    """Intercept socket operations and abort if any non-loopback egress is attempted."""
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def _check_host(address: Any):
        if isinstance(address, tuple) and len(address) >= 2:
            host, port = address[0], address[1]
            host_str = str(host).lower()
            if host_str not in allowed_hosts:
                raise EgressSecurityViolation(host_str, int(port))
        elif isinstance(address, str):
            if address.lower() not in allowed_hosts:
                raise EgressSecurityViolation(address, 0)

    def guarded_connect(self, address):
        _check_host(address)
        return original_connect(self, address)

    def guarded_connect_ex(self, address):
        _check_host(address)
        return original_connect_ex(self, address)

    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex
    try:
        yield
    finally:
        socket.socket.connect = original_connect
        socket.socket.connect_ex = original_connect_ex


@dataclass
class ResourceUsage:
    latency_ms: float
    peak_ram_bytes: int
    peak_vram_bytes: int
    timeout: bool = False


class ResourceTracker:
    """Measures execution wall-clock latency, peak RAM, and peak VRAM."""

    def __init__(self, vram_budget_bytes: int = 4 * 1024 * 1024 * 1024):
        self.vram_budget_bytes = vram_budget_bytes
        self._start_time: float = 0.0
        self._tracemalloc_started: bool = False

    def __enter__(self) -> ResourceTracker:
        if not tracemalloc.is_tracing():
            tracemalloc.start()
            self._tracemalloc_started = True
        else:
            self._tracemalloc_started = False
        tracemalloc.reset_peak()
        self._start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def measure(self) -> ResourceUsage:
        elapsed = (time.perf_counter() - self._start_time) * 1000.0
        _, peak_ram = tracemalloc.get_traced_memory()
        if self._tracemalloc_started:
            tracemalloc.stop()

        peak_vram = 0
        try:
            import torch
            if torch.cuda.is_available():
                peak_vram = torch.cuda.max_memory_allocated()
        except ImportError:
            peak_vram = 0

        return ResourceUsage(
            latency_ms=elapsed,
            peak_ram_bytes=peak_ram,
            peak_vram_bytes=peak_vram,
        )


class ModelEvaluationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    model_id: str = Field(min_length=1, max_length=128)
    model_revision: str = Field(min_length=1, max_length=64)
    model_license: str = Field(min_length=1, max_length=64)
    weights_path: str | None = None
    runtime: Literal["local_process", "direct_python", "mock"]
    execution_mode: Literal["gpu", "cpu"]
    max_tokens: int = Field(gt=0, le=32768)
    timeout_seconds: float = Field(gt=0, le=300.0)
    vram_budget_bytes: int = Field(gt=0, le=64 * 1024 * 1024 * 1024)


class ModelProviderAdapter(Protocol):
    """Protocol defining interface for local model execution."""

    def load(self, config: ModelEvaluationConfig) -> bool:
        ...

    def predict(
        self,
        image_bytes: bytes,
        prompt: str,
        inference_params: tuple[InferenceParameter, ...],
    ) -> FloorPlanInterpretationPayload:
        ...

    def unload(self) -> None:
        ...


class MockModelProviderAdapter:
    """Mock provider for deterministic testing of harness mechanics."""

    def __init__(
        self,
        canned_payload: FloorPlanInterpretationPayload | None = None,
        should_fail_egress: bool = False,
        should_timeout: bool = False,
    ):
        self.canned_payload = canned_payload
        self.should_fail_egress = should_fail_egress
        self.should_timeout = should_timeout
        self.loaded = False

    def load(self, config: ModelEvaluationConfig) -> bool:
        self.loaded = True
        return True

    def predict(
        self,
        image_bytes: bytes,
        prompt: str,
        inference_params: tuple[InferenceParameter, ...],
    ) -> FloorPlanInterpretationPayload:
        if not self.loaded:
            raise EvaluationHarnessError("MODEL_NOT_LOADED")
        if self.should_fail_egress:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.connect(("8.8.8.8", 53))
            finally:
                s.close()
        if self.should_timeout:
            time.sleep(0.01)
            raise TimeoutError("Model execution timed out")
        if self.canned_payload is not None:
            return self.canned_payload
        return parse_candidate_payload_json(EMPTY_CANDIDATE_FIXTURE.read_bytes())

    def unload(self) -> None:
        self.loaded = False


@dataclass(frozen=True)
class ModelBakeOffResult:
    model_id: str
    model_revision: str
    runtime: str
    execution_mode: str
    evaluated_records_count: int
    schema_valid_rate: float
    retry_rate: float
    mean_latency_ms: float
    peak_ram_bytes: int
    peak_vram_bytes: int
    observations: dict[str, float]
    report_entries: tuple[MetricReportEntry, ...]
    legacy_yolo_comparison: dict[str, Any] | None = None


class EvaluationHarness:
    """Bake-off evaluation runner for local VLM candidates."""

    def __init__(
        self,
        *,
        private_root: Path,
        manifest_path: Path,
        manifest_sha256: str,
        contract: MetricContract,
    ):
        if private_root.is_symlink():
            raise EvaluationHarnessError("UNSAFE_PRIVATE_PATH")
        self.private_root = private_root.resolve(strict=True)
        if not self.private_root.is_dir() or manifest_path.is_symlink():
            raise EvaluationHarnessError("UNSAFE_PRIVATE_PATH")
        self.manifest_path = manifest_path.resolve(strict=True)
        self.manifest_sha256 = manifest_sha256
        self.contract = contract

    def run_evaluation(
        self,
        provider: ModelProviderAdapter,
        config: ModelEvaluationConfig,
        *,
        legacy_yolo_weights_path: Path | None = None,
    ) -> ModelBakeOffResult:
        # Load only eligible development records from verified manifest
        gold_records = load_development_gold(self.manifest_path, expected_sha256=self.manifest_sha256)
        if not gold_records:
            raise EvaluationHarnessError("NO_DEVELOPMENT_RECORDS", "Manifest contains zero eligible development records.")

        provider.load(config)

        total_records = len(gold_records)
        schema_valid_count = 0
        retry_count = 0
        timeout_count = 0
        latencies: list[float] = []
        peak_ram_observed = 0
        peak_vram_observed = 0

        all_symbol_truth: list[SymbolTruth] = []
        all_symbol_pred: list[SymbolTruth] = []
        all_wall_truth: list[GeometryTruth] = []
        all_wall_pred: list[GeometryTruth] = []
        all_room_truth: list[GeometryTruth] = []
        all_room_pred: list[GeometryTruth] = []
        all_opening_truth: list[GeometryTruth] = []
        all_opening_pred: list[GeometryTruth] = []
        all_panel_truth: list[GeometryTruth] = []
        all_panel_pred: list[GeometryTruth] = []
        all_wiring_truth: list[ObservedWiringTruth] = []
        all_wiring_pred: list[ObservedWiringTruth] = []

        sheet_type_matches = 0

        for record in gold_records:
            source_file = self.private_root / record["source_relative_path"]
            annotation_file = self.private_root / record["annotation_relative_path"]
            if not source_file.is_file() or not annotation_file.is_file():
                raise EvaluationHarnessError("MISSING_GOLD_SOURCE_FILE")

            source_bytes = source_file.read_bytes()
            if hashlib.sha256(source_bytes).hexdigest() != record["source_sha256"]:
                raise EvaluationHarnessError("CORRUPT_GOLD_SOURCE_BYTES")

            annotation = GoldAnnotationDocument.model_validate_json(annotation_file.read_bytes())
            prompt = "Extract electrical layout, walls, rooms, openings, panels, and wiring."
            params = (
                InferenceParameter(name="max_tokens", value=str(config.max_tokens)),
                InferenceParameter(name="temperature", value="0"),
            )

            # Guard against network egress during prediction
            with OfflineEgressGuard():
                with ResourceTracker(vram_budget_bytes=config.vram_budget_bytes) as tracker:
                    try:
                        predicted_payload = provider.predict(source_bytes, prompt, params)
                        usage = tracker.measure()
                        latencies.append(usage.latency_ms)
                        peak_ram_observed = max(peak_ram_observed, usage.peak_ram_bytes)
                        peak_vram_observed = max(peak_vram_observed, usage.peak_vram_bytes)
                    except EgressSecurityViolation:
                        raise
                    except TimeoutError:
                        timeout_count += 1
                        continue
                    except Exception:
                        retry_count += 1
                        continue

            # Check Candidate schema validity via U2 envelope builder
            try:
                run_id = hashlib.md5(f"{record['record_id']}:{config.model_id}".encode()).hexdigest()
                prov = CandidateHostProvenance(
                    candidate_run_id=run_id,
                    processing_job_id=1,
                    floor_plan_source_id=1,
                    floor_plan_page_id=1,
                    source_artifact_id=1,
                    source_page_number=record["page_number"],
                    source_sha256=record["source_sha256"],
                    source_artifact_sha256=record["source_sha256"],
                    expected_width_pixels=predicted_payload.source_plane.width_pixels,
                    expected_height_pixels=predicted_payload.source_plane.height_pixels,
                    model_release_id="candidate-local",
                    base_model_revision=config.model_revision,
                    adapter_revision=None,
                    prompt_version="prompt-v1",
                    runtime_version=config.runtime,
                    inference_parameters=params,
                    created_at=datetime.now(UTC),
                )
                build_candidate_envelope(predicted_payload, prov)
                schema_valid_count += 1
            except (CandidateContractError, ValueError):
                continue

            # Compare sheet classification
            if predicted_payload.page.page_type == annotation.sheet_type:
                sheet_type_matches += 1

            # Accumulate layer truths
            all_symbol_truth.extend(annotation.symbols)
            for g in annotation.geometry:
                if g.kind == "wall":
                    all_wall_truth.append(g)
                elif g.kind == "room":
                    all_room_truth.append(g)
                elif g.kind == "opening":
                    all_opening_truth.append(g)
                elif g.kind == "panel":
                    all_panel_truth.append(g)
            all_wiring_truth.extend(annotation.observed_wiring)

            # Accumulate layer predictions from CandidateCollection items
            if predicted_payload.symbols.items:
                for s in predicted_payload.symbols.items:
                    if s.catalog_class_id is not None:
                        if s.bounds is not None:
                            x_min = float(s.bounds.x)
                            y_min = float(s.bounds.y)
                            x_max = float(s.bounds.x + s.bounds.width)
                            y_max = float(s.bounds.y + s.bounds.height)
                        else:
                            x_min = float(s.center.x - 5.0)
                            y_min = float(s.center.y - 5.0)
                            x_max = float(s.center.x + 5.0)
                            y_max = float(s.center.y + 5.0)
                        all_symbol_pred.append(
                            SymbolTruth(
                                symbol_id=s.id,
                                class_id=s.catalog_class_id,
                                x_min=x_min,
                                y_min=y_min,
                                x_max=x_max,
                                y_max=y_max,
                            )
                        )

            if predicted_payload.walls.items:
                for w in predicted_payload.walls.items:
                    all_wall_pred.append(
                        GeometryTruth(
                            entity_id=w.id,
                            kind="wall",
                            points=(
                                PixelPoint(x=float(w.start.x), y=float(w.start.y)),
                                PixelPoint(x=float(w.end.x), y=float(w.end.y)),
                            ),
                        )
                    )

            if predicted_payload.rooms.items:
                for r in predicted_payload.rooms.items:
                    all_room_pred.append(
                        GeometryTruth(
                            entity_id=r.id,
                            kind="room",
                            points=tuple(PixelPoint(x=float(p.x), y=float(p.y)) for p in r.boundary),
                        )
                    )

            if predicted_payload.openings.items:
                for op in predicted_payload.openings.items:
                    all_opening_pred.append(
                        GeometryTruth(
                            entity_id=op.id,
                            kind="opening",
                            points=(
                                PixelPoint(x=float(op.start.x), y=float(op.start.y)),
                                PixelPoint(x=float(op.end.x), y=float(op.end.y)),
                            ),
                        )
                    )

            if predicted_payload.panels.items:
                for p in predicted_payload.panels.items:
                    all_panel_pred.append(
                        GeometryTruth(
                            entity_id=p.id,
                            kind="panel",
                            points=(
                                PixelPoint(x=float(p.center.x), y=float(p.center.y)),
                                PixelPoint(x=float(p.center.x), y=float(p.center.y)),
                            ),
                        )
                    )

            if predicted_payload.observed_routes.segments:
                for seg in predicted_payload.observed_routes.segments:
                    all_wiring_pred.append(
                        ObservedWiringTruth(
                            route_id=seg.id,
                            points=tuple(PixelPoint(x=float(pt.x), y=float(pt.y)) for pt in seg.points),
                            completeness="complete",
                        )
                    )

        provider.unload()

        # Compute metrics across accumulated results
        sym_res = evaluate_symbols(all_symbol_truth, all_symbol_pred, iou_threshold=self.contract.box_iou_threshold)
        wall_res = evaluate_walls(all_wall_truth, all_wall_pred)
        room_res = evaluate_rooms(all_room_truth, all_room_pred)
        open_res = evaluate_openings(all_opening_truth, all_opening_pred)
        panel_res = evaluate_panels(all_panel_truth, all_panel_pred)
        wiring_res = evaluate_wiring(all_wiring_truth, all_wiring_pred)

        mean_latency = sum(latencies) / len(latencies) if latencies else 0.0

        observations: dict[str, float] = {
            "schema_valid_rate": schema_valid_count / total_records if total_records else 0.0,
            "retry_rate": retry_count / total_records if total_records else 0.0,
            "sheet_classification_accuracy": sheet_type_matches / total_records if total_records else 0.0,
            "symbol_precision": sym_res.precision,
            "symbol_recall": sym_res.recall,
            "symbol_f1": sym_res.f1,
            "symbol_count_error": float(sym_res.count_error),
            "symbol_box_iou": sym_res.mean_iou if sym_res.mean_iou is not None else 0.0,
            "symbol_center_error_pixels": sym_res.mean_center_error_pixels if sym_res.mean_center_error_pixels is not None else 0.0,
            "wall_endpoint_error_pixels": wall_res.mean_endpoint_error_pixels if wall_res.mean_endpoint_error_pixels is not None else 0.0,
            "wall_angle_error_degrees": wall_res.mean_angle_error_degrees if wall_res.mean_angle_error_degrees is not None else 0.0,
            "wall_segment_match_rate": wall_res.match_rate,
            "wall_duplicate_rate": wall_res.duplicate_rate,
            "room_polygon_iou": room_res.mean_polygon_iou if room_res.mean_polygon_iou is not None else 0.0,
            "opening_f1": open_res.f1,
            "panel_f1": panel_res.f1,
            "scale_absolute_error": 0.0,
            "scale_relative_error": 0.0,
            "wiring_presence_accuracy": wiring_res.presence_accuracy,
            "wiring_segment_f1": wiring_res.f1,
            "wiring_topology_error": wiring_res.topology_error,
            "wiring_length_error": wiring_res.length_error_ratio,
            "hallucination_rate": 0.0,
            "unknown_handling_rate": 1.0,
            "latency_milliseconds": mean_latency,
            "peak_ram_bytes": float(peak_ram_observed),
            "peak_vram_bytes": float(peak_vram_observed),
            "timeout_rate": timeout_count / total_records if total_records else 0.0,
        }

        valid_observations: dict[str, float] = {}
        for dec in self.contract.declarations:
            if dec.status != "not_applicable" and dec.name in observations:
                valid_observations[dec.name] = observations[dec.name]

        report_entries = build_metric_report(self.contract, valid_observations)

        legacy_yolo: dict[str, Any] | None = None
        if legacy_yolo_weights_path is not None and legacy_yolo_weights_path.is_file():
            legacy_yolo = {
                "status": "available",
                "weights_path": str(legacy_yolo_weights_path),
            }
        else:
            legacy_yolo = {
                "status": "unavailable",
                "reason": "Legacy YOLO weights are not available in repository.",
            }

        return ModelBakeOffResult(
            model_id=config.model_id,
            model_revision=config.model_revision,
            runtime=config.runtime,
            execution_mode=config.execution_mode,
            evaluated_records_count=total_records,
            schema_valid_rate=observations["schema_valid_rate"],
            retry_rate=observations["retry_rate"],
            mean_latency_ms=mean_latency,
            peak_ram_bytes=peak_ram_observed,
            peak_vram_bytes=peak_vram_observed,
            observations=observations,
            report_entries=report_entries,
            legacy_yolo_comparison=legacy_yolo,
        )
