import json
import unittest
from base64 import b64encode
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from PIL import Image
from pypdf import PdfWriter
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.core.config import Settings
from app.core.database import get_db, get_engine
from app.main import create_app
from app.models import FloorPlan, Project, ProjectFloor, Role, User


SESSION_COOKIE = "ved_session"
SESSION_SECRET = "e3-automated-test-session-secret"


def make_image(image_format: str) -> bytes:
    output = BytesIO()
    with Image.new("RGB", (18, 12), color=(255, 255, 255)) as image:
        image.save(output, format=image_format)
    return output.getvalue()


def make_pdf(*, encrypted: bool = False) -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    if encrypted:
        writer.encrypt("test-password")
    writer.write(output)
    return output.getvalue()


class FloorPlanUploadApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = get_engine().connect()
        cls.transaction = cls.connection.begin()
        cls.database_session = Session(
            bind=cls.connection,
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
            raise RuntimeError("The ADMIN and DESIGNER seed roles are required.")

        marker = uuid4().hex
        cls.designer = User(
            oauth_provider="e3-test",
            oauth_subject=f"designer-{marker}",
            email=f"designer-{marker}@example.test",
            display_name="E3 Designer",
            role_id=roles["DESIGNER"].id,
        )
        cls.other_designer = User(
            oauth_provider="e3-test",
            oauth_subject=f"other-{marker}",
            email=f"other-{marker}@example.test",
            display_name="E3 Other Designer",
            role_id=roles["DESIGNER"].id,
        )
        cls.admin = User(
            oauth_provider="e3-test",
            oauth_subject=f"admin-{marker}",
            email=f"admin-{marker}@example.test",
            display_name="E3 Admin",
            role_id=roles["ADMIN"].id,
        )
        cls.project = Project(owner=cls.designer, name=f"E3 Project {marker}")
        cls.project_floor = ProjectFloor(
            project=cls.project,
            name="Ground Floor",
            sort_order=0,
        )
        cls.second_project = Project(
            owner=cls.designer,
            name=f"E3 Second Project {marker}",
        )
        cls.second_project_floor = ProjectFloor(
            project=cls.second_project,
            name="Second Project Floor",
            sort_order=0,
        )
        cls.other_project = Project(
            owner=cls.other_designer,
            name=f"E3 Other Project {marker}",
        )
        cls.other_project_floor = ProjectFloor(
            project=cls.other_project,
            name="Other Floor",
            sort_order=0,
        )
        cls.database_session.add_all(
            (
                cls.project_floor,
                cls.second_project_floor,
                cls.other_project_floor,
                cls.admin,
            )
        )
        cls.database_session.flush()
        cls.database_session.commit()

        cls.storage_root = TemporaryDirectory()
        cls.settings = Settings(
            _env_file=None,
            app_env="development",
            database_url=None,
            oauth_provider="synthetic",
            oauth_client_id="e3-client",
            oauth_client_secret="e3-client-secret",
            oauth_redirect_uri="http://localhost:8000/api/auth/callback",
            oauth_discovery_url=(
                "https://provider.invalid/.well-known/openid-configuration"
            ),
            oauth_scopes="openid profile email",
            session_secret=SESSION_SECRET,
            upload_dir=Path(cls.storage_root.name),
            max_upload_size_mb=1,
        )
        cls.application = create_app(cls.settings)

        def override_database():
            yield cls.database_session

        cls.application.dependency_overrides[get_db] = override_database
        cls.client = TestClient(cls.application)
        cls.jpeg = make_image("JPEG")
        cls.png = make_image("PNG")
        cls.pdf = make_pdf()
        cls.encrypted_pdf = make_pdf(encrypted=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        cls.storage_root.cleanup()
        cls.database_session.close()
        if cls.transaction.is_active:
            cls.transaction.rollback()
        cls.connection.close()

    def setUp(self) -> None:
        self.client.cookies.clear()
        self.test_upload_directory = (
            Path(self.storage_root.name) / f"case-{uuid4().hex}"
        )
        self.settings.upload_dir = self.test_upload_directory

    def _set_session(self, user: User, **untrusted_values: object) -> None:
        encoded = b64encode(
            json.dumps({"user_id": user.id, **untrusted_values}).encode("utf-8")
        )
        cookie = TimestampSigner(SESSION_SECRET).sign(encoded).decode("utf-8")
        self.client.cookies.set(
            SESSION_COOKIE,
            cookie,
            domain="testserver.local",
        )

    def post_upload(
        self,
        *,
        user: User | None = None,
        project_id: int | None = None,
        project_floor_id: int | str | None = None,
        filename: str = "floor-plan.jpg",
        mime_type: str = "image/jpeg",
        content: bytes | None = None,
        include_file: bool = True,
        include_floor: bool = True,
        query: str = "",
        headers: dict[str, str] | None = None,
    ):
        if user is not None:
            self._set_session(user)
        target_project_id = self.project.id if project_id is None else project_id
        target_floor_id = (
            self.project_floor.id
            if project_floor_id is None
            else project_floor_id
        )
        files = (
            {"file": (filename, self.jpeg if content is None else content, mime_type)}
            if include_file
            else None
        )
        data = {"project_floor_id": str(target_floor_id)} if include_floor else {}
        return self.client.post(
            f"/api/projects/{target_project_id}/floor-plans{query}",
            data=data,
            files=files,
            headers=headers,
        )

    def count_floor_plans(self) -> int:
        floor_ids = (
            self.project_floor.id,
            self.second_project_floor.id,
            self.other_project_floor.id,
        )
        return self.database_session.scalar(
            select(func.count())
            .select_from(FloorPlan)
            .where(FloorPlan.project_floor_id.in_(floor_ids))
        )

    def stored_files(self) -> tuple[Path, ...]:
        originals = self.test_upload_directory / "originals"
        if not originals.exists():
            return ()
        return tuple(path for path in originals.iterdir() if path.is_file())

    def assert_error(self, response, status_code: int, code: str) -> None:
        self.assertEqual(response.status_code, status_code, response.text)
        error = response.json()["detail"]["error"]
        self.assertEqual(error["code"], code)
        self.assertIsInstance(error["message"], str)
        self.assertIsInstance(error["details"], dict)
        self.assertNotIn(str(self.test_upload_directory), response.text)

    def assert_successful_upload(
        self,
        *,
        filename: str,
        mime_type: str,
        content: bytes,
    ) -> tuple[dict[str, object], FloorPlan, Path]:
        response = self.post_upload(
            user=self.designer,
            filename=filename,
            mime_type=mime_type,
            content=content,
        )
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(
            set(body),
            {
                "id",
                "project_floor_id",
                "original_filename",
                "mime_type",
                "file_size",
                "processing_status",
            },
        )
        self.assertNotIn("storage_path", body)
        floor_plan = self.database_session.get(FloorPlan, body["id"])
        self.assertIsNotNone(floor_plan)
        stored_path = self.test_upload_directory / Path(floor_plan.storage_path)
        self.assertEqual(stored_path.parent, self.test_upload_directory / "originals")
        self.assertEqual(stored_path.read_bytes(), content)
        self.assertEqual(floor_plan.project_floor_id, self.project_floor.id)
        self.assertEqual(floor_plan.original_filename, filename)
        self.assertEqual(floor_plan.mime_type, mime_type)
        self.assertEqual(floor_plan.file_size, len(content))
        self.assertEqual(floor_plan.processing_status, "uploaded")
        self.assertEqual(body["processing_status"], "uploaded")
        return body, floor_plan, stored_path

    def test_valid_jpeg_returns_201_and_persists_file_and_metadata(self) -> None:
        body, floor_plan, _ = self.assert_successful_upload(
            filename="floor-plan.jpg",
            mime_type="image/jpeg",
            content=self.jpeg,
        )
        self.assertEqual(body["id"], floor_plan.id)
        self.assertEqual(body["project_floor_id"], self.project_floor.id)

    def test_valid_png_returns_201(self) -> None:
        self.assert_successful_upload(
            filename="floor-plan.png",
            mime_type="image/png",
            content=self.png,
        )

    def test_valid_pdf_returns_201(self) -> None:
        self.assert_successful_upload(
            filename="floor-plan.pdf",
            mime_type="application/pdf",
            content=self.pdf,
        )

    def test_unauthenticated_upload_returns_401_without_side_effects(self) -> None:
        before = self.count_floor_plans()
        response = self.post_upload()
        self.assert_error(response, 401, "AUTHENTICATION_REQUIRED")
        self.assertEqual(self.count_floor_plans(), before)
        self.assertEqual(self.stored_files(), ())

    def test_admin_upload_returns_403_without_side_effects(self) -> None:
        before = self.count_floor_plans()
        response = self.post_upload(user=self.admin)
        self.assert_error(response, 403, "AUTHORIZATION_DENIED")
        self.assertEqual(self.count_floor_plans(), before)
        self.assertEqual(self.stored_files(), ())

    def test_designer_cannot_upload_to_another_designers_project(self) -> None:
        before = self.count_floor_plans()
        response = self.post_upload(
            user=self.designer,
            project_id=self.other_project.id,
            project_floor_id=self.other_project_floor.id,
        )
        self.assert_error(response, 404, "PROJECT_NOT_FOUND")
        self.assertEqual(self.count_floor_plans(), before)
        self.assertEqual(self.stored_files(), ())

    def test_floor_from_another_project_returns_404(self) -> None:
        response = self.post_upload(
            user=self.designer,
            project_floor_id=self.second_project_floor.id,
        )
        self.assert_error(response, 404, "PROJECT_FLOOR_NOT_FOUND")
        self.assertEqual(self.stored_files(), ())

    def test_missing_project_returns_404(self) -> None:
        response = self.post_upload(user=self.designer, project_id=999999999)
        self.assert_error(response, 404, "PROJECT_NOT_FOUND")

    def test_missing_floor_returns_404(self) -> None:
        response = self.post_upload(
            user=self.designer,
            project_floor_id=999999999,
        )
        self.assert_error(response, 404, "PROJECT_FLOOR_NOT_FOUND")

    def test_forged_owner_and_role_values_do_not_grant_access(self) -> None:
        self._set_session(
            self.designer,
            role="ADMIN",
            owner_id=self.other_designer.id,
        )
        response = self.post_upload(
            project_id=self.other_project.id,
            project_floor_id=self.other_project_floor.id,
            query=f"?owner_id={self.other_designer.id}&role=ADMIN",
            headers={"X-Owner-ID": str(self.other_designer.id), "X-Role": "ADMIN"},
        )
        self.assert_error(response, 404, "PROJECT_NOT_FOUND")
        self.assertEqual(self.stored_files(), ())

    def test_missing_file_returns_422(self) -> None:
        response = self.post_upload(user=self.designer, include_file=False)
        self.assertEqual(response.status_code, 422)

    def test_missing_project_floor_id_returns_422(self) -> None:
        response = self.post_upload(user=self.designer, include_floor=False)
        self.assertEqual(response.status_code, 422)

    def test_non_integer_project_floor_id_returns_422(self) -> None:
        response = self.post_upload(user=self.designer, project_floor_id="not-an-id")
        self.assertEqual(response.status_code, 422)

    def test_non_positive_project_ids_return_422(self) -> None:
        for project_id in (0, -1):
            with self.subTest(project_id=project_id):
                response = self.post_upload(
                    user=self.designer,
                    project_id=project_id,
                )
                self.assertEqual(response.status_code, 422)

    def test_non_positive_floor_ids_return_422(self) -> None:
        for project_floor_id in (0, -1):
            with self.subTest(project_floor_id=project_floor_id):
                response = self.post_upload(
                    user=self.designer,
                    project_floor_id=project_floor_id,
                )
                self.assertEqual(response.status_code, 422)

    def test_unsupported_extension_returns_415(self) -> None:
        response = self.post_upload(user=self.designer, filename="floor-plan.gif")
        self.assert_error(response, 415, "UPLOAD_EXTENSION_UNSUPPORTED")

    def test_mime_mismatch_returns_415(self) -> None:
        response = self.post_upload(user=self.designer, mime_type="image/png")
        self.assert_error(response, 415, "UPLOAD_MIME_EXTENSION_MISMATCH")

    def test_disguised_content_returns_415(self) -> None:
        response = self.post_upload(user=self.designer, content=self.png)
        self.assert_error(response, 415, "UPLOAD_CONTENT_MISMATCH")

    def test_empty_file_returns_422(self) -> None:
        response = self.post_upload(user=self.designer, content=b"")
        self.assert_error(response, 422, "UPLOAD_EMPTY")

    def test_corrupt_image_returns_422(self) -> None:
        response = self.post_upload(
            user=self.designer,
            content=b"\xff\xd8\xffcorrupt",
        )
        self.assert_error(response, 422, "UPLOAD_IMAGE_CORRUPT")

    def test_corrupt_pdf_returns_422(self) -> None:
        response = self.post_upload(
            user=self.designer,
            filename="floor-plan.pdf",
            mime_type="application/pdf",
            content=b"%PDF-corrupt",
        )
        self.assert_error(response, 422, "UPLOAD_PDF_CORRUPT")

    def test_encrypted_pdf_returns_422(self) -> None:
        response = self.post_upload(
            user=self.designer,
            filename="floor-plan.pdf",
            mime_type="application/pdf",
            content=self.encrypted_pdf,
        )
        self.assert_error(response, 422, "UPLOAD_PDF_ENCRYPTED")

    def test_oversized_upload_returns_413(self) -> None:
        oversized = self.jpeg + b"x" * (1024 * 1024)
        response = self.post_upload(user=self.designer, content=oversized)
        self.assert_error(response, 413, "UPLOAD_TOO_LARGE")

    def test_overlong_original_filename_returns_422(self) -> None:
        response = self.post_upload(
            user=self.designer,
            filename=f"{'x' * 252}.jpg",
        )
        self.assert_error(response, 422, "ORIGINAL_FILENAME_TOO_LONG")

    def test_route_reads_only_configured_limit_plus_one(self) -> None:
        read_sizes: list[int] = []
        original_read = StarletteUploadFile.read

        async def tracked_read(upload_file, size=-1):
            read_sizes.append(size)
            return await original_read(upload_file, size)

        with patch.object(StarletteUploadFile, "read", new=tracked_read):
            response = self.post_upload(user=self.designer)

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(read_sizes, [1024 * 1024 + 1])

    def test_storage_failure_returns_sanitized_503(self) -> None:
        from app.services.floor_plan_storage import FloorPlanStorageError

        error = FloorPlanStorageError(
            "ORIGINAL_FILE_WRITE_FAILED",
            "The original floor-plan file could not be stored.",
        )
        with patch(
            "app.services.floor_plan_upload.store_floor_plan_upload",
            side_effect=error,
        ):
            response = self.post_upload(user=self.designer)
        self.assert_error(response, 503, "ORIGINAL_FILE_WRITE_FAILED")

    def test_database_failure_returns_503_and_removes_stored_file(self) -> None:
        before = self.count_floor_plans()
        with patch(
            "app.services.floor_plan_storage.add_floor_plan",
            side_effect=RuntimeError("private SQL failure"),
        ):
            response = self.post_upload(user=self.designer)

        self.assert_error(response, 503, "FLOOR_PLAN_RECORD_FAILED")
        self.assertEqual(self.count_floor_plans(), before)
        self.assertEqual(self.stored_files(), ())
        self.assertNotIn("SQL", response.text)

    def test_second_upload_preserves_first_and_uses_distinct_file(self) -> None:
        first_response = self.post_upload(user=self.designer)
        self.assertEqual(first_response.status_code, 201, first_response.text)
        first = self.database_session.get(FloorPlan, first_response.json()["id"])
        first_path = self.test_upload_directory / Path(first.storage_path)
        first_bytes = first_path.read_bytes()

        second_response = self.post_upload(user=self.designer)
        self.assertEqual(second_response.status_code, 201, second_response.text)
        second = self.database_session.get(FloorPlan, second_response.json()["id"])

        self.assertNotEqual(first.storage_path, second.storage_path)
        self.assertEqual(first_path.read_bytes(), first_bytes)

    def test_client_path_traversal_cannot_escape_upload_directory(self) -> None:
        response = self.post_upload(
            user=self.designer,
            filename="../../outside.jpg",
        )
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(body["original_filename"], "outside.jpg")
        floor_plan = self.database_session.get(FloorPlan, body["id"])
        stored_path = (self.test_upload_directory / floor_plan.storage_path).resolve()
        self.assertEqual(
            stored_path.parent,
            (self.test_upload_directory / "originals").resolve(),
        )

    def test_upload_file_is_closed_after_success(self) -> None:
        closed_states: list[bool] = []
        original_close = StarletteUploadFile.close

        async def tracked_close(upload_file):
            await original_close(upload_file)
            closed_states.append(upload_file.file.closed)

        with patch.object(StarletteUploadFile, "close", new=tracked_close):
            response = self.post_upload(user=self.designer)

        self.assertEqual(response.status_code, 201, response.text)
        self.assertGreaterEqual(len(closed_states), 1)
        self.assertTrue(all(closed_states))

    def test_upload_file_is_closed_after_validation_failure(self) -> None:
        closed_states: list[bool] = []
        original_close = StarletteUploadFile.close

        async def tracked_close(upload_file):
            await original_close(upload_file)
            closed_states.append(upload_file.file.closed)

        with patch.object(StarletteUploadFile, "close", new=tracked_close):
            response = self.post_upload(user=self.designer, content=b"")

        self.assertEqual(response.status_code, 422, response.text)
        self.assertGreaterEqual(len(closed_states), 1)
        self.assertTrue(all(closed_states))

    def test_upload_file_is_closed_after_configuration_failure(self) -> None:
        closed_states: list[bool] = []
        original_close = StarletteUploadFile.close

        async def tracked_close(upload_file):
            await original_close(upload_file)
            closed_states.append(upload_file.file.closed)

        with (
            patch.object(self.settings, "upload_dir", None),
            patch.object(StarletteUploadFile, "close", new=tracked_close),
        ):
            response = self.post_upload(user=self.designer)

        self.assert_error(response, 503, "UPLOAD_CONFIGURATION_UNAVAILABLE")
        self.assertGreaterEqual(len(closed_states), 1)
        self.assertTrue(all(closed_states))

    def test_openapi_preserves_upload_and_declares_only_approved_operations(
        self,
    ) -> None:
        paths = self.application.openapi()["paths"]
        endpoint = paths["/api/projects/{project_id}/floor-plans"]
        self.assertEqual(set(endpoint), {"get", "post"})
        self.assertIn("multipart/form-data", endpoint["post"]["requestBody"]["content"])
        self.assertIn("post", paths["/api/projects"])
        self.assertIn("get", paths["/api/projects"])
        self.assertIn("get", paths["/api/projects/{project_id}"])
        processing_endpoint = paths[
            "/api/floor-plans/{floor_plan_id}/process"
        ]
        self.assertEqual(set(processing_endpoint), {"post"})
        status_endpoint = paths["/api/processing-jobs/{job_id}"]
        self.assertEqual(
            set(status_endpoint),
            {"get"},
        )


if __name__ == "__main__":
    unittest.main()
