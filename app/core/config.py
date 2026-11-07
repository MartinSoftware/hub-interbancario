from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    ENV: Literal["dev", "prod", "test"] = "dev"
    APP_NAME: str = "Hub Interbancario"
    APP_VERSION: str = "0.1.0"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Servidor
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Base de datos
    DATABASE_URL: str = "postgresql+asyncpg://hub:hub@localhost:5432/hub"
    DATABASE_ECHO: bool = False

    # JWT / OAuth2
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = 60

    # Webhooks
    WEBHOOK_TIMEOUT_SECONDS: int = 30
    WEBHOOK_MAX_RETRIES: int = 3
    WEBHOOK_RETRY_BACKOFF_MINUTES: str = "1,5,15"

    # Seguridad
    SIGNATURE_MAX_DRIFT_SECONDS: int = 300

    # Worker
    WORKER_POLL_INTERVAL_SECONDS: int = 2
    WORKER_BATCH_SIZE: int = 10

    @property
    def is_dev(self) -> bool:
        return self.ENV == "dev"

    @property
    def retry_backoff_list(self) -> list[int]:
        """Convierte "1,5,15" en [1, 5, 15]."""
        return [int(x.strip()) for x in self.WEBHOOK_RETRY_BACKOFF_MINUTES.split(",")]

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_db_url(cls, v: str) -> str:
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL debe empezar con postgresql+asyncpg://")
        return v


@lru_cache
def get_settings() -> Settings:
    """
    Cachea la instancia de Settings.
    `lru_cache` evita releer el .env en cada request.
    """
    return Settings()

settings = get_settings()