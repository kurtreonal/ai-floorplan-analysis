from datetime import datetime
from typing import TYPE_CHECKING

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
from sqlalchemy.dialects.mysql import DOUBLE
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


if TYPE_CHECKING:
    from app.models.floor_plan import FloorPlan
    from app.models.processing_job import ProcessingJob


DETECTED_SYMBOL_STATUSES = ("detected", "needs_review")


class DetectedSymbol(Base):
    __tablename__ = "detected_symbols"
    __table_args__ = (
        UniqueConstraint(
            "processing_job_id",
            "prediction_index",
            name="uq_detected_symbols_job_prediction",
        ),
        CheckConstraint(
            "status IN ('detected', 'needs_review')",
            name="ck_detected_symbols_status",
        ),
        CheckConstraint(
            "prediction_index > 0",
            name="ck_detected_symbols_prediction_index",
        ),
        CheckConstraint(
            "original_class_id >= 0",
            name="ck_detected_symbols_class_id",
        ),
        CheckConstraint(
            "original_confidence >= 0 AND original_confidence <= 1",
            name="ck_detected_symbols_confidence",
        ),
        CheckConstraint(
            "confidence_threshold >= 0 AND confidence_threshold <= 1",
            name="ck_detected_symbols_threshold",
        ),
        CheckConstraint(
            "image_width_pixels > 0 AND image_height_pixels > 0",
            name="ck_detected_symbols_image_dimensions",
        ),
        CheckConstraint(
            "bounding_box_x_min_pixels >= 0 "
            "AND bounding_box_y_min_pixels >= 0 "
            "AND bounding_box_x_max_pixels <= image_width_pixels "
            "AND bounding_box_y_max_pixels <= image_height_pixels "
            "AND center_x_pixels >= 0 "
            "AND center_y_pixels >= 0 "
            "AND center_x_pixels <= image_width_pixels "
            "AND center_y_pixels <= image_height_pixels",
            name="ck_detected_symbols_pixel_bounds",
        ),
        CheckConstraint(
            "bounding_box_x_min_pixels < bounding_box_x_max_pixels "
            "AND bounding_box_y_min_pixels < bounding_box_y_max_pixels",
            name="ck_detected_symbols_box_order",
        ),
        CheckConstraint(
            "maximum_detections = 300",
            name="ck_detected_symbols_maximum_detections",
        ),
        CheckConstraint(
            "detection_limit_reached IN (0, 1)",
            name="ck_detected_symbols_limit_flag",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    floor_plan_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("floor_plans.id"),
        nullable=False,
        index=True,
    )
    processing_job_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("processing_jobs.id"),
        nullable=False,
        index=True,
    )
    prediction_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    original_class_id: Mapped[int] = mapped_column(Integer, nullable=False)
    original_class_name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_confidence: Mapped[float] = mapped_column(
        DOUBLE(asdecimal=False),
        nullable=False,
    )
    confidence_threshold: Mapped[float] = mapped_column(
        DOUBLE(asdecimal=False),
        nullable=False,
    )
    image_width_pixels: Mapped[int] = mapped_column(Integer, nullable=False)
    image_height_pixels: Mapped[int] = mapped_column(Integer, nullable=False)
    bounding_box_x_min_pixels: Mapped[float] = mapped_column(
        DOUBLE(asdecimal=False), nullable=False
    )
    bounding_box_y_min_pixels: Mapped[float] = mapped_column(
        DOUBLE(asdecimal=False), nullable=False
    )
    bounding_box_x_max_pixels: Mapped[float] = mapped_column(
        DOUBLE(asdecimal=False), nullable=False
    )
    bounding_box_y_max_pixels: Mapped[float] = mapped_column(
        DOUBLE(asdecimal=False), nullable=False
    )
    center_x_pixels: Mapped[float] = mapped_column(
        DOUBLE(asdecimal=False), nullable=False
    )
    center_y_pixels: Mapped[float] = mapped_column(
        DOUBLE(asdecimal=False), nullable=False
    )
    maximum_detections: Mapped[int] = mapped_column(Integer, nullable=False)
    detection_limit_reached: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    floor_plan: Mapped["FloorPlan"] = relationship(
        back_populates="detected_symbols"
    )
    processing_job: Mapped["ProcessingJob"] = relationship(
        back_populates="detected_symbols"
    )
