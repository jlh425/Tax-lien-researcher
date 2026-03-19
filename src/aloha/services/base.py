"""Base service — shared session + structlog binding."""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession


class BaseService:
    """Base class for all services.

    Provides an async database session and a pre-bound structlog logger.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.log = structlog.get_logger().bind(service=self.__class__.__name__)
