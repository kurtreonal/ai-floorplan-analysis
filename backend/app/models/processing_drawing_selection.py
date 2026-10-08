"""Immutable development reprocessing scope; never replaces a review/layout."""
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProcessingDrawingSelection(Base):
    __tablename__ = "processing_drawing_selections"
    __table_args__ = (
        UniqueConstraint("requested_by_user_id", "request_id", name="uq_drawing_selection_request"),
        CheckConstraint("x_pixels >= 0 AND y_pixels >= 0 AND width_pixels > 0 AND height_pixels > 0",
                        name="ck_drawing_selection_bounds"),
        CheckConstraint("CHAR_LENGTH(source_artifact_sha256) = 64 AND CHAR_LENGTH(selection_sha256) = 64",
                        name="ck_drawing_selection_hashes"),
    )
    processing_job_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("processing_jobs.id"), primary_key=True)
    source_run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("floor_plan_interpretation_runs.id"), nullable=False)
    requested_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    selection_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    x_pixels: Mapped[int] = mapped_column(Integer, nullable=False)
    y_pixels: Mapped[int] = mapped_column(Integer, nullable=False)
    width_pixels: Mapped[int] = mapped_column(Integer, nullable=False)
    height_pixels: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
