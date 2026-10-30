import unittest
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from prepare_native_symbol_context import context_rows, digest, prepare


class NativeSymbolContextTests(unittest.TestCase):
    def test_masks_remain_local_and_unreviewed_pixels_are_not_background(self):
        targets = [{'record_id': 'light', 'source_box': [100, 100, 120, 120], 'class_id': 54}]
        negatives = [{'id': 'dimension', 'box': [280, 30, 310, 60]}]
        before = deepcopy((targets, negatives))
        rows = context_rows(targets, negatives, (512, 512))
        self.assertEqual((targets, negatives), before)
        self.assertTrue(any(r['labels'] for r in rows))
        self.assertTrue(any(r['negative_regions_training_pixels'] for r in rows))
        for row in rows:
            self.assertFalse(row['reviewed_background'])
            self.assertTrue(row['context_only'])
            for region in row['negative_regions_training_pixels']:
                x, y = row['source_origin']
                a, b, c, d = region['box']
                self.assertGreaterEqual(a/1.25+x, 280)
                self.assertLessEqual(c/1.25+x, 310)
                self.assertGreaterEqual(b/1.25+y, 30)
                self.assertLessEqual(d/1.25+y, 60)

    def test_conflicting_negative_rejected_not_allowed_to_erase_a_label(self):
        with self.assertRaisesRegex(ValueError, 'overlaps'):
            context_rows([{'source_box': [10, 10, 30, 30]}],
                         [{'box': [20, 20, 40, 40]}], (512, 512))

    def test_negative_context_mode_keeps_nearby_labels_without_extra_control_windows(self):
        targets = [{'record_id': 'near', 'source_box': [30, 30, 50, 50], 'class_id': 0},
                   {'record_id': 'far', 'source_box': [450, 450, 470, 470], 'class_id': 1}]
        negatives = [{'id': 'text', 'box': [80, 80, 100, 100]}]
        rows = context_rows(targets, negatives, (512, 512), negative_context_only=True)
        self.assertTrue(all(r['negative_regions_training_pixels'] for r in rows))
        self.assertTrue(any('near' in r['supervised_records'] for r in rows))
        self.assertTrue(all('far' not in r['supervised_records'] for r in rows))
        with self.assertRaisesRegex(ValueError, 'overlaps'):
            context_rows(targets, [{'id': 'bad', 'box': [440, 440, 480, 480]}],
                         (512, 512), negative_context_only=True)

    def test_invalid_or_outside_rectangles_rejected(self):
        for box in ([0, 0, 600, 10], [0, 0, float('nan'), 10], [True, 0, 20, 20], [20, 0, 10, 10]):
            with self.subTest(box=box), self.assertRaises(ValueError):
                context_rows([], [{'box': box}], (512, 512))

    def test_clipped_positives_not_converted_to_partial_boxes(self):
        rows = context_rows([{'record_id': 'large', 'source_box': [10, 10, 400, 400], 'class_id': 1}],
                            [{'id': 'text', 'box': [420, 420, 450, 450]}], (512, 512))
        self.assertTrue(all(not r['labels'] for r in rows))

    def test_preparation_retains_identity_originals_and_all_classes(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, dataset, inspection = (root/name for name in ('source.png', 'dataset.json', 'inspection.json'))
            with Image.new('RGB', (512, 512), 'white') as image:
                image.save(source)
            source_hash = digest(source)
            data = {'classes': [{'id': 0, 'legend_entry': 'drawing:light'},
                                {'id': 1, 'legend_entry': 'drawing:rare'}],
                    'reviewed_targets': [{'record_id': 'original-record', 'source_sha256': source_hash,
                                          'class_id': 0, 'legend_entry': 'drawing:light',
                                          'source_box': [100, 100, 120, 120]}]}
            dataset.write_text(json.dumps(data))
            evidence = {'schema': 'ved-native-symbol-inspection-v1', 'source_sha256': source_hash,
                        'dataset_sha256': digest(dataset),
                        'annotation_origin': 'assistant_visual_under_user_development_authorization',
                        'human_review_claim': False, 'production_approval': False,
                        'missing_annotation_policy': 'ignore_unreviewed_not_empty_background',
                        'background_regions': [{'id': 'text', 'box': [300, 300, 320, 320],
                                                'meaning': 'Inspected text only'}]}
            inspection.write_text(json.dumps(evidence))
            result = prepare(source, dataset, inspection, root/'prepared')
            self.assertEqual(result['all_model_classes_preserved'], 2)
            manifest = json.loads((root/'prepared/manifest.json').read_text())
            self.assertEqual(manifest['positive_records'], data['reviewed_targets'])
            self.assertEqual(manifest['classes'], data['classes'])
            self.assertEqual(digest(source), source_hash)
            self.assertIsNone(manifest['precision'])
            self.assertFalse(manifest['checkpoint_changed'])
            for row in manifest['images']:
                path = root/'prepared'/(row['image_id']+'.png')
                self.assertEqual(digest(path), row['image_sha256'])
                x, y = row['source_origin']
                with Image.open(source) as original, Image.open(path) as actual:
                    with original.crop((x, y, x+256, y+256)) as expected:
                        self.assertEqual(actual.tobytes(), expected.tobytes())
            with self.assertRaises(FileExistsError):
                prepare(source, dataset, inspection, root/'prepared')
            evidence['source_sha256'] = '0'*64
            inspection.write_text(json.dumps(evidence))
            with self.assertRaises(ValueError):
                prepare(source, dataset, inspection, root/'bad')
            self.assertFalse((root/'bad').exists())


if __name__ == '__main__':
    unittest.main()
