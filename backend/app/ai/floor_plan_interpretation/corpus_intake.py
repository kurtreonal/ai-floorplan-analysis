from __future__ import annotations

import json
import os
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path, PurePosixPath, PureWindowsPath

import pypdfium2 as pdfium
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.upload_validation import FORMAT_BY_EXTENSION, validate_floor_plan_upload


MANIFEST_VERSION = 1
MAXIMUM_SOURCE_BYTES = 25 * 1024 * 1024
MAXIMUM_PAGES = 50
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
    eligible_count: int
    exact_duplicate_groups: int
    near_duplicate_pairs: int
    changed: bool


def _eligible_group_count(records: list[dict[str, object]], exact: dict[str, list[str]]) -> int:
    duplicate_hashes = set(exact)
    keys = set()
    for record in records:
        if not record["eligible"]:
            continue
        if record["sha256"] in duplicate_hashes:
            keys.add(("exact", record["sha256"]))
        else:
            keys.add(("drawing", record["project_group_id"], record["drawing_set_id"]))
    return len(keys)


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


def _image_hash(image: Image.Image) -> str:
    grayscale = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    try:
        pixels = list(grayscale.get_flattened_data())
    finally:
        grayscale.close()
    bits = [pixels[row * 9 + column] > pixels[row * 9 + column + 1] for row in range(8) for column in range(8)]
    return f"{sum(1 << index for index, bit in enumerate(bits) if bit):016x}"


def _page_fingerprints(path: Path, content: bytes, extension: str, page_count: int) -> list[dict[str, object]]:
    pages: list[dict[str, object]] = []
    if extension != ".pdf":
        with Image.open(BytesIO(content)) as image:
            pages.append({"page_number": 1, "width_pixels": image.width, "height_pixels": image.height, "perceptual_hash": _image_hash(image)})
        return pages
    document = None
    try:
        document = pdfium.PdfDocument(str(path))
        for index in range(page_count):
            page = document[index]
            bitmap = None
            pil_image = None
            try:
                bitmap = page.render(scale=0.25)
                pil_image = bitmap.to_pil()
                pages.append({"page_number": index + 1, "width_pixels": int(bitmap.width), "height_pixels": int(bitmap.height), "perceptual_hash": _image_hash(pil_image)})
            finally:
                if pil_image is not None:
                    pil_image.close()
                if bitmap is not None:
                    bitmap.close()
                page.close()
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
    before = sha256(source.read_bytes()).hexdigest()
    content = source.read_bytes()
    extension = source.suffix.casefold()
    policy = FORMAT_BY_EXTENSION.get(extension)
    if policy is None:
        _fail("UNSUPPORTED_SOURCE")
    try:
        validated = validate_floor_plan_upload(
            filename=source.name,
            declared_mime_type=policy[0],
            content=content,
            max_file_size_bytes=MAXIMUM_SOURCE_BYTES,
        )
    except Exception:
        _fail("INVALID_SOURCE")
    page_count = validated.page_count or 1
    if page_count > MAXIMUM_PAGES:
        _fail("PAGE_LIMIT_EXCEEDED")
    pages = _page_fingerprints(source, content, extension, page_count)
    after = sha256(source.read_bytes()).hexdigest()
    if before != after:
        _fail("ORIGINAL_CHANGED_DURING_INTAKE")
    complete_metadata = all((request.project_group_id, request.drawing_set_id)) and request.sheet_type != "pending" and request.quality != "pending"
    eligible = request.permission.status == "approved" and complete_metadata and (
        request.split != "pending" or request.source_type == "reference"
    )
    return {
        "source_id": request.source_id,
        "relative_path": request.relative_path,
        "source_type": request.source_type,
        "sha256": before,
        "byte_size": len(content),
        "mime_type": validated.mime_type,
        "project_group_id": request.project_group_id,
        "drawing_set_id": request.drawing_set_id,
        "split": request.split,
        "sheet_type": request.sheet_type,
        "quality": request.quality,
        "permission": request.permission.model_dump(mode="json"),
        "pages": pages,
        "eligible": bool(eligible),
    }


def _validate_groups(records: list[dict[str, object]]) -> tuple[dict[str, list[str]], list[dict[str, str]]]:
    group_splits: dict[tuple[str, str], set[str]] = {}
    hashes: dict[str, list[dict]] = {}
    for record in records:
        if record["project_group_id"] and record["drawing_set_id"] and record["split"] != "pending":
            key = (record["project_group_id"], record["drawing_set_id"])
            group_splits.setdefault(key, set()).add(record["split"])
        hashes.setdefault(record["sha256"], []).append(record)
    if any(len(splits) > 1 for splits in group_splits.values()):
        _fail("GROUP_CROSSES_SPLITS")
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
    return exact, near


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
    records = [_record(root, request) for request in requests]
    exact, near = _validate_groups(records)
    manifest = {
        "schema_version": MANIFEST_VERSION,
        "records": records,
        "exact_duplicate_groups": exact,
        "near_duplicate_pairs": near,
    }
    serialized = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if destination.exists():
        try:
            existing = json.loads(destination.read_text(encoding="utf-8"))
        except Exception:
            _fail("EXISTING_MANIFEST_INVALID")
        existing_by_id = {item.get("source_id"): item for item in existing.get("records", [])}
        for record in records:
            prior = existing_by_id.get(record["source_id"])
            if prior is not None and prior.get("sha256") != record["sha256"]:
                _fail("CHANGED_SOURCE_CONFLICT")
        if destination.read_text(encoding="utf-8") == serialized:
            return CorpusIntakeResult(destination, len(records), _eligible_group_count(records, exact), len(exact), len(near), False)
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
    return CorpusIntakeResult(destination, len(records), _eligible_group_count(records, exact), len(exact), len(near), True)
