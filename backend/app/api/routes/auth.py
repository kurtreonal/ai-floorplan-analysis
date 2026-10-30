import logging
import secrets
import time
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

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
from app.schemas.client_workflow import PasswordLogin, CredentialUpdate, LinkAccount, ContactEmailUpdate
from app.models.client_workflow import LocalCredential, LinkedIdentity
from sqlalchemy import select, delete
from app.services.local_accounts import (require_same_origin, throttle, sign_in, credential_for,
    reauthenticate, hash_password, link_identity, session_revision, invalidate_sessions, account_enabled, lock_account)
from app.services.authentication import (
    AuthenticationServiceError,
    AccountNotProvisioned,
    ExternalOIDCIdentity,
    resolve_external_user,
)


router = APIRouter(prefix="/api/auth", tags=["authentication"])
logger = logging.getLogger(__name__)


@router.post('/password-login', response_model=None)
def password_login(data: PasswordLogin, request: Request, db: Session = Depends(get_db)):
    require_same_origin(request)
    throttle(request, data.username)
    try:
        user = sign_in(db, data)
        result = current_user(user)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, 'Sign-in is temporarily unavailable.') from None
    from app.services.email_security import needs_verification, pending_signin
    if needs_verification(db, request, user):
        return pending_signin(db, request, user)
    request.session.clear()
    request.session.update(user_id=user.id, authenticated_at=time.time(), account_revision=session_revision(db, user.id))
    return result


@router.get('/methods')
def account_methods(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    credential = credential_for(db, user.id)
    linked = db.scalar(select(LinkedIdentity.id).where(LinkedIdentity.user_id == user.id))
    return {'username': credential.username if credential else None, 'email': user.email,
            'google_linked': (user.role.name == 'ADMIN' and user.oauth_provider not in ('local', '')) or linked is not None}


@router.put('/credentials')
def save_credentials(data: CredentialUpdate, request: Request, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    require_same_origin(request)
    lock_account(db, user.id)
    if credential_for(db, user.id) is None and user.role.name != 'ADMIN':
        raise HTTPException(403, 'Ask Admin to configure your initial username and password. You can then change them here.')
    reauthenticate(db, request, user, data.current_password)
    from app.services.local_accounts import username_taken,flush_credentials
    if username_taken(db,data.username,exclude_user_id=user.id):
        raise HTTPException(409, 'This username is already in use.')
    credential = credential_for(db, user.id)
    if credential is None:
        credential = LocalCredential(user_id=user.id, username=data.username, password_hash='')
        db.add(credential)
    credential.username = data.username
    credential.password_hash = hash_password(data.password)
    credential.failed_attempts = 0
    credential.locked_until = None
    access = invalidate_sessions(db, user.id)
    flush_credentials(db)
    db.commit()
    request.session['authenticated_at'] = time.time()
    request.session['account_revision'] = access.session_revision
    return {'status': 'saved'}


@router.post('/link-google')
def begin_link(data: LinkAccount, request: Request, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    require_same_origin(request)
    lock_account(db, user.id)
    if credential_for(db, user.id) is None and user.role.name != 'ADMIN':
        raise HTTPException(403, 'Ask Admin to configure your username and password first.')
    _get_active_configuration(request)
    reauthenticate(db, request, user, data.current_password)
    request.session['link_user_id'] = user.id
    request.session['link_started_at'] = time.time()
    request.session['link_revision'] = session_revision(db, user.id)
    return {'status': 'ready'}


@router.put('/contact-email')
def contact_email(data: ContactEmailUpdate, request: Request, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    require_same_origin(request)
    lock_account(db, user.id)
    reauthenticate(db, request, user, data.current_password)
    user.email = data.email
    db.commit()
    return {'email': user.email}


@router.delete('/link-google')
def unlink_google(data: LinkAccount, request: Request, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    require_same_origin(request)
    lock_account(db, user.id)
    if credential_for(db, user.id) is None:
        raise HTTPException(409, 'Set a username and password before disconnecting your only sign-in method.')
    reauthenticate(db, request, user, data.current_password)
    db.execute(delete(LinkedIdentity).where(LinkedIdentity.user_id == user.id))
    if user.oauth_provider != 'local':
        user.oauth_provider, user.oauth_subject = 'local', secrets.token_hex(32)
    access = invalidate_sessions(db, user.id)
    db.commit()
    request.session['account_revision'] = access.session_revision
    return {'status': 'disconnected'}


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


@router.post("/logout")
def logout(request: Request) -> dict[str, str]:
    session_data = request.scope.get("session")
    if session_data is not None:
        session_data.clear()
    return {"status": "ok"}


@router.get("/login", name="oauth_login")
async def oauth_login(request: Request) -> RedirectResponse:
    configuration = _get_active_configuration(request)
    state_value = secrets.token_urlsafe(32)
    nonce_value = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state_value
    if request.session.get('link_user_id') != request.session.get('user_id') or time.time() - request.session.get('link_started_at', 0) > 300:
        request.session.pop('link_user_id', None)

    try:
        client = create_oauth_client(configuration)
        return await client.authorize_redirect(
            request,
            str(configuration.redirect_uri),
            state=state_value,
            nonce=nonce_value,
            prompt="select_account",
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
        linking_user_id = request.session.pop('link_user_id', None)
        if linking_user_id is not None:
            if linking_user_id != request.session.get('user_id') or time.time() - request.session.get('link_started_at', 0) > 300:
                raise HTTPException(403, 'Account linking expired. Start again from User settings.')
            user = lock_account(database_session, linking_user_id)
            if user is None or not account_enabled(database_session, user.id) or request.session.get('link_revision', 0) != session_revision(database_session, user.id):
                raise HTTPException(403, 'Account linking expired.')
            link_identity(database_session, user, identity)
        else:
            user, _created = resolve_external_user(database_session, identity)
        database_session.commit()
    except ValidationError:
        database_session.rollback()
        raise _authentication_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="OIDC_IDENTITY_INVALID",
            message="The validated OIDC identity contains invalid profile data.",
        ) from None
    except AccountNotProvisioned:
        database_session.rollback()
        request.session.clear()
        raise _authentication_error(status_code=403, code='ACCOUNT_NOT_PROVISIONED',
            message='Ask Admin for a VED account. Sign in with your username and password, then connect Google from User settings.') from None
    except (AuthenticationServiceError, SQLAlchemyError) as error:
        database_session.rollback()
        args=getattr(getattr(error,'orig',None),'args',())
        database_code=args[0] if args and type(args[0]) is int else None
        logger.warning('OAuth user lookup failed: %s; database code=%s',type(error).__name__,database_code)
        raise _authentication_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="AUTH_USER_RESOLUTION_FAILED",
            message="The local user record could not be resolved.",
        ) from None

    from app.services.email_security import needs_verification, pending_signin
    frontend = urlsplit(str(request.app.state.settings.frontend_url))
    if not linking_user_id and needs_verification(database_session, request, user):
        pending_signin(database_session, request, user)
        return RedirectResponse(url=urlunsplit((frontend.scheme, frontend.netloc, frontend.path or '/', frontend.query, '/signin?verify=required')), status_code=303)
    request.session.clear()
    request.session["user_id"] = user.id
    request.session['authenticated_at'] = time.time()
    request.session['account_revision'] = session_revision(database_session, user.id)
    del token
    frontend = urlsplit(str(request.app.state.settings.frontend_url))
    return RedirectResponse(
        url=urlunsplit((frontend.scheme,frontend.netloc,frontend.path or '/',frontend.query,
                       '/app/settings' if linking_user_id else '/app')),
        status_code=status.HTTP_303_SEE_OTHER,
    )
