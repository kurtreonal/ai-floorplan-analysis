import json
from pathlib import Path
import tempfile
import unittest

from prepare_authorized_pdf_detection import learning_check, source_boxes, validate_authorization, validate_training_sources
from prepare_authored_legend_extension import digest
from probe_authorized_pdf_detection import score, select_source_targets


class AuthorizedPDFTests(unittest.TestCase):
    def test_multisource_replay_denominator_is_scoped_by_exact_pdf_not_page_or_coordinates(self):
        first={'pdf_sha256':'a'*64,'page_number':3,'source_box':[0,0,10,10],'class_id':56}
        second={**first,'pdf_sha256':'b'*64}
        targets=select_source_targets({'authorized_pdf_targets':[first,second]}, {'source_sha256':'a'*64})
        self.assertEqual(targets,[first])
        self.assertEqual(score(targets,[{'bbox':[0,0,10,10],'class_id':56}])['class_recall'],1)

    def test_metric_matching_is_one_to_one_and_not_independent_accuracy(self):
        targets=[{'source_box':[0,0,10,10],'class_id':56}]*2
        result=score(targets,[{'bbox':[0,0,10,10],'class_id':56}])
        self.assertEqual(result['localized_and_classified'],1)
        self.assertEqual(result['class_recall'],.5)
        self.assertIsNone(result['precision']);self.assertIsNone(result['independent_accuracy'])
        result=score(targets,[{'bbox':[0,0,10,10],'class_id':57}])
        self.assertEqual(result['localized'],1);self.assertEqual(result['localized_and_classified'],0)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.auth={'schema':'ved-user-authorized-development-label-preparation-v1',
            'source_sha256':'a'*64,'prepared_manifest_sha256':'b'*64,
            'local_development_training':True,'delegated_assistant_annotation':True,
            'human_review_claim':False,'production_approval':False,'user_statement':'All approved for training',
            'missing_annotation_policy':'ignore_unreviewed_not_empty_background','project_group_id':'one-project',
            'targets':[{'id':'target-1','page_number':3,'region_id':'L02',
                        'bbox_pdf_top_left_points':[20,30,30,50]}]}
        self.path=self.root/'authorization.json'; self.path.write_text(json.dumps(self.auth))
        self.pages={3:{'pdf_points_to_image':[2,0,0,0,2,0],'width':200,'height':200,'image_sha256':'c'*64}}
        self.regions={'L02':{'proposed_label':'Lamp'}}
        self.mapping={'L02':{'legend_entry':'pdf-source:p1:L02','class_id':56}}

    def test_authority_hash_and_development_scope(self):
        self.assertEqual(validate_authorization(self.path,'a'*64,'b'*64),self.auth)
        for change in ({'source_sha256':'f'*64},{'prepared_manifest_sha256':'f'*64},
                       {'human_review_claim':True},{'production_approval':True},
                       {'delegated_assistant_annotation':False}):
            with self.subTest(change=change):
                self.path.write_text(json.dumps({**self.auth,**change}))
                with self.assertRaises(ValueError):validate_authorization(self.path,'a'*64,'b'*64)

    def test_transform_and_provenance_do_not_claim_human_review(self):
        row=source_boxes(self.auth,self.pages,self.regions,self.mapping)[0]
        self.assertEqual(row['source_box'],[40,60,60,100])
        self.assertEqual(row['class_id'],56); self.assertEqual(row['project_group_id'],'one-project')
        self.assertFalse(row['human_review_claim']); self.assertEqual(row['split'],'train')

    def test_duplicate_unknown_outside_and_nonfinite_targets_rejected(self):
        for rows in ([self.auth['targets'][0]]*2,
                     [{**self.auth['targets'][0],'region_id':'L10'}],
                     [{**self.auth['targets'][0],'bbox_pdf_top_left_points':[-1,1,10,20]}],
                     [{**self.auth['targets'][0],'bbox_pdf_top_left_points':[1,1,float('nan'),20]}]):
            with self.subTest(rows=rows),self.assertRaises(ValueError):
                source_boxes({**self.auth,'targets':rows},self.pages,self.regions,self.mapping)

    def test_hash_changed_source_and_training_artifact_rejected(self):
        data={'additional_training_authorizations':[{'filename':'authorization.json','sha256':digest(self.path),
                'source_sha256':'a'*64,'prepared_manifest_sha256':'b'*64}]}
        self.assertIn('a'*64,validate_training_sources(self.root,data))
        self.path.write_text('{}')
        with self.assertRaises(ValueError):validate_training_sources(self.root,data)
        self.path.write_text(json.dumps(self.auth))
        (self.root/'images/train').mkdir(parents=True);(self.root/'labels/train').mkdir(parents=True)
        image=self.root/'images/train/pdfdev-a.png';label=self.root/'labels/train/pdfdev-a.txt'
        image.write_bytes(b'image'); label.write_text('56 .5 .5 .1 .1')
        data['authorized_pdf_training_images']=[{'image_id':'pdfdev-a','source_sha256':'a'*64,
            'human_review_claim':False,'annotation_origin':'assistant_visual_under_user_development_authorization',
            'image_sha256':digest(image),'label_sha256':digest(label)}]
        validate_training_sources(self.root,data)
        label.write_text('57 .5 .5 .1 .1')
        with self.assertRaises(ValueError):validate_training_sources(self.root,data)

    def test_real_learning_check_preserves_head_parent_and_delegated_authority(self):
        (self.root/'images/train').mkdir(parents=True);(self.root/'labels/train').mkdir(parents=True)
        rows=[]
        for index in range(35):
            name=f'pdfdev-{index}'; ip=self.root/'images/train'/f'{name}.png';lp=self.root/'labels/train'/f'{name}.txt'
            ip.write_bytes(b'fixture');lp.write_text('56 .5 .5 .1 .1')
            rows.append({'image_id':name,'source_sha256':'a'*64,'human_review_claim':False,
                'annotation_origin':'assistant_visual_under_user_development_authorization',
                'image_sha256':digest(ip),'label_sha256':digest(lp)})
        data={'classes':[{'id':i} for i in range(80)],'authorized_pdf_training_images':rows,
              'additional_training_authorizations':[{'filename':'authorization.json','sha256':digest(self.path),
                  'source_sha256':'a'*64,'prepared_manifest_sha256':'b'*64}]}
        manifest=self.root/'manifest.json';manifest.write_text(json.dumps(data));before=digest(manifest)
        (self.root/'data.yaml').write_text('path: fixture\ntrain: images/train\nval: images/train\n')
        checkpoint=self.root/'base.pt';checkpoint.write_bytes(b'fixture')
        output=self.root/'check';learning_check(self.root,checkpoint,output)
        subset=json.loads((output/'manifest.json').read_text())
        self.assertEqual(len(subset['classes']),80);self.assertTrue(subset['diagnostic_only'])
        self.assertFalse(subset['all_eligible_entries']);self.assertEqual(subset['reviewed_targets'],[])
        self.assertEqual(digest(manifest),before)
        self.assertEqual(subset['base_model_sha256'],digest(checkpoint))
        with self.assertRaises(FileExistsError):learning_check(self.root,checkpoint,output)

    def test_background_requires_authorized_source_no_human_claim_and_empty_labels(self):
        (self.root/'images/train').mkdir(parents=True);(self.root/'labels/train').mkdir(parents=True)
        name='reviewed-negative-pdfdev-01';ip=self.root/'images/train'/f'{name}.png';lp=self.root/'labels/train'/f'{name}.txt'
        ip.write_bytes(b'fixture');lp.write_text('')
        row={'image_id':name,'sha256':digest(ip),'source_sha256':'a'*64,'human_review_claim':False,
             'annotation_origin':'assistant_visual_under_user_development_authorization'}
        data={'additional_training_authorizations':[{'filename':'authorization.json','sha256':digest(self.path),
                  'source_sha256':'a'*64,'prepared_manifest_sha256':'b'*64}],
              'assistant_reviewed_background_regions':[row],'reviewed_background_images':[row]}
        validate_training_sources(self.root,data)
        lp.write_text('56 .5 .5 .1 .1')
        with self.assertRaises(ValueError):validate_training_sources(self.root,data)
        lp.write_text('');row['human_review_claim']=True
        with self.assertRaises(ValueError):validate_training_sources(self.root,data)


if __name__=='__main__':unittest.main()
