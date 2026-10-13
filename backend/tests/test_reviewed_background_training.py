"""No real source data: prove negative supervision is explicit and bounded."""
from unittest import TestCase
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import torch
from app.ai.symbol_detection.partial_label_training import (
    reviewed_background_weights, local_negative_mask, ReviewedBackgroundDetectionModel,
    construction_known_weights, ReviewedBackgroundTrainer, DetectionTrainer,
)


class ReviewedBackgroundTests(TestCase):
    def test_only_complete_generated_composites_supervise_outside_positive_boxes(self):
        original=torch.tensor([[1.,0.],[1.,0.],[0.,0.]])
        weights=construction_known_weights(original,[False,True,False],torch.tensor([[[1]],[[1]],[[0]]]))
        self.assertEqual(weights.tolist(),[[1.,0.],[1.,1.],[0.,0.]])
        self.assertEqual(original.tolist(),[[1.,0.],[1.,0.],[0.,0.]])
        logits=torch.zeros((3,2,2),requires_grad=True)
        (torch.nn.functional.binary_cross_entropy_with_logits(logits,torch.zeros_like(logits),reduction='none')
         *weights[...,None]).sum().backward()
        self.assertEqual(logits.grad[0,1].abs().sum().item(),0)
        self.assertGreater(logits.grad[1,1].abs().sum().item(),0)
        self.assertEqual(logits.grad[2].abs().sum().item(),0)
        self.assertIs(construction_known_weights(original,None,torch.zeros((3,0,1))),original)
        with self.assertRaises(ValueError):
            construction_known_weights(original,[True],torch.ones((3,1,1)))
        with self.assertRaises(ValueError):
            construction_known_weights(original,[True,False,False],torch.zeros((3,0,1)))

    def test_synthetic_provenance_flags_do_not_relabel_unreviewed_real_images(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary)
            data={'required_loss':'positive_boxes_and_explicit_reviewed_background',
                  'reviewed_background_images':[{'image_id':'reviewed-negative-1'}],
                  'synthetic_complete_background':True,'authored_legend_synthetic_images':[
                      {'image_id':'authored-legend-56-000','human_review_claim':False,
                       'label_origin':'known_synthetic_composite_geometry'}]}
            (root/'manifest.json').write_text(json.dumps(data))
            trainer=object.__new__(ReviewedBackgroundTrainer)
            trainer.data={'path':root}; trainer.device='cpu'
            batch={'im_file':['authored-legend-56-000.png','unreviewed-real.png','reviewed-negative-1.png']}
            with patch.object(DetectionTrainer,'preprocess_batch',return_value=batch):
                result=trainer.preprocess_batch(batch)
            self.assertEqual(result['synthetic_complete'].tolist(),[True,False,False])
            self.assertEqual(result['reviewed_background'].tolist(),[False,False,True])

    def test_real_model_empty_target_batch_has_finite_loss_and_background_gradient(self):
        from ultralytics.utils import DEFAULT_CFG
        model = ReviewedBackgroundDetectionModel('yolo11n.yaml', nc=2, ch=3, verbose=False)
        model.args = DEFAULT_CFG
        batch = {'img':torch.zeros((2,3,64,64)), 'batch_idx':torch.zeros(0),
                 'cls':torch.zeros((0,1)), 'bboxes':torch.zeros((0,4)),
                 'reviewed_background':torch.tensor([True,False])}
        loss, _ = model.loss(batch)
        self.assertTrue(torch.isfinite(loss).all())
        self.assertGreater(loss.sum().item(),0)
        loss.sum().backward()
        self.assertTrue(any(p.grad is not None and p.grad.abs().sum().item()>0 for p in model.model[-1].parameters()))

    def test_unreviewed_empty_images_have_no_background_gradient(self):
        logits = torch.zeros((2, 100, 3), requires_grad=True)
        weights = reviewed_background_weights(torch.zeros((2, 100)), [False, True], torch.zeros((2, 0, 1)))
        loss = (torch.nn.functional.binary_cross_entropy_with_logits(logits, torch.zeros_like(logits), reduction='none') * weights[..., None]).sum()
        loss.backward()
        self.assertEqual(logits.grad[0].abs().sum().item(), 0)
        self.assertGreater(logits.grad[1].sum().item(), 0)  # gradient descent reduces false scores
        self.assertAlmostEqual(weights[1].sum().item(), 32, places=4)

    def test_positive_box_supervision_unchanged_outside_stays_ignored(self):
        anchors = torch.tensor([[5., 5.], [50., 50.]])
        boxes = torch.tensor([[[0., 0., 10., 10.]]])
        valid = torch.ones((1, 1, 1))
        weights = local_negative_mask(anchors, boxes, valid, margin_pixels=0).float()
        self.assertEqual(reviewed_background_weights(weights, [False], valid).tolist(), [[1., 0.]])

    def test_conflicting_positive_and_negative_identity_fails(self):
        with self.assertRaises(ValueError):
            reviewed_background_weights(torch.zeros((1, 2)), [True], torch.ones((1, 1, 1)))
        with self.assertRaises(ValueError):
            reviewed_background_weights(torch.zeros((1, 2)), [True, False], torch.zeros((1, 0, 1)))

    def test_legacy_missing_flag_does_not_activate_negative_supervision(self):
        weights = torch.tensor([[1., 0.]])
        self.assertIs(reviewed_background_weights(weights, None, torch.zeros((1, 0, 1))), weights)

    def test_hard_mining_gives_top_32_max_class_logit_anchors_unit_mass(self):
        logits = torch.full((1,2100,3), -10.)
        # A single high class score must win even when other classes stay low.
        selected = torch.arange(2068,2100)
        logits[0,selected,1] = torch.arange(32).float() + 1
        logits.requires_grad_()
        original = torch.zeros((1,2100)); before = original.clone()
        weights = reviewed_background_weights(original, [True], torch.zeros((1,0,1)),
                                              logits=logits, hard_mining=True)
        self.assertEqual(torch.where(weights[0] > 0)[0].tolist(), selected.tolist())
        self.assertTrue(torch.equal(weights[0,selected], torch.ones(32)))
        self.assertEqual(weights.sum().item(), 32)
        self.assertFalse(weights.requires_grad)
        self.assertTrue(torch.equal(original, before))
        uniform = reviewed_background_weights(original, [True], torch.zeros((1,0,1)))
        self.assertAlmostEqual(uniform.sum().item(), 32, places=4)
        self.assertAlmostEqual(uniform[0,2099].item(), 32/2100, places=7)

    def test_hard_mining_gradients_ignore_unknowns_and_unreviewed_positive_exteriors(self):
        original = torch.zeros((3,64)); original[1,:2] = 1
        valid = torch.tensor([[[0]], [[1]], [[0]]])
        logits = torch.arange(64).float().view(1,64,1).expand(3,64,2).clone().requires_grad_()
        weights = reviewed_background_weights(original, [True,False,False], valid,
                                              logits=logits, hard_mining=True)
        targets = torch.zeros_like(logits); targets[1,:2,0] = 1
        loss = (torch.nn.functional.binary_cross_entropy_with_logits(logits, targets, reduction='none')
                * weights[...,None]).sum()
        loss.backward()
        self.assertEqual(logits.grad[0,:32].abs().sum().item(), 0)
        self.assertGreater(logits.grad[0,32:].abs().sum().item(), 0)
        self.assertGreater(logits.grad[1,:2].abs().sum().item(), 0)
        self.assertEqual(logits.grad[1,2:].abs().sum().item(), 0)
        self.assertEqual(logits.grad[2].abs().sum().item(), 0)
        self.assertTrue(torch.equal(weights[1:], original[1:]))
        self.assertTrue(torch.isfinite(loss))

    def test_hard_mining_budget_handles_fewer_than_32_anchors(self):
        for anchors in (1,7,32,33):
            with self.subTest(anchors=anchors):
                logits = torch.zeros((1,anchors,2))
                weights = reviewed_background_weights(torch.zeros((1,anchors)), [True],
                    torch.zeros((1,0,1)), logits=logits, hard_mining=True)
                self.assertEqual(weights.sum().item(), min(32,anchors))
                self.assertTrue(((weights == 0) | (weights == 1)).all())

    def test_hard_mining_requires_matching_finite_logits_and_explicit_negative_flags(self):
        original = torch.tensor([[1.,0.]])
        valid = torch.zeros((1,0,1))
        logits = torch.zeros((1,2,3))
        self.assertIs(reviewed_background_weights(original, None, valid, logits=logits,
                                                  hard_mining=True), original)
        self.assertTrue(torch.equal(reviewed_background_weights(original, [False], valid,
                                   logits=logits, hard_mining=True), original))
        for bad in (None, torch.zeros((2,2,3)), torch.zeros((1,3,3)), torch.zeros((1,2)),
                    torch.full((1,2,3), float('nan')), torch.full((1,2,3), float('inf'))):
            with self.subTest(logits_shape=None if bad is None else tuple(bad.shape)), self.assertRaises(ValueError):
                reviewed_background_weights(torch.zeros((1,2)), [True], valid, logits=bad, hard_mining=True)
        with self.assertRaises(ValueError):
            reviewed_background_weights(torch.zeros((1,2)), [True], torch.ones((1,1,1)),
                                        logits=logits, hard_mining=True)
        with self.assertRaises(ValueError):
            reviewed_background_weights(torch.zeros((1,2)), [True,False], valid,
                                        logits=logits, hard_mining=True)

    def test_legacy_uniform_mode_ignores_logits_and_keeps_existing_budget(self):
        weights = torch.zeros((1,64))
        actual = reviewed_background_weights(weights, [True], torch.zeros((1,0,1)),
                                             logits=torch.full((1,64,2),float('nan')))
        self.assertTrue(torch.equal(actual, torch.full_like(weights, .5)))

    def test_trainer_sampling_choice_defaults_uniform_and_rejects_unknown_modes(self):
        for mode in (None, 'uniform_budget', 'top_score_anchors', 'all_unlabeled_background'):
            with self.subTest(mode=mode), TemporaryDirectory() as folder:
                root = Path(folder)
                manifest = {'required_loss':'positive_boxes_and_explicit_reviewed_background',
                            'reviewed_background_images':[{'image_id':'reviewed-negative'}]}
                if mode is not None: manifest['reviewed_background_sampling'] = mode
                (root / 'manifest.json').write_text(json.dumps(manifest))
                trainer = object.__new__(ReviewedBackgroundTrainer)
                trainer.data = {'path':root}; trainer.device = 'cpu'
                batch = {'im_file':['reviewed-negative.png','unknown-empty.png','positive.png']}
                with patch.object(DetectionTrainer,'preprocess_batch',return_value=batch):
                    if mode == 'all_unlabeled_background':
                        with self.assertRaises(ValueError): trainer.preprocess_batch(batch)
                    else:
                        result = trainer.preprocess_batch(batch)
                        self.assertEqual(result['reviewed_background_sampling'], mode or 'uniform_budget')
                        self.assertEqual(result['reviewed_background'].tolist(), [True,False,False])
                        self.assertEqual(result['synthetic_complete'].tolist(), [False,False,False])
