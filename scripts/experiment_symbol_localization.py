"""Bounded, positive-only template localization probe for one reviewed legend class.

This development experiment never treats unlabeled page areas as background.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path

import cv2
import numpy as np


CLASS_ID = "sheet-20:L05"  # Pull station, exact drawing legend identity.
SEED_IDS = ("1421451ddf2e1217c0833e17", "0fa577e32ac65b7d915452e0")
SOURCE_SHA = "8cd5962e233fe1dbbe2de981a6169665720e49fb0b2da81215d7532a4299b1ed"
PLAN_ROI = (150, 250, 2050, 2500)  # Page-specific plan region; excludes title block.


def iou(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x1-x0) * max(0, y1-y0)
    area_a = (a[2]-a[0]) * (a[3]-a[1])
    area_b = (b[2]-b[0]) * (b[3]-b[1])
    return intersection / (area_a+area_b-intersection) if area_a+area_b-intersection else 0.0


def center_error(a, b):
    return (((a[0]+a[2]-b[0]-b[2])/2)**2 + ((a[1]+a[3]-b[1]-b[3])/2)**2)**0.5


def find_candidates(gray, templates, threshold):
    candidates = []
    for source_id, box in templates:
        x0, y0, x1, y1 = box
        template = gray[y0:y1, x0:x1]
        if template.size == 0 or template.std() < 3:
            raise ValueError("Blank or invalid template")
        response = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        peaks = (response >= threshold) & (response == cv2.dilate(response, np.ones((9, 9), np.uint8)))
        ys, xs = np.where(peaks)
        if len(xs) > 1000:
            raise ValueError("Candidate cap exceeded")
        for x, y in zip(xs.tolist(), ys.tolist()):
            candidates.append({"bbox": [x, y, x+x1-x0, y+y1-y0],
                               "score": float(response[y, x]), "template_id": source_id,
                               "class_id": CLASS_ID})
    kept = []
    for candidate in sorted(candidates, key=lambda item: -item["score"]):
        if not any(center_error(candidate["bbox"], previous["bbox"]) < 14
                   or iou(candidate["bbox"], previous["bbox"]) > 0.3 for previous in kept):
            kept.append(candidate)
    return kept


def render_overlay(source_path, width, height, targets, predictions, output):
    shapes = []
    for target in targets:
        x0, y0, x1, y1 = target["bbox"]
        color = "#22aa44" if target["localized"] else "#dd2233"
        shapes.append(f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" fill="none" stroke="{color}" stroke-width="4"/>')
    for candidate in predictions:
        x0, y0, x1, y1 = candidate["bbox"]
        shapes.append(f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" fill="none" stroke="#f4a000" stroke-width="2"/>')
    source_url = html.escape(source_path.resolve().as_uri(), quote=True)
    page = ("<!doctype html><meta charset='utf-8'><title>Private localization overlay</title>"
            "<p>Green: localized reviewed target. Red: missed reviewed target. Orange: candidate; unreviewed is uncertain, not false positive.</p>"
            f'<svg viewBox="0 0 {width} {height}" width="100%" xmlns="http://www.w3.org/2000/svg">'
            f'<image href="{source_url}" width="{width}" height="{height}"/>'
            + "".join(shapes) + "</svg>")
    output.write_text(page, encoding="utf-8")


def run(manifest_path, source_path, output, threshold, baseline_checkpoint=None):
    if not 0.5 <= threshold <= 0.95:
        raise ValueError("Experimental threshold outside bounded range")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if hashlib.sha256(source_path.read_bytes()).hexdigest() != SOURCE_SHA:
        raise ValueError("Source page identity mismatch")
    records = [r for r in manifest["records"] if r["source_sha256"] == SOURCE_SHA
               and r["sheet_id"] == "sheet-21" and r["legend_entry"] == CLASS_ID]
    if len(records) != 7 or {r["label"] for r in records} != {"Pull station"}:
        raise ValueError("Expected seven exact-legend reviewed positives")
    seeds = [r for r in records if r["id"] in SEED_IDS]
    heldout = [r for r in records if r["id"] not in SEED_IDS]
    if len(seeds) != 2 or len(heldout) != 5:
        raise ValueError("Diagnostic subset changed")
    gray = cv2.imread(str(source_path), cv2.IMREAD_GRAYSCALE)
    if gray is None or gray.shape != (3264, 2164):
        raise ValueError("Source image geometry mismatch")
    predictions = [p for p in find_candidates(gray, [(r["id"], r["bbox"]) for r in seeds], threshold)
                   if PLAN_ROI[0] <= (p["bbox"][0]+p["bbox"][2])/2 <= PLAN_ROI[2]
                   and PLAN_ROI[1] <= (p["bbox"][1]+p["bbox"][3])/2 <= PLAN_ROI[3]]
    targets = []
    for record in heldout:
        best = min(predictions, key=lambda p: center_error(record["bbox"], p["bbox"]), default=None)
        error = center_error(record["bbox"], best["bbox"]) if best else None
        overlap = iou(record["bbox"], best["bbox"]) if best else 0.0
        targets.append({"id": record["id"], "bbox": record["bbox"],
                        "best_center_error_px": error, "best_iou": overlap,
                        "localized": error is not None and error <= 14})
    baseline = None
    if baseline_checkpoint is not None:
        from ultralytics import YOLO
        model = YOLO(str(baseline_checkpoint))
        raw = model.predict(str(source_path), conf=0.001, imgsz=640, device="cpu", verbose=False)[0]
        baseline = {"checkpoint_sha256": hashlib.sha256(baseline_checkpoint.read_bytes()).hexdigest(),
                    "class_names": list(model.names.values()), "target_class_supported":
                    "Pull station" in model.names.values(), "threshold": 0.5,
                    "raw_max_confidence": max((float(box.conf[0]) for box in raw.boxes), default=0.0),
                    "raw_candidates_at_0_001": len(raw.boxes),
                    "candidates_at_0_5": sum(float(box.conf[0]) >= 0.5 for box in raw.boxes),
                    "comparison_warning": "Baseline has no Pull station class; class-recall comparison is not valid"}
    report = {"kind": "local_positive_only_template_probe", "source_sha256": SOURCE_SHA,
              "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
              "class_id": CLASS_ID, "class_label": "Pull station", "threshold": threshold,
              "plan_roi_source_pixels": PLAN_ROI,
              "class_coverage_before_split": 7, "template_count": len(seeds),
              "heldout_positive_count": len(heldout), "heldout_scope": "same_page_positions_not_project_generalization",
              "seed_ids": list(SEED_IDS), "targets": targets, "predictions": predictions,
              "reviewed_positive_recall_center_14px": sum(t["localized"] for t in targets)/len(targets),
              "reviewed_positive_recall_iou_0_5": sum(t["best_iou"] >= 0.5 for t in targets)/len(targets),
              "precision": None, "precision_reason": "Page is partially annotated; unmatched candidates remain uncertain",
              "baseline_same_page": baseline,
              "status": "inactive_experiment"}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    render_overlay(source_path, gray.shape[1], gray.shape[0], targets, predictions,
                   output.with_suffix(".html"))
    return {"candidates": len(predictions), "heldout_positives": len(heldout),
            "center_recall": report["reviewed_positive_recall_center_14px"],
            "iou_recall": report["reviewed_positive_recall_iou_0_5"], "precision": None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.7)
    parser.add_argument("--baseline-checkpoint", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.manifest, args.source, args.output, args.threshold,
                         args.baseline_checkpoint)))
