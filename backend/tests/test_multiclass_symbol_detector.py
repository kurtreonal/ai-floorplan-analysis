"""All-entry development detector contract; fixtures are not accuracy evidence."""
import json
import importlib.util
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import numpy as np

from app.ai.floor_plan_interpretation import multiclass_symbol_detector as detector
from app.ai.floor_plan_interpretation import experimental_symbol_detector as shared
from app.ai.floor_plan_interpretation.demo_cv import interpret_floor_plan_demo
from app.services.interpretation_job_configuration_service import pin_job_configuration, InterpretationConfigurationError
from app.services.processing_job_service import start_floor_plan_processing


def classes():
    return {i: (f"Fixture {i}", f"drawing:L{i}") for i in range(56)}


class MulticlassDetectorTests(TestCase):
    def test_dense_lighting_uses_bounded_native_context_without_lowering_threshold(self):
        mapping={0:('Troffer lights','drawing:L00'),1:('One gang device switch','drawing:L01'),
                 2:('Circuit home-run notation','drawing:L02'),3:('Duplex outlet','drawing:L03')}
        lamps=tuple({'class_id':0,'bbox':(10,10,20,50),'score':.8} for _ in range(8))
        contextual=({'class_id':1,'bbox':(40,40,50,60),'score':.8},)
        image=np.full((900,600,3),255,np.uint8)
        with patch.object(detector,'PROFILE','power80'),patch.object(detector,'verify_artifacts',return_value=mapping), \
                patch.object(detector,'_model'),patch.object(shared,'locate',side_effect=[(lamps,False),(contextual,False)]) as locate:
            assert detector.locate(image)==(contextual,False)
            assert locate.call_args_list[1].kwargs['catalog']['tile_size']==320
            assert locate.call_args_list[1].kwargs['catalog']['tile_stride']==160
            assert all(call.kwargs['catalog']['threshold']==.50 for call in locate.call_args_list)
        for baseline,shape in ((({'class_id':3},)*8,(900,600,3)),(lamps,(3264,3264,3))):
            with patch.object(detector,'PROFILE','power80'),patch.object(detector,'verify_artifacts',return_value=mapping), \
                    patch.object(detector,'_model'),patch.object(shared,'locate',return_value=(baseline,False)) as locate:
                assert detector.locate(np.full(shape,255,np.uint8))==(baseline,False)
                assert locate.call_count==1

    def test_overview_symbols_outside_selected_drawing_do_not_enter_editor(self):
        value=interpret_floor_plan_demo(np.full((200,200,3),255,np.uint8)).model_dump()
        value['regions'][0]['bounds']={'x':50,'y':50,'width':100,'height':100}
        from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationPayload
        payload=FloorPlanInterpretationPayload.model_validate(value)
        predictions=[{'class_id':0,'bbox':box,'score':.8,'tile_origin':(0,0)}
                     for box in ((80,80,100,100),(10,10,30,30))]
        with patch.object(detector,'PROFILE','power80'),patch.object(detector,'verify_artifacts',return_value=classes()):
            result=detector.with_proposals(payload,predictions)
        assert len(result.symbols.items)==1 and result.symbols.items[0].center.x==90

    def test_development_profile_has_explicit_rollback_and_rejects_unrecognized_values(self):
        from app.core.config import Settings
        from pydantic import ValidationError
        self.assertEqual(Settings(_env_file=None,development_symbol_profile='original56').development_symbol_profile,'original56')
        self.assertEqual(Settings(_env_file=None,development_symbol_profile='lamps80').development_symbol_profile,'lamps80')
        self.assertEqual(Settings(_env_file=None,development_symbol_profile='power80').development_symbol_profile,'power80')
        with self.assertRaises(ValidationError):Settings(_env_file=None,development_symbol_profile='unverified')
        self.assertEqual(detector.CLASS_COUNT,80 if detector.PROFILE in ('lamps80','power80') else 56)
        if detector.PROFILE in ('lamps80','power80'):
            self.assertNotEqual(detector.CHECKPOINT_SHA256,detector.LEGACY_CHECKPOINT_SHA256)

    def test_each_profile_pins_its_checkpoint_and_preserves_explicit_rollback(self):
        expected = {
            'original56': (56, detector.LEGACY_CHECKPOINT_SHA256, detector.LEGACY_DATASET_SHA256,
                           detector.LEGACY_DATASET_SHA256),
            'lamps80': (80, '867c7fb399104bf91caff1d6aad859504cc923443cb3e02fcb2b00255b2affa2',
                        '11ef819e20b120ea1bb44e08a64822f820f2f575c7c76212d5043f2b6249f527',
                        '11ef819e20b120ea1bb44e08a64822f820f2f575c7c76212d5043f2b6249f527'),
            'power80': (80, '2800866028ff65f5828b1e592542a3b09a08c15ad4ac7e657f4ade849b856aaa',
                        '7182de3a9b8616df8d01b8a204b085f95841a40d2740f2239183b8892e763c30',
                        '286ebf9ec56ffda32d39f73d04f65058c2bad9e99544de6fcc26c4005ffc5470'),
        }
        loaded = {}
        for profile, values in expected.items():
            with self.subTest(profile=profile), \
                    patch('app.core.config.get_settings', return_value=SimpleNamespace(development_symbol_profile=profile)):
                spec = importlib.util.spec_from_file_location('fixture_detector_'+profile, detector.__file__)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                loaded[profile] = module
                self.assertEqual(module.PROFILE, profile)
                self.assertEqual((module.CLASS_COUNT, module.CHECKPOINT_SHA256, module.DATASET_SHA256,
                                  module.TRAINING_DATASET_SHA256), values)
                self.assertEqual(module.PROVIDER, detector.PROVIDER)
        self.assertEqual(loaded['original56'].CHECKPOINT, detector.LEGACY_CHECKPOINT)
        self.assertEqual(loaded['original56'].DATASET, detector.LEGACY_DATASET)
        self.assertNotEqual(loaded['power80'].DATASET, loaded['lamps80'].DATASET)
        self.assertEqual(len({m.configuration_sha256() for m in loaded.values()}), 3)

    def test_configuration_fingerprint_pins_serving_and_training_manifest_separately(self):
        with patch.object(detector, 'PROFILE', 'power80'), \
                patch.object(detector, 'DATASET_SHA256', 'a'*64), \
                patch.object(detector, 'TRAINING_DATASET_SHA256', 'b'*64):
            baseline = detector.configuration_sha256()
            self.assertEqual(baseline, detector.configuration_sha256())
            with patch.object(detector, 'DATASET_SHA256', 'c'*64):
                self.assertNotEqual(detector.configuration_sha256(), baseline)
            with patch.object(detector, 'TRAINING_DATASET_SHA256', 'd'*64):
                self.assertNotEqual(detector.configuration_sha256(), baseline)
            self.assertEqual(detector.configuration_sha256(), baseline)

    def test_rollback_configuration_fingerprints_keep_legacy_hash_contract(self):
        for profile in ('original56', 'lamps80'):
            with self.subTest(profile=profile), patch.object(detector, 'PROFILE', profile):
                baseline = detector.configuration_sha256()
                with patch.object(detector, 'TRAINING_DATASET_SHA256', 'e'*64):
                    self.assertEqual(detector.configuration_sha256(), baseline)

    def test_power_proposals_use_training_provenance_and_remain_advisory(self):
        mapping = {i:(f'Fixture {i}',f'drawing:L{i}') for i in range(80)}
        mapping.update({56+i:entry for i,entry in enumerate(detector.EXTENSION_IDENTITIES)})
        proposals = [{'class_id':58, 'bbox':(10,10,30,30), 'score':.9, 'tile_origin':(0,0)}]
        with patch.object(detector, 'PROFILE', 'power80'), patch.object(detector, 'CLASS_COUNT', 80), \
                patch.object(detector, 'DATASET_SHA256', 'a'*64), \
                patch.object(detector, 'TRAINING_DATASET_SHA256', 'b'*64), \
                patch.object(detector, 'verify_artifacts', return_value=mapping):
            payload = detector.with_proposals(interpret_floor_plan_demo(np.full((100,100,3),255,dtype=np.uint8)), proposals)
        symbol = payload.symbols.items[0]
        self.assertEqual(symbol.training_legend.dataset_sha256, 'b'*64)
        self.assertNotEqual(symbol.training_legend.dataset_sha256, 'a'*64)
        self.assertEqual(symbol.mapping_state, 'unknown')
        self.assertEqual(symbol.ambiguity, 'ambiguous')
        self.assertIsNone(symbol.catalog_class_id)
        scope = ' '.join(w.message for w in payload.warnings if w.severity == 'warning').casefold()
        self.assertIn('same-source', scope)
        self.assertIn('independent', scope)
        self.assertIn('review', scope)
        self.assertIn('production', scope)
        self.assertTrue(any('not calibrated' in w.message for w in payload.warnings))
        self.assertEqual(type(payload).model_validate_json(payload.model_dump_json()), payload)

    def test_eighty_entry_candidate_uses_one_head_and_preserves_lamp_names_without_catalog_approval(self):
        mapping={i:(f'Fixture {i}',f'drawing:L{i}') for i in range(80)}
        mapping.update({56+i:entry for i,entry in enumerate(detector.EXTENSION_IDENTITIES)})
        mapping.update({62:('One gang device switch','drawing:L04'),
                        63:('Two gang device switch','drawing:L05'),
                        64:('Three gang device switch','drawing:L06')})
        calls=[]
        def predict(tiles,**kwargs):
            calls.append(kwargs)
            return [SimpleNamespace(boxes=[SimpleNamespace(xyxy=np.array([[10,20,30,40]]),
                    cls=np.array([i]),conf=np.array([.7])) for i in range(80)]) for _ in tiles]
        rgb=np.full((200,200,3),255,dtype=np.uint8)
        with patch.object(detector,'verify_artifacts',return_value=mapping), \
             patch.object(detector,'_model',return_value=SimpleNamespace(predict=predict)):
            predictions,truncated=detector.locate(rgb)
            payload=detector.with_proposals(interpret_floor_plan_demo(rgb),predictions,truncated)
        self.assertEqual(calls[0]['classes'],list(range(80)))
        symbols={s.training_legend.model_class_id:s for s in payload.symbols.items}
        self.assertEqual(set(symbols),set(range(80)))
        self.assertEqual(symbols[56].observed_label,'2 x 40 watts fluorescent lamp')
        self.assertEqual(symbols[57].observed_label,'1 x 40 watts fluorescent lamp')
        self.assertEqual(symbols[62].observed_label,'One gang device switch')
        self.assertEqual(symbols[63].training_legend.legend_entry,'drawing:L05')
        self.assertEqual(symbols[64].observed_label,'Three gang device switch')
        self.assertTrue(all(s.mapping_state=='unknown' and s.catalog_class_id is None for s in symbols.values()))
        self.assertEqual(type(payload).model_validate_json(payload.model_dump_json()),payload)

    def test_80_entry_replay_requires_original_identities_replay_and_delegated_not_production_authority(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary); parent_path=root/'parent.json'
            parent={'classes':[{'id':i,'label':f'Fixture {i}','legend_entry':f'drawing:L{i}'} for i in range(80)],
                    'reviewed_targets':[{'record_id':'retained'}],'images':[],
                    'authored_legend_synthetic_images':[],'authorized_pdf_targets':[{'record_id':'original-source'}]}
            parent_path.write_text(json.dumps(parent)); parent_hash=sha256(parent_path.read_bytes()).hexdigest()
            auth={'schema':'ved-user-authorized-development-label-preparation-v1','source_sha256':'a'*64,
                  'prepared_manifest_sha256':'b'*64,'local_development_training':True,
                  'delegated_assistant_annotation':True,'human_review_claim':False,'production_approval':False,
                  'missing_annotation_policy':'ignore_unreviewed_not_empty_background'}
            auth_path=root/'authorization.json';auth_path.write_text(json.dumps(auth))
            record={'filename':auth_path.name,'sha256':sha256(auth_path.read_bytes()).hexdigest(),
                    'source_sha256':'a'*64,'prepared_manifest_sha256':'b'*64}
            data={**parent,'class_scope':'parent60_plus_twenty_pdf_source_definitions',
                  'additional_training_authorizations':[record]}
            with patch.object(detector,'EXPANDED_PARENT_DATASET',parent_path), \
                 patch.object(detector,'EXPANDED_PARENT_SHA256',parent_hash), \
                 patch.object(detector,'DATASET',root/'manifest.json'):
                detector.validate_replay_extension(data)
                for key,value in (('diagnostic_only',True),('reviewed_targets',[]),
                                  ('additional_training_authorizations',[])):
                    with self.subTest(key=key),self.assertRaises(shared.ExperimentalDetectorUnavailable):
                        detector.validate_replay_extension({**data,key:value})
                changed=json.loads(json.dumps(data));changed['classes'][56]['label']='Smoke detector'
                with self.assertRaises(shared.ExperimentalDetectorUnavailable):detector.validate_replay_extension(changed)
                auth['production_approval']=True;auth_path.write_text(json.dumps(auth))
                changed={**data,'additional_training_authorizations':[{**record,'sha256':sha256(auth_path.read_bytes()).hexdigest()}]}
                with self.assertRaises(shared.ExperimentalDetectorUnavailable):detector.validate_replay_extension(changed)

    def test_running_scope_warning_does_not_silently_relabel_smoke_as_lamps(self):
        image=np.full((200,200,3),255,dtype=np.uint8)
        predictions=[{'class_id':20,'bbox':(10,10,30,30),'score':.7,'tile_origin':(0,0)}]
        mapping=classes();mapping[20]=('Smoke detector (new)','drawing:L20')
        with patch.object(detector,'verify_artifacts',return_value=mapping):
            payload=detector.with_proposals(interpret_floor_plan_demo(image),predictions)
        self.assertEqual(payload.symbols.items[0].observed_label,'Smoke detector (new)')
        self.assertTrue(any(w.code=='fluorescent_lamp_classes_unavailable' for w in payload.warnings))
        mapping.update({56+i:entry for i,entry in enumerate(detector.EXTENSION_IDENTITIES)})
        with patch.object(detector,'verify_artifacts',return_value=mapping):
            payload=detector.with_proposals(interpret_floor_plan_demo(image),predictions)
        self.assertFalse(any(w.code=='fluorescent_lamp_classes_unavailable' for w in payload.warnings))

    def test_nested_tile_duplicates_fuse_but_adjacent_and_different_class_marks_remain(self):
        rows=[{'class_id':56,'bbox':(400,87,408,121),'score':.99},
              {'class_id':56,'bbox':(398,86,416,122),'score':.7},
              {'class_id':56,'bbox':(417,87,425,121),'score':.8},
              {'class_id':57,'bbox':(400,87,408,121),'score':.75}]
        self.assertEqual(len(shared.fuse(rows)),4)
        fused=shared.fuse(rows,nested=True)
        self.assertEqual(len(fused),3)
        self.assertIn(rows[0],fused)
        self.assertIn(rows[2],fused)
        self.assertIn(rows[3],fused)

    def test_universal_fusion_preserves_alias_observations_not_adjacent_or_other_meanings(self):
        from copy import deepcopy
        from app.ai.floor_plan_interpretation.legend_equivalence import model_class_groups
        mapping = {0: ('Panelboard', 'drawing:L00'), 1: ('Panelboard', 'other:L01'),
                   2: ('Two gang device switch', 'drawing:L02'),
                   3: ('One gang device switch', 'drawing:L03')}
        rows = [{'class_id': cls, 'bbox': box, 'score': score, 'tile_origin': (0, 0)}
                for cls, box, score in ((0, (10, 10, 30, 30), .9), (1, (10, 10, 30, 30), .8),
                    (1, (32, 10, 52, 30), .7), (2, (10, 10, 30, 30), .6),
                    (3, (10, 10, 30, 30), .5))]
        before = deepcopy(rows)
        fused = shared.fuse(rows, nested=True, class_groups=model_class_groups(mapping))
        self.assertEqual(len(fused), 4)
        self.assertEqual(fused[0]['class_id'], 0)
        self.assertEqual(fused[0]['equivalent_observations'], (rows[1],))
        self.assertEqual(rows, before)
        with patch.object(detector, 'verify_artifacts', return_value=mapping):
            payload = detector.with_proposals(interpret_floor_plan_demo(np.full((100, 100, 3), 255, dtype=np.uint8)), fused)
        alias = next(w for w in payload.warnings if w.code == 'equivalent_legend_observations')
        score = next(w for w in payload.warnings if w.code == 'experimental_detector_score'
                     and w.entity_refs == ('symbol:symbol-0001',))
        self.assertIn('other:L01', score.message if detector.PROFILE=='power80' else alias.message)
        self.assertEqual(alias.entity_refs, ('symbol:symbol-0001',))
        self.assertTrue(all(s.catalog_class_id is None for s in payload.symbols.items))
        type(payload).model_validate_json(payload.model_dump_json())

    def test_alias_evidence_for_maximum_candidates_preserves_all_refs_within_warning_cap(self):
        mapping={0:('Panelboard','drawing:L00'),1:('Panelboard','other:L01')}
        rows=[{'class_id':0,'bbox':(10+i%20*40,10+i//20*40,30+i%20*40,30+i//20*40),
               'score':.9,'tile_origin':(0,0), 'equivalent_observations':(
                   {'class_id':1,'bbox':(10+i%20*40,10+i//20*40,30+i%20*40,30+i//20*40),
                    'score':.8,'tile_origin':(0,0)},)} for i in range(200)]
        with patch.object(detector,'verify_artifacts',return_value=mapping),patch.object(detector,'PROFILE','power80'):
            payload=detector.with_proposals(
                interpret_floor_plan_demo(np.full((450,850,3),255,dtype=np.uint8)),rows)
        markers=[w for w in payload.warnings if w.code=='equivalent_legend_observations']
        scores=[w for w in payload.warnings if w.code=='experimental_detector_score']
        self.assertEqual(len(markers),4)
        self.assertEqual(len(scores),200)
        self.assertLessEqual(len(payload.warnings),256)
        self.assertEqual(tuple(ref for w in markers for ref in w.entity_refs),
                         tuple(f'symbol:symbol-{i:04d}' for i in range(1,201)))
        self.assertTrue(all('other:L01' in w.message for w in scores))
        self.assertEqual(type(payload).model_validate_json(payload.model_dump_json()),payload)

    def test_universal_keys_do_not_infer_subtypes_or_merge_unknowns(self):
        from app.ai.floor_plan_interpretation.legend_equivalence import model_class_groups
        names = ('1 x 40 watts fluorescent lamp', '2 x 40 watts fluorescent lamp',
                 'One gang device switch', 'Two gang device switch', 'Three way device switch',
                 'Smoke detector', 'Smoke detector (new)', 'Unknown switch', 'Unknown switch')
        groups = model_class_groups({i: (name, f'drawing:L{i}') for i, name in enumerate(names)})
        self.assertEqual(len(set(groups.values())), len(names))

    def test_authored_extension_preserves_parent_and_rejects_diagnostic_or_reindexed_maps(self):
        with TemporaryDirectory() as temporary:
            parent_path=Path(temporary)/'parent.json'
            parent={'classes':[{'id':i,'label':name,'legend_entry':entry,'samples':1}
                               for i,(name,entry) in classes().items()]}
            parent_path.write_text(json.dumps(parent))
            parent_hash=sha256(parent_path.read_bytes()).hexdigest()
            data={**parent,'classes':parent['classes']+[
                {'id':56+i,'label':name,'legend_entry':entry,'samples':1}
                for i,(name,entry) in enumerate(detector.EXTENSION_IDENTITIES)],
                'class_scope':'parent56_plus_four_authored_lamp_and_outlet_definitions',
                'parent_dataset_sha256':parent_hash,'authored_source_sha256':detector.AUTHORED_SOURCE_SHA256,
                'source_approval_kind':'user_attested_source_permission','new_real_page_reviewed_targets':0,
                'synthetic_complete_background':True}
            with patch.object(detector,'LEGACY_DATASET',parent_path), \
                 patch.object(detector,'LEGACY_DATASET_SHA256',parent_hash):
                detector.validate_extension(data)
                for key,value in (('diagnostic_only',True),('authored_source_sha256','wrong'),
                                  ('synthetic_complete_background',False)):
                    with self.subTest(key=key),self.assertRaises(shared.ExperimentalDetectorUnavailable):
                        detector.validate_extension({**data,key:value})
                altered=json.loads(json.dumps(data))
                altered['classes'][0]['legend_entry']='reindexed'
                with self.assertRaises(shared.ExperimentalDetectorUnavailable):
                    detector.validate_extension(altered)
                altered=json.loads(json.dumps(data))
                altered['classes'][56]['label']='1 x 40 watts fluorescent lamp'
                with self.assertRaises(shared.ExperimentalDetectorUnavailable):
                    detector.validate_extension(altered)

    def test_four_new_classes_keep_exact_training_names_and_start_unresolved(self):
        mapping={**classes(),**{56+i:identity for i,identity in enumerate(detector.EXTENSION_IDENTITIES)}}
        predictions=[{'class_id':56+i,'bbox':(10+40*i,10,35+40*i,35),'score':.7,'tile_origin':(0,0)}
                     for i in range(4)]
        with patch.object(detector,'verify_artifacts',return_value=mapping):
            payload=detector.with_proposals(interpret_floor_plan_demo(np.full((220,220,3),255,dtype=np.uint8)),predictions)
        self.assertEqual([s.training_legend.model_class_id for s in payload.symbols.items],[56,57,58,59])
        self.assertEqual([s.training_legend.name for s in payload.symbols.items],[name for name,_ in detector.EXTENSION_IDENTITIES])
        self.assertTrue(all(s.mapping_state=='unknown' and s.catalog_class_id is None for s in payload.symbols.items))
        self.assertEqual(type(payload).model_validate_json(payload.model_dump_json()),payload)

    def test_bounded_candidate_output_stays_partial_and_reviewable(self):
        def predict(tiles, **kwargs):
            boxes = [SimpleNamespace(xyxy=np.array([[8*(i%19), 8*(i//19),
                                                     8*(i%19)+4, 8*(i//19)+4]]),
                                     cls=np.array([0]), conf=np.array([.7])) for i in range(95)]
            return [SimpleNamespace(boxes=boxes) for tile in tiles]
        rgb = np.full((256, 600, 3), 255, dtype=np.uint8)
        with patch.object(detector, "verify_artifacts", return_value=classes()), \
             patch.object(detector, "_model", return_value=SimpleNamespace(predict=predict)):
            predictions, truncated = detector.locate(rgb)
            payload = detector.with_proposals(interpret_floor_plan_demo(rgb), predictions, truncated)
        self.assertTrue(truncated)
        self.assertEqual(len(predictions), 200)
        self.assertEqual(payload.symbols.state, "partial")
        self.assertTrue(payload.symbols.truncated)
        self.assertEqual(payload.document_state, "partial")
        self.assertTrue(any(w.code == "experimental_detector_truncated" for w in payload.warnings))

    def test_second_lattice_is_target_independent_and_never_exceeds_existing_cap(self):
        standard = shared.tile_positions(1500, 2200)
        combined = shared.tile_positions(1500, 2200, dual_phase=True)
        self.assertTrue(set(standard).issubset(combined))
        self.assertIn((128, 128), combined)
        self.assertLessEqual(len(combined), shared.MAX_TILES)
        large = shared.tile_positions(3600, 3600, dual_phase=True)
        self.assertLessEqual(len(large), shared.MAX_TILES)
        self.assertEqual(large, shared.tile_positions(3600, 3600))
    def test_default_development_start_pins_one_checkpoint_for_all_pages(self):
        from app.services import processing_job_service as service
        settings = SimpleNamespace(app_env="development", local_vlm_runtime_url=None, local_vlm_model_path=None)
        outcomes = [SimpleNamespace() for _ in range(2)]
        with patch.object(service, "find_owned_floor_plan_for_update", return_value=SimpleNamespace(id=1)), \
             patch.object(service, "find_active_processing_job", return_value=None), \
             patch.object(service, "add_processing_job", return_value=SimpleNamespace(id=2, floor_plan_id=1)), \
             patch.object(service, "list_pages_for_floor_plan", return_value=[1, 2]), \
             patch.object(service, "configure_page_outcomes", return_value=outcomes), \
             patch("app.services.interpretation_release_service.current_runtime_release", return_value=None), \
             patch.object(detector, "verify_artifacts", return_value=classes()):
            start_floor_plan_processing(SimpleNamespace(), current_user=SimpleNamespace(id=3),
                                        floor_plan_id=1, settings=settings)
        self.assertEqual([o.provider for o in outcomes], [detector.PROVIDER]*2)
        self.assertTrue(all(o.configuration_sha256 == detector.configuration_sha256() for o in outcomes))

    def test_configured_or_production_runtime_is_not_overridden_by_development_weights(self):
        from app.services import processing_job_service as service
        for environment, gateway, release in (("production", None, None),
                                               ("development", "http://127.0.0.1:8081", None),
                                               ("development", None, object())):
            settings = SimpleNamespace(app_env=environment, local_vlm_runtime_url=gateway, local_vlm_model_path=None)
            outcome = SimpleNamespace(provider="existing")
            with patch.object(service, "find_owned_floor_plan_for_update", return_value=SimpleNamespace(id=1)), \
                 patch.object(service, "find_active_processing_job", return_value=None), \
                 patch.object(service, "add_processing_job", return_value=SimpleNamespace(id=2, floor_plan_id=1)), \
                 patch.object(service, "list_pages_for_floor_plan", return_value=[1]), \
                 patch.object(service, "configure_page_outcomes", return_value=[outcome]), \
                 patch("app.services.interpretation_release_service.current_runtime_release", return_value=release), \
                 patch.object(detector, "verify_artifacts") as verify:
                start_floor_plan_processing(SimpleNamespace(), current_user=SimpleNamespace(id=3),
                                            floor_plan_id=1, settings=settings)
            self.assertEqual(outcome.provider, "existing")
            verify.assert_not_called()

    def test_pinned_worker_configuration_is_development_only_and_hash_fenced(self):
        current = SimpleNamespace(provider=detector.PROVIDER, configuration_sha256=detector.configuration_sha256())
        session = SimpleNamespace(scalar=lambda *args: current)
        with patch.object(detector, "verify_artifacts", return_value=classes()), \
             patch("app.services.interpretation_job_configuration_service.current_runtime_release", return_value=None):
            self.assertIs(pin_job_configuration(session, processing_job=SimpleNamespace(id=1),
                                               settings=SimpleNamespace(app_env="development")), current)
            with self.assertRaises(InterpretationConfigurationError):
                pin_job_configuration(session, processing_job=SimpleNamespace(id=1),
                                      settings=SimpleNamespace(app_env="production"))
            current.configuration_sha256 = "altered"
            with self.assertRaises(InterpretationConfigurationError):
                pin_job_configuration(session, processing_job=SimpleNamespace(id=1),
                                      settings=SimpleNamespace(app_env="development"))

    def test_every_entry_is_inferred_and_preserved_as_unresolved_source_pixel_proposal(self):
        calls = []
        def predict(tiles, **kwargs):
            calls.append(kwargs)
            return [SimpleNamespace(boxes=[SimpleNamespace(xyxy=np.array([[10, 20, 30, 40]]),
                     cls=np.array([i]), conf=np.array([.7])) for i in range(56)]) for tile in tiles]
        rgb = np.full((300, 300, 3), 255, dtype=np.uint8)
        original = rgb.copy()
        with patch.object(detector, "verify_artifacts", return_value=classes()), \
             patch.object(detector, "_model", return_value=SimpleNamespace(predict=predict)):
            predictions, truncated = detector.locate(rgb)
            payload = detector.with_proposals(interpret_floor_plan_demo(rgb), predictions, truncated)
        self.assertEqual(calls[0]["classes"], list(range(56)))
        self.assertEqual(calls[0]["conf"], .5)
        self.assertEqual({p["class_id"] for p in predictions}, set(range(56)))
        self.assertTrue(any(p["bbox"] == (54., 64., 74., 84.) for p in predictions))
        self.assertTrue(all(s.mapping_state == "unknown" and s.catalog_class_id is None
                            for s in payload.symbols.items))
        self.assertTrue(any("Training legend drawing:L55" in w.message for w in payload.warnings))
        by_class = {s.training_legend.model_class_id: s for s in payload.symbols.items}
        self.assertEqual(set(by_class), set(range(56)))
        for class_id, (name, entry) in classes().items():
            self.assertEqual(by_class[class_id].training_legend.name, name)
            self.assertEqual(by_class[class_id].training_legend.legend_entry, entry)
            self.assertEqual(by_class[class_id].training_legend.dataset_sha256, detector.TRAINING_DATASET_SHA256)
        self.assertEqual(type(payload).model_validate_json(payload.model_dump_json()), payload)
        np.testing.assert_array_equal(rgb, original)

    def test_integrity_mapping_and_missing_class_examples_fail_closed(self):
        with TemporaryDirectory() as temporary:
            checkpoint, dataset = Path(temporary)/"weights.pt", Path(temporary)/"manifest.json"
            checkpoint.write_bytes(b"synthetic checkpoint")
            data = {"all_eligible_entries": True, "required_loss": "positive_and_reviewed_box_only",
                    "reference_rights_exclusions": {"sheet_ids": ["sheet-51", "sheet-52"]},
                    "classes": [{"id": i, "label": name, "legend_entry": key, "samples": 1}
                                for i, (name, key) in classes().items()]}
            dataset.write_text(json.dumps(data))
            with patch.object(detector, "CHECKPOINT", checkpoint), patch.object(detector, "DATASET", dataset), \
                 patch.object(detector, "CLASS_COUNT", 56), \
                 patch.object(detector, "REFINEMENT_MANIFEST", None), \
                 patch.object(detector, "CHECKPOINT_SHA256", sha256(checkpoint.read_bytes()).hexdigest()), \
                 patch.object(detector, "DATASET_SHA256", sha256(dataset.read_bytes()).hexdigest()):
                self.assertEqual(detector.verify_artifacts(), classes())
                for required_loss in ("positive_boxes_and_explicit_reviewed_background", "unreviewed_background"):
                    data["required_loss"] = required_loss
                    dataset.write_text(json.dumps(data))
                    with patch.object(detector, "DATASET_SHA256", sha256(dataset.read_bytes()).hexdigest()):
                        if required_loss == "unreviewed_background":
                            with self.assertRaisesRegex(shared.ExperimentalDetectorUnavailable, "CLASS_MAP_INVALID"):
                                detector.verify_artifacts()
                        else:
                            self.assertEqual(detector.verify_artifacts(), classes())
                data["required_loss"] = "positive_and_reviewed_box_only"
                dataset.write_text(json.dumps(data))
                checkpoint.write_bytes(b"tampered")
                with self.assertRaises(shared.ExperimentalDetectorUnavailable):
                    detector.verify_artifacts()
            checkpoint.write_bytes(b"synthetic checkpoint")
            data["classes"][55]["samples"] = 0
            dataset.write_text(json.dumps(data))
            with patch.object(detector, "CHECKPOINT", checkpoint), patch.object(detector, "DATASET", dataset), \
                 patch.object(detector, "CLASS_COUNT", 56), \
                 patch.object(detector, "CHECKPOINT_SHA256", sha256(checkpoint.read_bytes()).hexdigest()), \
                 patch.object(detector, "DATASET_SHA256", sha256(dataset.read_bytes()).hexdigest()):
                with self.assertRaisesRegex(shared.ExperimentalDetectorUnavailable, "CLASS_MAP_INVALID"):
                    detector.verify_artifacts()

    def test_unknown_or_nonfinite_model_outputs_fail_closed(self):
        model = SimpleNamespace(predict=lambda tiles, **kwargs: [SimpleNamespace(boxes=[
            SimpleNamespace(xyxy=np.array([[10, 20, 30, 40]]), cls=np.array([56]), conf=np.array([.7]))])])
        with patch.object(detector, "verify_artifacts", return_value=classes()), \
             patch.object(detector, "_model", return_value=model):
            with self.assertRaises(shared.ExperimentalDetectorUnavailable):
                detector.locate(np.full((100, 100, 3), 255, dtype=np.uint8))
        for box in ([float("nan"), 20, 30, 40], [10, 20, float("inf"), 40]):
            model = SimpleNamespace(predict=lambda tiles, **kwargs: [SimpleNamespace(boxes=[
                SimpleNamespace(xyxy=np.array([box]), cls=np.array([0]), conf=np.array([.7]))])])
            with patch.object(detector, "verify_artifacts", return_value=classes()), \
                 patch.object(detector, "_model", return_value=model):
                with self.assertRaises(shared.ExperimentalDetectorUnavailable):
                    detector.locate(np.full((100, 100, 3), 255, dtype=np.uint8))
