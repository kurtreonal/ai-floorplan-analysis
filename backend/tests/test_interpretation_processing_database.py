"""Run the actual interpretation worker through the isolated MySQL fixture."""
from hashlib import sha256
from tests import test_demo_processing_worker as fixture
from app.services.interpretation_processing_service import process_interpretation_job


class InterpretationProcessingDatabaseTests(fixture.DemoProcessingWorkerTests):
    process = staticmethod(process_interpretation_job)
    assert_page_outcome = True


class InterpretationArtifactCollisionDatabaseTests(InterpretationProcessingDatabaseTests):
    """Reset IDs or interrupted writes cannot overwrite/reuse unregistered pixels."""

    def process(self, session, **kwargs):
        from pathlib import Path
        from PIL import Image
        from app.models import ProcessingArtifact, ProcessingJob
        from sqlalchemy import select
        job = session.get(ProcessingJob, kwargs['job_id'])
        root = Path(kwargs['settings'].processed_dir)
        legacy = root / 'normalized' / f'floor-plan-{job.floor_plan_id}' / f'job-{job.id}' / 'page-0001.png'
        legacy.parent.mkdir(parents=True, exist_ok=True)
        with Image.new('RGB', (29, 17), 'red') as image:
            image.save(legacy, format='PNG')
        before = legacy.read_bytes()
        run = process_interpretation_job(session, **kwargs)
        artifact = session.scalar(select(ProcessingArtifact).where(
            ProcessingArtifact.id == run.source_artifact_id))
        self.assertTrue(artifact.relative_path.startswith('interpretation-runs/'))
        self.assertEqual((artifact.pixel_width, artifact.pixel_height), (400, 300))
        self.assertEqual(legacy.read_bytes(), before)
        self.assertNotEqual((root / artifact.relative_path).resolve(), legacy.resolve())
        return run


def test_pdf_preparation_preserves_orphans_page_identity_and_registered_reuse(tmp_path):
    """Real PDF conversion/registry; isolated DB transaction, no model inference."""
    from unittest.mock import patch
    from uuid import uuid4

    from PIL import Image
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.core.config import Settings
    from app.core.database import get_engine
    from app.models import (FloorPlan, FloorPlanSource, FloorPlanPage,
                            ProcessingArtifact, ProcessingJob, Project, ProjectFloor, Role, User)
    from app.services import interpretation_processing_service as service

    uploads, processed = tmp_path / 'uploads', tmp_path / 'processed'
    original = uploads / 'originals' / 'two-pages.pdf'
    original.parent.mkdir(parents=True)
    with Image.new('RGB', (160, 100), 'white') as first, \
         Image.new('RGB', (120, 180), 'white') as second:
        first.save(original, 'PDF', save_all=True, append_images=[second])
    original_bytes = original.read_bytes()
    settings = Settings(_env_file=None, app_env='development',
                        upload_dir=uploads, processed_dir=processed)
    with get_engine().connect() as connection:
        outer = connection.begin()
        try:
            with Session(connection, join_transaction_mode='create_savepoint',
                         expire_on_commit=False) as session:
                role = session.scalar(select(Role).where(Role.name == 'DESIGNER'))
                user = User(oauth_provider='pdf-collision-test', oauth_subject=uuid4().hex, role=role)
                project = Project(owner=user, name='PDF collision verification')
                floor = ProjectFloor(project=project, name='Ground')
                plan = FloorPlan(project_floor=floor, original_filename='two-pages.pdf',
                                 storage_path='originals/two-pages.pdf', mime_type='application/pdf',
                                 file_size=len(original_bytes), processing_status='uploaded')
                source = FloorPlanSource(floor_plan=plan, original_sha256=sha256(original_bytes).hexdigest(),
                                         pages=[FloorPlanPage(page_number=1), FloorPlanPage(page_number=2)])
                job = ProcessingJob(floor_plan=plan, job_type='floor_plan_analysis', status='processing')
                session.add_all([source, job]); session.flush()
                orphans = []
                for folder in ('pdf-pages', 'normalized'):
                    for page in source.pages:
                        path = processed / folder / f'floor-plan-{plan.id}' / f'job-{job.id}' / f'page-{page.page_number:04d}.png'
                        path.parent.mkdir(parents=True, exist_ok=True)
                        with Image.new('RGB', (29, 17), 'red') as image:
                            image.save(path, 'PNG')
                        orphans.append((path, path.read_bytes()))
                artifacts = [service._registered_artifact(session, job=job, floor_plan=plan,
                             source_manifest=source, settings=settings, page=page) for page in source.pages]
                artifact_paths = {item.absolute_path for item in artifacts}
                assert len(artifact_paths) == 2
                assert not artifact_paths.intersection(path for path, _ in orphans)
                records = session.scalars(select(ProcessingArtifact).where(
                    ProcessingArtifact.processing_job_id == job.id)).all()
                assert len(records) == 4
                page_numbers = {page.id: page.page_number for page in source.pages}
                assert {(item.artifact_kind, page_numbers[item.floor_plan_page_id]) for item in records} == {
                    ('pdf_page', 1), ('normalized_image', 1), ('pdf_page', 2), ('normalized_image', 2)}
                assert all(item.relative_path.startswith('interpretation-runs/') for item in records)
                with Image.open(artifacts[0].absolute_path) as image:
                    assert image.width > image.height
                with Image.open(artifacts[1].absolute_path) as image:
                    assert image.height > image.width
                with patch.object(service, 'convert_pdf_page', side_effect=AssertionError('must reuse')), \
                     patch.object(service, 'normalize_image', side_effect=AssertionError('must reuse')):
                    reused = service._registered_artifact(session, job=job, floor_plan=plan,
                             source_manifest=source, settings=settings, page=source.pages[1])
                assert reused.absolute_path == artifacts[1].absolute_path
                assert all(path.read_bytes() == content for path, content in orphans)
                assert original.read_bytes() == original_bytes
        finally:
            outer.rollback()


class MulticlassFluorescentWorkerDatabaseTests(fixture.DemoProcessingWorkerTests):
    """Real worker/persistence; fake inference is not detection-accuracy evidence."""
    expected_provider = 'development_multiclass56_yolo'
    assert_page_outcome = True
    model_classes = (56,57)
    expected_labels = ('2 x 40 watts fluorescent lamp','1 x 40 watts fluorescent lamp')

    def process(self, session, **kwargs):
        from unittest.mock import patch
        from app.ai.floor_plan_interpretation import multiclass_symbol_detector as detector
        from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationCandidate
        from app.models import ProcessingJob
        from app.services.interpretation_page_outcome_service import configure_page_outcomes
        mapping={i:(f'Fixture {i}',f'drawing:L{i}') for i in range(80)}
        mapping.update({56+i:entry for i,entry in enumerate(detector.EXTENSION_IDENTITIES)})
        mapping.update({cls:(label,f'drawing:L{cls}')
                        for cls,label in zip(self.model_classes,self.expected_labels)})
        proposals=[{'bbox':(100+40*i,120,128+40*i,148),'score':.81,'class_id':cls,
                    'tile_origin':(0,0)} for i,cls in enumerate(self.model_classes)]
        with patch.object(detector,'verify_artifacts',return_value=mapping), \
             patch.object(detector,'locate',return_value=(proposals,False)), \
             patch.object(detector,'PROFILE','lamps80'),patch.object(detector,'CLASS_COUNT',80), \
             patch.object(detector,'CHECKPOINT_SHA256','c'*64),patch.object(detector,'DATASET_SHA256','d'*64), \
             patch.object(detector,'PROMPT_VERSION','partial-label-80-lamps-replay-v4'):
            job=session.get(ProcessingJob,kwargs['job_id'])
            outcomes=configure_page_outcomes(session,processing_job=job,page_numbers=[1])
            outcomes[0].provider=detector.PROVIDER;outcomes[0].model_release_id=detector.PROVIDER
            outcomes[0].configuration_sha256=detector.configuration_sha256();session.commit()
            run=process_interpretation_job(session,**kwargs)
        candidate=FloorPlanInterpretationCandidate.model_validate_json(run.candidate_json)
        self.assertEqual(candidate.provenance.prompt_version,'partial-label-80-lamps-replay-v4')
        parameters={p.name:p.value for p in candidate.provenance.inference_parameters}
        self.assertEqual(parameters['model-class-count'],'80')
        self.assertEqual(parameters['development-profile'],'lamps80')
        self.assertEqual(parameters['checkpoint-sha256'],'c'*64)
        self.assertEqual([s.observed_label for s in candidate.payload.symbols.items],
                         list(self.expected_labels))
        self.assertEqual([s.training_legend.model_class_id for s in candidate.payload.symbols.items],
                         list(self.model_classes))
        self.assertTrue(all(s.mapping_state=='unknown' and s.catalog_class_id is None
                            for s in candidate.payload.symbols.items))
        self.assertEqual(run.candidate_sha256,sha256(run.candidate_json.encode()).hexdigest())
        return run


class MulticlassSwitchWorkerDatabaseTests(MulticlassFluorescentWorkerDatabaseTests):
    """Same shared worker: switch names/IDs persist without auto-approval."""
    model_classes = (62,63,64)
    expected_labels = ('One gang device switch','Two gang device switch','Three gang device switch')


class ExperimentalPullStationWorkerDatabaseTests(fixture.DemoProcessingWorkerTests):
    expected_provider = "experimental_pull_station_template"
    assert_page_outcome = True

    def process(self, session, **kwargs):
        from unittest.mock import patch
        from app.ai.floor_plan_interpretation.experimental_pull_station import (
            PROVIDER, SOURCE_SHA256, configuration_sha256,
        )
        from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationCandidate
        from app.models import ProcessingJob
        from app.services.interpretation_page_outcome_service import configure_page_outcomes
        job = session.get(ProcessingJob, kwargs["job_id"])
        outcomes = configure_page_outcomes(session, processing_job=job, page_numbers=[1])
        outcomes[0].provider = PROVIDER
        outcomes[0].model_release_id = PROVIDER
        outcomes[0].configuration_sha256 = configuration_sha256()
        session.commit()
        match = {"bbox": (100, 120, 128, 148), "score": 0.81, "scale": 1.0,
                 "template_id": "1421451ddf2e1217c0833e17"}
        with patch("app.ai.floor_plan_interpretation.experimental_pull_station.source_digest", return_value=SOURCE_SHA256), \
             patch("app.services.interpretation_processing_service.locate", return_value=(match,)):
            run = process_interpretation_job(session, **kwargs)
        candidate = FloorPlanInterpretationCandidate.model_validate_json(run.candidate_json)
        self.assertEqual(candidate.provenance.model_release_id, PROVIDER)
        self.assertEqual(candidate.payload.symbols.items[0].mapping_state, "unknown")
        self.assertEqual(candidate.payload.symbols.items[0].center.x, 114)
        self.assertEqual(run.candidate_sha256, sha256(run.candidate_json.encode()).hexdigest())
        return run


class ExperimentalTrainedSymbolWorkerDatabaseTests(fixture.DemoProcessingWorkerTests):
    expected_provider = "experimental_reviewed_symbol_yolo"
    assert_page_outcome = True

    def process(self, session, **kwargs):
        from unittest.mock import patch
        from app.ai.floor_plan_interpretation.experimental_symbol_detector import (
            PROVIDER, CHECKPOINT_SHA256, configuration_sha256,
        )
        from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationCandidate
        from app.models import ProcessingJob
        from app.services.interpretation_page_outcome_service import configure_page_outcomes
        job = session.get(ProcessingJob, kwargs["job_id"])
        outcomes = configure_page_outcomes(session, processing_job=job, page_numbers=[1])
        outcomes[0].provider = PROVIDER
        outcomes[0].model_release_id = PROVIDER
        outcomes[0].configuration_sha256 = configuration_sha256()
        session.commit()
        proposal = {"bbox": (100, 120, 128, 148), "score": 0.81,
                    "class_id": 3, "tile_origin": (0, 0)}
        with patch("app.ai.floor_plan_interpretation.experimental_symbol_detector.verify_artifacts"), \
             patch("app.services.interpretation_processing_service.locate_trained_symbols",
                   return_value=((proposal,), False)):
            run = process_interpretation_job(session, **kwargs)
        candidate = FloorPlanInterpretationCandidate.model_validate_json(run.candidate_json)
        self.assertEqual(candidate.provenance.model_release_id, PROVIDER)
        self.assertIn(CHECKPOINT_SHA256, [p.value for p in candidate.provenance.inference_parameters])
        self.assertEqual(candidate.payload.symbols.items[0].mapping_state, "unknown")
        self.assertEqual(candidate.payload.symbols.items[0].observed_label, "Troffer lights")
        self.assertEqual(candidate.payload.symbols.items[0].center.x, 114)
        self.assertEqual(run.candidate_sha256, sha256(run.candidate_json.encode()).hexdigest())
        return run


class ExperimentalLinkedLegendWorkerDatabaseTests(fixture.DemoProcessingWorkerTests):
    expected_provider = "experimental_linked_legend_yolo"
    assert_page_outcome = True

    def process(self, session, **kwargs):
        from unittest.mock import patch
        from app.ai.floor_plan_interpretation.experimental_symbol_detector import (
            LINKED_PROVIDER, LINKED_CHECKPOINT_SHA256, linked_configuration_sha256,
        )
        from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationCandidate
        from app.models import ProcessingJob
        from app.services.interpretation_page_outcome_service import configure_page_outcomes
        job = session.get(ProcessingJob, kwargs["job_id"])
        outcomes = configure_page_outcomes(session, processing_job=job, page_numbers=[1])
        outcomes[0].provider = LINKED_PROVIDER
        outcomes[0].model_release_id = LINKED_PROVIDER
        outcomes[0].configuration_sha256 = linked_configuration_sha256()
        session.commit()
        proposal = {"bbox": (100, 120, 128, 148), "score": 0.81,
                    "class_id": 4, "tile_origin": (0, 0)}
        with patch("app.ai.floor_plan_interpretation.experimental_symbol_detector.verify_linked_artifacts"), \
             patch("app.services.interpretation_processing_service.locate_trained_symbols",
                   return_value=((proposal,), False)) as locator:
            run = process_interpretation_job(session, **kwargs)
        locator.assert_called_once()
        self.assertTrue(locator.call_args.kwargs["linked"])
        candidate = FloorPlanInterpretationCandidate.model_validate_json(run.candidate_json)
        self.assertEqual(candidate.provenance.model_release_id, LINKED_PROVIDER)
        self.assertIn(LINKED_CHECKPOINT_SHA256,
                      [p.value for p in candidate.provenance.inference_parameters])
        self.assertEqual(candidate.payload.symbols.items[0].mapping_state, "unknown")
        self.assertEqual(candidate.payload.symbols.items[0].observed_label, "Troffer lights")
        self.assertEqual(run.candidate_sha256, sha256(run.candidate_json.encode()).hexdigest())
        return run


class InterpretationPageUniquenessDatabaseTests(fixture.DemoProcessingWorkerTests):
    def process(self, session, **kwargs):
        from uuid import uuid4
        from sqlalchemy.exc import IntegrityError, MultipleResultsFound
        from app.models import FloorPlanPage, FloorPlanInterpretationRun
        from app.repositories.floor_plan_interpretation_repository import find_by_processing_job
        run = process_interpretation_job(session, **kwargs)
        page = session.get(FloorPlanPage, run.floor_plan_page_id)
        # Only schema behavior is under test here, not multipage inference.
        savepoint = session.begin_nested()
        try:
            second_page = FloorPlanPage(floor_plan_source_id=page.floor_plan_source_id, page_number=2)
            session.add(second_page)
            session.flush()
            values = dict(processing_job_id=run.processing_job_id,
                floor_plan_id=run.floor_plan_id, floor_plan_page_id=second_page.id,
                source_artifact_id=run.source_artifact_id, provider=run.provider,
                candidate_sha256=run.candidate_sha256, candidate_json=run.candidate_json)
            second = FloorPlanInterpretationRun(candidate_run_id=uuid4().hex, **values)
            session.add(second)
            session.flush()
            self.assertEqual(find_by_processing_job(session, processing_job_id=run.processing_job_id,
                floor_plan_page_id=second_page.id).id, second.id)
            with self.assertRaises(MultipleResultsFound):
                find_by_processing_job(session, processing_job_id=run.processing_job_id)
            with self.assertRaises(IntegrityError):
                with session.begin_nested():
                    session.add(FloorPlanInterpretationRun(candidate_run_id=uuid4().hex, **values))
                    session.flush()
        finally:
            savepoint.rollback()
        return run


class InterpretationExpiredLeaseDatabaseTests(fixture.DemoProcessingWorkerTests):
    expected_attempts = 2

    def process(self, session, **kwargs):
        from datetime import datetime
        from unittest.mock import patch
        from sqlalchemy import select, func
        from app.models import FloorPlanInterpretationRun, ProcessingJobAttempt
        from app.services import interpretation_processing_service as service

        original = service._persist_fenced_run

        def expire_before_write(session, *, claim, worker_identity, run, page_outcome=None, provider=None):
            attempt = session.get(ProcessingJobAttempt, claim.attempt_id)
            attempt.lease_expires_at = datetime(2000, 1, 1)
            session.commit()
            return original(
                session,
                claim=claim,
                worker_identity=worker_identity,
                run=run,
                page_outcome=page_outcome,
                provider=provider or service.PROVIDER,
            )

        with patch.object(service, "_persist_fenced_run", side_effect=expire_before_write):
            with self.assertRaises(service.InterpretationProcessingError) as error:
                service.process_interpretation_job(session, **kwargs)
        self.assertEqual(error.exception.code, "PROCESSING_LEASE_EXPIRED")
        self.assertEqual(session.scalar(select(func.count()).select_from(FloorPlanInterpretationRun).where(
            FloorPlanInterpretationRun.processing_job_id == kwargs["job_id"],
        )), 0)
        session.rollback()
        # A fresh attempt reuses only trusted artifacts and publishes one run.
        return service.process_interpretation_job(session, **kwargs)


class InterpretationMemoryFailureDatabaseTests(fixture.DemoProcessingWorkerTests):
    expected_attempts = 2

    def process(self, session, **kwargs):
        from unittest.mock import patch
        from sqlalchemy import select, func
        from app.models import FloorPlanInterpretationRun
        from app.services import interpretation_processing_service as service

        with patch.object(service, "interpret_floor_plan_demo", side_effect=MemoryError("synthetic failure")):
            with self.assertRaises(service.InterpretationProcessingError) as error:
                service.process_interpretation_job(session, **kwargs)
        self.assertEqual(error.exception.code, "INTERPRETATION_PROCESSING_FAILED")
        self.assertEqual(session.scalar(select(func.count()).select_from(FloorPlanInterpretationRun).where(
            FloorPlanInterpretationRun.processing_job_id == kwargs["job_id"],
        )), 0)
        session.rollback()
        return service.process_interpretation_job(session, **kwargs)


class InterpretationCrashRecoveryDatabaseTests(fixture.DemoProcessingWorkerTests):
    expected_attempts = 2

    def process(self, session, **kwargs):
        from datetime import datetime
        from unittest.mock import patch
        from sqlalchemy import select
        from app.models import ProcessingJobAttempt
        from app.services import interpretation_processing_service as service
        from app.workers.interpretation_worker import _next_queued_job_id

        # SystemExit deliberately bypasses the service's recoverable Exception
        # path, modeling loss of the process after its durable claim/heartbeat.
        with patch.object(service, "_registered_artifact", side_effect=SystemExit()):
            with self.assertRaises(SystemExit):
                service.process_interpretation_job(session, **kwargs)
        session.rollback()
        self.assertIsNone(_next_queued_job_id(session))  # Live lease is not stolen.
        attempt = session.scalar(select(ProcessingJobAttempt).where(
            ProcessingJobAttempt.processing_job_id == kwargs["job_id"],
            ProcessingJobAttempt.active_marker.is_(True),
        ))
        attempt.lease_expires_at = datetime(2000, 1, 1)
        session.commit()
        self.assertEqual(_next_queued_job_id(session), kwargs["job_id"])
        return service.process_interpretation_job(session, **kwargs)
