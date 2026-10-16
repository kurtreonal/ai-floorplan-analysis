"""Read-only raster wiring replay with frozen symbol/wall proposals.

Explicit source/payload pairs only; no models, database, approvals or originals
are modified. Outputs are provisional diagnostics, never evaluation truth.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import subprocess
import types

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.ai.floor_plan_interpretation.automatic_wiring import with_automatic_wiring
from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationPayload, ObservedRoutes
from app.ai.floor_plan_interpretation import observed_wiring


def metrics(payload):
    routes = payload.observed_routes
    ends = {}
    length = 0
    for route in routes.segments:
        for point in (route.points[0], route.points[-1]):
            key = (point.x, point.y)
            ends[key] = ends.get(key, 0) + 1
        length += math.fsum(math.hypot(b.x-a.x, b.y-a.y) for a, b in zip(route.points, route.points[1:]))
    return dict(paths=len(routes.segments), vertices=sum(len(s.points) for s in routes.segments),
                contacts=len(routes.connections), shared_endpoints=sum(n > 1 for n in ends.values()),
                contacted_symbols=sorted({c.to_ref for c in routes.connections if c.to_ref.startswith('symbol:')}),
                truncated=routes.truncated,
                centerline_pixels=length, metric_length=None, independently_reviewed_reference=False)


def overlay(image, payload, combined):
    output = image.copy().convert('RGB') if combined else Image.new('RGB', image.size, '#fafafa')
    draw = ImageDraw.Draw(output)
    width = max(2, round(min(image.size)/450))
    if combined:
        for s in payload.symbols.items:
            if s.bounds:
                box = s.bounds
                draw.rectangle((box.x, box.y, box.x+box.width, box.y+box.height), outline='#888888', width=1)
    colors = ('#d54b1d', '#1469a1', '#7e3e96', '#238156')
    for i, route in enumerate(payload.observed_routes.segments):
        points = [(p.x, p.y) for p in route.points]
        draw.line(points, fill=colors[i % len(colors)], width=width)
        for x, y in (points[0], points[-1]):
            draw.ellipse((x-width, y-width, x+width, y+width), fill=colors[i % len(colors)])
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', nargs=2, action='append', metavar=('SOURCE', 'PAYLOAD'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--payload-encoding', default='utf-8')
    parser.add_argument('--auxiliary-baseline-ref', help='Compare auxiliary geometry to this local Git ref, without model inference.')
    parser.add_argument('--detector-baseline-ref', help='Compare full raster wiring to this local Git ref, holding symbols/walls fixed.')
    args = parser.parse_args()
    if args.auxiliary_baseline_ref and args.detector_baseline_ref:
        parser.error('Choose either auxiliary or full raster comparison, not both.')
    args.output.mkdir(parents=True, exist_ok=False)
    records = []
    for index, (source, payload_path) in enumerate(args.case, 1):
        source = Path(source)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        frozen = FloorPlanInterpretationPayload.model_validate_json(Path(payload_path).read_text(encoding=args.payload_encoding))
        with Image.open(source) as original:
            image = original.convert('RGB')
        if image.size != (frozen.source_plane.width_pixels, frozen.source_plane.height_pixels):
            raise ValueError('Source and frozen payload coordinate planes differ; no implicit resizing.')
        clean = frozen.model_copy(update={'observed_routes': ObservedRoutes(state='unavailable')})
        if args.auxiliary_baseline_ref:
            code = subprocess.check_output(['git', 'show', args.auxiliary_baseline_ref +
                ':backend/app/ai/floor_plan_interpretation/observed_wiring.py'], text=True)
            baseline = types.ModuleType('baseline_observed_wiring')
            baseline.__package__ = 'app.ai.floor_plan_interpretation'
            sys.modules[baseline.__name__] = baseline
            exec(compile(code, '<local-baseline-observed-wiring>', 'exec'), baseline.__dict__)
            # Unmodified native-resolution tiles, with exact source offsets.
            tiles = []
            from app.ai.floor_plan_interpretation.candidate import AffineTransform
            for y in range(0, image.height, 896):
                for x in range(0, image.width, 896):
                    tile = np.asarray(image.crop((x, y, min(x+1024, image.width), min(y+1024, image.height))))
                    if min(tile.shape[:2]) >= 16:
                        tiles.append(types.SimpleNamespace(region_id=f'tile-{len(tiles)+1:04d}',
                            image_rgb=tile, local_to_source=AffineTransform(a=1,b=0,c=0,d=1,e=x,f=y)))
            context = types.SimpleNamespace(tiles=tiles, source_plane=frozen.source_plane)
            before = clean.model_copy(update={'observed_routes': baseline.prepare_observed_wiring_evidence(context)})
            current = clean.model_copy(update={'observed_routes': observed_wiring.prepare_observed_wiring_evidence(context)})
            (args.output / f'{index}-baseline.json').write_text(before.model_dump_json(), encoding='utf-8')
            for kind in ('wiring', 'combined'):
                overlay(image, before, kind == 'combined').save(args.output / f'{index}-before-{kind}.png')
        else:
            current = with_automatic_wiring(clean, np.asarray(image))
            if args.detector_baseline_ref:
                modules = []
                for name in ('automatic_wiring', 'fixture_wiring', 'device_contact_evidence'):
                    code = subprocess.check_output(['git', 'show', args.detector_baseline_ref +
                        ':backend/app/ai/floor_plan_interpretation/' + name + '.py'], text=True)
                    module = types.ModuleType('baseline_' + name)
                    module.__package__ = 'app.ai.floor_plan_interpretation'
                    sys.modules[module.__name__] = module
                    exec(compile(code, '<local-baseline-' + name + '>', 'exec'), module.__dict__)
                    modules.append(module)
                modules[0].fixture_axis_traces = modules[1].fixture_axis_traces
                modules[0].with_device_contact_evidence = modules[2].with_device_contact_evidence
                before = modules[0].with_automatic_wiring(clean, np.asarray(image))
                (args.output / f'{index}-baseline.json').write_text(before.model_dump_json(), encoding='utf-8')
                for kind in ('wiring', 'combined'):
                    overlay(image, before, kind == 'combined').save(args.output / f'{index}-before-{kind}.png')
        (args.output / f'{index}-payload.json').write_text(current.model_dump_json(), encoding='utf-8')
        for kind in ('wiring', 'combined'):
            overlay(image, current, kind == 'combined').save(args.output / f'{index}-{kind}.png')
            if args.auxiliary_baseline_ref or args.detector_baseline_ref:
                comparison = Image.new('RGB', (image.width*2, image.height+40), '#f4f4f4')
                comparison.paste(overlay(image, before, kind == 'combined'), (0,40))
                comparison.paste(overlay(image, current, kind == 'combined'), (image.width,40))
                draw = ImageDraw.Draw(comparison)
                font = ImageFont.load_default(size=15)
                draw.text((10,10), f'BEFORE: {len(before.observed_routes.segments)} paths - proposals, not ground truth', fill='#222222', font=font)
                draw.text((image.width+10,10), f'AFTER: {len(current.observed_routes.segments)} paths - proposals, not ground truth', fill='#222222', font=font)
                comparison.save(args.output / f'{index}-comparison-{kind}.png')
        records.append(dict(source=str(source), source_sha256=digest, frozen_payload=str(payload_path),
                            walls_symbols_unchanged=current.walls == frozen.walls and current.symbols == frozen.symbols,
                            **metrics(current),
                            baseline=metrics(before) if args.auxiliary_baseline_ref or args.detector_baseline_ref else None,
                            geometry_changed=before.observed_routes.segments != current.observed_routes.segments
                                if args.auxiliary_baseline_ref or args.detector_baseline_ref else None,
                            extractor='auxiliary_unclassified_geometry' if args.auxiliary_baseline_ref else 'device_context_raster'))
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    (args.output / 'report.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    print(json.dumps(records, indent=2))


if __name__ == '__main__':
    main()
