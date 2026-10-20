"""Append-only item price choices, separate from uploaded quotes and geometry."""
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class ItemPriceAssignment(Base):
    __tablename__ = 'item_price_assignments'
    __table_args__ = (
        UniqueConstraint('project_id', 'version_number', name='uq_item_price_version'),
        UniqueConstraint('project_id', 'request_id', name='uq_item_price_request'),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('projects.id'), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict] = mapped_column(JSON, nullable=False)
