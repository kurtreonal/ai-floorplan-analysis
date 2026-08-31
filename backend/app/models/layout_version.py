from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


if TYPE_CHECKING:
    from app.models.floor_plan import FloorPlan
    from app.models.project import Project
    from app.models.project_floor import ProjectFloor


class LayoutVersion(Base):
    __tablename__ = "layout_versions"
    __table_args__ = (
        UniqueConstraint(
            "project_floor_id",
            "version_number",
            name="uq_layout_versions_floor_version",
        ),
        UniqueConstraint(
            "project_floor_id",
            "is_current",
            name="uq_layout_versions_floor_current",
        ),
        CheckConstraint(
            "version_number > 0",
            name="ck_layout_versions_version_number",
        ),
        CheckConstraint(
            "schema_version = 1",
            name="ck_layout_versions_schema_version",
        ),
        CheckConstraint(
            "is_current IS NULL OR is_current = 1",
            name="ck_layout_versions_current_marker",
        ),
        Index(
            "ix_layout_versions_project_floor_id",
            "project_id",
            "project_floor_id",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id"),
        nullable=False,
    )
    project_floor_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("project_floors.id"),
        nullable=False,
    )
    floor_plan_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("floor_plans.id"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    geometry_document: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
    )
    is_current: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    project: Mapped["Project"] = relationship(back_populates="layout_versions")
    project_floor: Mapped["ProjectFloor"] = relationship(
        back_populates="layout_versions"
    )
    floor_plan: Mapped["FloorPlan"] = relationship(
        back_populates="layout_versions"
    )
