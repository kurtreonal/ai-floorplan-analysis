import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db, get_engine
from app.main import create_app
from app.models import Base, FloorElevationSetting, FloorPlan, FloorPlanPage, FloorPlanSource, LayoutVersion, PageScaleSetting, Project, ProjectFloor, Role, User
from app.schemas.analysis_settings import AnalysisSettingsResponse
from app.services.analysis_settings_service import AnalysisSettingsError, require_approved_metric_inputs
from app.services.layout_version_service import save_layout_snapshot
from app.geometry import canonical_geometry_from_dict


class AnalysisSettingsTests(unittest.TestCase):
    def setUp(self):
        self.connection = get_engine().connect()
        self.transaction = self.connection.begin()
        self.session = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        roles = {role.name: role for role in self.session.scalars(select(Role))}
        marker = uuid4().hex
        self.owner = User(oauth_provider="pre6-test", oauth_subject=marker, role=roles["DESIGNER"])
        self.other = User(oauth_provider="pre6-test", oauth_subject=f"{marker}-other", role=roles["DESIGNER"])
        self.admin = User(oauth_provider="pre6-test", oauth_subject=f"{marker}-admin", role=roles["ADMIN"])
        self.project = Project(owner=self.owner, name="PRE6 fixture")
        self.floor = ProjectFloor(project=self.project, name="Ground", sort_order=0)
        self.plan = FloorPlan(project_floor=self.floor, original_filename="fixture.png", storage_path="originals/fixture.png", mime_type="image/png", file_size=1)
        self.page = FloorPlanPage(page_number=1)
        source = FloorPlanSource(floor_plan=self.plan, original_sha256="a" * 64, pages=[self.page])
        self.session.add_all((source, self.other, self.admin))
        self.session.commit()
        self.path = f"/api/projects/{self.project.id}/floors/{self.floor.id}/analysis-settings"
        self.app = create_app()
        self.app.dependency_overrides[get_db] = lambda: self.session
        self.app.dependency_overrides[get_current_user] = lambda: self.owner
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.session.close()
        self.transaction.rollback()
        self.connection.close()

    def elevation(self, value=-1.5):
        return self.client.put(self.path + "/elevation", json={"elevation_meters": value, "evidence_notes": "Survey datum, Designer reviewed"})

    def scale(self, value=100):
        return self.client.put(self.path + f"/pages/{self.page.id}/scale", json={
            "pixels_per_meter": value, "reference_width_pixels": 1000 if value is not None else None,
            "reference_height_pixels": 500 if value is not None else None, "evidence_notes": "Measured 500px over 5 meters",
        })

    def test_read_is_unresolved_private_and_has_no_write(self):
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["elevation"]["state"], "unresolved")
        self.assertIsNone(data["elevation"]["elevation_meters"])
        self.assertEqual(data["pages"][0]["floor_plan_page_id"], self.page.id)
        self.assertEqual(data["pages"][0]["scale"]["state"], "unresolved")
        for model in (FloorElevationSetting, PageScaleSetting):
            self.assertEqual(self.session.scalar(select(func.count()).select_from(model)), 0)
        for secret in ("storage_path", "original_sha256", "originals/"):
            self.assertNotIn(secret, response.text)

    def test_owner_approval_revision_and_unresolved_history(self):
        first = self.elevation()
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["state"], "approved")
        self.assertEqual(first.json()["reviewed_by_user_id"], self.owner.id)
        self.assertIsNotNone(first.json()["created_at"])
        second = self.elevation(0)
        self.assertGreater(second.json()["revision_id"], first.json()["revision_id"])
        self.assertEqual(second.json()["elevation_meters"], 0)
        self.assertEqual(self.scale().status_code, 200)
        self.assertEqual(self.scale(None).json()["state"], "unresolved")
        self.assertEqual(self.elevation(None).json()["state"], "unresolved")
        original = self.session.get(FloorElevationSetting, first.json()["revision_id"])
        self.assertEqual(float(original.elevation_meters), -1.5)
        self.assertEqual(self.session.scalar(select(func.count()).select_from(PageScaleSetting)), 2)

    def test_authentication_admin_read_only_and_owner_boundaries(self):
        self.app.dependency_overrides.pop(get_current_user)
        self.assertEqual(self.client.get(self.path).status_code, 401)
        self.app.dependency_overrides[get_current_user] = lambda: self.admin
        self.assertEqual(self.client.get(self.path).status_code, 200)
        self.assertEqual(self.elevation().status_code, 403)
        self.assertEqual(self.scale().status_code, 403)
        self.app.dependency_overrides[get_current_user] = lambda: self.other
        self.assertEqual(self.client.get(self.path).status_code, 404)
        self.assertEqual(self.elevation().status_code, 404)
        self.assertEqual(self.scale().status_code, 404)

    def test_invalid_and_cross_context_identifiers(self):
        self.assertEqual(self.client.get(self.path.replace(str(self.project.id) + "/floors", "9007199254740990/floors")).status_code, 404)
        self.assertEqual(self.client.get(self.path.replace(f"floors/{self.floor.id}", "floors/0")).status_code, 422)
        response = self.client.put(self.path + "/pages/9007199254740990/scale", json={
            "pixels_per_meter": None, "reference_width_pixels": None, "reference_height_pixels": None, "evidence_notes": "Unresolved",
        })
        self.assertEqual(response.status_code, 404)

    def test_rejects_invalid_values_notes_unknown_authority_and_partial_scale(self):
        base = {"elevation_meters": 1, "evidence_notes": "Datum"}
        cases = [{"elevation_meters": value} for value in (True, "1", "NaN", 10001, -10001)]
        cases += [{"evidence_notes": " "}, {"evidence_notes": "x" * 1001}, {"reviewed_by_user_id": self.admin.id}]
        for changes in cases:
            with self.subTest(changes=changes):
                self.assertEqual(self.client.put(self.path + "/elevation", json={**base, **changes}).status_code, 422)
        scale = {"pixels_per_meter": 100, "reference_width_pixels": 1000, "reference_height_pixels": 500, "evidence_notes": "Measured"}
        for changes in ({"pixels_per_meter": 0}, {"pixels_per_meter": -1}, {"pixels_per_meter": 1000001}, {"pixels_per_meter": None}, {"reference_width_pixels": None}, {"reference_width_pixels": True}, {"reference_height_pixels": 100001}):
            with self.subTest(changes=changes):
                self.assertEqual(self.client.put(self.path + f"/pages/{self.page.id}/scale", json={**scale, **changes}).status_code, 422)

    def test_metric_helper_requires_approved_matching_reference(self):
        settings = AnalysisSettingsResponse.model_validate(self.client.get(self.path).json())
        with self.assertRaises(AnalysisSettingsError):
            require_approved_metric_inputs(settings, page_id=self.page.id, image_width=1000, image_height=500)
        self.elevation(-2)
        self.scale(100)
        settings = AnalysisSettingsResponse.model_validate(self.client.get(self.path).json())
        self.assertEqual(require_approved_metric_inputs(settings, page_id=self.page.id, image_width=1000, image_height=500), (-2, 100))
        with self.assertRaises(AnalysisSettingsError):
            require_approved_metric_inputs(settings, page_id=self.page.id, image_width=500, image_height=250)

    def test_settings_revision_cannot_rewrite_historical_k1_snapshot(self):
        payload = json.loads((Path(__file__).resolve().parents[2] / "fixtures/canonical_geometry_v1.json").read_text())
        payload.update(project_id=self.project.id, floor_plan_id=self.plan.id, walls=[], rooms=[], symbols=[], routes=[])
        payload["floor"] = dict(project_floor_id=self.floor.id, name=self.floor.name, sort_order=0, elevation_meters=-1.5)
        snapshot = save_layout_snapshot(self.session, canonical_geometry_from_dict(payload))
        row = self.session.get(LayoutVersion, snapshot.id)
        before = copy.deepcopy(row.geometry_document)
        self.elevation(5)
        self.scale(250)
        self.session.refresh(row)
        self.assertEqual(row.geometry_document, before)

    def test_database_failures_are_sanitized_and_rolled_back(self):
        with patch("app.repositories.analysis_settings_repository.add_approval", side_effect=SQLAlchemyError("private password SELECT")):
            response = self.elevation()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("password", response.text)
        self.assertNotIn("SELECT", response.text)

    def test_schema_and_openapi_contract(self):
        inspector = inspect(get_engine())
        self.assertEqual(set(inspector.get_table_names()), set(Base.metadata.tables))
        self.assertEqual(len(Base.metadata.tables), 22)
        for model, check in ((FloorElevationSetting, "ck_floor_elevation_bounds"), (PageScaleSetting, "ck_page_scale_bounds")):
            name = model.__tablename__
            self.assertEqual({c["name"] for c in inspector.get_columns(name)}, set(model.__table__.columns.keys()))
            self.assertIn(check, {c["name"] for c in inspector.get_check_constraints(name)})
            self.assertEqual({i["name"] for i in inspector.get_indexes(name)}, {i.name for i in model.__table__.indexes})
        methods = {"get", "post", "put", "patch", "delete"}
        operations = [(path, method) for path, item in self.app.openapi()["paths"].items() for method in item if method in methods]
        self.assertEqual(len(operations), 30)
        self.assertEqual(len(operations), len(set(operations)))
