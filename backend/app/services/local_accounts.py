"""Password sign-in shares the existing signed session with OIDC."""
import hashlib
import hmac
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request
from sqlalchemy import select,func
from sqlalchemy.exc import IntegrityError

from app.core.config import get_cors_allowed_origins
from app.models import User
from app.models.client_workflow import LocalCredential, LinkedIdentity, AccountAccess
from app.repositories.user_repository import find_role_by_name, find_user_by_external_identity

_attempts = {}
_attempt_lock = threading.Lock()


def require_same_origin(request: Request):
    origin = request.headers.get('origin')
    allowed = get_cors_allowed_origins(request.app.state.settings)
    if origin not in allowed:
        raise HTTPException(403, 'Open this action from the VED application.')


def throttle(request: Request, username: str):
    # Bound both requests per address and per account, including unknown usernames.
    now = time.monotonic()
    keys = (('ip', request.client.host if request.client else 'unknown'), ('user', username))
    with _attempt_lock:
        for key in list(_attempts):
            if now - _attempts[key][0] > 900:
                del _attempts[key]
        if len(_attempts) > 10000:
            raise HTTPException(429, 'Sign-in is busy. Try again later.')
        for key, limit in zip(keys, (40, 10)):
            count = _attempts.get(key, (now, 0))
            if count[1] >= limit:
                raise HTTPException(429, 'Too many attempts. Try again in 15 minutes.')
        for key in keys:
            start, count = _attempts.get(key, (now, 0))
            _attempts[key] = (start, count + 1)


def hash_password(password: str, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=131072, r=8, p=1,
                            maxmem=256 * 1024 * 1024, dklen=32)
    return f'scrypt$131072$8$1${salt.hex()}${digest.hex()}'


def verify_password(password, encoded):
    if not encoded:
        # Equal work for unknown accounts; no plaintext or reversible passwords.
        hash_password(password, bytes(16))
        return False
    try:
        algorithm, n, r, p, salt, digest = encoded.split('$')
        if (algorithm, n, r, p) != ('scrypt', '131072', '8', '1'):
            return False
        actual = hash_password(password, bytes.fromhex(salt)).rsplit('$', 1)[1]
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError):
        return False


def credential_for(db, user_id):
    return db.get(LocalCredential, user_id)


def username_taken(db,username,exclude_user_id=None):
    query=select(LocalCredential.user_id).where(func.lower(LocalCredential.username)==username.strip().lower())
    if exclude_user_id is not None:query=query.where(LocalCredential.user_id!=exclude_user_id)
    return db.scalar(query.limit(1)) is not None


def flush_credentials(db):
    try:db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'This username is already in use. Choose another username.') from None


def lock_account(db, user_id):
    return db.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))


def access_for(db, user_id):
    return db.get(AccountAccess, user_id)


def account_enabled(db, user_id):
    access = access_for(db, user_id)
    return not access or not access.disabled


def session_revision(db, user_id):
    access = access_for(db, user_id)
    return access.session_revision if access else 0


def invalidate_sessions(db, user_id, admin_id=None):
    access = db.scalar(select(AccountAccess).where(AccountAccess.user_id == user_id).with_for_update())
    if access is None:
        access = AccountAccess(user_id=user_id, disabled=False, session_revision=0)
        db.add(access)
    access.session_revision += 1
    access.updated_by_user_id = admin_id
    db.flush()
    return access


def reauthenticate(db, request, user, password):
    credential = credential_for(db, user.id)
    if credential:
        throttle(request, credential.username)
        if not password or not verify_password(password, credential.password_hash):
            raise HTTPException(403, 'Enter your current password to continue.')
    elif time.time() - request.session.get('authenticated_at', 0) > 300:
        raise HTTPException(403, 'Sign in with Google again, then retry within five minutes.')


def sign_in(db, data):
    matches=db.scalars(select(LocalCredential).where(func.lower(LocalCredential.username)==data.username).with_for_update().limit(2)).all()
    credential=matches[0] if len(matches)==1 else None
    valid = verify_password(data.password, credential.password_hash if credential else None)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if credential and credential.locked_until and credential.locked_until > now:
        valid = False
    if credential and not account_enabled(db, credential.user_id):
        valid = False
    if not valid:
        if credential:
            credential.failed_attempts += 1
            if credential.failed_attempts >= 10:
                credential.locked_until = now + timedelta(minutes=15)
            db.commit()
        raise HTTPException(401, 'Username or password is incorrect.')
    credential.failed_attempts = 0
    credential.locked_until = None
    db.flush()
    return db.get(User, credential.user_id)


def create_account(db, data):
    from app.services.intake_schema import require_fields
    require_fields(db,(User,'profile_details'))
    if username_taken(db,data.username):
        raise HTTPException(409, 'This username is already in use.')
    role = find_role_by_name(db, name=data.role)
    if role is None:
        raise HTTPException(503, 'Account roles have not been provisioned.')
    user = User(oauth_provider='local', oauth_subject=secrets.token_hex(32),
                display_name=data.display_name.strip(), email=data.email, role_id=role.id,
                profile_details={key:getattr(data,key) for key in ('first_name','middle_name','last_name','phone_number','location')})
    db.add(user)
    db.flush()
    db.add(LocalCredential(user_id=user.id, username=data.username, password_hash=hash_password(data.password)))
    flush_credentials(db)
    return user


def create_client(db, data):
    return create_account(db, data.model_copy(update={'role': 'CLIENT'}))


def link_identity(db, user, identity):
    if not account_enabled(db, user.id) or (user.role.name != 'ADMIN' and credential_for(db, user.id) is None):
        raise HTTPException(403, 'Ask Admin to set up your username and password first.')
    existing = find_user_by_external_identity(db, provider=identity.provider, subject=identity.subject)
    linked = db.scalar(select(LinkedIdentity).where(LinkedIdentity.provider == identity.provider,
                                                   LinkedIdentity.subject == identity.subject))
    if (existing and existing.id != user.id) or (linked and linked.user_id != user.id):
        raise HTTPException(409, 'This Google account already belongs to another VED account.')
    if not linked:
        db.add(LinkedIdentity(user_id=user.id, provider=identity.provider, subject=identity.subject))
    db.flush()
