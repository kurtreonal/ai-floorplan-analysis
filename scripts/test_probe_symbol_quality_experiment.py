"""Comparison reports must not turn partial review into accuracy claims."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from PIL import Image

import probe_symbol_quality_experiment as evaluation


class QualityProbeTests(TestCase):
    def fixture(self, root):
        dataset = root / 'dataset'
        dataset.mkdir()
        source = root / 'source'
        source.mkdir()
        page = source / 'sheet-08.jpg'
        Image.new('RGB', (100, 100), 'white').save(page)
        source_hash = evaluation.digest(page)
        reviews = root / 'review.json'
        reviews.write_text(json.dumps({'sheets': [{
            'sheet_id': 'sheet-08', 'source_sha256': source_hash,
            'regions': [[.7, .7, .9, .9]],
        }]}))
        (dataset / 'manifest.json').write_text(json.dumps({
            'negative_review_sha256': evaluation.digest(reviews),
            'classes': [{'id': 0, 'label': 'Light', 'legend_entry': 'drawing:L1'}],
            'reviewed_targets': [{'record_id': 'one', 'sheet_id': 'sheet-08',
                'source_sha256': source_hash, 'class_id': 0, 'source_box': [10, 10, 20, 20]}],
        }))
        checkpoint = root / 'model.pt'
        checkpoint.write_bytes(b'synthetic model fixture')
        return dataset, reviews, source, checkpoint

    def test_partial_review_reports_only_measured_counts_and_preserves_original(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.fixture(root)
            before = evaluation.digest(args[2] / 'sheet-08.jpg')
            predictions = [{'class_id': 0, 'bbox': box, 'score': .7}
                           for box in ([10, 10, 20, 20], [75, 75, 85, 85], [40, 40, 50, 50])]
            with patch.object(evaluation, 'YOLO', return_value=SimpleNamespace(names={0: 'Light'})), \
                 patch.object(evaluation.runtime, 'locate', return_value=(predictions, True)):
                result = evaluation.probe(*args, root / 'output')
            self.assertEqual(result['class_matches'], 1)
            self.assertEqual(result['known_negative_proposals'], 1)
            self.assertEqual(result['proposals'], 3)  # Unknown region is not called a false positive.
            report = json.loads((root / 'output/report.json').read_text())
            self.assertIsNone(report['precision'])
            self.assertIsNone(report['independent_accuracy'])
            self.assertEqual(report['summary']['per_class'][0]['localized_and_classified'], 1)
            self.assertEqual(report['dataset_manifest_sha256'], evaluation.digest(args[0] / 'manifest.json'))
            self.assertEqual(result['truncated_pages'], 1)
            self.assertEqual(evaluation.digest(args[2] / 'sheet-08.jpg'), before)
            with self.assertRaises(FileExistsError):
                evaluation.probe(*args, root / 'output')

    def test_modified_review_or_wrong_class_head_fails_before_inference(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.fixture(root)
            with patch.object(evaluation, 'YOLO', return_value=SimpleNamespace(names={0: 'Other'})), \
                 patch.object(evaluation.runtime, 'locate') as infer:
                with self.assertRaisesRegex(ValueError, 'class identities'):
                    evaluation.probe(*args, root / 'wrong-head')
                args[1].write_text('{}')
                with self.assertRaisesRegex(ValueError, 'Review manifest changed'):
                    evaluation.probe(*args, root / 'changed-review')
                infer.assert_not_called()

    def test_cached_predictions_from_another_checkpoint_are_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.fixture(root)
            cached = root / 'cached.json'
            cached.write_text(json.dumps({'checkpoint_sha256': 'another checkpoint'}))
            with patch.object(evaluation, 'YOLO', return_value=SimpleNamespace(names={0: 'Light'})), \
                 patch.object(evaluation.runtime, 'locate') as infer:
                with self.assertRaisesRegex(ValueError, 'configuration differs'):
                    evaluation.probe(*args, root / 'output', cached)
                infer.assert_not_called()
