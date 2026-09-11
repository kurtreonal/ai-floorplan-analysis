import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from app.ai.floor_plan_interpretation.legend_reference_pack import (
    CatalogLegendSnapshot,
    DrawingLegendMapping,
    GlyphReference,
    LegendClassDefinition,
    LegendReferencePackError,
    LegendReferencePackRequest,
    SourceReference,
    SourceRegion,
    UnknownGlyph,
    build_legend_reference_pack,
)


def _image(path: Path, color: str) -> str:
    Image.new("RGB", (40, 30), color).save(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _catalog():
    return (
        CatalogLegendSnapshot(id=11, class_id=0, name="Approved outlet", is_active=True),
        CatalogLegendSnapshot(id=12, class_id=1, name="Approved switch", is_active=True),
        CatalogLegendSnapshot(id=13, class_id=2, name="Old class", is_active=False),
    )


def _request(root: Path, *, version=1, parent_path=None, parent_hash=None):
    first_hash = _image(root / "first.png", "white")
    second_hash = _image(root / "second.png", "black")
    region = SourceRegion(
        page_number=1,
        source_width=40,
        source_height=30,
        x_min=2,
        y_min=3,
        x_max=20,
        y_max=22,
    )
    return LegendReferencePackRequest(
        pack_id="ved-pack",
        version=version,
        parent_manifest_relative_path=parent_path,
        parent_manifest_sha256=parent_hash,
        sources=(
            SourceReference(
                source_id="drawing-a",
                source_kind="drawing_legend",
                source_relative_path="first.png",
                expected_sha256=first_hash,
                drawing_set_id="drawing-set-a",
                page_reference="sheet-E1-page-1",
                rights_holder="VED",
                permitted_uses=("inference_reference",),
                rights_evidence_ref="approval-rev-1",
            ),
            SourceReference(
                source_id="reference-b",
                source_kind="pec",
                source_relative_path="second.png",
                expected_sha256=second_hash,
                edition="2017",
                part="Part 1",
                page_reference="page-100",
                rights_holder="reference-owner",
                permitted_uses=("inference_reference", "evaluation"),
                rights_evidence_ref="rights-rev-2",
            ),
        ),
        classes=(
            LegendClassDefinition(
                symbol_legend_id=11,
                class_id=0,
                approved_name="Approved outlet",
                aliases=("Duplex receptacle",),
                description="Approved outlet class used by the local catalog.",
                approval_revision=1,
                approval_evidence_ref="class-review-1",
                glyphs=(
                    GlyphReference(
                        glyph_id="glyph-outlet",
                        source_id="drawing-a",
                        region=region,
                    ),
                ),
            ),
            LegendClassDefinition(
                symbol_legend_id=12,
                class_id=1,
                approved_name="Approved switch",
                aliases=("Single-pole switch",),
                description="Approved switch class used by the local catalog.",
                approval_revision=3,
                approval_evidence_ref="class-review-3",
                glyphs=(
                    GlyphReference(
                        glyph_id="glyph-switch",
                        source_id="reference-b",
                        region=region,
                    ),
                ),
            ),
        ),
        drawing_mappings=(
            DrawingLegendMapping(
                mapping_id="mapping-a-outlet",
                drawing_set_id="drawing-set-a",
                source_id="drawing-a",
                page_number=1,
                observed_label="DUPLEX OUTLET",
                symbol_legend_id=11,
                approval_revision=1,
                approval_evidence_ref="mapping-review-1",
            ),
        ),
        unknown_glyphs=(
            UnknownGlyph(
                unknown_id="unknown-a",
                drawing_set_id="drawing-set-a",
                source_id="drawing-a",
                region=region,
                reason="Meaning remains unresolved.",
            ),
        ),
    )


def test_builds_complete_immutable_pack_and_is_idempotent(tmp_path):
    request = _request(tmp_path)
    manifest = tmp_path / "packs" / "ved-pack" / "v0001" / "manifest.json"
    before = tuple(record.model_dump() for record in _catalog())

    first = build_legend_reference_pack(
        private_root=tmp_path,
        manifest_path=manifest,
        request=request,
        catalog=_catalog(),
    )
    second = build_legend_reference_pack(
        private_root=tmp_path,
        manifest_path=manifest,
        request=request,
        catalog=_catalog(),
    )

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert first.changed is True
    assert second.changed is False
    assert first.manifest_sha256 == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert (first.class_count, first.glyph_count, first.drawing_mapping_count) == (2, 2, 1)
    assert payload["unknown_glyphs"][0]["unknown_id"] == "unknown-a"
    assert tuple(record.model_dump() for record in _catalog()) == before


def test_requires_exact_active_catalog_coverage(tmp_path):
    request = _request(tmp_path)
    with pytest.raises(LegendReferencePackError, match="ACTIVE_CATALOG_COVERAGE"):
        build_legend_reference_pack(
            private_root=tmp_path,
            manifest_path=tmp_path / "manifest.json",
            request=request,
            catalog=_catalog()[:1],
        )


def test_rejects_catalog_identity_change_and_conflicting_alias(tmp_path):
    request = _request(tmp_path)
    changed_catalog = (*_catalog()[:1], CatalogLegendSnapshot(id=12, class_id=9, name="Approved switch", is_active=True))
    with pytest.raises(LegendReferencePackError, match="CATALOG_SNAPSHOT_MISMATCH"):
        build_legend_reference_pack(
            private_root=tmp_path,
            manifest_path=tmp_path / "manifest.json",
            request=request,
            catalog=changed_catalog,
        )

    payload = request.model_dump()
    payload["classes"][1]["aliases"] = ("Duplex receptacle",)
    conflict = LegendReferencePackRequest.model_validate(payload)
    with pytest.raises(LegendReferencePackError, match="CONFLICTING_ALIAS"):
        build_legend_reference_pack(
            private_root=tmp_path,
            manifest_path=tmp_path / "manifest.json",
            request=conflict,
            catalog=_catalog(),
        )


def test_rejects_missing_rights_and_incomplete_pec_metadata(tmp_path):
    digest = _image(tmp_path / "source.png", "white")
    base = {
        "source_id": "source-a",
        "source_kind": "drawing_legend",
        "source_relative_path": "source.png",
        "drawing_set_id": "drawing-set-a",
        "expected_sha256": digest,
        "page_reference": "page-1",
        "rights_holder": "owner",
        "permitted_uses": ("training",),
        "rights_evidence_ref": "rights-1",
    }
    with pytest.raises(ValidationError, match="Reference use must be explicit"):
        SourceReference(**base)
    base["source_kind"] = "pec"
    base["permitted_uses"] = ("inference_reference",)
    with pytest.raises(ValidationError, match="edition and part"):
        SourceReference(**base)


def test_rejects_unsafe_source_and_hash_mismatch(tmp_path):
    request = _request(tmp_path)
    payload = request.model_dump()
    payload["sources"][0]["source_relative_path"] = "../outside.png"
    with pytest.raises(ValidationError, match="private-root relative"):
        LegendReferencePackRequest.model_validate(payload)

    payload = request.model_dump()
    payload["sources"][0]["expected_sha256"] = "0" * 64
    mismatch = LegendReferencePackRequest.model_validate(payload)
    with pytest.raises(LegendReferencePackError, match="SOURCE_HASH_MISMATCH"):
        build_legend_reference_pack(
            private_root=tmp_path,
            manifest_path=tmp_path / "manifest.json",
            request=mismatch,
            catalog=_catalog(),
        )


def test_preserves_parent_linked_versions_and_rejects_wrong_parent(tmp_path):
    first_request = _request(tmp_path)
    first_path = tmp_path / "packs" / "ved-pack" / "v0001" / "manifest.json"
    first = build_legend_reference_pack(
        private_root=tmp_path,
        manifest_path=first_path,
        request=first_request,
        catalog=_catalog(),
    )
    first_bytes = first_path.read_bytes()

    second_request = _request(
        tmp_path,
        version=2,
        parent_path="packs/ved-pack/v0001/manifest.json",
        parent_hash=first.manifest_sha256,
    )
    second_path = tmp_path / "packs" / "ved-pack" / "v0002" / "manifest.json"
    second = build_legend_reference_pack(
        private_root=tmp_path,
        manifest_path=second_path,
        request=second_request,
        catalog=_catalog(),
    )
    assert second.changed is True
    assert first_path.read_bytes() == first_bytes

    wrong = second_request.model_copy(update={"parent_manifest_sha256": "f" * 64})
    with pytest.raises(LegendReferencePackError, match="PARENT_MANIFEST_HASH_MISMATCH"):
        build_legend_reference_pack(
            private_root=tmp_path,
            manifest_path=tmp_path / "wrong.json",
            request=wrong,
            catalog=_catalog(),
        )


def test_rejects_invalid_drawing_mapping_without_forcing_unknown(tmp_path):
    request = _request(tmp_path)
    invalid = request.model_copy(
        update={
            "drawing_mappings": (
                request.drawing_mappings[0].model_copy(update={"symbol_legend_id": 999}),
            )
        }
    )
    with pytest.raises(LegendReferencePackError, match="INVALID_DRAWING_MAPPING"):
        build_legend_reference_pack(
            private_root=tmp_path,
            manifest_path=tmp_path / "manifest.json",
            request=invalid,
            catalog=_catalog(),
        )

    cross_drawing = request.model_copy(
        update={
            "drawing_mappings": (
                request.drawing_mappings[0].model_copy(
                    update={"drawing_set_id": "different-drawing-set"}
                ),
            )
        }
    )
    with pytest.raises(LegendReferencePackError, match="INVALID_DRAWING_MAPPING"):
        build_legend_reference_pack(
            private_root=tmp_path,
            manifest_path=tmp_path / "cross-drawing.json",
            request=cross_drawing,
            catalog=_catalog(),
        )


def test_existing_version_cannot_be_rewritten(tmp_path):
    request = _request(tmp_path)
    manifest = tmp_path / "manifest.json"
    build_legend_reference_pack(
        private_root=tmp_path,
        manifest_path=manifest,
        request=request,
        catalog=_catalog(),
    )
    manifest.write_text("different", encoding="utf-8")
    with pytest.raises(LegendReferencePackError, match="IMMUTABLE_VERSION_CONFLICT"):
        build_legend_reference_pack(
            private_root=tmp_path,
            manifest_path=manifest,
            request=request,
            catalog=_catalog(),
        )


def test_historical_pack_survives_later_catalog_deactivation(tmp_path):
    request = _request(tmp_path)
    manifest = tmp_path / "manifest.json"
    build_legend_reference_pack(
        private_root=tmp_path,
        manifest_path=manifest,
        request=request,
        catalog=_catalog(),
    )
    original = manifest.read_bytes()
    changed_catalog = (
        _catalog()[0],
        _catalog()[1].model_copy(update={"is_active": False}),
        _catalog()[2],
    )
    with pytest.raises(LegendReferencePackError, match="ACTIVE_CATALOG_COVERAGE"):
        build_legend_reference_pack(
            private_root=tmp_path,
            manifest_path=tmp_path / "v2.json",
            request=request,
            catalog=changed_catalog,
        )
    assert manifest.read_bytes() == original
