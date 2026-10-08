"""Hash-bound drawing reprocessing through existing jobs/artifacts and review."""
from hashlib import sha256
import json

from sqlalchemy import inspect, select

from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationCandidate
from app.ai.floor_plan_interpretation.drawing_region import DrawingRegion
from app.core.config import get_processed_directory
from app.models import (
    FloorPlanInterpretationRun, FloorPlanPage, FloorPlanSource, ProcessingDrawingSelection, ProcessingJob,
)
from app.repositories.floor_plan_repository import find_owned_floor_plan_for_update
from app.schemas.drawing_selection import DrawingRegionProcessingRequest
from app.services.interpretation_release_service import current_runtime_release
from app.services.processing_artifact_service import ProcessingArtifactError, resolve_trusted_processing_artifact
from app.services.processing_job_service import FloorPlanNotFoundError, start_floor_plan_processing


class DrawingSelectionError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__("The selected drawing could not be processed.")


def selection_fingerprint(floor_plan_id, request):
    values = {"floor_plan_id": floor_plan_id, **request.model_dump(mode="json", exclude={"request_id"})}
    return sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def selection_region(selection):
    return DrawingRegion(x=selection.x_pixels, y=selection.y_pixels,
                         width=selection.width_pixels, height=selection.height_pixels)


def trusted_selection_source(session, *, selection, job, page, settings):
    """Current job, exact source run/page/hash, and immutable selected coordinates."""
    if settings.app_env != "development":
        raise DrawingSelectionError("DRAWING_SELECTION_DEVELOPMENT_ONLY")
    run = session.get(FloorPlanInterpretationRun, selection.source_run_id)
    if (run is None or selection.processing_job_id != job.id or run.floor_plan_id != job.floor_plan_id
            or run.floor_plan_page_id != page.id or run.processing_job_id == job.id):
        raise DrawingSelectionError("DRAWING_SELECTION_SOURCE_CONFLICT")
    if sha256(run.candidate_json.encode()).hexdigest() != run.candidate_sha256:
        raise DrawingSelectionError("DRAWING_SELECTION_SOURCE_CONFLICT")
    try:
        candidate = FloorPlanInterpretationCandidate.model_validate_json(run.candidate_json)
        source = session.get(FloorPlanSource, page.floor_plan_source_id)
        host = candidate.provenance
        if (source is None or source.floor_plan_id != job.floor_plan_id or source.original_sha256 != host.source_sha256
                or host.floor_plan_source_id != source.id or host.floor_plan_page_id != page.id
                or host.source_page_number != page.page_number or host.processing_job_id != run.processing_job_id
                or host.candidate_run_id != run.candidate_run_id or host.source_artifact_id != run.source_artifact_id
                or host.source_artifact_sha256 != selection.source_artifact_sha256):
            raise ValueError
        request = DrawingRegionProcessingRequest(intent="process_drawing_region", candidate_run_id=run.candidate_run_id,
            expected_source_artifact_sha256=selection.source_artifact_sha256,
            region=selection_region(selection), request_id=selection.request_id)
        if selection_fingerprint(job.floor_plan_id, request) != selection.selection_sha256:
            raise ValueError
        request.region.validate_plane(candidate.payload.source_plane)
        artifact = resolve_trusted_processing_artifact(session, floor_plan_id=job.floor_plan_id,
            processing_job_id=run.processing_job_id, floor_plan_page_id=page.id,
            artifact_kind="normalized_image", processed_directory=get_processed_directory(settings))
        if (artifact.record.id != run.source_artifact_id or artifact.record.sha256 != selection.source_artifact_sha256
                or (artifact.record.pixel_width, artifact.record.pixel_height) != (
                    host.expected_width_pixels, host.expected_height_pixels)):
            raise ValueError
    except (ValueError, ProcessingArtifactError):
        raise DrawingSelectionError("DRAWING_SELECTION_SOURCE_CONFLICT") from None
    return artifact


def load_drawing_selection(session, *, processing_job_id):
    # Mixed-version prototype databases can still execute old whole-page jobs
    # before the additive table is initialized. Region creation itself fails
    # safely until schema initialization; never manufacture a selection.
    if not inspect(session.get_bind()).has_table(ProcessingDrawingSelection.__tablename__):
        return None
    return session.get(ProcessingDrawingSelection, processing_job_id)


def start_drawing_region_processing(session, *, current_user, floor_plan_id, request, settings):
    # Role checks belong on both the route and service boundary.
    if current_user.role.name != "DESIGNER":
        raise DrawingSelectionError("DRAWING_SELECTION_FORBIDDEN")
    floor_plan = find_owned_floor_plan_for_update(session, floor_plan_id=floor_plan_id, owner_id=current_user.id)
    if floor_plan is None:
        raise FloorPlanNotFoundError
    if (settings.app_env != "development" or settings.local_vlm_runtime_url is not None
            or settings.local_vlm_model_path is not None or current_runtime_release(session) is not None):
        raise DrawingSelectionError("DRAWING_SELECTION_DEVELOPMENT_ONLY")
    fingerprint = selection_fingerprint(floor_plan_id, request)
    retry = session.scalar(select(ProcessingDrawingSelection).where(
        ProcessingDrawingSelection.requested_by_user_id == current_user.id,
        ProcessingDrawingSelection.request_id == request.request_id).with_for_update())
    if retry is not None:
        if retry.selection_sha256 != fingerprint:
            raise DrawingSelectionError("DRAWING_SELECTION_REQUEST_CONFLICT")
        return session.scalar(select(ProcessingJob).where(ProcessingJob.id == retry.processing_job_id)
                              .with_for_update().execution_options(populate_existing=True))
    run = session.scalar(select(FloorPlanInterpretationRun).where(
        FloorPlanInterpretationRun.candidate_run_id == request.candidate_run_id,
        FloorPlanInterpretationRun.floor_plan_id == floor_plan_id))
    if run is None:
        raise DrawingSelectionError("DRAWING_SELECTION_SOURCE_NOT_FOUND")
    if sha256(run.candidate_json.encode()).hexdigest() != run.candidate_sha256:
        raise DrawingSelectionError("DRAWING_SELECTION_SOURCE_CONFLICT")
    try:
        candidate = FloorPlanInterpretationCandidate.model_validate_json(run.candidate_json)
        request.region.validate_plane(candidate.payload.source_plane)
    except ValueError:
        raise DrawingSelectionError("DRAWING_SELECTION_BOUNDS_INVALID") from None
    if request.expected_source_artifact_sha256 != candidate.provenance.source_artifact_sha256:
        raise DrawingSelectionError("DRAWING_SELECTION_SOURCE_CONFLICT")
    page = session.get(FloorPlanPage, run.floor_plan_page_id)
    if page is None:
        raise DrawingSelectionError("DRAWING_SELECTION_SOURCE_NOT_FOUND")
    # The queued job and its selection commit together. No crop files, inferred
    # approvals, revisions or canonical geometry are created by this endpoint.
    job = start_floor_plan_processing(session, current_user=current_user, floor_plan_id=floor_plan_id,
                                      page_numbers=[page.page_number], settings=settings)
    region = request.region
    selection = ProcessingDrawingSelection(processing_job_id=job.id, source_run_id=run.id,
        requested_by_user_id=current_user.id, request_id=request.request_id,
        source_artifact_sha256=request.expected_source_artifact_sha256, selection_sha256=fingerprint,
        x_pixels=region.x, y_pixels=region.y, width_pixels=region.width, height_pixels=region.height)
    trusted_selection_source(session, selection=selection, job=job, page=page, settings=settings)
    session.add(selection)
    session.flush()
    return job
