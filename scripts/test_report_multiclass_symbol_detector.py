import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main

from report_multiclass_symbol_detector import digest, report


class CoverageTests(TestCase):
    def test_all_56_entries_with_zero_predictions_are_explicit_and_traceable(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset, probe = root/"dataset.json", root/"probe.json"
            classes = [{"id": i, "legend_entry": f"drawing:L{i}", "label": f"Fixture {i}", "samples": 1}
                       for i in range(56)]
            dataset.write_text(json.dumps({"classes": classes,
                "images": [{"class_id": i} for i in range(56)] + [{"class_id": 0, "augmentation_parent": "original"}],
                "balanced_augmentation": {"synthetic_variants": [{"class_id": 0}]}}))
            data = {"dataset_manifest_sha256": digest(dataset), "checkpoint_sha256": "a"*64,
                    "threshold": .5, "pages": [{"predictions": [{"class_id": 0}]}],
                    "summary": {"per_class": [{"class_id": c["id"], "legend_entry": c["legend_entry"],
                        "label": c["label"], "localized_and_classified": int(c["id"] == 0)} for c in classes]}}
            probe.write_text(json.dumps(data))
            self.assertEqual(report(dataset, probe, root/"report"),
                             {"entries_in_training": 56, "entries_with_predictions": 1, "entries_with_reviewed_matches": 1})
            entries = json.loads((root/"report/coverage.json").read_text())["entries"]
            self.assertEqual([e["model_class_id"] for e in entries], list(range(56)))
            self.assertEqual(entries[0]["center_training_images"], 1)
            self.assertEqual(entries[0]["augmented_variants"], 1)
            self.assertIn("ZERO predicted", entries[-1]["limitations"])
            self.assertTrue((root/"report/coverage.csv").is_file())
            with self.assertRaises(FileExistsError):
                report(dataset, probe, root/"report")
            data["dataset_manifest_sha256"] = "b"*64
            probe.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "hashes differ"):
                report(dataset, probe, root/"altered")


if __name__ == "__main__":
    main()
