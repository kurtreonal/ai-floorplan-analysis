"""Prepare a private, unapproved review queue from a frozen detector probe.

This never converts predictions into negatives or declares page completeness.
It records exactly which source-bound pages and proposals still need review.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path


def _load(path):
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def build_queue(source_path, dataset_path, probe_path):
    source, source_hash = _load(source_path)
    dataset, dataset_hash = _load(dataset_path)
    probe, probe_hash = _load(probe_path)
    if source.get("schema") != "ved-reviewed-symbol-crops-v1":
        raise ValueError("Unexpected source manifest")
    if (dataset.get("kind") != "positive_only_masked_symbol_detection_diagnostic_v1"
            or dataset.get("class_agnostic") is not False
            or dataset.get("source_manifest_sha256") != source_hash):
        raise ValueError("Dataset is not bound to the class-aware reviewed source")
    if (probe.get("kind") != "partial_label_full_page_probe_v1"
            or probe.get("dataset_manifest_sha256") != dataset_hash
            or probe.get("class_agnostic") is not False):
        raise ValueError("Probe is not bound to the class-aware dataset")
    if probe.get("precision") is not None or probe.get("generalization") is not None:
        raise ValueError("Incomplete pages cannot provide scored precision or generalization")

    classes = {row["id"]: row for row in dataset["classes"]}
    if len(classes) != len(dataset["classes"]):
        raise ValueError("Duplicate class ID")
    records = {row["id"]: row for row in source["records"]}
    images_by_source = defaultdict(list)
    for image in dataset["images"]:
        record = records.get(image["record_id"])
        if (record is None or record["source_sha256"] != image["source_sha256"]
                or record["legend_entry"] != image["legend_entry"]
                or record["bbox"] != image["source_box"]
                or classes.get(image["class_id"], {}).get("legend_entry") != image["legend_entry"]):
            raise ValueError("Dataset image identity or class mapping changed")
        images_by_source[image["source_sha256"]].append(image)

    pages = []
    seen = set()
    for page in probe["pages"]:
        source_sha = page["source_sha256"]
        if source_sha in seen or source_sha not in images_by_source:
            raise ValueError("Unexpected or repeated probe page")
        if page.get("overlay") != f"{source_sha[:16]}-overlay.jpg":
            raise ValueError("Unexpected probe overlay identity")
        seen.add(source_sha)
        expected = {row["record_id"] for row in images_by_source[source_sha]}
        if ({row["record_id"] for row in page["targets"]} != expected
                or len(page["targets"]) != len(expected)
                or page["reviewed_positive_count"] != len(expected)):
            raise ValueError("Probe target membership changed")
        by_record = {row["record_id"]: row for row in images_by_source[source_sha]}
        missed = []
        for target in page["targets"]:
            if not isinstance(target.get("localized_and_classified"), bool):
                raise ValueError("Probe target match state missing")
            if not target["localized_and_classified"]:
                image = by_record[target["record_id"]]
                missed.append({"record_id": target["record_id"],
                               "legend_entry": image["legend_entry"],
                               "bbox_source_pixels": image["source_box"]})
        groups = sorted({str(records[row["record_id"]]["group"])
                         for row in images_by_source[source_sha]})
        dimensions = {(records[row["record_id"]]["source_width"],
                       records[row["record_id"]]["source_height"])
                      for row in images_by_source[source_sha]}
        if len(dimensions) != 1:
            raise ValueError("Probe page has inconsistent source dimensions")
        width, height = dimensions.pop()
        proposals = []
        for index, prediction in enumerate(page["predictions"], start=1):
            class_id = prediction["class_id"]
            if class_id not in classes:
                raise ValueError("Probe proposed an unknown class ID")
            bbox = prediction["bbox"]
            score = prediction["score"]
            if (len(bbox) != 4 or not all(isinstance(value, (int, float))
                                           and math.isfinite(value) for value in bbox)
                    or not (0 <= bbox[0] < bbox[2] <= width
                            and 0 <= bbox[1] < bbox[3] <= height)
                    or not isinstance(score, (int, float))
                    or not math.isfinite(score) or not 0 <= score <= 1):
                raise ValueError("Probe proposal coordinates or score invalid")
            proposals.append({
                "proposal_id": f"{source_sha[:16]}-{index:04d}",
                "bbox_source_pixels": bbox,
                "proposed_legend_entry": classes[class_id]["legend_entry"],
                "detector_score_uncalibrated": score,
                "review_state": "pending",
            })
        pages.append({
            "source_sha256": source_sha,
            "sheet_ids": page["sheet_ids"],
            "probe_overlay_filename": page["overlay"],
            "workspace_groups_not_project_ids": groups,
            "reviewed_positive_count": len(expected),
            "missed_reviewed_targets": missed,
            "proposals": proposals,
            "project_identity": "unverified",
            "exhaustive_symbol_and_background_review": "not_recorded",
        })
    if seen != set(images_by_source):
        raise ValueError("Probe omitted a reviewed source page")
    counts = Counter(row["class_id"] for row in dataset["images"])
    return {
        "schema": "ved-detector-review-queue-v1",
        "source_manifest_sha256": source_hash,
        "dataset_manifest_sha256": dataset_hash,
        "probe_report_sha256": probe_hash,
        "checkpoint_sha256": probe["checkpoint_sha256"],
        "evaluation_status": "blocked_incomplete_regions_and_project_identity",
        "precision": None,
        "independent_project_recall": None,
        "class_support": [
            {"legend_entry": classes[class_id]["legend_entry"],
             "reviewed_boxes": counts[class_id],
             "source_pages": len({row["source_sha256"] for row in dataset["images"]
                                  if row["class_id"] == class_id})}
            for class_id in sorted(classes)
        ],
        "pages": pages,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--probe-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Review queue revisions are immutable")
    queue = build_queue(args.source_manifest, args.dataset_manifest, args.probe_report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(queue, stream, indent=2)
    print(json.dumps({"pages": len(queue["pages"]),
                      "classes": len(queue["class_support"]),
                      "proposals": sum(len(p["proposals"]) for p in queue["pages"]),
                      "evaluation_status": queue["evaluation_status"]}))
