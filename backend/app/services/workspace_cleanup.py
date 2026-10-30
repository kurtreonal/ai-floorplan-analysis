"""Cancellable account cleanup and project archiving; project files stay intact."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import subprocess

from fastapi import HTTPException
from sqlalchemy import MetaData, Table, delete, func, inspect, select, text, update
from sqlalchemy.orm import Session
from app.core.config import REPOSITORY_ROOT, get_settings
from app.models import Project, Role, User
from app.models.account_security import AccountEmail, AdminActivity, EmailChallenge, TrustedDevice
from app.models.client_workflow import AccountAccess, LinkedIdentity, LocalCredential
from app.services.activity_log import record
from app.services.local_accounts import account_enabled, invalidate_sessions

logger = logging.getLogger(__name__)
MODE = 'preserve_project_data'
ACTIVE = {'pending', 'executing', 'cleaning', 'recovery_required'}
PHASES = {'WORKSPACE_RESET_STARTED': 'executing', 'WORKSPACE_RESET_COMPLETED': 'completed',
          'WORKSPACE_RESET_CANCELLED': 'cancelled', 'WORKSPACE_RESET_FAILED': 'failed'}

def now():
    return datetime.now(timezone.utc)

def scheduled(db, lock=False):
    query = select(AdminActivity).where(AdminActivity.action == 'WORKSPACE_RESET_SCHEDULED').order_by(AdminActivity.id.desc()).limit(1)
    return db.scalar(query.with_for_update() if lock else query)

def state(db, row=None):
    row = row or scheduled(db)
    if row is None:
        return {'phase': 'idle', 'server_time': now().isoformat()}
    data = json.loads(row.summary)
    action = db.scalar(select(AdminActivity).where(AdminActivity.target_type == 'workspace_reset',
        AdminActivity.target_id == row.id, AdminActivity.action.in_(tuple(PHASES))).order_by(AdminActivity.id.desc()).limit(1))
    return dict(id=row.id, phase=PHASES.get(action.action, 'pending') if action else 'pending',
                due_at=data['due_at'], request_id=data['request_id'], server_time=now().isoformat(),
                mode=data.get('mode'), detail=action.summary if action else None,
                keep_admin_id=data.get('keep_admin_id'), keep_designer_id=data.get('keep_designer_id'))

def guard(db, request):
    if request.method in ('GET', 'HEAD', 'OPTIONS') or request.url.path.startswith(('/api/admin/workspace-reset', '/api/auth/', '/api/notifications/')):
        return
    if state(db)['phase'] in ACTIVE:
        raise HTTPException(423, 'Workspace cleanup is pending. Admin can cancel in Admin settings → Workspace data.')

def preview(db, user=None):
    users = list(db.scalars(select(User).order_by(User.id)))
    accounts = [u for u in users if account_enabled(db, u.id)]
    options = lambda role: [dict(id=u.id, label=u.display_name or u.email or f'{role.title()} #{u.id}', email=u.email)
                           for u in accounts if u.role.name == role and (u.email or db.get(LocalCredential, u.id))]
    projects = list(db.execute(select(Project.id, Project.status).order_by(Project.id)))
    access = list(db.execute(select(AccountAccess.user_id, AccountAccess.disabled, AccountAccess.session_revision).order_by(AccountAccess.user_id)))
    fingerprint = hashlib.sha256(json.dumps([[(u.id,u.role_id,u.email,u.oauth_provider,u.oauth_subject) for u in users],
        [tuple(p) for p in projects], [tuple(a) for a in access]], default=str, separators=(',', ':')).encode()).hexdigest()
    return dict(counts=dict(projects=sum(p.status != 'archived' for p in projects),
                           accounts=len(accounts), admins=sum(u.role.name == 'ADMIN' for u in accounts)),
                administrators=options('ADMIN'), designers=options('DESIGNER'),
                suggested_admin_id=user.id if user else None, fingerprint=fingerprint,
                preserved=['Floorplans and original uploads', 'BOMs and estimate history', 'Settings and budgets',
                           'Prices and pairings', 'Assemblies and legends', 'Model and training files'], **state(db))

def validate_kept(db, admin, admin_id, designer_id):
    if admin.role.name != 'ADMIN' or admin.id != admin_id:
        raise HTTPException(422, 'Keep the signed-in Admin account. Sign in as the Admin you want to retain first.')
    designer = db.get(User, designer_id)
    if not account_enabled(db, admin.id) or designer is None or designer.role.name != 'DESIGNER' or not account_enabled(db, designer.id):
        raise HTTPException(422, 'Choose an active Designer account to keep.')
    return {admin.id, designer.id}

def request_reset(db, user, data):
    db.scalar(select(Role).where(Role.name == 'ADMIN').with_for_update())
    current = state(db)
    if current['phase'] in ACTIVE:
        if current.get('request_id') == str(data.request_id):
            return preview(db, user)
        raise HTTPException(409, 'A cleanup is already scheduled. Cancel it first.')
    if data.confirmation != 'RESET WORKSPACE ACCESS':
        raise HTTPException(422, 'Type RESET WORKSPACE ACCESS to confirm.')
    validate_kept(db, user, data.keep_admin_id, data.keep_designer_id)
    if preview(db, user)['fingerprint'] != data.expected_fingerprint:
        raise HTTPException(409, 'Workspace data changed. Refresh the preview before confirming.')
    record(db, user, 'WORKSPACE_RESET_SCHEDULED', 'workspace_reset', 0, json.dumps(dict(
        due_at=(now()+timedelta(minutes=5)).isoformat(), request_id=str(data.request_id), mode=MODE,
        keep_admin_id=data.keep_admin_id, keep_designer_id=data.keep_designer_id), separators=(',', ':')))
    db.commit()
    return preview(db, user)

def cancel(db, user, identity):
    row = scheduled(db, lock=True)
    if not row or row.id != identity or state(db, row)['phase'] not in ('pending', 'cancelled'):
        raise HTTPException(409, 'This cleanup can no longer be cancelled.')
    if state(db, row)['phase'] == 'pending':
        record(db, user, 'WORKSPACE_RESET_CANCELLED', 'workspace_reset', row.id, 'Cleanup cancelled. No project or account changes applied.')
        db.commit()
    return preview(db, user)

def backup(db, identity):
    url = db.get_bind().engine.url
    if get_settings().app_env != 'development' or url.host not in ('localhost', '127.0.0.1'):
        raise RuntimeError('Local backup configuration required; cleanup stopped before changes.')
    executable = Path('C:/xampp/mysql/bin/mysqldump.exe')
    if not executable.is_file():
        raise RuntimeError('Database backup tool unavailable; cleanup stopped before changes.')
    directory = REPOSITORY_ROOT/'storage'/'admin-reset'/f'cleanup-{identity}'
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory/'database.sql'
    environment = os.environ.copy()
    environment['MYSQL_PWD'] = url.password or ''
    command = [str(executable), '--protocol=tcp', '--single-transaction', '--skip-lock-tables', '--hex-blob',
        '--default-character-set=utf8mb4', '--host='+url.host, '--port='+str(url.port or 3306),
        '--user='+url.username, '--result-file='+str(destination), url.database]
    result = subprocess.run(command, env=environment, capture_output=True, timeout=120)
    if result.returncode or not destination.is_file() or not destination.stat().st_size:
        raise RuntimeError('Database backup failed; cleanup stopped before changes.')
    return destination

def protected_fingerprints(db):
    excluded = {'users', 'projects', 'admin_activity', 'account_access', 'account_emails',
                'email_challenges', 'trusted_devices', 'local_credentials', 'linked_identities'}
    metadata, result = MetaData(), {}
    for name in sorted(set(inspect(db.connection()).get_table_names())-excluded):
        table = Table(name, metadata, autoload_with=db.connection())
        rows = sorted(hashlib.sha256(json.dumps(dict(row), sort_keys=True, default=str,
                      separators=(',', ':')).encode()).hexdigest() for row in db.execute(select(table)).mappings())
        result[name] = (len(rows), hashlib.sha256(''.join(rows).encode()).hexdigest())
    return result

def apply_cleanup(db, admin, kept):
    projects = list(db.scalars(select(Project).where(Project.status != 'archived').with_for_update()))
    for project in projects:
        project.status = 'archived'
        record(db, admin, 'PROJECT_ARCHIVED', 'project', project.id, 'Removed from active projects; floorplans, BOMs and saved versions preserved.')
    users = list(db.scalars(select(User).where(User.id.not_in(kept)).with_for_update()))
    removed = [u.id for u in users]
    # Child challenges must be removed before their referenced recovery emails.
    for model in (EmailChallenge, TrustedDevice, AccountEmail, LinkedIdentity, LocalCredential):
        db.execute(delete(model).where(model.user_id.in_(removed)))
    for user in users:
        access = invalidate_sessions(db, user.id, admin.id)
        access.disabled = True
        user.display_name, user.email, user.avatar_url, user.profile_details = f'Removed user #{user.id}', None, None, None
        user.oauth_provider, user.oauth_subject = 'removed', f'removed-{user.id}'
        record(db, admin, 'USER_DELETED', 'user', user.id, 'Removed sign-in methods and profile; historical authorship references retained where needed.')
    db.flush()
    # Physically remove unreferenced identity rows; retain disabled anonymous
    # author keys where project/catalog/audit history still references them.
    metadata = MetaData()
    referenced = set()
    inspector = inspect(db.connection())
    for name in inspector.get_table_names():
        for fk in inspector.get_foreign_keys(name):
            if fk['referred_table'] != 'users' or name == 'account_access' and fk['constrained_columns'] == ['user_id']:
                continue
            if fk['referred_columns'] != ['id'] or len(fk['constrained_columns']) != 1:
                raise RuntimeError('Unsupported identity reference; cleanup rolled back.')
            table = Table(name, metadata, autoload_with=db.connection(), extend_existing=True)
            column = table.c[fk['constrained_columns'][0]]
            referenced.update(db.scalars(select(column).where(column.in_(removed))))
    unreferenced = set(removed)-referenced
    db.execute(delete(AccountAccess).where(AccountAccess.user_id.in_(unreferenced)))
    db.execute(delete(User).where(User.id.in_(unreferenced)).execution_options(synchronize_session=False))
    if db.scalar(select(func.count()).select_from(Project).where(Project.status != 'archived')):
        raise RuntimeError('Active projects remain; cleanup rolled back.')
    active = set(db.scalars(select(User.id).outerjoin(AccountAccess, AccountAccess.user_id == User.id).where(
        (AccountAccess.disabled.is_(False)) | (AccountAccess.user_id.is_(None)))))
    if active != kept:
        raise RuntimeError('Account preservation check failed; cleanup rolled back.')
    return dict(projects_archived=len(projects), accounts_removed=len(removed),
                identity_rows_deleted=len(unreferenced), historical_author_keys_retained=len(referenced))

def tick(connection):
    with Session(bind=connection) as db:
        row = scheduled(db, lock=True)
        if row is None or state(db, row)['phase'] not in ACTIVE:
            return
        current = state(db, row)
        user = db.get(User, row.actor_id)
        if not user or user.role.name != 'ADMIN':
            raise RuntimeError('Cleanup requester unavailable.')
        if current.get('mode') != MODE or current['phase'] != 'pending':
            record(db, user, 'WORKSPACE_RESET_FAILED', 'workspace_reset', row.id,
                   'Old or interrupted reset stopped. No further deletion attempted; schedule a new preservation cleanup.')
            db.commit()
            return
        if now() < datetime.fromisoformat(current['due_at']):
            return
        jobs = Table('processing_jobs', MetaData(), autoload_with=db.connection())
        if db.scalar(select(jobs.c.id).where(jobs.c.status.in_(('queued', 'processing'))).limit(1)):
            return
        kept = validate_kept(db, user, current['keep_admin_id'], current['keep_designer_id'])
        record(db, user, 'WORKSPACE_RESET_STARTED', 'workspace_reset', row.id, 'Cooldown completed. Backing up before archiving projects and removing extra accounts.')
        db.commit()
        try:
            backup(db, row.id)
            protected = protected_fingerprints(db)
            summary = apply_cleanup(db, user, kept)
            if protected_fingerprints(db) != protected:
                raise RuntimeError('Protected project/catalog data changed; cleanup rolled back.')
            record(db, user, 'WORKSPACE_RESET_COMPLETED', 'workspace_reset', row.id,
                   'Cleanup complete; floorplans, BOMs, settings, catalog and files preserved. '+json.dumps(summary, separators=(',', ':')))
            db.commit()  # Data changes and completion state are one transaction.
        except Exception as error:
            db.rollback()
            record(db, user, 'WORKSPACE_RESET_FAILED', 'workspace_reset', row.id,
                   'Cleanup failed; database changes rolled back. No project files were moved or deleted. Failure type: '+type(error).__name__)
            db.commit()
            logger.error('Workspace cleanup failed: %s', type(error).__name__)

def run_worker(stop_event):
    from app.core.database import get_engine
    while not stop_event.is_set():
        try:
            with get_engine().connect() as connection:
                locked = connection.scalar(text("SELECT GET_LOCK('ved.workspace-reset',0)"))
                connection.commit()
                if locked:
                    try:
                        tick(connection)
                    finally:
                        connection.execute(text("SELECT RELEASE_LOCK('ved.workspace-reset')"))
                        connection.commit()
        except Exception as error:
            logger.error('Workspace cleanup status check failed: %s', type(error).__name__)
        stop_event.wait(5)
