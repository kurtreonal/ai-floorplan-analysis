from __future__ import annotations

import json
import math
from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai.floor_plan_interpretation import FloorPlanInterpretationCandidate
from app.geometry import canonical_geometry_from_dict
from app.models import (
    FloorPlan,
    FloorPlanInterpretationReview,
    FloorPlanInterpretationRun,
    ManualSymbol,
    Project,
    ProjectFloor,
    SymbolLegend,
    User,
)
from app.repositories.floor_plan_interpretation_repository import (
    add_review,
    find_latest_for_floor_plan,
    find_latest_review,
    find_review_revision,
    next_review_revision,
)
from app.repositories.manual_symbol_repository import (
    add_manual_symbol,
    find_manual_symbol_by_request,
)
from app.schemas.demo_interpretation import DemoReviewRequest
from app.services.analysis_settings_service import (
    AnalysisSettingsError,
    require_approved_metric_inputs,
    retrieve_settings,
)
from app.services.layout_service import LayoutServiceError, save_owned_layout


SAFE_ERROR_MESSAGE = "The demo interpretation operation could not be completed."


class DemoInterpretationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(SAFE_ERROR_MESSAGE)


@dataclass(frozen=True)
class DemoInterpretationRecord:
    run: FloorPlanInterpretationRun
    candidate: FloorPlanInterpretationCandidate
    review: FloorPlanInterpretationReview | None
    review_document: dict[str, object] | None


def _fail(code: str) -> None:
    raise DemoInterpretationError(code)


def _candidate(run: FloorPlanInterpretationRun) -> FloorPlanInterpretationCandidate:
    if sha256(run.candidate_json.encode("utf-8")).hexdigest() != run.candidate_sha256:
        _fail("INTERPRETATION_INTEGRITY_FAILED")
    try:
        candidate = FloorPlanInterpretationCandidate.model_validate_json(
            run.candidate_json
        )
    except Exception:
        _fail("INTERPRETATION_INTEGRITY_FAILED")
    if candidate.provenance.candidate_run_id != run.candidate_run_id:
        _fail("INTERPRETATION_INTEGRITY_FAILED")
    return candidate


def _review_document(review: FloorPlanInterpretationReview) -> dict[str, object]:
    if sha256(review.review_json.encode("utf-8")).hexdigest() != review.review_sha256:
        _fail("REVIEW_INTEGRITY_FAILED")
    try:
        value = json.loads(review.review_json)
    except (TypeError, ValueError):
        _fail("REVIEW_INTEGRITY_FAILED")
    if type(value) is not dict:
        _fail("REVIEW_INTEGRITY_FAILED")
    return value


def _authorized_run(
    session: Session,
    *,
    current_user: User,
    floor_plan_id: int,
    write: bool,
) -> FloorPlanInterpretationRun:
    role = getattr(getattr(current_user, "role", None), "name", None)
    if role not in ({"DESIGNER"} if write else {"ADMIN", "DESIGNER"}):
        _fail("AUTHORIZATION_DENIED")
    statement = (
        select(FloorPlanInterpretationRun)
        .join(FloorPlan, FloorPlanInterpretationRun.floor_plan_id == FloorPlan.id)
        .join(ProjectFloor, FloorPlan.project_floor_id == ProjectFloor.id)
        .join(Project, ProjectFloor.project_id == Project.id)
        .where(FloorPlan.id == floor_plan_id)
    )
    if role == "DESIGNER":
        statement = statement.where(Project.owner_id == current_user.id)
    run = session.scalar(
        statement.order_by(FloorPlanInterpretationRun.id.desc()).limit(1)
    )
    if run is None:
        _fail("INTERPRETATION_NOT_FOUND")
    return run


def retrieve_interpretation(
    session: Session,
    *,
    current_user: User,
    floor_plan_id: int,
) -> DemoInterpretationRecord:
    try:
        run = _authorized_run(
            session,
            current_user=current_user,
            floor_plan_id=floor_plan_id,
            write=False,
        )
        review = find_latest_review(session, interpretation_run_id=run.id)
        return DemoInterpretationRecord(
            run=run,
            candidate=_candidate(run),
            review=review,
            review_document=None if review is None else _review_document(review),
        )
    except DemoInterpretationError:
        raise
    except SQLAlchemyError:
        session.rollback()
        _fail("INTERPRETATION_RETRIEVAL_FAILED")


def _unique_ids(values: list[object], label: str) -> None:
    identifiers = [value.id for value in values]
    if len(identifiers) != len(set(identifiers)):
        _fail(f"DUPLICATE_{label}_IDENTITY")


def _validate_bounds(point, *, width: int, height: int) -> None:
    if not (0 <= float(point.x) <= width and 0 <= float(point.y) <= height):
        _fail("REVIEW_COORDINATE_OUT_OF_BOUNDS")


def append_interpretation_review(
    session: Session,
    *,
    current_user: User,
    floor_plan_id: int,
    payload: DemoReviewRequest,
) -> DemoInterpretationRecord:
    try:
        run = _authorized_run(
            session,
            current_user=current_user,
            floor_plan_id=floor_plan_id,
            write=True,
        )
        candidate = _candidate(run)
        if payload.candidate_run_id != run.candidate_run_id:
            _fail("STALE_INTERPRETATION_RUN")
        latest = find_latest_review(session, interpretation_run_id=run.id)
        latest_revision = None if latest is None else latest.revision_number
        if payload.expected_revision_number != latest_revision:
            _fail("STALE_REVIEW_REVISION")

        _unique_ids(payload.walls, "WALL")
        _unique_ids(payload.rooms, "ROOM")
        _unique_ids(payload.symbols, "SYMBOL")
        expected = {
            "walls": {item.id for item in candidate.payload.walls.items},
            "rooms": {item.id for item in candidate.payload.rooms.items},
            "symbols": {item.id for item in candidate.payload.symbols.items},
        }
        supplied = {
            "walls": {item.id for item in payload.walls if not item.id.startswith("manual-")},
            "rooms": {item.id for item in payload.rooms if not item.id.startswith("manual-")},
            "symbols": {item.id for item in payload.symbols if not item.id.startswith("manual-")},
        }
        if any(not values.issubset(expected[name]) for name, values in supplied.items()):
            _fail("UNKNOWN_CANDIDATE_IDENTITY")
        if payload.review_complete and supplied != expected:
            _fail("REVIEW_INCOMPLETE")

        width = candidate.payload.source_plane.width_pixels
        height = candidate.payload.source_plane.height_pixels
        for wall in payload.walls:
            _validate_bounds(wall.start, width=width, height=height)
            _validate_bounds(wall.end, width=width, height=height)
        for room in payload.rooms:
            for point in room.boundary:
                _validate_bounds(point, width=width, height=height)
        for symbol in payload.symbols:
            _validate_bounds(symbol.center, width=width, height=height)

        legend_ids = {
            symbol.symbol_legend_id
            for symbol in payload.symbols
            if symbol.disposition == "accepted"
            and symbol.symbol_legend_id is not None
        }
        legends = {
            legend.id: legend
            for legend in session.scalars(
                select(SymbolLegend).where(
                    SymbolLegend.id.in_(legend_ids),
                    SymbolLegend.is_active.is_(True),
                )
            )
        }
        accepted_symbols = [
            symbol for symbol in payload.symbols if symbol.disposition == "accepted"
        ]
        if payload.review_complete and any(
            symbol.symbol_legend_id not in legends for symbol in accepted_symbols
        ):
            _fail("SYMBOL_MAPPING_REQUIRED")
        if payload.approved_for_layout and (
            not any(wall.disposition == "accepted" for wall in payload.walls)
            or not any(room.disposition == "accepted" for room in payload.rooms)
            or not accepted_symbols
        ):
            _fail("APPROVED_GEOMETRY_EMPTY")

        document = payload.model_dump(mode="json")
        document["symbols"] = [
            {
                **symbol.model_dump(mode="json"),
                "class_id": (
                    legends[symbol.symbol_legend_id].class_id
                    if symbol.symbol_legend_id in legends
                    else None
                ),
                "class_name": (
                    legends[symbol.symbol_legend_id].name
                    if symbol.symbol_legend_id in legends
                    else None
                ),
            }
            for symbol in payload.symbols
        ]
        document.pop("expected_revision_number")
        serialized = json.dumps(document, sort_keys=True, separators=(",", ":"))
        review = add_review(
            session,
            FloorPlanInterpretationReview(
                interpretation_run_id=run.id,
                revision_number=next_review_revision(
                    session,
                    interpretation_run_id=run.id,
                ),
                reviewed_by_user_id=current_user.id,
                review_complete=payload.review_complete,
                approved_for_layout=payload.approved_for_layout,
                review_sha256=sha256(serialized.encode("utf-8")).hexdigest(),
                review_json=serialized,
            ),
        )
        session.commit()
        session.refresh(review)
        return DemoInterpretationRecord(
            run=run,
            candidate=candidate,
            review=review,
            review_document=document,
        )
    except DemoInterpretationError:
        session.rollback()
        raise
    except IntegrityError:
        session.rollback()
        _fail("STALE_REVIEW_REVISION")
    except SQLAlchemyError:
        session.rollback()
        _fail("REVIEW_SAVE_FAILED")


def _numeric_identity(value: str) -> int:
    try:
        return int(value.rsplit("-", 1)[1])
    except (IndexError, TypeError, ValueError):
        _fail("REVIEW_INTEGRITY_FAILED")


def _placement_request_id(
    *,
    interpretation_run_id: int,
    review_id: int,
    symbol_id: str,
) -> str:
    """Return a deterministic UUID4-shaped key for one approved placement."""
    digest = bytearray(
        sha256(
            f"demo-review:{interpretation_run_id}:{review_id}:{symbol_id}".encode(
                "utf-8"
            )
        ).digest()[:16]
    )
    digest[6] = (digest[6] & 0x0F) | 0x40
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(UUID(bytes=bytes(digest)))


def _approved_manual_symbol(
    session: Session,
    *,
    current_user: User,
    run: FloorPlanInterpretationRun,
    review: FloorPlanInterpretationReview,
    symbol: dict[str, object],
    image_width: int,
    image_height: int,
    legend: SymbolLegend,
) -> ManualSymbol:
    request_id = _placement_request_id(
        interpretation_run_id=run.id,
        review_id=review.id,
        symbol_id=str(symbol["id"]),
    )
    expected = {
        "floor_plan_id": run.floor_plan_id,
        "processing_job_id": run.processing_job_id,
        "created_by_user_id": current_user.id,
        "symbol_legend_id": legend.id,
        "status": "manually_added",
        "class_id": legend.class_id,
        "class_name": legend.name,
        "center_x_pixels": float(symbol["center"]["x"]),
        "center_y_pixels": float(symbol["center"]["y"]),
        "image_width_pixels": image_width,
        "image_height_pixels": image_height,
    }
    existing = find_manual_symbol_by_request(
        session,
        created_by_user_id=current_user.id,
        placement_request_id=request_id,
        lock=True,
    )
    if existing is not None:
        if any(getattr(existing, key) != value for key, value in expected.items()):
            _fail("APPROVED_SYMBOL_PROVENANCE_CONFLICT")
        return existing
    record = ManualSymbol(placement_request_id=request_id, **expected)
    add_manual_symbol(session, record)
    return record


def save_approved_interpretation_layout(
    session: Session,
    *,
    current_user: User,
    project_id: int,
    project_floor_id: int,
    floor_plan_id: int,
    candidate_run_id: str,
    review_revision_number: int,
    expected_layout_version_number: int | None,
    idempotency_key: str,
):
    try:
        run = _authorized_run(
            session,
            current_user=current_user,
            floor_plan_id=floor_plan_id,
            write=True,
        )
        if run.candidate_run_id != candidate_run_id:
            _fail("STALE_INTERPRETATION_RUN")
        review = find_review_revision(
            session,
            interpretation_run_id=run.id,
            revision_number=review_revision_number,
        )
        if review is None or not review.review_complete or not review.approved_for_layout:
            _fail("LAYOUT_REVIEW_NOT_APPROVED")
        latest_review = find_latest_review(session, interpretation_run_id=run.id)
        if latest_review is None or latest_review.id != review.id:
            _fail("STALE_REVIEW_REVISION")
        document = _review_document(review)
        context = session.execute(
            select(ProjectFloor, FloorPlan)
            .join(FloorPlan, FloorPlan.project_floor_id == ProjectFloor.id)
            .where(
                ProjectFloor.id == project_floor_id,
                ProjectFloor.project_id == project_id,
                FloorPlan.id == floor_plan_id,
            )
        ).one_or_none()
        if context is None:
            _fail("INTERPRETATION_NOT_FOUND")
        floor, floor_plan = context
        settings = retrieve_settings(
            session,
            current_user=current_user,
            project_id=project_id,
            floor_id=project_floor_id,
        )
        candidate = _candidate(run)
        elevation, pixels_per_meter = require_approved_metric_inputs(
            settings,
            page_id=run.floor_plan_page_id,
            image_width=candidate.payload.source_plane.width_pixels,
            image_height=candidate.payload.source_plane.height_pixels,
        )
        scale = float(pixels_per_meter)

        walls = []
        for index, wall in enumerate(
            (item for item in document["walls"] if item["disposition"] == "accepted"),
            start=1,
        ):
            start = {axis: round(float(wall["start"][axis]) / scale, 9) for axis in ("x", "y")}
            end = {axis: round(float(wall["end"][axis]) / scale, 9) for axis in ("x", "y")}
            delta_x, delta_y = end["x"] - start["x"], end["y"] - start["y"]
            walls.append({
                "id": index,
                "source_candidate_id": None if wall["id"].startswith("manual-") else _numeric_identity(wall["id"]),
                "processing_job_id": run.processing_job_id,
                "status": "verified",
                "start": start,
                "end": end,
                "length_meters": round(math.hypot(delta_x, delta_y), 9),
                "angle_degrees": round(math.degrees(math.atan2(delta_y, delta_x)) % 180, 9),
                "thickness_meters": document["wall_thickness_meters"],
                "height_meters": document["wall_height_meters"],
            })
        rooms = [
            {
                "id": index,
                "name": room["name"],
                "boundary": [
                    {axis: round(float(point[axis]) / scale, 9) for axis in ("x", "y")}
                    for point in room["boundary"]
                ],
            }
            for index, room in enumerate(
                (item for item in document["rooms"] if item["disposition"] == "accepted"),
                start=1,
            )
        ]
        accepted_symbols = [
            item for item in document["symbols"] if item["disposition"] == "accepted"
        ]
        legend_ids = {item["symbol_legend_id"] for item in accepted_symbols}
        legends = {
            legend.id: legend
            for legend in session.scalars(
                select(SymbolLegend).where(
                    SymbolLegend.id.in_(legend_ids),
                    SymbolLegend.is_active.is_(True),
                )
            )
        }
        if len(legends) != len(legend_ids) or any(
            item["class_id"] != legends[item["symbol_legend_id"]].class_id
            or item["class_name"] != legends[item["symbol_legend_id"]].name
            for item in accepted_symbols
        ):
            _fail("SYMBOL_MAPPING_REQUIRED")

        symbols = []
        for symbol in accepted_symbols:
            # K1 remains frozen: an accepted interpretation proposal is persisted as
            # a real human-approved manual placement. The immutable run/review retain
            # its machine provenance; it is never mislabeled as a legacy YOLO row.
            manual_record = _approved_manual_symbol(
                session,
                current_user=current_user,
                run=run,
                review=review,
                symbol=symbol,
                image_width=candidate.payload.source_plane.width_pixels,
                image_height=candidate.payload.source_plane.height_pixels,
                legend=legends[symbol["symbol_legend_id"]],
            )
            symbols.append({
                "id": f"manual:{manual_record.id}",
                "source_type": "manual",
                "source_record_id": manual_record.id,
                "processing_job_id": run.processing_job_id,
                "status": "manually_added",
                "class": {
                    "id": manual_record.class_id,
                    "name": manual_record.class_name,
                },
                "position": {
                    "x": round(float(symbol["center"]["x"]) / scale, 9),
                    "y": round(float(symbol["center"]["y"]) / scale, 9),
                },
            })
        geometry = canonical_geometry_from_dict({
            "schema_version": 1,
            "project_id": project_id,
            "floor": {
                "project_floor_id": project_floor_id,
                "name": floor.name,
                "sort_order": floor.sort_order,
                "elevation_meters": elevation,
            },
            "floor_plan_id": floor_plan.id,
            "coordinate_system": {
                "unit": "meter",
                "origin": "image_top_left",
                "x_direction": "right",
                "y_direction": "down",
                "pixels_per_meter": scale,
                "image_width_pixels": candidate.payload.source_plane.width_pixels,
                "image_height_pixels": candidate.payload.source_plane.height_pixels,
                "width_meters": round(candidate.payload.source_plane.width_pixels / scale, 9),
                "height_meters": round(candidate.payload.source_plane.height_pixels / scale, 9),
            },
            "walls": walls,
            "rooms": rooms,
            "symbols": symbols,
            "routes": [],
        })
        return save_owned_layout(
            session,
            current_user=current_user,
            project_id=project_id,
            project_floor_id=project_floor_id,
            geometry_payload=geometry.to_dict(),
            expected_version_number=expected_layout_version_number,
            idempotency_key=idempotency_key,
        )
    except DemoInterpretationError:
        session.rollback()
        raise
    except AnalysisSettingsError as error:
        session.rollback()
        _fail(error.code)
    except LayoutServiceError as error:
        session.rollback()
        _fail(error.code)
    except SQLAlchemyError:
        session.rollback()
        _fail("LAYOUT_SAVE_FAILED")
