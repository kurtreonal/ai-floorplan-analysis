import secrets
from collections.abc import Mapping
from typing import Any

import httpx
from authlib.integrations.base_client.errors import OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from joserfc.errors import JoseError
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.api.dependencies import get_current_user
from app.core.config import OAuthOIDCConfiguration
from app.core.database import get_db
from app.core.oauth import create_oauth_client
from app.models import User
from app.schemas.auth import CurrentUserResponse
from app.services.authentication import (
    AuthenticationServiceError,
    ExternalOIDCIdentity,
    resolve_external_user,
)


router = APIRouter(prefix="/api/auth", tags=["authentication"])


def _authentication_error(
    *,
    status_code: int,
    code: str,
    message: str,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code,
                "message": message,
                "details": {},
            }
        },
    )


def _get_active_configuration(request: Request) -> OAuthOIDCConfiguration:
    configuration = getattr(request.app.state, "oauth_oidc_configuration", None)
    if configuration is None:
        configuration_error = getattr(
            request.app.state,
            "oauth_oidc_configuration_error",
            "OAuth/OIDC configuration is unavailable.",
        )
        raise _authentication_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="AUTH_CONFIGURATION_ERROR",
            message=configuration_error,
        )
    return configuration


def _optional_string_claim(userinfo: Mapping[str, Any], name: str) -> str | None:
    value = userinfo.get(name)
    return value if isinstance(value, str) and value else None


@router.get("/me", response_model=CurrentUserResponse)
def current_user(user: User = Depends(get_current_user)) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=user.id,
        display_name=user.display_name,
        email=user.email,
        avatar_url=user.avatar_url,
        role=user.role.name,
    )


@router.get("/login", name="oauth_login")
async def oauth_login(request: Request) -> RedirectResponse:
    configuration = _get_active_configuration(request)
    state_value = secrets.token_urlsafe(32)
    nonce_value = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state_value

    try:
        client = create_oauth_client(configuration)
        return await client.authorize_redirect(
            request,
            str(configuration.redirect_uri),
            state=state_value,
            nonce=nonce_value,
        )
    except (OAuthError, httpx.HTTPError, KeyError, RuntimeError):
        request.session.pop("oauth_state", None)
        raise _authentication_error(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="OAUTH_PROVIDER_UNAVAILABLE",
            message="The configured identity provider is unavailable.",
        ) from None


@router.get("/callback", name="oauth_callback")
async def oauth_callback(
    request: Request,
    database_session: Session = Depends(get_db),
) -> RedirectResponse:
    configuration = _get_active_configuration(request)
    returned_state = request.query_params.get("state")
    expected_state = request.session.pop("oauth_state", None)
    if (
        not returned_state
        or not expected_state
        or not secrets.compare_digest(returned_state, expected_state)
    ):
        raise _authentication_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="OAUTH_STATE_INVALID",
            message="The OAuth callback state is missing or invalid.",
        )

    if request.query_params.get("error"):
        raise _authentication_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="OAUTH_PROVIDER_REJECTED",
            message="The identity provider did not authorize the request.",
        )
    if not request.query_params.get("code"):
        raise _authentication_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="OAUTH_CODE_MISSING",
            message="The OAuth callback did not include an authorization code.",
        )

    try:
        client = create_oauth_client(configuration)
        token = await client.authorize_access_token(request)
    except (JoseError, OAuthError, httpx.HTTPError, KeyError, RuntimeError):
        raise _authentication_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="OAUTH_CALLBACK_FAILED",
            message="The OAuth/OIDC callback could not be validated.",
        ) from None

    userinfo = token.get("userinfo")
    if not isinstance(userinfo, Mapping):
        raise _authentication_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="OIDC_IDENTITY_INVALID",
            message="The provider did not return a validated OIDC identity.",
        )

    subject = _optional_string_claim(userinfo, "sub")
    if subject is None:
        raise _authentication_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="OIDC_SUBJECT_MISSING",
            message="The validated OIDC identity has no provider subject.",
        )

    try:
        identity = ExternalOIDCIdentity(
            provider=configuration.provider,
            subject=subject,
            email=_optional_string_claim(userinfo, "email"),
            display_name=(
                _optional_string_claim(userinfo, "name")
                or _optional_string_claim(userinfo, "preferred_username")
            ),
            avatar_url=_optional_string_claim(userinfo, "picture"),
        )
        user, _created = resolve_external_user(database_session, identity)
        database_session.commit()
    except ValidationError:
        database_session.rollback()
        raise _authentication_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="OIDC_IDENTITY_INVALID",
            message="The validated OIDC identity contains invalid profile data.",
        ) from None
    except (AuthenticationServiceError, SQLAlchemyError):
        database_session.rollback()
        raise _authentication_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="AUTH_USER_RESOLUTION_FAILED",
            message="The local user record could not be resolved.",
        ) from None

    request.session.clear()
    request.session["user_id"] = user.id
    del token
    return RedirectResponse(
        url=str(request.app.state.settings.frontend_url),
        status_code=status.HTTP_303_SEE_OTHER,
    )
