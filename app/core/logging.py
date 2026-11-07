import logging
import sys
from logging.config import dictConfig

from app.core.config import settings


def configure_logging() -> None:
    """Configura logging estructurado con formato legible en dev."""
    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        if settings.is_dev
        else "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": log_format,
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "stream": sys.stdout,
                },
            },
            "root": {
                "level": settings.LOG_LEVEL,
                "handlers": ["console"],
            },
            "loggers": {
                # Silencia el ruido de librerías externas
                "uvicorn.access": {"level": "WARNING"},
                "sqlalchemy.engine": {
                    "level": "INFO" if settings.DATABASE_ECHO else "WARNING"
                },
            },
        }
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)