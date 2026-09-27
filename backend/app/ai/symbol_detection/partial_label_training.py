"""Experimental YOLO loss for positive-only review sheets.

Only assigned positives and a narrow local collar contribute classification
loss. Other anchors are ignored, not treated as reviewed background. This is
not a substitute for complete-region evaluation or a production training set.
"""

import torch

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
        target_scores_sum = max(target_scores.sum(), 1)
        bce_loss = self.bce(pred_scores, target_scores.to(dtype))
        if self.class_weights is not None:
            bce_loss *= self.class_weights
        # Unlike standard YOLO training, unknown page pixels are NOT negatives.
        near_reviewed = local_negative_mask(anchor_points * stride_tensor, gt_bboxes, mask_gt)
        bce_loss *= (fg_mask | near_reviewed).unsqueeze(-1)
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


class PartialLabelTrainer(DetectionTrainer):
    def get_model(self, cfg=None, weights=None, verbose=True):
        model = self.set_model_names_for_load(
            PartialLabelDetectionModel(cfg, nc=self.data["nc"], ch=self.data["channels"],
                                       verbose=verbose))
        if weights:
            model.load(weights)
        return model
