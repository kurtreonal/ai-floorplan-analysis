from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image
from prepare_pec_reference import digest
from prepare_pec_replay import inventory,label_classes,select_replay,reference_context,prepare,recover_byte_evidence


class PecReplayTests(unittest.TestCase):
    def checkpoint_fixture(self,root):
        dataset=root/'dataset';dataset.mkdir();checkpoint=root/'weights.pt';checkpoint.write_bytes(b'local-fixture')
        classes=[{'id':i,'legend_entry':f'drawing:L{i}','label':f'Class {i}','samples':4} for i in range(129)]
        data={'scope':'all_class_reference_replay_development_not_release','diagnostic_only':True,'classes':classes}
        (dataset/'manifest.json').write_text(json.dumps(data))
        common={'dataset_manifest_sha256':digest(dataset/'manifest.json'),'checkpoint_sha256':digest(checkpoint),
                'threshold':.50,'precision':None}
        replay={**common,'kind':'all_class_reference_replay_same_source_development_probe_v1',
                'model_entries':[{**c,'included_in_training':True,'synthetic_learning_check':None} for c in classes],
                'requested_device_references':[{'reference_id':f'ref-{i}','model_class_id':75+i} for i in range(54)],
                'wiring_references':[{'reference_id':f'wire-{i}'} for i in range(12)]}
        # Independently matched overlapping targets can allocate the sole match to different classes.
        targets=[{'record_id':'a','class_id':0,'localized':False,'localized_and_classified':True},
                 {'record_id':'b','class_id':1,'localized':True,'localized_and_classified':False}]
        measures=[{'class_id':c['id'],'label':c['label'],'legend_entry':c['legend_entry'],
                   'reviewed_positive_count':int(c['id']<2),'localized':int(c['id']==1),
                   'localized_and_classified':int(c['id']==0)} for c in classes]
        original={**common,'kind':'partial_label_full_page_probe_v1',
                  'candidate_shared_tiler_without_activation':True,'class_agnostic':False,
                  'pages':[{'source_sha256':'f'*64,'targets':targets,
                            'predictions':[{'class_id':c,'score':.75} for c in (0,0,1)]}],
                  'summary':{'per_class':measures,'reviewed_positive_count':2,'localized':1,
                             'localized_and_classified':1,'fused_proposals':3,'precision':None}}
        rp=root/'replay.json';op=root/'original.json'
        rp.write_text(json.dumps(replay));op.write_text(json.dumps(original))
        return dataset,checkpoint,rp,op,replay,original

    def test_checkpoint_coverage_distinguishes_proposals_matches_and_independent_allocations(self):
        from probe_pec_reference import write_replay_checkpoint_report
        with TemporaryDirectory() as folder:
            root=Path(folder);dataset,checkpoint,rp,op,_,_=self.checkpoint_fixture(root);output=root/'coverage.json'
            before=[digest(p) for p in (dataset/'manifest.json',checkpoint,rp,op)]
            result=write_replay_checkpoint_report(dataset,checkpoint,rp,op,output)
            report=json.loads(output.read_text());rows=report['all_129_entries']
            self.assertEqual((result['original_entries'],result['all_model_entries'],result['device_references']),(56,129,54))
            self.assertEqual((rows[0]['proposals_on_original_source_pages'],rows[0]['matched_original_source_targets'],
                              rows[0]['localized_original_source_targets']),(2,1,0))
            self.assertEqual(len(report['wiring_references']),12)
            self.assertIsNone(report['precision']);self.assertIsNone(report['independent_accuracy'])
            self.assertFalse(report['active_model_changed']);self.assertFalse(report['human_review_claim'])
            self.assertFalse(report['production_approval'])
            self.assertEqual(before,[digest(p) for p in (dataset/'manifest.json',checkpoint,rp,op)])
            with self.assertRaises(FileExistsError):write_replay_checkpoint_report(dataset,checkpoint,rp,op,output)

    def test_checkpoint_rejects_changed_identity_hash_threshold_and_invented_metrics(self):
        from probe_pec_reference import write_replay_checkpoint_report
        with TemporaryDirectory() as folder:
            root=Path(folder);dataset,checkpoint,rp,op,replay,original=self.checkpoint_fixture(root)
            def bad(which,change):
                fresh=deepcopy(replay if which=='replay' else original);change(fresh)
                path=rp if which=='replay' else op;path.write_text(json.dumps(fresh))
                with self.assertRaises(ValueError):write_replay_checkpoint_report(dataset,checkpoint,rp,op,root/'bad.json')
                self.assertFalse((root/'bad.json').exists());path.write_text(json.dumps(replay if which=='replay' else original))
            bad('replay',lambda r:r.update(checkpoint_sha256='0'*64))
            bad('original',lambda r:r.update(threshold=.25))
            bad('original',lambda r:r.update(precision=.95))
            bad('replay',lambda r:r['model_entries'].pop())
            bad('replay',lambda r:r['model_entries'][0].update(id=False))
            bad('replay',lambda r:r['model_entries'][0].update(label='Wrong'))
            bad('original',lambda r:r['summary']['per_class'][0].update(localized_and_classified=2))
            bad('original',lambda r:r['summary'].update(fused_proposals=999))
            bad('original',lambda r:r['pages'][0]['targets'][0].update(localized=1))
            bad('original',lambda r:r['pages'][0]['targets'].append(deepcopy(r['pages'][0]['targets'][0])))
            bad('original',lambda r:r['pages'][0]['predictions'][0].update(score=float('nan')))
            checkpoint.write_bytes(b'changed')
            with self.assertRaises(ValueError):write_replay_checkpoint_report(dataset,checkpoint,rp,op,root/'bad.json')

    def test_balanced_selection_keeps_every_old_class_without_counting_replicas_as_new(self):
        rows={f'{i}-{j}':{'kind':'real','classes':{i},'image_sha256':f'{i:03d}-{j:03d}'}
              for i in range(80) for j in range(12)}
        chosen=select_replay(rows)
        self.assertEqual(len(chosen),640)
        self.assertEqual(set().union(*(rows[n]['classes'] for n in chosen)),set(range(80)))
        self.assertEqual(chosen,select_replay(rows))
        for key in list(rows):
            if 79 in rows[key]['classes']:rows.pop(key)
        with self.assertRaises(ValueError):select_replay(rows)

    def test_labels_fail_on_unbounded_box_unknown_class_or_nan(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/'labels.txt'
            for text in ('80 .5 .5 .2 .2','0 nan .5 .2 .2','0 .01 .5 .3 .2','0 .5 .5 0 .2','0.0 .5 .5 .2 .2'):
                path.write_text(text)
                with self.subTest(text=text),self.assertRaises((ValueError,OverflowError)):label_classes(path,80)
            path.write_text('79 .5 .5 .2 .2\n')
            self.assertEqual(label_classes(path,80),{79})

    def test_generated_context_preserves_symbol_pixels_and_original_image(self):
        with Image.new('RGB',(256,256),'white') as image:
            image.putpixel((100,100),(0,0,0));before=image.tobytes()
            result=reference_context(image,[90,90,115,115],0)
            self.assertEqual(result.crop((90,90,115,115)).tobytes(),image.crop((90,90,115,115)).tobytes())
            self.assertEqual(image.tobytes(),before)
            self.assertNotEqual(result.tobytes(),before);result.close()

    def fixture(self,root):
        parent=root/'old';ref=root/'ref'
        for folder in (parent,ref):
            (folder/'images/train').mkdir(parents=True);(folder/'labels/train').mkdir(parents=True)
        classes=[{'id':i,'label':f'Class {i}','legend_entry':f'drawing:L{i}','samples':1} for i in range(129)]
        old={'kind':'positive_only_masked_symbol_detection_diagnostic_v1','all_eligible_entries':True,
             'required_loss':'positive_boxes_and_explicit_reviewed_background','diagnostic_only':False,
             'classes':deepcopy(classes[:80]),'images':[],'additional_training_authorizations':[],
             'warnings':[],'authored_legend_synthetic_images':[],'reviewed_background_images':[]}
        def tile(folder,name,cls):
            ip=folder/'images/train'/f'{name}.png';lp=folder/'labels/train'/f'{name}.txt'
            Image.new('RGB',(256,256),'white').save(ip);lp.write_text(f'{cls} .5 .5 .125 .125\n')
            return {'image_id':name,'class_id':cls,'image_sha256':digest(ip),'label_sha256':digest(lp),
                    'source_sha256':None,'box':[112,112,144,144],'human_review_claim':False,
                    'label_origin':'known_synthetic_composite_geometry','split':'train'}
        for i in range(80):
            row=tile(parent,f'old-{i}',i);row['record_id']=row.pop('image_id');old['images'].append(row)
        (parent/'manifest.json').write_text(json.dumps(old));checkpoint=root/'old.pt';checkpoint.write_bytes(b'fixture')
        head=ref/'initialized-head.pt';head.write_bytes(b'expanded-fixture')
        reference={'classes':classes,'additional_training_authorizations':[],
                   'reference_registry_sha256':'f'*64,'base_model_sha256':digest(head),
                   'reference_specification':{'point_mappings':[{'model_class_id':i} for i in range(75,129)],
                                              'wiring_references':[{} for _ in range(12)]},
                   'authored_legend_synthetic_images':[]}
        for index in range(248):reference['authored_legend_synthetic_images'].append(tile(ref,f'authored-legend-pec-{index}',75+index%54))
        (ref/'manifest.json').write_text(json.dumps(reference))
        return parent,ref,checkpoint,old

    def test_end_to_end_manifest_preserves_unknown_region_loss_all_classes_and_originals(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);parent,ref,checkpoint,old=self.fixture(root)
            original=digest(parent/'manifest.json');reference=digest(ref/'manifest.json')
            with patch.multiple('prepare_pec_replay',PARENT_DATASET_SHA256=original,
                                REFERENCE_DATASET_SHA256=reference,PARENT_CHECKPOINT_SHA256=digest(checkpoint)):
                output=root/'out';result=prepare(parent,ref,checkpoint,output)
                self.assertEqual(result['supervised_class_ids'],129);self.assertEqual(result['train_windows'],328)
                data=json.loads((output/'manifest.json').read_text())
                self.assertEqual(data['required_loss'],'positive_boxes_and_explicit_reviewed_background')
                self.assertTrue(data['synthetic_complete_background']);self.assertTrue(data['diagnostic_only'])
                self.assertFalse(data['production_approval']);self.assertTrue(data['all_eligible_entries'])
                self.assertTrue(all(r['samples']>0 for r in data['classes']))
                self.assertEqual([r['label'] for r in data['classes'][:80]],[r['label'] for r in old['classes']])
                for row in old['images']:
                    self.assertEqual(digest(output/'labels/train'/f"{row['record_id']}.txt"),row['label_sha256'])
                self.assertEqual(digest(parent/'manifest.json'),original)
                self.assertEqual(digest(ref/'manifest.json'),reference)
                from probe_symbol_detector_dev import probe_authored_synthetic
                model=SimpleNamespace(names={r['id']:r['label'] for r in data['classes']},
                    predict=lambda images,**kw:[SimpleNamespace(boxes=[]) for _ in images])
                with patch('probe_symbol_detector_dev.YOLO',return_value=model):
                    summaries=probe_authored_synthetic(output,output/'initialized-head.pt',root/'probe',samples_per_class=1)
                self.assertEqual(len(summaries),54)
                report=json.loads((root/'probe/report.json').read_text())
                self.assertTrue(report['all_class_reference_replay']);self.assertIsNone(report['independent_accuracy'])
                data['all_eligible_entries']=False;(output/'manifest.json').write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    probe_authored_synthetic(output,output/'initialized-head.pt',root/'bad-probe',samples_per_class=1)
                self.assertFalse((root/'bad-probe').exists())
                with self.assertRaises(FileExistsError):prepare(parent,ref,checkpoint,output)

    def test_tampered_source_rejected_before_output(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);parent,ref,checkpoint,old=self.fixture(root)
            with patch.multiple('prepare_pec_replay',PARENT_DATASET_SHA256=digest(parent/'manifest.json'),
                                REFERENCE_DATASET_SHA256=digest(ref/'manifest.json'),PARENT_CHECKPOINT_SHA256=digest(checkpoint)):
                (parent/'labels/train/old-0.txt').write_text('1 .5 .5 .125 .125\n')
                with self.assertRaises(ValueError):prepare(parent,ref,checkpoint,root/'out')
                self.assertFalse((root/'out').exists())

    def test_missing_historical_hashes_are_explicitly_excluded_not_invented(self):
        with TemporaryDirectory() as folder:
            parent,_,_,old=self.fixture(Path(folder))
            old['images'][0].pop('image_sha256')
            with self.assertRaises(ValueError):inventory(parent,old)
            exclusions=[];rows=inventory(parent,old,missing_hash_exclusions=exclusions)
            self.assertNotIn('old-0',rows);self.assertEqual(len(exclusions),1)
            self.assertEqual(exclusions[0]['original_metadata'],old['images'][0])
            with self.assertRaises(ValueError):select_replay(rows)

    def test_replay_evaluation_reports_every_class_and_does_not_invent_independent_metrics(self):
        from probe_pec_reference import replay_probe
        with TemporaryDirectory() as folder:
            root=Path(folder);parent,ref,checkpoint,old=self.fixture(root)
            old['switch_source_targets']=[{'class_id':62,'source_sha256':'s','source_box':[1,1,5,5]} for _ in range(9)]
            (parent/'manifest.json').write_text(json.dumps(old));image=parent/'images/train/old-0.png'
            data=json.loads((ref/'manifest.json').read_text())
            data.update(scope='all_class_reference_replay_development_not_release',diagnostic_only=True,all_eligible_entries=True)
            for index,row in enumerate(data['reference_specification']['point_mappings']):row['reference_id']=f'ref-{index}'
            (ref/'manifest.json').write_text(json.dumps(data))
            targets=[{'class_id':56,'source_box':[1,1,5,5]} for _ in range(20)]
            def synthetic(dataset,weights,out,**kwargs):
                out.mkdir(parents=True)
                rows=[{'reference_id':r['reference_id'],'localized_and_classified':True} for r in data['reference_specification']['point_mappings']]
                summary=[{'class_id':r['model_class_id'],'tested':1,'localized':1,'localized_and_classified':1} for r in data['reference_specification']['point_mappings']]
                (out/'report.json').write_text(json.dumps({'results':rows,'summary':summary}))
            def table(dataset,weights,prepared,registry,out,*,page_number):
                out.mkdir(parents=True);mapping=data['reference_specification']['point_mappings'][(page_number-1)*27:page_number*27]
                ts=[{'class_id':r['model_class_id'],'reference_id':r['reference_id'],'source_box':[1,1,5,5]} for r in mapping]
                ps=[{'class_id':t['class_id'],'bbox':t['source_box']} for t in ts]
                (out/'reference-report.json').write_text(json.dumps({'source_page_id':f'fixture:page:{page_number}',
                    'targets':ts,'predictions':ps,'target_count':27,'localized':27,'classified_and_localized':27,'truncated':False}))
            def upload(path,out,**kwargs):
                out.mkdir(parents=True);(out/'report.json').write_text(json.dumps({'predictions':[
                    {'class_id':56,'bbox':[1,1,5,5]},{'class_id':62,'bbox':[1,1,5,5]}],'truncated':False}))
            with patch('probe_pec_reference.PARENT_DATASET_SHA256',digest(parent/'manifest.json')), \
                 patch('probe_real_lamps.select_lamp_view',return_value=({'source_sha256':'s'},None,image,targets)), \
                 patch('probe_pec_reference.probe_authored_synthetic',side_effect=synthetic), \
                 patch('probe_pec_reference.table_probe',side_effect=table), \
                 patch('probe_pec_reference.probe_unreviewed_image',side_effect=upload):
                output=root/'evaluation';result=replay_probe(ref,checkpoint,root,root/'registry.json',parent,output)
            report=json.loads((output/'report.json').read_text())
            self.assertEqual(len(report['model_entries']),129);self.assertEqual(len(report['requested_device_references']),54)
            self.assertEqual(result['retention_upload']['all']['localized_and_classified'],2)
            self.assertEqual(result['table_correct'],54);self.assertIsNone(report['precision'])
            self.assertIsNone(report['independent_accuracy']);self.assertFalse(report['active_model_changed'])
            self.assertFalse(report['human_review_claim']);self.assertFalse(report['production_approval'])
            with self.assertRaises(FileExistsError):replay_probe(ref,checkpoint,root,root/'registry.json',parent,output)

    def test_replay_evaluation_wrong_parent_rejected_before_probes(self):
        from probe_pec_reference import replay_probe
        with TemporaryDirectory() as folder:
            root=Path(folder);parent,ref,checkpoint,_=self.fixture(root)
            with patch('probe_pec_reference.probe_authored_synthetic') as probe:
                with self.assertRaises(ValueError):replay_probe(ref,checkpoint,root,root/'registry.json',parent,root/'out')
                self.assertFalse((root/'out').exists());probe.assert_not_called()

    def test_recovered_pixels_labels_source_hash_and_history_verified_without_original_edits(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);parent,_,_,old=self.fixture(root);sources=root/'sources';sources.mkdir()
            original=sources/'sheet-01.jpg';Image.new('RGB',(300,300),'gray').save(original)
            source_hash=digest(original);name='recovered-test'
            with Image.open(original) as source:source.convert('RGB').crop((0,0,256,256)).save(parent/'images/train'/f'{name}.png')
            label=parent/'labels/train'/f'{name}.txt';label.write_text('0 .1171875 .1171875 .078125 .078125\n')
            row={'record_id':name,'sheet_id':'sheet-01','source_sha256':source_hash,'legend_entry':'drawing:L0',
                 'class_id':0,'source_box':[20,20,40,40],'source_crop':[0,0,256,256],'recovered_placement':True}
            recovery=root/'recovery.json';recovery.write_text(json.dumps({'records':[{
                'id':'test','sheet_id':'sheet-01','source_sha256':source_hash,'legend_entry':'drawing:L0',
                'bbox':[20,20,40,40],'split':'train','group':1}]}))
            old['images'].append(row);old['recovery_manifest_sha256']=digest(recovery)
            (parent/'manifest.json').write_text(json.dumps(old));before=digest(parent/'manifest.json')
            with patch('prepare_pec_replay.PARENT_DATASET_SHA256',before):
                result=recover_byte_evidence(parent,recovery,sources,root/'audit.json')
                self.assertEqual(result['verified_historical_windows'],1)
                audit=json.loads((root/'audit.json').read_text())
                self.assertEqual(audit['verified_records'][0]['original_metadata'],row)
                self.assertFalse(audit['human_review_claim']);self.assertEqual(digest(parent/'manifest.json'),before)
                with self.assertRaises(FileExistsError):recover_byte_evidence(parent,recovery,sources,root/'audit.json')
                label.write_text('1 .1171875 .1171875 .078125 .078125\n')
                with self.assertRaises(ValueError):recover_byte_evidence(parent,recovery,sources,root/'bad.json')
                self.assertFalse((root/'bad.json').exists())
                original.write_bytes(b'changed')
                with self.assertRaises(ValueError):recover_byte_evidence(parent,recovery,sources,root/'bad-source.json')
                self.assertFalse((root/'bad-source.json').exists())


if __name__=='__main__':unittest.main()
