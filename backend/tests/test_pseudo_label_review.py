import json
import shutil
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ai.floor_plan_interpretation import (
    CandidateHostProvenance,
    CompletenessChecklist,
    DatasetApprovalDecision,
    FloorPlanInterpretationCandidate,
    InferenceParameter,
    ObservedWiringReview,
    OpeningReview,
    PanelReview,
    PixelPoint,
    PseudoLabelingError,
    ReviewDocument,
    RoomReview,
    ScaleEvidenceReview,
    SymbolReview,
    WallReview,
    bind_dataset_approval,
    build_candidate_envelope,
    deserialize_review_document,
    export_approved_training_candidates,
    interpret_floor_plan_demo,
    record_pseudo_label_run,
    submit_append_only_review,
)
from app.core.database import get_engine
from app.models import (
    Base,
    DatasetApproverAssignment,
    FloorPlan,
    FloorPlanInterpretationReview,
    FloorPlanInterpretationRun,
    FloorPlanPage,
    FloorPlanSource,
    ProcessingArtifact,
    ProcessingJob,
    ProcessingJobAttempt,
    ProcessingJobCancellation,
    Project,
    ProjectFloor,
    Role,
    SymbolLegend,
    User,
)


def synthetic_plan():
    image = np.full((300, 400, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (50, 40), (350, 260), (0, 0, 0), 5)
    cv2.line(image, (200, 40), (200, 260), (0, 0, 0), 5)
    cv2.circle(image, (110, 150), 12, (0, 0, 0), 3)
    cv2.circle(image, (280, 150), 12, (0, 0, 0), 3)
    return image


class PseudoLabelReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = get_engine()
        Base.metadata.create_all(cls.engine)
        marker = uuid4().hex
        cls.marker = marker

        with Session(cls.engine) as session:
            session.execute(delete(DatasetApproverAssignment))
            session.commit()

        with Session(cls.engine, expire_on_commit=False) as session:
            roles = {
                role.name: role
                for role in session.scalars(
                    select(Role).where(Role.name.in_(("ADMIN", "DESIGNER")))
                )
            }
            cls.designer = User(
                oauth_provider=f"u9-{marker}",
                oauth_subject="designer",
                role=roles["DESIGNER"],
            )
            cls.other_designer = User(
                oauth_provider=f"u9-{marker}",
                oauth_subject="other_designer",
                role=roles["DESIGNER"],
            )
            cls.admin = User(
                oauth_provider=f"u9-{marker}",
                oauth_subject="admin",
                role=roles["ADMIN"],
            )
            cls.approver = User(
                oauth_provider=f"u9-{marker}",
                oauth_subject="approver",
                role=roles["ADMIN"],
            )
            cls.deactivated_approver = User(
                oauth_provider=f"u9-{marker}",
                oauth_subject="deactivated_approver",
                role=roles["ADMIN"],
            )

            project = Project(owner=cls.designer, name=f"U9 Project {marker}")
            floor = ProjectFloor(project=project, name="Ground Floor", sort_order=0)
            floor_plan = FloorPlan(
                project_floor=floor,
                original_filename="u9_test.png",
                storage_path=f"originals/{marker}.png",
                mime_type="image/png",
                file_size=128,
                processing_status="completed",
            )
            session.add_all((floor_plan, cls.other_designer, cls.admin, cls.approver, cls.deactivated_approver))
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
            legend = session.scalar(select(SymbolLegend).where(SymbolLegend.is_active.is_(True)))
            cls.created_legend = legend is None
            if legend is None:
                legend = SymbolLegend(
                    class_id=98765,
                    name=f"Duplex Receptacle {marker[:8]}",
                    is_active=True,
                )
                session.add(legend)
            session.add_all((page, job))
            session.flush()

            artifact = ProcessingArtifact(
                processing_job_id=job.id,
                floor_plan_page_id=page.id,
                artifact_kind="normalized_image",
                relative_path=f"normalized/u9-{marker}.png",
                mime_type="image/png",
                byte_size=128,
                sha256="2" * 64,
                pixel_width=400,
                pixel_height=300,
            )
            session.add(artifact)
            session.flush()

            # 1. Create assignment to be deactivated first
            deactivated_assignment = DatasetApproverAssignment(
                assignee_user_id=cls.deactivated_approver.id,
                assigned_by_user_id=cls.admin.id,
                authority_scope="VED_AI_DATASET_APPROVER",
                qualification_category="SENIOR_REE",
                professional_reference="PRC-REE-7654321",
                active_marker=True,
                active_from=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=20),
            )
            session.add(deactivated_assignment)
            session.commit()

            # Deactivate it so active_marker becomes NULL
            deactivated_assignment.active_marker = None
            deactivated_assignment.inactive_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=5)
            deactivated_assignment.deactivated_by_user_id = cls.admin.id
            session.commit()

            # 2. Now create the single active dataset approver assignment
            approver_assignment = DatasetApproverAssignment(
                assignee_user_id=cls.approver.id,
                assigned_by_user_id=cls.admin.id,
                authority_scope="VED_AI_DATASET_APPROVER",
                qualification_category="PEE",
                professional_reference="PRC-PEE-1234567",
                active_marker=True,
                active_from=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=10),
            )
            session.add(approver_assignment)
            session.commit()

            cls.floor_plan_id = floor_plan.id
            cls.floor_plan_page_id = page.id
            cls.job_id = job.id
            cls.artifact_id = artifact.id
            cls.legend_id = legend.id
            cls.approver_assignment_id = approver_assignment.id

        # Generate candidate payload
        cv_result = interpret_floor_plan_demo(synthetic_plan())
        provenance = CandidateHostProvenance(
            candidate_run_id=marker,
            processing_job_id=cls.job_id,
            floor_plan_source_id=source.id,
            floor_plan_page_id=cls.floor_plan_page_id,
            source_artifact_id=cls.artifact_id,
            source_page_number=1,
            source_sha256="1" * 64,
            source_artifact_sha256="2" * 64,
            expected_width_pixels=400,
            expected_height_pixels=300,
            model_release_id="ved-vlm-v1",
            base_model_revision="base-r1",
            adapter_revision="adapter-r1",
            prompt_version="v1_0",
            runtime_version="rt_1_0",
            inference_parameters=(
                InferenceParameter(name="temp", value="0.0"),
            ),
            created_at=datetime.now(UTC),
        )
        cls.candidate = build_candidate_envelope(
            payload=cv_result,
            provenance=provenance,
        )

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="u9_test_"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @classmethod
    def tearDownClass(cls):
        with Session(cls.engine) as session:
            session.execute(delete(FloorPlanInterpretationReview))
            session.execute(delete(FloorPlanInterpretationRun))
            session.execute(delete(ProcessingJobAttempt))
            session.execute(delete(ProcessingJobCancellation))
            session.execute(delete(ProcessingArtifact))
            session.execute(delete(ProcessingJob))
            session.execute(delete(FloorPlanPage))
            session.execute(delete(FloorPlanSource))
            session.execute(delete(FloorPlan))
            session.execute(delete(ProjectFloor))
            session.execute(delete(Project))
            session.execute(delete(DatasetApproverAssignment))
            session.execute(delete(User).where(User.oauth_provider.like(f"u9-{cls.marker}%")))
            if cls.created_legend:
                session.execute(delete(SymbolLegend).where(SymbolLegend.id == cls.legend_id))
            session.commit()

    def _ensure_run(self, session: Session) -> FloorPlanInterpretationRun:
        run = record_pseudo_label_run(
            session,
            candidate=self.candidate,
            processing_job_id=self.job_id,
            floor_plan_id=self.floor_plan_id,
            floor_plan_page_id=self.floor_plan_page_id,
            source_artifact_id=self.artifact_id,
            provider="vlm_local",
        )
        session.commit()
        return run

    def _ensure_review_revision_1(self, session: Session) -> FloorPlanInterpretationReview:
        self._ensure_run(session)
        existing = session.scalar(
            select(FloorPlanInterpretationReview)
            .join(
                FloorPlanInterpretationRun,
                FloorPlanInterpretationReview.interpretation_run_id == FloorPlanInterpretationRun.id,
            )
            .where(
                FloorPlanInterpretationRun.candidate_run_id == self.candidate.provenance.candidate_run_id,
                FloorPlanInterpretationReview.revision_number == 1,
            )
        )
        if existing is not None:
            return existing

        checklist = CompletenessChecklist(
            symbols="complete",
            walls="complete",
            rooms="complete",
            openings="complete",
            panels="not_applicable",
            scale_evidence="not_applicable",
            observed_wiring="not_applicable",
        )
        wall_rev = WallReview(
            id="wall-0001",
            disposition="accepted",
            start=PixelPoint(x=50.0, y=40.0),
            end=PixelPoint(x=350.0, y=40.0),
            thickness_meters=0.15,
            height_meters=3.0,
        )
        room_rev = RoomReview(
            id="room-0001",
            disposition="accepted",
            name="Main Office",
            boundary=(
                PixelPoint(x=50.0, y=40.0),
                PixelPoint(x=350.0, y=40.0),
                PixelPoint(x=350.0, y=260.0),
                PixelPoint(x=50.0, y=260.0),
            ),
        )
        sym_rev = SymbolReview(
            id="symbol-0001",
            disposition="accepted",
            center=PixelPoint(x=110.0, y=150.0),
            symbol_legend_id=self.legend_id,
            class_id=1,
            class_name="Duplex Convenience Receptacle",
        )
        opening_rev = OpeningReview(
            id="opening-0001",
            disposition="accepted",
            kind="door",
            points=(PixelPoint(x=50.0, y=100.0), PixelPoint(x=50.0, y=140.0)),
        )

        return submit_append_only_review(
            session,
            current_user=self.designer,
            floor_plan_id=self.floor_plan_id,
            candidate_run_id=self.candidate.provenance.candidate_run_id,
            expected_revision_number=None,
            review_complete=True,
            approved_for_layout=True,
            evidence_notes="Initial complete review",
            checklist=checklist,
            wall_thickness_meters=0.15,
            wall_height_meters=3.0,
            walls=[wall_rev],
            rooms=[room_rev],
            symbols=[sym_rev],
            openings=[opening_rev],
        )

    def test_record_pseudo_label_run_idempotency_and_integrity(self):
        with Session(self.engine) as session:
            run = self._ensure_run(session)
            self.assertIsNotNone(run.id)
            self.assertEqual(run.candidate_run_id, self.candidate.provenance.candidate_run_id)
            self.assertEqual(run.candidate_sha256, sha256(run.candidate_json.encode("utf-8")).hexdigest())

            # Idempotent call returns identical run
            run_repeat = record_pseudo_label_run(
                session,
                candidate=self.candidate,
                processing_job_id=self.job_id,
                floor_plan_id=self.floor_plan_id,
                floor_plan_page_id=self.floor_plan_page_id,
                source_artifact_id=self.artifact_id,
                provider="vlm_local",
            )
            self.assertEqual(run.id, run_repeat.id)

    def test_append_review_revision_monotonic_and_immutable(self):
        with Session(self.engine) as session:
            rev1 = self._ensure_review_revision_1(session)
            self.assertEqual(rev1.revision_number, 1)
            sha_rev1 = rev1.review_sha256

            checklist = CompletenessChecklist(
                symbols="complete",
                walls="complete",
                rooms="complete",
                openings="complete",
            )
            # Revision 2 (Designer corrects wall coordinates)
            wall_rev2 = WallReview(
                id="wall-0001",
                disposition="corrected",
                start=PixelPoint(x=52.0, y=40.0),
                end=PixelPoint(x=350.0, y=40.0),
                thickness_meters=0.15,
                height_meters=3.0,
            )
            room_rev = RoomReview(
                id="room-0001",
                disposition="accepted",
                name="Main Office",
                boundary=(
                    PixelPoint(x=50.0, y=40.0),
                    PixelPoint(x=350.0, y=40.0),
                    PixelPoint(x=350.0, y=260.0),
                    PixelPoint(x=50.0, y=260.0),
                ),
            )
            sym_rev = SymbolReview(
                id="symbol-0001",
                disposition="accepted",
                center=PixelPoint(x=110.0, y=150.0),
                symbol_legend_id=self.legend_id,
                class_id=1,
                class_name="Duplex Convenience Receptacle",
            )
            opening_rev = OpeningReview(
                id="opening-0001",
                disposition="accepted",
                kind="door",
                points=(PixelPoint(x=50.0, y=100.0), PixelPoint(x=50.0, y=140.0)),
            )
            rev2 = submit_append_only_review(
                session,
                current_user=self.designer,
                floor_plan_id=self.floor_plan_id,
                candidate_run_id=self.candidate.provenance.candidate_run_id,
                expected_revision_number=1,
                review_complete=True,
                approved_for_layout=True,
                evidence_notes="Corrected wall start coordinates",
                checklist=checklist,
                wall_thickness_meters=0.15,
                wall_height_meters=3.0,
                walls=[wall_rev2],
                rooms=[room_rev],
                symbols=[sym_rev],
                openings=[opening_rev],
            )
            self.assertEqual(rev2.revision_number, 2)

            # Check rev1 is untouched
            session.refresh(rev1)
            self.assertEqual(rev1.revision_number, 1)
            self.assertEqual(rev1.review_sha256, sha_rev1)

    def test_stale_review_revision_conflict(self):
        with Session(self.engine) as session:
            self._ensure_review_revision_1(session)
            checklist = CompletenessChecklist()
            wall_rev = WallReview(
                id="wall-0001",
                disposition="accepted",
                start=PixelPoint(x=50.0, y=40.0),
                end=PixelPoint(x=350.0, y=40.0),
            )
            room_rev = RoomReview(
                id="room-0001",
                disposition="accepted",
                boundary=(
                    PixelPoint(x=50.0, y=40.0),
                    PixelPoint(x=350.0, y=40.0),
                    PixelPoint(x=50.0, y=260.0),
                ),
            )
            sym_rev = SymbolReview(
                id="symbol-0001",
                disposition="accepted",
                center=PixelPoint(x=110.0, y=150.0),
            )

            with self.assertRaises(PseudoLabelingError) as cm:
                submit_append_only_review(
                    session,
                    current_user=self.designer,
                    floor_plan_id=self.floor_plan_id,
                    candidate_run_id=self.candidate.provenance.candidate_run_id,
                    expected_revision_number=999,  # Stale expected revision!
                    review_complete=False,
                    approved_for_layout=False,
                    evidence_notes="Stale test",
                    checklist=checklist,
                    walls=[wall_rev],
                    rooms=[room_rev],
                    symbols=[sym_rev],
                )
            self.assertEqual(cm.exception.code, "STALE_REVIEW_REVISION")

    def test_incomplete_review_and_checklist_enforcement(self):
        with Session(self.engine) as session:
            run = self._ensure_run(session)
            latest = session.scalar(
                select(FloorPlanInterpretationReview)
                .where(FloorPlanInterpretationReview.interpretation_run_id == run.id)
                .order_by(FloorPlanInterpretationReview.revision_number.desc())
                .limit(1)
            )
            latest_rev = latest.revision_number if latest is not None else None

            pending_checklist = CompletenessChecklist(
                symbols="pending",  # Pending marker!
                walls="complete",
                rooms="complete",
            )
            wall_rev = WallReview(
                id="wall-0001",
                disposition="accepted",
                start=PixelPoint(x=50.0, y=40.0),
                end=PixelPoint(x=350.0, y=40.0),
            )
            # Review complete cannot have pending checklist
            with self.assertRaises(PseudoLabelingError) as cm:
                submit_append_only_review(
                    session,
                    current_user=self.designer,
                    floor_plan_id=self.floor_plan_id,
                    candidate_run_id=self.candidate.provenance.candidate_run_id,
                    expected_revision_number=latest_rev,
                    review_complete=True,
                    approved_for_layout=False,
                    evidence_notes="Pending checklist test",
                    checklist=pending_checklist,
                    walls=[wall_rev],
                )
            self.assertEqual(cm.exception.code, "CHECKLIST_PENDING")

            # Review complete cannot have unresolved items
            valid_checklist = CompletenessChecklist()
            unresolved_sym = SymbolReview(
                id="symbol-0001",
                disposition="unresolved",
                center=PixelPoint(x=110.0, y=150.0),
            )
            with self.assertRaises(PseudoLabelingError) as cm:
                submit_append_only_review(
                    session,
                    current_user=self.designer,
                    floor_plan_id=self.floor_plan_id,
                    candidate_run_id=self.candidate.provenance.candidate_run_id,
                    expected_revision_number=latest_rev,
                    review_complete=True,
                    approved_for_layout=False,
                    evidence_notes="Unresolved item test",
                    checklist=valid_checklist,
                    walls=[wall_rev],
                    symbols=[unresolved_sym],
                )
            self.assertEqual(cm.exception.code, "REVIEW_HAS_UNRESOLVED_TARGETS")

    def test_cross_owner_denial_and_admin_read_only(self):
        with Session(self.engine) as session:
            self._ensure_review_revision_1(session)
            checklist = CompletenessChecklist()
            wall_rev = WallReview(
                id="wall-0001",
                disposition="accepted",
                start=PixelPoint(x=50.0, y=40.0),
                end=PixelPoint(x=350.0, y=40.0),
            )
            # Designer B cannot review Designer A's project
            with self.assertRaises(PseudoLabelingError) as cm:
                submit_append_only_review(
                    session,
                    current_user=self.other_designer,
                    floor_plan_id=self.floor_plan_id,
                    candidate_run_id=self.candidate.provenance.candidate_run_id,
                    expected_revision_number=1,
                    review_complete=False,
                    approved_for_layout=False,
                    evidence_notes="Cross-owner test",
                    checklist=checklist,
                    walls=[wall_rev],
                )
            self.assertEqual(cm.exception.code, "INTERPRETATION_NOT_FOUND")

            # Admin cannot write reviews for designer project
            with self.assertRaises(PseudoLabelingError) as cm:
                submit_append_only_review(
                    session,
                    current_user=self.admin,
                    floor_plan_id=self.floor_plan_id,
                    candidate_run_id=self.candidate.provenance.candidate_run_id,
                    expected_revision_number=1,
                    review_complete=False,
                    approved_for_layout=False,
                    evidence_notes="Admin write test",
                    checklist=checklist,
                    walls=[wall_rev],
                )
            self.assertEqual(cm.exception.code, "AUTHORIZATION_DENIED")

    def test_pre10_dataset_approver_authority_and_self_approval_denial(self):
        with Session(self.engine) as session:
            self._ensure_review_revision_1(session)

            # 1. Non-approver cannot bind dataset approval
            with self.assertRaises(PseudoLabelingError) as cm:
                bind_dataset_approval(
                    session,
                    current_user=self.other_designer,
                    floor_plan_id=self.floor_plan_id,
                    candidate_run_id=self.candidate.provenance.candidate_run_id,
                    revision_number=1,
                    decision="approved",
                    decision_notes="Unauthorized approval",
                )
            self.assertEqual(cm.exception.code, "DATASET_APPROVER_AUTHORITY_INVALID")

            # 2. Deactivated approver cannot bind dataset approval
            with self.assertRaises(PseudoLabelingError) as cm:
                bind_dataset_approval(
                    session,
                    current_user=self.deactivated_approver,
                    floor_plan_id=self.floor_plan_id,
                    candidate_run_id=self.candidate.provenance.candidate_run_id,
                    revision_number=1,
                    decision="approved",
                    decision_notes="Deactivated approval",
                )
            self.assertEqual(cm.exception.code, "DATASET_APPROVER_AUTHORITY_INVALID")

            # 3. Author / Reviewer self-approval rejection:
            # Temporarily deactivate current approver so active_marker becomes NULL
            approver_rec = session.get(DatasetApproverAssignment, self.approver_assignment_id)
            approver_rec.active_marker = None
            approver_rec.inactive_at = datetime.now(UTC).replace(tzinfo=None)
            approver_rec.deactivated_by_user_id = self.admin.id
            session.commit()

            designer_assignment = DatasetApproverAssignment(
                assignee_user_id=self.designer.id,
                assigned_by_user_id=self.admin.id,
                authority_scope="VED_AI_DATASET_APPROVER",
                qualification_category="PEE",
                professional_reference="PRC-PEE-9999999",
                active_marker=True,
                active_from=datetime.now(UTC).replace(tzinfo=None),
            )
            session.add(designer_assignment)
            session.commit()

            try:
                with self.assertRaises(PseudoLabelingError) as cm:
                    bind_dataset_approval(
                        session,
                        current_user=self.designer,
                        floor_plan_id=self.floor_plan_id,
                        candidate_run_id=self.candidate.provenance.candidate_run_id,
                        revision_number=1,
                        decision="approved",
                        decision_notes="Self-approval attempt",
                    )
                self.assertEqual(cm.exception.code, "DATASET_APPROVER_SELF_APPROVAL_DENIED")
            finally:
                session.delete(designer_assignment)
                session.commit()
                approver_rec.active_marker = True
                approver_rec.inactive_at = None
                approver_rec.deactivated_by_user_id = None
                session.commit()

            # 4. Valid distinct active approver approves revision 1
            approved_rev = bind_dataset_approval(
                session,
                current_user=self.approver,
                floor_plan_id=self.floor_plan_id,
                candidate_run_id=self.candidate.provenance.candidate_run_id,
                revision_number=1,
                decision="approved",
                decision_notes="Official PEE dataset approval for supervised training",
            )
            self.assertIsNotNone(approved_rev)
            doc = deserialize_review_document(approved_rev.review_json, approved_rev.review_sha256)
            self.assertIsNotNone(doc.dataset_approval)
            self.assertEqual(doc.dataset_approval.decision, "approved")
            self.assertEqual(doc.dataset_approval.approver_user_id, self.approver.id)

    def test_correction_after_approval_resets_dataset_approval(self):
        with Session(self.engine) as session:
            self._ensure_review_revision_1(session)

            # Ensure revision 1 has dataset approval first
            bind_dataset_approval(
                session,
                current_user=self.approver,
                floor_plan_id=self.floor_plan_id,
                candidate_run_id=self.candidate.provenance.candidate_run_id,
                revision_number=1,
                decision="approved",
                decision_notes="Approved for training",
            )

            # Ensure revision 2 exists
            rev2 = session.scalar(
                select(FloorPlanInterpretationReview)
                .join(
                    FloorPlanInterpretationRun,
                    FloorPlanInterpretationReview.interpretation_run_id == FloorPlanInterpretationRun.id,
                )
                .where(
                    FloorPlanInterpretationRun.candidate_run_id == self.candidate.provenance.candidate_run_id,
                    FloorPlanInterpretationReview.revision_number == 2,
                )
            )
            if rev2 is None:
                checklist = CompletenessChecklist()
                wall_rev2 = WallReview(
                    id="wall-0001",
                    disposition="corrected",
                    start=PixelPoint(x=52.0, y=40.0),
                    end=PixelPoint(x=350.0, y=40.0),
                    thickness_meters=0.15,
                    height_meters=3.0,
                )
                room_rev = RoomReview(
                    id="room-0001",
                    disposition="accepted",
                    name="Main Office",
                    boundary=(
                        PixelPoint(x=50.0, y=40.0),
                        PixelPoint(x=350.0, y=40.0),
                        PixelPoint(x=350.0, y=260.0),
                        PixelPoint(x=50.0, y=260.0),
                    ),
                )
                sym_rev = SymbolReview(
                    id="symbol-0001",
                    disposition="accepted",
                    center=PixelPoint(x=110.0, y=150.0),
                    symbol_legend_id=self.legend_id,
                    class_id=1,
                    class_name="Duplex Convenience Receptacle",
                )
                rev2 = submit_append_only_review(
                    session,
                    current_user=self.designer,
                    floor_plan_id=self.floor_plan_id,
                    candidate_run_id=self.candidate.provenance.candidate_run_id,
                    expected_revision_number=1,
                    review_complete=True,
                    approved_for_layout=True,
                    evidence_notes="Revision 2 correction",
                    checklist=checklist,
                    wall_thickness_meters=0.15,
                    wall_height_meters=3.0,
                    walls=[wall_rev2],
                    rooms=[room_rev],
                    symbols=[sym_rev],
                )

            self.assertIsNotNone(rev2)
            doc2 = deserialize_review_document(rev2.review_json, rev2.review_sha256)
            self.assertIsNone(doc2.dataset_approval, "New revision must not inherit prior dataset approval")

            # Rev 1 still retains its approval
            rev1 = session.scalar(
                select(FloorPlanInterpretationReview)
                .join(
                    FloorPlanInterpretationRun,
                    FloorPlanInterpretationReview.interpretation_run_id == FloorPlanInterpretationRun.id,
                )
                .where(
                    FloorPlanInterpretationRun.candidate_run_id == self.candidate.provenance.candidate_run_id,
                    FloorPlanInterpretationReview.revision_number == 1,
                )
            )
            doc1 = deserialize_review_document(rev1.review_json, rev1.review_sha256)
            self.assertIsNotNone(doc1.dataset_approval)
            self.assertEqual(doc1.dataset_approval.decision, "approved")

    def test_training_dataset_export_filtering(self):
        with Session(self.engine) as session:
            self._ensure_review_revision_1(session)

            # Ensure revision 1 is approved
            bind_dataset_approval(
                session,
                current_user=self.approver,
                floor_plan_id=self.floor_plan_id,
                candidate_run_id=self.candidate.provenance.candidate_run_id,
                revision_number=1,
                decision="approved",
                decision_notes="Approved for training",
            )
            # Export approved candidates
            exported = export_approved_training_candidates(
                session,
                current_user=self.admin,
                output_directory=self.temp_dir,
            )
            self.assertGreaterEqual(len(exported), 1, "At least 1 approved record should be exported")
            exported_doc = exported[0]
            self.assertEqual(exported_doc.schema_version, 1)
            self.assertGreaterEqual(len(exported_doc.symbols), 1)
            self.assertEqual(exported_doc.completeness.symbols, "complete")

            # Verify exported file exists on disk
            files = list(self.temp_dir.glob("*.json"))
            self.assertGreaterEqual(len(files), 1)


if __name__ == "__main__":
    unittest.main()
