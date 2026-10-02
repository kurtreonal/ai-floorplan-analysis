"""Probe a local detector on full, partially labeled source pages.

Only reviewed-positive recall is scored. Unmatched predictions remain
unresolved; this script never calls them false positives or reports precision.
"""

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import numpy as np

from PIL import Image, ImageDraw
os.environ["YOLO_AUTOINSTALL"] = "false"
os.environ["YOLO_OFFLINE"] = "true"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from ultralytics import YOLO


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def origins(length, tile=256, stride=192):
    values = list(range(0, max(1, length - tile + 1), stride))
    end = max(0, length - tile)
    if values[-1] != end:
        values.append(end)
    return values


def iou(a, b):
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    overlap = max(0, x2 - x1) * max(0, y2 - y1)
    aa = (a[2] - a[0]) * (a[3] - a[1])
    bb = (b[2] - b[0]) * (b[3] - b[1])
    return overlap / (aa + bb - overlap) if aa + bb > overlap else 0.0


def fuse(rows):
    retained = []
    for row in sorted(rows, key=lambda item: -item["score"]):
        if not any(row["class_id"] == earlier["class_id"]
                   and iou(row["bbox"], earlier["bbox"]) >= 0.5 for earlier in retained):
            retained.append(row)
    return retained


def match_targets(targets, predictions, *, require_class=True, threshold=0.5):
    """Maximum one-to-one IoU matching; a prediction cannot satisfy two targets."""
    edges = []
    for target in targets:
        compatible = [(index, iou(target["source_box"], prediction["bbox"]))
                      for index, prediction in enumerate(predictions)
                      if not require_class or prediction["class_id"] == target["class_id"]]
        edges.append([index for index, overlap in sorted(compatible, key=lambda pair: -pair[1])
                      if overlap >= threshold])
    assigned = {}

    def assign(target_index, visited):
        for prediction_index in edges[target_index]:
            if prediction_index in visited:
                continue
            visited.add(prediction_index)
            if prediction_index not in assigned or assign(assigned[prediction_index], visited):
                assigned[prediction_index] = target_index
                return True
        return False

    for index in range(len(targets)):
        assign(index, set())
    return {target_index: prediction_index for prediction_index, target_index in assigned.items()}


def probe_unreviewed_image(source, output):
    """Exercise the actual shared upload provider; no ground truth is invented."""
    from app.ai.floor_plan_interpretation import multiclass_symbol_detector as runtime
    if output.exists():
        raise FileExistsError("Probe result versions are immutable")
    if not source.is_file() or source.stat().st_size > 25 * 1024 * 1024:
        raise ValueError("Source exceeds file bounds")
    before = digest(source)
    with Image.open(source) as opened:
        if opened.width * opened.height > 60_000_000 or max(opened.size) > 10_000:
            raise ValueError("Source dimensions exceed bound")
        image = opened.convert("RGB")
    start = time.perf_counter()
    predictions, truncated = runtime.locate(np.asarray(image))
    seconds = round(time.perf_counter() - start, 3)
    if digest(source) != before:
        raise ValueError("Source changed during probe")
    overlay = image.copy()
    pen = ImageDraw.Draw(overlay)
    for row in predictions:
        pen.rectangle(row["bbox"], outline="orange", width=2)
        pen.text((row["bbox"][0], row["bbox"][1]), str(row["class_id"]), fill="red")
    result = {"kind": "unscored_shared_multiclass_upload_probe", "source_sha256": before,
        "source_size": image.size, "checkpoint_sha256": runtime.CHECKPOINT_SHA256,
        "dataset_manifest_sha256": runtime.DATASET_SHA256, "provider": runtime.PROVIDER,
        "threshold": runtime.THRESHOLD, "seconds": seconds, "predictions": predictions,
        "truncated": truncated, "precision": None, "recall": None,
        "reason": "No verified complete reference labels or drawing-specific legend mapping; proposals require review."}
    output.mkdir(parents=True)
    overlay.save(output / "overlay.png")
    (output / "report.json").write_text(json.dumps(result, indent=2))
    return {"proposals": len(predictions), "seconds": seconds, "precision": None, "recall": None}


def probe(dataset, source_root, checkpoint, output, *, threshold=0.25, inference_mode="tiles", shared_multiclass=False):
    if output.exists():
        raise FileExistsError("Probe result versions are immutable")
    if not 0.01 <= threshold <= 0.95:
        raise ValueError("Invalid threshold")
    manifest = json.loads((dataset / "manifest.json").read_text())
    if manifest["kind"] != "positive_only_masked_symbol_detection_diagnostic_v1":
        raise ValueError("Wrong dataset")
    generic = manifest.get("class_agnostic") is True
    by_hash = {}
    for path in source_root.rglob("*"):
        if path.is_file() and not path.is_symlink() and path.suffix.lower() in {".jpg", ".jpeg", ".png"} \
                and path.stat().st_size <= 25_000_000 and not any(
                    p in {"node_modules", ".git", "backups", "training_dataset", ".temp"} for p in path.parts):
            by_hash[digest(path)] = path
    reviewed = manifest.get("reviewed_targets", manifest["images"])
    source_hashes = {row["source_sha256"] for row in reviewed}
    if not source_hashes <= by_hash.keys():
        raise ValueError("Exact source missing")
    model = YOLO(str(checkpoint))
    if shared_multiclass:
        from app.ai.floor_plan_interpretation import multiclass_symbol_detector as runtime
        if (threshold != runtime.THRESHOLD or digest(checkpoint) != runtime.CHECKPOINT_SHA256
                or digest(dataset/"manifest.json") != runtime.DATASET_SHA256):
            raise ValueError("Probe must use the exact shared runtime checkpoint, dataset, and threshold")
    class_ids = sorted({row["id"] for row in manifest["classes"]})
    if inference_mode not in {"tiles", "full"}:
        raise ValueError("Unsupported inference mode")
    output.mkdir(parents=True)
    pages = []
    for source_hash in sorted(source_hashes):
        with Image.open(by_hash[source_hash]) as opened:
            image = opened.convert("RGB")
        if image.width * image.height > 60_000_000 or max(image.size) > 10_000:
            raise ValueError("Source dimensions exceed bound")
        positions = ([(x, y) for y in origins(image.height) for x in origins(image.width)]
                     if inference_mode == "tiles" else [])
        if shared_multiclass:
            positions = runtime.shared.tile_positions(image.width, image.height, dual_phase=True)
        if len(positions) > 500:
            raise ValueError("Tile count exceeds bound")
        raw = []
        truncated = False
        start = time.perf_counter()
        if shared_multiclass:
            predictions, truncated = runtime.locate(np.asarray(image))
            raw = list(predictions)
        elif inference_mode == "full":
            result = model.predict(image, imgsz=1280, conf=threshold, classes=class_ids,
                                   device="cpu", verbose=False, max_det=500)[0]
            for box in result.boxes:
                raw.append({"bbox": [float(v) for v in box.xyxy[0].tolist()],
                            "class_id": int(box.cls[0]), "score": float(box.conf[0]),
                            "tile_origin": None})
        for offset in range(0, 0 if shared_multiclass else len(positions), 16):
            batch_positions = positions[offset:offset + 16]
            tiles = [image.crop((x, y, x + 256, y + 256)) for x, y in batch_positions]
            results = model.predict(tiles, imgsz=320, conf=threshold, classes=class_ids,
                                    device="cpu", verbose=False,
                                    max_det=100, batch=16)
            for (x, y), result in zip(batch_positions, results):
                for box in result.boxes:
                    x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
                    raw.append({"bbox": [x+x1, y+y1, x+x2, y+y2],
                                "class_id": int(box.cls[0]), "score": float(box.conf[0]),
                                "tile_origin": [x, y]})
        elapsed = round(time.perf_counter() - start, 3)
        predictions = fuse(raw)
        targets = [row for row in reviewed if row["source_sha256"] == source_hash]
        classified_matches = match_targets(targets, predictions, require_class=not generic)
        localized_matches = match_targets(targets, predictions, require_class=False)
        matched = []
        for target_index, target in enumerate(targets):
            same_class = [p for p in predictions if p["class_id"] == target["class_id"]]
            best = max((iou(target["source_box"], p["bbox"]) for p in same_class), default=0.0)
            matched.append({"record_id": target["record_id"], "class_id": target["class_id"],
                            "best_class_iou": round(best, 4),
                            "localization_prediction_index": localized_matches.get(target_index),
                            "classification_prediction_index": classified_matches.get(target_index),
                            "localized": target_index in localized_matches,
                            **({"localized_and_classified": target_index in classified_matches}
                               if not generic else {})})
        overlay = image.copy()
        pen = ImageDraw.Draw(overlay)
        for target in targets:
            found = next(row["localized" if generic else "localized_and_classified"] for row in matched
                         if row["record_id"] == target["record_id"])
            pen.rectangle(target["source_box"], outline="green" if found else "red", width=4)
        for prediction in predictions:
            pen.rectangle(prediction["bbox"], outline="blue", width=2)
        overlay_name = f"{source_hash[:16]}-overlay.jpg"
        overlay.thumbnail((1400, 2000))
        overlay.save(output / overlay_name, quality=85)
        pages.append({"source_sha256": source_hash, "sheet_ids": sorted({r["sheet_id"] for r in targets}),
                      "tile_count": len(positions), "seconds": elapsed,
                      "raw_candidates": len(raw), "fused_candidates": len(predictions),
                      "reviewed_positive_count": len(targets),
                      "reviewed_positive_localization_recall_iou_0_5": len(localized_matches)/len(targets),
                      **({"reviewed_positive_recall_iou_0_5": len(classified_matches)/len(targets)}
                         if not generic else {}),
                      "targets": matched, "predictions": predictions, "overlay": overlay_name,
                      "truncated": truncated,
                      "unmatched_predictions": "unresolved, not scored false positives"})
    report = {"kind": "partial_label_full_page_probe_v1", "checkpoint_sha256": digest(checkpoint),
              "dataset_manifest_sha256": digest(dataset / "manifest.json"), "threshold": threshold,
              "inference_mode": inference_mode, "class_agnostic": generic,
              "classification": None if generic else "same-source diagnostic",
              "shared_runtime": shared_multiclass,
              "tiling": {"size": 256, "stride": 192, "model_input": 320,
                         "second_phase_offset": 128 if shared_multiclass else None,
                         "duplicate_suppression": "same-class IoU >= 0.5"},
              "precision": None, "generalization": None,
              "matching": "maximum one-to-one IoU >= 0.5; localization and same-class scored separately",
              "reasons": ["Pages are partially annotated; false positives cannot be established.",
                          "Training and probe share source projects/pages; no independent test.",
                          *(["The generic model does not predict approved legend classes."] if generic else [])],
              "pages": pages}
    per_class = []
    for cls in manifest["classes"]:
        targets = [target for page in pages for target in page["targets"]
                   if target["class_id"] == cls["id"]]
        per_class.append({"class_id": cls["id"], "legend_entry": cls["legend_entry"],
                          "label": cls["label"], "reviewed_positive_count": len(targets),
                          "localized": sum(t["localized"] for t in targets),
                          "localized_and_classified": (None if generic else
                              sum(t["localized_and_classified"] for t in targets))})
    total = sum(page["reviewed_positive_count"] for page in pages)
    localized = sum(c["localized"] for c in per_class)
    classified = None if generic else sum(c["localized_and_classified"] for c in per_class)
    report["summary"] = {"reviewed_positive_count": total, "localized": localized,
                         "localized_and_classified": classified,
                         "reviewed_positive_localization_recall": localized / total,
                         "reviewed_positive_class_recall": None if generic else classified / total,
                         "fused_proposals": sum(page["fused_candidates"] for page in pages),
                         "truncated_pages": sum(page["truncated"] for page in pages),
                         "precision": None, "independent_project_accuracy": None,
                         "per_class": per_class}
    (output / "report.json").write_text(json.dumps(report, indent=2))
    return [{k: v for k, v in p.items() if k in {"sheet_ids", "tile_count", "seconds",
                                                    "fused_candidates", "reviewed_positive_count",
                                                    "reviewed_positive_recall_iou_0_5",
                                                    "reviewed_positive_localization_recall_iou_0_5"}} for p in pages]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--source-image", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.25)
    parser.add_argument("--inference-mode", choices=("tiles", "full"), default="tiles")
    parser.add_argument("--shared-multiclass", action="store_true")
    args = parser.parse_args()
    if args.source_image:
        if any((args.dataset, args.source_root, args.checkpoint)):
            parser.error("Single-source probes use only the pinned shared runtime")
        print(json.dumps(probe_unreviewed_image(args.source_image, args.output)))
    else:
        if not all((args.dataset, args.source_root, args.checkpoint)):
            parser.error("Reviewed probes require dataset, source root, and checkpoint")
        print(json.dumps(probe(args.dataset, args.source_root, args.checkpoint, args.output,
                               threshold=args.threshold, inference_mode=args.inference_mode,
                               shared_multiclass=args.shared_multiclass)))
