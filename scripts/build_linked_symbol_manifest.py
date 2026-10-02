"""Prepare a reviewed-symbol detector input from one immutable local link revision.

This is development-only. Partial labels are not complete-page background truth.
"""

import argparse
from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import Path


EXCLUDED_SOURCE_SHEETS = {"sheet-51", "sheet-52"}
REVIEWED = {"corrected", "manually_added", "user_reviewed"}


def digest(data):
    return sha256(data).hexdigest()


def recovered_placement(sheet, annotation, chosen):
    """A class-link UI historically moved placed symbols into the legend layer.

    Recover only explicit, reviewed placement history and exact approved keys;
    never interpret a legend sample, an unresolved subtype or a name as a device.
    """
    return (sheet.get("sheet_type") == "plan"
            and annotation.get("layer") == "legend"
            and annotation.get("original_annotation", {}).get("layer") == "symbols"
            and annotation.get("review_state") in REVIEWED
            and not annotation.get("deleted") and not annotation.get("excluded")
            and annotation.get("class_state") in {
                "approved_legend_mapping", "cross_group_candidate", "user_proposed_legend_mapping"}
            and annotation.get("legend_entry") in chosen
            and not any(word in annotation.get("label", "").lower()
                        for word in ("unresolved", "unknown", "use default")))


def build(revision, output, *, all_approved=False, recover_reviewed_placements=False):
    if output.exists():
        raise FileExistsError("Refusing to replace a dataset version")
    original_bytes = (revision / "source-review.json").read_bytes()
    linked_bytes = (revision / "linked-review.json").read_bytes()
    audit_bytes = (revision / "audit.json").read_bytes()
    original, linked, audit = (json.loads(data) for data in
                               (original_bytes, linked_bytes, audit_bytes))
    if (original.get("schema") != "ved-editable-review-v2"
            or linked.get("schema") != original["schema"]
            or audit.get("schema") != "ved-central-legend-link-audit-v1"
            or digest(original_bytes) != audit.get("source_session_sha256")
            or original.get("training_approved") is not False
            or linked.get("training_approved") is not False):
        raise ValueError("Invalid or unbound development link revision")
    if len(original["sheets"]) != len(linked["sheets"]):
        raise ValueError("Page membership changed")
    if original.get("decisions") != linked.get("decisions"):
        raise ValueError("Page review decisions changed")
    linked_decisions = {(r["sheet_id"], r["annotation_id"]): r for r in audit["decisions"]}
    if len(linked_decisions) != audit["linked_this_revision"]:
        raise ValueError("Link decision identity conflict")
    chosen = {entry["legend_entry"]: entry["label"] for entry in audit["approved_legends"]
              if all_approved or entry["linked_this_revision"] > 0}
    if not chosen:
        raise ValueError("No linked classes")
    rows = []
    reasons = Counter()
    applied = set()
    recovered = []
    for before, sheet in zip(original["sheets"], linked["sheets"]):
        if (before["id"] != sheet["id"] or before.get("source_sha256") != sheet.get("source_sha256")
                or any(before.get(key) != sheet.get(key) for key in
                       ("width", "height", "group", "coordinate_frame", "pdf_page", "split"))
                or len(before.get("annotations", [])) != len(sheet.get("annotations", []))):
            raise ValueError("Source page identity changed")
        decision = linked.get("decisions", {}).get(sheet["id"], {}).get("decision")
        for old, annotation in zip(before.get("annotations", []), sheet.get("annotations", [])):
            if old.get("id") != annotation.get("id"):
                raise ValueError("Annotation identity changed")
            original_other = {k: v for k, v in old.items()
                              if k not in {"legend_entry", "legendKey", "pendingLegendKey", "class_state"}}
            linked_other = {k: v for k, v in annotation.items()
                            if k not in {"legend_entry", "legendKey", "pendingLegendKey", "class_state"}}
            if original_other != linked_other:
                raise ValueError("Link revision changed annotation evidence")
            key = (sheet["id"], annotation["id"])
            changed = any(old.get(field) != annotation.get(field) for field in
                          ("legend_entry", "legendKey", "pendingLegendKey", "class_state"))
            if changed != (key in linked_decisions):
                raise ValueError("Unrecorded or unapplied class link")
            if key in linked_decisions and (old.get("class_state") == annotation.get("class_state")
                                            or annotation.get("class_state") != "approved_legend_mapping"
                                            or linked_decisions[key]["legend_entry"] != annotation.get("legend_entry")):
                raise ValueError("Recorded link was not applied")
            if key in linked_decisions:
                applied.add(key)
            recovery = recover_reviewed_placements and recovered_placement(sheet, annotation, chosen)
            if ((annotation.get("layer") != "symbols" and not recovery) or
                    annotation.get("legend_entry") not in chosen):
                continue
            if not 1 <= int(sheet.get("group", 0)) <= 22:
                reasons["outside_authorized_groups"] += 1
                continue
            if sheet["id"] in EXCLUDED_SOURCE_SHEETS:
                reasons["underlying_source_rights_unresolved"] += 1
                continue
            if decision in {"exclude", "rescan_needed"} or sheet.get("split") in {"test", "sealed_test", "val", "validation", "evaluation"}:
                reasons["page_excluded_or_protected"] += 1
                continue
            if (annotation.get("review_state") not in REVIEWED or
                    annotation.get("deleted") or annotation.get("excluded") or
                    (annotation.get("class_state") != "approved_legend_mapping" and not recovery)):
                reasons["annotation_not_reviewed_and_mapped"] += 1
                continue
            box = annotation.get("geometry", {}).get("coordinates")
            if (annotation.get("geometry", {}).get("type") != "bbox" or
                    not isinstance(box, list) or len(box) != 4 or
                    any(type(value) not in (int, float) or not math.isfinite(value) for value in box) or
                    not (0 <= box[0] < box[2] <= sheet["width"] and
                         0 <= box[1] < box[3] <= sheet["height"])):
                reasons["invalid_box"] += 1
                continue
            record_id = digest(f"{sheet['id']}:{annotation['id']}".encode())[:24]
            if recovery:
                recovered.append({"sheet_id": sheet["id"], "annotation_id": annotation["id"],
                                  "original_layer": annotation["layer"],
                                  "original_class_state": annotation["class_state"],
                                  "basis": "owner-attested reviewed placement history + exact approved legend key; development only"})
            rows.append({"id": record_id, "sheet_id": sheet["id"],
                         "annotation_id": annotation["id"], "group": str(sheet["group"]),
                         "source_sha256": sheet["source_sha256"],
                         "source_width": sheet["width"], "source_height": sheet["height"],
                         "bbox": box,
                         "legend_entry": annotation["legend_entry"],
                         "label": chosen[annotation["legend_entry"]], "split": "train"})
    if applied != set(linked_decisions):
        raise ValueError("Link decision references missing annotation")
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate annotation identity")
    by_box = {}
    unique = []
    for row in rows:
        key = (row["source_sha256"], tuple(row["bbox"]))
        old = by_box.get(key)
        if old and old["legend_entry"] != row["legend_entry"]:
            raise ValueError("Conflicting reviewed classes on same source box")
        if old:
            reasons["duplicate_source_box"] += 1
        else:
            by_box[key] = row
            unique.append(row)
    if not unique:
        raise ValueError("No eligible source boxes")
    result = {"schema": "ved-reviewed-symbol-crops-v1",
              "task": "development_partial_label_detector",
              "scope": "all_approved_eligible" if all_approved else "newly_linked_classes",
              "source_review_sha256": digest(original_bytes),
              "linked_review_sha256": digest(linked_bytes),
              "link_audit_sha256": digest(audit_bytes),
              "authorization": "Owner-requested local development detection from groups 1-22; not production dataset approval",
              "class_scope": chosen,
              "excluded_source_sheet_ids": sorted(EXCLUDED_SOURCE_SHEETS),
              "exclusions": dict(reasons),
              "recovered_placements": recovered,
              "limitations": ["Related floors share a project", "No independent validation",
                              "Partial labels require ignore-region loss", "No production activation"],
              "records": unique}
    if all_approved:
        counts = Counter(row["legend_entry"] for row in unique)
        result["catalog_coverage"] = {
            "approved_classes": len(chosen),
            "eligible_classes": len(counts),
            "without_eligible_boxes": len(chosen) - len(counts),
            "eligible_boxes": len(unique),
            "by_class": [{"legend_entry": key, "eligible_boxes": counts[key]}
                         for key in sorted(chosen)],
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return {"records": len(unique), "classes": len({r["legend_entry"] for r in unique}),
            "sheets": len({r["sheet_id"] for r in unique}), "exclusions": dict(reasons)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--all-approved", action="store_true")
    parser.add_argument("--recover-reviewed-placements", action="store_true",
                        help="Reconcile owner-reviewed placed symbols moved into legend layer; development only")
    args = parser.parse_args()
    print(json.dumps(build(args.revision, args.output, all_approved=args.all_approved,
                           recover_reviewed_placements=args.recover_reviewed_placements)))
