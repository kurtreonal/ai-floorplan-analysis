import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from prepare_symbol_detector_dev import build, digest
from probe_symbol_detector_dev import fuse, iou, origins
from app.ai.symbol_detection.partial_label_training import local_negative_mask


class DetectorDevelopmentDatasetTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
