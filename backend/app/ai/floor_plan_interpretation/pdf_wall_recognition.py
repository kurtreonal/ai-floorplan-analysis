"""Advisory wall bands from native boundaries and confined transverse texture.

The PDF object type does not establish wall semantics. Two continuous banks,
wall-scale spacing, repeated transverse strokes confined *inside* those banks,
and a supported structural contact are required together. Native gap endpoints
are retained; no line extrapolation, room-box conversion or proximity snapping.
Raster-only documents keep their existing detector unchanged.
"""
import json
import math

import numpy as np

from app.ai.floor_plan_interpretation.candidate import (
    CandidateCollection, CandidateWarning, PixelPoint, WallCandidate,
)

VERSION = 'native-confined-hatch-wall-bands-v2'
CONFIGURATION = dict(version=VERSION, maximum_source_segments=30000,
                     maximum_boundary_pairs=12000, maximum_bands=300,
                     maximum_spatial_references=250000, maximum_segment_cells=512,
                     minimum_transverse_strokes=5, minimum_texture_coverage=.65,
                     maximum_texture_gap_ratio=.23, angular_tolerance_degrees=1.)


def _bounds(a, b, padding=0.):
    return [min(a[0], b[0])-padding, min(a[1], b[1])-padding,
            max(a[0], b[0])+padding, max(a[1], b[1])+padding]


class _SegmentIndex:
    def __init__(self, rows, cell_size):
        self.rows = rows
        self.cell_size = cell_size
        self.cells = {}
        self.exceeded = False
        references=0
        for i, row in enumerate(rows):
            keys=self._keys(_bounds(row['a'], row['b']))
            if keys is None or references+len(keys)>CONFIGURATION['maximum_spatial_references']:
                self.exceeded=True
                self.cells.clear()
                return
            references+=len(keys)
            for key in keys:
                self.cells.setdefault(key, []).append(i)

    def _keys(self, bounds):
        a, b, c, d = [math.floor(v/self.cell_size) for v in bounds]
        if (c-a+1)*(d-b+1)>CONFIGURATION['maximum_segment_cells']:return None
        return [(x,y) for x in range(a,c+1) for y in range(b,d+1)]

    def query(self, bounds):
        keys=self._keys(bounds)
        # Queries over a whole diagonal view remain bounded by source rows. The
        # reference limit is enforced before any grid membership allocation.
        indices = range(len(self.rows)) if keys is None else sorted(set(i for key in keys for i in self.cells.get(key, ())))
        a,b,c,d = bounds
        return [self.rows[i] for i in indices if self.rows[i]['bounds'][0]<=c
                and self.rows[i]['bounds'][2]>=a and self.rows[i]['bounds'][1]<=d
                and self.rows[i]['bounds'][3]>=b]


def _source_segments(index, bounds):
    rows = []
    for obj in index.query(bounds):
        color = obj.get('stroke_color') or [0,0,0,255]
        if (not obj.get('stroke') or obj.get('fill_mode') or obj.get('dash_array')
                or obj.get('clip_paths') or obj.get('level')
                or max(color[:3])-min(color[:3])>20 or min(color[:3])>160):
            continue
        previous = None
        for c in obj.get('commands', ()):
            if c[0]==2:
                previous = np.array(c[1:3], dtype=float)
                continue
            if c[0]!=0:
                previous = None  # Never replace a curve by its chord.
                continue
            end = np.array(c[1:3], dtype=float)
            if previous is not None:
                length = float(np.linalg.norm(end-previous))
                if length>1.:
                    a,b = previous,end
                    if tuple(a)>tuple(b):a,b=b,a
                    box = _bounds(a,b)
                    if bounds[0]<=box[0] and bounds[1]<=box[1] and box[2]<=bounds[2] and box[3]<=bounds[3]:
                        rows.append(dict(a=a,b=b,length=length,axis=(b-a)/length,
                                         bounds=box,object_id=obj['id']))
                        if len(rows)>CONFIGURATION['maximum_source_segments']:
                            return None
            previous = end
    return rows


def _texture_evidence(a, b, axis, normal, spacing, lines):
    length = float(np.linalg.norm(b-a))
    offsets=[];ids=[]
    tolerance = max(.25,spacing*.12)
    for row in lines:
        c,d = row['a'],row['b']
        longitudinal = sorted(float((p-a)@axis) for p in (c,d))
        transverse = sorted(float((p-a)@normal) for p in (c,d))
        if (longitudinal[0]<-tolerance or longitudinal[1]>length+tolerance
                or transverse[0]<-spacing/2-tolerance or transverse[1]>spacing/2+tolerance
                or transverse[0]>-spacing*.15 or transverse[1]<spacing*.15
                or longitudinal[1]-longitudinal[0]>spacing*2):
            continue
        offsets.append((longitudinal[0]+longitudinal[1])/2)
        ids.append(row['object_id'])
    ordered = sorted(set(round(v,3) for v in offsets))
    if len(ordered)<CONFIGURATION['minimum_transverse_strokes']:
        return None, 'insufficient_confined_transverse_strokes'
    coverage=(ordered[-1]-ordered[0])/length
    gaps=np.diff([0.,*ordered,length])
    if coverage<CONFIGURATION['minimum_texture_coverage'] or max(gaps)>length*CONFIGURATION['maximum_texture_gap_ratio']:
        return None, 'texture_does_not_cover_boundary_span'
    return dict(transverse_ids=sorted(set(ids))[:32], transverse_count=len(ordered),
                texture_coverage=round(coverage,5)), None


def _same_band(first, second):
    axis=first['axis'];normal=np.array([-axis[1],axis[0]])
    if abs(float(axis@second['axis']))<.9998:return False
    tolerance=min(first['width'],second['width'])*.30
    if max(abs(float((p-first['a'])@normal)) for p in (second['a'],second['b']))>tolerance:return False
    length=float(np.linalg.norm(first['b']-first['a']))
    lo,hi=sorted(float((p-first['a'])@axis) for p in (second['a'],second['b']))
    return min(length,hi)-max(0.,lo)>=min(length,second['length'])*.75


def _supported_contact(first, second):
    # Only observed strip footprints touching, not a broad proximity radius.
    if abs(float(first['axis']@second['axis']))>.90:return False
    v=first['b']-first['a'];u=second['b']-second['a'];delta=second['a']-first['a']
    cross=lambda a,b:float(a[0]*b[1]-a[1]*b[0])
    determinant=cross(v,u)
    if abs(determinant)>1e-8:
        t=cross(delta,u)/determinant;s=cross(delta,v)/determinant
        if 0<=t<=1 and 0<=s<=1:return True  # Observed interior T/X contact.
    for source,target in ((first,second),(second,first)):
        normal=np.array([-target['axis'][1],target['axis'][0]])
        for point in (source['a'],source['b']):
            t=float((point-target['a'])@target['axis'])
            if (-target['width']/2<=t<=target['length']+target['width']/2
                    and abs(float((point-target['a'])@normal))<=(source['width']+target['width'])/2):
                return True
    return False


def native_wall_bands(payload, index, diagnostics=None):
    """Return recognized bands with primitive identities, never reviewed truth."""
    result=[]
    diagnostics = diagnostics if diagnostics is not None else []
    for region in payload.regions:
        if region.kind!='plan_region' or region.bounds is None:continue
        b=region.bounds;box=[b.x,b.y,b.x+b.width,b.y+b.height]
        lines=_source_segments(index,box)
        if lines is None:
            diagnostics.append(dict(reason='source_segment_budget_exceeded',region_id=region.id))
            continue
        # Typical wall width is evidence, not an assumed real-world measurement.
        widths=[w.estimated_thickness_pixels for w in payload.walls.items
                if w.estimated_thickness_pixels and b.x<=w.start.x<=b.x+b.width and b.y<=w.start.y<=b.y+b.height]
        typical=float(np.median(widths)) if widths else min(b.width,b.height)*.012
        minimum=max(2.5,typical*.45)
        maximum=min(typical*1.8,min(b.width,b.height)*.035)
        span=max(24.,typical*5,min(b.width,b.height)*.035)
        lookup=_SegmentIndex(lines,max(32.,maximum*4))
        if lookup.exceeded:
            diagnostics.append(dict(reason='spatial_reference_budget_exceeded',region_id=region.id))
            continue
        candidates=[];tested=set();pair_count=0
        angle=math.cos(math.radians(CONFIGURATION['angular_tolerance_degrees']))
        for row in lines:
            if row['length']<span:continue
            a,axis=row['a'],row['axis'];normal=np.array([-axis[1],axis[0]])
            nearby=lookup.query(_bounds(row['a'],row['b'],maximum+1))
            for mate in nearby:
                if mate is row or mate['length']<span or abs(float(axis@mate['axis']))<angle:continue
                key=tuple(sorted((id(row),id(mate))))
                if key in tested:continue
                tested.add(key)
                offsets=[float((p-a)@normal) for p in (mate['a'],mate['b'])]
                signed=sum(offsets)/2;spacing=abs(signed)
                if not minimum<=spacing<=maximum or abs(offsets[0]-offsets[1])>max(.5,spacing*.15):continue
                lo=max(0.,min(float((p-a)@axis) for p in (mate['a'],mate['b'])))
                hi=min(row['length'],max(float((p-a)@axis) for p in (mate['a'],mate['b'])))
                if hi-lo<max(span,spacing*5):continue
                pair_count+=1
                if pair_count>CONFIGURATION['maximum_boundary_pairs']:break
                start=a+axis*lo+normal*signed/2;end=a+axis*hi+normal*signed/2
                local=lookup.query(_bounds(start,end,spacing/2+1))
                evidence,reason=_texture_evidence(start,end,axis,normal,spacing,local)
                record=dict(start=start.tolist(),end=end.tolist(),width=spacing,
                            bank_ids=sorted(set((row['object_id'],mate['object_id']))),region_id=region.id)
                if reason:
                    if diagnostics is not None:diagnostics.append(dict(**record,reason=reason))
                    continue
                # Long inner rails identify glass/frame grids, not a hatched core.
                def inner_rail(s):
                    if abs(float(axis@s['axis']))<=angle:return False
                    rail_lo,rail_hi=sorted(float((p-start)@axis) for p in (s['a'],s['b']))
                    overlap=min(hi-lo,rail_hi)-max(0.,rail_lo)
                    return overlap>=(hi-lo)*.8 and max(abs(float((p-start)@normal))
                        for p in (s['a'],s['b']))<spacing*.28
                inner=any(inner_rail(s) for s in local)
                if inner:
                    diagnostics.append(dict(**record,reason='sustained_inner_frame_bank'))
                    continue
                candidates.append(dict(a=start,b=end,axis=axis,length=hi-lo,width=spacing,
                                       evidence={**record,**evidence},region_id=region.id))
            if pair_count>CONFIGURATION['maximum_boundary_pairs']:break
        if pair_count>CONFIGURATION['maximum_boundary_pairs']:
            diagnostics.append(dict(reason='boundary_pair_budget_exceeded',region_id=region.id))
            continue  # No silently truncated wall recognition.
        kept=[]
        for row in sorted(candidates,key=lambda r:(-r['length'],*r['a'],*r['b'])):
            if any(_same_band(row,prior) for prior in kept):
                diagnostics.append(dict(**row['evidence'],reason='duplicate_same_observed_band'))
            else:kept.append(row)
        # Free-floating furniture strips can use the same hatch convention. A
        # supported perpendicular band contact is required for NEW proposals.
        for row in kept:
            connected=any(other is not row and _supported_contact(row,other) for other in kept)
            if not connected:
                diagnostics.append(dict(**row['evidence'],reason='no_supported_structural_contact'))
                continue
            diagnostics.append(dict(**row['evidence'],reason='retained_native_hatched_band'))
            result.append(row)
    if len(result)>CONFIGURATION['maximum_bands']:
        diagnostics.append(dict(reason='wall_band_budget_exceeded'))
        return []
    return result


def with_pdf_wall_recognition(payload, image_rgb, index, diagnostics=None):
    if not isinstance(image_rgb,np.ndarray) or image_rgb.shape!=(payload.source_plane.height_pixels,payload.source_plane.width_pixels,3):
        raise ValueError('PDF wall recognition requires matching source pixels.')
    # Existing opening references must not be detached by proposal refinement.
    if payload.openings.items:return payload
    bands=native_wall_bands(payload,index,diagnostics)
    if not bands or len(payload.warnings)+len(bands)>256:return payload
    walls=list(payload.walls.items);next_id=max([int(w.id.rsplit('-',1)[-1]) for w in walls] or [0])+1
    warnings=[]
    protected={reference for warning in payload.warnings for reference in warning.entity_refs}
    protected.update(reference for connection in payload.observed_routes.connections
                     for reference in (connection.from_ref,connection.to_ref))
    for row in bands:
        # A recognized narrow core inside a wider existing wall is supporting
        # evidence, not a second parallel wall. Keep that wider observed span.
        contained=False
        for wall in walls:
            if not wall.estimated_thickness_pixels:continue
            a=np.array([wall.start.x,wall.start.y]);b=np.array([wall.end.x,wall.end.y]);length=float(np.linalg.norm(b-a));axis=(b-a)/length
            if abs(float(axis@row['axis']))<.9998:continue
            normal=np.array([-axis[1],axis[0]])
            lo,hi=sorted(float((p-a)@axis) for p in (row['a'],row['b']))
            distance=max(abs(float((p-a)@normal)) for p in (row['a'],row['b']))
            if lo>=0 and hi<=length and distance+row['width']/2<=wall.estimated_thickness_pixels/2:
                contained=True;break
        if contained:
            if diagnostics is not None:diagnostics.append(dict(**row['evidence'],reason='already_inside_existing_wall_footprint'))
            continue
        candidate=WallCandidate(id=f'wall-{next_id:04d}',
            start=PixelPoint(x=float(row['a'][0]),y=float(row['a'][1])),
            end=PixelPoint(x=float(row['b'][0]),y=float(row['b'][1])),
            estimated_thickness_pixels=row['width'],evidence_refs=(f"region:{row['region_id']}",),ambiguity='ambiguous')
        duplicates=[]
        for wall in walls:
            a=np.array([wall.start.x,wall.start.y]);b=np.array([wall.end.x,wall.end.y]);length=float(np.linalg.norm(b-a))
            prior=dict(a=a,b=b,axis=(b-a)/length,length=length,width=wall.estimated_thickness_pixels or row['width'])
            if _same_band(row,prior) and length<=row['length']+row['width']*2:duplicates.append(wall)
        # Keep identity when one recognized source band refines a CV hypothesis.
        if duplicates:
            referenced=[w for w in duplicates if f'wall:{w.id}' in protected]
            if len(referenced)>1:
                if diagnostics is not None:diagnostics.append(dict(**row['evidence'],reason='referenced_wall_identities_prevent_refinement'))
                continue
            identity=(referenced or duplicates)[0].id
            candidate=candidate.model_copy(update={'id':identity})
            walls=[w for w in walls if w not in duplicates]
        else:next_id+=1
        walls.append(candidate)
        warnings.append(CandidateWarning(code='pdf_native_hatched_wall_band',severity='info',
            entity_refs=(f'wall:{candidate.id}',),
            message='Native paired-bank wall proposal (not approved): '+json.dumps(
                {k:v for k,v in row['evidence'].items() if k!='region_id'},separators=(',',':'))))
    if not warnings or len(walls)>CONFIGURATION['maximum_bands']:return payload
    return type(payload).model_validate(payload.model_copy(update={
        'walls':CandidateCollection(state='partial',items=tuple(sorted(walls,key=lambda w:w.id)),truncated=payload.walls.truncated),
        'rooms':CandidateCollection(state='unavailable'),'warnings':payload.warnings+tuple(warnings),
        'document_state':'partial'}).model_dump())
