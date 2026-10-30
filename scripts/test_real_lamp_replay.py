import unittest
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from prepare_real_lamp_replay import transformed_labels, inspected_upload_targets, replay_plan
from prepare_authored_legend_extension import digest
from probe_real_lamps import select_lamp_view, coverage
from train_symbol_detector_dev import validate_restorative_replay


class RealLampTransformTests(unittest.TestCase):
    def test_pdf_hash_and_rendered_page_hash_have_distinct_roles_in_scoring(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary);image=root/'panel.png';image.write_bytes(b'fixture')
            source={'source_sha256':'a'*64,'regions':[{'region_id':'lighting-layout','filename':'panel.png',
                    'page_number':7,'source_image_sha256':'b'*64,'crop_sha256':digest(image)}]}
            (root/'manifest.json').write_text(json.dumps(source))
            data={'lamp_source_targets':[{'pdf_sha256':'a'*64,'source_sha256':'b'*64,'page_number':7}]}
            self.assertEqual(select_lamp_view(root,data,root)[2],image)
            data['lamp_source_targets'][0]['source_sha256']='a'*64
            with self.assertRaises(ValueError):select_lamp_view(root,data,root)

    def test_all_entry_coverage_preserves_unobserved_classes_and_rejects_mixed_checkpoint_evidence(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary);checkpoint=root/'weights.pt';checkpoint.write_bytes(b'fixture')
            data={'all_eligible_entries':True,
                  'classes':[{'id':i,'label':f'Fixture {i}','legend_entry':f'legend:{i}','samples':1} for i in range(80)],
                  'reviewed_targets':[{'class_id':0}]}
            manifest=root/'manifest.json';manifest.write_text(json.dumps(data))
            report={'checkpoint_sha256':digest(checkpoint),'dataset_manifest_sha256':digest(manifest),
                    'predictions':[{'class_id':0}],'per_class':[{'class_id':0,'localized_and_classified':1}]}
            path=root/'probe.json';path.write_text(json.dumps(report))
            output=root/'coverage';self.assertEqual(coverage(root,checkpoint,{'source':path},output)['entries'],80)
            result=json.loads((output/'report.json').read_text())
            self.assertIsNone(result['precision']);self.assertIsNone(result['independent_accuracy'])
            self.assertEqual(result['entries'][0]['same_source_probes']['source']['class_and_location_matches'],1)
            self.assertEqual(result['entries'][79]['same_source_probes']['source']['prediction_count'],0)
            self.assertIsNone(result['entries'][79]['same_source_probes']['source']['class_and_location_matches'])
            with self.assertRaises(FileExistsError):coverage(root,checkpoint,{'source':path},output)
            report['checkpoint_sha256']='a'*64;path.write_text(json.dumps(report))
            with self.assertRaises(ValueError):coverage(root,checkpoint,{'source':path},root/'invalid')

    def test_restorative_replay_uses_train_only_preserves_multilabel_windows_and_rejects_missing_classes(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary);labels=root/'labels/train';labels.mkdir(parents=True)
            (labels/'original.txt').write_text('21 .2 .3 .1 .1\n51 .4 .3 .1 .1\n')
            plan=replay_plan(root,(21,51),3)
            self.assertEqual(len(plan),4)
            self.assertTrue(all(r['sampling_parent']=='original' and r['split']=='train'
                                and not r['independent_example'] for r in plan))
            self.assertEqual(len({r['image_id'] for r in plan}),4)
            with self.assertRaises(ValueError):replay_plan(root,(62,),3)
            with self.assertRaises(ValueError):replay_plan(root,(21,),201)

    def test_switch_coverage_keeps_related_sources_separate_and_retains_aliases(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary);checkpoint=root/'weights.pt';checkpoint.write_bytes(b'fixture')
            data={'all_eligible_entries':True,
                'classes':[{'id':i,'label':f'Fixture {i}','legend_entry':f'legend:{i}','samples':1} for i in range(80)],
                'switch_source_targets':[{'class_id':63,'source_legend_entry':'deped:L05','parent_pdf_sha256':'a'*64}]}
            manifest=root/'manifest.json';manifest.write_text(json.dumps(data))
            report={'checkpoint_sha256':digest(checkpoint),'dataset_manifest_sha256':digest(manifest),
                'sources':[{'source':'pdf','predictions':[{'class_id':63}],
                    'per_class':[{'class_id':63,'localized_and_classified':1}]},
                    {'source':'related-upload','predictions':[],
                    'per_class':[{'class_id':63,'localized_and_classified':0}]}]}
            path=root/'probe.json';path.write_text(json.dumps(report))
            coverage(root,checkpoint,{'switches':path},root/'coverage')
            entry=json.loads((root/'coverage/report.json').read_text())['entries'][63]
            self.assertEqual(entry['source_legend_aliases'],['deped:L05'])
            self.assertEqual(entry['real_source_box_counts']['dependent_upload_switches'],1)
            self.assertEqual(entry['same_source_probes']['switches/pdf']['class_and_location_matches'],1)
            self.assertEqual(entry['same_source_probes']['switches/related-upload']['class_and_location_matches'],0)

    def test_restorative_replicas_are_hash_checked_and_cannot_introduce_labels_or_validation_data(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary)
            for folder in ('images/train','labels/train'):(root/folder).mkdir(parents=True)
            row={'image_id':'restored-replay-21-000','sampling_parent':'source','class_id':21,
                 'split':'train','independent_example':False}
            for folder,suffix,key,contents in (('images/train','png','image_sha256',b'fixture'),
                                              ('labels/train','txt','label_sha256',b'21 .2 .3 .1 .1')):
                for name in (row['image_id'],row['sampling_parent']):(root/folder/f'{name}.{suffix}').write_bytes(contents)
                row[key]=digest(root/folder/f"{row['image_id']}.{suffix}")
            data={'restorative_replay_sampling':{'independent_examples_added':0,'replicas':[row]}}
            validate_restorative_replay(root,data)
            for change in ({'split':'validation'},{'class_id':51},{'image_id':'../elsewhere'},
                           {'independent_example':True},{'image_sha256':'a'*64}):
                altered=deepcopy(data);altered['restorative_replay_sampling']['replicas'][0].update(change)
                with self.subTest(change=change),self.assertRaises(ValueError):validate_restorative_replay(root,altered)

    def test_upload_scoring_uses_exact_derivative_pixels_and_rejects_wrong_source_targets(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary); image=root/'original-upload.png';image.write_bytes(b'fixture')
            source={'source_sha256':digest(image)}
            (root/'upload-preparation.json').write_text(json.dumps(source))
            targets=[{'source_sha256':source['source_sha256'],'source_box':[62,334,100,346],'class_id':57}]
            data={'lamp_upload_targets':targets,'lamp_source_targets':[{'source_box':[2000,3000,2100,3020]}]}
            actual,region,path,selected=select_lamp_view(root,data,upload=True)
            self.assertEqual(actual,source);self.assertEqual(path,image)
            self.assertEqual(region['bbox_source_pixels'],[0,0]);self.assertIs(selected,targets)
            targets[0]['source_sha256']='a'*64
            with self.assertRaises(ValueError):select_lamp_view(root,data,upload=True)
            targets[0]['source_sha256']=source['source_sha256'];image.write_bytes(b'altered')
            with self.assertRaises(ValueError):select_lamp_view(root,data,upload=True)

    def test_derivative_targets_are_bounded_source_tied_and_train_only_with_no_fake_human_review(self):
        evidence={'source_sha256':'a'*64,'parent_source_sha256':'b'*64,'project_group_id':'related-project',
                  'annotation_origin':'assistant_visual_under_user_development_authorization',
                  'targets':[{'id':f'fixture{i}','class_id':56 if i<16 else 57,'box':[10,20,30,40]} for i in range(20)]}
        data={'classes':[{'legend_entry':f'legend:{i}'} for i in range(80)]}
        targets=inspected_upload_targets(evidence,data,691,488)
        self.assertEqual(len(targets),20)
        self.assertEqual(targets[16]['legend_entry'],'legend:57')
        self.assertTrue(all(t['split']=='train' and not t['human_review_claim']
                            and t['project_group_id']=='related-project' for t in targets))
        for change in ({'id':'../../other'},{'id':'fixture1'},{'class_id':20},
                       {'box':[-1,1,10,20]},{'box':[1,1,10,500]},{'box':[1,1,10,float('nan')]}):
            with self.subTest(change=change):
                altered=deepcopy(evidence);altered['targets'][0].update(change)
                with self.assertRaises(ValueError):inspected_upload_targets(altered,data,691,488)

    def test_isotropic_scale_and_tile_translation_preserve_subtype_and_source_record(self):
        targets = [{'record_id':'double','class_id':56,'source_box':[200,300,240,400]},
                   {'record_id':'single','class_id':57,'source_box':[300,300,400,340]}]
        rows,ids = transformed_labels(targets,.5,80,100)
        self.assertEqual(ids,['double','single'])
        self.assertEqual([int(row.split()[0]) for row in rows],[56,57])
        actual = [float(v) for v in rows[0].split()[1:]]
        self.assertAlmostEqual(actual[0],30/256)
        self.assertAlmostEqual(actual[1],75/256)
        self.assertAlmostEqual(actual[2],20/256)
        self.assertAlmostEqual(actual[3],50/256)

    def test_clipped_or_unknown_neighbor_is_not_silently_made_a_positive_or_negative(self):
        targets = [{'record_id':'inside','class_id':56,'source_box':[10,20,40,60]},
                   {'record_id':'clipped','class_id':57,'source_box':[250,20,270,60]}]
        rows,ids = transformed_labels(targets,1,0,0)
        self.assertEqual(ids,['inside'])
        self.assertEqual(len(rows),1)
        self.assertTrue(rows[0].startswith('56 '))

    def test_scaled_context_does_not_merge_two_adjacent_lamps_or_change_numeric_head_ids(self):
        targets = [{'record_id':str(i),'class_id':56+i,'source_box':[20+i*50,10,40+i*50,30]}
                   for i in range(2)]
        for scale in (.4,.6,.8,1):
            rows,ids = transformed_labels(targets,scale,0,0)
            self.assertEqual(ids,['0','1'])
            self.assertEqual([int(row.split()[0]) for row in rows],[56,57])
