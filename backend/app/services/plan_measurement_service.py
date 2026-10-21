"""Paper/nominal-scale inputs never substitute for approved pixel calibration."""
from io import BytesIO
import math
from PIL import Image
from pypdf import PdfReader
from sqlalchemy import select
from app.models import FloorPlan,ProjectFloor,FloorElevationSetting
from app.repositories.analysis_settings_repository import latest_elevation
from app.repositories import plan_measurement_repository as repository
from app.repositories.floor_plan_lifecycle_repository import active_floor_plan
from app.schemas.plan_measurement import PlanMeasurementInput
from app.services.project_service import get_accessible_project

PAPER_MM={'A4':(210,297),'A3':(297,420),'A2':(420,594),'A1':(594,841),'A0':(841,1189)}


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
            result.append(dict(page_number=number,paper_size=paper,orientation='landscape' if w>h else 'portrait',
                page_width_mm=width,page_height_mm=height,rotation_degrees=rotation,
                cropped=tuple(page.cropbox)!=tuple(page.mediabox),basis='pdf_page_metadata',calibrated=False))
        return result
    with Image.open(BytesIO(content)) as image:
        exif=image.getexif().get(274,1)
        width,height=(image.height,image.width) if exif in (5,6,7,8) else image.size
        return [dict(page_number=1,paper_size=None,orientation='landscape' if width>height else 'portrait',
            width_pixels=image.width,height_pixels=image.height,exif_orientation=exif,
            basis='image_metadata_not_paper_calibration',calibrated=False)]


def effective(settings,source):
    values=settings.model_dump()
    pages=[dict(page,paper_size=values['paper_size'] or page.get('paper_size') or 'A1',
        orientation=values['orientation'] or page.get('orientation') or 'portrait',
        paper_basis='user_input' if values['paper_size'] else 'source_metadata' if page.get('paper_size') else 'input_default',
        scale_denominator=values['scale_denominator'],scale_basis='nominal_input_not_calibration') for page in source]
    return dict(settings=values,pages=pages,source_pages=source)


def initial(session,plan,user_id,data,content):
    from uuid import uuid4
    document=effective(data,source_metadata(content,plan.mime_type))
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


def retrieve(session,user,project_id,plan_id):
    plan=_plan(session,user,project_id,plan_id)
    row=repository.current(session,plan_id)
    return _response(session,plan,row)


def _response(session,plan,row):
    floor=latest_elevation(session,plan.project_floor_id)
    return dict(floor_plan_id=plan.id,revision=row.revision if row else 0,
        floor_elevation_meters=float(floor.elevation_meters) if floor and floor.elevation_meters is not None else None,
        **(row.document if row else effective(PlanMeasurementInput(),[])))


def save(session,user,project_id,plan_id,data):
    plan=_plan(session,user,project_id,plan_id,write=True)
    settings=PlanMeasurementInput.model_validate(data.model_dump(exclude={'expected_revision','request_id'}))
    previous=repository.retry(session,plan_id,data.request_id)
    if previous:
        if previous.document['settings']!=settings.model_dump():raise MeasurementSettingsError(409,'Retry inputs changed. Reload plan settings.')
        return _response(session,plan,previous)
    current=repository.current(session,plan_id,lock=True)
    revision=current.revision if current else 0
    if revision!=data.expected_revision:raise MeasurementSettingsError(409,'Plan settings changed. Reload before saving.')
    document=effective(settings,current.document['source_pages'] if current else [])
    _save_floor_input(session,plan,user.id,data.floor_elevation_meters)
    row=repository.append(session,floor_plan_id=plan_id,revision=revision+1,request_id=str(data.request_id),actor_user_id=user.id,document=document)
    return _response(session,plan,row)
