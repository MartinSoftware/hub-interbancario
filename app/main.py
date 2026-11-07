from app.api.v1.router import api_router
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.exceptions import HubError

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
app.include_router(api_router)

# ─────────────────────────────────────────────────────────────
# Handler global para excepciones del Hub
# ─────────────────────────────────────────────────────────────
@app.exception_handler(HubError)
async def hub_error_handler(request: Request, exc: HubError) -> JSONResponse:
    logger.warning(
        "HubError %s en %s %s: %s",
        exc.error_code,
        request.method,
        request.url.path,
        exc.message,
    )
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details or None,
            "request_id": request.headers.get("X-Request-Id"),
        },
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