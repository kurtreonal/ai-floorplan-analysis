import unittest
from probe_whole_pdf_development import recover_boxes, page_targets, map_drawing_region
from probe_symbol_detector_dev import match_targets


class WholePdfCoordinateTests(unittest.TestCase):
    def test_crop_local_power_boxes_and_whole_page_lamps_share_one_source_frame(self):
        page = {'page_number': 7, 'image_sha256': 'page', 'width': 6000, 'height': 4000}
        regions = [{'page_number': 7, 'crop_sha256': 'power', 'bbox_source_pixels': [2000, 1900, 3800, 3000]}]
        data = {'power_source_targets': [{'page_number': 7, 'source_sha256': 'power', 'source_box': [263, 556, 305, 587], 'class_id': 58}],
                'lamp_source_targets': [{'page_number': 7, 'source_sha256': 'page', 'source_box': [500, 2000, 520, 2040], 'class_id': 56}],
                'switch_source_targets': [{'page_number': 8, 'source_sha256': 'page', 'source_box': [0, 0, 10, 10]}]}
        mapped = page_targets(data, page, regions)
        self.assertEqual(len(mapped), 2)
        self.assertEqual(mapped[0]['source_box'], [500, 2000, 520, 2040])
        self.assertEqual(mapped[1]['source_box'], [2263, 2456, 2305, 2487])
        self.assertEqual(data['power_source_targets'][0]['source_box'], [263, 556, 305, 587])

    def test_invalid_declared_crop_box_is_rejected_instead_of_clipped(self):
        page = {'page_number': 7, 'image_sha256': 'page', 'width': 100, 'height': 100}
        with self.assertRaises(ValueError):
            page_targets({'power_source_targets': [{'page_number': 7, 'source_sha256': 'page', 'source_box': [90, 90, 110, 110]}]}, page, [])
        with self.assertRaises(ValueError):
            recover_boxes([], (10, 10), (0, 10))
        with self.assertRaises(ValueError):
            page_targets({}, page, [{'page_number': 7, 'crop_sha256': 'page', 'bbox_source_pixels': [0, 0, 50, 50]}])

    def test_exact_integer_raster_transform_preserves_class_and_location_matching(self):
        expected = [600, 800, 660, 900]
        sx, sy = 4096 / 6000, 2731 / 4000
        predictions = [{'class_id': 58, 'bbox': [expected[0]*sx, expected[1]*sy,
                                               expected[2]*sx, expected[3]*sy], 'score': .7}]
        converted = recover_boxes(predictions, (6000, 4000), (4096, 2731))
        for actual, value in zip(converted[0]['bbox'], expected):
            self.assertAlmostEqual(actual, value)
        self.assertEqual(match_targets([{'class_id': 58, 'source_box': expected}], converted), {0: 0})
        self.assertEqual(predictions[0]['bbox'][0], 600*sx)

    def test_distinct_classes_remain_distinct_and_unmatched_proposals_are_not_false_positive_labels(self):
        converted = recover_boxes([{'class_id': 1, 'bbox': [10, 10, 20, 20]}], (100, 100), (100, 100))
        targets = [{'class_id': 2, 'source_box': [10, 10, 20, 20]}]
        self.assertEqual(match_targets(targets, converted), {})
        self.assertEqual(match_targets(targets, converted, require_class=False), {0: 0})

    def test_region_rounding_covers_declared_rectangle_and_evidence_uses_same_scale(self):
        region = map_drawing_region({'bbox_source_pixels': [305, 1930, 2062, 3014]}, (6000, 4000), (4096, 2731))
        self.assertLessEqual(region.x, 305*4096/6000)
        self.assertGreaterEqual(region.x + region.width, 2062*4096/6000)
        self.assertLessEqual(region.y, 1930*2731/4000)
        self.assertGreaterEqual(region.y + region.height, 3014*2731/4000)
        observation = {'bbox': [10, 20, 30, 40], 'tile_origin': [0, 0], 'class_id': 58}
        result = recover_boxes([{**observation, 'localization_observations': [observation]}], (6000, 4000), (4096, 2731))
        self.assertEqual(result[0]['localization_observations'][0]['bbox'], result[0]['bbox'])
        self.assertEqual(observation['bbox'], [10, 20, 30, 40])
        with self.assertRaises(ValueError):
            map_drawing_region({'bbox_source_pixels': [0, 0, 6001, 10]}, (6000, 4000), (4096, 2731))


if __name__ == '__main__':
    unittest.main()
