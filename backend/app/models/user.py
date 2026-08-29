from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


if TYPE_CHECKING:
    from app.models.detection_review import DetectionReview
    from app.models.project import Project
    from app.models.role import Role


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint(
            "oauth_provider",
            "oauth_subject",
            name="uq_users_oauth_provider_subject",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    oauth_provider: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    oauth_subject: Mapped[str] = mapped_column(
        String(255, collation="utf8mb4_bin"),
        nullable=False,
    )
    email: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
    )
    display_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    avatar_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    role_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("roles.id"),
        nullable=False,
        index=True,
    )

    role: Mapped["Role"] = relationship(back_populates="users")
    projects: Mapped[list["Project"]] = relationship(back_populates="owner")
    detection_reviews: Mapped[list["DetectionReview"]] = relationship(
        back_populates="reviewer"
    )
