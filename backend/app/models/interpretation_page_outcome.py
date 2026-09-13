from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class InterpretationPageOutcome(Base):
    """Durable page selection and terminal outcome for a processing job."""

    __tablename__ = "interpretation_page_outcomes"
    __table_args__ = (
        UniqueConstraint("processing_job_id", "floor_plan_page_id", name="uq_interpretation_outcome_job_page"),
        CheckConstraint("page_number > 0", name="ck_interpretation_outcome_page_positive"),
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_interpretation_outcome_progress"),
        CheckConstraint(
            "selection_state IN ('selected', 'skipped')",
            name="ck_interpretation_outcome_selection",
        ),
        CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed', 'cancelled', 'timeout', 'skipped')",
            name="ck_interpretation_outcome_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    processing_job_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("processing_jobs.id"), nullable=False, index=True)
    floor_plan_page_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("floor_plan_pages.id"), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    selection_state: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued", server_default="queued")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    candidate_run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_artifact_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("processing_artifacts.id"), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_release_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    configuration_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
