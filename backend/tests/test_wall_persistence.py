import hashlib
import json
import math
import unittest
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import cv2
from sqlalchemy import (
    BigInteger,
    DateTime,
    Integer,
    Numeric,
    String,
    delete,
    func,
    inspect,
    select,
)
from sqlalchemy.exc import DatabaseError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai.wall_detection.detector import (
    CoordinateSpace,
    PixelPoint,
    WallDetectionResult,
    WallLineCandidate,
)
from app.core.database import get_engine
from app.geometry.walls import normalize_wall_coordinates
from app.models import (
    Base,
    FloorPlan,
    ProcessingJob,
    Project,
    ProjectFloor,
    Role,
    User,
    Wall,
)
from app.models.wall import WALL_STATUSES
from app.repositories.wall_repository import list_walls, lock_floor_plan
from app.services.processing_job_service import FLOOR_PLAN_ANALYSIS_JOB_TYPE
from app.services.wall_persistence import (
    ERROR_MESSAGES,
    PersistedWallRecord,
    WallPersistenceError,
    replace_detected_wall_geometry,
    retrieve_persisted_walls,
)


def wall_candidate(
    candidate_id: int,
    start: tuple[int, int],
    end: tuple[int, int],
    angle: float,
) -> WallLineCandidate:
    return WallLineCandidate(
        candidate_id=candidate_id,
        start=PixelPoint(*start),
        end=PixelPoint(*end),
        length_pixels=round(
            math.hypot(end[0] - start[0], end[1] - start[1]),
            6,
        ),
        angle_degrees=angle,
    )


def geometry(candidate_count: int = 2, *, truncated: bool = False):
    candidates = (
        wall_candidate(1, (10, 20), (110, 20), 0.0),
        wall_candidate(2, (20, 40), (20, 140), 90.0),
    )[:candidate_count]
    detection = WallDetectionResult(
        coordinate_space=CoordinateSpace(width=640, height=480),
        algorithm="probabilistic_hough",
        truncated=truncated,
        candidates=candidates,
    )
    return normalize_wall_coordinates(detection, 100)


def file_hashes(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class WallPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_engine()
        cls.inspector = inspect(cls.engine)
        if "walls" not in cls.inspector.get_table_names():
            raise RuntimeError("Run the development schema initializer before H3 tests.")

        cls.storage_root = Path(__file__).resolve().parents[2] / "storage"
        cls.storage_hashes = file_hashes(cls.storage_root)
        with Session(cls.engine) as session:
            cls.baseline_counts = {
                model.__tablename__: session.scalar(select(func.count()).select_from(model))
                for model in (
                    User,
                    Project,
                    ProjectFloor,
                    FloorPlan,
                    ProcessingJob,
                    Wall,
                )
            }
            designer_role = session.scalar(select(Role).where(Role.name == "DESIGNER"))
            if designer_role is None:
                raise RuntimeError("The DESIGNER seed role is required.")
            cls.marker = uuid4().hex
            user = User(
                oauth_provider="h3-test",
                oauth_subject=f"designer-{cls.marker}",
                email=f"designer-{cls.marker}@example.test",
                display_name="H3 Designer",
                role_id=designer_role.id,
            )
            project = Project(owner=user, name=f"H3 Project {cls.marker}")
            project_floor = ProjectFloor(project=project, name="H3 Floor")
            floor_plan = FloorPlan(
                project_floor=project_floor,
                original_filename="h3-original.png",
                storage_path="originals/h3-original.png",
                mime_type="image/png",
                file_size=100,
                processing_status="uploaded",
            )
            other_floor_plan = FloorPlan(
                project_floor=project_floor,
                original_filename="h3-other.png",
                storage_path="originals/h3-other.png",
                mime_type="image/png",
                file_size=100,
                processing_status="uploaded",
            )
            session.add_all((floor_plan, other_floor_plan))
            session.commit()
            cls.user_id = user.id
            cls.project_id = project.id
            cls.project_floor_id = project_floor.id
            cls.floor_plan_id = floor_plan.id
            cls.other_floor_plan_id = other_floor_plan.id

    @classmethod
    def tearDownClass(cls) -> None:
        with Session(cls.engine) as session:
            session.execute(
                delete(Wall).where(
                    Wall.floor_plan_id.in_((cls.floor_plan_id, cls.other_floor_plan_id))
                )
            )
            session.execute(
                delete(ProcessingJob).where(
                    ProcessingJob.floor_plan_id.in_(
                        (cls.floor_plan_id, cls.other_floor_plan_id)
                    )
                )
            )
            session.execute(
                delete(FloorPlan).where(
                    FloorPlan.id.in_((cls.floor_plan_id, cls.other_floor_plan_id))
                )
            )
            session.execute(
                delete(ProjectFloor).where(ProjectFloor.id == cls.project_floor_id)
            )
            session.execute(delete(Project).where(Project.id == cls.project_id))
            session.execute(delete(User).where(User.id == cls.user_id))
            session.commit()

        with Session(cls.engine) as session:
            current_counts = {
                model.__tablename__: session.scalar(select(func.count()).select_from(model))
                for model in (
                    User,
                    Project,
                    ProjectFloor,
                    FloorPlan,
                    ProcessingJob,
                    Wall,
                )
            }
            leaked_users = session.scalar(
                select(func.count())
                .select_from(User)
                .where(User.oauth_provider == "h3-test")
            )
        if current_counts != cls.baseline_counts or leaked_users:
            raise AssertionError("H3 database test records were not cleaned up.")
        if file_hashes(cls.storage_root) != cls.storage_hashes:
            raise AssertionError("H3 changed an original or derived storage file.")

    def setUp(self) -> None:
        self.database_session = Session(self.engine, expire_on_commit=False)
        self.database_session.execute(
            delete(Wall).where(
                Wall.floor_plan_id.in_((self.floor_plan_id, self.other_floor_plan_id))
            )
        )
        self.database_session.execute(
            delete(ProcessingJob).where(
                ProcessingJob.floor_plan_id.in_(
                    (self.floor_plan_id, self.other_floor_plan_id)
                )
            )
        )
        jobs = (
            ProcessingJob(
                floor_plan_id=self.floor_plan_id,
                job_type=FLOOR_PLAN_ANALYSIS_JOB_TYPE,
                status="processing",
                progress=25,
            ),
            ProcessingJob(
                floor_plan_id=self.other_floor_plan_id,
                job_type=FLOOR_PLAN_ANALYSIS_JOB_TYPE,
                status="processing",
                progress=25,
            ),
            ProcessingJob(
                floor_plan_id=self.floor_plan_id,
                job_type="other_job",
                status="processing",
            ),
            ProcessingJob(
                floor_plan_id=self.floor_plan_id,
                job_type=FLOOR_PLAN_ANALYSIS_JOB_TYPE,
                status="queued",
            ),
        )
        self.database_session.add_all(jobs)
        self.database_session.commit()
        (
            self.job,
            self.other_floor_job,
            self.wrong_type_job,
            self.queued_job,
        ) = jobs

    def tearDown(self) -> None:
        self.database_session.rollback()
        self.database_session.execute(
            delete(Wall).where(
                Wall.floor_plan_id.in_((self.floor_plan_id, self.other_floor_plan_id))
            )
        )
        self.database_session.execute(
            delete(ProcessingJob).where(
                ProcessingJob.floor_plan_id.in_(
                    (self.floor_plan_id, self.other_floor_plan_id)
                )
            )
        )
        self.database_session.commit()
        self.database_session.close()

    def assert_error(self, code: str, operation) -> WallPersistenceError:
        with self.assertRaises(WallPersistenceError) as caught:
            operation()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(str(caught.exception), ERROR_MESSAGES[code])
        return caught.exception

    def insert_wall(self, *, status: str = "detected", candidate_id: int = 1) -> Wall:
        wall = Wall(
            floor_plan_id=self.floor_plan_id,
            processing_job_id=self.job.id,
            candidate_id=candidate_id,
            status=status,
            pixels_per_meter=Decimal("100.000000000"),
            raw_start_x=10,
            raw_start_y=20,
            raw_end_x=110,
            raw_end_y=20,
            raw_length_pixels=Decimal("100.000000"),
            canonical_start_x=Decimal("0.100000000"),
            canonical_start_y=Decimal("0.200000000"),
            canonical_end_x=Decimal("1.100000000"),
            canonical_end_y=Decimal("0.200000000"),
            canonical_length_meters=Decimal("1.000000000"),
            angle_degrees=Decimal("0.000000"),
        )
        self.database_session.add(wall)
        self.database_session.flush()
        return wall

    def test_model_registered_with_exact_columns_types_and_defaults(self) -> None:
        self.assertIs(Wall.__table__, Base.metadata.tables["walls"])
        table = Wall.__table__
        self.assertEqual(
            tuple(table.columns),
            tuple(table.c[name] for name in (
                "id", "floor_plan_id", "processing_job_id", "candidate_id", "status",
                "pixels_per_meter", "raw_start_x", "raw_start_y", "raw_end_x", "raw_end_y",
                "raw_length_pixels", "canonical_start_x", "canonical_start_y",
                "canonical_end_x", "canonical_end_y", "canonical_length_meters",
                "angle_degrees", "created_at", "updated_at",
            )),
        )
        expected_types = {
            "id": BigInteger, "floor_plan_id": BigInteger,
            "processing_job_id": BigInteger, "candidate_id": Integer,
            "status": String, "pixels_per_meter": Numeric,
            "raw_start_x": Integer, "raw_start_y": Integer,
            "raw_end_x": Integer, "raw_end_y": Integer,
            "raw_length_pixels": Numeric, "canonical_start_x": Numeric,
            "canonical_start_y": Numeric, "canonical_end_x": Numeric,
            "canonical_end_y": Numeric, "canonical_length_meters": Numeric,
            "angle_degrees": Numeric, "created_at": DateTime, "updated_at": DateTime,
        }
        for name, expected_type in expected_types.items():
            with self.subTest(column=name):
                self.assertIsInstance(table.c[name].type, expected_type)
                self.assertFalse(table.c[name].nullable)
        self.assertEqual((table.c.pixels_per_meter.type.precision, table.c.pixels_per_meter.type.scale), (20, 9))
        self.assertEqual((table.c.raw_length_pixels.type.precision, table.c.raw_length_pixels.type.scale), (20, 6))
        self.assertEqual((table.c.angle_degrees.type.precision, table.c.angle_degrees.type.scale), (9, 6))
        self.assertIsNotNone(table.c.status.server_default)
        self.assertIsNotNone(table.c.created_at.server_default)
        self.assertIsNotNone(table.c.updated_at.server_default)
        self.assertIsNotNone(table.c.updated_at.onupdate)

    def test_live_schema_has_expected_application_tables(self) -> None:
        self.assertEqual(
            set(self.inspector.get_table_names()),
            {
                "roles",
                "users",
                "projects",
                "project_floors",
                "floor_plans",
                "processing_jobs",
                "walls",
                "detected_symbols",
                "detection_reviews",
                "symbol_legends",
            },
        )

    def test_named_constraints_foreign_keys_indexes_and_uniqueness(self) -> None:
        expected_checks = {
            "ck_walls_status", "ck_walls_candidate_id", "ck_walls_scale",
            "ck_walls_raw_coordinates", "ck_walls_canonical_coordinates",
            "ck_walls_lengths", "ck_walls_angle",
        }
        self.assertTrue(expected_checks.issubset({item["name"] for item in self.inspector.get_check_constraints("walls")}))
        self.assertIn("uq_walls_floor_plan_candidate", {item["name"] for item in self.inspector.get_unique_constraints("walls")})
        foreign_keys = {
            (tuple(item["constrained_columns"]), item["referred_table"], tuple(item["referred_columns"]))
            for item in self.inspector.get_foreign_keys("walls")
        }
        self.assertEqual(
            foreign_keys,
            {(('floor_plan_id',), 'floor_plans', ('id',)), (('processing_job_id',), 'processing_jobs', ('id',))},
        )
        indexes = {tuple(item["column_names"]) for item in self.inspector.get_indexes("walls")}
        self.assertIn(("floor_plan_id",), indexes)
        self.assertIn(("processing_job_id",), indexes)

    def test_bidirectional_relationships_and_floor_chain(self) -> None:
        wall = self.insert_wall()
        self.assertIs(wall.floor_plan, self.database_session.get(FloorPlan, self.floor_plan_id))
        self.assertIs(wall.processing_job, self.job)
        self.assertIn(wall, wall.floor_plan.walls)
        self.assertIn(wall, self.job.walls)
        self.assertEqual(wall.floor_plan.project_floor.id, self.project_floor_id)

    def test_detected_and_verified_are_accepted_but_unknown_status_is_rejected(self) -> None:
        for candidate_id, status in enumerate(WALL_STATUSES, start=1):
            wall = self.insert_wall(status=status, candidate_id=candidate_id)
            self.assertEqual(wall.status, status)
        self.database_session.commit()
        self.database_session.add(
            Wall(
                floor_plan_id=self.other_floor_plan_id,
                processing_job_id=self.other_floor_job.id,
                candidate_id=1,
                status="unsupported",
                pixels_per_meter=100,
                raw_start_x=0, raw_start_y=0, raw_end_x=1, raw_end_y=1,
                raw_length_pixels=1, canonical_start_x=0, canonical_start_y=0,
                canonical_end_x=1, canonical_end_y=1, canonical_length_meters=1,
                angle_degrees=0,
            )
        )
        with self.assertRaises(DatabaseError):
            self.database_session.flush()
        self.database_session.rollback()

    def test_nonempty_geometry_persists_exact_raw_metric_and_provenance_values(self) -> None:
        records = replace_detected_wall_geometry(
            self.database_session, self.floor_plan_id, self.job.id, geometry()
        )
        self.assertEqual(tuple(record.candidate_id for record in records), (1, 2))
        first = records[0]
        self.assertEqual(first.status, "detected")
        self.assertEqual(first.floor_plan_id, self.floor_plan_id)
        self.assertEqual(first.processing_job_id, self.job.id)
        self.assertEqual(first.pixels_per_meter, Decimal("100.000000000"))
        self.assertEqual((first.raw_start_x, first.raw_start_y, first.raw_end_x, first.raw_end_y), (10, 20, 110, 20))
        self.assertEqual(first.raw_length_pixels, Decimal("100.000000"))
        self.assertEqual((first.canonical_start_x, first.canonical_start_y), (Decimal("0.100000000"), Decimal("0.200000000")))
        self.assertEqual((first.canonical_end_x, first.canonical_end_y), (Decimal("1.100000000"), Decimal("0.200000000")))
        self.assertEqual(first.canonical_length_meters, Decimal("1.000000000"))
        self.assertEqual(first.angle_degrees, Decimal("0.000000"))
        self.assertIsNotNone(first.created_at)
        self.assertIsNotNone(first.updated_at)

    def test_retrieval_is_ordered_immutable_exact_and_json_serializable(self) -> None:
        replace_detected_wall_geometry(self.database_session, self.floor_plan_id, self.job.id, geometry())
        records = retrieve_persisted_walls(self.database_session, self.floor_plan_id)
        self.assertIs(type(records), tuple)
        self.assertTrue(all(isinstance(record, PersistedWallRecord) for record in records))
        self.assertEqual(tuple(record.candidate_id for record in records), (1, 2))
        self.assertIs(type(records[0].pixels_per_meter), Decimal)
        with self.assertRaises(FrozenInstanceError):
            records[0].status = "verified"
        self.assertEqual(json.loads(json.dumps(records[0].to_dict()))["status"], "detected")

    def test_retrieval_executes_no_opencv_or_h2_conversion_and_loads_no_relationships(self) -> None:
        replace_detected_wall_geometry(self.database_session, self.floor_plan_id, self.job.id, geometry(1))
        with patch.object(cv2, "HoughLinesP", side_effect=AssertionError("OpenCV executed")), patch(
            "app.geometry.walls.normalize_wall_coordinates",
            side_effect=AssertionError("H2 conversion executed"),
        ):
            records = retrieve_persisted_walls(self.database_session, self.floor_plan_id)
        self.assertEqual(len(records), 1)
        orm_wall = list_walls(self.database_session, floor_plan_id=self.floor_plan_id)[0]
        self.assertTrue({"floor_plan", "processing_job"}.issubset(inspect(orm_wall).unloaded))

    def test_empty_floor_plan_retrieval_and_empty_replacement_return_empty_tuples(self) -> None:
        self.assertEqual(retrieve_persisted_walls(self.database_session, self.floor_plan_id), ())
        replace_detected_wall_geometry(self.database_session, self.floor_plan_id, self.job.id, geometry())
        empty = geometry(0)
        self.assertEqual(replace_detected_wall_geometry(self.database_session, self.floor_plan_id, self.job.id, empty), ())
        self.assertEqual(retrieve_persisted_walls(self.database_session, self.floor_plan_id), ())

    def test_same_result_replaces_without_accumulating_duplicates(self) -> None:
        replace_detected_wall_geometry(self.database_session, self.floor_plan_id, self.job.id, geometry())
        replace_detected_wall_geometry(self.database_session, self.floor_plan_id, self.job.id, geometry())
        self.assertEqual(len(retrieve_persisted_walls(self.database_session, self.floor_plan_id)), 2)

    def test_new_job_and_fewer_candidates_replace_prior_set_and_remove_stale_rows(self) -> None:
        replace_detected_wall_geometry(self.database_session, self.floor_plan_id, self.job.id, geometry())
        newer = ProcessingJob(
            floor_plan_id=self.floor_plan_id,
            job_type=FLOOR_PLAN_ANALYSIS_JOB_TYPE,
            status="processing",
        )
        self.database_session.add(newer)
        self.database_session.commit()
        records = replace_detected_wall_geometry(self.database_session, self.floor_plan_id, newer.id, geometry(1))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].processing_job_id, newer.id)

    def test_verified_walls_block_machine_replacement(self) -> None:
        verified = self.insert_wall(status="verified")
        self.database_session.commit()
        self.assert_error(
            "VERIFIED_WALLS_PROTECTED",
            lambda: replace_detected_wall_geometry(
                self.database_session, self.floor_plan_id, self.job.id, geometry()
            ),
        )
        self.assertEqual(self.database_session.get(Wall, verified.id).status, "verified")

    def test_floor_plan_lock_serializes_replacement(self) -> None:
        with patch("app.services.wall_persistence.lock_floor_plan", wraps=lock_floor_plan) as locked:
            replace_detected_wall_geometry(self.database_session, self.floor_plan_id, self.job.id, geometry(1))
        locked.assert_called_once_with(self.database_session, floor_plan_id=self.floor_plan_id)
        statement = select(FloorPlan).where(FloorPlan.id == self.floor_plan_id).with_for_update()
        self.assertIsNotNone(statement._for_update_arg)

    def test_unique_constraint_prevents_duplicate_candidates(self) -> None:
        self.insert_wall(candidate_id=1)
        with self.assertRaises(DatabaseError):
            self.insert_wall(candidate_id=1)
        self.database_session.rollback()

    def test_insert_failure_rolls_back_delete_and_preserves_previous_set(self) -> None:
        replace_detected_wall_geometry(self.database_session, self.floor_plan_id, self.job.id, geometry())
        before = retrieve_persisted_walls(self.database_session, self.floor_plan_id)
        with patch("app.services.wall_persistence.add_detected_walls", side_effect=SQLAlchemyError("private SQL")):
            error = self.assert_error(
                "WALL_PERSISTENCE_FAILED",
                lambda: replace_detected_wall_geometry(
                    self.database_session, self.floor_plan_id, self.job.id, geometry(1)
                ),
            )
        after = retrieve_persisted_walls(self.database_session, self.floor_plan_id)
        self.assertEqual(tuple(item.candidate_id for item in after), tuple(item.candidate_id for item in before))
        self.assertNotIn("SQL", str(error))

    def test_database_read_delete_flush_and_commit_failures_are_sanitized(self) -> None:
        failure_points = (
            ("lock_floor_plan", "read failed"),
            ("delete_detected_walls", "DELETE walls secret"),
            ("add_detected_walls", "flush values secret"),
        )
        for function_name, detail in failure_points:
            with self.subTest(function=function_name), patch(
                f"app.services.wall_persistence.{function_name}",
                side_effect=SQLAlchemyError(detail),
            ):
                error = self.assert_error(
                    "WALL_PERSISTENCE_FAILED",
                    lambda: replace_detected_wall_geometry(
                        self.database_session, self.floor_plan_id, self.job.id, geometry(1)
                    ),
                )
                self.assertEqual(str(error), ERROR_MESSAGES["WALL_PERSISTENCE_FAILED"])
        with patch.object(self.database_session, "commit", side_effect=SQLAlchemyError("credentials")):
            error = self.assert_error(
                "WALL_PERSISTENCE_FAILED",
                lambda: replace_detected_wall_geometry(
                    self.database_session, self.floor_plan_id, self.job.id, geometry(1)
                ),
            )
        self.assertNotIn("credentials", str(error))

    def test_retrieval_database_failure_is_sanitized(self) -> None:
        with patch("app.services.wall_persistence.list_walls", side_effect=SQLAlchemyError("private path")):
            error = self.assert_error(
                "WALL_RETRIEVAL_FAILED",
                lambda: retrieve_persisted_walls(self.database_session, self.floor_plan_id),
            )
        self.assertNotIn("private", str(error))

    def test_identifier_floor_plan_and_job_validation_errors(self) -> None:
        cases = (
            ("INVALID_FLOOR_PLAN_ID", lambda: replace_detected_wall_geometry(self.database_session, 0, self.job.id, geometry())),
            ("INVALID_PROCESSING_JOB_ID", lambda: replace_detected_wall_geometry(self.database_session, self.floor_plan_id, False, geometry())),
            ("FLOOR_PLAN_NOT_FOUND", lambda: replace_detected_wall_geometry(self.database_session, 9223372036854775807, self.job.id, geometry())),
            ("PROCESSING_JOB_NOT_FOUND", lambda: replace_detected_wall_geometry(self.database_session, self.floor_plan_id, 9223372036854775807, geometry())),
            ("PROCESSING_JOB_FLOOR_PLAN_MISMATCH", lambda: replace_detected_wall_geometry(self.database_session, self.floor_plan_id, self.other_floor_job.id, geometry())),
            ("INVALID_PROCESSING_JOB_TYPE", lambda: replace_detected_wall_geometry(self.database_session, self.floor_plan_id, self.wrong_type_job.id, geometry())),
            ("INVALID_PROCESSING_JOB_STATUS", lambda: replace_detected_wall_geometry(self.database_session, self.floor_plan_id, self.queued_job.id, geometry())),
        )
        for code, operation in cases:
            with self.subTest(code=code):
                self.assert_error(code, operation)

    def test_truncated_malformed_nonsequential_and_nonfinite_geometry_are_rejected(self) -> None:
        valid = geometry()
        malformed_id = replace(valid, walls=(replace(valid.walls[0], candidate_id=2),))
        inconsistent = replace(
            valid,
            walls=(
                replace(
                    valid.walls[0],
                    canonical=replace(
                        valid.walls[0].canonical,
                        start=replace(valid.walls[0].canonical.start, x=9.0),
                    ),
                ),
            ),
        )
        unsafe = replace(
            valid,
            walls=(replace(valid.walls[0], canonical=replace(valid.walls[0].canonical, length_meters=float("nan"))),),
        )
        cases = (
            ("TRUNCATED_GEOMETRY", geometry(truncated=True)),
            ("INVALID_GEOMETRY", {}),
            ("INVALID_GEOMETRY", malformed_id),
            ("INVALID_GEOMETRY", inconsistent),
            ("INVALID_GEOMETRY", unsafe),
        )
        for code, value in cases:
            with self.subTest(code=code):
                self.assert_error(
                    code,
                    lambda item=value: replace_detected_wall_geometry(
                        self.database_session, self.floor_plan_id, self.job.id, item
                    ),
                )

    def test_persistence_leaves_job_and_floor_plan_state_unchanged(self) -> None:
        replace_detected_wall_geometry(self.database_session, self.floor_plan_id, self.job.id, geometry())
        self.database_session.refresh(self.job)
        floor_plan = self.database_session.get(FloorPlan, self.floor_plan_id)
        self.assertEqual((self.job.status, self.job.progress), ("processing", 25))
        self.assertEqual(floor_plan.processing_status, "uploaded")

    def test_current_openapi_operation_count_includes_j1(self) -> None:
        from app.main import app

        operations = sum(
            1
            for methods in app.openapi()["paths"].values()
            for method in methods
            if method.casefold() in {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
        )
        self.assertEqual(operations, 17)


if __name__ == "__main__":
    unittest.main()
