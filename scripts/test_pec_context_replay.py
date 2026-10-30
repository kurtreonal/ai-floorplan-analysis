from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch,Mock
import json

import numpy as np
from PIL import Image
from prepare_pec_context_replay import (
    source_views,verified_backfills,prepare,selected_reference_contexts,retention_windows,prepare_retention,
)
from prepare_pec_replay import inventory
from prepare_pec_reference import PARENT_DATASET_SHA256
from probe_pec_reference import lost_retention_examples,retention_diagnostic


class PecContextReplayTests(unittest.TestCase):
    def targets(self):
        return [{'record_id':'a','class_id':103,'source_box':[140,140,160,160]},
                {'record_id':'b','class_id':92,'source_box':[185,140,205,160]}]

    def test_source_windows_keep_exact_pixels_neighbors_and_invertible_coordinates(self):
        image=Image.fromarray(np.arange(400*400*3,dtype=np.uint8).reshape(400,400,3))
        targets=self.targets();before=image.tobytes();views=list(source_views(image,targets,targets))
        self.assertGreater(len(views),0);positions=set()
        for tile,lines,ids,scale,origin in views:
            self.assertEqual(scale,1);self.assertEqual(tile.size,(256,256))
            x,y=origin;self.assertEqual(tile.tobytes(),image.crop((x,y,x+256,y+256)).tobytes())
            self.assertNotIn((scale,x,y),positions);positions.add((scale,x,y))
            self.assertIn('a',ids);self.assertIn('b',ids)
            for line,identity in zip(lines,ids):
                cls,cx,cy,w,h=map(float,line.split());target=next(t for t in targets if t['record_id']==identity)
                recovered=[(cx-w/2)*256+x,(cy-h/2)*256+y,(cx+w/2)*256+x,(cy+h/2)*256+y]
                self.assertEqual(cls,target['class_id'])
                np.testing.assert_allclose(recovered,target['source_box'],atol=.00001)
            tile.close()
        self.assertEqual(image.tobytes(),before);image.close()

    def test_isotropic_scaling_and_clipped_neighbors_remain_ignored(self):
        image=Image.new('RGB',(400,400),'white');targets=self.targets()
        targets.append({'record_id':'outside','class_id':11,'source_box':[390,390,400,400]})
        for tile,lines,ids,scale,origin in source_views(image,targets,targets[:2],scales=(1,1.5,2)):
            self.assertNotIn('outside',ids);self.assertEqual(len(lines),len(ids));self.assertIn(scale,(1,1.5,2))
            tile.close()
        image.close()

    def test_scaled_source_bound_checked_before_image_allocation(self):
        image=Mock(size=(6000,10000),width=6000,height=10000)
        with self.assertRaisesRegex(ValueError,'Scaled source allocation'):
            list(source_views(image,self.targets(),self.targets(),scales=(2,)))
        image.resize.assert_not_called();image.copy.assert_not_called()

    def test_bad_source_targets_and_changed_focus_fail_closed(self):
        image=Image.new('RGB',(400,400),'white')
        for box in ([1,1,float('nan'),5],[-1,1,5,5],[1,1,450,5],[True,1,5,5]):
            targets=self.targets();targets[0]['source_box']=box
            with self.subTest(box=box),self.assertRaises(ValueError):list(source_views(image,targets,targets))
        targets=self.targets();targets.append(deepcopy(targets[0]))
        with self.assertRaises(ValueError):list(source_views(image,targets,targets))
        focus=deepcopy(self.targets()[0]);focus['class_id']=1
        with self.assertRaises(ValueError):list(source_views(image,self.targets(),[focus]))
        with self.assertRaises(ValueError):list(source_views(image,self.targets(),self.targets(),scales=(True,)))
        image.close()

    def fixture(self):
        row={'record_id':'recovered-a','class_id':0,'source_sha256':'s','source_crop':[0,0,256,256]}
        old={'images':[row],'recovery_manifest_sha256':'r'}
        audit={'kind':'historical_recovery_byte_reconstruction_audit','parent_manifest_sha256':PARENT_DATASET_SHA256,
               'recovery_manifest_sha256':'r','human_review_claim':False,'production_approval':False,'originals_modified':False,
               'verified_records':[{'image_id':'recovered-a','source_sha256':'s','source_crop':[0,0,256,256],
                   'original_metadata':deepcopy(row),'verification':'exact_original_RGB_pixels_and_historical_source_labels',
                   'image_sha256':'i','label_sha256':'l'}]}
        return old,audit

    def test_backfill_keeps_original_metadata_and_does_not_invent_review(self):
        old,audit=self.fixture();before=deepcopy(old)
        result=verified_backfills(old,audit)
        self.assertEqual(old,before);self.assertEqual(result[0]['image_sha256'],'i')
        self.assertEqual(result[0]['record_id'],old['images'][0]['record_id'])
        self.assertNotIn('human_review_claim',result[0])
        self.assertEqual(audit['verified_records'][0]['original_metadata'],old['images'][0])

    def test_incomplete_tampered_or_claimed_human_audit_cannot_restore_records(self):
        old,audit=self.fixture()
        cases=[]
        copy=deepcopy(audit);copy['human_review_claim']=True;cases.append(copy)
        copy=deepcopy(audit);copy['verified_records']=[];cases.append(copy)
        copy=deepcopy(audit);copy['verified_records']*=2;cases.append(copy)
        copy=deepcopy(audit);copy['verified_records'][0]['original_metadata']['class_id']=1;cases.append(copy)
        for copy in cases:
            with self.assertRaises(ValueError):verified_backfills(old,copy)

    def test_immutable_revision_and_wrong_hash_rejected_before_model_or_output(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);parent=root/'p';parent.mkdir();(parent/'manifest.json').write_text('{}')
            output=root/'out'
            with self.assertRaises(ValueError):prepare(parent,root,root/'model.pt',root,root/'reg.json',root/'audit.json',output)
            self.assertFalse(output.exists());output.mkdir()
            with self.assertRaises(FileExistsError):prepare(parent,root,root/'model.pt',root,root/'reg.json',root/'audit.json',output)

    def test_native_reference_and_switch_views_never_gain_complete_background(self):
        import torch
        from app.ai.symbol_detection.partial_label_training import (
            ReviewedBackgroundTrainer,DetectionTrainer,construction_known_weights,
        )
        native=['pdfdev-reference-native-source-001','pdfdev-switch-retention-native-source-001',
                'retention-native-original-001']
        synthetic='authored-legend-80-000'
        with TemporaryDirectory() as temporary:
            root=Path(temporary)
            data={'required_loss':'positive_boxes_and_explicit_reviewed_background',
                  'reviewed_background_images':[], 'synthetic_complete_background':True,
                  'authorized_pdf_training_images':[
                      {'image_id':name,'missing_annotation_policy':'ignore_unreviewed_not_empty_background'}
                      for name in native],
                  'authored_legend_synthetic_images':[{'image_id':synthetic,
                      'human_review_claim':False,'label_origin':'known_synthetic_composite_geometry'}]}
            (root/'manifest.json').write_text(json.dumps(data))
            trainer=object.__new__(ReviewedBackgroundTrainer);trainer.data={'path':root};trainer.device='cpu'
            batch={'im_file':[str(root/f'{name}.png') for name in native+[synthetic]]}
            with patch.object(DetectionTrainer,'preprocess_batch',return_value=batch):
                result=trainer.preprocess_batch(batch)
            self.assertEqual(result['synthetic_complete'].tolist(),[False,False,False,True])
            self.assertEqual(result['reviewed_background'].tolist(),[False,False,False,False])
            weights=construction_known_weights(torch.tensor([[1.,0.]]*4),
                result['synthetic_complete'],torch.ones((4,1,1)))
            self.assertEqual(weights.tolist(),[[1.,0.],[1.,0.],[1.,0.],[1.,1.]])
            logits=torch.zeros((4,2,129),requires_grad=True)
            (torch.nn.functional.binary_cross_entropy_with_logits(logits,torch.zeros_like(logits),
                reduction='none')*weights[...,None]).sum().backward()
            self.assertEqual(logits.grad[:3,1].abs().sum().item(),0)
            self.assertGreater(logits.grad[3,1].abs().sum().item(),0)

    def test_reference_sampling_preserves_two_windows_for_every_variant_and_is_order_independent(self):
        targets=[{'record_id':'a'},{'record_id':'b'}]
        rows=[{'image_id':f'view-{i}','image_sha256':str(i),'supervised_record_ids':ids,'context_kind':'reference-native'}
              for i,ids in enumerate((['a','b'],['a'],['b'],['a','b']))]
        data={'reference_source_context_targets':targets,'authorized_pdf_training_images':rows}
        snapshot=deepcopy(data);chosen=selected_reference_contexts(data)
        self.assertEqual(chosen,{'view-0','view-1','view-2'});self.assertEqual(data,snapshot)
        data['authorized_pdf_training_images'].reverse();self.assertEqual(selected_reference_contexts(data),chosen)
        data['reference_source_context_targets'].append({'record_id':'missing'})
        with self.assertRaises(ValueError):selected_reference_contexts(data)
        with self.assertRaises(ValueError):selected_reference_contexts(snapshot,per_variant=True)

    def test_retention_native_pixels_neighbors_coordinates_and_clipped_unknowns(self):
        image=Image.fromarray(np.arange(400*400*3,dtype=np.uint8).reshape(400,400,3))
        targets=self.targets()
        for target in targets:target['class_id']=20
        targets.append({'record_id':'clipped','class_id':55,'source_box':[0,0,300,20]})
        before=image.tobytes();views=list(retention_windows(image,targets,targets[:2]));self.assertLessEqual(len(views),4)
        self.assertGreater(len(views),0)
        for tile,lines,ids,origin in views:
            x,y=origin;self.assertEqual(tile.tobytes(),image.crop((x,y,x+256,y+256)).tobytes())
            self.assertNotIn('clipped',ids)
            for line,identity in zip(lines,ids):
                cls,cx,cy,w,h=map(float,line.split());expected=next(t for t in targets if t['record_id']==identity)
                np.testing.assert_allclose([(cx-w/2)*256+x,(cy-h/2)*256+y,(cx+w/2)*256+x,(cy+h/2)*256+y],expected['source_box'],atol=.00001)
            tile.close()
        self.assertEqual(image.tobytes(),before)
        targets[0]['source_box']=[0,0,float('nan'),20]
        with self.assertRaises(ValueError):list(retention_windows(image,targets,targets[:2]))
        image.close()

    def test_inventory_accepts_exact_extended_namespace_without_weakening_original_guard(self):
        from prepare_pec_reference import digest
        with TemporaryDirectory() as folder:
            root=Path(folder);(root/'images/train').mkdir(parents=True);(root/'labels/train').mkdir(parents=True)
            image=root/'images/train/a.png';Image.new('RGB',(256,256),'white').save(image)
            label=root/'labels/train/a.txt';label.write_text('128 .5 .5 .1 .1\n')
            data={'images':[{'record_id':'a','image_sha256':digest(image),'label_sha256':digest(label)}]}
            self.assertEqual(inventory(root,data,class_count=129)['a']['classes'],{128})
            with self.assertRaises(ValueError):inventory(root,data)
            with self.assertRaises(ValueError):inventory(root,data,class_count=True)
            label.write_text('128 .5 .5 .2 .1\n')
            with self.assertRaises(ValueError):inventory(root,data,class_count=129)

    def test_all_regressions_remain_traceable_and_preparation_rejects_wrong_frozen_input(self):
        original,before,after=self.retention_fixture()
        selected=lost_retention_examples(original,before,after,class_ids=tuple(range(80)),examples_per_class=200)
        self.assertEqual([r['record_id'] for r in selected],['a','b','d'])
        for limit in (True,0,201):
            with self.assertRaises(ValueError):lost_retention_examples(original,before,after,examples_per_class=limit)
        with TemporaryDirectory() as folder:
            root=Path(folder);(root/'manifest.json').write_text('{}');output=root/'out'
            with self.assertRaises(ValueError):prepare_retention(root,root,root,root,root,root,output)
            self.assertFalse(output.exists());output.mkdir()
            with self.assertRaises(FileExistsError):prepare_retention(root,root,root,root,root,root,output)

    def test_training_preflight_checks_every_byte_directory_member_and_class_count(self):
        from prepare_pec_reference import digest
        from train_symbol_detector_dev import validate_frozen_reference_replay
        with TemporaryDirectory() as folder:
            root=Path(folder);(root/'images/train').mkdir(parents=True);(root/'labels/train').mkdir(parents=True)
            data={'scope':'all_class_reference_replay_development_not_release','diagnostic_only':True,
                  'all_eligible_entries':True,'required_loss':'positive_boxes_and_explicit_reviewed_background',
                  'classes':[{'id':i,'samples':1} for i in range(129)],'images':[]}
            for cls in range(129):
                name=f'window-{cls}';ip=root/'images/train'/f'{name}.png';lp=root/'labels/train'/f'{name}.txt'
                Image.new('RGB',(16,16),'white').save(ip);lp.write_text(f'{cls} .5 .5 .1 .1\n')
                data['images'].append({'record_id':name,'image_sha256':digest(ip),'label_sha256':digest(lp)})
            validate_frozen_reference_replay(root,data)
            data['classes'][0]['id']=True
            with self.assertRaises(ValueError):validate_frozen_reference_replay(root,data)
            data['classes'][0]['id']=0
            data['classes'][0]['samples']=2
            with self.assertRaises(ValueError):validate_frozen_reference_replay(root,data)
            data['classes'][0]['samples']=1
            extra=root/'images/train/extra.png';Image.new('RGB',(16,16),'white').save(extra)
            with self.assertRaises(ValueError):validate_frozen_reference_replay(root,data)
            extra.unlink()
            label=root/'labels/train/window-0.txt';original=label.read_bytes();label.write_text('1 .5 .5 .1 .1\n')
            with self.assertRaises(ValueError):validate_frozen_reference_replay(root,data)
            label.write_bytes(original)
            image=root/'images/train/window-0.png';original=image.read_bytes();image.write_bytes(b'changed')
            with self.assertRaises(ValueError):validate_frozen_reference_replay(root,data)
            image.write_bytes(original);validate_frozen_reference_replay(root,data)

    def retention_fixture(self):
        targets=[{'record_id':name,'source_sha256':'s','class_id':cls,'source_box':[10,10,20,20]}
                 for name,cls in (('b',20),('a',20),('c',33),('d',55))]
        original={'reviewed_targets':targets}
        before={'kind':'partial_label_full_page_probe_v1','pages':[{'source_sha256':'s','targets':[
            {'record_id':t['record_id'],'class_id':t['class_id'],'localized_and_classified':True} for t in targets]}]}
        after=deepcopy(before)
        for row in after['pages'][0]['targets']:row['localized_and_classified']=row['record_id']=='c'
        return original,before,after

    def test_retention_selection_is_deterministic_and_only_uses_original_regressions(self):
        original,before,after=self.retention_fixture();snapshot=deepcopy((original,before,after))
        selected=lost_retention_examples(original,before,after)
        self.assertEqual([r['record_id'] for r in selected],['a','d'])
        self.assertEqual((original,before,after),snapshot)

    def test_retention_selection_rejects_missing_changed_duplicate_or_wrong_source_targets(self):
        original,before,after=self.retention_fixture()
        cases=[]
        row=deepcopy(after);row['pages'][0]['targets'].pop();cases.append(row)
        row=deepcopy(after);row['pages'][0]['targets'][0]['class_id']=11;cases.append(row)
        row=deepcopy(after);row['pages'][0]['targets'].append(deepcopy(row['pages'][0]['targets'][0]));cases.append(row)
        row=deepcopy(after);row['pages'][0]['source_sha256']='wrong';cases.append(row)
        row=deepcopy(after);row['pages'][0]['targets'][0]['localized_and_classified']=0;cases.append(row)
        for row in cases:
            with self.assertRaises(ValueError):lost_retention_examples(original,before,row)
        with TemporaryDirectory() as folder:
            root=Path(folder);(root/'manifest.json').write_text('{}')
            output=root/'out'
            with self.assertRaises(ValueError):
                retention_diagnostic(root,root,root,root,root,root,root,output)
            self.assertFalse(output.exists());output.mkdir()
            with self.assertRaises(FileExistsError):
                retention_diagnostic(root,root,root,root,root,root,root,output)


if __name__=='__main__':unittest.main()
