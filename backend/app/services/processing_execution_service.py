from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from re import fullmatch

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import ProcessingJobAttempt, ProcessingJobCancellation, User
from app.repositories.processing_execution_repository import (
    active_attempt,
    add_record,
    find_attempt,
    find_cancellation,
    lock_attempt,
    lock_processing_job,
    maximum_attempt_number,
)
from app.repositories.processing_job_repository import find_processing_job_by_id_and_owner


MAXIMUM_ATTEMPTS = 3
MINIMUM_LEASE_SECONDS = 15
MAXIMUM_LEASE_SECONDS = 900
MAXIMUM_WORKER_IDENTITY_LENGTH = 128
STAGE_PROGRESS = {
    "claimed": 0,
    "source_preparation": 10,
    "normalization": 30,
    "geometry_evidence": 55,
    "symbol_evidence": 75,
    "persistence": 90,
    "completed": 100,
}
TERMINAL_JOB_STATUSES = {"completed", "failed", "cancelled"}
SAFE_RETRY_EXHAUSTED_MESSAGE = "Floor-plan processing exhausted its retry limit."


class ProcessingExecutionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("The processing execution operation could not be completed.")


@dataclass(frozen=True)
class ClaimResult:
    attempt_id: int
    job_id: int
    attempt_number: int
    worker_identity: str
    lease_expires_at: datetime


@dataclass(frozen=True)
class CancellationResult:
    job_id: int
    status: str
    mode: str


def _fail(code: str) -> None:
    raise ProcessingExecutionError(code)


def _now(value: datetime | None) -> datetime:
    value = value or datetime.now(UTC).replace(tzinfo=None)
    if type(value) is not datetime or value.tzinfo is not None:
        _fail("INVALID_EXECUTION_TIME")
    return value


def _identifier(value: int) -> int:
    if type(value) is not int or value <= 0:
        _fail("INVALID_IDENTIFIER")
    return value


def _lease_seconds(value: int) -> int:
    if type(value) is not int or not MINIMUM_LEASE_SECONDS <= value <= MAXIMUM_LEASE_SECONDS:
        _fail("INVALID_LEASE")
    return value


def _failure_code(value: str | None, *, required: bool) -> str | None:
    if not required:
        if value is not None:
            _fail("UNEXPECTED_FAILURE_CODE")
        return None
    if type(value) is not str or fullmatch(r"[A-Z][A-Z0-9_]{0,63}", value) is None:
        _fail("INVALID_FAILURE_CODE")
    return value


def _worker_identity(value: str) -> str:
    if type(value) is not str or not value or len(value) > MAXIMUM_WORKER_IDENTITY_LENGTH:
        _fail("INVALID_WORKER_IDENTITY")
    if not all(character.isascii() and (character.isalnum() or character in "._:-") for character in value):
        _fail("INVALID_WORKER_IDENTITY")
    return value


def _attempt_result(attempt: ProcessingJobAttempt) -> ClaimResult:
    return ClaimResult(
        attempt_id=attempt.id,
        job_id=attempt.processing_job_id,
        attempt_number=attempt.attempt_number,
        worker_identity=attempt.worker_identity,
        lease_expires_at=attempt.lease_expires_at,
    )


def _expire_active_attempt(
    database_session: Session,
    *,
    job,
    attempt: ProcessingJobAttempt,
    now: datetime,
) -> None:
    attempt.status = "lease_expired"
    attempt.active_marker = None
    attempt.finished_at = now
    attempt.failure_code = "LEASE_EXPIRED"
    if attempt.attempt_number >= MAXIMUM_ATTEMPTS:
        job.status = "failed"
        job.error_message = SAFE_RETRY_EXHAUSTED_MESSAGE
    else:
        job.status = "queued"
        job.error_message = None
    database_session.flush()


def claim_processing_job(
    database_session: Session,
    *,
    job_id: int,
    worker_identity: str,
    lease_seconds: int,
    now: datetime | None = None,
) -> ClaimResult:
    job_id = _identifier(job_id)
    worker_identity = _worker_identity(worker_identity)
    lease_seconds = _lease_seconds(lease_seconds)
    now = _now(now)
    try:
        job = lock_processing_job(database_session, job_id=job_id)
        if job is None:
            _fail("PROCESSING_JOB_NOT_FOUND")
        attempt = active_attempt(database_session, job_id=job.id)
        if attempt is not None:
            if attempt.lease_expires_at > now:
                _fail("PROCESSING_JOB_ALREADY_CLAIMED")
            _expire_active_attempt(database_session, job=job, attempt=attempt, now=now)
        elif job.status == "processing":
            _fail("LEGACY_PROCESSING_JOB_REQUIRES_RECOVERY")
        if job.status in TERMINAL_JOB_STATUSES:
            database_session.commit()
            _fail("PROCESSING_JOB_NOT_CLAIMABLE")
        if find_cancellation(database_session, job_id=job.id) is not None:
            job.status = "cancelled"
            database_session.flush()
            database_session.commit()
            _fail("PROCESSING_JOB_CANCELLED")
        attempt_number = maximum_attempt_number(database_session, job_id=job.id) + 1
        if attempt_number > MAXIMUM_ATTEMPTS:
            job.status = "failed"
            job.error_message = SAFE_RETRY_EXHAUSTED_MESSAGE
            database_session.flush()
            database_session.commit()
            _fail("PROCESSING_RETRY_EXHAUSTED")
        attempt = add_record(
            database_session,
            ProcessingJobAttempt(
                processing_job_id=job.id,
                attempt_number=attempt_number,
                worker_identity=worker_identity,
                status="active",
                stage="claimed",
                active_marker=True,
                heartbeat_at=now,
                lease_expires_at=now + timedelta(seconds=lease_seconds),
            ),
        )
        job.status = "processing"
        job.progress = STAGE_PROGRESS["claimed"]
        job.error_message = None
        database_session.commit()
        return _attempt_result(attempt)
    except ProcessingExecutionError:
        database_session.rollback()
        raise
    except SQLAlchemyError:
        database_session.rollback()
        _fail("PROCESSING_EXECUTION_FAILED")


def heartbeat_processing_attempt(
    database_session: Session,
    *,
    attempt_id: int,
    worker_identity: str,
    stage: str,
    lease_seconds: int,
    now: datetime | None = None,
) -> bool:
    attempt_id = _identifier(attempt_id)
    worker_identity = _worker_identity(worker_identity)
    lease_seconds = _lease_seconds(lease_seconds)
    now = _now(now)
    if stage not in STAGE_PROGRESS or stage == "completed":
        _fail("INVALID_PROCESSING_STAGE")
    try:
        attempt_reference = find_attempt(database_session, attempt_id=attempt_id)
        if attempt_reference is None or attempt_reference.worker_identity != worker_identity:
            _fail("PROCESSING_ATTEMPT_NOT_FOUND")
        job = lock_processing_job(
            database_session,
            job_id=attempt_reference.processing_job_id,
        )
        attempt = lock_attempt(database_session, attempt_id=attempt_id)
        if attempt is None or attempt.worker_identity != worker_identity:
            _fail("PROCESSING_ATTEMPT_NOT_FOUND")
        if attempt.active_marker is not True or attempt.status != "active":
            _fail("PROCESSING_ATTEMPT_NOT_ACTIVE")
        if attempt.lease_expires_at <= now:
            _expire_active_attempt(database_session, job=job, attempt=attempt, now=now)
            database_session.commit()
            _fail("PROCESSING_LEASE_EXPIRED")
        if STAGE_PROGRESS[stage] < STAGE_PROGRESS[attempt.stage]:
            _fail("PROCESSING_STAGE_REGRESSION")
        attempt.stage = stage
        attempt.heartbeat_at = now
        attempt.lease_expires_at = now + timedelta(seconds=lease_seconds)
        job.progress = STAGE_PROGRESS[stage]
        cancellation_requested = find_cancellation(database_session, job_id=job.id) is not None
        database_session.commit()
        return cancellation_requested
    except ProcessingExecutionError:
        if database_session.in_transaction():
            database_session.rollback()
        raise
    except SQLAlchemyError:
        database_session.rollback()
        _fail("PROCESSING_EXECUTION_FAILED")


def finish_processing_attempt(
    database_session: Session,
    *,
    attempt_id: int,
    worker_identity: str,
    outcome: str,
    failure_code: str | None = None,
    now: datetime | None = None,
) -> None:
    attempt_id = _identifier(attempt_id)
    worker_identity = _worker_identity(worker_identity)
    now = _now(now)
    if outcome not in {"succeeded", "failed", "cancelled"}:
        _fail("INVALID_PROCESSING_OUTCOME")
    failure_code = _failure_code(failure_code, required=outcome == "failed")
    try:
        attempt_reference = find_attempt(database_session, attempt_id=attempt_id)
        if attempt_reference is None or attempt_reference.worker_identity != worker_identity:
            _fail("PROCESSING_ATTEMPT_NOT_FOUND")
        job = lock_processing_job(
            database_session,
            job_id=attempt_reference.processing_job_id,
        )
        attempt = lock_attempt(database_session, attempt_id=attempt_id)
        if attempt is None or attempt.worker_identity != worker_identity:
            _fail("PROCESSING_ATTEMPT_NOT_FOUND")
        if attempt.active_marker is not True or attempt.status != "active":
            _fail("PROCESSING_ATTEMPT_NOT_ACTIVE")
        cancellation = find_cancellation(database_session, job_id=job.id)
        if outcome == "cancelled" and cancellation is None:
            _fail("CANCELLATION_NOT_REQUESTED")
        attempt.status = outcome
        attempt.active_marker = None
        attempt.finished_at = now
        attempt.failure_code = failure_code if outcome == "failed" else None
        if outcome == "succeeded":
            attempt.stage = "completed"
            job.status = "completed"
            job.progress = 100
            job.error_message = None
        elif outcome == "cancelled":
            job.status = "cancelled"
            cancellation.resolved_at = now
        elif attempt.attempt_number < MAXIMUM_ATTEMPTS:
            job.status = "queued"
            job.error_message = None
        else:
            job.status = "failed"
            job.error_message = SAFE_RETRY_EXHAUSTED_MESSAGE
        database_session.commit()
    except ProcessingExecutionError:
        database_session.rollback()
        raise
    except SQLAlchemyError:
        database_session.rollback()
        _fail("PROCESSING_EXECUTION_FAILED")


def request_processing_cancellation(
    database_session: Session,
    *,
    current_user: User,
    job_id: int,
) -> CancellationResult:
    job_id = _identifier(job_id)
    timestamp = datetime.now(UTC).replace(tzinfo=None)
    try:
        accessible = find_processing_job_by_id_and_owner(
            database_session,
            job_id=job_id,
            owner_id=current_user.id,
        )
        if accessible is None:
            _fail("PROCESSING_JOB_NOT_FOUND")
        job = lock_processing_job(database_session, job_id=job_id)
        existing = find_cancellation(database_session, job_id=job.id)
        if existing is not None:
            return CancellationResult(job.id, job.status, existing.mode)
        if job.status in TERMINAL_JOB_STATUSES:
            _fail("PROCESSING_JOB_NOT_CANCELLABLE")
        mode = "queued_cancelled" if job.status == "queued" else "cooperative_requested"
        add_record(
            database_session,
            ProcessingJobCancellation(
                processing_job_id=job.id,
                requested_by_user_id=current_user.id,
                mode=mode,
                requested_at=timestamp,
                resolved_at=timestamp if mode == "queued_cancelled" else None,
            ),
        )
        if mode == "queued_cancelled":
            job.status = "cancelled"
        database_session.commit()
        return CancellationResult(job.id, job.status, mode)
    except ProcessingExecutionError:
        database_session.rollback()
        raise
    except SQLAlchemyError:
        database_session.rollback()
        _fail("PROCESSING_EXECUTION_FAILED")


def recover_legacy_processing_job(database_session: Session, *, job_id: int) -> None:
    job_id = _identifier(job_id)
    try:
        job = lock_processing_job(database_session, job_id=job_id)
        if job is None:
            _fail("PROCESSING_JOB_NOT_FOUND")
        if job.status != "processing" or active_attempt(database_session, job_id=job.id) is not None:
            _fail("LEGACY_RECOVERY_NOT_APPLICABLE")
        job.status = "queued"
        job.error_message = None
        database_session.commit()
    except ProcessingExecutionError:
        database_session.rollback()
        raise
    except SQLAlchemyError:
        database_session.rollback()
        _fail("PROCESSING_EXECUTION_FAILED")
