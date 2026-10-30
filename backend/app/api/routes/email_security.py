import hashlib
import secrets
import time
from datetime import timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field,model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models import User
from app.models.account_security import AccountEmail, TrustedDevice
from app.services import email_security as service
from app.services.local_accounts import require_same_origin, reauthenticate, throttle, lock_account, session_revision, invalidate_sessions, account_enabled

router = APIRouter(prefix='/api/auth', tags=['email security'])


class EnrollEmail(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: str = Field(max_length=254)
    channel: Literal['primary', 'backup']
    current_password: str | None = Field(default=None, max_length=256, repr=False)


class SendCode(BaseModel):
    model_config = ConfigDict(extra='forbid')
    channel: Literal['primary', 'backup'] = 'primary'


class Recover(BaseModel):
    model_config=ConfigDict(extra='forbid')
    email: str = Field(min_length=3,max_length=254)


class VerifyCode(BaseModel):
    model_config = ConfigDict(extra='forbid')
    challenge_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    code: str = Field(pattern=r'^\d{5}$', repr=False)
    remember_device: bool = False


class ResetPassword(BaseModel):
    model_config = ConfigDict(extra='forbid')
    password: str = Field(min_length=15, max_length=256, repr=False)
    confirm_password: str = Field(min_length=15,max_length=256,repr=False)

    @model_validator(mode='after')
    def matching_passwords(self):
        if self.password!=self.confirm_password:raise ValueError('The passwords do not match.')
        return self


@router.get('/emails')
def emails(request: Request, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    rows = service.addresses(db, user.id)
    return {'addresses': [{'email': x.email, 'primary': x.primary, 'verified': x.verified} for x in rows if x.verified],
        'verification_enabled': any(x.verified for x in rows), 'delivery_available': service.delivery_ready(request.app.state.settings),
        'delivery_missing_settings': service.missing_delivery_settings(request.app.state.settings), 'contact_email': user.email}


@router.post('/emails', status_code=201)
def enroll(data: EnrollEmail, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_same_origin(request); lock_account(db, user.id)
    reauthenticate(db, request, user, data.current_password)
    email = service.normalize_email(data.email)
    if any(x.email == email and x.verified and x.primary != (data.channel == 'primary') for x in service.addresses(db, user.id)):
        raise HTTPException(422, 'Use a different address for your backup email.')
    record = db.scalar(select(AccountEmail).where(AccountEmail.user_id == user.id, AccountEmail.email == email))
    if record is None:
        record = AccountEmail(user_id=user.id, email=email, verified=False, primary=data.channel == 'primary')
        db.add(record); db.flush()
    return service.issue(db, request, record, 'verify_primary' if data.channel == 'primary' else 'verify_backup')


@router.get('/pending')
def pending(request: Request, db: Session = Depends(get_db)):
    user = service.pending_user(db, request)
    return {'verification_required': True, 'channels': [{'channel': 'primary' if x.primary else 'backup', 'email': service.mask(x.email)} for x in service.addresses(db, user.id) if x.verified]}


@router.post('/send-code')
def signin_code(data: SendCode, request: Request, db: Session = Depends(get_db)):
    require_same_origin(request)
    user = service.pending_user(db, request)
    email = next((x for x in service.addresses(db, user.id) if x.verified and x.primary == (data.channel == 'primary')), None)
    if not email:
        raise HTTPException(422, 'This sign-in email has not been verified. Choose another method or contact Admin.')
    return service.issue(db, request, email, 'signin')


@router.post('/recover')
def recover(data: Recover, request: Request, db: Session = Depends(get_db)):
    require_same_origin(request)
    address=service.normalize_email(data.email)
    throttle(request,'recover:'+hashlib.sha256(address.encode()).hexdigest())
    if not service.delivery_ready(request.app.state.settings):
        raise HTTPException(503, 'Email recovery requires SMTP setup by Admin. Contact Admin for a password reset.')
    email=service.recovery_address(db,address)
    if email:
        result = service.issue(db, request, email, 'reset_password')
    else:
        result = {'challenge_id': secrets.token_hex(16), 'expires_in': 300, 'resend_after': 60}
        request.session['email_challenge_id'] = result['challenge_id']
    return {key: value for key, value in result.items() if key != 'destination'}


@router.post('/verify-code')
def verify(data: VerifyCode, request: Request, db: Session = Depends(get_db)):
    require_same_origin(request)
    challenge = service.consume(db, request, data.challenge_id, data.code)
    if challenge.purpose.startswith('verify_'):
        user = get_current_user(request, db)
        if user.id != challenge.user_id:
            raise HTTPException(403, 'Start email verification again from your account.')
        primary = challenge.purpose == 'verify_primary'
        for email in service.addresses(db, user.id):
            if email.id == challenge.email_id:
                email.verified, email.primary = True, primary
                if primary:
                    user.email = email.email
            elif email.primary == primary:
                email.verified = False
        access = invalidate_sessions(db, user.id)
        db.commit(); request.session['account_revision'] = access.session_revision
        request.session.pop('email_challenge_id', None)
        return {'status': 'verified'}
    if challenge.purpose == 'reset_password':
        request.session.clear()
        request.session.update(reset_user=challenge.user_id, reset_revision=session_revision(db, challenge.user_id), reset_expires=time.time() + 300)
        db.commit()
        return {'status': 'password_reset_ready'}
    user = service.pending_user(db, request)
    if challenge.purpose != 'signin' or user.id != challenge.user_id:
        raise HTTPException(403, 'Start sign-in again.')
    revision = session_revision(db, user.id)
    request.session.clear(); request.session.update(user_id=user.id, authenticated_at=time.time(), account_revision=revision)
    response = JSONResponse({'status': 'authenticated'})
    if data.remember_device:
        token = secrets.token_urlsafe(32)
        db.add(TrustedDevice(token_digest=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id, account_revision=revision, expires_at=service.now() + timedelta(days=30)))
        response.set_cookie('ved_trusted_device', token, max_age=30 * 86400, httponly=True, secure=request.app.state.settings.app_env == 'production', samesite='lax', path='/')
    db.commit()
    return response


@router.post('/reset-password')
def reset(data: ResetPassword, request: Request, db: Session = Depends(get_db)):
    require_same_origin(request)
    user_id = request.session.get('reset_user')
    user = lock_account(db, user_id) if type(user_id) is int else None
    if not user or request.session.get('reset_expires', 0) < time.time() or request.session.get('reset_revision') != session_revision(db, user.id):
        raise HTTPException(403, 'Request a new password recovery code.')
    from app.services.local_accounts import account_enabled
    if not account_enabled(db, user.id):
        raise HTTPException(403, 'Contact Admin about your account access.')
    service.reset_password(db, user, data.password)
    request.session.clear()
    return {'status': 'password_reset'}
