"""Bounded offline multi-class adaptation from hash-bound reviewed annotations.

No source matching, downloads, activation, automatic approval, or training on
unannotated background. Historical development trainers remain unchanged.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import unicodedata

os.environ["YOLO_AUTOINSTALL"] = "false"
os.environ["YOLO_OFFLINE"] = "true"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

KIND = "ved_reviewed_multiclass_training_v1"
LOSS = "reviewed_boxes_allowed_subtypes_and_explicit_background"


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def normalized_names(classes):
    return {r["id"]: unicodedata.normalize("NFKD", r["label"]).encode("ascii", "ignore").decode()
            for r in classes}


def normalized_checkpoint_names(names):
    return {i: unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode()
            for i, label in names.items()}


def validate_reviewed_provenance(dataset, data):
    from prepare_reviewed_plan_training import review_targets, tile_rows, technical_decisions
    from PIL import Image
    snapshots = {
        "saved-session-snapshot.json": "saved_session_sha256",
        "legend-registry-snapshot.json": "legend_registry_sha256",
        "local-training-authorization.json": "authorization_sha256",
        "parent-manifest-snapshot.json": "parent_manifest_sha256",
    }
    for filename, key in snapshots.items():
        path = dataset / filename
        if not path.is_file() or path.is_symlink() or digest(path) != data.get(key):
            raise ValueError("Reviewed source snapshot differs from authorized manifest")
    session = json.loads((dataset / "saved-session-snapshot.json").read_text(encoding="utf-8"))
    registry = json.loads((dataset / "legend-registry-snapshot.json").read_text(encoding="utf-8"))
    auth = json.loads((dataset / "local-training-authorization.json").read_text(encoding="utf-8"))
    if auth != data["authorization"] or auth.get("saved_session_sha256") != data["saved_session_sha256"]:
        raise ValueError("Authorization is not bound to reviewed source snapshot")
    sheets = data.get("reviewed_plan_sheets", [])
    sources = {}
    for sheet in sheets:
        stem = sheet["sheet_id"]
        if Path(stem).name != stem or "/" in stem or "\\" in stem or stem in (".", ".."):
            raise ValueError("Unsafe reviewed source identity")
        for suffix, key in ((".png", "source_sha256"), ("-normalized.png", "normalized_image_sha256")):
            path = dataset / "sources" / f"{stem}{suffix}"
            if not path.is_file() or path.is_symlink() or digest(path) != sheet[key]:
                raise ValueError("Reviewed source pixels changed")
        sources[sheet["source_sha256"]] = dataset / "sources" / f"{stem}.png"
        with Image.open(dataset / "sources" / f"{stem}-normalized.png") as image:
            size = list(image.size)
        if (size != sheet["normalized_size"] or sheet["review_to_training_source_scale"] !=
                [size[0]/sheet["source_width"], size[1]/sheet["source_height"]]):
            raise ValueError("Reviewed source-to-training transform changed")
    excluded, uncertain = technical_decisions(data.get("technical_review_proposals"), session,
                                             data["saved_session_sha256"])
    targets, _, reconciled = review_targets(session, registry["legend_catalog"], sources,
        auth["groups"], data["classes"], excluded, uncertain)
    if targets != data.get("reviewed_plan_targets") or len(reconciled) != len(sheets):
        raise ValueError("Reviewed target classes, subtype sets or coordinates changed")
    for expected, stored in zip(reconciled, sheets):
        if any(stored.get(key) != value for key, value in expected.items() if key != "source_path"):
            raise ValueError("Reviewed source frame or project split changed")
    for row in data["training_image_records"]:
        if row.get("source_kind") != "latest_user_reviewed_plan":
            continue
        sheet = next((s for s in sheets if s["sheet_id"] == row["sheet_id"]), None)
        if sheet is None or any(row.get(k) != sheet[k] for k in
                ("project_id", "split", "source_sha256", "review_to_training_source_scale")):
            raise ValueError("Reviewed tile source frame or split changed")
        members = [t for t in targets if t["sheet_id"] == sheet["sheet_id"]]
        expected = tile_rows(members, row["tile_origin"], sheet["review_to_training_source_scale"])
        if (row.get("supervised_record_ids") != [t["record_id"] for t in expected]
                or row["allowed_class_ids"] != [t["allowed_class_ids"] for t in expected]):
            raise ValueError("Reviewed subtype sets or target row identities changed")
        lines = (dataset / "labels/train" / f"{row['image_id']}.txt").read_text().splitlines()
        if len(lines) != len(expected):
            raise ValueError("Reviewed tile positives were lost")
        for line, target in zip(lines, expected):
            actual = list(map(float, line.split()))
            a, b, c, d = target["local_box"]
            desired = [target["class_id"], (a+c)/512, (b+d)/512, (c-a)/256, (d-b)/256]
            if any(abs(x-y) > 1e-7 for x, y in zip(actual, desired)):
                raise ValueError("Reviewed box transform or serialized class changed")


def validate_dataset(dataset, base, parent_manifest):
    data = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    parent = json.loads(parent_manifest.read_text(encoding="utf-8"))
    auth = data.get("authorization", {})
    classes = data.get("classes", [])
    if (data.get("kind") != KIND or data.get("required_loss") != LOSS
            or data.get("base_model_sha256") != digest(base)
            or data.get("parent_manifest_sha256") != digest(parent_manifest)
            or auth.get("local_development_training") is not True
            or auth.get("production_approval") is not False
            or not isinstance(auth.get("user_statement"), str) or not auth["user_statement"].strip()
            or len(auth.get("saved_session_sha256", "")) != 64):
        raise ValueError("Missing hash-bound reviewed development authorization")
    parent_classes = parent["classes"]
    identity = lambda rows: [(r["id"], r["label"], r["legend_entry"]) for r in rows]
    if (not len(parent_classes) <= len(classes) <= 256
            or [r.get("id") for r in classes] != list(range(len(classes)))
            or len({r["legend_entry"] for r in classes}) != len(classes)
            or identity(classes[:len(parent_classes)]) != identity(parent_classes)):
        raise ValueError("Existing numeric class identities changed")
    rows = data.get("training_image_records", [])
    if not rows or len(rows) > 20_000 or len({r["image_id"] for r in rows}) != len(rows):
        raise ValueError("Invalid bounded image inventory")
    supervised = set()
    image_supervision = {}
    for row in rows:
        stem = row["image_id"]
        if Path(stem).name != stem or "/" in stem or "\\" in stem or stem in (".", ".."):
            raise ValueError("Unsafe training image identity")
        image = dataset / "images/train" / f"{stem}.png"
        label = dataset / "labels/train" / f"{stem}.txt"
        if image.is_symlink() or label.is_symlink() or digest(image) != row["image_sha256"] or digest(label) != row["label_sha256"]:
            raise ValueError("Training artifacts differ from reviewed manifest")
        lines = [line.split() for line in label.read_text().splitlines() if line.strip()]
        sets = row["allowed_class_ids"]
        image_supervision[stem] = {i for ids in sets for i in ids}
        if len(lines) != len(sets):
            raise ValueError("Allowed sets differ from YOLO label row order")
        for values, ids in zip(lines, sets):
            if (len(values) != 5 or not values[0].isdigit() or not isinstance(ids, list)
                    or not 1 <= len(ids) <= 8 or len(set(ids)) != len(ids)
                    or any(type(i) is not int or not 0 <= i < len(classes) for i in ids)
                    or int(values[0]) not in ids):
                raise ValueError("Invalid subtype set or label representative")
            x, y, width, height = map(float, values[1:])
            if (not all(math.isfinite(v) for v in (x, y, width, height))
                    or not 0 < width <= 1 or not 0 < height <= 1
                    or not width / 2 - 1e-7 <= x <= 1 - width / 2 + 1e-7
                    or not height / 2 - 1e-7 <= y <= 1 - height / 2 + 1e-7):
                raise ValueError("Label clipped or outside context tile")
            supervised.update(ids)
    inventory = {r["image_id"] for r in rows}
    for folder, suffix in (("images/train", ".png"), ("labels/train", ".txt")):
        files = list((dataset / folder).iterdir())
        if any(not p.is_file() or p.suffix != suffix for p in files) or {p.stem for p in files} != inventory:
            raise ValueError("Dataset directory includes unmanifested examples")
    # Every original class must remain represented in real or authorized replay.
    if not set(range(len(parent_classes))) <= supervised:
        raise ValueError("Prior class replay was lost")
    train_list = dataset / "train-images.txt"
    if train_list.exists():
        selected = set()
        folder = (dataset / "images/train").resolve()
        for value in train_list.read_text(encoding="utf-8").splitlines():
            if not value.strip():
                continue
            path = Path(value).resolve()
            if path.parent != folder or path.suffix != ".png" or path.stem not in inventory:
                raise ValueError("Training sampler escapes reviewed image inventory")
            selected.add(path.stem)
        if not selected or not set(range(len(parent_classes))) <= {
                i for stem in selected for i in image_supervision[stem]}:
            raise ValueError("Selected training sampler lost prior class replay")
    for row in data.get("reviewed_background_images", []):
        if row["image_id"] not in inventory or row["sha256"] != digest(dataset / "images/train" / f"{row['image_id']}.png"):
            raise ValueError("Explicit parent negative changed")
        if (dataset / "labels/train" / f"{row['image_id']}.txt").read_text().strip():
            raise ValueError("Negative flag conflicts with positive labels")
    validate_reviewed_provenance(dataset, data)
    return data


def effective_training_inputs(dataset, data, output, replay_policy):
    """Full replay reuses validated authorized rows, never adds pseudo-labels."""
    if replay_policy == "manifest_sampler":
        return dataset / "data.yaml", {"replay_policy": replay_policy}
    if replay_policy != "full_authorized_pool":
        raise ValueError("Unsupported replay policy")
    import yaml
    listing = output / "full-replay-images.txt"
    images = sorted(r["image_id"] for r in data["training_image_records"])
    listing.write_text("\n".join(str((dataset / "images/train" / f"{stem}.png").resolve())
        for stem in images) + "\n", encoding="utf-8")
    config = output / "full-replay-data.yaml"
    config.write_text(yaml.safe_dump(dict(path=dataset.resolve().as_posix(),
        train=listing.resolve().as_posix(), val=listing.resolve().as_posix(),
        names=normalized_names(data["classes"])), sort_keys=False), encoding="utf-8")
    return config, dict(replay_policy=replay_policy, effective_training_images=len(images),
        effective_image_list_sha256=digest(listing), effective_training_config_sha256=digest(config),
        supervision="unchanged authorized rows; no new background or model pseudo-labels")


def train(dataset, base, parent_manifest, output, *, epochs=2, image_size=320,
          batch_size=4, learning_rate=.0001, seed=20261014, freeze=10, warm_start=None,
          replay_policy="manifest_sampler"):
    if output.exists():
        raise FileExistsError("Training runs are immutable; use a new output revision")
    if (type(epochs) is not int or not 1 <= epochs <= 20 or image_size not in (320, 480, 640)
            or batch_size not in (1, 2, 4, 8) or not .00001 <= learning_rate <= .001
            or type(seed) is not int or type(freeze) is not int or not 0 <= freeze <= 20
            or replay_policy not in ("manifest_sampler", "full_authorized_pool")):
        raise ValueError("Bounded diagnostic settings exceeded")
    data = validate_dataset(dataset, base, parent_manifest)
    import torch
    from ultralytics import YOLO
    from app.ai.symbol_detection.reviewed_set_training import ReviewedSetTrainer
    torch.set_num_threads(8)
    if warm_start is not None:
        previous = json.loads((warm_start.parent.parent / "run-manifest.json").read_text(encoding="utf-8"))
        if (previous.get("dataset_manifest_sha256") != digest(dataset / "manifest.json")
                or previous.get("checkpoint_sha256") != digest(warm_start)
                or previous.get("activation") is not False):
            raise ValueError("Warm-start checkpoint is not hash-bound to this reviewed dataset")
    model = YOLO(str(warm_start or base))
    if normalized_checkpoint_names(model.names) != normalized_names(data["classes"]):
        raise ValueError("Initialized checkpoint head differs from source class identities")
    metadata = {"kind": "reviewed_multiclass_offline_training_run_v1",
                "checkpoint_initialization_sha256": digest(base), "dataset_manifest_sha256": digest(dataset / "manifest.json"),
                "parent_manifest_sha256": digest(parent_manifest), "class_mapping": data["classes"],
                "required_loss": LOSS, "epochs": epochs, "image_size": image_size, "batch_size": batch_size,
                "learning_rate": learning_rate, "seed": seed, "freeze": freeze,
                "runtime": {"torch": torch.__version__, "device": "cpu", "threads": 8, "workers": 0},
                "activation": False, "production_approval": False, "optimizer_resume": False,
                "warm_start_sha256": digest(warm_start) if warm_start else None,
                "training_source_performance_not_generalization": True,
                "geometric_augmentation": "reviewed_letterbox_hsv_format_v1; no affine size filter or row loss",
                "unknown_pixels": "ignored, not confirmed background"}
    metadata["ordinary_validation"] = {
        "enabled": False, "metrics": "NOT TESTED",
        "fitness": "constant_zero_checkpoint_serialization_sentinel_not_quality"}
    output.mkdir(parents=True)
    training_config, replay_metadata = effective_training_inputs(dataset, data, output, replay_policy)
    metadata.update(replay_metadata)
    (output / "run-manifest.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    model.train(data=str(training_config.resolve()), trainer=ReviewedSetTrainer,
                epochs=epochs, imgsz=image_size, batch=batch_size, nbs=batch_size,
                workers=0, device="cpu", project=str(output.parent.resolve()), name=output.name,
                exist_ok=True, val=False, plots=False, save=True, save_period=1, pretrained=True,
                cache=False, optimizer="AdamW", lr0=learning_rate, lrf=.1, freeze=freeze,
                warmup_epochs=1, warmup_bias_lr=learning_rate, seed=seed, deterministic=True,
                mosaic=0, mixup=0, copy_paste=0, cutmix=0, close_mosaic=0,
                fliplr=0, flipud=0, degrees=0, perspective=0, shear=0,
                translate=0, scale=0, hsv_h=0, hsv_s=0, hsv_v=.1, cls_remap=False)
    last = output / "weights/last.pt"
    reloaded = YOLO(str(last))
    if reloaded.names != model.names:
        raise ValueError("Serialized detector class mapping changed")
    metadata.update({"checkpoint_sha256": digest(last), "reload_class_mapping_exact": True,
                     "ultralytics": __import__("ultralytics").__version__})
    (output / "run-manifest.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {"checkpoint_sha256": metadata["checkpoint_sha256"], "reload_class_mapping_exact": True,
            "activation": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "base", "parent-manifest", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--image-size", type=int, default=320)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=.0001)
    parser.add_argument("--seed", type=int, default=20261014)
    parser.add_argument("--freeze", type=int, default=10)
    parser.add_argument("--warm-start", type=Path)
    parser.add_argument("--replay-policy", choices=("manifest_sampler", "full_authorized_pool"),
                        default="manifest_sampler")
    args = parser.parse_args()
    print(json.dumps(train(args.dataset, args.base, args.parent_manifest, args.output,
                           epochs=args.epochs, image_size=args.image_size, batch_size=args.batch_size,
                           learning_rate=args.learning_rate, seed=args.seed, freeze=args.freeze,
                           warm_start=args.warm_start, replay_policy=args.replay_policy)))
