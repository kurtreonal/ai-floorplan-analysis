from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


SYMBOL_LEGEND_HISTORY_ACTIONS = ("created", "updated", "activated", "deactivated")


class SymbolLegendHistory(Base):
    __tablename__ = "symbol_legend_history"
    __table_args__ = (
        UniqueConstraint(
            "symbol_legend_id",
            "sequence",
            name="uq_symbol_legend_history_sequence",
        ),
        CheckConstraint("sequence > 0", name="ck_symbol_legend_history_sequence"),
        CheckConstraint(
            "action IN ('created', 'updated', 'activated', 'deactivated')",
            name="ck_symbol_legend_history_action",
        ),
        CheckConstraint(
            "old_class_id IS NULL OR old_class_id >= 0",
            name="ck_symbol_legend_history_old_class_id",
        ),
        CheckConstraint("new_class_id >= 0", name="ck_symbol_legend_history_new_class_id"),
        CheckConstraint(
            "old_name IS NULL OR (old_name = TRIM(old_name) AND CHAR_LENGTH(old_name) BETWEEN 1 AND 255)",
            name="ck_symbol_legend_history_old_name",
        ),
        CheckConstraint(
            "new_name = TRIM(new_name) AND CHAR_LENGTH(new_name) BETWEEN 1 AND 255",
            name="ck_symbol_legend_history_new_name",
        ),
        CheckConstraint(
            "(action = 'created' AND old_class_id IS NULL AND old_name IS NULL AND old_is_active IS NULL) "
            "OR (action <> 'created' AND old_class_id IS NOT NULL AND old_name IS NOT NULL "
            "AND old_is_active IS NOT NULL)",
            name="ck_symbol_legend_history_old_snapshot",
        ),
        Index("ix_symbol_legend_history_actor_user_id", "actor_user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol_legend_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("symbol_legends.id"),
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(16))
    old_class_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    old_name: Mapped[str | None] = mapped_column(
        String(255, collation="utf8mb4_bin"),
        nullable=True,
    )
    old_is_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    new_class_id: Mapped[int] = mapped_column(Integer)
    new_name: Mapped[str] = mapped_column(String(255, collation="utf8mb4_bin"))
    new_is_active: Mapped[bool] = mapped_column(Boolean)
    actor_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
