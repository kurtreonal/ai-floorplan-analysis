from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


if TYPE_CHECKING:
    from app.models.floor_plan import FloorPlan
    from app.models.processing_job import ProcessingJob


WALL_STATUSES = ("detected", "verified")


class Wall(Base):
    __tablename__ = "walls"
    __table_args__ = (
        UniqueConstraint(
            "floor_plan_id",
            "candidate_id",
            name="uq_walls_floor_plan_candidate",
        ),
        CheckConstraint(
            "status IN ('detected', 'verified')",
            name="ck_walls_status",
        ),
        CheckConstraint("candidate_id > 0", name="ck_walls_candidate_id"),
        CheckConstraint("pixels_per_meter > 0", name="ck_walls_scale"),
        CheckConstraint(
            "raw_start_x >= 0 AND raw_start_y >= 0 "
            "AND raw_end_x >= 0 AND raw_end_y >= 0",
            name="ck_walls_raw_coordinates",
        ),
        CheckConstraint(
            "canonical_start_x >= 0 AND canonical_start_y >= 0 "
            "AND canonical_end_x >= 0 AND canonical_end_y >= 0",
            name="ck_walls_canonical_coordinates",
        ),
        CheckConstraint(
            "raw_length_pixels >= 0 AND canonical_length_meters >= 0",
            name="ck_walls_lengths",
        ),
        CheckConstraint(
            "angle_degrees >= 0 AND angle_degrees < 180",
            name="ck_walls_angle",
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
    candidate_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="detected",
        server_default="detected",
    )
    pixels_per_meter: Mapped[Decimal] = mapped_column(
        Numeric(20, 9),
        nullable=False,
    )
    raw_start_x: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_start_y: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_end_x: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_end_y: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_length_pixels: Mapped[Decimal] = mapped_column(
        Numeric(20, 6),
        nullable=False,
    )
    canonical_start_x: Mapped[Decimal] = mapped_column(
        Numeric(20, 9),
        nullable=False,
    )
    canonical_start_y: Mapped[Decimal] = mapped_column(
        Numeric(20, 9),
        nullable=False,
    )
    canonical_end_x: Mapped[Decimal] = mapped_column(
        Numeric(20, 9),
        nullable=False,
    )
    canonical_end_y: Mapped[Decimal] = mapped_column(
        Numeric(20, 9),
        nullable=False,
    )
    canonical_length_meters: Mapped[Decimal] = mapped_column(
        Numeric(20, 9),
        nullable=False,
    )
    angle_degrees: Mapped[Decimal] = mapped_column(
        Numeric(9, 6),
        nullable=False,
    )
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

    floor_plan: Mapped["FloorPlan"] = relationship(back_populates="walls")
    processing_job: Mapped["ProcessingJob"] = relationship(back_populates="walls")
