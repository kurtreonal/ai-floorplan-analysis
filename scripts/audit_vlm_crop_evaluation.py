"""Audit historical crop splits without turning workspace groups into projects."""
import argparse
import json
from pathlib import Path

from train_vlm_symbol_crops import validate_manifest

REVIEW_SHA = "829de08a31e2c8014ac6194cb958f999b2aa534297af749a661b31d7a383afc9"
RELATED_FLOORS = frozenset(str(number) for number in range(1, 7))


def audit(manifest):
    records = manifest["records"]
    train = [r for r in records if r["split"] == "train"]
    validation = [r for r in records if r["split"] == "development_validation"]
    known_groups = RELATED_FLOORS if manifest.get("review_sha256") == REVIEW_SHA else frozenset()
    known_related = [r for r in records if str(r["group"]) in known_groups]
    related_splits = sorted({r["split"] for r in known_related})
    train_labels = {r["legend_entry"] for r in train}
    unseen = [r for r in validation if r["legend_entry"] not in train_labels]
    same_class = [r for r in validation if r["legend_entry"] in train_labels]
    # There is no independently verified project identity for other workspace
    # groups. A same-class example is not automatically a valid held-out project.
    return {
        "source_records": len(records), "train_records": len(train),
        "historical_validation_records": len(validation),
        "known_related_floor_groups": sorted(known_groups),
        "known_related_floor_splits": related_splits,
        "known_project_leak": len(related_splits) > 1,
        "unseen_class_validation_records": len(unseen),
        "same_class_validation_records_not_yet_project_verified": len(same_class),
        "scorable_project_separated_closed_set_records": 0,
        "status": "no_project_verified_score",
        "reason": "Other group-to-project relationships lack verified source evidence",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    validate_manifest(manifest, args.manifest.parent)
    print(json.dumps(audit(manifest), indent=2))
