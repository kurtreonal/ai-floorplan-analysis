from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.client_workflow import LinkedIdentity

from app.models import User
from app.repositories.user_repository import (
    find_user_by_external_identity,
    find_user_by_id_with_role,
)


class AuthenticationServiceError(RuntimeError):
    """Raised when a verified identity cannot be mapped to a local user."""


class AccountNotProvisioned(AuthenticationServiceError):
    """A provider identity is not an enabled, previously provisioned account."""


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
    user = find_user_by_id_with_role(
        database_session,
        user_id=user_id,
    )
    from app.services.local_accounts import account_enabled, credential_for
    if not user or not account_enabled(database_session, user.id):
        return None
    if user.role.name != 'ADMIN' and credential_for(database_session, user.id) is None:
        return None
    return user


def resolve_external_user(
    database_session: Session,
    identity: ExternalOIDCIdentity,
) -> tuple[User, bool]:
    user = find_user_by_external_identity(
        database_session,
        provider=identity.provider,
        subject=identity.subject,
    )
    linked = database_session.scalar(select(LinkedIdentity).where(
        LinkedIdentity.provider == identity.provider, LinkedIdentity.subject == identity.subject))
    if linked:
        user = database_session.get(User, linked.user_id)
    if user is not None:
        from app.services.local_accounts import account_enabled, credential_for
        # Preserve explicitly provisioned Admin access for bootstrap. Designer and
        # Client Google login requires a managed password account and prior link.
        if not account_enabled(database_session, user.id) or (user.role.name != 'ADMIN'
                and (credential_for(database_session, user.id) is None or linked is None)):
            raise AccountNotProvisioned()
        # Google is a sign-in method, not authority to rename a managed account.
        return user, False
    # Never auto-provision or match by email: linking requires an authenticated
    # account and current-password confirmation in the explicit linking flow.
    raise AccountNotProvisioned()
