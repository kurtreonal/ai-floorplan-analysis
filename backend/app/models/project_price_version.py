"""Immutable, project-owned client imports. Never write the shared catalog."""
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.dialects.mysql import MEDIUMBLOB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class ProjectPriceVersion(Base):
    __tablename__ = 'project_price_versions'

    @property
    def usage(self):
        return self.document.get('usage', 'project_default')
    __table_args__ = (
        UniqueConstraint('project_id', 'version_number', name='uq_project_price_version'),
        UniqueConstraint('project_id', 'request_id', name='uq_project_price_request'),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('projects.id'), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    document: Mapped[dict] = mapped_column(JSON, nullable=False, deferred=True)
    source_bytes: Mapped[bytes] = mapped_column(LargeBinary().with_variant(MEDIUMBLOB(), 'mysql'), nullable=False, deferred=True)
