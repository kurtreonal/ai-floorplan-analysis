from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.models.base import Base


if TYPE_CHECKING:
    from app.models.detection_class_correction import DetectionClassCorrection
    from app.models.manual_symbol import ManualSymbol


MAXIMUM_SYMBOL_LEGEND_NAME_LENGTH = 255


class SymbolLegend(Base):
    __tablename__ = "symbol_legends"
    __table_args__ = (
        UniqueConstraint(
            "class_id",
            name="uq_symbol_legends_class_id",
        ),
        UniqueConstraint(
            "name",
            name="uq_symbol_legends_name",
        ),
        CheckConstraint(
            "class_id >= 0",
            name="ck_symbol_legends_class_id",
        ),
        CheckConstraint(
            "name = TRIM(name) AND CHAR_LENGTH(name) BETWEEN 1 AND 255",
            name="ck_symbol_legends_name",
        ),
        Index(
            "ix_symbol_legends_active_class_order",
            "is_active",
            "class_id",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    class_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(
        String(MAXIMUM_SYMBOL_LEGEND_NAME_LENGTH, collation="utf8mb4_bin"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="1",
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

    corrections_as_old: Mapped[list["DetectionClassCorrection"]] = relationship(
        foreign_keys="DetectionClassCorrection.old_symbol_legend_id",
        back_populates="old_symbol_legend",
    )
    corrections_as_new: Mapped[list["DetectionClassCorrection"]] = relationship(
        foreign_keys="DetectionClassCorrection.new_symbol_legend_id",
        back_populates="new_symbol_legend",
    )
    manual_symbols: Mapped[list["ManualSymbol"]] = relationship(
        back_populates="symbol_legend"
    )

    @validates("name")
    def validate_name(self, _key: str, value: object) -> str:
        if (
            type(value) is not str
            or not value
            or value != value.strip()
            or len(value) > MAXIMUM_SYMBOL_LEGEND_NAME_LENGTH
            or "\x00" in value
        ):
            raise ValueError("Symbol legend names must be normalized and bounded.")
        return value
