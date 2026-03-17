"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aloha import __version__
from aloha.api.routes.health import router as health_router
from aloha.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Handle application startup and shutdown events."""
    # ── Startup ───────────────────────────────────────────────────────────
    # TODO: initialise DB connection pool, Redis, background workers
    yield
    # ── Shutdown ──────────────────────────────────────────────────────────
    # TODO: drain queues, close pools


def create_app() -> FastAPI:
    """Build and return a configured FastAPI instance."""
    application = FastAPI(
        title="Aloha — Tax Lien/Deed Research Platform",
        version=__version__,
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

    return application


app = create_app()
