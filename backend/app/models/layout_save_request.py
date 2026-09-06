from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


if TYPE_CHECKING:
    from app.models.layout_version import LayoutVersion


class LayoutSaveRequest(Base):
    __tablename__ = "layout_save_requests"
    __table_args__ = (
        UniqueConstraint(
            "project_floor_id",
            "idempotency_key",
            name="uq_layout_save_requests_floor_key",
        ),
        CheckConstraint(
            "expected_version_number IS NULL OR expected_version_number > 0",
            name="ck_layout_save_requests_expected_version",
        ),
        CheckConstraint(
            "CHAR_LENGTH(idempotency_key) = 36",
            name="ck_layout_save_requests_key_length",
        ),
        CheckConstraint(
            "CHAR_LENGTH(geometry_sha256) = 64",
            name="ck_layout_save_requests_hash_length",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_floor_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("project_floors.id"),
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(36, collation="ascii_bin"))
    expected_version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    geometry_sha256: Mapped[str] = mapped_column(String(64, collation="ascii_bin"))
    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        index=True,
    )
    layout_version_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("layout_versions.id"),
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    layout_version: Mapped["LayoutVersion"] = relationship()
