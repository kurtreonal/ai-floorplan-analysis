import copy
import hashlib
import json
import unittest
from base64 import b64encode
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import delete, func, inspect, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import Settings
from app.core.database import get_db, get_engine
from app.main import create_app
from app.models import (
    Base,
    FloorPlan,
    LayoutSaveRequest,
    LayoutVersion,
    Project,
    ProjectFloor,
    Role,
    User,
)
from app.services.layout_service import LayoutServiceError, save_owned_layout
from app.services.layout_version_service import LayoutVersionServiceError


SESSION_COOKIE = "ved_session"
SESSION_SECRET = "k3-layout-api-test-session-secret"
FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "canonical_geometry_v1.json"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LAYOUT_PATH = "/api/projects/{project_id}/floors/{project_floor_id}/layouts"


class LayoutApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_engine()
        cls.baseline_counts = cls._counts()
        cls.connection = cls.engine.connect()
        cls.transaction = cls.connection.begin()
        cls.database_session = Session(
            bind=cls.connection,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        roles = {
            role.name: role
            for role in cls.database_session.scalars(
                select(Role).where(Role.name.in_(("ADMIN", "DESIGNER")))
            )
        }
        if set(roles) != {"ADMIN", "DESIGNER"}:
            raise unittest.SkipTest("The seeded ADMIN and DESIGNER roles are required.")

        marker = uuid4().hex
        cls.designer = User(
            oauth_provider=f"k3-{marker}",
            oauth_subject="designer",
            role=roles["DESIGNER"],
        )
        cls.other_designer = User(
            oauth_provider=f"k3-{marker}",
            oauth_subject="other-designer",
            role=roles["DESIGNER"],
        )
        cls.admin = User(
            oauth_provider=f"k3-{marker}",
            oauth_subject="admin",
            role=roles["ADMIN"],
        )
        cls.project = Project(owner=cls.designer, name=f"K3 project {marker}")
        cls.second_project = Project(
            owner=cls.designer,
            name=f"K3 second project {marker}",
        )
        cls.other_project = Project(
            owner=cls.other_designer,
            name=f"K3 other project {marker}",
        )
        cls.floor = ProjectFloor(
            project=cls.project,
            name="Lower Ground Floor",
            sort_order=0,
        )
        cls.second_floor = ProjectFloor(
            project=cls.project,
            name="Upper Floor",
            sort_order=1,
        )
        cls.foreign_floor = ProjectFloor(
            project=cls.second_project,
            name="Second Project Floor",
            sort_order=0,
        )
        cls.other_floor = ProjectFloor(
            project=cls.other_project,
            name="Other Designer Floor",
            sort_order=0,
        )
        cls.floor_plan = cls._floor_plan(cls.floor, "plan.png")
        cls.second_floor_plan = cls._floor_plan(cls.second_floor, "upper.png")
        cls.foreign_floor_plan = cls._floor_plan(cls.foreign_floor, "foreign.png")
        cls.other_floor_plan = cls._floor_plan(cls.other_floor, "other.png")
        cls.database_session.add_all(
            (
                cls.floor_plan,
                cls.second_floor_plan,
                cls.foreign_floor_plan,
                cls.other_floor_plan,
                cls.admin,
            )
        )
        cls.database_session.flush()
        cls.database_session.commit()

        settings = Settings(
            _env_file=None,
            app_env="development",
            database_url=None,
            oauth_provider="synthetic",
            oauth_client_id="k3-client",
            oauth_client_secret="k3-client-secret",
            oauth_redirect_uri="http://localhost:8000/api/auth/callback",
            oauth_discovery_url=(
                "https://provider.invalid/.well-known/openid-configuration"
            ),
            oauth_scopes="openid profile email",
            session_secret=SESSION_SECRET,
        )
        cls.application = create_app(settings)

        def override_database():
            yield cls.database_session

        cls.application.dependency_overrides[get_db] = override_database
        cls.client = TestClient(cls.application)

    @classmethod
    def _floor_plan(cls, floor: ProjectFloor, name: str) -> FloorPlan:
        return FloorPlan(
            project_floor=floor,
            original_filename=name,
            storage_path=f"originals/{name}",
            mime_type="image/png",
            file_size=24_493,
            processing_status="processed",
        )

    @classmethod
    def _counts(cls) -> dict[str, int]:
        with Session(cls.engine) as session:
            return {
                table.name: session.scalar(select(func.count()).select_from(table))
                for table in Base.metadata.sorted_tables
            }

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        cls.database_session.close()
        if cls.transaction.is_active:
            cls.transaction.rollback()
        cls.connection.close()
        if cls._counts() != cls.baseline_counts:
            raise AssertionError("K3 database row counts were not restored.")

    def setUp(self) -> None:
        self.client.cookies.clear()
        self.application.dependency_overrides.pop(get_current_user, None)
        self.database_session.rollback()
        self.database_session.execute(
            delete(LayoutSaveRequest).where(
                LayoutSaveRequest.project_floor_id.in_(
                    (
                        self.floor.id,
                        self.second_floor.id,
                        self.foreign_floor.id,
                        self.other_floor.id,
                    )
                )
            )
        )
        self.database_session.execute(
            delete(LayoutVersion).where(
                LayoutVersion.project_id.in_(
                    (
                        self.project.id,
                        self.second_project.id,
                        self.other_project.id,
                    )
                )
            )
        )
        self.database_session.commit()

    def _set_session(self, user: User) -> None:
        encoded = b64encode(json.dumps({"user_id": user.id}).encode("utf-8"))
        cookie = TimestampSigner(SESSION_SECRET).sign(encoded).decode("utf-8")
        self.client.cookies.set(
            SESSION_COOKIE,
            cookie,
            domain="testserver.local",
        )

    def _path(
        self,
        *,
        project_id: int | None = None,
        floor_id: int | None = None,
    ) -> str:
        return LAYOUT_PATH.format(
            project_id=self.project.id if project_id is None else project_id,
            project_floor_id=self.floor.id if floor_id is None else floor_id,
        )

    def _payload(
        self,
        *,
        project: Project | None = None,
        floor: ProjectFloor | None = None,
        floor_plan: FloorPlan | None = None,
        verified: bool = True,
        dimensions: bool = True,
        empty: bool = False,
    ) -> dict[str, object]:
        project = project or self.project
        floor = floor or self.floor
        floor_plan = floor_plan or self.floor_plan
        payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        payload["project_id"] = project.id
        payload["floor"]["project_floor_id"] = floor.id
        payload["floor"]["name"] = floor.name
        payload["floor"]["sort_order"] = floor.sort_order
        payload["floor_plan_id"] = floor_plan.id
        for point in payload["routes"][0]["points"]:
            point["project_floor_id"] = floor.id
        if verified:
            payload["walls"][0]["status"] = "verified"
        if dimensions:
            payload["walls"][0]["thickness_meters"] = 0.15
            payload["walls"][0]["height_meters"] = 3.0
        if empty:
            for key in ("walls", "rooms", "symbols", "routes"):
                payload[key] = []
        return payload

    def _post(
        self,
        payload: dict[str, object] | None = None,
        *,
        user: User | None = None,
        project_id: int | None = None,
        floor_id: int | None = None,
        expected_version_number: int | None | object = ...,
        idempotency_key: str | None = None,
    ):
        if user is not None:
            self._set_session(user)
        target_floor_id = self.floor.id if floor_id is None else floor_id
        if expected_version_number is ...:
            expected_version_number = self.database_session.scalar(
                select(LayoutVersion.version_number).where(
                    LayoutVersion.project_floor_id == target_floor_id,
                    LayoutVersion.is_current.is_(True),
                )
            )
        body = {
            "expected_version_number": expected_version_number,
            "idempotency_key": idempotency_key or str(uuid4()),
            "geometry": self._payload() if payload is None else payload,
        }
        return self.client.post(
            self._path(project_id=project_id, floor_id=floor_id),
            json=body,
        )

    def _get(
        self,
        *,
        user: User | None = None,
        project_id: int | None = None,
        floor_id: int | None = None,
    ):
        if user is not None:
            self._set_session(user)
        return self.client.get(
            self._path(project_id=project_id, floor_id=floor_id)
        )

    def _layout_count(self) -> int:
        return self.database_session.scalar(
            select(func.count()).select_from(LayoutVersion)
        )

    def _save_request_count(self) -> int:
        return self.database_session.scalar(
            select(func.count()).select_from(LayoutSaveRequest)
        )

    def _file_state(self) -> dict[str, tuple[int, str]]:
        roots = (
            REPOSITORY_ROOT / "storage" / "uploads" / "originals",
            REPOSITORY_ROOT / "storage" / "processed",
            REPOSITORY_ROOT / "models",
        )
        state = {}
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if path.is_file() and path.name != ".gitkeep":
                    relative = path.relative_to(REPOSITORY_ROOT).as_posix()
                    state[relative] = (
                        path.stat().st_size,
                        hashlib.sha256(path.read_bytes()).hexdigest(),
                    )
        return state

    def test_routes_openapi_models_and_schema_contract(self) -> None:
        schema = self.application.openapi()
        path = schema["paths"][LAYOUT_PATH]
        self.assertEqual(set(path), {"get", "post"})
        self.assertIn("$ref", path["get"]["responses"]["200"]["content"]["application/json"]["schema"])
        self.assertIn("$ref", path["post"]["requestBody"]["content"]["application/json"]["schema"])
        self.assertIn("$ref", path["post"]["responses"]["201"]["content"]["application/json"]["schema"])
        operations = [
            method
            for item in schema["paths"].values()
            for method in item
            if method in {"get", "post", "put", "patch", "delete"}
        ]
        self.assertEqual(len(operations), 30)
        self.assertFalse(
            any("history" in path or "current" in path for path in schema["paths"])
        )
        self.assertEqual(len(Base.metadata.tables), 22)
        self.assertEqual(
            set(inspect(self.engine).get_table_names()), set(Base.metadata.tables)
        )

    def test_authentication_role_and_admin_read_only_behavior(self) -> None:
        for method in (self._get, self._post):
            with self.subTest(method=method.__name__, authentication="missing"):
                response = method()
                self.assertEqual(response.status_code, 401, response.text)

        unsupported_user = SimpleNamespace(role=SimpleNamespace(name="VIEWER"))
        self.application.dependency_overrides[get_current_user] = (
            lambda: unsupported_user
        )
        try:
            self.assertEqual(self._get().status_code, 403)
            self.assertEqual(self._post().status_code, 403)
        finally:
            self.application.dependency_overrides.pop(get_current_user, None)

        created = self._post(user=self.designer)
        self.assertEqual(created.status_code, 201, created.text)
        self.client.cookies.clear()
        admin_get = self._get(user=self.admin)
        self.assertEqual(admin_get.status_code, 200, admin_get.text)
        self.client.cookies.clear()
        admin_post = self._post(user=self.admin)
        self.assertEqual(admin_post.status_code, 403, admin_post.text)
        self.assertEqual(self._layout_count(), 1)

        with self.assertRaises(LayoutServiceError) as caught:
            save_owned_layout(
                self.database_session,
                current_user=self.admin,
                project_id=self.project.id,
                project_floor_id=self.floor.id,
                geometry_payload=self._payload(),
                expected_version_number=None,
                idempotency_key=str(uuid4()),
            )
        self.assertEqual(caught.exception.code, "AUTHORIZATION_DENIED")

    def test_designer_context_authorization_is_non_disclosing(self) -> None:
        cases = (
            (self.other_project.id, self.other_floor.id),
            (self.project.id + 9_000_000, self.floor.id),
            (self.project.id, self.floor.id + 9_000_000),
            (self.project.id, self.foreign_floor.id),
        )
        for project_id, floor_id in cases:
            for method in (self._get, self._post):
                with self.subTest(
                    project_id=project_id,
                    floor_id=floor_id,
                    method=method.__name__,
                ):
                    self.client.cookies.clear()
                    response = method(
                        user=self.designer,
                        project_id=project_id,
                        floor_id=floor_id,
                    )
                    self.assertEqual(response.status_code, 404, response.text)
                    self.assertEqual(response.json()["detail"]["error"]["code"], "LAYOUT_NOT_FOUND")
        self.assertEqual(self._layout_count(), 0)

    def test_first_post_round_trips_complete_canonical_document(self) -> None:
        payload = self._payload()
        original = copy.deepcopy(payload)
        response = self._post(payload, user=self.designer)
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(
            set(body),
            {
                "id",
                "project_id",
                "project_floor_id",
                "floor_plan_id",
                "version_number",
                "schema_version",
                "is_current",
                "created_at",
                "geometry",
            },
        )
        self.assertEqual(body["version_number"], 1)
        self.assertTrue(body["is_current"])
        self.assertEqual(body["schema_version"], 1)
        self.assertEqual(body["project_id"], self.project.id)
        self.assertEqual(body["project_floor_id"], self.floor.id)
        self.assertEqual(body["floor_plan_id"], self.floor_plan.id)
        self.assertEqual(body["geometry"], original)
        self.assertEqual(payload, original)
        self.assertEqual(body["geometry"]["floor"]["elevation_meters"], -1.5)
        self.assertEqual(body["geometry"]["walls"][0]["status"], "verified")
        self.assertEqual(body["geometry"]["walls"][0]["height_meters"], 3.0)
        self.assertEqual(body["geometry"]["symbols"][0]["class"]["name"], "Power outlet")
        self.assertEqual(body["geometry"]["symbols"][1]["status"], "manually_added")
        self.assertEqual(body["geometry"]["rooms"][0]["name"], "Living Room")
        self.assertEqual(body["geometry"]["routes"][0]["points"][0]["elevation_meters"], -1.5)
        datetime.fromisoformat(body["created_at"])

    def test_empty_geometry_is_accepted(self) -> None:
        response = self._post(self._payload(empty=True), user=self.designer)
        self.assertEqual(response.status_code, 201, response.text)
        geometry = response.json()["geometry"]
        self.assertEqual(
            (geometry["walls"], geometry["rooms"], geometry["symbols"], geometry["routes"]),
            ([], [], [], []),
        )

    def test_versions_current_get_identical_save_and_independent_floor_sequences(self) -> None:
        first_payload = self._payload()
        second_payload = self._payload()
        second_payload["floor"]["elevation_meters"] = 2.5
        first = self._post(first_payload, user=self.designer)
        self.client.cookies.clear()
        second = self._post(second_payload, user=self.designer)
        self.client.cookies.clear()
        third = self._post(second_payload, user=self.designer)
        self.assertEqual(
            [first.json()["version_number"], second.json()["version_number"], third.json()["version_number"]],
            [1, 2, 3],
        )
        rows = tuple(
            self.database_session.scalars(
                select(LayoutVersion)
                .where(LayoutVersion.project_floor_id == self.floor.id)
                .order_by(LayoutVersion.version_number)
            )
        )
        self.assertEqual([row.version_number for row in rows], [1, 2, 3])
        self.assertEqual([row.is_current for row in rows], [None, None, True])
        self.assertEqual(rows[0].geometry_document, first_payload)

        self.client.cookies.clear()
        current = self._get(user=self.designer)
        self.assertEqual(current.status_code, 200, current.text)
        self.assertEqual(current.json()["version_number"], 3)
        self.assertEqual(current.json()["geometry"], second_payload)

        other_payload = self._payload(
            floor=self.second_floor,
            floor_plan=self.second_floor_plan,
        )
        self.client.cookies.clear()
        other = self._post(
            other_payload,
            user=self.designer,
            floor_id=self.second_floor.id,
        )
        self.assertEqual(other.status_code, 201, other.text)
        self.assertEqual(other.json()["version_number"], 1)
        self.assertTrue(other.json()["is_current"])

    def test_k5_symbol_move_creates_new_version_and_get_reloads_only_position(self) -> None:
        first_payload = self._payload()
        moved_payload = copy.deepcopy(first_payload)
        moved_payload["symbols"][0]["position"] = {"x": 4.25, "y": 1.75}
        source_counts_before = {
            table.name: self.database_session.scalar(
                select(func.count()).select_from(table)
            )
            for table in Base.metadata.sorted_tables
            if table.name not in {"layout_versions", "layout_save_requests"}
        }
        files_before = self._file_state()

        first = self._post(first_payload, user=self.designer)
        self.assertEqual(first.status_code, 201, first.text)
        self.client.cookies.clear()
        second = self._post(moved_payload, user=self.designer)
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(second.json()["version_number"], 2)

        self.client.cookies.clear()
        loaded = self._get(user=self.designer)
        self.assertEqual(loaded.status_code, 200, loaded.text)
        self.assertEqual(loaded.json()["version_number"], 2)
        self.assertEqual(
            loaded.json()["geometry"]["symbols"][0]["position"],
            {"x": 4.25, "y": 1.75},
        )

        rows = tuple(
            self.database_session.scalars(
                select(LayoutVersion)
                .where(LayoutVersion.project_floor_id == self.floor.id)
                .order_by(LayoutVersion.version_number)
            )
        )
        self.assertEqual([row.version_number for row in rows], [1, 2])
        self.assertEqual(rows[0].geometry_document, first_payload)
        self.assertEqual(rows[1].geometry_document, moved_payload)

        original_symbol = copy.deepcopy(first_payload["symbols"][0])
        moved_symbol = copy.deepcopy(moved_payload["symbols"][0])
        original_position = original_symbol.pop("position")
        moved_position = moved_symbol.pop("position")
        self.assertNotEqual(original_position, moved_position)
        self.assertEqual(moved_symbol, original_symbol)
        self.assertEqual(moved_payload["symbols"][1:], first_payload["symbols"][1:])
        for field in (
            "schema_version", "project_id", "floor", "floor_plan_id",
            "coordinate_system", "walls", "rooms", "routes",
        ):
            self.assertEqual(moved_payload[field], first_payload[field])

        source_counts_after = {
            table.name: self.database_session.scalar(
                select(func.count()).select_from(table)
            )
            for table in Base.metadata.sorted_tables
            if table.name not in {"layout_versions", "layout_save_requests"}
        }
        self.assertEqual(source_counts_after, source_counts_before)
        self.assertEqual(self._file_state(), files_before)

    def test_conditional_save_rejects_stale_versions_without_creating_rows(self) -> None:
        first = self._post(user=self.designer)
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual((self._layout_count(), self._save_request_count()), (1, 1))

        self.client.cookies.clear()
        stale = self._post(
            self._payload(),
            user=self.designer,
            expected_version_number=None,
        )
        self.assertEqual(stale.status_code, 409, stale.text)
        self.assertEqual(stale.json()["detail"]["error"]["code"], "STALE_LAYOUT_VERSION")
        self.assertEqual((self._layout_count(), self._save_request_count()), (1, 1))

        self.database_session.execute(delete(LayoutSaveRequest))
        self.database_session.execute(delete(LayoutVersion))
        self.database_session.commit()
        self.client.cookies.clear()
        stale_first = self._post(
            self._payload(),
            user=self.designer,
            expected_version_number=1,
        )
        self.assertEqual(stale_first.status_code, 409, stale_first.text)
        self.assertEqual((self._layout_count(), self._save_request_count()), (0, 0))

    def test_identical_idempotent_retry_returns_original_without_new_snapshot(self) -> None:
        key = str(uuid4())
        payload = self._payload()
        first = self._post(
            payload,
            user=self.designer,
            expected_version_number=None,
            idempotency_key=key,
        )
        self.assertEqual(first.status_code, 201, first.text)
        self.client.cookies.clear()
        retry = self._post(
            copy.deepcopy(payload),
            user=self.designer,
            expected_version_number=None,
            idempotency_key=key,
        )
        self.assertEqual(retry.status_code, 201, retry.text)
        self.assertEqual(retry.json(), first.json())
        self.assertEqual((self._layout_count(), self._save_request_count()), (1, 1))

    def test_idempotency_key_reuse_with_different_request_is_conflict(self) -> None:
        key = str(uuid4())
        first = self._post(
            self._payload(),
            user=self.designer,
            expected_version_number=None,
            idempotency_key=key,
        )
        self.assertEqual(first.status_code, 201, first.text)
        changed = self._payload()
        changed["symbols"][0]["position"] = {"x": 4.25, "y": 1.75}
        self.client.cookies.clear()
        conflict = self._post(
            changed,
            user=self.designer,
            expected_version_number=1,
            idempotency_key=key,
        )
        self.assertEqual(conflict.status_code, 409, conflict.text)
        self.assertEqual(
            conflict.json()["detail"]["error"]["code"],
            "IDEMPOTENCY_KEY_CONFLICT",
        )
        self.assertEqual((self._layout_count(), self._save_request_count()), (1, 1))

    def test_get_exact_current_is_read_only_and_missing_is_404(self) -> None:
        missing = self._get(user=self.designer)
        self.assertEqual(missing.status_code, 404, missing.text)
        self.assertEqual(missing.json()["detail"]["error"]["code"], "LAYOUT_NOT_FOUND")

        self.client.cookies.clear()
        saved = self._post(user=self.designer)
        self.assertEqual(saved.status_code, 201, saved.text)
        before = self._counts()
        self.client.cookies.clear()
        with patch.object(self.database_session, "commit", side_effect=AssertionError("GET committed")):
            with patch.object(self.database_session, "flush", side_effect=AssertionError("GET flushed")):
                response = self._get(user=self.designer)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), saved.json())
        self.assertEqual(self._counts(), before)

    def test_corrupt_current_and_integrity_failures_are_sanitized(self) -> None:
        saved = self._post(user=self.designer)
        row_id = saved.json()["id"]
        self.database_session.execute(
            update(LayoutVersion)
            .where(LayoutVersion.id == row_id)
            .values(geometry_document={"schema_version": 1})
        )
        self.database_session.commit()
        self.client.cookies.clear()
        corrupt = self._get(user=self.designer)
        self.assertEqual(corrupt.status_code, 503, corrupt.text)
        self.assertEqual(corrupt.json()["detail"]["error"]["code"], "LAYOUT_RETRIEVAL_FAILED")
        self.assertNotIn("INVALID_STORED_GEOMETRY", corrupt.text)

        self.client.cookies.clear()
        with patch(
            "app.services.layout_service.retrieve_current_layout_version",
            side_effect=LayoutVersionServiceError("CURRENT_MARKER_INTEGRITY_FAILED"),
        ):
            integrity = self._get(user=self.designer)
        self.assertEqual(integrity.status_code, 503, integrity.text)
        self.assertEqual(integrity.json()["detail"]["error"]["code"], "LAYOUT_RETRIEVAL_FAILED")

    def test_structural_and_semantic_geometry_validation_creates_no_row(self) -> None:
        cases = []
        unknown = self._payload()
        unknown["version_number"] = 1
        cases.append(("unknown", unknown))
        boolean = self._payload()
        boolean["project_id"] = True
        cases.append(("boolean", boolean))
        schema = self._payload()
        schema["schema_version"] = 2
        cases.append(("schema", schema))
        scale = self._payload()
        scale["coordinate_system"]["pixels_per_meter"] = 0
        cases.append(("scale", scale))
        dimensions = self._payload()
        dimensions["coordinate_system"]["width_meters"] = 999
        cases.append(("dimensions", dimensions))
        outside = self._payload()
        outside["walls"][0]["end"]["x"] = 7
        cases.append(("outside", outside))
        length = self._payload()
        length["walls"][0]["length_meters"] = 1
        cases.append(("wall-length", length))
        room = self._payload()
        room["rooms"][0]["boundary"][1] = room["rooms"][0]["boundary"][0]
        cases.append(("room", room))
        symbol = self._payload()
        symbol["symbols"][0]["id"] = "detected:999"
        cases.append(("symbol", symbol))
        route = self._payload()
        route["routes"][0]["points"][0]["x"] = -1
        cases.append(("route", route))
        elevation = self._payload()
        elevation["floor"]["elevation_meters"] = "not-a-number"
        cases.append(("elevation", elevation))

        for name, payload in cases:
            with self.subTest(case=name):
                self.client.cookies.clear()
                response = self._post(payload, user=self.designer)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(self._layout_count(), 0)

    def test_path_body_and_database_identity_validation_preserves_current(self) -> None:
        current = self._post(user=self.designer)
        self.assertEqual(current.status_code, 201, current.text)
        cases = []
        project = self._payload()
        project["project_id"] = self.second_project.id
        cases.append(("project", project))
        floor = self._payload()
        floor["floor"]["project_floor_id"] = self.second_floor.id
        cases.append(("floor", floor))
        floor_plan = self._payload()
        floor_plan["floor_plan_id"] = self.foreign_floor_plan.id
        cases.append(("floor-plan", floor_plan))
        name = self._payload()
        name["floor"]["name"] = "Stale Name"
        cases.append(("name", name))
        order = self._payload()
        order["floor"]["sort_order"] = 99
        cases.append(("sort-order", order))

        for name, payload in cases:
            with self.subTest(case=name):
                self.client.cookies.clear()
                response = self._post(payload, user=self.designer)
                self.assertEqual(response.status_code, 422, response.text)
                if "detail" in response.json() and "error" in response.json()["detail"]:
                    self.assertEqual(response.json()["detail"]["error"]["code"], "INVALID_LAYOUT_GEOMETRY")
                self.assertEqual(self._layout_count(), 1)
                self.client.cookies.clear()
                loaded = self._get(user=self.designer)
                self.assertEqual(loaded.json()["id"], current.json()["id"])

    def test_nonfinite_values_are_rejected(self) -> None:
        payload = self._payload()
        payload["floor"]["elevation_meters"] = "NaN"
        response = self._post(payload, user=self.designer)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self._layout_count(), 0)

    def test_save_and_retrieval_failures_are_sanitized_and_rollback(self) -> None:
        with patch(
            "app.services.layout_service.save_layout_snapshot_conditionally",
            side_effect=LayoutVersionServiceError("LAYOUT_PERSISTENCE_FAILED"),
        ):
            failed = self._post(user=self.designer)
        self.assertEqual(failed.status_code, 503, failed.text)
        self.assertEqual(failed.json()["detail"]["error"]["code"], "LAYOUT_SAVE_FAILED")
        self.assertNotIn("LAYOUT_PERSISTENCE_FAILED", failed.text)
        self.assertEqual(self._layout_count(), 0)

        self.client.cookies.clear()
        first = self._post(user=self.designer)
        self.assertEqual(first.status_code, 201, first.text)
        self.client.cookies.clear()
        with patch(
            "app.services.layout_version_service.add_layout_version",
            side_effect=SQLAlchemyError("private SQL and path detail"),
        ):
            rollback = self._post(user=self.designer)
        self.assertEqual(rollback.status_code, 503, rollback.text)
        self.assertEqual(self._layout_count(), 1)
        self.client.cookies.clear()
        self.assertEqual(self._get(user=self.designer).json()["id"], first.json()["id"])

        self.client.cookies.clear()
        with patch(
            "app.services.layout_service.retrieve_current_layout_version",
            side_effect=SQLAlchemyError("private SQL and path detail"),
        ):
            retrieval = self._get(user=self.designer)
        self.assertEqual(retrieval.status_code, 503, retrieval.text)
        self.assertEqual(retrieval.json()["detail"]["error"]["code"], "LAYOUT_RETRIEVAL_FAILED")
        for secret in ("private SQL", "path detail", "Traceback"):
            self.assertNotIn(secret, retrieval.text)

    def test_only_layout_rows_change_and_files_are_untouched(self) -> None:
        before_rows = {
            table.name: self.database_session.scalar(
                select(func.count()).select_from(table)
            )
            for table in Base.metadata.sorted_tables
            if table.name not in {"layout_versions", "layout_save_requests"}
        }
        before_files = self._file_state()
        project_status = self.project.status
        floor_state = (self.floor.name, self.floor.sort_order)
        plan_state = (
            self.floor_plan.storage_path,
            self.floor_plan.mime_type,
            self.floor_plan.file_size,
            self.floor_plan.processing_status,
        )
        response = self._post(user=self.designer)
        self.assertEqual(response.status_code, 201, response.text)
        self.client.cookies.clear()
        self.assertEqual(self._get(user=self.designer).status_code, 200)
        after_rows = {
            table.name: self.database_session.scalar(
                select(func.count()).select_from(table)
            )
            for table in Base.metadata.sorted_tables
            if table.name not in {"layout_versions", "layout_save_requests"}
        }
        self.assertEqual(after_rows, before_rows)
        self.assertEqual(self._file_state(), before_files)
        self.assertEqual(self.project.status, project_status)
        self.assertEqual((self.floor.name, self.floor.sort_order), floor_state)
        self.assertEqual(
            (
                self.floor_plan.storage_path,
                self.floor_plan.mime_type,
                self.floor_plan.file_size,
                self.floor_plan.processing_status,
            ),
            plan_state,
        )


if __name__ == "__main__":
    unittest.main()
