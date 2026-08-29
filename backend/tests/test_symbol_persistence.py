import hashlib
import json
import math
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import delete, func, inspect, select
from sqlalchemy.exc import DatabaseError, IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai.symbol_detection.confidence_filter import (
    ClassifiedSymbolPrediction,
    SymbolConfidenceFilterResult,
    classify_symbol_predictions,
)
from app.ai.symbol_detection.inference import (
    MAXIMUM_DETECTIONS,
    SymbolBoundingBox,
    SymbolCenter,
    SymbolInferenceResult,
    SymbolPrediction,
)
from app.core.database import get_engine
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
    Wall,
)
from app.models.detected_symbol import DETECTED_SYMBOL_STATUSES
from app.repositories.detected_symbol_repository import (
    list_detected_symbols,
    lock_floor_plan,
)
from app.services.symbol_persistence import (
    ERROR_MESSAGES,
    PersistedDetectedSymbolRecord,
    SymbolPersistenceError,
    replace_detected_symbols,
    retrieve_detected_symbols,
)


def file_hashes(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def prediction(
    confidence: float,
    *,
    class_id: int = 0,
    class_name: str = "custom-symbol",
    box: SymbolBoundingBox | None = None,
    center: SymbolCenter | None = None,
) -> SymbolPrediction:
    selected_box = box or SymbolBoundingBox(1.25, 2.5, 5.75, 7.5)
    selected_center = center or SymbolCenter(3.5, 5.0)
    return SymbolPrediction(
        class_id=class_id,
        class_name=class_name,
        confidence=confidence,
        bounding_box=selected_box,
        center=selected_center,
    )


def classified_result(
    predictions: tuple[SymbolPrediction, ...] = (),
    *,
    threshold: float = 0.5,
    width: int = 100,
    height: int = 80,
    limit_reached: bool = False,
) -> SymbolConfidenceFilterResult:
    inference = SymbolInferenceResult(
        image_width=width,
        image_height=height,
        predictions=predictions,
        maximum_detections=MAXIMUM_DETECTIONS,
        detection_limit_reached=limit_reached,
    )
    return classify_symbol_predictions(inference, threshold=threshold)


class SymbolPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_engine()
        cls.storage_root = Path(__file__).resolve().parents[2] / "storage"
        cls.storage_hashes = file_hashes(cls.storage_root)
        cls.marker = uuid4().hex
        cls.created_ids: dict[str, object] = {}
        models = (
            User,
            Project,
            ProjectFloor,
            FloorPlan,
            ProcessingJob,
            Wall,
            DetectedSymbol,
            DetectionReview,
        )
        with Session(cls.engine) as session:
            cls.baseline_counts = {
                model.__tablename__: session.scalar(select(func.count()).select_from(model))
                for model in models
            }
        try:
            with Session(cls.engine) as session:
                designer_role = session.scalar(
                    select(Role).where(Role.name == "DESIGNER")
                )
                if designer_role is None:
                    raise RuntimeError("The DESIGNER seed role is required.")
                user = User(
                    oauth_provider="i4-test",
                    oauth_subject=f"designer-{cls.marker}",
                    email=f"designer-{cls.marker}@example.test",
                    display_name="I4 Designer",
                    role_id=designer_role.id,
                )
                project = Project(owner=user, name=f"I4 Project {cls.marker}")
                project_floor = ProjectFloor(project=project, name="I4 Floor")
                floor_plan = FloorPlan(
                    project_floor=project_floor,
                    original_filename="i4-original.png",
                    storage_path=f"originals/i4-{cls.marker}.png",
                    mime_type="image/png",
                    file_size=100,
                    processing_status="uploaded",
                )
                other_floor_plan = FloorPlan(
                    project_floor=project_floor,
                    original_filename="i4-other.png",
                    storage_path=f"originals/i4-other-{cls.marker}.png",
                    mime_type="image/png",
                    file_size=100,
                    processing_status="uploaded",
                )
                first_job = ProcessingJob(
                    floor_plan=floor_plan,
                    job_type="floor_plan_analysis",
                    status="processing",
                    progress=35,
                    error_message=None,
                )
                second_job = ProcessingJob(
                    floor_plan=floor_plan,
                    job_type="floor_plan_analysis",
                    status="processing",
                    progress=65,
                    error_message=None,
                )
                other_job = ProcessingJob(
                    floor_plan=other_floor_plan,
                    job_type="floor_plan_analysis",
                    status="processing",
                    progress=15,
                    error_message=None,
                )
                session.add_all((first_job, second_job, other_job))
                session.commit()
                cls.created_ids = {
                    "user": user.id,
                    "project": project.id,
                    "project_floor": project_floor.id,
                    "floor_plans": (floor_plan.id, other_floor_plan.id),
                    "jobs": (first_job.id, second_job.id, other_job.id),
                }
        except Exception:
            cls._cleanup_created_rows()
            raise

    @classmethod
    def _cleanup_created_rows(cls) -> None:
        ids = cls.created_ids
        with Session(cls.engine) as session:
            try:
                jobs = tuple(ids.get("jobs", ()))
                floors = tuple(ids.get("floor_plans", ()))
                if jobs:
                    detection_ids = tuple(
                        session.scalars(
                            select(DetectedSymbol.id).where(
                                DetectedSymbol.processing_job_id.in_(jobs)
                            )
                        )
                    )
                    if detection_ids:
                        session.execute(
                            delete(DetectionReview).where(
                                DetectionReview.detected_symbol_id.in_(detection_ids)
                            )
                        )
                    session.execute(
                        delete(DetectedSymbol).where(
                            DetectedSymbol.processing_job_id.in_(jobs)
                        )
                    )
                    session.execute(
                        delete(Wall).where(Wall.processing_job_id.in_(jobs))
                    )
                    session.execute(
                        delete(ProcessingJob).where(ProcessingJob.id.in_(jobs))
                    )
                if floors:
                    session.execute(delete(FloorPlan).where(FloorPlan.id.in_(floors)))
                if ids.get("project_floor"):
                    session.execute(
                        delete(ProjectFloor).where(
                            ProjectFloor.id == ids["project_floor"]
                        )
                    )
                if ids.get("project"):
                    session.execute(delete(Project).where(Project.id == ids["project"]))
                if ids.get("user"):
                    session.execute(delete(User).where(User.id == ids["user"]))
                session.commit()
            except Exception:
                session.rollback()
                raise

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls._cleanup_created_rows()
            with Session(cls.engine) as session:
                models = (
                    User,
                    Project,
                    ProjectFloor,
                    FloorPlan,
                    ProcessingJob,
                    Wall,
                    DetectedSymbol,
                    DetectionReview,
                )
                current = {
                    model.__tablename__: session.scalar(
                        select(func.count()).select_from(model)
                    )
                    for model in models
                }
            if current != cls.baseline_counts:
                raise AssertionError(
                    f"I4 database cleanup mismatch: {current!r}"
                )
            if file_hashes(cls.storage_root) != cls.storage_hashes:
                raise AssertionError("I4 changed storage artifacts.")
        finally:
            cls.engine.dispose()

    def setUp(self) -> None:
        self.session = Session(self.engine, expire_on_commit=False)
        self.floor_plan_id, self.other_floor_plan_id = self.created_ids["floor_plans"]
        self.job_id, self.second_job_id, self.other_job_id = self.created_ids["jobs"]
        detection_ids = tuple(
            self.session.scalars(
                select(DetectedSymbol.id).where(
                    DetectedSymbol.processing_job_id.in_(self.created_ids["jobs"])
                )
            )
        )
        if detection_ids:
            self.session.execute(
                delete(DetectionReview).where(
                    DetectionReview.detected_symbol_id.in_(detection_ids)
                )
            )
        self.session.execute(
            delete(DetectedSymbol).where(
                DetectedSymbol.processing_job_id.in_(self.created_ids["jobs"])
            )
        )
        for job_id, progress in (
            (self.job_id, 35),
            (self.second_job_id, 65),
            (self.other_job_id, 15),
        ):
            job = self.session.get(ProcessingJob, job_id)
            job.job_type = "floor_plan_analysis"
            job.status = "processing"
            job.progress = progress
            job.error_message = None
        for floor_plan_id in self.created_ids["floor_plans"]:
            self.session.get(FloorPlan, floor_plan_id).processing_status = "uploaded"
        self.session.commit()

    def tearDown(self) -> None:
        self.session.rollback()
        self.session.close()

    def assert_error(self, code: str, operation) -> SymbolPersistenceError:
        with self.assertRaises(SymbolPersistenceError) as caught:
            operation()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(str(caught.exception), ERROR_MESSAGES[code])
        return caught.exception

    def test_exact_model_columns_constraints_indexes_relationships_and_table_count(self):
        table = DetectedSymbol.__table__
        self.assertEqual(
            tuple(table.columns.keys()),
            (
                "id",
                "floor_plan_id",
                "processing_job_id",
                "prediction_index",
                "status",
                "original_class_id",
                "original_class_name",
                "original_confidence",
                "confidence_threshold",
                "image_width_pixels",
                "image_height_pixels",
                "bounding_box_x_min_pixels",
                "bounding_box_y_min_pixels",
                "bounding_box_x_max_pixels",
                "bounding_box_y_max_pixels",
                "center_x_pixels",
                "center_y_pixels",
                "maximum_detections",
                "detection_limit_reached",
                "created_at",
                "updated_at",
            ),
        )
        self.assertEqual(
            {constraint.name for constraint in table.constraints if constraint.name},
            {
                "uq_detected_symbols_job_prediction",
                "ck_detected_symbols_status",
                "ck_detected_symbols_prediction_index",
                "ck_detected_symbols_class_id",
                "ck_detected_symbols_confidence",
                "ck_detected_symbols_threshold",
                "ck_detected_symbols_image_dimensions",
                "ck_detected_symbols_pixel_bounds",
                "ck_detected_symbols_box_order",
                "ck_detected_symbols_maximum_detections",
                "ck_detected_symbols_limit_flag",
            },
        )
        self.assertEqual(
            {foreign_key.target_fullname for foreign_key in table.foreign_keys},
            {"floor_plans.id", "processing_jobs.id"},
        )
        self.assertTrue(table.c.floor_plan_id.index)
        self.assertTrue(table.c.processing_job_id.index)
        self.assertEqual(DETECTED_SYMBOL_STATUSES, ("detected", "needs_review"))
        self.assertIn("detected_symbols", Base.metadata.tables)
        self.assertEqual(len(Base.metadata.tables), 9)
        self.assertEqual(len(inspect(self.engine).get_table_names()), 9)
        self.assertEqual(
            DetectedSymbol.floor_plan.property.back_populates,
            "detected_symbols",
        )
        self.assertEqual(
            DetectedSymbol.processing_job.property.back_populates,
            "detected_symbols",
        )
        self.assertEqual(DetectedSymbol.reviews.property.back_populates, "detected_symbol")

    def test_mixed_predictions_round_trip_all_original_provenance_exactly(self):
        high = prediction(
            0.5000000000000001,
            class_id=7,
            class_name="custom-high",
        )
        low = prediction(
            0.49999999999999994,
            class_id=2,
            class_name="custom-low",
            box=SymbolBoundingBox(10.125, 12.25, 20.875, 30.5),
            center=SymbolCenter(15.5, 21.375),
        )
        result = classified_result((high, low), threshold=0.5)
        records = replace_detected_symbols(
            self.session,
            self.floor_plan_id,
            self.job_id,
            result,
        )
        self.assertEqual(tuple(item.prediction_index for item in records), (1, 2))
        self.assertEqual(tuple(item.status for item in records), ("detected", "needs_review"))
        self.assertEqual(records[0].original_class_id, 7)
        self.assertEqual(records[0].original_class_name, "custom-high")
        self.assertEqual(records[0].original_confidence, high.confidence)
        self.assertEqual(records[1].original_confidence, low.confidence)
        self.assertEqual(records[0].confidence_threshold, 0.5)
        self.assertEqual(records[1].bounding_box_x_min_pixels, 10.125)
        self.assertEqual(records[1].center_y_pixels, 21.375)
        self.assertEqual((records[0].image_width_pixels, records[0].image_height_pixels), (100, 80))
        self.assertEqual(records[0].maximum_detections, 300)
        self.assertFalse(records[0].detection_limit_reached)
        self.assertIsNotNone(records[0].created_at)
        self.assertIsNotNone(records[0].updated_at)

    def test_empty_and_same_job_replacement_clear_stale_rows(self):
        replace_detected_symbols(
            self.session,
            self.floor_plan_id,
            self.job_id,
            classified_result((prediction(0.9), prediction(0.1))),
        )
        replacement = replace_detected_symbols(
            self.session,
            self.floor_plan_id,
            self.job_id,
            classified_result((prediction(0.75, class_id=3),)),
        )
        self.assertEqual(len(replacement), 1)
        self.assertEqual(replacement[0].prediction_index, 1)
        empty = replace_detected_symbols(
            self.session,
            self.floor_plan_id,
            self.job_id,
            classified_result(),
        )
        self.assertEqual(empty, ())
        self.assertEqual(
            retrieve_detected_symbols(self.session, self.floor_plan_id, self.job_id),
            (),
        )

    def test_new_job_preserves_older_version_and_retrieval_isolated(self):
        first = replace_detected_symbols(
            self.session,
            self.floor_plan_id,
            self.job_id,
            classified_result((prediction(0.8, class_id=1),)),
        )
        second = replace_detected_symbols(
            self.session,
            self.floor_plan_id,
            self.second_job_id,
            classified_result((prediction(0.2, class_id=2),)),
        )
        self.assertNotEqual(first[0].processing_job_id, second[0].processing_job_id)
        self.assertEqual(
            retrieve_detected_symbols(self.session, self.floor_plan_id, self.job_id),
            first,
        )
        self.assertEqual(
            retrieve_detected_symbols(
                self.session, self.floor_plan_id, self.second_job_id
            ),
            second,
        )

    def test_reviewed_same_job_replacement_is_rejected_but_other_job_isolated(self):
        original = replace_detected_symbols(
            self.session,
            self.floor_plan_id,
            self.job_id,
            classified_result((prediction(0.8, class_id=1),)),
        )
        review = DetectionReview(
            detected_symbol_id=original[0].id,
            reviewer_user_id=self.created_ids["user"],
            sequence_number=1,
            decision="confirmed",
        )
        self.session.add(review)
        self.session.commit()
        job_before = self.session.get(ProcessingJob, self.job_id)
        floor_before = self.session.get(FloorPlan, self.floor_plan_id)
        side_effects_before = (
            job_before.status,
            job_before.progress,
            job_before.error_message,
            floor_before.processing_status,
        )

        self.assert_error(
            "SYMBOL_PERSISTENCE_FAILED",
            lambda: replace_detected_symbols(
                self.session,
                self.floor_plan_id,
                self.job_id,
                classified_result((prediction(0.7, class_id=2),)),
            ),
        )
        self.assertEqual(
            retrieve_detected_symbols(self.session, self.floor_plan_id, self.job_id),
            original,
        )
        self.assertEqual(
            self.session.scalar(
                select(func.count())
                .select_from(DetectionReview)
                .where(DetectionReview.detected_symbol_id == original[0].id)
            ),
            1,
        )
        other_version = replace_detected_symbols(
            self.session,
            self.floor_plan_id,
            self.second_job_id,
            classified_result((prediction(0.6, class_id=3),)),
        )
        self.assertEqual(len(other_version), 1)
        self.session.refresh(job_before)
        self.session.refresh(floor_before)
        self.assertEqual(
            (
                job_before.status,
                job_before.progress,
                job_before.error_message,
                floor_before.processing_status,
            ),
            side_effects_before,
        )

    def test_retrieval_is_ordered_immutable_json_compatible_and_relationship_free(self):
        replace_detected_symbols(
            self.session,
            self.floor_plan_id,
            self.job_id,
            classified_result(
                (
                    prediction(0.9, class_id=5, class_name="first"),
                    prediction(0.4, class_id=2, class_name="second"),
                )
            ),
        )
        records = retrieve_detected_symbols(
            self.session,
            self.floor_plan_id,
            self.job_id,
        )
        self.assertEqual(tuple(item.original_class_name for item in records), ("first", "second"))
        self.assertIsInstance(records[0], PersistedDetectedSymbolRecord)
        with self.assertRaises(FrozenInstanceError):
            records[0].status = "needs_review"
        serialized = records[0].to_dict()
        json.dumps(serialized)
        self.assertIsInstance(serialized["created_at"], str)
        raw = list_detected_symbols(
            self.session,
            floor_plan_id=self.floor_plan_id,
            processing_job_id=self.job_id,
        )[0]
        with self.assertRaises(Exception):
            _ = raw.floor_plan

    def test_retrieval_executes_no_i1_i2_i3_opencv_or_filesystem(self):
        replace_detected_symbols(
            self.session,
            self.floor_plan_id,
            self.job_id,
            classified_result((prediction(0.8),)),
        )
        with patch("builtins.open", side_effect=AssertionError("file used")), patch(
            "app.ai.symbol_detection.model_loader.load_symbol_detection_model",
            side_effect=AssertionError("I1 used"),
        ), patch(
            "app.ai.symbol_detection.inference.run_symbol_inference",
            side_effect=AssertionError("I2 used"),
        ), patch(
            "app.ai.symbol_detection.confidence_filter.classify_symbol_predictions",
            side_effect=AssertionError("I3 used"),
        ), patch("cv2.Canny", side_effect=AssertionError("OpenCV used")):
            records = retrieve_detected_symbols(
                self.session,
                self.floor_plan_id,
                self.job_id,
            )
        self.assertEqual(len(records), 1)

    def test_invalid_identifiers_and_parent_job_contracts_fail_safely(self):
        valid = classified_result()
        cases = [
            ("INVALID_FLOOR_PLAN_ID", lambda: replace_detected_symbols(self.session, 0, self.job_id, valid)),
            ("INVALID_FLOOR_PLAN_ID", lambda: replace_detected_symbols(self.session, True, self.job_id, valid)),
            ("INVALID_FLOOR_PLAN_ID", lambda: replace_detected_symbols(self.session, 2**63, self.job_id, valid)),
            ("INVALID_PROCESSING_JOB_ID", lambda: replace_detected_symbols(self.session, self.floor_plan_id, -1, valid)),
            ("FLOOR_PLAN_NOT_FOUND", lambda: replace_detected_symbols(self.session, 9_000_000_000, self.job_id, valid)),
            ("PROCESSING_JOB_NOT_FOUND", lambda: replace_detected_symbols(self.session, self.floor_plan_id, 9_000_000_000, valid)),
            ("PROCESSING_JOB_FLOOR_PLAN_MISMATCH", lambda: replace_detected_symbols(self.session, self.floor_plan_id, self.other_job_id, valid)),
        ]
        for code, operation in cases:
            with self.subTest(code=code):
                self.assert_error(code, operation)

        job = self.session.get(ProcessingJob, self.job_id)
        for field, value, code in (
            ("job_type", "other", "INVALID_PROCESSING_JOB_TYPE"),
            ("status", "queued", "INVALID_PROCESSING_JOB_STATUS"),
            ("status", "completed", "INVALID_PROCESSING_JOB_STATUS"),
            ("status", "failed", "INVALID_PROCESSING_JOB_STATUS"),
            ("status", "cancelled", "INVALID_PROCESSING_JOB_STATUS"),
        ):
            with self.subTest(field=field, value=value):
                setattr(job, field, value)
                self.session.flush()
                self.assert_error(
                    code,
                    lambda: replace_detected_symbols(
                        self.session,
                        self.floor_plan_id,
                        self.job_id,
                        valid,
                    ),
                )
                job = self.session.get(ProcessingJob, self.job_id)
                job.job_type = "floor_plan_analysis"
                job.status = "processing"
                self.session.commit()

    def test_malformed_results_are_rejected_before_database_access(self):
        valid_prediction = prediction(0.8)
        valid = classified_result((valid_prediction,))
        invalid_status = replace(
            valid,
            predictions=(
                ClassifiedSymbolPrediction(valid_prediction, "needs_review"),
            ),
        )
        invalid = (
            None,
            object(),
            replace(valid, predictions=list(valid.predictions)),
            replace(valid, image_width=0),
            replace(valid, image_height=4097),
            replace(valid, threshold=math.nan),
            replace(valid, threshold=1.1),
            replace(valid, maximum_detections=299),
            replace(valid, detection_limit_reached=True),
            invalid_status,
            replace(valid, predictions=(replace(valid.predictions[0], prediction=replace(valid_prediction, class_id=-1)),)),
            replace(valid, predictions=(replace(valid.predictions[0], prediction=replace(valid_prediction, class_name="")),)),
            replace(valid, predictions=(replace(valid.predictions[0], prediction=replace(valid_prediction, confidence=math.inf)),)),
            replace(valid, predictions=(replace(valid.predictions[0], prediction=replace(valid_prediction, bounding_box=SymbolBoundingBox(-1, 2, 5, 7.5))),)),
            replace(valid, predictions=(replace(valid.predictions[0], prediction=replace(valid_prediction, bounding_box=SymbolBoundingBox(5, 2, 1, 7.5))),)),
            replace(valid, predictions=(replace(valid.predictions[0], prediction=replace(valid_prediction, center=SymbolCenter(3.4, 5))),)),
        )
        for value in invalid:
            with self.subTest(value=repr(value)):
                with patch(
                    "app.services.symbol_persistence.lock_floor_plan",
                    side_effect=AssertionError("database accessed"),
                ):
                    self.assert_error(
                        "INVALID_CLASSIFIED_RESULT",
                        lambda item=value: replace_detected_symbols(
                            self.session,
                            self.floor_plan_id,
                            self.job_id,
                            item,
                        ),
                    )

    def test_unique_constraint_rejects_duplicate_job_prediction_index(self):
        replace_detected_symbols(
            self.session,
            self.floor_plan_id,
            self.job_id,
            classified_result((prediction(0.8),)),
        )
        existing = self.session.scalar(
            select(DetectedSymbol).where(
                DetectedSymbol.processing_job_id == self.job_id
            )
        )
        duplicate = DetectedSymbol(
            **{
                column.name: getattr(existing, column.name)
                for column in DetectedSymbol.__table__.columns
                if column.name not in {"id", "created_at", "updated_at"}
            }
        )
        self.session.add(duplicate)
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_failures_rollback_preserve_prior_rows_and_sanitize_details(self):
        original = replace_detected_symbols(
            self.session,
            self.floor_plan_id,
            self.job_id,
            classified_result((prediction(0.9),)),
        )
        private = r"mysql://secret C:\private\file SQL details"
        operations = (
            ("lock_floor_plan", "lock_floor_plan"),
            ("find_processing_job", "find_processing_job"),
            ("delete_processing_job_detections", "delete"),
        )
        for patch_name, label in operations:
            with self.subTest(stage=label), patch(
                f"app.services.symbol_persistence.{patch_name}",
                side_effect=DatabaseError("statement", {}, Exception(private)),
            ):
                error = self.assert_error(
                    "SYMBOL_PERSISTENCE_FAILED",
                    lambda: replace_detected_symbols(
                        self.session,
                        self.floor_plan_id,
                        self.job_id,
                        classified_result((prediction(0.2),)),
                    ),
                )
                self.assertNotIn(private, str(error))
            self.assertEqual(
                retrieve_detected_symbols(self.session, self.floor_plan_id, self.job_id),
                original,
            )

        for target in ("add_all", "flush", "commit"):
            with self.subTest(stage=target), patch.object(
                self.session,
                target,
                side_effect=SQLAlchemyError(private),
            ):
                self.assert_error(
                    "SYMBOL_PERSISTENCE_FAILED",
                    lambda: replace_detected_symbols(
                        self.session,
                        self.floor_plan_id,
                        self.job_id,
                        classified_result((prediction(0.2),)),
                    ),
                )
            self.assertEqual(
                retrieve_detected_symbols(self.session, self.floor_plan_id, self.job_id),
                original,
            )

    def test_retrieval_failure_is_sanitized_and_rolls_back(self):
        private = r"SELECT secret FROM C:\private"
        with patch(
            "app.services.symbol_persistence.list_detected_symbols",
            side_effect=SQLAlchemyError(private),
        ):
            error = self.assert_error(
                "SYMBOL_RETRIEVAL_FAILED",
                lambda: retrieve_detected_symbols(
                    self.session,
                    self.floor_plan_id,
                    self.job_id,
                ),
            )
        self.assertNotIn(private, str(error))

    def test_success_leaves_job_and_floor_plan_state_unchanged(self):
        job = self.session.get(ProcessingJob, self.job_id)
        floor_plan = self.session.get(FloorPlan, self.floor_plan_id)
        before = (
            job.status,
            job.progress,
            job.error_message,
            floor_plan.processing_status,
        )
        replace_detected_symbols(
            self.session,
            self.floor_plan_id,
            self.job_id,
            classified_result((prediction(0.8),)),
        )
        self.session.refresh(job)
        self.session.refresh(floor_plan)
        self.assertEqual(
            (job.status, job.progress, job.error_message, floor_plan.processing_status),
            before,
        )

    def test_current_openapi_operation_count_includes_j1(self):
        from app.main import app

        operations = sum(
            1
            for methods in app.openapi()["paths"].values()
            for method in methods
            if method.casefold()
            in {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
        )
        self.assertEqual(operations, 16)


if __name__ == "__main__":
    unittest.main()
