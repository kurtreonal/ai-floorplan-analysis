from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User
from app.services.authentication import resolve_current_user


def _authentication_error(
    *,
    status_code: int,
    code: str,
    message: str,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code,
                "message": message,
                "details": {},
            }
        },
    )


def get_current_user(
    request: Request,
    database_session: Session = Depends(get_db),
) -> User:
    session_data = request.scope.get("session")
    if not isinstance(session_data, dict):
        raise _authentication_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTHENTICATION_REQUIRED",
            message="Authentication is required.",
        )

    user_id = session_data.get("user_id")
    if type(user_id) is not int or user_id <= 0:
        session_data.pop("user_id", None)
        raise _authentication_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTHENTICATION_REQUIRED",
            message="Authentication is required.",
        )

    try:
        user = resolve_current_user(
            database_session,
            user_id=user_id,
        )
    except SQLAlchemyError:
        raise _authentication_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="AUTH_USER_LOOKUP_FAILED",
            message="The local user record could not be loaded.",
        ) from None

    if user is None or user.role is None:
        session_data.pop("user_id", None)
        raise _authentication_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTHENTICATION_REQUIRED",
            message="Authentication is required.",
        )

    return user


def require_roles(*allowed_role_names: str) -> Callable[[User], User]:
    if not allowed_role_names or any(
        not isinstance(role_name, str) or not role_name.strip()
        for role_name in allowed_role_names
    ):
        raise ValueError("At least one non-empty role name is required.")

    allowed_roles = frozenset(
        role_name.strip().upper() for role_name in allowed_role_names
    )

    def role_dependency(
        current_user: User = Depends(get_current_user),
    ) -> User:
        role = current_user.role
        if role is None or role.name not in allowed_roles:
            raise _authentication_error(
                status_code=status.HTTP_403_FORBIDDEN,
                code="AUTHORIZATION_DENIED",
                message="The authenticated user is not authorized for this action.",
            )
        return current_user

    return role_dependency
