from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image
from prepare_pec_reference import digest, entries, existing_class_mapping
from reconcile_pec_reference_catalog import catalog_evidence, reference_specification, read_json, build


class CatalogReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.images=self.root/'images';self.images.mkdir()
        Image.new('RGB',(100,100),'white').save(self.images/'sheet-01.jpg')
        image_hash=digest(self.images/'sheet-01.jpg')
        self.annotation={'id':'annotation-1','layer':'legend','label':'Junction box','review_state':'user_reviewed',
            'geometry':{'type':'bbox','coordinates':[10,10,30,30]}}
        self.page={'id':'sheet-01','filename':'original-legend.jpg','width':100,'height':100,
            'source_sha256':image_hash,'annotations':[self.annotation]}
        self.session={'sheets':[self.page]}
        self.example={'source_annotation_id':'annotation-1','source_sheet_id':'sheet-01','source_sha256':image_hash,
            'label':'Junction box','geometry':deepcopy(self.annotation['geometry']),'role':'legend_definition'}
        self.references={'legend_catalog':[{'legend_entry':'sheet-01:L01','label':'Junction box','examples':[self.example]}]}

    def test_renamed_portable_image_resolved_by_hash_not_original_filename(self):
        result=catalog_evidence(self.references,self.session,self.images)
        self.assertEqual(len(result['eligible_entries']),1)
        self.assertEqual(result['verified_source_images']['sheet-01']['storage_filename'],'sheet-01.jpg')
        self.assertEqual(self.references['legend_catalog'][0]['examples'][0],self.example)

    def test_stale_geometry_uses_same_user_reviewed_identity_and_keeps_prior_box(self):
        original=deepcopy(self.example['geometry'])
        self.annotation['geometry']['coordinates']=[15,15,35,35]
        result=catalog_evidence(self.references,self.session,self.images)
        row=result['eligible_entries'][0]['examples'][0]
        self.assertEqual(row['export_geometry'],original)
        self.assertEqual(row['geometry'],self.annotation['geometry'])
        self.assertEqual(len(result['reconciled_geometry_examples']),1)
        self.assertEqual(self.example['geometry'],original)

    def test_deleted_excluded_pending_and_changed_class_never_auto_approved(self):
        for change,reason in [({'review_state':'deleted'},'current_deleted'),
                              ({'review_state':'corrected'},'current_corrected'),
                              ({'excluded':True},'explicitly_deleted_or_excluded'),
                              ({'label':'Pull box'},'source_annotation_identity_differs')]:
            with self.subTest(change=change):
                session=deepcopy(self.session);session['sheets'][0]['annotations'][0].update(change)
                result=catalog_evidence(self.references,session,self.images)
                self.assertEqual(result['eligible_entries'],[])
                self.assertEqual(result['excluded_examples'][0]['reason'],reason)

    def test_changed_source_wrong_dimensions_and_path_escape_fail_closed(self):
        for change in ({'source_sha256':'a'*64},{'width':99},{'filename':'../private.png'}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                session=deepcopy(self.session);session['sheets'][0].update(change)
                # Ensure the altered hash also matches the export metadata so
                # this specifically tests the source-file verification seam.
                refs=deepcopy(self.references)
                refs['legend_catalog'][0]['examples'][0]['source_sha256']=session['sheets'][0]['source_sha256']
                catalog_evidence(refs,session,self.images)

    def test_invalid_current_boxes_are_excluded_not_repaired_silently(self):
        for box in ([-1,1,10,10],[1,1,110,10],[1,1,float('nan'),10],[True,1,10,10]):
            session=deepcopy(self.session);session['sheets'][0]['annotations'][0]['geometry']['coordinates']=box
            result=catalog_evidence(self.references,session,self.images)
            self.assertEqual(result['eligible_entries'],[])
            self.assertEqual(result['excluded_examples'][0]['reason'],'legend_box_invalid')

    def test_reference_only_alias_pixels_keep_existing_rights_exclusion(self):
        folder=self.root/'references/additional';folder.mkdir(parents=True)
        Image.new('RGB',(100,100),'white').save(folder/'bdo-page-1.png')
        sha=digest(folder/'bdo-page-1.png')
        session=deepcopy(self.session);session['sheets'][0].update(id='sheet-51',source_sha256=sha)
        refs=deepcopy(self.references);refs['sheets']=[{'id':'sheet-51','image':'references/additional/bdo-page-1.png'}]
        refs['legend_catalog'][0]['examples'][0].update(source_sheet_id='sheet-51',source_sha256=sha)
        result=catalog_evidence(refs,session,self.images)
        self.assertFalse(result['verified_source_images']['sheet-51']['pixel_training_eligible'])
        refs['sheets'][0]['image']='../../private.png'
        with self.assertRaises(ValueError):catalog_evidence(refs,session,self.images)

    def test_metadata_bounds_duplicates_and_bad_source_cannot_create_output(self):
        path=self.root/'large.json';path.write_text('12345')
        with self.assertRaises(ValueError):read_json(path,4)
        refs=deepcopy(self.references);refs['legend_catalog']*=2
        with self.assertRaises(ValueError):catalog_evidence(refs,self.session,self.images)
        (self.root/'cleaned').mkdir();(self.root/'cleaned/manifest.json').write_text('{}')
        with self.assertRaises(ValueError):build(self.root/'cleaned',self.root/'parent.json',self.root/'weights.pt',
            self.root/'ref.json',self.root/'session.json',self.images,self.root/'out')
        self.assertFalse((self.root/'out').exists())


class ReferenceSpecificationTests(unittest.TestCase):
    def test_full_reference_probe_requires_all_classes_and_unchanged_labels(self):
        from types import SimpleNamespace
        from probe_symbol_detector_dev import probe_authored_synthetic
        with TemporaryDirectory() as folder:
            root=Path(folder);(root/'images/train').mkdir(parents=True);(root/'labels/train').mkdir(parents=True)
            checkpoint=root/'local.pt';checkpoint.write_bytes(b'local-fixture');rows=[]
            for index in range(54):
                name=f'authored-legend-ref-{index}';ip=root/'images/train'/f'{name}.png';lp=root/'labels/train'/f'{name}.txt'
                Image.new('RGB',(256,256),'white').save(ip);lp.write_text(f'{index} .078125 .078125 .078125 .078125')
                rows.append({'image_id':name,'class_id':index,'human_review_claim':False,
                    'image_sha256':digest(ip),'label_sha256':digest(lp),'box':[10,10,30,30]})
            names={i:f'class-{i}' for i in range(129)}
            data={'classes':[{'id':i,'label':label} for i,label in names.items()],
                'authored_legend_synthetic_images':rows,'diagnostic_only':True,
                'required_loss':'synthetic_complete_known_composite_only',
                'scope':'full_requested_reference_learning_diagnostic_not_universal_detector_release',
                'reference_specification':{'point_mappings':[{'model_class_id':i} for i in range(54)],
                    'wiring_references':[{} for _ in range(12)]}}
            (root/'manifest.json').write_text(json.dumps(data))
            model=SimpleNamespace(names=names,predict=lambda images,**kw:[SimpleNamespace(boxes=[]) for _ in images])
            with patch('probe_symbol_detector_dev.YOLO',return_value=model):
                summary=probe_authored_synthetic(root,checkpoint,root/'probe',samples_per_class=1)
            self.assertEqual(len(summary),54)
            (root/'labels/train/authored-legend-ref-0.txt').write_text('0 nan .078125 .078125 .078125')
            rows[0]['label_sha256']=digest(root/'labels/train/authored-legend-ref-0.txt')
            (root/'manifest.json').write_text(json.dumps(data))
            with self.assertRaises(ValueError):probe_authored_synthetic(root,checkpoint,root/'tampered',samples_per_class=1)
            self.assertFalse((root/'tampered').exists())
            data['authored_legend_synthetic_images']=rows[:-1]
            (root/'manifest.json').write_text(json.dumps(data))
            with self.assertRaises(ValueError):probe_authored_synthetic(root,checkpoint,root/'missing',samples_per_class=1)
            self.assertFalse((root/'missing').exists())

    def fixture(self):
        classes=[{'id':i,'label':f'original-{i}'} for i in range(80)]
        for i,label in {0:'Circuit home-run notation',11:'Smoke detector',23:'Pull box',72:'Push button',74:'Fire alarm control panel'}.items():
            classes[i]['label']=label
        rows=[]
        for row in entries():
            rows.append({**row,'glyph_id':row['region_id']+'-as_shown',
                         'mapped_model_class_ids':existing_class_mapping(row['reference_id'],classes)})
        evidence={'eligible_entries':[{'legend_entry':'drawing:J','label':'Junction box','examples':[{'source_annotation_id':'J'}]},
            {'legend_entry':'drawing:HD','label':'Addressable heat detector','examples':[]},
            {'legend_entry':'drawing:L','label':'2 x 40 watts fluorescent lamp','examples':[]},
            {'legend_entry':'drawing:S','label':'One gang device switch','examples':[]}]}
        return classes,{'references':rows},evidence

    def test_all_54_definitions_and_12_wiring_patterns_traceable_without_subtype_merge(self):
        classes,registry,evidence=self.fixture();original=deepcopy(classes)
        result=reference_specification(registry,classes,evidence)
        self.assertEqual(len(result['point_mappings']),54);self.assertEqual(len(result['wiring_references']),12)
        self.assertEqual(len(result['additions']),49);self.assertEqual(result['new_numeric_head_count'],129)
        self.assertEqual([r['id'] for r in result['additions']],list(range(80,129)))
        self.assertEqual(classes,original)
        mapping={r['reference_id']:r for r in result['point_mappings']}
        self.assertEqual(mapping['1.23']['model_class_id'],23)
        self.assertEqual(mapping['1.22']['catalog_links'][0]['legend_entry'],'drawing:J')
        for identity in ['1.20.5','1.21.1','1.36.3']:
            self.assertGreaterEqual(mapping[identity]['model_class_id'],80)
            self.assertEqual(mapping[identity]['catalog_links'],[])
        self.assertEqual(mapping['1.36.1']['model_label'],'Fire alarm - Manual [reference 1.36.1]')
        self.assertTrue(all(r['model_class_id'] is None for r in result['wiring_references']))
        self.assertTrue(all(r['project_mapping_state']=='unresolved_until_drawing_legend_review' and
                            not r['production_approval'] and not r['human_review_claim'] for r in result['point_mappings']))

    def test_missing_requested_entry_bad_parent_or_incompatible_variants_rejected(self):
        classes,registry,evidence=self.fixture()
        with self.assertRaises(ValueError):reference_specification({'references':registry['references'][:-1]},classes,evidence)
        with self.assertRaises(ValueError):reference_specification(registry,classes[:-1]+[{'id':81,'label':'wrong'}],evidence)
        extra={**registry['references'][0],'glyph_id':'second','mapped_model_class_ids':[0]}
        with self.assertRaises(ValueError):reference_specification({'references':registry['references']+[extra]},classes,evidence)


class ReferenceProbeTests(unittest.TestCase):
    def fixture(self,root):
        from prepare_pec_reference import SOURCE_SHA256
        classes,registry,evidence=ReferenceSpecificationTests().fixture()
        spec=reference_specification(registry,classes,evidence)
        classes=deepcopy(classes)+deepcopy(spec['additions'])
        expected={r['model_class_id'] for r in spec['point_mappings']}
        for row in classes:row['samples']=1 if row['id'] in expected else 0
        data={'classes':classes,'reference_specification':spec,'diagnostic_only':True,
              'scope':'full_requested_reference_learning_diagnostic_not_universal_detector_release'}
        for row in registry['references']:
            row.update(source_page_id=f"{SOURCE_SHA256}:page:{row['page_number']}",variant='as_shown',
                       bbox_source_pixels=[10,20,30,40])
        dataset=root/'data';dataset.mkdir();(dataset/'manifest.json').write_text(json.dumps(data))
        checkpoint=root/'model.pt';checkpoint.write_bytes(b'local-fixture-not-a-model')
        report={'dataset_sha256':digest(dataset/'manifest.json'),'checkpoint_sha256':digest(checkpoint),
                'full_requested_reference_diagnostic':True,'summary':[],'results':[]}
        for cls in sorted(expected):
            report['summary'].append({'class_id':cls,'tested':1,'localized':1,'localized_and_classified':1})
            report['results'].append({'image_id':f'test-{cls}','expected_class_id':cls,
                'localized':True,'localized_and_classified':True,'predictions':[{'class_id':cls}]})
        path=root/'probe.json';path.write_text(json.dumps(report))
        return dataset,checkpoint,path,data,registry,report

    def test_explicit_page_identity_variants_and_wiring_exclusion(self):
        from probe_pec_reference import reference_page_targets
        with TemporaryDirectory() as folder:
            _,_,_,data,registry,_=self.fixture(Path(folder))
            first=reference_page_targets(registry,data['reference_specification'],1)
            second=reference_page_targets(registry,data['reference_specification'],2)
            self.assertEqual(len(first)+len(second),54)
            self.assertEqual({r['reference_id'] for r in first+second},
                             {r['reference_id'] for r in data['reference_specification']['point_mappings']})
            self.assertTrue(all(r['source_page_id'].endswith(':page:1') for r in first))
            for page in (True,0,3,'1'):
                with self.assertRaises(ValueError):reference_page_targets(registry,data['reference_specification'],page)
            registry['references'].append(deepcopy(registry['references'][0]))
            with self.assertRaises(ValueError):reference_page_targets(registry,data['reference_specification'],1)

    def test_bad_reference_box_and_duplicate_meaning_rejected(self):
        from probe_pec_reference import reference_page_targets
        with TemporaryDirectory() as folder:
            _,_,_,data,registry,_=self.fixture(Path(folder))
            for box in ([1,1,float('nan'),2],[1,1,True,2],[-1,1,2,2],[2,1,1,2]):
                copy=deepcopy(registry);copy['references'][0]['bbox_source_pixels']=box
                with self.assertRaises(ValueError):reference_page_targets(copy,data['reference_specification'],1)
            spec=deepcopy(data['reference_specification']);spec['point_mappings'].append(spec['point_mappings'][0])
            with self.assertRaises(ValueError):reference_page_targets(registry,spec,1)

    def test_per_entry_coverage_retains_unsupported_metrics_and_immutable_history(self):
        from probe_pec_reference import write_coverage
        with TemporaryDirectory() as folder:
            root=Path(folder);dataset,checkpoint,path,_,_,_=self.fixture(root)
            output=root/'coverage.json';result=write_coverage(dataset,checkpoint,path,output)
            self.assertEqual(result['device_entries'],54);self.assertEqual(result['wiring_entries'],12)
            coverage=read_json(output)
            self.assertEqual(len(coverage['unsupervised_parent_class_ids']),75)
            self.assertTrue(all(r['real_page_precision'] is None and r['real_page_recall'] is None
                                and r['independent_accuracy'] is None for r in coverage['entries']))
            self.assertTrue(all(not r['included_in_point_training'] for r in coverage['wiring_references']))
            before=digest(output)
            with self.assertRaises(FileExistsError):write_coverage(dataset,checkpoint,path,output)
            self.assertEqual(digest(output),before)

    def test_coverage_rejects_wrong_hash_incomplete_or_inconsistent_results(self):
        from probe_pec_reference import write_coverage
        with TemporaryDirectory() as folder:
            root=Path(folder);dataset,checkpoint,path,_,_,report=self.fixture(root)
            cases=[]
            copy=deepcopy(report);copy['checkpoint_sha256']='0'*64;cases.append(copy)
            copy=deepcopy(report);copy['dataset_sha256']='0'*64;cases.append(copy)
            copy=deepcopy(report);copy['summary'].pop();cases.append(copy)
            copy=deepcopy(report);copy['summary'].append(copy['summary'][0]);cases.append(copy)
            copy=deepcopy(report);copy['results'][0]['localized']=False;cases.append(copy)
            copy=deepcopy(report);copy['results'].append(copy['results'][0]);cases.append(copy)
            copy=deepcopy(report);copy['summary'][0]['localized_and_classified']=0;cases.append(copy)
            for index,copy in enumerate(cases):
                path.write_text(json.dumps(copy));output=root/f'failed-{index}.json'
                with self.subTest(index=index),self.assertRaises(ValueError):write_coverage(dataset,checkpoint,path,output)
                self.assertFalse(output.exists())

    def test_changed_source_or_wrong_selected_page_fails_before_inference(self):
        from probe_pec_reference import table_probe
        with TemporaryDirectory() as folder:
            root=Path(folder);dataset,checkpoint,path,_,_,_=self.fixture(root)
            prepared=root/'prepared';prepared.mkdir();(prepared/'manifest.json').write_text('{}')
            with patch('probe_pec_reference.probe_unreviewed_image') as model:
                for page in (True,3,1):
                    output=root/f'invalid-{page}'
                    with self.assertRaises(ValueError):table_probe(dataset,checkpoint,prepared,path,output,page_number=page)
                    self.assertFalse(output.exists())
                model.assert_not_called()


if __name__=='__main__':unittest.main()
