import copy
import json
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Integer,
    delete,
    func,
    inspect,
    select,
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.geometry import canonical_geometry_from_dict
from app.models import (
    Base,
    FloorPlan,
    LayoutVersion,
    Project,
    ProjectFloor,
    Role,
    User,
)
from app.services.layout_version_service import (
    ERROR_MESSAGE,
    MAXIMUM_VERSION_NUMBER,
    LayoutVersionServiceError,
    list_layout_version_history,
    mark_layout_version_current,
    retrieve_current_layout_version,
    retrieve_layout_version,
    save_layout_snapshot,
)


FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "canonical_geometry_v1.json"


class LayoutVersionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_engine()
        Base.metadata.create_all(bind=cls.engine, tables=[LayoutVersion.__table__])
        cls.marker = f"k2-{uuid.uuid4().hex}"
        cls.session = Session(cls.engine, autoflush=False, expire_on_commit=False)
        cls.baseline = cls._counts()
        role = cls.session.scalar(select(Role).where(Role.name == "DESIGNER"))
        if role is None:
            raise unittest.SkipTest("The seeded DESIGNER role is required.")
        cls.user = User(
            oauth_provider=cls.marker,
            oauth_subject="designer",
            role=role,
        )
        cls.project = Project(owner=cls.user, name=f"{cls.marker}-project")
        cls.floor = ProjectFloor(
            project=cls.project,
            name="Lower Ground Floor",
            sort_order=0,
        )
        cls.other_floor = ProjectFloor(
            project=cls.project,
            name="Upper Floor",
            sort_order=1,
        )
        cls.floor_plan = FloorPlan(
            project_floor=cls.floor,
            original_filename="plan.png",
            storage_path="originals/plan.png",
            mime_type="image/png",
            file_size=100,
            processing_status="processed",
        )
        cls.newer_floor_plan = FloorPlan(
            project_floor=cls.floor,
            original_filename="plan-v2.png",
            storage_path="originals/plan-v2.png",
            mime_type="image/png",
            file_size=101,
            processing_status="processed",
        )
        cls.other_floor_plan = FloorPlan(
            project_floor=cls.other_floor,
            original_filename="upper.png",
            storage_path="originals/upper.png",
            mime_type="image/png",
            file_size=102,
            processing_status="processed",
        )
        cls.session.add_all(
            (cls.floor_plan, cls.newer_floor_plan, cls.other_floor_plan)
        )
        cls.session.commit()
        cls.project_id = cls.project.id
        cls.floor_id = cls.floor.id
        cls.other_floor_id = cls.other_floor.id
        cls.floor_plan_id = cls.floor_plan.id
        cls.newer_floor_plan_id = cls.newer_floor_plan.id
        cls.other_floor_plan_id = cls.other_floor_plan.id

    @classmethod
    def _counts(cls) -> dict[str, int]:
        with Session(cls.engine) as session:
            return {
                table.name: session.scalar(select(func.count()).select_from(table))
                for table in Base.metadata.sorted_tables
            }

    @classmethod
    def tearDownClass(cls) -> None:
        cls.session.rollback()
        cls.session.execute(
            delete(LayoutVersion).where(LayoutVersion.project_id == cls.project_id)
        )
        cls.session.execute(
            delete(FloorPlan).where(
                FloorPlan.id.in_(
                    (
                        cls.floor_plan_id,
                        cls.newer_floor_plan_id,
                        cls.other_floor_plan_id,
                    )
                )
            )
        )
        cls.session.execute(
            delete(ProjectFloor).where(
                ProjectFloor.id.in_((cls.floor_id, cls.other_floor_id))
            )
        )
        cls.session.execute(delete(Project).where(Project.id == cls.project_id))
        cls.session.execute(delete(User).where(User.oauth_provider == cls.marker))
        cls.session.commit()
        cls.session.close()
        if cls._counts() != cls.baseline:
            raise AssertionError("K2 database row counts were not restored.")

    def setUp(self) -> None:
        self.session.rollback()
        self.session.execute(
            delete(LayoutVersion).where(LayoutVersion.project_id == self.project_id)
        )
        self.session.commit()

    def document(
        self,
        *,
        floor_id=None,
        floor_plan_id=None,
        floor_name=None,
        sort_order=None,
        elevation=-1.5,
        verified=False,
        dimensions=False,
        empty=False,
        project_id=None,
    ):
        payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        payload["project_id"] = project_id or self.project_id
        payload["floor"]["project_floor_id"] = floor_id or self.floor_id
        payload["floor"]["name"] = floor_name or self.floor.name
        payload["floor"]["sort_order"] = (
            self.floor.sort_order if sort_order is None else sort_order
        )
        payload["floor"]["elevation_meters"] = elevation
        payload["floor_plan_id"] = floor_plan_id or self.floor_plan_id
        for point in payload["routes"][0]["points"]:
            point["project_floor_id"] = payload["floor"]["project_floor_id"]
        if verified:
            payload["walls"][0]["status"] = "verified"
        if dimensions:
            payload["walls"][0]["thickness_meters"] = 0.15
            payload["walls"][0]["height_meters"] = 3.0
        if empty:
            for key in ("walls", "rooms", "symbols", "routes"):
                payload[key] = []
        return canonical_geometry_from_dict(payload)

    def test_model_contract_constraints_indexes_relationships_and_live_schema(self):
        table = LayoutVersion.__table__
        self.assertIs(table, Base.metadata.tables["layout_versions"])
        self.assertEqual(
            tuple(table.columns.keys()),
            (
                "id",
                "project_id",
                "project_floor_id",
                "floor_plan_id",
                "version_number",
                "schema_version",
                "geometry_document",
                "is_current",
                "created_at",
            ),
        )
        expected_types = {
            "id": BigInteger,
            "project_id": BigInteger,
            "project_floor_id": BigInteger,
            "floor_plan_id": BigInteger,
            "version_number": Integer,
            "schema_version": Integer,
            "geometry_document": JSON,
            "is_current": Boolean,
            "created_at": DateTime,
        }
        for name, expected_type in expected_types.items():
            with self.subTest(column=name):
                self.assertIsInstance(table.c[name].type, expected_type)
        self.assertTrue(table.c.is_current.nullable)
        for name in (
            "project_id",
            "project_floor_id",
            "floor_plan_id",
            "version_number",
            "schema_version",
            "geometry_document",
            "created_at",
        ):
            self.assertFalse(table.c[name].nullable)
        self.assertEqual(
            {constraint.name for constraint in table.constraints if constraint.name},
            {
                "uq_layout_versions_floor_version",
                "uq_layout_versions_floor_current",
                "ck_layout_versions_version_number",
                "ck_layout_versions_schema_version",
                "ck_layout_versions_current_marker",
            },
        )
        self.assertEqual(
            {foreign_key.target_fullname for foreign_key in table.foreign_keys},
            {"projects.id", "project_floors.id", "floor_plans.id"},
        )
        self.assertTrue(
            all(foreign_key.ondelete is None for foreign_key in table.foreign_keys)
        )
        self.assertEqual(
            {index.name for index in table.indexes},
            {"ix_layout_versions_project_floor_id"},
        )
        self.assertEqual(len(Base.metadata.tables), 15)
        self.assertEqual(
            set(inspect(self.engine).get_table_names()), set(Base.metadata.tables)
        )
        inspector = inspect(self.engine)
        self.assertEqual(
            {
                constraint["name"]
                for constraint in inspector.get_unique_constraints("layout_versions")
            },
            {
                "uq_layout_versions_floor_version",
                "uq_layout_versions_floor_current",
            },
        )
        self.assertEqual(
            {
                constraint["name"]
                for constraint in inspector.get_check_constraints("layout_versions")
            },
            {
                "ck_layout_versions_version_number",
                "ck_layout_versions_schema_version",
                "ck_layout_versions_current_marker",
            },
        )
        self.assertIn(
            "ix_layout_versions_project_floor_id",
            {index["name"] for index in inspector.get_indexes("layout_versions")},
        )
        self.assertEqual(
            {
                foreign_key["referred_table"]
                for foreign_key in inspector.get_foreign_keys("layout_versions")
            },
            {"projects", "project_floors", "floor_plans"},
        )
        self.assertEqual(Project.layout_versions.property.back_populates, "project")
        self.assertEqual(
            ProjectFloor.layout_versions.property.back_populates, "project_floor"
        )
        self.assertEqual(
            FloorPlan.layout_versions.property.back_populates, "floor_plan"
        )
        for relationship in (
            Project.layout_versions,
            ProjectFloor.layout_versions,
            FloorPlan.layout_versions,
        ):
            self.assertFalse(relationship.property.cascade.delete)

    def test_first_snapshot_round_trips_complete_fixture_and_is_immutable(self):
        document = self.document(verified=True)
        original = copy.deepcopy(document.to_dict())
        record = save_layout_snapshot(self.session, document)
        self.assertEqual(record.version_number, 1)
        self.assertTrue(record.is_current)
        self.assertEqual(record.schema_version, 1)
        self.assertEqual(record.project_id, self.project_id)
        self.assertEqual(record.project_floor_id, self.floor_id)
        self.assertEqual(record.floor_plan_id, self.floor_plan_id)
        self.assertIsNotNone(record.created_at)
        self.assertEqual(record.geometry.to_dict(), original)
        self.assertEqual(document.to_dict(), original)
        self.assertEqual(record.geometry.walls[0].status, "verified")
        self.assertEqual(record.geometry.symbols[0].class_name, "Power outlet")
        self.assertEqual(record.geometry.symbols[1].status, "manually_added")
        self.assertEqual(record.geometry.rooms[0].name, "Living Room")
        self.assertEqual(record.geometry.routes[0].points[0].elevation_meters, -1.5)
        with self.assertRaises(FrozenInstanceError):
            record.geometry.project_id = 1

    def test_negative_zero_positive_elevation_and_wall_dimensions_round_trip(self):
        for elevation in (-2.25, 0, 4.5):
            with self.subTest(elevation=elevation):
                self.setUp()
                document = self.document(
                    elevation=elevation,
                    verified=True,
                    dimensions=True,
                )
                record = save_layout_snapshot(self.session, document)
                wall = record.geometry.walls[0]
                self.assertEqual(record.geometry.floor.elevation_meters, elevation)
                self.assertEqual(wall.thickness_meters, 0.15)
                self.assertEqual(wall.height_meters, 3.0)

    def test_nullable_wall_dimensions_and_empty_collections_round_trip(self):
        full = save_layout_snapshot(self.session, self.document())
        self.assertIsNone(full.geometry.walls[0].thickness_meters)
        self.assertIsNone(full.geometry.walls[0].height_meters)
        empty = save_layout_snapshot(
            self.session,
            self.document(floor_plan_id=self.newer_floor_plan_id, empty=True),
        )
        self.assertEqual(empty.version_number, 2)
        self.assertEqual(
            (empty.geometry.walls, empty.geometry.rooms, empty.geometry.symbols, empty.geometry.routes),
            ((), (), (), ()),
        )

    def test_three_saves_preserve_history_and_only_newest_is_current(self):
        documents = (
            self.document(elevation=-1.5),
            self.document(elevation=0),
            self.document(floor_plan_id=self.newer_floor_plan_id, elevation=2.5),
        )
        records = tuple(save_layout_snapshot(self.session, item) for item in documents)
        self.assertEqual([record.version_number for record in records], [1, 2, 3])
        with Session(self.engine, autoflush=False, expire_on_commit=False) as session:
            history = list_layout_version_history(
                session,
                project_id=self.project_id,
                project_floor_id=self.floor_id,
            )
        self.assertEqual([item.version_number for item in history], [1, 2, 3])
        self.assertEqual([item.is_current for item in history], [False, False, True])
        self.assertEqual(
            retrieve_layout_version(
                self.session,
                project_id=self.project_id,
                project_floor_id=self.floor_id,
                version_number=1,
            ).geometry.to_dict(),
            documents[0].to_dict(),
        )
        self.assertEqual(
            retrieve_current_layout_version(
                self.session,
                project_id=self.project_id,
                project_floor_id=self.floor_id,
            ).version_number,
            3,
        )

    def test_identical_save_creates_new_version_and_separate_floors_start_at_one(self):
        document = self.document()
        first = save_layout_snapshot(self.session, document)
        second = save_layout_snapshot(self.session, document)
        other = save_layout_snapshot(
            self.session,
            self.document(
                floor_id=self.other_floor_id,
                floor_plan_id=self.other_floor_plan_id,
                floor_name=self.other_floor.name,
                sort_order=self.other_floor.sort_order,
                elevation=3,
            ),
        )
        self.assertEqual((first.version_number, second.version_number), (1, 2))
        self.assertEqual(other.version_number, 1)
        self.assertTrue(other.is_current)

    def test_older_version_can_be_current_and_repeated_selection_is_idempotent(self):
        first = save_layout_snapshot(self.session, self.document(elevation=-1))
        save_layout_snapshot(self.session, self.document(elevation=1))
        before = retrieve_layout_version(
            self.session,
            project_id=self.project_id,
            project_floor_id=self.floor_id,
            version_number=1,
        )
        selected = mark_layout_version_current(
            self.session,
            project_id=self.project_id,
            project_floor_id=self.floor_id,
            version_number=1,
        )
        repeated = mark_layout_version_current(
            self.session,
            project_id=self.project_id,
            project_floor_id=self.floor_id,
            version_number=1,
        )
        history = list_layout_version_history(
            self.session,
            project_id=self.project_id,
            project_floor_id=self.floor_id,
        )
        self.assertEqual(len(history), 2)
        self.assertEqual([item.is_current for item in history], [True, False])
        self.assertEqual(selected.geometry.to_dict(), first.geometry.to_dict())
        self.assertEqual(repeated.id, selected.id)
        self.assertEqual(repeated.created_at, before.created_at)

    def test_database_constraint_prevents_two_current_versions_per_floor(self):
        first = save_layout_snapshot(self.session, self.document())
        duplicate = LayoutVersion(
            project_id=self.project_id,
            project_floor_id=self.floor_id,
            floor_plan_id=self.floor_plan_id,
            version_number=2,
            schema_version=1,
            geometry_document=first.geometry.to_dict(),
            is_current=True,
        )
        self.session.add(duplicate)
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()
        self.assertEqual(
            retrieve_current_layout_version(
                self.session,
                project_id=self.project_id,
                project_floor_id=self.floor_id,
            ).version_number,
            1,
        )

    def test_invalid_documents_and_context_mismatches_are_sanitized(self):
        invalid_values = (
            object(),
            replace(self.document(), schema_version=2),
            replace(self.document(), project_id=9_007_199_254_740_992),
            self.document(project_id=self.project_id + 999_999),
            self.document(floor_id=self.other_floor_id),
            self.document(floor_plan_id=self.other_floor_plan_id),
            self.document(floor_name="Stale floor name"),
            self.document(sort_order=99),
        )
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaisesRegex(LayoutVersionServiceError, f"^{ERROR_MESSAGE}$"):
                    save_layout_snapshot(self.session, value)
                self.assertEqual(
                    self.session.scalar(select(func.count()).select_from(LayoutVersion)),
                    0,
                )

    def test_unknown_cross_floor_and_unsafe_version_retrieval_are_rejected(self):
        save_layout_snapshot(self.session, self.document())
        requests = (
            (self.project_id, self.floor_id, 2),
            (self.project_id, self.other_floor_id, 1),
            (self.project_id, self.floor_id, 0),
            (self.project_id, self.floor_id, True),
            (9_007_199_254_740_992, self.floor_id, 1),
        )
        for project_id, floor_id, version_number in requests:
            with self.subTest(request=(project_id, floor_id, version_number)):
                with self.assertRaises(LayoutVersionServiceError):
                    retrieve_layout_version(
                        self.session,
                        project_id=project_id,
                        project_floor_id=floor_id,
                        version_number=version_number,
                    )

    def test_zero_history_is_valid_and_missing_current_is_sanitized(self):
        self.assertEqual(
            list_layout_version_history(
                self.session,
                project_id=self.project_id,
                project_floor_id=self.floor_id,
            ),
            (),
        )
        with self.assertRaisesRegex(LayoutVersionServiceError, f"^{ERROR_MESSAGE}$"):
            retrieve_current_layout_version(
                self.session,
                project_id=self.project_id,
                project_floor_id=self.floor_id,
            )

    def test_corrupt_stored_json_and_identity_mismatch_fail_reconstruction(self):
        record = save_layout_snapshot(self.session, self.document())
        for corrupted in ({"schema_version": 1}, {**record.geometry.to_dict(), "project_id": self.project_id + 1}):
            with self.subTest(corrupted=corrupted):
                self.session.execute(
                    LayoutVersion.__table__.update()
                    .where(LayoutVersion.id == record.id)
                    .values(geometry_document=corrupted)
                )
                self.session.commit()
                with self.assertRaisesRegex(LayoutVersionServiceError, f"^{ERROR_MESSAGE}$"):
                    retrieve_layout_version(
                        self.session,
                        project_id=self.project_id,
                        project_floor_id=self.floor_id,
                        version_number=1,
                    )
                self.session.execute(
                    LayoutVersion.__table__.update()
                    .where(LayoutVersion.id == record.id)
                    .values(geometry_document=record.geometry.to_dict())
                )
                self.session.commit()

    def test_version_overflow_does_not_change_history(self):
        document = self.document()
        row = LayoutVersion(
            project_id=self.project_id,
            project_floor_id=self.floor_id,
            floor_plan_id=self.floor_plan_id,
            version_number=MAXIMUM_VERSION_NUMBER,
            schema_version=1,
            geometry_document=document.to_dict(),
            is_current=True,
        )
        self.session.add(row)
        self.session.commit()
        with self.assertRaises(LayoutVersionServiceError):
            save_layout_snapshot(self.session, document)
        history = list_layout_version_history(
            self.session,
            project_id=self.project_id,
            project_floor_id=self.floor_id,
        )
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].version_number, MAXIMUM_VERSION_NUMBER)
        self.assertTrue(history[0].is_current)

    def test_save_failure_after_current_clear_rolls_back_everything(self):
        save_layout_snapshot(self.session, self.document())
        with patch(
            "app.services.layout_version_service.add_layout_version",
            side_effect=SQLAlchemyError("private SQL detail"),
        ):
            with self.assertRaisesRegex(LayoutVersionServiceError, f"^{ERROR_MESSAGE}$"):
                save_layout_snapshot(self.session, self.document(elevation=2))
        history = list_layout_version_history(
            self.session,
            project_id=self.project_id,
            project_floor_id=self.floor_id,
        )
        self.assertEqual([(item.version_number, item.is_current) for item in history], [(1, True)])

    def test_commit_retrieval_and_current_update_failures_are_sanitized_and_rollback(self):
        save_layout_snapshot(self.session, self.document())
        save_layout_snapshot(self.session, self.document(elevation=2))
        with patch.object(self.session, "commit", side_effect=SQLAlchemyError("secret")):
            with self.assertRaisesRegex(LayoutVersionServiceError, f"^{ERROR_MESSAGE}$"):
                mark_layout_version_current(
                    self.session,
                    project_id=self.project_id,
                    project_floor_id=self.floor_id,
                    version_number=1,
                )
        self.assertEqual(
            retrieve_current_layout_version(
                self.session,
                project_id=self.project_id,
                project_floor_id=self.floor_id,
            ).version_number,
            2,
        )
        with patch(
            "app.services.layout_version_service.find_layout_version",
            side_effect=SQLAlchemyError("secret"),
        ):
            with self.assertRaisesRegex(LayoutVersionServiceError, f"^{ERROR_MESSAGE}$"):
                retrieve_layout_version(
                    self.session,
                    project_id=self.project_id,
                    project_floor_id=self.floor_id,
                    version_number=1,
                )

    def test_concurrent_saves_serialize_and_use_distinct_version_numbers(self):
        document = self.document()

        def save_one(_index):
            with Session(self.engine, autoflush=False, expire_on_commit=False) as session:
                return save_layout_snapshot(session, document).version_number

        with ThreadPoolExecutor(max_workers=2) as executor:
            versions = tuple(executor.map(save_one, range(2)))
        self.assertEqual(set(versions), {1, 2})
        with Session(self.engine, autoflush=False, expire_on_commit=False) as session:
            history = list_layout_version_history(
                session,
                project_id=self.project_id,
                project_floor_id=self.floor_id,
            )
        self.assertEqual([item.version_number for item in history], [1, 2])
        self.assertEqual(sum(item.is_current for item in history), 1)

    def test_save_commits_once_and_does_not_mutate_other_domain_rows_or_files(self):
        document = self.document()
        before = {
            table.name: self.session.scalar(select(func.count()).select_from(table))
            for table in Base.metadata.sorted_tables
            if table.name != "layout_versions"
        }
        with patch.object(self.session, "commit", wraps=self.session.commit) as commit:
            with patch("builtins.open", side_effect=AssertionError("unexpected file access")):
                save_layout_snapshot(self.session, document)
        self.assertEqual(commit.call_count, 1)
        after = {
            table.name: self.session.scalar(select(func.count()).select_from(table))
            for table in Base.metadata.sorted_tables
            if table.name != "layout_versions"
        }
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
