"""Synthetic, source-preserving tests for development link manifest construction."""

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from build_linked_symbol_manifest import build, recovered_placement


class LinkedSymbolManifestTests(unittest.TestCase):
    def test_recovery_requires_reviewed_placement_history_and_exact_supported_identity(self):
        sheet = {"sheet_type": "plan"}
        annotation = {"layer": "legend", "original_annotation": {"layer": "symbols"},
                      "review_state": "user_reviewed", "class_state": "cross_group_candidate",
                      "label": "Downlight", "legend_entry": "source:L2"}
        chosen = {"source:L2": "Downlight"}
        self.assertTrue(recovered_placement(sheet, annotation, chosen))
        for patch in ({"review_state": "deleted"}, {"deleted": True}, {"excluded": True}, {"class_state": "unmapped"},
                      {"original_annotation": {"layer": "legend"}}, {"legend_entry": "other:L2"},
                      {"label": "Switch subtype unresolved"}):
            self.assertFalse(recovered_placement(sheet, {**annotation, **patch}, chosen))
        self.assertFalse(recovered_placement({"sheet_type": "legend_reference"}, annotation, chosen))

    def test_recovery_is_explicit_versioned_and_respects_page_exclusion(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            revision = self.make_revision(root)
            for name in ("source-review", "linked-review"):
                path = revision / f"{name}.json"
                data = json.loads(path.read_text())
                data["sheets"][0]["sheet_type"] = "plan"
                ann = data["sheets"][0]["annotations"][1]
                ann.update(layer="legend", original_annotation={"layer": "symbols"},
                           geometry={"type": "bbox", "coordinates": [15, 3, 25, 20]})
                path.write_text(json.dumps(data))
            audit_path = revision / "audit.json"
            audit = json.loads(audit_path.read_text())
            audit["source_session_sha256"] = sha256((revision / "source-review.json").read_bytes()).hexdigest()
            audit_path.write_text(json.dumps(audit))
            self.assertEqual(build(revision, root / "legacy.json")["records"], 1)
            self.assertEqual(build(revision, root / "recovered.json", recover_reviewed_placements=True)["records"], 2)
            result = json.loads((root / "recovered.json").read_text())
            self.assertEqual(result["recovered_placements"][0]["original_layer"], "legend")
            for name in ("source-review", "linked-review"):
                path = revision / f"{name}.json"
                data = json.loads(path.read_text())
                data["decisions"] = {"sheet-11": {"decision": "exclude"}}
                path.write_text(json.dumps(data))
            audit["source_session_sha256"] = sha256((revision / "source-review.json").read_bytes()).hexdigest()
            audit_path.write_text(json.dumps(audit))
            with self.assertRaisesRegex(ValueError, "No eligible"):
                build(revision, root / "excluded.json", recover_reviewed_placements=True)
    def make_revision(self, root):
        revision = root / "revision"
        revision.mkdir()
        symbol = lambda identity, state: {
            "id": identity, "layer": "symbols", "review_state": "user_reviewed",
            "class_state": state, "legend_entry": "u:troffer",
            "label": "Troffer lights", "geometry": {"type": "bbox", "coordinates": [2, 3, 12, 20]},
        }
        source = {"schema": "ved-editable-review-v2", "training_approved": False,
                  "decisions": {}, "sheets": [{"id": "sheet-11", "group": 1,
                  "source_sha256": "a" * 64, "width": 30, "height": 40,
                  "coordinate_frame": "original_image_pixels", "annotations": [
                      symbol("one", "user_proposed_legend_mapping"),
                      symbol("two", "approved_legend_mapping"),
                  ]}]}
        linked = json.loads(json.dumps(source))
        linked["sheets"][0]["annotations"][0]["class_state"] = "approved_legend_mapping"
        linked["sheets"][0]["annotations"][0]["legendKey"] = "u:troffer"
        audit = {"schema": "ved-central-legend-link-audit-v1",
                 "source_session_sha256": sha256(json.dumps(source).encode()).hexdigest(),
                 "linked_this_revision": 1,
                 "approved_legends": [{"legend_entry": "u:troffer",
                                       "label": "Troffer lights", "linked_this_revision": 1}],
                 "decisions": [{"sheet_id": "sheet-11", "annotation_id": "one",
                                "legend_entry": "u:troffer"}]}
        for name, value in (("source-review", source), ("linked-review", linked), ("audit", audit)):
            (revision / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")
        return revision

    def test_exact_links_and_existing_mappings_are_versioned_without_approval(self):
        with TemporaryDirectory(prefix="ved-linked-manifest-") as folder:
            root = Path(folder)
            revision = self.make_revision(root)
            original_hash = sha256((revision / "source-review.json").read_bytes()).hexdigest()
            output = root / "manifest.json"
            result = build(revision, output)
            manifest = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["records"], 1)  # Same reviewed source box deduplicated.
            self.assertEqual(manifest["records"][0]["legend_entry"], "u:troffer")
            self.assertEqual(manifest["records"][0]["source_width"], 30)
            self.assertEqual(manifest["exclusions"]["duplicate_source_box"], 1)
            self.assertIn("not production", manifest["authorization"])
            self.assertEqual(sha256((revision / "source-review.json").read_bytes()).hexdigest(), original_hash)
            with self.assertRaises(FileExistsError):
                build(revision, output)

    def test_unrecorded_changes_are_rejected(self):
        with TemporaryDirectory(prefix="ved-linked-manifest-") as folder:
            root = Path(folder)
            revision = self.make_revision(root)
            linked_path = revision / "linked-review.json"
            linked = json.loads(linked_path.read_text())
            linked["sheets"][0]["annotations"][1]["label"] = "Wrong"
            linked_path.write_text(json.dumps(linked))
            with self.assertRaisesRegex(ValueError, "annotation evidence"):
                build(revision, root / "manifest.json")

    def test_all_approved_scope_counts_existing_only_and_zero_example_classes(self):
        with TemporaryDirectory(prefix="ved-linked-manifest-") as folder:
            root = Path(folder)
            revision = self.make_revision(root)
            source_path = revision / "source-review.json"
            linked_path = revision / "linked-review.json"
            audit_path = revision / "audit.json"
            source = json.loads(source_path.read_text())
            linked = json.loads(linked_path.read_text())
            audit = json.loads(audit_path.read_text())
            extra = {"id": "three", "layer": "symbols", "review_state": "corrected",
                     "class_state": "approved_legend_mapping", "legend_entry": "drawing:L2",
                     "label": "Switch", "geometry": {"type": "bbox", "coordinates": [15, 3, 25, 20]}}
            source["sheets"][0]["annotations"].append(extra)
            linked["sheets"][0]["annotations"].append(extra)
            audit["approved_legends"].extend([
                {"legend_entry": "drawing:L2", "label": "Switch", "linked_this_revision": 0},
                {"legend_entry": "drawing:L3", "label": "Outlet", "linked_this_revision": 0},
            ])
            source_path.write_text(json.dumps(source))
            linked_path.write_text(json.dumps(linked))
            audit["source_session_sha256"] = sha256(source_path.read_bytes()).hexdigest()
            audit_path.write_text(json.dumps(audit))
            output = root / "all.json"
            result = build(revision, output, all_approved=True)
            manifest = json.loads(output.read_text())
            self.assertEqual((result["records"], result["classes"]), (2, 2))
            self.assertEqual(manifest["catalog_coverage"], {
                "approved_classes": 3, "eligible_classes": 2,
                "without_eligible_boxes": 1, "eligible_boxes": 2,
                "by_class": [
                    {"legend_entry": "drawing:L2", "eligible_boxes": 1},
                    {"legend_entry": "drawing:L3", "eligible_boxes": 0},
                    {"legend_entry": "u:troffer", "eligible_boxes": 1},
                ],
            })
            default = root / "linked.json"
            self.assertEqual(build(revision, default)["records"], 1)


if __name__ == "__main__":
    unittest.main()
