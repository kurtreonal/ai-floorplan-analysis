import json
import unittest
import uuid
from base64 import b64encode
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import delete, event, func, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.core.config import Settings
from app.core.database import get_db, get_engine
from app.main import create_app
from app.models import (
    Base,
    DetectedSymbol,
    DetectionClassCorrection,
    DetectionReview,
    FloorPlan,
    ProcessingJob,
    Project,
    ProjectFloor,
    Role,
    SymbolLegend,
    User,
)
from app.services.detection_classification_service import (
    DetectionClassificationServiceError,
    correct_detection_classification,
)


SESSION_SECRET = "j4-test-session-secret-with-sufficient-length"
SESSION_COOKIE = "ved_session"


class DetectionClassCorrectionModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_engine()
        Base.metadata.create_all(
            bind=cls.engine,
            tables=[DetectionClassCorrection.__table__],
        )

    def test_exact_append_only_model_contract(self) -> None:
        table = DetectionClassCorrection.__table__
        self.assertEqual(
            tuple(table.columns.keys()),
            (
                "id",
                "detected_symbol_id",
                "reviewer_user_id",
                "sequence_number",
                "old_symbol_legend_id",
                "old_class_id",
                "old_class_name",
                "new_symbol_legend_id",
                "new_class_id",
                "new_class_name",
                "created_at",
            ),
        )
        self.assertNotIn("updated_at", table.columns)
        self.assertEqual(
            {constraint.name for constraint in table.constraints if constraint.name},
            {
                "uq_detection_class_corrections_symbol_sequence",
                "ck_detection_class_corrections_sequence_number",
                "ck_detection_class_corrections_class_ids",
                "ck_detection_class_corrections_class_names",
            },
        )
        self.assertEqual(
            {foreign_key.target_fullname for foreign_key in table.foreign_keys},
            {"detected_symbols.id", "users.id", "symbol_legends.id"},
        )
        self.assertTrue(
            all(foreign_key.ondelete is None for foreign_key in table.foreign_keys)
        )
        self.assertEqual(
            {index.name for index in table.indexes},
            {
                "ix_detection_class_corrections_detected_symbol_id",
                "ix_detection_class_corrections_reviewer_user_id",
                "ix_detection_class_corrections_old_symbol_legend_id",
                "ix_detection_class_corrections_new_symbol_legend_id",
            },
        )
        self.assertEqual(len(Base.metadata.tables), 11)
        self.assertEqual(len(inspect(self.engine).get_table_names()), 11)
        self.assertEqual(
            DetectedSymbol.class_corrections.property.back_populates,
            "detected_symbol",
        )
        self.assertEqual(
            User.detection_class_corrections.property.back_populates,
            "reviewer",
        )
        self.assertFalse(DetectedSymbol.class_corrections.property.cascade.delete)
        self.assertFalse(User.detection_class_corrections.property.cascade.delete)
        self.assertFalse(SymbolLegend.corrections_as_old.property.cascade.delete)
        self.assertFalse(SymbolLegend.corrections_as_new.property.cascade.delete)


class DetectionClassificationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_engine()
        Base.metadata.create_all(
            bind=cls.engine,
            tables=[DetectionClassCorrection.__table__],
        )
        cls.marker = f"j4-{uuid.uuid4().hex}"
        cls.database_session = Session(
            cls.engine,
            autoflush=False,
            expire_on_commit=False,
        )
        cls.baseline_counts = cls._counts()
        designer_role = cls.database_session.scalar(
            select(Role).where(Role.name == "DESIGNER")
        )
        admin_role = cls.database_session.scalar(
            select(Role).where(Role.name == "ADMIN")
        )
        if designer_role is None or admin_role is None:
            raise unittest.SkipTest("Seeded ADMIN and DESIGNER roles are required.")
        cls.unsupported_role = Role(name=f"J4_{uuid.uuid4().hex[:20].upper()}")
        cls.designer = User(
            oauth_provider=cls.marker,
            oauth_subject="designer",
            role=designer_role,
        )
        cls.other_designer = User(
            oauth_provider=cls.marker,
            oauth_subject="other",
            role=designer_role,
        )
        cls.admin = User(
            oauth_provider=cls.marker,
            oauth_subject="admin",
            role=admin_role,
        )
        cls.unsupported = User(
            oauth_provider=cls.marker,
            oauth_subject="unsupported",
            role=cls.unsupported_role,
        )
        cls.project = Project(owner=cls.designer, name=f"{cls.marker}-project")
        cls.other_project = Project(
            owner=cls.other_designer,
            name=f"{cls.marker}-other-project",
        )
        cls.floor = ProjectFloor(project=cls.project, name="Ground")
        cls.other_floor = ProjectFloor(project=cls.other_project, name="Other")
        cls.floor_plan = FloorPlan(
            project_floor=cls.floor,
            original_filename="j4.png",
            storage_path="originals/j4.png",
            mime_type="image/png",
            file_size=100,
            processing_status="uploaded",
        )
        cls.other_floor_plan = FloorPlan(
            project_floor=cls.other_floor,
            original_filename="other.png",
            storage_path="originals/other.png",
            mime_type="image/png",
            file_size=100,
            processing_status="uploaded",
        )
        cls.original_legend = SymbolLegend(
            class_id=1,
            name=f"{cls.marker}-original",
            is_active=True,
        )
        cls.legend_a = SymbolLegend(
            class_id=10,
            name=f"{cls.marker}-approved-a",
            is_active=True,
        )
        cls.legend_b = SymbolLegend(
            class_id=20,
            name=f"{cls.marker}-approved-b",
            is_active=True,
        )
        cls.inactive_legend = SymbolLegend(
            class_id=30,
            name=f"{cls.marker}-inactive",
            is_active=False,
        )
        cls.database_session.add_all(
            (
                cls.admin,
                cls.unsupported,
                cls.floor_plan,
                cls.other_floor_plan,
                cls.original_legend,
                cls.legend_a,
                cls.legend_b,
                cls.inactive_legend,
            )
        )
        cls.database_session.flush()
        cls.job = ProcessingJob(
            floor_plan=cls.floor_plan,
            job_type="floor_plan_analysis",
            status="processing",
            progress=42,
        )
        cls.other_job = ProcessingJob(
            floor_plan=cls.other_floor_plan,
            job_type="floor_plan_analysis",
            status="processing",
            progress=24,
        )
        cls.database_session.add_all((cls.job, cls.other_job))
        cls.database_session.flush()
        cls.pending_symbol = cls._symbol(
            cls.floor_plan.id,
            cls.job.id,
            1,
            cls.original_legend.class_id,
            cls.original_legend.name,
        )
        cls.confirmed_symbol = cls._symbol(
            cls.floor_plan.id,
            cls.job.id,
            2,
            2,
            f"{cls.marker}-machine-confirmed",
        )
        cls.deleted_symbol = cls._symbol(
            cls.floor_plan.id,
            cls.job.id,
            3,
            3,
            f"{cls.marker}-machine-deleted",
        )
        cls.other_symbol = cls._symbol(
            cls.other_floor_plan.id,
            cls.other_job.id,
            1,
            4,
            f"{cls.marker}-other",
        )
        cls.database_session.add_all(
            (
                cls.pending_symbol,
                cls.confirmed_symbol,
                cls.deleted_symbol,
                cls.other_symbol,
            )
        )
        cls.database_session.commit()
        cls.user_ids = {
            "designer": cls.designer.id,
            "other": cls.other_designer.id,
            "admin": cls.admin.id,
            "unsupported": cls.unsupported.id,
        }
        cls.symbol_ids = (
            cls.pending_symbol.id,
            cls.confirmed_symbol.id,
            cls.deleted_symbol.id,
            cls.other_symbol.id,
        )
        cls.legend_names = {
            cls.original_legend.id: cls.original_legend.name,
            cls.legend_a.id: cls.legend_a.name,
            cls.legend_b.id: cls.legend_b.name,
            cls.inactive_legend.id: cls.inactive_legend.name,
        }
        cls.job_ids = (cls.job.id, cls.other_job.id)
        cls.floor_plan_ids = (cls.floor_plan.id, cls.other_floor_plan.id)
        cls.project_ids = (cls.project.id, cls.other_project.id)
        settings = Settings(
            _env_file=None,
            app_env="development",
            database_url=None,
            oauth_provider="synthetic",
            oauth_client_id="j4-client",
            oauth_client_secret="j4-client-secret",
            oauth_redirect_uri="http://localhost:8000/api/auth/callback",
            oauth_discovery_url=(
                "https://provider.invalid/.well-known/openid-configuration"
            ),
            oauth_scopes="openid profile email",
            session_secret=SESSION_SECRET,
        )
        cls.application = create_app(settings)

        def override_database():
            yield cls.database_session

        cls.application.dependency_overrides[get_db] = override_database
        cls.client = TestClient(cls.application)

    @classmethod
    def _symbol(
        cls,
        floor_plan_id: int,
        processing_job_id: int,
        prediction_index: int,
        class_id: int,
        class_name: str,
    ) -> DetectedSymbol:
        return DetectedSymbol(
            floor_plan_id=floor_plan_id,
            processing_job_id=processing_job_id,
            prediction_index=prediction_index,
            status="needs_review" if prediction_index == 1 else "detected",
            original_class_id=class_id,
            original_class_name=class_name,
            original_confidence=0.4 if prediction_index == 1 else 0.9,
            confidence_threshold=0.5,
            image_width_pixels=800,
            image_height_pixels=600,
            bounding_box_x_min_pixels=10.0 * prediction_index,
            bounding_box_y_min_pixels=20.0,
            bounding_box_x_max_pixels=10.0 * prediction_index + 40.0,
            bounding_box_y_max_pixels=60.0,
            center_x_pixels=10.0 * prediction_index + 20.0,
            center_y_pixels=40.0,
            maximum_detections=300,
            detection_limit_reached=False,
        )

    @classmethod
    def _counts(cls) -> dict[str, int]:
        with Session(cls.engine) as session:
            return {
                table.name: session.scalar(select(func.count()).select_from(table))
                for table in Base.metadata.sorted_tables
            }

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        session = cls.database_session
        try:
            session.rollback()
            session.execute(
                delete(DetectionClassCorrection).where(
                    DetectionClassCorrection.detected_symbol_id.in_(cls.symbol_ids)
                )
            )
            session.execute(
                delete(DetectionReview).where(
                    DetectionReview.detected_symbol_id.in_(cls.symbol_ids)
                )
            )
            session.execute(
                delete(DetectedSymbol).where(
                    DetectedSymbol.processing_job_id.in_(cls.job_ids)
                )
            )
            session.execute(delete(ProcessingJob).where(ProcessingJob.id.in_(cls.job_ids)))
            session.execute(delete(FloorPlan).where(FloorPlan.id.in_(cls.floor_plan_ids)))
            session.execute(
                delete(ProjectFloor).where(ProjectFloor.project_id.in_(cls.project_ids))
            )
            session.execute(delete(Project).where(Project.id.in_(cls.project_ids)))
            session.execute(delete(User).where(User.oauth_provider == cls.marker))
            session.execute(delete(Role).where(Role.id == cls.unsupported_role.id))
            session.execute(
                delete(SymbolLegend).where(SymbolLegend.name.like(f"{cls.marker}%"))
            )
            session.commit()
        finally:
            session.close()
        if cls._counts() != cls.baseline_counts:
            raise AssertionError("J4 database row counts were not restored.")

    def setUp(self) -> None:
        self.client.cookies.clear()
        self.database_session.rollback()
        self.database_session.execute(
            delete(DetectionClassCorrection).where(
                DetectionClassCorrection.detected_symbol_id.in_(self.symbol_ids)
            )
        )
        self.database_session.execute(
            delete(DetectionReview).where(
                DetectionReview.detected_symbol_id.in_(self.symbol_ids)
            )
        )
        for legend in (
            self.original_legend,
            self.legend_a,
            self.legend_b,
            self.inactive_legend,
        ):
            self.database_session.refresh(legend)
            legend.name = self.legend_names[legend.id]
        self.original_legend.is_active = True
        self.legend_a.is_active = True
        self.legend_b.is_active = True
        self.inactive_legend.is_active = False
        self.database_session.add_all(
            (
                DetectionReview(
                    detected_symbol_id=self.confirmed_symbol.id,
                    reviewer_user_id=self.designer.id,
                    sequence_number=1,
                    decision="confirmed",
                ),
                DetectionReview(
                    detected_symbol_id=self.deleted_symbol.id,
                    reviewer_user_id=self.designer.id,
                    sequence_number=1,
                    decision="deleted",
                ),
            )
        )
        self.database_session.commit()

    def _set_session(self, user_id: int, **untrusted: object) -> None:
        encoded = b64encode(
            json.dumps({"user_id": user_id, **untrusted}).encode("utf-8")
        )
        cookie = TimestampSigner(SESSION_SECRET).sign(encoded).decode("utf-8")
        self.client.cookies.set(SESSION_COOKIE, cookie, domain="testserver.local")

    def _put(
        self,
        *,
        symbol=None,
        legend=None,
        user: str | None = "designer",
        floor_plan_id=None,
        processing_job_id=None,
        payload=None,
    ):
        symbol = symbol or self.pending_symbol
        legend = legend or self.legend_a
        if user is not None:
            self._set_session(self.user_ids[user])
        floor_plan_id = floor_plan_id if floor_plan_id is not None else self.floor_plan.id
        processing_job_id = processing_job_id if processing_job_id is not None else self.job.id
        return self.client.put(
            f"/api/floor-plans/{floor_plan_id}/detections/{symbol.id}/classification"
            f"?processing_job_id={processing_job_id}",
            json=payload if payload is not None else {"symbol_legend_id": legend.id},
        )

    def _get_results(self):
        return self.client.get(
            f"/api/floor-plans/{self.floor_plan.id}/detections"
            f"?processing_job_id={self.job.id}"
        )

    def test_first_idempotent_reversal_and_fresh_authoritative_get(self) -> None:
        machine_before = tuple(
            getattr(self.pending_symbol, column.name)
            for column in DetectedSymbol.__table__.columns
        )
        first = self._put(legend=self.legend_a)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["sequence_number"], 1)
        self.assertEqual(first.json()["old_class"]["id"], self.original_legend.class_id)
        self.assertEqual(
            first.json()["old_class"]["symbol_legend_id"],
            self.original_legend.id,
        )
        self.assertEqual(first.json()["new_class"]["id"], self.legend_a.class_id)
        repeated = self._put(legend=self.legend_a)
        self.assertEqual(repeated.status_code, 200, repeated.text)
        self.assertEqual(repeated.json(), first.json())
        reversed_response = self._put(legend=self.legend_b)
        self.assertEqual(reversed_response.status_code, 200, reversed_response.text)
        self.assertEqual(reversed_response.json()["sequence_number"], 2)
        rows = tuple(
            self.database_session.scalars(
                select(DetectionClassCorrection)
                .where(
                    DetectionClassCorrection.detected_symbol_id
                    == self.pending_symbol.id
                )
                .order_by(DetectionClassCorrection.sequence_number)
            )
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1].old_class_id, self.legend_a.class_id)
        self.assertEqual(rows[1].new_class_id, self.legend_b.class_id)
        self.assertTrue(all(row.reviewer_user_id == self.designer.id for row in rows))
        self.database_session.refresh(self.pending_symbol)
        machine_after = tuple(
            getattr(self.pending_symbol, column.name)
            for column in DetectedSymbol.__table__.columns
        )
        self.assertEqual(machine_after, machine_before)
        fresh = self._get_results()
        self.assertEqual(fresh.status_code, 200, fresh.text)
        symbol = fresh.json()["symbols"][0]
        self.assertEqual(symbol["original_class"]["id"], self.original_legend.class_id)
        self.assertEqual(symbol["authoritative_class"]["id"], self.legend_b.class_id)
        self.assertEqual(symbol["correction"]["sequence_number"], 2)
        self.assertIsNone(symbol["review"])

    def test_original_class_selection_is_stable_noop(self) -> None:
        response = self._put(legend=self.original_legend)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(response.json()["sequence_number"])
        self.assertIsNone(response.json()["corrected_at"])
        self.assertEqual(response.json()["authoritative_class"]["id"], 1)
        self.assertEqual(
            self.database_session.scalar(
                select(func.count())
                .select_from(DetectionClassCorrection)
                .where(
                    DetectionClassCorrection.detected_symbol_id
                    == self.pending_symbol.id
                )
            ),
            0,
        )

    def test_review_decisions_remain_independent_for_all_states(self) -> None:
        expected_reviews = {
            self.pending_symbol.id: None,
            self.confirmed_symbol.id: "confirmed",
            self.deleted_symbol.id: "deleted",
        }
        for symbol in (
            self.pending_symbol,
            self.confirmed_symbol,
            self.deleted_symbol,
        ):
            response = self._put(symbol=symbol, legend=self.legend_a)
            self.assertEqual(response.status_code, 200, response.text)
        fresh = self._get_results()
        self.assertEqual(fresh.status_code, 200, fresh.text)
        by_id = {item["id"]: item for item in fresh.json()["symbols"]}
        for symbol_id, decision in expected_reviews.items():
            with self.subTest(symbol_id=symbol_id):
                actual = by_id[symbol_id]["review"]
                self.assertEqual(actual["decision"] if actual else None, decision)
                self.assertEqual(
                    by_id[symbol_id]["authoritative_class"]["id"],
                    self.legend_a.class_id,
                )

    def test_authorization_scope_legend_availability_and_strict_body(self) -> None:
        self.assertEqual(self._put(user=None).status_code, 401)
        self.client.cookies.clear()
        self.assertEqual(self._put(user="admin").status_code, 403)
        self.client.cookies.clear()
        self.assertEqual(self._put(user="unsupported").status_code, 403)
        self.client.cookies.clear()
        self.assertEqual(self._put(user="other").status_code, 404)
        self.client.cookies.clear()
        self.assertEqual(self._put(legend=self.inactive_legend).status_code, 409)
        self.client.cookies.clear()
        missing = self._put(payload={"symbol_legend_id": 9_223_372_036_854_775_807})
        self.assertEqual(missing.status_code, 409)
        for payload in (
            {"symbol_legend_id": self.legend_a.id, "class_name": "spoof"},
            {"class_id": self.legend_a.class_id},
            {"symbol_legend_id": 0},
            {"symbol_legend_id": "x"},
        ):
            self.client.cookies.clear()
            with self.subTest(payload=payload):
                self.assertEqual(self._put(payload=payload).status_code, 422)
        for floor_plan_id, processing_job_id, symbol in (
            (self.floor_plan.id, self.other_job.id, self.pending_symbol),
            (self.other_floor_plan.id, self.job.id, self.pending_symbol),
            (self.floor_plan.id, self.job.id, self.other_symbol),
        ):
            self.client.cookies.clear()
            with self.subTest(ids=(floor_plan_id, processing_job_id, symbol.id)):
                self.assertEqual(
                    self._put(
                        floor_plan_id=floor_plan_id,
                        processing_job_id=processing_job_id,
                        symbol=symbol,
                    ).status_code,
                    404,
                )

    def test_database_failure_is_sanitized_and_rolled_back(self) -> None:
        private = r"SELECT secret FROM C:\private Traceback password=hunter2"
        with patch.object(
            self.database_session,
            "commit",
            side_effect=SQLAlchemyError(private),
        ), patch.object(
            self.database_session,
            "rollback",
            wraps=self.database_session.rollback,
        ) as rollback:
            response = self._put()
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(
            response.json()["detail"]["error"]["code"],
            "CLASSIFICATION_PERSISTENCE_FAILED",
        )
        rollback.assert_called()
        for private_part in ("select", "private", "traceback", "hunter2"):
            self.assertNotIn(private_part, response.text.casefold())
        self.assertEqual(
            self.database_session.scalar(
                select(func.count()).select_from(DetectionClassCorrection)
            ),
            0,
        )

    def test_concurrent_changes_allocate_distinct_sequences(self) -> None:
        designer_id = self.designer.id
        floor_plan_id = self.floor_plan.id
        processing_job_id = self.job.id
        detected_symbol_id = self.pending_symbol.id

        def submit(legend_id: int):
            with Session(self.engine, expire_on_commit=False) as session:
                user = session.scalar(
                    select(User)
                    .options(joinedload(User.role))
                    .where(User.id == designer_id)
                )
                return correct_detection_classification(
                    session,
                    current_user=user,
                    floor_plan_id=floor_plan_id,
                    processing_job_id=processing_job_id,
                    detected_symbol_id=detected_symbol_id,
                    symbol_legend_id=legend_id,
                )

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = tuple(
                executor.map(submit, (self.legend_a.id, self.legend_b.id))
            )
        self.assertEqual({result.sequence_number for result in results}, {1, 2})

    def test_latest_correction_bulk_query_is_single_separate_and_unlocked(self) -> None:
        self._put(symbol=self.pending_symbol, legend=self.legend_a)
        self._put(symbol=self.confirmed_symbol, legend=self.legend_b)
        statements: list[str] = []

        def capture(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement)

        event.listen(self.engine, "before_cursor_execute", capture)
        try:
            response = self._get_results()
        finally:
            event.remove(self.engine, "before_cursor_execute", capture)
        self.assertEqual(response.status_code, 200, response.text)
        correction_queries = [
            item
            for item in statements
            if "detection_class_corrections" in item.casefold()
            and item.lstrip().casefold().startswith("select")
        ]
        review_queries = [
            item
            for item in statements
            if "detection_reviews" in item.casefold()
            and item.lstrip().casefold().startswith("select")
        ]
        self.assertEqual(len(correction_queries), 1)
        self.assertEqual(len(review_queries), 1)
        self.assertNotIn("FOR UPDATE", correction_queries[0].upper())
        self.assertNotIn("FOR UPDATE", review_queries[0].upper())

    def test_legend_changes_do_not_rewrite_correction_snapshots(self) -> None:
        original_name = self.legend_a.name
        response = self._put(legend=self.legend_a)
        self.assertEqual(response.status_code, 200, response.text)
        self.legend_a.name = f"{self.marker}-renamed-a"
        self.legend_a.is_active = False
        self.database_session.commit()
        row = self.database_session.scalar(
            select(DetectionClassCorrection).where(
                DetectionClassCorrection.detected_symbol_id
                == self.pending_symbol.id
            )
        )
        self.assertEqual(row.new_class_name, original_name)
        fresh = self._get_results()
        self.assertEqual(fresh.status_code, 200, fresh.text)
        self.assertEqual(
            fresh.json()["symbols"][0]["authoritative_class"]["name"],
            original_name,
        )

    def test_no_geometry_review_job_file_or_model_side_effects(self) -> None:
        before = tuple(
            getattr(self.pending_symbol, column.name)
            for column in DetectedSymbol.__table__.columns
        )
        review_before = self.database_session.scalar(
            select(func.count()).select_from(DetectionReview)
        )
        job_before = (self.job.status, self.job.progress, self.job.error_message)
        floor_before = self.floor_plan.processing_status
        with patch(
            "app.ai.symbol_detection.model_loader.load_symbol_detection_model",
            side_effect=AssertionError("classification loaded YOLO"),
        ), patch.object(
            Path,
            "open",
            side_effect=AssertionError("classification accessed a file"),
        ):
            response = self._put()
        self.assertEqual(response.status_code, 200, response.text)
        self.database_session.refresh(self.pending_symbol)
        self.database_session.refresh(self.job)
        self.database_session.refresh(self.floor_plan)
        self.assertEqual(
            tuple(
                getattr(self.pending_symbol, column.name)
                for column in DetectedSymbol.__table__.columns
            ),
            before,
        )
        self.assertEqual(
            self.database_session.scalar(
                select(func.count()).select_from(DetectionReview)
            ),
            review_before,
        )
        self.assertEqual(
            (self.job.status, self.job.progress, self.job.error_message),
            job_before,
        )
        self.assertEqual(self.floor_plan.processing_status, floor_before)

    def test_openapi_adds_exactly_one_classification_operation(self) -> None:
        schema = self.application.openapi()
        path = (
            "/api/floor-plans/{floor_plan_id}/detections/"
            "{detected_symbol_id}/classification"
        )
        self.assertEqual(set(schema["paths"][path]), {"put"})
        request_schema = schema["paths"][path]["put"]["requestBody"]["content"][
            "application/json"
        ]["schema"]
        self.assertEqual(
            request_schema["$ref"],
            "#/components/schemas/DetectionClassificationRequest",
        )
        operations = {
            (method, route)
            for route, definitions in schema["paths"].items()
            for method in definitions
            if method in {"get", "post", "put", "patch", "delete"}
        }
        self.assertEqual(len(operations), 18)


if __name__ == "__main__":
    unittest.main()
