from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProcessingJobCancellation(Base):
    __tablename__ = "processing_job_cancellations"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('queued_cancelled', 'cooperative_requested')",
            name="ck_processing_job_cancellations_mode",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    processing_job_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("processing_jobs.id"),
        nullable=False,
        unique=True,
    )
    requested_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
