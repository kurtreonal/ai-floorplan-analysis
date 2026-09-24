"""Read-only local detector probe on reviewed positives; not a gold evaluation."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image
from ultralytics import YOLO


def iou(left, right):
    x0, y0 = max(left[0], right[0]), max(left[1], right[1])
    x1, y1 = min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0, x1-x0) * max(0, y1-y0)
    a = (left[2]-left[0]) * (left[3]-left[1])
    b = (right[2]-right[0]) * (right[3]-right[1])
    return intersection/(a+b-intersection) if a+b-intersection else 0.0


def starts(length, tile, stride):
    points = list(range(0, max(1, length-tile+1), stride))
    last = max(0, length-tile)
    if points[-1] != last:
        points.append(last)
    return points


def fuse(predictions):
    retained = []
    for candidate in sorted(predictions, key=lambda item: -item["confidence"]):
        if not any(candidate["class"] == prior["class"]
                   and iou(candidate["bbox"], prior["bbox"]) >= 0.5 for prior in retained):
            retained.append(candidate)
    return retained


def run(manifest_path, image_path, checkpoint_path, output):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
    records = [r for r in manifest["records"] if r["source_sha256"] == source_hash
               and r["sheet_id"] == "sheet-14"]
    if len(records) != 2 or any(r["label"] != "Panelboard" for r in records):
        raise ValueError("Expected two source-verified reviewed positives")
    trained = checkpoint_path.parent.parent.parent / "reviewed-train.txt"
    if trained.exists() and "sheet-14" in trained.read_text(encoding="utf-8"):
        raise ValueError("Probe page appears in detector training")
    model = YOLO(str(checkpoint_path))
    with Image.open(image_path) as source:
        image = source.convert("RGB")
        result = model.predict(image, conf=0.5, imgsz=640, device="cpu", verbose=False)[0]
        tile_origins = [(x, y) for y in starts(image.height, 256, 224)
                        for x in starts(image.width, 256, 224)]
        if len(tile_origins) > 128:
            raise ValueError("Tile count exceeds bounded probe")
        tiles = [image.crop((x, y, x+256, y+256)) for x, y in tile_origins]
        tile_results = model.predict(tiles, conf=0.5, imgsz=128, device="cpu",
                                     batch=8, verbose=False)
    predictions = []
    for box in result.boxes:
        predictions.append({"bbox": [float(v) for v in box.xyxy[0].tolist()],
                            "class": model.names[int(box.cls[0])],
                            "confidence": float(box.conf[0])})
    full_page_predictions = predictions
    tiled_predictions = []
    for (x, y), tile_result in zip(tile_origins, tile_results):
        for box in tile_result.boxes:
            x0, y0, x1, y1 = [float(v) for v in box.xyxy[0].tolist()]
            tiled_predictions.append({"bbox": [x+x0, y+y0, x+x1, y+y1],
                                      "class": model.names[int(box.cls[0])],
                                      "confidence": float(box.conf[0])})
    predictions = fuse(tiled_predictions)
    targets = []
    for record in records:
        overlaps = [(iou(record["bbox"], candidate["bbox"]), candidate["class"])
                    for candidate in predictions]
        best = max(overlaps, default=(0.0, None))
        targets.append({"id": record["id"], "expected_class": record["label"],
                        "best_iou": best[0], "best_predicted_class": best[1],
                        "localized_iou_0_5": best[0] >= 0.5,
                        "classified_if_localized": best[1] == record["label"] if best[0] >= 0.5 else None})
    report = {"kind": "bounded_existing_detector_probe", "source_sha256": source_hash,
              "checkpoint_sha256": hashlib.sha256(checkpoint_path.read_bytes()).hexdigest(),
              "reviewed_positive_count": len(records), "full_page_predictions": full_page_predictions,
              "tile_count": len(tiles), "tiled_predictions_before_fusion": len(tiled_predictions),
              "predictions": predictions,
              "targets": targets,
              "reviewed_positive_localization_recall": sum(t["localized_iou_0_5"] for t in targets)/len(targets),
              "precision": None,
              "precision_unavailable_reason": "Page has partial annotations; unmatched predictions cannot be called false positives",
              "classification_accuracy": None if not any(t["localized_iou_0_5"] for t in targets)
              else sum(t["classified_if_localized"] for t in targets if t["localized_iou_0_5"])
                   / sum(t["localized_iou_0_5"] for t in targets),
              "limitations": ["Not project-verified gold evaluation", "Two reviewed positives only",
                              "Existing detector is a benchmark, not the trained VLM adapter"]}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"reviewed_positives": len(records), "predictions": len(predictions),
            "localization_recall": report["reviewed_positive_localization_recall"],
            "precision": report["precision"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.manifest, args.image, args.checkpoint, args.output)))
