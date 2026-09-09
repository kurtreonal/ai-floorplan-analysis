from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


LongText = Text().with_variant(LONGTEXT(), "mysql")


class FloorPlanInterpretationRun(Base):
    __tablename__ = "floor_plan_interpretation_runs"
    __table_args__ = (
        CheckConstraint(
            "CHAR_LENGTH(candidate_run_id) = 32",
            name="ck_floor_plan_interpretation_runs_run_id",
        ),
        CheckConstraint(
            "CHAR_LENGTH(candidate_sha256) = 64",
            name="ck_floor_plan_interpretation_runs_sha256",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_run_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    processing_job_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("processing_jobs.id"),
        nullable=False,
        unique=True,
    )
    floor_plan_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("floor_plans.id"),
        nullable=False,
        index=True,
    )
    floor_plan_page_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("floor_plan_pages.id"),
        nullable=False,
    )
    source_artifact_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("processing_artifacts.id"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_json: Mapped[str] = mapped_column(LongText, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
