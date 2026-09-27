"""Build positive-only, source-verified local detector diagnostics.

Masked mode exposes one reviewed symbol and a narrow context collar. Full
context mode requires the matching partial-label loss; unreviewed pixels must
never become YOLO background truth. Neither mode is a gold dataset.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import unicodedata

from PIL import Image


DEFAULT_CLASSES = ("Troffer lights", "Smoke detector", "Pull station")
# The two additional reference plans have unresolved underlying-source rights.
# Annotation ownership alone does not resolve permission to train on their pixels.
UNRESOLVED_REFERENCE_SHEETS = frozenset({"sheet-51", "sheet-52"})


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build(manifest_path, source_root, output, labels=DEFAULT_CLASSES, base_weights=None,
          context_mode="masked"):
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get("schema") != "ved-reviewed-symbol-crops-v1":
        raise ValueError("Expected source-verified reviewed crop manifest")
    if output.exists():
        raise FileExistsError("Refusing to replace an existing dataset version")
    if context_mode not in {"masked", "full_partial"}:
        raise ValueError("Unknown training context")
    selected = [r for r in manifest["records"] if r["label"] in labels and r["split"] == "train"]
    rows = [r for r in selected if r["sheet_id"] not in UNRESOLVED_REFERENCE_SHEETS]
    if not rows or len({r["label"] for r in rows}) != len(labels):
        raise ValueError("Selected labels are not all represented by reviewed training records")
    # Drawing IDs remain distinct even when the visible names coincide.
    identities = sorted({(r["legend_entry"], r["label"]) for r in rows})
    if base_weights is not None:
        from ultralytics import YOLO
        names = YOLO(str(base_weights)).names
        by_name = {}
        for index, name in names.items():
            by_name.setdefault(name, []).append(index)
        if any(len(by_name.get(label, [])) != 1 for _, label in identities):
            raise ValueError("Every selected name must map to exactly one existing model class")
        classes = {identity: by_name[identity[1]][0] for identity in identities}
    else:
        classes = {identity: index for index, identity in enumerate(identities)}
        names = {index: identity[1] for identity, index in classes.items()}
    source_by_hash = {}
    for path in sorted(source_root.rglob("*")):
        if not path.is_file() or path.is_symlink() or any(
            part in {"node_modules", ".git", "training_dataset", "backups", ".temp"}
            for part in path.parts
        ):
            continue
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png"} or path.stat().st_size > 25_000_000:
            continue
        source_by_hash[digest(path)] = path
    required = {r["source_sha256"] for r in rows}
    if not required <= source_by_hash.keys():
        raise ValueError(f"Missing {len(required - source_by_hash.keys())} exact source images")
    output.mkdir(parents=True)
    (output / "images/train").mkdir(parents=True)
    (output / "labels/train").mkdir(parents=True)
    sheet_rows = defaultdict(list)
    for row in rows:
        sheet_rows[row["source_sha256"]].append(row)
    audit = []
    for source_hash, members in sheet_rows.items():
        with Image.open(source_by_hash[source_hash]) as opened:
            source = opened.convert("RGB")
        if source.width * source.height > 60_000_000 or max(source.size) > 10_000:
            raise ValueError("Source exceeds bounded image dimensions")
        for row in members:
            x1, y1, x2, y2 = row["bbox"]
            if not (0 <= x1 < x2 <= source.width and 0 <= y1 < y2 <= source.height):
                raise ValueError("Reviewed box lies outside exact source")
            width, height = x2 - x1, y2 - y1
            # Cap the visible collar. The rest is masked, never called negative evidence.
            collar = min(20, max(6, round(min(width, height) * 0.3)))
            tile_w = 256 if context_mode == "full_partial" else max(128, round(width * 2.0))
            tile_h = 256 if context_mode == "full_partial" else max(128, round(height * 2.0))
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            left, top = round(cx - tile_w / 2), round(cy - tile_h / 2)
            image = Image.new("RGB", (tile_w, tile_h), "white")
            src_rect = ((max(0, left), max(0, top),
                         min(source.width, left + tile_w), min(source.height, top + tile_h))
                        if context_mode == "full_partial" else
                        (max(0, x1 - collar), max(0, y1 - collar),
                         min(source.width, x2 + collar), min(source.height, y2 + collar)))
            image.paste(source.crop(src_rect), (src_rect[0] - left, src_rect[1] - top))
            name = row["id"]
            image_path = output / "images/train" / f"{name}.png"
            image.save(image_path)
            local = (x1 - left, y1 - top, x2 - left, y2 - top)
            if not (0 <= local[0] < local[2] <= tile_w and 0 <= local[1] < local[3] <= tile_h):
                raise ValueError("Target clipping in diagnostic tile")
            class_id = classes[(row["legend_entry"], row["label"])]
            xywh = ((local[0] + local[2]) / (2 * tile_w),
                    (local[1] + local[3]) / (2 * tile_h), width / tile_w, height / tile_h)
            label_path = output / "labels/train" / f"{name}.txt"
            label_path.write_text(f"{class_id} " + " ".join(f"{v:.8f}" for v in xywh) + "\n")
            audit.append({"record_id": name, "sheet_id": row["sheet_id"],
                          "source_sha256": source_hash, "legend_entry": row["legend_entry"],
                          "class_id": class_id, "source_box": row["bbox"],
                          "image_sha256": digest(image_path), "label_sha256": digest(label_path),
                          "collar_pixels": collar if context_mode == "masked" else None,
                          "split": "training_diagnostic_only"})
    # Display names in the training YAML are ASCII-only to prevent Ultralytics
    # from downloading a Unicode font. Exact catalog names stay in the manifest.
    display_names = {i: unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode()
                     for i, label in names.items()}
    yaml = (f"path: {output.resolve().as_posix()}\ntrain: images/train\n"
            "val: images/train\n"
            f"nc: {len(names)}\nnames:\n" + "".join(
                f"  {i}: {json.dumps(label)}\n" for i, label in sorted(display_names.items())))
    (output / "data.yaml").write_text(yaml)
    report = {"kind": "positive_only_masked_symbol_detection_diagnostic_v1",
              "source_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
              "context_mode": context_mode,
              "required_loss": ("positive_and_local_negative_only" if context_mode == "full_partial"
                                else "standard"),
              "reference_rights_exclusions": {"sheet_ids": sorted(UNRESOLVED_REFERENCE_SHEETS),
                                               "selected_records_excluded": len(selected) - len(rows)},
              "base_model_sha256": digest(base_weights) if base_weights else None,
              "classes": [{"id": i, "legend_entry": key, "label": label,
                           "samples": sum(r["legend_entry"] == key for r in rows)}
                          for (key, label), i in classes.items()],
              "sheets": dict(Counter(r["sheet_id"] for r in rows)),
              "related_groups": dict(Counter(r["group"] for r in rows)),
              "images": audit,
              "warnings": ["The val path repeats training images; no generalization metric is available.",
                           ("Full-context pixels outside a narrow target collar are unlabeled and require an ignore loss."
                            if context_mode == "full_partial" else
                            "Only reviewed positive symbols and narrow collars are visible; other page pixels are masked."),
                           "This diagnostic does not establish performance on unmasked full pages."]}
    (output / "manifest.json").write_text(json.dumps(report, indent=2))
    return {"images": len(audit), "classes": len(classes), "sheets": len(report["sheets"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", action="append", dest="labels")
    parser.add_argument("--base-weights", type=Path)
    parser.add_argument("--context-mode", choices=("masked", "full_partial"), default="masked")
    args = parser.parse_args()
    print(json.dumps(build(args.manifest, args.source_root, args.output,
                           tuple(args.labels) if args.labels else DEFAULT_CLASSES,
                           base_weights=args.base_weights, context_mode=args.context_mode)))
