"""Five-digit email verification; codes are never logged, stored or returned."""
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import hashlib
import hmac
import re
import secrets
import smtplib
import ssl
import time

from fastapi import HTTPException
from sqlalchemy import func, select
from app.models import User
from app.models.account_security import AccountEmail, EmailChallenge, TrustedDevice
from app.services.local_accounts import account_enabled, session_revision, invalidate_sessions, credential_for, hash_password


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_email(value):
    value = str(value).strip().lower()
    if len(value) > 254 or not re.fullmatch(r'[^\s@<>\x00-\x1f]+@[^\s@<>\x00-\x1f]+\.[^\s@<>\x00-\x1f]+', value):
        raise HTTPException(422, 'Enter a valid email address.')
    return value


def recovery_address(db,value):
    address=normalize_email(value)
    matches=db.scalars(select(AccountEmail).where(AccountEmail.email==address,AccountEmail.verified.is_(True))).all()
    eligible=[email for email in matches if account_enabled(db,email.user_id) and credential_for(db,email.user_id)]
    return eligible[0] if len(eligible)==1 else None


def missing_delivery_settings(settings):
    required = ('smtp_host', 'smtp_from_email', 'smtp_username', 'smtp_password', 'session_secret')
    missing = []
    for name in required:
        value = getattr(settings, name, None)
        if hasattr(value, 'get_secret_value'):
            value = value.get_secret_value()
        if not value or not str(value).strip():
            missing.append(name.upper())
    return missing


def delivery_ready(settings):
    return not missing_delivery_settings(settings)


def digest(settings, identity, code):
    return hmac.new(settings.session_secret.get_secret_value().encode(), f'{identity}:{code}'.encode(), hashlib.sha256).hexdigest()


def smtp_password(settings):
    value = settings.smtp_password.get_secret_value()
    # Google displays App Passwords in four groups; spaces are presentation only.
    compact = re.sub(r'\s', '', value)
    if settings.smtp_host == 'smtp.gmail.com' and re.fullmatch(r'[A-Za-z0-9]{16}', compact):
        return compact
    return value


def send(settings, email, code):
    if not delivery_ready(settings):
        raise HTTPException(503, 'Email verification is not configured. Ask Admin to configure SMTP delivery; no code was sent.')
    message = EmailMessage()
    message['From'], message['To'], message['Subject'] = normalize_email(settings.smtp_from_email), normalize_email(email), 'Your VED verification code'
    message.set_content(f'Your VED code is {code}. It expires in 5 minutes and can be used once.\n\nIf you did not request this, ignore this email. Never share this code.')
    try:
        client = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=12, context=ssl.create_default_context()) if settings.smtp_implicit_tls else smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=12)
        with client:
            if not settings.smtp_implicit_tls:
                client.starttls(context=ssl.create_default_context())
            client.login(settings.smtp_username, smtp_password(settings))
            client.send_message(message)
    except (OSError, smtplib.SMTPException):
        raise HTTPException(503, 'The verification email could not be delivered. Try again later or contact Admin.') from None


def addresses(db, user_id):
    return list(db.scalars(select(AccountEmail).where(AccountEmail.user_id == user_id).order_by(AccountEmail.primary.desc(), AccountEmail.id)))


def mask(email):
    name, domain = email.split('@', 1)
    return f'{name[:2]}***@{domain}'


def issue(db, request, email, purpose):
    settings = request.app.state.settings
    if not delivery_ready(settings):
        raise HTTPException(503, 'Email verification requires SMTP setup by Admin. No code was sent.')
    # Serialize sends for an account, including concurrent resend requests.
    db.scalar(select(User).where(User.id == email.user_id).with_for_update())
    recent = list(db.scalars(select(EmailChallenge).where(EmailChallenge.user_id == email.user_id,
        EmailChallenge.created_at > now() - timedelta(hours=1)).order_by(EmailChallenge.created_at.desc())))
    if len(recent) >= 10 or recent and recent[0].created_at > now() - timedelta(seconds=60):
        raise HTTPException(429, 'Please wait at least 60 seconds between codes. At most 10 codes can be requested per hour.')
    identity, code = secrets.token_hex(16), f'{secrets.randbelow(100000):05d}'
    send(settings, email.email, code)
    challenge = EmailChallenge(id=identity, user_id=email.user_id, email_id=email.id, purpose=purpose,
        code_digest=digest(settings, f'{identity}:{session_revision(db, email.user_id)}', code), created_at=now(), expires_at=now() + timedelta(minutes=5), attempts=0, used=False)
    db.add(challenge); db.commit()
    request.session['email_challenge_id'] = identity
    return {'challenge_id': identity, 'destination': mask(email.email), 'expires_in': 300, 'resend_after': 60}


def needs_verification(db, request, user):
    if not any(x.verified for x in addresses(db, user.id)):
        return False
    token = request.cookies.get('ved_trusted_device', '')
    record = db.get(TrustedDevice, hashlib.sha256(token.encode()).hexdigest()) if token else None
    return not record or record.user_id != user.id or record.expires_at <= now() or record.account_revision != session_revision(db, user.id)


def pending_signin(db, request, user):
    request.session.clear()
    request.session.update(pending_auth_user=user.id, pending_auth_revision=session_revision(db, user.id), pending_auth_expires=time.time() + 600)
    return {'verification_required': True, 'channels': [{'channel': 'primary' if x.primary else 'backup', 'email': mask(x.email)} for x in addresses(db, user.id) if x.verified]}


def pending_user(db, request):
    identity = request.session.get('pending_auth_user')
    user = db.get(User, identity) if type(identity) is int else None
    if not user or not account_enabled(db, user.id) or request.session.get('pending_auth_revision') != session_revision(db, user.id) or request.session.get('pending_auth_expires', 0) < time.time():
        raise HTTPException(401, 'Sign in again to request a verification code.')
    return user


def consume(db, request, challenge_id, code):
    challenge = db.scalar(select(EmailChallenge).where(EmailChallenge.id == challenge_id).with_for_update())
    if request.session.get('email_challenge_id') != challenge_id or not challenge or challenge.used or challenge.expires_at <= now() or challenge.attempts >= 5:
        raise HTTPException(400, 'This code is invalid or expired. Request a new code.')
    challenge.attempts += 1
    valid = hmac.compare_digest(challenge.code_digest, digest(request.app.state.settings, f'{challenge.id}:{session_revision(db, challenge.user_id)}', code))
    if not valid:
        db.commit()
        raise HTTPException(400, 'The code is incorrect. Check all five digits.')
    if not account_enabled(db, challenge.user_id):
        raise HTTPException(403, 'Account access is unavailable.')
    email = db.get(AccountEmail, challenge.email_id)
    if not email or (challenge.purpose in ('signin', 'reset_password') and not email.verified):
        raise HTTPException(400, 'This email is no longer available for authentication.')
    challenge.used = True
    db.flush()
    return challenge


def reset_password(db, user, password):
    credential = credential_for(db, user.id)
    if credential is None:
        raise HTTPException(403, 'Admin must configure this account before password recovery is available.')
    credential.password_hash = hash_password(password)
    credential.failed_attempts, credential.locked_until = 0, None
    invalidate_sessions(db, user.id)
    db.commit()
