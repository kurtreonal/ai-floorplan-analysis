from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


if TYPE_CHECKING:
    from app.models.project_floor import ProjectFloor
    from app.models.user import User


PROJECT_STATUSES = (
    "draft",
    "uploaded",
    "processing",
    "needs_review",
    "layout_ready",
    "routing_ready",
    "estimated",
    "report_ready",
    "archived",
)


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'draft', 'uploaded', 'processing', 'needs_review', "
            "'layout_ready', 'routing_ready', 'estimated', "
            "'report_ready', 'archived'"
            ")",
            name="ck_projects_status",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    owner_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="draft",
        server_default="draft",
    )
    client_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    location: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    owner: Mapped["User"] = relationship(back_populates="projects")
    project_floors: Mapped[list["ProjectFloor"]] = relationship(
        back_populates="project"
    )
