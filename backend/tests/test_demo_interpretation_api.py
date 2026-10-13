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
    @staticmethod
    def candidate_payload():
        return interpret_floor_plan_demo(synthetic_plan())

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
                cls.candidate_payload(),
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

    def test_joined_wall_coordinates_width_and_revision_survive_move_reload(self):
        self._login()
        body=self._review_payload(complete=False,approved=False,mapped=False)
        body['walls'] += [dict(id='manual-wall-1000',disposition='added',start=dict(x=30,y=50),end=dict(x=150,y=50),estimated_thickness_pixels=8),
                         dict(id='manual-wall-1001',disposition='added',start=dict(x=150,y=50),end=dict(x=150,y=190),estimated_thickness_pixels=8)]
        url=f'/api/floor-plans/{self.ids["floor_plan"]}/interpretation'
        first=self.client.post(url+'/reviews',json=body)
        self.assertEqual(first.status_code,201,first.text)
        revision=first.json()['review']['revision_number']
        body['expected_revision_number']=revision
        body['walls'][-2]['start']['y']=60;body['walls'][-2]['end']['y']=60
        body['walls'][-1]['start']['y']=60
        second=self.client.post(url+'/reviews',json=body)
        self.assertEqual(second.status_code,201,second.text)
        loaded=self.client.get(url).json()['review']['walls']
        self.assertEqual(loaded[-2]['end'],loaded[-1]['start'])
        self.assertEqual(loaded[-1]['estimated_thickness_pixels'],8)
        self.assertEqual(first.json()['review']['walls'][-1]['start']['y'],50)
        self.assertEqual(self.client.post(url+'/reviews',json=body).status_code,409)

    def test_manual_split_dimensions_persist_and_feed_canonical_geometry(self):
        self._login()
        body=self._review_payload()
        body['walls'] += [dict(id='manual-wall-2000',disposition='added',start=dict(x=10,y=280),end=dict(x=200,y=280),
                              estimated_thickness_pixels=10,thickness_meters=0.1,height_meters=2.5),
                          dict(id='manual-wall-2001',disposition='added',start=dict(x=200,y=280),end=dict(x=390,y=280),
                              estimated_thickness_pixels=10,thickness_meters=0.1,height_meters=2.5)]
        url=f'/api/floor-plans/{self.ids["floor_plan"]}/interpretation'
        first=self.client.post(url+'/reviews',json=body)
        self.assertEqual(first.status_code,201,first.text)
        loaded=self.client.get(url).json()
        self.assertEqual(loaded['routing_context']['pixels_per_meter'],100)
        self.assertEqual(loaded['review']['walls'][-2:],body['walls'][-2:])
        saved=self.client.post(f'/api/projects/{self.ids["project"]}/floors/{self.ids["floor"]}/floor-plans/{self.ids["floor_plan"]}/interpretation/layout',
            json=dict(candidate_run_id=self.candidate.provenance.candidate_run_id,review_revision_number=first.json()['review']['revision_number'],
                      expected_layout_version_number=None,idempotency_key=str(uuid4())))
        self.assertEqual(saved.status_code,201,saved.text)
        walls=saved.json()['geometry']['walls'][-2:]
        self.assertEqual(walls[0]['end'],walls[1]['start'])
        self.assertEqual([w['length_meters'] for w in walls],[1.9,1.9])
        self.assertEqual([w['thickness_meters'] for w in walls],[0.1,0.1])
        self.assertEqual([w['height_meters'] for w in walls],[2.5,2.5])
        reloaded=self.client.get(f'/api/projects/{self.ids["project"]}/floors/{self.ids["floor"]}/layouts')
        self.assertEqual(reloaded.json()['geometry'],saved.json()['geometry'])

    def test_bom_includes_unapproved_saved_draft_without_creating_layout_or_approval(self):
        self._login()
        payload = self._review_payload(complete=False, approved=False)
        payload['symbols'][0]['disposition']='unresolved'
        saved=self.client.post(f'/api/floor-plans/{self.ids["floor_plan"]}/interpretation/reviews',json=payload)
        self.assertEqual(saved.status_code,201,saved.text)
        before=self._counts()
        url=f'/api/projects/{self.ids["project"]}/bom?floor_plan_id={self.ids["floor_plan"]}&processing_job_id={self.ids["job"]}'
        response=self.client.get(url)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(sum(r['quantity'] for r in response.json()['planning']['items'] if r['kind']=='device'),1)
        self.assertEqual(response.json()['planning']['sources'][0]['state'],'saved_draft')
        csv=self.client.get(url.replace('/bom?', '/bom.csv?'))
        self.assertEqual(csv.status_code,200,csv.text)
        self.assertIn('DRAFT BOM',csv.text)
        self.assertEqual(self._counts(),before)
        self._login('other')
        self.assertEqual(self.client.get(url).status_code,404)


    def test_custom_device_price_persists_in_draft_and_prices_without_approval(self):
        self._login()
        payload=self._review_payload(complete=False,approved=False,mapped=False)
        payload['symbols'][0].update(disposition='unresolved',custom_unit_price=123.45)
        url=f'/api/floor-plans/{self.ids["floor_plan"]}/interpretation'
        saved=self.client.post(url+'/reviews',json=payload)
        self.assertEqual(saved.status_code,201,saved.text)
        self.assertEqual(saved.json()['review']['symbols'][0]['custom_unit_price'],123.45)
        self.assertEqual(self.client.get(url).json()['review']['symbols'][0]['custom_unit_price'],123.45)
        bom=self.client.get(f'/api/projects/{self.ids["project"]}/bom',params={'floor_plan_id':self.ids['floor_plan'],'paper_size':'A3'})
        self.assertEqual(bom.status_code,200,bom.text)
        item=next(r for r in bom.json()['planning']['items'] if r['kind']=='device')
        self.assertEqual(item['pricing_state'],'custom_priced')
        self.assertEqual(float(item['line_total']),123.45)
        measured=bom.json()['planning']['sources'][0]
        self.assertEqual(measured['scale_basis'],'measured_page')
        self.assertEqual(measured['pixels_per_meter'],100)
        custom=self.client.get(f'/api/projects/{self.ids["project"]}/bom',params={
            'floor_plan_id':self.ids['floor_plan'],'paper_size':'CUSTOM','custom_width_mm':300,'custom_height_mm':600})
        self.assertEqual(custom.json()['planning']['sources'][0]['pixels_per_meter'],100)
        self.assertFalse(saved.json()['review']['approved_for_layout'])
        for bad in (-1,1000000001,True):
            payload['expected_revision_number']=1
            payload['symbols'][0]['custom_unit_price']=bad
            self.assertEqual(self.client.post(url+'/reviews',json=payload).status_code,422)

    def test_all_paper_assumptions_and_custom_size_allow_mismatches_without_scale_writes(self):
        self._login()
        with Session(self.engine) as session:
            scale=session.scalar(select(PageScaleSetting).where(PageScaleSetting.floor_plan_page_id==self.ids['page']))
            scale.reference_width_pixels=401  # no usable measured source-page scale
            session.commit()
        try:
            before=self._counts()
            url=f'/api/projects/{self.ids["project"]}/bom'
            for paper,long_mm in [('A4',297),('A3',420),('A2',594),('A1',841),('A0',1189),('CUSTOM',600)]:
                params={'floor_plan_id':self.ids['floor_plan'],'paper_size':paper}
                if paper=='CUSTOM': params.update(custom_width_mm=300,custom_height_mm=600)
                response=self.client.get(url,params=params)
                self.assertEqual(response.status_code,200,response.text)
                source=response.json()['planning']['sources'][0]
                self.assertAlmostEqual(source['pixels_per_meter'],400/(long_mm/10))
                self.assertEqual(source['scale_basis'],'assumed_full_paper_1_100')
                self.assertIsNone(source['scale_revision_id'])
            self.assertEqual(self._counts(),before)
        finally:
            with Session(self.engine) as session:
                scale=session.scalar(select(PageScaleSetting).where(PageScaleSetting.floor_plan_page_id==self.ids['page']))
                scale.reference_width_pixels=400
                session.commit()

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
        self.assertEqual(len(Base.metadata.tables), 34)
        self.assertEqual(set(inspect(self.engine).get_table_names()), set(Base.metadata.tables))
        schema = self.client.app.openapi()
        self.assertIn("get", schema["paths"]["/api/floor-plans/{floor_plan_id}/interpretation"])
        self.assertIn("post", schema["paths"]["/api/floor-plans/{floor_plan_id}/interpretation/reviews"])
        operations = sum(
            method in {"get", "post", "put", "patch", "delete"}
            for path in schema["paths"].values()
            for method in path
        )
        self.assertEqual(operations, 49)  # Includes draft BOM CSV as well as material import.
        self.assertIn("post", schema["paths"]["/api/admin/symbol-legends/import-trained"])

    def test_owner_retrieves_candidate_but_other_designer_cannot(self):
        self._login()
        response = self.client.get(f"/api/floor-plans/{self.ids['floor_plan']}/interpretation")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["candidate_run_id"], self.candidate.provenance.candidate_run_id)
        self.assertIsNone(response.json()["review"])

        self._login("other")
        response = self.client.get(f"/api/floor-plans/{self.ids['floor_plan']}/interpretation")
        self.assertEqual(response.status_code, 404)

    def test_provisional_gang_default_saves_as_draft_but_requires_correction_for_final_review(self):
        from app.ai.floor_plan_interpretation import FloorPlanInterpretationCandidate
        document=self.candidate.model_dump(mode='json')
        document['payload']['symbols']['items'][0]['observed_label']='Gang switch'
        document['payload']['symbols']['items'][0]['gang_count_proposal']={
            'count':1,'basis':'user_requested_default','provisional':True}
        snapshot=FloorPlanInterpretationCandidate.model_validate_json(json.dumps(document)).model_dump_json()
        with Session(self.engine) as session:
            run=session.get(FloorPlanInterpretationRun,self.ids['run'])
            original=(run.candidate_json,run.candidate_sha256)
            run.candidate_json=snapshot;run.candidate_sha256=sha256(snapshot.encode()).hexdigest();session.commit()
        try:
            self._login()
            url=f"/api/floor-plans/{self.ids['floor_plan']}/interpretation/reviews"
            draft=self._review_payload(complete=False,approved=False)
            saved=self.client.post(url,json=draft)
            self.assertEqual(saved.status_code,201,saved.text)
            final=self._review_payload(expected=1)
            blocked=self.client.post(url,json=final)
            self.assertEqual(blocked.status_code,409,blocked.text)
            self.assertIn('PROVISIONAL_SWITCH_COUNT_REQUIRES_CORRECTION',blocked.text)
            final['symbols'][0]['disposition']='corrected'
            moved=self.client.post(url,json=final)
            self.assertEqual(moved.status_code,409,'Movement alone must not verify a gang count.')
            final['symbols'][0]['gang_count_confirmed']=True
            corrected=self.client.post(url,json=final)
            self.assertEqual(corrected.status_code,201,corrected.text)
            with Session(self.engine) as session:
                self.assertEqual(session.get(FloorPlanInterpretationRun,self.ids['run']).candidate_json,snapshot)
        finally:
            with Session(self.engine) as session:
                run=session.get(FloorPlanInterpretationRun,self.ids['run'])
                run.candidate_json,run.candidate_sha256=original;session.commit()

    def test_training_legend_survives_review_save_and_reload_without_rewriting_prediction(self):
        from app.ai.floor_plan_interpretation import FloorPlanInterpretationCandidate
        document = self.candidate.model_dump(mode="json")
        training = {"model_class_id": 0, "legend_entry": "sheet-08:L01",
                    "name": "Reviewed downlight", "dataset_sha256": "a" * 64}
        document["provenance"]["model_release_id"] = "development_multiclass56_yolo"
        document["payload"]["symbols"]["items"][0]["training_legend"] = training
        snapshot = FloorPlanInterpretationCandidate.model_validate_json(json.dumps(document)).model_dump_json()
        with Session(self.engine) as session:
            run = session.get(FloorPlanInterpretationRun, self.ids["run"])
            original = (run.candidate_json, run.candidate_sha256)
            run.candidate_json = snapshot
            run.candidate_sha256 = sha256(snapshot.encode()).hexdigest()
            session.commit()
        try:
            self._login()
            body = self._review_payload(complete=False, approved=False)
            body["symbols"][0]["disposition"] = "unresolved"
            response = self.client.post(
                f"/api/floor-plans/{self.ids['floor_plan']}/interpretation/reviews", json=body)
            self.assertEqual(response.status_code, 201, response.text)
            loaded = self.client.get(f"/api/floor-plans/{self.ids['floor_plan']}/interpretation").json()
            self.assertEqual(loaded["candidate"]["payload"]["symbols"]["items"][0]["training_legend"], training)
            self.assertEqual(loaded["review"]["symbols"][0]["disposition"], "unresolved")
            self.assertEqual(loaded["review"]["symbols"][0]["symbol_legend_id"], self.ids["legend"])
            with Session(self.engine) as session:
                self.assertEqual(session.get(FloorPlanInterpretationRun, self.ids["run"]).candidate_json, snapshot)
        finally:
            with Session(self.engine) as session:
                run = session.get(FloorPlanInterpretationRun, self.ids["run"])
                run.candidate_json, run.candidate_sha256 = original
                session.commit()

    def test_wiring_reference_cannot_be_saved_as_symbol_even_in_unfinished_draft(self):
        with Session(self.engine) as session:
            legend = session.get(SymbolLegend, self.ids["legend"])
            original = legend.name
            legend.name = "Raceway conduit concealed in ceiling [pdf-76f411c60b6d:p1:L10]"
            session.commit()
        try:
            self._login()
            payload = self._review_payload(complete=False, approved=False)
            response = self.client.post(
                f"/api/floor-plans/{self.ids['floor_plan']}/interpretation/reviews", json=payload)
            self.assertEqual(response.status_code, 409, response.text)
            self.assertEqual(response.json()["detail"]["error"]["code"], "SYMBOL_MAPPING_REQUIRED")
            for symbol in payload["symbols"]:
                symbol["disposition"] = "rejected"
            rejected = self.client.post(
                f"/api/floor-plans/{self.ids['floor_plan']}/interpretation/reviews", json=payload)
            self.assertEqual(rejected.status_code, 201, rejected.text)
        finally:
            with Session(self.engine) as session:
                session.get(SymbolLegend, self.ids["legend"]).name = original
                session.commit()

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

    def test_experimental_unresolved_correction_survives_draft_save_and_reload(self):
        """An advisory proposal stays out of canonical geometry until approval."""
        with Session(self.engine) as session:
            run = session.get(FloorPlanInterpretationRun, self.ids["run"])
            original = (run.provider, run.candidate_json, run.candidate_sha256)
            candidate = self.candidate.model_copy(update={
                "provenance": self.candidate.provenance.model_copy(update={
                    "model_release_id": "experimental_pull_station_template",
                }),
            })
            run.provider = "experimental_pull_station_template"
            run.candidate_json = candidate.model_dump_json()
            run.candidate_sha256 = sha256(run.candidate_json.encode()).hexdigest()
            session.commit()
        try:
            self._login()
            payload = self._review_payload(complete=False, approved=False)
            payload["symbols"][0]["disposition"] = "unresolved"
            payload["symbols"][0]["symbol_legend_id"] = None
            path = f"/api/floor-plans/{self.ids['floor_plan']}/interpretation"
            saved = self.client.post(f"{path}/reviews", json=payload)
            self.assertEqual(saved.status_code, 201, saved.text)
            self.assertFalse(saved.json()["review"]["approved_for_layout"])
            reloaded = self.client.get(path)
            self.assertEqual(reloaded.status_code, 200, reloaded.text)
            self.assertEqual(reloaded.json()["review"]["symbols"][0]["disposition"], "unresolved")
            self.assertEqual(reloaded.json()["candidate"]["provenance"]["model_release_id"],
                             "experimental_pull_station_template")
            corrected = self._review_payload(complete=False, approved=False, expected=1)
            corrected["symbols"][0]["disposition"] = "corrected"
            corrected["symbols"][0]["center"] = {"x": 75, "y": 85}
            second = self.client.post(f"{path}/reviews", json=corrected)
            self.assertEqual(second.status_code, 201, second.text)
            reloaded = self.client.get(path).json()
            self.assertEqual(reloaded["review"]["revision_number"], 2)
            self.assertEqual(reloaded["review"]["symbols"][0]["center"], {"x": 75, "y": 85})
            self.assertFalse(reloaded["review"]["approved_for_layout"])
        finally:
            with Session(self.engine) as session:
                run = session.get(FloorPlanInterpretationRun, self.ids["run"])
                run.provider, run.candidate_json, run.candidate_sha256 = original
                session.commit()

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

    def test_device_move_remove_reload_preserves_revision_and_canonical_exclusion(self):
        self._login()
        path = f"/api/floor-plans/{self.ids['floor_plan']}/interpretation"
        original = self.client.get(path).json()["candidate"]
        payload = self._review_payload(complete=False, approved=False)
        payload["symbols"][0].update(disposition="corrected", center={"x": 85, "y": 65})
        moved = self.client.post(f"{path}/reviews", json=payload)
        self.assertEqual(moved.status_code, 201, moved.text)
        self.assertEqual(moved.json()["review"]["symbols"][0]["center"], {"x": 85, "y": 65})
        self.assertIsNotNone(moved.json()["review"]["symbols"][0]["class_name"])
        payload.update(expected_revision_number=1, review_complete=True, approved_for_layout=True,
                       wall_thickness_meters=0.15, wall_height_meters=3.0)
        payload["symbols"][0]["disposition"] = "rejected"
        removed = self.client.post(f"{path}/reviews", json=payload)
        self.assertEqual(removed.status_code, 201, removed.text)
        loaded = self.client.get(path).json()
        self.assertEqual(loaded["candidate"], original)
        self.assertEqual(loaded["review"]["symbols"][0]["disposition"], "rejected")
        self.assertEqual(loaded["review"]["symbols"][0]["center"], {"x": 85, "y": 65})
        with Session(self.engine) as session:
            revisions = session.scalars(select(FloorPlanInterpretationReview)
                .where(FloorPlanInterpretationReview.interpretation_run_id == self.ids["run"])
                .order_by(FloorPlanInterpretationReview.revision_number)).all()
            self.assertEqual(len(revisions), 2)
            self.assertEqual(json.loads(revisions[0].review_json)["symbols"][0]["disposition"], "corrected")
        saved = self.client.post(
            f"/api/projects/{self.ids['project']}/floors/{self.ids['floor']}/floor-plans/{self.ids['floor_plan']}/interpretation/layout",
            json={"candidate_run_id": self.candidate.provenance.candidate_run_id,
                  "review_revision_number": 2, "expected_layout_version_number": None,
                  "idempotency_key": str(uuid4())},
        )
        self.assertEqual(saved.status_code, 201, saved.text)
        self.assertEqual(saved.json()["geometry"]["symbols"], [])

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

    def test_unfinished_visible_wiring_draft_preserves_uncertainty_and_removed_history(self):
        self._login()
        review_path = f"/api/floor-plans/{self.ids['floor_plan']}/interpretation/reviews"
        payload = self._review_payload()
        payload.update(review_complete=False, approved_for_layout=False,
                       wall_thickness_meters=None, wall_height_meters=None)
        wire = {"id": "manual-wiring-0001", "disposition": "unresolved",
                "points": [{"x": 20.0, "y": 30.0}, {"x": 80.0, "y": 90.0}],
                "completeness": "partial", "elevation_meters": None}
        from app.schemas.demo_interpretation import DemoObservedWiringReview
        wire=DemoObservedWiringReview.model_validate(wire).model_dump()
        payload["observed_wiring"] = [wire]
        first = self.client.post(review_path, json=payload)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["review"]["observed_wiring"], [wire])
        payload["expected_revision_number"] = 1
        payload["observed_wiring"][0] = {**wire, "disposition": "rejected"}
        second = self.client.post(review_path, json=payload)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.json()["review"]["observed_wiring"][0]["disposition"], "rejected")
        self.assertEqual(second.json()["review"]["observed_wiring"][0]["points"], wire["points"])
        self.assertFalse(second.json()["review"]["approved_for_layout"])
        self.assertEqual(first.json()["review"]["observed_wiring"][0]["disposition"], "unresolved")
        loaded = self.client.get(f"/api/floor-plans/{self.ids['floor_plan']}/interpretation")
        self.assertEqual(loaded.status_code, 200)
        self.assertEqual(loaded.json()["review"]["observed_wiring"], payload["observed_wiring"])
        layout = self.client.get(f"/api/projects/{self.ids['project']}/floors/{self.ids['floor']}/layouts")
        self.assertEqual(layout.status_code, 404)
        with Session(self.engine) as session:
            revisions = session.scalars(select(FloorPlanInterpretationReview).where(
                FloorPlanInterpretationReview.interpretation_run_id == self.ids["run"]
            ).order_by(FloorPlanInterpretationReview.revision_number)).all()
            self.assertEqual(len(revisions), 2)
            self.assertNotEqual(revisions[0].review_json, revisions[1].review_json)


    def test_observed_wiring_revision_save_reload_and_elevation_gate(self):
        self._login()
        review_path = f"/api/floor-plans/{self.ids['floor_plan']}/interpretation/reviews"
        payload = self._review_payload()
        payload["observed_wiring"] = [{
            "id": "manual-wiring-0001", "disposition": "added",
            "points": [{"x": 20.0, "y": 30.0}, {"x": 80.0, "y": 90.0}],
            "completeness": "complete", "elevation_meters": None,
        }]
        rejected = self.client.post(review_path, json=payload)
        self.assertEqual(rejected.status_code, 409, rejected.text)
        payload["observed_wiring"][0]["elevation_meters"] = 2.8
        first = self.client.post(review_path, json=payload)
        self.assertEqual(first.status_code, 201, first.text)
        payload["expected_revision_number"] = 1
        payload["observed_wiring"][0]["points"][1]["x"] = 100.0
        second = self.client.post(review_path, json=payload)
        self.assertEqual(second.status_code, 201, second.text)
        save_path = f"/api/projects/{self.ids['project']}/floors/{self.ids['floor']}/floor-plans/{self.ids['floor_plan']}/interpretation/layout"
        save = {
            "candidate_run_id": self.candidate.provenance.candidate_run_id,
            "review_revision_number": 2, "expected_layout_version_number": None,
            "idempotency_key": str(uuid4()),
        }
        saved = self.client.post(save_path, json=save)
        self.assertEqual(saved.status_code, 201, saved.text)
        route = saved.json()["geometry"]["routes"][0]
        self.assertEqual(route["points"][1]["x"], 1.0)
        self.assertEqual(route["points"][0]["elevation_meters"], 2.8)
        loaded = self.client.get(f"/api/projects/{self.ids['project']}/floors/{self.ids['floor']}/layouts")
        self.assertEqual(loaded.status_code, 200, loaded.text)
        self.assertEqual(loaded.json()["geometry"]["routes"], [route])
        self.assertEqual(loaded.json()["extension"]["route_details"][0]["route_kind"], "observed")
        with Session(self.engine) as session:
            revisions = session.scalars(select(FloorPlanInterpretationReview).where(
                FloorPlanInterpretationReview.interpretation_run_id == self.ids["run"]
            ).order_by(FloorPlanInterpretationReview.revision_number)).all()
            self.assertEqual(len(revisions), 2)
            self.assertNotEqual(revisions[0].review_json, revisions[1].review_json)
    def test_walls_only_layout_save_without_room_polygons(self):
        self._login()
        review_path = f"/api/floor-plans/{self.ids['floor_plan']}/interpretation/reviews"
        payload = self._review_payload()
        # Reject all rooms to simulate a walls-only review
        for room in payload["rooms"]:
            room["disposition"] = "rejected"
        res = self.client.post(review_path, json=payload)
        self.assertEqual(res.status_code, 201, res.text)
        save_path = f"/api/projects/{self.ids['project']}/floors/{self.ids['floor']}/floor-plans/{self.ids['floor_plan']}/interpretation/layout"
        save = {
            "candidate_run_id": self.candidate.provenance.candidate_run_id,
            "review_revision_number": 1,
            "expected_layout_version_number": None,
            "idempotency_key": str(uuid4()),
        }
        saved = self.client.post(save_path, json=save)
        self.assertEqual(saved.status_code, 201, saved.text)
        layout_geom = saved.json()["geometry"]
        self.assertGreater(len(layout_geom["walls"]), 0)
        self.assertEqual(len(layout_geom["rooms"]), 0)


if __name__ == "__main__":
    unittest.main()
