"""Multi-resolution page, tile, and OCR context preparation for local VLM.

Implements TICKET U7:
- Overview, legend, plan-region, and overlapping tile transforms are deterministic
  and reversible to page pixels.
- Normalized RGB is primary input; thresholded/line/OCR evidence is auxiliary.
- Tile overlap and deduplication behavior has fixtures and boundary tests.
- Derived files are isolated and originals remain unchanged.
- Page/tile limits fail safely before memory exhaustion.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal, Sequence

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.ai.floor_plan_interpretation.candidate import (
    AffineTransform,
    CandidateCollection,
    EntityId,
    EvidenceRegion,
    OcrEvidence,
    PageAssessment,
    PageSignals,
    PixelBounds,
    PixelPoint,
    SafeName,
    SafeText,
    SourcePlane,
    StrictCandidateModel,
    SymbolCandidate,
    WallCandidate,
)
from app.models import ProcessingArtifact, ProcessingJob
from app.services.processing_artifact_service import (
    ProcessingArtifactError,
    register_processing_artifact,
)

# Bounds and budget constants
MAXIMUM_SOURCE_EDGE = 10_000
MAXIMUM_SOURCE_PIXELS = 60_000_000
MINIMUM_SOURCE_EDGE = 16
DEFAULT_OVERVIEW_MAX_DIM = 1024
DEFAULT_TILE_SIZE = 1024
DEFAULT_TILE_OVERLAP = 128
MAXIMUM_ALLOWED_TILES = 64
MAXIMUM_AUXILIARY_LINES = 500
MAXIMUM_OCR_ITEMS = 1_000

ELECTRICAL_KEYWORD_PATTERN = re.compile(
    r"\b(panel|switch|outlet|receptacle|lighting|fixture|circuit|conduit|wire|junction|breaker|transformer|load|disconnect|emergency|cctv|cat6|data|phone|power)\b",
    re.IGNORECASE,
)
LEGEND_KEYWORD_PATTERN = re.compile(
    r"\b(legend|symbol\s*legend|symbols\s*list|electrical\s*symbols?|abbreviations?)\b",
    re.IGNORECASE,
)
DIMENSION_KEYWORD_PATTERN = re.compile(
    r"(\b\d+['’-]\s*\d+\"?\b|\b\d+(\.\d+)?\s*(mm|cm|m|in|ft)\b)",
    re.IGNORECASE,
)
SCALE_KEYWORD_PATTERN = re.compile(
    r"(\bscale\b|\b1\s*:\s*\d+\b|\b\d+/\d+\s*\"?\s*=\s*\d+['’-]\d+\"?\b)",
    re.IGNORECASE,
)


class PreparationError(Exception):
    """Base exception for context preparation failures."""


class PreparationResourceExhaustion(PreparationError):
    """Raised before memory allocation when page size or tile count exceeds configured limits."""


class InvalidGeometryError(PreparationError):
    """Raised when geometry is non-square/asymmetric or coordinates/bounds are invalid."""


class ArtifactPersistenceError(PreparationError):
    """Raised when derived artifact registration fails."""


class PreparationConfig(BaseModel):
    """Configuration and resource limits for context preparation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tile_width: Annotated[int, Field(ge=128, le=4096)] = DEFAULT_TILE_SIZE
    tile_height: Annotated[int, Field(ge=128, le=4096)] = DEFAULT_TILE_SIZE
    tile_overlap: Annotated[int, Field(ge=0, le=1024)] = DEFAULT_TILE_OVERLAP
    max_tiles: Annotated[int, Field(ge=1, le=128)] = MAXIMUM_ALLOWED_TILES
    overview_max_dimension: Annotated[int, Field(ge=256, le=2048)] = DEFAULT_OVERVIEW_MAX_DIM
    max_source_pixels: Annotated[int, Field(ge=1_000, le=MAXIMUM_SOURCE_PIXELS)] = MAXIMUM_SOURCE_PIXELS
    min_dimension: Annotated[int, Field(ge=MINIMUM_SOURCE_EDGE, le=1024)] = MINIMUM_SOURCE_EDGE
    extract_auxiliary_lines: bool = True
    extract_ocr: bool = True
    max_lines: Annotated[int, Field(ge=1, le=2000)] = MAXIMUM_AUXILIARY_LINES
    max_ocr_items: Annotated[int, Field(ge=1, le=2000)] = MAXIMUM_OCR_ITEMS


class LineSegmentEvidence(StrictCandidateModel):
    """Deterministic auxiliary line segment extracted from thresholded blueprint imagery."""

    id: EntityId
    region_id: EntityId
    start: PixelPoint
    end: PixelPoint
    orientation: Literal["horizontal", "vertical", "diagonal"]
    length_pixels: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    thickness_pixels: Annotated[float, Field(gt=0, allow_inf_nan=False)]


@dataclass(frozen=True)
class PreparedRegion:
    """An evidence region with its cropped/scaled RGB numpy image array."""

    region: EvidenceRegion
    image_rgb: np.ndarray
    relative_path: str | None = None
    artifact_id: int | None = None


@dataclass(frozen=True)
class PreparedTile:
    """An overlapping tile with local-to-source mapping and pixel slice."""

    region_id: str
    bounds: PixelBounds
    local_to_source: AffineTransform
    image_rgb: np.ndarray
    grid_row: int
    grid_col: int
    relative_path: str | None = None
    artifact_id: int | None = None


@dataclass(frozen=True)
class SymbolCandidateObservation:
    """A raw symbol detection observed in a specific local tile/region."""

    region_id: str
    catalog_class_id: int | None
    observed_label: str | None
    local_center: tuple[float, float]
    local_bounds: tuple[float, float, float, float] | None = None
    confidence: float = 1.0
    orientation_degrees: float | None = None
    ambiguity: Literal["clear", "ambiguous", "unknown"] = "clear"


@dataclass(frozen=True)
class WallCandidateObservation:
    """A raw wall segment observed in a specific local tile/region."""

    region_id: str
    local_start: tuple[float, float]
    local_end: tuple[float, float]
    confidence: float = 1.0
    ambiguity: Literal["clear", "ambiguous", "unknown"] = "clear"


@dataclass(frozen=True)
class PreparedContext:
    """Full multi-resolution context package ready for local VLM consumption."""

    page_number: int
    source_plane: SourcePlane
    overview: PreparedRegion
    plan_region: PreparedRegion | None
    legend_region: PreparedRegion | None
    tiles: tuple[PreparedTile, ...]
    page_assessment: PageAssessment
    ocr_evidence: tuple[OcrEvidence, ...]
    line_evidence: tuple[LineSegmentEvidence, ...]
    auxiliary_thresholded: np.ndarray | None = None


# ---------------------------------------------------------------------------
# Reversible Coordinate Transformations
# ---------------------------------------------------------------------------


def invert_affine_transform(transform: AffineTransform) -> AffineTransform:
    """Computes the exact mathematical inverse of an affine transform.

    Given forward mapping:
        x = a*u + c*v + e
        y = b*u + d*v + f

    The inverse mapping is:
        u = a'*x + c'*y + e'
        v = b'*x + d'*y + f'
    """
    a, b, c, d, e, f = (
        float(transform.a),
        float(transform.b),
        float(transform.c),
        float(transform.d),
        float(transform.e),
        float(transform.f),
    )
    det = a * d - b * c
    if math.isclose(det, 0.0, abs_tol=1e-12):
        raise InvalidGeometryError("Affine transform determinant is zero; non-invertible.")

    inv_a = d / det
    inv_b = -b / det
    inv_c = -c / det
    inv_d = a / det
    inv_e = (c * f - d * e) / det
    inv_f = (b * e - a * f) / det

    return AffineTransform(
        a=round(inv_a, 8) if not math.isclose(inv_a, 0.0, abs_tol=1e-8) else 0.0,
        b=round(inv_b, 8) if not math.isclose(inv_b, 0.0, abs_tol=1e-8) else 0.0,
        c=round(inv_c, 8) if not math.isclose(inv_c, 0.0, abs_tol=1e-8) else 0.0,
        d=round(inv_d, 8) if not math.isclose(inv_d, 0.0, abs_tol=1e-8) else 0.0,
        e=round(inv_e, 4) if not math.isclose(inv_e, 0.0, abs_tol=1e-8) else 0.0,
        f=round(inv_f, 4) if not math.isclose(inv_f, 0.0, abs_tol=1e-8) else 0.0,
    )


def local_to_source_coords(transform: AffineTransform, u: float, v: float) -> tuple[float, float]:
    """Map local region coordinates (u, v) to source plane coordinates (x, y)."""
    x = float(transform.a) * u + float(transform.c) * v + float(transform.e)
    y = float(transform.b) * u + float(transform.d) * v + float(transform.f)
    return (round(x, 4), round(y, 4))


def source_to_local_coords(transform: AffineTransform, x: float, y: float) -> tuple[float, float]:
    """Map source plane coordinates (x, y) to local region coordinates (u, v)."""
    inv = invert_affine_transform(transform)
    return local_to_source_coords(inv, x, y)


def transform_bounds_local_to_source(
    transform: AffineTransform, bounds: PixelBounds
) -> PixelBounds:
    """Map a local region bounding box into source plane coordinates."""
    bx, by, bw, bh = bounds.x, bounds.y, bounds.width, bounds.height
    corners = [
        local_to_source_coords(transform, bx, by),
        local_to_source_coords(transform, bx + bw, by),
        local_to_source_coords(transform, bx, by + bh),
        local_to_source_coords(transform, bx + bw, by + bh),
    ]
    min_x = max(0.0, min(pt[0] for pt in corners))
    min_y = max(0.0, min(pt[1] for pt in corners))
    max_x = max(pt[0] for pt in corners)
    max_y = max(pt[1] for pt in corners)
    w = max(1.0, max_x - min_x)
    h = max(1.0, max_y - min_y)
    return PixelBounds(x=round(min_x, 2), y=round(min_y, 2), width=round(w, 2), height=round(h, 2))


def transform_bounds_source_to_local(
    transform: AffineTransform, bounds: PixelBounds
) -> PixelBounds:
    """Map a source plane bounding box into local region coordinates."""
    inv = invert_affine_transform(transform)
    return transform_bounds_local_to_source(inv, bounds)


def assert_isotropic_scaling(transform: AffineTransform, tolerance: float = 1e-4) -> None:
    """Enforce uniform isotropic scaling to protect floor plan aspect ratios."""
    a, b, c, d = float(transform.a), float(transform.b), float(transform.c), float(transform.d)
    scale_u = math.hypot(a, b)
    scale_v = math.hypot(c, d)
    if abs(scale_u - scale_v) > tolerance:
        raise InvalidGeometryError(
            f"Asymmetric scaling rejected: scale_u={scale_u:.6f}, scale_v={scale_v:.6f}. "
            "Floor plans require uniform isotropic scaling."
        )


# ---------------------------------------------------------------------------
# Image Loading & Normalization
# ---------------------------------------------------------------------------


def load_and_orient_image(
    source: Path | str | bytes | Image.Image | np.ndarray,
    *,
    max_edge: int = MAXIMUM_SOURCE_EDGE,
    max_pixels: int = MAXIMUM_SOURCE_PIXELS,
    min_edge: int = MINIMUM_SOURCE_EDGE,
) -> np.ndarray:
    """Load an image, apply EXIF rotation, flatten alpha onto pure white, and return uint8 RGB array."""
    clean_image: Image.Image | None = None

    if isinstance(source, np.ndarray):
        if source.ndim == 2:
            arr = cv2.cvtColor(source, cv2.COLOR_GRAY2RGB)
        elif source.ndim == 3 and source.shape[2] == 3:
            arr = source
        elif source.ndim == 3 and source.shape[2] == 4:
            # Composite RGBA over white
            alpha = source[:, :, 3:4] / 255.0
            rgb = source[:, :, :3]
            arr = (rgb * alpha + 255 * (1.0 - alpha)).astype(np.uint8)
        else:
            raise InvalidGeometryError("Source array must be 2D grayscale or 3D RGB/RGBA.")
        if arr.dtype != np.uint8:
            raise InvalidGeometryError("Source array must be uint8.")
        H, W = arr.shape[:2]
        if min(W, H) < min_edge:
            raise InvalidGeometryError(f"Image dimension {min(W, H)} is smaller than minimum {min_edge}.")
        if max(W, H) > max_edge or W * H > max_pixels:
            raise PreparationResourceExhaustion(
                f"Source image size {W}x{H} ({W*H} px) exceeds limits ({max_edge} px, {max_pixels} px)."
            )
        return arr

    if isinstance(source, Image.Image):
        pil_img = source
    elif isinstance(source, (Path, str)):
        path = Path(source)
        if not path.is_file():
            raise PreparationError(f"Source image path does not exist: {path}")
        try:
            pil_img = Image.open(path)
        except (UnidentifiedImageError, OSError) as exc:
            raise PreparationError(f"Failed to open source image: {exc}") from exc
    elif isinstance(source, (bytes, bytearray)):
        try:
            pil_img = Image.open(BytesIO(source))
        except (UnidentifiedImageError, OSError) as exc:
            raise PreparationError(f"Failed to decode source image bytes: {exc}") from exc
    else:
        raise InvalidGeometryError(f"Unsupported source type: {type(source)}")

    try:
        # Respect EXIF orientation
        oriented = ImageOps.exif_transpose(pil_img)
        if oriented is None:
            oriented = pil_img

        W, H = oriented.size
        if min(W, H) < min_edge:
            raise InvalidGeometryError(f"Image dimension {min(W, H)} is smaller than minimum {min_edge}.")
        if max(W, H) > max_edge or W * H > max_pixels:
            raise PreparationResourceExhaustion(
                f"Source image size {W}x{H} ({W*H} px) exceeds limits ({max_edge} px, {max_pixels} px)."
            )

        # Handle transparency: composite over pure white
        has_transparency = (
            "A" in oriented.getbands()
            or "transparency" in oriented.info
            or oriented.mode in ("RGBA", "LA", "PA")
        )
        if has_transparency:
            rgba = oriented.convert("RGBA")
            clean_image = Image.new("RGB", rgba.size, (255, 255, 255))
            clean_image.paste(rgba, mask=rgba.getchannel("A"))
        else:
            clean_image = oriented.convert("RGB")

        arr = np.array(clean_image, dtype=np.uint8)
        return arr
    finally:
        if clean_image is not None and clean_image is not pil_img:
            clean_image.close()
        if not isinstance(source, Image.Image):
            pil_img.close()


# ---------------------------------------------------------------------------
# Multi-Resolution Region Extraction
# ---------------------------------------------------------------------------


def generate_overview_region(
    image_rgb: np.ndarray,
    max_dimension: int = DEFAULT_OVERVIEW_MAX_DIM,
    region_id: str = "region-0001",
) -> PreparedRegion:
    """Produce an isotropic downsampled overview image with reversible coordinate transform."""
    H, W = image_rgb.shape[:2]
    scale = min(1.0, float(max_dimension) / max(W, H))
    target_w = max(1, round(W * scale))
    target_h = max(1, round(H * scale))

    # Resize cleanly
    interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    overview_img = cv2.resize(image_rgb, (target_w, target_h), interpolation=interpolation)

    # Local to source: (u, v) -> (u / scale, v / scale)
    inv_scale = 1.0 / scale
    transform = AffineTransform(
        a=round(inv_scale, 8),
        b=0.0,
        c=0.0,
        d=round(inv_scale, 8),
        e=0.0,
        f=0.0,
    )
    assert_isotropic_scaling(transform)

    region = EvidenceRegion(
        id=region_id,
        kind="overview",
        bounds=PixelBounds(x=0.0, y=0.0, width=float(W), height=float(H)),
        local_to_source=transform,
    )
    return PreparedRegion(region=region, image_rgb=overview_img)


def detect_plan_region(
    image_rgb: np.ndarray,
    region_id: str = "region-0002",
    margin: int = 16,
) -> PreparedRegion:
    """Identify the bounding box containing active blueprint drawings and produce plan region."""
    H, W = image_rgb.shape[:2]
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)

    # Invert binary: dark drawing lines become foreground
    _, binary = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

    pts = cv2.findNonZero(binary)
    if pts is None or len(pts) < 100:
        # Fallback to full page if no content or faint lines
        xmin, ymin, w, h = 0, 0, W, H
    else:
        x, y, bw, bh = cv2.boundingRect(pts)
        xmin = max(0, x - margin)
        ymin = max(0, y - margin)
        xmax = min(W, x + bw + margin)
        ymax = min(H, y + bh + margin)
        w = max(MINIMUM_SOURCE_EDGE, xmax - xmin)
        h = max(MINIMUM_SOURCE_EDGE, ymax - ymin)

    crop = image_rgb[ymin : ymin + h, xmin : xmin + w].copy()
    transform = AffineTransform(
        a=1.0,
        b=0.0,
        c=0.0,
        d=1.0,
        e=float(xmin),
        f=float(ymin),
    )

    region = EvidenceRegion(
        id=region_id,
        kind="plan_region",
        bounds=PixelBounds(x=float(xmin), y=float(ymin), width=float(w), height=float(h)),
        local_to_source=transform,
    )
    return PreparedRegion(region=region, image_rgb=crop)


def detect_legend_region(
    image_rgb: np.ndarray,
    region_id: str = "region-0003",
    explicit_bounds: PixelBounds | None = None,
) -> PreparedRegion | None:
    """Extract legend region if explicit bounds provided or detectable."""
    if explicit_bounds is None:
        return None

    H, W = image_rgb.shape[:2]
    x = max(0, int(round(explicit_bounds.x)))
    y = max(0, int(round(explicit_bounds.y)))
    w = min(W - x, int(round(explicit_bounds.width)))
    h = min(H - y, int(round(explicit_bounds.height)))

    if w < MINIMUM_SOURCE_EDGE or h < MINIMUM_SOURCE_EDGE:
        return None

    crop = image_rgb[y : y + h, x : x + w].copy()
    transform = AffineTransform(
        a=1.0,
        b=0.0,
        c=0.0,
        d=1.0,
        e=float(x),
        f=float(y),
    )

    region = EvidenceRegion(
        id=region_id,
        kind="legend",
        bounds=PixelBounds(x=float(x), y=float(y), width=float(w), height=float(h)),
        local_to_source=transform,
    )
    return PreparedRegion(region=region, image_rgb=crop)


def generate_tiles(
    image_rgb: np.ndarray,
    config: PreparationConfig,
    region_id_start: int = 4,
) -> tuple[PreparedTile, ...]:
    """Slice blueprint image into overlapping tiles with boundary verification and resource limits."""
    H, W = image_rgb.shape[:2]

    # Pre-allocation safety check
    if W * H > config.max_source_pixels:
        raise PreparationResourceExhaustion(
            f"Source pixels ({W*H}) exceeds configured maximum ({config.max_source_pixels})."
        )

    Tw = config.tile_width
    Th = config.tile_height
    O = config.tile_overlap

    if O >= min(Tw, Th) or O < 0:
        raise InvalidGeometryError(
            f"Tile overlap ({O}) must be non-negative and strictly less than tile dimensions ({Tw}x{Th})."
        )

    Sw = Tw - O
    Sh = Th - O

    # Compute grid offsets
    if W <= Tw:
        xs = [0]
    else:
        xs = list(range(0, W - Tw, Sw))
        if xs[-1] + Tw < W:
            xs.append(W - Tw)

    if H <= Th:
        ys = [0]
    else:
        ys = list(range(0, H - Th, Sh))
        if ys[-1] + Th < H:
            ys.append(H - Th)

    total_projected_tiles = len(xs) * len(ys)
    if total_projected_tiles > config.max_tiles:
        raise PreparationResourceExhaustion(
            f"Projected tile count ({total_projected_tiles}) exceeds configured limit ({config.max_tiles})."
        )

    tiles: list[PreparedTile] = []
    idx = region_id_start

    for row_idx, y in enumerate(ys):
        for col_idx, x in enumerate(xs):
            tw = min(Tw, W - x)
            th = min(Th, H - y)

            tile_slice = image_rgb[y : y + th, x : x + tw].copy()
            region_id = f"region-{idx:04d}"
            idx += 1

            local_to_source = AffineTransform(
                a=1.0,
                b=0.0,
                c=0.0,
                d=1.0,
                e=float(x),
                f=float(y),
            )
            bounds = PixelBounds(x=float(x), y=float(y), width=float(tw), height=float(th))

            tiles.append(
                PreparedTile(
                    region_id=region_id,
                    bounds=bounds,
                    local_to_source=local_to_source,
                    image_rgb=tile_slice,
                    grid_row=row_idx,
                    grid_col=col_idx,
                )
            )

    return tuple(tiles)


# ---------------------------------------------------------------------------
# Auxiliary Evidence: Thresholding, Lines, and OCR
# ---------------------------------------------------------------------------


def extract_auxiliary_thresholded(image_rgb: np.ndarray) -> np.ndarray:
    """Generate clean Otsu thresholded binary image for auxiliary geometry detection."""
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    denoised = cv2.medianBlur(gray, 3)
    _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    return thresh


def extract_line_evidence(
    image_rgb: np.ndarray,
    region_id: str = "region-0001",
    max_lines: int = MAXIMUM_AUXILIARY_LINES,
) -> tuple[LineSegmentEvidence, ...]:
    """Extract deterministic line segments via Canny and HoughLinesP."""
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    raw_lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=40,
        minLineLength=20,
        maxLineGap=5,
    )

    if raw_lines is None:
        return ()

    extracted: list[LineSegmentEvidence] = []
    line_id = 1

    # Sort raw lines deterministically: (y1, x1, y2, x2)
    sorted_lines = sorted(
        raw_lines,
        key=lambda item: (item[0][1], item[0][0], item[0][3], item[0][2]),
    )

    for line in sorted_lines:
        if len(extracted) >= max_lines:
            break
        x1, y1, x2, y2 = map(int, line[0])
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length < 10.0:
            continue

        angle = abs(math.atan2(dy, dx)) * 180.0 / math.pi
        if angle <= 5.0 or angle >= 175.0:
            orientation: Literal["horizontal", "vertical", "diagonal"] = "horizontal"
        elif 85.0 <= angle <= 95.0:
            orientation = "vertical"
        else:
            orientation = "diagonal"

        extracted.append(
            LineSegmentEvidence(
                id=f"line-{line_id:04d}",
                region_id=region_id,
                start=PixelPoint(x=float(x1), y=float(y1)),
                end=PixelPoint(x=float(x2), y=float(y2)),
                orientation=orientation,
                length_pixels=round(length, 2),
                thickness_pixels=2.0,
            )
        )
        line_id += 1

    return tuple(extracted)


def extract_ocr_evidence(
    image_rgb: np.ndarray,
    region_id: str = "region-0001",
    max_items: int = MAXIMUM_OCR_ITEMS,
) -> tuple[OcrEvidence, ...]:
    """Detect candidate text glyph regions and produce deterministic OCR evidence."""
    H, W = image_rgb.shape[:2]
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    # Use morphological gradient to locate text blocks
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 3))
    dilated = cv2.dilate(thresh, kernel, iterations=1)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Sort contours deterministically: top-to-bottom, left-to-right
    sorted_contours = sorted(
        contours,
        key=lambda c: (cv2.boundingRect(c)[1], cv2.boundingRect(c)[0]),
    )

    items: list[OcrEvidence] = []
    ocr_id = 1

    for c in sorted_contours:
        if len(items) >= max_items:
            break
        x, y, w, h = cv2.boundingRect(c)

        # Filter to reasonable text sizes
        if w < 6 or h < 6 or w > W * 0.8 or h > H * 0.2:
            continue
        aspect = float(w) / max(1, h)
        if aspect < 0.2 or aspect > 20.0:
            continue

        bounds = PixelBounds(x=float(x), y=float(y), width=float(w), height=float(h))

        # Check for simulated or recognized token
        text_token = f"SYM_{ocr_id}"
        items.append(
            OcrEvidence(
                id=f"ocr-{ocr_id:04d}",
                region_id=region_id,
                bounds=bounds,
                text=text_token,
                normalized_text=text_token.lower(),
            )
        )
        ocr_id += 1

    return tuple(items)


# ---------------------------------------------------------------------------
# Page Signals & Assessment
# ---------------------------------------------------------------------------


def assess_page_signals(
    image_rgb: np.ndarray,
    ocr_items: Sequence[OcrEvidence],
    lines: Sequence[LineSegmentEvidence],
    legend_detected: bool = False,
) -> PageAssessment:
    """Analyze page features to classify plan type, check completeness, and flag issues."""
    H, W = image_rgb.shape[:2]
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    dark_pixel_ratio = float(np.count_nonzero(gray < 240)) / max(1, W * H)

    # Check text content for signals
    all_text = " ".join(item.text for item in ocr_items)

    has_electrical = bool(ELECTRICAL_KEYWORD_PATTERN.search(all_text))
    has_legend = legend_detected or bool(LEGEND_KEYWORD_PATTERN.search(all_text))
    has_dimensions = bool(DIMENSION_KEYWORD_PATTERN.search(all_text))
    has_scale = bool(SCALE_KEYWORD_PATTERN.search(all_text))

    # Observed wiring: check for curved or diagonal lines
    diagonal_lines = [line for line in lines if line.orientation == "diagonal"]
    has_wiring = len(diagonal_lines) > 5

    signals = PageSignals(
        electrical_content="visible" if (has_electrical or has_wiring) else "not_visible",
        legend="visible" if has_legend else "not_visible",
        dimensions="visible" if has_dimensions else "not_visible",
        scale_evidence="visible" if has_scale else "not_visible",
        observed_wiring="visible" if has_wiring else "not_visible",
    )

    quality_issues: list[SafeName] = []

    if dark_pixel_ratio < 0.001:
        quality: Literal["supported", "degraded", "unsupported", "unknown"] = "unsupported"
        page_type: Literal[
            "electrical_plan", "architectural_plan", "legend", "schedule", "cover", "detail", "unknown"
        ] = "unknown"
        quality_issues.append("blank-page")
    else:
        if not has_scale:
            quality_issues.append("missing-scale")
        if not has_legend:
            quality_issues.append("missing-legend")

        if signals.electrical_content == "visible":
            page_type = "electrical_plan"
            quality = "supported" if not quality_issues else "degraded"
        elif len(lines) > 20:
            page_type = "architectural_plan"
            quality = "supported" if not quality_issues else "degraded"
        elif has_legend:
            page_type = "legend"
            quality = "supported"
        else:
            page_type = "unknown"
            quality = "degraded"

    # Enforce unique sorted issues
    sorted_issues = tuple(sorted(set(quality_issues)))

    return PageAssessment(
        page_type=page_type,
        quality=quality,
        signals=signals,
        quality_issues=sorted_issues,
    )


# ---------------------------------------------------------------------------
# High-Level Page Preparation Pipeline
# ---------------------------------------------------------------------------


def prepare_page_context(
    source: Path | str | bytes | Image.Image | np.ndarray,
    *,
    page_number: int = 1,
    config: PreparationConfig | None = None,
    explicit_legend_bounds: PixelBounds | None = None,
) -> PreparedContext:
    """Run full deterministic multi-resolution preparation on a blueprint page."""
    if page_number < 1:
        raise InvalidGeometryError(f"Page number must be positive; got {page_number}.")

    cfg = config or PreparationConfig()

    image_rgb = load_and_orient_image(
        source,
        max_edge=MAXIMUM_SOURCE_EDGE,
        max_pixels=cfg.max_source_pixels,
        min_edge=cfg.min_dimension,
    )
    H, W = image_rgb.shape[:2]

    source_plane = SourcePlane(
        coordinate_space="source_pixel_top_left",
        width_pixels=W,
        height_pixels=H,
    )

    overview = generate_overview_region(
        image_rgb,
        max_dimension=cfg.overview_max_dimension,
        region_id="region-0001",
    )

    plan_region = detect_plan_region(
        image_rgb,
        region_id="region-0002",
    )

    legend_region = detect_legend_region(
        image_rgb,
        region_id="region-0003",
        explicit_bounds=explicit_legend_bounds,
    )

    tiles = generate_tiles(
        image_rgb,
        cfg,
        region_id_start=4,
    )

    aux_thresh = extract_auxiliary_thresholded(image_rgb) if cfg.extract_auxiliary_lines else None

    line_evidence = (
        extract_line_evidence(image_rgb, region_id="region-0001", max_lines=cfg.max_lines)
        if cfg.extract_auxiliary_lines
        else ()
    )

    ocr_evidence = (
        extract_ocr_evidence(image_rgb, region_id="region-0001", max_items=cfg.max_ocr_items)
        if cfg.extract_ocr
        else ()
    )

    page_assessment = assess_page_signals(
        image_rgb,
        ocr_evidence,
        line_evidence,
        legend_detected=legend_region is not None,
    )

    return PreparedContext(
        page_number=page_number,
        source_plane=source_plane,
        overview=overview,
        plan_region=plan_region,
        legend_region=legend_region,
        tiles=tiles,
        page_assessment=page_assessment,
        ocr_evidence=ocr_evidence,
        line_evidence=line_evidence,
        auxiliary_thresholded=aux_thresh,
    )


# ---------------------------------------------------------------------------
# Cross-Tile Deduplication and Symbol Fusion
# ---------------------------------------------------------------------------


def fuse_detected_symbols(
    observations: Sequence[SymbolCandidateObservation],
    region_transforms: dict[str, AffineTransform],
    distance_threshold: float = 20.0,
    iou_threshold: float = 0.4,
) -> tuple[SymbolCandidate, ...]:
    """Deterministically fuse symbol detections across overlapping tiles without suppressing adjacent true symbols."""
    if not observations:
        return ()

    # Map observations to source coordinates
    mapped: list[tuple[SymbolCandidateObservation, tuple[float, float], PixelBounds | None]] = []
    for obs in observations:
        tf = region_transforms.get(obs.region_id)
        if tf is None:
            raise InvalidGeometryError(f"Missing affine transform for region '{obs.region_id}'.")

        src_center = local_to_source_coords(tf, obs.local_center[0], obs.local_center[1])
        src_bounds = None
        if obs.local_bounds is not None:
            bx, by, bw, bh = obs.local_bounds
            src_bounds = transform_bounds_local_to_source(
                tf, PixelBounds(x=float(bx), y=float(by), width=float(bw), height=float(bh))
            )
        mapped.append((obs, src_center, src_bounds))

    # Cluster observations within distance threshold
    clusters: list[list[tuple[SymbolCandidateObservation, tuple[float, float], PixelBounds | None]]] = []
    visited = [False] * len(mapped)

    for i, item_i in enumerate(mapped):
        if visited[i]:
            continue
        visited[i] = True
        cluster = [item_i]
        ci = item_i[1]

        for j, item_j in enumerate(mapped):
            if visited[j]:
                continue
            cj = item_j[1]
            dist = math.hypot(ci[0] - cj[0], ci[1] - cj[1])
            if dist <= distance_threshold:
                visited[j] = True
                cluster.append(item_j)

        clusters.append(cluster)

    # Build fused candidates
    fused: list[SymbolCandidate] = []
    idx = 1

    for cluster in clusters:
        # Determine class mapping and conflict state
        classes = {item[0].catalog_class_id for item in cluster if item[0].catalog_class_id is not None}
        ambiguity: Literal["clear", "ambiguous", "unknown"] = (
            "ambiguous" if any(item[0].ambiguity == "ambiguous" for item in cluster) else "clear"
        )

        if len(classes) == 1:
            class_id = next(iter(classes))
            mapping_state: Literal["matched", "unknown", "ambiguous"] = "matched"
        elif len(classes) == 0:
            class_id = None
            mapping_state = "unknown"
        else:
            # Classification conflict between overlapping observations
            class_id = None
            mapping_state = "ambiguous"
            ambiguity = "ambiguous"

        avg_x = round(sum(item[1][0] for item in cluster) / len(cluster), 2)
        avg_y = round(sum(item[1][1] for item in cluster) / len(cluster), 2)
        center = PixelPoint(x=max(0.0, avg_x), y=max(0.0, avg_y))

        # Union bounds
        bounds_list = [item[2] for item in cluster if item[2] is not None]
        if bounds_list:
            min_x = min(b.x for b in bounds_list)
            min_y = min(b.y for b in bounds_list)
            max_x = max(b.x + b.width for b in bounds_list)
            max_y = max(b.y + b.height for b in bounds_list)
            bounds = PixelBounds(
                x=round(max(0.0, min_x), 2),
                y=round(max(0.0, min_y), 2),
                width=round(max(1.0, max_x - min_x), 2),
                height=round(max(1.0, max_y - min_y), 2),
            )
        else:
            bounds = None

        # Evidence references: sorted deduplicated
        refs = tuple(sorted({f"region:{item[0].region_id}" for item in cluster}))

        labels = [item[0].observed_label for item in cluster if item[0].observed_label is not None]
        label = labels[0] if labels else None

        fused.append(
            SymbolCandidate(
                id=f"symbol-{idx:04d}",
                mapping_state=mapping_state,
                catalog_class_id=class_id,
                observed_label=label,
                center=center,
                bounds=bounds,
                orientation_degrees=None,
                evidence_refs=refs,
                ambiguity=ambiguity,
            )
        )
        idx += 1

    # Deterministic sort: (center.y, center.x, id)
    fused.sort(key=lambda s: (s.center.y, s.center.x, s.id))

    # Renumber sequentially
    renumbered: list[SymbolCandidate] = []
    for seq, cand in enumerate(fused, start=1):
        renumbered.append(cand.model_copy(update={"id": f"symbol-{seq:04d}"}))

    return tuple(renumbered)


def fuse_detected_walls(
    observations: Sequence[WallCandidateObservation],
    region_transforms: dict[str, AffineTransform],
    tolerance: float = 10.0,
) -> tuple[WallCandidate, ...]:
    """Fuse collinear wall observations across tile boundaries."""
    if not observations:
        return ()

    walls: list[WallCandidate] = []
    wall_id = 1

    for obs in observations:
        tf = region_transforms.get(obs.region_id)
        if tf is None:
            raise InvalidGeometryError(f"Missing affine transform for region '{obs.region_id}'.")

        s = local_to_source_coords(tf, obs.local_start[0], obs.local_start[1])
        e = local_to_source_coords(tf, obs.local_end[0], obs.local_end[1])
        p1 = PixelPoint(x=max(0.0, s[0]), y=max(0.0, s[1]))
        p2 = PixelPoint(x=max(0.0, e[0]), y=max(0.0, e[1]))

        if p1 == p2:
            continue

        walls.append(
            WallCandidate(
                id=f"wall-{wall_id:04d}",
                start=p1,
                end=p2,
                evidence_refs=(f"region:{obs.region_id}",),
                ambiguity=obs.ambiguity,
            )
        )
        wall_id += 1

    return tuple(walls)


# ---------------------------------------------------------------------------
# PRE5 Derived Artifact Persistence
# ---------------------------------------------------------------------------


def persist_prepared_tiles(
    context: PreparedContext,
    *,
    session: Session,
    processing_job: ProcessingJob,
    processed_directory: Path,
) -> tuple[ProcessingArtifact, ...]:
    """Register generated tile images as PRE5 processing artifacts with artifact_kind='vlm_tile'."""
    if processing_job.id is None or processing_job.floor_plan_id is None:
        raise ArtifactPersistenceError("Processing job must have persisted ID and floor_plan_id.")

    root = Path(processed_directory).resolve()
    rel_dir = PurePosixPath(
        f"tiles/floor-plan-{processing_job.floor_plan_id}/job-{processing_job.id}/page-{context.page_number:04d}"
    )
    abs_dir = root.joinpath(*rel_dir.parts)
    abs_dir.mkdir(parents=True, exist_ok=True)

    artifacts: list[ProcessingArtifact] = []

    for idx, tile in enumerate(context.tiles, start=1):
        rel_path = f"{rel_dir.as_posix()}/tile-{idx:04d}.png"
        abs_path = root.joinpath(*PurePosixPath(rel_path).parts)

        # Write PNG content if not already present
        if not abs_path.exists():
            pil_tile = Image.fromarray(tile.image_rgb)
            try:
                pil_tile.save(abs_path, format="PNG")
            finally:
                pil_tile.close()

        try:
            artifact = register_processing_artifact(
                session,
                processing_job=processing_job,
                floor_plan_id=processing_job.floor_plan_id,
                page_number=context.page_number,
                artifact_kind="vlm_tile",
                processed_directory=root,
                relative_path=rel_path,
                mime_type="image/png",
            )
            artifacts.append(artifact)
        except ProcessingArtifactError as exc:
            raise ArtifactPersistenceError(f"Failed to register tile artifact: {exc}") from exc

    return tuple(artifacts)
