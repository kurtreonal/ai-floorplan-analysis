from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from math import ceil, isfinite
from pathlib import Path, PurePosixPath, PureWindowsPath

import pypdfium2 as pdfium
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.upload_validation import FORMAT_BY_EXTENSION, validate_floor_plan_upload


MANIFEST_VERSION = 1
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
        return self


@dataclass(frozen=True)
class CorpusIntakeResult:
    manifest_path: Path
    record_count: int
    blueprint_source_count: int
    eligible_blueprint_source_count: int
    eligible_blueprint_drawing_group_count: int
    independent_eligible_blueprint_project_count: int
    reference_material_count: int
    eligible_reference_material_count: int
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
            pages.append({"page_number": 1, "width_pixels": image.width, "height_pixels": image.height, "perceptual_hash": _image_hash(image)})
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
                bitmap = page.render(scale=FINGERPRINT_PDF_SCALE)
                if (
                    int(bitmap.width) > MAXIMUM_IMAGE_EDGE
                    or int(bitmap.height) > MAXIMUM_IMAGE_EDGE
                    or int(bitmap.width) * int(bitmap.height) > MAXIMUM_IMAGE_PIXELS
                ):
                    _fail("PDF_RENDER_LIMIT_EXCEEDED")
                pil_image = bitmap.to_pil()
                pages.append({"page_number": index + 1, "width_pixels": int(bitmap.width), "height_pixels": int(bitmap.height), "perceptual_hash": _image_hash(pil_image)})
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


def _hamming(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def _near_duplicate(left: dict, right: dict) -> bool:
    left_pages, right_pages = left["pages"], right["pages"]
    return len(left_pages) == len(right_pages) and all(
        _hamming(a["perceptual_hash"], b["perceptual_hash"]) <= 5
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
    try:
        validated = validate_floor_plan_upload(
            filename=source.name,
            declared_mime_type=policy[0],
            content=content,
            max_file_size_bytes=MAXIMUM_SOURCE_BYTES,
        )
    except CorpusIntakeError:
        raise
    except Exception:
        _fail("INVALID_SOURCE")
    page_count = validated.page_count or 1
    if page_count > MAXIMUM_PAGES:
        _fail("PAGE_LIMIT_EXCEEDED")
    pages = _page_fingerprints(content, extension, page_count)
    _verify_original_digest(source, original_digest)
    reasons = []
    if request.permission.status != "approved":
        reasons.append("permission_not_approved")
    if not request.project_group_id:
        reasons.append("project_group_missing")
    if not request.drawing_set_id:
        reasons.append("drawing_set_missing")
    if request.sheet_type == "pending":
        reasons.append("sheet_type_pending")
    if request.quality == "pending":
        reasons.append("quality_pending")
    elif request.quality == "degraded":
        reasons.append("degraded_requires_quality_approval")
    elif request.quality == "unsupported":
        reasons.append("quality_unsupported")
    if request.source_type == "blueprint" and request.split == "pending":
        reasons.append("split_pending")
    return {
        "source_id": request.source_id,
        "relative_path": request.relative_path,
        "source_type": request.source_type,
        "sha256": original_digest,
        "byte_size": len(content),
        "mime_type": validated.mime_type,
        "project_group_id": request.project_group_id,
        "drawing_set_id": request.drawing_set_id,
        "split": request.split,
        "sheet_type": request.sheet_type,
        "quality": request.quality,
        "permission": request.permission.model_dump(mode="json"),
        "pages": pages,
        "eligible": not reasons,
        "eligibility_reasons": sorted(reasons),
    }


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
            left["eligible"] = False
            right["eligible"] = False
            for record in (left, right):
                reasons = set(record.get("eligibility_reasons", []))
                reasons.add("near_duplicate_pending_resolution")
                record["eligibility_reasons"] = sorted(reasons)
    return exact, near


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


def _load_existing_manifest(destination: Path) -> tuple[dict[str, object] | None, bytes | None]:
    if not destination.exists():
        return None, None
    try:
        size = destination.stat().st_size
        if size <= 0 or size > MAXIMUM_MANIFEST_BYTES:
            _fail("EXISTING_MANIFEST_INVALID")
        with destination.open("rb") as stream:
            raw = stream.read(MAXIMUM_MANIFEST_BYTES + 1)
        existing = json.loads(raw.decode("utf-8"))
    except CorpusIntakeError:
        raise
    except Exception:
        _fail("EXISTING_MANIFEST_INVALID")
    required = {
        "schema_version", "manifest_revision", "previous_manifest_sha256",
        "records", "exact_duplicate_groups", "near_duplicate_pairs", "coverage",
    }
    if (
        type(existing) is not dict
        or set(existing) != required
        or existing["schema_version"] != MANIFEST_VERSION
        or type(existing["manifest_revision"]) is not int
        or existing["manifest_revision"] <= 0
        or type(existing["records"]) is not list
    ):
        _fail("EXISTING_MANIFEST_INVALID")
    identifiers = tuple(record.get("source_id") for record in existing["records"] if type(record) is dict)
    if len(identifiers) != len(existing["records"]) or tuple(sorted(set(identifiers))) != identifiers:
        _fail("EXISTING_MANIFEST_INVALID")
    return existing, raw


def _assert_incremental_compatibility(prior: dict[str, object], current: dict[str, object]) -> None:
    if prior.get("sha256") != current["sha256"]:
        _fail("CHANGED_SOURCE_CONFLICT")
    for field in ("relative_path", "source_type", "byte_size", "mime_type", "pages"):
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


def _merge_incrementally(existing: dict[str, object] | None, incoming: list[dict[str, object]]) -> list[dict[str, object]]:
    if existing is None:
        return incoming
    merged = {record["source_id"]: deepcopy(record) for record in existing["records"]}
    for record in incoming:
        prior = merged.get(record["source_id"])
        if prior is not None:
            _assert_incremental_compatibility(prior, record)
        merged[record["source_id"]] = record
    return [merged[source_id] for source_id in sorted(merged)]


def _reset_eligibility(records: list[dict[str, object]]) -> None:
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


def _result(destination: Path, coverage: dict[str, int], exact, near, changed: bool) -> CorpusIntakeResult:
    return CorpusIntakeResult(
        manifest_path=destination,
        record_count=coverage["source_count"],
        blueprint_source_count=coverage["blueprint_source_count"],
        eligible_blueprint_source_count=coverage["eligible_blueprint_source_count"],
        eligible_blueprint_drawing_group_count=coverage["eligible_blueprint_drawing_group_count"],
        independent_eligible_blueprint_project_count=coverage["independent_eligible_blueprint_project_count"],
        reference_material_count=coverage["reference_material_count"],
        eligible_reference_material_count=coverage["eligible_reference_material_count"],
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
        temporary.replace(destination)
    except FileExistsError:
        _fail("MANIFEST_WRITE_CONFLICT")
    except OSError:
        temporary.unlink(missing_ok=True)
        _fail("MANIFEST_WRITE_FAILED")
    return _result(destination, coverage, exact, near, True)
