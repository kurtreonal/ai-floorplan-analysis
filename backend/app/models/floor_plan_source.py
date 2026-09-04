from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


if TYPE_CHECKING:
    from app.models.floor_plan import FloorPlan
    from app.models.floor_plan_page import FloorPlanPage


class FloorPlanSource(Base):
    __tablename__ = "floor_plan_sources"
    __table_args__ = (
        CheckConstraint(
            "CHAR_LENGTH(original_sha256) = 64",
            name="ck_floor_plan_sources_sha256_length",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    floor_plan_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("floor_plans.id"),
        nullable=False,
        unique=True,
    )
    original_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    floor_plan: Mapped["FloorPlan"] = relationship(back_populates="source_manifest")
    pages: Mapped[list["FloorPlanPage"]] = relationship(
        back_populates="source_manifest",
        cascade="all, delete-orphan",
        order_by="FloorPlanPage.page_number",
    )
