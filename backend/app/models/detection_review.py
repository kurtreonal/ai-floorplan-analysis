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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


if TYPE_CHECKING:
    from app.models.detected_symbol import DetectedSymbol
    from app.models.user import User


DETECTION_REVIEW_DECISIONS = ("confirmed", "deleted")


class DetectionReview(Base):
    __tablename__ = "detection_reviews"
    __table_args__ = (
        UniqueConstraint(
            "detected_symbol_id",
            "sequence_number",
            name="uq_detection_reviews_symbol_sequence",
        ),
        CheckConstraint(
            "sequence_number > 0",
            name="ck_detection_reviews_sequence_number",
        ),
        CheckConstraint(
            "decision IN ('confirmed', 'deleted')",
            name="ck_detection_reviews_decision",
        ),
        Index(
            "ix_detection_reviews_detected_symbol_id",
            "detected_symbol_id",
        ),
        Index(
            "ix_detection_reviews_reviewer_user_id",
            "reviewer_user_id",
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
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    detected_symbol: Mapped["DetectedSymbol"] = relationship(
        back_populates="reviews"
    )
    reviewer: Mapped["User"] = relationship(back_populates="detection_reviews")
