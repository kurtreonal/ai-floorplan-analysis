"""Append-only removal/restore history; uploaded rows and files are never deleted."""
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FloorPlanLifecycleEvent(Base):
    __tablename__ = "floor_plan_lifecycle_events"
    __table_args__ = (
        UniqueConstraint("floor_plan_id", "revision", name="uq_plan_lifecycle_revision"),
        UniqueConstraint("floor_plan_id", "request_id", name="uq_plan_lifecycle_request"),
        CheckConstraint("action IN ('removed', 'restored')", name="ck_plan_lifecycle_action"),
        CheckConstraint("revision > 0", name="ck_plan_lifecycle_revision"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    floor_plan_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("floor_plans.id"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    request_id: Mapped[str] = mapped_column(String(36, collation="ascii_bin"), nullable=False)
    actor_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
