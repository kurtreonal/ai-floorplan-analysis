"""Account selection uses the existing OIDC state/nonce flow, without a DB."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse

from app.api.routes.auth import router
from app.core.config import OAuthOIDCConfiguration
from app.core.database import get_db


@pytest.fixture
def client():
    application = FastAPI()
    application.state.oauth_oidc_configuration = OAuthOIDCConfiguration(
        provider="synthetic",
        client_id="account-selection-test-client",
        client_secret="account-selection-test-secret",
        redirect_uri="http://localhost:8000/api/auth/callback",
        discovery_url="https://provider.invalid/.well-known/openid-configuration",
        scopes=("openid", "profile", "email"),
        session_secret="account-selection-test-session-secret",
    )
    application.add_middleware(
        SessionMiddleware,
        secret_key="account-selection-test-session-secret",
        session_cookie="ved_session",
    )
    application.include_router(router)

    def no_database():
        yield None

    application.dependency_overrides[get_db] = no_database
    with TestClient(application) as test_client:
        yield test_client


def test_login_always_requests_explicit_account_selection(client):
    provider = AsyncMock()
    provider.authorize_redirect.return_value = RedirectResponse(
        "https://provider.invalid/authorize"
    )
    with patch("app.api.routes.auth.create_oauth_client", return_value=provider):
        first = client.get("/api/auth/login", follow_redirects=False)
        second = client.get(
            "/api/auth/login?prompt=none&login_hint=previous-account",
            follow_redirects=False,
        )
    assert first.status_code == second.status_code == 307
    calls = provider.authorize_redirect.await_args_list
    for call in calls:
        assert call.kwargs["prompt"] == "select_account"
        assert len(call.kwargs["state"]) >= 32
        assert len(call.kwargs["nonce"]) >= 32
        assert "login_hint" not in call.kwargs
    assert calls[0].kwargs["state"] != calls[1].kwargs["state"]
    assert calls[0].kwargs["nonce"] != calls[1].kwargs["nonce"]
    assert "ved_session" in client.cookies


def test_account_selection_does_not_bypass_callback_state_check(client):
    provider = AsyncMock()
    provider.authorize_redirect.return_value = RedirectResponse(
        "https://provider.invalid/authorize"
    )
    with patch("app.api.routes.auth.create_oauth_client", return_value=provider):
        client.get("/api/auth/login", follow_redirects=False)
        response = client.get("/api/auth/callback?state=incorrect&code=synthetic")
    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "OAUTH_STATE_INVALID"
    provider.authorize_access_token.assert_not_awaited()


def test_logout_clears_pending_login_without_changing_authorization(client):
    provider = AsyncMock()
    provider.authorize_redirect.return_value = RedirectResponse(
        "https://provider.invalid/authorize"
    )
    with patch("app.api.routes.auth.create_oauth_client", return_value=provider):
        client.get("/api/auth/login", follow_redirects=False)
        state = provider.authorize_redirect.await_args.kwargs["state"]
        assert client.post("/api/auth/logout").json() == {"status": "ok"}
        response = client.get(f"/api/auth/callback?state={state}&code=synthetic")
    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "OAUTH_STATE_INVALID"
    provider.authorize_access_token.assert_not_awaited()
