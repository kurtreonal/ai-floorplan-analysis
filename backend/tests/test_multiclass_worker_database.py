"""Run only with scripts/run_isolated_backend_tests.py; never the dev database."""
from hashlib import sha256
from unittest.mock import patch

from app.ai.floor_plan_interpretation import multiclass_symbol_detector as detector
from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationCandidate
from app.models import ProcessingJob
from app.services.interpretation_page_outcome_service import configure_page_outcomes
from app.services.interpretation_processing_service import process_interpretation_job
from tests.test_demo_processing_worker import DemoProcessingWorkerTests


class MulticlassWorkerDatabaseTests(DemoProcessingWorkerTests):
    expected_provider = detector.PROVIDER
    assert_page_outcome = True

    def process(self, session, **kwargs):
        job = session.get(ProcessingJob, kwargs["job_id"])
        outcomes = configure_page_outcomes(session, processing_job=job, page_numbers=[1])
        outcomes[0].provider = detector.PROVIDER
        outcomes[0].model_release_id = detector.PROVIDER
        outcomes[0].configuration_sha256 = detector.configuration_sha256()
        session.commit()
        classes = {i: (f"Fixture {i}", f"drawing:L{i}") for i in range(56)}
        proposals = tuple({"bbox": (100, 120, 128, 148), "score": .8,
                           "class_id": i, "tile_origin": (0, 0)} for i in range(56))
        with patch.object(detector, "verify_artifacts", return_value=classes), \
             patch.object(detector, "locate", return_value=(proposals, False)):
            run = process_interpretation_job(session, **kwargs)
        candidate = FloorPlanInterpretationCandidate.model_validate_json(run.candidate_json)
        self.assertEqual(candidate.provenance.model_release_id, detector.PROVIDER)
        self.assertEqual(candidate.provenance.base_model_revision,
                         f"yolo11n-warmstart-{detector.TRAINING_BASE_SHA256[:12]}")
        self.assertEqual(candidate.provenance.prompt_version, "reviewed-background-56-detector-v3")
        self.assertEqual(len(candidate.payload.symbols.items), 56)
        self.assertTrue(all(s.mapping_state == "unknown" for s in candidate.payload.symbols.items))
        self.assertIn(detector.CHECKPOINT_SHA256,
                      [p.value for p in candidate.provenance.inference_parameters])
        self.assertEqual(run.candidate_sha256, sha256(run.candidate_json.encode()).hexdigest())
        return run
