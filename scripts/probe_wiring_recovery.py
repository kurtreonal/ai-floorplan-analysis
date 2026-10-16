"""Read-only private-source comparison. Output overlays are proposals, not gold."""
import argparse
import json
import math
from pathlib import Path
import sys
from hashlib import sha256

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import cv2
import numpy as np
from PIL import Image
from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationPayload
from app.ai.floor_plan_interpretation.wiring_recovery import recover_wiring, RecoveryLimits


def overlay(payload,image,wiring_only=False):
    canvas=np.full_like(image,255) if wiring_only else image.copy()
    for route in payload.observed_routes.segments:
        cv2.polylines(canvas,[np.rint([(p.x,p.y) for p in route.points]).astype(int)],False,(0,90,230),2)
    symbols={s.id:s for s in payload.symbols.items}
    for contact in payload.observed_routes.connections:
        if contact.device_anchor is None:continue
        p=contact.device_anchor
        cv2.circle(canvas,(round(p.x),round(p.y)),5,(0,150,50) if contact.ambiguity=='unambiguous' else (220,100,0),2)
    if payload.observed_routes.recovery:
        for device in payload.observed_routes.recovery.devices:
            if device.state=='observed_recovered':continue
            p=symbols[device.symbol_id].center
            cv2.circle(canvas,(round(p.x),round(p.y)),8,(220,100,0),2)
    return canvas


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',nargs=2,action='append',metavar=('SOURCE','PAYLOAD'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--maximum-windows',type=int,default=64)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    reports=[]
    for index,(source,payload_file) in enumerate(args.case,1):
        image=np.asarray(Image.open(source).convert('RGB'))
        before=FloorPlanInterpretationPayload.model_validate_json(Path(payload_file).read_text(encoding='utf-8'))
        after=recover_wiring(before,image,limits=RecoveryLimits(maximum_windows=args.maximum_windows))
        for only,name in ((True,'wiring'),(False,'combined')):
            a,b=overlay(before,image,only),overlay(after,image,only)
            strip=np.full((40,a.shape[1]*2,3),255,np.uint8)
            cv2.putText(strip,'BEFORE (proposals)',(10,27),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,0,0),1)
            cv2.putText(strip,'AFTER - observed blue / contacts green / unresolved orange',(a.shape[1]+10,27),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,0,0),1)
            result=np.concatenate((strip,np.concatenate((a,b),axis=1)),axis=0)
            Image.fromarray(result).save(args.output/f'{index}-{name}.png')
        (args.output/f'{index}-after.json').write_text(after.model_dump_json(),encoding='utf-8')
        old_ids={r.id for r in before.observed_routes.segments}
        added=[r for r in after.observed_routes.segments if r.id not in old_ids]
        for number,route in enumerate(added,1):
            xs=[p.x for p in route.points];ys=[p.y for p in route.points]
            left,top=max(0,math.floor(min(xs))-80),max(0,math.floor(min(ys))-80)
            right,bottom=min(image.shape[1],math.ceil(max(xs))+80),min(image.shape[0],math.ceil(max(ys))+80)
            a=overlay(before,image)[top:bottom,left:right];b=overlay(after,image)[top:bottom,left:right]
            Image.fromarray(np.concatenate((a,b),axis=1)).save(args.output/f'{index}-detail-{number}.png')
        report=dict(source=source,source_sha256=sha256(Path(source).read_bytes()).hexdigest(),
            before_paths=len(before.observed_routes.segments),after_paths=len(after.observed_routes.segments),
            before_contacts=len(before.observed_routes.connections),after_contacts=len(after.observed_routes.connections),
            walls_symbols_unchanged=before.walls==after.walls and before.symbols==after.symbols,
            independent_ground_truth=False,recovery=after.observed_routes.recovery.model_dump(mode='json'))
        reports.append(report)
        print(json.dumps({k:v for k,v in report.items() if k!='recovery'}),flush=True)
    (args.output/'report.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')


if __name__=='__main__':main()
