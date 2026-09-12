import copy
from datetime import UTC, datetime
import json
from pathlib import Path
import unittest
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ai.floor_plan_interpretation.candidate import (
    CandidateHostProvenance,
    FloorPlanInterpretationCandidate,
    FloorPlanInterpretationPayload,
    PageAssessment,
    PageSignals,
    SourcePlane,
)
from app.ai.floor_plan_interpretation.pseudo_labeling import (
    CompletenessChecklist,
    ObservedWiringReview,
    OpeningReview,
    PanelReview,
    PixelPoint,
    ReviewDocument,
    RoomReview,
    SymbolReview,
    WallReview,
)
from app.core.database import get_engine
from app.geometry import (
    CanonicalExtensionV2,
    CanonicalGeometryDocument,
    CanonicalGeometryError,
    CanonicalOpening,
    CanonicalPanel,
    CanonicalRouteDetail,
    CanonicalSymbolDetail,
    SourcePlaneReference,
    adapt_reviewed_candidate_to_canonical,
    canonical_extension_from_dict,
    canonical_geometry_from_dict,
    compose_canonical_view,
)
from app.models import (
    Base,
    FloorPlan,
    LayoutSaveRequest,
    LayoutVersion,
    Project,
    ProjectFloor,
    Role,
    SymbolLegend,
    User,
)
from app.services.canonical_extension_storage import (
    delete_canonical_extension,
    retrieve_canonical_extension,
    save_canonical_extension,
)
from app.services.layout_version_service import (
    LayoutVersionServiceError,
    retrieve_current_layout_version,
    retrieve_layout_version,
    save_layout_snapshot_conditionally,
)

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"
BASE_FIXTURE_PATH = FIXTURES_DIR / "canonical_geometry_v1.json"
EXT_V2_PATH = FIXTURES_DIR / "canonical_extension_v2.json"
EMPTY_PATH = FIXTURES_DIR / "canonical_extension_v2_empty.json"
PARTIAL_PATH = FIXTURES_DIR / "canonical_extension_v2_partial.json"
MALFORMED_PATH = FIXTURES_DIR / "canonical_extension_v2_malformed.json"
UNSUPPORTED_PATH = FIXTURES_DIR / "canonical_extension_v2_unsupported.json"


class CanonicalExtensionTests(unittest.TestCase):
    def setUp(self):
        self.base_payload = json.loads(BASE_FIXTURE_PATH.read_text(encoding="utf-8"))
        self.base_doc = canonical_geometry_from_dict(self.base_payload)
        self.ext_v2_payload = json.loads(EXT_V2_PATH.read_text(encoding="utf-8"))
        self.empty_payload = json.loads(EMPTY_PATH.read_text(encoding="utf-8"))
        self.partial_payload = json.loads(PARTIAL_PATH.read_text(encoding="utf-8"))
        self.malformed_payload = json.loads(MALFORMED_PATH.read_text(encoding="utf-8"))
        self.unsupported_payload = json.loads(UNSUPPORTED_PATH.read_text(encoding="utf-8"))

    def test_database_table_count_remains_25(self):
        self.assertEqual(len(Base.metadata.tables), 25)

    def test_accepts_representative_v2_fixture(self):
        extension = canonical_extension_from_dict(self.ext_v2_payload, self.base_doc)
        self.assertIsInstance(extension, CanonicalExtensionV2)
        self.assertEqual(extension.extension_schema_version, 2)
        self.assertEqual(extension.base_schema_version, 1)
        self.assertEqual(len(extension.openings), 1)
        self.assertEqual(len(extension.panels), 1)
        self.assertEqual(len(extension.symbol_details), 2)
        self.assertEqual(len(extension.route_details), 1)
        self.assertEqual(extension.to_dict(), self.ext_v2_payload)

    def test_accepts_empty_extension_fixture(self):
        extension = canonical_extension_from_dict(self.empty_payload, self.base_doc)
        self.assertEqual(len(extension.openings), 0)
        self.assertEqual(len(extension.panels), 0)
        self.assertEqual(len(extension.symbol_details), 0)
        self.assertEqual(len(extension.route_details), 0)

    def test_accepts_partial_extension_fixture(self):
        extension = canonical_extension_from_dict(self.partial_payload, self.base_doc)
        self.assertEqual(len(extension.openings), 1)
        self.assertEqual(extension.openings[0].opening_type, "unknown")

    def test_rejects_malformed_extension_fixture(self):
        with self.assertRaises(CanonicalGeometryError) as cm:
            canonical_extension_from_dict(self.malformed_payload, self.base_doc)
        self.assertEqual(cm.exception.code, "INVALID_SOURCE_PLANE_REFERENCE")

    def test_rejects_unsupported_extension_version(self):
        with self.assertRaises(CanonicalGeometryError) as cm:
            canonical_extension_from_dict(self.unsupported_payload, self.base_doc)
        self.assertEqual(cm.exception.code, "UNSUPPORTED_EXTENSION_VERSION")

    def test_rejects_symbol_detail_referencing_nonexistent_base_symbol(self):
        payload = copy.deepcopy(self.ext_v2_payload)
        payload["symbol_details"].append({
            "symbol_id": "detected:99999",
            "orientation_degrees": None,
            "bounds": None,
            "provenance": None,
        })
        with self.assertRaises(CanonicalGeometryError) as cm:
            canonical_extension_from_dict(payload, self.base_doc)
        self.assertEqual(cm.exception.code, "EXTENSION_CROSS_REFERENCE_FAILED")

    def test_rejects_route_detail_referencing_nonexistent_base_route(self):
        payload = copy.deepcopy(self.ext_v2_payload)
        payload["route_details"].append({
            "route_id": 99999,
            "route_kind": "observed",
            "provenance_ref": None,
        })
        with self.assertRaises(CanonicalGeometryError) as cm:
            canonical_extension_from_dict(payload, self.base_doc)
        self.assertEqual(cm.exception.code, "EXTENSION_CROSS_REFERENCE_FAILED")

    def test_rejects_opening_referencing_nonexistent_base_wall(self):
        payload = copy.deepcopy(self.ext_v2_payload)
        payload["openings"][0]["associated_wall_id"] = 99999
        with self.assertRaises(CanonicalGeometryError) as cm:
            canonical_extension_from_dict(payload, self.base_doc)
        self.assertEqual(cm.exception.code, "EXTENSION_CROSS_REFERENCE_FAILED")

    def test_rejects_dimension_mismatch_with_base_coordinate_system(self):
        payload = copy.deepcopy(self.ext_v2_payload)
        payload["source_plane_reference"]["width_pixels"] = 1000
        with self.assertRaises(CanonicalGeometryError) as cm:
            canonical_extension_from_dict(payload, self.base_doc)
        self.assertEqual(cm.exception.code, "INVALID_SOURCE_PLANE_REFERENCE")

    def test_rejects_duplicate_opening_ids(self):
        payload = copy.deepcopy(self.ext_v2_payload)
        payload["openings"].append(payload["openings"][0])
        with self.assertRaises(CanonicalGeometryError) as cm:
            canonical_extension_from_dict(payload, self.base_doc)
        self.assertEqual(cm.exception.code, "INVALID_OPENING")

    def test_compose_canonical_view(self):
        extension = canonical_extension_from_dict(self.ext_v2_payload, self.base_doc)
        view = compose_canonical_view(self.base_doc, extension)
        self.assertEqual(view["schema_version"], 1)
        self.assertIn("extension", view)
        self.assertEqual(view["extension"]["extension_schema_version"], 2)

        view_none = compose_canonical_view(self.base_doc, None)
        self.assertIsNone(view_none["extension"])

    def test_extension_storage_lifecycle(self):
        extension = canonical_extension_from_dict(self.ext_v2_payload, self.base_doc)
        test_layout_version_id = 999998
        try:
            path, sha = save_canonical_extension(test_layout_version_id, extension)
            self.assertTrue(path.is_file())
            self.assertEqual(len(sha), 64)

            retrieved = retrieve_canonical_extension(test_layout_version_id, self.base_doc)
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.to_dict(), extension.to_dict())

            deleted = delete_canonical_extension(test_layout_version_id)
            self.assertTrue(deleted)
            self.assertFalse(path.is_file())
            self.assertIsNone(retrieve_canonical_extension(test_layout_version_id))
        finally:
            delete_canonical_extension(test_layout_version_id)


class AdaptationAndPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = get_engine()
        cls.marker = f"u11-{uuid4().hex[:12]}"
        with Session(cls.engine) as session:
            role = session.scalar(select(Role).where(Role.name == "DESIGNER"))
            if role is None:
                raise unittest.SkipTest("DESIGNER role required")
            cls.user = User(
                oauth_provider=cls.marker,
                oauth_subject="designer",
                role=role,
            )
            cls.project = Project(owner=cls.user, name=f"U11 Project {cls.marker}")
            cls.floor = ProjectFloor(project=cls.project, name="Ground Floor", sort_order=0)
            cls.plan = FloorPlan(
                project_floor=cls.floor,
                original_filename="u11-plan.png",
                storage_path="originals/u11-plan.png",
                mime_type="image/png",
                file_size=500,
                processing_status="processed",
            )
            cls.legend = SymbolLegend(
                class_id=1234,
                name="Duplex Receptacle",
                is_active=True,
            )
            session.add_all((cls.user, cls.project, cls.floor, cls.plan, cls.legend))
            session.commit()
            cls.user_id = cls.user.id
            cls.project_id = cls.project.id
            cls.floor_id = cls.floor.id
            cls.plan_id = cls.plan.id
            cls.legend_id = cls.legend.id

    @classmethod
    def tearDownClass(cls):
        with Session(cls.engine) as session:
            session.execute(delete(LayoutSaveRequest).where(LayoutSaveRequest.project_floor_id == cls.floor_id))
            session.execute(delete(LayoutVersion).where(LayoutVersion.project_floor_id == cls.floor_id))
            session.execute(delete(FloorPlan).where(FloorPlan.id == cls.plan_id))
            session.execute(delete(ProjectFloor).where(ProjectFloor.id == cls.floor_id))
            session.execute(delete(Project).where(Project.id == cls.project_id))
            session.execute(delete(SymbolLegend).where(SymbolLegend.id == cls.legend_id))
            session.execute(delete(User).where(User.id == cls.user_id))
            session.commit()

    def _sample_candidate(self) -> FloorPlanInterpretationCandidate:
        empty_payload_dict = json.loads(
            (FIXTURES_DIR / "floor_plan_interpretation_candidate_empty_v1.json").read_text(encoding="utf-8")
        )
        payload = FloorPlanInterpretationPayload.model_validate(empty_payload_dict)
        provenance = CandidateHostProvenance(
            candidate_run_id="c" * 32,
            processing_job_id=1,
            floor_plan_source_id=1,
            floor_plan_page_id=1,
            source_artifact_id=1,
            source_page_number=1,
            source_sha256="a" * 64,
            source_artifact_sha256="b" * 64,
            expected_width_pixels=640,
            expected_height_pixels=480,
            model_release_id="ved-vlm-v1",
            base_model_revision="base-r1",
            adapter_revision="adapter-r1",
            prompt_version="v1_0",
            runtime_version="rt_1_0",
            inference_parameters=(),
            created_at=datetime.now(UTC),
        )
        return FloorPlanInterpretationCandidate(
            provenance=provenance,
            payload=payload,
        )

    def _sample_review(self, approved: bool = True, complete: bool = True) -> ReviewDocument:
        checklist = CompletenessChecklist(
            symbols="complete",
            walls="complete",
            rooms="complete",
            openings="complete",
            panels="complete",
            scale_evidence="complete",
            observed_wiring="complete",
        )
        walls = (
            WallReview(
                id="wall-0001",
                disposition="accepted",
                start=PixelPoint(x=100.0, y=100.0),
                end=PixelPoint(x=300.0, y=100.0),
            ),
        )
        rooms = (
            RoomReview(
                id="room-0001",
                disposition="accepted",
                name="Conference Room",
                boundary=(
                    PixelPoint(x=50.0, y=50.0),
                    PixelPoint(x=350.0, y=50.0),
                    PixelPoint(x=350.0, y=250.0),
                    PixelPoint(x=50.0, y=250.0),
                ),
            ),
        )
        symbols = (
            SymbolReview(
                id="sym-0001",
                disposition="accepted",
                center=PixelPoint(x=200.0, y=200.0),
                bbox=(190.0, 190.0, 210.0, 210.0),
                symbol_legend_id=self.legend_id,
                class_id=1234,
                class_name="Duplex Receptacle",
            ),
        )
        openings = (
            OpeningReview(
                id="opening-0001",
                disposition="accepted",
                kind="door",
                points=(
                    PixelPoint(x=120.0, y=100.0),
                    PixelPoint(x=160.0, y=100.0),
                ),
            ),
        )
        panels = (
            PanelReview(
                id="panel-0001",
                disposition="accepted",
                name="Main Panel",
                points=(
                    PixelPoint(x=60.0, y=60.0),
                    PixelPoint(x=80.0, y=80.0),
                ),
            ),
        )
        wiring = (
            ObservedWiringReview(
                id="wire-0001",
                disposition="accepted",
                points=(
                    PixelPoint(x=70.0, y=70.0),
                    PixelPoint(x=200.0, y=200.0),
                ),
                completeness="complete",
                elevation_meters=2.8,
            ),
        )
        return ReviewDocument(
            candidate_run_id="c" * 32,
            revision_number=1,
            reviewed_by_user_id=self.user_id,
            review_complete=complete,
            approved_for_layout=approved,
            evidence_notes="Approved for canonical geometry",
            wall_thickness_meters=0.15,
            wall_height_meters=2.8,
            checklist=checklist,
            walls=walls,
            rooms=rooms,
            symbols=symbols,
            openings=openings,
            panels=panels,
            observed_wiring=wiring,
            created_at=datetime.now(UTC),
        )

    def test_adapt_reviewed_candidate_success(self):
        review = self._sample_review(approved=True, complete=True)
        candidate = self._sample_candidate()
        legends_by_id = {self.legend_id: self.legend}

        base, extension = adapt_reviewed_candidate_to_canonical(
            review_document=review,
            candidate=candidate,
            project_id=self.project_id,
            project_floor_id=self.floor_id,
            floor_name="Ground Floor",
            floor_sort_order=0,
            floor_elevation_meters=0.0,
            floor_plan_id=self.plan_id,
            floor_plan_page_id=1,
            source_artifact_id=1,
            approved_scale_pixels_per_meter=100.0,
            symbol_legends_by_id=legends_by_id,
            processing_job_id=1,
        )

        self.assertEqual(base.schema_version, 1)
        self.assertEqual(len(base.walls), 1)
        self.assertEqual(base.walls[0].length_meters, 2.0)
        self.assertEqual(len(base.rooms), 1)
        self.assertEqual(len(base.symbols), 1)
        self.assertEqual(base.symbols[0].class_name, "Duplex Receptacle")
        self.assertEqual(len(base.routes), 1)
        self.assertTrue(all(point.elevation_meters == 2.8 for point in base.routes[0].points))

        self.assertEqual(extension.extension_schema_version, 2)
        self.assertEqual(len(extension.openings), 1)
        self.assertEqual(extension.openings[0].opening_type, "door")
        self.assertEqual(len(extension.panels), 1)
        self.assertEqual(extension.panels[0].name, "Main Panel")
        self.assertEqual(len(extension.symbol_details), 1)
        self.assertEqual(extension.symbol_details[0].symbol_id, base.symbols[0].id)
        self.assertEqual(len(extension.route_details), 1)
        self.assertEqual(extension.route_details[0].route_kind, "observed")

    def test_adapt_reviewed_candidate_rejects_unapproved(self):
        unapproved = self._sample_review(approved=False, complete=True)
        candidate = self._sample_candidate()
        legends_by_id = {self.legend_id: self.legend}

        with self.assertRaises(CanonicalGeometryError) as cm:
            adapt_reviewed_candidate_to_canonical(
                review_document=unapproved,
                candidate=candidate,
                project_id=self.project_id,
                project_floor_id=self.floor_id,
                floor_name="Ground Floor",
                floor_sort_order=0,
                floor_elevation_meters=0.0,
                floor_plan_id=self.plan_id,
                floor_plan_page_id=1,
                source_artifact_id=1,
                approved_scale_pixels_per_meter=100.0,
                symbol_legends_by_id=legends_by_id,
                processing_job_id=1,
            )
        self.assertEqual(cm.exception.code, "LAYOUT_REVIEW_NOT_APPROVED")

    def test_save_and_retrieve_layout_snapshot_with_extension(self):
        review = self._sample_review(approved=True, complete=True)
        candidate = self._sample_candidate()
        legends_by_id = {self.legend_id: self.legend}

        base, extension = adapt_reviewed_candidate_to_canonical(
            review_document=review,
            candidate=candidate,
            project_id=self.project_id,
            project_floor_id=self.floor_id,
            floor_name="Ground Floor",
            floor_sort_order=0,
            floor_elevation_meters=0.0,
            floor_plan_id=self.plan_id,
            floor_plan_page_id=1,
            source_artifact_id=1,
            approved_scale_pixels_per_meter=100.0,
            symbol_legends_by_id=legends_by_id,
            processing_job_id=1,
        )

        idempotency_key = str(uuid4())
        with Session(self.engine) as session:
            record = save_layout_snapshot_conditionally(
                session,
                document=base,
                expected_version_number=None,
                idempotency_key=idempotency_key,
                created_by_user_id=self.user_id,
                extension=extension,
            )

            self.assertIsNotNone(record)
            self.assertEqual(record.schema_version, 1)
            self.assertIsNotNone(record.extension)
            self.assertEqual(record.extension.extension_schema_version, 2)
            self.assertEqual(len(record.extension.openings), 1)

            # Retrieve current version
            current = retrieve_current_layout_version(
                session,
                project_id=self.project_id,
                project_floor_id=self.floor_id,
            )
            self.assertEqual(current.id, record.id)
            self.assertIsNotNone(current.extension)
            self.assertEqual(current.extension.extension_schema_version, 2)

            # Idempotent retry returns exact same record
            retry = save_layout_snapshot_conditionally(
                session,
                document=base,
                expected_version_number=None,
                idempotency_key=idempotency_key,
                created_by_user_id=self.user_id,
                extension=extension,
            )
            self.assertEqual(retry.id, record.id)
            self.assertIsNotNone(retry.extension)
