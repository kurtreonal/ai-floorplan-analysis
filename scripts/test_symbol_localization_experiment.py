import unittest

import numpy as np

from experiment_symbol_localization import center_error, find_candidates, iou


class LocalizationExperimentTests(unittest.TestCase):
    def test_box_metrics_use_source_pixels(self):
        self.assertEqual(iou([0, 0, 10, 10], [5, 0, 15, 10]), 1 / 3)
        self.assertEqual(center_error([0, 0, 10, 10], [3, 4, 13, 14]), 5)

    def test_matcher_finds_repeated_positive_without_background_labels(self):
        image = np.full((80, 80), 240, dtype=np.uint8)
        glyph = np.full((12, 12), 240, dtype=np.uint8)
        glyph[2:10, 2:4] = 20
        glyph[2:4, 2:10] = 20
        glyph[5:7, 2:8] = 20
        image[5:17, 5:17] = glyph
        image[45:57, 45:57] = glyph
        candidates = find_candidates(image, [("seed", [5, 5, 17, 17])], 0.9)
        self.assertTrue(any(iou(p["bbox"], [5, 5, 17, 17]) > 0.9 for p in candidates))
        self.assertTrue(any(iou(p["bbox"], [45, 45, 57, 57]) > 0.9 for p in candidates))


if __name__ == "__main__":
    unittest.main()
