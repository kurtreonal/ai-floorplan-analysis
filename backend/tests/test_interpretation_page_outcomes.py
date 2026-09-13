"""U13 page selection/outcome ledger tests; no real source data is used."""

from sqlalchemy import BigInteger, create_engine, event, select
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.models import Base, FloorPlanPage, FloorPlanSource, ProcessingJob
from app.core.config import Settings
from app.services.interpretation_job_configuration_service import (
    InterpretationConfigurationError,
    pin_job_configuration,
)
from app.services.interpretation_page_outcome_service import (
    PageSelectionError,
    configure_page_outcomes,
    next_selected_page,
    requeue_retryable_pages,
)
from app.services.interpretation_processing_service import page_outcome_failure_status


@compiles(BigInteger, "sqlite")
def _sqlite_bigint_autoincrement(_type, _compiler, **_kwargs):
    return "INTEGER"


def _session_with_pages(page_count=3):
    engine = create_engine("sqlite:///:memory:")
    @event.listens_for(engine, "connect")
    def _register_mysql_collation(dbapi_connection, _connection_record):
        dbapi_connection.create_collation("utf8mb4_bin", lambda left, right: (left > right) - (left < right))
        dbapi_connection.create_collation("ascii_bin", lambda left, right: (left > right) - (left < right))
        dbapi_connection.create_function("CHAR_LENGTH", 1, lambda value: len(value) if value is not None else None)
    Base.metadata.create_all(engine)
    session = Session(engine)
    source = FloorPlanSource(id=1, floor_plan_id=1, original_sha256="a" * 64)
    job = ProcessingJob(id=1, floor_plan_id=1, job_type="floor_plan_analysis")
    session.add_all([source, job])
    session.flush()
    session.add_all([
        FloorPlanPage(id=index, floor_plan_source_id=source.id, page_number=index)
        for index in range(1, page_count + 1)
    ])
    session.commit()
    return engine, session, job


def test_explicit_multipage_selection_persists_skipped_pages_and_order():
    engine, session, job = _session_with_pages()
    try:
        rows = configure_page_outcomes(session, processing_job=job, page_numbers=[1, 3])
        assert [(row.page_number, row.selection_state, row.status) for row in rows] == [
            (1, "selected", "queued"),
            (2, "skipped", "skipped"),
            (3, "selected", "queued"),
        ]
        assert next_selected_page(session, processing_job_id=job.id).page_number == 1
    finally:
        session.close()
        engine.dispose()


def test_selection_rejects_duplicates_unknown_pages_and_rewrite():
    engine, session, job = _session_with_pages(2)
    try:
        for selection, code in (([1, 1], "PROCESSING_PAGE_SELECTION_INVALID"),
                                ([3], "PROCESSING_PAGE_NOT_FOUND")):
            try:
                configure_page_outcomes(session, processing_job=job, page_numbers=selection)
            except PageSelectionError as error:
                assert error.code == code
            else:
                raise AssertionError("invalid selection unexpectedly accepted")
        configure_page_outcomes(session, processing_job=job, page_numbers=[1])
        try:
            configure_page_outcomes(session, processing_job=job, page_numbers=[2])
        except PageSelectionError as error:
            assert error.code == "PROCESSING_PAGE_SELECTION_IMMUTABLE"
        else:
            raise AssertionError("selection rewrite unexpectedly accepted")
    finally:
        session.close()
        engine.dispose()


def test_retry_requeues_failed_timeout_and_crash_pages_without_touching_completed():
    engine, session, job = _session_with_pages(4)
    try:
        rows = configure_page_outcomes(session, processing_job=job, page_numbers=[1, 2, 3])
        rows[0].status = "completed"
        rows[1].status = "failed"
        rows[1].progress = 100
        rows[2].status = "processing"
        rows[2].progress = 55
        rows[2].failure_code = "MODEL_TIMEOUT"
        session.commit()
        assert requeue_retryable_pages(session, processing_job_id=job.id) == 2
        session.commit()
        values = session.scalars(
            select(type(rows[0])).order_by(type(rows[0]).page_number)
        ).all()
        assert [(row.status, row.progress) for row in values] == [
            ("completed", 0), ("queued", 0), ("queued", 0), ("skipped", 100)
        ]
    finally:
        session.close()
        engine.dispose()


def test_failure_outcomes_distinguish_cancellation_timeout_and_failure():
    assert page_outcome_failure_status("PROCESSING_CANCELLED") == "cancelled"
    assert page_outcome_failure_status("MODEL_TIMEOUT") == "timeout"
    assert page_outcome_failure_status("MODEL_UNAVAILABLE") == "failed"
    assert page_outcome_failure_status("INTERPRETATION_PROCESSING_FAILED") == "failed"


def test_job_provider_configuration_is_pinned_and_cannot_switch_mid_job():
    engine, session, job = _session_with_pages(1)
    try:
        configure_page_outcomes(session, processing_job=job, page_numbers=[1])
        settings = Settings(_env_file=None)
        first = pin_job_configuration(session, processing_job=job, settings=settings)
        session.commit()
        second = pin_job_configuration(session, processing_job=job, settings=settings)
        assert second.id == first.id
        changed = Settings(
            _env_file=None,
            local_vlm_runtime_url="http://127.0.0.1:8081",
        )
        try:
            pin_job_configuration(session, processing_job=job, settings=changed)
        except InterpretationConfigurationError as error:
            assert error.code == "PROCESSING_CONFIGURATION_CONFLICT"
        else:
            raise AssertionError("provider configuration changed mid-job")
    finally:
        session.close()
        engine.dispose()
