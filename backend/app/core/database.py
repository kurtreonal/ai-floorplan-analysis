from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


MYSQL_DRIVER = "mysql+pymysql"
CONNECTION_TIMEOUT_SECONDS = 5


class DatabaseConfigurationError(RuntimeError):
    """Raised when database configuration is missing or unsupported."""


class DatabaseConnectionError(RuntimeError):
    """Raised when the configured database cannot be reached safely."""


@lru_cache
def get_engine() -> Engine:
    database_url = get_settings().database_url
    if not database_url:
        raise DatabaseConfigurationError(
            "DATABASE_URL is required when database functionality is used."
        )

    try:
        url = make_url(database_url)
    except ArgumentError:
        raise DatabaseConfigurationError(
            "DATABASE_URL is not a valid SQLAlchemy database URL."
        ) from None

    if url.drivername != MYSQL_DRIVER:
        raise DatabaseConfigurationError(
            f"DATABASE_URL must use the {MYSQL_DRIVER} driver."
        )

    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": CONNECTION_TIMEOUT_SECONDS},
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        expire_on_commit=False,
    )


def get_db() -> Generator[Session, None, None]:
    database_session = get_session_factory()()
    try:
        yield database_session
    finally:
        database_session.close()


def verify_database_connection() -> bool:
    try:
        with get_engine().connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar_one()
    except SQLAlchemyError:
        raise DatabaseConnectionError(
            "Unable to connect to the configured database."
        ) from None

    if result != 1:
        raise DatabaseConnectionError(
            "The configured database returned an unexpected connectivity result."
        )

    return True
