"""Build a small, project-separated diagnostic from an immutable crop manifest."""

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from train_vlm_symbol_crops import validate_manifest


def prepare(source_manifest: Path, output: Path) -> dict:
    source = source_manifest.parent
    manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    validate_manifest(manifest, source)
    train = Counter(r["label"] for r in manifest["records"] if r["split"] == "train")
    validation = Counter(r["label"] for r in manifest["records"] if r["split"] == "development_validation")
    labels = sorted(
        (label for label in train if train[label] >= 3 and validation[label] >= 2),
        key=lambda label: (-min(train[label], validation[label]), label),
    )[:2]
    if len(labels) != 2:
        raise ValueError("Two shared classes with separate training/validation groups required")
    selected = []
    for label in labels:
        selected.extend(r for r in manifest["records"] if r["label"] == label and r["split"] == "train")
        selected.extend(r for r in manifest["records"] if r["label"] == label and r["split"] == "development_validation")
    # Keep all examples of the two classes. Existing project and duplicate grouping
    # remain unchanged; this is a diagnosis, never a model-selection score.
    hashes = {}
    for record in selected:
        for key in (record["source_sha256"], record["image_sha256"]):
            prior = hashes.setdefault(key, record["split"])
            if prior != record["split"]:
                raise ValueError("Diagnostic split leakage")
    output.mkdir(parents=True, exist_ok=False)
    (output / "crops").mkdir()
    for name in ("source-review.json", "source-references.json", "source-approval.json"):
        shutil.copy2(source / name, output / name)
    for record in selected:
        src = (source / record["image"]).resolve()
        if not src.is_relative_to(source.resolve()):
            raise ValueError("Unsafe crop path")
        shutil.copy2(src, output / record["image"])
    diagnostic = {**manifest, "records": selected,
                  "limitations": [*manifest.get("limitations", []),
                                  "Two-class learning diagnostic; not full-plan detection"]}
    (output / "manifest.json").write_text(json.dumps(diagnostic, indent=2), encoding="utf-8")
    validate_manifest(diagnostic, output)
    return {"train": sum(r["split"] == "train" for r in selected),
            "validation": sum(r["split"] == "development_validation" for r in selected),
            "classes": 2}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source_manifest, args.output)))
