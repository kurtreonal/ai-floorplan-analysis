import sys

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.database import DatabaseConfigurationError, get_session_factory


INITIAL_ROLE_NAMES = ("ADMIN", "DESIGNER")


class DevelopmentSeedError(RuntimeError):
    """Raised when explicit development reference-data seeding cannot proceed."""


def seed_initial_roles() -> tuple[str, ...]:
    settings = get_settings()
    if settings.app_env.casefold() != "development":
        raise DevelopmentSeedError(
            "Development role seeding is only available when APP_ENV=development."
        )

    from app.models import Role

    try:
        session_factory = get_session_factory()
        with session_factory.begin() as database_session:
            existing_names = set(
                database_session.scalars(
                    select(Role.name).where(Role.name.in_(INITIAL_ROLE_NAMES))
                )
            )
            database_session.add_all(
                Role(name=role_name)
                for role_name in INITIAL_ROLE_NAMES
                if role_name not in existing_names
            )
    except DatabaseConfigurationError:
        raise DevelopmentSeedError(
            "Development role seeding requires valid database configuration."
        ) from None
    except SQLAlchemyError:
        raise DevelopmentSeedError(
            "Development role seeding could not update the configured database."
        ) from None

    return INITIAL_ROLE_NAMES


def main() -> int:
    try:
        role_names = seed_initial_roles()
    except DevelopmentSeedError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print("Development role seeding completed.")
    print(f"Required roles: {', '.join(role_names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
