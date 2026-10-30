"""Immutable fixture datasets exercise audit guards without real annotations."""
import json
from pathlib import Path

import pytest

from train_reviewed_multiclass import KIND, LOSS, digest, validate_dataset, train, effective_training_inputs


def fixture(tmp_path):
    from PIL import Image
    from prepare_reviewed_plan_training import review_targets
    dataset = tmp_path / "dataset"
    (dataset / "images/train").mkdir(parents=True)
    (dataset / "labels/train").mkdir(parents=True)
    classes = [{"id": 0, "label": "Normal", "legend_entry": "approved:N"},
               {"id": 1, "label": "UPS", "legend_entry": "approved:U"}]
    parent = tmp_path / "parent.json"
    parent.write_text(json.dumps({"classes": classes[:1]}))
    base = tmp_path / "local.pt"
    base.write_bytes(b"local existing fixture checkpoint, not inference weights")
    image = dataset / "images/train/positive.png"
    Image.new("RGB", (256, 256), "white").save(image)
    label = dataset / "labels/train/positive.txt"
    label.write_text("0 .5 .5 .1 .1\n")
    data = {"kind": KIND, "required_loss": LOSS, "base_model_sha256": digest(base),
            "parent_manifest_sha256": digest(parent), "classes": classes,
            "authorization": {"local_development_training": True, "production_approval": False,
                              "user_statement": "Standing local training authorization", "saved_session_sha256": "a" * 64},
            "training_image_records": [{"image_id": "positive", "image_sha256": digest(image),
                                       "label_sha256": digest(label), "allowed_class_ids": [[0, 1]]}]}
    sheet = dict(id="sheet-01", group=21, source_sha256=digest(image), width=256, height=256,
        annotations=[dict(id="one", layer="symbols", review_state="user_reviewed", class_state="unmapped",
            legend_entry="uncertain", label="Duplex convenience outlet normal/UPS",
            geometry=dict(type="bbox", coordinates=[115.2, 115.2, 140.8, 140.8]))])
    session = dict(sheets=[sheet])
    registry = dict(legend_catalog=[dict(legend_entry=r["legend_entry"],
        label="Duplex convenience outlet - " + ("normal power" if r["id"]==0 else "UPS power"),
        examples=[dict(source_sheet_id="sheet-01")]) for r in classes])
    data["authorization"]["groups"] = [21]
    (dataset / "saved-session-snapshot.json").write_text(json.dumps(session))
    data["saved_session_sha256"] = digest(dataset / "saved-session-snapshot.json")
    data["authorization"]["saved_session_sha256"] = data["saved_session_sha256"]
    for filename, value, key in (("legend-registry-snapshot.json", registry, "legend_registry_sha256"),
            ("local-training-authorization.json", data["authorization"], "authorization_sha256")):
        (dataset / filename).write_text(json.dumps(value))
        data[key] = digest(dataset / filename)
    (dataset / "parent-manifest-snapshot.json").write_bytes(parent.read_bytes())
    (dataset / "sources").mkdir()
    for filename in ("sheet-01.png", "sheet-01-normalized.png"):
        (dataset / "sources" / filename).write_bytes(image.read_bytes())
    targets, _, sheets = review_targets(session, registry["legend_catalog"],
        {digest(image): dataset / "sources/sheet-01.png"}, [21], classes)
    sheets[0].update(normalized_size=[256, 256], normalized_image_sha256=digest(image),
                     review_to_training_source_scale=[1., 1.])
    data.update(reviewed_plan_targets=targets, reviewed_plan_sheets=sheets)
    data["training_image_records"][0].update(source_kind="latest_user_reviewed_plan", sheet_id="sheet-01",
        project_id="review-group-21", split="train", source_sha256=digest(image), tile_origin=[0, 0],
        review_to_training_source_scale=[1., 1.], supervised_record_ids=[targets[0]["record_id"]])
    (dataset / "manifest.json").write_text(json.dumps(data))
    return dataset, base, parent, data


def write(dataset, data):
    (dataset / "manifest.json").write_text(json.dumps(data))


def test_exact_reviewed_dataset_and_partial_subtypes_validate(tmp_path):
    dataset, base, parent, data = fixture(tmp_path)
    assert validate_dataset(dataset, base, parent) == data


@pytest.mark.parametrize("change", ["missing_auth", "production", "wrong_hash", "reindexed",
                                    "missing_allowed", "forced_subtype", "extra_image", "changed_bytes"])
def test_mutated_or_unsupported_training_provenance_fails(tmp_path, change):
    dataset, base, parent, data = fixture(tmp_path)
    if change == "missing_auth":
        data["authorization"]["user_statement"] = ""
    elif change == "production":
        data["authorization"]["production_approval"] = True
    elif change == "wrong_hash":
        data["base_model_sha256"] = "a" * 64
    elif change == "reindexed":
        data["classes"][0]["label"] = "Something else"
    elif change == "missing_allowed":
        data["training_image_records"][0]["allowed_class_ids"] = []
    elif change == "forced_subtype":
        data["training_image_records"][0]["allowed_class_ids"] = [[1]]
    elif change == "extra_image":
        (dataset / "images/train/unreviewed.png").write_bytes(b"unreviewed")
    elif change == "changed_bytes":
        (dataset / "images/train/positive.png").write_bytes(b"changed")
    write(dataset, data)
    with pytest.raises(ValueError):
        validate_dataset(dataset, base, parent)


def test_original_classes_cannot_disappear_from_replay(tmp_path):
    dataset, base, parent, data = fixture(tmp_path)
    label = dataset / "labels/train/positive.txt"
    label.write_text("1 .5 .5 .1 .1\n")
    data["training_image_records"][0].update(label_sha256=digest(label), allowed_class_ids=[[1]])
    write(dataset, data)
    with pytest.raises(ValueError, match="replay was lost"):
        validate_dataset(dataset, base, parent)


def test_uncertain_set_cannot_narrow_while_preserving_representative_and_label_bytes(tmp_path):
    dataset, base, parent, data = fixture(tmp_path)
    data["training_image_records"][0]["allowed_class_ids"] = [[0]]
    write(dataset, data)
    with pytest.raises(ValueError, match="subtype sets"):
        validate_dataset(dataset, base, parent)


def test_reviewed_source_snapshot_cannot_change(tmp_path):
    dataset, base, parent, _ = fixture(tmp_path)
    (dataset / "saved-session-snapshot.json").write_text("{}")
    with pytest.raises(ValueError, match="snapshot"):
        validate_dataset(dataset, base, parent)


def test_conflicting_whole_negative_does_not_convert_positive_to_background(tmp_path):
    dataset, base, parent, data = fixture(tmp_path)
    data["reviewed_background_images"] = [{"image_id": "positive", "sha256": data["training_image_records"][0]["image_sha256"]}]
    write(dataset, data)
    with pytest.raises(ValueError, match="conflicts"):
        validate_dataset(dataset, base, parent)


def test_sampler_cannot_use_unknown_image_or_omit_replay(tmp_path):
    dataset, base, parent, _ = fixture(tmp_path)
    for value in (str(tmp_path / "outside.png"), ""):
        (dataset / "train-images.txt").write_text(value)
        with pytest.raises(ValueError):
            validate_dataset(dataset, base, parent)


def test_training_bound_and_existing_output_fail_before_model_loading(tmp_path):
    dataset, base, parent, _ = fixture(tmp_path)
    with pytest.raises(ValueError):
        train(dataset, base, parent, tmp_path / "run", epochs=21)
    with pytest.raises(ValueError):
        train(dataset, base, parent, tmp_path / "run", negative_sampling_override="unreviewed")
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(FileExistsError):
        train(dataset, base, parent, existing)


def test_full_replay_uses_only_manifested_unchanged_authorized_images(tmp_path):
    import yaml
    dataset, _, _, data = fixture(tmp_path)
    output = tmp_path / "run"
    output.mkdir()
    before = digest(dataset / "manifest.json")
    config, metadata = effective_training_inputs(dataset, data, output, "full_authorized_pool")
    parsed = yaml.safe_load(config.read_text())
    assert Path(parsed["train"]).read_text().splitlines() == [str((dataset / "images/train/positive.png").resolve())]
    assert metadata["effective_training_image_occurrences"] == 1
    assert metadata["effective_unique_training_images"] == 1
    assert metadata["effective_training_config_sha256"] == digest(config)
    assert digest(dataset / "manifest.json") == before
    assert parsed["names"] == {0: "Normal", 1: "UPS"}
    with pytest.raises(ValueError):
        effective_training_inputs(dataset, data, output, "unreviewed_background")


def test_retention_weighting_repeats_only_existing_parent_positives(tmp_path):
    dataset, _, _, data = fixture(tmp_path)
    data["training_image_records"].append(dict(image_id="parent", source_kind="parent_retention_replay",
                                             allowed_class_ids=[[0]]))
    (dataset / "images/train/parent.png").write_bytes((dataset / "images/train/positive.png").read_bytes())
    output = tmp_path / "weighted-run"
    output.mkdir()
    config, metadata = effective_training_inputs(dataset, data, output, "full_authorized_pool", 0, 3)
    import yaml
    paths = Path(yaml.safe_load(config.read_text())["train"]).read_text().splitlines()
    assert paths.count(str((dataset / "images/train/parent.png").resolve())) == 3
    assert paths.count(str((dataset / "images/train/positive.png").resolve())) == 1
    assert metadata["effective_unique_training_images"] == 2
    assert metadata["effective_training_image_occurrences"] == 4
    for cls, factor in ((1,3), (0,5), (None,3)):
        with pytest.raises(ValueError):
            effective_training_inputs(dataset, data, output, "full_authorized_pool", cls, factor)
