from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Role, User


def find_user_by_external_identity(
    database_session: Session,
    *,
    provider: str,
    subject: str,
) -> User | None:
    return database_session.scalar(
        select(User).where(
            User.oauth_provider == provider,
            User.oauth_subject == subject,
        )
    )


def find_user_by_id_with_role(
    database_session: Session,
    *,
    user_id: int,
) -> User | None:
    return database_session.scalar(
        select(User)
        .options(joinedload(User.role))
        .where(User.id == user_id)
        .execution_options(populate_existing=True)
    )


def find_role_by_name(database_session: Session, *, name: str) -> Role | None:
    return database_session.scalar(select(Role).where(Role.name == name))


def add_user(database_session: Session, user: User) -> User:
    database_session.add(user)
    database_session.flush()
    return user
