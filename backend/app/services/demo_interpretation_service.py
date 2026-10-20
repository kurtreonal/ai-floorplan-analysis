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
    find_latest_previous_review,
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
from app.services.wiring_legend_service import annotate_wiring
from app.routing.endpoint_connections import connect_touching_endpoints
from app.repositories.analysis_settings_repository import latest_elevation, latest_scales


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
    generated_wiring: list[dict] | None = None
    draft_wiring_limitations: list[str] | None = None
    observed_wiring: list[dict] | None = None
    draft_walls: list[dict] | None = None
    draft_review: dict | None = None
    routing_context: dict | None = None


def _routing_context(session, run):
    floor = session.get(FloorPlan, run.floor_plan_id).project_floor_id
    elevation = latest_elevation(session, floor)
    scale = latest_scales(session,[run.floor_plan_page_id]).get(run.floor_plan_page_id)
    plane = _candidate(run).payload.source_plane
    ppm = float(scale.pixels_per_meter) if scale and scale.pixels_per_meter is not None and (
        scale.reference_width_pixels,scale.reference_height_pixels)==(plane.width_pixels,plane.height_pixels) else None
    return {'floor_elevation_meters': float(elevation.elevation_meters)
            if elevation and elevation.elevation_meters is not None else None,
            'pixels_per_meter':ppm}


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
    processing_job_id: int | None = None,
) -> FloorPlanInterpretationRun:
    role = getattr(getattr(current_user, "role", None), "name", None)
    if role not in ({"DESIGNER"} if write else {"ADMIN", "DESIGNER"}):
        _fail("AUTHORIZATION_DENIED")
    if write:
        from app.repositories.floor_plan_lifecycle_repository import lock_active_plan
        if lock_active_plan(session, floor_plan_id) is None:
            _fail("INTERPRETATION_NOT_FOUND")
    statement = (
        select(FloorPlanInterpretationRun)
        .join(FloorPlan, FloorPlanInterpretationRun.floor_plan_id == FloorPlan.id)
        .join(ProjectFloor, FloorPlan.project_floor_id == ProjectFloor.id)
        .join(Project, ProjectFloor.project_id == Project.id)
        .where(FloorPlan.id == floor_plan_id)
    )
    if role == "DESIGNER":
        statement = statement.where(Project.owner_id == current_user.id)
    if processing_job_id is not None:
        statement = statement.where(FloorPlanInterpretationRun.processing_job_id == processing_job_id)
    run = session.scalar(
        statement.order_by(FloorPlanInterpretationRun.processing_job_id.desc(), FloorPlanInterpretationRun.id.desc()).limit(1)
    )
    if run is None:
        _fail("INTERPRETATION_NOT_FOUND")
    return run


def retrieve_interpretation(
    session: Session,
    *,
    current_user: User,
    floor_plan_id: int,
    processing_job_id: int | None = None,
) -> DemoInterpretationRecord:
    try:
        run = _authorized_run(
            session,
            current_user=current_user,
            floor_plan_id=floor_plan_id,
            write=False,
            processing_job_id=processing_job_id,
        )
        review = find_latest_review(session, interpretation_run_id=run.id)
        candidate = _candidate(run)
        document = None if review is None else _review_document(review)
        inherited = {}
        if review is None:
            previous = find_latest_previous_review(session, run=run)
            if previous is not None:
                from app.ai.floor_plan_interpretation.reviewed_reference import inherit_review_draft
                inherited = inherit_review_draft(candidate, _candidate(previous[0]),
                                                      _review_document(previous[1]))
                document = inherited or None
        drawing_name=session.get(FloorPlan,run.floor_plan_id).original_filename
        document = annotate_wiring(session,candidate,document,drawing_name=drawing_name)
        from app.routing.draft_wiring import generate_draft_wiring
        generated, limitations = generate_draft_wiring(candidate, document)
        document=annotate_wiring(session,candidate,{**document,'generated_wiring':generated},
                                 drawing_name=drawing_name)
        document = connect_touching_endpoints(candidate, document)
        generated=document['generated_wiring']
        return DemoInterpretationRecord(
            run=run,
            candidate=candidate,
            review=review,
            review_document=document,
            generated_wiring=generated,
            draft_wiring_limitations=limitations,
            observed_wiring=document.get("observed_wiring",[]),
            draft_walls=inherited.get('walls'),
            draft_review=inherited or None,
            routing_context=_routing_context(session, run),
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
        _unique_ids(payload.observed_wiring, "WIRING")
        _unique_ids(payload.generated_wiring, "GENERATED_WIRING")
        if {w.id for w in payload.observed_wiring} & {w.id for w in payload.generated_wiring}:
            _fail("DUPLICATE_WIRING_IDENTITY")
        expected = {
            "walls": {item.id for item in candidate.payload.walls.items},
            "rooms": {item.id for item in candidate.payload.rooms.items},
            "symbols": {item.id for item in candidate.payload.symbols.items},
            "wiring": {item.id for item in candidate.payload.observed_routes.segments},
        }
        supplied = {
            "walls": {item.id for item in payload.walls if not item.id.startswith("manual-")},
            "rooms": {item.id for item in payload.rooms if not item.id.startswith("manual-")},
            "symbols": {item.id for item in payload.symbols if not item.id.startswith("manual-")},
            "wiring": {item.id for item in payload.observed_wiring if not item.id.startswith("manual-")},
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
        for wire in payload.observed_wiring:
            for point in wire.points:
                _validate_bounds(point, width=width, height=height)
            if payload.approved_for_layout and wire.disposition in ("accepted", "corrected", "added"):
                if wire.completeness != "complete":
                    _fail("OBSERVED_WIRING_INCOMPLETE")
                if wire.elevation_meters is None:
                    _fail("OBSERVED_WIRING_ELEVATION_REQUIRED")

        # Generated drafts never enter observed wiring, canonical quantities or
        # dataset completeness. Their anchors must belong to this saved draft.
        symbol_ids = {s.id for s in payload.symbols}
        active_symbols = {s.id: s for s in payload.symbols if s.disposition != 'rejected'}
        active_wall_ids = {w.id for w in payload.walls if w.disposition != 'rejected'}
        if any(s.mounting_wall_id is not None and s.mounting_wall_id not in active_wall_ids for s in active_symbols.values()):
            _fail('INVALID_DEVICE_ATTACHMENT')
        for wire in [*payload.observed_wiring, *payload.generated_wiring]:
            if wire.disposition == 'rejected':
                continue  # A historical tombstone is not an active connection.
            for attachment in wire.device_attachments:
                symbol = active_symbols.get(attachment.symbol_id)
                if symbol is None or wire.points[attachment.point_index] != symbol.center:
                    _fail('INVALID_DEVICE_ATTACHMENT')
                if attachment.provenance == 'source_supported_proposal':
                    evidence_run = session.scalar(select(FloorPlanInterpretationRun).where(
                        FloorPlanInterpretationRun.floor_plan_id == run.floor_plan_id,
                        FloorPlanInterpretationRun.candidate_run_id == attachment.source_candidate_run_id))
                    evidence_candidate = _candidate(evidence_run) if evidence_run else None
                    contact = next((c for c in evidence_candidate.payload.observed_routes.connections
                        if c.id == attachment.source_connection_id),None) if evidence_candidate else None
                    if (contact is None or contact.ambiguity != 'unambiguous'
                        or contact.evidence_kind != attachment.evidence_kind
                        or contact.path_anchor.model_dump() != attachment.observed_anchor.model_dump()
                        or evidence_candidate.provenance.source_sha256 != candidate.provenance.source_sha256):
                        _fail('INVALID_DEVICE_ATTACHMENT')
                    if attachment.terminal_id is not None:
                        from app.routing.endpoint_connections import source_terminal_id
                        if attachment.terminal_id != source_terminal_id(contact): _fail('INVALID_DEVICE_ATTACHMENT')
            for attachment in wire.junction_attachments:
                if attachment.source_candidate_run_id is None:continue
                evidence_run=session.scalar(select(FloorPlanInterpretationRun).where(
                    FloorPlanInterpretationRun.floor_plan_id==run.floor_plan_id,
                    FloorPlanInterpretationRun.floor_plan_page_id==run.floor_plan_page_id,
                    FloorPlanInterpretationRun.candidate_run_id==attachment.source_candidate_run_id))
                evidence_candidate=_candidate(evidence_run) if evidence_run else None
                junction=next((j for j in evidence_candidate.payload.observed_routes.junctions
                    if j.id==attachment.source_junction_id),None) if evidence_candidate else None
                if junction is None or evidence_candidate.provenance.source_sha256!=candidate.provenance.source_sha256:
                    _fail('INVALID_DEVICE_ATTACHMENT')
                member=junction.members[0]
                source_route=next(r for r in evidence_candidate.payload.observed_routes.segments if r.id==member.segment_id)
                if source_route.points[member.point_index].model_dump()!=attachment.observed_anchor.model_dump():
                    _fail('INVALID_DEVICE_ATTACHMENT')
        trace_ids = {w.id for w in payload.observed_wiring}
        for wire in payload.generated_wiring:
            if wire.source_device_id not in symbol_ids or wire.target_id not in (
                    symbol_ids if wire.target_kind == "device" else trace_ids):
                _fail("UNKNOWN_CANDIDATE_IDENTITY")
            for point in wire.points:
                _validate_bounds(point, width=width, height=height)

        legend_ids = {
            symbol.symbol_legend_id
            for symbol in payload.symbols
            if symbol.disposition != "rejected"
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
            symbol for symbol in payload.symbols if symbol.disposition in ("accepted", "corrected", "added")
        ]
        from app.services.pdf_legend_catalog import is_wiring_legend
        if any(symbol.disposition != "rejected" and symbol.symbol_legend_id in legends
               and is_wiring_legend(legends[symbol.symbol_legend_id].name)
               for symbol in payload.symbols):
            _fail("SYMBOL_MAPPING_REQUIRED")
        if payload.review_complete:
            provisional_defaults={s.id for s in candidate.payload.symbols.items if s.gang_count_proposal
                and s.gang_count_proposal.basis=='user_requested_default'}
            if any(s.id in provisional_defaults and not s.gang_count_confirmed for s in accepted_symbols):
                _fail('PROVISIONAL_SWITCH_COUNT_REQUIRES_CORRECTION')
            if payload.checklist is not None and not payload.checklist.complete:
                _fail("CHECKLIST_PENDING")
            all_items = (
                list(payload.walls)
                + list(payload.rooms)
                + list(payload.symbols)
                + list(payload.openings)
                + list(payload.panels)
                + list(payload.scale_evidence)
                + list(payload.observed_wiring)
            )
            if any(item.disposition == "unresolved" for item in all_items):
                _fail("REVIEW_HAS_UNRESOLVED_TARGETS")
            if any(
                symbol.symbol_legend_id not in legends for symbol in accepted_symbols
            ):
                _fail("SYMBOL_MAPPING_REQUIRED")

        accepted_walls = [
            wall for wall in payload.walls if wall.disposition in ("accepted", "corrected", "added")
        ]
        if payload.approved_for_layout and (
            not accepted_walls and not accepted_symbols
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
        # Compatibility: older clients detach by removing an attachment. Persist
        # that intent as an endpoint opt-out instead of immediately reattaching.
        previous_document = _review_document(latest) if latest else {}
        previous_wires = {w['id']: w for key in ('observed_wiring','generated_wiring')
                          for w in previous_document.get(key, [])}
        for key in ('observed_wiring','generated_wiring'):
            for wire in document.get(key, []):
                occupied = {a['point_index'] for a in wire.get('device_attachments', [])}
                removed = {a['point_index'] for a in previous_wires.get(wire['id'], {}).get('device_attachments', [])} - occupied
                endpoints = set(range(len(wire['points'])))
                wire['auto_connect_disabled_endpoints'] = sorted((set(wire.get('auto_connect_disabled_endpoints', [])) | removed) & endpoints - occupied)
        drawing_name=session.get(FloorPlan,run.floor_plan_id).original_filename
        document = annotate_wiring(session,candidate,document,drawing_name=drawing_name)
        from app.routing.draft_wiring import generate_draft_wiring
        generated, limitations = generate_draft_wiring(candidate, document)
        document["generated_wiring"] = generated
        document=annotate_wiring(session,candidate,document,drawing_name=drawing_name)
        document = connect_touching_endpoints(candidate, document)
        generated = document['generated_wiring']
        from app.geometry.wire_network import wire_networks
        try:
            wire_networks(document.get('observed_wiring', []) + [dict(w,origin='generated') for w in generated])
        except ValueError:
            _fail('INVALID_WIRING_JUNCTION')
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
            generated_wiring=generated,
            draft_wiring_limitations=limitations,
            observed_wiring=document.get("observed_wiring",[]),
            routing_context=_routing_context(session, run),
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
        if any(w.code=='separate_source_views' for w in candidate.payload.warnings):
            # One project floor cannot silently accept ground/mezzanine sheet coordinates
            # as one physical floor. Unfinished reviews are still freely saveable.
            _fail('SOURCE_VIEW_ASSIGNMENT_REQUIRED')
        elevation, pixels_per_meter = require_approved_metric_inputs(
            settings,
            page_id=run.floor_plan_page_id,
            image_width=candidate.payload.source_plane.width_pixels,
            image_height=candidate.payload.source_plane.height_pixels,
        )
        scale = float(pixels_per_meter)

        walls = []
        wall_id_map = {}
        for index, wall in enumerate(
            (item for item in document["walls"] if item["disposition"] in ("accepted", "corrected", "added")),
            start=1,
        ):
            start = {axis: round(float(wall["start"][axis]) / scale, 9) for axis in ("x", "y")}
            wall_id_map[wall['id']] = index
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
                "thickness_meters": wall.get("thickness_meters") or document["wall_thickness_meters"],
                "height_meters": wall.get("height_meters") or document["wall_height_meters"],
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
                (item for item in document["rooms"] if item["disposition"] in ("accepted", "corrected", "added")),
                start=1,
            )
        ]
        accepted_symbols = [
            item for item in document["symbols"] if item["disposition"] in ("accepted", "corrected", "added")
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
        from app.services.pdf_legend_catalog import is_wiring_legend
        if len(legends) != len(legend_ids) or any(
            is_wiring_legend(legend.name) for legend in legends.values()
        ) or any(
            item["class_id"] != legends[item["symbol_legend_id"]].class_id
            or item["class_name"] != legends[item["symbol_legend_id"]].name
            for item in accepted_symbols
        ):
            _fail("SYMBOL_MAPPING_REQUIRED")

        symbols = []
        symbol_id_map = {}
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
            symbol_id_map[symbol['id']] = symbols[-1]['id']
        draft_symbols = {s['id']: s for s in accepted_symbols}
        for wire in document.get("observed_wiring", []):
            if wire["disposition"] not in ("accepted", "corrected", "added"):
                continue
            if wire["completeness"] != "complete":
                _fail("OBSERVED_WIRING_INCOMPLETE")
            if wire.get("elevation_meters") is None:
                _fail("OBSERVED_WIRING_ELEVATION_REQUIRED")
            for attachment in wire.get('device_attachments', []):
                symbol = draft_symbols.get(attachment['symbol_id'])
                if symbol is None or symbol.get('mounting_height_meters') is None:
                    _fail('DEVICE_MOUNTING_HEIGHT_REQUIRED')
        from app.geometry.observed_connections import observed_connection_routes
        routes,route_details,connection_v4=observed_connection_routes(document.get('observed_wiring',[]),
            draft_symbols,symbol_id_map,floor_id=project_floor_id,floor_elevation=elevation,scale=scale,
            provenance=f'vlm:{candidate_run_id}:review:{review_revision_number}')
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
            "routes": routes,
        })
        openings = []
        for index, op in enumerate(
            (item for item in document.get("openings", []) if item.get("disposition") in ("accepted", "corrected", "added")),
            start=1,
        ):
            pts = op.get("points", [])
            if len(pts) >= 2:
                openings.append({
                    "id": index,
                    "source_candidate_id": op.get("id"),
                    "opening_type": op.get("kind", "unknown"),
                    "start": {axis: round(float(pts[0][axis]) / scale, 9) for axis in ("x", "y")},
                    "end": {axis: round(float(pts[1][axis]) / scale, 9) for axis in ("x", "y")},
                    "associated_wall_id": None,
                })

        panels = []
        for index, pan in enumerate(
            (item for item in document.get("panels", []) if item.get("disposition") in ("accepted", "corrected", "added")),
            start=1,
        ):
            pts = pan.get("points", [])
            if pts:
                panels.append({
                    "id": index,
                    "source_candidate_id": pan.get("id"),
                    "name": pan.get("name"),
                    "position": {axis: round(float(pts[0][axis]) / scale, 9) for axis in ("x", "y")},
                    "orientation_degrees": None,
                    "bounds": None,
                })

        installations = {symbol_id_map[s['id']]: {
            'elevation_meters': float(elevation) + s['mounting_height_meters'],
            'wall_id': wall_id_map.get(s.get('mounting_wall_id')),
        } for s in accepted_symbols if s.get('mounting_height_meters') is not None}
        for symbol in accepted_symbols:
            wall_id = wall_id_map.get(symbol.get('mounting_wall_id'))
            if wall_id is None:
                continue
            wall = next(w for w in walls if w['id'] == wall_id)
            a, b = wall['start'], wall['end']
            x, y = symbol['center']['x']/scale, symbol['center']['y']/scale
            dx, dy = b['x']-a['x'], b['y']-a['y']
            t = max(0., min(1., ((x-a['x'])*dx+(y-a['y'])*dy)/(dx*dx+dy*dy)))
            if math.hypot(x-a['x']-t*dx, y-a['y']-t*dy) > wall['thickness_meters']/2 + 1e-8:
                _fail('DEVICE_NOT_ON_MOUNTING_WALL')
        symbol_details = [
            {
                "symbol_id": sym["id"],
                "orientation_degrees": None,
                "bounds": None,
                "provenance": f"vlm:{candidate_run_id}:symbol:{sym['id']}",
                **({'installation': installations[sym['id']]} if sym['id'] in installations else {}),
            }
            for sym in symbols
        ]

        extension = {
            "extension_schema_version": 6 if any(d.get('route_kind') == 'manual' or d.get('vertex_ids') or d.get('network_lineage') or any(c.get('terminal_id') for c in d.get('device_connections',[])) for d in route_details) else 5 if any('junction_connections' in detail for detail in route_details) else 4 if connection_v4 else 3 if installations else 2,
            "base_schema_version": 1,
            "source_plane_reference": {
                "floor_plan_page_id": run.floor_plan_page_id,
                "source_artifact_id": run.source_artifact_id,
                "width_pixels": candidate.payload.source_plane.width_pixels,
                "height_pixels": candidate.payload.source_plane.height_pixels,
            },
            "openings": openings,
            "panels": panels,
            "symbol_details": symbol_details,
            "route_details": route_details,
        }

        return save_owned_layout(
            session,
            current_user=current_user,
            project_id=project_id,
            project_floor_id=project_floor_id,
            geometry_payload=geometry.to_dict(),
            expected_version_number=expected_layout_version_number,
            idempotency_key=idempotency_key,
            extension_payload=extension,
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
