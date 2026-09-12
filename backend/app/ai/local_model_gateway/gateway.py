"""Isolated schema-constrained local VLM gateway implementation.

Implements TICKET U8:
- Pinned, lazy, cached, local-only model loading.
- Bounded concurrency, timeout, and retry limits.
- Offline egress enforcement during inference.
- Strict Pydantic candidate schema validation (invalid text never bypasses validation).
- Sanitized error reporting with private diagnostic traceability.
"""

from __future__ import annotations

import concurrent.futures
import json
import threading
from pathlib import Path
from typing import Any, Protocol, Sequence

import numpy as np

from app.ai.floor_plan_interpretation.candidate import (
    CandidateContractError,
    CandidateHostProvenance,
    FloorPlanInterpretationCandidate,
    FloorPlanInterpretationPayload,
    build_candidate_envelope,
    parse_candidate_payload_json,
)
from app.ai.floor_plan_interpretation.evaluation_harness import (
    EgressSecurityViolation,
    OfflineEgressGuard,
    ResourceTracker,
    ResourceUsage,
)
from app.ai.floor_plan_interpretation.preparation import PreparedContext
from app.ai.floor_plan_interpretation.observed_wiring import prepare_observed_wiring_evidence
from app.ai.local_model_gateway.config import (
    GatewayHealth,
    GatewayInferenceRequest,
    GatewayInferenceResult,
    LocalGatewayConfig,
)
from app.ai.local_model_gateway.diagnostics import (
    ConcurrencyLimitError,
    DiagnosticsStore,
    EgressViolationError,
    GatewayError,
    GatewayTimeoutError,
    ModelExecutionError,
    ModelNotReadyError,
    SchemaValidationError,
)


class LocalVLMRuntimeAdapter(Protocol):
    """Protocol defining the interface for process-isolated local model backends."""

    def load(self) -> None:
        """Initialize and cache the model in local memory."""
        ...

    def predict(
        self,
        prompt: str,
        images: Sequence[np.ndarray],
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        """Execute local inference and return the generated text output."""
        ...

    def unload(self) -> None:
        """Release cached model weights and VRAM."""
        ...

    def is_ready(self) -> bool:
        """Return True if model is initialized and healthy."""
        ...


class MockLocalVLMAdapter:
    """Deterministic mock adapter for testing gateway behaviors without live hardware."""

    def __init__(
        self,
        *,
        fixed_payload: dict[str, Any] | None = None,
        simulate_error: Exception | None = None,
        simulate_raw_text: str | None = None,
        simulate_hang: bool = False,
    ) -> None:
        self._loaded = False
        self._fixed_payload = fixed_payload
        self._simulate_error = simulate_error
        self._simulate_raw_text = simulate_raw_text
        self._simulate_hang = simulate_hang

    def load(self) -> None:
        self._loaded = True

    def is_ready(self) -> bool:
        return self._loaded

    def unload(self) -> None:
        self._loaded = False

    def predict(
        self,
        prompt: str,
        images: Sequence[np.ndarray],
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        if not self._loaded:
            raise RuntimeError("Model runtime is not loaded.")
        if self._simulate_hang:
            import time
            time.sleep(10.0)
        if self._simulate_error:
            raise self._simulate_error
        if self._simulate_raw_text is not None:
            return self._simulate_raw_text
        if self._fixed_payload is not None:
            return json.dumps(self._fixed_payload)

        # Default to standard validated candidate fixture
        fixtures_path = Path(__file__).resolve().parents[4] / "fixtures" / "floor_plan_interpretation_candidate_v1.json"
        if fixtures_path.is_file():
            return fixtures_path.read_text(encoding="utf-8")

        fallback_payload = {
            "schema_version": 1,
            "document_state": "completed",
            "source_plane": {
                "coordinate_space": "source_pixel_top_left",
                "width_pixels": 1000,
                "height_pixels": 800,
            },
            "page": {
                "page_type": "electrical_plan",
                "quality": "supported",
                "signals": {
                    "electrical_content": "visible",
                    "legend": "not_visible",
                    "dimensions": "not_visible",
                    "scale_evidence": "not_visible",
                    "observed_wiring": "not_visible",
                },
                "quality_issues": [],
            },
            "regions": [
                {
                    "id": "region-0001",
                    "kind": "overview",
                    "bounds": {"x": 0.0, "y": 0.0, "width": 1000.0, "height": 800.0},
                    "local_to_source": {"a": 1.0, "b": 0.0, "c": 0.0, "d": 1.0, "e": 0.0, "f": 0.0},
                }
            ],
            "ocr": {"state": "unavailable", "items": [], "truncated": False},
            "scales": {"state": "unavailable", "items": [], "truncated": False},
            "walls": {"state": "unavailable", "items": [], "truncated": False},
            "rooms": {"state": "unavailable", "items": [], "truncated": False},
            "openings": {"state": "unavailable", "items": [], "truncated": False},
            "symbols": {"state": "unavailable", "items": [], "truncated": False},
            "panels": {"state": "unavailable", "items": [], "truncated": False},
            "observed_routes": {"state": "unavailable", "segments": [], "connections": []},
            "warnings": [],
        }
        return json.dumps(fallback_payload)


class LocalModelGateway:
    """Schema-constrained local VLM gateway."""

    def __init__(
        self,
        config: LocalGatewayConfig,
        runtime_adapter: LocalVLMRuntimeAdapter,
        *,
        diagnostics_store: DiagnosticsStore | None = None,
    ) -> None:
        self.config = config
        self.runtime_adapter = runtime_adapter
        self.diagnostics_store = (
            diagnostics_store or DiagnosticsStore(config.diagnostics_directory)
        )
        self._semaphore = threading.BoundedSemaphore(config.max_concurrency)
        self._active_requests = 0
        self._lock = threading.Lock()

    def warmup(self) -> None:
        """Pre-load the model into memory if not already active."""
        with self._lock:
            if not self.runtime_adapter.is_ready():
                self.runtime_adapter.load()

    def shutdown(self) -> None:
        """Unload model weights and release compute resources."""
        with self._lock:
            if self.runtime_adapter.is_ready():
                self.runtime_adapter.unload()

    def health_check(self) -> GatewayHealth:
        """Query readiness and runtime status."""
        is_ready = self.runtime_adapter.is_ready()
        return GatewayHealth(
            status="ready" if is_ready else "unavailable",
            model_name=self.config.model_name,
            model_revision=self.config.model_revision,
            local_runtime_url=self.config.runtime_url,
            vram_budget_mb=self.config.vram_budget_mb,
            loaded_in_memory=is_ready,
            active_requests=self._active_requests,
            diagnostics_path=str(self.config.diagnostics_directory),
            message="Gateway is ready for local inference." if is_ready else "Model is not loaded in memory.",
        )

    def submit_inference(
        self,
        request: GatewayInferenceRequest,
        prepared_context: PreparedContext,
    ) -> GatewayInferenceResult:
        """Execute local model inference within safety, resource, and schema boundaries."""
        # Ensure model is ready (lazy load)
        if not self.runtime_adapter.is_ready():
            self.warmup()

        # Bounded concurrency guard
        acquired = self._semaphore.acquire(blocking=False)
        if not acquired:
            raise ConcurrencyLimitError(
                "GATEWAY_CONCURRENCY_EXCEEDED",
                f"Active requests exceed concurrency budget ({self.config.max_concurrency}).",
            )

        with self._lock:
            self._active_requests += 1

        raw_output: str | None = None
        diag_id: str | None = None

        with ResourceTracker() as tracker:
            try:
                wiring_evidence = prepare_observed_wiring_evidence(prepared_context)
                effective_prompt = (
                    request.prompt
                    + "\nAuxiliary thin-line evidence in source pixels (not electrical truth):\n"
                    + wiring_evidence.model_dump_json()
                    + "\nThese fragments may be walls, text or wiring. Verify against pixels. "
                    "Do not infer connections from crossings, proximity or dash alignment. "
                    "No fragments does not prove no wiring. Preserve unresolved evidence; "
                    "only visibly drawn wiring belongs in observed_routes."
                )
                # Collect images for multimodal model
                images: list[np.ndarray] = [prepared_context.overview.image_rgb]
                for tile in prepared_context.tiles:
                    images.append(tile.image_rgb)

                # Enforce offline network egress guard
                with OfflineEgressGuard():
                    # Bounded execution with timeout
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(
                            self.runtime_adapter.predict,
                            effective_prompt,
                            images,
                            temperature=request.decoding_temperature,
                            max_tokens=request.max_tokens,
                        )
                        try:
                            raw_output = future.result(timeout=self.config.timeout_seconds)
                        except concurrent.futures.TimeoutError:
                            raise GatewayTimeoutError(
                                "GATEWAY_TIMEOUT",
                                f"Model inference timed out after {self.config.timeout_seconds} seconds.",
                            ) from None

                # Validate grammar and Pydantic candidate schema
                try:
                    payload = parse_candidate_payload_json(raw_output)
                except (CandidateContractError, ValueError, json.JSONDecodeError) as exc:
                    raise SchemaValidationError(
                        "INVALID_CANDIDATE_SCHEMA",
                        "The local model output failed strict candidate schema validation.",
                        raw_detail=str(exc),
                    ) from exc

                # Envelope with host provenance
                try:
                    candidate = build_candidate_envelope(payload, request.provenance)
                except (CandidateContractError, ValueError) as exc:
                    raise SchemaValidationError(
                        "INVALID_CANDIDATE_ENVELOPE",
                        "The model candidate envelope failed strict provenance validation.",
                        raw_detail=str(exc),
                    ) from exc

                resources = tracker.measure()

                diag_id = self.diagnostics_store.record_diagnostic(
                    run_id=request.run_id,
                    model_name=self.config.model_name,
                    prompt=effective_prompt,
                    raw_output=raw_output,
                    resource_usage=resources,
                )

                return GatewayInferenceResult(
                    run_id=request.run_id,
                    candidate=candidate,
                    resource_usage=resources,
                    diagnostics_id=diag_id,
                    status="completed",
                )

            except EgressSecurityViolation as exc:
                resources = tracker.measure()
                diag_id = self.diagnostics_store.record_diagnostic(
                    run_id=request.run_id,
                    model_name=self.config.model_name,
                    prompt=request.prompt,
                    raw_output=raw_output,
                    error=exc,
                    resource_usage=resources,
                )
                raise EgressViolationError(
                    "EGRESS_VIOLATION",
                    "Model attempted unauthorized external network communication.",
                    diagnostics_id=diag_id,
                ) from exc

            except GatewayError as exc:
                resources = tracker.measure()
                diag_id = self.diagnostics_store.record_diagnostic(
                    run_id=request.run_id,
                    model_name=self.config.model_name,
                    prompt=request.prompt,
                    raw_output=raw_output,
                    error=exc,
                    resource_usage=resources,
                )
                exc.diagnostics_id = diag_id
                raise

            except Exception as exc:
                resources = tracker.measure()
                diag_id = self.diagnostics_store.record_diagnostic(
                    run_id=request.run_id,
                    model_name=self.config.model_name,
                    prompt=request.prompt,
                    raw_output=raw_output,
                    error=exc,
                    resource_usage=resources,
                )
                raise ModelExecutionError(
                    "MODEL_EXECUTION_FAILED",
                    "The local floor plan model encountered an execution error.",
                    diagnostics_id=diag_id,
                    raw_detail=str(exc),
                ) from exc

            finally:
                with self._lock:
                    self._active_requests -= 1
                self._semaphore.release()
