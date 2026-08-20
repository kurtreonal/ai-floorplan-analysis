import sys

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.database import DatabaseConfigurationError, get_engine


class DevelopmentSchemaInitializationError(RuntimeError):
    """Raised when explicit development schema initialization cannot proceed."""


def initialize_development_schema() -> tuple[str, ...]:
    settings = get_settings()
    if settings.app_env.casefold() != "development":
        raise DevelopmentSchemaInitializationError(
            "Development schema initialization is only available when "
            "APP_ENV=development."
        )

    from app import models

    try:
        engine = get_engine()
        models.Base.metadata.create_all(bind=engine)
    except DatabaseConfigurationError:
        raise DevelopmentSchemaInitializationError(
            "Development schema initialization requires valid database configuration."
        ) from None
    except SQLAlchemyError:
        raise DevelopmentSchemaInitializationError(
            "Development schema initialization could not reach the configured database."
        ) from None

    return tuple(sorted(models.Base.metadata.tables))


def main() -> int:
    try:
        table_names = initialize_development_schema()
    except DevelopmentSchemaInitializationError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print("Development schema initialization completed.")
    print(f"Registered application tables: {len(table_names)}")
    if table_names:
        print(f"Tables: {', '.join(table_names)}")
    else:
        print("Tables: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
