"""Run the actual interpretation worker through the isolated MySQL fixture."""
from tests import test_demo_processing_worker as fixture
from app.services.interpretation_processing_service import process_interpretation_job


class InterpretationProcessingDatabaseTests(fixture.DemoProcessingWorkerTests):
    process = staticmethod(process_interpretation_job)


class InterpretationExpiredLeaseDatabaseTests(fixture.DemoProcessingWorkerTests):
    expected_attempts = 2

    def process(self, session, **kwargs):
        from datetime import datetime
        from unittest.mock import patch
        from sqlalchemy import select, func
        from app.models import FloorPlanInterpretationRun, ProcessingJobAttempt
        from app.services import interpretation_processing_service as service

        original = service._persist_fenced_run

        def expire_before_write(session, *, claim, worker_identity, run):
            attempt = session.get(ProcessingJobAttempt, claim.attempt_id)
            attempt.lease_expires_at = datetime(2000, 1, 1)
            session.commit()
            return original(session, claim=claim, worker_identity=worker_identity, run=run)

        with patch.object(service, "_persist_fenced_run", side_effect=expire_before_write):
            with self.assertRaises(service.InterpretationProcessingError) as error:
                service.process_interpretation_job(session, **kwargs)
        self.assertEqual(error.exception.code, "PROCESSING_LEASE_EXPIRED")
        self.assertEqual(session.scalar(select(func.count()).select_from(FloorPlanInterpretationRun).where(
            FloorPlanInterpretationRun.processing_job_id == kwargs["job_id"],
        )), 0)
        session.rollback()
        # A fresh attempt reuses only trusted artifacts and publishes one run.
        return service.process_interpretation_job(session, **kwargs)


class InterpretationMemoryFailureDatabaseTests(fixture.DemoProcessingWorkerTests):
    expected_attempts = 2

    def process(self, session, **kwargs):
        from unittest.mock import patch
        from sqlalchemy import select, func
        from app.models import FloorPlanInterpretationRun
        from app.services import interpretation_processing_service as service

        with patch.object(service, "interpret_floor_plan_demo", side_effect=MemoryError("synthetic failure")):
            with self.assertRaises(service.InterpretationProcessingError) as error:
                service.process_interpretation_job(session, **kwargs)
        self.assertEqual(error.exception.code, "INTERPRETATION_PROCESSING_FAILED")
        self.assertEqual(session.scalar(select(func.count()).select_from(FloorPlanInterpretationRun).where(
            FloorPlanInterpretationRun.processing_job_id == kwargs["job_id"],
        )), 0)
        session.rollback()
        return service.process_interpretation_job(session, **kwargs)


class InterpretationCrashRecoveryDatabaseTests(fixture.DemoProcessingWorkerTests):
    expected_attempts = 2

    def process(self, session, **kwargs):
        from datetime import datetime
        from unittest.mock import patch
        from sqlalchemy import select
        from app.models import ProcessingJobAttempt
        from app.services import interpretation_processing_service as service
        from app.workers.interpretation_worker import _next_queued_job_id

        # SystemExit deliberately bypasses the service's recoverable Exception
        # path, modeling loss of the process after its durable claim/heartbeat.
        with patch.object(service, "_registered_artifact", side_effect=SystemExit()):
            with self.assertRaises(SystemExit):
                service.process_interpretation_job(session, **kwargs)
        session.rollback()
        self.assertIsNone(_next_queued_job_id(session))  # Live lease is not stolen.
        attempt = session.scalar(select(ProcessingJobAttempt).where(
            ProcessingJobAttempt.processing_job_id == kwargs["job_id"],
            ProcessingJobAttempt.active_marker.is_(True),
        ))
        attempt.lease_expires_at = datetime(2000, 1, 1)
        session.commit()
        self.assertEqual(_next_queued_job_id(session), kwargs["job_id"])
        return service.process_interpretation_job(session, **kwargs)
