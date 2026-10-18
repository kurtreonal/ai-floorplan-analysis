"""Private-source stage ablation, not approved ground truth or an upload API.

Run on a frozen candidate and its exact registered raster. No database writes.
Never use overlays/assistant labels as independent evaluation annotations.
"""
import argparse
import ast
from hashlib import sha256
import inspect
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import cv2
import numpy as np
from PIL import Image
from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationCandidate
from app.ai.floor_plan_interpretation import automatic_wiring as wires
from app.ai.floor_plan_interpretation import experimental_symbol_detector as shared
from app.ai.floor_plan_interpretation import multiclass_symbol_detector as detector
from app.ai.floor_plan_interpretation.wiring_recovery import recover_wiring, RecoveryLimits
from probe_wiring_recovery import overlay


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--maximum-seconds',type=float,default=90)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    frozen=FloorPlanInterpretationCandidate.model_validate_json(args.baseline.read_text(encoding='utf-8'))
    before=frozen.payload;rgb=np.asarray(Image.open(args.source).convert('RGB'))
    if rgb.shape[:2]!=(before.source_plane.height_pixels,before.source_plane.width_pixels):
        raise ValueError('Use the exact baseline raster, not a thumbnail or distorted copy.')
    report=dict(source_sha256=sha256(args.source.read_bytes()).hexdigest(),
                baseline_sha256=sha256(args.baseline.read_bytes()).hexdigest(),
                detector_configuration=detector.configuration_sha256(),independent_ground_truth=False,
                width=rgb.shape[1],height=rgb.shape[0],inference_views=[],wire_rejections={})
    original_fuse=shared.fuse
    def capture(rows,**kwargs):
        retained=original_fuse(rows,**kwargs)
        report['inference_views'].append(dict(raw=rows,retained=retained,
            raw_count=len(rows),fused_count=len(retained),cap=shared.MAX_CANDIDATES))
        return retained
    shared.fuse=capture
    start=time.monotonic();predictions,truncated=detector.locate(rgb)
    report['symbol_seconds']=time.monotonic()-start
    report['selected_raw_predictions']=predictions
    report['selected_count_before_scope']=len(predictions)
    report['symbol_truncated']=truncated
    # Frozen walls/regions isolate recognition changes from unrelated geometry edits.
    value=before.model_dump(mode='json');value['warnings']=[]
    value['observed_routes']={'state':'empty','segments':[],'connections':[],'truncated':False}
    base=type(before).model_validate(value)
    symbol_value=base.model_dump(mode='json')
    symbol_value['regions']=[r for r in symbol_value['regions'] if r['kind']=='plan_region']
    symbol_value['symbols']={'state':'empty','items':[],'truncated':False}
    symbols=detector.with_proposals(type(before).model_validate(symbol_value),predictions,truncated)
    report['retained_after_scope']=len(symbols.symbols.items)
    source=inspect.getsource(wires.with_automatic_wiring)
    tree=ast.parse(source);offset=inspect.getsourcelines(wires.with_automatic_wiring)[1]-1
    reasons={offset+body.lineno:ast.unparse(node.test) for node in ast.walk(tree) if isinstance(node,ast.If)
             for body in node.body if isinstance(body,ast.Continue)}
    def trace(frame,event,arg):
        if frame.f_code is not wires.with_automatic_wiring.__code__:return None
        if event=='line' and frame.f_lineno in reasons:
            reason=reasons[frame.f_lineno]
            report['wire_rejections'][reason]=report['wire_rejections'].get(reason,0)+1
        return trace
    original_context=wires.with_validated_solid_context
    def capture_context(payload,image):
        report['before_solid_context']=dict(paths=len(payload.observed_routes.segments),contacts=len(payload.observed_routes.connections))
        (args.output/'pre-context.json').write_text(payload.model_dump_json(),encoding='utf-8')
        return original_context(payload,image)
    wires.with_validated_solid_context=capture_context
    # Separate ablations: old symbols/new wires, then new symbols/new wires.
    start=time.monotonic();wire_only=wires.with_automatic_wiring(base,rgb)
    report['wire_only_seconds']=time.monotonic()-start
    (args.output/'wire-only.json').write_text(wire_only.model_dump_json(),encoding='utf-8')
    start=time.monotonic();sys.settrace(trace)
    try: initial=wires.with_automatic_wiring(symbols,rgb)
    finally:sys.settrace(None)
    report['wire_seconds']=time.monotonic()-start
    (args.output/'initial.json').write_text(initial.model_dump_json(),encoding='utf-8')
    start=time.monotonic();after=recover_wiring(initial,rgb,limits=RecoveryLimits(maximum_seconds=args.maximum_seconds))
    report['recovery_seconds']=time.monotonic()-start
    report['initial']=dict(paths=len(initial.observed_routes.segments),contacts=len(initial.observed_routes.connections))
    report['final']=dict(paths=len(after.observed_routes.segments),contacts=len(after.observed_routes.connections),
                         recovery=after.observed_routes.recovery.model_dump(mode='json'))
    (args.output/'after.json').write_text(after.model_dump_json(),encoding='utf-8')
    Image.fromarray(overlay(before,rgb)).save(args.output/'before.png')
    Image.fromarray(overlay(after,rgb)).save(args.output/'after.png')
    (args.output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('inference_views','selected_raw_predictions')}),flush=True)


if __name__=='__main__':main()
