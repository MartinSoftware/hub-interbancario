from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "%s v%s arrancando en modo %s",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.ENV,
    )
    yield
    logger.info("%s apagándose", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "API neutral que actúa como broker de mensajes entre bancos digitales. "
        "No custodia fondos ni mantiene deudas entre bancos."
    ),
    lifespan=lifespan,
    docs_url="/docs" if settings.is_dev else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.is_dev else None,
)


@app.get("/health", tags=["ops"])
async def health() -> JSONResponse:
    # Estado - Health
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "env": settings.ENV,
        },
    )


@app.get("/", tags=["ops"])
async def root() -> dict[str, str]:
    # Root Info
    return {
        "service": settings.APP_NAME,
        "docs": "/docs" if settings.is_dev else "disabled",
        "health": "/health",
    }