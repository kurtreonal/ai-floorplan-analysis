from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.config import (
    UploadDirectoryConfigurationError,
    get_max_upload_size_bytes,
    get_upload_directory,
)
from app.core.database import get_db
from app.models import User
from app.schemas.floor_plan import FloorPlanListItemResponse, FloorPlanUploadResponse
from app.services.floor_plan_storage import FloorPlanStorageError
from app.services.floor_plan_upload import (
    ProjectFloorNotFoundError,
    list_accessible_floor_plans,
    upload_floor_plan,
)
from app.services.project_service import ProjectNotFoundError
from app.services.upload_validation import UploadValidationError
from app.schemas.plan_measurement import PlanMeasurementInput,PlanMeasurementWrite,PlanMeasurementResponse
from app.services import plan_measurement_service as measurements
from pydantic import ValidationError
from app.schemas.floor_plan_lifecycle import FloorPlanLifecycleRequest, FloorPlanLifecycleResponse
from app.services.floor_plan_lifecycle_service import (
    FloorPlanLifecycleError, change_plan_state, inspect_plan, list_removed,
)


router = APIRouter(prefix="/api/projects", tags=["floor plans"])


def _measurement_operation(session,action,*,write=False):
    try:
        value=action()
        if write:
            session.commit()
        return value
    except ProjectNotFoundError:
        session.rollback()
        raise HTTPException(status_code=404,detail={'error':{'code':'PROJECT_NOT_FOUND','message':'Project not found.','details':{}}}) from None
    except (measurements.MeasurementSettingsError,SQLAlchemyError) as error:
        session.rollback()
        status_code=error.status if isinstance(error,measurements.MeasurementSettingsError) else 503
        message=str(error) if isinstance(error,measurements.MeasurementSettingsError) else 'Plan measurement settings are unavailable. Existing uploads are unchanged.'
        raise HTTPException(status_code=status_code,detail={'error':{'code':'PLAN_MEASUREMENT_SETTINGS_UNAVAILABLE','message':message,'details':{}}}) from None


@router.get('/{project_id}/floor-plans/{floor_plan_id}/measurement-settings',response_model=PlanMeasurementResponse)
def get_plan_measurements(project_id:Annotated[int,Path(gt=0)],floor_plan_id:Annotated[int,Path(gt=0)],
    user:User=Depends(require_roles('DESIGNER','ADMIN')),session:Session=Depends(get_db)):
    return _measurement_operation(session,lambda:measurements.retrieve(session,user,project_id,floor_plan_id))


@router.put('/{project_id}/floor-plans/{floor_plan_id}/measurement-settings',response_model=PlanMeasurementResponse)
def put_plan_measurements(project_id:Annotated[int,Path(gt=0)],floor_plan_id:Annotated[int,Path(gt=0)],data:PlanMeasurementWrite,
    user:User=Depends(require_roles('DESIGNER')),session:Session=Depends(get_db)):
    return _measurement_operation(session,lambda:measurements.save(session,user,project_id,floor_plan_id,data),write=True)


def _lifecycle_operation(session, operation, **kwargs):
    try:
        return operation(session, **kwargs)
    except ProjectNotFoundError:
        session.rollback()
        raise _api_error(status_code=404, code="PROJECT_NOT_FOUND", message="The project was not found.") from None
    except FloorPlanLifecycleError as error:
        session.rollback()
        raise _api_error(status_code=error.status, code=error.code, message=error.message) from None
    except SQLAlchemyError:
        session.rollback()
        raise _api_error(status_code=503, code="FLOOR_PLAN_CHANGE_UNAVAILABLE",
                         message="Floor-plan management is temporarily unavailable. Retry this request.") from None


@router.get("/{project_id}/floor-plan-trash", response_model=list[FloorPlanLifecycleResponse])
def removed_plans_endpoint(project_id: Annotated[int, Path(gt=0)],
    current_user: User = Depends(require_roles("ADMIN", "DESIGNER")),
    database_session: Session = Depends(get_db)):
    return _lifecycle_operation(database_session, list_removed, current_user=current_user, project_id=project_id)


@router.get("/{project_id}/floor-plans/{floor_plan_id}/lifecycle", response_model=FloorPlanLifecycleResponse)
def inspect_plan_endpoint(project_id: Annotated[int, Path(gt=0)], floor_plan_id: Annotated[int, Path(gt=0)],
    current_user: User = Depends(require_roles("ADMIN", "DESIGNER")), database_session: Session = Depends(get_db)):
    return _lifecycle_operation(database_session, inspect_plan, current_user=current_user,
                               project_id=project_id, floor_plan_id=floor_plan_id)


@router.delete("/{project_id}/floor-plans/{floor_plan_id}", response_model=FloorPlanLifecycleResponse)
def remove_plan_endpoint(project_id: Annotated[int, Path(gt=0)], floor_plan_id: Annotated[int, Path(gt=0)],
    request: FloorPlanLifecycleRequest, current_user: User = Depends(require_roles("DESIGNER")),
    database_session: Session = Depends(get_db)):
    return _lifecycle_operation(database_session, change_plan_state, current_user=current_user,
                               project_id=project_id, floor_plan_id=floor_plan_id, request=request, remove=True)


@router.post("/{project_id}/floor-plans/{floor_plan_id}/restore", response_model=FloorPlanLifecycleResponse)
def restore_plan_endpoint(project_id: Annotated[int, Path(gt=0)], floor_plan_id: Annotated[int, Path(gt=0)],
    request: FloorPlanLifecycleRequest, current_user: User = Depends(require_roles("DESIGNER")),
    database_session: Session = Depends(get_db)):
    return _lifecycle_operation(database_session, change_plan_state, current_user=current_user,
                               project_id=project_id, floor_plan_id=floor_plan_id, request=request, remove=False)

UNSUPPORTED_MEDIA_CODES = frozenset(
    {
        "UPLOAD_EXTENSION_UNSUPPORTED",
        "UPLOAD_MIME_UNSUPPORTED",
        "UPLOAD_MIME_EXTENSION_MISMATCH",
        "UPLOAD_CONTENT_MISMATCH",
    }
)
INVALID_FILENAME_CODES = frozenset(
    {"ORIGINAL_FILENAME_INVALID", "ORIGINAL_FILENAME_TOO_LONG"}
)


def _api_error(
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, object] | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code,
                "message": message,
                "details": dict(details or {}),
            }
        },
    )


def _validation_http_error(error: UploadValidationError) -> HTTPException:
    if error.code == "UPLOAD_TOO_LARGE":
        status_code = status.HTTP_413_CONTENT_TOO_LARGE
    elif error.code in UNSUPPORTED_MEDIA_CODES:
        status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    elif error.code == "UPLOAD_SIZE_LIMIT_INVALID":
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    return _api_error(
        status_code=status_code,
        code=error.code,
        message=error.message,
        details=error.details,
    )


def _storage_http_error(error: FloorPlanStorageError) -> HTTPException:
    status_code = (
        status.HTTP_422_UNPROCESSABLE_CONTENT
        if error.code in INVALID_FILENAME_CODES
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return _api_error(
        status_code=status_code,
        code=error.code,
        message=error.message,
        details=error.details,
    )


@router.get(
    "/{project_id}/floor-plans",
    response_model=list[FloorPlanListItemResponse],
    status_code=status.HTTP_200_OK,
)
def list_floor_plans_endpoint(
    project_id: Annotated[int, Path(gt=0)],
    project_floor_id: Annotated[int | None, Query(gt=0)] = None,
    current_user: User = Depends(require_roles("ADMIN", "DESIGNER")),
    database_session: Session = Depends(get_db),
) -> list[FloorPlanListItemResponse]:
    try:
        floor_plans = list_accessible_floor_plans(
            database_session,
            current_user=current_user,
            project_id=project_id,
            project_floor_id=project_floor_id,
        )
    except ProjectNotFoundError:
        raise _api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="PROJECT_NOT_FOUND",
            message="The requested project was not found.",
        ) from None
    except ProjectFloorNotFoundError:
        raise _api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="PROJECT_FLOOR_NOT_FOUND",
            message="The requested project floor was not found.",
        ) from None
    except SQLAlchemyError:
        database_session.rollback()
        raise _api_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="FLOOR_PLAN_LIST_FAILED",
            message="Floor plans could not be loaded.",
        ) from None

    return [
        FloorPlanListItemResponse.model_validate(floor_plan)
        for floor_plan in floor_plans
    ]


@router.post(
    "/{project_id}/floor-plans",
    response_model=FloorPlanUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_floor_plan_endpoint(
    request: Request,
    project_id: Annotated[int, Path(gt=0)],
    project_floor_id: Annotated[int, Form(gt=0)],
    file: Annotated[UploadFile, File()],
    measurement_settings: Annotated[str | None, Form(max_length=20000)] = None,
    current_user: User = Depends(require_roles("DESIGNER")),
    database_session: Session = Depends(get_db),
) -> FloorPlanUploadResponse:
    settings = request.app.state.settings
    max_file_size_bytes = get_max_upload_size_bytes(settings)

    try:
        try:
            upload_directory = get_upload_directory(settings)
        except UploadDirectoryConfigurationError as error:
            raise _api_error(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="UPLOAD_CONFIGURATION_UNAVAILABLE",
                message=str(error),
            ) from None

        try:
            content = await file.read(max_file_size_bytes + 1)
        except Exception:
            raise _api_error(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="UPLOAD_READ_FAILED",
                message="The uploaded floor-plan file could not be read.",
            ) from None

        try:
            try:
                measurement_input=PlanMeasurementInput.model_validate_json(measurement_settings) if measurement_settings is not None else None
            except ValidationError:
                raise _api_error(status_code=422,code='INVALID_PLAN_MEASUREMENTS',message='Check the paper, scale and elevation inputs.') from None
            floor_plan = upload_floor_plan(
                database_session,
                current_user=current_user,
                project_id=project_id,
                project_floor_id=project_floor_id,
                filename=file.filename or "",
                declared_mime_type=file.content_type or "",
                content=content,
                upload_directory=upload_directory,
                max_file_size_bytes=max_file_size_bytes,
                **({'measurement_settings':measurement_input} if measurement_input is not None else {}),
            )
        except ProjectNotFoundError:
            raise _api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="PROJECT_NOT_FOUND",
                message="The requested project was not found.",
            ) from None
        except ProjectFloorNotFoundError:
            raise _api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="PROJECT_FLOOR_NOT_FOUND",
                message="The requested project floor was not found.",
            ) from None
        except UploadValidationError as error:
            raise _validation_http_error(error) from None
        except FloorPlanStorageError as error:
            raise _storage_http_error(error) from None
        except SQLAlchemyError:
            database_session.rollback()
            raise _api_error(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="FLOOR_PLAN_UPLOAD_FAILED",
                message="The floor plan could not be uploaded.",
            ) from None
    finally:
        try:
            await file.close()
        except Exception:
            pass

    return FloorPlanUploadResponse.model_validate(floor_plan)
