import hashlib
import json
import os
from io import BytesIO
from pathlib import Path

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


def image_bytes(image_format="PNG", *, reverse=False):
    image = Image.new("L", (32, 24))
    for y in range(24):
        for x in range(32):
            image.putpixel((x, y), (31 - x if reverse else x) * 8)
    output = BytesIO()
    image.convert("RGB").save(output, format=image_format)
    image.close()
    return output.getvalue()


def pdf_bytes(pages=2):
    output = BytesIO()
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=72, height=72)
    writer.write(output)
    return output.getvalue()


def permission(purpose="training"):
    return PermissionRecord(
        status="approved",
        allowed_purposes=(purpose,),
        approved_by="VED data owner",
        evidence_reference="local approval record 1",
    )


def request(source_id, relative_path, *, split="train", project="project-a", drawing="drawing-a", source_type="blueprint", permitted=None):
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
        quality="supported",
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
    assert result.eligible_count == 1
    assert len(json.loads(manifest.read_text(encoding="utf-8"))["exact_duplicate_groups"]) == 1

    manifest.unlink()
    cross = [same[0], request("source-b", "source-materials/b.png", split="sealed_test", drawing="drawing-b")]
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
    assert error.value.code == "GROUP_CROSSES_SPLITS"


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
        request("source-b", "source-materials/b.jpg", split="sealed_test", drawing="drawing-b"),
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
