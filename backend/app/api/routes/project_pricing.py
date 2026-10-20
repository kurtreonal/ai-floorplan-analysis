from typing import Annotated
from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Query, UploadFile
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.api.dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.project_pricing import ApplyRequest, ImportInspection, PreviewRequest, ProjectImportPreview, VersionDetail, VersionSummary
from app.services import project_pricing_service as service
from app.services.material_workbook import MAX_FILE, WorkbookError
from app.services.project_service import ProjectNotFoundError

router = APIRouter(prefix='/api/projects/{project_id}/client-pricing', tags=['project pricing'])
ProjectId = Annotated[int, Path(gt=0)]


def execute(session, action):
    try:
        return action()
    except (WorkbookError, ValidationError, PermissionError, ProjectNotFoundError, LookupError, SQLAlchemyError) as error:
        session.rollback()
        status = 503 if isinstance(error, SQLAlchemyError) else 403 if isinstance(error, PermissionError) else (
            404 if isinstance(error, (ProjectNotFoundError, LookupError)) else 409 if isinstance(error, service.PricingConflict) else 422)
        code = {503: 'PROJECT_PRICING_UNAVAILABLE', 403: 'AUTHORIZATION_DENIED', 404: 'PROJECT_PRICING_NOT_FOUND',
            409: 'PROJECT_PRICING_CONFLICT', 422: 'PROJECT_PRICING_INVALID'}[status]
        message = str(error) if isinstance(error, WorkbookError) else 'The project pricing operation could not be completed.'
        raise HTTPException(status, detail={'error': {'code': code, 'message': message, 'details': {}}}) from None


def contents(file):
    allowed = {'application/octet-stream', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'text/csv', 'application/csv', 'application/vnd.ms-excel', 'text/plain'}
    if file.content_type not in allowed:
        raise WorkbookError('Choose an XLSX or UTF-8 CSV file.')
    return file.file.read(MAX_FILE + 1)


@router.post('/inspect', response_model=ImportInspection)
def inspect(project_id: ProjectId, file: Annotated[UploadFile, File()],
        sheet: Annotated[str | None, Form(max_length=100)] = None,
        header_row: Annotated[int, Form(ge=1, le=10000)] = 1,
        user: User = Depends(require_roles('DESIGNER')), session: Session = Depends(get_db)):
    return execute(session, lambda: service.inspect_file(session, user, project_id,
        contents(file), file.filename, sheet, header_row))


@router.post('/preview', response_model=ProjectImportPreview)
def preview(project_id: ProjectId, file: Annotated[UploadFile, File()],
        selection: Annotated[str | None, Form(max_length=300000)] = None,
        user: User = Depends(require_roles('DESIGNER')), session: Session = Depends(get_db)):
    return execute(session, lambda: service.automatic_preview(session, user, project_id,
        contents(file), file.filename) if selection is None else service.preview(session, user, project_id,
        contents(file), file.filename, PreviewRequest.model_validate_json(selection)))


@router.post('/apply', response_model=VersionSummary)
def apply(project_id: ProjectId, file: Annotated[UploadFile, File()],
        selection: Annotated[str, Form(max_length=300000)],
        user: User = Depends(require_roles('DESIGNER')), session: Session = Depends(get_db)):
    return execute(session, lambda: service.apply(session, user, project_id,
        contents(file), file.filename, ApplyRequest.model_validate_json(selection)))


@router.get('', response_model=list[VersionSummary])
def versions(project_id: ProjectId, user: User = Depends(require_roles('ADMIN', 'DESIGNER')), session: Session = Depends(get_db)):
    return execute(session, lambda: service.list_versions(session, user, project_id))


@router.get('/{version_id}', response_model=VersionDetail)
def detail(project_id: ProjectId, version_id: Annotated[int, Path(gt=0)],
        estimate_id: Annotated[int | None, Query(gt=0)] = None,
        user: User = Depends(require_roles('ADMIN', 'DESIGNER')), session: Session = Depends(get_db)):
    def action():
        record = service.get_version(session, user, project_id, version_id)
        value = VersionSummary.model_validate(record).model_dump() | {'document': record.document}
        if estimate_id is not None:
            value['comparison'] = service.compare_estimate(session, user, project_id, record, estimate_id)
        return value
    return execute(session, action)
