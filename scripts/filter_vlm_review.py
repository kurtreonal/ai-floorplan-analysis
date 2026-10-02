"""Create an immutable, private review subset; never imply training approval.

This is a preparation artifact, not a training manifest. Incomplete pages must
not become negative examples simply because their unresolved objects are removed.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


REVIEWED = {"corrected", "manually_added", "user_reviewed"}
MAX_EXPORT_BYTES = 32 * 1024 * 1024


def filter_review(payload, references):
    if payload.get("schema") != "ved-editable-review-v2":
        raise ValueError("Unsupported review schema")
    known = {entry["legend_entry"] for entry in references["legend_catalog"]}
    counts = Counter()
    sheets = []
    for sheet in payload["sheets"]:
        decision = payload.get("decisions", {}).get(sheet["id"], {}).get("decision")
        retained, excluded = [], []
        for annotation in sheet["annotations"]:
            reason = None
            if annotation.get("review_state") == "deleted":
                reason = "deleted"
            elif decision in {"exclude", "rescan_needed"}:
                reason = "sheet_" + decision
            elif annotation.get("review_state") not in REVIEWED:
                reason = "review_pending"
            elif annotation.get("layer") in {"symbols", "legend"}:
                if annotation.get("class_state") != "approved_legend_mapping":
                    reason = "mapping_not_approved"
                elif annotation.get("legend_entry") not in known:
                    reason = "legend_not_in_catalog"
            elif annotation.get("layer") not in {"geometry", "wiring", "text"}:
                reason = "unsupported_training_layer"
            if reason:
                excluded.append({"id": annotation.get("id"), "reason": reason})
                counts[reason] += 1
            else:
                retained.append(annotation)
                counts["retained_for_validation"] += 1
        sheets.append({
            "id": sheet["id"], "source_sha256": sheet["source_sha256"],
            "group": sheet.get("group"), "width": sheet["width"],
            "height": sheet["height"], "coordinate_frame": sheet.get("coordinate_frame"),
            "pdf_page": sheet.get("pdf_page"), "training_eligible": False,
            "annotations": retained, "excluded": excluded,
        })
    return {
        "schema": "ved-filtered-review-draft-v1", "training_approved": False,
        "status": "pending_geometry_class_identity_completeness_and_split_validation",
        "detector_confidence_threshold": 0.5,
        "summary": dict(counts), "sheets": sheets,
    }


def read_bounded(path):
    with path.open("rb") as stream:
        raw = stream.read(MAX_EXPORT_BYTES + 1)
    if len(raw) > MAX_EXPORT_BYTES:
        raise ValueError("Export exceeds preparation size bound")
    return raw, json.loads(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--review-export", type=Path,
                        help="New export to snapshot without replacing the workspace session")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source, payload = read_bounded(args.review_export or args.workspace / "data" / "saved-session.json")
    reference_bytes, references = read_bounded(args.workspace / "data" / "approved-references.json")
    result = filter_review(payload, references)
    result["source_sha256"] = hashlib.sha256(source).hexdigest()
    result["references_sha256"] = hashlib.sha256(reference_bytes).hexdigest()
    result["created_at"] = datetime.now(timezone.utc).isoformat()
    args.output.mkdir(parents=True, exist_ok=False)
    # Exclusive writes plus an exclusive directory preserve earlier revisions.
    for name, content in (
        ("source-review.json", source), ("source-references.json", reference_bytes),
        ("filtered-review.json", json.dumps(result, indent=2).encode()),
    ):
        with (args.output / name).open("xb") as stream:
            stream.write(content)
    print(json.dumps({"status": result["status"], "summary": result["summary"]}))


if __name__ == "__main__":
    main()
