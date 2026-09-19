"""Company material identities; prices belong to the separate pricing domain."""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.models.base import Base


class Material(Base):
    __tablename__ = "materials"
    __table_args__ = tuple(
        CheckConstraint(
            f"{field} = TRIM({field}) AND CHAR_LENGTH({field}) BETWEEN 1 AND {limit}",
            name=f"ck_materials_{field}",
        )
        for field, limit in (("code", 64), ("name", 255), ("unit", 32), ("category", 100))
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    @validates("code", "name", "unit", "category")
    def validate_text(self, key: str, value: object) -> str:
        limit = self.__table__.c[key].type.length
        if type(value) is not str or not value or value != value.strip() or len(value) > limit or "\x00" in value:
            raise ValueError(f"Material {key} must be normalized, nonempty and bounded.")
        return value
