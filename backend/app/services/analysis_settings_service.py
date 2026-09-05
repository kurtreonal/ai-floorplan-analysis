from sqlalchemy.orm import Session

from app.models import FloorElevationSetting, PageScaleSetting, User
from app.repositories import analysis_settings_repository as repository
from app.schemas.analysis_settings import AnalysisSettingsResponse, ElevationInput, ElevationResponse, PageSettingsResponse, ScaleInput, ScaleResponse
from app.services.project_service import ProjectNotFoundError, get_accessible_project


class AnalysisSettingsError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__("The analysis settings operation could not be completed.")


def _authorize(session, user, project_id, floor_id, *, write=False):
    allowed = {"DESIGNER"} if write else {"DESIGNER", "ADMIN"}
    if getattr(getattr(user, "role", None), "name", None) not in allowed:
        raise AnalysisSettingsError("AUTHORIZATION_DENIED")
    try:
        get_accessible_project(session, current_user=user, project_id=project_id)
    except ProjectNotFoundError:
        raise AnalysisSettingsError("ANALYSIS_SETTINGS_NOT_FOUND") from None
    floor = repository.find_floor(session, project_id=project_id, floor_id=floor_id, lock=write)
    if floor is None:
        raise AnalysisSettingsError("ANALYSIS_SETTINGS_NOT_FOUND")
    return floor


def _metadata(row, value):
    return dict(
        revision_id=row.id if row else None,
        state="approved" if value is not None else "unresolved",
        evidence_notes=row.evidence_notes if row else None,
        reviewed_by_user_id=row.reviewed_by_user_id if row else None,
        created_at=row.created_at if row else None,
    )


def elevation_response(row):
    value = float(row.elevation_meters) if row and row.elevation_meters is not None else None
    return ElevationResponse(**_metadata(row, value), elevation_meters=value)


def scale_response(row):
    value = float(row.pixels_per_meter) if row and row.pixels_per_meter is not None else None
    return ScaleResponse(
        **_metadata(row, value), pixels_per_meter=value,
        reference_width_pixels=row.reference_width_pixels if row else None,
        reference_height_pixels=row.reference_height_pixels if row else None,
    )


def retrieve_settings(session: Session, *, current_user: User, project_id: int, floor_id: int):
    _authorize(session, current_user, project_id, floor_id)
    pages = repository.list_pages(session, floor_id)
    scales = repository.latest_scales(session, [page.id for page, _ in pages])
    return AnalysisSettingsResponse(
        project_floor_id=floor_id,
        elevation=elevation_response(repository.latest_elevation(session, floor_id)),
        pages=[PageSettingsResponse(
            floor_plan_id=plan_id, floor_plan_page_id=page.id, page_number=page.page_number,
            scale=scale_response(scales.get(page.id)),
        ) for page, plan_id in pages],
    )


def approve_elevation(session: Session, *, current_user: User, project_id: int, floor_id: int, data: ElevationInput):
    _authorize(session, current_user, project_id, floor_id, write=True)
    row = repository.add_approval(session, FloorElevationSetting(
        project_floor_id=floor_id, reviewed_by_user_id=current_user.id, **data.model_dump(),
    ))
    return elevation_response(row)


def approve_scale(session: Session, *, current_user: User, project_id: int, floor_id: int, page_id: int, data: ScaleInput):
    _authorize(session, current_user, project_id, floor_id, write=True)
    if page_id not in {page.id for page, _ in repository.list_pages(session, floor_id)}:
        raise AnalysisSettingsError("ANALYSIS_SETTINGS_NOT_FOUND")
    row = repository.add_approval(session, PageScaleSetting(
        floor_plan_page_id=page_id, reviewed_by_user_id=current_user.id, **data.model_dump(),
    ))
    return scale_response(row)


def require_approved_metric_inputs(settings: AnalysisSettingsResponse, *, page_id: int, image_width: int, image_height: int):
    """Return explicit K1 inputs only for the exact reviewed reference dimensions."""
    page = next((page for page in settings.pages if page.floor_plan_page_id == page_id), None)
    if settings.elevation.state != "approved" or page is None or page.scale.state != "approved":
        raise AnalysisSettingsError("METRIC_INPUTS_UNRESOLVED")
    scale = page.scale
    if (image_width, image_height) != (scale.reference_width_pixels, scale.reference_height_pixels):
        raise AnalysisSettingsError("SCALE_REFERENCE_MISMATCH")
    return settings.elevation.elevation_meters, scale.pixels_per_meter
