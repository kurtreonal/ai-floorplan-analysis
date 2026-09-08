import hashlib
import json
import os
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image
from pydantic import ValidationError
from pypdf import PdfWriter

from app.ai.floor_plan_interpretation import (
    CorpusIntakeError,
    CorpusIntakeRequest,
    PermissionRecord,
    build_private_corpus_manifest,
)
from app.services.upload_validation import UploadValidationError


def image_bytes(image_format="PNG", *, reverse=False):
    image = Image.new("L", (32, 24))
    for y in range(24):
        for x in range(32):
            image.putpixel((x, y), (31 - x if reverse else x) * 8)
    output = BytesIO()
    image.convert("RGB").save(output, format=image_format)
    image.close()
    return output.getvalue()


def pdf_bytes(pages=2, *, width=72, height=72):
    output = BytesIO()
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=width, height=height)
    writer.write(output)
    return output.getvalue()


def permission(purpose="training"):
    return PermissionRecord(
        status="approved",
        allowed_purposes=(purpose,),
        approved_by="VED data owner",
        evidence_reference="local approval record 1",
    )


def request(source_id, relative_path, *, split="train", project="project-a", drawing="drawing-a", source_type="blueprint", permitted=None, quality="supported"):
    if permitted is None:
        permitted = "reference_grounding" if source_type == "reference" else {
            "train": "training",
            "development_validation": "development_evaluation",
            "sealed_test": "sealed_evaluation",
        }.get(split, "training")
    return CorpusIntakeRequest(
        source_id=source_id,
        relative_path=relative_path,
        source_type=source_type,
        project_group_id=project,
        drawing_set_id=drawing,
        split=split,
        sheet_type="legend" if source_type == "reference" else "electrical_plan",
        quality=quality,
        permission=permission(permitted),
    )


def setup_root(tmp_path):
    source = tmp_path / "source-materials"
    manifests = tmp_path / "manifests"
    source.mkdir()
    manifests.mkdir()
    return source, manifests / "corpus-v1.json"


def build(tmp_path, requests):
    return build_private_corpus_manifest(
        private_root=tmp_path,
        manifest_path=tmp_path / "manifests" / "corpus-v1.json",
        requests=tuple(requests),
    )


def test_intake_is_idempotent_and_preserves_original_bytes(tmp_path):
    source, manifest = setup_root(tmp_path)
    path = source / "plan.png"
    path.write_bytes(image_bytes())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    item = request("source-a", "source-materials/plan.png")
    first = build(tmp_path, [item])
    first_bytes = manifest.read_bytes()
    first_mtime = manifest.stat().st_mtime_ns
    second = build(tmp_path, [item])
    assert first.changed is True
    assert second.changed is False
    assert second.eligible_count == 1
    assert second.independent_eligible_blueprint_project_count == 1
    assert manifest.read_bytes() == first_bytes
    assert manifest.stat().st_mtime_ns == first_mtime
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_changed_source_conflicts_with_existing_identity(tmp_path):
    source, _ = setup_root(tmp_path)
    path = source / "plan.png"
    path.write_bytes(image_bytes())
    item = request("source-a", "source-materials/plan.png")
    build(tmp_path, [item])
    path.write_bytes(image_bytes(reverse=True))
    with pytest.raises(CorpusIntakeError) as error:
        build(tmp_path, [item])
    assert error.value.code == "CHANGED_SOURCE_CONFLICT"


def test_multipage_pdf_inventory_is_one_based(tmp_path):
    source, manifest = setup_root(tmp_path)
    (source / "plan.pdf").write_bytes(pdf_bytes(3))
    result = build(tmp_path, [request("source-a", "source-materials/plan.pdf")])
    stored = json.loads(manifest.read_text(encoding="utf-8"))
    assert result.record_count == 1
    assert [page["page_number"] for page in stored["records"][0]["pages"]] == [1, 2, 3]


def test_pending_permission_and_metadata_are_not_eligible(tmp_path):
    source, manifest = setup_root(tmp_path)
    (source / "plan.png").write_bytes(image_bytes())
    pending = CorpusIntakeRequest(
        source_id="source-a",
        relative_path="source-materials/plan.png",
        source_type="blueprint",
        project_group_id=None,
        drawing_set_id=None,
        split="pending",
        sheet_type="pending",
        quality="pending",
        permission=PermissionRecord(status="pending", allowed_purposes=()),
    )
    result = build(tmp_path, [pending])
    assert result.eligible_count == 0
    assert json.loads(manifest.read_text(encoding="utf-8"))["records"][0]["eligible"] is False


def test_permission_cannot_be_incomplete_or_used_for_wrong_split():
    with pytest.raises(ValidationError):
        PermissionRecord(status="approved", allowed_purposes=("training",))
    with pytest.raises(ValidationError):
        request("source-a", "source-materials/a.png", split="sealed_test", permitted="training")
    with pytest.raises(ValidationError):
        request("source-a", "source-materials/a.png", source_type="reference", permitted="training")


def test_exact_duplicates_are_grouped_and_cannot_cross_splits(tmp_path):
    source, manifest = setup_root(tmp_path)
    content = image_bytes()
    (source / "a.png").write_bytes(content)
    (source / "b.png").write_bytes(content)
    same = [
        request("source-a", "source-materials/a.png", drawing="drawing-a"),
        request("source-b", "source-materials/b.png", drawing="drawing-b"),
    ]
    result = build(tmp_path, same)
    assert result.exact_duplicate_groups == 1
    assert result.eligible_blueprint_source_count == 2
    assert result.eligible_blueprint_drawing_group_count == 2
    assert result.independent_eligible_blueprint_project_count == 1
    assert len(json.loads(manifest.read_text(encoding="utf-8"))["exact_duplicate_groups"]) == 1

    manifest.unlink()
    cross = [
        same[0],
        request(
            "source-b",
            "source-materials/b.png",
            split="sealed_test",
            project="project-b",
            drawing="drawing-b",
        ),
    ]
    with pytest.raises(CorpusIntakeError) as error:
        build(tmp_path, cross)
    assert error.value.code == "EXACT_DUPLICATE_CROSSES_SPLITS"


def test_related_drawing_group_cannot_cross_splits(tmp_path):
    source, _ = setup_root(tmp_path)
    (source / "a.png").write_bytes(image_bytes())
    (source / "b.png").write_bytes(image_bytes(reverse=True))
    requests = [
        request("source-a", "source-materials/a.png"),
        request("source-b", "source-materials/b.png", split="sealed_test"),
    ]
    with pytest.raises(CorpusIntakeError) as error:
        build(tmp_path, requests)
    assert error.value.code == "PROJECT_CROSSES_SPLITS"


def test_different_drawing_sets_in_one_project_cannot_cross_splits(tmp_path):
    source, _ = setup_root(tmp_path)
    (source / "a.png").write_bytes(image_bytes())
    (source / "b.png").write_bytes(image_bytes(reverse=True))
    with pytest.raises(CorpusIntakeError) as error:
        build(tmp_path, [
            request("source-a", "source-materials/a.png", drawing="drawing-a"),
            request("source-b", "source-materials/b.png", split="sealed_test", drawing="drawing-b"),
        ])
    assert error.value.code == "PROJECT_CROSSES_SPLITS"


def test_drawing_set_identity_is_scoped_by_project(tmp_path):
    source, _ = setup_root(tmp_path)
    (source / "a.png").write_bytes(image_bytes())
    (source / "b.png").write_bytes(image_bytes(reverse=True))
    result = build(tmp_path, [
        request("source-a", "source-materials/a.png", project="project-a", drawing="drawing-a"),
        request("source-b", "source-materials/b.png", project="project-b", drawing="drawing-a"),
    ])
    assert result.eligible_blueprint_drawing_group_count == 2
    assert result.independent_eligible_blueprint_project_count == 2


def test_exact_duplicates_across_projects_count_as_one_independent_project_cluster(tmp_path):
    source, manifest = setup_root(tmp_path)
    content = image_bytes()
    (source / "a.png").write_bytes(content)
    (source / "b.png").write_bytes(content)
    result = build(tmp_path, [
        request("source-a", "source-materials/a.png", project="project-a", drawing="drawing-a"),
        request("source-b", "source-materials/b.png", project="project-b", drawing="drawing-b"),
    ])
    assert result.eligible_blueprint_source_count == 2
    assert result.eligible_blueprint_drawing_group_count == 2
    assert result.independent_eligible_blueprint_project_count == 1
    assert json.loads(manifest.read_text(encoding="utf-8"))["coverage"] == {
        "blueprint_source_count": 2,
        "eligible_blueprint_drawing_group_count": 2,
        "eligible_blueprint_source_count": 2,
        "eligible_reference_material_count": 0,
        "independent_eligible_blueprint_project_count": 1,
        "reference_material_count": 0,
        "source_count": 2,
    }


def test_near_duplicates_are_flagged_and_cross_split_rejected(tmp_path):
    source, _ = setup_root(tmp_path)
    visual = image_bytes()
    with Image.open(BytesIO(visual)) as image:
        output = BytesIO()
        image.save(output, format="JPEG", quality=95)
    (source / "a.png").write_bytes(visual)
    (source / "b.jpg").write_bytes(output.getvalue())
    requests = [
        request("source-a", "source-materials/a.png", drawing="drawing-a"),
        request(
            "source-b",
            "source-materials/b.jpg",
            split="sealed_test",
            project="project-b",
            drawing="drawing-b",
        ),
    ]
    with pytest.raises(CorpusIntakeError) as error:
        build(tmp_path, requests)
    assert error.value.code == "NEAR_DUPLICATE_CROSSES_SPLITS"


@pytest.mark.parametrize("relative", ["../outside.png", "C:/outside.png", "source-materials\\plan.png"])
def test_path_traversal_and_absolute_paths_are_rejected(tmp_path, relative):
    setup_root(tmp_path)
    with pytest.raises(CorpusIntakeError) as error:
        build(tmp_path, [request("source-a", relative)])
    assert error.value.code == "UNSAFE_SOURCE_PATH"


def test_symlink_source_is_rejected_when_supported(tmp_path):
    source, _ = setup_root(tmp_path)
    target = source / "target.png"
    link = source / "link.png"
    target.write_bytes(image_bytes())
    try:
        os.symlink(target, link)
    except OSError:
        pytest.skip("Creating symlinks is unavailable for this Windows user.")
    with pytest.raises(CorpusIntakeError) as error:
        build(tmp_path, [request("source-a", "source-materials/link.png")])
    assert error.value.code == "UNSAFE_SOURCE_PATH"


def test_symlink_rejection_branch_is_covered_without_windows_privilege(tmp_path):
    source, _ = setup_root(tmp_path)
    (source / "plan.png").write_bytes(image_bytes())
    original = Path.is_symlink

    def reports_only_source_as_link(path):
        return path.name == "plan.png" or original(path)

    with patch.object(Path, "is_symlink", reports_only_source_as_link):
        with pytest.raises(CorpusIntakeError) as error:
            build(tmp_path, [request("source-a", "source-materials/plan.png")])
    assert error.value.code == "UNSAFE_SOURCE_PATH"


def test_unsupported_and_corrupt_sources_fail_safely(tmp_path):
    source, _ = setup_root(tmp_path)
    (source / "bad.txt").write_text("not a plan")
    (source / "bad.png").write_bytes(b"not a png")
    for source_id, relative in (("source-a", "source-materials/bad.txt"), ("source-b", "source-materials/bad.png")):
        with pytest.raises(CorpusIntakeError):
            build(tmp_path, [request(source_id, relative)])


def test_manifest_must_remain_inside_existing_private_root(tmp_path):
    source, _ = setup_root(tmp_path)
    (source / "plan.png").write_bytes(image_bytes())
    outside = tmp_path.parent / "outside-manifest.json"
    with pytest.raises(CorpusIntakeError) as error:
        build_private_corpus_manifest(
            private_root=tmp_path,
            manifest_path=outside,
            requests=(request("source-a", "source-materials/plan.png"),),
        )
    assert error.value.code == "INVALID_PRIVATE_ROOT"


def test_request_order_is_deterministic(tmp_path):
    source, _ = setup_root(tmp_path)
    (source / "a.png").write_bytes(image_bytes())
    (source / "b.png").write_bytes(image_bytes(reverse=True))
    with pytest.raises(CorpusIntakeError) as error:
        build(tmp_path, [
            request("source-b", "source-materials/b.png", drawing="drawing-b"),
            request("source-a", "source-materials/a.png", drawing="drawing-a"),
        ])
    assert error.value.code == "INVALID_SOURCE_ORDER"


def test_incremental_intake_preserves_absent_records_and_versions_changes(tmp_path):
    source, manifest = setup_root(tmp_path)
    (source / "a.png").write_bytes(image_bytes())
    (source / "b.png").write_bytes(image_bytes(reverse=True))
    build(tmp_path, [request("source-a", "source-materials/a.png", project="project-a", drawing="drawing-a")])
    first = json.loads(manifest.read_text(encoding="utf-8"))
    result = build(tmp_path, [request("source-b", "source-materials/b.png", project="project-b", drawing="drawing-b")])
    second = json.loads(manifest.read_text(encoding="utf-8"))
    assert result.record_count == 2
    assert [record["source_id"] for record in second["records"]] == ["source-a", "source-b"]
    assert second["manifest_revision"] == 2
    assert second["previous_manifest_sha256"] == hashlib.sha256(
        (json.dumps(first, indent=2, sort_keys=True) + "\n").encode()
    ).hexdigest()


def test_incremental_intake_archives_exact_prior_manifest_bytes(tmp_path):
    source, manifest = setup_root(tmp_path)
    (source / "a.png").write_bytes(image_bytes())
    (source / "b.png").write_bytes(image_bytes(reverse=True))
    build(tmp_path, [request("source-a", "source-materials/a.png", project="project-a", drawing="drawing-a")])
    first_bytes = manifest.read_bytes()
    first_digest = hashlib.sha256(first_bytes).hexdigest()

    build(tmp_path, [request("source-b", "source-materials/b.png", project="project-b", drawing="drawing-b")])

    archive = manifest.with_name(f".{manifest.name}.revisions") / f"00000001-{first_digest}.json"
    assert archive.read_bytes() == first_bytes


def test_tampered_manifest_revision_archive_is_rejected(tmp_path):
    source, manifest = setup_root(tmp_path)
    (source / "a.png").write_bytes(image_bytes())
    (source / "b.png").write_bytes(image_bytes(reverse=True))
    (source / "c.png").write_bytes(image_bytes("JPEG"))
    build(tmp_path, [request("source-a", "source-materials/a.png", project="project-a", drawing="drawing-a")])
    first_digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    build(tmp_path, [request("source-b", "source-materials/b.png", project="project-b", drawing="drawing-b")])
    archive = manifest.with_name(f".{manifest.name}.revisions") / f"00000001-{first_digest}.json"
    archive.write_bytes(b"{}\n")

    with pytest.raises(CorpusIntakeError) as error:
        build(tmp_path, [request("source-c", "source-materials/c.png", project="project-c", drawing="drawing-c")])
    assert error.value.code == "EXISTING_MANIFEST_INVALID"


def test_malformed_preserved_record_is_rejected_before_incremental_merge(tmp_path):
    source, manifest = setup_root(tmp_path)
    (source / "a.png").write_bytes(image_bytes())
    (source / "b.png").write_bytes(image_bytes(reverse=True))
    build(tmp_path, [request("source-a", "source-materials/a.png", project="project-a", drawing="drawing-a")])
    stored = json.loads(manifest.read_text(encoding="utf-8"))
    stored["records"][0]["pages"][0]["page_number"] = True
    manifest.write_text(json.dumps(stored, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(CorpusIntakeError) as error:
        build(tmp_path, [request("source-b", "source-materials/b.png", project="project-b", drawing="drawing-b")])
    assert error.value.code == "EXISTING_MANIFEST_INVALID"


def test_tampered_derived_manifest_coverage_is_rejected(tmp_path):
    source, manifest = setup_root(tmp_path)
    (source / "a.png").write_bytes(image_bytes())
    (source / "b.png").write_bytes(image_bytes(reverse=True))
    build(tmp_path, [request("source-a", "source-materials/a.png", project="project-a", drawing="drawing-a")])
    stored = json.loads(manifest.read_text(encoding="utf-8"))
    stored["coverage"]["independent_eligible_blueprint_project_count"] = 99
    manifest.write_text(json.dumps(stored, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(CorpusIntakeError) as error:
        build(tmp_path, [request("source-b", "source-materials/b.png", project="project-b", drawing="drawing-b")])
    assert error.value.code == "EXISTING_MANIFEST_INVALID"


def test_incremental_intake_cannot_rewrite_established_split(tmp_path):
    source, _ = setup_root(tmp_path)
    (source / "a.png").write_bytes(image_bytes())
    build(tmp_path, [request("source-a", "source-materials/a.png")])
    with pytest.raises(CorpusIntakeError) as error:
        build(tmp_path, [request(
            "source-a",
            "source-materials/a.png",
            split="development_validation",
        )])
    assert error.value.code == "ESTABLISHED_MEMBERSHIP_CONFLICT"


def test_pending_record_can_be_enriched_without_removal(tmp_path):
    source, manifest = setup_root(tmp_path)
    (source / "a.png").write_bytes(image_bytes())
    pending = CorpusIntakeRequest(
        source_id="source-a",
        relative_path="source-materials/a.png",
        source_type="blueprint",
        project_group_id=None,
        drawing_set_id=None,
        split="pending",
        sheet_type="pending",
        quality="pending",
        permission=PermissionRecord(status="pending", allowed_purposes=()),
    )
    build(tmp_path, [pending])
    result = build(tmp_path, [request("source-a", "source-materials/a.png")])
    stored = json.loads(manifest.read_text(encoding="utf-8"))
    assert result.eligible_blueprint_source_count == 1
    assert stored["manifest_revision"] == 2
    assert stored["records"][0]["split"] == "train"


def test_degraded_and_unsupported_sources_are_inventoried_but_not_eligible(tmp_path):
    source, manifest = setup_root(tmp_path)
    (source / "a.png").write_bytes(image_bytes())
    (source / "b.png").write_bytes(image_bytes(reverse=True))
    result = build(tmp_path, [
        request("source-a", "source-materials/a.png", project="project-a", drawing="drawing-a", quality="degraded"),
        request("source-b", "source-materials/b.png", project="project-b", drawing="drawing-b", quality="unsupported"),
    ])
    stored = json.loads(manifest.read_text(encoding="utf-8"))
    assert result.blueprint_source_count == 2
    assert result.eligible_blueprint_source_count == 0
    assert [record["eligibility_reasons"] for record in stored["records"]] == [
        ["degraded_requires_quality_approval"],
        ["quality_unsupported"],
    ]


def test_recoverable_pdf_rejected_by_strict_validator_requires_degraded_quality(tmp_path):
    source, manifest = setup_root(tmp_path)
    (source / "plan.pdf").write_bytes(pdf_bytes())
    strict_rejection = UploadValidationError(
        "UPLOAD_PDF_CORRUPT",
        "The floor-plan PDF is corrupt or unreadable.",
    )
    with patch(
        "app.ai.floor_plan_interpretation.corpus_intake.validate_floor_plan_upload",
        side_effect=strict_rejection,
    ):
        result = build(tmp_path, [
            request(
                "source-a",
                "source-materials/plan.pdf",
                quality="degraded",
            )
        ])
    stored = json.loads(manifest.read_text(encoding="utf-8"))
    assert result.eligible_blueprint_source_count == 0
    assert stored["records"][0]["eligibility_reasons"] == [
        "degraded_requires_quality_approval"
    ]
    assert len(stored["records"][0]["pages"]) == 2


def test_strictly_invalid_pdf_cannot_be_marked_supported(tmp_path):
    source, _ = setup_root(tmp_path)
    (source / "plan.pdf").write_bytes(pdf_bytes())
    strict_rejection = UploadValidationError(
        "UPLOAD_PDF_CORRUPT",
        "The floor-plan PDF is corrupt or unreadable.",
    )
    with patch(
        "app.ai.floor_plan_interpretation.corpus_intake.validate_floor_plan_upload",
        side_effect=strict_rejection,
    ):
        with pytest.raises(CorpusIntakeError) as error:
            build(tmp_path, [request("source-a", "source-materials/plan.pdf")])
    assert error.value.code == "INVALID_SOURCE"


def test_reference_material_is_reported_separately(tmp_path):
    source, _ = setup_root(tmp_path)
    (source / "plan.png").write_bytes(image_bytes())
    (source / "reference.png").write_bytes(image_bytes(reverse=True))
    result = build(tmp_path, [
        request("source-a", "source-materials/plan.png"),
        request("source-b", "source-materials/reference.png", source_type="reference", split="pending"),
    ])
    assert result.record_count == 2
    assert result.blueprint_source_count == 1
    assert result.reference_material_count == 1
    assert result.eligible_reference_material_count == 1
    assert result.independent_eligible_blueprint_project_count == 1


def test_oversized_source_is_rejected_before_content_allocation(tmp_path):
    source, _ = setup_root(tmp_path)
    path = source / "large.png"
    with path.open("wb") as stream:
        stream.seek(25 * 1024 * 1024)
        stream.write(b"x")
    with patch.object(Path, "open", side_effect=AssertionError("oversized source must not be opened")):
        with pytest.raises(CorpusIntakeError) as error:
            build(tmp_path, [request("source-a", "source-materials/large.png")])
    assert error.value.code == "SOURCE_TOO_LARGE"


def test_image_dimensions_are_rejected_before_full_upload_decode(tmp_path):
    source, _ = setup_root(tmp_path)
    image = Image.new("RGB", (10001, 1), color="white")
    image.save(source / "wide.png", format="PNG")
    image.close()
    with patch(
        "app.ai.floor_plan_interpretation.corpus_intake.validate_floor_plan_upload",
        side_effect=AssertionError("full decoder must not run"),
    ):
        with pytest.raises(CorpusIntakeError) as error:
            build(tmp_path, [request("source-a", "source-materials/wide.png")])
    assert error.value.code == "IMAGE_ALLOCATION_LIMIT_EXCEEDED"


def test_pdf_render_dimensions_are_bounded_before_bitmap_allocation(tmp_path):
    source, _ = setup_root(tmp_path)
    (source / "huge.pdf").write_bytes(pdf_bytes(1, width=100000, height=72))
    with pytest.raises(CorpusIntakeError) as error:
        build(tmp_path, [request("source-a", "source-materials/huge.pdf")])
    assert error.value.code == "PDF_RENDER_LIMIT_EXCEEDED"
