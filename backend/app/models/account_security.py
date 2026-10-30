"""Verified email, one-use challenges and revocable device trust."""
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class AccountEmail(Base):
    __tablename__ = 'account_emails'
    __table_args__ = (UniqueConstraint('user_id', 'email', name='uq_account_email'),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), index=True)
    email: Mapped[str] = mapped_column(String(320))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    primary: Mapped[bool] = mapped_column(Boolean, default=False)


class EmailChallenge(Base):
    __tablename__ = 'email_challenges'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), index=True)
    email_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('account_emails.id'))
    purpose: Mapped[str] = mapped_column(String(32))
    code_digest: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class TrustedDevice(Base):
    __tablename__ = 'trusted_devices'
    token_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), index=True)
    account_revision: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class AdminActivity(Base):
    __tablename__ = 'admin_activity'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), index=True)
    action: Mapped[str] = mapped_column(String(80))
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[int] = mapped_column(BigInteger)
    summary: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
