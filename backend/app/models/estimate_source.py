from sqlalchemy import BigInteger, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class EstimateSource(Base):
    """Immutable generation inputs and retry identity, separate from O1 tables."""
    __tablename__ = "estimate_sources"
    __table_args__ = (UniqueConstraint("project_id", "request_id", name="uq_estimate_request"),)
    estimate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("estimates.id"), primary_key=True)
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("projects.id"), nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
