import json
import unittest
from base64 import b64encode
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

import cv2
import numpy as np
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import delete, func, inspect, select
from sqlalchemy.orm import Session

from app.ai.floor_plan_interpretation import (
    CandidateHostProvenance,
    InferenceParameter,
    build_candidate_envelope,
    interpret_floor_plan_demo,
)
from app.core.config import Settings
from app.core.database import get_engine
from app.main import create_app
from app.models import (
    Base,
    FloorElevationSetting,
    FloorPlan,
    FloorPlanInterpretationReview,
    FloorPlanInterpretationRun,
    FloorPlanPage,
    FloorPlanSource,
    LayoutSaveRequest,
    LayoutVersion,
    ManualSymbol,
    PageScaleSetting,
    ProcessingArtifact,
    ProcessingJob,
    Project,
    ProjectFloor,
    Role,
    SymbolLegend,
    User,
)


SESSION_SECRET = "demo-interpretation-test-secret"


def synthetic_plan():
    image = np.full((300, 400, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (50, 40), (350, 260), (0, 0, 0), 5)
    cv2.line(image, (200, 40), (200, 260), (0, 0, 0), 5)
    cv2.circle(image, (110, 150), 12, (0, 0, 0), 3)
    cv2.circle(image, (280, 150), 12, (0, 0, 0), 3)
    return image


class DemoInterpretationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = get_engine()
        Base.metadata.create_all(cls.engine)
        cls.baseline = cls._counts()
        marker = uuid4().hex
        with Session(cls.engine, expire_on_commit=False) as session:
            roles = {
                role.name: role
                for role in session.scalars(
                    select(Role).where(Role.name.in_(("ADMIN", "DESIGNER")))
                )
            }
            cls.designer = User(
                oauth_provider=f"demo-{marker}",
                oauth_subject="designer",
                role=roles["DESIGNER"],
            )
            cls.other = User(
                oauth_provider=f"demo-{marker}",
                oauth_subject="other",
                role=roles["DESIGNER"],
            )
            cls.admin = User(
                oauth_provider=f"demo-{marker}",
                oauth_subject="admin",
                role=roles["ADMIN"],
            )
            project = Project(owner=cls.designer, name=f"Demo {marker}")
            floor = ProjectFloor(project=project, name="Ground Floor", sort_order=0)
            floor_plan = FloorPlan(
                project_floor=floor,
                original_filename="demo.png",
                storage_path=f"originals/{marker}.png",
                mime_type="image/png",
                file_size=128,
                processing_status="uploaded",
            )
            session.add_all((floor_plan, cls.other, cls.admin))
            session.flush()
            source = FloorPlanSource(
                floor_plan_id=floor_plan.id,
                original_sha256="1" * 64,
            )
            session.add(source)
            session.flush()
            page = FloorPlanPage(floor_plan_source_id=source.id, page_number=1)
            job = ProcessingJob(
                floor_plan_id=floor_plan.id,
                job_type="floor_plan_analysis",
                status="completed",
                progress=100,
            )
            legend = SymbolLegend(
                class_id=901,
                name=f"Demo approved light {marker[:8]}",
                is_active=True,
            )
            session.add_all((page, job, legend))
            session.flush()
            artifact = ProcessingArtifact(
                processing_job_id=job.id,
                floor_plan_page_id=page.id,
                artifact_kind="normalized_image",
                relative_path=f"normalized/demo-{marker}.png",
                mime_type="image/png",
                byte_size=128,
                sha256="2" * 64,
                pixel_width=400,
                pixel_height=300,
            )
            session.add(artifact)
            session.flush()
            candidate = build_candidate_envelope(
                interpret_floor_plan_demo(synthetic_plan()),
                CandidateHostProvenance(
                    candidate_run_id=marker,
                    processing_job_id=job.id,
                    floor_plan_source_id=source.id,
                    floor_plan_page_id=page.id,
                    source_artifact_id=artifact.id,
                    source_page_number=1,
                    source_sha256=source.original_sha256,
                    source_artifact_sha256=artifact.sha256,
                    expected_width_pixels=400,
                    expected_height_pixels=300,
                    model_release_id="demo_cv_baseline",
                    base_model_revision=f"opencv-{cv2.__version__}",
                    adapter_revision=None,
                    prompt_version="demo-cv-v1",
                    runtime_version=f"opencv-{cv2.__version__}",
                    inference_parameters=(
                        InferenceParameter(name="provider", value="demo_cv_baseline"),
                    ),
                    created_at=datetime.now(UTC),
                ),
            )
            serialized = candidate.model_dump_json()
            run = FloorPlanInterpretationRun(
                candidate_run_id=marker,
                processing_job_id=job.id,
                floor_plan_id=floor_plan.id,
                floor_plan_page_id=page.id,
                source_artifact_id=artifact.id,
                provider="demo_cv_baseline",
                candidate_sha256=sha256(serialized.encode()).hexdigest(),
                candidate_json=serialized,
            )
            session.add(run)
            session.flush()
            session.add_all((
                FloorElevationSetting(
                    project_floor_id=floor.id,
                    elevation_meters=0,
                    evidence_notes="Synthetic reviewed floor elevation.",
                    reviewed_by_user_id=cls.designer.id,
                ),
                PageScaleSetting(
                    floor_plan_page_id=page.id,
                    pixels_per_meter=100,
                    reference_width_pixels=400,
                    reference_height_pixels=300,
                    evidence_notes="Synthetic reviewed drawing scale.",
                    reviewed_by_user_id=cls.designer.id,
                ),
            ))
            session.commit()
            cls.ids = {
                "designer": cls.designer.id,
                "other": cls.other.id,
                "admin": cls.admin.id,
                "project": project.id,
                "floor": floor.id,
                "floor_plan": floor_plan.id,
                "source": source.id,
                "page": page.id,
                "job": job.id,
                "artifact": artifact.id,
                "run": run.id,
                "legend": legend.id,
            }
            cls.candidate = candidate

        settings = Settings(
            _env_file=None,
            app_env="development",
            oauth_provider="synthetic",
            oauth_client_id="demo-client",
            oauth_client_secret="demo-secret",
            oauth_redirect_uri="http://localhost:8000/api/auth/callback",
            oauth_discovery_url="https://provider.invalid/.well-known/openid-configuration",
            oauth_scopes="openid profile email",
            session_secret=SESSION_SECRET,
        )
        cls.client = TestClient(create_app(settings))

    @classmethod
    def _counts(cls):
        with Session(cls.engine) as session:
            return {
                table.name: session.scalar(select(func.count()).select_from(table))
                for table in Base.metadata.sorted_tables
            }

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        with Session(cls.engine) as session:
            session.execute(delete(LayoutSaveRequest).where(LayoutSaveRequest.project_floor_id == cls.ids["floor"]))
            session.execute(delete(LayoutVersion).where(LayoutVersion.project_floor_id == cls.ids["floor"]))
            session.execute(delete(ManualSymbol).where(ManualSymbol.floor_plan_id == cls.ids["floor_plan"]))
            session.execute(delete(FloorPlanInterpretationReview).where(FloorPlanInterpretationReview.interpretation_run_id == cls.ids["run"]))
            session.execute(delete(FloorPlanInterpretationRun).where(FloorPlanInterpretationRun.id == cls.ids["run"]))
            session.execute(delete(PageScaleSetting).where(PageScaleSetting.floor_plan_page_id == cls.ids["page"]))
            session.execute(delete(FloorElevationSetting).where(FloorElevationSetting.project_floor_id == cls.ids["floor"]))
            session.execute(delete(ProcessingArtifact).where(ProcessingArtifact.id == cls.ids["artifact"]))
            session.execute(delete(ProcessingJob).where(ProcessingJob.id == cls.ids["job"]))
            session.execute(delete(FloorPlanPage).where(FloorPlanPage.id == cls.ids["page"]))
            session.execute(delete(FloorPlanSource).where(FloorPlanSource.id == cls.ids["source"]))
            session.execute(delete(FloorPlan).where(FloorPlan.id == cls.ids["floor_plan"]))
            session.execute(delete(ProjectFloor).where(ProjectFloor.id == cls.ids["floor"]))
            session.execute(delete(Project).where(Project.id == cls.ids["project"]))
            session.execute(delete(SymbolLegend).where(SymbolLegend.id == cls.ids["legend"]))
            session.execute(delete(User).where(User.id.in_((cls.ids["designer"], cls.ids["other"], cls.ids["admin"]))))
            session.commit()
        if cls._counts() != cls.baseline:
            raise AssertionError("Demo interpretation test rows were not restored.")

    def setUp(self):
        self.client.cookies.clear()
        with Session(self.engine) as session:
            session.execute(delete(LayoutSaveRequest).where(LayoutSaveRequest.project_floor_id == self.ids["floor"]))
            session.execute(delete(LayoutVersion).where(LayoutVersion.project_floor_id == self.ids["floor"]))
            session.execute(delete(ManualSymbol).where(ManualSymbol.floor_plan_id == self.ids["floor_plan"]))
            session.execute(delete(FloorPlanInterpretationReview).where(FloorPlanInterpretationReview.interpretation_run_id == self.ids["run"]))
            session.commit()

    def _login(self, user="designer"):
        encoded = b64encode(json.dumps({"user_id": self.ids[user]}).encode())
        signed = TimestampSigner(SESSION_SECRET).sign(encoded).decode()
        self.client.cookies.set("ved_session", signed, domain="testserver.local")

    def _review_payload(self, *, complete=True, approved=True, expected=None, mapped=True):
        payload = self.candidate.payload
        walls = [
            {
                "id": item.id,
                "disposition": "accepted" if index == 0 else "rejected",
                "start": item.start.model_dump(),
                "end": item.end.model_dump(),
            }
            for index, item in enumerate(payload.walls.items)
        ]
        rooms = [
            {
                "id": item.id,
                "disposition": "accepted" if index == 0 else "rejected",
                "name": "Reviewed room" if index == 0 else None,
                "boundary": [point.model_dump() for point in item.boundary],
            }
            for index, item in enumerate(payload.rooms.items)
        ]
        symbols = [
            {
                "id": item.id,
                "disposition": "accepted" if index == 0 else "rejected",
                "center": item.center.model_dump(),
                "symbol_legend_id": self.ids["legend"] if index == 0 and mapped else None,
            }
            for index, item in enumerate(payload.symbols.items)
        ]
        return {
            "candidate_run_id": self.candidate.provenance.candidate_run_id,
            "expected_revision_number": expected,
            "review_complete": complete,
            "approved_for_layout": approved,
            "wall_thickness_meters": 0.15 if approved else None,
            "wall_height_meters": 3.0 if approved else None,
            "evidence_notes": "Reviewed against the visible synthetic source.",
            "walls": walls,
            "rooms": rooms,
            "symbols": symbols,
        }

    def test_schema_and_openapi_include_append_only_demo_contract(self):
        self.assertEqual(len(Base.metadata.tables), 25)
        self.assertEqual(set(inspect(self.engine).get_table_names()), set(Base.metadata.tables))
        schema = self.client.app.openapi()
        self.assertIn("get", schema["paths"]["/api/floor-plans/{floor_plan_id}/interpretation"])
        self.assertIn("post", schema["paths"]["/api/floor-plans/{floor_plan_id}/interpretation/reviews"])
        operations = sum(
            method in {"get", "post", "put", "patch", "delete"}
            for path in schema["paths"].values()
            for method in path
        )
        self.assertEqual(operations, 37)

    def test_owner_retrieves_candidate_but_other_designer_cannot(self):
        self._login()
        response = self.client.get(f"/api/floor-plans/{self.ids['floor_plan']}/interpretation")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["candidate_run_id"], self.candidate.provenance.candidate_run_id)
        self.assertIsNone(response.json()["review"])

        self._login("other")
        response = self.client.get(f"/api/floor-plans/{self.ids['floor_plan']}/interpretation")
        self.assertEqual(response.status_code, 404)

    def test_review_is_immutable_stale_safe_and_preserves_candidate(self):
        self._login()
        first = self._review_payload(complete=False, approved=False)
        first["walls"] = first["walls"][:1]
        first["rooms"] = first["rooms"][:1]
        first["symbols"] = first["symbols"][:1]
        response = self.client.post(
            f"/api/floor-plans/{self.ids['floor_plan']}/interpretation/reviews",
            json=first,
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["review"]["revision_number"], 1)

        second = self._review_payload(expected=1)
        response = self.client.post(
            f"/api/floor-plans/{self.ids['floor_plan']}/interpretation/reviews",
            json=second,
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["review"]["revision_number"], 2)
        self.assertTrue(response.json()["review"]["approved_for_layout"])
        self.assertIsNotNone(response.json()["review"]["symbols"][0]["class_name"])

        stale = self.client.post(
            f"/api/floor-plans/{self.ids['floor_plan']}/interpretation/reviews",
            json=second,
        )
        self.assertEqual(stale.status_code, 409)
        with Session(self.engine) as session:
            revisions = session.scalars(
                select(FloorPlanInterpretationReview)
                .where(FloorPlanInterpretationReview.interpretation_run_id == self.ids["run"])
                .order_by(FloorPlanInterpretationReview.revision_number)
            ).all()
            run = session.get(FloorPlanInterpretationRun, self.ids["run"])
            self.assertEqual([item.revision_number for item in revisions], [1, 2])
            self.assertEqual(run.candidate_sha256, sha256(run.candidate_json.encode()).hexdigest())

    def test_complete_review_requires_approved_symbol_mapping(self):
        self._login()
        response = self.client.post(
            f"/api/floor-plans/{self.ids['floor_plan']}/interpretation/reviews",
            json=self._review_payload(mapped=False),
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["error"]["code"], "SYMBOL_MAPPING_REQUIRED")

    def test_approved_review_saves_and_reloads_shared_canonical_geometry(self):
        self._login()
        reviewed = self.client.post(
            f"/api/floor-plans/{self.ids['floor_plan']}/interpretation/reviews",
            json=self._review_payload(),
        )
        self.assertEqual(reviewed.status_code, 201, reviewed.text)
        request_id = str(uuid4())
        response = self.client.post(
            f"/api/projects/{self.ids['project']}/floors/{self.ids['floor']}/floor-plans/{self.ids['floor_plan']}/interpretation/layout",
            json={
                "candidate_run_id": self.candidate.provenance.candidate_run_id,
                "review_revision_number": 1,
                "expected_layout_version_number": None,
                "idempotency_key": request_id,
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        geometry = response.json()["geometry"]
        self.assertEqual(geometry["routes"], [])
        self.assertEqual(len(geometry["walls"]), 1)
        self.assertEqual(len(geometry["rooms"]), 1)
        self.assertEqual(len(geometry["symbols"]), 1)
        self.assertEqual(geometry["walls"][0]["height_meters"], 3.0)
        self.assertEqual(geometry["coordinate_system"]["pixels_per_meter"], 100.0)
        symbol = geometry["symbols"][0]
        self.assertEqual(symbol["source_type"], "manual")
        with Session(self.engine) as session:
            placement = session.get(ManualSymbol, symbol["source_record_id"])
            self.assertIsNotNone(placement)
            self.assertEqual(placement.processing_job_id, self.ids["job"])
            self.assertEqual(placement.created_by_user_id, self.ids["designer"])
        repeated = self.client.post(
            f"/api/projects/{self.ids['project']}/floors/{self.ids['floor']}/floor-plans/{self.ids['floor_plan']}/interpretation/layout",
            json={
                "candidate_run_id": self.candidate.provenance.candidate_run_id,
                "review_revision_number": 1,
                "expected_layout_version_number": None,
                "idempotency_key": request_id,
            },
        )
        self.assertEqual(repeated.status_code, 201, repeated.text)
        self.assertEqual(repeated.json()["geometry"], geometry)
        with Session(self.engine) as session:
            count = session.scalar(select(func.count()).select_from(ManualSymbol).where(ManualSymbol.floor_plan_id == self.ids["floor_plan"]))
            self.assertEqual(count, 1)

        reloaded = self.client.get(
            f"/api/projects/{self.ids['project']}/floors/{self.ids['floor']}/layouts"
        )
        self.assertEqual(reloaded.status_code, 200)
        self.assertEqual(reloaded.json()["geometry"], geometry)

    def test_newer_unapproved_review_blocks_old_approval(self):
        self._login()
        path = f"/api/floor-plans/{self.ids['floor_plan']}/interpretation/reviews"
        self.assertEqual(self.client.post(path, json=self._review_payload()).status_code, 201)
        self.assertEqual(self.client.post(path, json=self._review_payload(expected=1, complete=False, approved=False)).status_code, 201)
        response = self.client.post(
            f"/api/projects/{self.ids['project']}/floors/{self.ids['floor']}/floor-plans/{self.ids['floor_plan']}/interpretation/layout",
            json={
                "candidate_run_id": self.candidate.provenance.candidate_run_id,
                "review_revision_number": 1,
                "expected_layout_version_number": None,
                "idempotency_key": str(uuid4()),
            },
        )
        self.assertEqual(response.status_code, 409)
        with Session(self.engine) as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(ManualSymbol).where(ManualSymbol.floor_plan_id == self.ids['floor_plan'])), 0)


if __name__ == "__main__":
    unittest.main()
