"""Immutable, local-only U4 legend/reference-pack construction."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator


MAX_REFERENCE_FILE_BYTES = 25 * 1024 * 1024
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class LegendReferencePackError(ValueError):
    """Raised when a reference pack cannot be built safely."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> None:
    raise LegendReferencePackError(code)


class PackModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class CatalogLegendSnapshot(PackModel):
    id: int = Field(gt=0)
    class_id: int = Field(ge=0, le=2_147_483_647)
    name: str = Field(min_length=1, max_length=255)
    is_active: bool


class SourceReference(PackModel):
    source_id: str
    source_kind: Literal["drawing_legend", "pec", "other_reference"]
    source_relative_path: str = Field(min_length=1, max_length=512)
    expected_sha256: str
    drawing_set_id: str | None = Field(default=None, max_length=128)
    edition: str | None = Field(default=None, max_length=128)
    part: str | None = Field(default=None, max_length=128)
    page_reference: str = Field(min_length=1, max_length=128)
    rights_holder: str = Field(min_length=1, max_length=255)
    permitted_uses: tuple[
        Literal["inference_reference", "evaluation", "training"], ...
    ] = Field(min_length=1, max_length=8)
    rights_evidence_ref: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_source(self):
        if not SAFE_ID.fullmatch(self.source_id):
            raise ValueError("Invalid source identity.")
        path = Path(self.source_relative_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Reference source path must be private-root relative.")
        if not SHA256.fullmatch(self.expected_sha256):
            raise ValueError("Invalid source hash.")
        if self.source_kind == "drawing_legend" and (
            self.drawing_set_id is None or not SAFE_ID.fullmatch(self.drawing_set_id)
        ):
            raise ValueError("Drawing legend sources require drawing-set identity.")
        if len(set(self.permitted_uses)) != len(self.permitted_uses):
            raise ValueError("Permitted uses must be unique.")
        if "inference_reference" not in self.permitted_uses:
            raise ValueError("Reference use must be explicit.")
        if self.source_kind == "pec" and (not self.edition or not self.part):
            raise ValueError("PEC references require edition and part metadata.")
        return self


class SourceRegion(PackModel):
    page_number: int = Field(gt=0, le=10_000)
    source_width: int = Field(gt=0, le=10_000)
    source_height: int = Field(gt=0, le=10_000)
    x_min: int = Field(ge=0)
    y_min: int = Field(ge=0)
    x_max: int = Field(gt=0)
    y_max: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_bounds(self):
        if (
            self.x_min >= self.x_max
            or self.y_min >= self.y_max
            or self.x_max > self.source_width
            or self.y_max > self.source_height
        ):
            raise ValueError("Source region is outside its declared page frame.")
        return self


class GlyphReference(PackModel):
    glyph_id: str
    source_id: str
    region: SourceRegion

    @model_validator(mode="after")
    def validate_identity(self):
        if not SAFE_ID.fullmatch(self.glyph_id) or not SAFE_ID.fullmatch(self.source_id):
            raise ValueError("Invalid glyph identity.")
        return self


class LegendClassDefinition(PackModel):
    symbol_legend_id: int = Field(gt=0)
    class_id: int = Field(ge=0, le=2_147_483_647)
    approved_name: str = Field(min_length=1, max_length=255)
    is_active: Literal[True] = True
    aliases: tuple[str, ...] = Field(min_length=1, max_length=32)
    description: str = Field(min_length=1, max_length=1_000)
    approval_revision: int = Field(gt=0)
    approval_evidence_ref: str = Field(min_length=1, max_length=128)
    glyphs: tuple[GlyphReference, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_names(self):
        names = (self.approved_name, *self.aliases)
        if any(value != value.strip() or "\x00" in value for value in names):
            raise ValueError("Legend names and aliases must be normalized.")
        if len({value.casefold() for value in names}) != len(names):
            raise ValueError("Legend aliases must be distinct.")
        return self


class DrawingLegendMapping(PackModel):
    mapping_id: str
    drawing_set_id: str
    source_id: str
    page_number: int = Field(gt=0, le=10_000)
    observed_label: str = Field(min_length=1, max_length=255)
    symbol_legend_id: int = Field(gt=0)
    approval_revision: int = Field(gt=0)
    approval_evidence_ref: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_ids(self):
        if any(
            not SAFE_ID.fullmatch(value)
            for value in (self.mapping_id, self.drawing_set_id, self.source_id)
        ):
            raise ValueError("Invalid drawing mapping identity.")
        if self.observed_label != self.observed_label.strip() or "\x00" in self.observed_label:
            raise ValueError("Observed labels must be normalized.")
        return self


class UnknownGlyph(PackModel):
    unknown_id: str
    drawing_set_id: str
    source_id: str
    region: SourceRegion
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_ids(self):
        if any(
            not SAFE_ID.fullmatch(value)
            for value in (self.unknown_id, self.drawing_set_id, self.source_id)
        ):
            raise ValueError("Invalid unknown-glyph identity.")
        return self


class LegendReferencePackRequest(PackModel):
    pack_id: str
    version: int = Field(gt=0)
    parent_manifest_relative_path: str | None = Field(default=None, max_length=512)
    parent_manifest_sha256: str | None = None
    sources: tuple[SourceReference, ...] = Field(min_length=1, max_length=1_000)
    classes: tuple[LegendClassDefinition, ...] = Field(min_length=1, max_length=1_000)
    drawing_mappings: tuple[DrawingLegendMapping, ...] = Field(default=(), max_length=10_000)
    unknown_glyphs: tuple[UnknownGlyph, ...] = Field(default=(), max_length=10_000)

    @model_validator(mode="after")
    def validate_version(self):
        if not SAFE_ID.fullmatch(self.pack_id):
            raise ValueError("Invalid pack identity.")
        has_parent = self.parent_manifest_relative_path is not None
        if self.version == 1 and (has_parent or self.parent_manifest_sha256 is not None):
            raise ValueError("Version 1 cannot declare a parent.")
        if self.version > 1 and (
            not has_parent
            or self.parent_manifest_sha256 is None
            or not SHA256.fullmatch(self.parent_manifest_sha256)
        ):
            raise ValueError("Later versions require a hashed parent manifest.")
        if has_parent:
            path = Path(self.parent_manifest_relative_path)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Parent manifest path must be private-root relative.")
        return self


@dataclass(frozen=True)
class LegendReferencePackResult:
    manifest_path: Path
    manifest_sha256: str
    class_count: int
    glyph_count: int
    drawing_mapping_count: int
    unknown_glyph_count: int
    changed: bool


def _resolve_private_file(root: Path, relative_path: str, error_code: str) -> Path:
    candidate = root / relative_path
    if candidate.is_symlink():
        _fail(error_code)
    resolved = candidate.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError:
        _fail(error_code)
    if not resolved.is_file() or resolved.stat().st_size > MAX_REFERENCE_FILE_BYTES:
        _fail(error_code)
    return resolved


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_catalog(
    request: LegendReferencePackRequest,
    catalog: Sequence[CatalogLegendSnapshot],
) -> None:
    active = {record.id: record for record in catalog if record.is_active}
    supplied = {record.symbol_legend_id: record for record in request.classes}
    if len(supplied) != len(request.classes) or set(active) != set(supplied):
        _fail("ACTIVE_CATALOG_COVERAGE")
    aliases: dict[str, int] = {}
    for legend_id, definition in supplied.items():
        snapshot = active[legend_id]
        if (
            snapshot.class_id != definition.class_id
            or snapshot.name != definition.approved_name
        ):
            _fail("CATALOG_SNAPSHOT_MISMATCH")
        for alias in (definition.approved_name, *definition.aliases):
            owner = aliases.setdefault(alias.casefold(), legend_id)
            if owner != legend_id:
                _fail("CONFLICTING_ALIAS")


def _validate_sources(
    root: Path,
    request: LegendReferencePackRequest,
) -> dict[str, str]:
    sources = {source.source_id: source for source in request.sources}
    if len(sources) != len(request.sources):
        _fail("DUPLICATE_SOURCE_ID")
    observed_hashes: dict[str, str] = {}
    for source in request.sources:
        path = _resolve_private_file(
            root,
            source.source_relative_path,
            "UNSAFE_REFERENCE_SOURCE",
        )
        digest = _sha256_file(path)
        if digest != source.expected_sha256:
            _fail("SOURCE_HASH_MISMATCH")
        observed_hashes[source.source_id] = digest
    for definition in request.classes:
        for glyph in definition.glyphs:
            if glyph.source_id not in sources:
                _fail("UNKNOWN_GLYPH_SOURCE")
    class_ids = {record.symbol_legend_id for record in request.classes}
    mapping_ids: set[str] = set()
    for mapping in request.drawing_mappings:
        if mapping.mapping_id in mapping_ids:
            _fail("DUPLICATE_DRAWING_MAPPING")
        mapping_ids.add(mapping.mapping_id)
        source = sources.get(mapping.source_id)
        if (
            source is None
            or mapping.symbol_legend_id not in class_ids
            or source.source_kind != "drawing_legend"
            or source.drawing_set_id != mapping.drawing_set_id
        ):
            _fail("INVALID_DRAWING_MAPPING")
    unknown_ids: set[str] = set()
    for unknown in request.unknown_glyphs:
        source = sources.get(unknown.source_id)
        if (
            unknown.unknown_id in unknown_ids
            or source is None
            or source.source_kind != "drawing_legend"
            or source.drawing_set_id != unknown.drawing_set_id
        ):
            _fail("INVALID_UNKNOWN_GLYPH")
        unknown_ids.add(unknown.unknown_id)
    return observed_hashes


def _validate_parent(root: Path, request: LegendReferencePackRequest) -> None:
    if request.version == 1:
        return
    parent = _resolve_private_file(
        root,
        request.parent_manifest_relative_path,
        "INVALID_PARENT_MANIFEST",
    )
    raw = parent.read_bytes()
    if hashlib.sha256(raw).hexdigest() != request.parent_manifest_sha256:
        _fail("PARENT_MANIFEST_HASH_MISMATCH")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail("INVALID_PARENT_MANIFEST")
    if payload.get("pack_id") != request.pack_id or payload.get("version") != request.version - 1:
        _fail("INVALID_PARENT_MANIFEST")


def build_legend_reference_pack(
    *,
    private_root: Path,
    manifest_path: Path,
    request: LegendReferencePackRequest,
    catalog: Sequence[CatalogLegendSnapshot],
) -> LegendReferencePackResult:
    """Validate and write one immutable reference-pack manifest."""

    if private_root.is_symlink():
        _fail("INVALID_PRIVATE_ROOT")
    root = private_root.resolve(strict=True)
    if not root.is_dir():
        _fail("INVALID_PRIVATE_ROOT")
    destination = manifest_path.resolve(strict=False)
    try:
        destination.relative_to(root)
    except ValueError:
        _fail("MANIFEST_OUTSIDE_PRIVATE_ROOT")
    if destination.is_symlink():
        _fail("MANIFEST_OUTSIDE_PRIVATE_ROOT")

    _validate_catalog(request, catalog)
    source_hashes = _validate_sources(root, request)
    _validate_parent(root, request)

    payload = request.model_dump(mode="json")
    payload["schema_version"] = 1
    payload["source_hashes"] = dict(sorted(source_hashes.items()))
    raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    digest = hashlib.sha256(raw).hexdigest()

    if destination.exists():
        if (
            destination.is_file()
            and destination.stat().st_size <= MAX_REFERENCE_FILE_BYTES
            and destination.read_bytes() == raw
        ):
            changed = False
        else:
            _fail("IMMUTABLE_VERSION_CONFLICT")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
        try:
            with temporary.open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink()
        changed = True

    return LegendReferencePackResult(
        manifest_path=destination,
        manifest_sha256=digest,
        class_count=len(request.classes),
        glyph_count=sum(len(record.glyphs) for record in request.classes),
        drawing_mapping_count=len(request.drawing_mappings),
        unknown_glyph_count=len(request.unknown_glyphs),
        changed=changed,
    )
