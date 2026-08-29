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
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.models.base import Base


if TYPE_CHECKING:
    from app.models.detected_symbol import DetectedSymbol
    from app.models.symbol_legend import SymbolLegend
    from app.models.user import User


MAXIMUM_CLASS_NAME_LENGTH = 255


class DetectionClassCorrection(Base):
    __tablename__ = "detection_class_corrections"
    __table_args__ = (
        UniqueConstraint(
            "detected_symbol_id",
            "sequence_number",
            name="uq_detection_class_corrections_symbol_sequence",
        ),
        CheckConstraint(
            "sequence_number > 0",
            name="ck_detection_class_corrections_sequence_number",
        ),
        CheckConstraint(
            "old_class_id >= 0 AND new_class_id >= 0",
            name="ck_detection_class_corrections_class_ids",
        ),
        CheckConstraint(
            "old_class_name = TRIM(old_class_name) "
            "AND CHAR_LENGTH(old_class_name) BETWEEN 1 AND 255 "
            "AND new_class_name = TRIM(new_class_name) "
            "AND CHAR_LENGTH(new_class_name) BETWEEN 1 AND 255",
            name="ck_detection_class_corrections_class_names",
        ),
        Index(
            "ix_detection_class_corrections_detected_symbol_id",
            "detected_symbol_id",
        ),
        Index(
            "ix_detection_class_corrections_reviewer_user_id",
            "reviewer_user_id",
        ),
        Index(
            "ix_detection_class_corrections_old_symbol_legend_id",
            "old_symbol_legend_id",
        ),
        Index(
            "ix_detection_class_corrections_new_symbol_legend_id",
            "new_symbol_legend_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    detected_symbol_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("detected_symbols.id"),
        nullable=False,
    )
    reviewer_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    old_symbol_legend_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("symbol_legends.id"),
        nullable=True,
    )
    old_class_id: Mapped[int] = mapped_column(Integer, nullable=False)
    old_class_name: Mapped[str] = mapped_column(
        String(MAXIMUM_CLASS_NAME_LENGTH, collation="utf8mb4_bin"),
        nullable=False,
    )
    new_symbol_legend_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("symbol_legends.id"),
        nullable=False,
    )
    new_class_id: Mapped[int] = mapped_column(Integer, nullable=False)
    new_class_name: Mapped[str] = mapped_column(
        String(MAXIMUM_CLASS_NAME_LENGTH, collation="utf8mb4_bin"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    detected_symbol: Mapped["DetectedSymbol"] = relationship(
        back_populates="class_corrections"
    )
    reviewer: Mapped["User"] = relationship(
        back_populates="detection_class_corrections"
    )
    old_symbol_legend: Mapped["SymbolLegend | None"] = relationship(
        foreign_keys=[old_symbol_legend_id],
        back_populates="corrections_as_old",
    )
    new_symbol_legend: Mapped["SymbolLegend"] = relationship(
        foreign_keys=[new_symbol_legend_id],
        back_populates="corrections_as_new",
    )

    @validates("old_class_name", "new_class_name")
    def validate_class_name(self, _key: str, value: object) -> str:
        if (
            type(value) is not str
            or not value
            or value != value.strip()
            or len(value) > MAXIMUM_CLASS_NAME_LENGTH
            or "\x00" in value
        ):
            raise ValueError("Correction class names must be normalized and bounded.")
        return value
