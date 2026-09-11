from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Annotated, Any, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.floor_plan_interpretation.candidate import (
    CandidateHostProvenance,
    FloorPlanInterpretationCandidate,
)
from app.ai.floor_plan_interpretation.gold_evaluation import (
    ApproverAuthoritySnapshot,
    CompletenessMarkers,
    GeometryTruth,
    GoldAnnotationDocument,
    ObservedWiringTruth,
    PixelPoint,
    ReviewDecision,
    SymbolTruth,
    TextDimensionTruth,
)
from app.models.dataset_approver_assignment import DatasetApproverAssignment
from app.models.floor_plan import FloorPlan
from app.models.floor_plan_interpretation_review import FloorPlanInterpretationReview
from app.models.floor_plan_interpretation_run import FloorPlanInterpretationRun
from app.models.project import Project
from app.models.project_floor import ProjectFloor
from app.models.user import User
from app.repositories.floor_plan_interpretation_repository import (
    add_review,
    add_run,
    find_latest_review,
    find_review_revision,
    next_review_revision,
)


SAFE_ID = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
HASH = re.compile(r"^[0-9a-f]{64}$")
RUN_ID = re.compile(r"^[0-9a-f]{32}$")


class PseudoLabelingError(ValueError):
    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message or code)


def _fail(code: str, message: str | None = None) -> None:
    raise PseudoLabelingError(code, message)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


ReviewDisposition = Literal["accepted", "corrected", "added", "rejected", "unresolved"]
MarkerState = Literal["complete", "pending", "not_applicable"]


class CompletenessChecklist(StrictModel):
    symbols: MarkerState = "complete"
    walls: MarkerState = "complete"
    rooms: MarkerState = "complete"
    openings: MarkerState = "not_applicable"
    panels: MarkerState = "not_applicable"
    scale_evidence: MarkerState = "not_applicable"
    observed_wiring: MarkerState = "not_applicable"

    @property
    def complete(self) -> bool:
        return "pending" not in (
            self.symbols,
            self.walls,
            self.rooms,
            self.openings,
            self.panels,
            self.scale_evidence,
            self.observed_wiring,
        )


class DatasetApprovalDecision(StrictModel):
    decision: Literal["approved", "rejected"]
    assignment_id: int = Field(gt=0)
    approver_user_id: int = Field(gt=0)
    decided_at: datetime
    reviewed_revision_number: int = Field(gt=0)
    reviewed_sha256: str
    decision_notes: str = Field(min_length=1, max_length=2000)

    @field_validator("decided_at")
    @classmethod
    def _validate_tz(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("decided_at must be timezone-aware")
        return value

    @field_validator("reviewed_sha256")
    @classmethod
    def _validate_hash(cls, value: str) -> str:
        if not HASH.fullmatch(value):
            raise ValueError("reviewed_sha256 must be 64-char hex")
        return value


class SymbolReview(StrictModel):
    id: str
    disposition: ReviewDisposition
    center: PixelPoint
    bbox: tuple[float, float, float, float] | None = None
    symbol_legend_id: int | None = Field(default=None, gt=0)
    class_id: int | None = Field(default=None, ge=0)
    class_name: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> SymbolReview:
        if not SAFE_ID.fullmatch(self.id):
            raise ValueError(f"Invalid symbol identity: {self.id}")
        if self.bbox is not None:
            xmin, ymin, xmax, ymax = self.bbox
            if xmin >= xmax or ymin >= ymax:
                raise ValueError("Invalid bbox coordinates")
        return self


class WallReview(StrictModel):
    id: str
    disposition: ReviewDisposition
    start: PixelPoint
    end: PixelPoint
    thickness_meters: float | None = Field(default=None, gt=0, le=10)
    height_meters: float | None = Field(default=None, gt=0, le=100)

    @model_validator(mode="after")
    def _validate(self) -> WallReview:
        if not SAFE_ID.fullmatch(self.id):
            raise ValueError(f"Invalid wall identity: {self.id}")
        if self.start == self.end:
            raise ValueError("Wall start and end must differ")
        return self


class RoomReview(StrictModel):
    id: str
    disposition: ReviewDisposition
    name: str | None = None
    boundary: tuple[PixelPoint, ...] = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def _validate(self) -> RoomReview:
        if not SAFE_ID.fullmatch(self.id):
            raise ValueError(f"Invalid room identity: {self.id}")
        return self


class OpeningReview(StrictModel):
    id: str
    disposition: ReviewDisposition
    kind: Literal["door", "window"]
    points: tuple[PixelPoint, ...] = Field(min_length=2, max_length=1000)

    @model_validator(mode="after")
    def _validate(self) -> OpeningReview:
        if not SAFE_ID.fullmatch(self.id):
            raise ValueError(f"Invalid opening identity: {self.id}")
        return self


class PanelReview(StrictModel):
    id: str
    disposition: ReviewDisposition
    name: str | None = None
    points: tuple[PixelPoint, ...] = Field(min_length=2, max_length=1000)

    @model_validator(mode="after")
    def _validate(self) -> PanelReview:
        if not SAFE_ID.fullmatch(self.id):
            raise ValueError(f"Invalid panel identity: {self.id}")
        return self


class ScaleEvidenceReview(StrictModel):
    id: str
    disposition: ReviewDisposition
    text: str = Field(min_length=1, max_length=1000)
    measured_pixels: float = Field(gt=0, le=100_000)
    real_world_meters: float = Field(gt=0, le=10_000)

    @model_validator(mode="after")
    def _validate(self) -> ScaleEvidenceReview:
        if not SAFE_ID.fullmatch(self.id):
            raise ValueError(f"Invalid scale evidence identity: {self.id}")
        return self


class ObservedWiringReview(StrictModel):
    id: str
    disposition: ReviewDisposition
    points: tuple[PixelPoint, ...] = Field(min_length=2, max_length=2000)
    completeness: Literal["complete", "partial", "unreadable"]

    @model_validator(mode="after")
    def _validate(self) -> ObservedWiringReview:
        if not SAFE_ID.fullmatch(self.id):
            raise ValueError(f"Invalid wiring identity: {self.id}")
        return self


class ReviewDocument(StrictModel):
    schema_version: Literal[1] = 1
    candidate_run_id: str
    revision_number: int = Field(gt=0)
    reviewed_by_user_id: int = Field(gt=0)
    review_complete: bool
    approved_for_layout: bool
    evidence_notes: str = Field(min_length=1, max_length=2000)
    wall_thickness_meters: float | None = Field(default=None, gt=0, le=10)
    wall_height_meters: float | None = Field(default=None, gt=0, le=100)
    checklist: CompletenessChecklist
    walls: tuple[WallReview, ...] = Field(default=())
    rooms: tuple[RoomReview, ...] = Field(default=())
    symbols: tuple[SymbolReview, ...] = Field(default=())
    openings: tuple[OpeningReview, ...] = Field(default=())
    panels: tuple[PanelReview, ...] = Field(default=())
    scale_evidence: tuple[ScaleEvidenceReview, ...] = Field(default=())
    observed_wiring: tuple[ObservedWiringReview, ...] = Field(default=())
    dataset_approval: DatasetApprovalDecision | None = None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _validate_tz(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value

    @field_validator("candidate_run_id")
    @classmethod
    def _validate_run_id(cls, value: str) -> str:
        if not RUN_ID.fullmatch(value):
            raise ValueError("candidate_run_id must be 32 hex chars")
        return value


def serialize_review_document(doc: ReviewDocument) -> tuple[str, str]:
    data = doc.model_dump(mode="json")
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
    digest = sha256(serialized.encode("utf-8")).hexdigest()
    return serialized, digest


def deserialize_review_document(raw_json: str, expected_sha256: str) -> ReviewDocument:
    actual_digest = sha256(raw_json.encode("utf-8")).hexdigest()
    if actual_digest != expected_sha256:
        _fail("REVIEW_INTEGRITY_FAILED", "Digest mismatch for review JSON")
    try:
        return ReviewDocument.model_validate_json(raw_json)
    except Exception as exc:
        _fail("REVIEW_INTEGRITY_FAILED", f"Invalid review document schema: {exc}")


def record_pseudo_label_run(
    session: Session,
    *,
    candidate: FloorPlanInterpretationCandidate,
    processing_job_id: int,
    floor_plan_id: int,
    floor_plan_page_id: int,
    source_artifact_id: int,
    provider: str,
) -> FloorPlanInterpretationRun:
    """Idempotently persist or retrieve candidate run without erasing previous reviews."""
    existing = session.scalar(
        select(FloorPlanInterpretationRun).where(
            FloorPlanInterpretationRun.candidate_run_id
            == candidate.provenance.candidate_run_id
        )
    )
    if existing is not None:
        return existing

    candidate_json = candidate.model_dump_json()
    candidate_sha256 = sha256(candidate_json.encode("utf-8")).hexdigest()

    run = FloorPlanInterpretationRun(
        candidate_run_id=candidate.provenance.candidate_run_id,
        processing_job_id=processing_job_id,
        floor_plan_id=floor_plan_id,
        floor_plan_page_id=floor_plan_page_id,
        source_artifact_id=source_artifact_id,
        provider=provider,
        candidate_sha256=candidate_sha256,
        candidate_json=candidate_json,
    )
    return add_run(session, run)


def _check_review_auth(
    session: Session,
    *,
    current_user: User,
    floor_plan_id: int,
    write: bool,
) -> tuple[FloorPlanInterpretationRun, Project]:
    role = getattr(getattr(current_user, "role", None), "name", None)
    if role not in ({"DESIGNER"} if write else {"ADMIN", "DESIGNER"}):
        _fail("AUTHORIZATION_DENIED", "Insufficient permissions for review")

    statement = (
        select(FloorPlanInterpretationRun, Project)
        .join(FloorPlan, FloorPlanInterpretationRun.floor_plan_id == FloorPlan.id)
        .join(ProjectFloor, FloorPlan.project_floor_id == ProjectFloor.id)
        .join(Project, ProjectFloor.project_id == Project.id)
        .where(FloorPlan.id == floor_plan_id)
    )
    if role == "DESIGNER":
        statement = statement.where(Project.owner_id == current_user.id)

    row = session.execute(
        statement.order_by(FloorPlanInterpretationRun.id.desc()).limit(1)
    ).first()
    if row is None:
        _fail("INTERPRETATION_NOT_FOUND", "No interpretation run found for floor plan")
    run, project = row
    return run, project


def submit_append_only_review(
    session: Session,
    *,
    current_user: User,
    floor_plan_id: int,
    candidate_run_id: str,
    expected_revision_number: int | None,
    review_complete: bool,
    approved_for_layout: bool,
    evidence_notes: str,
    checklist: CompletenessChecklist,
    wall_thickness_meters: float | None = None,
    wall_height_meters: float | None = None,
    walls: Sequence[WallReview] = (),
    rooms: Sequence[RoomReview] = (),
    symbols: Sequence[SymbolReview] = (),
    openings: Sequence[OpeningReview] = (),
    panels: Sequence[PanelReview] = (),
    scale_evidence: Sequence[ScaleEvidenceReview] = (),
    observed_wiring: Sequence[ObservedWiringReview] = (),
) -> FloorPlanInterpretationReview:
    """Appends a new immutable review revision, preserving prior history."""
    run, project = _check_review_auth(
        session, current_user=current_user, floor_plan_id=floor_plan_id, write=True
    )
    if run.candidate_run_id != candidate_run_id:
        _fail("STALE_INTERPRETATION_RUN", "Target candidate run ID does not match")

    latest = find_latest_review(session, interpretation_run_id=run.id)
    latest_rev = latest.revision_number if latest is not None else None
    if expected_revision_number != latest_rev:
        _fail("STALE_REVIEW_REVISION", f"Expected revision {expected_revision_number}, found {latest_rev}")

    # Completeness enforcement
    if review_complete:
        if not checklist.complete:
            _fail("CHECKLIST_PENDING", "Review cannot be marked complete while checklist items are pending")
        # Ensure no active item is left unresolved
        all_items = list(walls) + list(rooms) + list(symbols) + list(openings) + list(panels) + list(scale_evidence) + list(observed_wiring)
        if any(item.disposition == "unresolved" for item in all_items):
            _fail("REVIEW_HAS_UNRESOLVED_TARGETS", "All items must be resolved when review is complete")

    if approved_for_layout:
        if not review_complete:
            _fail("REVIEW_INCOMPLETE", "Layout approval requires complete review")
        if not any(w.disposition in ("accepted", "corrected", "added") for w in walls):
            _fail("APPROVED_GEOMETRY_EMPTY", "Layout approval requires at least one accepted wall")
        if not any(r.disposition in ("accepted", "corrected", "added") for r in rooms):
            _fail("APPROVED_GEOMETRY_EMPTY", "Layout approval requires at least one accepted room")
        if not any(s.disposition in ("accepted", "corrected", "added") for s in symbols):
            _fail("APPROVED_GEOMETRY_EMPTY", "Layout approval requires at least one accepted symbol")
        if wall_thickness_meters is None or wall_height_meters is None:
            _fail("WALL_DIMENSIONS_REQUIRED", "Wall dimensions are required for layout approval")

    next_rev = (latest_rev or 0) + 1
    doc = ReviewDocument(
        schema_version=1,
        candidate_run_id=run.candidate_run_id,
        revision_number=next_rev,
        reviewed_by_user_id=current_user.id,
        review_complete=review_complete,
        approved_for_layout=approved_for_layout,
        evidence_notes=evidence_notes,
        wall_thickness_meters=wall_thickness_meters,
        wall_height_meters=wall_height_meters,
        checklist=checklist,
        walls=tuple(walls),
        rooms=tuple(rooms),
        symbols=tuple(symbols),
        openings=tuple(openings),
        panels=tuple(panels),
        scale_evidence=tuple(scale_evidence),
        observed_wiring=tuple(observed_wiring),
        dataset_approval=None,  # Reset dataset approval on new revision!
        created_at=datetime.now(timezone.utc),
    )
    raw_json, digest = serialize_review_document(doc)

    review = FloorPlanInterpretationReview(
        interpretation_run_id=run.id,
        revision_number=next_rev,
        reviewed_by_user_id=current_user.id,
        review_complete=review_complete,
        approved_for_layout=approved_for_layout,
        review_sha256=digest,
        review_json=raw_json,
    )
    add_review(session, review)
    session.commit()
    session.refresh(review)
    return review


def bind_dataset_approval(
    session: Session,
    *,
    current_user: User,
    floor_plan_id: int,
    candidate_run_id: str,
    revision_number: int,
    decision: Literal["approved", "rejected"],
    decision_notes: str,
) -> FloorPlanInterpretationReview:
    """Applies PRE10 dataset approver authority binding to an existing complete review revision."""
    # Verify approver authority
    approver_assignment = session.scalar(
        select(DatasetApproverAssignment).where(
            DatasetApproverAssignment.assignee_user_id == current_user.id,
            DatasetApproverAssignment.active_marker.is_(True),
            DatasetApproverAssignment.authority_scope == "VED_AI_DATASET_APPROVER",
        )
    )
    if approver_assignment is None:
        _fail("DATASET_APPROVER_AUTHORITY_INVALID", "User lacks active VED_AI_DATASET_APPROVER authority")

    # Retrieve run and review
    statement = (
        select(FloorPlanInterpretationRun, Project)
        .join(FloorPlan, FloorPlanInterpretationRun.floor_plan_id == FloorPlan.id)
        .join(ProjectFloor, FloorPlan.project_floor_id == ProjectFloor.id)
        .join(Project, ProjectFloor.project_id == Project.id)
        .where(FloorPlan.id == floor_plan_id)
    )
    row = session.execute(
        statement.order_by(FloorPlanInterpretationRun.id.desc()).limit(1)
    ).first()
    if row is None:
        _fail("INTERPRETATION_NOT_FOUND", "Floor plan interpretation run not found")
    run, project = row

    if run.candidate_run_id != candidate_run_id:
        _fail("STALE_INTERPRETATION_RUN", "Candidate run mismatch")

    review = find_review_revision(
        session, interpretation_run_id=run.id, revision_number=revision_number
    )
    if review is None:
        _fail("REVIEW_NOT_FOUND", f"Review revision {revision_number} not found")

    # Author self-approval check: approver cannot be the designer or reviewer
    if current_user.id == review.reviewed_by_user_id or current_user.id == project.owner_id:
        _fail(
            "DATASET_APPROVER_SELF_APPROVAL_DENIED",
            "Dataset approvers cannot approve their own reviews or project outputs",
        )

    if not review.review_complete:
        _fail("REVIEW_INCOMPLETE", "Cannot bind dataset approval to incomplete review")

    doc = deserialize_review_document(review.review_json, review.review_sha256)

    # Re-verify checklist and no unresolved items
    if not doc.checklist.complete:
        _fail("CHECKLIST_PENDING", "Checklist must be complete for dataset approval")

    approval = DatasetApprovalDecision(
        decision=decision,
        assignment_id=approver_assignment.id,
        approver_user_id=current_user.id,
        decided_at=datetime.now(timezone.utc),
        reviewed_revision_number=review.revision_number,
        reviewed_sha256=review.review_sha256,
        decision_notes=decision_notes,
    )

    updated_doc = ReviewDocument(
        schema_version=doc.schema_version,
        candidate_run_id=doc.candidate_run_id,
        revision_number=doc.revision_number,
        reviewed_by_user_id=doc.reviewed_by_user_id,
        review_complete=doc.review_complete,
        approved_for_layout=doc.approved_for_layout,
        evidence_notes=doc.evidence_notes,
        wall_thickness_meters=doc.wall_thickness_meters,
        wall_height_meters=doc.wall_height_meters,
        checklist=doc.checklist,
        walls=doc.walls,
        rooms=doc.rooms,
        symbols=doc.symbols,
        openings=doc.openings,
        panels=doc.panels,
        scale_evidence=doc.scale_evidence,
        observed_wiring=doc.observed_wiring,
        dataset_approval=approval,
        created_at=doc.created_at,
    )
    raw_json, digest = serialize_review_document(updated_doc)
    review.review_json = raw_json
    review.review_sha256 = digest
    session.commit()
    session.refresh(review)
    return review


def export_approved_training_candidates(
    session: Session,
    *,
    current_user: User,
    output_directory: Path,
    split_filter: Literal["development_train", "development_validation"] = "development_train",
) -> list[GoldAnnotationDocument]:
    """Strictly exports only permission-eligible, fully dataset-approved non-test records."""
    # Authorized caller: Admin or active Dataset Approver
    role = getattr(getattr(current_user, "role", None), "name", None)
    is_approver = session.scalar(
        select(DatasetApproverAssignment).where(
            DatasetApproverAssignment.assignee_user_id == current_user.id,
            DatasetApproverAssignment.active_marker.is_(True),
            DatasetApproverAssignment.authority_scope == "VED_AI_DATASET_APPROVER",
        )
    ) is not None

    if role != "ADMIN" and not is_approver:
        _fail("AUTHORIZATION_DENIED", "Export requires Admin or active Dataset Approver authority")

    output_directory.mkdir(parents=True, exist_ok=True)
    exported: list[GoldAnnotationDocument] = []

    # Query all completed reviews with an approval
    reviews = session.scalars(
        select(FloorPlanInterpretationReview)
        .where(FloorPlanInterpretationReview.review_complete.is_(True))
        .order_by(FloorPlanInterpretationReview.id)
    ).all()

    for rev in reviews:
        doc = deserialize_review_document(rev.review_json, rev.review_sha256)
        if doc.dataset_approval is None or doc.dataset_approval.decision != "approved":
            continue

        run = session.get(FloorPlanInterpretationRun, rev.interpretation_run_id)
        if run is None:
            continue

        candidate = FloorPlanInterpretationCandidate.model_validate_json(run.candidate_json)

        # Ensure no unresolved elements
        all_items = (
            list(doc.walls)
            + list(doc.rooms)
            + list(doc.symbols)
            + list(doc.openings)
            + list(doc.panels)
            + list(doc.scale_evidence)
            + list(doc.observed_wiring)
        )
        if any(item.disposition == "unresolved" for item in all_items):
            continue

        # Build GoldAnnotationDocument
        truth_symbols: list[SymbolTruth] = []
        for sym in doc.symbols:
            if sym.disposition in ("accepted", "corrected", "added") and sym.class_id is not None:
                # Approximate bounding box around center if missing
                if sym.bbox is not None:
                    xmin, ymin, xmax, ymax = sym.bbox
                else:
                    xmin = max(0.0, sym.center.x - 10.0)
                    ymin = max(0.0, sym.center.y - 10.0)
                    xmax = min(float(candidate.payload.source_plane.width_pixels), sym.center.x + 10.0)
                    ymax = min(float(candidate.payload.source_plane.height_pixels), sym.center.y + 10.0)
                truth_symbols.append(
                    SymbolTruth(
                        symbol_id=sym.id,
                        class_id=sym.class_id,
                        x_min=xmin,
                        y_min=ymin,
                        x_max=xmax,
                        y_max=ymax,
                    )
                )

        truth_geometry: list[GeometryTruth] = []
        for wall in doc.walls:
            if wall.disposition in ("accepted", "corrected", "added"):
                truth_geometry.append(
                    GeometryTruth(
                        entity_id=wall.id,
                        kind="wall",
                        points=(wall.start, wall.end),
                    )
                )
        for room in doc.rooms:
            if room.disposition in ("accepted", "corrected", "added"):
                truth_geometry.append(
                    GeometryTruth(
                        entity_id=room.id,
                        kind="room",
                        points=room.boundary,
                    )
                )
        for op in doc.openings:
            if op.disposition in ("accepted", "corrected", "added"):
                truth_geometry.append(
                    GeometryTruth(
                        entity_id=op.id,
                        kind="opening",
                        points=op.points,
                    )
                )
        for pan in doc.panels:
            if pan.disposition in ("accepted", "corrected", "added"):
                truth_geometry.append(
                    GeometryTruth(
                        entity_id=pan.id,
                        kind="panel",
                        points=pan.points,
                    )
                )

        truth_wiring: list[ObservedWiringTruth] = []
        for wire in doc.observed_wiring:
            if wire.disposition in ("accepted", "corrected", "added"):
                truth_wiring.append(
                    ObservedWiringTruth(
                        route_id=wire.id,
                        points=wire.points,
                        completeness=wire.completeness,
                    )
                )

        truth_text: list[TextDimensionTruth] = []
        for sc in doc.scale_evidence:
            if sc.disposition in ("accepted", "corrected", "added"):
                truth_text.append(
                    TextDimensionTruth(
                        evidence_id=sc.id,
                        text=sc.text,
                        region=(
                            PixelPoint(x=0.0, y=0.0),
                            PixelPoint(x=sc.measured_pixels, y=10.0),
                        ),
                    )
                )

        markers = CompletenessMarkers(
            symbols=doc.checklist.symbols,
            geometry="complete" if doc.checklist.walls == "complete" and doc.checklist.rooms == "complete" else "pending",
            observed_wiring=doc.checklist.observed_wiring,
            text_dimensions=doc.checklist.scale_evidence,
        )

        gold_doc = GoldAnnotationDocument(
            schema_version=1,
            source_id=f"page-{run.floor_plan_page_id}",
            source_sha256=run.candidate_sha256,
            page_number=1,
            width_pixels=candidate.payload.source_plane.width_pixels,
            height_pixels=candidate.payload.source_plane.height_pixels,
            sheet_type="electrical_plan",
            symbols=tuple(truth_symbols),
            geometry=tuple(truth_geometry),
            observed_wiring=tuple(truth_wiring),
            text_dimensions=tuple(truth_text),
            completeness=markers,
        )

        filename = f"{run.candidate_run_id}_rev{doc.revision_number}.json"
        target_path = output_directory / filename
        target_path.write_text(gold_doc.model_dump_json(indent=2), encoding="utf-8")
        exported.append(gold_doc)

    return exported
