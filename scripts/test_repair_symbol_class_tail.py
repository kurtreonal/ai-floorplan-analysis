"""Frozen-row repair invariants using synthetic tensors, never real checkpoints."""
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import hashlib
import json

import numpy as np
from PIL import Image
import torch
from torch import nn
from torch.nn import functional as F

from repair_symbol_class_tail import FrozenClassTailRepair, native_context_windows, fit_reviewed_contrast
from app.ai.symbol_detection.partial_label_training import reviewed_background_weights, reviewed_region_weights


class FakeDetect(nn.Module):
    def __init__(self, nc=80):
        super().__init__()
        self.nc = nc
        self.end2end = False
        self.cv3 = nn.ModuleList([
            nn.Sequential(nn.Conv2d(80, 80, 1), nn.BatchNorm2d(80), nn.Conv2d(80, nc, 1))
            for _ in range(3)
        ])
        self.cv2 = nn.ModuleList([nn.Conv2d(80, 4, 1) for _ in range(3)])

    def forward(self, pixels):
        feats = [F.adaptive_avg_pool2d(pixels, size) for size in (4, 2, 1)]
        return {'scores': torch.cat([branch(f).flatten(2) for branch, f in zip(self.cv3, feats)], 2),
                'boxes': torch.cat([branch(f).flatten(2) for branch, f in zip(self.cv2, feats)], 2),
                'feats': feats}


class FakeModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.model = nn.ModuleList([
            nn.Sequential(nn.Conv2d(3, 80, 1), nn.BatchNorm2d(80)), FakeDetect()
        ])

    def forward(self, pixels):
        return self.model[-1](self.model[0](F.adaptive_avg_pool2d(pixels, 8)))


class FrozenClassTailRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_threads = torch.get_num_threads()
        torch.set_num_threads(1)

    @classmethod
    def tearDownClass(cls):
        torch.set_num_threads(cls.original_threads)

    def test_selected_row_updates_with_all_other_weights_and_bn_state_exact(self):
        torch.manual_seed(0)
        model = FakeModel()
        before = {name: value.clone() for name, value in model.state_dict().items()}
        repair = FrozenClassTailRepair(model, 58)
        self.assertEqual(sum(p.numel() for p in repair.parameters()), 243)
        self.assertTrue(all(p.requires_grad for p in repair.parameters()))
        self.assertTrue(all(not p.requires_grad for p in model.parameters()))
        cached = repair.cache(torch.full((2, 3, 320, 320), .5))
        raw_scores = cached['scores'].clone()
        self.assertTrue(all(not module.training for module in model.modules()))
        optimizer = torch.optim.SGD(repair.parameters(), lr=.01)
        predictions = repair.predictions(cached)
        F.binary_cross_entropy_with_logits(predictions['scores'][:, 58],
                                          torch.zeros_like(predictions['scores'][:, 58])).backward()
        self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all()
                            for p in repair.parameters()))
        self.assertTrue(all(p.grad is None for p in model.parameters()))
        optimizer.step()
        predictions = repair.predictions(cached)
        mask = torch.arange(80) != 58
        self.assertTrue(torch.equal(predictions['scores'][:, mask], raw_scores[:, mask]))
        self.assertFalse(torch.equal(predictions['scores'][:, 58], raw_scores[:, 58]))
        self.assertTrue(torch.equal(cached['scores'], raw_scores))
        result = repair.apply()
        self.assertEqual(result['updated_class'], 58)
        self.assertEqual(result['trainable_scalars'], 243)
        self.assertTrue(result['other_state_exact'])
        self.assertEqual(result['protected_state_entries'], len(before))
        selected = {name + suffix for name in repair.tail_names for suffix in ('.weight', '.bias')}
        for name, value in model.state_dict().items():
            with self.subTest(state=name):
                if name in selected:
                    self.assertTrue(torch.equal(value[mask], before[name][mask]))
                else:
                    self.assertTrue(torch.equal(value, before[name]))
        for name in repair.tail_names:
            self.assertFalse(torch.equal(model.state_dict()[name+'.bias'][58], before[name+'.bias'][58]))

    def test_apply_rejects_external_frozen_state_change(self):
        model = FakeModel()
        repair = FrozenClassTailRepair(model, 58)
        with torch.no_grad():
            model.model[0][1].running_mean[0] += 1
        with self.assertRaisesRegex(ValueError, 'Frozen state changed'):
            repair.apply()

    def test_invalid_class_and_head_contracts_fail_before_update(self):
        for class_id in (-1, 80, True, '58', 58.0):
            with self.subTest(class_id=class_id), self.assertRaises(ValueError):
                FrozenClassTailRepair(FakeModel(), class_id)
        for kind in ('end2end', 'two_tails', 'wrong_classes', 'large_kernel', 'groups', 'no_bias', 'nonconv'):
            model = FakeModel(); head = model.model[-1]
            if kind == 'end2end': head.end2end = True
            elif kind == 'two_tails': head.cv3 = nn.ModuleList(list(head.cv3)[:2])
            elif kind == 'wrong_classes': head.cv3[0][-1] = nn.Conv2d(80, 79, 1)
            elif kind == 'large_kernel': head.cv3[0][-1] = nn.Conv2d(80, 80, 3)
            elif kind == 'groups': head.cv3[0][-1] = nn.Conv2d(80, 80, 1, groups=2)
            elif kind == 'no_bias': head.cv3[0][-1] = nn.Conv2d(80, 80, 1, bias=False)
            else: head.cv3[0][-1] = nn.Identity()
            with self.subTest(head=kind), self.assertRaises(ValueError):
                FrozenClassTailRepair(model, 58)

    def test_cache_rejects_invalid_shape_batch_range_and_nonfinite_pixels(self):
        repair = FrozenClassTailRepair(FakeModel(), 58)
        for shape in ((3,320,320), (1,1,320,320), (1,3,319,320), (0,3,320,320), (9,3,320,320)):
            with self.subTest(shape=shape), self.assertRaises(ValueError):
                repair.cache(torch.zeros(shape))
        for value in (-.01, 1.01, float('nan'), float('inf')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                repair.cache(torch.full((1,3,320,320), value))
        for value in (0., 1.):
            with self.subTest(boundary=value):
                cached = repair.cache(torch.full((1,3,320,320), value))
                self.assertEqual(cached['scores'].shape, (1,80,21))
                self.assertTrue(torch.isfinite(cached['scores']).all())

    def test_cache_failure_removes_hooks_and_restores_eval_without_bn_drift(self):
        model = FakeModel(); repair = FrozenClassTailRepair(model, 58)
        before = {name: value.clone() for name, value in model.state_dict().items()}
        original_forward = model.forward
        model.forward = lambda images: (_ for _ in ()).throw(RuntimeError('synthetic failure'))
        with self.assertRaisesRegex(RuntimeError, 'synthetic failure'):
            repair.cache(torch.zeros((1,3,320,320)))
        self.assertFalse(repair.head.training)
        self.assertTrue(all(not tail._forward_pre_hooks for tail in repair.tails))
        self.assertTrue(all(torch.equal(before[k], v) for k, v in model.state_dict().items()))
        model.forward = original_forward
        cached = repair.cache(torch.zeros((1,3,320,320)))
        self.assertEqual(len(cached['tail_features']), 3)

    def test_cache_rejects_unexpected_raw_class_output_and_releases_hooks(self):
        model = FakeModel(); repair = FrozenClassTailRepair(model, 58)
        forward = model.forward

        def wrong_classes(images):
            output = forward(images)
            return {**output, 'scores': output['scores'][:, :79]}

        model.forward = wrong_classes
        with self.assertRaisesRegex(ValueError, 'Unexpected raw detection output'):
            repair.cache(torch.zeros((1,3,320,320)))
        self.assertFalse(repair.head.training)
        self.assertTrue(all(not tail._forward_pre_hooks for tail in repair.tails))

    def test_selected_class_mining_uses_32_anchors_and_unknown_images_have_zero_gradient(self):
        logits = torch.full((3,64,80), -10.)
        logits[:, :32, 0] = 100
        logits[:, 32:, 58] = torch.arange(32).float() + 1
        logits.requires_grad_()
        original = torch.zeros((3,64)); original[1,:2] = 1
        mask_gt = torch.tensor([[[0]], [[1]], [[0]]])
        weights = reviewed_background_weights(original, [True,False,False], mask_gt,
                                               logits=logits, hard_mining=True, mining_class=58)
        self.assertEqual(torch.where(weights[0] > 0)[0].tolist(), list(range(32,64)))
        self.assertEqual(weights[0].sum().item(), 32)
        self.assertFalse(weights.requires_grad)
        self.assertTrue(torch.equal(weights[1:], original[1:]))
        loss = (F.binary_cross_entropy_with_logits(logits, torch.zeros_like(logits), reduction='none')
                * weights[..., None]).sum()
        self.assertTrue(torch.isfinite(loss))
        loss.backward()
        self.assertEqual(logits.grad[2].abs().sum().item(), 0)
        self.assertEqual(logits.grad[1,2:].abs().sum().item(), 0)
        self.assertEqual(logits.grad[0,:32].abs().sum().item(), 0)
        self.assertGreater(logits.grad[0,32:,58].abs().sum().item(), 0)
        defaults = reviewed_background_weights(original, [True,False,False], mask_gt,
                                               logits=logits, hard_mining=True)
        self.assertEqual(torch.where(defaults[0] > 0)[0].tolist(), list(range(32)))
        self.assertTrue(torch.equal(original[0], torch.zeros(64)))

    def test_class_mining_rejects_invalid_class_or_nonfinite_reviewed_logits(self):
        weights = torch.zeros((1,64)); valid = torch.zeros((1,0,1))
        logits = torch.zeros((1,64,80))
        for class_id in (-1,80,True,'58',58.0):
            with self.subTest(class_id=class_id), self.assertRaises(ValueError):
                reviewed_background_weights(weights, [True], valid, logits=logits,
                                            hard_mining=True, mining_class=class_id)
        for value in (float('nan'), float('inf')):
            broken = logits.clone(); broken[0,0,58] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                reviewed_background_weights(weights, [True], valid, logits=broken,
                                            hard_mining=True, mining_class=58)

    def test_reloaded_protected_state_verification_detects_dtype_or_other_row_changes(self):
        model = FakeModel(); repair = FrozenClassTailRepair(model, 58)
        with torch.no_grad():
            repair.biases[0].add_(.1)
        repair.apply()
        reloaded = deepcopy(model)
        repair.verify_protected(reloaded)
        with torch.no_grad():
            reloaded.model[-1].cv3[0][-1].bias[57] += .1
        with self.assertRaisesRegex(ValueError, 'Frozen state changed'):
            repair.verify_protected(reloaded)
        with self.assertRaisesRegex(ValueError, 'Frozen state changed'):
            repair.verify_protected(deepcopy(model).half())
        reloaded = deepcopy(model); reloaded.register_buffer('unexpected_state', torch.zeros(1))
        with self.assertRaisesRegex(ValueError, 'Frozen state keys changed'):
            repair.verify_protected(reloaded)

    def test_region_mining_limits_gradient_to_known_rectangles_and_retains_positive_weights(self):
        anchors = torch.stack((torch.arange(64).float()+.5, torch.ones(64)), 1)
        logits = torch.zeros((2,64,80), requires_grad=True)
        with torch.no_grad():
            logits[0,:,58] = torch.arange(64).float()
        weights = torch.zeros((2,64)); weights[1,60] = 1
        regions = [[[0,0,40,2], [0,0,0,0]], [[0,0,0,0], [0,0,0,0]]]
        selected = reviewed_region_weights(weights, anchors, regions, logits=logits, mining_class=58)
        self.assertEqual(torch.where(selected[0] > 0)[0].tolist(), list(range(8,40)))
        self.assertEqual(selected[0].sum().item(), 32)
        self.assertTrue(torch.equal(selected[1], weights[1]))
        self.assertFalse(selected.requires_grad)
        loss = (F.binary_cross_entropy_with_logits(logits, torch.zeros_like(logits), reduction='none')
                * selected[...,None]).sum()
        loss.backward()
        self.assertEqual(logits.grad[0,40:].abs().sum().item(), 0)
        self.assertEqual(logits.grad[0,:8].abs().sum().item(), 0)
        self.assertGreater(logits.grad[0,8:40,58].abs().sum().item(), 0)
        self.assertEqual(logits.grad[1,:60].abs().sum().item(), 0)
        self.assertEqual(logits.grad[1,61:].abs().sum().item(), 0)
        self.assertTrue(torch.equal(weights[0], torch.zeros(64)))

    def test_region_mining_empty_padding_and_small_known_regions_do_not_select_unknowns(self):
        weights = torch.zeros((1,4)); anchors = torch.tensor([[1.,1.],[3.,1.],[5.,1.],[7.,1.]])
        logits = torch.zeros((1,4,80))
        self.assertIs(reviewed_region_weights(weights, anchors, None, logits=logits, mining_class=58), weights)
        for regions in ([[]], [[[0,0,0,0]]]):
            with self.subTest(regions=regions):
                if regions == [[]]:
                    regions = torch.zeros((1,0,4))
                self.assertEqual(reviewed_region_weights(weights, anchors, regions,
                                 logits=logits, mining_class=58).sum().item(), 0)
        result = reviewed_region_weights(weights, anchors, [[[0,0,4,2]]], logits=logits, mining_class=58)
        self.assertEqual(result.tolist(), [[1.,1.,0.,0.]])

    def test_region_mining_invalid_masks_and_classes_fail_closed(self):
        weights = torch.zeros((1,4)); anchors = torch.tensor([[1.,1.],[3.,1.],[5.,1.],[7.,1.]])
        logits = torch.zeros((1,4,80))
        for regions in (torch.zeros((2,1,4)), torch.zeros((1,17,4)),
                        [[[-1,0,4,2]]], [[[0,0,0,2]]], [[[4,0,2,2]]],
                        [[[0,0,float('nan'),2]]], [[[0,0,4,float('inf')]]]):
            with self.subTest(regions=regions), self.assertRaises(ValueError):
                reviewed_region_weights(weights, anchors, regions, logits=logits, mining_class=58)
        for class_id in (-1,80,True,'58'):
            with self.subTest(class_id=class_id), self.assertRaises(ValueError):
                reviewed_region_weights(weights, anchors, [[[0,0,4,2]]], logits=logits, mining_class=class_id)

    def test_region_mining_rejects_nonfinite_reviewed_logits(self):
        weights = torch.zeros((1,4)); anchors = torch.tensor([[1.,1.],[3.,1.],[5.,1.],[7.,1.]])
        for value in (float('nan'), float('inf')):
            logits = torch.zeros((1,4,80)); logits[0,0,58] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                reviewed_region_weights(weights, anchors, [[[0,0,4,2]]], logits=logits, mining_class=58)

    def test_region_mining_rejects_mismatched_dimensions_and_nonfinite_anchors(self):
        weights = torch.zeros((1,4)); anchors = torch.tensor([[1.,1.],[3.,1.],[5.,1.],[7.,1.]])
        logits = torch.zeros((1,4,80)); regions = [[[0,0,4,2]]]
        for bad in (torch.zeros((4,)), torch.zeros((3,2)), torch.zeros((4,3)),
                    torch.full((4,2), float('nan')), torch.full((4,2), float('inf'))):
            with self.subTest(anchors=tuple(bad.shape)), self.assertRaises(ValueError):
                reviewed_region_weights(weights, bad, regions, logits=logits, mining_class=58)
        for bad in (torch.zeros((4,80)), torch.zeros((2,4,80)), torch.zeros((1,3,80)),
                    torch.zeros((1,4,0))):
            with self.subTest(logits=tuple(bad.shape)), self.assertRaises(ValueError):
                reviewed_region_weights(weights, anchors, regions, logits=bad, mining_class=58)

    def test_region_mining_respects_explicit_image_bounds_and_exact_boundary(self):
        weights = torch.zeros((1,4)); anchors = torch.tensor([[1.,1.],[3.,1.],[5.,1.],[7.,1.]])
        logits = torch.zeros((1,4,80))
        for bounds in ((0,320), (-1,320), (320,10001), (True,320), (320.,320), (320,)):
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                reviewed_region_weights(weights, anchors, [[[0,0,4,2]]], logits=logits,
                                        mining_class=58, image_size=bounds)
        for region in ([[0,0,321,2]], [[0,0,4,321]]):
            with self.subTest(region=region), self.assertRaises(ValueError):
                reviewed_region_weights(weights, anchors, [region], logits=logits, mining_class=58)
        result = reviewed_region_weights(weights, anchors, [[[0,0,8,2]]], logits=logits,
                                         mining_class=58, image_size=(8,2))
        self.assertEqual(result.tolist(), [[1.,1.,1.,1.]])
        with self.assertRaises(ValueError):
            reviewed_region_weights(weights, anchors, [[[0,0,9,2]]], logits=logits,
                                    mining_class=58, image_size=(8,2))

    def test_native_context_uses_actual_lattice_pixels_and_transformed_inspected_masks(self):
        from test_power_quality_replay import PowerQualityReplayTests, snapshot
        from prepare_power_quality_replay import prepare
        from app.ai.floor_plan_interpretation.experimental_symbol_detector import tile_positions

        with TemporaryDirectory() as folder:
            root = Path(folder); fixture = PowerQualityReplayTests()
            paths = fixture.disk_fixture(root); prepare(*paths)
            revision = fixture.background_revision(root, paths)
            data = json.loads((paths[-1] / 'manifest.json').read_text())
            evidence = json.loads(revision[2].read_text())
            before = snapshot(paths[1])
            rows = native_context_windows(paths[1], data, evidence)
            self.assertEqual(snapshot(paths[1]), before)
            with Image.open(paths[1] / 'power.png') as image:
                expected = []
                for x,y in tile_positions(image.width,image.height,dual_phase=True):
                    a,b,c,d = evidence['background_regions'][0]['box']
                    box = [max(a,x),max(b,y),min(c,x+256),min(d,y+256)]
                    if box[2]-box[0] >= 8 and box[3]-box[1] >= 8:
                        expected.append(([x,y], [(box[0]-x)*1.25,(box[1]-y)*1.25,
                                                 (box[2]-x)*1.25,(box[3]-y)*1.25]))
                self.assertEqual([(r['source_origin'],r['negative_regions_training_pixels'][0]) for r in rows], expected)
                for row in rows:
                    x,y = row['source_origin']
                    with image.crop((x,y,x+256,y+256)) as crop:
                        np.testing.assert_array_equal(row['pixels'], np.array(crop.convert('RGB')))
                    self.assertEqual(row['pixel_sha256'], hashlib.sha256(row['pixels'].tobytes()).hexdigest())
                    self.assertFalse(row['human_review_claim'])
                    self.assertFalse(row['independent_example'])
            with patch('app.ai.floor_plan_interpretation.experimental_symbol_detector.tile_positions', return_value=[(600,600)]):
                with self.assertRaisesRegex(ValueError, 'bounded diagnostic'):
                    native_context_windows(paths[1], data, evidence)
            with patch('app.ai.floor_plan_interpretation.experimental_symbol_detector.tile_positions', return_value=[(0,300)]*33):
                with self.assertRaisesRegex(ValueError, 'bounded diagnostic'):
                    native_context_windows(paths[1], data, evidence)
            positive_evidence = json.loads(paths[2].read_text())
            with self.assertRaisesRegex(ValueError, 'negative-only'):
                native_context_windows(paths[1], data, positive_evidence)

    def test_native_positive_controls_preserve_source_bound_class_and_original_boxes(self):
        from test_power_quality_replay import PowerQualityReplayTests, snapshot
        from prepare_power_quality_replay import prepare
        from app.ai.floor_plan_interpretation.experimental_symbol_detector import tile_positions

        with TemporaryDirectory() as folder:
            root = Path(folder); fixture = PowerQualityReplayTests()
            paths = fixture.disk_fixture(root); prepare(*paths)
            revision = fixture.background_revision(root, paths)
            data = json.loads((paths[-1] / 'manifest.json').read_text())
            evidence = json.loads(revision[2].read_text())
            target = data['power_source_targets'][0]
            adjacent = {**deepcopy(target), 'record_id': 'adjacentOutlet', 'source_box': [380,415,415,445]}
            other_class = {**deepcopy(target), 'record_id': 'otherClass', 'class_id': 57,
                           'source_box': [380,450,415,480]}
            foreign_crop = {**deepcopy(target), 'record_id': 'foreignCrop', 'source_sha256': 'f'*64,
                            'source_box': [100,100,130,130]}
            foreign_pdf = {**deepcopy(target), 'record_id': 'foreignPDF', 'pdf_sha256': 'e'*64,
                           'source_box': [140,100,170,130]}
            data['power_source_targets'].extend([adjacent,other_class,foreign_crop,foreign_pdf])
            before_data, before_evidence, before_source = deepcopy(data), deepcopy(evidence), snapshot(paths[1])
            rows = native_context_windows(paths[1], data, evidence, positive_controls=True)
            self.assertEqual(data, before_data)
            self.assertEqual(evidence, before_evidence)
            self.assertEqual(snapshot(paths[1]), before_source)
            expected = {t['record_id']: t for t in (target,adjacent)}
            self.assertEqual({r for row in rows for r in row['supervised_records']}, set(expected))
            self.assertLessEqual(len(rows), 32)
            self.assertEqual(len({row['image_id'] for row in rows}), len(rows))
            positions = tile_positions(800,800,dual_phase=True)
            for record_id, original in expected.items():
                a,b,c,d = original['source_box']
                contained = [(x,y) for x,y in positions if x<=a<c<=x+256 and y<=b<d<=y+256]
                contained.sort(key=lambda p: (-min(a-p[0],b-p[1],p[0]+256-c,p[1]+256-d),p))
                actual_origins = {tuple(row['source_origin']) for row in rows if record_id in row['supervised_records']}
                self.assertTrue(set(contained[:2]).issubset(actual_origins))
            for row in rows:
                self.assertEqual(len(row['labels']), len(row['supervised_records']))
                x,y = row['source_origin']
                for label, record_id in zip(row['labels'], row['supervised_records']):
                    cls,cx,cy,width,height = label
                    self.assertEqual(cls, 58)
                    self.assertEqual(expected[record_id]['class_id'], cls)
                    recovered = [x+(cx-width/2)*256,y+(cy-height/2)*256,
                                 x+(cx+width/2)*256,y+(cy+height/2)*256]
                    np.testing.assert_allclose(recovered, expected[record_id]['source_box'], atol=1e-10)
                self.assertFalse(row['human_review_claim'])
                self.assertFalse(row['independent_example'])
            default = native_context_windows(paths[1], data, evidence)
            self.assertTrue(all('labels' not in row and 'supervised_records' not in row for row in default))

    def contrast_fixture(self):
        model = FakeModel(); model.stride = torch.tensor([80.,160.,320.])
        with torch.no_grad():
            for branch in model.model[-1].cv3:
                branch[-1].weight[58].zero_()
                branch[-1].bias[58] = -1
        repair = FrozenClassTailRepair(model, 58)
        cached = repair.cache(torch.zeros((1,3,320,320)))
        cached['feats'] = [torch.zeros_like(f) for f in cached['feats']]
        # A negative and positive have distinct synthetic features. Every other
        # anchor is unknown, even though its features are much larger.
        features = [torch.zeros_like(f) for f in cached['tail_features']]
        features[0][:,0] = 100
        features[0][0,0,0,0] = 2
        features[0][0,0,0,1] = -2
        cached['tail_features'] = features
        positive = torch.zeros((1,21), dtype=torch.bool); positive[0,1] = True
        batch = {'reviewed_negative_regions': [[[0,0,70,70]]],
                 'preserve_reviewed_positive': positive}
        return repair, cached, batch

    def test_contrast_solve_uses_only_reviewed_anchors_and_preserves_other_state(self):
        repair, cached, batch = self.contrast_fixture()
        baseline = repair.predictions(cached)['scores'].clone()
        cached_before = {k: ([t.clone() for t in v] if isinstance(v,list) else v.clone())
                         for k,v in cached.items()}
        batch_before = deepcopy(batch)
        parameters_before = [p.detach().clone() for p in repair.parameters()]
        statistics = fit_reviewed_contrast(repair, [(cached,batch)])
        self.assertEqual(len(statistics), 1)
        self.assertEqual(statistics[0]['level'], 0)
        self.assertEqual(statistics[0]['positive_anchors'], 1)
        self.assertEqual(statistics[0]['negative_anchors'], 1)
        self.assertLessEqual(statistics[0]['max_parameter_delta'], 1)
        after = repair.predictions(cached)['scores']
        self.assertLess(after[0,58,0].item(), baseline[0,58,0].item())
        self.assertLess(abs(after[0,58,1].item()-baseline[0,58,1].item()), .1)
        mask = torch.arange(80) != 58
        self.assertTrue(torch.equal(after[:,mask], baseline[:,mask]))
        for index, (before,current) in enumerate(zip(parameters_before,repair.parameters())):
            self.assertTrue(torch.isfinite(current).all())
            self.assertLessEqual((current.detach()-before).abs().max().item(), 1)
            if index not in (0,3):
                self.assertTrue(torch.equal(current, before))
        self.assertTrue(repair.apply()['other_state_exact'])
        self.assertEqual(batch['reviewed_negative_regions'], batch_before['reviewed_negative_regions'])
        self.assertTrue(torch.equal(batch['preserve_reviewed_positive'], batch_before['preserve_reviewed_positive']))
        for key, original in cached_before.items():
            current = cached[key]
            if isinstance(original,list):
                self.assertTrue(all(torch.equal(a,b) for a,b in zip(original,current)))
            else:
                self.assertTrue(torch.equal(original,current))

    def test_contrast_solve_rejects_no_known_false_anchors_without_parameter_changes(self):
        for reason in ('no_known_region', 'below_false_score_floor'):
            with self.subTest(reason=reason):
                repair, cached, batch = self.contrast_fixture()
                if reason == 'no_known_region':
                    batch['reviewed_negative_regions'] = [[[0,0,0,0]]]
                else:
                    cached['scores'][0,58,0] = -3
                before = [p.detach().clone() for p in repair.parameters()]
                with self.assertRaisesRegex(ValueError, 'No reproduced inspected false anchors'):
                    fit_reviewed_contrast(repair, [(cached,batch)])
                self.assertTrue(all(torch.equal(a,b) for a,b in zip(before,repair.parameters())))


if __name__ == '__main__':
    unittest.main()
