"""Periodic native strokes and supported open curves, not inferred circuits.

Some CAD exports flatten dash-dot graphics state into short solid paths. The
periodic runs below are proposed observed geometry. A half-filled enclosure
supplies additional source context; it never becomes an approved device class,
electrical attachment, junction, installation method or generated route.
"""
import json
import math

import cv2
import numpy as np

from app.ai.floor_plan_interpretation.candidate import (
    CandidateWarning, FloorPlanInterpretationPayload, ObservedRouteSegment, PixelPoint,
)

VERSION = 'native-periodic-and-context-curves-v3'
MAXIMUM_OBJECTS_PER_VIEW = 24_000
MAXIMUM_LINES_PER_VIEW = 8_000
MAXIMUM_TRACES = 32
MAXIMUM_CONTEXT_POLYGONS = 512
MAXIMUM_RECTANGLES_PER_BIN = 64
MAXIMUM_CURVE_POINTS = 128


def _source_curve_points(commands, tolerance):
    """Flatten actual cubic ink, not bounding boxes or endpoint chords."""
    if (not commands or commands[0][0]!=2 or any(c[3] for c in commands)
            or not any(c[0]==1 for c in commands)):
        return None
    def cubic(a,b,c,d,depth=0):
        delta=d-a;length=float(np.linalg.norm(delta))
        cross=lambda p:abs(delta[0]*(p-a)[1]-delta[1]*(p-a)[0])
        error=max(cross(b),cross(c))/length if length else max(np.linalg.norm(b-a),np.linalg.norm(c-a))
        if error<=tolerance:return [d]
        if depth>=12:raise ValueError('Curve subdivision limit')
        ab=(a+b)/2;bc=(b+c)/2;cd=(c+d)/2;abc=(ab+bc)/2;bcd=(bc+cd)/2;middle=(abc+bcd)/2
        result=cubic(a,ab,abc,middle,depth+1)+cubic(middle,bcd,cd,d,depth+1)
        if len(result)>MAXIMUM_CURVE_POINTS:raise ValueError('Curve vertex limit')
        return result
    points=[np.array(commands[0][1:3],float)];i=1
    try:
        while i<len(commands):
            if commands[i][0]==0:
                points.append(np.array(commands[i][1:3],float));i+=1
            elif i+2<len(commands) and all(c[0]==1 for c in commands[i:i+3]):
                points+=cubic(points[-1],*(np.array(c[1:3],float) for c in commands[i:i+3]));i+=3
            else:return None  # Multiple subpaths/unknown commands stay unresolved.
            if len(points)>MAXIMUM_CURVE_POINTS:raise ValueError('Curve vertex limit')
    except ValueError:return None
    return points if np.linalg.norm(points[0]-points[-1])>tolerance*2 else None


def _source_pen(obj):
    matrix=obj.get('transform',[1,0,0,1,0,0])
    return obj.get('stroke_width',0)*math.sqrt(abs(matrix[0]*matrix[3]-matrix[1]*matrix[2]))


def native_context_curves(objects, *, coordinate_tolerance, diagnostics, supported_context_ids):
    """Open visible curves meeting compound source-marker boundaries.

    Marker geometry supplies context only: no new device ID, electrical class,
    attachment, circuit join or mounting measurement is created.
    """
    objects=[o for o in objects if o.get('type')==2 and not o.get('clip_paths') and not o.get('level')]
    markers=_compound_markers(objects,coordinate_tolerance,diagnostics)
    # A legend sample or isolated architectural marker is not installed wiring.
    # The same source enclosure must already support an observed periodic run.
    markers=[m for m in markers if set(m['ids'])<=supported_context_ids]
    by_id={o['id']:o for o in objects};result=[]
    for obj in objects:
        color=obj.get('stroke_color')
        if (not obj.get('stroke') or obj.get('fill_mode') or obj.get('dash_array')
                or not color or color[3]<200 or min(color[:3])>220):continue
        points=_source_curve_points(obj.get('commands',()),min(.5,coordinate_tolerance*.3))
        if not points:continue
        length=sum(float(np.linalg.norm(b-a)) for a,b in zip(points,points[1:]));pen=_source_pen(obj)
        context=[]
        for marker in markers:
            outline=by_id[marker['ids'][1]];marker_pen=_source_pen(outline)
            if (marker_pen<=0 or not .7<=pen/marker_pen<=1.35
                    or length<marker['radius']*1.5):continue
            low,high=np.array(outline['bounds'][:2]),np.array(outline['bounds'][2:])
            for point,other in ((points[0],points[1]),(points[-1],points[-2])):
                distance=float(np.linalg.norm(np.maximum(np.maximum(low-point,point-high),0)))
                # Match a terminal boundary and path direction, not nearest center.
                if distance>max(coordinate_tolerance,pen*2):continue
                if float((other-point)@(marker['center']-point))>0:continue
                context.extend(marker['ids']);break
        if not context:continue
        result.append(dict(a=points[0],b=points[-1],points=points,line_style='solid',
                           primitive_ids=[obj['id']],context_ids=sorted(set(context)),kind='curve'))
        if len(result)>MAXIMUM_TRACES:
            diagnostics['curve_trace_budget']=True
            return []
    return result


def _polygon(obj):
    commands = obj.get('commands', ())
    if not 4 <= len(commands) <= 5 or any(p[0] not in (0, 2) for p in commands):
        return None
    points = np.asarray([p[1:3] for p in commands], float)
    if np.linalg.norm(points[0]-points[-1]) < .01:
        points = points[:-1]
    elif not commands[-1][3]:
        return None
    return points


def _area(points):
    return abs(sum(a[0]*b[1]-a[1]*b[0]
                   for a,b in zip(points,np.roll(points,-1,axis=0))))/2


def _compound_markers(objects, tolerance, diagnostics):
    """A triangular fill inside its actual rectangular outline, not any dot."""
    rectangles = {}
    triangles = []
    rectangle_count=0
    for obj in objects:
        polygon = _polygon(obj)
        if polygon is None or _area(polygon) < tolerance*tolerance*4:
            continue
        color = obj.get('fill_color') if obj.get('fill_mode') else obj.get('stroke_color')
        if not color or color[3] < 200 or min(color[:3]) > 220:
            continue
        if len(polygon)==3 and obj.get('fill_mode'):
            if len(triangles)>=MAXIMUM_CONTEXT_POLYGONS:
                diagnostics['context_polygon_budget']=True
                continue
            triangles.append((obj,polygon))
        elif len(polygon)==4 and obj.get('stroke') and not obj.get('fill_mode'):
            edges=np.roll(polygon,-1,axis=0)-polygon
            if any(np.linalg.norm(edge)<tolerance for edge in edges):
                continue
            if any(abs(float(a@b))/(np.linalg.norm(a)*np.linalg.norm(b))>.03
                   for a,b in zip(edges,np.roll(edges,-1,axis=0))):
                continue
            center=polygon.mean(axis=0)
            key=tuple(np.floor(center/64).astype(int))
            rows=rectangles.setdefault(key,[])
            if rectangle_count>=MAXIMUM_CONTEXT_POLYGONS or len(rows)>=MAXIMUM_RECTANGLES_PER_BIN:
                diagnostics['context_polygon_budget']=True
                continue
            rows.append((obj,polygon));rectangle_count+=1
    result=[]
    for obj,triangle in triangles:
        center=triangle.mean(axis=0)
        key=tuple(np.floor(center/64).astype(int))
        nearby=[row for dx in (-1,0,1) for dy in (-1,0,1)
                for row in rectangles.get((key[0]+dx,key[1]+dy),())]
        for outline,rectangle in nearby:
            ratio=_area(triangle)/_area(rectangle)
            if not .45<=ratio<=.55:
                continue
            if any(min(np.linalg.norm(point-corner) for corner in rectangle)>tolerance
                   for point in triangle):
                continue
            result.append(dict(ids=(obj['id'],outline['id']),
                               center=rectangle.mean(axis=0),
                               radius=float(max(np.linalg.norm(p-rectangle.mean(axis=0))
                                                for p in rectangle))))
            break
    return result


def _periodic_chain(chain):
    if not 6<=len(chain)<=128:
        return False
    lengths=np.array([q['high']-q['low'] for q in chain])
    gaps=np.array([b['low']-a['high'] for a,b in zip(chain,chain[1:])])
    # Native, unsampled geometry: gaps scale with the actual strokes.
    if min(gaps)<=0 or max(gaps)>min(gaps)*1.8:
        return False
    interior=lengths[1:-1]
    ordered=sorted(interior)
    split=max(range(1,len(ordered)),key=lambda i:ordered[i]/ordered[i-1])
    if not 2.5<=ordered[split]/ordered[split-1]<=12:
        return False
    cutoff=(ordered[split]+ordered[split-1])/2
    modes=interior>cutoff
    if not (modes[1:]!=modes[:-1]).all():
        return False
    short=interior[interior<cutoff];long=interior[interior>cutoff]
    if not (len(short)>=2 and len(long)>=2
            and max(short)<=min(short)*1.6 and max(long)<=min(long)*1.6
            and max(gaps)<min(long)*.5):
        return False
    # A glyph may clip an endpoint dash; it cannot change the interior period.
    for length,neighbour_is_long in ((lengths[0],modes[0]),(lengths[-1],modes[-1])):
        if neighbour_is_long:
            if length>max(short)*1.6:return False
        elif not max(short)*1.8<=length<=max(long)*1.6:
            return False
    return True


def native_periodic_traces(objects, *, coordinate_tolerance, diagnostics=None):
    """Return independently supported partial fragments; never join crossings."""
    diagnostics={} if diagnostics is None else diagnostics
    objects=[o for o in objects if o.get('type')==2 and not o.get('clip_paths')
             and not o.get('level')]
    if len(objects)>MAXIMUM_OBJECTS_PER_VIEW:
        diagnostics['object_budget']=True
        return []
    markers=_compound_markers(objects,coordinate_tolerance,diagnostics)
    if not markers:
        return []
    lines=[]
    for obj in objects:
        commands=obj.get('commands',())
        if (len(commands)!=2 or commands[0][0]!=2 or commands[1][0]!=0
                or commands[1][3] or not obj.get('stroke') or obj.get('fill_mode')
                or obj.get('dash_array')):
            continue
        color=obj.get('stroke_color')
        if not color or color[3]<200 or min(color[:3])>220:
            continue
        a,b=np.array([p[1:3] for p in commands]);delta=b-a
        distance=float(np.linalg.norm(delta))
        if distance<coordinate_tolerance*1.5:
            continue
        axis=delta/distance
        if axis[0]<-.01 or (abs(axis[0])<.01 and axis[1]<0):
            axis=-axis
        normal=np.array([-axis[1],axis[0]])
        matrix=obj.get('transform',[1,0,0,1,0,0])
        pen=obj.get('stroke_width',0)*math.sqrt(abs(matrix[0]*matrix[3]-matrix[1]*matrix[2]))
        key=(tuple(color),round(pen,5),round(math.degrees(math.atan2(axis[1],axis[0])),1))
        lines.append(dict(obj=obj,axis=axis,normal=normal,offset=float(a@normal),
                          low=min(a@axis,b@axis),high=max(a@axis,b@axis),key=key))
    if len(lines)>MAXIMUM_LINES_PER_VIEW:
        diagnostics['line_budget']=True
        return []
    groups={}
    for line in sorted(lines,key=lambda l:(l['key'],l['offset'])):
        style_groups=groups.setdefault(line['key'],[])
        # Sorted offsets make the last group the only eligible neighbour.
        if not style_groups or abs(style_groups[-1][0]['offset']-line['offset'])>coordinate_tolerance:
            style_groups.append([line])
        else:
            style_groups[-1].append(line)
    result=[]
    for style_groups in groups.values():
        for group in style_groups:
            rows=sorted(group,key=lambda l:l['low'])
            positive_gaps=[b['low']-a['high'] for a,b in zip(rows,rows[1:]) if b['low']>a['high']]
            if not positive_gaps:
                continue
            gap_limit=float(np.median(positive_gaps))*1.8
            chains=[];chain=[]
            for row in rows:
                if chain and row['low']-chain[-1]['high']>gap_limit:
                    chains.append(chain);chain=[]
                chain.append(row)
            if chain:chains.append(chain)
            for chain in chains:
                if not _periodic_chain(chain):
                    continue
                first=chain[0];axis=first['axis'];normal=first['normal']
                offset=float(np.median([q['offset'] for q in chain]))
                low,high=first['low'],chain[-1]['high']
                context=[m for m in markers
                         if low-m['radius']*2<=float(m['center']@axis)<=high+m['radius']*2
                         and abs(float(m['center']@normal)-offset)<=m['radius']*.7+coordinate_tolerance]
                if not context:
                    continue
                result.append(dict(a=low*axis+offset*normal,b=high*axis+offset*normal,
                                   primitive_ids=[q['obj']['id'] for q in chain],
                                   context_ids=sorted({i for m in context for i in m['ids']})[:32]))
    if len(result)>MAXIMUM_TRACES:
        diagnostics['trace_budget']=True
    return result[:MAXIMUM_TRACES]


def with_pdf_observed_wiring(payload,image_rgb,index):
    """Add new proposals only; saved routes/reviews and device IDs stay untouched."""
    if (type(payload) is not FloorPlanInterpretationPayload or not isinstance(image_rgb,np.ndarray)
            or image_rgb.dtype!=np.uint8 or image_rgb.ndim!=3 or image_rgb.shape[2]!=3
            or image_rgb.shape[:2]!=(payload.source_plane.height_pixels,payload.source_plane.width_pixels)):
        raise ValueError('Native wiring requires unchanged, matching source RGB pixels.')
    if image_rgb.shape[0]*image_rgb.shape[1]>12_000_000 or max(image_rgb.shape[:2])>4096:
        warning=CandidateWarning(code='pdf_native_wiring_budget',severity='warning',
            message='Native observed-wiring source-pixel verification exceeded its bounded image limit.')
        routes=payload.observed_routes.model_copy(update={'state':'partial','failure_reason':None,'truncated':True})
        return type(payload).model_validate(payload.model_copy(update={
            'observed_routes':routes,'warnings':payload.warnings+(warning,) if len(payload.warnings)<256 else payload.warnings,
            'document_state':'partial'}).model_dump())
    tolerance=max(.5,min(payload.source_plane.width_pixels,payload.source_plane.height_pixels)*.00066)
    gray=cv2.cvtColor(image_rgb,cv2.COLOR_RGB2GRAY)
    support=cv2.dilate((gray<220).astype(np.uint8),np.ones((3,3),np.uint8))
    segments=list(payload.observed_routes.segments);warnings=list(payload.warnings)
    diagnostics={}
    next_id=max((int(s.id.rsplit('-',1)[-1]) for s in segments),default=0)
    for region in payload.regions:
        if region.kind!='plan_region' or not region.bounds:
            continue
        box=region.bounds
        objects=index.query([box.x,box.y,box.x+box.width,box.y+box.height])
        objects=[o for o in objects if box.x<=o['bounds'][0] and o['bounds'][2]<=box.x+box.width
                 and box.y<=o['bounds'][1] and o['bounds'][3]<=box.y+box.height]
        if len(objects)>MAXIMUM_OBJECTS_PER_VIEW:
            diagnostics['object_budget']=True
            continue
        by_id={o['id']:o for o in objects}
        traces=native_periodic_traces(objects,coordinate_tolerance=tolerance,diagnostics=diagnostics)
        context_ids={identity for trace in traces for identity in trace['context_ids']}
        traces+=native_context_curves(objects,coordinate_tolerance=tolerance,diagnostics=diagnostics,
                                     supported_context_ids=context_ids)
        for trace in traces:
            # Every proposed stroke must be visible in the unchanged raster.
            verified=True
            for primitive in trace['primitive_ids']:
                commands=by_id[primitive]['commands']
                ink_points=trace.get('points') if trace.get('kind')=='curve' else [np.array(p[1:3]) for p in commands]
                xy=np.rint(np.concatenate([np.linspace(a,b,max(2,math.ceil(np.linalg.norm(b-a))+1))
                    for a,b in zip(ink_points,ink_points[1:])])).astype(int)
                if ((xy<0).any() or (xy[:,0]>=gray.shape[1]).any()
                        or (xy[:,1]>=gray.shape[0]).any()
                        or float(support[xy[:,1],xy[:,0]].mean())<.9):
                    verified=False;break
            if not verified:
                continue
            if len(warnings)>=255 or len(segments)>=512:
                diagnostics['candidate_budget']=True
                continue
            a,b=trace['a'],trace['b'];delta=b-a;length=float(np.linalg.norm(delta));axis=delta/length
            points=trace.get('points',[a,b])
            duplicate=False
            for segment in segments:
                existing=np.array([[p.x,p.y] for p in segment.points])
                if len(existing)==len(points) and (np.allclose(existing,points,atol=1e-7,rtol=0)
                        or np.allclose(existing,list(reversed(points)),atol=1e-7,rtol=0)):
                    duplicate=True;break
                if trace.get('kind')=='curve':continue
                if len(segment.points)!=2:continue
                c,d=np.array([[p.x,p.y] for p in segment.points])
                normal=np.array([-axis[1],axis[0]])
                if (max(abs(float((p-a)@normal)) for p in (c,d))<=tolerance
                        and abs(float((d-c)@axis))>=length*.8
                        and min(float((p-a)@axis) for p in (c,d))<=length*.1
                        and max(float((p-a)@axis) for p in (c,d))>=length*.9):
                    duplicate=True;break
            if duplicate:continue
            next_id+=1;route_id=f'segment-{next_id:04d}'
            segments.append(ObservedRouteSegment(id=route_id,points=tuple(PixelPoint(x=float(p[0]),y=float(p[1])) for p in points),line_style=trace.get('line_style','dashed'),
                evidence_refs=(f'region:{region.id}',),ambiguity='ambiguous'))
            warnings.append(CandidateWarning(code='pdf_native_open_curve_trace' if trace.get('kind')=='curve' else 'pdf_periodic_observed_trace',severity='info',
                entity_refs=(f'segment:{route_id}',),
                message='Native source ink, not a confirmed circuit or device attachment: '+json.dumps(
                    dict(primitive_ids=trace['primitive_ids'],
                         compound_marker_ids=trace['context_ids']),separators=(',',':'))))
    if diagnostics and len(warnings)<256:
        warnings.append(CandidateWarning(code='pdf_native_wiring_budget',severity='warning',
            message='Native observed-wiring proposals are incomplete after bounded limits: '+', '.join(sorted(diagnostics))))
    if len(segments)==len(payload.observed_routes.segments) and len(warnings)==len(payload.warnings):
        return payload
    routes=payload.observed_routes.model_copy(update={'segments':tuple(segments),'state':'partial',
        'failure_reason':None,'truncated':payload.observed_routes.truncated or bool(diagnostics)})
    return type(payload).model_validate(payload.model_copy(update={
        'observed_routes':routes,'warnings':tuple(warnings),'document_state':'partial'}).model_dump())
