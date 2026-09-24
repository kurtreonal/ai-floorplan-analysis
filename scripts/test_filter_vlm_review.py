import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from filter_vlm_review import filter_review, main


class FilterReviewTests(unittest.TestCase):
    def test_new_export_snapshot_preserves_workspace_and_previous_revision(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            (workspace / "data").mkdir(parents=True)
            original = b'{"previous_version":true}'
            session = workspace / "data/saved-session.json"
            session.write_bytes(original)
            (workspace / "data/approved-references.json").write_text(
                json.dumps({"legend_catalog": []}), encoding="utf-8")
            source = root / "new-export.json"
            raw = json.dumps({"schema": "ved-editable-review-v2", "sheets": [],
                              "training_approved": False}).encode()
            source.write_bytes(raw)
            output = root / "revision-2"
            argv = ["filter", "--workspace", str(workspace), "--review-export", str(source),
                    "--output", str(output)]
            with patch("sys.argv", argv), patch("builtins.print"):
                main()
                with self.assertRaises(FileExistsError):
                    main()
            self.assertEqual(session.read_bytes(), original)
            self.assertEqual(source.read_bytes(), raw)
            self.assertEqual((output / "source-review.json").read_bytes(), raw)
            self.assertFalse(json.loads((output / "filtered-review.json").read_text())["training_approved"])

    def run_filter(self, annotations, decision=None):
        payload = {
            "schema": "ved-editable-review-v2",
            "sheets": [{"id": "s1", "source_sha256": "a" * 64,
                        "width": 100, "height": 100, "annotations": annotations}],
            "decisions": {"s1": {"decision": decision}},
        }
        original = copy.deepcopy(payload)
        result = filter_review(payload, {"legend_catalog": [{"legend_entry": "L1"}]})
        self.assertEqual(payload, original)
        self.assertFalse(result["training_approved"])
        self.assertFalse(result["sheets"][0]["training_eligible"])
        return result["sheets"][0]

    def test_review_and_mapping_required(self):
        base = {"id": "a", "layer": "symbols", "review_state": "corrected",
                "class_state": "approved_legend_mapping", "legend_entry": "L1"}
        result = self.run_filter([base, {**base, "review_state": "needs_review"},
                                 {**base, "class_state": "proposed_legend_mapping"},
                                 {**base, "legend_entry": "unknown"}])
        self.assertEqual(result["annotations"], [base])
        self.assertEqual(len(result["excluded"]), 3)

    def test_excluded_and_rescan_sheets(self):
        for decision in ("exclude", "rescan_needed"):
            result = self.run_filter([{"id": "a", "layer": "geometry",
                                       "review_state": "corrected"}], decision)
            self.assertEqual(result["annotations"], [])

    def test_deleted_and_ocr_not_targets(self):
        result = self.run_filter([
            {"id": "a", "layer": "geometry", "review_state": "deleted"},
            {"id": "b", "layer": "ocr", "review_state": "corrected"},
        ])
        self.assertEqual(result["annotations"], [])

    def test_unknown_schema_rejected(self):
        with self.assertRaises(ValueError):
            filter_review({"schema": "other"}, {})


if __name__ == "__main__":
    unittest.main()
