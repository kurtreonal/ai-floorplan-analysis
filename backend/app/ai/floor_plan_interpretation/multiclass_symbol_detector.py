"""One pinned 56-entry local development detector; not a promoted release.

Names are never used to merge drawing-specific IDs. Prior experimental jobs
retain their old providers; new development uploads use this shared checkpoint.
"""
from functools import lru_cache
from hashlib import sha256
import json
import os
import unicodedata

from app.core.config import REPOSITORY_ROOT
from app.ai.floor_plan_interpretation import experimental_symbol_detector as shared

PROVIDER = "development_multiclass56_yolo"
CHECKPOINT = REPOSITORY_ROOT / "storage/training/symbol-quality-20260929-run3/weights/best.pt"
CHECKPOINT_SHA256 = "5951c7375bed147244e36cbd93bfdd6ecc8ab3942b0a96fa842363ea087efa22"
TRAINING_BASE_SHA256 = "2c46051a30673d1fcee9255b7890ef9c2a5ff9481073b06bb4e419c0c272dafc"
DATASET = REPOSITORY_ROOT / "storage/training/symbol-quality-20260929-v2/manifest.json"
DATASET_SHA256 = "26c3dcc6a843e110f4ed373ba2abbf15d0261d70ecbe6dd1fba1d91410c10d37"
THRESHOLD = .50  # uncalibrated detector score; original configurable legacy path unchanged


def verify_artifacts():
    if (shared._digest(CHECKPOINT, 30_000_000) != CHECKPOINT_SHA256
            or shared._digest(DATASET, 5_000_000) != DATASET_SHA256):
        raise shared.ExperimentalDetectorUnavailable("MULTICLASS_MODEL_INTEGRITY_FAILED")
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    rows = data.get("classes", [])
    if (data.get("all_eligible_entries") is not True
            or data.get("required_loss") not in {"positive_and_reviewed_box_only",
                                                 "positive_boxes_and_explicit_reviewed_background"}
            or len(rows) != 56 or {r["id"] for r in rows} != set(range(56))
            or len({r["legend_entry"] for r in rows}) != 56
            or any(r["samples"] < 1 for r in rows)
            or data.get("reference_rights_exclusions", {}).get("sheet_ids") != ["sheet-51", "sheet-52"]):
        raise shared.ExperimentalDetectorUnavailable("MULTICLASS_CLASS_MAP_INVALID")
    return {row["id"]: (row["label"], row["legend_entry"]) for row in rows}


def configuration_sha256():
    return sha256(json.dumps({"provider": PROVIDER, "checkpoint": CHECKPOINT_SHA256,
        "dataset": DATASET_SHA256, "threshold": THRESHOLD,
        "tile": shared.TILE_SIZE, "stride": shared.TILE_STRIDE, "model_input": 320,
        "second_grid_offset": 128, "second_grid_policy": "only if total within existing 500-window cap",
        "batch": 8,
        "nms": shared.NMS_IOU, "max_tiles": shared.MAX_TILES,
        "max_candidates": shared.MAX_CANDIDATES}, sort_keys=True).encode()).hexdigest()


@lru_cache(maxsize=1)
def _model():
    os.environ["YOLO_AUTOINSTALL"] = "false"
    os.environ["YOLO_OFFLINE"] = "true"
    from ultralytics import YOLO
    model = YOLO(str(CHECKPOINT))
    expected = {i: unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode()
                for i, (label, _) in verify_artifacts().items()}
    if model.names != expected:
        raise shared.ExperimentalDetectorUnavailable("MULTICLASS_CHECKPOINT_HEAD_INVALID")
    # The manifest is hash-bound to the head's numeric identities. Duplicate
    # visible wording does not collapse drawing-specific model outputs.
    return model


def locate(rgb):
    classes = verify_artifacts()
    return shared.locate(rgb, catalog={"classes": classes, "threshold": THRESHOLD, "model": _model()})


def with_proposals(payload, predictions, truncated=False):
    return shared.with_trained_symbol_proposals(payload, predictions, truncated,
                                               catalog={"classes": verify_artifacts()})
