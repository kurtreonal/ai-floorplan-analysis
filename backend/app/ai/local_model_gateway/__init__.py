"""Isolated schema-constrained local VLM gateway boundary."""

from app.ai.local_model_gateway.config import (
    DEFAULT_CONCURRENCY,
    DEFAULT_LOCAL_RUNTIME_URL,
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_SYSTEM_PROMPT_VERSION,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_VRAM_BUDGET_MB,
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
    redact_sensitive_text,
)
from app.ai.local_model_gateway.gateway import (
    LocalModelGateway,
    LocalVLMRuntimeAdapter,
    MockLocalVLMAdapter,
)

__all__ = [
    "DEFAULT_CONCURRENCY",
    "DEFAULT_LOCAL_RUNTIME_URL",
    "DEFAULT_MAX_OUTPUT_TOKENS",
    "DEFAULT_SYSTEM_PROMPT_VERSION",
    "DEFAULT_TIMEOUT_SECONDS",
    "DEFAULT_VRAM_BUDGET_MB",
    "GatewayHealth",
    "GatewayInferenceRequest",
    "GatewayInferenceResult",
    "LocalGatewayConfig",
    "ConcurrencyLimitError",
    "DiagnosticsStore",
    "EgressViolationError",
    "GatewayError",
    "GatewayTimeoutError",
    "ModelExecutionError",
    "ModelNotReadyError",
    "SchemaValidationError",
    "redact_sensitive_text",
    "LocalModelGateway",
    "LocalVLMRuntimeAdapter",
    "MockLocalVLMAdapter",
]
