"""Configuration and data contracts for the isolated local VLM gateway.

Implements TICKET U8:
- Pinned local-only configuration (no external endpoints or hosted fallbacks).
- Resource budgets (RTX 3050 4GB VRAM, peak RAM, max concurrency).
- Strict request and response envelopes with host provenance and reference pack tracking.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.ai.floor_plan_interpretation.candidate import (
    CandidateHostProvenance,
    FloorPlanInterpretationCandidate,
    FloorPlanInterpretationPayload,
)
from app.ai.floor_plan_interpretation.evaluation_harness import ResourceUsage
from app.ai.floor_plan_interpretation.preparation import PreparedContext


LOCAL_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
DEFAULT_LOCAL_RUNTIME_URL = "http://127.0.0.1:8081"
DEFAULT_SYSTEM_PROMPT_VERSION = "v1.0.0"
MAXIMUM_CONCURRENCY = 8
DEFAULT_CONCURRENCY = 2
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_OUTPUT_TOKENS = 4096
DEFAULT_VRAM_BUDGET_MB = 4096  # 4GB budget for RTX 3050 Laptop GPU


class LocalGatewayConfig(BaseModel):
    """Configuration and safety parameters for the local VLM gateway."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_name: Annotated[str, Field(min_length=1, max_length=128)] = "Qwen2.5-VL-7B-Instruct"
    model_revision: Annotated[str, Field(min_length=1, max_length=128)] = "pinned-rev-1"
    model_path: Path | None = None
    adapter_path: Path | None = None
    runtime_url: str = DEFAULT_LOCAL_RUNTIME_URL
    allow_network: bool = False
    max_concurrency: Annotated[int, Field(ge=1, le=MAXIMUM_CONCURRENCY)] = DEFAULT_CONCURRENCY
    timeout_seconds: Annotated[float, Field(gt=0.0, le=300.0)] = DEFAULT_TIMEOUT_SECONDS
    max_output_tokens: Annotated[int, Field(ge=128, le=16384)] = DEFAULT_MAX_OUTPUT_TOKENS
    temperature: Annotated[float, Field(ge=0.0, le=2.0)] = 0.0
    max_retries: Annotated[int, Field(ge=0, le=3)] = 2
    vram_budget_mb: Annotated[int, Field(ge=1024, le=16384)] = DEFAULT_VRAM_BUDGET_MB
    system_prompt_version: str = DEFAULT_SYSTEM_PROMPT_VERSION
    diagnostics_directory: Path = Path("storage/diagnostics")

    @field_validator("runtime_url")
    @classmethod
    def validate_runtime_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Invalid URL scheme: {parsed.scheme}")
        hostname = (parsed.hostname or "").lower()
        if hostname not in LOCAL_LOOPBACK_HOSTS:
            raise ValueError(
                f"External runtime host '{hostname}' rejected. The local VLM gateway strictly forbids external endpoints."
            )
        return value

    @model_validator(mode="after")
    def enforce_offline_policy(self) -> LocalGatewayConfig:
        if self.allow_network:
            raise ValueError("allow_network must be False. External egress is prohibited.")
        return self


class GatewayInferenceRequest(BaseModel):
    """Encapsulated request submitted to the local VLM gateway."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    page_number: int = Field(gt=0)
    reference_pack_id: int | None = None
    reference_pack_version: str = "v1"
    reference_pack_sha256: str | None = None
    prompt: str = Field(min_length=1)
    provenance: CandidateHostProvenance
    decoding_temperature: float = 0.0
    max_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS


class GatewayInferenceResult(BaseModel):
    """Validated interpretation candidate with host provenance and resource usage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    candidate: FloorPlanInterpretationCandidate
    resource_usage: ResourceUsage
    diagnostics_id: str | None = None
    status: Literal["completed", "failed", "cancelled"] = "completed"


class GatewayHealth(BaseModel):
    """Health and readiness check report for the gateway process."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["ready", "initializing", "unavailable", "error"]
    model_name: str
    model_revision: str
    local_runtime_url: str
    vram_budget_mb: int
    loaded_in_memory: bool
    active_requests: int
    diagnostics_path: str
    message: str
