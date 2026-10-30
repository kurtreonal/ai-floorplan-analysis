"""Synthetic loss fixtures, not accuracy claims or private drawing labels."""
import json
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

import pytest
import torch
from torch.nn import functional as F
from ultralytics.models.yolo.detect.train import DetectionTrainer
from ultralytics.utils import DEFAULT_CFG

from app.ai.symbol_detection.reviewed_set_training import (
    LOSS_CONTRACT, allowed_target_masks, set_classification_loss,
    ReviewedSetDetectionModel, ReviewedSetTrainer,
    AllowedSetAssigner,
    reviewed_transform_pipeline,
)


def fixture(logits):
    return dict(logits=logits, targets=torch.tensor([[[1., 0., 0.], [0., 0., 0.]]]),
                allowed=torch.tensor([[[True, True, False]]]),
                boxes=torch.tensor([[[0., 0., 10., 10.]]]),
                labels=torch.tensor([[[0.]]]), anchor_pixels=torch.tensor([[5., 5.], [50., 50.]]),
                foreground=torch.tensor([[True, False]]), assigned_gt=torch.tensor([[0, 0]]))


def test_ambiguous_alternative_is_not_forced_to_representative():
    logits = torch.tensor([[[-10., 10., -10.], [0., 0., 0.]]], requires_grad=True)
    loss = set_classification_loss(**fixture(logits))
    assert loss[0, 0].sum() < .001
    loss[0, 0].sum().backward()
    assert logits.grad[0, 0, 1] <= 0  # Never punish the supported alternative.
    assert logits.grad[0, 1].abs().sum() == 0  # Exterior remains caller-masked.


def test_both_allowed_logits_can_receive_positive_localization_association_gradient():
    logits = torch.full((1, 2, 3), -5., requires_grad=True)
    loss = set_classification_loss(**fixture(logits))
    loss[0, 0].sum().backward()
    assert (logits.grad[0, 0, :2] < 0).all()
    assert logits.grad[0, 0, 2] > 0


def test_unassigned_ambiguous_anchor_does_not_penalize_either_subtype():
    args = fixture(torch.zeros((1, 2, 3), requires_grad=True))
    args["foreground"] = torch.zeros((1, 2), dtype=torch.bool)
    loss = set_classification_loss(**args)
    assert loss[0, 0, :2].tolist() == [0., 0.]
    assert loss[0, 0, 2] > 0


def test_exact_singleton_matches_existing_bce_bitwise():
    args = fixture(torch.randn((1, 2, 3)))
    args["allowed"] = torch.tensor([[[True, False, False]]])
    assert torch.equal(set_classification_loss(**args), F.binary_cross_entropy_with_logits(
        args["logits"], args["targets"], reduction="none"))


def test_assignment_uses_supported_alternative_not_serialization_class():
    assigner = AllowedSetAssigner(num_classes=3, alpha=.5, beta=6.)
    assigner.bs = 1
    assigner.n_max_boxes = 1
    assigner.allowed = torch.tensor([[[True, True, False]]])
    scores = torch.tensor([[[.0001, .9, .99], [.9, .0001, .99]]])
    predicted = torch.tensor([[[0., 0., 10., 10.], [0., 0., 10., 10.]]])
    metric, _ = assigner.get_box_metrics(scores, predicted, torch.tensor([[[0.]]]),
                                        predicted[:, :1], torch.ones((1, 1, 2), dtype=torch.bool))
    assert torch.equal(metric[0, 0, :1], metric[0, 0, 1:])


@pytest.mark.parametrize("values", [(100., -100.), (-100., -100.), (100., 100.)])
def test_union_probability_extreme_logits_is_finite(values):
    logits = torch.tensor([[[*values, -100.], [0., 0., 0.]]], requires_grad=True)
    loss = set_classification_loss(**fixture(logits))
    assert torch.isfinite(loss).all()
    loss.sum().backward()
    assert torch.isfinite(logits.grad).all()


def test_row_alignment_and_invalid_sets_fail_closed():
    batch = {"img": torch.zeros((2, 3, 64, 64)), "cls": torch.tensor([[0.], [1.]]),
             "batch_idx": torch.tensor([0., 1.]), "allowed_class_ids": [[0, 1], [1]]}
    masks = allowed_target_masks(batch, 3, "cpu")
    assert masks.tolist() == [[[True, True, False]], [[False, True, False]]]
    for bad in ([[1], [1]], [[0, 0], [1]], [[0, 3], [1]], [[0]]):
        with pytest.raises(ValueError):
            allowed_target_masks({**batch, "allowed_class_ids": bad}, 3, "cpu")


def test_actual_model_loss_has_box_gradient_and_unknown_empty_image_is_ignored():
    model = ReviewedSetDetectionModel("yolo11n.yaml", nc=3, ch=3, verbose=False)
    model.args = DEFAULT_CFG
    batch = {"img": torch.zeros((2, 3, 64, 64)), "batch_idx": torch.tensor([0.]),
             "cls": torch.tensor([[0.]]), "bboxes": torch.tensor([[.5, .5, .3, .3]]),
             "reviewed_background": torch.tensor([False, False]), "allowed_class_ids": [[0, 1]]}
    loss, _ = model.loss(batch)
    assert torch.isfinite(loss).all()
    assert loss[0] > 0
    loss.sum().backward()
    assert any(p.grad is not None and p.grad.abs().sum() > 0 for p in model.model[-1].cv2.parameters())
    empty = {**batch, "batch_idx": torch.zeros(0), "cls": torch.zeros((0, 1)),
             "bboxes": torch.zeros((0, 4)), "allowed_class_ids": []}
    empty_loss, _ = model.loss(empty)
    assert empty_loss.sum() == 0


def test_trainer_exact_parent_flags_and_allowed_sets_survive_batch(tmp_path):
    root = tmp_path
    data = {"kind": "ved_reviewed_multiclass_training_v1", "required_loss": LOSS_CONTRACT,
            "training_image_records": [{"image_id": "positive", "allowed_class_ids": [[0, 1]]},
                                       {"image_id": "negative", "allowed_class_ids": []}],
            "reviewed_background_images": [{"image_id": "negative"}]}
    (root / "manifest.json").write_text(json.dumps(data))
    trainer = object.__new__(ReviewedSetTrainer)
    trainer.data = {"path": root, "nc": 3}
    trainer.device = "cpu"
    batch = {"img": torch.zeros((2, 3, 64, 64)), "im_file": ["positive.png", "negative.png"],
             "batch_idx": torch.tensor([0.]), "cls": torch.tensor([[0.]])}
    with patch.object(DetectionTrainer, "preprocess_batch", return_value=batch):
        actual = trainer.preprocess_batch(batch)
    assert actual["allowed_class_ids"] == [[0, 1]]
    assert actual["reviewed_background"].tolist() == [False, True]
    assert actual["synthetic_complete"].tolist() == [False, False]


def test_initialized_appended_head_preserves_every_parent_hidden_tensor_exactly():
    from ultralytics.nn.tasks import DetectionModel
    parent = DetectionModel("yolo11n.yaml", nc=80, ch=3, verbose=False)
    head = parent.model[-1]
    for branch in head.cv3:
        old = branch[-1]
        extended = torch.nn.Conv2d(old.in_channels, 91, old.kernel_size, old.stride,
                                   old.padding, bias=True)
        with torch.no_grad():
            extended.weight[:80].copy_(old.weight)
            extended.bias[:80].copy_(old.bias)
        branch[-1] = extended
    head.nc, head.no = 91, 91 + head.reg_max * 4
    parent.names = {i: f"class-{i}" for i in range(91)}
    before = {k: v.clone() for k, v in parent.state_dict().items()}
    trainer = object.__new__(ReviewedSetTrainer)
    trainer.data = dict(nc=91, channels=3, names=parent.names)
    trainer.args = SimpleNamespace(cls_remap=False)
    actual = trainer.get_model(weights=parent, verbose=False)
    assert type(actual) is ReviewedSetDetectionModel
    assert actual is not parent
    assert actual.criterion is None
    assert set(actual.state_dict()) == set(before)
    assert all(torch.equal(before[k], v) for k, v in actual.state_dict().items())
    assert all(branch[-1].in_channels == 80 for branch in actual.model[-1].cv3)


def test_partial_training_never_publishes_full_precision_map():
    trainer = object.__new__(ReviewedSetTrainer)
    trainer.final_eval()
    assert trainer.metrics == {}


def test_final_epoch_validation_never_calls_unannotated_standard_validator():
    trainer = object.__new__(ReviewedSetTrainer)
    trainer.validator = lambda *args, **kwargs: pytest.fail("Partial tiles cannot enter ordinary full-label validation")
    trainer.args = SimpleNamespace(val=False)
    assert trainer.validate() == ({}, 0.0)


def test_noop_geometry_cannot_discard_tiny_reviewed_labels_or_reorder_rows():
    import numpy as np
    from ultralytics.utils.instance import Instances
    options = SimpleNamespace(hsv_h=0, hsv_s=0, hsv_v=0, bgr=0)
    labels = dict(img=np.zeros((256, 256, 3), dtype=np.uint8),
        cls=np.array([[0.], [1.]], dtype=np.float32),
        instances=Instances(np.array([[.5, .5, .3, .3], [.6, .6, 1/256, 1/256]], dtype=np.float32),
            segments=np.zeros((0, 1000, 2), dtype=np.float32), bbox_format="xywh", normalized=True))
    result = reviewed_transform_pipeline(320, options)(labels)
    assert result["cls"].flatten().tolist() == [0., 1.]
    assert torch.allclose(result["bboxes"][1], torch.tensor([.6, .6, 1/256, 1/256]), atol=1e-6)
    assert result["img"].shape == (3, 320, 320)
    with pytest.raises(ValueError, match="Geometric augmentation"):
        reviewed_transform_pipeline(320, SimpleNamespace(**vars(options), fliplr=.5))


def test_negative_sampling_override_is_bounded_and_does_not_mutate_manifest():
    from app.ai.symbol_detection.partial_label_training import ReviewedBackgroundTrainer
    with patch.object(ReviewedBackgroundTrainer, "__init__", return_value=None):
        trainer = ReviewedSetTrainer(negative_sampling_override="top_score_anchors")
        assert trainer.negative_sampling_override == "top_score_anchors"
        assert ReviewedSetTrainer().negative_sampling_override is None
        with pytest.raises(ValueError, match="negative sampling"):
            ReviewedSetTrainer(negative_sampling_override="unknown_pixels")
