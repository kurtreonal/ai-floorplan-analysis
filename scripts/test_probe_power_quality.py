"""Source-bound probe regressions without loading a checkpoint or running CV."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

import probe_power_quality as probe_module
from probe_symbol_detector_dev import match_targets
from prepare_authored_legend_extension import digest
import test_power_quality_replay as replay_tests

snapshot, write_json = replay_tests.snapshot, replay_tests.write_json


class PowerQualityProbeTests(unittest.TestCase):
    def fixture(self, root):
        return replay_tests.PowerQualityReplayTests().disk_fixture(root, size=(801, 805))

    def model(self, paths):
        classes = json.loads((paths[0] / 'manifest.json').read_text())['classes']
        return SimpleNamespace(names={r['id']: r['label'] for r in classes})

    def test_negative_scoring_excludes_unknown_regions_and_uses_half_open_centers(self):
        predictions = [{'bbox': box} for box in (
            [10,10,20,20], [700,700,710,710], [250,10,262,20], [-2,10,2,20],
            [245,10,265,20])]
        regions = [{'box': [0,0,256,256]}, {'box': [10,10,30,30]}]
        before = deepcopy((predictions, regions))
        self.assertEqual(probe_module.negative_proposals(predictions, regions), [0,3,4])
        self.assertEqual((predictions, regions), before)

    def test_frozen_matching_is_class_aware_one_to_one_at_iou_half(self):
        targets = [{'source_box': [0,0,30,30], 'class_id': 58},
                   {'source_box': [0,31,30,61], 'class_id': 58}]
        predictions = [{'bbox': [0,0,30,30], 'class_id': 58},
                       {'bbox': [0,31,30,61], 'class_id': 58}]
        self.assertEqual(match_targets(targets, predictions), {0: 0, 1: 1})
        self.assertEqual(len(match_targets(targets * 2, predictions)), 2)
        self.assertEqual(match_targets(targets[:1], [{'bbox': [0,0,15,30], 'class_id': 58}]), {0: 0})
        self.assertEqual(match_targets(targets[:1], [{'bbox': [0,0,14.99,30], 'class_id': 58}]), {})
        wrong = [{'bbox': [0,0,30,30], 'class_id': 68}]
        self.assertEqual(match_targets(targets, wrong), {})
        self.assertEqual(match_targets(targets, wrong, require_class=False), {0: 0})

    def test_probe_recovers_rounded_source_coordinates_and_never_claims_precision(self):
        with TemporaryDirectory() as folder:
            paths = self.fixture(Path(folder))
            evidence = json.loads(paths[2].read_text())
            evidence['targets'].append({**evidence['targets'][0], 'id': 'outlet02',
                                       'box': [380,415,415,445]})
            write_json(paths[2], evidence)
            expected = [t['box'] for t in evidence['targets']] + [[10,10,20,20], [700,700,710,710]]
            before_parent, before_source = snapshot(paths[0]), snapshot(paths[1])
            pixels_seen = []

            def locate(pixels, *, catalog):
                self.assertEqual(catalog['threshold'], .5)
                self.assertEqual(len(catalog['classes']), 80)
                sx, sy = pixels.shape[1] / 801, pixels.shape[0] / 805
                return [{'bbox': [a*sx,b*sy,c*sx,d*sy], 'class_id': 58, 'score': .9}
                        for a,b,c,d in expected], False

            def walls(pixels):
                pixels_seen.append(pixels.copy())
                return SimpleNamespace(walls=SimpleNamespace(items=[]))

            with patch.object(probe_module, 'YOLO', return_value=self.model(paths)) as loader, \
                    patch.object(probe_module.runtime.shared, 'locate', side_effect=locate), \
                    patch.object(probe_module, 'interpret_floor_plan_demo', side_effect=walls):
                result = probe_module.probe(*paths)
                loader.assert_called_once()
            report = json.loads((paths[-1] / 'report.json').read_text())
            self.assertEqual([r['scale'] for r in result], [1, .375])
            self.assertEqual(report['threshold'], .5)
            self.assertEqual(report['matching'], 'one-to-one class-aware IoU >= .50 in source coordinates')
            self.assertEqual(report['inspection_sha256'], digest(paths[2]))
            self.assertEqual(report['checkpoint_sha256'], digest(paths[3]))
            self.assertFalse(report['human_review_claim'])
            self.assertIsNone(report['precision'])
            self.assertIsNone(report['independent_accuracy'])
            for row in report['outcomes']:
                self.assertEqual(row['targets'], 2)
                self.assertEqual(row['class_and_location_matches'], 2)
                self.assertEqual(row['localization_matches'], 2)
                self.assertEqual(row['negative_prediction_indices'], [2])
                self.assertEqual(row['inspected_negative_proposals'], 1)
                self.assertIsNone(row['precision'])
                self.assertIsNone(row['independent_accuracy'])
                for predicted, box in zip(row['predictions'], expected):
                    np.testing.assert_allclose(predicted['bbox'], box, atol=1e-10)
                self.assertEqual(row['per_class'][0], {'class_id': 58, 'targets': 2,
                                                      'prediction_count': 4, 'matched': 2})
            reduced = report['outcomes'][1]
            self.assertEqual(reduced['actual_scale_xy'], [300/801, 302/805])
            self.assertNotEqual(reduced['actual_scale_xy'][0], .375)
            self.assertTrue(all(np.all(pixels == 255) for pixels in pixels_seen))
            self.assertEqual(snapshot(paths[0]), before_parent)
            self.assertEqual(snapshot(paths[1]), before_source)
            with self.assertRaises(FileExistsError): probe_module.probe(*paths)

    def test_probe_rejects_changed_frozen_source_and_parent_before_model_loading(self):
        for relative in ('parent/manifest.json', 'prepared/manifest.json', 'prepared/original.pdf',
                         'prepared/source-authorization.json', 'prepared/power.png'):
            with self.subTest(file=relative), TemporaryDirectory() as folder:
                root = Path(folder); paths = self.fixture(root)
                with (root / relative).open('ab') as stream: stream.write(b' ')
                with patch.object(probe_module, 'YOLO') as loader:
                    with self.assertRaises(ValueError): probe_module.probe(*paths)
                    loader.assert_not_called()
                self.assertFalse(paths[-1].exists())

    def test_probe_rejects_permission_not_covering_exact_source_even_when_rehashed(self):
        for changes in ({'allowed_purposes': ['evaluation']}, {'source_sha256': 'f'*64}):
            with self.subTest(changes=changes), TemporaryDirectory() as folder:
                paths = self.fixture(Path(folder))
                permission = paths[1] / 'source-authorization.json'
                auth = json.loads(permission.read_text()); auth.update(changes); write_json(permission, auth)
                source = json.loads((paths[1] / 'manifest.json').read_text())
                source['authorization_sha256'] = digest(permission)
                write_json(paths[1] / 'manifest.json', source)
                evidence = json.loads(paths[2].read_text())
                evidence['prepared_manifest_sha256'] = digest(paths[1] / 'manifest.json')
                write_json(paths[2], evidence)
                with patch.object(probe_module, 'YOLO') as loader:
                    with self.assertRaises(ValueError): probe_module.probe(*paths)
                    loader.assert_not_called()
                self.assertFalse(paths[-1].exists())

    def test_candidate_probe_requires_explicit_frozen_parent_and_exact_lineage(self):
        with TemporaryDirectory() as folder:
            paths = self.fixture(Path(folder))
            replay_tests.prepare(*paths)
            frozen, prepared, inspection, checkpoint, candidate = paths
            with self.assertRaises(ValueError):
                probe_module.validate_probe_inputs(candidate, prepared, inspection, checkpoint)
            data, source, evidence, region, path = probe_module.validate_probe_inputs(
                candidate, prepared, inspection, checkpoint, frozen_parent=frozen)
            self.assertEqual(data['parent_dataset_sha256'], digest(frozen / 'manifest.json'))
            self.assertEqual(data['classes'], json.loads((frozen / 'manifest.json').read_text())['classes'])
            self.assertEqual(evidence['parent_manifest_sha256'], digest(frozen / 'manifest.json'))
            self.assertEqual(source['source_sha256'], evidence['source_sha256'])
            self.assertEqual(path, prepared / region['filename'])

    def test_candidate_cannot_change_classes_lineage_copied_inspection_or_authorization(self):
        for change in ('classes', 'lineage', 'inspection', 'authorization', 'frozen_parent'):
            with self.subTest(change=change), TemporaryDirectory() as folder:
                paths = self.fixture(Path(folder)); replay_tests.prepare(*paths)
                frozen, prepared, inspection, checkpoint, candidate = paths
                manifest = candidate / 'manifest.json'; data = json.loads(manifest.read_text())
                if change == 'classes':
                    data['classes'][58]['legend_entry'] = 'different-source:58'
                    write_json(manifest, data)
                elif change == 'lineage':
                    data['parent_dataset_sha256'] = 'e'*64
                    write_json(manifest, data)
                else:
                    if change == 'inspection':
                        target = candidate / 'power-inspection.json'
                        archived = candidate / 'power-inspections' / (digest(inspection)+'.json')
                        with archived.open('ab') as stream: stream.write(b' ')
                    elif change == 'authorization':
                        target = candidate / data['additional_training_authorizations'][-1]['filename']
                    else:
                        target = frozen / 'manifest.json'
                    with target.open('ab') as stream: stream.write(b' ')
                with self.assertRaises(ValueError):
                    probe_module.validate_probe_inputs(candidate, prepared, inspection, checkpoint,
                                                       frozen_parent=frozen)

    def test_phase_replay_has_one_verified_ancestor_and_rejects_changed_history(self):
        with TemporaryDirectory() as folder:
            root = Path(folder); paths = self.fixture(root); replay_tests.prepare(*paths)
            frozen, prepared, inspection, checkpoint, candidate = paths
            phase = root / 'phase'; replay_tests.replay_negatives(candidate, checkpoint, phase)
            manifest = phase / 'manifest.json'; original_bytes = manifest.read_bytes()
            original = json.loads(original_bytes)
            before_frozen = snapshot(frozen)
            data, _, evidence, _, _ = probe_module.validate_probe_inputs(
                phase, prepared, inspection, checkpoint, frozen_parent=frozen)
            self.assertEqual(data['parent_dataset_sha256'], digest(candidate / 'manifest.json'))
            self.assertEqual(evidence['parent_manifest_sha256'], digest(frozen / 'manifest.json'))
            self.assertEqual(snapshot(frozen), before_frozen)
            ancestor = phase / 'lineage' / (data['parent_dataset_sha256']+'.json')
            ancestor_bytes = ancestor.read_bytes()
            with ancestor.open('ab') as stream: stream.write(b' ')
            with self.assertRaisesRegex(ValueError, 'artifact'):
                probe_module.validate_probe_inputs(phase, prepared, inspection, checkpoint, frozen_parent=frozen)
            ancestor.write_bytes(ancestor_bytes)
            for key in ('power_source_targets', 'power_negative_regions', 'authorized_pdf_training_images',
                        'assistant_reviewed_background_regions'):
                changed = deepcopy(original); changed[key] = changed[key][1:]
                write_json(manifest, changed)
                with self.subTest(history=key), self.assertRaisesRegex(ValueError, 'history'):
                    probe_module.validate_probe_inputs(phase, prepared, inspection, checkpoint, frozen_parent=frozen)
            manifest.write_bytes(original_bytes)
            changed_ancestor = json.loads(ancestor_bytes)
            changed_ancestor['parent_dataset_sha256'] = 'e'*64
            untrusted = phase / 'lineage/untrusted.json'; write_json(untrusted, changed_ancestor)
            spoofed_hash = digest(untrusted)
            untrusted.rename(phase / 'lineage' / (spoofed_hash+'.json'))
            changed = deepcopy(original); changed['parent_dataset_sha256'] = spoofed_hash
            write_json(manifest, changed)
            with self.assertRaisesRegex(ValueError, 'ancestry'):
                probe_module.validate_probe_inputs(phase, prepared, inspection, checkpoint, frozen_parent=frozen)

    def test_switch_retention_follows_exact_multiple_ancestors_without_rewriting_frozen_evidence(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            paths = replay_tests.PowerQualityReplayTests().switch_fixture(root)
            frozen, prepared, inspection, checkpoint, candidate = paths
            phase = root / 'phase'
            replay_tests.replay_negatives(candidate, checkpoint, phase, hard_mining=True)
            retained = root / 'retained'
            replay_tests.restore_switch_replay(phase, checkpoint, retained)
            snapshots = {p: snapshot(p) for p in (frozen, prepared, candidate, phase)}
            data, _, _, _, _ = probe_module.validate_probe_inputs(
                retained, prepared, inspection, checkpoint, frozen_parent=frozen)
            self.assertEqual(data['parent_dataset_sha256'], digest(phase / 'manifest.json'))
            self.assertEqual(len(data['power_switch_retention_replay']['replicas']), 1)
            for path, before in snapshots.items():
                self.assertEqual(snapshot(path), before)
            manifest = retained / 'manifest.json'
            original = manifest.read_bytes()
            for key in ('classes', 'power_source_targets', 'power_negative_regions',
                        'authorized_pdf_training_images', 'assistant_reviewed_background_regions'):
                changed = deepcopy(data); changed[key] = changed[key][1:]
                write_json(manifest, changed)
                with self.subTest(key=key), self.assertRaises(ValueError):
                    probe_module.validate_probe_inputs(retained, prepared, inspection, checkpoint, frozen_parent=frozen)
            manifest.write_bytes(original)
            archive = retained / 'lineage' / (digest(phase / 'manifest.json')+'.json')
            with archive.open('ab') as stream:
                stream.write(b' ')
            with self.assertRaisesRegex(ValueError, 'artifact'):
                probe_module.validate_probe_inputs(retained, prepared, inspection, checkpoint, frozen_parent=frozen)

    def test_comparison_ancestry_is_bounded_and_cycles_fail_closed(self):
        with TemporaryDirectory() as folder:
            root = Path(folder); paths = self.fixture(root); replay_tests.prepare(*paths)
            frozen, prepared, inspection, checkpoint, candidate = paths
            manifest = candidate / 'manifest.json'
            data = json.loads(manifest.read_text())
            archive = candidate / 'lineage'; archive.mkdir(exist_ok=True)
            # Actual hash-addressed revisions beyond the explicit four-hop bound.
            for revision in range(5):
                prior_bytes = manifest.read_bytes(); prior_hash = digest(manifest)
                (archive / (prior_hash+'.json')).write_bytes(prior_bytes)
                data['parent_dataset_sha256'] = prior_hash
                data['test_revision'] = revision
                write_json(manifest, data)
            with self.assertRaisesRegex(ValueError, 'bounded depth'):
                probe_module.validate_probe_inputs(candidate, prepared, inspection, checkpoint, frozen_parent=frozen)

            # A cycle cannot be manufactured with real SHA identities. Simulate
            # the identity layer only to prove the traversal's repeated-pin guard.
            cycle = deepcopy(data); cycle['parent_dataset_sha256'] = 'e'*64
            write_json(manifest, cycle)
            loop_path = archive / ('e'*64+'.json'); write_json(loop_path, cycle)
            actual_digest = probe_module.digest
            with patch.object(probe_module, 'digest', side_effect=lambda path:
                              'e'*64 if Path(path) == loop_path else actual_digest(path)):
                with self.assertRaisesRegex(ValueError, 'cycle'):
                    probe_module.validate_probe_inputs(candidate, prepared, inspection, checkpoint, frozen_parent=frozen)


if __name__ == '__main__':
    unittest.main()
