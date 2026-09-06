import json
import socket
import subprocess
import unittest
from base64 import b64encode
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import delete, func, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_engine
from app.main import create_app
from app.models import Base, DatasetApproverAssignment, Role, User
from app.schemas.dataset_approver_assignment import DatasetApproverAssignmentWrite
from app.services.dataset_approver_assignment_service import (
    DatasetApproverAssignmentServiceError,
    create_dataset_approver_assignment,
    deactivate_dataset_approver_assignment,
)


SESSION_SECRET = "pre10-dataset-approver-test-secret"


class DatasetApproverAssignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_engine()
        cls.baseline = cls._counts()
        marker = uuid4().hex
        with Session(cls.engine, expire_on_commit=False) as session:
            roles = {
                role.name: role
                for role in session.scalars(
                    select(Role).where(Role.name.in_(("ADMIN", "DESIGNER")))
                )
            }
            cls.admin = User(
                oauth_provider=f"pre10-{marker}",
                oauth_subject="admin",
                role=roles["ADMIN"],
            )
            cls.other_admin = User(
                oauth_provider=f"pre10-{marker}",
                oauth_subject="other-admin",
                role=roles["ADMIN"],
            )
            cls.designer = User(
                oauth_provider=f"pre10-{marker}",
                oauth_subject="designer",
                role=roles["DESIGNER"],
            )
            session.add_all((cls.admin, cls.other_admin, cls.designer))
            session.commit()
            cls.user_ids = {
                "admin": cls.admin.id,
                "other_admin": cls.other_admin.id,
                "designer": cls.designer.id,
            }

        settings = Settings(
            _env_file=None,
            app_env="development",
            database_url=None,
            oauth_provider="synthetic",
            oauth_client_id="pre10-client",
            oauth_client_secret="pre10-secret",
            oauth_redirect_uri="http://localhost:8000/api/auth/callback",
            oauth_discovery_url="https://provider.invalid/.well-known/openid-configuration",
            oauth_scopes="openid profile email",
            session_secret=SESSION_SECRET,
        )
        cls.application = create_app(settings)
        cls.client = TestClient(cls.application)

    @classmethod
    def _counts(cls):
        with Session(cls.engine) as session:
            return {
                table.name: session.scalar(select(func.count()).select_from(table))
                for table in Base.metadata.sorted_tables
            }

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        with Session(cls.engine) as session:
            session.execute(delete(DatasetApproverAssignment).where(
                DatasetApproverAssignment.assignee_user_id.in_(tuple(cls.user_ids.values()))
            ))
            session.execute(delete(User).where(User.id.in_(tuple(cls.user_ids.values()))))
            session.commit()
        if cls._counts() != cls.baseline:
            raise AssertionError("PRE10 database rows were not restored.")

    def setUp(self) -> None:
        self.application.dependency_overrides.clear()
        self.client.cookies.clear()
        with Session(self.engine) as session:
            session.execute(delete(DatasetApproverAssignment).where(
                DatasetApproverAssignment.assignee_user_id.in_(tuple(self.user_ids.values()))
            ))
            session.commit()

    def _session_cookie(self, user_id: int) -> None:
        encoded = b64encode(json.dumps({"user_id": user_id}).encode())
        value = TimestampSigner(SESSION_SECRET).sign(encoded).decode()
        self.client.cookies.set("ved_session", value, domain="testserver.local")

    def _payload(self, assignee="designer", category="PEE") -> dict[str, object]:
        return {
            "assignee_user_id": self.user_ids[assignee],
            "qualification_category": category,
            "professional_reference": "PRC-REFERENCE-0001",
        }

    def test_schema_and_openapi_contract(self) -> None:
        inspector = inspect(self.engine)
        self.assertEqual(len(Base.metadata.tables), 23)
        self.assertEqual(set(inspector.get_table_names()), set(Base.metadata.tables))
        self.assertEqual(
            [column["name"] for column in inspector.get_columns("dataset_approver_assignments")],
            [
                "id", "assignee_user_id", "assigned_by_user_id",
                "deactivated_by_user_id", "authority_scope",
                "qualification_category", "professional_reference",
                "active_marker", "active_from", "inactive_at",
            ],
        )
        self.assertEqual(
            {item["name"] for item in inspector.get_check_constraints("dataset_approver_assignments")},
            {
                "ck_dataset_approver_assignments_active_marker",
                "ck_dataset_approver_assignments_authority_scope",
                "ck_dataset_approver_assignments_no_self_assignment",
                "ck_dataset_approver_assignments_qualification",
                "ck_dataset_approver_assignments_state",
            },
        )
        self.assertEqual(
            {item["name"] for item in inspector.get_indexes("dataset_approver_assignments")},
            {
                "ix_dataset_approver_assignments_assignee_user_id",
                "ix_dataset_approver_assignments_assigned_by_user_id",
                "ix_dataset_approver_assignments_deactivated_by_user_id",
                "uq_dataset_approver_assignments_active_marker",
            },
        )
        self.assertEqual(
            {
                (tuple(item['constrained_columns']), item['referred_table'])
                for item in inspector.get_foreign_keys('dataset_approver_assignments')
            },
            {
                (('assignee_user_id',), 'users'),
                (('assigned_by_user_id',), 'users'),
                (('deactivated_by_user_id',), 'users'),
            },
        )
        schema = self.application.openapi()
        self.assertIn("get", schema["paths"]["/api/dataset-approver-assignment"])
        self.assertIn("get", schema["paths"]["/api/admin/dataset-approver-assignments"])
        self.assertIn("post", schema["paths"]["/api/admin/dataset-approver-assignments"])
        self.assertIn(
            "post",
            schema["paths"]["/api/admin/dataset-approver-assignments/{assignment_id}/deactivate"],
        )
        operations = sum(
            method in {"get", "post", "put", "patch", "delete"}
            for path in schema["paths"].values()
            for method in path
        )
        self.assertEqual(operations, 34)

    def test_safe_current_read_and_admin_authorization(self) -> None:
        current_path = "/api/dataset-approver-assignment"
        admin_path = "/api/admin/dataset-approver-assignments"
        self.assertEqual(self.client.get(current_path).status_code, 401)
        self.assertEqual(self.client.get(admin_path).status_code, 401)
        self._session_cookie(self.user_ids["designer"])
        self.assertEqual(self.client.get(current_path).json(), {"assignment": None})
        self.assertEqual(self.client.get(admin_path).status_code, 403)
        self.assertEqual(self.client.post(admin_path, json=self._payload()).status_code, 403)

    def test_admin_create_safe_read_and_private_history(self) -> None:
        self._session_cookie(self.user_ids["admin"])
        response = self.client.post(
            "/api/admin/dataset-approver-assignments",
            json=self._payload(),
        )
        self.assertEqual(response.status_code, 201, response.text)
        managed = response.json()
        self.assertEqual(managed["assignee_user_id"], self.user_ids["designer"])
        self.assertEqual(managed["assigned_by_user_id"], self.user_ids["admin"])
        self.assertEqual(managed["authority_scope"], "VED_AI_DATASET_APPROVER")
        self.assertEqual(managed["qualification_category"], "PEE")
        self.assertEqual(managed["professional_reference"], "PRC-REFERENCE-0001")
        self.client.cookies.clear()
        self._session_cookie(self.user_ids["designer"])
        safe = self.client.get("/api/dataset-approver-assignment")
        self.assertEqual(safe.status_code, 200)
        assignment = safe.json()["assignment"]
        self.assertEqual(
            set(assignment),
            {"assignment_id", "assignee_user_id", "authority_scope", "active_from"},
        )
        self.assertNotIn("professional_reference", safe.text)
        self.assertNotIn("qualification_category", safe.text)

    def test_deactivation_is_history_preserving_and_idempotent(self) -> None:
        self._session_cookie(self.user_ids["admin"])
        created = self.client.post(
            "/api/admin/dataset-approver-assignments",
            json=self._payload(),
        ).json()
        path = (
            f"/api/admin/dataset-approver-assignments/"
            f"{created['assignment_id']}/deactivate"
        )
        first = self.client.post(path)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertFalse(first.json()["is_active"])
        self.assertEqual(first.json()["deactivated_by_user_id"], self.user_ids["admin"])
        second = self.client.post(path)
        self.assertEqual(second.json(), first.json())
        self.assertEqual(
            self.client.get("/api/dataset-approver-assignment").json(),
            {"assignment": None},
        )
        new_assignment = self.client.post(
            "/api/admin/dataset-approver-assignments",
            json=self._payload(assignee="other_admin", category="SENIOR_REE"),
        )
        self.assertEqual(new_assignment.status_code, 201, new_assignment.text)
        history = self.client.get("/api/admin/dataset-approver-assignments").json()
        self.assertEqual(len(history), 2)
        self.assertTrue(history[0]["is_active"])
        self.assertFalse(history[1]["is_active"])

    def test_self_assignment_active_conflict_and_missing_assignee(self) -> None:
        self._session_cookie(self.user_ids["admin"])
        self.assertEqual(
            self.client.post(
                "/api/admin/dataset-approver-assignments",
                json=self._payload(assignee="admin"),
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.post(
                "/api/admin/dataset-approver-assignments",
                json={**self._payload(), "assignee_user_id": 9_223_372_036_854_775_807},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                "/api/admin/dataset-approver-assignments",
                json=self._payload(),
            ).status_code,
            201,
        )
        conflict = self.client.post(
            "/api/admin/dataset-approver-assignments",
            json=self._payload(assignee="other_admin", category="SENIOR_REE"),
        )
        self.assertEqual(conflict.status_code, 409)

    def test_request_validation_is_strict_and_private(self) -> None:
        self._session_cookie(self.user_ids["admin"])
        path = "/api/admin/dataset-approver-assignments"
        for payload in (
            {**self._payload(), "qualification_category": "MODEL"},
            {**self._payload(), "professional_reference": " secret "},
            {**self._payload(), "professional_reference": ""},
            {**self._payload(), "unexpected": "value"},
        ):
            response = self.client.post(path, json=payload)
            self.assertEqual(response.status_code, 422)
            self.assertNotIn("pre10-secret", response.text)

    def test_concurrent_assignment_has_one_active_human(self) -> None:
        def submit(admin_name, assignee_name, category):
            try:
                with Session(self.engine) as session:
                    admin = session.get(User, self.user_ids[admin_name])
                    assert admin is not None
                    return create_dataset_approver_assignment(
                        session,
                        current_user=admin,
                        data=DatasetApproverAssignmentWrite(
                            **self._payload(assignee=assignee_name, category=category)
                        ),
                    )
            except DatasetApproverAssignmentServiceError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = (
                executor.submit(submit, "admin", "designer", "PEE"),
                executor.submit(submit, "other_admin", "designer", "SENIOR_REE"),
            )
            results = tuple(future.result() for future in futures)
        self.assertEqual(sum(not isinstance(item, str) for item in results), 1)
        self.assertIn("DATASET_APPROVER_ASSIGNMENT_CONFLICT", results)
        with Session(self.engine) as session:
            self.assertEqual(
                session.scalar(select(func.count()).select_from(
                    DatasetApproverAssignment
                ).where(DatasetApproverAssignment.active_marker.is_(True))),
                1,
            )

    def test_foundation_creates_no_review_and_invokes_no_model_or_files(self) -> None:
        with Session(self.engine, expire_on_commit=False) as session:
            admin = session.get(User, self.user_ids["admin"])
            assert admin is not None
            with (
                patch("builtins.open", side_effect=AssertionError("file invoked")),
                patch.object(socket, "create_connection", side_effect=AssertionError("network invoked")),
                patch.object(subprocess, "run", side_effect=AssertionError("process invoked")),
            ):
                created = create_dataset_approver_assignment(
                    session,
                    current_user=admin,
                    data=DatasetApproverAssignmentWrite(**self._payload()),
                )
            deactivated = deactivate_dataset_approver_assignment(
                session,
                current_user=admin,
                assignment_id=created.assignment_id,
            )
        self.assertFalse(deactivated.is_active)
        with Session(self.engine) as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Role)), 2)

    def test_database_failure_is_sanitized(self) -> None:
        self._session_cookie(self.user_ids["admin"])
        with patch(
            "app.services.dataset_approver_assignment_service.repository.list_assignments",
            side_effect=SQLAlchemyError("private database detail"),
        ):
            response = self.client.get("/api/admin/dataset-approver-assignments")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private database detail", response.text)


if __name__ == "__main__":
    unittest.main()
