import re
from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, BaseModel, Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
OAUTH_PLACEHOLDER_VALUES = frozenset(
    {"change_me", "changeme", "configure_me", "placeholder", "replace_me"}
)


class OAuthOIDCConfigurationError(RuntimeError):
    """Raised when the authentication feature lacks safe OAuth/OIDC settings."""


class CORSConfigurationError(RuntimeError):
    """Raised when credentialed CORS configuration is unsafe."""


class OAuthOIDCConfiguration(BaseModel):
    provider: str
    client_id: str
    client_secret: SecretStr
    redirect_uri: AnyHttpUrl
    discovery_url: AnyHttpUrl
    scopes: tuple[str, ...]
    session_secret: SecretStr


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "production"
    app_name: str = "VED Electrical Services"
    app_debug: bool = False

    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    api_prefix: str = "/api"

    frontend_url: str = "http://localhost:5173"

    database_url: str | None = None

    oauth_provider: str | None = None
    oauth_client_id: str | None = None
    oauth_client_secret: SecretStr | None = None
    oauth_redirect_uri: str | None = None
    oauth_discovery_url: str | None = None
    oauth_scopes: str | None = None
    session_secret: SecretStr | None = None

    upload_dir: Path | None = None
    processed_dir: Path | None = None
    detection_dir: Path | None = None
    preview_dir: Path | None = None
    report_dir: Path | None = None

    max_upload_size_mb: int = Field(default=25, gt=0)
    allowed_upload_extensions: str = ".jpg,.jpeg,.png,.pdf"

    yolo_model_path: Path | None = None
    yolo_confidence_threshold: float = Field(default=0.50, ge=0, le=1)

    cors_allowed_origins: str = "http://localhost:5173"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_max_upload_size_bytes(settings: Settings | None = None) -> int:
    source = settings or get_settings()
    return source.max_upload_size_mb * 1024 * 1024


def get_cors_allowed_origins(settings: Settings | None = None) -> tuple[str, ...]:
    source = settings or get_settings()
    origins = tuple(
        dict.fromkeys(
            origin.strip()
            for origin in source.cors_allowed_origins.split(",")
            if origin.strip()
        )
    )
    if "*" in origins:
        raise CORSConfigurationError(
            "CORS_ALLOWED_ORIGINS cannot contain '*' when credentials are enabled."
        )
    return origins


def get_oauth_oidc_configuration(
    settings: Settings | None = None,
) -> OAuthOIDCConfiguration:
    source = settings or get_settings()
    environment_values: dict[str, str | SecretStr | None] = {
        "OAUTH_PROVIDER": source.oauth_provider,
        "OAUTH_CLIENT_ID": source.oauth_client_id,
        "OAUTH_CLIENT_SECRET": source.oauth_client_secret,
        "OAUTH_REDIRECT_URI": source.oauth_redirect_uri,
        "OAUTH_DISCOVERY_URL": source.oauth_discovery_url,
        "OAUTH_SCOPES": source.oauth_scopes,
        "SESSION_SECRET": source.session_secret,
    }

    plain_values = {
        name: value.get_secret_value() if isinstance(value, SecretStr) else value
        for name, value in environment_values.items()
    }
    missing_names = tuple(
        name
        for name, value in plain_values.items()
        if value is None or not value.strip()
    )
    if missing_names:
        raise OAuthOIDCConfigurationError(
            "OAuth/OIDC configuration is incomplete. Missing: "
            f"{', '.join(missing_names)}."
        )

    placeholder_names = tuple(
        name
        for name, value in plain_values.items()
        if value is not None
        and value.strip().casefold() in OAUTH_PLACEHOLDER_VALUES
    )
    if placeholder_names:
        raise OAuthOIDCConfigurationError(
            "OAuth/OIDC configuration contains placeholder values for: "
            f"{', '.join(placeholder_names)}."
        )

    scopes = tuple(
        dict.fromkeys(
            scope
            for scope in re.split(r"[\s,]+", plain_values["OAUTH_SCOPES"].strip())
            if scope
        )
    )
    if "openid" not in scopes:
        raise OAuthOIDCConfigurationError(
            "OAuth/OIDC configuration is invalid: "
            "OAUTH_SCOPES must include openid."
        )

    try:
        return OAuthOIDCConfiguration(
            provider=plain_values["OAUTH_PROVIDER"],
            client_id=plain_values["OAUTH_CLIENT_ID"],
            client_secret=source.oauth_client_secret,
            redirect_uri=plain_values["OAUTH_REDIRECT_URI"],
            discovery_url=plain_values["OAUTH_DISCOVERY_URL"],
            scopes=scopes,
            session_secret=source.session_secret,
        )
    except ValidationError:
        raise OAuthOIDCConfigurationError(
            "OAuth/OIDC configuration is invalid. Check the configured "
            "provider, client ID, redirect URI, discovery URL, and scopes."
        ) from None
