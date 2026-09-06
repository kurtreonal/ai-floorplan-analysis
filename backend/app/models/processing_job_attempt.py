from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProcessingJobAttempt(Base):
    __tablename__ = "processing_job_attempts"
    __table_args__ = (
        UniqueConstraint(
            "processing_job_id",
            "attempt_number",
            name="uq_processing_job_attempts_job_number",
        ),
        UniqueConstraint(
            "processing_job_id",
            "active_marker",
            name="uq_processing_job_attempts_job_active",
        ),
        CheckConstraint(
            "attempt_number > 0",
            name="ck_processing_job_attempts_number",
        ),
        CheckConstraint(
            "status IN ('active', 'succeeded', 'failed', 'lease_expired', 'cancelled')",
            name="ck_processing_job_attempts_status",
        ),
        CheckConstraint(
            "stage IN ('claimed', 'source_preparation', 'normalization', "
            "'geometry_evidence', 'symbol_evidence', 'persistence', 'completed')",
            name="ck_processing_job_attempts_stage",
        ),
        CheckConstraint(
            "active_marker IS NULL OR active_marker = TRUE",
            name="ck_processing_job_attempts_active_marker",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    processing_job_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("processing_jobs.id"),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_identity: Mapped[str] = mapped_column(
        String(128, collation="ascii_bin"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    active_marker: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
