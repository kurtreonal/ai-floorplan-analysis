from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "VED Electrical Services"
    app_debug: bool = True

    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    api_prefix: str = "/api"

    frontend_url: str = "http://localhost:5173"

    database_url: str | None = None

    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=30, gt=0)
    jwt_refresh_token_expire_days: int = Field(default=7, gt=0)

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
