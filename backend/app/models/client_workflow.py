"""Additive prototype models for managed accounts and project publication."""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func, null
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LocalCredential(Base):
    __tablename__ = 'local_credentials'
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), primary_key=True)
    username: Mapped[str] = mapped_column(String(80, collation='utf8mb4_bin'), unique=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default='0')
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AccountAccess(Base):
    """Revoke access without deleting authorship, estimates or audit references."""
    __tablename__ = 'account_access'
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), primary_key=True)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default='0')
    session_revision: Mapped[int] = mapped_column(Integer, default=0, server_default='0')
    updated_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=True)


class LinkedIdentity(Base):
    __tablename__ = 'linked_identities'
    __table_args__ = (UniqueConstraint('provider', 'subject', name='uq_linked_identity'),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), index=True)
    provider: Mapped[str] = mapped_column(String(64))
    subject: Mapped[str] = mapped_column(String(255, collation='utf8mb4_bin'))


class ProjectAssignment(Base):
    __tablename__ = 'project_assignments'
    intake_details: Mapped[dict | None] = mapped_column(JSON, nullable=True, deferred=True,server_default=null())
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('projects.id'), primary_key=True)
    client_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), index=True)
    created_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'))


class ProjectPublication(Base):
    __tablename__ = 'project_publications'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('projects.id'), index=True)
    approved_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'))
    # Immutable references to saved versions, never a pointer to the live draft.
    layout_version_ids: Mapped[list] = mapped_column(JSON)
    estimate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('estimates.id'))
    approved_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
