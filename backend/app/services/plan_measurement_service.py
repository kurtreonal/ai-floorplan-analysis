"""Paper/nominal-scale inputs never substitute for approved pixel calibration."""
from io import BytesIO
from contextlib import closing
from threading import RLock
from functools import lru_cache
import math
import re
from PIL import Image
from pypdf import PdfReader
from sqlalchemy import select
from app.models import FloorPlan,ProjectFloor,FloorElevationSetting
from app.repositories.analysis_settings_repository import latest_elevation
from app.repositories import plan_measurement_repository as repository
from app.repositories.floor_plan_lifecycle_repository import active_floor_plan
from app.schemas.plan_measurement import PlanMeasurementInput
from app.services.project_service import get_accessible_project

PAPER_MM={'A5':(148,210),'A4':(210,297),'A3':(297,420),'A2':(420,594),'A1':(594,841),'A0':(841,1189)}
_MARKER_LOCK=RLock()


@lru_cache(maxsize=8)
def _pdf_scale_markers(content,page_number):
    """Caption evidence only; PDFium maps text through the raster's own transform."""
    import pypdfium2 as pdfium
    from app.ai.floor_plan_interpretation.pdf_evidence import page_to_source
    markers=[]
    try:
        with _MARKER_LOCK,closing(pdfium.PdfDocument(content)) as pdf:
            page=pdf[page_number-1]
            with closing(page):
                pw,ph=page.get_size();width=1000;height=max(1,round(1000*ph/pw))
                if height>4096:return []
                matrix=page_to_source(page,width,height)
                with closing(page.get_textpage()) as text:
                    seen=set()
                    for term in ('1','NTS','N.T.S','N T S','NOT TO SCALE'):
                        search=text.search(term)
                        try:
                            for _ in range(1024):
                                hit=search.get_next()
                                if hit is None:break
                                index,count=hit
                                if index in seen:continue
                                ratio=None
                                if term=='1':
                                    match=re.match(r'1\s*:\s*(\d+(?:\.\d+)?)',text.get_text_range(index,min(24,text.count_chars()-index)))
                                    if not match:continue
                                    ratio=float(match[1])
                                    if not 1<=ratio<=100000:continue
                                left,bottom,right,top=text.get_charbox(index)
                                x,y=matrix.on_point((left+right)/2,(bottom+top)/2)
                                markers.append(dict(x=x/width,y=y/height,denominator=ratio,not_to_scale=term!='1'))
                                seen.add(index)
                                if len(markers)>=256:return markers
                        finally:search.close()
    except (ValueError,RuntimeError,OSError):
        return []
    return markers


class MeasurementSettingsError(ValueError):
    def __init__(self,status,message):
        self.status=status;super().__init__(message)


def source_metadata(content,mime):
    if mime=='application/pdf':
        result=[]
        for number,page in enumerate(PdfReader(BytesIO(content),strict=False).pages,1):
            unit=float(page.get('/UserUnit',1))
            width,height=float(page.mediabox.width)*unit*25.4/72,float(page.mediabox.height)*unit*25.4/72
            if any(not math.isfinite(v) or v<=0 or v>100000 for v in (width,height)):
                continue
            rotation=int(page.rotation)%360
            paper=next((name for name,dims in PAPER_MM.items() if all(abs(a-b)<=2 for a,b in zip(sorted((width,height)),dims))),None)
            w,h=(height,width) if rotation in (90,270) else (width,height)
            left,bottom=max(float(page.cropbox.left),float(page.mediabox.left)),max(float(page.cropbox.bottom),float(page.mediabox.bottom))
            right,top=min(float(page.cropbox.right),float(page.mediabox.right)),min(float(page.cropbox.top),float(page.mediabox.top))
            rendered_width,rendered_height=(right-left)*unit*25.4/72,(top-bottom)*unit*25.4/72
            if rotation in (90,270):rendered_width,rendered_height=rendered_height,rendered_width
            fallback_markers=[]
            def caption(value,cm,tm,font,size):
                # Some valid PDFs expose text to pypdf but not PDFium. Short
                # caption runs have one unambiguous text origin; large merged
                # blocks are deliberately not used to assign a plan's scale.
                if len(value)>80 or len(fallback_markers)>=256:return
                ratio=re.search(r'\b1\s*:\s*(\d+(?:\.\d+)?)',value)
                nts=bool(re.search(r'\bN\s*\.?\s*T\s*\.?\s*S(?:\b|SCALE)|NOT\s+TO\s+SCALE',value,re.I))
                if not ratio and not nts:return
                if ratio and not 1<=float(ratio[1])<=100000:return
                x=tm[4]*cm[0]+tm[5]*cm[2]+cm[4];y=tm[4]*cm[1]+tm[5]*cm[3]+cm[5]
                u,v=(x-left)/(right-left),(top-y)/(top-bottom)
                if rotation==90:u,v=1-v,u
                elif rotation==180:u,v=1-u,1-v
                elif rotation==270:u,v=v,1-u
                if 0<=u<=1 and 0<=v<=1:
                    fallback_markers.append(dict(x=u,y=v,denominator=float(ratio[1]) if ratio else None,not_to_scale=nts))
            text=page.extract_text(visitor_text=caption) or ''
            ratios=sorted({float(value) for value in re.findall(r'\b1\s*:\s*(\d+(?:\.\d+)?)',text) if 1<=float(value)<=100000})
            has_nts=bool(re.search(r'\bN\s*\.?\s*T\s*\.?\s*S(?:\b|SCALE)|NOT\s+TO\s+SCALE',text,re.I))
            result.append(dict(page_number=number,paper_size=paper,orientation='landscape' if w>h else 'portrait',
                page_width_mm=width,page_height_mm=height,rotation_degrees=rotation,
                rendered_width_mm=rendered_width,rendered_height_mm=rendered_height,
                drawing_scale_denominators=ratios,has_not_to_scale=has_nts,
                scale_markers=_pdf_scale_markers(content,number) or fallback_markers,
                cropped=tuple(page.cropbox)!=tuple(page.mediabox),basis='pdf_page_metadata',calibrated=False))
        return result
    with Image.open(BytesIO(content)) as image:
        exif=image.getexif().get(274,1)
        width,height=(image.height,image.width) if exif in (5,6,7,8) else image.size
        return [dict(page_number=1,paper_size=None,orientation='landscape' if width>height else 'portrait',
            width_pixels=image.width,height_pixels=image.height,exif_orientation=exif,
            basis='image_metadata_not_paper_calibration',calibrated=False)]


def effective(settings,source,defaults=None):
    values=settings.model_dump()
    pages=[dict(page,paper_size=values['paper_size'] or page.get('paper_size') or (defaults or {}).get('paper_size','A1'),
        orientation=values['orientation'] or page.get('orientation') or 'portrait',
        paper_basis='user_input' if values['paper_size'] else 'source_metadata' if page.get('paper_size') else 'admin_default' if defaults else 'input_default',
        scale_denominator=values['scale_denominator'],scale_basis='nominal_input_not_calibration') for page in source]
    return dict(settings=values,pages=pages,source_pages=source)


def initial(session,plan,user_id,data,content):
    from uuid import uuid4
    from app.services.application_defaults_service import retrieve as shared_defaults
    from app.services.automatic_plan_setup import automatic_settings
    shared=shared_defaults(session);defaults=shared['settings']
    values=automatic_settings(data.model_dump(),defaults,shared['revision'])
    # Explicit upload inputs remain authoritative, including existing integrations.
    values.update(data.model_dump(include=data.model_fields_set))
    if data.model_fields_set & {'service_height_above_floor_meters','fixture_center_height_meters','fixture_connection_height_meters','service_elevation_meters'}:
        values['height_mode']='custom'
    data=PlanMeasurementInput.model_validate(values)
    document=effective(data,source_metadata(content,plan.mime_type),defaults)
    _save_floor_input(session,plan,user_id,data.floor_elevation_meters)
    return repository.append(session,floor_plan_id=plan.id,revision=1,request_id=str(uuid4()),actor_user_id=user_id,document=document)


def _save_floor_input(session,plan,user_id,value):
    if value is None:return  # An upload default never clears an existing datum.
    repository.lock_floor(session,plan.project_floor_id)
    current=session.scalar(select(FloorElevationSetting).where(FloorElevationSetting.project_floor_id==plan.project_floor_id)
        .order_by(FloorElevationSetting.id.desc()).limit(1).with_for_update())
    if current is None or current.elevation_meters is None or float(current.elevation_meters)!=value:
        session.add(FloorElevationSetting(project_floor_id=plan.project_floor_id,elevation_meters=value,
            reviewed_by_user_id=user_id,evidence_notes='Designer-entered floor elevation from plan measurement settings; metres from project datum.'))


def _plan(session,user,project_id,plan_id,write=False):
    get_accessible_project(session,current_user=user,project_id=project_id)
    if write and user.role.name!='DESIGNER':raise MeasurementSettingsError(403,'Only a Designer can change plan measurements.')
    query=select(FloorPlan).join(ProjectFloor).where(FloorPlan.id==plan_id,ProjectFloor.project_id==project_id,active_floor_plan())
    plan=session.scalar(query)
    if plan is None:raise MeasurementSettingsError(404,'Floor plan not found.')
    if write:
        repository.lock_floor(session,plan.project_floor_id)
        plan=session.scalar(query.with_for_update())
        if plan is None:raise MeasurementSettingsError(404,'Floor plan not found.')
    return plan


def _context_run(session,plan_id,job_id):
    if job_id is None:return None
    from app.models import FloorPlanInterpretationRun
    run=session.scalar(select(FloorPlanInterpretationRun).where(
        FloorPlanInterpretationRun.floor_plan_id==plan_id,FloorPlanInterpretationRun.processing_job_id==job_id))
    if run is None:raise MeasurementSettingsError(404,'Analysis view not found for this plan.')
    from hashlib import sha256
    if sha256(run.candidate_json.encode()).hexdigest()!=run.candidate_sha256:
        raise MeasurementSettingsError(409,'Source identity changed. Reload the plan.')
    return run


def retrieve(session,user,project_id,plan_id,processing_job_id=None):
    plan=_plan(session,user,project_id,plan_id)
    row=repository.current(session,plan_id)
    return _response(session,plan,row,_context_run(session,plan_id,processing_job_id))


def stored_source_metadata(plan):
    """Recover metadata for existing uploads without modifying original bytes."""
    from app.core.config import get_upload_directory
    from app.services.source_identity import resolve_stored_original
    try:
        original=resolve_stored_original(get_upload_directory(),plan.storage_path)
        return source_metadata(original.read_bytes(),plan.mime_type)
    except (OSError,ValueError,RuntimeError):
        # Legacy records may predate durable originals. Keep settings readable,
        # but never invent paper dimensions for an unavailable source.
        return []


def _response(session,plan,row,run=None):
    floor=latest_elevation(session,plan.project_floor_id)
    document=row.document if row else effective(PlanMeasurementInput(),stored_source_metadata(plan))
    if row and plan.mime_type=='application/pdf' and any('rendered_width_mm' not in p for p in document.get('source_pages',[])):
        document=effective(PlanMeasurementInput.model_validate(document['settings']),stored_source_metadata(plan))
    context,metric=None,None
    if run is not None:
        from app.services.measurement_bindings import settings_for_run
        from app.services.draft_scale_service import source_scale
        from app.services.demo_interpretation_service import _candidate
        from app.repositories.analysis_settings_repository import latest_scales
        values,context=settings_for_run(document,run)
        from app.services.application_defaults_service import effective as shared_defaults
        values.setdefault('source_paper_size',shared_defaults(session)['paper_size'])
        document=dict(document,settings=PlanMeasurementInput.model_validate({k:v for k,v in values.items() if not k.startswith('_')}).model_dump())
        candidate=_candidate(run)
        metric=source_scale(session,run,candidate.payload.source_plane,latest_scales(session,[run.floor_plan_page_id]).get(run.floor_plan_page_id),
            multiple_views=any(w.code=='separate_source_views' for w in candidate.payload.warnings),document_override=row.document if row else document)
        if values.get('measurement_method','auto')=='auto' and not values.get('drawing_scale_confirmed'):
            document['settings']['scale_denominator']=metric.get('scale_denominator') or document['settings']['scale_denominator']
    return dict(floor_plan_id=plan.id,revision=row.revision if row else 0,
        floor_elevation_meters=float(floor.elevation_meters) if floor and floor.elevation_meters is not None else None,
        **{k:v for k,v in document.items() if k!='measurement_views'},measurement_context=context,effective_measurement=metric)


def save(session,user,project_id,plan_id,data):
    plan=_plan(session,user,project_id,plan_id,write=True)
    run=_context_run(session,plan_id,data.processing_job_id)
    requested=PlanMeasurementInput.model_validate(data.model_dump(exclude={'expected_revision','request_id','processing_job_id','use_automatic_setup'}))
    previous=repository.retry(session,plan_id,data.request_id)
    if previous:
        submitted=previous.document.get('submitted_settings',previous.document['settings'])
        if (PlanMeasurementInput.model_validate(submitted)!=requested or previous.document.get('submitted_job_id')!=data.processing_job_id
            or previous.document.get('submitted_automatic_setup',False)!=data.use_automatic_setup):
            raise MeasurementSettingsError(409,'Retry inputs changed. Reload plan settings.')
        return _response(session,plan,previous,run)
    current=repository.current(session,plan_id,lock=True)
    revision=current.revision if current else 0
    if revision!=data.expected_revision:raise MeasurementSettingsError(409,'Plan settings changed. Reload before saving.')
    from app.services.measurement_bindings import settings_for_run,DISPLAY_FIELDS,run_binding
    bound_values=settings_for_run(current.document if current else {},run)[0] if run is not None else {}
    settings=requested
    if data.use_automatic_setup:
        if run is None:raise MeasurementSettingsError(422,'Open the plan view before applying automatic setup.')
        from app.services.application_defaults_service import retrieve as shared_defaults
        from app.services.automatic_plan_setup import automatic_settings
        shared=shared_defaults(session)
        values=dict(bound_values)
        if values.get('_transform_invalid'):
            # Reset may replace a broken assumption, never certify a distorted
            # inherited reference as a new distance calibration.
            values.update(reference=None,measurement_method='auto',full_sheet_confirmed=False)
        settings=PlanMeasurementInput.model_validate(automatic_settings({k:v for k,v in values.items() if not k.startswith('_')},shared['settings'],shared['revision']))
    if run is None and settings.measurement_method!='auto':
        raise MeasurementSettingsError(422,'Open the plan view before changing its measurement basis.')
    if run is not None and settings.reference:
        from app.services.measurement_bindings import run_binding
        binding=run_binding(run)
        if any(p.x>binding['width_pixels'] or p.y>binding['height_pixels'] for p in (settings.reference.start,settings.reference.end)):
            raise MeasurementSettingsError(422,'Reference endpoints must be inside this source page.')
        region=binding['region']
        reference_changed=settings.reference.model_dump()!=bound_values.get('reference')
        if reference_changed and region and any(not(region['x']-1e-6<=p.x/binding['width_pixels']<=region['x']+region['width']+1e-6 and
                              region['y']-1e-6<=p.y/binding['height_pixels']<=region['y']+region['height']+1e-6)
                          for p in (settings.reference.start,settings.reference.end)):
            raise MeasurementSettingsError(422,'Place the reference endpoints inside the selected plan area.')
        if settings.reference.start==settings.reference.end:
            raise MeasurementSettingsError(422,'Choose two different reference endpoints.')
    source=current.document.get('source_pages') if current else None
    if not source or (plan.mime_type=='application/pdf' and any('rendered_width_mm' not in p for p in source)):
        source=stored_source_metadata(plan)
    views=dict((current.document if current else {}).get('measurement_views') or {})
    global_values=dict((current.document if current else {}).get('settings') or {})
    if run is not None:
        binding=run_binding(run)
        previous_values=PlanMeasurementInput.model_validate({k:v for k,v in bound_values.items() if not k.startswith('_')})
        if data.use_automatic_setup or settings.model_dump(exclude=DISPLAY_FIELDS)!=previous_values.model_dump(exclude=DISPLAY_FIELDS):
            views[binding['binding_id']]=dict(binding=binding,settings=settings.model_dump(exclude=DISPLAY_FIELDS))
        global_values.update({k:v for k,v in settings.model_dump().items() if k in DISPLAY_FIELDS})
    else:global_values.update(settings.model_dump())
    document=effective(PlanMeasurementInput.model_validate(global_values),source)
    document.update(measurement_views=views,submitted_settings=requested.model_dump(),submitted_job_id=data.processing_job_id,
        submitted_automatic_setup=data.use_automatic_setup)
    _save_floor_input(session,plan,user.id,data.floor_elevation_meters)
    row=repository.append(session,floor_plan_id=plan_id,revision=revision+1,request_id=str(data.request_id),actor_user_id=user.id,document=document)
    return _response(session,plan,row,run)
