import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from prepare_detector_review_queue import build_queue


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DetectorReviewQueueTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.source = root / "source.json"
        self.dataset = root / "dataset.json"
        self.probe = root / "probe.json"
        source_hash = _write(self.source, {
            "schema": "ved-reviewed-symbol-crops-v1",
            "records": [{"id": "target-1", "source_sha256": "a" * 64,
                         "source_width": 100, "source_height": 100,
                         "legend_entry": "drawing:L1", "bbox": [10, 20, 30, 40],
                         "group": 2}],
        })
        dataset_hash = _write(self.dataset, {
            "kind": "positive_only_masked_symbol_detection_diagnostic_v1",
            "class_agnostic": False,
            "source_manifest_sha256": source_hash,
            "classes": [{"id": 0, "legend_entry": "drawing:L1", "label": "Troffer"}],
            "images": [{"record_id": "target-1", "source_sha256": "a" * 64,
                        "legend_entry": "drawing:L1", "source_box": [10, 20, 30, 40],
                        "class_id": 0}],
        })
        _write(self.probe, {
            "kind": "partial_label_full_page_probe_v1", "class_agnostic": False,
            "dataset_manifest_sha256": dataset_hash,
            "checkpoint_sha256": "b" * 64, "precision": None, "generalization": None,
            "pages": [{"source_sha256": "a" * 64, "sheet_ids": ["sheet-1"],
                       "overlay": "aaaaaaaaaaaaaaaa-overlay.jpg",
                       "reviewed_positive_count": 1,
                       "targets": [{"record_id": "target-1",
                                    "localized_and_classified": False}],
                       "predictions": [{"class_id": 0, "bbox": [11, 21, 31, 41],
                                        "score": 0.8}]}],
        })

    def test_keeps_proposals_unapproved_and_metrics_unscored(self):
        queue = build_queue(self.source, self.dataset, self.probe)
        self.assertEqual(queue["class_support"], [
            {"legend_entry": "drawing:L1", "reviewed_boxes": 1, "source_pages": 1}])
        self.assertIsNone(queue["precision"])
        self.assertIsNone(queue["independent_project_recall"])
        page = queue["pages"][0]
        self.assertEqual(page["workspace_groups_not_project_ids"], ["2"])
        self.assertEqual(page["probe_overlay_filename"], "aaaaaaaaaaaaaaaa-overlay.jpg")
        self.assertEqual(page["project_identity"], "unverified")
        self.assertEqual(page["exhaustive_symbol_and_background_review"], "not_recorded")
        self.assertEqual(page["proposals"][0]["review_state"], "pending")
        self.assertEqual(page["proposals"][0]["proposed_legend_entry"], "drawing:L1")
        self.assertEqual(page["missed_reviewed_targets"], [
            {"record_id": "target-1", "legend_entry": "drawing:L1",
             "bbox_source_pixels": [10, 20, 30, 40]}])

    def test_rejects_unbound_probe_and_fabricated_precision(self):
        probe = json.loads(self.probe.read_text(encoding="utf-8"))
        probe["dataset_manifest_sha256"] = "0" * 64
        _write(self.probe, probe)
        with self.assertRaisesRegex(ValueError, "not bound"):
            build_queue(self.source, self.dataset, self.probe)
        probe["dataset_manifest_sha256"] = hashlib.sha256(self.dataset.read_bytes()).hexdigest()
        probe["precision"] = 1.0
        _write(self.probe, probe)
        with self.assertRaisesRegex(ValueError, "Incomplete pages"):
            build_queue(self.source, self.dataset, self.probe)

    def test_rejects_changed_class_mapping_and_missing_page(self):
        dataset = json.loads(self.dataset.read_text(encoding="utf-8"))
        dataset["images"][0]["legend_entry"] = "different:L1"
        dataset_hash = _write(self.dataset, dataset)
        probe = json.loads(self.probe.read_text(encoding="utf-8"))
        probe["dataset_manifest_sha256"] = dataset_hash
        _write(self.probe, probe)
        with self.assertRaisesRegex(ValueError, "mapping changed"):
            build_queue(self.source, self.dataset, self.probe)
        dataset["images"][0]["legend_entry"] = "drawing:L1"
        probe["dataset_manifest_sha256"] = _write(self.dataset, dataset)
        probe["pages"] = []
        _write(self.probe, probe)
        with self.assertRaisesRegex(ValueError, "omitted"):
            build_queue(self.source, self.dataset, self.probe)

    def test_rejects_out_of_bounds_prediction(self):
        probe = json.loads(self.probe.read_text(encoding="utf-8"))
        probe["pages"][0]["predictions"][0]["bbox"] = [90, 21, 110, 41]
        _write(self.probe, probe)
        with self.assertRaisesRegex(ValueError, "coordinates"):
            build_queue(self.source, self.dataset, self.probe)


if __name__ == "__main__":
    unittest.main()
