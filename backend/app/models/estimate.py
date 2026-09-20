"""Stored estimate snapshots; generation and rounding policy belong to O2."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Estimate(Base):
    __tablename__ = "estimates"
    __table_args__ = (
        UniqueConstraint("project_id", "version_number", name="uq_estimate_project_version"),
        CheckConstraint("version_number > 0", name="ck_estimate_version"),
        CheckConstraint("total >= 0", name="ck_estimate_total"),
        CheckConstraint("CHAR_LENGTH(currency) = 3", name="ck_estimate_currency"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("projects.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(30, 8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class EstimateItem(Base):
    __tablename__ = "estimate_items"
    __table_args__ = (
        UniqueConstraint("estimate_id", "line_number", name="uq_estimate_item_line"),
        CheckConstraint("line_number > 0", name="ck_estimate_item_line"),
        CheckConstraint("quantity >= 0 AND captured_unit_price >= 0 AND line_total >= 0", name="ck_estimate_item_amounts"),
        CheckConstraint("CHAR_LENGTH(unit) BETWEEN 1 AND 32", name="ck_estimate_item_unit"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    estimate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("estimates.id"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    material_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("materials.id"), nullable=False)
    material_code: Mapped[str] = mapped_column(String(64), nullable=False)
    material_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(16, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    captured_unit_price: Mapped[Decimal] = mapped_column(Numeric(16, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(30, 8), nullable=False)
