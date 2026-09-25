"""Compare reviewed Pull-station crops with frozen cross-page matches (local only)."""

import json
from hashlib import sha256
from pathlib import Path
import sys

import cv2

from experiment_symbol_localization import center_error, find_patch_candidates


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.ai.floor_plan_interpretation.experimental_pull_station import LOCAL_SOURCE, locate
SOURCE = Path.home() / "Documents/VED-floor-plan-review-portable/images"
DIAGNOSTIC = ROOT / "storage/training/diagnostic-g1-22-829de08a31e2"
SOURCE_SHA = "8cd5962e233fe1dbbe2de981a6169665720e49fb0b2da81215d7532a4299b1ed"
TARGET_SHA = "c8501119a41e3686502af24d34c4554d19016802cc9ed28f691beec3b615389b"
TEMPLATE_BOXES = ((1043, 1779, 1071, 1807), (1986, 1895, 2014, 1924))


def crop(image, box):
    x0, y0, x1, y1 = box
    return cv2.resize(image[y0:y1, x0:x1], (28, 28))


def interior_score(patch, template):
    core = (slice(5, 23), slice(5, 23))
    return float(cv2.matchTemplate(patch[core], template[core], cv2.TM_CCOEFF_NORMED)[0, 0])


def main():
    for sheet, expected in (("sheet-21.jpg", SOURCE_SHA), ("sheet-19.jpg", TARGET_SHA)):
        digest = sha256()
        with (SOURCE / sheet).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise ValueError("Supplied source hash mismatch")
    source = cv2.imread(str(SOURCE / "sheet-21.jpg"), cv2.IMREAD_GRAYSCALE)
    target = cv2.imread(str(SOURCE / "sheet-19.jpg"), cv2.IMREAD_GRAYSCALE)
    manifest = json.loads((ROOT / "storage/training/symbol-crops-20260925-localization-v3/manifest.json").read_text(encoding="utf-8"))
    frozen = json.loads((DIAGNOSTIC / "pull-cross-page-frozen-v1.json").read_text(encoding="utf-8"))
    templates = [crop(source, box) for box in TEMPLATE_BOXES]
    positives = [record for record in manifest["records"]
                 if record["source_sha256"] == SOURCE_SHA and record["legend_entry"] == "sheet-20:L05"]
    for kind, image, boxes in (
        ("reviewed_positive", source, [record["bbox"] for record in positives]),
        ("assistant_reject_proposal", target, [record["bbox"] for record in frozen["predictions"]]),
    ):
        for box in boxes:
            patch = crop(image, box)
            print(kind, box, [round(interior_score(patch, template), 3) for template in templates])

    for scale in (0.8, 1.0, 1.2):
        patches = [(str(index), cv2.resize(template, None, fx=scale, fy=scale))
                   for index, template in enumerate(templates)]
        predictions = find_patch_candidates(target, patches, 0.60)
        overlay = cv2.cvtColor(target, cv2.COLOR_GRAY2BGR)
        for prediction in predictions:
            x0, y0, x1, y1 = prediction["bbox"]
            cv2.rectangle(overlay, (x0, y0), (x1, y1), (0, 140, 255), 3)
        cv2.imwrite(str(DIAGNOSTIC / f"pull-cross-page-scale-{scale:.1f}-development.png"), overlay)
        print("development_scale", scale, "candidates", len(predictions))
        source_predictions = find_patch_candidates(source, patches, 0.60)
        hits = sum(any(center_error(record["bbox"], p["bbox"]) <= 14
                       for p in source_predictions) for record in positives)
        print("same_page_reviewed_positive", scale, hits, len(positives),
              "all_candidates", len(source_predictions))
    for sheet in ("sheet-21.jpg", "sheet-19.jpg"):
        rgb = cv2.imread(str(SOURCE / sheet))[:, :, ::-1].copy()
        matches = locate(rgb, LOCAL_SOURCE)
        print("development_runtime", sheet, "candidates", len(matches),
              "scale", matches[0]["scale"] if matches else None,
              "boxes", [item["bbox"] for item in matches])
        if sheet == "sheet-19.jpg":
            overlay = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            for item in matches:
                x0, y0, x1, y1 = item["bbox"]
                cv2.rectangle(overlay, (x0, y0), (x1, y1), (0, 140, 255), 3)
            cv2.imwrite(str(DIAGNOSTIC / "pull-cross-page-adjusted-v2.png"), overlay)


if __name__ == "__main__":
    main()
