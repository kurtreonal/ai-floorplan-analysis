"""Prepare reviewed-object classification, never incomplete-page detection truth."""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path

from PIL import Image
from filter_vlm_review import REVIEWED, read_bounded


REVIEW_WITH_VERIFIED_RELATED_FLOORS = "829de08a31e2c8014ac6194cb958f999b2aa534297af749a661b31d7a383afc9"


def link_verified_related_floors(parent, review_sha256):
    """Keep owner-identified floors 1-6 together for this exact export only."""
    if review_sha256 != REVIEW_WITH_VERIFIED_RELATED_FLOORS or "1" not in parent:
        return

    def root(group):
        while parent[group] != group:
            group = parent[group]
        return group

    for number in range(2, 7):
        group = str(number)
        if group in parent:
            parent[root(group)] = root("1")
    # Groups 8-20 lack enough project identity evidence to prove independence.
    # Grouping them for split assignment does not assert one real project.
    if "8" in parent:
        for number in range(9, 21):
            group = str(number)
            if group in parent:
                parent[root(group)] = root("8")


def closed_set_validation_groups(records, proposed):
    """Reject proposed holdouts with legend classes absent from training."""
    validation = set(proposed)
    while validation:
        train_classes = {r["legend_entry"] for r in records if r["group"] not in validation}
        train_hashes = {r.get(key) for r in records if r["group"] not in validation
                        for key in ("source_sha256", "image_sha256") if r.get(key)}
        invalid = {r["group"] for r in records if r["group"] in validation
                   and (r["legend_entry"] not in train_classes
                        or any(r.get(key) in train_hashes for key in ("source_sha256", "image_sha256")
                               if r.get(key)))}
        if not invalid:
            break
        validation.difference_update(invalid)
    return validation


def normalized(value):
    return " ".join(str(value or "").casefold().split())


def resolve_legend(annotation, sheet, catalog):
    """Resolve only exact catalog identity/label within the drawing legend scope."""
    scope = set(sheet.get("associated_legend_ids", []))
    scope.add(sheet["id"])
    entries = [entry for entry in catalog if any(
        example.get("source_sheet_id") in scope for example in entry.get("examples", [])
    )]
    explicit = [entry for entry in entries
                if entry["legend_entry"] == annotation.get("legend_entry")]
    if len(explicit) == 1 and (
        annotation.get("class_state") == "approved_legend_mapping"
        or normalized(explicit[0]["label"]) == normalized(annotation.get("label"))
    ):
        return explicit[0], "exact_scoped_identity"
    matches = [entry for entry in entries
               if normalized(entry["label"]) == normalized(annotation.get("label"))]
    if len(matches) == 1:
        return matches[0], "exact_scoped_label"
    return None, "ambiguous_or_unmapped"


def valid_box(annotation, width, height):
    geometry = annotation.get("geometry", {})
    box = geometry.get("coordinates", [])
    if geometry.get("type") != "bbox" or len(box) != 4:
        return None
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in box):
        return None
    x1, y1, x2, y2 = box
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        return None
    return (math.floor(x1), math.floor(y1), math.ceil(x2), math.ceil(y2))


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare(workspace, output, *, review_export=None, approval_record=None, prior_manifest=None,
            technical_exclusions=None):
    raw, review = read_bounded(review_export or workspace / "data/saved-session.json")
    ref_raw, refs = read_bounded(workspace / "data/approved-references.json")
    if review.get("schema") != "ved-editable-review-v2":
        raise ValueError("Unsupported schema")
    approval_raw, approval = (None, None)
    if review_export is not None:
        if approval_record is None:
            raise ValueError("Version-bound group approval required")
        approval_raw, approval = read_bounded(approval_record)
        if (approval.get("review_sha256") != hashlib.sha256(raw).hexdigest()
                or not approval.get("user_statement") or not approval.get("approved_groups")
                or any(type(g) is not int or g <= 0 for g in approval["approved_groups"])):
            raise ValueError("Invalid version-bound approval")
    exclusion_raw, excluded_ids = None, set()
    if technical_exclusions is not None:
        exclusion_raw, exclusions = read_bounded(technical_exclusions)
        if (exclusions.get("kind") != "assistant_visual_proposals_not_applied"
                or exclusions.get("review_export_sha256") != hashlib.sha256(raw).hexdigest()):
            raise ValueError("Technical exclusions do not bind this review export")
        for proposal in exclusions.get("proposals", []):
            record_id = proposal.get("record_id")
            if (proposal.get("decision") != "exclude_ambiguous" or not isinstance(record_id, str)
                    or record_id in excluded_ids):
                raise ValueError("Invalid or duplicate technical exclusion")
            excluded_ids.add(record_id)
        source_ids = {hashlib.sha256((sheet["id"] + ":" + str(ann.get("id"))).encode()).hexdigest()[:24]
                      for sheet in review["sheets"] for ann in sheet["annotations"]
                      if ann.get("layer") == "symbols"}
        if not excluded_ids <= source_ids:
            raise ValueError("Technical exclusion references unknown annotation")
    sources = {}
    for folder, directories, files in os.walk(workspace, followlinks=False):
        directories[:] = [d for d in directories if d not in
                          {"node_modules", ".git", "training_dataset", "backups", ".temp"}
                          and not (Path(folder) / d).is_symlink()]
        for name in files:
            path = Path(folder) / name
            if (not path.is_symlink() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}
                    and path.stat().st_size <= 25 * 1024 * 1024):
                sources.setdefault(sha(path), path)
    output.mkdir(parents=True, exist_ok=False)
    (output / "crops").mkdir()
    records, decisions = [], []
    # Join groups sharing source bytes before making experimental group splits.
    parent = {str(s.get("group")): str(s.get("group")) for s in review["sheets"]}

    def root(group):
        while parent[group] != group:
            group = parent[group]
        return group

    seen_sources = {}
    for sheet in review["sheets"]:
        group = str(sheet.get("group"))
        for source_hash in (sheet.get("source_sha256"), sheet.get("original_source_sha256")):
            if not source_hash:
                continue
            if source_hash in seen_sources:
                parent[root(group)] = root(seen_sources[source_hash])
            seen_sources[source_hash] = group
    link_verified_related_floors(parent, hashlib.sha256(raw).hexdigest())
    for sheet in review["sheets"]:
        decision = review.get("decisions", {}).get(sheet["id"], {}).get("decision")
        source = sources.get(sheet.get("source_sha256"))
        for ann in sheet["annotations"]:
            if ann.get("layer") != "symbols":
                continue
            record_id = hashlib.sha256((sheet["id"] + ":" + str(ann.get("id"))).encode()).hexdigest()[:24]
            reason = None
            entry, evidence = resolve_legend(ann, sheet, refs["legend_catalog"])
            if record_id in excluded_ids:
                reason = "technical_exclusion_pending_review"
            elif approval is not None and sheet.get("group") not in approval["approved_groups"]:
                reason = "outside_approved_groups"
            elif decision in {"exclude", "rescan_needed"}:
                reason = "sheet_" + decision
            elif sheet.get("split") in {"sealed_test", "test"}:
                reason = "protected_split"
            elif ann.get("review_state") not in REVIEWED:
                reason = "not_reviewed"
            elif entry is None:
                reason = evidence
            elif source is None:
                reason = "exact_source_missing"
            box = valid_box(ann, sheet["width"], sheet["height"])
            if not reason and box is None:
                reason = "invalid_geometry"
            if not reason:
                with Image.open(source) as image:
                    w, h = image.size
                    if (w, h) != (sheet["width"], sheet["height"]) or max(w, h) > 10000 or w*h > 60000000:
                        reason = "source_dimensions_invalid"
                    else:
                        crop = image.crop(box).convert("RGB")
                        crop.thumbnail((512, 512))
                        crop_path = output / "crops" / (record_id + ".png")
                        crop.save(crop_path)
                        records.append({
                            "id": record_id, "sheet_id": sheet["id"], "annotation_id": ann["id"],
                            "group": root(str(sheet.get("group"))), "source_sha256": sha(source),
                            "image": "crops/" + crop_path.name, "image_sha256": sha(crop_path),
                            "bbox": box, "legend_entry": entry["legend_entry"], "label": entry["label"],
                            "mapping_evidence": evidence, "original_annotation": ann,
                        })
            decisions.append({"id": record_id, "reason": reason or "included"})
    groups = sorted({r["group"] for r in records}, key=lambda g: hashlib.sha256(g.encode()).hexdigest())
    validation = set(groups[:max(1, len(groups)//5)]) if len(groups) > 1 else set()
    # Identical crop pixels never cross training/validation, even across groups.
    crop_groups = {}
    for record in records:
        crop_groups.setdefault(record["image_sha256"], set()).add(record["group"])
    changed = True
    while changed:
        old = set(validation)
        for members in crop_groups.values():
            if members & validation:
                validation.update(members)
        changed = old != validation
    validation = closed_set_validation_groups(records, validation)
    for record in records:
        record["split"] = "development_validation" if record["group"] in validation else "train"
    if prior_manifest is not None:
        _, previous = read_bounded(prior_manifest)
        prior_review_raw, prior_review = read_bounded(prior_manifest.parent / "source-review.json")
        if hashlib.sha256(prior_review_raw).hexdigest() != previous.get("review_sha256"):
            raise ValueError("Prior split source integrity failed")
        prior_sheets = {s["id"]: s for s in prior_review["sheets"]}
        established = {}
        for record in previous["records"]:
            group = str(prior_sheets[record["sheet_id"]].get("group"))
            if group not in parent:
                continue
            group = root(group)
            if group in established and established[group] != record["split"]:
                raise ValueError("Related groups conflict with established splits")
            established[group] = record["split"]
        for record in records:
            record["split"] = established.get(record["group"], record["split"])
        seen = {}
        for record in records:
            for key in (record["source_sha256"], record["image_sha256"]):
                if key in seen and seen[key] != record["split"]:
                    raise ValueError("New duplicate conflicts with established splits")
                seen[key] = record["split"]
    manifest = {
        "schema": "ved-reviewed-symbol-crops-v1", "task": "symbol_crop_classification",
        "authorization": approval or "User authorized reviewed correction reconciliation and local training on 2026-09-21",
        "limitations": ["Not a gold release", "Not full-page detection truth",
                        "Groups are workspace groups, not independently verified projects",
                        "No production activation or sealed-test evaluation"],
        "review_sha256": hashlib.sha256(raw).hexdigest(),
        "split_policy": "related-source grouping; unseen legend classes excluded from validation; empty validation allowed",
        "split_evidence": ({
            "1": "Owner-confirmed related floors across workspace groups 1-6",
            "7": "Same drawing set; source title block identifies one named project",
            "8": "Conservative unresolved relationship cluster for workspace groups 8-20; not asserted as one project",
            "21": "Source title block identifies a distinct named project",
            "22": "Source title block identifies a distinct named project",
        } if hashlib.sha256(raw).hexdigest() == REVIEW_WITH_VERIFIED_RELATED_FLOORS else {}),
        "reference_sha256": hashlib.sha256(ref_raw).hexdigest(),
        "records": records, "decisions": decisions,
    }
    if approval_raw is not None:
        manifest["approval_sha256"] = hashlib.sha256(approval_raw).hexdigest()
        with (output / "source-approval.json").open("xb") as stream:
            stream.write(approval_raw)
    if exclusion_raw is not None:
        manifest["technical_exclusions_sha256"] = hashlib.sha256(exclusion_raw).hexdigest()
        with (output / "source-technical-exclusions.json").open("xb") as stream:
            stream.write(exclusion_raw)
    if prior_manifest is not None:
        manifest["split_baseline_sha256"] = sha(prior_manifest)
    for name, content in (("manifest.json", json.dumps(manifest, indent=2).encode()),
                          ("source-review.json", raw), ("source-references.json", ref_raw)):
        with (output / name).open("xb") as stream:
            stream.write(content)
    print(json.dumps({"decisions": dict(Counter(d["reason"] for d in decisions)),
                      "splits": dict(Counter(r["split"] for r in records)), "groups": len(groups)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review-export", type=Path)
    parser.add_argument("--approval-record", type=Path)
    parser.add_argument("--prior-manifest", type=Path)
    parser.add_argument("--technical-exclusions", type=Path)
    args = parser.parse_args()
    prepare(args.workspace, args.output, review_export=args.review_export,
            approval_record=args.approval_record, prior_manifest=args.prior_manifest,
            technical_exclusions=args.technical_exclusions)
