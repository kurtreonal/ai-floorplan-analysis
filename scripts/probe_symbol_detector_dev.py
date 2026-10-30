"""Probe a local detector on full, partially labeled source pages.

Only reviewed-positive recall is scored. Unmatched predictions remain
unresolved; this script never calls them false positives or reports precision.
"""

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import unicodedata
import numpy as np

from PIL import Image, ImageDraw
os.environ["YOLO_AUTOINSTALL"] = "false"
os.environ["YOLO_OFFLINE"] = "true"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from ultralytics import YOLO


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_model_classes(model, rows):
    if any(type(row['id']) is not int for row in rows) or {row['id'] for row in rows} != set(range(len(rows))):
        raise ValueError("Candidate class IDs must be contiguous")
    expected = {row['id']: unicodedata.normalize('NFKD', row['label']).encode('ascii', 'ignore').decode()
                for row in rows}
    actual = {i: unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
              for i, name in model.names.items()}
    if actual != expected:
        raise ValueError("Candidate checkpoint and legend identities differ")


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


def probe_unreviewed_image(source, output, *, checkpoint=None, dataset=None):
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
    if (checkpoint is None) != (dataset is None):
        raise ValueError("Candidate probes require both checkpoint and dataset")
    checkpoint_hash, dataset_hash = runtime.CHECKPOINT_SHA256, runtime.DATASET_SHA256
    if checkpoint is None:
        predictions, truncated = runtime.locate(np.asarray(image))
    else:
        # Exercise the same bounded tiler without changing the active provider.
        manifest_path = dataset / "manifest.json"
        if checkpoint.stat().st_size > 30_000_000 or manifest_path.stat().st_size > 5_000_000:
            raise ValueError("Candidate artifacts exceed bounds")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        rows = manifest["classes"]
        model = YOLO(str(checkpoint))
        validate_model_classes(model, rows)
        predictions, truncated = runtime.shared.locate(np.asarray(image), catalog={
            "classes": {row["id"]: (row["label"], row["legend_entry"]) for row in rows},
            "threshold": runtime.THRESHOLD, "model": model})
        checkpoint_hash, dataset_hash = digest(checkpoint), digest(manifest_path)
    seconds = round(time.perf_counter() - start, 3)
    if digest(source) != before:
        raise ValueError("Source changed during probe")
    overlay = image.copy()
    pen = ImageDraw.Draw(overlay)
    for row in predictions:
        pen.rectangle(row["bbox"], outline="orange", width=2)
        pen.text((row["bbox"][0], row["bbox"][1]), str(row["class_id"]), fill="red")
    result = {"kind": "unscored_shared_multiclass_upload_probe", "source_sha256": before,
        "source_size": image.size, "checkpoint_sha256": checkpoint_hash,
        "dataset_manifest_sha256": dataset_hash, "provider": runtime.PROVIDER,
        "active_provider_checkpoint": checkpoint is None,
        "threshold": runtime.THRESHOLD, "seconds": seconds, "predictions": predictions,
        "truncated": truncated, "precision": None, "recall": None,
        "reason": "No verified complete reference labels or drawing-specific legend mapping; proposals require review."}
    output.mkdir(parents=True)
    overlay.save(output / "overlay.png")
    (output / "report.json").write_text(json.dumps(result, indent=2))
    return {"proposals": len(predictions), "seconds": seconds, "precision": None, "recall": None}


def probe_authored_synthetic(dataset, checkpoint, output, *, samples_per_class=16, image_size=320):
    """Known-box learning check only; never interpreted as real-page accuracy."""
    if output.exists():
        raise FileExistsError("Probe result versions are immutable")
    if type(samples_per_class) is not int or not 1 <= samples_per_class <= 64:
        raise ValueError("Synthetic probe bounds exceeded")
    if image_size not in (320,640):
        raise ValueError('Synthetic image-size bound exceeded')
    if checkpoint.stat().st_size > 30_000_000 or (dataset / "manifest.json").stat().st_size > 5_000_000:
        raise ValueError("Candidate artifacts exceed bounds")
    manifest = json.loads((dataset / "manifest.json").read_text())
    selected, counts = [], Counter()
    for row in manifest["authored_legend_synthetic_images"]:
        if counts[row["class_id"]] >= samples_per_class:
            continue
        name = row["image_id"]
        if Path(name).name != name or row.get("human_review_claim") is not False:
            raise ValueError("Invalid synthetic identity")
        path = dataset / "images/train" / f"{name}.png"
        if path.stat().st_size > 2_000_000 or digest(path) != row["image_sha256"]:
            raise ValueError("Synthetic image differs")
        selected.append((row, path))
        counts[row["class_id"]] += 1
    full_reference = manifest.get('scope') == 'full_requested_reference_learning_diagnostic_not_universal_detector_release'
    replay = manifest.get('scope') == 'all_class_reference_replay_development_not_release'
    limit = 5
    if full_reference or replay:
        specification = manifest.get('reference_specification', {})
        reference_classes={r['model_class_id'] for r in specification.get('point_mappings', [])}
        if (manifest.get('diagnostic_only') is not True
                or manifest.get('required_loss') != ('positive_boxes_and_explicit_reviewed_background' if replay
                                                     else 'synthetic_complete_known_composite_only')
                or len(specification.get('point_mappings', [])) != 54
                or len(specification.get('wiring_references', [])) != 12
                or len(manifest['authored_legend_synthetic_images']) > 512
                or not reference_classes.issubset(counts)
                or not replay and set(counts)!=reference_classes
                or replay and (manifest.get('all_eligible_entries') is not True
                               or len(manifest['classes'])!=129
                               or any(r['samples']<1 for r in manifest['classes']))):
            raise ValueError('Full reference diagnostic coverage or bounds differ')
        for row, _ in selected:
            values = (dataset/'labels/train'/f"{row['image_id']}.txt").read_text().split()
            x1,y1,x2,y2 = row['box']
            if (any(type(v) not in (int,float) or not math.isfinite(v) for v in row['box'])
                    or not 0<=x1<x2<=256 or not 0<=y1<y2<=256):
                raise ValueError('Full reference known composite box outside source tile')
            expected = [(x1+x2)/512,(y1+y2)/512,(x2-x1)/256,(y2-y1)/256]
            if (digest(dataset/'labels/train'/f"{row['image_id']}.txt") != row['label_sha256']
                    or len(values) != 5 or int(values[0]) != row['class_id']
                    or any(not math.isfinite(float(v)) or abs(float(v)-e)>1e-6 for v,e in zip(values[1:],expected))):
                raise ValueError('Full reference label or known composite box differs')
        limit = 129 if replay else 54
    # The full reference experiment increases class coverage, not memory: two
    # images per serial batch; never full-page or independent validation.
    if not selected or len(counts) > limit:
        raise ValueError("Expected bounded authored-legend learning check")
    model = YOLO(str(checkpoint))
    validate_model_classes(model, manifest['classes'])
    results = []
    output.mkdir(parents=True)
    for offset in range(0, len(selected), 2):
        batch = selected[offset:offset+2]
        images = []
        for row, path in batch:
            with Image.open(path) as opened:
                if opened.size != (256, 256):
                    raise ValueError("Synthetic dimensions differ")
                images.append(opened.convert("RGB"))
        predictions = model.predict(images, imgsz=image_size, conf=.50, device="cpu", batch=2,
                                    verbose=False, max_det=200)
        for (row, _), image, prediction in zip(batch, images, predictions):
            boxes = [{"bbox": box.xyxy[0].tolist(), "class_id": int(box.cls[0]),
                      "score": float(box.conf[0])} for box in prediction.boxes]
            target = {"source_box": row["box"], "class_id": row["class_id"]}
            localized = bool(match_targets([target], boxes, require_class=False))
            classified = bool(match_targets([target], boxes))
            pen = ImageDraw.Draw(image)
            pen.rectangle(row["box"], outline="green", width=2)
            for box in boxes:
                pen.rectangle(box["bbox"], outline="orange", width=1)
                pen.text((box["bbox"][0], box["bbox"][1]), str(box["class_id"]), fill="red")
            image.save(output / f"{row['image_id']}.png")
            image.close()
            results.append({"image_id": row["image_id"], "expected_class_id": row["class_id"],
                            "reference_id": row.get('reference_id'), "variant": row.get('variant'),
                            "localized": localized, "localized_and_classified": classified,
                            "predictions": boxes})
    summary = [{"class_id": cls, "tested": sum(r["expected_class_id"] == cls for r in results),
                "localized": sum(r["expected_class_id"] == cls and r["localized"] for r in results),
                "localized_and_classified": sum(r["expected_class_id"] == cls and r["localized_and_classified"] for r in results)}
               for cls in sorted(counts)]
    report = {"kind": "synthetic_reference_resubstitution_learning_check", "threshold": .50, 'model_input':image_size,
              'full_requested_reference_diagnostic':full_reference,
              'all_class_reference_replay':replay,
              "checkpoint_sha256": digest(checkpoint), "dataset_sha256": digest(dataset / "manifest.json"),
              "independent_accuracy": None, "real_page_accuracy": None, "summary": summary,
              "results": results}
    (output / "report.json").write_text(json.dumps(report, indent=2))
    return summary


def probe(dataset, source_root, checkpoint, output, *, threshold=0.25, inference_mode="tiles",
          shared_multiclass=False, candidate_shared=False, box_fusion=False):
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
    if shared_multiclass and candidate_shared:
        raise ValueError('Choose the active runtime or a candidate probe, not both')
    if box_fusion and not candidate_shared:
        raise ValueError('Explicit box-fusion probing requires the candidate shared runtime')
    if shared_multiclass or candidate_shared:
        from app.ai.floor_plan_interpretation import multiclass_symbol_detector as runtime
        if (threshold != runtime.THRESHOLD or (shared_multiclass and
                (digest(checkpoint) != runtime.CHECKPOINT_SHA256
                 or digest(dataset/"manifest.json") != runtime.TRAINING_DATASET_SHA256))):
            raise ValueError("Probe must use the exact shared runtime checkpoint, dataset, and threshold")
        validate_model_classes(model, manifest['classes'])
    use_shared_tiler = shared_multiclass or candidate_shared
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
        if use_shared_tiler:
            positions = runtime.shared.tile_positions(image.width, image.height, dual_phase=True)
        if len(positions) > 500:
            raise ValueError("Tile count exceeds bound")
        raw = []
        truncated = False
        start = time.perf_counter()
        if shared_multiclass:
            predictions, truncated = runtime.locate(np.asarray(image))
            raw = list(predictions)
        elif candidate_shared:
            candidate_classes={row['id']:(row['label'],row['legend_entry']) for row in manifest['classes']}
            predictions, truncated = runtime.shared.locate(np.asarray(image), catalog={
                'classes':candidate_classes, 'threshold':threshold, 'model':model,
                **({'box_fusion':True,'class_groups':runtime.model_class_groups(candidate_classes)}
                   if box_fusion else {})})
            raw = list(predictions)
        elif inference_mode == "full":
            result = model.predict(image, imgsz=1280, conf=threshold, classes=class_ids,
                                   device="cpu", verbose=False, max_det=500)[0]
            for box in result.boxes:
                raw.append({"bbox": [float(v) for v in box.xyxy[0].tolist()],
                            "class_id": int(box.cls[0]), "score": float(box.conf[0]),
                            "tile_origin": None})
        for offset in range(0, 0 if use_shared_tiler else len(positions), 16):
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
        # The opt-in candidate path already uses the exact serving fusion.
        # A second legacy NMS would alter its measured coordinates/provenance.
        predictions = raw if box_fusion else fuse(raw)
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
              "candidate_shared_tiler_without_activation": candidate_shared,
              "box_fusion": box_fusion,
              "tiling": {"size": 256, "stride": 192, "model_input": 320,
                         "second_phase_offset": 128 if use_shared_tiler else None,
                         "duplicate_suppression": ("same-class IoU >= 0.5 or nested IoS >= 0.85 with bounded centers"
                                                   if use_shared_tiler else "same-class IoU >= 0.5")},
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
    parser.add_argument("--candidate-shared", action="store_true")
    parser.add_argument("--box-fusion", action="store_true")
    parser.add_argument("--authored-synthetic", action="store_true")
    parser.add_argument('--synthetic-image-size',type=int,default=320,choices=(320,640))
    args = parser.parse_args()
    if args.authored_synthetic:
        if not args.dataset or not args.checkpoint or args.source_image or args.source_root:
            parser.error("Synthetic learning checks require dataset and checkpoint only")
        print(json.dumps(probe_authored_synthetic(args.dataset, args.checkpoint, args.output,
                                                  image_size=args.synthetic_image_size)))
    elif args.source_image:
        if args.source_root or bool(args.dataset) != bool(args.checkpoint):
            parser.error("Single-source candidate probes require both dataset and checkpoint, not source root")
        print(json.dumps(probe_unreviewed_image(args.source_image, args.output,
                                               checkpoint=args.checkpoint, dataset=args.dataset)))
    else:
        if not all((args.dataset, args.source_root, args.checkpoint)):
            parser.error("Reviewed probes require dataset, source root, and checkpoint")
        print(json.dumps(probe(args.dataset, args.source_root, args.checkpoint, args.output,
                               threshold=args.threshold, inference_mode=args.inference_mode,
                               shared_multiclass=args.shared_multiclass, candidate_shared=args.candidate_shared,
                               box_fusion=args.box_fusion)))
