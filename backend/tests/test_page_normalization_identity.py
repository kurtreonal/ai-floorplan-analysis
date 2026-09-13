"""Page-aware normalized artifacts retain legacy paths and source bytes."""
from hashlib import sha256

import pytest
from PIL import Image

from app.services.image_normalization import normalize_image, ImageNormalizationError


def test_distinct_pages_never_overwrite_each_other_or_original(tmp_path):
    source = tmp_path / "originals" / "source.png"
    source.parent.mkdir()
    Image.new("RGB", (200, 200), "white").save(source)
    digest = sha256(source.read_bytes()).hexdigest()
    options = dict(source_path=source, source_mime_type="image/png",
                   processed_directory=tmp_path / "processed", floor_plan_id=1,
                   processing_job_id=2)
    first = normalize_image(**options, page_number=1)
    second = normalize_image(**options, page_number=2)
    legacy = normalize_image(**options)
    assert len({first.output_reference, second.output_reference, legacy.output_reference}) == 3
    assert first.output_reference.endswith("page-0001.png")
    assert second.output_reference.endswith("page-0002.png")
    assert legacy.output_reference.endswith("image.png")
    assert sha256(source.read_bytes()).hexdigest() == digest
    with pytest.raises(ImageNormalizationError) as error:
        normalize_image(**options, page_number=1)
    assert error.value.code == "OUTPUT_ALREADY_EXISTS"


@pytest.mark.parametrize("page", [True, 0, -1, "2", 1.5])
def test_invalid_page_identity_rejected_before_file_access(tmp_path, page):
    with pytest.raises(ImageNormalizationError) as error:
        normalize_image(source_path=tmp_path / "missing.png", source_mime_type="image/png",
                        processed_directory=tmp_path / "processed", floor_plan_id=1,
                        processing_job_id=2, page_number=page)
    assert error.value.code == "INVALID_PAGE_NUMBER"
