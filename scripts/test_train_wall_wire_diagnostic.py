"""Offline diagnostic guard tests; do not touch datasets, production weights or DB."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import cv2
import numpy as np

from train_wall_wire_diagnostic import (
    PREPROCESSING, component_partition, digest, fit_model, load_dataset,
    pixel_features, prediction_report, run, sample_strip,
)


class CanonicalStripTests(unittest.TestCase):
    def test_reversed_horizontal_vertical_diagonal_segments_have_exact_same_crop(self):
        gray=np.arange(300*300,dtype=np.uint32).reshape(300,300).astype(np.uint8)
        original=gray.copy()
        for segment in ([[70,100],[230,100]],[[150,50],[150,250]],[[70,70],[230,230]],[[130,150],[170,150]]):
            with self.subTest(segment=segment):
                crop,quad=sample_strip(gray,segment)
                reverse,reversed_quad=sample_strip(gray,list(reversed(segment)))
                self.assertEqual(crop.shape,(48,128));self.assertEqual(crop.dtype,np.uint8)
                np.testing.assert_array_equal(crop,reverse)
                np.testing.assert_array_equal(quad,reversed_quad)
        np.testing.assert_array_equal(gray,original)

    def test_short_trace_caps_context_within_reviewed_endpoints(self):
        _,quad=sample_strip(np.zeros((100,100),np.uint8),[[40,50],[60,50]])
        np.testing.assert_array_equal(quad,[[40,30],[60,30],[60,70],[40,70]])

    def test_invalid_segment_or_context_cannot_be_padded_into_truth(self):
        gray=np.zeros((100,100),np.uint8)
        for segment in ([[0,10],[99,10]],[[50,50],[50,50]],[[30,50],[float('nan'),50]],
                        [[30,50],[float('inf'),50]],[[-1,50],[70,50]],[[30,50],[100,50]],[[30,50]]):
            with self.subTest(segment=segment),self.assertRaises(ValueError):sample_strip(gray,segment)
        for source in (gray.astype(float),np.zeros((100,100,3),np.uint8),None):
            with self.subTest(source_type=type(source)),self.assertRaises(ValueError):sample_strip(source,[[40,50],[60,50]])

    def test_pixel_features_only_accept_identical_crop_contract(self):
        vector=pixel_features(np.zeros((48,128),np.uint8))
        self.assertEqual(vector.shape,(384,));self.assertEqual(vector.dtype,np.float32)
        self.assertTrue(np.all(vector==0))
        for crop in (np.zeros((64,128),np.uint8),np.zeros((48,128),float),None):
            with self.subTest(crop_type=type(crop)),self.assertRaises(ValueError):pixel_features(crop)


class DiagnosticManifestTests(unittest.TestCase):
    def setUp(self):
        self.temporary=TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'storage')
        self.addCleanup(self.temporary.cleanup)
        self.base=Path(self.temporary.name);self.sources=self.base/'sources';self.sources.mkdir()
        self.manifest=self.base/'manifest.json'
        records=[];source_hashes={}
        for page,component in ((1,'owner_related_groups_1_6'),(24,'uncertain_groups_8_20')):
            sheet=f'sheet-{page:02}'
            gray=np.random.default_rng(page).integers(230,250,(240,300),dtype=np.uint8)
            cv2.rectangle(gray,(30,53),(270,67),30,-1)
            cv2.line(gray,(30,160),(270,160),30,2)
            source=self.sources/(sheet+'.jpg');self.assertTrue(cv2.imwrite(str(source),gray))
            decoded=cv2.imread(str(source),cv2.IMREAD_GRAYSCALE);source_hashes[sheet]=digest(source)
            for class_name,class_id,y in (('standard_wall',1,60),('explicit_wiring_trace',4,160)):
                segment=[[50,y],[250,y]];crop,quad=sample_strip(decoded,segment)
                name=f'{sheet}-{class_id}.png';cv2.imwrite(str(self.base/name),crop)
                records.append({'annotation_id':f'{sheet}-annotation-{class_id}','sheet_id':sheet,
                    'group':1 if page==1 else 9,'split_component':component,
                    'class_name':class_name,'class_id':class_id,'review_state':'user_reviewed',
                    'assistant_crop_quality':'supports_explicit_class_patch_diagnostic',
                    'source_coordinate_supervision':'explicit_reviewed_trace_class_only',
                    'original_annotation_unchanged':True,'source_sha256':source_hashes[sheet],
                    'source_dimensions':[300,240],'source_segment':segment,'sampling_quadrilateral':quad,
                    'crop_file':name,'crop_sha256':digest(self.base/name)})
        self.data={'schema':'ved-wall-wiring-identical-patch-inspection-v1',
            'class_ids':{'standard_wall':1,'explicit_wiring_trace':4},'preprocessing':deepcopy(PREPROCESSING),
            'authorization_origin':'existing_user_attestation','authorization_sha256':'a'*64,
            'export_sha256':'b'*64,'no_unlabeled_background_truth':True,'records':records,
            'source_hashes':source_hashes,'excluded_current_windows':3}
        self.evidence={
            'wall':{'schema':'ved-reviewed-positive-wall-audit-v1',
                'export_sha256':self.data['export_sha256'],'authorization_sha256':self.data['authorization_sha256'],
                'records':[{**deepcopy(r),'wall_type':'standard','points':r['source_segment']}
                           for r in records if r['class_id']==1]},
            'wire':{'schema':'ved-explicit-wiring-negative-inventory-v1',
                'export_sha256':self.data['export_sha256'],'authorization_sha256':self.data['authorization_sha256'],
                'records':[{**deepcopy(r),'status':'eligible_explicit_wiring_geometry_pending_visual_check',
                    'geometry':{'type':'polyline','coordinates':r['source_segment']}}
                           for r in records if r['class_id']==4]},
            'review':{'schema':'ved-assistant-wire-strip-quality-proposals-v1',
                'separate_human_approval_claimed':False,
                'records':[{'annotation_id':r['annotation_id'],
                    'crop_quality_proposal':'supports_explicit_wiring_strip_diagnostic'}
                           for r in records if r['class_id']==4]}}
        self.write_evidence()
        self.write()

    def write_evidence(self):
        wall=self.base/'wall-audit.json';wire=self.base/'wire-inventory.json';review=self.base/'wire-review.json'
        wall.write_text(json.dumps(self.evidence['wall']),encoding='utf-8')
        self.evidence['wire']['wall_audit_sha256']=digest(wall)
        wire.write_text(json.dumps(self.evidence['wire']),encoding='utf-8')
        self.evidence['review']['inventory_sha256']=digest(wire)
        review.write_text(json.dumps(self.evidence['review']),encoding='utf-8')
        self.data['input_hashes']={p.name:digest(p) for p in (wall,wire,review)}

    def write(self,data=None):
        self.manifest.write_text(json.dumps(data or self.data),encoding='utf-8')

    def rejects(self,change):
        data=deepcopy(self.data);change(data);self.write(data)
        with self.assertRaises(ValueError):load_dataset(self.manifest,self.sources,self.base)

    def test_valid_source_verified_dataset_is_exact_and_metadata_free(self):
        before={p:p.read_bytes() for p in self.sources.iterdir()}
        data,x,y=load_dataset(self.manifest,self.sources,self.base)
        self.assertEqual(x.shape,(4,384));np.testing.assert_array_equal(y,[1,4,1,4])
        for i,row in enumerate(data['records']):
            np.testing.assert_array_equal(x[i],pixel_features(cv2.imread(str(self.base/row['crop_file']),cv2.IMREAD_GRAYSCALE)))
        self.assertTrue(all(p.read_bytes()==body for p,body in before.items()))

    def test_manifest_identity_and_preprocessing_are_required(self):
        changes=[lambda d:d.update(schema='other'),lambda d:d.update(export_sha256='invalid'),
                 lambda d:d.update(authorization_sha256=None),lambda d:d.update(authorization_origin='fabricated_approver'),
                 lambda d:d.update(no_unlabeled_background_truth=False),
                 lambda d:d['preprocessing'].update(shape=[64,128])]
        for i,change in enumerate(changes):
            with self.subTest(case=i):self.rejects(change)

    def test_excluded_unresolved_and_unapproved_crop_states_remain_rejected(self):
        for state in ('deleted','excluded','needs_review','rescan_needed','unresolved'):
            with self.subTest(state=state):self.rejects(lambda d:d['records'][0].update(review_state=state))
        self.rejects(lambda d:d['records'][0].update(assistant_crop_quality='exclude_selected_window'))
        self.rejects(lambda d:d['records'][0].update(original_annotation_unchanged=False))

    def test_class_ids_are_strict_integers_not_bool_or_float_equivalents(self):
        for label in (True,1.0,99,None):
            with self.subTest(label=repr(label)):self.rejects(lambda d:d['records'][0].update(class_id=label))
        self.rejects(lambda d:d['records'][0].update(class_name='glass_wall'))
        self.rejects(lambda d:d.update(records=[r for r in d['records'] if r['class_id']==1]))

    def test_source_and_crop_hash_pairing_and_dimensions_cannot_be_changed(self):
        changes=[lambda d:d['records'][0].update(source_sha256='c'*64),
                 lambda d:d['source_hashes'].update({'sheet-01':'c'*64}),
                 lambda d:d['records'][0].update(crop_sha256='c'*64),
                 lambda d:d['records'][0].update(source_dimensions=[299,240]),
                 lambda d:d['records'][0].update(crop_file='../escape.png'),
                 lambda d:d['records'][0].update(source_segment=[[50,80],[250,80]]),
                 lambda d:d['records'][0].update(source_segment=[[50,60],[float('nan'),60]]),
                 lambda d:d['records'][0].update(sampling_quadrilateral=[[0,0]]*4)]
        for i,change in enumerate(changes):
            with self.subTest(case=i):self.rejects(change)

    def test_duplicate_identity_or_duplicate_features_are_not_independent_examples(self):
        self.rejects(lambda d:d['records'].append(deepcopy(d['records'][0])))
        duplicate=deepcopy(self.data['records'][0]);duplicate['annotation_id']='new-identity-same-pixels'
        authority=deepcopy(self.evidence['wall']['records'][0]);authority['annotation_id']=duplicate['annotation_id']
        self.evidence['wall']['records'].append(authority);self.write_evidence()
        self.data['records'].append(duplicate);self.write()
        with self.assertRaisesRegex(ValueError,'Duplicate or conflicting crop features'):
            load_dataset(self.manifest,self.sources,self.base)

    def test_provenance_hash_inputs_and_all_three_linked_inputs_are_required(self):
        for change in (lambda d:d.pop('input_hashes'),
                       lambda d:d['input_hashes'].update({'wall-audit.json':'c'*64}),
                       lambda d:d['input_hashes'].pop('wire-review.json'),
                       lambda d:d['input_hashes'].update({'../escape.json':'c'*64})):
            with self.subTest(change=change):self.rejects(change)

    def test_authorization_and_export_tampering_break_lineage(self):
        for key in ('authorization_sha256','export_sha256'):
            with self.subTest(key=key):self.rejects(lambda d:d.update({key:'c'*64}))

    def test_source_authority_membership_class_status_and_review_are_required(self):
        self.rejects(lambda d:d['records'][0].update(annotation_id='not-in-reviewed-audit'))
        self.rejects(lambda d:d['records'][0].update(review_state='corrected'))
        self.evidence['review']['records'][0]['crop_quality_proposal']='exclude_selected_window'
        self.write_evidence();self.write()
        with self.assertRaisesRegex(ValueError,'Trace not in reconciled source evidence'):
            load_dataset(self.manifest,self.sources,self.base)

    def test_longest_source_trace_not_merely_reconstructed_pixels_controls_pairing(self):
        self.evidence['wall']['records'][0]['points']=[[50,60],[100,60],[250,60]]
        self.write_evidence();self.write()
        with self.assertRaisesRegex(ValueError,'Trace segment changed from reconciled source'):
            load_dataset(self.manifest,self.sources,self.base)

    def test_groups1_6_cannot_split_across_different_pages_or_source_hashes(self):
        for r in self.data['records'][2:]:r['group']=4
        for category in ('wall','wire'):
            self.evidence[category]['records'][1]['group']=4
        self.write_evidence();self.write()
        with self.assertRaisesRegex(ValueError,'Related floors/groups cross split components'):
            load_dataset(self.manifest,self.sources,self.base)

    def test_uncertain_groups8_20_cannot_split_across_different_pages_or_source_hashes(self):
        for r in self.data['records'][:2]:r['group']=8
        for category in ('wall','wire'):
            self.evidence[category]['records'][0]['group']=8
        self.write_evidence();self.write()
        with self.assertRaisesRegex(ValueError,'Related floors/groups cross split components'):
            load_dataset(self.manifest,self.sources,self.base)

    def test_group_scope_rejects_outside_authorization_and_bool(self):
        for group in (0,23,True,1.0,None):
            with self.subTest(group=repr(group)):
                self.rejects(lambda d:d['records'][0].update(group=group))

    def test_component_partition_keeps_every_related_page_crop_together(self):
        rows=deepcopy(self.data['records'])
        # Another floor/source belongs to the same mandatory component.
        rows.append({**rows[0],'sheet_id':'sheet-17','source_sha256':'d'*64})
        train,test=component_partition(rows,['owner_related_groups_1_6'])
        self.assertEqual(train,[0,1,4]);self.assertEqual(test,[2,3])
        self.assertFalse({rows[i]['source_sha256'] for i in train}&{rows[i]['source_sha256'] for i in test})
        with self.assertRaises(ValueError):component_partition(rows,[])
        with self.assertRaises(ValueError):component_partition(rows,['missing-component'])

    def test_same_source_cannot_cross_split_components(self):
        self.rejects(lambda d:d['records'][1].update(split_component='other-component'))
        rows=deepcopy(self.data['records']);rows[2]['source_sha256']=rows[0]['source_sha256']
        with self.assertRaises(ValueError):component_partition(rows,['owner_related_groups_1_6'])

    def test_save_reload_smoke_keeps_explicit_class_ids_and_sources_unchanged(self):
        data,x,y=load_dataset(self.manifest,self.sources,self.base)
        model=fit_model(x,y);path=self.base/'model.xml';model.save(str(path))
        restored=cv2.ml.RTrees_load(str(path))
        np.testing.assert_array_equal(model.predict(x)[1],restored.predict(x)[1])
        report=prediction_report(restored,x,y,data['records'])
        self.assertEqual(report['class_order'],[1,4]);self.assertEqual(report['unique_examples'],4)
        self.assertEqual(report['matches'],4)
        before={p:p.read_bytes() for p in self.sources.iterdir()}
        complete=run(self.manifest,self.sources,self.base/'run',provenance_root=self.base)
        self.assertTrue(complete['originals_unchanged']);self.assertFalse(complete['model_activated'])
        self.assertIsNone(complete['precision']);self.assertIsNone(complete['localization_recall'])
        self.assertEqual(len(complete['experiments']),3)
        self.assertTrue(all(r['checkpoint_reload_predictions_identical'] for r in complete['experiments']))
        self.assertTrue(all(p.read_bytes()==body for p,body in before.items()))
        with self.assertRaises(FileExistsError):run(self.manifest,self.sources,self.base/'run',provenance_root=self.base)


if __name__=='__main__':
    unittest.main()
