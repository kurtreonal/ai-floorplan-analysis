"""U14 release lifecycle tests; all evidence is synthetic and non-release."""

import hashlib
import json

from sqlalchemy import BigInteger, create_engine, event, select
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Base, FloorPlanPage, FloorPlanSource, InterpretationRelease, ProcessingJob
from app.services.interpretation_release_service import (
    InterpretationReleaseError,
    PromotionEvidence,
    current_runtime_release,
    build_shadow_report,
    promote_release,
    record_shadow_result,
    register_release,
    rollback_release,
)
from app.services.interpretation_job_configuration_service import (
    InterpretationConfigurationError,
    pin_job_configuration,
)
from app.services.interpretation_page_outcome_service import configure_page_outcomes


@compiles(BigInteger, "sqlite")
def _sqlite_bigint_autoincrement(_type, _compiler, **_kwargs):
    return "INTEGER"


def _session():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _register_sqlite_compat(dbapi_connection, _connection_record):
        dbapi_connection.create_collation("utf8mb4_bin", lambda left, right: (left > right) - (left < right))
        dbapi_connection.create_collation("ascii_bin", lambda left, right: (left > right) - (left < right))
        dbapi_connection.create_function("CHAR_LENGTH", 1, lambda value: len(value) if value is not None else None)

    Base.metadata.create_all(engine)
    return engine, Session(engine)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _evidence(release, *, decision="decision-1", target=None, **overrides):
    values = dict(
        manifest_sha256=release.manifest_sha256,
        evaluation_report_sha256=release.evaluation_report_sha256,
        signed_decision_ref=decision,
        signed_decision_sha256=_hash(decision),
        metrics_passed=True,
        schema_passed=True,
        privacy_passed=True,
        resource_passed=True,
        rollback_target_release_id=target,
    )
    values.update(overrides)
    return PromotionEvidence(**values)


def test_shadow_report_hash_is_persisted_and_bad_hash_is_rejected():
    engine, session = _session()
    try:
        release = register_release(
            session,
            release_id="u14-test-1",
            provider="local_vlm_gateway",
            model_revision="rev-1",
            manifest_sha256="a" * 64,
        )
        report = {"evaluated_records": 0, "status": "synthetic-only"}
        bad = _hash(json.dumps(report))
        try:
            record_shadow_result(session, release_id=release.release_id, report=report, evaluation_report_sha256=bad)
        except InterpretationReleaseError as error:
            assert error.code == "SHADOW_REPORT_HASH_MISMATCH"
        else:
            raise AssertionError("unverified shadow hash was accepted")
        saved = record_shadow_result(session, release_id=release.release_id, report=report)
        assert saved.status == "shadow"
        assert saved.shadow_report_sha256 == saved.evaluation_report_sha256
        session.commit()
    finally:
        session.close()
        engine.dispose()


def test_shadow_comparison_discloses_missing_legacy_weights_without_fabricating_metrics():
    unavailable = build_shadow_report(vlm_result={"schema_valid_rate": 1.0}, legacy_result=None)
    assert unavailable["status"] == "legacy_unavailable"
    assert unavailable["legacy"] is None
    assert unavailable["discrepancies"] == {}
    compared = build_shadow_report(
        vlm_result={"schema_valid_rate": 1.0, "symbol_f1": 0.75},
        legacy_result={"schema_valid_rate": 0.9, "symbol_f1": 0.5},
    )
    assert compared["status"] == "compared"
    assert compared["discrepancies"]["symbol_f1"]["absolute_delta"] == 0.25


def test_promotion_requires_all_gates_and_signed_decision():
    engine, session = _session()
    try:
        release = register_release(
            session,
            release_id="u14-test-2",
            provider="local_vlm_gateway",
            model_revision="rev-2",
            manifest_sha256="b" * 64,
        )
        record_shadow_result(session, release_id=release.release_id, report={"metrics": "synthetic"})
        try:
            promote_release(session, release_id=release.release_id, evidence=_evidence(release, decision=""))
        except InterpretationReleaseError as error:
            assert error.code == "SIGNED_RELEASE_DECISION_REQUIRED"
        else:
            raise AssertionError("promotion without signed decision was accepted")
        try:
            promote_release(session, release_id=release.release_id, evidence=_evidence(release, metrics_passed=False))
        except InterpretationReleaseError as error:
            assert error.code == "RELEASE_GATES_FAILED"
        else:
            raise AssertionError("failed metric gate was accepted")
        promoted = promote_release(session, release_id=release.release_id, evidence=_evidence(release))
        assert promoted.status == "active"
        assert current_runtime_release(session).release_id == release.release_id
        session.commit()
    finally:
        session.close()
        engine.dispose()


def test_promotion_adopts_new_jobs_and_rollback_restores_retained_release_or_fences_manual_review():
    engine, session = _session()
    try:
        first = register_release(
            session,
            release_id="u14-test-3a",
            provider="local_vlm_gateway",
            model_revision="rev-a",
            manifest_sha256="c" * 64,
        )
        record_shadow_result(session, release_id=first.release_id, report={"candidate": "a"})
        promote_release(session, release_id=first.release_id, evidence=_evidence(first, decision="decision-a"))
        second = register_release(
            session,
            release_id="u14-test-3b",
            provider="local_vlm_gateway",
            model_revision="rev-b",
            manifest_sha256="d" * 64,
        )
        record_shadow_result(session, release_id=second.release_id, report={"candidate": "b"})
        promote_release(session, release_id=second.release_id, evidence=_evidence(second, decision="decision-b"))
        assert current_runtime_release(session).release_id == second.release_id
        # The old release remains readable and is the explicit rollback target.
        assert session.scalar(select(InterpretationRelease).where(InterpretationRelease.release_id == first.release_id)).status == "retired"
        rollback_release(session, release_id=second.release_id, reason="synthetic bad artifact", target_release_id=first.release_id)
        assert current_runtime_release(session).release_id == first.release_id
        rollback_release(session, release_id=first.release_id, reason="synthetic missing artifact")
        assert current_runtime_release(session).status == "manual_review"
        assert session.scalar(select(InterpretationRelease).where(InterpretationRelease.release_id == second.release_id)).status == "rolled_back"
        session.commit()
    finally:
        session.close()
        engine.dispose()


def test_active_release_is_pinned_for_new_jobs_but_inflight_jobs_cannot_switch():
    engine, session = _session()
    try:
        first = register_release(
            session,
            release_id="u14-test-pin-a",
            provider="local_vlm_gateway",
            model_revision="rev-a",
            manifest_sha256="e" * 64,
        )
        record_shadow_result(session, release_id=first.release_id, report={"candidate": "a"})
        promote_release(session, release_id=first.release_id, evidence=_evidence(first, decision="decision-pin-a"))
        source = FloorPlanSource(id=10, floor_plan_id=10, original_sha256="f" * 64)
        job_one = ProcessingJob(id=10, floor_plan_id=10, job_type="floor_plan_analysis")
        page_one = FloorPlanPage(id=10, floor_plan_source_id=10, page_number=1)
        session.add_all([source, job_one, page_one])
        session.flush()
        configure_page_outcomes(session, processing_job=job_one, page_numbers=[1])
        settings = Settings(_env_file=None)
        pinned = pin_job_configuration(session, processing_job=job_one, settings=settings)
        assert pinned.model_release_id == first.release_id

        second = register_release(
            session,
            release_id="u14-test-pin-b",
            provider="local_vlm_gateway",
            model_revision="rev-b",
            manifest_sha256="1" * 64,
        )
        record_shadow_result(session, release_id=second.release_id, report={"candidate": "b"})
        promote_release(session, release_id=second.release_id, evidence=_evidence(second, decision="decision-pin-b"))
        try:
            pin_job_configuration(session, processing_job=job_one, settings=settings)
        except InterpretationConfigurationError as error:
            assert error.code == "PROCESSING_CONFIGURATION_CONFLICT"
        else:
            raise AssertionError("in-flight job changed release")

        job_two = ProcessingJob(id=11, floor_plan_id=10, job_type="floor_plan_analysis")
        page_two = FloorPlanPage(id=11, floor_plan_source_id=10, page_number=2)
        session.add_all([job_two, page_two])
        session.flush()
        configure_page_outcomes(session, processing_job=job_two, page_numbers=[2])
        assert pin_job_configuration(session, processing_job=job_two, settings=settings).model_release_id == second.release_id
    finally:
        session.close()
        engine.dispose()
