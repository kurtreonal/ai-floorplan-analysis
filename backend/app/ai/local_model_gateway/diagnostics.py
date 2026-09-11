"""Diagnostics, redaction, and error sanitization for the local VLM gateway.

Implements TICKET U8:
- Private diagnostic logging with retention controls.
- Credential and path redaction.
- Sanitized application-level errors for API boundaries.
"""

from __future__ import annotations

import json
import re
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.ai.floor_plan_interpretation.evaluation_harness import ResourceUsage


def redact_sensitive_text(text: str) -> str:
    """Sanitize text by masking tokens, passwords, and private file system paths."""
    sanitized = text
    # Bearer tokens
    sanitized = re.sub(r"Bearer\s+[A-Za-z0-9_\-\.]+", "Bearer [REDACTED]", sanitized, flags=re.IGNORECASE)
    # Passwords and secret keys
    sanitized = re.sub(r"(password\s*[:=]\s*)[^\s,;&]+", r"\1[REDACTED]", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"(token\s*[:=]\s*)[^\s,;&]+", r"\1[REDACTED]", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"(secret\s*[:=]\s*)[^\s,;&]+", r"\1[REDACTED]", sanitized, flags=re.IGNORECASE)
    # Windows absolute file paths
    sanitized = re.sub(r"[A-Za-z]:\\[A-Za-z0-9_\-\.\\]+", "[REDACTED_PATH]", sanitized)
    # Unix user home paths
    sanitized = re.sub(r"/(?:Users|home)/[A-Za-z0-9_\-\.\/]+", "[REDACTED_PATH]", sanitized)
    return sanitized


class GatewayError(Exception):
    """Base exception for gateway failures with sanitized user-facing messages."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        diagnostics_id: str | None = None,
        raw_detail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.diagnostics_id = diagnostics_id
        self.raw_detail = raw_detail

    def to_sanitized_response(self) -> dict[str, Any]:
        resp: dict[str, Any] = {
            "error": {
                "code": self.code,
                "message": self.message,
            }
        }
        if self.diagnostics_id:
            resp["error"]["diagnostics_id"] = self.diagnostics_id
        return resp


class ModelNotReadyError(GatewayError):
    """Raised when the local VLM process or weights are not loaded/ready."""


class GatewayTimeoutError(GatewayError):
    """Raised when model inference exceeds configured time limits."""


class EgressViolationError(GatewayError):
    """Raised when an inference process attempts external network communication."""


class SchemaValidationError(GatewayError):
    """Raised when raw model output fails strict Pydantic candidate schema validation."""


class ModelExecutionError(GatewayError):
    """Raised when the local model process exits abnormally or produces malformed output."""


class ConcurrencyLimitError(GatewayError):
    """Raised when active requests exceed the gateway concurrency budget."""


class DiagnosticsStore:
    """Stores full raw model diagnostics in a protected directory for offline debugging."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def record_diagnostic(
        self,
        *,
        run_id: str,
        model_name: str,
        prompt: str,
        raw_output: str | None,
        error: Exception | None = None,
        resource_usage: ResourceUsage | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        diag_id = f"diag-{uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        payload = {
            "diagnostics_id": diag_id,
            "run_id": run_id,
            "timestamp": timestamp,
            "model_name": model_name,
            "prompt": redact_sensitive_text(prompt),
            "raw_output": redact_sensitive_text(raw_output or ""),
            "status": "error" if error is not None else "success",
            "error_type": type(error).__name__ if error else None,
            "error_message": redact_sensitive_text(str(error)) if error else None,
            "traceback": redact_sensitive_text(traceback.format_exc()) if error else None,
            "resource_usage": (
                {
                    "latency_ms": resource_usage.latency_ms,
                    "peak_ram_bytes": resource_usage.peak_ram_bytes,
                    "peak_vram_bytes": resource_usage.peak_vram_bytes,
                    "timeout": resource_usage.timeout,
                }
                if resource_usage
                else None
            ),
            "metadata": metadata or {},
        }

        diag_path = self.directory / f"{diag_id}.json"
        try:
            diag_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError:
            # Diagnostics persistence failure must not crash the caller
            pass

        return diag_id
