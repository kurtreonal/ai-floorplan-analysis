"""Frozen, development-only Pull station template proposals.

Similarity is not a calibrated confidence or an approved class mapping.
The supplied source drawing is copied to ignored local model storage and
verified before every run; its original and reviewed annotations stay intact.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json

import cv2
import numpy as np

from app.ai.floor_plan_interpretation.candidate import (
    AffineTransform, CandidateCollection, CandidateWarning, EvidenceRegion,
    FloorPlanInterpretationPayload,
    PixelBounds, PixelPoint, SymbolCandidate,
)
from app.core.config import REPOSITORY_ROOT


PROVIDER = "experimental_pull_station_template"
SOURCE_SHA256 = "8cd5962e233fe1dbbe2de981a6169665720e49fb0b2da81215d7532a4299b1ed"
LEGEND_IDENTITY = "sheet-20:L05"
TEMPLATES = (
    ("1421451ddf2e1217c0833e17", (1043, 1779, 1071, 1807)),
    ("0fa577e32ac65b7d915452e0", (1986, 1895, 2014, 1924)),
)
THRESHOLD = 0.60
SCALES = (1.0, 1.2)  # Cross-page adjustment; sheet-19 is development data.
SCALE_SELECTION_INTERIOR_MARGIN = 0.09
PEAK_WINDOW = 9
NMS_CENTER_PIXELS = 14
NMS_IOU = 0.30
MAX_CANDIDATES = 200
LOCAL_SOURCE = REPOSITORY_ROOT / "models/vlm/pull-station-template-v1/source-sheet-21.jpg"


def configuration_sha256() -> str:
    values = {"provider": PROVIDER, "source_sha256": SOURCE_SHA256,
              "templates": TEMPLATES, "threshold": THRESHOLD,
              "scales": SCALES, "scale_selection_interior_margin": SCALE_SELECTION_INTERIOR_MARGIN,
              "peak_window": PEAK_WINDOW, "nms_center": NMS_CENTER_PIXELS,
              "nms_iou": NMS_IOU, "search": "full_image_scale_selected_by_interior_consensus"}
    return sha256(json.dumps(values, sort_keys=True).encode("utf-8")).hexdigest()


class ExperimentalLocatorUnavailable(ValueError):
    pass


def source_digest(path: Path) -> str:
    if not path.is_file() or path.stat().st_size > 25 * 1024 * 1024:
        raise ExperimentalLocatorUnavailable("EXPERIMENTAL_TEMPLATE_UNAVAILABLE")
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != SOURCE_SHA256:
        raise ExperimentalLocatorUnavailable("EXPERIMENTAL_TEMPLATE_INTEGRITY_FAILED")
    return digest.hexdigest()


def _iou(a, b) -> float:
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    overlap = max(0, x1 - x0) * max(0, y1 - y0)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return overlap / (area_a + area_b - overlap) if area_a + area_b > overlap else 0.0


def _center_distance(a, b) -> float:
    return (((a[0] + a[2] - b[0] - b[2]) / 2) ** 2
            + ((a[1] + a[3] - b[1] - b[3]) / 2) ** 2) ** 0.5


def _interior_count(candidates, width: int) -> int:
    """Use interior matches to choose scale, but still return edge proposals."""
    margin = width * SCALE_SELECTION_INTERIOR_MARGIN
    return sum(margin <= (item["bbox"][0] + item["bbox"][2]) / 2 <= width - margin
               for item in candidates)


def locate(rgb: np.ndarray, template_source_path: Path) -> tuple[dict, ...]:
    """Return full-image, native-pixel matches with immutable template IDs."""
    source_digest(template_source_path)
    if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype != np.uint8:
        raise ExperimentalLocatorUnavailable("EXPERIMENTAL_PAGE_INVALID")
    if max(rgb.shape[:2]) > 4096 or rgb.shape[0] * rgb.shape[1] > 60_000_000:
        raise ExperimentalLocatorUnavailable("EXPERIMENTAL_PAGE_TOO_LARGE")
    template_page = cv2.imread(str(template_source_path), cv2.IMREAD_GRAYSCALE)
    if template_page is None or template_page.shape != (3264, 2164):
        raise ExperimentalLocatorUnavailable("EXPERIMENTAL_TEMPLATE_INVALID")
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    candidates_by_scale = []
    for scale in SCALES:
        candidates = []
        for template_id, (x0, y0, x1, y1) in TEMPLATES:
            patch = template_page[y0:y1, x0:x1]
            if scale != 1.0:
                patch = cv2.resize(patch, None, fx=scale, fy=scale)
            if patch.std() < 3 or gray.shape[0] < patch.shape[0] or gray.shape[1] < patch.shape[1]:
                raise ExperimentalLocatorUnavailable("EXPERIMENTAL_TEMPLATE_INVALID")
            response = cv2.matchTemplate(gray, patch, cv2.TM_CCOEFF_NORMED)
            peaks = (response >= THRESHOLD) & (response == cv2.dilate(response, np.ones((PEAK_WINDOW, PEAK_WINDOW), np.uint8)))
            ys, xs = np.where(peaks)
            if len(xs) > 1000:
                raise ExperimentalLocatorUnavailable("EXPERIMENTAL_CANDIDATE_CAP")
            for x, y in zip(xs.tolist(), ys.tolist()):
                candidates.append({"bbox": (x, y, x + patch.shape[1], y + patch.shape[0]),
                                   "score": float(response[y, x]), "template_id": template_id,
                                   "scale": scale})
        kept = []
        for candidate in sorted(candidates, key=lambda item: -item["score"]):
            if not any(_center_distance(candidate["bbox"], previous["bbox"]) < NMS_CENTER_PIXELS
                       or _iou(candidate["bbox"], previous["bbox"]) > NMS_IOU for previous in kept):
                kept.append(candidate)
        if len(kept) > MAX_CANDIDATES:
            raise ExperimentalLocatorUnavailable("EXPERIMENTAL_CANDIDATE_CAP")
        candidates_by_scale.append(kept)
    selected = max(candidates_by_scale, key=lambda items: _interior_count(items, gray.shape[1]))
    return tuple(selected)


def with_pull_station_proposals(payload, matches):
    """Replace generic demo symbols while retaining existing wall/room proposals."""
    symbols = tuple(
        SymbolCandidate(
            id=f"symbol-{index:04d}", mapping_state="unknown", catalog_class_id=None,
            observed_label="Pull station template proposal",
            center=PixelPoint(x=(box[0] + box[2]) / 2, y=(box[1] + box[3]) / 2),
            bounds=PixelBounds(x=box[0], y=box[1], width=box[2] - box[0], height=box[3] - box[1]),
            orientation_degrees=None, evidence_refs=("region:region-0002",), ambiguity="ambiguous",
        )
        for index, match in enumerate(matches, start=1)
        for box in (match["bbox"],)
    )
    warnings = payload.warnings + (
        CandidateWarning(
            code="experimental_pull_station_scope", severity="warning",
            message="Pull station only; two Group 7 templates, 1.0/1.2 page-scale selection from interior matches. Sheet-19 was used for tuning. Similarity is not calibrated confidence. Verify every proposal and approved legend mapping.",
        ),
    ) + tuple(
        CandidateWarning(
            code="template_similarity", severity="info",
            message=f"{match['template_id']} scale {match['scale']:.1f} similarity {match['score']:.4f}; not calibrated confidence.",
            entity_refs=(f"symbol:symbol-{index:04d}",),
        )
        for index, match in enumerate(matches, start=1)
    )
    result = payload.model_copy(update={
        "regions": payload.regions + (EvidenceRegion(
            id="region-0002", kind="overview",
            bounds=PixelBounds(x=0, y=0, width=payload.source_plane.width_pixels,
                               height=payload.source_plane.height_pixels),
            local_to_source=AffineTransform(a=1, b=0, c=0, d=1, e=0, f=0),
        ),),
        "symbols": CandidateCollection(state="completed" if symbols else "empty", items=symbols),
        "warnings": warnings,
    })
    return FloorPlanInterpretationPayload.model_validate(result.model_dump())
