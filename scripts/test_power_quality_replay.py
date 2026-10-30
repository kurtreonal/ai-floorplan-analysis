from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from prepare_power_quality_replay import checked_inspection, power_views, prepare, replay_negatives, restore_switch_replay, ORIGIN
from prepare_authored_legend_extension import digest
from train_symbol_detector_dev import validate_restorative_replay


def write_json(path, data):
    path.write_text(json.dumps(data), encoding='utf-8')


def snapshot(path):
    return {p.relative_to(path).as_posix(): p.read_bytes() for p in path.rglob('*') if p.is_file()}


class PowerQualityReplayTests(unittest.TestCase):
    def fixture(self):
        evidence = {'schema': 'ved-delegated-power-quality-inspection-v1', 'human_review_claim': False,
            'production_approval': False, 'annotation_origin': ORIGIN, 'user_statement': 'Delegated development',
            'missing_annotation_policy': 'ignore_unreviewed_not_empty_background', 'source_sha256': 'a' * 64,
            'source_image_sha256': 'b' * 64, 'project_group_id': 'related', 'page_number': 7,
            'layout_region_id': 'power', 'targets': [{'id': 'outlet01', 'box': [380,380,415,410],
                'class_id': 58, 'legend_region_id': 'L12', 'meaning_evidence': 'Source legend glyph'}],
            'background_regions': [{'id': 'grid01', 'box': [0,0,256,256], 'reason': 'Only grid lines'}]}
        parent = {'all_eligible_entries': True, 'classes': [{'id': i, 'label': str(i), 'legend_entry': f'original:{i}'} for i in range(80)]}
        parent['classes'][58]['label'] = 'Duplex outlet'
        region = {'region_id': 'power', 'crop_sha256': 'b' * 64, 'page_number': 7}
        source = {'source_sha256': 'a' * 64, 'project_group_id': 'related', 'regions': [region,
            {'region_id': 'L12', 'kind': 'symbol_legend', 'proposed_label': 'Duplex outlet', 'page_number': 7}]}
        return evidence, parent, source, region

    def check(self, args):
        return checked_inspection(*args, (800,800))

    def switch_fixture(self, root):
        paths = self.disk_fixture(root); prepare(*paths)
        parent = paths[-1]; manifest = parent / 'manifest.json'; data = json.loads(manifest.read_text())
        name = 'pdfdev-switch-fixture'
        ip, lp = parent / 'images/train' / (name+'.png'), parent / 'labels/train' / (name+'.txt')
        ip.write_bytes((parent / 'images/train/prior.png').read_bytes())
        lp.write_text('62 .2 .3 .1 .1\n63 .4 .3 .1 .1\n')
        row = {**data['authorized_pdf_training_images'][0], 'image_id':name,
               'primary_class_id':62, 'supervised_record_ids':['switch01','switch02'],
               'image_sha256':digest(ip), 'label_sha256':digest(lp)}
        data['authorized_pdf_training_images'].append(row)
        data['switch_source_targets'] = [{'record_id':'switch01', 'class_id':62},
                                         {'record_id':'switch02', 'class_id':63}]
        old_name = 'restored-replay-62-000'
        (parent / 'images/train' / (old_name+'.png')).write_bytes(ip.read_bytes())
        (parent / 'labels/train' / (old_name+'.txt')).write_bytes(lp.read_bytes())
        data['restorative_replay_sampling'] = {'independent_examples_added':0,
            'replicas':[{'image_id':old_name, 'sampling_parent':name, 'class_id':62,
                         'split':'train', 'independent_example':False,
                         'image_sha256':digest(ip), 'label_sha256':digest(lp)}]}
        write_json(manifest, data)
        return paths

    def disk_fixture(self, root, size=(800, 800)):
        evidence, parent_data, source, region = self.fixture()
        parent, prepared = root / 'parent', root / 'prepared'
        for folder in ('images/train', 'labels/train', 'images/val', 'labels/val'):
            (parent / folder).mkdir(parents=True)
        prepared.mkdir()
        (parent / 'labels/train/prior.txt').write_text('58 .2 .2 .1 .1\n')
        (parent / 'labels/val/frozen.txt').write_text('71 .4 .4 .1 .1\n')
        for split, name in (('train', 'prior'), ('val', 'frozen')):
            with Image.new('RGB', (8, 8), 'white') as image:
                image.save(parent / f'images/{split}/{name}.png')
        parent_data.update(additional_training_authorizations=[], authorized_pdf_training_images=[],
                           reviewed_background_images=[], warnings=[],
                           required_loss='positive_boxes_and_explicit_reviewed_background',
                           frozen_metrics={'iou': .5, 'threshold': .5, 'split': 'val'})
        write_json(parent / 'manifest.json', parent_data)
        (parent / 'data.yaml').write_text('path: parent\ntrain: images/train\nval: images/val\n')
        (prepared / 'original.pdf').write_bytes(b'synthetic identity fixture, not a real drawing')
        source['source_sha256'] = digest(prepared / 'original.pdf')
        region['filename'] = 'power.png'
        with Image.new('RGB', size, 'white') as image:
            image.save(prepared / region['filename'])
        region['crop_sha256'] = digest(prepared / region['filename'])
        write_json(prepared / 'source-authorization.json', {
            'source_sha256': source['source_sha256'], 'allowed_purposes': ['training']})
        source['authorization_sha256'] = digest(prepared / 'source-authorization.json')
        write_json(prepared / 'manifest.json', source)
        evidence.update(source_sha256=source['source_sha256'], source_image_sha256=region['crop_sha256'],
                        parent_manifest_sha256=digest(parent / 'manifest.json'),
                        prepared_manifest_sha256=digest(prepared / 'manifest.json'))
        inspection, checkpoint = root / 'inspection.json', root / 'checkpoint.pt'
        write_json(inspection, evidence)
        checkpoint.write_bytes(b'no model, hash fixture only')
        return parent, prepared, inspection, checkpoint, root / 'output'

    def test_preserves_source_alias_head_identity_and_no_human_claim(self):
        args = self.fixture(); before = deepcopy(args)
        targets, backgrounds = self.check(args)
        self.assertEqual(args, before)
        self.assertEqual(targets[0]['legend_entry'], 'original:58')
        self.assertEqual(targets[0]['source_legend_entry'], 'pdf-aaaaaaaaaaaa:p7:L12')
        self.assertFalse(targets[0]['human_review_claim'])
        self.assertEqual(targets[0]['project_group_id'], 'related')
        self.assertEqual(targets[0]['split'], 'train')
        self.assertEqual(len(backgrounds), 1)

    def test_forged_approval_wrong_source_and_unknown_background_policy_rejected(self):
        for patch in ({'human_review_claim': True}, {'production_approval': True}, {'source_sha256': 'c'*64},
                      {'source_image_sha256': 'c'*64}, {'project_group_id': 'different'}, {'page_number': 1},
                      {'missing_annotation_policy': 'background'}):
            args = self.fixture(); args[0].update(patch)
            with self.subTest(patch=patch), self.assertRaises(ValueError): self.check(args)

    def test_class_equivalence_requires_source_definition_not_just_a_numeric_index(self):
        args = self.fixture(); args[0]['targets'][0]['class_id'] = 57
        with self.assertRaises(ValueError): self.check(args)
        args = self.fixture(); args[2]['regions'][1]['kind'] = 'wiring_legend_not_device'
        with self.assertRaises(ValueError): self.check(args)

    def test_complete_head_requires_exact_ordered_integer_class_ids(self):
        for value in (57, '58', True):
            args = self.fixture(); args[1]['classes'][58]['id'] = value
            with self.subTest(class_id=value), self.assertRaises(ValueError): self.check(args)
        args = self.fixture()
        args[1]['classes'][57], args[1]['classes'][58] = args[1]['classes'][58], args[1]['classes'][57]
        with self.assertRaises(ValueError): self.check(args)

    def test_source_legend_case_alias_preserves_full_parent_class_identity(self):
        args = self.fixture()
        args[2]['regions'][1]['proposed_label'] = 'DUPLEX OUTLET'
        targets, _ = self.check(args)
        self.assertEqual(targets[0]['class_id'], 58)
        self.assertEqual(targets[0]['label'], 'Duplex outlet')
        for value in ('Duplex socket', 'Duplex outlet '):
            args[2]['regions'][1]['proposed_label'] = value
            with self.subTest(label=value), self.assertRaises(ValueError):
                self.check(args)

    def test_incomplete_head_and_cross_region_authorization_rejected(self):
        for field, value in (('schema', 'other'), ('annotation_origin', 'human'),
                             ('user_statement', ''), ('layout_region_id', 'another')):
            args = self.fixture(); args[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check(args)
        for mutate in (lambda p: p['classes'].pop(), lambda p: p.update(diagnostic_only=True),
                       lambda p: p.update(all_eligible_entries=False)):
            args = self.fixture(); mutate(args[1])
            with self.assertRaises(ValueError): self.check(args)

    def test_overlapping_positive_cannot_become_hard_negative(self):
        args = self.fixture(); args[0]['background_regions'][0]['box'] = [350,350,500,500]
        with self.assertRaises(ValueError): self.check(args)

    def test_invalid_bounds_ids_duplicate_and_oversized_negative_are_rejected(self):
        for box in ([-1,0,10,10], [0,0,900,10], [0,0,float('nan'),10]):
            args = self.fixture(); args[0]['targets'][0]['box'] = box
            with self.subTest(box=box), self.assertRaises(ValueError): self.check(args)
        args = self.fixture(); args[0]['targets'] *= 2
        with self.assertRaises(ValueError): self.check(args)
        args = self.fixture(); args[0]['background_regions'][0]['box'] = [0,0,300,300]
        with self.assertRaises(ValueError): self.check(args)

    def test_grid_phase_and_small_upload_views_preserve_distinct_adjacent_outlets(self):
        targets = [{'record_id': 'a', 'class_id': 58, 'source_box': [400,380,430,410]},
                   {'record_id': 'b', 'class_id': 58, 'source_box': [400,415,430,445]}]
        with Image.new('RGB', (1000,1000), 'white') as image:
            views = list(power_views(image, targets))
        self.assertEqual({v[3] for v in views}, {.375,.5,.75,1})
        for tile, lines, ids, scale, origin, target in views:
            self.assertEqual(tile.size, (256,256)); tile.close()
            self.assertIn(target['record_id'], ids)
            self.assertEqual(len(lines), len(ids))
        native = [v for v in views if v[3] == 1]
        self.assertTrue(any(v[2] == ['a','b'] for v in native))
        self.assertGreater(len({tuple(v[4]) for v in native}), 4)

    def test_yolo_labels_recover_source_boxes_at_each_scale_and_phase(self):
        targets = [{'record_id': 'edge', 'class_id': 58, 'source_box': [1, 5, 35, 36]},
                   {'record_id': 'a', 'class_id': 58, 'source_box': [400,380,430,410]},
                   {'record_id': 'b', 'class_id': 58, 'source_box': [400,415,430,445]}]
        expected = {t['record_id']: t for t in targets}
        before = deepcopy(targets)
        paired_scales = set()
        with Image.new('RGB', (1000,1000), 'white') as image:
            for tile, lines, ids, scale, (left, top), _ in power_views(image, targets):
                tile.close()
                if 'a' in ids and 'b' in ids: paired_scales.add(scale)
                for line, record_id in zip(lines, ids):
                    cls, cx, cy, width, height = map(float, line.split())
                    recovered = [(left + (cx-width/2)*256)/scale,
                                 (top + (cy-height/2)*256)/scale,
                                 (left + (cx+width/2)*256)/scale,
                                 (top + (cy+height/2)*256)/scale]
                    self.assertEqual(int(cls), expected[record_id]['class_id'])
                    for actual, wanted in zip(recovered, expected[record_id]['source_box']):
                        self.assertAlmostEqual(actual, wanted, delta=.00002)
        self.assertEqual(paired_scales, {.375, .5, .75, 1})
        self.assertEqual(targets, before)

    def test_prepare_preserves_parent_frozen_validation_and_only_inspected_negatives(self):
        with TemporaryDirectory() as folder:
            paths = self.disk_fixture(Path(folder))
            parent, prepared, _, _, output = paths
            before_parent, before_source = snapshot(parent), snapshot(prepared)
            result = prepare(*paths)
            data = json.loads((output / 'manifest.json').read_text())
            original = json.loads(before_parent['manifest.json'])
            self.assertEqual(snapshot(parent), before_parent)
            self.assertEqual(snapshot(prepared), before_source)
            for name, contents in before_parent.items():
                if name not in ('manifest.json', 'data.yaml'):
                    self.assertEqual((output / name).read_bytes(), contents)
            self.assertEqual(data['classes'], original['classes'])
            self.assertEqual(data['frozen_metrics'], original['frozen_metrics'])
            self.assertEqual(data['parent_dataset_sha256'], digest(parent / 'manifest.json'))
            self.assertEqual(result['dependent_positive_views'], 36)
            self.assertEqual(len(data['reviewed_background_images']), 3)
            self.assertEqual(data['power_sampling']['unknown_regions'], 'ignored')
            for row in data['authorized_pdf_training_images']:
                self.assertTrue((output / 'labels/train' / (row['image_id']+'.txt')).read_text().strip())
                self.assertEqual(row['supervised_record_ids'], ['outlet01'])
                self.assertFalse(row['independent_example'])
                self.assertFalse(row['human_review_claim'])
            empty = {p.stem for p in (output / 'labels/train').glob('*.txt') if not p.read_text().strip()}
            self.assertEqual(empty, {r['image_id'] for r in data['reviewed_background_images']})
            self.assertEqual({tuple(r['box']) for r in data['reviewed_background_images']}, {(0,0,256,256)})
            with self.assertRaises(FileExistsError): prepare(*paths)

    def test_prepare_rejects_each_changed_source_or_permission_before_creating_output(self):
        for relative in ('parent/manifest.json', 'prepared/manifest.json', 'prepared/original.pdf',
                         'prepared/source-authorization.json', 'prepared/power.png'):
            with self.subTest(file=relative), TemporaryDirectory() as folder:
                root = Path(folder); paths = self.disk_fixture(root)
                with (root / relative).open('ab') as stream: stream.write(b' ')
                with self.assertRaises(ValueError): prepare(*paths)
                self.assertFalse(paths[-1].exists())
        for permission in ({'allowed_purposes': ['evaluation']}, {'source_sha256': 'f'*64}):
            with self.subTest(permission=permission), TemporaryDirectory() as folder:
                paths = self.disk_fixture(Path(folder))
                authorization = paths[1] / 'source-authorization.json'
                data = json.loads(authorization.read_text()); data.update(permission)
                write_json(authorization, data)
                source = json.loads((paths[1] / 'manifest.json').read_text())
                source['authorization_sha256'] = digest(authorization)
                write_json(paths[1] / 'manifest.json', source)
                evidence = json.loads(paths[2].read_text())
                evidence['prepared_manifest_sha256'] = digest(paths[1] / 'manifest.json')
                write_json(paths[2], evidence)
                with self.assertRaises(ValueError): prepare(*paths)
                self.assertFalse(paths[-1].exists())

    def test_prepare_rejects_duplicate_historical_annotation_before_output(self):
        with TemporaryDirectory() as folder:
            paths = self.disk_fixture(Path(folder))
            parent = paths[0] / 'manifest.json'
            data = json.loads(parent.read_text())
            data['power_source_targets'] = [{'record_id': 'outlet01'}]
            write_json(parent, data)
            evidence = json.loads(paths[2].read_text()); evidence['parent_manifest_sha256'] = digest(parent)
            write_json(paths[2], evidence)
            with self.assertRaisesRegex(ValueError, 'history'): prepare(*paths)
            self.assertFalse(paths[-1].exists())

    def test_next_replay_retains_prior_structured_annotation_history(self):
        with TemporaryDirectory() as folder:
            paths = self.disk_fixture(Path(folder))
            parent = paths[0] / 'manifest.json'
            data = json.loads(parent.read_text())
            old_target = {'record_id': 'priorOutlet', 'source_box': [20,20,40,40], 'class_id': 58}
            old_negative = {'id': 'priorGrid', 'box': [50,50,80,80], 'reason': 'Prior inspected grid'}
            data['power_source_targets'] = [old_target]
            data['power_negative_regions'] = [old_negative]
            write_json(parent, data)
            evidence = json.loads(paths[2].read_text()); evidence['parent_manifest_sha256'] = digest(parent)
            write_json(paths[2], evidence)
            prepare(*paths)
            output = json.loads((paths[-1] / 'manifest.json').read_text())
            self.assertIn(old_target, output['power_source_targets'])
            self.assertIn(old_negative, output['power_negative_regions'])

    def test_second_replay_archives_inspection_and_preserves_all_prior_artifacts(self):
        with TemporaryDirectory() as folder:
            root = Path(folder); paths = self.disk_fixture(root)
            prepare(*paths)
            first = paths[-1]
            before = snapshot(first)
            first_data = json.loads(before['manifest.json'])
            evidence = json.loads(paths[2].read_text())
            evidence['parent_manifest_sha256'] = digest(first / 'manifest.json')
            evidence['targets'][0].update(id='outlet02', box=[480,380,515,410])
            evidence['background_regions'][0].update(id='grid02', box=[0,300,256,556])
            inspection = root / 'second-inspection.json'; write_json(inspection, evidence)
            second = root / 'second'
            prepare(first, paths[1], inspection, paths[3], second)
            data = json.loads((second / 'manifest.json').read_text())
            self.assertEqual(snapshot(first), before)
            for name, contents in before.items():
                if name not in ('manifest.json', 'data.yaml', 'target-overlay.png', 'negative-contact.png'):
                    self.assertEqual((second / name).read_bytes(), contents, name)
            self.assertEqual(data['power_source_targets'][:1], first_data['power_source_targets'])
            self.assertEqual(data['power_negative_regions'][:1], first_data['power_negative_regions'])
            self.assertEqual(data['power_source_identity'], first_data['power_source_identity'])
            self.assertEqual(data['power_sampling'], first_data['power_sampling'])
            self.assertEqual(data['power_replay_revisions'][:1], first_data['power_replay_revisions'])
            self.assertEqual(len(data['power_replay_revisions']), 2)
            self.assertEqual(data['additional_training_authorizations'][:1],
                             first_data['additional_training_authorizations'])
            self.assertEqual(len(data['authorized_pdf_training_images']), 72)
            self.assertEqual(len(data['reviewed_background_images']), 6)
            self.assertEqual((second / 'power-inspections' / (digest(inspection)+'.json')).read_bytes(),
                             inspection.read_bytes())

    def background_revision(self, root, paths, offsets=None):
        first = paths[-1]
        evidence = json.loads(paths[2].read_text())
        evidence.update(parent_manifest_sha256=digest(first / 'manifest.json'), targets=[],
                        background_regions=[{'id': 'grid02', 'box': [0,300,256,556],
                                             'reason': 'Only inspected grid pixels'}])
        if offsets is not None:
            evidence['background_phase_offsets'] = offsets
        inspection = root / 'background-inspection.json'
        write_json(inspection, evidence)
        return first, paths[1], inspection, paths[3], root / 'background-output'

    def test_prepare_archives_exact_parent_manifest_for_multihop_frozen_probe(self):
        from probe_power_quality import validate_probe_inputs

        with TemporaryDirectory() as folder:
            root = Path(folder); paths = self.disk_fixture(root)
            frozen_bytes = (paths[0] / 'manifest.json').read_bytes()
            frozen_hash = digest(paths[0] / 'manifest.json')
            prepare(*paths)
            first = paths[-1]
            first_archive = first / 'lineage' / (frozen_hash+'.json')
            self.assertEqual(first_archive.read_bytes(), frozen_bytes)
            self.assertEqual(digest(first_archive), frozen_hash)
            revision = self.background_revision(root, paths)
            first_bytes = (first / 'manifest.json').read_bytes()
            first_hash = digest(first / 'manifest.json')
            prepare(*revision)
            second = revision[-1]
            self.assertEqual((second / 'lineage' / (first_hash+'.json')).read_bytes(), first_bytes)
            self.assertEqual(digest(second / 'lineage' / (first_hash+'.json')), first_hash)
            self.assertEqual((second / 'lineage' / (frozen_hash+'.json')).read_bytes(), frozen_bytes)
            data, _, evidence, _, _ = validate_probe_inputs(
                second, paths[1], paths[2], paths[3], frozen_parent=paths[0])
            self.assertEqual(data['parent_dataset_sha256'], first_hash)
            self.assertEqual(evidence['parent_manifest_sha256'], frozen_hash)

    def test_background_only_revision_preserves_positive_artifacts_and_authorization_history(self):
        with TemporaryDirectory() as folder:
            root = Path(folder); paths = self.disk_fixture(root); prepare(*paths)
            revision = self.background_revision(root, paths)
            before, source_before = snapshot(paths[-1]), snapshot(paths[1])
            original = json.loads(before['manifest.json'])
            result = prepare(*revision)
            data = json.loads((revision[-1] / 'manifest.json').read_text())
            self.assertEqual(result['positive_targets'], 0)
            self.assertEqual(result['dependent_positive_views'], 0)
            self.assertEqual(snapshot(paths[-1]), before)
            self.assertEqual(snapshot(paths[1]), source_before)
            for name, contents in before.items():
                if name not in ('manifest.json', 'data.yaml', 'target-overlay.png', 'negative-contact.png'):
                    self.assertEqual((revision[-1] / name).read_bytes(), contents, name)
            for key in ('classes', 'power_source_targets', 'authorized_pdf_training_images',
                        'power_source_identity', 'power_sampling', 'frozen_metrics'):
                self.assertEqual(data[key], original[key], key)
            for key in ('additional_training_authorizations', 'power_replay_revisions',
                        'reviewed_background_images', 'assistant_reviewed_background_regions'):
                self.assertEqual(data[key][:len(original[key])], original[key], key)
            added = data['reviewed_background_images'][len(original['reviewed_background_images']):]
            self.assertEqual(len(added), 3)
            self.assertEqual({row['scale'] for row in added}, {1, .75, .5})
            self.assertTrue(all('dependent_phase_offset' not in row for row in added))
            self.assertEqual(data['power_replay_revisions'][-1]['target_ids'], [])
            self.assertEqual((revision[-1] / 'power-inspections' / (digest(revision[2])+'.json')).read_bytes(),
                             revision[2].read_bytes())

    def test_background_only_revision_requires_prior_exact_source_positive_before_output(self):
        for change in ('missing', 'wrong_crop', 'wrong_pdf'):
            with self.subTest(change=change), TemporaryDirectory() as folder:
                root = Path(folder); paths = self.disk_fixture(root); prepare(*paths)
                manifest = paths[-1] / 'manifest.json'
                data = json.loads(manifest.read_text())
                if change == 'missing':
                    data['power_source_targets'] = []
                else:
                    key = 'source_sha256' if change == 'wrong_crop' else 'pdf_sha256'
                    data['power_source_targets'][0][key] = 'f' * 64
                write_json(manifest, data)
                revision = self.background_revision(root, paths)
                before = snapshot(paths[-1])
                with self.assertRaisesRegex(ValueError, 'source-bound positive'):
                    prepare(*revision)
                self.assertFalse(revision[-1].exists())
                self.assertEqual(snapshot(paths[-1]), before)

    def test_background_only_revision_rejects_prior_positive_overlap_before_output(self):
        with TemporaryDirectory() as folder:
            root = Path(folder); paths = self.disk_fixture(root); prepare(*paths)
            revision = self.background_revision(root, paths)
            evidence = json.loads(revision[2].read_text())
            evidence['background_regions'][0]['box'] = [350,350,500,500]
            write_json(revision[2], evidence)
            before = snapshot(paths[-1])
            with self.assertRaisesRegex(ValueError, 'positive region'):
                prepare(*revision)
            self.assertFalse(revision[-1].exists())
            self.assertEqual(snapshot(paths[-1]), before)

    def test_background_phase_offsets_rejected_before_output_mutation(self):
        for offsets in ([False], [0,0], [-64,0,32,64], [-65], [65], '0', [], {'phase': 0}):
            with self.subTest(offsets=offsets), TemporaryDirectory() as folder:
                root = Path(folder); paths = self.disk_fixture(root); prepare(*paths)
                revision = self.background_revision(root, paths, offsets)
                parent_before, source_before = snapshot(paths[-1]), snapshot(paths[1])
                with self.assertRaisesRegex(ValueError, 'phase offsets'):
                    prepare(*revision)
                self.assertFalse(revision[-1].exists())
                self.assertEqual(snapshot(paths[-1]), parent_before)
                self.assertEqual(snapshot(paths[1]), source_before)

    def test_phased_background_revision_uses_only_inspected_pixels_and_known_white_padding(self):
        with TemporaryDirectory() as folder:
            root = Path(folder); paths = self.disk_fixture(root)
            # Unknown pixels have a conspicuous color that must never enter a negative.
            source_path = paths[1] / 'power.png'
            with Image.new('RGB', (800,800), (255,0,255)) as image:
                image.paste((255,255,255), (0,0,256,256))
                image.paste((255,255,255), (30,320,230,520))
                image.putpixel((31,322), (0,0,0))
                image.putpixel((100,425), (30,40,50))
                image.putpixel((228,518), (90,80,70))
                image.save(source_path)
            source = json.loads((paths[1] / 'manifest.json').read_text())
            source['regions'][0]['crop_sha256'] = digest(source_path)
            write_json(paths[1] / 'manifest.json', source)
            evidence = json.loads(paths[2].read_text())
            evidence.update(source_image_sha256=digest(source_path),
                            prepared_manifest_sha256=digest(paths[1] / 'manifest.json'))
            write_json(paths[2], evidence)
            prepare(*paths)
            revision = self.background_revision(root, paths, [-64,0,64])
            evidence = json.loads(revision[2].read_text())
            evidence['background_regions'][0]['box'] = [30,320,230,520]
            write_json(revision[2], evidence)
            before, source_before = snapshot(paths[-1]), snapshot(paths[1])
            original = json.loads(before['manifest.json'])
            prepare(*revision)
            data = json.loads((revision[-1] / 'manifest.json').read_text())
            rows = data['reviewed_background_images'][len(original['reviewed_background_images']):]
            self.assertEqual(len(rows), 27)
            self.assertEqual(len({row['image_id'] for row in rows}), 27)
            self.assertEqual(data['assistant_reviewed_background_regions'][-27:], rows)
            self.assertEqual(data['power_replay_revisions'][-1]['sampling']['negative_views'], 27)
            self.assertEqual(data['power_replay_revisions'][-1]['sampling']['background_phase_offsets'], [-64,0,64])
            self.assertEqual(snapshot(paths[-1]), before)
            self.assertEqual(snapshot(paths[1]), source_before)
            with Image.open(source_path) as source_image, Image.new('RGB', (256,256), 'white') as tile:
                with source_image.crop((30,320,230,520)) as crop:
                    tile.paste(crop, (28,28))
                for row in rows:
                    self.assertFalse(row['human_review_claim'])
                    self.assertFalse(row['independent_example'])
                    self.assertEqual(row['annotation_origin'], ORIGIN)
                    self.assertEqual(row['split'], 'train')
                    ip = revision[-1] / 'images/train' / (row['image_id']+'.png')
                    self.assertEqual(row['sha256'], digest(ip))
                    self.assertEqual(row['source_image_sha256'], digest(source_path))
                    self.assertEqual((revision[-1] / 'labels/train' / (row['image_id']+'.txt')).read_bytes(), b'')
                    with tile.resize((round(256*row['scale']), round(256*row['scale'])),
                                     Image.Resampling.LANCZOS) as view, \
                            Image.new('RGB', (256,256), 'white') as expected, Image.open(ip) as actual:
                        dx, dy = row['dependent_phase_offset']
                        expected.paste(view, ((256-view.width)//2+dx, (256-view.height)//2+dy))
                        self.assertEqual(actual.tobytes(), expected.tobytes())

    def test_prior_background_identity_cannot_be_reused(self):
        with TemporaryDirectory() as folder:
            paths = self.disk_fixture(Path(folder))
            parent = paths[0] / 'manifest.json'; data = json.loads(parent.read_text())
            data['power_negative_regions'] = [{'id': 'grid01', 'box': [10,10,20,20]}]
            write_json(parent, data)
            evidence = json.loads(paths[2].read_text()); evidence['parent_manifest_sha256'] = digest(parent)
            write_json(paths[2], evidence)
            with self.assertRaisesRegex(ValueError, 'history'): prepare(*paths)
            self.assertFalse(paths[-1].exists())

    def test_negative_phase_replay_preserves_history_and_translates_only_known_pixels(self):
        with TemporaryDirectory() as folder:
            root = Path(folder); paths = self.disk_fixture(root); prepare(*paths)
            parent = paths[-1]; manifest = parent / 'manifest.json'
            data = json.loads(manifest.read_text())
            image_id = data['assistant_reviewed_background_regions'][0]['image_id']
            original_path = parent / 'images/train' / (image_id+'.png')
            # A synthetic asymmetric grid mark makes clipping/white padding testable.
            with Image.open(original_path) as opened:
                image = opened.convert('RGB')
            with image:
                for x, y, color in ((1,2,(0,0,0)), (100,125,(30,40,50)), (240,250,(90,80,70))):
                    image.putpixel((x,y), color)
                image.save(original_path)
            for key in ('reviewed_background_images', 'assistant_reviewed_background_regions'):
                for row in data[key]:
                    if row['image_id'] == image_id: row['sha256'] = digest(original_path)
            write_json(manifest, data)
            before = snapshot(parent); output = root / 'phase'
            result = replay_negatives(parent, paths[3], output)
            after = json.loads((output / 'manifest.json').read_text())
            self.assertEqual(snapshot(parent), before)
            for name, contents in before.items():
                if name not in ('manifest.json', 'data.yaml'):
                    self.assertEqual((output / name).read_bytes(), contents, name)
            for key in ('classes', 'power_source_targets', 'power_negative_regions',
                        'power_source_identity', 'power_replay_revisions', 'frozen_metrics',
                        'authorized_pdf_training_images', 'additional_training_authorizations'):
                self.assertEqual(after[key], data[key], key)
            originals = data['assistant_reviewed_background_regions']
            rows = after['assistant_reviewed_background_regions'][len(originals):]
            self.assertEqual(len(rows), 24)
            self.assertEqual(result['translated_negative_views'], 24)
            self.assertEqual(result['unknown_regions'], 'ignored')
            self.assertFalse(result['independent_examples'])
            self.assertEqual((output / 'lineage' / (digest(manifest)+'.json')).read_bytes(), before['manifest.json'])
            self.assertEqual({tuple(r['augmentation_offset']) for r in rows},
                             {(x,y) for x in (-64,0,64) for y in (-64,0,64) if (x,y) != (0,0)})
            for row in rows:
                self.assertFalse(row['human_review_claim'])
                self.assertFalse(row['independent_example'])
                self.assertEqual(row['split'], 'train')
                self.assertEqual((output / 'labels/train' / (row['image_id']+'.txt')).read_bytes(), b'')
                with Image.open(parent / 'images/train' / (row['sampling_parent']+'.png')) as original, \
                        Image.new('RGB', (256,256), 'white') as expected, \
                        Image.open(output / 'images/train' / (row['image_id']+'.png')) as actual:
                    expected.paste(original, tuple(row['augmentation_offset']))
                    self.assertEqual(actual.tobytes(), expected.tobytes())
            with self.assertRaises(ValueError): replay_negatives(output, paths[3], root / 'second-phase')
            self.assertFalse((root / 'second-phase').exists())
            with self.assertRaises(FileExistsError): replay_negatives(parent, paths[3], output)

    def test_negative_phase_replay_rejects_missing_excessive_or_incomplete_head_inputs(self):
        with TemporaryDirectory() as folder:
            root = Path(folder); paths = self.disk_fixture(root); prepare(*paths)
            manifest = paths[-1] / 'manifest.json'; original = json.loads(manifest.read_text())
            for change in ('no_negatives', 'too_many', 'head', 'loss', 'targets'):
                data = deepcopy(original)
                if change == 'no_negatives': data['assistant_reviewed_background_regions'] = []
                elif change == 'too_many': data['assistant_reviewed_background_regions'] *= 65
                elif change == 'head': data['classes'].pop()
                elif change == 'loss': data['required_loss'] = 'unlabeled_as_background'
                else: data['power_source_targets'] = []
                write_json(manifest, data)
                with self.subTest(change=change), self.assertRaises(ValueError):
                    replay_negatives(paths[-1], paths[3], root / change)
                self.assertFalse((root / change).exists())

    def test_negative_phase_hard_mining_opt_in_preserves_source_and_full_head(self):
        with TemporaryDirectory() as folder:
            root = Path(folder); paths = self.disk_fixture(root); prepare(*paths)
            before = snapshot(paths[-1]); output = root / 'hard-phase'
            result = replay_negatives(paths[-1], paths[3], output, hard_mining=True)
            data = json.loads((output / 'manifest.json').read_text())
            original = json.loads(before['manifest.json'])
            self.assertEqual(snapshot(paths[-1]), before)
            self.assertEqual(data['classes'], original['classes'])
            self.assertEqual(data['power_source_targets'], original['power_source_targets'])
            self.assertEqual(data['authorized_pdf_training_images'], original['authorized_pdf_training_images'])
            self.assertEqual(data['reviewed_background_sampling'], 'top_score_anchors')
            self.assertEqual(result['hard_negative_anchor_budget'], 32)
            self.assertEqual(result['translated_negative_views'], 24)
            self.assertFalse(result['independent_examples'])
            self.assertFalse(result['human_review_claim'])

    def test_switch_retention_copies_authorized_window_once_without_losing_history(self):
        with TemporaryDirectory() as folder:
            root = Path(folder); paths = self.switch_fixture(root)
            parent = paths[-1]; before = snapshot(parent); output = root / 'switch-retained'
            result = restore_switch_replay(parent, paths[3], output)
            original = json.loads(before['manifest.json']); data = json.loads((output / 'manifest.json').read_text())
            self.assertEqual(result['retained_switch_views'], 1)
            self.assertEqual(result['classes'], 80)
            self.assertEqual(snapshot(parent), before)
            for name, contents in before.items():
                if name not in ('manifest.json','data.yaml'):
                    self.assertEqual((output / name).read_bytes(), contents, name)
            for key in ('classes','power_source_targets','power_negative_regions','power_replay_revisions',
                        'switch_source_targets','restorative_replay_sampling','reviewed_background_images',
                        'authorized_pdf_training_images','additional_training_authorizations'):
                self.assertEqual(data[key], original[key], key)
            replay = data['power_switch_retention_replay']
            self.assertEqual(replay['independent_examples_added'], 0)
            self.assertEqual(replay['parent_manifest_sha256'], digest(parent / 'manifest.json'))
            self.assertEqual((output / 'lineage' / (digest(parent / 'manifest.json')+'.json')).read_bytes(),
                             before['manifest.json'])
            replica = replay['replicas'][0]
            self.assertEqual(replica['sampling_parent'], 'pdfdev-switch-fixture')
            self.assertEqual(replica['class_id'], 62)
            self.assertEqual(replica['split'], 'train')
            self.assertFalse(replica['independent_example'])
            for directory, suffix in (('images','png'),('labels','txt')):
                self.assertEqual((output / f'{directory}/train' / (replica['image_id']+'.'+suffix)).read_bytes(),
                                 (parent / f'{directory}/train/pdfdev-switch-fixture.{suffix}').read_bytes())
            validate_restorative_replay(output, data)
            with self.assertRaises(ValueError): restore_switch_replay(output, paths[3], root / 'again')
            self.assertFalse((root / 'again').exists())
            with self.assertRaises(FileExistsError): restore_switch_replay(parent, paths[3], output)

    def test_switch_retention_fails_closed_on_missing_wrong_or_duplicate_source_supervision(self):
        with TemporaryDirectory() as folder:
            root = Path(folder); paths = self.switch_fixture(root)
            manifest = paths[-1] / 'manifest.json'; original = json.loads(manifest.read_text())
            for change in ('no_switches','wrong_class','no_positive_ids','head','too_many','combined_bound','duplicate'):
                data = deepcopy(original); row = data['authorized_pdf_training_images'][-1]
                if change == 'no_switches': data['switch_source_targets'] = []
                elif change == 'wrong_class': row['primary_class_id'] = 58
                elif change == 'no_positive_ids': row['supervised_record_ids'] = ['missing']
                elif change == 'head': data['classes'].pop()
                elif change == 'too_many': data['authorized_pdf_training_images'].extend([deepcopy(row)]*800)
                elif change == 'combined_bound': data['restorative_replay_sampling']['replicas'] *= 1600
                else: data['authorized_pdf_training_images'].append(deepcopy(row))
                write_json(manifest, data)
                with self.subTest(change=change), self.assertRaises(ValueError):
                    restore_switch_replay(paths[-1], paths[3], root / change)
                self.assertFalse((root / change).exists())

    def test_switch_retention_replica_validator_rejects_tamper_labels_splits_and_duplicate_ids(self):
        with TemporaryDirectory() as folder:
            root = Path(folder); paths = self.switch_fixture(root); output = root / 'switch-retained'
            restore_switch_replay(paths[-1], paths[3], output)
            data = json.loads((output / 'manifest.json').read_text())
            for change in ({'image_sha256':'f'*64},{'label_sha256':'e'*64},{'class_id':64},
                           {'split':'val'},{'independent_example':True},{'image_id':'../bad'},
                           {'image_id':data['restorative_replay_sampling']['replicas'][0]['image_id']}):
                altered = deepcopy(data); altered['power_switch_retention_replay']['replicas'][0].update(change)
                with self.subTest(change=change), self.assertRaises(ValueError):
                    validate_restorative_replay(output, altered)
            altered = deepcopy(data); altered['power_switch_retention_replay']['replicas'] *= 1600
            with self.assertRaises(ValueError): validate_restorative_replay(output, altered)
            row = data['power_switch_retention_replay']['replicas'][0]
            label = output / 'labels/train' / (row['image_id']+'.txt')
            label.write_text('64 .2 .3 .1 .1\n')
            with self.assertRaises(ValueError): validate_restorative_replay(output, data)


if __name__ == '__main__':
    unittest.main()
