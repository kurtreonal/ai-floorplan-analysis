import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from prepare_symbol_detector_dev import build, digest, overlapping_reviewed_records, tile_supervision
from probe_symbol_detector_dev import fuse, iou, origins, match_targets, probe, probe_unreviewed_image
from app.ai.symbol_detection.partial_label_training import (
    local_negative_mask, ReviewedBoxOnlyLoss, ReviewedBoxOnlyTrainer,
)


class DetectorDevelopmentDatasetTests(unittest.TestCase):
    def test_unreviewed_upload_probe_never_invents_metrics_or_changes_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = root / "page.png"
            Image.new("RGB", (200, 200), "white").save(original)
            before = digest(original)
            with patch("app.ai.floor_plan_interpretation.multiclass_symbol_detector.locate",
                       return_value=(({"bbox": (10, 10, 30, 30), "class_id": 1,
                                       "score": .7, "tile_origin": (0, 0)},), False)):
                summary = probe_unreviewed_image(original, root / "out")
                self.assertEqual(summary["proposals"], 1)
                self.assertIsNone(summary["precision"])
                self.assertIsNone(summary["recall"])
                self.assertEqual(digest(original), before)
                report = json.loads((root / "out/report.json").read_text())
                self.assertEqual(report["source_sha256"], before)
                self.assertTrue((root / "out/overlay.png").is_file())
                with self.assertRaises(FileExistsError):
                    probe_unreviewed_image(original, root / "out")

    def test_native_grid_alignment_preserves_seam_targets_and_source_coordinates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = root / "source"
            sources.mkdir()
            original = sources / "page.png"
            Image.new("RGB", (900, 900), "white").save(original)
            before = digest(original)
            # First target fits native windows; second spans every local grid
            # seam but still fits a 256px centered training window.
            records = [{"id": name, "sheet_id": "sheet-1", "source_sha256": before,
                        "legend_entry": legend, "label": "Fixture", "group": "1",
                        "bbox": box, "split": "train"}
                       for name, legend, box in (("fit", "L1", [100, 100, 120, 120]),
                                                ("seam", "L2", [180, 180, 390, 390]))]
            manifest = root / "input.json"
            manifest.write_text(json.dumps({"schema": "ved-reviewed-symbol-crops-v1", "records": records}))
            output = root / "out"
            build(manifest, sources, output, context_mode="full_partial",
                  include_reviewed_neighbors=True, reviewed_box_only=True,
                  all_entries=True, align_inference_grid=True)
            data = json.loads((output / "manifest.json").read_text())
            self.assertEqual([r["grid_alignment"] for r in data["images"]],
                             ["native_inference_window", "centered_fallback_no_full_native_window"])
            self.assertEqual([c["samples"] for c in data["classes"]], [1, 1])
            for row in data["images"]:
                left, top = row["tile_origin"]
                cls, x, y, w, h = map(float, (output / "labels/train" / f"{row['record_id']}.txt").read_text().split())
                recovered = [left+(x-w/2)*256, top+(y-h/2)*256,
                             left+(x+w/2)*256, top+(y+h/2)*256]
                for actual, expected in zip(recovered, row["source_box"]):
                    self.assertAlmostEqual(actual, expected, places=4)
            self.assertEqual(digest(original), before)

    def test_all_entries_retains_scarce_overlaps_and_augments_without_new_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root = root / "source"
            source_root.mkdir()
            original = source_root / "page.png"
            Image.new("RGB", (400, 400), "white").save(original)
            before = digest(original)
            records = [{"id": name, "sheet_id": "sheet-1", "source_sha256": before,
                        "legend_entry": legend, "label": "Fixture", "group": "1",
                        "bbox": box, "split": "train"}
                       for name, legend, box in (("a", "L1", [180, 180, 200, 200]),
                                                ("b", "L2", [181, 180, 201, 200]))]
            manifest = root / "input.json"
            manifest.write_text(json.dumps({"schema": "ved-reviewed-symbol-crops-v1", "records": records}))
            output = root / "out"
            build(manifest, source_root, output, context_mode="full_partial",
                  include_reviewed_neighbors=True, reviewed_box_only=True,
                  all_entries=True, balance_minimum=3)
            data = json.loads((output / "manifest.json").read_text())
            self.assertEqual([c["samples"] for c in data["classes"]], [1, 1])
            self.assertEqual(len(data["images"]), 6)
            self.assertEqual(data["balanced_augmentation"]["independent_sources_added"], 0)
            self.assertEqual(data["overlap_exclusion_proposals"][0]["decision"],
                             "retained_owner_attested_overlap_requires_review")
            for row in data["images"]:
                labels = (output / "labels/train" / f"{row['record_id']}.txt").read_text().splitlines()
                self.assertEqual({int(line.split()[0]) for line in labels}, {0, 1})
                for line in labels:
                    _, x, y, w, h = map(float, line.split())
                    self.assertTrue(0 <= x-w/2 < x+w/2 <= 1)
                    self.assertTrue(0 <= y-h/2 < y+h/2 <= 1)
            self.assertEqual(digest(original), before)

    def test_probe_scores_unique_neighbor_targets_without_claiming_precision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root = root / "source"
            source_root.mkdir()
            original = source_root / "sheet.png"
            Image.new("RGB", (200, 200), "white").save(original)
            source_hash = digest(original)
            dataset = root / "dataset"
            dataset.mkdir()
            targets = [{"record_id": name, "sheet_id": "sheet-1", "source_sha256": source_hash,
                        "class_id": cls, "source_box": box}
                       for name, cls, box in (("a", 0, [10, 10, 30, 30]),
                                              ("b", 1, [50, 10, 70, 30]),
                                              ("c", 1, [100, 10, 120, 30]))]
            (dataset / "manifest.json").write_text(json.dumps({
                "kind": "positive_only_masked_symbol_detection_diagnostic_v1",
                "class_agnostic": False, "images": targets[:1], "reviewed_targets": targets,
                "classes": [{"id": 0, "legend_entry": "L1", "label": "Fixture"},
                            {"id": 1, "legend_entry": "L2", "label": "Switch"}]}))
            checkpoint = root / "mock.pt"
            checkpoint.write_bytes(b"mock contract test only")
            boxes = [SimpleNamespace(xyxy=torch.tensor([target["source_box"]]),
                                     cls=torch.tensor([0]), conf=torch.tensor([.8]))
                     for target in targets[:2]]
            model = SimpleNamespace(predict=lambda *args, **kwargs: [SimpleNamespace(boxes=boxes)])
            output = root / "probe"
            with patch("probe_symbol_detector_dev.YOLO", return_value=model):
                probe(dataset, source_root, checkpoint, output, inference_mode="full")
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(report["summary"]["reviewed_positive_count"], 3)
            self.assertEqual(report["summary"]["localized"], 2)
            self.assertEqual(report["summary"]["localized_and_classified"], 1)
            self.assertAlmostEqual(report["summary"]["reviewed_positive_class_recall"], 1/3)
            self.assertIsNone(report["precision"])
            self.assertIsNone(report["summary"]["independent_project_accuracy"])
            self.assertTrue((output / report["pages"][0]["overlay"]).is_file())

    def test_detection_matching_does_not_double_count_and_separates_classification(self):
        targets = [{"source_box": [0, 0, 10, 10], "class_id": 1},
                   {"source_box": [1, 0, 11, 10], "class_id": 1}]
        predictions = [{"bbox": [0, 0, 10, 10], "class_id": 2}]
        self.assertEqual(len(match_targets(targets, predictions, require_class=False)), 1)
        self.assertEqual(match_targets(targets, predictions), {})
        predictions[0]["class_id"] = 1
        self.assertEqual(len(match_targets(targets, predictions)), 1)

    def test_one_to_one_matching_recovers_alternative_instead_of_greedy_undercount(self):
        targets = [{"source_box": [0, 0, 10, 10], "class_id": 1},
                   {"source_box": [2, 0, 12, 10], "class_id": 1}]
        predictions = [{"bbox": [1, 0, 11, 10], "class_id": 1},
                       {"bbox": [-3, 0, 7, 10], "class_id": 1}]
        self.assertEqual(match_targets(targets, predictions), {0: 1, 1: 0})

    def test_full_context_supervises_all_visible_reviewed_neighbors(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root = root / "source"
            source_root.mkdir()
            original = source_root / "sheet.png"
            Image.new("RGB", (400, 400), "white").save(original)
            before = digest(original)
            records = [{"id": name, "sheet_id": "sheet-1", "source_sha256": before,
                        "legend_entry": legend, "label": label, "group": "1",
                        "bbox": box, "split": "train"}
                       for name, legend, label, box in (
                           ("one", "drawing:L1", "Fixture", [180, 180, 200, 200]),
                           ("two", "drawing:L2", "Switch", [210, 180, 230, 200]),
                           ("far", "drawing:L2", "Switch", [350, 350, 370, 370]))]
            manifest = root / "input.json"
            manifest.write_text(json.dumps({"schema": "ved-reviewed-symbol-crops-v1", "records": records}))
            source_before = digest(manifest)
            output = root / "out"
            build(manifest, source_root, output, labels=("Fixture", "Switch"),
                  context_mode="full_partial", include_reviewed_neighbors=True,
                  reviewed_box_only=True)
            lines = (output / "labels/train/one.txt").read_text().splitlines()
            self.assertEqual([int(line.split()[0]) for line in lines], [0, 1])
            second_box = list(map(float, lines[1].split()[1:]))
            self.assertAlmostEqual(second_box[0], 158/256)
            self.assertAlmostEqual(second_box[1], .5)
            data = json.loads((output / "manifest.json").read_text())
            self.assertEqual(data["unique_supervised_records"], 3)
            self.assertEqual(data["required_loss"], "positive_and_reviewed_box_only")
            self.assertEqual(data["supervised_label_occurrences"], 5)
            self.assertEqual([c["samples"] for c in data["classes"]], [1, 2])
            self.assertEqual({r["record_id"] for r in data["images"][0]["supervised_records"]},
                             {"one", "two"})
            self.assertEqual(digest(original), before)
            self.assertEqual(digest(manifest), source_before)

    def test_invalid_neighbor_rejected_before_any_tile_label_is_written(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root = root / "source"
            source_root.mkdir()
            original = source_root / "sheet.png"
            Image.new("RGB", (400, 400), "white").save(original)
            records = [{"id": name, "sheet_id": "sheet-1", "source_sha256": digest(original),
                        "legend_entry": "L1", "label": "Fixture", "group": "1",
                        "bbox": box, "split": "train"}
                       for name, box in (("first", [20, 20, 30, 30]),
                                         ("invalid", [50, 10, float("inf"), 30]))]
            manifest = root / "input.json"
            manifest.write_text(json.dumps({"schema": "ved-reviewed-symbol-crops-v1", "records": records}))
            output = root / "out"
            with self.assertRaisesRegex(ValueError, "Reviewed box lies outside"):
                build(manifest, source_root, output, labels=("Fixture",),
                      context_mode="full_partial", include_reviewed_neighbors=True)
            self.assertEqual(list((output / "labels/train").iterdir()), [])

    def test_overlapping_conflicting_and_duplicate_boxes_are_only_exclusion_proposals(self):
        records = [{"id": "a", "legend_entry": "L1", "bbox": [10, 10, 30, 30]},
                   {"id": "b", "legend_entry": "L2", "bbox": [11, 10, 31, 30]},
                   {"id": "c", "legend_entry": "L2", "bbox": [12, 10, 32, 30]},
                   {"id": "d", "legend_entry": "L1", "bbox": [50, 10, 70, 30]}]
        before = json.dumps(records)
        excluded, pairs = overlapping_reviewed_records(records)
        self.assertEqual(excluded, {"a", "b", "c"})
        self.assertEqual(len(pairs), 3)
        self.assertTrue(all(p["decision"] == "assistant_experiment_exclusion_not_label_correction" for p in pairs))
        self.assertEqual(tile_supervision(records, [0, 0, 100, 100], excluded), [records[3]])
        self.assertEqual(json.dumps(records), before)

    def test_known_clipped_targets_near_supervised_collar_skip_tile_not_negative_truth(self):
        records = [{"id": "complete", "legend_entry": "L1", "bbox": [70, 10, 90, 30]},
                   {"id": "partial", "legend_entry": "L2", "bbox": [95, 10, 115, 30]}]
        self.assertEqual(tile_supervision(records, [0, 0, 100, 100], set()), [])
        # A distant clipped symbol stays ignored outside the local supervised collar.
        records[0]["bbox"] = [10, 10, 30, 30]
        self.assertEqual(tile_supervision(records, [0, 0, 100, 100], set()), [records[0]])

    def test_masked_positive_tiles_preserve_source_and_legend_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root = root / "source"
            source_root.mkdir()
            original = source_root / "sheet-1.png"
            image = Image.new("RGB", (400, 400), "white")
            image.putpixel((40, 40), (0, 0, 0))
            image.putpixel((220, 220), (0, 0, 0))  # not reviewed; must not leak into first tile
            image.save(original)
            before = digest(original)
            manifest = root / "input.json"
            manifest.write_text(json.dumps({
                "schema": "ved-reviewed-symbol-crops-v1",
                "records": [{"id": "first", "sheet_id": "sheet-1", "source_sha256": before,
                             "legend_entry": "drawing-a:L1", "label": "Fixture", "group": "1",
                             "bbox": [35, 35, 45, 45], "split": "train"},
                            {"id": "second", "sheet_id": "sheet-1", "source_sha256": before,
                             "legend_entry": "drawing-b:L1", "label": "Fixture", "group": "1",
                             "bbox": [215, 215, 225, 225], "split": "train"},
                            {"id": "reference", "sheet_id": "sheet-52", "source_sha256": before,
                             "legend_entry": "reference:L1", "label": "Fixture", "group": "22",
                             "bbox": [215, 215, 225, 225], "split": "train"}]}))
            output = root / "out"
            summary = build(manifest, source_root, output, labels=("Fixture",))
            self.assertEqual(summary, {"images": 2, "classes": 2, "sheets": 1})
            self.assertEqual(digest(original), before)
            audit = json.loads((output / "manifest.json").read_text())
            self.assertEqual({row["legend_entry"] for row in audit["classes"]},
                             {"drawing-a:L1", "drawing-b:L1"})
            self.assertEqual(audit["reference_rights_exclusions"]["selected_records_excluded"], 1)
            self.assertFalse((output / "images/train/reference.png").exists())
            with Image.open(output / "images/train/first.png") as tile:
                self.assertEqual(tile.getpixel((64, 64)), (0, 0, 0))
                self.assertEqual(tile.getpixel((0, 0)), (255, 255, 255))
            with self.assertRaises(FileExistsError):
                build(manifest, source_root, output, labels=("Fixture",))

    def test_source_pixel_fusion_retains_neighbors(self):
        self.assertEqual(origins(500), [0, 192, 244])
        self.assertAlmostEqual(iou([0, 0, 10, 10], [5, 0, 15, 10]), 1 / 3)
        rows = [{"bbox": [0, 0, 10, 10], "class_id": 1, "score": .8},
                {"bbox": [1, 0, 11, 10], "class_id": 1, "score": .7},
                {"bbox": [11, 0, 21, 10], "class_id": 1, "score": .6}]
        self.assertEqual(len(fuse(rows)), 2)

    def test_class_agnostic_localization_preserves_approved_legend_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root = root / "source"
            source_root.mkdir()
            original = source_root / "sheet-1.png"
            Image.new("RGB", (400, 400), "white").save(original)
            before = digest(original)
            manifest = root / "input.json"
            manifest.write_text(json.dumps({
                "schema": "ved-reviewed-symbol-crops-v1",
                "records": [
                    {"id": "one", "sheet_id": "sheet-1", "source_sha256": before,
                     "legend_entry": "drawing:L1", "label": "Fixture", "group": "1",
                     "bbox": [35, 35, 45, 45], "split": "train"},
                    {"id": "two", "sheet_id": "sheet-1", "source_sha256": before,
                     "legend_entry": "drawing:L2", "label": "Switch", "group": "1",
                     "bbox": [215, 215, 225, 225], "split": "train"},
                ],
            }))
            output = root / "generic"
            self.assertEqual(build(manifest, source_root, output,
                                   context_mode="full_partial", class_agnostic=True),
                             {"images": 2, "classes": 1, "sheets": 1})
            data = json.loads((output / "manifest.json").read_text())
            self.assertEqual(data["classes"], [{"id": 0, "legend_entry": None,
                                                  "label": "Reviewed electrical symbol", "samples": 2}])
            self.assertEqual(data["source_legend_classes"], 2)
            self.assertEqual({row["legend_entry"] for row in data["images"]},
                             {"drawing:L1", "drawing:L2"})
            self.assertTrue(all((output / "labels/train" / f"{name}.txt").read_text().startswith("0 ")
                                for name in ("one", "two")))
            self.assertEqual(digest(original), before)

    def test_versioned_source_dimensions_must_match_exact_pixels(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root = root / "source"
            source_root.mkdir()
            original = source_root / "sheet-1.png"
            Image.new("RGB", (400, 400), "white").save(original)
            manifest = root / "input.json"
            manifest.write_text(json.dumps({
                "schema": "ved-reviewed-symbol-crops-v1",
                "records": [{"id": "first", "sheet_id": "sheet-1",
                             "source_sha256": digest(original), "source_width": 401,
                             "source_height": 400, "legend_entry": "drawing-a:L1",
                             "label": "Fixture", "group": "1",
                             "bbox": [35, 35, 45, 45], "split": "train"}],
            }))
            with self.assertRaisesRegex(ValueError, "Source image dimensions"):
                build(manifest, source_root, root / "out", labels=("Fixture",))

    def test_partial_label_loss_masks_unreviewed_anchors(self):
        anchors = torch.tensor([[10., 10.], [25., 25.], [80., 80.]])
        boxes = torch.tensor([[[8., 8., 16., 16.]]])
        valid = torch.tensor([[[True]]])
        self.assertEqual(local_negative_mask(anchors, boxes, valid).tolist(),
                         [[True, True, False]])
        self.assertEqual(local_negative_mask(anchors, boxes, torch.tensor([[[False]]])).tolist(),
                         [[False, False, False]])
        self.assertEqual(local_negative_mask(anchors, boxes, torch.tensor([[[1.0]]])).tolist(),
                         [[True, True, False]])

    def test_reviewed_box_only_mask_gives_unlabeled_collar_zero_gradient(self):
        anchors = torch.tensor([[10., 10.], [25., 25.], [80., 80.]])
        boxes = torch.tensor([[[8., 8., 16., 16.]]])
        mask = local_negative_mask(anchors, boxes, torch.tensor([[[True]]]),
                                   margin_pixels=ReviewedBoxOnlyLoss.negative_margin_pixels)
        self.assertEqual(mask.tolist(), [[True, False, False]])
        logits = torch.zeros((1, 3, 2), requires_grad=True)
        bce = torch.nn.functional.binary_cross_entropy_with_logits(
            logits, torch.zeros_like(logits), reduction="none")
        (bce * mask.unsqueeze(-1)).sum().backward()
        self.assertTrue((logits.grad[0, 0] != 0).all())
        self.assertEqual(logits.grad[0, 1:].abs().sum().item(), 0)

    def test_training_preserves_numeric_class_identity_when_labels_share_wording(self):
        from ultralytics.nn.tasks import DetectionModel
        source = DetectionModel("yolo11n.yaml", nc=2, ch=3, verbose=False)
        source.names = {0: "Fixture", 1: "Fixture"}
        with torch.no_grad():
            for branch in source.model[-1].cv3:
                branch[-1].bias.copy_(torch.tensor([10., 20.]))
        trainer = ReviewedBoxOnlyTrainer.__new__(ReviewedBoxOnlyTrainer)
        trainer.args = SimpleNamespace(cls_remap=False)
        trainer.data = {"nc": 2, "channels": 3, "names": source.names}
        loaded = trainer.get_model(cfg=source.yaml, weights=source, verbose=False)
        for branch in loaded.model[-1].cv3:
            self.assertEqual(branch[-1].bias.tolist(), [10., 20.])
        from ultralytics.utils import DEFAULT_CFG
        loaded.args = DEFAULT_CFG  # normally attached during trainer setup
        self.assertEqual(loaded.init_criterion().negative_margin_pixels, 0)


if __name__ == "__main__":
    unittest.main()
