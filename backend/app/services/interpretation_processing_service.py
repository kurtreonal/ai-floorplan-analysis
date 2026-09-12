from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from uuid import uuid4

import cv2
import numpy as np
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.floor_plan_interpretation.candidate import CandidateHostProvenance, InferenceParameter, build_candidate_envelope
from app.ai.floor_plan_interpretation import interpret_floor_plan_demo
from app.core.config import (
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
from app.services.source_identity import resolve_stored_original


# This path currently executes deterministic OpenCV, not a model gateway.
# Keep provenance honest until a separately verified VLM provider is connected.
PROVIDER = "demo_cv_baseline"
LEASE_SECONDS = 300
SAFE_ERROR_MESSAGE = "The interpretation processing job could not be completed."


class InterpretationProcessingError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(SAFE_ERROR_MESSAGE)


def _context(session: Session, job_id: int):
    row = session.execute(
        select(ProcessingJob, FloorPlan, FloorPlanSource, FloorPlanPage)
        .join(FloorPlan, ProcessingJob.floor_plan_id == FloorPlan.id)
        .join(FloorPlanSource, FloorPlanSource.floor_plan_id == FloorPlan.id)
        .join(FloorPlanPage, FloorPlanPage.floor_plan_source_id == FloorPlanSource.id)
        .where(
            ProcessingJob.id == job_id,
            ProcessingJob.job_type == "floor_plan_analysis",
            FloorPlanPage.page_number == 1,
        )
    ).one_or_none()
    if row is None:
        raise InterpretationProcessingError("PROCESSING_CONTEXT_NOT_FOUND")
    return row


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
):
    processed_directory = get_processed_directory(settings)
    try:
        return resolve_trusted_processing_artifact(
            session,
            floor_plan_id=floor_plan.id,
            processing_job_id=job.id,
            artifact_kind="normalized_image",
            processed_directory=processed_directory,
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
            )
            render_path = rendered.absolute_path
        except ProcessingArtifactError:
            converted = convert_pdf_page(
                source_path=original,
                processed_directory=processed_directory,
                floor_plan_id=floor_plan.id,
                processing_job_id=job.id,
                page_number=1,
            )
            register_processing_artifact(
                session,
                processing_job=job,
                floor_plan_id=floor_plan.id,
                page_number=1,
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
    )
    register_processing_artifact(
        session,
        processing_job=job,
        floor_plan_id=floor_plan.id,
        page_number=1,
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


def _persist_fenced_run(session, *, claim, worker_identity, run):
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
        existing = find_by_processing_job(session, processing_job_id=claim.job_id)
        if existing is not None:
            if existing.provider != PROVIDER:
                raise InterpretationProcessingError("PROCESSING_PROVIDER_CONFLICT")
            result = existing
        else:
            result = add_run(session, run)
        finish_processing_attempt(
            session, attempt_id=claim.attempt_id,
            worker_identity=worker_identity, outcome="succeeded",
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
        existing = find_by_processing_job(session, processing_job_id=job_id)
        if existing is not None:
            return _persist_fenced_run(
                session, claim=claim, worker_identity=worker_identity, run=existing,
            )
        job, floor_plan, source_manifest, page = _context(session, job_id)
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
        payload = interpret_floor_plan_demo(rgb)
        _heartbeat(
            session,
            attempt_id=claim.attempt_id,
            worker_identity=worker_identity,
            stage="symbol_evidence",
        )
        run_id = uuid4().hex
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
                model_release_id=PROVIDER,
                base_model_revision=f"opencv-{cv2.__version__}",
                adapter_revision=None,
                prompt_version="demo-cv-room-v2",
                runtime_version=f"opencv-{cv2.__version__}",
                inference_parameters=(
                    InferenceParameter(name="provider", value=PROVIDER),
                    InferenceParameter(name="review-required", value="true"),
                ),
                created_at=datetime.now(UTC),
            ),
        )
        serialized = candidate.model_dump_json()
        run = FloorPlanInterpretationRun(
            candidate_run_id=run_id,
            processing_job_id=job.id,
            floor_plan_id=floor_plan.id,
            floor_plan_page_id=page.id,
            source_artifact_id=artifact.record.id,
            provider=PROVIDER,
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
        )
    except InterpretationProcessingError as error:
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
            )
        except ProcessingExecutionError:
            # Do not obscure the original error when this attempt was replaced
            # or was already acknowledged by the heartbeat.
            pass
        raise
    except Exception:
        session.rollback()
        try:
            finish_processing_attempt(
                session,
                attempt_id=claim.attempt_id,
                worker_identity=worker_identity,
                outcome="failed",
                failure_code="INTERPRETATION_PROCESSING_FAILED",
            )
        except Exception:
            pass
        raise InterpretationProcessingError("INTERPRETATION_PROCESSING_FAILED") from None
