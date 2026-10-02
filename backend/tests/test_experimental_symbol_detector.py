"""Development trained-symbol proposal contract; synthetic data only."""

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import numpy as np

from app.ai.floor_plan_interpretation import experimental_symbol_detector as detector
from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationPayload
from app.ai.floor_plan_interpretation.demo_cv import interpret_floor_plan_demo


class _FakeModel:
    def predict(self, tiles, **kwargs):
        assert kwargs["classes"] == [0, 1, 2, 3]
        return [SimpleNamespace(boxes=[SimpleNamespace(
            xyxy=np.array([[10, 20, 30, 40]], dtype=float),
            cls=np.array([3]), conf=np.array([.7]))]) for _ in tiles]


class _FakeLinkedModel:
    def predict(self, tiles, **kwargs):
        assert kwargs["classes"] == [0, 1, 2, 3, 4]
        return [SimpleNamespace(boxes=[SimpleNamespace(
            xyxy=np.array([[10, 20, 30, 40]], dtype=float),
            cls=np.array([4]), conf=np.array([.7]))]) for _ in tiles]


class ExperimentalSymbolDetectorTests(TestCase):
    def test_integrity_and_reference_rights_fence(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkpoint = root / "weights.pt"
            checkpoint.write_bytes(b"checkpoint")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "required_loss": "positive_and_local_negative_only", "context_mode": "full_partial",
                "reference_rights_exclusions": {"sheet_ids": ["sheet-51", "sheet-52"]},
                "classes": [{"id": index} for index in range(4)],
            }))
            with patch.object(detector, "CHECKPOINT", checkpoint), \
                 patch.object(detector, "CHECKPOINT_SHA256", sha256(checkpoint.read_bytes()).hexdigest()), \
                 patch.object(detector, "DATASET_MANIFEST", manifest), \
                 patch.object(detector, "DATASET_SHA256", sha256(manifest.read_bytes()).hexdigest()):
                detector.verify_artifacts()
                checkpoint.write_bytes(b"tampered")
                with self.assertRaises(detector.ExperimentalDetectorUnavailable):
                    detector.verify_artifacts()
            self.assertEqual(len(detector.configuration_sha256()), 64)

    def test_source_pixel_tiling_preserves_image_and_candidates_remain_unresolved(self):
        image = np.full((300, 300, 3), 255, dtype=np.uint8)
        original = image.copy()
        with patch.object(detector, "verify_artifacts"), patch.object(detector, "_model", return_value=_FakeModel()):
            candidates, truncated = detector.locate(image)
        self.assertFalse(truncated)
        self.assertEqual(len(candidates), 4)
        self.assertIn((54.0, 64.0, 74.0, 84.0), [row["bbox"] for row in candidates])
        np.testing.assert_array_equal(image, original)
        payload = detector.with_trained_symbol_proposals(interpret_floor_plan_demo(image), candidates)
        self.assertIsInstance(payload, FloorPlanInterpretationPayload)
        self.assertEqual(len(payload.symbols.items), 4)
        self.assertTrue(all(item.mapping_state == "unknown" and item.catalog_class_id is None
                            for item in payload.symbols.items))
        self.assertEqual(payload.symbols.items[0].observed_label, "Troffer lights")
        self.assertTrue(any("not calibrated" in warning.message for warning in payload.warnings))

    def test_linked_classes_are_pinned_and_remain_unresolved(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkpoint = root / "weights.pt"
            checkpoint.write_bytes(b"linked checkpoint")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "required_loss": "positive_and_local_negative_only", "context_mode": "full_partial",
                "reference_rights_exclusions": {"sheet_ids": ["sheet-51", "sheet-52"]},
                "classes": [{"id": index, "legend_entry": value[1]}
                            for index, value in detector.LINKED_CLASSES.items()],
            }))
            with patch.object(detector, "LINKED_CHECKPOINT", checkpoint), \
                 patch.object(detector, "LINKED_CHECKPOINT_SHA256", sha256(checkpoint.read_bytes()).hexdigest()), \
                 patch.object(detector, "LINKED_DATASET_MANIFEST", manifest), \
                 patch.object(detector, "LINKED_DATASET_SHA256", sha256(manifest.read_bytes()).hexdigest()):
                detector.verify_linked_artifacts()
                data = json.loads(manifest.read_text())
                data["classes"][0]["legend_entry"] = "wrong-class"
                manifest.write_text(json.dumps(data))
                with self.assertRaises(detector.ExperimentalDetectorUnavailable):
                    detector.verify_linked_artifacts()
        image = np.full((300, 300, 3), 255, dtype=np.uint8)
        with patch.object(detector, "verify_linked_artifacts"), \
             patch.object(detector, "_linked_model", return_value=_FakeLinkedModel()):
            candidates, truncated = detector.locate(image, linked=True)
        payload = detector.with_trained_symbol_proposals(
            interpret_floor_plan_demo(image), candidates, truncated, linked=True)
        self.assertEqual(payload.symbols.items[0].observed_label, "Troffer lights")
        self.assertTrue(all(item.mapping_state == "unknown" for item in payload.symbols.items))
        self.assertTrue(any("five linked legend IDs" in warning.message for warning in payload.warnings))
        self.assertNotEqual(detector.configuration_sha256(), detector.linked_configuration_sha256())

    def test_fusion_keeps_distinct_nearby_symbols_and_capped_result_is_partial(self):
        rows = [{"bbox": (0, 0, 20, 20), "class_id": 3, "score": .9, "tile_origin": (0, 0)},
                {"bbox": (1, 0, 21, 20), "class_id": 3, "score": .8, "tile_origin": (0, 0)},
                {"bbox": (21, 0, 41, 20), "class_id": 3, "score": .7, "tile_origin": (0, 0)}]
        self.assertEqual(len(detector.fuse(rows)), 2)
        payload = detector.with_trained_symbol_proposals(
            interpret_floor_plan_demo(np.full((100, 100, 3), 255, dtype=np.uint8)),
            detector.fuse(rows), truncated=True)
        self.assertEqual(payload.symbols.state, "partial")
        self.assertTrue(payload.symbols.truncated)
