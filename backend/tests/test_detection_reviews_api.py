import json
import unittest
import uuid
from base64 import b64encode
from concurrent.futures import ThreadPoolExecutor
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
    DetectionReview,
    FloorPlan,
    ProcessingJob,
    Project,
    ProjectFloor,
    Role,
    User,
)
from app.services.detection_review_service import review_detection


SESSION_SECRET = "j3-test-session-secret-with-sufficient-length"
SESSION_COOKIE = "ved_session"


class DetectionReviewModelTests(unittest.TestCase):
    def test_exact_append_only_model_contract(self) -> None:
        table = DetectionReview.__table__
        self.assertEqual(
            tuple(table.columns.keys()),
            (
                "id",
                "detected_symbol_id",
                "reviewer_user_id",
                "sequence_number",
                "decision",
                "created_at",
            ),
        )
        self.assertNotIn("updated_at", table.columns)
        self.assertEqual(
            {constraint.name for constraint in table.constraints if constraint.name},
            {
                "uq_detection_reviews_symbol_sequence",
                "ck_detection_reviews_sequence_number",
                "ck_detection_reviews_decision",
            },
        )
        self.assertEqual(
            {foreign_key.target_fullname for foreign_key in table.foreign_keys},
            {"detected_symbols.id", "users.id"},
        )
        self.assertTrue(
            all(foreign_key.ondelete is None for foreign_key in table.foreign_keys)
        )
        self.assertEqual(
            {index.name for index in table.indexes},
            {
                "ix_detection_reviews_detected_symbol_id",
                "ix_detection_reviews_reviewer_user_id",
            },
        )
        self.assertEqual(len(Base.metadata.tables), 11)
        self.assertEqual(len(inspect(get_engine()).get_table_names()), 11)
        self.assertEqual(
            DetectedSymbol.reviews.property.back_populates,
            "detected_symbol",
        )
        self.assertEqual(User.detection_reviews.property.back_populates, "reviewer")
        self.assertFalse(DetectedSymbol.reviews.property.cascade.delete)
        self.assertFalse(User.detection_reviews.property.cascade.delete)


class DetectionReviewApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_engine()
        cls.marker = f"j3-{uuid.uuid4().hex}"
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
        cls.unsupported_role = Role(name=f"J3_{uuid.uuid4().hex[:20].upper()}")
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
            original_filename="j3.png",
            storage_path="originals/j3.png",
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
        cls.database_session.add_all(
            (cls.admin, cls.unsupported, cls.floor_plan, cls.other_floor_plan)
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
        cls.symbol = cls._symbol(cls.floor_plan.id, cls.job.id, 1)
        cls.second_symbol = cls._symbol(cls.floor_plan.id, cls.job.id, 2)
        cls.other_symbol = cls._symbol(
            cls.other_floor_plan.id,
            cls.other_job.id,
            1,
        )
        cls.database_session.add_all(
            (cls.symbol, cls.second_symbol, cls.other_symbol)
        )
        cls.database_session.commit()
        cls.user_ids = {
            "designer": cls.designer.id,
            "other": cls.other_designer.id,
            "admin": cls.admin.id,
            "unsupported": cls.unsupported.id,
        }
        cls.job_ids = (cls.job.id, cls.other_job.id)
        cls.floor_plan_ids = (cls.floor_plan.id, cls.other_floor_plan.id)
        cls.project_ids = (cls.project.id, cls.other_project.id)
        settings = Settings(
            _env_file=None,
            app_env="development",
            database_url=None,
            oauth_provider="synthetic",
            oauth_client_id="j3-client",
            oauth_client_secret="j3-client-secret",
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
    ) -> DetectedSymbol:
        return DetectedSymbol(
            floor_plan_id=floor_plan_id,
            processing_job_id=processing_job_id,
            prediction_index=prediction_index,
            status="needs_review" if prediction_index == 2 else "detected",
            original_class_id=prediction_index,
            original_class_name=f"symbol-{prediction_index}",
            original_confidence=0.4 if prediction_index == 2 else 0.9,
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
                delete(DetectionReview).where(
                    DetectionReview.detected_symbol_id.in_(
                        (cls.symbol.id, cls.second_symbol.id, cls.other_symbol.id)
                    )
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
            session.commit()
        finally:
            session.close()
        if cls._counts() != cls.baseline_counts:
            raise AssertionError("J3 database row counts were not restored.")

    def setUp(self) -> None:
        self.client.cookies.clear()
        self.database_session.rollback()
        self.database_session.execute(
            delete(DetectionReview).where(
                DetectionReview.detected_symbol_id.in_(
                    (self.symbol.id, self.second_symbol.id, self.other_symbol.id)
                )
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
        user: str | None = "designer",
        decision: str = "confirmed",
        floor_plan_id: int | str | None = None,
        processing_job_id: int | str | None = None,
        detected_symbol_id: int | str | None = None,
        payload: dict[str, object] | None = None,
    ):
        if user is not None:
            self._set_session(self.user_ids[user])
        floor_plan_id = floor_plan_id if floor_plan_id is not None else self.floor_plan.id
        processing_job_id = processing_job_id if processing_job_id is not None else self.job.id
        detected_symbol_id = detected_symbol_id if detected_symbol_id is not None else self.symbol.id
        return self.client.put(
            f"/api/floor-plans/{floor_plan_id}/detections/{detected_symbol_id}/review"
            f"?processing_job_id={processing_job_id}",
            json=payload if payload is not None else {"decision": decision},
        )

    def test_confirm_idempotency_reversal_and_fresh_get(self) -> None:
        machine_before = tuple(
            getattr(self.symbol, column.name)
            for column in DetectedSymbol.__table__.columns
        )
        first = self._put(decision="confirmed")
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["sequence_number"], 1)
        repeat = self._put(decision="confirmed")
        self.assertEqual(repeat.status_code, 200, repeat.text)
        self.assertEqual(repeat.json(), first.json())
        changed = self._put(decision="deleted")
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual(changed.json()["sequence_number"], 2)
        reviews = tuple(
            self.database_session.scalars(
                select(DetectionReview)
                .where(DetectionReview.detected_symbol_id == self.symbol.id)
                .order_by(DetectionReview.sequence_number)
            )
        )
        self.assertEqual([item.decision for item in reviews], ["confirmed", "deleted"])
        self.assertTrue(all(item.reviewer_user_id == self.designer.id for item in reviews))
        self.database_session.refresh(self.symbol)
        machine_after = tuple(
            getattr(self.symbol, column.name)
            for column in DetectedSymbol.__table__.columns
        )
        self.assertEqual(machine_after, machine_before)

        fresh = self.client.get(
            f"/api/floor-plans/{self.floor_plan.id}/detections"
            f"?processing_job_id={self.job.id}"
        )
        self.assertEqual(fresh.status_code, 200, fresh.text)
        symbols = fresh.json()["symbols"]
        self.assertEqual(symbols[0]["review"]["decision"], "deleted")
        self.assertEqual(symbols[0]["review"]["sequence_number"], 2)
        self.assertIsNone(symbols[1]["review"])
        self.assertEqual(symbols[0]["status"], "detected")

    def test_authorization_and_non_disclosing_scope(self) -> None:
        self.assertEqual(self._put(user=None).status_code, 401)
        self.assertEqual(self._put(user="admin").status_code, 403)
        self.assertEqual(self._put(user="unsupported").status_code, 403)
        self.assertEqual(
            self._put(
                user="other",
                floor_plan_id=self.floor_plan.id,
                processing_job_id=self.job.id,
                detected_symbol_id=self.symbol.id,
            ).status_code,
            404,
        )
        for floor_plan_id, job_id, symbol_id in (
            (self.floor_plan.id, self.other_job.id, self.symbol.id),
            (self.other_floor_plan.id, self.job.id, self.symbol.id),
            (self.floor_plan.id, self.job.id, self.other_symbol.id),
            (self.floor_plan.id, self.job.id, 9_223_372_036_854_775_807),
        ):
            with self.subTest(ids=(floor_plan_id, job_id, symbol_id)):
                self.assertEqual(
                    self._put(
                        floor_plan_id=floor_plan_id,
                        processing_job_id=job_id,
                        detected_symbol_id=symbol_id,
                    ).status_code,
                    404,
                )

    def test_strict_validation_and_identity_spoofing(self) -> None:
        for kwargs in (
            {"decision": "corrected"},
            {"payload": {"decision": "confirmed", "reviewer_user_id": self.other_designer.id}},
            {"floor_plan_id": 0},
            {"processing_job_id": 0},
            {"detected_symbol_id": "x"},
        ):
            with self.subTest(kwargs=kwargs):
                self.assertEqual(self._put(**kwargs).status_code, 422)
        self._set_session(self.designer.id, role="ADMIN", owner_id=self.other_designer.id)
        response = self.client.put(
            f"/api/floor-plans/{self.other_floor_plan.id}/detections/"
            f"{self.other_symbol.id}/review?processing_job_id={self.other_job.id}",
            headers={"X-Role": "ADMIN", "X-Reviewer-User-Id": str(self.other_designer.id)},
            json={"decision": "confirmed"},
        )
        self.assertEqual(response.status_code, 404, response.text)

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
            "REVIEW_PERSISTENCE_FAILED",
        )
        rollback.assert_called()
        for private_part in ("select", "private", "traceback", "hunter2"):
            self.assertNotIn(private_part, response.text.casefold())
        self.assertEqual(
            self.database_session.scalar(
                select(func.count())
                .select_from(DetectionReview)
                .where(DetectionReview.detected_symbol_id == self.symbol.id)
            ),
            0,
        )

    def test_concurrent_changes_allocate_distinct_sequences(self) -> None:
        designer_id = self.user_ids["designer"]
        floor_plan_id = self.floor_plan.id
        processing_job_id = self.job.id
        detected_symbol_id = self.symbol.id

        def submit(decision: str):
            with Session(self.engine, expire_on_commit=False) as session:
                user = session.scalar(
                    select(User)
                    .options(joinedload(User.role))
                    .where(User.id == designer_id)
                )
                return review_detection(
                    session,
                    current_user=user,
                    floor_plan_id=floor_plan_id,
                    processing_job_id=processing_job_id,
                    detected_symbol_id=detected_symbol_id,
                    decision=decision,
                )

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = tuple(executor.map(submit, ("confirmed", "deleted")))
        self.assertEqual({result.sequence_number for result in results}, {1, 2})
        self.database_session.rollback()
        rows = tuple(
            self.database_session.scalars(
                select(DetectionReview)
                .where(DetectionReview.detected_symbol_id == detected_symbol_id)
                .order_by(DetectionReview.sequence_number)
            )
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual({row.decision for row in rows}, {"confirmed", "deleted"})

    def test_j1_bulk_latest_review_query_is_single_and_unlocked(self) -> None:
        self._put(detected_symbol_id=self.symbol.id, decision="confirmed")
        self._put(detected_symbol_id=self.second_symbol.id, decision="deleted")
        statements: list[str] = []

        def capture(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement)

        event.listen(self.engine, "before_cursor_execute", capture)
        try:
            response = self.client.get(
                f"/api/floor-plans/{self.floor_plan.id}/detections"
                f"?processing_job_id={self.job.id}"
            )
        finally:
            event.remove(self.engine, "before_cursor_execute", capture)
        self.assertEqual(response.status_code, 200, response.text)
        review_queries = [
            statement for statement in statements
            if "detection_reviews" in statement.casefold()
            and statement.lstrip().casefold().startswith("select")
        ]
        self.assertEqual(len(review_queries), 1)
        self.assertNotIn("FOR UPDATE", review_queries[0].upper())
        self.assertEqual(
            [item["review"]["decision"] for item in response.json()["symbols"]],
            ["confirmed", "deleted"],
        )

    def test_review_has_no_job_floor_plan_or_machine_side_effects(self) -> None:
        before = (
            self.job.status,
            self.job.progress,
            self.job.error_message,
            self.floor_plan.processing_status,
            self.symbol.status,
            self.symbol.updated_at,
        )
        response = self._put(decision="deleted")
        self.assertEqual(response.status_code, 200, response.text)
        for item in (self.job, self.floor_plan, self.symbol):
            self.database_session.refresh(item)
        self.assertEqual(
            (
                self.job.status,
                self.job.progress,
                self.job.error_message,
                self.floor_plan.processing_status,
                self.symbol.status,
                self.symbol.updated_at,
            ),
            before,
        )

    def test_openapi_adds_only_the_j3_put(self) -> None:
        schema = self.application.openapi()
        path = "/api/floor-plans/{floor_plan_id}/detections/{detected_symbol_id}/review"
        self.assertEqual(set(schema["paths"][path]), {"put"})
        request_schema = schema["paths"][path]["put"]["requestBody"]["content"][
            "application/json"
        ]["schema"]
        self.assertEqual(
            request_schema["$ref"],
            "#/components/schemas/DetectionReviewRequest",
        )
        operations = {
            (method, path)
            for path, definitions in schema["paths"].items()
            for method in definitions
            if method in {"get", "post", "put", "patch", "delete"}
        }
        self.assertEqual(len(operations), 18)


if __name__ == "__main__":
    unittest.main()
