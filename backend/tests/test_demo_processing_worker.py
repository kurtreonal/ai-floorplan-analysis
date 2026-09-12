import unittest
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import cv2
import numpy as np
from PIL import Image
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_engine
from app.models import (
    Base,
    FloorPlan,
    FloorPlanInterpretationRun,
    FloorPlanPage,
    FloorPlanSource,
    ProcessingArtifact,
    ProcessingJob,
    ProcessingJobAttempt,
    Project,
    ProjectFloor,
    Role,
    User,
)
from app.services.demo_processing_service import process_demo_job


def floor_plan_png() -> bytes:
    image = np.full((300, 400, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (50, 40), (350, 260), (0, 0, 0), 5)
    cv2.line(image, (200, 40), (200, 260), (0, 0, 0), 5)
    cv2.circle(image, (110, 150), 12, (0, 0, 0), 3)
    output = BytesIO()
    Image.fromarray(image).save(output, format="PNG")
    return output.getvalue()


class DemoProcessingWorkerTests(unittest.TestCase):
    process = staticmethod(process_demo_job)

    def test_real_uploaded_pixels_follow_leased_worker_and_immutable_persistence(self):
        engine = get_engine()
        Base.metadata.create_all(engine)
        marker = uuid4().hex
        content = floor_plan_png()
        original_hash = sha256(content).hexdigest()
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            upload_root = root / "uploads"
            processed_root = root / "processed"
            original = upload_root / "originals" / f"{marker}.png"
            original.parent.mkdir(parents=True)
            original.write_bytes(content)
            processed_root.mkdir(parents=True)
            settings = Settings(
                _env_file=None,
                app_env="development",
                upload_dir=upload_root,
                processed_dir=processed_root,
                max_upload_size_mb=25,
            )

            with Session(engine, expire_on_commit=False) as session:
                designer_role = session.scalar(select(Role).where(Role.name == "DESIGNER"))
                user = User(
                    oauth_provider=f"demo-worker-{marker}",
                    oauth_subject="designer",
                    role=designer_role,
                )
                project = Project(owner=user, name=f"Demo worker {marker}")
                floor = ProjectFloor(project=project, name="Ground", sort_order=0)
                plan = FloorPlan(
                    project_floor=floor,
                    original_filename="plan.png",
                    storage_path=f"originals/{marker}.png",
                    mime_type="image/png",
                    file_size=len(content),
                    processing_status="uploaded",
                )
                session.add(plan)
                session.flush()
                source = FloorPlanSource(
                    floor_plan_id=plan.id,
                    original_sha256=original_hash,
                )
                session.add(source)
                session.flush()
                page = FloorPlanPage(floor_plan_source_id=source.id, page_number=1)
                job = ProcessingJob(
                    floor_plan_id=plan.id,
                    job_type="floor_plan_analysis",
                    status="queued",
                )
                session.add_all((page, job))
                session.commit()
                ids = {
                    "user": user.id,
                    "project": project.id,
                    "floor": floor.id,
                    "plan": plan.id,
                    "source": source.id,
                    "page": page.id,
                    "job": job.id,
                }

            try:
                with Session(engine, expire_on_commit=False) as session:
                    run = self.process(
                        session,
                        job_id=ids["job"],
                        worker_identity="demo-worker:test",
                        settings=settings,
                    )
                    self.assertEqual(run.provider, "demo_cv_baseline")
                    candidate_json = run.candidate_json

                self.assertEqual(sha256(original.read_bytes()).hexdigest(), original_hash)
                with Session(engine) as session:
                    job = session.get(ProcessingJob, ids["job"])
                    attempts = session.scalars(
                        select(ProcessingJobAttempt).where(
                            ProcessingJobAttempt.processing_job_id == ids["job"]
                        )
                    ).all()
                    artifacts = session.scalars(
                        select(ProcessingArtifact).where(
                            ProcessingArtifact.processing_job_id == ids["job"]
                        )
                    ).all()
                    persisted = session.scalar(
                        select(FloorPlanInterpretationRun).where(
                            FloorPlanInterpretationRun.processing_job_id == ids["job"]
                        )
                    )
                    self.assertEqual((job.status, job.progress), ("completed", 100))
                    self.assertEqual(len(attempts), 1)
                    self.assertEqual(attempts[0].status, "succeeded")
                    self.assertEqual([item.artifact_kind for item in artifacts], ["normalized_image"])
                    self.assertEqual(persisted.candidate_json, candidate_json)
                    self.assertEqual(
                        persisted.candidate_sha256,
                        sha256(candidate_json.encode()).hexdigest(),
                    )
            finally:
                with Session(engine) as session:
                    run_ids = select(FloorPlanInterpretationRun.id).where(
                        FloorPlanInterpretationRun.processing_job_id == ids["job"]
                    )
                    session.execute(delete(FloorPlanInterpretationRun).where(FloorPlanInterpretationRun.id.in_(run_ids)))
                    session.execute(delete(ProcessingArtifact).where(ProcessingArtifact.processing_job_id == ids["job"]))
                    session.execute(delete(ProcessingJobAttempt).where(ProcessingJobAttempt.processing_job_id == ids["job"]))
                    session.execute(delete(ProcessingJob).where(ProcessingJob.id == ids["job"]))
                    session.execute(delete(FloorPlanPage).where(FloorPlanPage.id == ids["page"]))
                    session.execute(delete(FloorPlanSource).where(FloorPlanSource.id == ids["source"]))
                    session.execute(delete(FloorPlan).where(FloorPlan.id == ids["plan"]))
                    session.execute(delete(ProjectFloor).where(ProjectFloor.id == ids["floor"]))
                    session.execute(delete(Project).where(Project.id == ids["project"]))
                    session.execute(delete(User).where(User.id == ids["user"]))
                    session.commit()


if __name__ == "__main__":
    unittest.main()
