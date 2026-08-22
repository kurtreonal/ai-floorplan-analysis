import json
import unittest
from base64 import b64encode
from uuid import uuid4

from fastapi import Depends
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_roles
from app.core.config import Settings, get_settings
from app.core.database import get_db, get_engine
from app.main import create_app
from app.models import Role, User
from app.services.authentication import ExternalOIDCIdentity, resolve_external_user


SESSION_COOKIE = "ved_session"
SESSION_SECRET = "c4-automated-test-session-secret"


class RoleAuthorizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        base_settings = get_settings()
        settings = Settings(
            _env_file=None,
            app_env="development",
            database_url=base_settings.database_url,
            oauth_provider="synthetic",
            oauth_client_id="c4-client",
            oauth_client_secret="c4-client-secret",
            oauth_redirect_uri="http://localhost:8000/api/auth/callback",
            oauth_discovery_url=(
                "https://provider.invalid/.well-known/openid-configuration"
            ),
            oauth_scopes="openid profile email",
            session_secret=SESSION_SECRET,
        )

        cls.connection = get_engine().connect()
        cls.transaction = cls.connection.begin()
        cls.database_session = Session(
            bind=cls.connection,
            expire_on_commit=False,
        )
        cls.roles = {
            role.name: role
            for role in cls.database_session.scalars(
                select(Role).where(Role.name.in_(("ADMIN", "DESIGNER")))
            )
        }
        if set(cls.roles) != {"ADMIN", "DESIGNER"}:
            raise RuntimeError("The ADMIN and DESIGNER seed roles are required.")

        marker = uuid4().hex
        cls.admin = User(
            oauth_provider="c4-test",
            oauth_subject=f"admin-{marker}",
            email=f"admin-{marker}@example.test",
            display_name="C4 Admin",
            role_id=cls.roles["ADMIN"].id,
        )
        cls.designer = User(
            oauth_provider="c4-test",
            oauth_subject=f"designer-{marker}",
            email=f"designer-{marker}@example.test",
            display_name="C4 Designer",
            role_id=cls.roles["DESIGNER"].id,
        )
        cls.database_session.add_all((cls.admin, cls.designer))
        cls.database_session.flush()

        cls.application = create_app(settings)

        def override_database():
            yield cls.database_session

        cls.application.dependency_overrides[get_db] = override_database

        @cls.application.get("/_tests/admin-only")
        def admin_only(
            user: User = Depends(require_roles("ADMIN")),
        ) -> dict[str, str]:
            return {"role": user.role.name}

        @cls.application.get("/_tests/designer-accessible")
        def designer_accessible(
            user: User = Depends(require_roles("ADMIN", "DESIGNER")),
        ) -> dict[str, str]:
            return {"role": user.role.name}

        cls.client = TestClient(cls.application)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        cls.database_session.close()
        if cls.transaction.is_active:
            cls.transaction.rollback()
        cls.connection.close()

    def setUp(self) -> None:
        self.admin.role_id = self.roles["ADMIN"].id
        self.designer.role_id = self.roles["DESIGNER"].id
        self.database_session.flush()
        self.client.cookies.clear()

    def _set_session(self, user: User, **untrusted_values: object) -> None:
        payload = {"user_id": user.id, **untrusted_values}
        encoded = b64encode(json.dumps(payload).encode("utf-8"))
        cookie = TimestampSigner(SESSION_SECRET).sign(encoded).decode("utf-8")
        self.client.cookies.set(
            SESSION_COOKIE,
            cookie,
            domain="testserver.local",
        )

    def test_unauthenticated_request_returns_401(self) -> None:
        response = self.client.get("/_tests/admin-only")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json()["detail"]["error"]["code"],
            "AUTHENTICATION_REQUIRED",
        )

    def test_admin_is_allowed_on_admin_only_route(self) -> None:
        self._set_session(self.admin)

        response = self.client.get("/_tests/admin-only")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"role": "ADMIN"})

    def test_designer_is_denied_on_admin_only_route(self) -> None:
        self._set_session(self.designer)

        response = self.client.get("/_tests/admin-only")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"]["error"]["code"],
            "AUTHORIZATION_DENIED",
        )

    def test_admin_and_designer_are_allowed_on_shared_route(self) -> None:
        for user, expected_role in (
            (self.admin, "ADMIN"),
            (self.designer, "DESIGNER"),
        ):
            with self.subTest(role=expected_role):
                self._set_session(user)
                response = self.client.get("/_tests/designer-accessible")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"role": expected_role})

    def test_database_role_change_is_used_on_next_request(self) -> None:
        self._set_session(self.designer, role="ADMIN")
        denied = self.client.get("/_tests/admin-only")
        self.assertEqual(denied.status_code, 403)

        self.designer.role_id = self.roles["ADMIN"].id
        self.database_session.flush()

        allowed = self.client.get("/_tests/admin-only")
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json(), {"role": "ADMIN"})

    def test_client_role_forgery_does_not_grant_admin(self) -> None:
        self._set_session(
            self.designer,
            role="ADMIN",
            roles=["ADMIN"],
            groups=["ADMIN"],
        )

        response = self.client.request(
            "GET",
            "/_tests/admin-only?role=ADMIN",
            headers={"X-Role": "ADMIN"},
            json={"role": "ADMIN"},
        )

        self.assertEqual(response.status_code, 403)

    def test_missing_role_relationship_is_denied(self) -> None:
        malformed_user = User(
            oauth_provider="c4-test",
            oauth_subject="malformed-role",
            role_id=self.roles["ADMIN"].id,
        )
        malformed_user.role = None
        self.application.dependency_overrides[get_current_user] = (
            lambda: malformed_user
        )

        try:
            response = self.client.get("/_tests/admin-only")
        finally:
            self.application.dependency_overrides.pop(get_current_user)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"]["error"]["code"],
            "AUTHORIZATION_DENIED",
        )

    def test_provider_role_claims_do_not_grant_admin(self) -> None:
        identity = ExternalOIDCIdentity.model_validate(
            {
                "provider": "c4-provider-test",
                "subject": uuid4().hex,
                "email": "provider-role@example.test",
                "roles": ["ADMIN"],
                "groups": ["ADMIN"],
                "admin": True,
            }
        )

        user, created = resolve_external_user(self.database_session, identity)

        self.assertTrue(created)
        self.assertEqual(user.role.name, "DESIGNER")

    def test_c2_and_c3_routes_and_current_user_remain_available(self) -> None:
        auth_paths = {
            path
            for path in self.application.openapi()["paths"]
            if path.startswith("/api/auth")
        }
        self.assertEqual(
            auth_paths,
            {
                "/api/auth/login",
                "/api/auth/callback",
                "/api/auth/me",
                "/api/auth/logout",
            },
        )

        unauthenticated = self.client.get("/api/auth/me")
        self.assertEqual(unauthenticated.status_code, 401)

        self._set_session(self.designer, role="ADMIN")
        authenticated = self.client.get("/api/auth/me")
        self.assertEqual(authenticated.status_code, 200)
        self.assertEqual(authenticated.json()["role"], "DESIGNER")
        self.assertNotIn("oauth_subject", authenticated.json())

    def test_logout_invalidates_session_and_role_authorization(self) -> None:
        self._set_session(self.designer)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)
        self.assertEqual(
            self.client.get("/_tests/designer-accessible").status_code,
            200,
        )

        logout = self.client.post("/api/auth/logout")

        self.assertEqual(logout.status_code, 200)
        self.assertEqual(logout.json(), {"status": "ok"})
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        self.assertEqual(
            self.client.get("/_tests/designer-accessible").status_code,
            401,
        )

    def test_logout_is_idempotent_for_unauthenticated_session(self) -> None:
        first = self.client.post("/api/auth/logout")
        second = self.client.post("/api/auth/logout")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), {"status": "ok"})
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json(), {"status": "ok"})

    def test_logout_preserves_credentialed_cors_policy(self) -> None:
        trusted = self.client.post(
            "/api/auth/logout",
            headers={"Origin": "http://localhost:5173"},
        )
        untrusted = self.client.post(
            "/api/auth/logout",
            headers={"Origin": "https://untrusted.example"},
        )

        self.assertEqual(trusted.status_code, 200)
        self.assertEqual(
            trusted.headers.get("access-control-allow-origin"),
            "http://localhost:5173",
        )
        self.assertEqual(
            trusted.headers.get("access-control-allow-credentials"),
            "true",
        )
        self.assertNotIn("access-control-allow-origin", untrusted.headers)


if __name__ == "__main__":
    unittest.main()
