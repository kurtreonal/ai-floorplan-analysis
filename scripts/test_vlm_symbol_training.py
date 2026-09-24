import copy
import json
import tempfile
import unittest
from pathlib import Path

from prepare_vlm_symbol_crops import (resolve_legend, valid_box, sha,
                                      link_verified_related_floors, closed_set_validation_groups)
from train_vlm_symbol_crops import validate_manifest
from audit_vlm_crop_evaluation import audit, REVIEW_SHA


class MappingTests(unittest.TestCase):
    def test_verified_related_floors_join_only_on_exact_export_version(self):
        parent = {str(number): str(number) for number in range(1, 8)}
        link_verified_related_floors(parent, "another-export")
        self.assertEqual(parent["4"], "4")
        link_verified_related_floors(parent, REVIEW_SHA)
        self.assertTrue(all(parent[str(number)] == "1" for number in range(2, 7)))
        self.assertEqual(parent["7"], "7")

    def test_closed_set_holdout_keeps_only_seen_class_and_no_duplicate(self):
        records = [
            {"group": "train", "legend_entry": "L1", "source_sha256": "a"},
            {"group": "good", "legend_entry": "L1", "source_sha256": "b"},
            {"group": "unseen", "legend_entry": "L2", "source_sha256": "c"},
            {"group": "duplicate", "legend_entry": "L1", "source_sha256": "a"},
        ]
        self.assertEqual(closed_set_validation_groups(records, {"good", "unseen", "duplicate"}),
                         {"good"})

    def test_project_related_floors_and_unseen_classes_are_not_scored(self):
        manifest = {"review_sha256": REVIEW_SHA, "records": [
            {"group": "1", "split": "train", "legend_entry": "L1"},
            {"group": "4", "split": "development_validation", "legend_entry": "L1"},
            {"group": "7", "split": "development_validation", "legend_entry": "L2"},
        ]}
        result = audit(manifest)
        self.assertTrue(result["known_project_leak"])
        self.assertEqual(result["unseen_class_validation_records"], 1)
        self.assertEqual(result["same_class_validation_records_not_yet_project_verified"], 1)
        self.assertEqual(result["scorable_project_separated_closed_set_records"], 0)

    def setUp(self):
        self.sheet = {"id": "plan", "associated_legend_ids": ["legend"]}
        self.catalog = [{"legend_entry": "legend:L1", "label": "Duplex outlet",
                         "examples": [{"source_sheet_id": "legend"}]}]

    def test_exact_reviewed_label_reconciliation(self):
        annotation = {"label": "  DUPLEX   outlet ", "class_state": "unmapped"}
        original = copy.deepcopy(annotation)
        entry, method = resolve_legend(annotation, self.sheet, self.catalog)
        self.assertEqual(entry["legend_entry"], "legend:L1")
        self.assertEqual(method, "exact_scoped_label")
        self.assertEqual(annotation, original)

    def test_ambiguous_or_other_drawing_not_invented(self):
        duplicate = {**self.catalog[0], "legend_entry": "legend:L2"}
        annotation = {"label": "Duplex outlet"}
        self.assertIsNone(resolve_legend(annotation, self.sheet, self.catalog+[duplicate])[0])
        self.assertIsNone(resolve_legend(annotation, {"id": "other"}, self.catalog)[0])
        self.assertIsNone(resolve_legend({"label": "outlet"}, self.sheet, self.catalog)[0])

    def test_invalid_coordinates_rejected_not_clamped(self):
        for box in ([0, 0, 101, 3], [0, 0, float("nan"), 3], [3, 3, 1, 1]):
            self.assertIsNone(valid_box({"geometry": {"type": "bbox", "coordinates": box}}, 100, 100))

    def test_integrity_review_and_split_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "image.png"
            image.write_bytes(b"test-fixture")
            annotation = {"id": "a", "review_state": "corrected", "label": "Duplex outlet", "note": "\u00b0 verified",
                          "geometry": {"type": "bbox", "coordinates": [0, 0, 5, 5]}}
            review = {"sheets": [{**self.sheet, "annotations": [annotation], "width": 10, "height": 10}]}
            (root / "source-review.json").write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
            (root / "source-references.json").write_text(json.dumps({"legend_catalog": self.catalog}), encoding="utf-8")
            record = {"id": "r1", "sheet_id": "plan", "annotation_id": "a",
                      "label": "Duplex outlet", "legend_entry": "legend:L1", "bbox": [0, 0, 5, 5],
                      "mapping_evidence": "exact_scoped_label",
                      "group": "g1", "source_sha256": "source", "image_sha256": sha(image),
                      "image": "image.png", "split": "train",
                      "original_annotation": annotation}
            manifest = {"schema": "ved-reviewed-symbol-crops-v1", "task": "symbol_crop_classification",
                        "review_sha256": sha(root / "source-review.json"),
                        "reference_sha256": sha(root / "source-references.json"),
                        "authorization": "test only", "records": [record]}
            validate_manifest(manifest, root)
            for mutation in ({"split": "sealed_test"}, {"image_sha256": "altered"}, {"label": "invented"},
                             {"original_annotation": {"review_state": "needs_review"}}):
                with self.assertRaises(ValueError):
                    validate_manifest({**manifest, "records": [{**record, **mutation}]}, root)
            with self.assertRaises(ValueError):
                validate_manifest({**manifest, "records": [record, {**record, "id": "r2", "split": "development_validation"}]}, root)
            review["sheets"][0]["group"] = 1
            (root / "source-review.json").write_text(json.dumps(review), encoding="utf-8")
            manifest["review_sha256"] = sha(root / "source-review.json")
            approval = {"review_sha256": manifest["review_sha256"], "approved_groups": [1],
                        "user_statement": "synthetic test approval"}
            approval_path = root / "source-approval.json"
            approval_path.write_text(json.dumps(approval), encoding="utf-8")
            manifest.update(authorization=approval, approval_sha256=sha(approval_path))
            validate_manifest(manifest, root)
            with self.assertRaises(ValueError):
                validate_manifest({**manifest, "approval_sha256": "altered"}, root)
            for change in ({"approved_groups": [2]}, {"review_sha256": "another-version"}):
                changed = {**approval, **change}
                approval_path.write_text(json.dumps(changed), encoding="utf-8")
                with self.assertRaises(ValueError):
                    validate_manifest({**manifest, "authorization": changed,
                                       "approval_sha256": sha(approval_path)}, root)


if __name__ == "__main__":
    unittest.main()
