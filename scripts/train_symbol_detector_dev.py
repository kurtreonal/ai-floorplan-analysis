"""Bounded local YOLO training diagnostic; not a production detector release."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import unicodedata
from collections import Counter

os.environ["YOLO_AUTOINSTALL"] = "false"
os.environ["YOLO_OFFLINE"] = "true"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from ultralytics import YOLO


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_restorative_replay(dataset, data):
    samplings=[data[key] for key in ('restorative_replay_sampling', 'power_switch_retention_replay') if key in data]
    if not samplings:return
    if (any(s.get('independent_examples_added')!=0 for s in samplings)
            or sum(len(s.get('replicas',[])) for s in samplings)>1600):
        raise ValueError('Restorative replicas are not independent data')
    seen=set()
    for row in (r for sampling in samplings for r in sampling['replicas']):
        name,parent=row['image_id'],row['sampling_parent']
        if (Path(name).name!=name or Path(parent).name!=parent or name in seen
                or not name.startswith('restored-replay-') or row.get('split')!='train'
                or row.get('independent_example') is not False):
            raise ValueError('Restorative replay identity differs')
        seen.add(name)
        for folder,suffix,key in (('images/train','png','image_sha256'),('labels/train','txt','label_sha256')):
            if (digest(dataset/folder/f'{name}.{suffix}')!=row[key]
                    or digest(dataset/folder/f'{parent}.{suffix}')!=row[key]):
                raise ValueError('Restorative replay bytes differ from original train window')
        values={int(line.split()[0]) for line in (dataset/'labels/train'/f'{name}.txt').read_text().splitlines()}
        if row['class_id'] not in values:raise ValueError('Restorative class is not supervised')


def validate_frozen_reference_replay(dataset,data):
    """Fail before model loading on altered, extra or missing replay windows."""
    if data.get('scope')!='all_class_reference_replay_development_not_release':return
    if (data.get('diagnostic_only') is not True or data.get('all_eligible_entries') is not True
            or len(data['classes'])!=129 or any(type(r['id']) is not int for r in data['classes'])
            or {r['id'] for r in data['classes']}!=set(range(129))
            or data.get('required_loss')!='positive_boxes_and_explicit_reviewed_background'):
        raise ValueError('Exact frozen development replay contract required')
    from prepare_pec_replay import inventory
    rows=inventory(dataset,data,class_count=129)
    for folder,suffix in (('images/train','.png'),('labels/train','.txt')):
        entries=list((dataset/folder).iterdir())
        if (any(not p.is_file() or p.is_symlink() or p.suffix!=suffix for p in entries)
                or {p.stem for p in entries}!=set(rows)):
            raise ValueError('Replay directory differs from immutable manifest')
    counts=Counter(cls for row in rows.values() for cls in row['classes'])
    if (set(counts)!=set(range(129)) or any(type(r['samples']) is not int or r['samples']!=counts[r['id']]
                                           for r in data['classes'])):
        raise ValueError('Replay supervision counts changed')


def train(dataset, base, output, *, epochs=3, image_size=320, fine_tune=False,
          partial_label=False, learning_rate=None, warm_start=None, batch_size=8):
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
    if type(batch_size) is not int or batch_size not in (1, 2, 4, 8):
        raise ValueError("Training batch exceeds bounded local configuration")
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
    from prepare_authorized_pdf_detection import validate_training_sources
    allowed_source_hashes = validate_training_sources(dataset, data)
    validate_restorative_replay(dataset,data)
    validate_frozen_reference_replay(dataset,data)
    synthetic = data.get('authored_legend_synthetic_images', [])
    diagnostic = data.get('diagnostic_only') is True
    if data.get('required_loss') == 'synthetic_complete_known_composite_only' and (
            not diagnostic or partial_label or not synthetic or data.get('reviewed_targets')
            or data.get('images') or data.get('reviewed_background_images')):
        raise ValueError('Complete synthetic supervision must contain only construction-known diagnostic images')
    if synthetic:
        limit = 512 if data.get('additional_training_authorizations') else 256
        if len(synthetic) > limit or len({row['image_id'] for row in synthetic}) != len(synthetic):
            raise ValueError('Synthetic target bounds or identities differ')
        for row in synthetic:
            name = row['image_id']
            if (Path(name).name != name or not name.startswith('authored-legend-')
                    or row.get('human_review_claim') is not False
                    or row.get('label_origin') != 'known_synthetic_composite_geometry'
                    or row.get('source_sha256') not in allowed_source_hashes
                    or row.get('split') != 'train'
                    or digest(dataset / 'images/train' / f'{name}.png') != row['image_sha256']
                    or digest(dataset / 'labels/train' / f'{name}.txt') != row['label_sha256']):
                raise ValueError('Synthetic supervision or source provenance differs')
    output.parent.mkdir(parents=True, exist_ok=True)
    metadata = {"kind": "local_development_symbol_detector_diagnostic",
                "base_sha256": digest(warm_start or base), "dataset_manifest_sha256": digest(dataset / "manifest.json"),
                "warm_start": str(warm_start) if warm_start else None,
                "optimizer_resume": False,
                "dataset_path": str(dataset.resolve()), "epochs": epochs, "image_size": image_size,
                "fine_tune": fine_tune,
                  "partial_label": partial_label,
                  "reviewed_background_sampling": data.get('reviewed_background_sampling', 'uniform_budget'),
                "required_loss": data.get("required_loss"),
                "learning_rate_override": learning_rate,
                "batch_size": batch_size,
                'effective_batch_target':batch_size if diagnostic else 64,
                'diagnostic_only':diagnostic,
                'synthetic_complete_background':data.get('synthetic_complete_background') is True,
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
        actual_names = {i: unicodedata.normalize('NFKD', name).encode('ascii','ignore').decode()
                        for i, name in model.names.items()}
        if actual_names != expected_names:
            raise ValueError('Warm-start numeric legend identities do not match the dataset')
    model.train(data=str((dataset / "data.yaml").resolve()), epochs=epochs,
                imgsz=image_size, batch=batch_size, workers=0, device="cpu", project=str(output.parent.resolve()),
                nbs=batch_size if diagnostic else 64,
                name=output.name, exist_ok=True, val=False, plots=False, save=True, save_period=1,
                pretrained=True, cache=False, mosaic=0, mixup=0, copy_paste=0,
                fliplr=0, flipud=0, degrees=0, translate=0, scale=0,
                optimizer="AdamW" if fine_tune or balanced else "auto",
                lr0=learning_rate if learning_rate is not None else 0.001 if balanced else 0.0001 if fine_tune else 0.01,
                lrf=0.1 if fine_tune or balanced else 0.01,
                warmup_epochs=1 if balanced else 3,
                warmup_bias_lr=(learning_rate or 0.0001) if diagnostic or fine_tune else 0.1,
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
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--warm-start", type=Path, help="Continue same-dataset weights in a new immutable run; optimizer resets")
    args = parser.parse_args()
    print(json.dumps(train(args.dataset, args.base, args.output,
                           epochs=args.epochs, image_size=args.image_size,
                           fine_tune=args.fine_tune, partial_label=args.partial_label,
                           learning_rate=args.learning_rate, warm_start=args.warm_start,
                           batch_size=args.batch_size)))
