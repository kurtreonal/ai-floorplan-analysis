from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from fastapi.responses import Response
from pydantic import BaseModel

from app.api.dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.estimate import EstimateOptions, EstimateResponse, EstimateWrite
from app.schemas.demo_interpretation import DemoReviewRequest
from app.services import estimate_service as service
from app.services.layout_service import LayoutServiceError
from app.services.project_service import ProjectNotFoundError
from app.services.bom_service import reviewed_bom, estimate_csv, planning_csv
from app.services.demo_interpretation_service import DemoInterpretationError
from app.services.bom_spreadsheet import MIME as XLSX_MIME

router = APIRouter(prefix="/api/projects", tags=["estimates"])
ProjectId = Annotated[int, Path(gt=0)]


class BOMResponse(BaseModel):
    project_id: int
    layouts: list[dict]
    missing_layout_floors: list[int]
    components: list[dict]
    route_lengths: dict | None
    route_state: str
    wiring_types: list[dict] = []
    planning: dict


def execute(session, action):
    try:
        return action()
    except (service.EstimateError, LayoutServiceError, DemoInterpretationError, ProjectNotFoundError, SQLAlchemyError, ValueError, LookupError) as error:
        session.rollback()
        if isinstance(error, SQLAlchemyError):
            code, status = "ESTIMATE_STORAGE_UNAVAILABLE", 503
        elif isinstance(error, ProjectNotFoundError):
            code, status = "PROJECT_NOT_FOUND", 404
        elif isinstance(error, LookupError):
            code, status = 'PROJECT_PRICING_NOT_FOUND', 404
        elif isinstance(error, (service.EstimateError, LayoutServiceError, DemoInterpretationError)):
            code = error.code
            status = 403 if code == "AUTHORIZATION_DENIED" else 404 if code.endswith("NOT_FOUND") else 409 if code in {"STALE_ROUTE", "ESTIMATE_RETRY_CONFLICT"} else 422
        else:
            code, status = "INVALID_ESTIMATE_SOURCE", 422
        raise HTTPException(status, detail={"error": {"code": code,
            "message": "The estimate operation could not be completed.", "details": {}}}) from None


@router.get("/{project_id}/estimate-options", response_model=EstimateOptions)
def options(project_id: ProjectId, project_price_version_id: Annotated[int | None, Query(gt=0)] = None,
        user: User = Depends(require_roles("ADMIN", "DESIGNER")), session: Session = Depends(get_db)):
    return execute(session, lambda: service.estimate_options(session, user, project_id, project_price_version_id))


@router.get('/{project_id}/bom', response_model=BOMResponse)
def bom(project_id: ProjectId, floor_plan_id: Annotated[int | None, Query(gt=0)] = None,
        purchase_pricing: Annotated[str | None, Query(max_length=4000)] = None,
        device_materials: Annotated[str | None, Query(max_length=12000)] = None,
        processing_job_id: Annotated[int | None, Query(gt=0)] = None,
        conduit_material_id: Annotated[int | None, Query(gt=0)] = None,
        wire_material_id: Annotated[int | None, Query(gt=0)] = None,
        wire_meters_per_unit: Annotated[float | None, Query(gt=0, le=100000, allow_inf_nan=False)] = None,
        wire_price_per_meter: Annotated[float | None, Query(ge=0, le=1000000000, allow_inf_nan=False)] = None,
        conduit_price_per_meter: Annotated[float | None, Query(ge=0, le=1000000000, allow_inf_nan=False)] = None,
        scale_denominator: Annotated[float | None, Query(ge=1, le=100000, allow_inf_nan=False)] = None,
        paper_size: Annotated[Literal['A5', 'A4', 'A3', 'A2', 'A1', 'A0', 'CUSTOM'] | None, Query()] = None,
        custom_width_mm: Annotated[float | None, Query(gt=0, le=10000, allow_inf_nan=False)] = None,
        custom_height_mm: Annotated[float | None, Query(gt=0, le=10000, allow_inf_nan=False)] = None,
        user: User = Depends(require_roles('ADMIN', 'DESIGNER')), session: Session = Depends(get_db)):
    return execute(session, lambda: reviewed_bom(session, user, project_id,
        floor_plan_id=floor_plan_id, processing_job_id=processing_job_id,device_materials=device_materials,
        conduit_material_id=conduit_material_id, wire_material_id=wire_material_id, paper_size=paper_size,
        conduit_price_per_meter=conduit_price_per_meter, scale_denominator=scale_denominator,
        custom_width_mm=custom_width_mm, custom_height_mm=custom_height_mm,
        wire_meters_per_unit=wire_meters_per_unit, wire_price_per_meter=wire_price_per_meter,purchase_pricing=purchase_pricing))


@router.get('/{project_id}/bom.csv')
def export_draft_bom(project_id: ProjectId, format: Literal['csv', 'xlsx'] = 'csv', floor_plan_id: Annotated[int | None, Query(gt=0)] = None,
        purchase_pricing: Annotated[str | None, Query(max_length=4000)] = None,
        device_materials: Annotated[str | None, Query(max_length=12000)] = None,
        processing_job_id: Annotated[int | None, Query(gt=0)] = None,
        conduit_material_id: Annotated[int | None, Query(gt=0)] = None,
        wire_material_id: Annotated[int | None, Query(gt=0)] = None,
        wire_meters_per_unit: Annotated[float | None, Query(gt=0, le=100000, allow_inf_nan=False)] = None,
        wire_price_per_meter: Annotated[float | None, Query(ge=0, le=1000000000, allow_inf_nan=False)] = None,
        conduit_price_per_meter: Annotated[float | None, Query(ge=0, le=1000000000, allow_inf_nan=False)] = None,
        scale_denominator: Annotated[float | None, Query(ge=1, le=100000, allow_inf_nan=False)] = None,
        paper_size: Annotated[Literal['A5', 'A4', 'A3', 'A2', 'A1', 'A0', 'CUSTOM'] | None, Query()] = None,
        custom_width_mm: Annotated[float | None, Query(gt=0, le=10000, allow_inf_nan=False)] = None,
        custom_height_mm: Annotated[float | None, Query(gt=0, le=10000, allow_inf_nan=False)] = None,
        user: User = Depends(require_roles('ADMIN', 'DESIGNER')), session: Session = Depends(get_db)):
    value = execute(session, lambda: planning_csv(reviewed_bom(session, user, project_id,
        floor_plan_id=floor_plan_id, processing_job_id=processing_job_id,device_materials=device_materials,
        conduit_material_id=conduit_material_id, wire_material_id=wire_material_id, paper_size=paper_size,
        conduit_price_per_meter=conduit_price_per_meter, scale_denominator=scale_denominator,
        custom_width_mm=custom_width_mm, custom_height_mm=custom_height_mm,
        wire_meters_per_unit=wire_meters_per_unit, wire_price_per_meter=wire_price_per_meter,purchase_pricing=purchase_pricing), xlsx=format=='xlsx'))
    return Response(value, media_type=XLSX_MIME if format=='xlsx' else 'text/csv', headers={'Content-Disposition': f'attachment; filename="VED-Bill-of-Materials-{project_id}.{format}"'})


@router.post('/{project_id}/bom/preview', response_model=BOMResponse)
def preview_bom(project_id: ProjectId, payload: DemoReviewRequest,
        floor_plan_id: Annotated[int, Query(gt=0)], processing_job_id: Annotated[int, Query(gt=0)],
        purchase_pricing: Annotated[str | None, Query(max_length=4000)] = None,
        device_materials: Annotated[str | None, Query(max_length=12000)] = None,
        conduit_material_id: Annotated[int | None, Query(gt=0)] = None,
        wire_material_id: Annotated[int | None, Query(gt=0)] = None,
        wire_meters_per_unit: Annotated[float | None, Query(gt=0, le=100000, allow_inf_nan=False)] = None,
        wire_price_per_meter: Annotated[float | None, Query(ge=0, le=1000000000, allow_inf_nan=False)] = None,
        conduit_price_per_meter: Annotated[float | None, Query(ge=0, le=1000000000, allow_inf_nan=False)] = None,
        scale_denominator: Annotated[float | None, Query(ge=1, le=100000, allow_inf_nan=False)] = None,
        paper_size: Annotated[Literal['A5', 'A4', 'A3', 'A2', 'A1', 'A0', 'CUSTOM'] | None, Query()] = None,
        custom_width_mm: Annotated[float | None, Query(gt=0, le=10000, allow_inf_nan=False)] = None,
        custom_height_mm: Annotated[float | None, Query(gt=0, le=10000, allow_inf_nan=False)] = None,
        download: bool = False, format: Literal['csv', 'xlsx'] = 'csv',
        user: User = Depends(require_roles('ADMIN', 'DESIGNER')), session: Session = Depends(get_db)):
    value = execute(session, lambda: reviewed_bom(session, user, project_id,
        floor_plan_id=floor_plan_id, processing_job_id=processing_job_id, draft_preview=payload,device_materials=device_materials,
        conduit_material_id=conduit_material_id, wire_material_id=wire_material_id, paper_size=paper_size,
        conduit_price_per_meter=conduit_price_per_meter, scale_denominator=scale_denominator,
        custom_width_mm=custom_width_mm, custom_height_mm=custom_height_mm,
        wire_meters_per_unit=wire_meters_per_unit, wire_price_per_meter=wire_price_per_meter,purchase_pricing=purchase_pricing))
    if download:
        return Response(planning_csv(value,xlsx=format=='xlsx'), media_type=XLSX_MIME if format=='xlsx' else 'text/csv', headers={'Content-Disposition':f'attachment; filename="VED-Bill-of-Materials-{project_id}.{format}"'})
    return value


@router.get('/{project_id}/estimates/{estimate_id}/bom.csv')
def export_bom(project_id: ProjectId, estimate_id: Annotated[int, Path(gt=0)],
               format: Literal['csv', 'xlsx'] = 'csv',
               user: User = Depends(require_roles('ADMIN', 'DESIGNER')), session: Session = Depends(get_db)):
    value = execute(session, lambda: estimate_csv(service.retrieve_estimate(session, user, project_id, estimate_id),xlsx=format=='xlsx'))
    return Response(value, media_type=XLSX_MIME if format=='xlsx' else 'text/csv', headers={'Content-Disposition': f'attachment; filename="VED-Bill-of-Materials-estimate-{estimate_id}.{format}"'})


@router.get("/{project_id}/estimates", response_model=list[EstimateResponse])
def list_estimates(project_id: ProjectId, user: User = Depends(require_roles("ADMIN", "DESIGNER")), session: Session = Depends(get_db)):
    return execute(session, lambda: service.retrieve_estimates(session, user, project_id))


@router.get("/{project_id}/estimates/{estimate_id}", response_model=EstimateResponse)
def get_estimate(project_id: ProjectId, estimate_id: Annotated[int, Path(gt=0)], user: User = Depends(require_roles("ADMIN", "DESIGNER")), session: Session = Depends(get_db)):
    return execute(session, lambda: service.retrieve_estimate(session, user, project_id, estimate_id))


@router.post("/{project_id}/estimates", response_model=EstimateResponse, status_code=201)
def create_estimate(project_id: ProjectId, payload: EstimateWrite, user: User = Depends(require_roles("DESIGNER")), session: Session = Depends(get_db)):
    return execute(session, lambda: service.generate_estimate(session, user, project_id, payload))
