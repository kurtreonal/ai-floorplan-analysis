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
from app.ai.floor_plan_interpretation import demo_cv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--contrast-offset", type=int, choices=range(1, 21),
                        help="Diagnostic-only adaptive contrast experiment; never changes defaults")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new output directory; prior diagnostics are immutable")
    before_hash = hashlib.sha256(args.source.read_bytes()).hexdigest()
    image = cv2.imread(str(args.source))
    if image is None:
        parser.error("Unreadable source")
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
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
        old = baseline_demo.interpret_floor_plan_demo(rgb)
    if args.contrast_offset is None:
        new = demo_cv.interpret_floor_plan_demo(rgb)
    else:
        adaptive = cv2.adaptiveThreshold
        def experiment(source, maximum, method, kind, block, _offset):
            return adaptive(source, maximum, method, kind, block, args.contrast_offset)
        with patch.object(cv2, "adaptiveThreshold", side_effect=experiment):
            new = demo_cv.interpret_floor_plan_demo(rgb)
    args.output.mkdir(parents=True)
    report = {"source_sha256": before_hash, "note": "Candidate counts, not accuracy or approved geometry"}
    report["experimental_contrast_offset"] = args.contrast_offset
    for name, result in (("before", old), ("after", new)):
        canvas = image.copy()
        for wall in result.walls.items:
            cv2.line(canvas, (round(wall.start.x), round(wall.start.y)),
                     (round(wall.end.x), round(wall.end.y)), (0, 0, 255), 4)
        cv2.imwrite(str(args.output / f"{name}.png"), canvas)
        report[name] = {"walls": len(result.walls.items), "rooms": len(result.rooms.items)}
        (args.output / f"{name}.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    report["original_unchanged"] = before_hash == hashlib.sha256(args.source.read_bytes()).hexdigest()
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
