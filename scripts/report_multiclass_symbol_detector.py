"""Hash-bound per-entry coverage, not an independent accuracy claim."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def report(dataset, probe, output):
    if output.exists():
        raise FileExistsError("Coverage reports are immutable")
    manifest = json.loads(dataset.read_text(encoding="utf-8"))
    evidence = json.loads(probe.read_text(encoding="utf-8"))
    if evidence["dataset_manifest_sha256"] != digest(dataset):
        raise ValueError("Probe and dataset hashes differ")
    predictions = Counter(p["class_id"] for page in evidence["pages"] for p in page["predictions"])
    scored = {r["class_id"]: r for r in evidence["summary"]["per_class"]}
    conflicts = Counter(key for pair in manifest.get("overlap_exclusion_proposals", [])
                        for key in pair["legend_entries"])
    centers = Counter(row["class_id"] for row in manifest["images"] if "augmentation_parent" not in row)
    variants = Counter(row["class_id"] for row in manifest["balanced_augmentation"]["synthetic_variants"])
    entries = []
    for cls in manifest["classes"]:
        metric = scored[cls["id"]]
        if (metric["legend_entry"], metric["label"]) != (cls["legend_entry"], cls["label"]):
            raise ValueError("Probe class mapping changed")
        limitations = ["same-source diagnostic; precision and independent accuracy unscored"]
        if cls["samples"] < 5:
            limitations.append("fewer than five reviewed records; variants add no independent evidence")
        if conflicts[cls["legend_entry"]]:
            limitations.append("overlapping owner-attested labels retained; semantic/box conflict remains reviewable")
        if cls["legend_entry"] == "sheet-16:L04":
            limitations.append("assistant inspection: two supplied panelboard boxes resemble homerun notation; originals unchanged")
        if not predictions[cls["id"]]:
            limitations.append("ZERO predicted boxes at the operating threshold; not successfully detected")
        elif not metric["localized_and_classified"]:
            limitations.append("predictions exist but no reviewed class+IoU matches")
        entries.append({"model_class_id": cls["id"], "legend_entry": cls["legend_entry"],
            "label": cls["label"], "training_reviewed_records": cls["samples"],
            "center_training_images": centers[cls["id"]], "augmented_variants": variants[cls["id"]],
            "prediction_count": predictions[cls["id"]],
            "class_and_location_matches": metric["localized_and_classified"],
            "limitations": "; ".join(limitations)})
    if len(entries) != 56 or any(e["training_reviewed_records"] < 1 for e in entries):
        raise ValueError("All 56 eligible entries must be represented")
    output.mkdir(parents=True)
    result = {"schema": "ved-development-56-entry-coverage-v1",
        "checkpoint_sha256": evidence["checkpoint_sha256"], "dataset_sha256": digest(dataset),
        "probe_sha256": digest(probe), "operating_score": evidence["threshold"],
        "precision": None, "independent_accuracy": None, "entries": entries}
    (output/"coverage.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    with (output/"coverage.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(entries[0]))
        writer.writeheader()
        writer.writerows(entries)
    return {"entries_in_training": len(entries),
            "entries_with_predictions": sum(e["prediction_count"] > 0 for e in entries),
            "entries_with_reviewed_matches": sum(e["class_and_location_matches"] > 0 for e in entries)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(report(args.dataset, args.probe, args.output)))
