"""Source-bound view settings inside the existing append-only JSON document."""
from hashlib import sha256
import json

DISPLAY_FIELDS={'display_paper_size','display_orientation','display_width_mm','display_height_mm'}


def run_binding(run):
    candidate=json.loads(run.candidate_json)
    plane=candidate['payload']['source_plane']
    width,height=plane['width_pixels'],plane['height_pixels']
    parameters=candidate['provenance'].get('inference_parameters',[])
    region=next((json.loads(p['value']) for p in parameters if p['name']=='drawing-region'),None)
    normalized=None if region is None else {k:round(region[k]/(width if k in ('x','width') else height),6) for k in ('x','y','width','height')}
    identity=dict(source_sha256=candidate['provenance']['source_sha256'],page_id=run.floor_plan_page_id,region=normalized)
    key=sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return dict(identity,binding_id=key,width_pixels=width,height_pixels=height,
                coordinate_space=plane['coordinate_space'],source_to_view=[1,0,0,1,0,0])


def settings_for_run(document,run):
    values=dict(document.get('settings') or {})
    binding=run_binding(run)
    entry=(document.get('measurement_views') or {}).get(binding['binding_id'])
    if entry is None and binding['region'] is not None:
        child=binding['region']
        parents=[]
        mixed=any(p.get('has_not_to_scale') or len(p.get('drawing_scale_denominators',[]))>1 for p in document.get('source_pages',[]))
        for candidate in (document.get('measurement_views') or {}).values():
            parent=candidate['binding'];region=parent['region']
            if (parent['source_sha256'],parent['page_id'])!=(binding['source_sha256'],binding['page_id']):continue
            if candidate['settings'].get('measurement_method')=='not_to_scale':continue
            if region is None and mixed:continue
            region=region or dict(x=0,y=0,width=1,height=1)
            if (child['x']>=region['x'] and child['y']>=region['y'] and
                child['x']+child['width']<=region['x']+region['width']+1e-6 and
                child['y']+child['height']<=region['y']+region['height']+1e-6):
                parents.append((region['width']*region['height'],candidate))
        if parents:entry=min(parents,key=lambda p:(p[0],p[1]['binding']['binding_id']))[1]
    if entry:
        values.update(entry['settings'])
        # Reference points are persisted in their source plane, not screen pixels.
        old=entry['binding']
        sx=binding['width_pixels']/old['width_pixels'];sy=binding['height_pixels']/old['height_pixels']
        if abs(sx/sy-1)>.001:
            values['_transform_invalid']=True
        elif values.get('reference'):
            ref=dict(values['reference'])
            for endpoint in ('start','end'):
                ref[endpoint]={axis:ref[endpoint][axis]*(sx if axis=='x' else sy) for axis in ('x','y')}
            values['reference']=ref
    return values,binding
