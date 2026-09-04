from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


if TYPE_CHECKING:
    from app.models.floor_plan_page import FloorPlanPage
    from app.models.processing_job import ProcessingJob


ARTIFACT_KINDS = ("pdf_page", "normalized_image", "preprocessing_debug", "vlm_tile")


class ProcessingArtifact(Base):
    __tablename__ = "processing_artifacts"
    __table_args__ = (
        CheckConstraint(
            "artifact_kind IN ('pdf_page', 'normalized_image', 'preprocessing_debug', 'vlm_tile')",
            name="ck_processing_artifacts_kind",
        ),
        CheckConstraint("byte_size > 0", name="ck_processing_artifacts_byte_size"),
        CheckConstraint("CHAR_LENGTH(sha256) = 64", name="ck_processing_artifacts_sha256_length"),
        CheckConstraint(
            "(pixel_width IS NULL AND pixel_height IS NULL) OR "
            "(pixel_width > 0 AND pixel_height > 0)",
            name="ck_processing_artifacts_dimensions",
        ),
        UniqueConstraint("relative_path", name="uq_processing_artifacts_relative_path"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    processing_job_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("processing_jobs.id"), nullable=False, index=True
    )
    floor_plan_page_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("floor_plan_pages.id"), nullable=False, index=True
    )
    artifact_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    pixel_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pixel_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    processing_job: Mapped["ProcessingJob"] = relationship(back_populates="artifacts")
    floor_plan_page: Mapped["FloorPlanPage"] = relationship(back_populates="artifacts")
