from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from math import ceil, isfinite
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal

import pypdfium2 as pdfium
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator

from app.services.upload_validation import (
    FORMAT_BY_EXTENSION,
    UploadValidationError,
    validate_floor_plan_upload,
)


LEGACY_MANIFEST_VERSION = 1
MANIFEST_VERSION = 2
MAXIMUM_SOURCE_BYTES = 25 * 1024 * 1024
MAXIMUM_PAGES = 50
MAXIMUM_IMAGE_EDGE = 10_000
MAXIMUM_IMAGE_PIXELS = 60_000_000
MAXIMUM_MANIFEST_BYTES = 16 * 1024 * 1024
FINGERPRINT_PDF_SCALE = 0.25
ERROR_MESSAGE = "The private corpus intake request is invalid."


class CorpusIntakeError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(ERROR_MESSAGE)


def _fail(code: str) -> None:
    raise CorpusIntakeError(code)


class IntakeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PermissionRecord(IntakeModel):
    status: str = Field(pattern=r"^(pending|approved|rejected)$")
    allowed_purposes: tuple[str, ...] = Field(max_length=4)
    approved_by: str | None = Field(default=None, min_length=1, max_length=200)
    evidence_reference: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def complete_approval(self):
        allowed = {"training", "development_evaluation", "sealed_evaluation", "reference_grounding"}
        if set(self.allowed_purposes) - allowed or tuple(sorted(set(self.allowed_purposes))) != self.allowed_purposes:
            raise ValueError("Purposes must be supported, unique, and ordered.")
        evidence = self.approved_by is not None and self.evidence_reference is not None
        if self.status == "approved" and (not evidence or not self.allowed_purposes):
            raise ValueError("Approved permission requires authority, evidence, and purpose.")
        if self.status != "approved" and (evidence or self.allowed_purposes):
            raise ValueError("Pending or rejected permission cannot grant a purpose.")
        return self


class QualityReviewDecision(IntakeModel):
    decision_revision: StrictInt = Field(ge=1)
    decision: Literal["accepted", "rejected"]
    readability: Literal["readable", "unreadable"]
    reviewed_purposes: tuple[
        Literal[
            "development_evaluation",
            "reference_grounding",
            "sealed_evaluation",
            "training",
        ],
        ...,
    ] = Field(min_length=1, max_length=4)
    reviewed_by: str = Field(min_length=1, max_length=200)
    evidence_reference: str = Field(min_length=1, max_length=500)
    decided_at: str = Field(min_length=20, max_length=30)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_perceptual_hash: str = Field(pattern=r"^[0-9a-f]{16}$")

    @model_validator(mode="after")
    def decision_is_coherent(self):
        if tuple(sorted(set(self.reviewed_purposes))) != self.reviewed_purposes:
            raise ValueError("Reviewed purposes must be unique and ordered.")
        if self.decision == "accepted" and self.readability != "readable":
            raise ValueError("Accepted degraded quality must be readable.")
        try:
            decided_at = datetime.fromisoformat(self.decided_at.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("Quality decision time must be RFC 3339.") from None
        if decided_at.tzinfo is None or decided_at.utcoffset() != timezone.utc.utcoffset(decided_at):
            raise ValueError("Quality decision time must be UTC.")
        return self


class PageIntakeMetadata(IntakeModel):
    page_number: StrictInt = Field(ge=1, le=MAXIMUM_PAGES)
    sheet_type: Literal[
        "pending",
        "electrical_plan",
        "architectural_plan",
        "legend",
        "schedule",
        "cover",
        "detail",
        "other",
    ]
    quality: Literal["pending", "supported", "degraded", "unsupported"]
    quality_review_history: tuple[QualityReviewDecision, ...] = Field(
        default=(), max_length=100
    )

    @model_validator(mode="after")
    def review_history_is_ordered(self):
        revisions = tuple(item.decision_revision for item in self.quality_review_history)
        if revisions != tuple(range(1, len(revisions) + 1)):
            raise ValueError("Quality review revisions must be contiguous and one-based.")
        if self.quality != "degraded" and self.quality_review_history:
            raise ValueError("Only degraded pages can have quality review decisions.")
        return self


class CorpusIntakeRequest(IntakeModel):
    source_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    relative_path: str = Field(min_length=1, max_length=500)
    source_type: str = Field(pattern=r"^(blueprint|reference)$")
    project_group_id: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    drawing_set_id: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    split: str = Field(pattern=r"^(pending|train|development_validation|sealed_test)$")
    sheet_type: str = Field(pattern=r"^(pending|electrical_plan|architectural_plan|legend|schedule|cover|detail|other)$")
    quality: str = Field(pattern=r"^(pending|supported|degraded|unsupported)$")
    permission: PermissionRecord
    page_metadata: tuple[PageIntakeMetadata, ...] = Field(default=(), max_length=MAXIMUM_PAGES)
    inventory_recoverable_pdf: StrictBool = False

    @model_validator(mode="after")
    def purpose_matches_split(self):
        purpose = {
            "train": "training",
            "development_validation": "development_evaluation",
            "sealed_test": "sealed_evaluation",
        }.get(self.split)
        if purpose is not None and purpose not in self.permission.allowed_purposes:
            raise ValueError("Assigned split is not permitted for this source.")
        if self.source_type == "reference" and self.split != "pending":
            raise ValueError("Reference material is not a floor-plan split member.")
        if self.source_type == "reference" and self.permission.status == "approved" and "reference_grounding" not in self.permission.allowed_purposes:
            raise ValueError("Approved reference material requires grounding permission.")
        page_numbers = tuple(page.page_number for page in self.page_metadata)
        if page_numbers and page_numbers != tuple(range(1, len(page_numbers) + 1)):
            raise ValueError("Page metadata must be contiguous and one-based.")
        if self.quality == "degraded" and any(
            page.quality == "supported" for page in self.page_metadata
        ):
            raise ValueError("A degraded source cannot contain a supported page.")
        if self.quality == "unsupported" and any(
            page.quality != "unsupported" for page in self.page_metadata
        ):
            raise ValueError("An unsupported source cannot contain an eligible page quality.")
        return self


class _StoredPageV1(IntakeModel):
    page_number: StrictInt = Field(ge=1, le=MAXIMUM_PAGES)
    width_pixels: StrictInt = Field(ge=1, le=MAXIMUM_IMAGE_EDGE)
    height_pixels: StrictInt = Field(ge=1, le=MAXIMUM_IMAGE_EDGE)
    perceptual_hash: str = Field(pattern=r"^[0-9a-f]{16}$")

    @model_validator(mode="after")
    def allocation_is_bounded(self):
        if self.width_pixels * self.height_pixels > MAXIMUM_IMAGE_PIXELS:
            raise ValueError("Stored page exceeds the allocation limit.")
        return self


class _StoredRecordV1(IntakeModel):
    source_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    relative_path: str = Field(min_length=1, max_length=500)
    source_type: Literal["blueprint", "reference"]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_size: StrictInt = Field(ge=1, le=MAXIMUM_SOURCE_BYTES)
    mime_type: Literal["image/jpeg", "image/png", "application/pdf"]
    project_group_id: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    drawing_set_id: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    split: Literal["pending", "train", "development_validation", "sealed_test"]
    sheet_type: Literal["pending", "electrical_plan", "architectural_plan", "legend", "schedule", "cover", "detail", "other"]
    quality: Literal["pending", "supported", "degraded", "unsupported"]
    permission: PermissionRecord
    pages: tuple[_StoredPageV1, ...] = Field(min_length=1, max_length=MAXIMUM_PAGES)
    eligible: StrictBool
    eligibility_reasons: tuple[
        Literal[
            "degraded_requires_quality_approval",
            "drawing_set_missing",
            "near_duplicate_pending_resolution",
            "permission_not_approved",
            "project_group_missing",
            "quality_pending",
            "quality_unsupported",
            "sheet_type_pending",
            "split_pending",
        ],
        ...,
    ]

    @model_validator(mode="after")
    def stored_contract_is_coherent(self):
        portable = PurePosixPath(self.relative_path)
        if (
            PureWindowsPath(self.relative_path).is_absolute()
            or portable.is_absolute()
            or "\\" in self.relative_path
            or any(part in {"", ".", ".."} for part in portable.parts)
        ):
            raise ValueError("Stored source path is unsafe.")
        extension = portable.suffix.casefold()
        policy = FORMAT_BY_EXTENSION.get(extension)
        if policy is None or policy[0] != self.mime_type:
            raise ValueError("Stored source format is inconsistent.")
        if tuple(page.page_number for page in self.pages) != tuple(range(1, len(self.pages) + 1)):
            raise ValueError("Stored pages must be contiguous and one-based.")
        if tuple(sorted(set(self.eligibility_reasons))) != self.eligibility_reasons:
            raise ValueError("Stored eligibility reasons must be unique and ordered.")
        if self.eligible != (not self.eligibility_reasons):
            raise ValueError("Stored eligibility state is inconsistent.")
        purpose = {
            "train": "training",
            "development_validation": "development_evaluation",
            "sealed_test": "sealed_evaluation",
        }.get(self.split)
        if purpose is not None and purpose not in self.permission.allowed_purposes:
            raise ValueError("Stored split is not permitted.")
        if self.source_type == "reference" and self.split != "pending":
            raise ValueError("Stored reference cannot belong to a floor-plan split.")
        if (
            self.source_type == "reference"
            and self.permission.status == "approved"
            and "reference_grounding" not in self.permission.allowed_purposes
        ):
            raise ValueError("Stored reference permission is inconsistent.")
        return self


class _NearDuplicatePair(IntakeModel):
    left_source_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    right_source_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")

    @model_validator(mode="after")
    def pair_is_ordered(self):
        if self.left_source_id >= self.right_source_id:
            raise ValueError("Near-duplicate pair must be ordered.")
        return self


class _CoverageV1(IntakeModel):
    source_count: StrictInt = Field(ge=0)
    blueprint_source_count: StrictInt = Field(ge=0)
    eligible_blueprint_source_count: StrictInt = Field(ge=0)
    eligible_blueprint_drawing_group_count: StrictInt = Field(ge=0)
    independent_eligible_blueprint_project_count: StrictInt = Field(ge=0)
    reference_material_count: StrictInt = Field(ge=0)
    eligible_reference_material_count: StrictInt = Field(ge=0)


class _StoredManifestV1(IntakeModel):
    schema_version: Literal[LEGACY_MANIFEST_VERSION]
    manifest_revision: StrictInt = Field(ge=1)
    previous_manifest_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    records: tuple[_StoredRecordV1, ...]
    exact_duplicate_groups: dict[str, tuple[str, ...]]
    near_duplicate_pairs: tuple[_NearDuplicatePair, ...]
    coverage: _CoverageV1

    @model_validator(mode="after")
    def revision_contract_is_coherent(self):
        if (self.manifest_revision == 1) != (self.previous_manifest_sha256 is None):
            raise ValueError("Stored revision link is inconsistent.")
        identifiers = tuple(record.source_id for record in self.records)
        if tuple(sorted(set(identifiers))) != identifiers:
            raise ValueError("Stored source identifiers must be unique and ordered.")
        for digest, source_ids in self.exact_duplicate_groups.items():
            if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
                raise ValueError("Stored duplicate digest is invalid.")
            if len(source_ids) < 2 or tuple(sorted(set(source_ids))) != source_ids:
                raise ValueError("Stored exact-duplicate members must be unique and ordered.")
        pairs = tuple((pair.left_source_id, pair.right_source_id) for pair in self.near_duplicate_pairs)
        if tuple(sorted(set(pairs))) != pairs:
            raise ValueError("Stored near-duplicate pairs must be unique and ordered.")
        return self


class _StructuralValidation(IntakeModel):
    status: Literal["passed", "strict_validation_failed_recoverable", "legacy_not_recorded"]
    findings: tuple[Literal["UPLOAD_PDF_CORRUPT"], ...] = Field(max_length=1)

    @model_validator(mode="after")
    def findings_match_status(self):
        if self.status == "strict_validation_failed_recoverable":
            if self.findings != ("UPLOAD_PDF_CORRUPT",):
                raise ValueError("Recoverable strict validation failure must retain its finding.")
        elif self.findings:
            raise ValueError("Passed or legacy validation status cannot contain a finding.")
        return self


class _StoredPage(IntakeModel):
    page_number: StrictInt = Field(ge=1, le=MAXIMUM_PAGES)
    width_pixels: StrictInt = Field(ge=1, le=MAXIMUM_IMAGE_EDGE)
    height_pixels: StrictInt = Field(ge=1, le=MAXIMUM_IMAGE_EDGE)
    perceptual_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{16}$")
    renderability: Literal["renderable", "unrenderable"]
    render_findings: tuple[Literal["PAGE_RENDER_FAILED"], ...] = Field(max_length=1)
    sheet_type: Literal[
        "pending",
        "electrical_plan",
        "architectural_plan",
        "legend",
        "schedule",
        "cover",
        "detail",
        "other",
    ]
    quality: Literal["pending", "supported", "degraded", "unsupported"]
    quality_review_history: tuple[QualityReviewDecision, ...] = Field(max_length=100)
    eligible: StrictBool
    eligibility_reasons: tuple[str, ...]

    @model_validator(mode="after")
    def stored_page_is_coherent(self):
        if self.width_pixels * self.height_pixels > MAXIMUM_IMAGE_PIXELS:
            raise ValueError("Stored page exceeds the allocation limit.")
        if self.renderability == "renderable":
            if self.perceptual_hash is None or self.render_findings:
                raise ValueError("A renderable page requires a fingerprint and no render failure.")
        elif self.perceptual_hash is not None or self.render_findings != ("PAGE_RENDER_FAILED",):
            raise ValueError("An unrenderable page must retain its render failure.")
        if tuple(sorted(set(self.eligibility_reasons))) != self.eligibility_reasons:
            raise ValueError("Stored page eligibility reasons must be unique and ordered.")
        if self.eligible != (not self.eligibility_reasons):
            raise ValueError("Stored page eligibility state is inconsistent.")
        revisions = tuple(item.decision_revision for item in self.quality_review_history)
        if revisions != tuple(range(1, len(revisions) + 1)):
            raise ValueError("Stored quality reviews must be contiguous and one-based.")
        if self.renderability != "renderable" and self.quality_review_history:
            raise ValueError("An unrenderable page cannot have a quality review decision.")
        if self.quality != "degraded" and self.quality_review_history:
            raise ValueError("Only degraded pages can retain quality review decisions.")
        return self


class _StoredRecord(IntakeModel):
    source_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    relative_path: str = Field(min_length=1, max_length=500)
    source_type: Literal["blueprint", "reference"]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_size: StrictInt = Field(ge=1, le=MAXIMUM_SOURCE_BYTES)
    mime_type: Literal["image/jpeg", "image/png", "application/pdf"]
    project_group_id: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    drawing_set_id: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    split: Literal["pending", "train", "development_validation", "sealed_test"]
    sheet_type: Literal["pending", "electrical_plan", "architectural_plan", "legend", "schedule", "cover", "detail", "other"]
    quality: Literal["pending", "supported", "degraded", "unsupported"]
    permission: PermissionRecord
    structural_validation: _StructuralValidation
    pages: tuple[_StoredPage, ...] = Field(min_length=1, max_length=MAXIMUM_PAGES)
    eligible: StrictBool
    eligibility_reasons: tuple[str, ...]

    @model_validator(mode="after")
    def stored_contract_is_coherent(self):
        portable = PurePosixPath(self.relative_path)
        if (
            PureWindowsPath(self.relative_path).is_absolute()
            or portable.is_absolute()
            or "\\" in self.relative_path
            or any(part in {"", ".", ".."} for part in portable.parts)
        ):
            raise ValueError("Stored source path is unsafe.")
        extension = portable.suffix.casefold()
        policy = FORMAT_BY_EXTENSION.get(extension)
        if policy is None or policy[0] != self.mime_type:
            raise ValueError("Stored source format is inconsistent.")
        if tuple(page.page_number for page in self.pages) != tuple(range(1, len(self.pages) + 1)):
            raise ValueError("Stored pages must be contiguous and one-based.")
        if tuple(sorted(set(self.eligibility_reasons))) != self.eligibility_reasons:
            raise ValueError("Stored eligibility reasons must be unique and ordered.")
        if self.eligible != any(page.eligible for page in self.pages):
            raise ValueError("Stored source eligibility must match its pages.")
        if self.eligible and self.eligibility_reasons:
            raise ValueError("An eligible source cannot retain source-level exclusion reasons.")
        purpose = {
            "train": "training",
            "development_validation": "development_evaluation",
            "sealed_test": "sealed_evaluation",
        }.get(self.split)
        if purpose is not None and purpose not in self.permission.allowed_purposes:
            raise ValueError("Stored split is not permitted.")
        if self.source_type == "reference" and self.split != "pending":
            raise ValueError("Stored reference cannot belong to a floor-plan split.")
        if (
            self.source_type == "reference"
            and self.permission.status == "approved"
            and "reference_grounding" not in self.permission.allowed_purposes
        ):
            raise ValueError("Stored reference permission is inconsistent.")
        for page in self.pages:
            if self.quality == "degraded" and page.quality == "supported":
                raise ValueError("A degraded source cannot contain a supported page.")
            if self.quality == "unsupported" and page.quality != "unsupported":
                raise ValueError("An unsupported source cannot contain an eligible page quality.")
            for review in page.quality_review_history:
                if (
                    review.source_sha256 != self.sha256
                    or review.page_perceptual_hash != page.perceptual_hash
                ):
                    raise ValueError("Stored quality review is not bound to its source page.")
        return self


class _Coverage(IntakeModel):
    source_count: StrictInt = Field(ge=0)
    page_count: StrictInt = Field(ge=0)
    blueprint_source_count: StrictInt = Field(ge=0)
    blueprint_page_count: StrictInt = Field(ge=0)
    eligible_blueprint_source_count: StrictInt = Field(ge=0)
    eligible_blueprint_page_count: StrictInt = Field(ge=0)
    eligible_blueprint_drawing_group_count: StrictInt = Field(ge=0)
    independent_eligible_blueprint_project_count: StrictInt = Field(ge=0)
    reference_material_count: StrictInt = Field(ge=0)
    reference_page_count: StrictInt = Field(ge=0)
    eligible_reference_material_count: StrictInt = Field(ge=0)
    eligible_reference_page_count: StrictInt = Field(ge=0)


class _StoredManifest(IntakeModel):
    schema_version: Literal[MANIFEST_VERSION]
    manifest_revision: StrictInt = Field(ge=1)
    previous_manifest_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    records: tuple[_StoredRecord, ...]
    exact_duplicate_groups: dict[str, tuple[str, ...]]
    near_duplicate_pairs: tuple[_NearDuplicatePair, ...]
    coverage: _Coverage

    @model_validator(mode="after")
    def revision_contract_is_coherent(self):
        if self.manifest_revision == 1 and self.previous_manifest_sha256 is not None:
            raise ValueError("Initial manifest cannot link to a previous revision.")
        if self.manifest_revision > 1 and self.previous_manifest_sha256 is None:
            raise ValueError("Stored revision link is missing.")
        identifiers = tuple(record.source_id for record in self.records)
        if tuple(sorted(set(identifiers))) != identifiers:
            raise ValueError("Stored source identifiers must be unique and ordered.")
        for digest, source_ids in self.exact_duplicate_groups.items():
            if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
                raise ValueError("Stored duplicate digest is invalid.")
            if len(source_ids) < 2 or tuple(sorted(set(source_ids))) != source_ids:
                raise ValueError("Stored exact-duplicate members must be unique and ordered.")
        pairs = tuple((pair.left_source_id, pair.right_source_id) for pair in self.near_duplicate_pairs)
        if tuple(sorted(set(pairs))) != pairs:
            raise ValueError("Stored near-duplicate pairs must be unique and ordered.")
        return self


@dataclass(frozen=True)
class CorpusIntakeResult:
    manifest_path: Path
    record_count: int
    page_count: int
    blueprint_source_count: int
    blueprint_page_count: int
    eligible_blueprint_source_count: int
    eligible_blueprint_page_count: int
    eligible_blueprint_drawing_group_count: int
    independent_eligible_blueprint_project_count: int
    reference_material_count: int
    reference_page_count: int
    eligible_reference_material_count: int
    eligible_reference_page_count: int
    exact_duplicate_groups: int
    near_duplicate_pairs: int
    changed: bool

    @property
    def eligible_count(self) -> int:
        """Backward-compatible aggregate; use the explicit coverage fields."""
        return self.eligible_blueprint_source_count


def _safe_source(root: Path, relative_path: str) -> Path:
    portable = PurePosixPath(relative_path)
    if (
        PureWindowsPath(relative_path).is_absolute()
        or portable.is_absolute()
        or "\\" in relative_path
        or any(part in {"", ".", ".."} for part in portable.parts)
    ):
        _fail("UNSAFE_SOURCE_PATH")
    try:
        lexical = root.joinpath(*portable.parts)
        if lexical.is_symlink() or any(parent.is_symlink() for parent in lexical.parents if parent != root.parent):
            _fail("UNSAFE_SOURCE_PATH")
        resolved = lexical.resolve(strict=True)
    except CorpusIntakeError:
        raise
    except (OSError, RuntimeError):
        _fail("SOURCE_UNAVAILABLE")
    if resolved != lexical or not resolved.is_relative_to(root) or not resolved.is_file():
        _fail("UNSAFE_SOURCE_PATH")
    return resolved


def _read_source_bounded(source: Path) -> tuple[bytes, str]:
    try:
        before = source.stat()
        if before.st_size <= 0:
            _fail("SOURCE_EMPTY")
        if before.st_size > MAXIMUM_SOURCE_BYTES:
            _fail("SOURCE_TOO_LARGE")
        with source.open("rb") as stream:
            content = stream.read(MAXIMUM_SOURCE_BYTES + 1)
        after = source.stat()
    except CorpusIntakeError:
        raise
    except OSError:
        _fail("SOURCE_UNAVAILABLE")
    if len(content) > MAXIMUM_SOURCE_BYTES:
        _fail("SOURCE_TOO_LARGE")
    if len(content) != before.st_size or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        _fail("SOURCE_CHANGED_DURING_READ")
    return content, sha256(content).hexdigest()


def _verify_original_digest(source: Path, expected_digest: str) -> None:
    digest = sha256()
    total = 0
    try:
        with source.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                total += len(chunk)
                if total > MAXIMUM_SOURCE_BYTES:
                    _fail("SOURCE_TOO_LARGE")
                digest.update(chunk)
    except CorpusIntakeError:
        raise
    except OSError:
        _fail("SOURCE_UNAVAILABLE")
    if digest.hexdigest() != expected_digest:
        _fail("ORIGINAL_CHANGED_DURING_INTAKE")


def _validate_image_allocation(content: bytes) -> None:
    try:
        with Image.open(BytesIO(content)) as image:
            width, height = image.size
    except Exception:
        _fail("INVALID_SOURCE")
    if (
        width <= 0
        or height <= 0
        or width > MAXIMUM_IMAGE_EDGE
        or height > MAXIMUM_IMAGE_EDGE
        or width * height > MAXIMUM_IMAGE_PIXELS
    ):
        _fail("IMAGE_ALLOCATION_LIMIT_EXCEEDED")


def _image_hash(image: Image.Image) -> str:
    grayscale = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    try:
        pixels = list(grayscale.get_flattened_data())
    finally:
        grayscale.close()
    bits = [pixels[row * 9 + column] > pixels[row * 9 + column + 1] for row in range(8) for column in range(8)]
    return f"{sum(1 << index for index, bit in enumerate(bits) if bit):016x}"


def _page_fingerprints(content: bytes, extension: str, page_count: int) -> list[dict[str, object]]:
    pages: list[dict[str, object]] = []
    if extension != ".pdf":
        with Image.open(BytesIO(content)) as image:
            pages.append({
                "page_number": 1,
                "width_pixels": image.width,
                "height_pixels": image.height,
                "perceptual_hash": _image_hash(image),
                "renderability": "renderable",
                "render_findings": [],
            })
        return pages
    document = None
    try:
        document = pdfium.PdfDocument(content)
        for index in range(page_count):
            page = document[index]
            bitmap = None
            pil_image = None
            try:
                width_points, height_points = page.get_size()
                width = ceil(width_points * FINGERPRINT_PDF_SCALE)
                height = ceil(height_points * FINGERPRINT_PDF_SCALE)
                if (
                    not all(isfinite(value) and value > 0 for value in (width_points, height_points))
                    or width <= 0
                    or height <= 0
                    or width > MAXIMUM_IMAGE_EDGE
                    or height > MAXIMUM_IMAGE_EDGE
                    or width * height > MAXIMUM_IMAGE_PIXELS
                ):
                    _fail("PDF_RENDER_LIMIT_EXCEEDED")
                try:
                    bitmap = page.render(scale=FINGERPRINT_PDF_SCALE)
                except Exception:
                    pages.append({
                        "page_number": index + 1,
                        "width_pixels": width,
                        "height_pixels": height,
                        "perceptual_hash": None,
                        "renderability": "unrenderable",
                        "render_findings": ["PAGE_RENDER_FAILED"],
                    })
                    continue
                if (
                    int(bitmap.width) > MAXIMUM_IMAGE_EDGE
                    or int(bitmap.height) > MAXIMUM_IMAGE_EDGE
                    or int(bitmap.width) * int(bitmap.height) > MAXIMUM_IMAGE_PIXELS
                ):
                    _fail("PDF_RENDER_LIMIT_EXCEEDED")
                pil_image = bitmap.to_pil()
                pages.append({
                    "page_number": index + 1,
                    "width_pixels": int(bitmap.width),
                    "height_pixels": int(bitmap.height),
                    "perceptual_hash": _image_hash(pil_image),
                    "renderability": "renderable",
                    "render_findings": [],
                })
            finally:
                if pil_image is not None:
                    pil_image.close()
                if bitmap is not None:
                    bitmap.close()
                page.close()
    except CorpusIntakeError:
        raise
    except Exception:
        _fail("PAGE_FINGERPRINT_FAILED")
    finally:
        if document is not None:
            document.close()
    return pages


def _recoverable_pdf_page_count(content: bytes) -> int:
    document = None
    try:
        document = pdfium.PdfDocument(content)
        page_count = len(document)
    except Exception:
        _fail("INVALID_SOURCE")
    finally:
        if document is not None:
            document.close()
    if page_count <= 0:
        _fail("INVALID_SOURCE")
    return page_count


def _hamming(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def _near_duplicate(left: dict, right: dict) -> bool:
    left_pages, right_pages = left["pages"], right["pages"]
    return len(left_pages) == len(right_pages) and all(
        a["perceptual_hash"] is not None
        and b["perceptual_hash"] is not None
        and _hamming(a["perceptual_hash"], b["perceptual_hash"]) <= 5
        for a, b in zip(left_pages, right_pages)
    )


def _record(root: Path, request: CorpusIntakeRequest) -> dict[str, object]:
    source = _safe_source(root, request.relative_path)
    extension = source.suffix.casefold()
    policy = FORMAT_BY_EXTENSION.get(extension)
    if policy is None:
        _fail("UNSUPPORTED_SOURCE")
    content, original_digest = _read_source_bounded(source)
    if extension != ".pdf":
        _validate_image_allocation(content)
    mime_type = policy[0]
    structural_validation = {"status": "passed", "findings": []}
    try:
        validated = validate_floor_plan_upload(
            filename=source.name,
            declared_mime_type=policy[0],
            content=content,
            max_file_size_bytes=MAXIMUM_SOURCE_BYTES,
        )
    except UploadValidationError as error:
        if (
            extension != ".pdf"
            or not request.inventory_recoverable_pdf
            or error.code != "UPLOAD_PDF_CORRUPT"
        ):
            _fail("INVALID_SOURCE")
        page_count = _recoverable_pdf_page_count(content)
        structural_validation = {
            "status": "strict_validation_failed_recoverable",
            "findings": [error.code],
        }
    except Exception:
        _fail("INVALID_SOURCE")
    else:
        page_count = validated.page_count or 1
        mime_type = validated.mime_type
    if page_count > MAXIMUM_PAGES:
        _fail("PAGE_LIMIT_EXCEEDED")
    page_fingerprints = _page_fingerprints(content, extension, page_count)
    _verify_original_digest(source, original_digest)
    if request.page_metadata:
        if len(request.page_metadata) != page_count:
            _fail("PAGE_METADATA_MISMATCH")
        page_metadata = request.page_metadata
    else:
        page_metadata = tuple(
            PageIntakeMetadata(
                page_number=page_number,
                sheet_type=request.sheet_type,
                quality=request.quality,
            )
            for page_number in range(1, page_count + 1)
        )
    if structural_validation["status"] == "strict_validation_failed_recoverable" and any(
        metadata.quality not in {"degraded", "unsupported"}
        for metadata in page_metadata
    ):
        _fail("INVALID_SOURCE")
    pages = []
    for fingerprint, metadata in zip(page_fingerprints, page_metadata):
        if fingerprint["page_number"] != metadata.page_number:
            _fail("PAGE_METADATA_MISMATCH")
        for review in metadata.quality_review_history:
            if (
                review.source_sha256 != original_digest
                or review.page_perceptual_hash != fingerprint["perceptual_hash"]
            ):
                _fail("QUALITY_REVIEW_IDENTITY_MISMATCH")
        pages.append({
            **fingerprint,
            "sheet_type": metadata.sheet_type,
            "quality": metadata.quality,
            "quality_review_history": [
                item.model_dump(mode="json")
                for item in metadata.quality_review_history
            ],
            "eligible": False,
            "eligibility_reasons": [],
        })
    record = {
        "source_id": request.source_id,
        "relative_path": request.relative_path,
        "source_type": request.source_type,
        "sha256": original_digest,
        "byte_size": len(content),
        "mime_type": mime_type,
        "project_group_id": request.project_group_id,
        "drawing_set_id": request.drawing_set_id,
        "split": request.split,
        "sheet_type": request.sheet_type,
        "quality": request.quality,
        "permission": request.permission.model_dump(mode="json"),
        "structural_validation": structural_validation,
        "pages": pages,
        "eligible": False,
        "eligibility_reasons": [],
    }
    _reset_eligibility([record])
    return record


def _validate_groups(records: list[dict[str, object]]) -> tuple[dict[str, list[str]], list[dict[str, str]]]:
    project_splits: dict[str, set[str]] = {}
    hashes: dict[str, list[dict]] = {}
    for record in records:
        if record["source_type"] == "blueprint" and record["project_group_id"] and record["split"] != "pending":
            project_splits.setdefault(record["project_group_id"], set()).add(record["split"])
        hashes.setdefault(record["sha256"], []).append(record)
    if any(len(splits) > 1 for splits in project_splits.values()):
        _fail("PROJECT_CROSSES_SPLITS")
    exact = {digest: sorted(item["source_id"] for item in values) for digest, values in hashes.items() if len(values) > 1}
    for values in hashes.values():
        splits = {item["split"] for item in values if item["split"] != "pending"}
        if len(splits) > 1:
            _fail("EXACT_DUPLICATE_CROSSES_SPLITS")
    near: list[dict[str, str]] = []
    for index, left in enumerate(records):
        for right in records[index + 1:]:
            if left["sha256"] == right["sha256"] or not _near_duplicate(left, right):
                continue
            near.append({"left_source_id": left["source_id"], "right_source_id": right["source_id"]})
            if left["split"] != "pending" and right["split"] != "pending" and left["split"] != right["split"]:
                _fail("NEAR_DUPLICATE_CROSSES_SPLITS")
            for record in (left, right):
                if record["pages"] and "eligible" in record["pages"][0]:
                    for page in record["pages"]:
                        reasons = set(page.get("eligibility_reasons", []))
                        reasons.add("near_duplicate_pending_resolution")
                        page["eligibility_reasons"] = sorted(reasons)
                        page["eligible"] = False
                    record["eligible"] = False
                    record["eligibility_reasons"] = ["near_duplicate_pending_resolution"]
                else:
                    record["eligible"] = False
                    reasons = set(record.get("eligibility_reasons", []))
                    reasons.add("near_duplicate_pending_resolution")
                    record["eligibility_reasons"] = sorted(reasons)
    return exact, near


def _coverage_v1(records: list[dict[str, object]], exact: dict[str, list[str]]) -> dict[str, int]:
    blueprints = [record for record in records if record["source_type"] == "blueprint"]
    eligible = [record for record in blueprints if record["eligible"]]
    projects = {record["project_group_id"] for record in eligible}
    parent = {project: project for project in projects}

    def find(project):
        while parent[project] != project:
            parent[project] = parent[parent[project]]
            project = parent[project]
        return project

    def union(left, right):
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    by_source = {record["source_id"]: record for record in eligible}
    for source_ids in exact.values():
        duplicate_projects = sorted({
            by_source[source_id]["project_group_id"]
            for source_id in source_ids
            if source_id in by_source
        })
        for project in duplicate_projects[1:]:
            union(duplicate_projects[0], project)

    references = [record for record in records if record["source_type"] == "reference"]
    return {
        "source_count": len(records),
        "blueprint_source_count": len(blueprints),
        "eligible_blueprint_source_count": len(eligible),
        "eligible_blueprint_drawing_group_count": len({
            (record["project_group_id"], record["drawing_set_id"])
            for record in eligible
        }),
        "independent_eligible_blueprint_project_count": len({find(project) for project in projects}),
        "reference_material_count": len(references),
        "eligible_reference_material_count": sum(record["eligible"] for record in references),
    }


def _coverage(records: list[dict[str, object]], exact: dict[str, list[str]]) -> dict[str, int]:
    blueprints = [record for record in records if record["source_type"] == "blueprint"]
    eligible = [record for record in blueprints if record["eligible"]]
    projects = {record["project_group_id"] for record in eligible}
    parent = {project: project for project in projects}

    def find(project):
        while parent[project] != project:
            parent[project] = parent[parent[project]]
            project = parent[project]
        return project

    def union(left, right):
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    by_source = {record["source_id"]: record for record in eligible}
    for source_ids in exact.values():
        duplicate_projects = sorted({
            by_source[source_id]["project_group_id"]
            for source_id in source_ids
            if source_id in by_source
        })
        for project in duplicate_projects[1:]:
            union(duplicate_projects[0], project)

    references = [record for record in records if record["source_type"] == "reference"]
    return {
        "source_count": len(records),
        "page_count": sum(len(record["pages"]) for record in records),
        "blueprint_source_count": len(blueprints),
        "blueprint_page_count": sum(len(record["pages"]) for record in blueprints),
        "eligible_blueprint_source_count": len(eligible),
        "eligible_blueprint_page_count": sum(
            page["eligible"] for record in blueprints for page in record["pages"]
        ),
        "eligible_blueprint_drawing_group_count": len({
            (record["project_group_id"], record["drawing_set_id"])
            for record in eligible
        }),
        "independent_eligible_blueprint_project_count": len({find(project) for project in projects}),
        "reference_material_count": len(references),
        "reference_page_count": sum(len(record["pages"]) for record in references),
        "eligible_reference_material_count": sum(record["eligible"] for record in references),
        "eligible_reference_page_count": sum(
            page["eligible"] for record in references for page in record["pages"]
        ),
    }


def _read_manifest_bytes(path: Path) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            _fail("EXISTING_MANIFEST_INVALID")
        size = path.stat().st_size
        if size <= 0 or size > MAXIMUM_MANIFEST_BYTES:
            _fail("EXISTING_MANIFEST_INVALID")
        with path.open("rb") as stream:
            raw = stream.read(MAXIMUM_MANIFEST_BYTES + 1)
    except CorpusIntakeError:
        raise
    except OSError:
        _fail("EXISTING_MANIFEST_INVALID")
    if len(raw) != size:
        _fail("EXISTING_MANIFEST_INVALID")
    return raw


def _validate_manifest_payload(raw: bytes) -> dict[str, object]:
    try:
        decoded = json.loads(raw.decode("utf-8"))
        if type(decoded) is not dict:
            raise ValueError("Manifest must be an object.")
        schema_version = decoded.get("schema_version")
        if schema_version == LEGACY_MANIFEST_VERSION:
            existing = _StoredManifestV1.model_validate(decoded).model_dump(mode="json")
            records = deepcopy(existing["records"])
            _reset_eligibility_v1(records)
            exact, near = _validate_groups(records)
            coverage = _coverage_v1(records, exact)
        elif schema_version == MANIFEST_VERSION:
            existing = _StoredManifest.model_validate(decoded).model_dump(mode="json")
            records = deepcopy(existing["records"])
            _reset_eligibility(records)
            exact, near = _validate_groups(records)
            coverage = _coverage(records, exact)
        else:
            raise ValueError("Manifest schema version is unsupported.")
    except Exception:
        _fail("EXISTING_MANIFEST_INVALID")
    if (
        records != existing["records"]
        or exact != existing["exact_duplicate_groups"]
        or near != existing["near_duplicate_pairs"]
        or coverage != existing["coverage"]
    ):
        _fail("EXISTING_MANIFEST_INVALID")
    return existing


def _revision_directory(destination: Path) -> Path:
    return destination.with_name(f".{destination.name}.revisions")


def _validate_revision_history(destination: Path, existing: dict[str, object], existing_raw: bytes) -> None:
    revision_directory = _revision_directory(destination)
    expected_paths: set[Path] = set()
    expected_digest = existing["previous_manifest_sha256"]
    revision = existing["manifest_revision"] - 1
    while revision:
        archive = revision_directory / f"{revision:08d}-{expected_digest}.json"
        expected_paths.add(archive)
        raw = _read_manifest_bytes(archive)
        if sha256(raw).hexdigest() != expected_digest:
            _fail("EXISTING_MANIFEST_INVALID")
        archived = _validate_manifest_payload(raw)
        if archived["manifest_revision"] != revision:
            _fail("EXISTING_MANIFEST_INVALID")
        expected_digest = archived["previous_manifest_sha256"]
        revision -= 1
    if expected_digest is not None:
        _fail("EXISTING_MANIFEST_INVALID")
    if revision_directory.exists():
        try:
            if revision_directory.is_symlink() or not revision_directory.is_dir():
                _fail("EXISTING_MANIFEST_INVALID")
            actual_paths = set(revision_directory.iterdir())
        except CorpusIntakeError:
            raise
        except OSError:
            _fail("EXISTING_MANIFEST_INVALID")
        staged_archive = revision_directory / (
            f"{existing['manifest_revision']:08d}-{sha256(existing_raw).hexdigest()}.json"
        )
        if staged_archive in actual_paths and _read_manifest_bytes(staged_archive) == existing_raw:
            expected_paths.add(staged_archive)
        if actual_paths != expected_paths:
            _fail("EXISTING_MANIFEST_INVALID")
    elif expected_paths:
        _fail("EXISTING_MANIFEST_INVALID")


def _load_existing_manifest(destination: Path) -> tuple[dict[str, object] | None, bytes | None]:
    if not destination.exists():
        return None, None
    raw = _read_manifest_bytes(destination)
    existing = _validate_manifest_payload(raw)
    _validate_revision_history(destination, existing, raw)
    return existing, raw


def _archive_manifest_revision(destination: Path, existing: dict[str, object], existing_raw: bytes) -> None:
    revision_directory = _revision_directory(destination)
    try:
        if revision_directory.exists():
            if revision_directory.is_symlink() or not revision_directory.is_dir():
                _fail("MANIFEST_WRITE_CONFLICT")
        else:
            revision_directory.mkdir()
        digest = sha256(existing_raw).hexdigest()
        archive = revision_directory / f"{existing['manifest_revision']:08d}-{digest}.json"
        if archive.exists():
            if _read_manifest_bytes(archive) != existing_raw:
                _fail("MANIFEST_WRITE_CONFLICT")
            return
        with archive.open("xb") as output:
            output.write(existing_raw)
            output.flush()
            os.fsync(output.fileno())
    except CorpusIntakeError:
        raise
    except FileExistsError:
        _fail("MANIFEST_WRITE_CONFLICT")
    except OSError:
        _fail("MANIFEST_WRITE_FAILED")


def _upgrade_v1_records(existing: dict[str, object]) -> list[dict[str, object]]:
    if existing["schema_version"] == MANIFEST_VERSION:
        return deepcopy(existing["records"])
    records = []
    for prior in existing["records"]:
        pages = [
            {
                **page,
                "renderability": "renderable",
                "render_findings": [],
                "sheet_type": prior["sheet_type"],
                "quality": prior["quality"],
                "quality_review_history": [],
                "eligible": False,
                "eligibility_reasons": [],
            }
            for page in prior["pages"]
        ]
        records.append({
            **{key: value for key, value in prior.items() if key not in {"pages", "eligible", "eligibility_reasons"}},
            "structural_validation": {
                "status": "legacy_not_recorded",
                "findings": [],
            },
            "pages": pages,
            "eligible": False,
            "eligibility_reasons": [],
        })
    _reset_eligibility(records)
    return records


def _assert_incremental_compatibility(prior: dict[str, object], current: dict[str, object]) -> None:
    if prior.get("sha256") != current["sha256"]:
        _fail("CHANGED_SOURCE_CONFLICT")
    for field in ("relative_path", "source_type", "byte_size", "mime_type"):
        if prior.get(field) != current[field]:
            _fail("ESTABLISHED_SOURCE_CONFLICT")
    for field in ("project_group_id", "drawing_set_id"):
        if prior.get(field) is not None and prior.get(field) != current[field]:
            _fail("ESTABLISHED_GROUP_CONFLICT")
    for field in ("split", "sheet_type", "quality"):
        if prior.get(field) != "pending" and prior.get(field) != current[field]:
            _fail("ESTABLISHED_MEMBERSHIP_CONFLICT")
    prior_permission = prior.get("permission")
    if type(prior_permission) is not dict:
        _fail("EXISTING_MANIFEST_INVALID")
    if prior_permission.get("status") == "approved" and prior_permission != current["permission"]:
        _fail("ESTABLISHED_PERMISSION_CONFLICT")
    if (
        prior["structural_validation"]["status"] != "legacy_not_recorded"
        and prior["structural_validation"] != current["structural_validation"]
    ):
        _fail("ESTABLISHED_SOURCE_CONFLICT")
    if len(prior["pages"]) != len(current["pages"]):
        _fail("ESTABLISHED_SOURCE_CONFLICT")
    for prior_page, current_page in zip(prior["pages"], current["pages"]):
        for field in (
            "page_number",
            "width_pixels",
            "height_pixels",
            "perceptual_hash",
            "renderability",
            "render_findings",
        ):
            if prior_page[field] != current_page[field]:
                _fail("ESTABLISHED_SOURCE_CONFLICT")
        if prior_page["sheet_type"] != "pending" and current_page["sheet_type"] == "pending":
            current_page["sheet_type"] = prior_page["sheet_type"]
        if prior_page["quality"] != "pending" and prior_page["quality"] != current_page["quality"]:
            _fail("ESTABLISHED_QUALITY_CONFLICT")
        prior_reviews = prior_page["quality_review_history"]
        current_reviews = current_page["quality_review_history"]
        if not current_reviews:
            current_page["quality_review_history"] = deepcopy(prior_reviews)
        elif (
            len(current_reviews) < len(prior_reviews)
            or current_reviews[:len(prior_reviews)] != prior_reviews
        ):
            _fail("ESTABLISHED_QUALITY_REVIEW_CONFLICT")


def _merge_incrementally(existing: dict[str, object] | None, incoming: list[dict[str, object]]) -> list[dict[str, object]]:
    if existing is None:
        return incoming
    merged = {record["source_id"]: record for record in _upgrade_v1_records(existing)}
    for record in incoming:
        prior = merged.get(record["source_id"])
        if prior is not None:
            _assert_incremental_compatibility(prior, record)
        merged[record["source_id"]] = record
    return [merged[source_id] for source_id in sorted(merged)]


def _reset_eligibility_v1(records: list[dict[str, object]]) -> None:
    for record in records:
        reasons = []
        permission = record["permission"]
        if permission["status"] != "approved":
            reasons.append("permission_not_approved")
        if not record["project_group_id"]:
            reasons.append("project_group_missing")
        if not record["drawing_set_id"]:
            reasons.append("drawing_set_missing")
        if record["sheet_type"] == "pending":
            reasons.append("sheet_type_pending")
        if record["quality"] == "pending":
            reasons.append("quality_pending")
        elif record["quality"] == "degraded":
            reasons.append("degraded_requires_quality_approval")
        elif record["quality"] == "unsupported":
            reasons.append("quality_unsupported")
        if record["source_type"] == "blueprint" and record["split"] == "pending":
            reasons.append("split_pending")
        record["eligibility_reasons"] = sorted(reasons)
        record["eligible"] = not reasons


def _required_purpose(record: dict[str, object]) -> str | None:
    if record["source_type"] == "reference":
        return "reference_grounding"
    return {
        "train": "training",
        "development_validation": "development_evaluation",
        "sealed_test": "sealed_evaluation",
    }.get(record["split"])


def _reset_eligibility(records: list[dict[str, object]]) -> None:
    for record in records:
        common_reasons = []
        permission = record["permission"]
        required_purpose = _required_purpose(record)
        if (
            permission["status"] != "approved"
            or required_purpose not in permission["allowed_purposes"]
        ):
            common_reasons.append("permission_not_approved")
        if not record["project_group_id"]:
            common_reasons.append("project_group_missing")
        if not record["drawing_set_id"]:
            common_reasons.append("drawing_set_missing")
        if record["source_type"] == "blueprint" and record["split"] == "pending":
            common_reasons.append("split_pending")
        for page in record["pages"]:
            reasons = list(common_reasons)
            if page["renderability"] != "renderable":
                reasons.append("page_unrenderable")
            if page["sheet_type"] == "pending":
                reasons.append("sheet_type_pending")
            if page["quality"] == "pending":
                reasons.append("quality_pending")
            elif page["quality"] == "unsupported":
                reasons.append("quality_unsupported")
            elif page["quality"] == "degraded":
                applicable_reviews = [
                    review
                    for review in page["quality_review_history"]
                    if required_purpose in review["reviewed_purposes"]
                ]
                if not applicable_reviews:
                    reasons.append("degraded_quality_review_pending")
                elif applicable_reviews[-1]["decision"] != "accepted":
                    reasons.append("degraded_quality_rejected")
            page["eligibility_reasons"] = sorted(set(reasons))
            page["eligible"] = not page["eligibility_reasons"]
        record["eligible"] = any(page["eligible"] for page in record["pages"])
        record["eligibility_reasons"] = [] if record["eligible"] else sorted({
            reason
            for page in record["pages"]
            for reason in page["eligibility_reasons"]
        })


def _result(destination: Path, coverage: dict[str, int], exact, near, changed: bool) -> CorpusIntakeResult:
    return CorpusIntakeResult(
        manifest_path=destination,
        record_count=coverage["source_count"],
        page_count=coverage["page_count"],
        blueprint_source_count=coverage["blueprint_source_count"],
        blueprint_page_count=coverage["blueprint_page_count"],
        eligible_blueprint_source_count=coverage["eligible_blueprint_source_count"],
        eligible_blueprint_page_count=coverage["eligible_blueprint_page_count"],
        eligible_blueprint_drawing_group_count=coverage["eligible_blueprint_drawing_group_count"],
        independent_eligible_blueprint_project_count=coverage["independent_eligible_blueprint_project_count"],
        reference_material_count=coverage["reference_material_count"],
        reference_page_count=coverage["reference_page_count"],
        eligible_reference_material_count=coverage["eligible_reference_material_count"],
        eligible_reference_page_count=coverage["eligible_reference_page_count"],
        exact_duplicate_groups=len(exact),
        near_duplicate_pairs=len(near),
        changed=changed,
    )


def build_private_corpus_manifest(
    *,
    private_root: Path,
    manifest_path: Path,
    requests: tuple[CorpusIntakeRequest, ...],
) -> CorpusIntakeResult:
    try:
        root = Path(private_root).resolve(strict=True)
        destination = Path(manifest_path)
        parent = destination.parent.resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError):
        _fail("INVALID_PRIVATE_ROOT")
    if not root.is_dir() or not parent.is_relative_to(root) or destination.is_symlink():
        _fail("INVALID_PRIVATE_ROOT")
    identifiers = tuple(request.source_id for request in requests)
    if not requests or tuple(sorted(set(identifiers))) != identifiers:
        _fail("INVALID_SOURCE_ORDER")
    existing, existing_raw = _load_existing_manifest(destination)
    records = _merge_incrementally(existing, [_record(root, request) for request in requests])
    _reset_eligibility(records)
    exact, near = _validate_groups(records)
    coverage = _coverage(records, exact)
    semantic = {
        "records": records,
        "exact_duplicate_groups": exact,
        "near_duplicate_pairs": near,
        "coverage": coverage,
    }
    if existing is not None and all(existing[key] == value for key, value in semantic.items()):
        return _result(destination, coverage, exact, near, False)
    revision = 1 if existing is None else existing["manifest_revision"] + 1
    manifest = {
        "schema_version": MANIFEST_VERSION,
        "manifest_revision": revision,
        "previous_manifest_sha256": None if existing_raw is None else sha256(existing_raw).hexdigest(),
        **semantic,
    }
    serialized = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as output:
            output.write(serialized)
            output.flush()
            os.fsync(output.fileno())
        if existing is not None:
            _archive_manifest_revision(destination, existing, existing_raw)
        temporary.replace(destination)
    except CorpusIntakeError:
        temporary.unlink(missing_ok=True)
        raise
    except FileExistsError:
        _fail("MANIFEST_WRITE_CONFLICT")
    except OSError:
        temporary.unlink(missing_ok=True)
        _fail("MANIFEST_WRITE_FAILED")
    return _result(destination, coverage, exact, near, True)
