"""All-entry development detector contract; fixtures are not accuracy evidence."""
import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import numpy as np

from app.ai.floor_plan_interpretation import multiclass_symbol_detector as detector
from app.ai.floor_plan_interpretation import experimental_symbol_detector as shared
from app.ai.floor_plan_interpretation.demo_cv import interpret_floor_plan_demo
from app.services.interpretation_job_configuration_service import pin_job_configuration, InterpretationConfigurationError
from app.services.processing_job_service import start_floor_plan_processing


def classes():
    return {i: (f"Fixture {i}", f"drawing:L{i}") for i in range(56)}


class MulticlassDetectorTests(TestCase):
    def test_bounded_candidate_output_stays_partial_and_reviewable(self):
        def predict(tiles, **kwargs):
            boxes = [SimpleNamespace(xyxy=np.array([[8*(i%19), 8*(i//19),
                                                     8*(i%19)+4, 8*(i//19)+4]]),
                                     cls=np.array([0]), conf=np.array([.7])) for i in range(95)]
            return [SimpleNamespace(boxes=boxes) for tile in tiles]
        rgb = np.full((256, 600, 3), 255, dtype=np.uint8)
        with patch.object(detector, "verify_artifacts", return_value=classes()), \
             patch.object(detector, "_model", return_value=SimpleNamespace(predict=predict)):
            predictions, truncated = detector.locate(rgb)
            payload = detector.with_proposals(interpret_floor_plan_demo(rgb), predictions, truncated)
        self.assertTrue(truncated)
        self.assertEqual(len(predictions), 200)
        self.assertEqual(payload.symbols.state, "partial")
        self.assertTrue(payload.symbols.truncated)
        self.assertEqual(payload.document_state, "partial")
        self.assertTrue(any(w.code == "experimental_detector_truncated" for w in payload.warnings))

    def test_second_lattice_is_target_independent_and_never_exceeds_existing_cap(self):
        standard = shared.tile_positions(1500, 2200)
        combined = shared.tile_positions(1500, 2200, dual_phase=True)
        self.assertTrue(set(standard).issubset(combined))
        self.assertIn((128, 128), combined)
        self.assertLessEqual(len(combined), shared.MAX_TILES)
        large = shared.tile_positions(3600, 3600, dual_phase=True)
        self.assertLessEqual(len(large), shared.MAX_TILES)
        self.assertEqual(large, shared.tile_positions(3600, 3600))
    def test_default_development_start_pins_one_checkpoint_for_all_pages(self):
        from app.services import processing_job_service as service
        settings = SimpleNamespace(app_env="development", local_vlm_runtime_url=None, local_vlm_model_path=None)
        outcomes = [SimpleNamespace() for _ in range(2)]
        with patch.object(service, "find_owned_floor_plan_for_update", return_value=SimpleNamespace(id=1)), \
             patch.object(service, "find_active_processing_job", return_value=None), \
             patch.object(service, "add_processing_job", return_value=SimpleNamespace(id=2, floor_plan_id=1)), \
             patch.object(service, "list_pages_for_floor_plan", return_value=[1, 2]), \
             patch.object(service, "configure_page_outcomes", return_value=outcomes), \
             patch("app.services.interpretation_release_service.current_runtime_release", return_value=None), \
             patch.object(detector, "verify_artifacts", return_value=classes()):
            start_floor_plan_processing(SimpleNamespace(), current_user=SimpleNamespace(id=3),
                                        floor_plan_id=1, settings=settings)
        self.assertEqual([o.provider for o in outcomes], [detector.PROVIDER]*2)
        self.assertTrue(all(o.configuration_sha256 == detector.configuration_sha256() for o in outcomes))

    def test_configured_or_production_runtime_is_not_overridden_by_development_weights(self):
        from app.services import processing_job_service as service
        for environment, gateway, release in (("production", None, None),
                                               ("development", "http://127.0.0.1:8081", None),
                                               ("development", None, object())):
            settings = SimpleNamespace(app_env=environment, local_vlm_runtime_url=gateway, local_vlm_model_path=None)
            outcome = SimpleNamespace(provider="existing")
            with patch.object(service, "find_owned_floor_plan_for_update", return_value=SimpleNamespace(id=1)), \
                 patch.object(service, "find_active_processing_job", return_value=None), \
                 patch.object(service, "add_processing_job", return_value=SimpleNamespace(id=2, floor_plan_id=1)), \
                 patch.object(service, "list_pages_for_floor_plan", return_value=[1]), \
                 patch.object(service, "configure_page_outcomes", return_value=[outcome]), \
                 patch("app.services.interpretation_release_service.current_runtime_release", return_value=release), \
                 patch.object(detector, "verify_artifacts") as verify:
                start_floor_plan_processing(SimpleNamespace(), current_user=SimpleNamespace(id=3),
                                            floor_plan_id=1, settings=settings)
            self.assertEqual(outcome.provider, "existing")
            verify.assert_not_called()

    def test_pinned_worker_configuration_is_development_only_and_hash_fenced(self):
        current = SimpleNamespace(provider=detector.PROVIDER, configuration_sha256=detector.configuration_sha256())
        session = SimpleNamespace(scalar=lambda *args: current)
        with patch.object(detector, "verify_artifacts", return_value=classes()), \
             patch("app.services.interpretation_job_configuration_service.current_runtime_release", return_value=None):
            self.assertIs(pin_job_configuration(session, processing_job=SimpleNamespace(id=1),
                                               settings=SimpleNamespace(app_env="development")), current)
            with self.assertRaises(InterpretationConfigurationError):
                pin_job_configuration(session, processing_job=SimpleNamespace(id=1),
                                      settings=SimpleNamespace(app_env="production"))
            current.configuration_sha256 = "altered"
            with self.assertRaises(InterpretationConfigurationError):
                pin_job_configuration(session, processing_job=SimpleNamespace(id=1),
                                      settings=SimpleNamespace(app_env="development"))

    def test_every_entry_is_inferred_and_preserved_as_unresolved_source_pixel_proposal(self):
        calls = []
        def predict(tiles, **kwargs):
            calls.append(kwargs)
            return [SimpleNamespace(boxes=[SimpleNamespace(xyxy=np.array([[10, 20, 30, 40]]),
                     cls=np.array([i]), conf=np.array([.7])) for i in range(56)]) for tile in tiles]
        rgb = np.full((300, 300, 3), 255, dtype=np.uint8)
        original = rgb.copy()
        with patch.object(detector, "verify_artifacts", return_value=classes()), \
             patch.object(detector, "_model", return_value=SimpleNamespace(predict=predict)):
            predictions, truncated = detector.locate(rgb)
            payload = detector.with_proposals(interpret_floor_plan_demo(rgb), predictions, truncated)
        self.assertEqual(calls[0]["classes"], list(range(56)))
        self.assertEqual(calls[0]["conf"], .5)
        self.assertEqual({p["class_id"] for p in predictions}, set(range(56)))
        self.assertTrue(any(p["bbox"] == (54., 64., 74., 84.) for p in predictions))
        self.assertTrue(all(s.mapping_state == "unknown" and s.catalog_class_id is None
                            for s in payload.symbols.items))
        self.assertTrue(any("Training legend drawing:L55" in w.message for w in payload.warnings))
        np.testing.assert_array_equal(rgb, original)

    def test_integrity_mapping_and_missing_class_examples_fail_closed(self):
        with TemporaryDirectory() as temporary:
            checkpoint, dataset = Path(temporary)/"weights.pt", Path(temporary)/"manifest.json"
            checkpoint.write_bytes(b"synthetic checkpoint")
            data = {"all_eligible_entries": True, "required_loss": "positive_and_reviewed_box_only",
                    "reference_rights_exclusions": {"sheet_ids": ["sheet-51", "sheet-52"]},
                    "classes": [{"id": i, "label": name, "legend_entry": key, "samples": 1}
                                for i, (name, key) in classes().items()]}
            dataset.write_text(json.dumps(data))
            with patch.object(detector, "CHECKPOINT", checkpoint), patch.object(detector, "DATASET", dataset), \
                 patch.object(detector, "CHECKPOINT_SHA256", sha256(checkpoint.read_bytes()).hexdigest()), \
                 patch.object(detector, "DATASET_SHA256", sha256(dataset.read_bytes()).hexdigest()):
                self.assertEqual(detector.verify_artifacts(), classes())
                for required_loss in ("positive_boxes_and_explicit_reviewed_background", "unreviewed_background"):
                    data["required_loss"] = required_loss
                    dataset.write_text(json.dumps(data))
                    with patch.object(detector, "DATASET_SHA256", sha256(dataset.read_bytes()).hexdigest()):
                        if required_loss == "unreviewed_background":
                            with self.assertRaisesRegex(shared.ExperimentalDetectorUnavailable, "CLASS_MAP_INVALID"):
                                detector.verify_artifacts()
                        else:
                            self.assertEqual(detector.verify_artifacts(), classes())
                data["required_loss"] = "positive_and_reviewed_box_only"
                dataset.write_text(json.dumps(data))
                checkpoint.write_bytes(b"tampered")
                with self.assertRaises(shared.ExperimentalDetectorUnavailable):
                    detector.verify_artifacts()
            checkpoint.write_bytes(b"synthetic checkpoint")
            data["classes"][55]["samples"] = 0
            dataset.write_text(json.dumps(data))
            with patch.object(detector, "CHECKPOINT", checkpoint), patch.object(detector, "DATASET", dataset), \
                 patch.object(detector, "CHECKPOINT_SHA256", sha256(checkpoint.read_bytes()).hexdigest()), \
                 patch.object(detector, "DATASET_SHA256", sha256(dataset.read_bytes()).hexdigest()):
                with self.assertRaisesRegex(shared.ExperimentalDetectorUnavailable, "CLASS_MAP_INVALID"):
                    detector.verify_artifacts()

    def test_unknown_or_nonfinite_model_outputs_fail_closed(self):
        model = SimpleNamespace(predict=lambda tiles, **kwargs: [SimpleNamespace(boxes=[
            SimpleNamespace(xyxy=np.array([[10, 20, 30, 40]]), cls=np.array([56]), conf=np.array([.7]))])])
        with patch.object(detector, "verify_artifacts", return_value=classes()), \
             patch.object(detector, "_model", return_value=model):
            with self.assertRaises(shared.ExperimentalDetectorUnavailable):
                detector.locate(np.full((100, 100, 3), 255, dtype=np.uint8))
        for box in ([float("nan"), 20, 30, 40], [10, 20, float("inf"), 40]):
            model = SimpleNamespace(predict=lambda tiles, **kwargs: [SimpleNamespace(boxes=[
                SimpleNamespace(xyxy=np.array([box]), cls=np.array([0]), conf=np.array([.7]))])])
            with patch.object(detector, "verify_artifacts", return_value=classes()), \
                 patch.object(detector, "_model", return_value=model):
                with self.assertRaises(shared.ExperimentalDetectorUnavailable):
                    detector.locate(np.full((100, 100, 3), 255, dtype=np.uint8))
