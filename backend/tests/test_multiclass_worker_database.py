"""Run only with scripts/run_isolated_backend_tests.py; never the dev database."""
from hashlib import sha256
import json
import cv2
from datetime import datetime, timedelta, UTC
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch, MagicMock
from sqlalchemy import select

from app.ai.floor_plan_interpretation import multiclass_symbol_detector as detector
from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationCandidate
from app.models import ProcessingJob, ProcessingJobAttempt, InterpretationPageOutcome, FloorPlanInterpretationRun
from app.services.processing_execution_service import claim_processing_job
from app.services.interpretation_page_outcome_service import configure_page_outcomes
from app.services.interpretation_processing_service import process_interpretation_job
from tests.test_demo_processing_worker import DemoProcessingWorkerTests


class MulticlassWorkerDatabaseTests(DemoProcessingWorkerTests):
    expected_provider = detector.PROVIDER
    assert_page_outcome = True

    def process(self, session, **kwargs):
        from app.services import interpretation_processing_service as service
        decoded = {}
        decode_source = service._decode_rgb
        detect_wiring = service.with_automatic_wiring

        def record_pre_annotation(content):
            rgb = decode_source(content)
            self.assertFalse(rgb.flags.writeable)
            decoded['pixels'] = sha256(rgb.tobytes()).hexdigest()
            decoded['rgb'] = rgb
            return rgb

        def check_wiring_source(payload, rgb):
            self.assertIs(rgb, decoded['rgb'])
            self.assertEqual(sha256(rgb.tobytes()).hexdigest(), decoded['pixels'])
            self.assertFalse(rgb.flags.writeable)
            before = rgb.tobytes()
            result = detect_wiring(payload, rgb)
            self.assertEqual(rgb.tobytes(), before)
            return result

        job = session.get(ProcessingJob, kwargs["job_id"])
        outcomes = configure_page_outcomes(session, processing_job=job, page_numbers=[1])
        outcomes[0].provider = detector.PROVIDER
        outcomes[0].model_release_id = detector.PROVIDER
        outcomes[0].configuration_sha256 = detector.configuration_sha256()
        session.commit()
        classes = {i: (f"Fixture {i}", f"drawing:L{i}") for i in range(detector.CLASS_COUNT)}
        proposals = tuple({"bbox": (100, 120, 128, 148), "score": .8,
                           "class_id": i, "tile_origin": (0, 0)} for i in range(detector.CLASS_COUNT))
        with patch.object(detector, "verify_artifacts", return_value=classes), \
             patch.object(detector, "locate", return_value=(proposals, False)), \
             patch.object(service, '_decode_rgb', side_effect=record_pre_annotation), \
             patch.object(service, 'with_automatic_wiring', side_effect=check_wiring_source) as wiring_source:
            run = process_interpretation_job(session, **kwargs)
        wiring_source.assert_called_once()
        candidate = FloorPlanInterpretationCandidate.model_validate_json(run.candidate_json)
        self.assertEqual(candidate.provenance.model_release_id, detector.PROVIDER)
        self.assertEqual(candidate.provenance.base_model_revision,
                         f"yolo11n-warmstart-{detector.TRAINING_BASE_SHA256[:12]}")
        self.assertEqual(candidate.provenance.prompt_version, detector.PROMPT_VERSION)
        self.assertEqual(len(candidate.payload.symbols.items), detector.CLASS_COUNT)
        parameters={p.name:p.value for p in candidate.provenance.inference_parameters}
        configuration=json.loads(parameters['preprocessing-configuration'])
        self.assertEqual(configuration['resize'],'none')
        self.assertEqual(configuration['opencv'],cv2.__version__)
        self.assertEqual(parameters['symbol-configuration-sha256'],detector.configuration_sha256())
        self.assertEqual(parameters['model-class-count'],str(detector.CLASS_COUNT))
        self.assertEqual(parameters['development-profile'],detector.PROFILE)
        self.assertEqual(parameters['dataset-sha256'], detector.TRAINING_DATASET_SHA256)
        if detector.PROFILE == 'power80':
            self.assertEqual(parameters['serving-dataset-sha256'], detector.DATASET_SHA256)
            self.assertEqual(parameters['refinement-manifest-sha256'],detector.REFINEMENT_MANIFEST_SHA256)
            self.assertNotEqual(parameters['dataset-sha256'], parameters['serving-dataset-sha256'])
        else:
            self.assertNotIn('serving-dataset-sha256', parameters)
        self.assertTrue(all(s.training_legend.dataset_sha256 == detector.TRAINING_DATASET_SHA256
                            for s in candidate.payload.symbols.items))
        self.assertTrue(all(s.mapping_state == "unknown" for s in candidate.payload.symbols.items))
        self.assertTrue(all(s.catalog_class_id is None and s.ambiguity == 'ambiguous'
                            for s in candidate.payload.symbols.items))
        self.assertIn(detector.CHECKPOINT_SHA256,
                      [p.value for p in candidate.provenance.inference_parameters])
        self.assertEqual(run.candidate_sha256, sha256(run.candidate_json.encode()).hexdigest())
        return run


class MulticlassExpiredPageRecoveryDatabaseTests(MulticlassWorkerDatabaseTests):
    expected_attempts = 2

    def process(self, session, **kwargs):
        job = session.get(ProcessingJob, kwargs['job_id'])
        page = configure_page_outcomes(session, processing_job=job, page_numbers=[1])[0]
        page.provider = detector.PROVIDER
        page.model_release_id = detector.PROVIDER
        page.configuration_sha256 = detector.configuration_sha256()
        session.commit()
        claim_processing_job(session, job_id=job.id, worker_identity='interrupted-multiclass-worker',
                             lease_seconds=30, now=datetime(2000, 1, 1))
        page.status = 'processing'
        page.progress = 75
        session.commit()
        prior_autoflush = session.autoflush
        session.autoflush = False  # Match the application SessionLocal configuration.
        try:
            run = super().process(session, **kwargs)
        finally:
            session.autoflush = prior_autoflush
        attempts = session.scalars(select(ProcessingJobAttempt).where(
            ProcessingJobAttempt.processing_job_id == job.id
        ).order_by(ProcessingJobAttempt.attempt_number)).all()
        self.assertEqual(len(attempts), 2)
        self.assertEqual((attempts[0].status, attempts[0].failure_code), ('lease_expired', 'LEASE_EXPIRED'))
        self.assertEqual(attempts[1].status, 'succeeded')
        return run


class MulticlassLateFailureRecoveryDatabaseTests(MulticlassWorkerDatabaseTests):
    expected_attempts = 2
    late_failure_code = 'INTERPRETATION_PROCESSING_FAILED'

    def process(self, session, **kwargs):
        from app.services import interpretation_processing_service as service

        original = service._registered_artifact
        replaced = False
        successor = {}

        def replace_before_late_error(active_session, **artifact_kwargs):
            nonlocal replaced
            if replaced:
                return original(active_session, **artifact_kwargs)
            replaced = True
            attempt = active_session.scalar(select(ProcessingJobAttempt).where(
                ProcessingJobAttempt.processing_job_id == kwargs['job_id'],
                ProcessingJobAttempt.active_marker.is_(True),
            ))
            attempt.lease_expires_at = datetime(2000, 1, 1)
            active_session.commit()
            successor['run'] = MulticlassWorkerDatabaseTests.process(
                self, active_session, **{**kwargs, 'worker_identity': 'successor-multiclass-worker'})
            page = active_session.scalar(select(InterpretationPageOutcome).where(
                InterpretationPageOutcome.processing_job_id == kwargs['job_id']))
            successor['page'] = (page.status, page.progress, page.failure_code,
                                 page.candidate_run_id, page.source_artifact_id)
            successor['candidate'] = successor['run'].candidate_json
            if self.late_failure_code == 'INTERPRETATION_PROCESSING_FAILED':
                raise RuntimeError('Synthetic error from replaced worker')
            raise service.InterpretationProcessingError(self.late_failure_code)

        prior_autoflush = session.autoflush
        session.autoflush = False
        try:
            with patch.object(service, '_registered_artifact', side_effect=replace_before_late_error):
                with self.assertRaises(service.InterpretationProcessingError) as error:
                    MulticlassWorkerDatabaseTests.process(self, session, **kwargs)
        finally:
            session.autoflush = prior_autoflush
        self.assertEqual(error.exception.code, self.late_failure_code)
        session.expire_all()
        page = session.scalar(select(InterpretationPageOutcome).where(
            InterpretationPageOutcome.processing_job_id == kwargs['job_id']))
        self.assertEqual((page.status, page.progress, page.failure_code,
                          page.candidate_run_id, page.source_artifact_id), successor['page'])
        persisted = session.scalar(select(FloorPlanInterpretationRun).where(
            FloorPlanInterpretationRun.processing_job_id == kwargs['job_id']))
        self.assertEqual(persisted.candidate_json, successor['candidate'])
        attempts = session.scalars(select(ProcessingJobAttempt).where(
            ProcessingJobAttempt.processing_job_id == kwargs['job_id']
        ).order_by(ProcessingJobAttempt.attempt_number)).all()
        self.assertEqual([(a.status,a.failure_code) for a in attempts],
                         [('lease_expired','LEASE_EXPIRED'), ('succeeded',None)])
        return persisted


class MulticlassLateTimeoutRecoveryDatabaseTests(MulticlassLateFailureRecoveryDatabaseTests):
    late_failure_code = 'MODEL_TIMEOUT'


class MulticlassLateCancellationRecoveryDatabaseTests(MulticlassLateFailureRecoveryDatabaseTests):
    late_failure_code = 'PROCESSING_CANCELLED'


class MulticlassCurrentOwnerFailureDatabaseTests(MulticlassWorkerDatabaseTests):
    expected_attempts = 2
    expected_failure_code = 'INTERPRETATION_PROCESSING_FAILED'
    expected_page_status = 'failed'

    def process(self, session, **kwargs):
        from app.services import interpretation_processing_service as service

        error_to_raise = (RuntimeError('Synthetic current-owner error')
                          if self.expected_failure_code == 'INTERPRETATION_PROCESSING_FAILED'
                          else service.InterpretationProcessingError(self.expected_failure_code))
        with patch.object(service, '_registered_artifact', side_effect=error_to_raise):
            with self.assertRaises(service.InterpretationProcessingError) as error:
                MulticlassWorkerDatabaseTests.process(self, session, **kwargs)
        self.assertEqual(error.exception.code, self.expected_failure_code)
        session.expire_all()
        page = session.scalar(select(InterpretationPageOutcome).where(
            InterpretationPageOutcome.processing_job_id == kwargs['job_id']))
        self.assertEqual((page.status,page.progress,page.failure_code),
                         (self.expected_page_status,100,self.expected_failure_code))
        self.assertIsNone(page.candidate_run_id)
        self.assertIsNone(session.scalar(select(FloorPlanInterpretationRun).where(
            FloorPlanInterpretationRun.processing_job_id == kwargs['job_id'])))
        attempt = session.scalar(select(ProcessingJobAttempt).where(
            ProcessingJobAttempt.processing_job_id == kwargs['job_id']))
        self.assertEqual((attempt.status,attempt.failure_code,attempt.active_marker),
                         ('failed',self.expected_failure_code,None))
        return MulticlassWorkerDatabaseTests.process(self, session, **kwargs)


class MulticlassCurrentOwnerTimeoutDatabaseTests(MulticlassCurrentOwnerFailureDatabaseTests):
    expected_failure_code = 'MODEL_TIMEOUT'
    expected_page_status = 'timeout'


class MulticlassCooperativeCancellationTests(TestCase):
    def test_owned_cancellation_updates_page_and_acknowledges_attempt_atomically(self):
        from app.services import interpretation_processing_service as service

        session = MagicMock()
        claim = SimpleNamespace(job_id=7, attempt_id=9)
        job = SimpleNamespace(id=7, status='processing')
        attempt = SimpleNamespace(processing_job_id=7, worker_identity='current-worker', status='active',
            active_marker=True, lease_expires_at=datetime.now(UTC).replace(tzinfo=None)+timedelta(seconds=60))
        page = SimpleNamespace(id=8, processing_job_id=7, selection_state='selected', status='processing',
                               progress=75, failure_code=None, candidate_run_id=None, source_artifact_id=None)
        session.scalar.return_value = page

        def acknowledge(active_session, **kwargs):
            self.assertIs(active_session, session)
            self.assertEqual((page.status,page.progress,page.failure_code), ('cancelled',100,'PROCESSING_CANCELLED'))
            self.assertEqual(kwargs, dict(attempt_id=9, worker_identity='current-worker', outcome='cancelled',
                                         failure_code=None, complete_job=True))
            session.commit.assert_not_called()

        with patch.object(service, 'lock_processing_job', return_value=job), \
                patch.object(service, 'lock_attempt', return_value=attempt), \
                patch.object(service, 'find_cancellation', return_value=object()), \
                patch.object(service, 'has_open_selected_pages', return_value=False), \
                patch.object(service, 'finish_processing_attempt', side_effect=acknowledge) as finish:
            service._finish_fenced_failure(session, claim=claim, worker_identity='current-worker',
                                           page_outcome=page, failure_code='MODEL_TIMEOUT')
        finish.assert_called_once()
        self.assertIsNone(page.candidate_run_id)
        self.assertIsNone(page.source_artifact_id)
        session.commit.assert_not_called()

    def test_cooperative_heartbeat_leaves_terminal_acknowledgment_to_fenced_failure(self):
        from app.services import interpretation_processing_service as service

        with patch.object(service, 'heartbeat_processing_attempt', return_value=True), \
                patch.object(service, 'finish_processing_attempt') as finish:
            with self.assertRaises(service.InterpretationProcessingError) as error:
                service._heartbeat(MagicMock(), attempt_id=9, worker_identity='current-worker',
                                   stage='symbol_evidence')
        self.assertEqual(error.exception.code, 'PROCESSING_CANCELLED')
        finish.assert_not_called()
