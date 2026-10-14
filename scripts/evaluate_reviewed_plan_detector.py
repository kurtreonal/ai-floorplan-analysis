"""Offline paired detector evidence; partial labels never imply full precision."""
import argparse
from collections import Counter
from contextlib import ExitStack, closing
from hashlib import sha256
import json
from io import BytesIO
import os
from pathlib import Path
import re
import sys
import time
from unittest.mock import patch

os.environ["YOLO_AUTOINSTALL"] = "false"
os.environ["YOLO_OFFLINE"] = "true"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.ai.floor_plan_interpretation import experimental_symbol_detector as shared
from app.ai.floor_plan_interpretation import multiclass_symbol_detector as multiclass
from app.ai.floor_plan_interpretation.legend_equivalence import model_class_groups


def digest(path):
    with Path(path).open("rb") as stream:
        return __import__("hashlib").file_digest(stream, "sha256").hexdigest()


def transform_targets(rows, scales):
    return [{**r, "bbox": [v * scales[i % 2] for i, v in enumerate(r["source_box"])]} for r in rows]


def center_inside(box, region):
    x, y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return region[0] <= x <= region[2] and region[1] <= y <= region[3]


def match_reviewed(targets, predictions, iou=.5):
    """Maximum-cardinality allowed-class matches, then explicit confusions."""
    edges = {i: sorted((j for j, p in enumerate(predictions)
                        if p["class_id"] in t["allowed_class_ids"]
                        and shared._iou(t["bbox"], p["bbox"]) >= iou),
                       key=lambda j: -shared._iou(t["bbox"], predictions[j]["bbox"]))
             for i, t in enumerate(targets)}
    assigned = {}

    def assign(i, seen):
        for j in edges[i]:
            if j in seen:
                continue
            seen.add(j)
            if j not in assigned or assign(assigned[j], seen):
                assigned[j] = i
                return True
        return False

    for i in range(len(targets)):
        assign(i, set())
    matches = [{"target_index": i, "prediction_index": j,
                "record_id": targets[i].get("record_id"), "class_id": predictions[j]["class_id"],
                "iou": shared._iou(targets[i]["bbox"], predictions[j]["bbox"])} for j, i in sorted(assigned.items())]
    matched_targets = set(assigned.values())
    confusions = []
    available = set(range(len(predictions))) - set(assigned)
    for i, target in enumerate(targets):
        if i in matched_targets:
            continue
        candidates = [j for j in available if shared._iou(target["bbox"], predictions[j]["bbox"]) >= iou]
        if candidates:
            j = max(candidates, key=lambda j: shared._iou(target["bbox"], predictions[j]["bbox"]))
            available.remove(j)
            confusions.append(dict(target_index=i, prediction_index=j,
                expected_allowed=target["allowed_class_ids"], predicted=predictions[j]["class_id"],
                record_id=target.get("record_id"), iou=shared._iou(target["bbox"], predictions[j]["bbox"])))
    per_class = []
    for allowed in sorted({tuple(t["allowed_class_ids"]) for t in targets}):
        members = {i for i, t in enumerate(targets) if tuple(t["allowed_class_ids"]) == allowed}
        per_class.append(dict(allowed_class_ids=list(allowed), reviewed_positives=len(members),
                              matched=len(members & matched_targets), missed=len(members - matched_targets)))
    return dict(reviewed_positives=len(targets), matched=len(matches), matches=matches,
                misses=[i for i in range(len(targets)) if i not in matched_targets], confusions=confusions,
                unmatched_proposals=sorted(set(range(len(predictions))) - set(assigned)),
                per_class=per_class, precision=None, precision_reason="partial reviewed-positive coverage, not exhaustive background truth")


def locate_with_trace(rgb, model, classes, *, catalog=None, locate_impl=None):
    raw = []
    complete_fused = []
    original = shared.fuse

    def capture(rows, **kwargs):
        raw.extend(dict(r) for r in rows)
        result = original(rows, **kwargs)
        complete_fused.extend(result)
        return result

    with patch.object(shared, "fuse", side_effect=capture):
        fused, truncated = (locate_impl or shared.locate)(rgb, catalog=catalog or dict(
            classes=classes, threshold=.50, model=model, class_groups=model_class_groups(classes), box_fusion=True))
    return fused, truncated, raw, complete_fused


def observation_key(row):
    return (row["class_id"], round(row["score"], 9), tuple(round(v, 8) for v in row["bbox"]),
            tuple(row.get("tile_origin", ())))


def restore_trace_row(row, offset):
    result = {**row, "bbox": [v + offset[i % 2] for i, v in enumerate(row["bbox"])]}
    for key in ("localization_observations", "equivalent_observations"):
        if row.get(key):
            result[key] = [restore_trace_row(r, offset) for r in row[key]]
    return result


def fusion_rejections(raw, fused, truncated=False):
    observed = set()
    aliases = set()
    for row in fused:
        if row.get("localization_observations"):
            observed.update(observation_key(r) for r in row["localization_observations"])
        else:
            observed.add(observation_key(row))
        aliases.update(observation_key(r) for r in row.get("equivalent_observations", ()))
    rejected = []
    for row in raw:
        key = observation_key(row)
        if key in observed:
            continue
        reason = ("equivalent_class_alias_preserved_not_separate_device" if key in aliases
                  else "covered_internal_tile_seam_fragment" if any(shared._covered_tile_fragment(row, r) for r in raw)
                  else "cross_tile_nested_or_same_class_duplicate_suppression")
        if truncated and not any(shared._iou(row["bbox"], r["bbox"]) >= .3 for r in fused):
            reason = "candidate_cap_or_duplicate_suppression"
        rejected.append(dict(row, rejection_reason=reason))
    return rejected


def run_scope(rgb, region, model, classes, dataset_hash, pdf_index=None, *, reviewed_candidate=False):
    """Use actual processing ownership; injection is local to this subprocess."""
    from app.services.interpretation_processing_service import _interpret_cv_scope
    trace = {}
    serving_locate, primitive_locate = multiclass.locate, shared.locate

    def locate(image):
        passes = []

        def capture_pass(pixels, *, catalog):
            fused, truncated, raw, complete = locate_with_trace(pixels, model, classes,
                catalog=catalog, locate_impl=primitive_locate)
            passes.append(dict(raw=raw, fused=list(fused), uncapped_fused_count=len(complete),
                truncated=truncated, tile_size=catalog.get("tile_size", shared.TILE_SIZE),
                tile_stride=catalog.get("tile_stride", shared.TILE_STRIDE)))
            return fused, truncated

        with patch.object(shared, "locate", side_effect=capture_pass):
            fused, truncated = serving_locate(image)
        if not passes:
            raise ValueError("Serving localization policy produced no captured inference pass")
        trace.update(**passes[-1], localization_passes=passes)
        return fused, truncated

    with patch.object(multiclass, "locate", side_effect=locate), \
            patch.object(multiclass, "_model", return_value=model), \
            patch.object(multiclass, "verify_artifacts", return_value=classes), \
            patch.object(multiclass, "TRAINING_DATASET_SHA256", dataset_hash):
        payload = _interpret_cv_scope(rgb, region=region, experimental=False, trained=True,
                                      general=True, linked=False, pdf_index=pdf_index)
    if reviewed_candidate:
        from app.ai.floor_plan_interpretation.candidate import CandidateWarning
        payload = payload.model_copy(update={"warnings": tuple(w for w in payload.warnings
            if w.code != "experimental_eighty_entry_checkpoint") + (CandidateWarning(
                code="reviewed_candidate_offline_comparison", severity="warning",
                message="Offline reviewed-source multi-class candidate under the baseline localization policy. "
                        "Not an activated or approved release. Partial reviewed positives do not establish full-page precision."),)})
        payload = type(payload).model_validate(payload.model_dump())
    offset = (region.x, region.y) if region is not None else (0, 0)
    for key in ("raw", "fused"):
        trace[key] = [restore_trace_row(p, offset) for p in trace[key]]
    for inference_pass in trace["localization_passes"]:
        for key in ("raw", "fused"):
            inference_pass[key] = [restore_trace_row(p, offset) for p in inference_pass[key]]
    retained = []
    for symbol in payload.symbols.items:
        if symbol.training_legend is None:
            continue
        box = symbol.bounds
        retained.append(dict(bbox=[box.x, box.y, box.x + box.width, box.y + box.height],
                             class_id=symbol.training_legend.model_class_id, symbol_id=symbol.id))
    trace["retained"] = retained
    rejected = fusion_rejections(trace["raw"], trace["fused"], trace["truncated"])
    for p in trace["fused"]:
        if not any(shared._iou(p["bbox"], r["bbox"]) >= .3 for r in retained):
            rejected.append(dict(p, rejection_reason="plan_region_or_shared_postprocessing"))
    trace["rejected"] = rejected
    trace["plan_regions"] = [[r.bounds.x, r.bounds.y, r.bounds.x + r.bounds.width,
                              r.bounds.y + r.bounds.height] for r in payload.regions if r.kind == "plan_region"]
    trace["walls_count"] = len(payload.walls.items)
    trace["wire_paths_count"] = len(payload.observed_routes.segments)
    trace["device_connections_count"] = len(payload.observed_routes.connections)
    trace["candidate_payload"] = payload.model_dump(mode="json")
    trace["wall_wire_status"] = "shared raster/native processing; detector training is not itself a wall/wire fix"
    return trace


def overlay(image, predictions, targets, classes, region, title):
    a, b, c, d = map(int, region)
    canvas = image.crop((a, b, c, d)).resize(((c - a) * 2, (d - b) * 2))
    header = Image.new("RGB", (canvas.width, canvas.height + 50), "white")
    header.paste(canvas, (0, 50))
    pen = ImageDraw.Draw(header)
    try:
        font = ImageFont.truetype("arial.ttf", 17)
    except OSError:
        font = ImageFont.load_default()
    pen.text((8, 8), title, fill="black", font=font)
    for t in targets:
        if center_inside(t["bbox"], region):
            box = [2 * (v - (a if i % 2 == 0 else b)) + (50 if i % 2 else 0) for i, v in enumerate(t["bbox"])]
            pen.rectangle(box, outline="#009a58", width=2)
    for p in predictions:
        if not center_inside(p["bbox"], region):
            continue
        box = [2 * (v - (a if i % 2 == 0 else b)) + (50 if i % 2 else 0) for i, v in enumerate(p["bbox"])]
        pen.rectangle(box, outline="#d64c20", width=2)
        name = classes[p["class_id"]][0]
        label = f"{p['class_id']}: {name[:42]}"
        pen.text((box[0], max(50, box[1] - 17)), label, fill="#0b306a", font=font,
                 stroke_width=2, stroke_fill="white")
    return header


def geometry_overlay(image, payload, classes, region, mode, title):
    """Draw only shared candidate geometry, never reviewed boxes as predictions."""
    a, b, c, d = map(int, region)
    canvas = image.crop((a, b, c, d)).resize(((c-a)*2, (d-b)*2))
    header = Image.new("RGB", (canvas.width, canvas.height + 50), "white")
    header.paste(canvas, (0, 50))
    pen = ImageDraw.Draw(header)
    pen.text((8, 8), title, fill="black")

    def point(p):
        return (2*(p["x"]-a), 2*(p["y"]-b)+50)

    if mode in ("walls", "combined"):
        for wall in payload["walls"]["items"]:
            pen.line([point(wall["start"]), point(wall["end"])], fill="#12467a", width=4)
    if mode in ("wiring", "combined"):
        for route in payload["observed_routes"]["segments"]:
            pen.line([point(p) for p in route["points"]], fill="#00a6bc", width=3)
        for contact in payload["observed_routes"]["connections"]:
            if contact.get("path_anchor") and contact.get("device_anchor"):
                pen.line([point(contact["path_anchor"]), point(contact["device_anchor"])],
                         fill="#b73abd", width=3)
    if mode in ("wiring", "combined"):
        for symbol in payload["symbols"]["items"]:
            bounds = symbol.get("bounds")
            legend = symbol.get("training_legend")
            if not bounds or not legend:
                continue
            box = [2*(bounds["x"]-a), 2*(bounds["y"]-b)+50,
                   2*(bounds["x"]+bounds["width"]-a), 2*(bounds["y"]+bounds["height"]-b)+50]
            pen.rectangle(box, outline="#d64c20", width=2)
            pen.text((box[0], max(50, box[1]-12)), str(legend["model_class_id"]), fill="#7a250b")
    return header


def scopes_for_sheet(sheet, rgb, pdf_sources):
    from app.ai.floor_plan_interpretation.pdf_evidence import extract_pdf_evidence, PrimitiveIndex
    from app.ai.floor_plan_interpretation.pdf_views import propose_pdf_views
    path = pdf_sources.get(sheet.get("original_source_sha256"))
    if path:
        import pypdfium2 as pdfium
        with pdfium.PdfDocument(str(path)) as document:
            number = sheet.get("pdf_page")
            if number is None and len(document) == 1:
                number = 1
        if number is None:
            raise ValueError("PDF page identity is missing; do not guess a multi-page source")
        evidence = extract_pdf_evidence(path, page_number=number, width=rgb.shape[1], height=rgb.shape[0])
        views = propose_pdf_views(evidence)
        if views:
            return [(v["label"], v["region"]) for v in views], "native_pdf_caption_and_image_bank_views", PrimitiveIndex(evidence)
        return [("Raster drawing", None)], "native_pdf_without_auto_floor_scopes", PrimitiveIndex(evidence)
    return [("Raster drawing", None)], "existing_raster_cv_plan_region", None


def image_for_sheet(dataset, sheet, pdf_sources, pdf_dpi=300, review_raster_only=False, overrides=None):
    source = dataset / "sources" / f"{sheet['sheet_id']}-normalized.png"
    if sheet.get("normalized_image_sha256") and digest(source) != sheet["normalized_image_sha256"]:
        raise ValueError("Normalized evaluation source changed")
    with Image.open(source) as opened:
        review_image = opened.convert("RGB")
    expected_size = review_image.size
    path = pdf_sources.get(sheet.get("original_source_sha256"))
    override = (overrides or {}).get(sheet["sheet_id"])
    if override is not None:
        with Image.open(override) as opened:
            cached = opened.convert("RGB")
        review_image.close()
        if cached.size != expected_size or not sheet.get("original_source_sha256"):
            cached.close()
            raise ValueError("Cached system pixels do not match declared source plane")
        return cached, dict(mode="explicit_cached_system_source_pixels", source_image_sha256=digest(override),
                            declared_original_sha256=sheet["original_source_sha256"],
                            source_binding="caller-supplied original artifact identity; no guessed source lookup",
                            pixel_sha256=sha256(cached.tobytes()).hexdigest())
    if path is None or review_raster_only:
        return review_image, dict(mode="review_raster_normalized", source_image_sha256=digest(source))
    import pypdfium2 as pdfium
    from app.services.pdf_conversion import _encode_pdf_page
    from app.services.image_normalization import _resize_if_required
    number = sheet.get("pdf_page")
    if number is None:
        with pdfium.PdfDocument(str(path)) as document:
            if len(document) == 1:
                number = 1
    if number is None:
        raise ValueError("Exact native PDF page identity required")
    rendered, _, _ = _encode_pdf_page(path, page_number=number, dpi=pdf_dpi, max_pixel_count=60_000_000)
    with Image.open(BytesIO(rendered)) as opened:
        native = opened.convert("RGB")
    native, _ = _resize_if_required(native, maximum_dimension=4096)
    review_image.close()
    if native.size != expected_size:
        native.close()
        raise ValueError("Native PDF and reviewed source frames differ")
    return native, dict(mode="native_pdf_shared_render_and_normalization", original_sha256=digest(path),
                        pdf_page=number, render_dpi=pdf_dpi, pixel_sha256=sha256(native.tobytes()).hexdigest())


def retention_windows(dataset, data, model, class_count):
    """All old manifested context labels, plus unique reviewed-ID coverage."""
    old = [r for r in data["training_image_records"] if r.get("source_kind") != "latest_user_reviewed_plan"]
    window_targets = window_matches = 0
    source_ids = set()
    matched_ids = set()
    by_class = Counter()
    matched_class = Counter()
    confusions = Counter()
    old_lookup = {r["record_id"]: r for r in data.get("images", [])}
    negative_results = []
    explicit_negative = {r["image_id"] for r in data.get("reviewed_background_images", [])}
    start = time.perf_counter()
    for offset in range(0, len(old), 8):
        batch = old[offset:offset + 8]
        with ExitStack() as stack:
            images = [stack.enter_context(closing(Image.open(dataset / "images/train" / f"{r['image_id']}.png").convert("RGB"))) for r in batch]
            results = model.predict(images, imgsz=320, conf=.50, max_det=100, batch=8,
                                    device="cpu", verbose=False)
            for row, image, result in zip(batch, images, results):
                predictions = [dict(bbox=list(map(float, b.xyxy[0].tolist())), class_id=int(b.cls[0]),
                                    score=float(b.conf[0])) for b in result.boxes]
                if row["image_id"] in explicit_negative:
                    negative_results.append(dict(image_id=row["image_id"], proposals=len(predictions),
                                                 predictions=predictions))
                targets = []
                metadata = old_lookup.get(row["image_id"], {}).get("supervised_records", [])
                lines = (dataset / "labels/train" / f"{row['image_id']}.txt").read_text().splitlines()
                for index, line in enumerate(lines):
                    if not line.strip():
                        continue
                    cls, x, y, width, height = map(float, line.split())
                    if cls >= class_count:
                        continue
                    record = metadata[index].get("record_id") if len(metadata) == len(lines) and metadata[index].get("class_id") == int(cls) else None
                    if record:
                        source_ids.add(record)
                    targets.append(dict(record_id=record, allowed_class_ids=[int(cls)],
                        bbox=[(x-width/2)*image.width, (y-height/2)*image.height,
                              (x+width/2)*image.width, (y+height/2)*image.height]))
                    by_class[int(cls)] += 1
                report = match_reviewed(targets, predictions)
                for confusion in report["confusions"]:
                    confusions[(confusion["expected_allowed"][0], confusion["predicted"])] += 1
                window_targets += len(targets)
                window_matches += report["matched"]
                for match in report["matches"]:
                    matched_class[match["class_id"]] += 1
                    if match["record_id"]:
                        matched_ids.add(match["record_id"])
    expected = {r["record_id"] for r in data.get("reviewed_targets", [])}
    return dict(window_positive_occurrences=window_targets, matched_occurrences=window_matches,
                per_class=[dict(class_id=i, positives=by_class[i], matched=matched_class[i]) for i in range(class_count)],
                prior_reviewed_targets=len(expected), reviewed_target_ids_with_row_verified_windows=len(expected & source_ids),
                reviewed_target_ids_matched=len(expected & matched_ids),
                reviewed_target_ids_without_verifiable_window=sorted(expected - source_ids),
                explicit_negative_controls=negative_results, elapsed_seconds=time.perf_counter() - start,
                class_confusions=[dict(expected=a, predicted=b, occurrences=n)
                    for (a,b), n in sorted(confusions.items())],
                scope="old training/source/reference replay, not independent accuracy; duplicate windows are not new examples")


def evaluate(dataset, baseline, candidate, output, *, pdf_paths=(), skip_retention=False,
             pdf_dpi=300, review_raster_only=False, source_overrides=None, retention_only=False):
    if output.exists():
        raise FileExistsError("Evaluation outputs are immutable")
    if retention_only and skip_retention:
        raise ValueError("Retention-only evaluation cannot skip retention")
    data = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    if data.get("kind") != "ved_reviewed_multiclass_training_v1":
        raise ValueError("Reviewed versioned dataset required")
    pdf_sources = {digest(p): p for p in pdf_paths}
    if not set(source_overrides or {}) <= {s["sheet_id"] for s in data["reviewed_plan_sheets"]}:
        raise ValueError("Source override references an unknown reviewed sheet")
    output.mkdir(parents=True)
    import torch
    from ultralytics import YOLO
    torch.set_num_threads(8)
    report = dict(dataset_sha256=digest(dataset / "manifest.json"), models={},
                  settings=dict(confidence=.50, matching_iou=.50, native_tile=256, stride=192,
                                model_input=320, dual_phase=True, box_fusion=True, candidate_cap=200),
                  evaluation_kind="training_source_reviewed_positive_performance_not_unseen_accuracy", precision=None)
    for model_name, weights in (("baseline", baseline), ("candidate", candidate)):
        model = YOLO(str(weights))
        classes = {r["id"]: (r["label"], r["legend_entry"]) for r in data["classes"][:len(model.names)]}
        if len(classes) != len(model.names):
            raise ValueError("Model class count is outside dataset mapping")
        normalize = lambda name: __import__("unicodedata").normalize("NFKD", name).encode("ascii", "ignore").decode()
        if {i: normalize(n) for i, n in model.names.items()} != {i: normalize(v[0]) for i, v in classes.items()}:
            raise ValueError("Model numeric class identities differ")
        model_report = dict(checkpoint_sha256=digest(weights), sheets=[], retention="NOT TESTED")
        for sheet in (() if retention_only else data["reviewed_plan_sheets"]):
            image, source_provenance = image_for_sheet(dataset, sheet, pdf_sources, pdf_dpi,
                                                     review_raster_only, source_overrides)
            rgb = np.array(image)
            targets = transform_targets([r for r in data["reviewed_plan_targets"] if r["sheet_id"] == sheet["sheet_id"]],
                                        sheet["review_to_training_source_scale"])
            scopes, scope_origin, pdf_index = scopes_for_sheet(sheet, rgb, pdf_sources)
            sheet_report = dict(sheet_id=sheet["sheet_id"], scope_origin=scope_origin,
                                source_provenance=source_provenance, views=[])
            all_regions = []
            all_predictions = []
            for view_name, region in scopes:
                start = time.perf_counter()
                trace = run_scope(rgb, region, model, classes,
                    report["dataset_sha256"] if model_name == "candidate" else data["parent_manifest_sha256"],
                    pdf_index, reviewed_candidate=model_name == "candidate")
                trace["elapsed_seconds"] = time.perf_counter() - start
                all_regions.extend(trace["plan_regions"])
                view_targets = [t for t in targets if any(center_inside(t["bbox"], r) for r in trace["plan_regions"])]
                trace["matches"] = match_reviewed(view_targets, trace["retained"])
                trace["reviewed_targets"] = view_targets
                all_predictions.extend(trace["retained"])
                stem = re.sub(r"[^a-z0-9]+", "-", f"{sheet['sheet_id']}-{view_name}".casefold()).strip("-")
                for stage in ("raw", "fused", "retained", "rejected"):
                    bounds = [region.x, region.y, region.x + region.width, region.y + region.height] if region else (
                        trace["plan_regions"][0] if trace["plan_regions"] else [0, 0, image.width, image.height])
                    overlay(image, trace[stage], view_targets, classes, bounds,
                            f"{model_name} {view_name}: {stage}; green=reviewed boxes, orange=predictions").save(output / f"{model_name}-{stem}-{stage}.png")
                for stage in ("walls", "wiring", "combined"):
                    geometry_overlay(image, trace["candidate_payload"], classes, bounds, stage,
                        f"{model_name} {view_name}: {stage}; proposals only; cyan=observed, purple=contact leads").save(
                            output / f"{model_name}-{stem}-{stage}.png")
                (output / f"{model_name}-{stem}.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
                sheet_report["views"].append(dict(view=view_name, raw=len(trace["raw"]), fused=len(trace["fused"]),
                    retained=len(trace["retained"]), rejected=len(trace["rejected"]), truncated=trace["truncated"],
                    elapsed_seconds=trace["elapsed_seconds"], matches=trace["matches"],
                    localization_passes=[dict(tile_size=p["tile_size"], tile_stride=p["tile_stride"],
                        raw=len(p["raw"]), fused=len(p["fused"])) for p in trace["localization_passes"]]))
                sheet_report["views"][-1].update(walls=trace["walls_count"], observed_paths=trace["wire_paths_count"],
                                               device_connections=trace["device_connections_count"])
            sheet_report["targets_outside_current_views"] = [t["record_id"] for t in targets
                if not any(center_inside(t["bbox"], r) for r in all_regions)]
            sheet_report["all_reviewed_matches"] = match_reviewed(targets, all_predictions)
            sheet_report["physical_and_annotation_counts"] = dict(Counter(
                "annotation" if re.search(r"home.?run|circuit.*notation", classes[p["class_id"]][0], re.I) else "physical"
                for p in all_predictions))
            model_report["sheets"].append(sheet_report)
            image.close()
        if not skip_retention:
            model_report["retention"] = retention_windows(dataset, data, model, min(80, len(model.names)))
        report["models"][model_name] = model_report
        (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        del model
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "baseline", "candidate", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--pdf-source", action="append", type=Path, default=[])
    parser.add_argument("--skip-retention", action="store_true")
    parser.add_argument("--retention-only", action="store_true")
    parser.add_argument("--pdf-dpi", type=int, choices=(150, 300), default=300)
    parser.add_argument("--review-raster-only", action="store_true")
    parser.add_argument("--source-image", action="append", default=[], metavar="SHEET_ID=PATH")
    args = parser.parse_args()
    result = evaluate(args.dataset, args.baseline, args.candidate, args.output,
                      pdf_paths=args.pdf_source, skip_retention=args.skip_retention,
                      pdf_dpi=args.pdf_dpi, review_raster_only=args.review_raster_only,
                      retention_only=args.retention_only,
                      source_overrides={v.split("=", 1)[0]: Path(v.split("=", 1)[1]) for v in args.source_image})
    print(json.dumps({"output": str(args.output), "models": {k: {"sheets": [
        dict(sheet_id=s["sheet_id"], positives=s["all_reviewed_matches"]["reviewed_positives"],
             matched=s["all_reviewed_matches"]["matched"]) for s in v["sheets"]]} for k, v in result["models"].items()}}))
