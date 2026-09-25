from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
from uuid import uuid4

import cv2
import numpy as np
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.floor_plan_interpretation.candidate import CandidateHostProvenance, InferenceParameter, build_candidate_envelope
from app.ai.floor_plan_interpretation import interpret_floor_plan_demo
from app.ai.floor_plan_interpretation.experimental_pull_station import (
    ExperimentalLocatorUnavailable, LOCAL_SOURCE,
    PROVIDER as EXPERIMENTAL_PROVIDER, THRESHOLD as EXPERIMENTAL_THRESHOLD,
    locate, with_pull_station_proposals,
)
from app.ai.floor_plan_interpretation.preparation import prepare_page_context
from app.ai.local_model_gateway import (
    GatewayInferenceRequest,
    LocalGatewayConfig,
    LocalModelGateway,
    LoopbackHTTPVLMAdapter,
)
from app.ai.local_model_gateway.diagnostics import GatewayError, GatewayTimeoutError
from app.core.config import (
    REPOSITORY_ROOT,
    Settings,
    get_max_upload_size_bytes,
    get_processed_directory,
    get_upload_directory,
)
from app.models import (
    FloorPlan,
    FloorPlanInterpretationRun,
    FloorPlanPage,
    FloorPlanSource,
    InterpretationPageOutcome,
    ProcessingJob,
)
from app.repositories.floor_plan_interpretation_repository import (
    add_run,
    find_by_processing_job,
)
from app.repositories.processing_execution_repository import (
    find_cancellation,
    lock_attempt,
    lock_processing_job,
)
from app.services.image_normalization import normalize_image
from app.services.pdf_conversion import convert_pdf_page
from app.services.processing_artifact_service import (
    ProcessingArtifactError,
    register_processing_artifact,
    resolve_trusted_processing_artifact,
)
from app.services.processing_execution_service import (
    ProcessingExecutionError,
    claim_processing_job,
    finish_processing_attempt,
    heartbeat_processing_attempt,
)
from app.services.interpretation_page_outcome_service import (
    PageSelectionError,
    configure_page_outcomes,
    has_open_selected_pages,
    next_selected_page,
    list_page_outcomes,
    list_pages_for_floor_plan,
    requeue_retryable_pages,
)
from app.services.interpretation_job_configuration_service import (
    InterpretationConfigurationError,
    pin_job_configuration,
)
from app.services.interpretation_release_service import MANUAL_REVIEW_PROVIDER
from app.services.source_identity import resolve_stored_original


# This path currently executes deterministic OpenCV, not a model gateway.
# Keep provenance honest until a separately verified VLM provider is connected.
PROVIDER = "demo_cv_baseline"
LOCAL_PROVIDER = "local_vlm_gateway"
LEASE_SECONDS = 300
SAFE_ERROR_MESSAGE = "The interpretation processing job could not be completed."
_GATEWAY_CACHE: dict[tuple[object, ...], LocalModelGateway] = {}


class InterpretationProcessingError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(SAFE_ERROR_MESSAGE)


def page_outcome_failure_status(error_code: str) -> str:
    """Map a sanitized processing error to its durable page terminal state."""
    if error_code == "PROCESSING_CANCELLED":
        return "cancelled"
    if "TIMEOUT" in error_code or error_code == "MODEL_TIMEOUT":
        return "timeout"
    return "failed"


def _context(session: Session, job_id: int, page_number: int | None = None):
    predicates = [
        ProcessingJob.id == job_id,
        ProcessingJob.job_type == "floor_plan_analysis",
    ]
    if page_number is not None:
        predicates.append(FloorPlanPage.page_number == page_number)
    rows = session.execute(
        select(ProcessingJob, FloorPlan, FloorPlanSource, FloorPlanPage)
        .join(FloorPlan, ProcessingJob.floor_plan_id == FloorPlan.id)
        .join(FloorPlanSource, FloorPlanSource.floor_plan_id == FloorPlan.id)
        .join(FloorPlanPage, FloorPlanPage.floor_plan_source_id == FloorPlanSource.id)
        .where(*predicates)
    ).all()
    if not rows:
        raise InterpretationProcessingError("PROCESSING_CONTEXT_NOT_FOUND")
    if len(rows) != 1:
        # Until the explicit page selection/outcome ledger is connected, never
        # present a page-one candidate as successful whole-document processing.
        raise InterpretationProcessingError("MULTIPAGE_SELECTION_REQUIRED")
    return rows[0]


def _heartbeat(
    session: Session,
    *,
    attempt_id: int,
    worker_identity: str,
    stage: str,
) -> None:
    cancellation_requested = heartbeat_processing_attempt(
        session,
        attempt_id=attempt_id,
        worker_identity=worker_identity,
        stage=stage,
        lease_seconds=LEASE_SECONDS,
    )
    if cancellation_requested:
        finish_processing_attempt(
            session,
            attempt_id=attempt_id,
            worker_identity=worker_identity,
            outcome="cancelled",
        )
        raise InterpretationProcessingError("PROCESSING_CANCELLED")


def _registered_artifact(
    session: Session,
    *,
    job: ProcessingJob,
    floor_plan: FloorPlan,
    source_manifest: FloorPlanSource,
    settings: Settings,
    page: FloorPlanPage,
):
    processed_directory = get_processed_directory(settings)
    try:
        return resolve_trusted_processing_artifact(
            session,
            floor_plan_id=floor_plan.id,
            processing_job_id=job.id,
            artifact_kind="normalized_image",
            processed_directory=processed_directory,
            floor_plan_page_id=page.id,
        )
    except ProcessingArtifactError:
        pass

    upload_directory = get_upload_directory(settings)
    original = resolve_stored_original(upload_directory, floor_plan.storage_path)
    size = original.stat().st_size
    if (
        size != floor_plan.file_size
        or size <= 0
        or size > get_max_upload_size_bytes(settings)
    ):
        raise InterpretationProcessingError("ORIGINAL_INTEGRITY_FAILED")
    digest = sha256()
    with original.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != source_manifest.original_sha256:
        raise InterpretationProcessingError("ORIGINAL_INTEGRITY_FAILED")
    if floor_plan.mime_type == "application/pdf":
        try:
            rendered = resolve_trusted_processing_artifact(
                session,
                floor_plan_id=floor_plan.id,
                processing_job_id=job.id,
                artifact_kind="pdf_page",
                processed_directory=processed_directory,
                floor_plan_page_id=page.id,
            )
            render_path = rendered.absolute_path
        except ProcessingArtifactError:
            converted = convert_pdf_page(
                source_path=original,
                processed_directory=processed_directory,
                floor_plan_id=floor_plan.id,
                processing_job_id=job.id,
                page_number=page.page_number,
            )
            register_processing_artifact(
                session,
                processing_job=job,
                floor_plan_id=floor_plan.id,
                page_number=page.page_number,
                artifact_kind="pdf_page",
                processed_directory=processed_directory,
                relative_path=converted.output_reference,
                mime_type=converted.mime_type,
            )
            session.commit()
            render_path = converted.absolute_output_path
        source_path = render_path
        source_mime_type = "image/png"
    else:
        source_path = original
        source_mime_type = floor_plan.mime_type

    normalized = normalize_image(
        source_path=source_path,
        source_mime_type=source_mime_type,
        processed_directory=processed_directory,
        floor_plan_id=floor_plan.id,
        processing_job_id=job.id,
        page_number=page.page_number,
    )
    register_processing_artifact(
        session,
        processing_job=job,
        floor_plan_id=floor_plan.id,
        page_number=page.page_number,
        artifact_kind="normalized_image",
        processed_directory=processed_directory,
        relative_path=normalized.output_reference,
        mime_type=normalized.output_mime_type,
    )
    session.commit()
    return resolve_trusted_processing_artifact(
        session,
        floor_plan_id=floor_plan.id,
        processing_job_id=job.id,
        artifact_kind="normalized_image",
        processed_directory=processed_directory,
        floor_plan_page_id=page.id,
    )


def _decode_rgb(content: bytes) -> np.ndarray:
    try:
        with Image.open(BytesIO(content)) as image:
            if image.format != "PNG":
                raise ValueError
            rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    except Exception:
        raise InterpretationProcessingError("NORMALIZED_IMAGE_INVALID") from None
    return rgb


def _safe_release(value: str | None, fallback: str) -> str:
    candidate = re.sub(r"[^a-z0-9_-]+", "-", (value or "").strip().lower()).strip("-")
    return candidate[:128] or fallback


def _configured_local_gateway(settings: Settings) -> tuple[LocalModelGateway, LocalGatewayConfig] | None:
    """Build/cache the U8 gateway only when an administrator configured it.

    No configured runtime is a normal unavailable state.  The deterministic
    OpenCV demo remains explicitly identified as such for the local demo; it
    is never mislabeled as VLM inference.
    """
    runtime_url = getattr(settings, "local_vlm_runtime_url", None)
    model_path = getattr(settings, "local_vlm_model_path", None)
    adapter_path = getattr(settings, "local_vlm_adapter_path", None)
    if runtime_url is None and model_path is None:
        return None
    if runtime_url is None:
        raise InterpretationProcessingError("MODEL_UNAVAILABLE")
    resolved_model_path = None if model_path is None else Path(model_path)
    if resolved_model_path is not None and not resolved_model_path.is_absolute():
        resolved_model_path = (REPOSITORY_ROOT / resolved_model_path).resolve(strict=False)
    if resolved_model_path is not None and not resolved_model_path.is_file():
        raise InterpretationProcessingError("MODEL_UNAVAILABLE")
    resolved_adapter_path = None if adapter_path is None else Path(adapter_path)
    if resolved_adapter_path is not None and not resolved_adapter_path.is_absolute():
        resolved_adapter_path = (REPOSITORY_ROOT / resolved_adapter_path).resolve(strict=False)
    config = LocalGatewayConfig(
        model_name=getattr(settings, "local_vlm_model_name", "Qwen2.5-VL-7B-Instruct"),
        model_revision=getattr(settings, "local_vlm_model_revision", "unconfigured"),
        model_path=resolved_model_path,
        adapter_path=resolved_adapter_path,
        runtime_url=runtime_url,
        timeout_seconds=getattr(settings, "local_vlm_timeout_seconds", 60.0),
        diagnostics_directory=Path("storage/diagnostics"),
    )
    key = (
        config.model_name,
        config.model_revision,
        str(config.model_path) if config.model_path else None,
        str(config.adapter_path) if config.adapter_path else None,
        config.runtime_url,
        config.timeout_seconds,
    )
    gateway = _GATEWAY_CACHE.get(key)
    if gateway is None:
        gateway = LocalModelGateway(config, LoopbackHTTPVLMAdapter(config))
        _GATEWAY_CACHE[key] = gateway
    return gateway, config


def _persist_fenced_run(session, *, claim, worker_identity, run, page_outcome=None, provider=PROVIDER):
    """Publish output and acknowledge success under the same PRE9 row locks.

    Never commit candidate output before checking lease ownership/cancellation.
    The PRE9 completion operation commits both the candidate and acknowledgment.
    """
    try:
        job = lock_processing_job(session, job_id=claim.job_id)
        attempt = lock_attempt(session, attempt_id=claim.attempt_id)
        if (
            job is None or attempt is None or job.status != "processing"
            or attempt.processing_job_id != claim.job_id
            or attempt.worker_identity != worker_identity
            or attempt.status != "active" or attempt.active_marker is not True
        ):
            raise InterpretationProcessingError("PROCESSING_ATTEMPT_NOT_ACTIVE")
        if attempt.lease_expires_at <= datetime.now(UTC).replace(tzinfo=None):
            raise InterpretationProcessingError("PROCESSING_LEASE_EXPIRED")
        if find_cancellation(session, job_id=claim.job_id) is not None:
            raise InterpretationProcessingError("PROCESSING_CANCELLED")
        existing = find_by_processing_job(session, processing_job_id=claim.job_id,
                                          floor_plan_page_id=run.floor_plan_page_id)
        if existing is not None:
            if existing.provider != provider:
                raise InterpretationProcessingError("PROCESSING_PROVIDER_CONFLICT")
            result = existing
        else:
            result = add_run(session, run)
        if page_outcome is not None:
            page_outcome = session.scalar(
                select(InterpretationPageOutcome)
                .where(InterpretationPageOutcome.id == page_outcome.id)
                .with_for_update()
            )
            if page_outcome is None:
                raise InterpretationProcessingError("PROCESSING_PAGE_OUTCOME_NOT_FOUND")
            page_outcome.status = "completed"
            page_outcome.progress = 100
            page_outcome.candidate_run_id = result.candidate_run_id
            page_outcome.source_artifact_id = result.source_artifact_id
        session.flush()
        if page_outcome is None:
            finish_processing_attempt(
                session, attempt_id=claim.attempt_id,
                worker_identity=worker_identity, outcome="succeeded",
            )
        else:
            finish_processing_attempt(
                session, attempt_id=claim.attempt_id,
                worker_identity=worker_identity, outcome="succeeded",
                complete_job=not has_open_selected_pages(session, processing_job_id=claim.job_id),
            )
        return result
    except Exception:
        session.rollback()
        raise


def process_interpretation_job(
    session: Session,
    *,
    job_id: int,
    worker_identity: str,
    settings: Settings,
) -> FloorPlanInterpretationRun | None:
    page_outcome = None
    try:
        claim = claim_processing_job(
            session,
            job_id=job_id,
            worker_identity=worker_identity,
            lease_seconds=LEASE_SECONDS,
        )
    except ProcessingExecutionError as error:
        raise InterpretationProcessingError(error.code) from None
    try:
        job = session.get(ProcessingJob, job_id)
        if job is None or job.job_type != "floor_plan_analysis":
            raise InterpretationProcessingError("PROCESSING_CONTEXT_NOT_FOUND")
        outcomes = list_page_outcomes(session, processing_job_id=job.id)
        if not outcomes:
            pages = list_pages_for_floor_plan(session, floor_plan_id=job.floor_plan_id)
            if len(pages) != 1:
                raise InterpretationProcessingError("PROCESSING_PAGE_SELECTION_REQUIRED")
            try:
                outcomes = configure_page_outcomes(
                    session, processing_job=job, page_numbers=[pages[0].page_number]
                )
            except PageSelectionError as error:
                raise InterpretationProcessingError(error.code) from None
        try:
            pinned_configuration = pin_job_configuration(
                session, processing_job=job, settings=settings
            )
        except InterpretationConfigurationError as error:
            raise InterpretationProcessingError(error.code) from None
        requeue_retryable_pages(session, processing_job_id=job.id)
        page_outcome = next_selected_page(session, processing_job_id=job.id)
        if page_outcome is None:
            raise InterpretationProcessingError("PROCESSING_PAGE_SELECTION_REQUIRED")
        page_outcome.status = "processing"
        page_outcome.progress = 1
        session.commit()
        job, floor_plan, source_manifest, page = _context(
            session, job_id, page_outcome.page_number
        )
        existing = find_by_processing_job(session, processing_job_id=job_id,
                                          floor_plan_page_id=page.id)
        if existing is not None:
            expected_provider = pinned_configuration.provider
            return _persist_fenced_run(
                session, claim=claim, worker_identity=worker_identity, run=existing,
                page_outcome=page_outcome, provider=expected_provider,
            )
        _heartbeat(
            session,
            attempt_id=claim.attempt_id,
            worker_identity=worker_identity,
            stage="source_preparation",
        )
        artifact = _registered_artifact(
            session,
            job=job,
            floor_plan=floor_plan,
            source_manifest=source_manifest,
            settings=settings,
            page=page,
        )
        _heartbeat(
            session,
            attempt_id=claim.attempt_id,
            worker_identity=worker_identity,
            stage="normalization",
        )
        rgb = _decode_rgb(artifact.content)
        _heartbeat(
            session,
            attempt_id=claim.attempt_id,
            worker_identity=worker_identity,
            stage="geometry_evidence",
        )
        _heartbeat(
            session,
            attempt_id=claim.attempt_id,
            worker_identity=worker_identity,
            stage="symbol_evidence",
        )
        run_id = uuid4().hex
        experimental = pinned_configuration.provider == EXPERIMENTAL_PROVIDER
        gateway_configured = None if experimental else _configured_local_gateway(settings)
        if pinned_configuration.provider == PROVIDER:
            # Tests and unconfigured jobs may explicitly pin the deterministic
            # demo provider; keep that choice stable even if settings change.
            gateway_configured = None
        if gateway_configured is None:
            if pinned_configuration.provider in (LOCAL_PROVIDER, MANUAL_REVIEW_PROVIDER):
                # A promoted release never silently falls back to the demo CV
                # detector when its local gateway is unavailable or fenced.
                raise InterpretationProcessingError("MODEL_UNAVAILABLE")
            provider = pinned_configuration.provider
            payload = interpret_floor_plan_demo(rgb)
            if experimental:
                try:
                    payload = with_pull_station_proposals(payload, locate(rgb, LOCAL_SOURCE))
                except ExperimentalLocatorUnavailable as error:
                    raise InterpretationProcessingError(str(error)) from None
            candidate = build_candidate_envelope(
                payload,
                CandidateHostProvenance(
                    candidate_run_id=run_id,
                    processing_job_id=job.id,
                    floor_plan_source_id=source_manifest.id,
                    floor_plan_page_id=page.id,
                    source_artifact_id=artifact.record.id,
                    source_page_number=page.page_number,
                    source_sha256=source_manifest.original_sha256,
                    source_artifact_sha256=artifact.record.sha256,
                    expected_width_pixels=artifact.record.pixel_width,
                    expected_height_pixels=artifact.record.pixel_height,
                    model_release_id=provider,
                    base_model_revision=(f"opencv-template-{cv2.__version__}" if experimental
                                         else f"opencv-{cv2.__version__}"),
                    adapter_revision=None,
                    prompt_version="pull-template-v1" if experimental else "demo-cv-room-v2",
                    runtime_version=f"opencv-{cv2.__version__}",
                    inference_parameters=(
                        InferenceParameter(name="provider", value=provider),
                        InferenceParameter(name="review-required", value="true"),
                        *((
                            InferenceParameter(name="template-class", value="sheet-20:L05 Pull station"),
                            InferenceParameter(name="template-score-threshold", value=str(EXPERIMENTAL_THRESHOLD)),
                        ) if experimental else ()),
                    ),
                    created_at=datetime.now(UTC),
                ),
            )
        else:
            if pinned_configuration.provider == MANUAL_REVIEW_PROVIDER:
                raise InterpretationProcessingError("MODEL_UNAVAILABLE")
            gateway, gateway_config = gateway_configured
            provider = LOCAL_PROVIDER
            prepared_context = prepare_page_context(
                rgb, page_number=page.page_number
            )
            provenance = CandidateHostProvenance(
                candidate_run_id=run_id,
                processing_job_id=job.id,
                floor_plan_source_id=source_manifest.id,
                floor_plan_page_id=page.id,
                source_artifact_id=artifact.record.id,
                source_page_number=page.page_number,
                source_sha256=source_manifest.original_sha256,
                source_artifact_sha256=artifact.record.sha256,
                expected_width_pixels=artifact.record.pixel_width,
                expected_height_pixels=artifact.record.pixel_height,
                model_release_id=getattr(
                    pinned_configuration,
                    "model_release_id",
                    _safe_release(gateway_config.model_name, LOCAL_PROVIDER),
                ),
                base_model_revision=_safe_release(
                    gateway_config.model_revision, "unavailable"
                ),
                adapter_revision=(
                    _safe_release(str(gateway_config.adapter_path), "none")
                    if gateway_config.adapter_path
                    else None
                ),
                prompt_version=gateway_config.system_prompt_version,
                runtime_version="u8-loopback-http-v1",
                inference_parameters=(
                    InferenceParameter(name="provider", value=provider),
                    InferenceParameter(name="review-required", value="true"),
                ),
                created_at=datetime.now(UTC),
            )
            request = GatewayInferenceRequest(
                run_id=run_id,
                page_number=page.page_number,
                prompt=(
                    "Interpret this electrical floor-plan page. Return only the "
                    "strict U2 candidate payload; preserve unknowns and review "
                    "state rather than inventing geometry or classes."
                ),
                provenance=provenance,
                decoding_temperature=gateway_config.temperature,
                max_tokens=gateway_config.max_output_tokens,
            )
            try:
                result = gateway.submit_inference(request, prepared_context)
            except GatewayTimeoutError:
                raise InterpretationProcessingError("MODEL_TIMEOUT") from None
            except GatewayError as error:
                raise InterpretationProcessingError(error.code) from None
            candidate = result.candidate
        serialized = candidate.model_dump_json()
        run = FloorPlanInterpretationRun(
            candidate_run_id=run_id,
            processing_job_id=job.id,
            floor_plan_id=floor_plan.id,
            floor_plan_page_id=page.id,
            source_artifact_id=artifact.record.id,
            provider=provider,
            candidate_sha256=sha256(serialized.encode("utf-8")).hexdigest(),
            candidate_json=serialized,
        )
        _heartbeat(
            session,
            attempt_id=claim.attempt_id,
            worker_identity=worker_identity,
            stage="persistence",
        )
        return _persist_fenced_run(
            session, claim=claim, worker_identity=worker_identity, run=run,
            page_outcome=page_outcome, provider=provider,
        )
    except InterpretationProcessingError as error:
        session.rollback()
        remaining = False
        if page_outcome is not None:
            try:
                page_outcome = session.get(InterpretationPageOutcome, page_outcome.id)
                if page_outcome is not None:
                    page_outcome.status = page_outcome_failure_status(error.code)
                    page_outcome.progress = 100
                    page_outcome.failure_code = error.code
                    session.flush()
                    remaining = has_open_selected_pages(
                        session, processing_job_id=claim.job_id
                    )
                    session.commit()
            except Exception:
                session.rollback()
        try:
            # A heartbeat may already have acknowledged cancellation. A final
            # write-fence cancellation still needs acknowledgment, without output.
            finish_processing_attempt(
                session,
                attempt_id=claim.attempt_id,
                worker_identity=worker_identity,
                outcome="cancelled" if error.code == "PROCESSING_CANCELLED" else "failed",
                failure_code=None if error.code == "PROCESSING_CANCELLED" else error.code,
                complete_job=not remaining,
            )
        except ProcessingExecutionError:
            # Do not obscure the original error when this attempt was replaced
            # or was already acknowledged by the heartbeat.
            pass
        raise
    except Exception:
        session.rollback()
        remaining = False
        if page_outcome is not None:
            try:
                page_outcome = session.get(InterpretationPageOutcome, page_outcome.id)
                if page_outcome is not None:
                    page_outcome.status = page_outcome_failure_status(
                        "INTERPRETATION_PROCESSING_FAILED"
                    )
                    page_outcome.progress = 100
                    page_outcome.failure_code = "INTERPRETATION_PROCESSING_FAILED"
                    session.flush()
                    remaining = has_open_selected_pages(
                        session, processing_job_id=claim.job_id
                    )
                    session.commit()
            except Exception:
                session.rollback()
        try:
            finish_processing_attempt(
                session,
                attempt_id=claim.attempt_id,
                worker_identity=worker_identity,
                outcome="failed",
                failure_code="INTERPRETATION_PROCESSING_FAILED",
                complete_job=not remaining,
            )
        except Exception:
            pass
        raise InterpretationProcessingError("INTERPRETATION_PROCESSING_FAILED") from None
