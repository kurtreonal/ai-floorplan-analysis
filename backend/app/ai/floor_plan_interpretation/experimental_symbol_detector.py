"""Pinned, local-only supervised symbol proposals for development review.

This checkpoint learned from partially annotated VED source pages. It is not
independently validated, calibrated, or authorized for production activation.
"""

from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
import json
import os
from pathlib import Path
from threading import Lock

import numpy as np
from PIL import Image

from app.ai.floor_plan_interpretation.candidate import (
    AffineTransform, CandidateCollection, CandidateWarning, EvidenceRegion,
    FloorPlanInterpretationPayload, PixelBounds, PixelPoint, SymbolCandidate,
)
from app.core.config import REPOSITORY_ROOT


PROVIDER = "experimental_reviewed_symbol_yolo"
CHECKPOINT = REPOSITORY_ROOT / "storage/training/symbol-detector-dev-20260925-partial-run3/weights/best.pt"
CHECKPOINT_SHA256 = "42c950006c3abe91af8218d14d6b4a52c8bc58b376457d75348dfc16992dd5cc"
DATASET_MANIFEST = REPOSITORY_ROOT / "storage/training/symbol-detector-dev-20260925-partial-v1/manifest.json"
DATASET_SHA256 = "22fab4a937e3e0cc95cc1a726e59f1da17ec7565987531fd9187e41ccec96add"
BASE_SHA256 = "0ebbc80d4a7680d14987a577cd21342b65ecfdf94632bd9a8da63ae6417644ee1"
CLASSES = {
    0: ("Smoke detector", "sheet-20:L02"),
    1: ("Pull station", "sheet-20:L05"),
    2: ("Smoke detector", "sheet-39:L07"),
    3: ("Troffer lights", "sheet-52:L08"),
}
LINKED_PROVIDER = "experimental_linked_legend_yolo"
LINKED_CHECKPOINT = REPOSITORY_ROOT / "storage/training/linked-symbol-detector-20260927-five-run1/weights/best.pt"
LINKED_CHECKPOINT_SHA256 = "c1236f94bfaf34e0b41c0ff8d7fa2c5122b06256201974bc32715e64bbf97d4c"
LINKED_DATASET_MANIFEST = REPOSITORY_ROOT / "storage/training/linked-symbol-detector-20260927-five-v1/manifest.json"
LINKED_DATASET_SHA256 = "f5e8a06963bd9b820fdb4bfe66e3815c27dad8ed64336a674426bd807ebd0b53"
LINKED_CLASSES = {
    0: ("Magnetic contact", "sheet-26:L03"),
    1: ("Duplex convenience outlet - normal power, white plate", "sheet-51:L01N"),
    2: ("Circuit homerun - panel letters and encircled circuit number", "sheet-51:L08"),
    3: ("200 mm LED recessed downlight", "sheet-52:L02"),
    4: ("Troffer lights", "u:troffer-lights"),
}
THRESHOLD = 0.25  # detector score, not calibrated probability
TILE_SIZE = 256
TILE_STRIDE = 192
NMS_IOU = 0.5
MAX_TILES = 500
MAX_CANDIDATES = 200
_inference_lock = Lock()


class ExperimentalDetectorUnavailable(ValueError):
    pass


def _digest(path: Path, maximum: int) -> str:
    if not path.is_file() or path.stat().st_size > maximum:
        raise ExperimentalDetectorUnavailable("EXPERIMENTAL_MODEL_UNAVAILABLE")
    result = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def verify_artifacts() -> None:
    if (_digest(CHECKPOINT, 30_000_000) != CHECKPOINT_SHA256
            or _digest(DATASET_MANIFEST, 2_000_000) != DATASET_SHA256):
        raise ExperimentalDetectorUnavailable("EXPERIMENTAL_MODEL_INTEGRITY_FAILED")
    manifest = json.loads(DATASET_MANIFEST.read_text(encoding="utf-8"))
    if (manifest.get("required_loss") != "positive_and_local_negative_only"
            or manifest.get("context_mode") != "full_partial"
            or manifest.get("reference_rights_exclusions", {}).get("sheet_ids") != ["sheet-51", "sheet-52"]
            or set(CLASSES) != {row["id"] for row in manifest.get("classes", [])}):
        raise ExperimentalDetectorUnavailable("EXPERIMENTAL_DATASET_INVALID")


def verify_linked_artifacts() -> None:
    if (_digest(LINKED_CHECKPOINT, 30_000_000) != LINKED_CHECKPOINT_SHA256
            or _digest(LINKED_DATASET_MANIFEST, 2_000_000) != LINKED_DATASET_SHA256):
        raise ExperimentalDetectorUnavailable("EXPERIMENTAL_MODEL_INTEGRITY_FAILED")
    manifest = json.loads(LINKED_DATASET_MANIFEST.read_text(encoding="utf-8"))
    classes = {row["id"]: row["legend_entry"] for row in manifest.get("classes", [])}
    if (manifest.get("required_loss") != "positive_and_local_negative_only"
            or manifest.get("context_mode") != "full_partial"
            or manifest.get("reference_rights_exclusions", {}).get("sheet_ids") != ["sheet-51", "sheet-52"]
            or classes != {index: value[1] for index, value in LINKED_CLASSES.items()}):
        raise ExperimentalDetectorUnavailable("EXPERIMENTAL_DATASET_INVALID")


def configuration_sha256() -> str:
    values = {"provider": PROVIDER, "checkpoint": CHECKPOINT_SHA256,
              "dataset": DATASET_SHA256, "classes": CLASSES,
              "threshold": THRESHOLD, "tile": TILE_SIZE, "stride": TILE_STRIDE,
              "nms_iou": NMS_IOU, "max_tiles": MAX_TILES,
              "max_candidates": MAX_CANDIDATES}
    return sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def linked_configuration_sha256() -> str:
    values = {"provider": LINKED_PROVIDER, "checkpoint": LINKED_CHECKPOINT_SHA256,
              "dataset": LINKED_DATASET_SHA256, "classes": LINKED_CLASSES,
              "threshold": THRESHOLD, "tile": TILE_SIZE, "stride": TILE_STRIDE,
              "nms_iou": NMS_IOU, "max_tiles": MAX_TILES,
              "max_candidates": MAX_CANDIDATES}
    return sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


@lru_cache(maxsize=1)
def _model():
    os.environ["YOLO_AUTOINSTALL"] = "false"
    import ultralytics.utils.checks as dependency_checks
    dependency_checks.AUTOINSTALL = False
    from ultralytics import YOLO
    return YOLO(str(CHECKPOINT))


@lru_cache(maxsize=1)
def _linked_model():
    os.environ["YOLO_AUTOINSTALL"] = "false"
    import ultralytics.utils.checks as dependency_checks
    dependency_checks.AUTOINSTALL = False
    from ultralytics import YOLO
    return YOLO(str(LINKED_CHECKPOINT))


def _origins(length: int) -> list[int]:
    values = list(range(0, max(1, length - TILE_SIZE + 1), TILE_STRIDE))
    final = max(0, length - TILE_SIZE)
    if values[-1] != final:
        values.append(final)
    return values


def tile_positions(width, height, *, dual_phase=False):
    positions = [(x, y) for y in _origins(height) for x in _origins(width)]
    if dual_phase:
        # A deterministic second lattice, independent of any target positions.
        # Retain the existing page cap; never widen the resource allowance.
        shifted = [(x, y) for y in range(128, max(128, height-TILE_SIZE+1), TILE_STRIDE)
                   for x in range(128, max(128, width-TILE_SIZE+1), TILE_STRIDE)]
        if len(positions)+len(shifted) <= MAX_TILES:
            positions.extend(shifted)
    return positions


def _iou(a, b) -> float:
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return intersection / (area_a + area_b - intersection) if area_a + area_b > intersection else 0.0


def fuse(predictions):
    kept = []
    for row in sorted(predictions, key=lambda value: -value["score"]):
        if not any(row["class_id"] == prior["class_id"]
                   and _iou(row["bbox"], prior["bbox"]) >= NMS_IOU for prior in kept):
            kept.append(row)
    return kept


def locate(rgb: np.ndarray, *, linked: bool = False, catalog=None) -> tuple[tuple[dict, ...], bool]:
    if catalog is None:
        (verify_linked_artifacts if linked else verify_artifacts)()
    if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype != np.uint8:
        raise ExperimentalDetectorUnavailable("EXPERIMENTAL_PAGE_INVALID")
    height, width = rgb.shape[:2]
    if max(width, height) > 10_000 or width * height > 60_000_000:
        raise ExperimentalDetectorUnavailable("EXPERIMENTAL_PAGE_TOO_LARGE")
    origins = tile_positions(width, height, dual_phase=catalog is not None)
    if len(origins) > MAX_TILES:
        raise ExperimentalDetectorUnavailable("EXPERIMENTAL_TILE_LIMIT")
    source = Image.fromarray(rgb)
    predictions = []
    with _inference_lock:
        model = catalog["model"] if catalog is not None else _linked_model() if linked else _model()
        classes = catalog["classes"] if catalog is not None else LINKED_CLASSES if linked else CLASSES
        threshold = catalog["threshold"] if catalog is not None else THRESHOLD
        for offset in range(0, len(origins), 8):
            positions = origins[offset:offset + 8]
            tiles = [source.crop((x, y, x + TILE_SIZE, y + TILE_SIZE)) for x, y in positions]
            results = model.predict(tiles, imgsz=320, conf=threshold,
                                    classes=sorted(classes),
                                    batch=8, max_det=100,
                                    device="cpu", verbose=False)
            if len(results) != len(positions):
                raise ExperimentalDetectorUnavailable("EXPERIMENTAL_OUTPUT_INVALID")
            for (x, y), result in zip(positions, results):
                for box in result.boxes:
                    x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
                    raw_class, score = float(box.cls[0]), float(box.conf[0])
                    if (not np.isfinite([x1, y1, x2, y2, raw_class, score]).all()
                            or not raw_class.is_integer() or not 0 <= score <= 1):
                        raise ExperimentalDetectorUnavailable("EXPERIMENTAL_OUTPUT_INVALID")
                    source_box = (max(0.0, x + x1), max(0.0, y + y1),
                                  min(float(width), x + x2), min(float(height), y + y2))
                    if source_box[0] >= source_box[2] or source_box[1] >= source_box[3]:
                        continue
                    class_id = int(raw_class)
                    if class_id not in classes or not np.isfinite([*source_box, score]).all():
                        raise ExperimentalDetectorUnavailable("EXPERIMENTAL_OUTPUT_INVALID")
                    predictions.append({"bbox": source_box, "class_id": class_id,
                                        "score": score, "tile_origin": (x, y)})
                    if len(predictions) > 5000:
                        raise ExperimentalDetectorUnavailable("EXPERIMENTAL_CANDIDATE_LIMIT")
    fused = fuse(predictions)
    return tuple(fused[:MAX_CANDIDATES]), len(fused) > MAX_CANDIDATES


def with_trained_symbol_proposals(payload, predictions, truncated=False, *, linked=False, catalog=None):
    classes = catalog["classes"] if catalog is not None else LINKED_CLASSES if linked else CLASSES
    region_id = "region-0002"
    symbols = tuple(
        SymbolCandidate(
            id=f"symbol-{index:04d}", mapping_state="unknown", catalog_class_id=None,
            observed_label=classes[row["class_id"]][0],
            center=PixelPoint(x=(row["bbox"][0] + row["bbox"][2]) / 2,
                              y=(row["bbox"][1] + row["bbox"][3]) / 2),
            bounds=PixelBounds(x=row["bbox"][0], y=row["bbox"][1],
                               width=row["bbox"][2] - row["bbox"][0],
                               height=row["bbox"][3] - row["bbox"][1]),
            orientation_degrees=None, evidence_refs=(f"region:{region_id}",),
            ambiguity="ambiguous",
        ) for index, row in enumerate(predictions, start=1)
    )
    warnings = payload.warnings + (
        CandidateWarning(
            code="experimental_supervised_symbol_scope", severity="warning",
            message=("One development-only supervised detector trained on all 56 eligible drawing-legend entries. Inclusion is not successful detection; scarce and conflicting examples remain limitations. Scores are not calibrated. Every proposal requires drawing-legend review; no production or independent accuracy approval." if catalog is not None else
                     "Development-only supervised YOLO proposals for five linked legend IDs: troffer, duplex outlet, circuit homerun, LED downlight, and magnetic contact. Same-source diagnostics only; grid/text mistakes occur. No independent accuracy or production approval. Confirm drawing legend and every candidate before use." if linked else
                     "Development-only supervised YOLO proposals for troffer, smoke detector, and Pull station. Same-source diagnostics only; no independent accuracy or production approval. Confirm drawing legend and every candidate before use."),
        ),
    ) + tuple(
        CandidateWarning(
            code="experimental_detector_score", severity="info",
            message=(f"Training legend {classes[row['class_id']][1]}; score {row['score']:.4f} "
                     f"is not calibrated confidence; tile origin {row['tile_origin']} source pixels."),
            entity_refs=(f"symbol:symbol-{index:04d}",),
        ) for index, row in enumerate(predictions, start=1)
    )
    if truncated:
        warnings += (CandidateWarning(code="experimental_detector_truncated", severity="warning",
                                      message="Candidate cap reached; other predictions were omitted."),)
    result = payload.model_copy(update={
        "document_state": "partial" if truncated else payload.document_state,
        "regions": payload.regions + (EvidenceRegion(
            id=region_id, kind="overview",
            bounds=PixelBounds(x=0, y=0, width=payload.source_plane.width_pixels,
                               height=payload.source_plane.height_pixels),
            local_to_source=AffineTransform(a=1, b=0, c=0, d=1, e=0, f=0)),),
        "symbols": CandidateCollection(
            state="partial" if truncated else "completed" if symbols else "empty",
            items=symbols, truncated=truncated),
        "warnings": warnings,
    })
    return FloorPlanInterpretationPayload.model_validate(result.model_dump())
