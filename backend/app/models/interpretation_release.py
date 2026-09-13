"""Durable local interpretation release controls and rollback history."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


LongText = Text().with_variant(LONGTEXT(), "mysql")


class InterpretationRelease(Base):
    """Immutable release identity with mutable, audited lifecycle state.

    A release row is never deleted.  ``active_marker`` follows the existing
    nullable-unique-marker pattern so at most one release is active while
    historical shadow, retired and rollback states remain queryable.
    """

    __tablename__ = "interpretation_releases"
    __table_args__ = (
        UniqueConstraint("active_marker", name="uq_interpretation_releases_active_marker"),
        CheckConstraint(
            "status IN ('registered', 'shadow', 'active', 'retired', 'rolled_back', 'manual_review')",
            name="ck_interpretation_releases_status",
        ),
        CheckConstraint(
            "active_marker IS NULL OR active_marker = TRUE",
            name="ck_interpretation_releases_active_marker",
        ),
        CheckConstraint("CHAR_LENGTH(manifest_sha256) = 64", name="ck_interpretation_releases_manifest_sha256"),
        CheckConstraint(
            "evaluation_report_sha256 IS NULL OR CHAR_LENGTH(evaluation_report_sha256) = 64",
            name="ck_interpretation_releases_evaluation_sha256",
        ),
        CheckConstraint(
            "shadow_report_sha256 IS NULL OR CHAR_LENGTH(shadow_report_sha256) = 64",
            name="ck_interpretation_releases_shadow_sha256",
        ),
        CheckConstraint(
            "signed_decision_sha256 IS NULL OR CHAR_LENGTH(signed_decision_sha256) = 64",
            name="ck_interpretation_releases_decision_sha256",
        ),
        CheckConstraint(
            "(status = 'active' AND active_marker = TRUE) OR (status <> 'active' AND active_marker IS NULL)",
            name="ck_interpretation_releases_active_state",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    release_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_revision: Mapped[str] = mapped_column(String(128), nullable=False)
    adapter_revision: Mapped[str | None] = mapped_column(String(128), nullable=True)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluation_report_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    shadow_report_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    shadow_report_json: Mapped[str | None] = mapped_column(LongText, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="registered", server_default="registered")
    active_marker: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    signed_decision_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signed_decision_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rollback_target_release_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rollback_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    shadowed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
