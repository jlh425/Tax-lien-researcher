"""FastAPI application factory."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import structlog

from aloha import __version__
from aloha.api.routes.auth import router as auth_router
from aloha.api.routes.health import router as health_router
from aloha.api.routes.parcels import router as parcels_router
from aloha.api.routes.scan import router as scan_router
from aloha.config import settings
from aloha.core.logging import configure_logging

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Handle application startup and shutdown events."""
    configure_logging()
    log.info("aloha_starting", version=__version__, env=settings.environment)

    # Start queue worker in the background
    from aloha.agents.orchestrator.agent import agent as orchestrator
    worker_task = asyncio.create_task(orchestrator.run_forever())

    yield

    # Graceful shutdown
    orchestrator.stop()
    worker_task.cancel()
    try:
        await asyncio.wait_for(worker_task, timeout=10.0)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        pass
    log.info("aloha_shutdown")


def create_app() -> FastAPI:
    """Build and return a configured FastAPI instance."""
    application = FastAPI(
        title="Aloha — Tax Lien/Deed Research Platform",
        version=__version__,
        description="AI-powered tax lien and tax deed investment research platform.",
        lifespan=lifespan,
    )

    # ── Middleware ─────────────────────────────────────────────────────────
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.environment == "development" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────
    application.include_router(health_router)
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(parcels_router, prefix="/api/v1")
    application.include_router(scan_router, prefix="/api/v1")

    return application


app = create_app()
