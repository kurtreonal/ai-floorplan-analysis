import hashlib
import json
import unittest
import uuid
from base64 import b64encode
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from PIL import Image
from sqlalchemy import delete, func, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.ai.symbol_detection.confidence_filter import classify_symbol_predictions
from app.ai.symbol_detection.inference import (
    MAXIMUM_DETECTIONS,
    SymbolBoundingBox,
    SymbolCenter,
    SymbolInferenceResult,
    SymbolPrediction,
)
from app.core.config import Settings
from app.core.database import get_db, get_engine
from app.main import create_app
from app.models import (
    Base,
    DetectedSymbol,
    DetectionClassCorrection,
    DetectionReview,
    FloorPlan,
    ManualSymbol,
    ProcessingJob,
    Project,
    ProjectFloor,
    Role,
    SymbolLegend,
    User,
)
from app.services.authoritative_symbol_service import (
    retrieve_authoritative_symbol_candidates,
)
from app.services.manual_symbol_service import create_manual_symbol
from app.services.symbol_persistence import SymbolPersistenceError, replace_detected_symbols
from tests.artifact_fixtures import (
    attach_source_identity,
    delete_artifact_identity_fixtures,
    register_normalized_fixture,
)


SESSION_SECRET = "j5-test-session-secret-with-sufficient-length"
SESSION_COOKIE = "ved_session"


def png_bytes(size=(100, 80), mode="RGB") -> bytes:
    output = BytesIO()
    Image.new(mode, size, 255).save(output, format="PNG")
    return output.getvalue()


class ManualSymbolModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_engine()
        Base.metadata.create_all(bind=cls.engine, tables=[ManualSymbol.__table__])

    def test_exact_model_contract_and_registration(self) -> None:
        table = ManualSymbol.__table__
        self.assertEqual(
            tuple(table.columns.keys()),
            (
                "id", "floor_plan_id", "processing_job_id",
                "created_by_user_id", "symbol_legend_id",
                "placement_request_id", "status", "class_id", "class_name",
                "center_x_pixels", "center_y_pixels", "image_width_pixels",
                "image_height_pixels", "created_at",
            ),
        )
        self.assertNotIn("updated_at", table.columns)
        self.assertEqual(
            {constraint.name for constraint in table.constraints if constraint.name},
            {
                "uq_manual_symbols_creator_request",
                "ck_manual_symbols_status",
                "ck_manual_symbols_class_id",
                "ck_manual_symbols_class_name",
                "ck_manual_symbols_image_dimensions",
                "ck_manual_symbols_pixel_bounds",
            },
        )
        self.assertEqual(
            {foreign_key.target_fullname for foreign_key in table.foreign_keys},
            {
                "floor_plans.id", "processing_jobs.id", "users.id",
                "symbol_legends.id",
            },
        )
        self.assertTrue(all(foreign_key.ondelete is None for foreign_key in table.foreign_keys))
        self.assertEqual(
            {index.name for index in table.indexes},
            {
                "ix_manual_symbols_floor_plan_job_id",
                "ix_manual_symbols_created_by_user_id",
                "ix_manual_symbols_symbol_legend_id",
            },
        )
        self.assertEqual(len(Base.metadata.tables), 25)
        self.assertEqual(set(inspect(self.engine).get_table_names()), set(Base.metadata.tables))
        self.assertEqual(FloorPlan.manual_symbols.property.back_populates, "floor_plan")
        self.assertEqual(ProcessingJob.manual_symbols.property.back_populates, "processing_job")
        self.assertEqual(User.manual_symbols.property.back_populates, "creator")
        self.assertEqual(SymbolLegend.manual_symbols.property.back_populates, "symbol_legend")
        for relationship in (
            FloorPlan.manual_symbols, ProcessingJob.manual_symbols,
            User.manual_symbols, SymbolLegend.manual_symbols,
        ):
            self.assertFalse(relationship.property.cascade.delete)


class ManualSymbolApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_engine()
        Base.metadata.create_all(bind=cls.engine)
        cls.marker = f"j5-{uuid.uuid4().hex}"
        cls.session = Session(cls.engine, autoflush=False, expire_on_commit=False)
        cls.baseline = cls._counts()
        designer_role = cls.session.scalar(select(Role).where(Role.name == "DESIGNER"))
        admin_role = cls.session.scalar(select(Role).where(Role.name == "ADMIN"))
        if designer_role is None or admin_role is None:
            raise unittest.SkipTest("Seeded roles are required.")
        cls.unsupported_role = Role(name=f"J5_{uuid.uuid4().hex[:20].upper()}")
        cls.designer = User(oauth_provider=cls.marker, oauth_subject="designer", role=designer_role)
        cls.other = User(oauth_provider=cls.marker, oauth_subject="other", role=designer_role)
        cls.admin = User(oauth_provider=cls.marker, oauth_subject="admin", role=admin_role)
        cls.unsupported = User(oauth_provider=cls.marker, oauth_subject="unsupported", role=cls.unsupported_role)
        cls.project = Project(owner=cls.designer, name=f"{cls.marker}-project")
        cls.other_project = Project(owner=cls.other, name=f"{cls.marker}-other")
        cls.floor = ProjectFloor(project=cls.project, name="Ground")
        cls.other_floor = ProjectFloor(project=cls.other_project, name="Other")
        cls.storage = TemporaryDirectory()
        cls.root = Path(cls.storage.name)
        cls.upload_root = cls.root / "uploads"
        cls.processed_root = cls.root / "processed"
        (cls.upload_root / "originals").mkdir(parents=True)
        cls.processed_root.mkdir()
        cls.original = cls.upload_root / "originals" / "plan.png"
        cls.original.write_bytes(png_bytes((20, 10)))
        cls.original_hash = hashlib.sha256(cls.original.read_bytes()).hexdigest()
        cls.floor_plan = FloorPlan(
            project_floor=cls.floor, original_filename="plan.png",
            storage_path="originals/plan.png", mime_type="image/png",
            file_size=cls.original.stat().st_size, processing_status="processed",
        )
        cls.other_floor_plan = FloorPlan(
            project_floor=cls.other_floor, original_filename="other.png",
            storage_path="originals/other.png", mime_type="image/png",
            file_size=1, processing_status="uploaded",
        )
        cls.active = SymbolLegend(class_id=101, name=f"{cls.marker}-active", is_active=True)
        cls.second = SymbolLegend(class_id=102, name=f"{cls.marker}-second", is_active=True)
        cls.inactive = SymbolLegend(class_id=103, name=f"{cls.marker}-inactive", is_active=False)
        cls.session.add_all((cls.admin, cls.unsupported, cls.floor_plan, cls.other_floor_plan, cls.active, cls.second, cls.inactive))
        cls.session.flush()
        attach_source_identity(cls.session, cls.floor_plan, cls.original.read_bytes())
        attach_source_identity(cls.session, cls.other_floor_plan, b"x")
        cls.job = ProcessingJob(floor_plan=cls.floor_plan, job_type="floor_plan_analysis", status="processing", progress=44)
        cls.second_job = ProcessingJob(floor_plan=cls.floor_plan, job_type="floor_plan_analysis", status="processing", progress=55)
        cls.other_job = ProcessingJob(floor_plan=cls.other_floor_plan, job_type="floor_plan_analysis", status="processing", progress=66)
        cls.wrong_job = ProcessingJob(floor_plan=cls.floor_plan, job_type="other", status="processing", progress=1)
        cls.session.add_all((cls.job, cls.second_job, cls.other_job, cls.wrong_job))
        cls.session.commit()
        cls.job_ids = (cls.job.id, cls.second_job.id, cls.other_job.id, cls.wrong_job.id)
        cls.floor_plan_ids = (cls.floor_plan.id, cls.other_floor_plan.id)
        cls.project_ids = (cls.project.id, cls.other_project.id)
        cls.legend_ids = (cls.active.id, cls.second.id, cls.inactive.id)
        cls.active_name = cls.active.name
        cls.image = cls._image_path(cls.floor_plan.id, cls.job.id)
        cls.image.parent.mkdir(parents=True)
        cls.image.write_bytes(png_bytes())
        cls.second_image = cls._image_path(cls.floor_plan.id, cls.second_job.id)
        cls.second_image.parent.mkdir(parents=True)
        cls.second_image.write_bytes(png_bytes())
        register_normalized_fixture(
            cls.session,
            floor_plan=cls.floor_plan,
            processing_job=cls.job,
            processed_root=cls.processed_root,
            image_path=cls.image,
        )
        register_normalized_fixture(
            cls.session,
            floor_plan=cls.floor_plan,
            processing_job=cls.second_job,
            processed_root=cls.processed_root,
            image_path=cls.second_image,
        )
        cls.session.commit()
        settings = Settings(
            _env_file=None, app_env="development", database_url=None,
            upload_dir=cls.upload_root, processed_dir=cls.processed_root,
            oauth_provider="synthetic", oauth_client_id="j5-client",
            oauth_client_secret="j5-secret",
            oauth_redirect_uri="http://localhost:8000/api/auth/callback",
            oauth_discovery_url="https://provider.invalid/.well-known/openid-configuration",
            oauth_scopes="openid profile email", session_secret=SESSION_SECRET,
        )
        cls.app = create_app(settings)
        def override_database():
            yield cls.session
        cls.app.dependency_overrides[get_db] = override_database
        cls.client = TestClient(cls.app)
        cls.users = {
            "designer": cls.designer.id, "other": cls.other.id,
            "admin": cls.admin.id, "unsupported": cls.unsupported.id,
        }

    @classmethod
    def _image_path(cls, floor_plan_id, job_id):
        return cls.processed_root / "normalized" / f"floor-plan-{floor_plan_id}" / f"job-{job_id}" / "image.png"

    @classmethod
    def _counts(cls):
        with Session(cls.engine) as session:
            return {table.name: session.scalar(select(func.count()).select_from(table)) for table in Base.metadata.sorted_tables}

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        try:
            cls.session.rollback()
            detection_ids = tuple(cls.session.scalars(select(DetectedSymbol.id).where(DetectedSymbol.processing_job_id.in_(cls.job_ids))))
            if detection_ids:
                cls.session.execute(delete(DetectionClassCorrection).where(DetectionClassCorrection.detected_symbol_id.in_(detection_ids)))
                cls.session.execute(delete(DetectionReview).where(DetectionReview.detected_symbol_id.in_(detection_ids)))
            cls.session.execute(delete(ManualSymbol).where(ManualSymbol.processing_job_id.in_(cls.job_ids)))
            cls.session.execute(delete(DetectedSymbol).where(DetectedSymbol.processing_job_id.in_(cls.job_ids)))
            delete_artifact_identity_fixtures(
                cls.session, floor_plan_ids=cls.floor_plan_ids
            )
            cls.session.execute(delete(ProcessingJob).where(ProcessingJob.id.in_(cls.job_ids)))
            cls.session.execute(delete(FloorPlan).where(FloorPlan.id.in_(cls.floor_plan_ids)))
            cls.session.execute(delete(ProjectFloor).where(ProjectFloor.project_id.in_(cls.project_ids)))
            cls.session.execute(delete(Project).where(Project.id.in_(cls.project_ids)))
            cls.session.execute(delete(User).where(User.oauth_provider == cls.marker))
            cls.session.execute(delete(Role).where(Role.id == cls.unsupported_role.id))
            cls.session.execute(delete(SymbolLegend).where(SymbolLegend.id.in_(cls.legend_ids)))
            cls.session.commit()
        finally:
            cls.session.close()
        try:
            if hashlib.sha256(cls.original.read_bytes()).hexdigest() != cls.original_hash:
                raise AssertionError("J5 modified an original upload.")
        finally:
            cls.storage.cleanup()
        if cls._counts() != cls.baseline:
            raise AssertionError("J5 database row counts were not restored.")

    def setUp(self) -> None:
        self.client.cookies.clear()
        self.session.rollback()
        detection_ids = tuple(self.session.scalars(select(DetectedSymbol.id).where(DetectedSymbol.processing_job_id.in_(self.job_ids))))
        if detection_ids:
            self.session.execute(delete(DetectionClassCorrection).where(DetectionClassCorrection.detected_symbol_id.in_(detection_ids)))
            self.session.execute(delete(DetectionReview).where(DetectionReview.detected_symbol_id.in_(detection_ids)))
        self.session.execute(delete(ManualSymbol).where(ManualSymbol.processing_job_id.in_(self.job_ids)))
        self.session.execute(delete(DetectedSymbol).where(DetectedSymbol.processing_job_id.in_(self.job_ids)))
        self.active.is_active = True
        self.active.name = self.active_name
        self.second.is_active = True
        self.inactive.is_active = False
        self.session.commit()
        self.image.parent.mkdir(parents=True, exist_ok=True)
        self.image.write_bytes(png_bytes())

    def _session_cookie(self, user_id):
        encoded = b64encode(json.dumps({"user_id": user_id}).encode())
        return TimestampSigner(SESSION_SECRET).sign(encoded).decode()

    def _post(self, *, user="designer", request_id=None, legend=None, center=None, floor_plan_id=None, job_id=None, payload=None):
        if user is not None:
            self.client.cookies.set(SESSION_COOKIE, self._session_cookie(self.users[user]), domain="testserver.local")
        request_id = request_id or str(uuid.uuid4())
        legend = legend or self.active
        body = payload if payload is not None else {
            "placement_request_id": request_id,
            "symbol_legend_id": legend.id,
            "center": center or {"x": 25.5, "y": 40.25},
        }
        return self.client.post(
            f"/api/floor-plans/{self.floor_plan.id if floor_plan_id is None else floor_plan_id}/manual-symbols",
            params={"processing_job_id": self.job.id if job_id is None else job_id},
            json=body,
        )

    def test_owner_creation_idempotency_snapshot_and_fresh_j1_get(self) -> None:
        request_id = str(uuid.uuid4())
        before = (self.job.status, self.job.progress, self.floor_plan.processing_status)
        first = self._post(request_id=request_id)
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(set(first.json()), {
            "id", "floor_plan_id", "processing_job_id", "status",
            "authoritative_class", "center", "image_width_pixels",
            "image_height_pixels", "created_at",
        })
        self.assertEqual(first.json()["status"], "manually_added")
        self.assertEqual(first.json()["authoritative_class"], {"id": 101, "name": self.active.name})
        self.assertEqual(first.json()["center"], {"x": 25.5, "y": 40.25})
        self.assertEqual((first.json()["image_width_pixels"], first.json()["image_height_pixels"]), (100, 80))
        repeat = self._post(request_id=request_id)
        self.assertEqual(repeat.status_code, 200, repeat.text)
        self.assertEqual(repeat.json(), first.json())
        self.assertEqual(self.session.scalar(select(func.count()).select_from(ManualSymbol)), 1)
        fresh = self.client.get(f"/api/floor-plans/{self.floor_plan.id}/detections?processing_job_id={self.job.id}")
        self.assertEqual(fresh.status_code, 200, fresh.text)
        self.assertEqual(fresh.json()["symbols"], [])
        self.assertEqual(fresh.json()["manual_symbols"], [first.json()])
        for item in (self.job, self.floor_plan):
            self.session.refresh(item)
        self.assertEqual((self.job.status, self.job.progress, self.floor_plan.processing_status), before)

    def test_active_legend_authorization_scope_and_strict_validation(self) -> None:
        self.assertEqual(self._post(user=None).status_code, 401)
        for user in ("admin", "unsupported"):
            self.client.cookies.clear()
            self.assertEqual(self._post(user=user).status_code, 403)
        self.client.cookies.clear()
        self.assertEqual(self._post(user="other").status_code, 404)
        self.client.cookies.clear()
        self.assertEqual(self._post(legend=self.inactive).status_code, 409)
        self.client.cookies.clear()
        missing = self._post(payload={"placement_request_id": str(uuid.uuid4()), "symbol_legend_id": 9_223_372_036_854_775_000, "center": {"x": 1, "y": 1}})
        self.assertEqual(missing.status_code, 409)
        for payload in (
            {"placement_request_id": "bad", "symbol_legend_id": self.active.id, "center": {"x": 1, "y": 1}},
            {"placement_request_id": str(uuid.uuid4()), "symbol_legend_id": self.active.id, "center": {"x": -1, "y": 1}},
            {"placement_request_id": str(uuid.uuid4()), "symbol_legend_id": self.active.id, "center": {"x": 1, "y": 1}, "status": "manually_added"},
            {"placement_request_id": str(uuid.uuid4()), "symbol_legend_id": self.active.id, "center": {"x": 1, "y": 1}, "image_width_pixels": 100},
            {"placement_request_id": str(uuid.uuid4()), "symbol_legend_id": self.active.id, "center": {"x": 1, "y": 1}, "created_by_user_id": self.other.id},
        ):
            self.client.cookies.clear()
            self.assertEqual(self._post(payload=payload).status_code, 422)
        for floor_id, job_id in ((0, self.job.id), (self.floor_plan.id, 0), (self.floor_plan.id, self.other_job.id), (self.floor_plan.id, self.wrong_job.id)):
            self.client.cookies.clear()
            response = self._post(floor_plan_id=floor_id, job_id=job_id)
            self.assertIn(response.status_code, {404, 422})

    def test_bounds_conflicts_and_distinct_same_coordinate(self) -> None:
        for center in ({"x": 0, "y": 0}, {"x": 100, "y": 80}):
            self.client.cookies.clear()
            self.assertEqual(self._post(center=center).status_code, 201)
        for center in ({"x": 100.01, "y": 1}, {"x": 1, "y": 80.01}):
            self.client.cookies.clear()
            self.assertEqual(self._post(center=center).status_code, 422)
        request_id = str(uuid.uuid4())
        self.client.cookies.clear()
        self.assertEqual(self._post(request_id=request_id).status_code, 201)
        for kwargs in ({"request_id": request_id, "legend": self.second}, {"request_id": request_id, "center": {"x": 2, "y": 3}}, {"request_id": request_id, "job_id": self.second_job.id}):
            self.client.cookies.clear()
            self.assertEqual(self._post(**kwargs).status_code, 409)
        self.client.cookies.clear()
        self.assertEqual(self._post(center={"x": 25.5, "y": 40.25}).status_code, 201)

    def test_missing_invalid_image_and_database_failure_create_no_row(self) -> None:
        self.image.unlink()
        response = self._post()
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.session.scalar(select(func.count()).select_from(ManualSymbol)), 0)
        self.image.write_bytes(png_bytes(mode="L"))
        self.client.cookies.clear()
        self.assertEqual(self._post().status_code, 409)
        self.image.write_bytes(png_bytes())
        private = r"SELECT password FROM C:\private Traceback"
        with patch.object(self.session, "commit", side_effect=SQLAlchemyError(private)):
            self.client.cookies.clear()
            response = self._post()
        self.assertEqual(response.status_code, 503, response.text)
        self.assertNotIn("private", response.text.casefold())
        self.assertEqual(self.session.scalar(select(func.count()).select_from(ManualSymbol)), 0)

    def test_concurrent_identical_requests_create_one_row(self) -> None:
        request_id = str(uuid.uuid4())
        designer_id = self.designer.id
        floor_plan_id = self.floor_plan.id
        processing_job_id = self.job.id
        symbol_legend_id = self.active.id
        processed_root = self.processed_root
        def submit():
            with Session(self.engine, expire_on_commit=False) as session:
                user = session.scalar(select(User).options(joinedload(User.role)).where(User.id == designer_id))
                return create_manual_symbol(
                    session, current_user=user, processed_directory=processed_root,
                    floor_plan_id=floor_plan_id, processing_job_id=processing_job_id,
                    placement_request_id=request_id, symbol_legend_id=symbol_legend_id,
                    center_x=12.5, center_y=13.5,
                )
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = tuple(executor.map(lambda _value: submit(), range(2)))
        self.assertEqual(sum(result.created for result in results), 1)
        self.session.rollback()
        self.assertEqual(self.session.scalar(select(func.count()).select_from(ManualSymbol)), 1)

    def test_snapshots_version_isolation_i4_protection_and_authoritative_handoff(self) -> None:
        manual = self._post()
        self.assertEqual(manual.status_code, 201, manual.text)
        self.active.name = f"{self.marker}-renamed"
        self.active.is_active = False
        self.session.commit()
        fresh = self.client.get(f"/api/floor-plans/{self.floor_plan.id}/detections?processing_job_id={self.job.id}")
        self.assertEqual(fresh.json()["manual_symbols"][0]["authoritative_class"]["name"], f"{self.marker}-active")
        self.assertEqual(self.client.get(f"/api/floor-plans/{self.floor_plan.id}/detections?processing_job_id={self.second_job.id}").json()["manual_symbols"], [])

        predictions = SymbolInferenceResult(
            image_width=100, image_height=80,
            predictions=(SymbolPrediction(1, "machine", 0.9, SymbolBoundingBox(1, 1, 5, 5), SymbolCenter(3, 3)),),
            maximum_detections=MAXIMUM_DETECTIONS, detection_limit_reached=False,
        )
        with self.assertRaises(SymbolPersistenceError):
            replace_detected_symbols(self.session, self.floor_plan.id, self.job.id, classify_symbol_predictions(predictions, threshold=0.5))
        records = replace_detected_symbols(self.session, self.floor_plan.id, self.second_job.id, classify_symbol_predictions(predictions, threshold=0.5))
        self.assertEqual(len(records), 1)

        confirmed = DetectedSymbol(
            floor_plan_id=self.floor_plan.id, processing_job_id=self.job.id,
            prediction_index=1, status="detected", original_class_id=1,
            original_class_name="machine", original_confidence=.9,
            confidence_threshold=.5, image_width_pixels=100, image_height_pixels=80,
            bounding_box_x_min_pixels=1, bounding_box_y_min_pixels=1,
            bounding_box_x_max_pixels=5, bounding_box_y_max_pixels=5,
            center_x_pixels=3, center_y_pixels=3, maximum_detections=300,
            detection_limit_reached=False,
        )
        deleted = DetectedSymbol(**{
            key: value for key, value in {
                **{column.name: getattr(confirmed, column.name, None) for column in DetectedSymbol.__table__.columns if column.name not in {"id", "created_at", "updated_at"}},
                "prediction_index": 2,
            }.items()
        })
        pending = DetectedSymbol(**{
            key: value for key, value in {
                **{column.name: getattr(confirmed, column.name, None) for column in DetectedSymbol.__table__.columns if column.name not in {"id", "created_at", "updated_at"}},
                "prediction_index": 3,
            }.items()
        })
        self.session.add_all((confirmed, deleted, pending))
        self.session.flush()
        self.session.add_all((
            DetectionReview(detected_symbol_id=confirmed.id, reviewer_user_id=self.designer.id, sequence_number=1, decision="confirmed"),
            DetectionReview(detected_symbol_id=deleted.id, reviewer_user_id=self.designer.id, sequence_number=1, decision="deleted"),
            DetectionClassCorrection(detected_symbol_id=confirmed.id, reviewer_user_id=self.designer.id, sequence_number=1, old_symbol_legend_id=None, old_class_id=1, old_class_name="machine", new_symbol_legend_id=self.second.id, new_class_id=self.second.class_id, new_class_name=self.second.name),
        ))
        self.session.commit()
        handoff = retrieve_authoritative_symbol_candidates(self.session, floor_plan_id=self.floor_plan.id, processing_job_id=self.job.id)
        self.assertEqual([item.source_type for item in handoff], ["detected", "manual"])
        self.assertEqual(handoff[0].class_id, self.second.class_id)
        self.assertEqual(handoff[0].status, "confirmed")
        self.assertEqual(handoff[1].status, "manually_added")
        self.assertTrue(all(hasattr(item, "center_x_pixels") for item in handoff))

    def test_openapi_has_current_operation_count(self) -> None:
        schema = self.app.openapi()
        path = "/api/floor-plans/{floor_plan_id}/manual-symbols"
        self.assertEqual(set(schema["paths"][path]), {"post"})
        operations = {(method, route) for route, definitions in schema["paths"].items() for method in definitions if method in {"get", "post", "put", "patch", "delete"}}
        self.assertEqual(len(operations), 37)


if __name__ == "__main__":
    unittest.main()
