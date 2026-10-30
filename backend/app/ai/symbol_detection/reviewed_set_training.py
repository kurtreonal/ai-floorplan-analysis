"""Offline reviewed-box training with explicit allowed subtype sets.

The class stored in a YOLO row is a serialization representative, not an
assertion of an uncertain subtype. Unknown image regions remain loss-masked.
"""
import json
from copy import deepcopy
from pathlib import Path

import torch
from torch.nn import functional as F
from ultralytics.utils.tal import TaskAlignedAssigner, make_anchors
from ultralytics.data.augment import Compose, LetterBox, RandomHSV, Format

from app.ai.symbol_detection.partial_label_training import (
    ReviewedBackgroundLoss, ReviewedBackgroundDetectionModel,
    ReviewedBackgroundTrainer,
)

LOSS_CONTRACT = "reviewed_boxes_allowed_subtypes_and_explicit_background"


def reviewed_transform_pipeline(image_size, options):
    """No no-op affine filter may discard/reorder reviewed target rows."""
    geometry_options = ("mosaic", "mixup", "copy_paste", "cutmix", "degrees", "translate",
                        "scale", "fliplr", "flipud", "perspective", "shear")
    if any(getattr(options, name, 0) != 0 for name in geometry_options):
        raise ValueError("Geometric augmentation cannot preserve reviewed row identities")
    return Compose([
        LetterBox(new_shape=(image_size, image_size), scaleup=True),
        RandomHSV(hgain=options.hsv_h, sgain=options.hsv_s, vgain=options.hsv_v),
        Format(bbox_format="xywh", normalize=True, batch_idx=True, bgr=options.bgr),
    ])


def allowed_target_masks(batch, class_count, device):
    """Pad row-aligned allowed sets in the same per-image order as YOLO GTs."""
    classes = batch["cls"].flatten().long().to(device)
    indices = batch["batch_idx"].long().to(device)
    sets = batch.get("allowed_class_ids")
    if sets is None or len(sets) != len(classes):
        raise ValueError("Missing row-aligned allowed subtype evidence")
    batch_size = batch["img"].shape[0]
    counts = [int((indices == i).sum()) for i in range(batch_size)]
    result = torch.zeros((batch_size, max(counts, default=0), class_count),
                         device=device, dtype=torch.bool)
    cursors = [0] * batch_size
    for row, ids in enumerate(sets):
        if (not isinstance(ids, (list, tuple)) or not ids or len(ids) > 8
                or len(set(ids)) != len(ids)
                or any(type(i) is not int or not 0 <= i < class_count for i in ids)
                or int(classes[row]) not in ids):
            raise ValueError("Invalid allowed subtype set or representative")
        image_index = int(indices[row])
        if not 0 <= image_index < batch_size:
            raise ValueError("Target image index exceeds batch")
        result[image_index, cursors[image_index], list(ids)] = True
        cursors[image_index] += 1
    return result


def set_classification_loss(logits, targets, allowed, boxes, labels,
                            anchor_pixels, foreground, assigned_gt):
    """Exact labels retain BCE; ambiguous labels supervise the allowed union.

    An allowed alternative is never treated as a negative at a reviewed
    ambiguous box. Assigned exact labels take precedence over overlapping
    uncertain boxes. Outside reviewed boxes the caller applies its zero mask.
    """
    original = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
    result = original.clone()
    ambiguous = allowed.sum(-1) > 1
    for b, g in torch.nonzero(ambiguous, as_tuple=False).tolist():
        x1, y1, x2, y2 = boxes[b, g]
        inside = ((anchor_pixels[:, 0] >= x1) & (anchor_pixels[:, 0] <= x2)
                  & (anchor_pixels[:, 1] >= y1) & (anchor_pixels[:, 1] <= y2))
        anchors = torch.where(inside)[0]
        ids = torch.where(allowed[b, g])[0]
        result[b, anchors[:, None], ids[None, :]] = 0
    # Restore ordinary BCE for every assigned target before overriding sets.
    result[foreground] = original[foreground]
    for b, g in torch.nonzero(ambiguous, as_tuple=False).tolist():
        anchors = torch.where(foreground[b] & (assigned_gt[b] == g))[0]
        if not len(anchors):
            continue
        ids = torch.where(allowed[b, g])[0]
        selected = logits[b, anchors[:, None], ids[None, :]]
        # log P(no allowed class) is stable even for very large finite logits.
        log_none = F.logsigmoid(-selected).sum(-1)
        log_union = torch.log((-torch.expm1(log_none)).clamp_min(torch.finfo(logits.dtype).tiny))
        quality = targets[b, anchors].sum(-1)
        union_loss = -quality * log_union - (1 - quality) * log_none
        result[b, anchors[:, None], ids[None, :]] = 0
        representative = int(labels[b, g, 0])
        result[b, anchors, representative] = union_loss
    return result


class AllowedSetAssigner(TaskAlignedAssigner):
    """Use supported subtype evidence, not the serialization representative."""
    def get_box_metrics(self, pd_scores, pd_bboxes, gt_labels, gt_bboxes, mask_gt):
        _, overlaps = super().get_box_metrics(
            pd_scores, pd_bboxes, gt_labels, gt_bboxes, mask_gt)
        scores = torch.zeros_like(overlaps)
        for b, g in torch.nonzero(self.allowed.any(-1), as_tuple=False).tolist():
            ids = torch.where(self.allowed[b, g])[0]
            scores[b, g] = pd_scores[b, :, ids].amax(-1)
        scores *= mask_gt.to(scores.dtype)
        return scores.pow(self.alpha) * overlaps.pow(self.beta), overlaps

    def forward(self, *args, **kwargs):
        result = super().forward(*args, **kwargs)
        self.foreground = result[3].bool()
        self.assigned_gt = result[4]
        return result


class ReviewedSetLoss(ReviewedBackgroundLoss):
    def __init__(self, model, tal_topk=10, tal_topk2=None):
        super().__init__(model, tal_topk=tal_topk, tal_topk2=tal_topk2)
        if self.class_weights is not None:
            raise ValueError("Set-valued supervision does not support per-logit class weights")
        self.assigner = AllowedSetAssigner(
            topk=tal_topk, num_classes=self.nc, alpha=.5, beta=6.,
            stride=self.stride.tolist(), topk2=tal_topk2)
        del self.bce
        self.bce = self._set_bce

    def _set_bce(self, logits, targets):
        return set_classification_loss(
            logits, targets, self.assigner.allowed, self._set_boxes,
            self._set_labels, self._set_anchor_pixels,
            self.assigner.foreground, self.assigner.assigned_gt)

    def get_assigned_targets_and_loss(self, preds, batch):
        self.assigner.allowed = allowed_target_masks(batch, self.nc, self.device)
        dtype = preds["scores"].dtype
        size = torch.tensor(preds["feats"][0].shape[2:], device=self.device, dtype=dtype) * self.stride[0]
        targets = torch.cat((batch["batch_idx"].view(-1, 1), batch["cls"].view(-1, 1), batch["bboxes"]), 1)
        padded = self.preprocess(targets.to(self.device), batch["img"].shape[0],
                                 scale_tensor=size[[1, 0, 1, 0]])
        self._set_labels, self._set_boxes = padded.split((1, 4), 2)
        points, strides = make_anchors(preds["feats"], self.stride, .5)
        self._set_anchor_pixels = points * strides
        return super().get_assigned_targets_and_loss(preds, batch)


class ReviewedSetDetectionModel(ReviewedBackgroundDetectionModel):
    def init_criterion(self):
        if getattr(self, "end2end", False):
            raise ValueError("Allowed sets are not implemented for end-to-end heads")
        return ReviewedSetLoss(self)


class ReviewedSetTrainer(ReviewedBackgroundTrainer):
    model_class = ReviewedSetDetectionModel

    def __init__(self, *args, negative_sampling_override=None, **kwargs):
        if negative_sampling_override not in (None, "uniform_budget", "top_score_anchors"):
            raise ValueError("Unsupported explicit negative sampling override")
        self.negative_sampling_override = negative_sampling_override
        super().__init__(*args, **kwargs)

    def build_dataset(self, img_path, mode="train", batch=None):
        dataset = super().build_dataset(img_path, mode=mode, batch=batch)
        if mode == "train":
            if dataset.use_segments or dataset.use_keypoints or dataset.use_obb:
                raise ValueError("Reviewed row-aligned training supports detection boxes only")
            dataset.transforms = reviewed_transform_pipeline(self.args.imgsz, self.args)
        return dataset

    def get_model(self, cfg=None, weights=None, verbose=True):
        if weights is None:
            return super().get_model(cfg=cfg, weights=None, verbose=verbose)
        if not isinstance(weights, torch.nn.Module):
            raise ValueError("An initialized local detector module is required")
        head = weights.model[-1]
        if (type(head).__name__ != "Detect" or getattr(head, "end2end", False)
                or head.nc != self.data["nc"] or len(weights.names) != self.data["nc"]):
            raise ValueError("Initialized classifier architecture differs from reviewed class map")
        # Reconstructing nc91 from YAML would widen classifier hidden channels
        # from80 to91 and silently skip parent body weights during load. Keep
        # the actual serialized graph; only replace the offline loss owner.
        model = deepcopy(weights)
        model.__class__ = ReviewedSetDetectionModel
        model.criterion = None
        model.names = dict(self.data["names"])
        return self.set_model_names_for_load(model)

    def final_eval(self):
        """Do not manufacture full precision/mAP from partially reviewed tiles.

        The paired offline harness measures reviewed-positive matches and
        explicit negative controls; this is not an independently gold val set.
        """
        self.metrics = {}

    def validate(self):
        # Ultralytics invokes validation on the final epoch even when val=False.
        # Its ordinary validator lacks row-aligned allowed sets and assumes
        # exhaustive annotations. Zero is a serialization fitness sentinel,
        # never a recognition score or a checkpoint promotion criterion.
        return {}, 0.0

    def preprocess_batch(self, batch):
        # Reuse explicit parent negative/synthetic flags, with the new contract.
        if not hasattr(self, "_allowed_sets"):
            data = json.loads((Path(self.data["path"]) / "manifest.json").read_text(encoding="utf-8"))
            if data.get("kind") != "ved_reviewed_multiclass_training_v1" or data.get("required_loss") != LOSS_CONTRACT:
                raise ValueError("Missing reviewed multiclass loss contract")
            rows = data["training_image_records"]
            self._allowed_sets = {r["image_id"]: r["allowed_class_ids"] for r in rows}
            if len(self._allowed_sets) != len(rows):
                raise ValueError("Duplicate training image identity")
            self._reviewed_background_stems = {r["image_id"] for r in data.get("reviewed_background_images", [])}
            self._reviewed_background_sampling = (getattr(self, "negative_sampling_override", None)
                or data.get("reviewed_background_sampling", "uniform_budget"))
            if self._reviewed_background_sampling not in ("uniform_budget", "top_score_anchors"):
                raise ValueError("Unsupported explicit negative sampling")
            self._synthetic_complete_stems = {
                r["image_id"] for r in data.get("authored_legend_synthetic_images", [])
                if data.get("synthetic_complete_background") is True
                and r.get("human_review_claim") is False
                and r.get("label_origin") == "known_synthetic_composite_geometry"}
        batch = super().preprocess_batch(batch)
        sets = []
        for image_index, filename in enumerate(batch["im_file"]):
            stem = Path(filename).stem
            if stem not in self._allowed_sets:
                raise ValueError("Unknown image has no allowed-set provenance")
            rows = self._allowed_sets[stem]
            if len(rows) != int((batch["batch_idx"] == image_index).sum()):
                raise ValueError("Augmentation changed reviewed label row order/count")
            sets.extend(rows)
        batch["allowed_class_ids"] = sets
        allowed_target_masks(batch, self.data["nc"], self.device)
        return batch
