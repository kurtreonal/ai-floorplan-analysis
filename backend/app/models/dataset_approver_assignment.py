from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DatasetApproverAssignment(Base):
    __tablename__ = "dataset_approver_assignments"
    __table_args__ = (
        UniqueConstraint(
            "active_marker",
            name="uq_dataset_approver_assignments_active_marker",
        ),
        CheckConstraint(
            "authority_scope = 'VED_AI_DATASET_APPROVER'",
            name="ck_dataset_approver_assignments_authority_scope",
        ),
        CheckConstraint(
            "qualification_category IN ('PEE', 'SENIOR_REE')",
            name="ck_dataset_approver_assignments_qualification",
        ),
        CheckConstraint(
            "active_marker IS NULL OR active_marker = TRUE",
            name="ck_dataset_approver_assignments_active_marker",
        ),
        CheckConstraint(
            "assignee_user_id <> assigned_by_user_id",
            name="ck_dataset_approver_assignments_no_self_assignment",
        ),
        CheckConstraint(
            "(active_marker = TRUE AND inactive_at IS NULL AND "
            "deactivated_by_user_id IS NULL) OR "
            "(active_marker IS NULL AND inactive_at IS NOT NULL AND "
            "deactivated_by_user_id IS NOT NULL)",
            name="ck_dataset_approver_assignments_state",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    assignee_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    assigned_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    deactivated_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    authority_scope: Mapped[str] = mapped_column(
        String(32, collation="ascii_bin"),
        nullable=False,
        default="VED_AI_DATASET_APPROVER",
        server_default="VED_AI_DATASET_APPROVER",
    )
    qualification_category: Mapped[str] = mapped_column(
        String(16, collation="ascii_bin"),
        nullable=False,
    )
    professional_reference: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    active_marker: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        default=True,
        server_default="1",
    )
    active_from: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    inactive_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
