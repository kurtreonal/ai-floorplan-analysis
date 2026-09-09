from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


LongText = Text().with_variant(LONGTEXT(), "mysql")


class FloorPlanInterpretationReview(Base):
    __tablename__ = "floor_plan_interpretation_reviews"
    __table_args__ = (
        UniqueConstraint(
            "interpretation_run_id",
            "revision_number",
            name="uq_floor_plan_interpretation_reviews_run_revision",
        ),
        CheckConstraint(
            "revision_number > 0",
            name="ck_floor_plan_interpretation_reviews_revision",
        ),
        CheckConstraint(
            "CHAR_LENGTH(review_sha256) = 64",
            name="ck_floor_plan_interpretation_reviews_sha256",
        ),
        CheckConstraint(
            "approved_for_layout = 0 OR review_complete = 1",
            name="ck_floor_plan_interpretation_reviews_approval",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    interpretation_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("floor_plan_interpretation_runs.id"),
        nullable=False,
        index=True,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewed_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
    )
    review_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved_for_layout: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    review_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    review_json: Mapped[str] = mapped_column(LongText, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
