"""Bounded local YOLO training diagnostic; not a production detector release."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import unicodedata

os.environ["YOLO_AUTOINSTALL"] = "false"
os.environ["YOLO_OFFLINE"] = "true"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from ultralytics import YOLO


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def train(dataset, base, output, *, epochs=3, image_size=320, fine_tune=False,
          partial_label=False, learning_rate=None, warm_start=None):
    if output.exists():
        raise FileExistsError("Refusing to replace an existing training run; use the saved last.pt to resume")
    if not base.is_file() or not (dataset / "manifest.json").is_file():
        raise ValueError("Existing local base weights and dataset manifest are required")
    data = json.loads((dataset / "manifest.json").read_text())
    if data.get("kind") != "positive_only_masked_symbol_detection_diagnostic_v1":
        raise ValueError("Wrong dataset type")
    if (data.get("required_loss") in {"positive_and_local_negative_only",
                                     "positive_and_reviewed_box_only",
                                     "positive_boxes_and_explicit_reviewed_background"}) != partial_label:
        raise ValueError("Dataset context and partial-label loss must match")
    if data.get("base_model_sha256") and data["base_model_sha256"] != digest(base):
        raise ValueError("Dataset class IDs do not match the pinned base model")
    if warm_start is not None:
        parent = json.loads((warm_start.parent.parent / 'run-manifest.json').read_text())
        if parent.get('dataset_manifest_sha256') != digest(dataset/'manifest.json'):
            raise ValueError('Warm-start checkpoint belongs to another dataset revision')
    if not 1 <= epochs <= 20 or image_size not in (320, 480, 640):
        raise ValueError("Training bounds exceeded")
    if learning_rate is not None and not 0.00001 <= learning_rate <= 0.001:
        raise ValueError("Learning rate exceeds bounded fine-tuning range")
    if data.get("required_loss") == "positive_boxes_and_explicit_reviewed_background":
        for row in data["reviewed_background_images"]:
            name = row["image_id"]
            if Path(name).name != name or not name.startswith("reviewed-negative-"):
                raise ValueError("Invalid reviewed background identity")
            if (digest(dataset / "images/train" / f"{name}.png") != row["sha256"]
                    or (dataset / "labels/train" / f"{name}.txt").read_text().strip()):
                raise ValueError("Reviewed negative image or labels changed")
    output.parent.mkdir(parents=True, exist_ok=True)
    metadata = {"kind": "local_development_symbol_detector_diagnostic",
                "base_sha256": digest(warm_start or base), "dataset_manifest_sha256": digest(dataset / "manifest.json"),
                "warm_start": str(warm_start) if warm_start else None,
                "optimizer_resume": False,
                "dataset_path": str(dataset.resolve()), "epochs": epochs, "image_size": image_size,
                "fine_tune": fine_tune,
                "partial_label": partial_label,
                "required_loss": data.get("required_loss"),
                "learning_rate_override": learning_rate,
                "class_remapping": "disabled; preserve numeric legend-ID order",
                "validation_status": "training-resubstitution only; no independent validation",
                "license_warning": "Ultralytics weights/code are AGPL-3.0 by default; no production release authorization"}
    # Keep the provenance beside the checkpoint even if the run is interrupted.
    output.mkdir()
    (output / "run-manifest.json").write_text(json.dumps(metadata, indent=2))
    model = YOLO(str(warm_start or base))
    if partial_label:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
        from app.ai.symbol_detection.partial_label_training import PartialLabelTrainer
        if data.get("required_loss") == "positive_and_reviewed_box_only":
            from app.ai.symbol_detection.partial_label_training import ReviewedBoxOnlyTrainer
            PartialLabelTrainer = ReviewedBoxOnlyTrainer
        elif data.get("required_loss") == "positive_boxes_and_explicit_reviewed_background":
            from app.ai.symbol_detection.partial_label_training import ReviewedBackgroundTrainer
            PartialLabelTrainer = ReviewedBackgroundTrainer
    else:
        PartialLabelTrainer = None
    balanced = data.get("all_eligible_entries") is True
    if balanced:
        expected = {row["id"] for row in data["classes"]}
        if expected != set(range(len(data["classes"]))) or any(row["samples"] < 1 for row in data["classes"]):
            raise ValueError("Every eligible class must have supervised examples")
        if len(model.names) != len(expected):
            raise ValueError("Balanced warm-start checkpoint has the wrong class head")
        expected_names = {r['id']: unicodedata.normalize('NFKD', r['label']).encode('ascii','ignore').decode()
                          for r in data['classes']}
        if model.names != expected_names:
            raise ValueError('Warm-start numeric legend identities do not match the dataset')
    model.train(data=str((dataset / "data.yaml").resolve()), epochs=epochs,
                imgsz=image_size, batch=8, workers=0, device="cpu", project=str(output.parent.resolve()),
                name=output.name, exist_ok=True, val=False, plots=False, save=True, save_period=1,
                pretrained=True, cache=False, mosaic=0, mixup=0, copy_paste=0,
                fliplr=0, flipud=0, degrees=0, translate=0, scale=0,
                optimizer="AdamW" if fine_tune or balanced else "auto",
                lr0=learning_rate if learning_rate is not None else 0.001 if balanced else 0.0001 if fine_tune else 0.01,
                lrf=0.1 if fine_tune or balanced else 0.01,
                warmup_epochs=1 if balanced else 3,
                hsv_h=0, hsv_s=0, hsv_v=.15,
                cls_remap=False,
                trainer=PartialLabelTrainer)
    best = output / "weights/best.pt"
    last = output / "weights/last.pt"
    return {"last_sha256": digest(last) if last.exists() else None,
            "best_sha256": digest(best) if best.exists() else None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--image-size", type=int, default=320)
    parser.add_argument("--fine-tune", action="store_true")
    parser.add_argument("--partial-label", action="store_true")
    parser.add_argument("--learning-rate", type=float)
    parser.add_argument("--warm-start", type=Path, help="Continue same-dataset weights in a new immutable run; optimizer resets")
    args = parser.parse_args()
    print(json.dumps(train(args.dataset, args.base, args.output,
                           epochs=args.epochs, image_size=args.image_size,
                           fine_tune=args.fine_tune, partial_label=args.partial_label,
                           learning_rate=args.learning_rate, warm_start=args.warm_start)))
