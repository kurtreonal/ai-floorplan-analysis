import hashlib
import json
import unittest
import uuid
from base64 import b64encode
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import delete, func, select
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import InvalidRequestError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_db, get_engine
from app.main import create_app
from app.models import (
    DetectedSymbol,
    FloorPlan,
    ProcessingJob,
    Project,
    ProjectFloor,
    Role,
    User,
    Wall,
)
from app.repositories.detection_result_repository import (
    find_owned_detection_context,
    list_current_walls,
    list_versioned_symbols,
)


SESSION_SECRET = "j1-test-session-secret-with-sufficient-length"
SESSION_COOKIE = "ved_session"
PATH = "/api/floor-plans/{floor_plan_id}/detections"
TABLES = (
    "detected_symbols",
    "detection_class_corrections",
    "detection_reviews",
    "floor_plans",
    "layout_versions",
    "manual_symbols",
    "processing_jobs",
    "project_floors",
    "projects",
    "roles",
    "symbol_legends",
    "users",
    "walls",
)


class DetectionResultsApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_engine()
        cls.marker = f"j1-{uuid.uuid4().hex}"
        cls.database_session = Session(
            cls.engine,
            autoflush=False,
            expire_on_commit=False,
        )
        cls.baseline_counts = cls._table_counts()

        designer_role = cls.database_session.scalar(
            select(Role).where(Role.name == "DESIGNER")
        )
        admin_role = cls.database_session.scalar(
            select(Role).where(Role.name == "ADMIN")
        )
        if designer_role is None or admin_role is None:
            raise unittest.SkipTest("Seeded ADMIN and DESIGNER roles are required.")

        cls.unsupported_role = Role(name=f"J1_{uuid.uuid4().hex[:20].upper()}")
        cls.designer = User(
            oauth_provider=cls.marker,
            oauth_subject="designer",
            display_name="J1 Designer",
            role=designer_role,
        )
        cls.other_designer = User(
            oauth_provider=cls.marker,
            oauth_subject="other-designer",
            display_name="J1 Other Designer",
            role=designer_role,
        )
        cls.admin = User(
            oauth_provider=cls.marker,
            oauth_subject="admin",
            display_name="J1 Admin",
            role=admin_role,
        )
        cls.unsupported_user = User(
            oauth_provider=cls.marker,
            oauth_subject="unsupported",
            display_name="J1 Unsupported",
            role=cls.unsupported_role,
        )
        cls.project = Project(owner=cls.designer, name=f"{cls.marker}-project")
        cls.other_project = Project(
            owner=cls.other_designer,
            name=f"{cls.marker}-other-project",
        )
        cls.project_floor = ProjectFloor(project=cls.project, name="Ground Floor")
        cls.other_project_floor = ProjectFloor(
            project=cls.other_project,
            name="Other Floor",
        )

        cls.storage_root = TemporaryDirectory()
        cls.original_path = Path(cls.storage_root.name) / "original.png"
        cls.original_bytes = b"j1-original-floor-plan-bytes"
        cls.original_path.write_bytes(cls.original_bytes)
        cls.original_digest = hashlib.sha256(cls.original_bytes).hexdigest()
        cls.floor_plan = FloorPlan(
            project_floor=cls.project_floor,
            original_filename="original.png",
            storage_path=str(cls.original_path),
            mime_type="image/png",
            file_size=len(cls.original_bytes),
            processing_status="uploaded",
        )
        cls.other_floor_plan = FloorPlan(
            project_floor=cls.other_project_floor,
            original_filename="other.png",
            storage_path="originals/other.png",
            mime_type="image/png",
            file_size=12,
            processing_status="uploaded",
        )
        cls.database_session.add_all(
            (cls.admin, cls.unsupported_user, cls.floor_plan, cls.other_floor_plan)
        )
        cls.database_session.flush()

        cls.job_a = ProcessingJob(
            floor_plan_id=cls.floor_plan.id,
            job_type="floor_plan_analysis",
            status="processing",
            progress=55,
        )
        cls.job_b = ProcessingJob(
            floor_plan_id=cls.floor_plan.id,
            job_type="floor_plan_analysis",
            status="completed",
            progress=100,
        )
        cls.wrong_type_job = ProcessingJob(
            floor_plan_id=cls.floor_plan.id,
            job_type="other_job",
            status="failed",
            progress=10,
        )
        cls.other_job = ProcessingJob(
            floor_plan_id=cls.other_floor_plan.id,
            job_type="floor_plan_analysis",
            status="failed",
            progress=80,
        )
        cls.empty_other_job = ProcessingJob(
            floor_plan_id=cls.other_floor_plan.id,
            job_type="floor_plan_analysis",
            status="cancelled",
            progress=0,
        )
        cls.database_session.add_all(
            (
                cls.job_a,
                cls.job_b,
                cls.wrong_type_job,
                cls.other_job,
                cls.empty_other_job,
            )
        )
        cls.database_session.flush()

        cls.wall_two = cls._wall(candidate_id=2, processing_job_id=cls.job_a.id)
        cls.wall_one = cls._wall(candidate_id=1, processing_job_id=cls.job_a.id)
        cls.symbol_two = cls._symbol(
            processing_job_id=cls.job_a.id,
            prediction_index=2,
            status="needs_review",
            class_id=9,
            class_name="wall_switch",
            confidence=0.49,
        )
        cls.symbol_one = cls._symbol(
            processing_job_id=cls.job_a.id,
            prediction_index=1,
            status="detected",
            class_id=3,
            class_name="power_outlet",
            confidence=0.91,
        )
        cls.other_symbol = cls._symbol(
            floor_plan_id=cls.other_floor_plan.id,
            processing_job_id=cls.other_job.id,
            prediction_index=1,
            status="detected",
            class_id=4,
            class_name="light",
            confidence=0.88,
        )
        cls.database_session.add_all(
            (
                cls.wall_two,
                cls.wall_one,
                cls.symbol_two,
                cls.symbol_one,
                cls.other_symbol,
            )
        )
        cls.database_session.commit()

        cls.user_ids = {
            "designer": cls.designer.id,
            "other": cls.other_designer.id,
            "admin": cls.admin.id,
            "unsupported": cls.unsupported_user.id,
        }
        cls.created_ids = {
            "floor_plans": (cls.floor_plan.id, cls.other_floor_plan.id),
            "jobs": (
                cls.job_a.id,
                cls.job_b.id,
                cls.wrong_type_job.id,
                cls.other_job.id,
                cls.empty_other_job.id,
            ),
            "projects": (cls.project.id, cls.other_project.id),
        }

        settings = Settings(
            _env_file=None,
            app_env="development",
            database_url=None,
            oauth_provider="synthetic",
            oauth_client_id="j1-client",
            oauth_client_secret="j1-client-secret",
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
    def _table_counts(cls) -> dict[str, int]:
        with Session(cls.engine) as session:
            return {
                table.__tablename__: session.scalar(
                    select(func.count()).select_from(table)
                )
                for table in (
                    DetectedSymbol,
                    FloorPlan,
                    ProcessingJob,
                    ProjectFloor,
                    Project,
                    Role,
                    User,
                    Wall,
                )
            }

    @classmethod
    def _wall(cls, *, candidate_id: int, processing_job_id: int) -> Wall:
        start_x = (candidate_id - 1) * 100
        end_x = start_x + 100
        return Wall(
            floor_plan_id=cls.floor_plan.id,
            processing_job_id=processing_job_id,
            candidate_id=candidate_id,
            status="detected",
            pixels_per_meter=Decimal("100.000000000"),
            raw_start_x=start_x,
            raw_start_y=20,
            raw_end_x=end_x,
            raw_end_y=20,
            raw_length_pixels=Decimal("100.000000"),
            canonical_start_x=Decimal(start_x) / 100,
            canonical_start_y=Decimal("0.200000000"),
            canonical_end_x=Decimal(end_x) / 100,
            canonical_end_y=Decimal("0.200000000"),
            canonical_length_meters=Decimal("1.000000000"),
            angle_degrees=Decimal("0.000000"),
        )

    @classmethod
    def _symbol(
        cls,
        *,
        processing_job_id: int,
        prediction_index: int,
        status: str,
        class_id: int,
        class_name: str,
        confidence: float,
        floor_plan_id: int | None = None,
    ) -> DetectedSymbol:
        return DetectedSymbol(
            floor_plan_id=floor_plan_id or cls.floor_plan.id,
            processing_job_id=processing_job_id,
            prediction_index=prediction_index,
            status=status,
            original_class_id=class_id,
            original_class_name=class_name,
            original_confidence=confidence,
            confidence_threshold=0.5,
            image_width_pixels=800,
            image_height_pixels=600,
            bounding_box_x_min_pixels=10.0,
            bounding_box_y_min_pixels=20.0,
            bounding_box_x_max_pixels=50.0,
            bounding_box_y_max_pixels=60.0,
            center_x_pixels=30.0,
            center_y_pixels=40.0,
            maximum_detections=300,
            detection_limit_reached=False,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        try:
            cls.database_session.rollback()
            cls.database_session.execute(
                delete(DetectedSymbol).where(
                    DetectedSymbol.processing_job_id.in_(cls.created_ids["jobs"])
                )
            )
            cls.database_session.execute(
                delete(Wall).where(Wall.floor_plan_id.in_(cls.created_ids["floor_plans"]))
            )
            cls.database_session.execute(
                delete(ProcessingJob).where(
                    ProcessingJob.id.in_(cls.created_ids["jobs"])
                )
            )
            cls.database_session.execute(
                delete(FloorPlan).where(
                    FloorPlan.id.in_(cls.created_ids["floor_plans"])
                )
            )
            cls.database_session.execute(
                delete(ProjectFloor).where(
                    ProjectFloor.project_id.in_(cls.created_ids["projects"])
                )
            )
            cls.database_session.execute(
                delete(Project).where(Project.id.in_(cls.created_ids["projects"]))
            )
            cls.database_session.execute(
                delete(User).where(User.oauth_provider == cls.marker)
            )
            cls.database_session.execute(
                delete(Role).where(Role.id == cls.unsupported_role.id)
            )
            cls.database_session.commit()
        finally:
            cls.database_session.close()

        try:
            digest = hashlib.sha256(cls.original_path.read_bytes()).hexdigest()
            if digest != cls.original_digest:
                raise AssertionError("The J1 original test file was modified.")
        finally:
            cls.storage_root.cleanup()

        if cls._table_counts() != cls.baseline_counts:
            raise AssertionError("J1 database row counts were not restored.")

    def setUp(self) -> None:
        self.client.cookies.clear()
        self.database_session.rollback()

    def _set_session(self, user_id: int, **untrusted: object) -> None:
        encoded = b64encode(
            json.dumps({"user_id": user_id, **untrusted}).encode("utf-8")
        )
        cookie = TimestampSigner(SESSION_SECRET).sign(encoded).decode("utf-8")
        self.client.cookies.set(SESSION_COOKIE, cookie, domain="testserver.local")

    def _get(
        self,
        floor_plan_id: int | str,
        processing_job_id: int | str | None,
        *,
        user_id: int | None = None,
        headers: dict[str, str] | None = None,
        extra_query: str = "",
    ):
        if user_id is not None:
            self._set_session(user_id)
        query = (
            ""
            if processing_job_id is None
            else f"?processing_job_id={processing_job_id}{extra_query}"
        )
        return self.client.get(
            PATH.format(floor_plan_id=floor_plan_id) + query,
            headers=headers,
        )

    def test_owning_designer_receives_nested_ordered_contract(self) -> None:
        response = self._get(
            self.floor_plan.id,
            self.job_a.id,
            user_id=self.user_ids["designer"],
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["floor_plan_id"], self.floor_plan.id)
        self.assertEqual(body["symbol_processing_job_id"], self.job_a.id)
        self.assertEqual([item["candidate_id"] for item in body["walls"]], [1, 2])
        self.assertEqual(
            [item["prediction_index"] for item in body["symbols"]],
            [1, 2],
        )
        self.assertEqual(
            [item["status"] for item in body["symbols"]],
            ["detected", "needs_review"],
        )
        self.assertEqual(body["symbols"][0]["original_class"]["name"], "power_outlet")
        self.assertEqual(body["symbols"][0]["confidence_threshold"], 0.5)
        self.assertEqual(body["symbols"][0]["bounding_box"]["x_min"], 10.0)
        self.assertEqual(body["symbols"][0]["center"], {"x": 30.0, "y": 40.0})
        self.assertEqual(body["symbols"][0]["maximum_detections"], 300)
        self.assertFalse(body["symbols"][0]["detection_limit_reached"])
        self.assertIsNone(body["symbols"][0]["review"])

    def test_admin_can_read_another_project_without_mutation(self) -> None:
        before = (self.other_job.status, self.other_floor_plan.processing_status)
        response = self._get(
            self.other_floor_plan.id,
            self.other_job.id,
            user_id=self.user_ids["admin"],
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()["symbols"]), 1)
        self.database_session.refresh(self.other_job)
        self.database_session.refresh(self.other_floor_plan)
        self.assertEqual(
            (self.other_job.status, self.other_floor_plan.processing_status),
            before,
        )

    def test_explicit_empty_version_never_falls_back(self) -> None:
        response = self._get(
            self.floor_plan.id,
            self.job_b.id,
            user_id=self.user_ids["designer"],
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["symbol_processing_job_id"], self.job_b.id)
        self.assertEqual(body["symbols"], [])
        self.assertEqual(len(body["walls"]), 2)
        self.assertTrue(
            all(wall["processing_job_id"] == self.job_a.id for wall in body["walls"])
        )

    def test_valid_context_with_no_records_returns_empty_arrays(self) -> None:
        response = self._get(
            self.other_floor_plan.id,
            self.empty_other_job.id,
            user_id=self.user_ids["other"],
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["walls"], [])
        self.assertEqual(response.json()["symbols"], [])

    def test_unauthenticated_and_unsupported_roles_are_denied(self) -> None:
        self.assertEqual(self._get(self.floor_plan.id, self.job_a.id).status_code, 401)
        response = self._get(
            self.floor_plan.id,
            self.job_a.id,
            user_id=self.user_ids["unsupported"],
        )
        self.assertEqual(response.status_code, 403, response.text)

    def test_inaccessible_missing_mismatched_and_wrong_type_share_404(self) -> None:
        responses = (
            self._get(
                self.other_floor_plan.id,
                self.other_job.id,
                user_id=self.user_ids["designer"],
            ),
            self._get(
                9_223_372_036_854_775_807,
                self.job_a.id,
                user_id=self.user_ids["designer"],
            ),
            self._get(
                self.floor_plan.id,
                9_223_372_036_854_775_807,
                user_id=self.user_ids["designer"],
            ),
            self._get(
                self.floor_plan.id,
                self.other_job.id,
                user_id=self.user_ids["designer"],
            ),
            self._get(
                self.floor_plan.id,
                self.wrong_type_job.id,
                user_id=self.user_ids["designer"],
            ),
        )
        expected = {
            "detail": {
                "error": {
                    "code": "DETECTION_RESULTS_NOT_FOUND",
                    "message": "The requested detection results were not found.",
                    "details": {},
                }
            }
        }
        for response in responses:
            self.assertEqual(response.status_code, 404, response.text)
            self.assertEqual(response.json(), expected)

    def test_path_and_required_query_validation(self) -> None:
        for floor_id, job_id in ((0, self.job_a.id), (-1, self.job_a.id), ("x", 1)):
            with self.subTest(floor_id=floor_id):
                response = self._get(
                    floor_id,
                    job_id,
                    user_id=self.user_ids["designer"],
                )
                self.assertEqual(response.status_code, 422, response.text)
        for job_id in (None, 0, -1, "x"):
            with self.subTest(job_id=job_id):
                response = self._get(
                    self.floor_plan.id,
                    job_id,
                    user_id=self.user_ids["designer"],
                )
                self.assertEqual(response.status_code, 422, response.text)

    def test_untrusted_identity_inputs_do_not_grant_access(self) -> None:
        self._set_session(
            self.user_ids["designer"],
            owner_id=self.user_ids["other"],
            role="ADMIN",
        )
        response = self.client.get(
            PATH.format(floor_plan_id=self.other_floor_plan.id)
            + f"?processing_job_id={self.other_job.id}"
            + f"&owner_id={self.user_ids['designer']}&role=ADMIN",
            headers={"X-Role": "ADMIN", "X-Owner-Id": str(self.user_ids["other"])},
        )
        self.assertEqual(response.status_code, 404, response.text)

    def test_response_excludes_sensitive_and_relationship_fields(self) -> None:
        response = self._get(
            self.floor_plan.id,
            self.job_a.id,
            user_id=self.user_ids["designer"],
        )
        self.assertEqual(response.status_code, 200, response.text)
        lowered = response.text.casefold()
        for forbidden in (
            "storage_path",
            str(self.original_path).casefold(),
            "oauth",
            "provider",
            "model_path",
            "sql",
        ):
            self.assertNotIn(forbidden, lowered)

    def test_retrieval_executes_no_pipeline_persistence_filesystem_or_network(self) -> None:
        guarded_targets = (
            "app.ai.wall_detection.detect_wall_lines",
            "app.geometry.normalize_wall_coordinates",
            "app.ai.symbol_detection.load_symbol_detection_model",
            "app.ai.symbol_detection.run_symbol_inference",
            "app.ai.symbol_detection.classify_symbol_predictions",
            "app.services.wall_persistence.replace_detected_wall_geometry",
            "app.services.symbol_persistence.replace_detected_symbols",
            "pathlib.Path.write_bytes",
            "socket.create_connection",
        )
        guards = [
            patch(target, side_effect=AssertionError(f"unexpected call: {target}"))
            for target in guarded_targets
        ]
        for guard in guards:
            guard.start()
        try:
            response = self._get(
                self.floor_plan.id,
                self.job_a.id,
                user_id=self.user_ids["designer"],
            )
        finally:
            for guard in reversed(guards):
                guard.stop()

        self.assertEqual(response.status_code, 200, response.text)

    def test_retrieval_is_read_only_and_preserves_timestamps_and_original(self) -> None:
        before = (
            self.job_a.status,
            self.job_a.progress,
            self.floor_plan.processing_status,
            self.wall_one.created_at,
            self.wall_one.updated_at,
            self.symbol_one.created_at,
            self.symbol_one.updated_at,
        )
        with (
            patch.object(self.database_session, "commit", wraps=self.database_session.commit) as commit,
            patch.object(self.database_session, "flush", wraps=self.database_session.flush) as flush,
        ):
            response = self._get(
                self.floor_plan.id,
                self.job_a.id,
                user_id=self.user_ids["designer"],
            )
        self.assertEqual(response.status_code, 200, response.text)
        commit.assert_not_called()
        flush.assert_not_called()
        self.database_session.refresh(self.job_a)
        self.database_session.refresh(self.floor_plan)
        self.database_session.refresh(self.wall_one)
        self.database_session.refresh(self.symbol_one)
        self.assertEqual(
            (
                self.job_a.status,
                self.job_a.progress,
                self.floor_plan.processing_status,
                self.wall_one.created_at,
                self.wall_one.updated_at,
                self.symbol_one.created_at,
                self.symbol_one.updated_at,
            ),
            before,
        )
        self.assertEqual(
            hashlib.sha256(self.original_path.read_bytes()).hexdigest(),
            self.original_digest,
        )

    def test_repository_queries_are_deterministic_lazy_safe_and_unlocked(self) -> None:
        mock_session = Mock(spec=Session)
        mock_session.scalar.return_value = self.job_a
        result = find_owned_detection_context(
            mock_session,
            floor_plan_id=self.floor_plan.id,
            processing_job_id=self.job_a.id,
            owner_id=self.designer.id,
        )
        self.assertIs(result, self.job_a)
        statement = mock_session.scalar.call_args.args[0]
        compiled = str(
            statement.compile(
                dialect=mysql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        self.assertNotIn("FOR UPDATE", compiled.upper())
        self.assertIn("projects.owner_id", compiled)
        self.assertIn("processing_jobs.floor_plan_id", compiled)
        self.assertIn("processing_jobs.type", compiled)

        with Session(self.engine) as isolated:
            context = find_owned_detection_context(
                isolated,
                floor_plan_id=self.floor_plan.id,
                processing_job_id=self.job_a.id,
                owner_id=self.designer.id,
            )
            self.assertIsNotNone(context)
            with self.assertRaises(InvalidRequestError):
                _ = context.floor_plan
            self.assertEqual(
                [wall.candidate_id for wall in list_current_walls(
                    isolated, floor_plan_id=self.floor_plan.id
                )],
                [1, 2],
            )
            self.assertEqual(
                [symbol.prediction_index for symbol in list_versioned_symbols(
                    isolated,
                    floor_plan_id=self.floor_plan.id,
                    processing_job_id=self.job_a.id,
                )],
                [1, 2],
            )

    def test_each_retrieval_failure_is_sanitized(self) -> None:
        raw = "password=hunter2 SELECT users C:\\private\\db.sql Traceback"
        targets = (
            "find_owned_detection_context",
            "list_current_walls",
            "list_versioned_symbols",
            "list_latest_reviews",
        )
        for target in targets:
            with self.subTest(target=target), patch(
                f"app.services.detection_result_service.{target}",
                side_effect=SQLAlchemyError(raw),
            ):
                response = self._get(
                    self.floor_plan.id,
                    self.job_a.id,
                    user_id=self.user_ids["designer"],
                )
                self.assertEqual(response.status_code, 503, response.text)
                self.assertEqual(
                    response.json()["detail"]["error"]["code"],
                    "DETECTION_RESULTS_RETRIEVAL_FAILED",
                )
                lowered = response.text.casefold()
                for forbidden in ("hunter2", "select", "users", "private", "traceback"):
                    self.assertNotIn(forbidden, lowered)

    def test_openapi_adds_exactly_one_required_get_operation(self) -> None:
        schema = self.application.openapi()
        route_path = PATH.format(floor_plan_id="{floor_plan_id}")
        operation = schema["paths"][route_path]
        self.assertEqual(set(operation), {"get"})
        parameters = {
            (item["name"], item["in"], item["required"])
            for item in operation["get"]["parameters"]
        }
        self.assertIn(("floor_plan_id", "path", True), parameters)
        self.assertIn(("processing_job_id", "query", True), parameters)
        response_schema = operation["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        self.assertEqual(
            response_schema["$ref"],
            "#/components/schemas/DetectionResultsResponse",
        )
        operations = {
            (method, path)
            for path, definition in schema["paths"].items()
            for method in definition
            if method in {"get", "post", "put", "patch", "delete"}
        }
        self.assertEqual(len(operations), 23)

    def test_schema_and_storage_remain_stable(self) -> None:
        self.assertEqual(tuple(sorted(Wall.metadata.tables)), TABLES)
        inspector = __import__("sqlalchemy").inspect(self.engine)
        self.assertEqual(tuple(sorted(inspector.get_table_names())), TABLES)
        self.assertEqual(
            hashlib.sha256(self.original_path.read_bytes()).hexdigest(),
            self.original_digest,
        )


if __name__ == "__main__":
    unittest.main()
