"""Private, reproducible before/after wall diagnostic; originals are read-only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import cv2
import numpy as np
from app.ai.floor_plan_interpretation import demo_cv
from app.ai.floor_plan_interpretation.drawing_region import DrawingRegion, interpret_drawing_region
from app.ai.wall_detection import detector


def band_record(pair):
    (start, end), thickness = pair
    return {"start": [int(v) for v in start], "end": [int(v) for v in end],
            "thickness_pixels": float(thickness)}


def trace_wall_evidence(rgb, interpreter):
    """Observe existing decisions without changing thresholds or accepted ink."""
    trace = {"style": "solid_or_unqualified_outline", "pairs": [], "segment_profiles": []}
    qualify = detector._without_detached_enclosing_bands
    outline = detector._outlined_wall_evidence
    compact = detector._has_compact_parallel_bars

    def capture_profile(segment, image):
        rejected = compact(segment, image)
        if len(trace["segment_profiles"]) < 256:
            x1, y1, x2, y2, thickness = segment
            length = np.hypot(x2 - x1, y2 - y1)
            if length:
                offsets = np.arange(-min(64, max(2, round(thickness * 2))),
                                    min(64, max(2, round(thickness * 2))) + 1)
                t = np.linspace(.2, .8, 64)
                xs = np.rint(x1 + t[None, :] * (x2 - x1) - offsets[:, None] * (y2 - y1) / length).astype(int)
                ys = np.rint(y1 + t[None, :] * (y2 - y1) + offsets[:, None] * (x2 - x1) / length).astype(int)
                valid = (xs >= 0) & (xs < image.shape[1]) & (ys >= 0) & (ys < image.shape[0])
                active = (valid & (image[np.clip(ys, 0, image.shape[0]-1), np.clip(xs, 0, image.shape[1]-1)] == 0)).mean(axis=1) > .65
                starts = np.flatnonzero(active & ~np.r_[False, active[:-1]])
                ends = np.flatnonzero(active & ~np.r_[active[1:], False])
                trace["segment_profiles"].append({"segment": [float(v) for v in segment],
                    "stripe_widths": (ends-starts+1).tolist(),
                    "stripe_centers": ((offsets[starts]+offsets[ends])/2).tolist(),
                    "compact_rejected": bool(rejected)})
        return rejected

    def capture_pairs(pairs):
        trace["pairs"] = [band_record(pair) for pair in pairs]
        return qualify(pairs)

    def capture_outline(*args, **kwargs):
        result = outline(*args, **kwargs)
        if result is not None:
            trace.update(style="paired_outline", median_band_width_pixels=result[1],
                         rejected_pairs=[band_record(pair) for pair in result[2]],
                         recovered_ends=[band_record(pair) for pair in result[3]])
        return result

    with patch.object(detector, "_without_detached_enclosing_bands", side_effect=capture_pairs), \
         patch.object(detector, "_outlined_wall_evidence", side_effect=capture_outline), \
         patch.object(detector, "_has_compact_parallel_bars", side_effect=capture_profile):
        result = interpreter(rgb)
    return result, trace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--contrast-offset", type=int, choices=range(1, 21),
                        help="Diagnostic-only adaptive contrast experiment; never changes defaults")
    parser.add_argument("--region", type=int, nargs=4, metavar=("X", "Y", "WIDTH", "HEIGHT"),
                        help="Explicit drawing bounds; same native pixels for both versions")
    parser.add_argument("--trace", action="store_true", help="Save paired-band evidence without altering inference")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new output directory; prior diagnostics are immutable")
    before_hash = hashlib.sha256(args.source.read_bytes()).hexdigest()
    image = cv2.imread(str(args.source))
    if image is None:
        parser.error("Unreadable source")
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    region = DrawingRegion(x=args.region[0], y=args.region[1], width=args.region[2], height=args.region[3]) if args.region else None

    def interpret(interpreter, source):
        return interpret_drawing_region(source, region=region, interpreter=interpreter) if region else interpreter(source)
    old_source = subprocess.check_output(
        ["git", "show", "HEAD:backend/app/ai/wall_detection/detector.py"], cwd=ROOT, text=True,
    )
    baseline = types.ModuleType("wall_diagnostic_baseline")
    sys.modules[baseline.__name__] = baseline
    exec(compile(old_source, "baseline_detector", "exec"), baseline.__dict__)
    old_demo_source = subprocess.check_output(
        ["git", "show", "HEAD:backend/app/ai/floor_plan_interpretation/demo_cv.py"], cwd=ROOT, text=True,
    )
    baseline_demo = types.ModuleType("wall_diagnostic_baseline_demo")
    sys.modules[baseline_demo.__name__] = baseline_demo
    exec(compile(old_demo_source, "baseline_demo", "exec"), baseline_demo.__dict__)
    with patch.object(baseline_demo, "detect_wall_lines", baseline.detect_wall_lines):
        old = interpret(baseline_demo.interpret_floor_plan_demo, rgb)
    trace = None
    if args.contrast_offset is None:
        if args.trace:
            new, trace = trace_wall_evidence(rgb, lambda source: interpret(demo_cv.interpret_floor_plan_demo, source))
        else:
            new = interpret(demo_cv.interpret_floor_plan_demo, rgb)
    else:
        adaptive = cv2.adaptiveThreshold
        def experiment(source, maximum, method, kind, block, _offset):
            return adaptive(source, maximum, method, kind, block, args.contrast_offset)
        with patch.object(cv2, "adaptiveThreshold", side_effect=experiment):
            new = interpret(demo_cv.interpret_floor_plan_demo, rgb)
    args.output.mkdir(parents=True)
    report = {"source_sha256": before_hash, "note": "Candidate counts, not accuracy or approved geometry"}
    report["experimental_contrast_offset"] = args.contrast_offset
    report["drawing_region"] = region.model_dump() if region else None
    if trace is not None:
        report["evidence_trace"] = trace
        report["evidence_trace"]["coordinate_frame"] = "drawing_region_local" if region else "source_pixels"
    for name, result in (("before", old), ("after", new)):
        canvas = image.copy()
        for wall in result.walls.items:
            cv2.line(canvas, (round(wall.start.x), round(wall.start.y)),
                     (round(wall.end.x), round(wall.end.y)), (0, 0, 255), 4)
            if args.trace:
                cv2.putText(canvas, wall.id, (round(wall.start.x) + 3, round(wall.start.y) + 14),
                            cv2.FONT_HERSHEY_SIMPLEX, .45, (0, 0, 180), 1, cv2.LINE_AA)
        cv2.imwrite(str(args.output / f"{name}.png"), canvas)
        report[name] = {"walls": len(result.walls.items), "rooms": len(result.rooms.items)}
        (args.output / f"{name}.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    report["original_unchanged"] = before_hash == hashlib.sha256(args.source.read_bytes()).hexdigest()
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "evidence_trace"}))
    if trace is not None:
        print(json.dumps({"style": trace["style"], "paired_bands": len(trace["pairs"]),
                          "rejected_pairs": len(trace.get("rejected_pairs", [])),
                          "recovered_ends": len(trace.get("recovered_ends", []))}))


if __name__ == "__main__":
    main()
