import sys

from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateColumn
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.database import DatabaseConfigurationError, get_engine


class DevelopmentSchemaInitializationError(RuntimeError):
    """Raised when explicit development schema initialization cannot proceed."""


def ensure_project_intake_columns(engine) -> tuple[str, ...]:
    """Explicit prototype compatibility expansion, never called by HTTP startup.

    Only add nullable intake columns. Never rewrite, drop, reset or populate data.
    Back up the database before running the existing development initializer.
    """
    from app.models import Project
    if get_settings().app_env.casefold() != 'development':
        raise DevelopmentSchemaInitializationError('Project intake expansion requires APP_ENV=development.')
    if engine.dialect.name != 'mysql':
        raise DevelopmentSchemaInitializationError('Project intake expansion requires the configured MySQL database.')
    names = ('contact_number', 'service_type', 'service_type_other', 'preferred_start_date', 'blueprint_availability')
    with engine.begin() as connection:
        existing = {column['name']: column for column in inspect(connection).get_columns('projects')}
        for name in names:
            if name in existing:
                expected = Project.__table__.c[name]
                actual = existing[name]
                if (not actual['nullable'] or str(actual['type']).upper() != str(expected.type.compile(dialect=engine.dialect)).upper()):
                    raise DevelopmentSchemaInitializationError('An existing project intake column has an incompatible definition; no repair was attempted.')
        added = []
        for name in names:
            if name not in existing:
                definition = str(CreateColumn(Project.__table__.c[name]).compile(dialect=engine.dialect))
                connection.execute(text('ALTER TABLE projects ADD COLUMN ' + definition))
                added.append(name)
        return tuple(added)


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
        ensure_project_intake_columns(engine)
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
