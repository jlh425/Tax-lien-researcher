"""Structlog configuration for JSON-based structured logging."""

from __future__ import annotations

import logging
import sys

import structlog

from aloha.config import settings


def configure_logging() -> None:
    """Set up structlog with a JSON processor pipeline.

    Call this once at application startup (e.g. inside the FastAPI lifespan
    context manager).  After this runs, both ``structlog.get_logger()`` and
    the stdlib ``logging`` module will emit structured JSON lines.
    """
    log_level = getattr(logging, settings.log_level.upper(), logging.DEBUG)

    # ── Shared processors used by both structlog and stdlib ───────────────
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    # ── Structlog configuration ───────────────────────────────────────────
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # ── Stdlib logging handler so third-party libs also emit JSON ─────────
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)
