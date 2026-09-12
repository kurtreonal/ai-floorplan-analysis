"""Database-independent U13 worker checks; not real-model acceptance evidence."""

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services import interpretation_processing_service as service
from app.workers import interpretation_worker as worker


def test_demo_provider_is_explicit_and_detector_is_callable():
    assert service.PROVIDER == "demo_cv_baseline"
    assert callable(service.interpret_floor_plan_demo)


@pytest.mark.parametrize("job_id", [None, 7])
def test_poll_dispatches_only_a_queued_job_and_preserves_configuration(monkeypatch, job_id):
    stop = threading.Event()
    factory = MagicMock()
    session = factory.return_value.__enter__.return_value
    settings = object()
    process = MagicMock(return_value=SimpleNamespace(candidate_run_id="a" * 32))
    monkeypatch.setattr(worker, "_next_queued_job_id", lambda _: job_id)
    monkeypatch.setattr(worker, "process_interpretation_job", process)
    monkeypatch.setattr(stop, "wait", lambda _: stop.set())
    worker.run_interpretation_worker(
        stop_event=stop, worker_identity="test-worker", session_factory=factory,
        settings=settings,
    )
    if job_id is None:
        process.assert_not_called()
    else:
        process.assert_called_once_with(
            session, job_id=7, worker_identity="test-worker", settings=settings,
        )


def test_shutdown_before_poll_never_opens_a_session():
    stop = threading.Event()
    stop.set()
    factory = MagicMock()
    worker.run_interpretation_worker(
        stop_event=stop, worker_identity="test-worker", session_factory=factory,
        settings=object(),
    )
    factory.assert_not_called()


@pytest.mark.parametrize("error", [
    service.InterpretationProcessingError("MODEL_UNAVAILABLE"),
    RuntimeError("private diagnostic must not be printed"),
])
def test_worker_errors_are_sanitized_and_polling_resumes(monkeypatch, capsys, error):
    stop = threading.Event()
    factory = MagicMock()
    process = MagicMock(side_effect=[error, SimpleNamespace(candidate_run_id="b" * 32)])
    monkeypatch.setattr(worker, "_next_queued_job_id", lambda _: 7)
    monkeypatch.setattr(worker, "process_interpretation_job", process)
    monkeypatch.setattr(stop, "wait", lambda _: stop.set() if process.call_count == 2 else None)
    worker.run_interpretation_worker(
        stop_event=stop, worker_identity="test-worker", session_factory=factory,
        settings=object(),
    )
    output = capsys.readouterr().out
    assert "private diagnostic" not in output
    assert "status=completed" in output
    assert process.call_count == 2


def test_claim_rejection_prevents_artifact_or_inference_work(monkeypatch):
    from app.services.processing_execution_service import ProcessingExecutionError
    claim = MagicMock(side_effect=ProcessingExecutionError("PROCESSING_JOB_ALREADY_CLAIMED"))
    prepare = MagicMock()
    detector = MagicMock()
    monkeypatch.setattr(service, "claim_processing_job", claim)
    monkeypatch.setattr(service, "_registered_artifact", prepare)
    monkeypatch.setattr(service, "interpret_floor_plan_demo", detector)
    with pytest.raises(service.InterpretationProcessingError) as error:
        service.process_interpretation_job(
            MagicMock(), job_id=7, worker_identity="second-worker", settings=object(),
        )
    assert error.value.code == "PROCESSING_JOB_ALREADY_CLAIMED"
    prepare.assert_not_called()
    detector.assert_not_called()


@pytest.fixture
def fenced_context(monkeypatch):
    from datetime import datetime, timedelta, UTC
    session = MagicMock()
    claim = SimpleNamespace(job_id=7, attempt_id=9)
    attempt = SimpleNamespace(
        processing_job_id=7, worker_identity="test-worker", status="active",
        active_marker=True, lease_expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=60),
    )
    monkeypatch.setattr(service, "lock_processing_job", lambda *a, **k: SimpleNamespace(status="processing"))
    monkeypatch.setattr(service, "lock_attempt", lambda *a, **k: attempt)
    monkeypatch.setattr(service, "find_cancellation", lambda *a, **k: None)
    monkeypatch.setattr(service, "find_by_processing_job", lambda *a, **k: None)
    add = MagicMock(side_effect=lambda session, run: run)
    finish = MagicMock()
    monkeypatch.setattr(service, "add_run", add)
    monkeypatch.setattr(service, "finish_processing_attempt", finish)
    return session, claim, attempt, add, finish


@pytest.mark.parametrize("failure", ["expired", "replaced", "cancelled", "inactive"])
def test_final_write_fence_rejects_late_output(monkeypatch, fenced_context, failure):
    from datetime import datetime
    session, claim, attempt, add, finish = fenced_context
    if failure == "expired":
        attempt.lease_expires_at = datetime(2000, 1, 1)
    elif failure == "replaced":
        attempt.worker_identity = "replacement-worker"
    elif failure == "inactive":
        attempt.active_marker = None
    else:
        monkeypatch.setattr(service, "find_cancellation", lambda *a, **k: object())
    with pytest.raises(service.InterpretationProcessingError):
        service._persist_fenced_run(session, claim=claim, worker_identity="test-worker", run=object())
    add.assert_not_called()
    finish.assert_not_called()
    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_persistence_failure_does_not_acknowledge_success(fenced_context):
    session, claim, attempt, add, finish = fenced_context
    add.side_effect = RuntimeError("simulated database failure")
    with pytest.raises(RuntimeError):
        service._persist_fenced_run(session, claim=claim, worker_identity="test-worker", run=object())
    finish.assert_not_called()
    session.rollback.assert_called_once()


def test_replay_reuses_existing_run_without_duplicate_write(monkeypatch, fenced_context):
    session, claim, attempt, add, finish = fenced_context
    existing = SimpleNamespace(provider=service.PROVIDER)
    monkeypatch.setattr(service, "find_by_processing_job", lambda *a, **k: existing)
    assert service._persist_fenced_run(
        session, claim=claim, worker_identity="test-worker", run=object(),
    ) is existing
    add.assert_not_called()
    finish.assert_called_once_with(session, attempt_id=9, worker_identity="test-worker", outcome="succeeded")
    session.commit.assert_not_called()  # The real PRE9 finish owns the atomic commit.


def test_actual_demo_pixels_produce_honest_validated_provenance(monkeypatch):
    """Real CV and schema, fake database; deliberately not a persisted-E2E claim."""
    from hashlib import sha256
    from io import BytesIO
    import cv2
    import numpy as np
    from PIL import Image
    from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationCandidate

    image = np.full((300, 400, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (50, 40), (350, 260), (0, 0, 0), 5)
    buffer = BytesIO()
    Image.fromarray(image).save(buffer, format="PNG")
    content = buffer.getvalue()
    digest = sha256(content).hexdigest()
    session = MagicMock()
    claim = SimpleNamespace(job_id=7, attempt_id=9)
    monkeypatch.setattr(service, "claim_processing_job", lambda *a, **k: claim)
    monkeypatch.setattr(service, "find_by_processing_job", lambda *a, **k: None)
    monkeypatch.setattr(service, "_context", lambda *a, **k: (
        SimpleNamespace(id=7), SimpleNamespace(id=2),
        SimpleNamespace(id=3, original_sha256=digest), SimpleNamespace(id=4, page_number=1),
    ))
    monkeypatch.setattr(service, "_registered_artifact", lambda *a, **k: SimpleNamespace(
        content=content, record=SimpleNamespace(id=5, sha256=digest, pixel_width=400, pixel_height=300),
    ))
    stages = []
    monkeypatch.setattr(service, "_heartbeat", lambda *a, **k: stages.append(k["stage"]))
    persist = MagicMock(side_effect=lambda session, **kw: kw["run"])
    monkeypatch.setattr(service, "_persist_fenced_run", persist)
    run = service.process_interpretation_job(
        session, job_id=7, worker_identity="test-worker", settings=object(),
    )
    candidate = FloorPlanInterpretationCandidate.model_validate_json(run.candidate_json)
    assert run.provider == "demo_cv_baseline"
    assert candidate.provenance.model_release_id == "demo_cv_baseline"
    assert candidate.provenance.base_model_revision.startswith("opencv-")
    assert run.candidate_sha256 == sha256(run.candidate_json.encode()).hexdigest()
    assert sha256(content).hexdigest() == digest
    assert stages == ["source_preparation", "normalization", "geometry_evidence", "symbol_evidence", "persistence"]
    persist.assert_called_once()
