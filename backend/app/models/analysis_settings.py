"""Append-only human approvals; existing layout snapshots remain self-contained."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FloorElevationSetting(Base):
    __tablename__ = "floor_elevation_settings"
    __table_args__ = (
        CheckConstraint("elevation_meters BETWEEN -10000 AND 10000", name="ck_floor_elevation_bounds"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_floor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project_floors.id"), index=True)
    elevation_meters: Mapped[Decimal | None] = mapped_column(Numeric(15, 9), nullable=True)
    evidence_notes: Mapped[str] = mapped_column(String(1000))
    reviewed_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PageScaleSetting(Base):
    __tablename__ = "page_scale_settings"
    __table_args__ = (
        CheckConstraint(
            "(pixels_per_meter IS NULL AND reference_width_pixels IS NULL AND reference_height_pixels IS NULL) OR "
            "(pixels_per_meter IS NOT NULL AND pixels_per_meter BETWEEN 0.000001 AND 1000000 "
            "AND reference_width_pixels IS NOT NULL AND reference_width_pixels BETWEEN 1 AND 100000 "
            "AND reference_height_pixels IS NOT NULL AND reference_height_pixels BETWEEN 1 AND 100000)",
            name="ck_page_scale_bounds",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    floor_plan_page_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("floor_plan_pages.id"), index=True)
    pixels_per_meter: Mapped[Decimal | None] = mapped_column(Numeric(16, 9), nullable=True)
    reference_width_pixels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reference_height_pixels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_notes: Mapped[str] = mapped_column(String(1000))
    reviewed_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
