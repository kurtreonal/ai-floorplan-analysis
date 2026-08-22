from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models import User
from app.repositories.user_repository import (
    add_user,
    find_role_by_name,
    find_user_by_external_identity,
    find_user_by_id_with_role,
)


DEFAULT_NEW_USER_ROLE = "DESIGNER"


class AuthenticationServiceError(RuntimeError):
    """Raised when a verified identity cannot be mapped to a local user."""


class ExternalOIDCIdentity(BaseModel):
    provider: str = Field(min_length=1, max_length=64)
    subject: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    display_name: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = None


def resolve_current_user(
    database_session: Session,
    *,
    user_id: int,
) -> User | None:
    return find_user_by_id_with_role(
        database_session,
        user_id=user_id,
    )


def resolve_external_user(
    database_session: Session,
    identity: ExternalOIDCIdentity,
) -> tuple[User, bool]:
    user = find_user_by_external_identity(
        database_session,
        provider=identity.provider,
        subject=identity.subject,
    )
    if user is not None:
        if identity.email is not None:
            user.email = identity.email
        if identity.display_name is not None:
            user.display_name = identity.display_name
        if identity.avatar_url is not None:
            user.avatar_url = identity.avatar_url
        database_session.flush()
        return user, False

    default_role = find_role_by_name(
        database_session,
        name=DEFAULT_NEW_USER_ROLE,
    )
    if default_role is None:
        raise AuthenticationServiceError(
            "The default local role is unavailable. Run the development role seed."
        )

    user = User(
        oauth_provider=identity.provider,
        oauth_subject=identity.subject,
        email=identity.email,
        display_name=identity.display_name,
        avatar_url=identity.avatar_url,
        role_id=default_role.id,
    )
    return add_user(database_session, user), True
