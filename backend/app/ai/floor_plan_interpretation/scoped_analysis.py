"""One coordinated envelope from independently processed source views.

Scopes retain page coordinates and distinct evidence identities. Postprocessing
must happen inside each callback, before merge; no cross-view fusion or routing.
"""
from app.ai.floor_plan_interpretation.candidate import (
    AffineTransform,CandidateCollection,CandidateWarning,EvidenceRegion,FloorPlanInterpretationPayload,
    ObservedRoutes,PageAssessment,PageSignals,PixelBounds,SourcePlane,SCHEMA_VERSION,
)

VERSION='independent-source-view-layer-outcomes-v2'
COLLECTIONS=('ocr','scales','walls','rooms','openings','symbols','panels')
PREFIXES=dict(ocr='ocr',scales='scale',walls='wall',rooms='room',openings='opening',
              symbols='symbol',panels='panel',segments='segment',connections='connection',regions='region')


def raster_configuration_versions():
    """Pin geometry/contact algorithms, not only the detector checkpoint."""
    from app.ai.floor_plan_interpretation.demo_cv import EVIDENCE_VERSION as cv_version
    from app.ai.floor_plan_interpretation.automatic_wiring import EVIDENCE_VERSION as wire_version
    from app.ai.floor_plan_interpretation.device_contact_evidence import EVIDENCE_VERSION as contact_version
    from app.ai.floor_plan_interpretation.fixture_wiring import CONFIGURATION as fixture_configuration
    from app.ai.floor_plan_interpretation.wiring_recovery import VERSION as recovery_version, RecoveryLimits
    from dataclasses import asdict
    from app.ai.ocr.local_words import VERSION as ocr_version
    return dict(geometry=cv_version, observed_wiring=wire_version, device_contacts=contact_version,dimension_ocr=ocr_version,
                fixture_axis=dict(fixture_configuration),recovery_version=recovery_version,recovery_limits=asdict(RecoveryLimits()))


def native_configuration_versions():
    """Pin native evidence and view orchestration for every CV provider."""
    from app.ai.floor_plan_interpretation.pdf_evidence import VERSION as pdf_version
    from app.ai.floor_plan_interpretation.pdf_views import VERSION as view_version
    from app.ai.floor_plan_interpretation.pdf_wall_evidence import VERSION as wall_version
    from app.ai.floor_plan_interpretation.pdf_wall_recognition import VERSION as native_wall_version
    from app.ai.floor_plan_interpretation.pdf_observed_wiring import VERSION as native_wire_version
    return dict(source_evidence=pdf_version, view_scopes=view_version,
                wall_evidence=wall_version, wall_recognition=native_wall_version,
                wiring_recognition=native_wire_version, orchestration=VERSION)


def failed_geometry_payload(width,height):
    """Allow independent trained-symbol evidence, without claiming CV success."""
    unavailable=CandidateCollection(state='unavailable')
    failed=CandidateCollection(state='failed',failure_reason='Raster geometry evidence could not be extracted.')
    return FloorPlanInterpretationPayload(schema_version=SCHEMA_VERSION,document_state='partial',
        source_plane=SourcePlane(width_pixels=width,height_pixels=height),
        page=PageAssessment(page_type='unknown',quality='unknown',signals=PageSignals(
            electrical_content='unknown',legend='unknown',dimensions='unknown',scale_evidence='unknown',observed_wiring='unknown')),
        regions=(EvidenceRegion(id='region-0001',kind='plan_region',
            bounds=PixelBounds(x=0,y=0,width=width,height=height),
            local_to_source=AffineTransform(a=1,b=0,c=0,d=1,e=0,f=0)),),
        walls=failed,rooms=failed,ocr=unavailable,scales=unavailable,openings=unavailable,
        symbols=unavailable,panels=unavailable,observed_routes=ObservedRoutes(state='unavailable'),
        warnings=(CandidateWarning(code='geometry_layer_failed',severity='warning',
            message='Raster wall/room extraction failed. Other layers remain proposals, not a complete analysis.'),))


def failed_wiring_payload(payload):
    return type(payload).model_validate(payload.model_copy(update={
        'document_state':'partial',
        'observed_routes':ObservedRoutes(state='failed',failure_reason='Observed wiring extraction could not be completed.'),
        'warnings':payload.warnings+(CandidateWarning(code='wiring_layer_failed',severity='warning',
            message='Observed wiring extraction failed; wall and symbol proposals remain editable. No replacement routes were invented.'),),
    }).model_dump())


def merge_view_payloads(payloads):
    if not 1<=len(payloads)<=8:
        raise ValueError('Source view count exceeds the bounded analysis contract.')
    planes={p.source_plane.model_dump_json() for p in payloads}
    if len(planes)!=1:raise ValueError('Source views must use one exact page coordinate plane.')
    counters={key:0 for key in PREFIXES}
    rows=[]
    for payload in payloads:
        row=payload.model_dump(mode='json')
        mapping={}
        lists={key:row[key]['items'] for key in COLLECTIONS}
        lists.update(regions=row['regions'],segments=row['observed_routes']['segments'],
                     connections=row['observed_routes']['connections'])
        for key,items in lists.items():
            for item in items:
                counters[key]+=1
                old=item['id'];new=f'{PREFIXES[key]}-{counters[key]:04d}'
                mapping[old]=new
                item['id']=new
        def ref(value):
            kind,identity=value.split(':',1)
            return f'{kind}:{mapping[identity]}'
        for key,items in lists.items():
            for item in items:
                if 'evidence_refs' in item:item['evidence_refs']=sorted(ref(v) for v in item['evidence_refs'])
                if key=='ocr':item['region_id']=mapping[item['region_id']]
                if key=='openings' and item['wall_ref']:item['wall_ref']=mapping[item['wall_ref']]
                if key=='connections':
                    item['from_ref'],item['to_ref']=ref(item['from_ref']),ref(item['to_ref'])
        for warning in row['warnings']:
            warning['entity_refs']=sorted(ref(v) for v in warning['entity_refs'])
        rows.append(row)
    result=rows[0]
    for key in COLLECTIONS:
        states=[r[key]['state'] for r in rows]
        items=[item for r in rows for item in r[key]['items']]
        truncated=any(r[key]['truncated'] for r in rows)
        state=('partial' if items and (truncated or any(s in ('partial','failed','unavailable') for s in states))
               else 'completed' if items else 'failed' if 'failed' in states else
               'unavailable' if 'unavailable' in states else 'empty')
        result[key]=dict(state=state,items=items,truncated=truncated,
                        failure_reason='One or more source views failed extraction.' if state=='failed' else None)
    result['regions']=[item for r in rows for item in r['regions']]
    result['warnings']=[w for r in rows for w in r['warnings']]
    route_segments=[item for r in rows for item in r['observed_routes']['segments']]
    route_states=[r['observed_routes']['state'] for r in rows]
    route_state=('partial' if route_segments or 'partial' in route_states else
                 'failed' if 'failed' in route_states else 'unavailable' if 'unavailable' in route_states else 'empty')
    result['observed_routes']=dict(state=route_state,
        segments=route_segments,
        connections=[item for r in rows for item in r['observed_routes']['connections']],
        truncated=any(r['observed_routes']['truncated'] for r in rows),
        failure_reason='One or more source views failed wiring extraction.' if route_state=='failed' else None)
    result['document_state']='partial'
    result['warnings'].append(CandidateWarning(code='separate_source_views',severity='warning',
        message='Caption-supported drawing regions were processed independently. Their extents are partial proposals; '
                'outside content is unreviewed, not empty. Select one drawing region before measured floor publication.').model_dump())
    return FloorPlanInterpretationPayload.model_validate(result)
