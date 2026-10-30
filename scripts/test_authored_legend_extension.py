import random
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image, ImageDraw
import torch
from ultralytics.nn.modules.head import Detect

from prepare_authored_legend_extension import extend_head, synthetic_tile, build_learning_check, revise_synthetic_supervision, digest
from train_symbol_detector_dev import train


class AuthoredLegendExtensionTests(unittest.TestCase):
    def test_learning_subset_preserves_parent_and_all_head_identities_without_claiming_full_coverage(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'images/train').mkdir(parents=True)
            (root/'labels/train').mkdir(parents=True)
            checkpoint=root/'base.pt'; checkpoint.write_bytes(b'fixture')
            rows=[]
            for cls in (56,57):
                for index in (2,18,34,50):
                    name=f'authored-legend-{cls}-{index:03d}'
                    image=root/'images/train'/f'{name}.png'
                    label=root/'labels/train'/f'{name}.txt'
                    Image.new('RGB',(256,256),'white').save(image)
                    label.write_text(f'{cls} .5 .5 .2 .2\n')
                    rows.append({'class_id':cls,'image_id':name,'human_review_claim':False,
                                 'image_sha256':digest(image),'label_sha256':digest(label)})
            data={'class_scope':'parent56_plus_four_authored_lamp_and_outlet_definitions',
                  'classes':[{'id':i,'label':f'Class {i}','legend_entry':f'Drawing:L{i}','samples':1} for i in range(60)],
                  'authored_legend_synthetic_images':rows}
            manifest=root/'manifest.json'; manifest.write_text(json.dumps(data)); before=digest(manifest)
            result=build_learning_check(root,checkpoint,root/'out')
            self.assertEqual(result['training_images'],8)
            self.assertTrue(result['diagnostic_only'])
            self.assertEqual(digest(manifest),before)
            subset=json.loads((root/'out/manifest.json').read_text())
            self.assertFalse(subset['all_eligible_entries'])
            self.assertEqual(subset['required_loss'],'synthetic_complete_known_composite_only')
            self.assertEqual([r['legend_entry'] for r in subset['classes']],[r['legend_entry'] for r in data['classes']])
            self.assertEqual([r['samples'] for r in subset['classes']],[0]*56+[4,4,0,0])
            with self.assertRaises(FileExistsError):
                build_learning_check(root,checkpoint,root/'out')

    def test_revised_full_supervision_is_versioned_not_a_human_review_claim(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary)
            (root/'images/train').mkdir(parents=True); (root/'labels/train').mkdir(parents=True)
            name='authored-legend-56-000'; image=root/'images/train'/f'{name}.png'; label=root/'labels/train'/f'{name}.txt'
            Image.new('RGB',(256,256),'white').save(image); label.write_text('56 .5 .5 .2 .2\n')
            checkpoint=root/'base.pt'; checkpoint.write_bytes(b'fixture')
            (root/'source-extension-specification.json').write_text('{}')
            data={'classes':[{'id':i,'label':f'Class {i}','legend_entry':f'L{i}'} for i in range(60)],
                  'all_eligible_entries':True,'class_scope':'parent56_plus_four_authored_lamp_and_outlet_definitions',
                  'reviewed_targets':[{'record_id':'preserved'}],'authored_legend_synthetic_images':[
                      {'class_id':56,'image_id':name,'human_review_claim':False,
                       'label_origin':'known_synthetic_composite_geometry','image_sha256':digest(image),'label_sha256':digest(label)}]}
            manifest=root/'manifest.json'; manifest.write_text(json.dumps(data)); before=digest(manifest)
            revise_synthetic_supervision(root,checkpoint,root/'out')
            revised=json.loads((root/'out/manifest.json').read_text())
            self.assertTrue(revised['synthetic_complete_background'])
            self.assertEqual(revised['classes'],data['classes'])
            self.assertEqual(revised['reviewed_targets'],data['reviewed_targets'])
            self.assertFalse(revised['authored_legend_synthetic_images'][0]['human_review_claim'])
            self.assertEqual(digest(manifest),before)
            self.assertEqual(digest(root/'out/images/train'/f'{name}.png'),digest(image))
            label.write_text('57 .5 .5 .2 .2\n')
            with self.assertRaisesRegex(ValueError,'source differs'):
                revise_synthetic_supervision(root,checkpoint,root/'bad')
            self.assertFalse((root/'bad').exists())

    def test_training_batch_bound_and_recorded_low_memory_configuration(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = root / 'base.pt'
            base.write_bytes(b'fixture')
            (root / 'manifest.json').write_text(json.dumps({
                'kind': 'positive_only_masked_symbol_detection_diagnostic_v1',
                'classes': [], 'all_eligible_entries': False}))
            for batch in (0, 3, 16, True):
                with self.subTest(batch=batch), self.assertRaisesRegex(ValueError, 'batch'):
                    train(root, base, root / 'invalid', batch_size=batch)
                self.assertFalse((root / 'invalid').exists())
            model = Mock()
            with patch('train_symbol_detector_dev.YOLO', return_value=model):
                train(root, base, root / 'run', batch_size=2)
            self.assertEqual(model.train.call_args.kwargs['batch'], 2)
            self.assertEqual(model.train.call_args.kwargs['nbs'],64)
            self.assertEqual(json.loads((root / 'run/run-manifest.json').read_text())['batch_size'], 2)

    def test_unicode_serialization_does_not_reindex_warm_start_classes(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = root / 'base.pt'
            base.write_bytes(b'fixture')
            (root / 'manifest.json').write_text(json.dumps({
                'kind': 'positive_only_masked_symbol_detection_diagnostic_v1',
                'classes': [{'id': 0, 'label': 'Circuit homerun — panel', 'samples': 1}],
                'all_eligible_entries': True}))
            model = Mock(names={0: 'Circuit homerun — panel'})
            with patch('train_symbol_detector_dev.YOLO', return_value=model):
                train(root, base, root / 'run', batch_size=2)
            model.train.assert_called_once()
            model.names = {1: 'Circuit homerun — panel'}
            with patch('train_symbol_detector_dev.YOLO', return_value=model), \
                 self.assertRaisesRegex(ValueError, 'numeric legend identities'):
                train(root, base, root / 'wrong-id', batch_size=2)

    def test_appending_classes_preserves_all_parent_weights_and_box_branches(self):
        head = Detect(nc=56, ch=(64,128,256))
        box_state = {k:v.clone() for k,v in head.cv2.state_dict().items()}
        classifier_state = [(branch[-1].weight.clone(),branch[-1].bias.clone()) for branch in head.cv3]
        names = {i:f'Class {i}' for i in range(56)}
        model = SimpleNamespace(names=names, model=[head], yaml={'nc':56})
        additions = [{'label':f'New {i}', 'seed_parent_class_id':55} for i in range(4)]
        extend_head(model, additions)
        self.assertEqual(model.names, {**names, **{56+i:f'New {i}' for i in range(4)}})
        self.assertEqual(head.nc, 60)
        self.assertEqual(head.no, 60+4*head.reg_max)
        for key,value in head.cv2.state_dict().items():
            self.assertTrue(torch.equal(value,box_state[key]))
        for branch,(weight,bias) in zip(head.cv3,classifier_state):
            self.assertTrue(torch.equal(branch[-1].weight[:56],weight))
            self.assertTrue(torch.equal(branch[-1].bias[:56],bias))
            self.assertTrue(torch.equal(branch[-1].weight[56],weight[55]))
            self.assertTrue(torch.equal(branch[-1].bias[56],bias[55]-2))
            self.assertTrue(branch[-1].weight.requires_grad)

    def test_no_silent_architecture_or_noncontiguous_mapping_change(self):
        model=SimpleNamespace(names={0:'A',2:'B'}, model=[object()])
        with self.assertRaises(ValueError):
            extend_head(model,[{'label':'C','seed_parent_class_id':0}])
        model.names={0:'A',1:'B'}
        with self.assertRaises(ValueError):
            extend_head(model,[{'label':'C','seed_parent_class_id':0}])

    def test_synthetic_targets_have_known_locations_and_preserve_source(self):
        glyph=Image.new('RGB',(100,30),'white')
        pen=ImageDraw.Draw(glyph); pen.rectangle((10,8,90,22),outline='black',width=2)
        pen.text((45,10),'2',fill='black')
        before=np.asarray(glyph).copy()
        for index in range(16):
            image,box=synthetic_tile(glyph,index,random.Random(42))
            self.assertEqual(image.size,(256,256))
            self.assertTrue(0 <= box[0] < box[2] <= 256 and 0 <= box[1] < box[3] <= 256)
            self.assertLess(np.asarray(image.crop(box)).min(),50)
            image.close()
        np.testing.assert_array_equal(np.asarray(glyph),before)

    def test_empty_glyph_is_not_a_training_target(self):
        with self.assertRaises(ValueError):
            synthetic_tile(Image.new('RGB',(100,30),'white'),0,random.Random(42))


if __name__ == '__main__':
    unittest.main()
