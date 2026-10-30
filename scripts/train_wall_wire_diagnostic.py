"""Bounded source-verified wall/wiring patch check; never a production detector.

Only explicit, source-aligned trace classes are supervised. Surrounding pixels
are context, not background/segmentation labels. Outputs remain separate from
the application model selection and from canonical project geometry.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import time

import cv2
import numpy as np


CLASS_IDS = {"standard_wall": 1, "explicit_wiring_trace": 4}
PREPROCESSING = {
    "shape": [48, 128], "along_pixels": 128,
    "along_cap": "within reviewed longest segment at midpoint",
    "normal_pixels": [-20, 20], "orientation": "lexicographically ordered endpoints",
    "interpolation": "linear", "both_classes_identical": True,
}
PARAMETERS = {"trees": 64, "max_depth": 12, "min_samples": 1,
              "active_variables": 20, "seed": 92013, "threads": 1,
              "exact_training_repetitions": 4}
ROOT = Path(__file__).resolve().parents[1]


def verify_provenance(data, provenance_root):
    """Verify existing reconciliation evidence; this does not issue approval."""
    root = Path(provenance_root).resolve()
    hashes = data.get("input_hashes")
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError("Missing reconciliation evidence")
    inputs = {}
    for relative, identity in hashes.items():
        if not isinstance(relative, str):
            raise ValueError("Invalid evidence path")
        path = (root / Path(relative.replace("\\", "/"))).resolve()
        if not path.is_relative_to(root) or not path.is_file() or digest(path) != identity:
            raise ValueError("Evidence path/hash mismatch")
        evidence = json.loads(path.read_text(encoding="utf-8"))
        schema = evidence.get("schema")
        if schema in inputs:
            raise ValueError("Duplicate reconciliation evidence")
        inputs[schema] = (evidence, identity)
    required = ("ved-reviewed-positive-wall-audit-v1", "ved-explicit-wiring-negative-inventory-v1",
                "ved-assistant-wire-strip-quality-proposals-v1")
    if set(inputs) != set(required):
        raise ValueError("Incomplete reconciliation evidence")
    wall, wall_hash = inputs[required[0]]
    wiring, wire_hash = inputs[required[1]]
    review, _ = inputs[required[2]]
    if (wiring.get("wall_audit_sha256") != wall_hash or review.get("inventory_sha256") != wire_hash
            or review.get("separate_human_approval_claimed") is not False):
        raise ValueError("Reconciliation lineage mismatch")
    for evidence in (wall, wiring):
        if (evidence.get("export_sha256") != data["export_sha256"]
                or evidence.get("authorization_sha256") != data["authorization_sha256"]):
            raise ValueError("Authorization/export lineage mismatch")
    clear_wires = {row["annotation_id"] for row in review["records"]
                   if row.get("crop_quality_proposal") == "supports_explicit_wiring_strip_diagnostic"}
    authorities = {}
    for label, evidence in ((1, wall), (4, wiring)):
        for row in evidence["records"]:
            if label == 1 and row.get("wall_type") != "standard":
                continue
            if label == 4 and (row.get("status") != "eligible_explicit_wiring_geometry_pending_visual_check"
                               or row["annotation_id"] not in clear_wires):
                continue
            key = (label, row["annotation_id"])
            if key in authorities:
                raise ValueError("Duplicate source authority")
            authorities[key] = row
    return authorities


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sample_strip(gray, segment):
    """Canonical fixed source-pixel window, identical for either trace class."""
    if not isinstance(gray, np.ndarray) or gray.ndim != 2 or gray.dtype != np.uint8:
        raise ValueError("Source must be uint8 grayscale")
    try:
        values = np.asarray(segment, dtype=object)
        if values.shape != (2, 2) or any(isinstance(v, (bool, np.bool_)) for v in values.flat):
            raise ValueError("Invalid source segment")
        points = np.asarray(segment, dtype=float)
    except (TypeError, ValueError):
        raise ValueError("Invalid source segment") from None
    if points.shape != (2, 2) or not np.isfinite(points).all():
        raise ValueError("Invalid source segment")
    height, width = gray.shape
    if np.any(points < 0) or np.any(points[:, 0] >= width) or np.any(points[:, 1] >= height):
        raise ValueError("Source segment outside image")
    a, b = points
    if tuple(b) < tuple(a):
        a, b = b, a
    length = float(np.linalg.norm(b - a))
    if length <= 0:
        raise ValueError("Zero length source segment")
    direction = (b - a) / length
    normal = np.array([-direction[1], direction[0]])
    midpoint = (a + b) / 2
    halfspan = min(64., length / 2)
    along = np.linspace(-halfspan, halfspan, 128, dtype=np.float32)
    across = np.linspace(-20., 20., 48, dtype=np.float32)
    coordinates = (midpoint[None, None, :] + along[None, :, None] * direction
                   + across[:, None, None] * normal)
    if (np.any(coordinates[:, :, 0] < 0) or np.any(coordinates[:, :, 0] >= width)
            or np.any(coordinates[:, :, 1] < 0) or np.any(coordinates[:, :, 1] >= height)):
        raise ValueError("Source context outside image")
    crop = cv2.remap(gray, coordinates[:, :, 0].astype(np.float32),
                     coordinates[:, :, 1].astype(np.float32), cv2.INTER_LINEAR)
    quad = coordinates[[0, 0, -1, -1], [0, -1, -1, 0]].tolist()
    return crop, quad


def pixel_features(crop):
    if not isinstance(crop, np.ndarray) or crop.shape != (48, 128) or crop.dtype != np.uint8:
        raise ValueError("Expected 48x128 uint8 crop")
    # No label, source/page/group identity or annotation metadata enters features.
    return (cv2.resize(crop, (32, 12), interpolation=cv2.INTER_AREA)
            .astype(np.float32) / 255).reshape(-1)


def load_dataset(manifest_path, source_root, provenance_root=ROOT):
    manifest_path, source_root = Path(manifest_path), Path(source_root)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (data.get("schema") != "ved-wall-wiring-identical-patch-inspection-v1"
            or data.get("class_ids") != CLASS_IDS or data.get("preprocessing") != PREPROCESSING
            or data.get("authorization_origin") != "existing_user_attestation"
            or data.get("no_unlabeled_background_truth") is not True):
        raise ValueError("Unsupported explicit-trace diagnostic manifest")
    for key in ("export_sha256", "authorization_sha256"):
        if not isinstance(data.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", data[key]):
            raise ValueError("Missing authorization/export identity")
    authorities = verify_provenance(data, provenance_root)
    records = data.get("records")
    if not isinstance(records, list) or not records or len(records) > 4096:
        raise ValueError("Invalid bounded record collection")
    images, identities, features, labels = {}, set(), [], []
    source_components, feature_labels, group_components = {}, {}, {}
    for row in records:
        if (row.get("assistant_crop_quality") != "supports_explicit_class_patch_diagnostic"
                or row.get("review_state") not in ("corrected", "manually_added", "user_reviewed")
                or row.get("source_coordinate_supervision") != "explicit_reviewed_trace_class_only"
                or type(row.get("class_id")) is not int
                or CLASS_IDS.get(row.get("class_name")) != row.get("class_id")
                or row.get("original_annotation_unchanged") is not True):
            raise ValueError("Unresolved/excluded or unsupported trace label")
        identity = row.get("annotation_id")
        component = row.get("split_component")
        sheet = row.get("sheet_id")
        if (not isinstance(identity, str) or not identity or identity in identities
                or not isinstance(component, str) or not component
                or not isinstance(sheet, str) or not re.fullmatch(r"sheet-[0-9]+", sheet)):
            raise ValueError("Invalid/duplicate trace identity")
        identities.add(identity)
        group = row.get("group")
        if type(group) is not int or not 1 <= group <= 22:
            raise ValueError("Outside groups1-22 authorization")
        related = "groups1_6" if group <= 6 else "groups8_20" if 8 <= group <= 20 else group
        if related in group_components and group_components[related] != component:
            raise ValueError("Related floors/groups cross split components")
        group_components[related] = component
        authority = authorities.get((row["class_id"], identity))
        if authority is None or any(authority.get(key) != row.get(key)
                                    for key in ("sheet_id", "source_sha256", "group", "review_state")):
            raise ValueError("Trace not in reconciled source evidence")
        points = np.asarray(authority.get("points") if row["class_id"] == 1
                            else authority["geometry"]["coordinates"], dtype=float)
        index = int(np.argmax(np.linalg.norm(np.diff(points, axis=0), axis=1)))
        a, b = points[index:index + 2]
        expected_segment = [a.tolist(), b.tolist()] if tuple(a) <= tuple(b) else [b.tolist(), a.tolist()]
        if expected_segment != row.get("source_segment"):
            raise ValueError("Trace segment changed from reconciled source")
        source_hash = row.get("source_sha256")
        if source_hash in source_components and source_components[source_hash] != component:
            raise ValueError("Same source crosses split components")
        source_components[source_hash] = component
        if sheet not in images:
            source = source_root / (sheet + ".jpg")
            if digest(source) != source_hash or data.get("source_hashes", {}).get(sheet) != source_hash:
                raise ValueError("Source hash mismatch")
            gray = cv2.imread(str(source), cv2.IMREAD_GRAYSCALE)
            if gray is None:
                raise ValueError("Unreadable source image")
            images[sheet] = (gray, source_hash)
        gray, actual_hash = images[sheet]
        if actual_hash != source_hash or [gray.shape[1], gray.shape[0]] != row.get("source_dimensions"):
            raise ValueError("Source identity/dimensions mismatch")
        name = row.get("crop_file")
        if not isinstance(name, str) or Path(name).name != name or not name.endswith(".png"):
            raise ValueError("Invalid crop filename")
        crop_path = manifest_path.parent / name
        if digest(crop_path) != row.get("crop_sha256"):
            raise ValueError("Crop hash mismatch")
        cached = cv2.imread(str(crop_path), cv2.IMREAD_GRAYSCALE)
        reconstructed, quad = sample_strip(gray, row.get("source_segment"))
        if (cached is None or not np.array_equal(cached, reconstructed)
                or np.asarray(row.get("sampling_quadrilateral")).shape != (4, 2)
                or not np.allclose(quad, row["sampling_quadrilateral"], atol=1e-6, rtol=0)):
            raise ValueError("Crop/source pairing or coordinate mismatch")
        feature = pixel_features(reconstructed)
        feature_hash = hashlib.sha256(feature.tobytes()).hexdigest()
        if feature_hash in feature_labels:
            raise ValueError("Duplicate or conflicting crop features")
        feature_labels[feature_hash] = row["class_id"]
        features.append(feature)
        labels.append(row["class_id"])
    if set(labels) != set(CLASS_IDS.values()):
        raise ValueError("Both explicit classes required")
    return data, np.stack(features), np.asarray(labels, dtype=np.int32)


def component_partition(records, training_components):
    selected = set(training_components)
    if not selected:
        raise ValueError("Training component required")
    train = [i for i, row in enumerate(records) if row["split_component"] in selected]
    test = [i for i, row in enumerate(records) if row["split_component"] not in selected]
    if not train:
        raise ValueError("Empty training component")
    train_sources = {records[i]["source_sha256"] for i in train}
    test_sources = {records[i]["source_sha256"] for i in test}
    if train_sources & test_sources:
        raise ValueError("Source leakage between components")
    return train, test


def fit_model(features, labels):
    if set(np.asarray(labels).tolist()) != set(CLASS_IDS.values()):
        raise ValueError("Both classes required in training")
    cv2.setNumThreads(PARAMETERS["threads"])
    cv2.setRNGSeed(PARAMETERS["seed"])
    model = cv2.ml.RTrees_create()
    model.setMaxDepth(PARAMETERS["max_depth"])
    model.setMinSampleCount(PARAMETERS["min_samples"])
    model.setUseSurrogates(False)
    model.setMaxCategories(2)
    model.setActiveVarCount(PARAMETERS["active_variables"])
    model.setTermCriteria((cv2.TERM_CRITERIA_MAX_ITER, PARAMETERS["trees"], 0))
    repetitions = PARAMETERS["exact_training_repetitions"]
    if not model.train(np.repeat(features, repetitions, axis=0), cv2.ml.ROW_SAMPLE,
                       np.repeat(labels, repetitions, axis=0)):
        raise RuntimeError("RTrees fitting failed")
    return model


def prediction_report(model, features, labels, records):
    _, raw = model.predict(features)
    predicted = raw.reshape(-1).astype(np.int32)
    if not np.array_equal(raw.reshape(-1), predicted) or not set(predicted.tolist()) <= {1, 4}:
        raise RuntimeError("Unexpected decoded class index")
    votes = model.getVotes(features, 0)
    if set(votes[0].tolist()) != {1, 4} or votes.shape != (len(records) + 1, 2):
        raise RuntimeError("Unexpected vote class mapping")
    class_order, names = [1, 4], {value: key for key, value in CLASS_IDS.items()}
    confusion = [[int(np.sum((labels == expected) & (predicted == actual)))
                  for actual in class_order] for expected in class_order]
    details = [{"annotation_id": row["annotation_id"], "sheet_id": row["sheet_id"],
                "source_sha256": row["source_sha256"], "split_component": row["split_component"],
                "crop_file": row["crop_file"], "expected_class_id": int(labels[i]),
                "raw_prediction": float(raw[i, 0]), "normalized_prediction": names[int(predicted[i])],
                "tree_vote_class_ids": votes[0].tolist(), "raw_tree_votes": votes[i + 1].tolist(),
                "match": bool(labels[i] == predicted[i]),
                "feature_sha256": hashlib.sha256(features[i].tobytes()).hexdigest()}
               for i, row in enumerate(records)]
    return {"matches": int(np.sum(labels == predicted)), "unique_examples": len(records),
            "class_order": class_order, "confusion_expected_rows_predicted_columns": confusion,
            "baseline_constant_wall_matches": int(np.sum(labels == 1)), "predictions": details,
            "tree_votes_are_not_calibrated_confidence": True}


def run(manifest_path, source_root, output, provenance_root=ROOT):
    data, features, labels = load_dataset(manifest_path, source_root, provenance_root)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    records = data["records"]
    components = sorted({row["split_component"] for row in records})
    experiments = [("memorization", list(range(len(records))), [])]
    for component in components:
        train, test = component_partition(records, [component])
        if set(labels[train].tolist()) == {1, 4}:
            experiments.append(("component_" + component, train, test))
    results = []
    for name, train, test in experiments:
        started = time.perf_counter()
        model = fit_model(features[train], labels[train])
        elapsed = time.perf_counter() - started
        checkpoint = output / (name + ".xml")
        model.save(str(checkpoint))
        loaded = cv2.ml.RTrees_load(str(checkpoint))
        np.testing.assert_array_equal(model.predict(features)[1], loaded.predict(features)[1])
        result = {"name": name, "checkpoint_file": checkpoint.name,
                  "checkpoint_sha256": digest(checkpoint), "fit_seconds": elapsed,
                  "checkpoint_reload_predictions_identical": True,
                  "training_components": sorted({records[i]["split_component"] for i in train}),
                  "training": prediction_report(loaded, features[train], labels[train],
                                                [records[i] for i in train]),
                  "repeated_training_rows": len(train) * PARAMETERS["exact_training_repetitions"],
                  "project_generalization_verified": False}
        if test:
            result["exploratory_component_transfer"] = prediction_report(
                loaded, features[test], labels[test], [records[i] for i in test])
        results.append(result)
    unchanged = all(digest(Path(source_root) / (sheet + ".jpg")) == identity
                    for sheet, identity in data["source_hashes"].items())
    if not unchanged:
        raise RuntimeError("Source changed during experiment")
    report = {"schema": "ved-wall-wiring-patch-diagnostic-v1", "model": "OpenCV RTrees",
              "training_script_sha256": digest(__file__),
              "opencv_version": cv2.__version__, "parameters": PARAMETERS,
              "manifest_sha256": digest(manifest_path), "export_sha256": data["export_sha256"],
              "authorization_sha256": data["authorization_sha256"], "class_ids": CLASS_IDS,
              "preprocessing": PREPROCESSING,
              "features": "384 grayscale pixels, float32/255; no identity/label metadata",
              "class_counts": dict(Counter(row["class_name"] for row in records)),
              "excluded_windows_preserved": data.get("excluded_current_windows"),
              "experiments": results, "originals_unchanged": unchanged,
              "model_activated": False, "precision": None, "localization_recall": None,
              "limitations": ["Memorization is only a pipeline check, not detection quality.",
                              "Component transfer is exploratory; project independence is unverified.",
                              "Group7 has no wall labels; groups8-20 have only one wiring patch.",
                              "Only explicit reviewed patch classes; no complete-page background truth.",
                              "No wall width/height/connectivity or full-page localization learned.",
                              "Exact repetitions are not independent real-world examples.",
                              "No product configuration, model download or production activation."]}
    (output / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.manifest, args.source_root, args.output)
    print(json.dumps({"class_counts": report["class_counts"], "originals_unchanged": report["originals_unchanged"],
                      "model_activated": False, "experiments": [
                          {"name": row["name"], "training_matches": row["training"]["matches"],
                           "training_examples": row["training"]["unique_examples"],
                           "transfer_matches": row.get("exploratory_component_transfer", {}).get("matches"),
                           "transfer_examples": row.get("exploratory_component_transfer", {}).get("unique_examples")}
                          for row in report["experiments"]]}))


if __name__ == "__main__":
    main()
