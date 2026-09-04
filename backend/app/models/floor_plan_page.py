from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


if TYPE_CHECKING:
    from app.models.floor_plan_source import FloorPlanSource
    from app.models.processing_artifact import ProcessingArtifact


class FloorPlanPage(Base):
    __tablename__ = "floor_plan_pages"
    __table_args__ = (
        CheckConstraint("page_number > 0", name="ck_floor_plan_pages_number_positive"),
        UniqueConstraint(
            "floor_plan_source_id",
            "page_number",
            name="uq_floor_plan_pages_source_number",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    floor_plan_source_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("floor_plan_sources.id"),
        nullable=False,
        index=True,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)

    source_manifest: Mapped["FloorPlanSource"] = relationship(back_populates="pages")
    artifacts: Mapped[list["ProcessingArtifact"]] = relationship(
        back_populates="floor_plan_page"
    )
