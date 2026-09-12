"""Unit and boundary test suite for U8 isolated local VLM gateway."""

import json
import socket
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

import numpy as np

from app.ai.floor_plan_interpretation.candidate import CandidateHostProvenance, InferenceParameter
from app.ai.floor_plan_interpretation.preparation import (
    PreparationConfig,
    prepare_page_context,
)
from app.ai.local_model_gateway import (
    ConcurrencyLimitError,
    DiagnosticsStore,
    EgressViolationError,
    GatewayHealth,
    GatewayInferenceRequest,
    GatewayInferenceResult,
    GatewayTimeoutError,
    LocalGatewayConfig,
    LocalModelGateway,
    MockLocalVLMAdapter,
    ModelExecutionError,
    SchemaValidationError,
    redact_sensitive_text,
)


def make_sample_provenance(**changes) -> CandidateHostProvenance:
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
        "created_at": datetime.now(timezone.utc),
    }
    values.update(changes)
    return CandidateHostProvenance(**values)


def make_sample_context():
    img = np.ones((800, 1000, 3), dtype=np.uint8) * 255
    return prepare_page_context(
        img,
        page_number=1,
        config=PreparationConfig(tile_width=500, tile_height=400, tile_overlap=100),
    )


class GatewayConfigTests(TestCase):
    """Tests for gateway configuration and offline network constraints."""

    def test_accepts_loopback_urls(self) -> None:
        valid_urls = [
            "http://127.0.0.1:8081",
            "http://localhost:8081",
            "http://[::1]:8081",
        ]
        for url in valid_urls:
            cfg = LocalGatewayConfig(runtime_url=url)
            self.assertEqual(cfg.runtime_url, url)

    def test_rejects_external_hosts(self) -> None:
        invalid_urls = [
            "https://api.openai.com/v1",
            "http://192.168.1.100:8081",
            "http://example.com/vlm",
            "http://10.0.0.5:8080",
        ]
        for url in invalid_urls:
            with self.assertRaises(ValueError):
                LocalGatewayConfig(runtime_url=url)

    def test_rejects_network_egress_enablement(self) -> None:
        with self.assertRaises(ValueError):
            LocalGatewayConfig(allow_network=True)


class DiagnosticsAndRedactionTests(TestCase):
    """Tests for redaction, diagnostic persistence, and safe user-facing errors."""

    def test_redact_sensitive_tokens_and_paths(self) -> None:
        raw = (
            "Error with Bearer eyJhbGciOiJIUzI1Ni.secret and password: MyPassword123 "
            "at C:\\Users\\Administrator\\secret.key and /Users/developer/keys.pem"
        )
        cleaned = redact_sensitive_text(raw)
        self.assertNotIn("MyPassword123", cleaned)
        self.assertNotIn("eyJhbGciOiJIUzI1Ni.secret", cleaned)
        self.assertNotIn("C:\\Users\\Administrator", cleaned)
        self.assertNotIn("/Users/developer", cleaned)

    def test_diagnostic_store_writes_records_safely(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = DiagnosticsStore(Path(temp_dir))
            diag_id = store.record_diagnostic(
                run_id="run-001",
                model_name="Qwen2.5-VL-7B-Instruct",
                prompt="Detect symbols with password=secret",
                raw_output="Raw model output text",
            )
            self.assertTrue(diag_id.startswith("diag-"))
            diag_file = Path(temp_dir) / f"{diag_id}.json"
            self.assertTrue(diag_file.is_file())
            content = json.loads(diag_file.read_text(encoding="utf-8"))
            self.assertEqual(content["run_id"], "run-001")
            self.assertNotIn("secret", content["prompt"])


class GatewayExecutionTests(TestCase):
    """Tests for gateway lifecycle, inference execution, validation, and safety boundaries."""

    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.diag_path = Path(self.temp_dir.name)
        self.config = LocalGatewayConfig(
            diagnostics_directory=self.diag_path,
            timeout_seconds=2.0,
            max_concurrency=2,
        )
        self.context = make_sample_context()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_wiring_evidence_reaches_runtime_as_non_authoritative_hints(self):
        from unittest.mock import patch
        adapter = MockLocalVLMAdapter()
        gateway = LocalModelGateway(self.config, adapter)
        request = GatewayInferenceRequest(
            run_id="wiring-evidence", page_number=1,
            prompt="Inspect the source pixels", provenance=make_sample_provenance(),
        )
        with patch.object(adapter, "predict", wraps=adapter.predict) as predict:
            result = gateway.submit_inference(request, self.context)
        prompt = predict.call_args.args[0]
        self.assertIn("not electrical truth", prompt)
        self.assertIn("No fragments does not prove no wiring", prompt)
        self.assertIn('"state":"partial"', prompt)
        self.assertEqual(result.status, "completed")

    def test_lazy_loading_and_health_check(self) -> None:
        adapter = MockLocalVLMAdapter()
        gateway = LocalModelGateway(self.config, adapter)

        health_before = gateway.health_check()
        self.assertEqual(health_before.status, "unavailable")
        self.assertFalse(health_before.loaded_in_memory)

        gateway.warmup()
        health_after = gateway.health_check()
        self.assertEqual(health_after.status, "ready")
        self.assertTrue(health_after.loaded_in_memory)

        gateway.shutdown()
        health_down = gateway.health_check()
        self.assertEqual(health_down.status, "unavailable")

    def test_successful_inference_produces_validated_candidate(self) -> None:
        adapter = MockLocalVLMAdapter()
        gateway = LocalModelGateway(self.config, adapter)

        request = GatewayInferenceRequest(
            run_id="run-success-001",
            page_number=1,
            prompt="Analyze floor plan symbols",
            provenance=make_sample_provenance(),
        )

        result = gateway.submit_inference(request, self.context)
        self.assertEqual(result.run_id, "run-success-001")
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.candidate.payload.schema_version, 1)
        self.assertEqual(result.candidate.provenance.model_release_id, "candidate-local")
        self.assertIsNotNone(result.diagnostics_id)
        self.assertGreater(result.resource_usage.latency_ms, 0.0)

    def test_malformed_model_output_raises_schema_validation_error(self) -> None:
        # Simulate corrupted or incomplete JSON generated by model
        adapter = MockLocalVLMAdapter(simulate_raw_text='{"schema_version": 1, "unclosed":')
        gateway = LocalModelGateway(self.config, adapter)

        request = GatewayInferenceRequest(
            run_id="run-malformed-001",
            page_number=1,
            prompt="Analyze floor plan",
            provenance=make_sample_provenance(),
        )

        with self.assertRaises(SchemaValidationError) as ctx:
            gateway.submit_inference(request, self.context)

        err_dict = ctx.exception.to_sanitized_response()
        self.assertEqual(err_dict["error"]["code"], "INVALID_CANDIDATE_SCHEMA")
        self.assertIn("diagnostics_id", err_dict["error"])

    def test_missing_required_fields_raises_schema_validation_error(self) -> None:
        # Valid JSON but missing required candidate collections
        invalid_payload = {"schema_version": 1, "page_assessment": None}
        adapter = MockLocalVLMAdapter(fixed_payload=invalid_payload)
        gateway = LocalModelGateway(self.config, adapter)

        request = GatewayInferenceRequest(
            run_id="run-invalid-schema-002",
            page_number=1,
            prompt="Analyze floor plan",
            provenance=make_sample_provenance(),
        )

        with self.assertRaises(SchemaValidationError):
            gateway.submit_inference(request, self.context)

    def test_timeout_cancels_inference_safely(self) -> None:
        # Simulate a hanging model inference process exceeding timeout
        fast_config = self.config.model_copy(update={"timeout_seconds": 0.5})
        adapter = MockLocalVLMAdapter(simulate_hang=True)
        gateway = LocalModelGateway(fast_config, adapter)

        request = GatewayInferenceRequest(
            run_id="run-hang-001",
            page_number=1,
            prompt="Analyze floor plan",
            provenance=make_sample_provenance(),
        )

        with self.assertRaises(GatewayTimeoutError) as ctx:
            gateway.submit_inference(request, self.context)

        self.assertEqual(ctx.exception.code, "GATEWAY_TIMEOUT")

    def test_egress_violation_triggers_security_escalation(self) -> None:
        class EgressViolatingAdapter:
            def load(self) -> None:
                pass

            def is_ready(self) -> bool:
                return True

            def unload(self) -> None:
                pass

            def predict(self, prompt: str, images, **kwargs) -> str:
                # Attempt to open an unauthorized external socket connection
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    sock.connect(("8.8.8.8", 53))
                finally:
                    sock.close()
                return "{}"

        gateway = LocalModelGateway(self.config, EgressViolatingAdapter())
        request = GatewayInferenceRequest(
            run_id="run-egress-001",
            page_number=1,
            prompt="Analyze floor plan",
            provenance=make_sample_provenance(),
        )

        with self.assertRaises(EgressViolationError) as ctx:
            gateway.submit_inference(request, self.context)

        self.assertEqual(ctx.exception.code, "EGRESS_VIOLATION")

    def test_concurrency_limit_enforced(self) -> None:
        strict_config = self.config.model_copy(update={"max_concurrency": 1})
        adapter = MockLocalVLMAdapter()
        gateway = LocalModelGateway(strict_config, adapter)

        # Artificially exhaust semaphore
        gateway._semaphore.acquire()
        try:
            request = GatewayInferenceRequest(
                run_id="run-concurrency-001",
                page_number=1,
                prompt="Analyze floor plan",
                provenance=make_sample_provenance(),
            )
            with self.assertRaises(ConcurrencyLimitError):
                gateway.submit_inference(request, self.context)
        finally:
            gateway._semaphore.release()
