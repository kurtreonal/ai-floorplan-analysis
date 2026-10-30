"""Admin-maintained device assemblies, backed by existing priced materials."""
from datetime import datetime
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class MaterialAssembly(Base):
    __tablename__ = 'material_assemblies'
    __table_args__ = (CheckConstraint('default_key IS NULL OR default_key = device_type',name='ck_assembly_default_type'),)
    material_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('materials.id'), primary_key=True)
    brand: Mapped[str] = mapped_column(String(80), nullable=False)
    device_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    default_key: Mapped[str | None] = mapped_column(String(40), nullable=True, unique=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    document: Mapped[dict] = mapped_column(JSON, nullable=False)
    price_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    @property
    def is_default(self):
        return self.default_key is not None

    @is_default.setter
    def is_default(self,value):
        self.default_key = self.device_type if value else None
