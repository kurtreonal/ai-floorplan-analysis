"""Build positive-only, source-verified local detector diagnostics.

Masked mode exposes one reviewed symbol and a narrow context collar. Full
context mode requires the matching partial-label loss; unreviewed pixels must
never become YOLO background truth. Neither mode is a gold dataset.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
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


def intersection(a, b):
    return (max(0, min(a[2], b[2]) - max(a[0], b[0]))
            * max(0, min(a[3], b[3]) - max(a[1], b[1])))


def overlapping_reviewed_records(members):
    """Conservatively quarantine ambiguous/duplicate boxes, never rewrite them."""
    excluded = set()
    pairs = []
    for index, row in enumerate(members):
        a = row["bbox"]
        for other in members[index + 1:]:
            b = other["bbox"]
            overlap = intersection(a, b)
            union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - overlap
            if union > 0 and overlap / union >= 0.5:
                excluded.update((row["id"], other["id"]))
                pairs.append({"record_ids": [row["id"], other["id"]],
                              "legend_entries": [row["legend_entry"], other["legend_entry"]],
                              "iou": overlap / union,
                              "decision": "assistant_experiment_exclusion_not_label_correction"})
    return excluded, pairs


def tile_supervision(members, tile, excluded):
    """Include visible reviewed neighbors; avoid negative collars on known unknowns."""
    targets, uncertain = [], []
    for row in members:
        box = row["bbox"]
        contained = tile[0] <= box[0] < box[2] <= tile[2] and tile[1] <= box[1] < box[3] <= tile[3]
        if row["id"] not in excluded and contained:
            targets.append(row)
        elif intersection(box, tile) > 0:
            uncertain.append(box)
    # The existing partial loss supervises a 12 model-pixel collar. A 12 source-
    # pixel collar is conservative for the allowed 320+ inputs on 256px tiles.
    if any(intersection([r["bbox"][0]-12, r["bbox"][1]-12,
                         r["bbox"][2]+12, r["bbox"][3]+12], box) > 0
           for r in targets for box in uncertain):
        return []
    return targets


def build(manifest_path, source_root, output, labels=DEFAULT_CLASSES, base_weights=None,
          context_mode="masked", class_agnostic=False, include_reviewed_neighbors=False,
          reviewed_box_only=False):
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get("schema") != "ved-reviewed-symbol-crops-v1":
        raise ValueError("Expected source-verified reviewed crop manifest")
    if output.exists():
        raise FileExistsError("Refusing to replace an existing dataset version")
    if context_mode not in {"masked", "full_partial"}:
        raise ValueError("Unknown training context")
    if include_reviewed_neighbors and context_mode != "full_partial":
        raise ValueError("Neighbor supervision requires full partial-label context")
    if reviewed_box_only and context_mode != "full_partial":
        raise ValueError("Reviewed-box-only loss requires full partial-label context")
    selected = [r for r in manifest["records"] if r["split"] == "train"
                and (class_agnostic or r["label"] in labels)]
    rows = [r for r in selected if r["sheet_id"] not in UNRESOLVED_REFERENCE_SHEETS]
    if not rows or (not class_agnostic and len({r["label"] for r in rows}) != len(labels)):
        raise ValueError("Selected labels are not all represented by reviewed training records")
    # Drawing IDs remain distinct even when the visible names coincide.
    identities = sorted({(r["legend_entry"], r["label"]) for r in rows})
    if class_agnostic:
        if base_weights is not None:
            raise ValueError("Class-agnostic localization cannot inherit a class-specific label map")
        classes = {identity: 0 for identity in identities}
        names = {0: "Reviewed electrical symbol"}
    elif base_weights is not None:
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
    overlap_proposals = []
    skipped_tiles = []
    reviewed_targets = {}
    for source_hash, members in sheet_rows.items():
        with Image.open(source_by_hash[source_hash]) as opened:
            if opened.width * opened.height > 60_000_000 or max(opened.size) > 10_000:
                raise ValueError("Source exceeds bounded image dimensions")
            source = opened.convert("RGB")
        # Validate every neighbor before it can enter another row's tile labels.
        for row in members:
            if ((row.get("source_width") is not None or row.get("source_height") is not None)
                    and (row.get("source_width"), row.get("source_height")) != source.size):
                raise ValueError("Source image dimensions differ from reviewed page")
            x1, y1, x2, y2 = row["bbox"]
            if not (all(math.isfinite(value) for value in row["bbox"])
                    and 0 <= x1 < x2 <= source.width and 0 <= y1 < y2 <= source.height):
                raise ValueError("Reviewed box lies outside exact source")
        excluded, pairs = overlapping_reviewed_records(members) if include_reviewed_neighbors else (set(), [])
        overlap_proposals.extend({"source_sha256": source_hash, **pair} for pair in pairs)
        for row in members:
            x1, y1, x2, y2 = row["bbox"]
            if row["id"] in excluded:
                continue
            width, height = x2 - x1, y2 - y1
            # Cap the visible collar. The rest is masked, never called negative evidence.
            collar = min(20, max(6, round(min(width, height) * 0.3)))
            tile_w = 256 if context_mode == "full_partial" else max(128, round(width * 2.0))
            tile_h = 256 if context_mode == "full_partial" else max(128, round(height * 2.0))
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            left, top = round(cx - tile_w / 2), round(cy - tile_h / 2)
            supervised = (tile_supervision(members, [left, top, left+tile_w, top+tile_h], excluded)
                          if include_reviewed_neighbors else [row])
            if not supervised:
                skipped_tiles.append({"record_id": row["id"],
                                      "reason": "known_partial_or_ambiguous_target_in_negative_collar"})
                continue
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
            lines, supervised_audit = [], []
            for target in supervised:
                a, b, c, d = target["bbox"]
                target_id = classes[(target["legend_entry"], target["label"])]
                xywh = ((a+c-2*left)/(2*tile_w), (b+d-2*top)/(2*tile_h),
                        (c-a)/tile_w, (d-b)/tile_h)
                lines.append(f"{target_id} " + " ".join(f"{v:.8f}" for v in xywh) + "\n")
                identity = {"record_id": target["id"], "sheet_id": target["sheet_id"],
                            "source_sha256": source_hash, "legend_entry": target["legend_entry"],
                            "class_id": target_id, "source_box": target["bbox"]}
                supervised_audit.append(identity)
                reviewed_targets[target["id"]] = identity
            label_path = output / "labels/train" / f"{name}.txt"
            label_path.write_text("".join(lines))
            audit.append({"record_id": name, "sheet_id": row["sheet_id"],
                          "source_sha256": source_hash, "legend_entry": row["legend_entry"],
                          "class_id": class_id, "source_box": row["bbox"],
                          "image_sha256": digest(image_path), "label_sha256": digest(label_path),
                          "collar_pixels": collar if context_mode == "masked" else None,
                          **({"tile_origin": [left, top], "supervised_records": supervised_audit}
                             if include_reviewed_neighbors else {}),
                          "split": "training_diagnostic_only"})
    if not audit:
        raise ValueError("No unambiguous reviewed tiles remain")
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
              "class_agnostic": class_agnostic,
              "context_mode": context_mode,
              "required_loss": ("positive_and_reviewed_box_only" if reviewed_box_only else
                                "positive_and_local_negative_only" if context_mode == "full_partial"
                                else "standard"),
              "reference_rights_exclusions": {"sheet_ids": sorted(UNRESOLVED_REFERENCE_SHEETS),
                                               "selected_records_excluded": len(selected) - len(rows)},
              "base_model_sha256": digest(base_weights) if base_weights else None,
              "classes": ([{"id": 0, "legend_entry": None, "label": names[0],
                            "samples": len(rows)}] if class_agnostic else
                          [{"id": i, "legend_entry": key, "label": label,
                            "samples": (sum(r["legend_entry"] == key for r in reviewed_targets.values())
                                        if include_reviewed_neighbors else
                                        sum(r["legend_entry"] == key for r in rows)),
                            **({"source_samples": sum(r["legend_entry"] == key for r in rows)}
                               if include_reviewed_neighbors else {})}
                           for (key, label), i in classes.items()]),
              "source_legend_classes": len(identities),
              "sheets": dict(Counter(r["sheet_id"] for r in rows)),
              "related_groups": dict(Counter(r["group"] for r in rows)),
              "images": audit,
              **({"reviewed_targets": list(reviewed_targets.values()),
                  "neighbor_supervision": True,
                  "overlap_exclusion_proposals": overlap_proposals,
                  "skipped_tiles": skipped_tiles,
                  "unique_supervised_records": len(reviewed_targets),
                  "supervised_label_occurrences": sum(len(r["supervised_records"]) for r in audit)}
                 if include_reviewed_neighbors else {}),
              "warnings": ["The val path repeats training images; no generalization metric is available.",
                           ("Pixels outside reviewed target boxes are ignored; no background completeness is claimed."
                            if reviewed_box_only else
                            "Full-context pixels outside a narrow target collar are unlabeled and require an ignore loss."
                            if context_mode == "full_partial" else
                            "Only reviewed positive symbols and narrow collars are visible; other page pixels are masked."),
                           "This diagnostic does not establish performance on unmasked full pages.",
                           *(["Class-agnostic localization cannot identify an approved legend class; classification remains unresolved."]
                             if class_agnostic else [])]}
    (output / "manifest.json").write_text(json.dumps(report, indent=2))
    return {"images": len(audit), "classes": len(names), "sheets": len(report["sheets"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", action="append", dest="labels")
    parser.add_argument("--base-weights", type=Path)
    parser.add_argument("--context-mode", choices=("masked", "full_partial"), default="masked")
    parser.add_argument("--class-agnostic", action="store_true")
    parser.add_argument("--include-reviewed-neighbors", action="store_true")
    parser.add_argument("--reviewed-box-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(args.manifest, args.source_root, args.output,
                           tuple(args.labels) if args.labels else DEFAULT_CLASSES,
                           base_weights=args.base_weights, context_mode=args.context_mode,
                           class_agnostic=args.class_agnostic,
                           include_reviewed_neighbors=args.include_reviewed_neighbors,
                           reviewed_box_only=args.reviewed_box_only)))
