from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


if TYPE_CHECKING:
    from app.models.processing_job import ProcessingJob
    from app.models.project_floor import ProjectFloor
    from app.models.wall import Wall


class FloorPlan(Base):
    __tablename__ = "floor_plans"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    project_floor_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("project_floors.id"),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    storage_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    processing_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="uploaded",
        server_default="uploaded",
    )

    project_floor: Mapped["ProjectFloor"] = relationship(
        back_populates="floor_plans"
    )
    processing_jobs: Mapped[list["ProcessingJob"]] = relationship(
        back_populates="floor_plan"
    )
    walls: Mapped[list["Wall"]] = relationship(back_populates="floor_plan")
