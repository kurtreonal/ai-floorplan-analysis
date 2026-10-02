"""Experimental YOLO loss for positive-only review sheets.

The legacy loss retains its narrow collar for historical experiments. New
ReviewedBoxOnlyLoss experiments ignore every anchor outside reviewed boxes;
unreviewed collars are not assumed background. Neither mode establishes
complete-region evaluation or production dataset approval.
"""

import torch
import json
from pathlib import Path

from ultralytics.models.yolo.detect.train import DetectionTrainer
from ultralytics.nn.tasks import DetectionModel
from ultralytics.utils.loss import v8DetectionLoss
from ultralytics.utils.tal import make_anchors


def local_negative_mask(anchor_pixels, boxes, valid_boxes, margin_pixels=12):
    """Mark anchors in a narrow collar of a reviewed target box."""
    x = anchor_pixels[:, 0].view(1, -1, 1)
    y = anchor_pixels[:, 1].view(1, -1, 1)
    x1, y1, x2, y2 = (boxes[:, None, :, index] for index in range(4))
    near = ((x >= x1 - margin_pixels) & (x <= x2 + margin_pixels)
            & (y >= y1 - margin_pixels) & (y <= y2 + margin_pixels))
    return (near & valid_boxes[:, None, :, 0].bool()).any(dim=-1)


class PartialLabelLoss(v8DetectionLoss):
    negative_margin_pixels = 12
    reviewed_background_enabled = False

    def get_assigned_targets_and_loss(self, preds, batch):
        loss = torch.zeros(3, device=self.device)
        pred_distri = preds["boxes"].permute(0, 2, 1).contiguous()
        pred_scores = preds["scores"].permute(0, 2, 1).contiguous()
        anchor_points, stride_tensor = make_anchors(preds["feats"], self.stride, 0.5)
        dtype = pred_scores.dtype
        batch_size = pred_scores.shape[0]
        imgsz = torch.tensor(preds["feats"][0].shape[2:], device=self.device, dtype=dtype) * self.stride[0]
        targets = torch.cat((batch["batch_idx"].view(-1, 1),
                             batch["cls"].view(-1, 1), batch["bboxes"]), 1)
        targets = self.preprocess(targets.to(self.device), batch_size, scale_tensor=imgsz[[1, 0, 1, 0]])
        gt_labels, gt_bboxes = targets.split((1, 4), 2)
        mask_gt = gt_bboxes.sum(2, keepdim=True).gt_(0.0)
        pred_bboxes = self.bbox_decode(anchor_points, pred_distri)
        _, target_bboxes, target_scores, fg_mask, target_gt_idx = self.assigner(
            pred_scores.detach().sigmoid(),
            (pred_bboxes.detach() * stride_tensor).type(gt_bboxes.dtype),
            anchor_points * stride_tensor, gt_labels, gt_bboxes, mask_gt)
        # Empty-target batches return a floating zero mask in this runtime.
        fg_mask = fg_mask.bool()
        target_scores_sum = max(target_scores.sum(), 1)
        bce_loss = self.bce(pred_scores, target_scores.to(dtype))
        if self.class_weights is not None:
            bce_loss *= self.class_weights
        # New reviewed-box-only runs use zero margin. Preserve the old collar
        # loss for checkpoint compatibility, not as reviewed-background proof.
        near_reviewed = local_negative_mask(anchor_points * stride_tensor, gt_bboxes, mask_gt,
                                            margin_pixels=self.negative_margin_pixels)
        weights = (fg_mask | near_reviewed).to(bce_loss.dtype)
        if self.reviewed_background_enabled:
            weights = reviewed_background_weights(weights, batch.get("reviewed_background"), mask_gt)
        bce_loss *= weights.unsqueeze(-1)
        loss[1] = bce_loss.sum() / target_scores_sum
        if fg_mask.sum():
            loss[0], loss[2] = self.bbox_loss(
                pred_distri, pred_bboxes, anchor_points, target_bboxes / stride_tensor,
                target_scores, target_scores_sum, fg_mask, imgsz, stride_tensor)
        loss[0] *= self.hyp.box
        loss[1] *= self.hyp.cls
        loss[2] *= self.hyp.dfl
        return ((fg_mask, target_gt_idx, target_bboxes, anchor_points, stride_tensor),
                loss, dict(zip(self.loss_names, loss.detach())))


class PartialLabelDetectionModel(DetectionModel):
    def init_criterion(self):
        if getattr(self, "end2end", False):
            raise ValueError("Partial-label loss is not implemented for end-to-end detectors")
        return PartialLabelLoss(self)


class ReviewedBoxOnlyLoss(PartialLabelLoss):
    """No assumed negatives beyond the user-reviewed symbol boxes."""
    negative_margin_pixels = 0


class ReviewedBoxOnlyDetectionModel(PartialLabelDetectionModel):
    def init_criterion(self):
        if getattr(self, "end2end", False):
            raise ValueError("Partial-label loss is not implemented for end-to-end detectors")
        return ReviewedBoxOnlyLoss(self)


class PartialLabelTrainer(DetectionTrainer):
    model_class = PartialLabelDetectionModel

    def get_model(self, cfg=None, weights=None, verbose=True):
        model = self.set_model_names_for_load(
            self.model_class(cfg, nc=self.data["nc"], ch=self.data["channels"], verbose=verbose))
        if weights:
            model.load(weights)
        return model


class ReviewedBoxOnlyTrainer(PartialLabelTrainer):
    model_class = ReviewedBoxOnlyDetectionModel


def reviewed_background_weights(weights, reviewed_background, mask_gt):
    """Only explicitly reviewed, wholly negative images supervise other anchors.

    Limit their loss mass to 32 anchors per image so thousands of background
    anchors do not overwhelm scarce positive examples. Unknown empty images
    remain ignored, not negatives. Positive and negative flags may not conflict.
    """
    if reviewed_background is None:
        return weights
    flags = torch.as_tensor(reviewed_background, device=weights.device, dtype=torch.bool)
    if flags.shape != (weights.shape[0],) or (flags & mask_gt.bool().any(dim=(1, 2))).any():
        raise ValueError("Invalid reviewed background identity or conflicting positive labels")
    return torch.where(flags[:, None], torch.full_like(weights, min(1., 32 / weights.shape[1])), weights)


class ReviewedBackgroundLoss(ReviewedBoxOnlyLoss):
    reviewed_background_enabled = True


class ReviewedBackgroundDetectionModel(ReviewedBoxOnlyDetectionModel):
    def init_criterion(self):
        if getattr(self, "end2end", False):
            raise ValueError("Reviewed-background loss is not implemented for end-to-end detectors")
        return ReviewedBackgroundLoss(self)


class ReviewedBackgroundTrainer(ReviewedBoxOnlyTrainer):
    model_class = ReviewedBackgroundDetectionModel

    def preprocess_batch(self, batch):
        batch = super().preprocess_batch(batch)
        if not hasattr(self, "_reviewed_background_stems"):
            manifest = json.loads((Path(self.data["path"]) / "manifest.json").read_text())
            if manifest.get("required_loss") != "positive_boxes_and_explicit_reviewed_background":
                raise ValueError("Missing explicit reviewed-background manifest")
            self._reviewed_background_stems = {r["image_id"] for r in manifest["reviewed_background_images"]}
        batch["reviewed_background"] = torch.tensor(
            [Path(name).stem in self._reviewed_background_stems for name in batch["im_file"]], device=self.device)
        return batch
