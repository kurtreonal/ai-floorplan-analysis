from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.mysql import DOUBLE
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.models.base import Base


if TYPE_CHECKING:
    from app.models.floor_plan import FloorPlan
    from app.models.processing_job import ProcessingJob
    from app.models.symbol_legend import SymbolLegend
    from app.models.user import User


MANUAL_SYMBOL_STATUS = "manually_added"
MAXIMUM_MANUAL_SYMBOL_CLASS_NAME_LENGTH = 255


class ManualSymbol(Base):
    __tablename__ = "manual_symbols"
    __table_args__ = (
        UniqueConstraint(
            "created_by_user_id",
            "placement_request_id",
            name="uq_manual_symbols_creator_request",
        ),
        CheckConstraint(
            "status = 'manually_added'",
            name="ck_manual_symbols_status",
        ),
        CheckConstraint(
            "class_id >= 0",
            name="ck_manual_symbols_class_id",
        ),
        CheckConstraint(
            "class_name = TRIM(class_name) "
            "AND CHAR_LENGTH(class_name) BETWEEN 1 AND 255",
            name="ck_manual_symbols_class_name",
        ),
        CheckConstraint(
            "image_width_pixels BETWEEN 1 AND 4096 "
            "AND image_height_pixels BETWEEN 1 AND 4096",
            name="ck_manual_symbols_image_dimensions",
        ),
        CheckConstraint(
            "center_x_pixels >= 0 "
            "AND center_y_pixels >= 0 "
            "AND center_x_pixels <= image_width_pixels "
            "AND center_y_pixels <= image_height_pixels",
            name="ck_manual_symbols_pixel_bounds",
        ),
        Index(
            "ix_manual_symbols_floor_plan_job_id",
            "floor_plan_id",
            "processing_job_id",
            "id",
        ),
        Index("ix_manual_symbols_created_by_user_id", "created_by_user_id"),
        Index("ix_manual_symbols_symbol_legend_id", "symbol_legend_id"),
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
    )
    processing_job_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("processing_jobs.id"),
        nullable=False,
    )
    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
    )
    symbol_legend_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("symbol_legends.id"),
        nullable=False,
    )
    placement_request_id: Mapped[str] = mapped_column(
        String(36, collation="utf8mb4_bin"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=MANUAL_SYMBOL_STATUS,
        server_default=MANUAL_SYMBOL_STATUS,
    )
    class_id: Mapped[int] = mapped_column(Integer, nullable=False)
    class_name: Mapped[str] = mapped_column(
        String(MAXIMUM_MANUAL_SYMBOL_CLASS_NAME_LENGTH, collation="utf8mb4_bin"),
        nullable=False,
    )
    center_x_pixels: Mapped[float] = mapped_column(
        DOUBLE(asdecimal=False),
        nullable=False,
    )
    center_y_pixels: Mapped[float] = mapped_column(
        DOUBLE(asdecimal=False),
        nullable=False,
    )
    image_width_pixels: Mapped[int] = mapped_column(Integer, nullable=False)
    image_height_pixels: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    floor_plan: Mapped["FloorPlan"] = relationship(back_populates="manual_symbols")
    processing_job: Mapped["ProcessingJob"] = relationship(
        back_populates="manual_symbols"
    )
    creator: Mapped["User"] = relationship(back_populates="manual_symbols")
    symbol_legend: Mapped["SymbolLegend"] = relationship(
        back_populates="manual_symbols"
    )

    @validates("class_name")
    def validate_class_name(self, _key: str, value: object) -> str:
        if (
            type(value) is not str
            or not value
            or value != value.strip()
            or len(value) > MAXIMUM_MANUAL_SYMBOL_CLASS_NAME_LENGTH
            or "\x00" in value
        ):
            raise ValueError("Manual-symbol class names must be normalized and bounded.")
        return value
