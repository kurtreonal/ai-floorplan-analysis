"""No real source data: prove negative supervision is explicit and bounded."""
from unittest import TestCase
import torch
from app.ai.symbol_detection.partial_label_training import reviewed_background_weights, local_negative_mask, ReviewedBackgroundDetectionModel


class ReviewedBackgroundTests(TestCase):
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
