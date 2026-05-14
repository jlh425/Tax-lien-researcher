"""FastAPI dependency injection helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aloha.config import Settings, settings
from aloha.db.engine import async_session_factory

_bearer = HTTPBearer(auto_error=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield an async database session, committing on success."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            # Catch-all: rollback on any error to keep the session clean
            await session.rollback()
            raise


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> Any | None:
    """Return the authenticated User model, or None if no token provided.

    Raises 401 if a token is present but invalid.
    """
    if credentials is None:
        return None

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id_str: str | None = payload.get("sub")
        if not user_id_str:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    from aloha.db.models.user import User

    user = await db.get(User, UUID(user_id_str))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def require_user(
    user: Any = Depends(get_current_user),
) -> Any:
    """Like get_current_user but raises 401 if not authenticated."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


def get_settings() -> Settings:
    """Return the application settings singleton."""
    return settings


# ── Service factories ────────────────────────────────────────────────────


def get_auth_service(
    db: AsyncSession = Depends(get_db),
) -> "AuthService":
    """Return an AuthService bound to the current request session."""
    from aloha.services.auth_service import AuthService

    return AuthService(db, settings)


def get_parcel_service(
    db: AsyncSession = Depends(get_db),
) -> "ParcelService":
    """Return a ParcelService bound to the current request session."""
    from aloha.services.parcel_service import ParcelService

    return ParcelService(db)


def get_billing_service(
    db: AsyncSession = Depends(get_db),
) -> "BillingService":
    """Return a BillingService bound to the current request session."""
    from aloha.services.billing_service import BillingService

    return BillingService(db)


def get_research_service(
    db: AsyncSession = Depends(get_db),
) -> "ResearchService":
    """Return a ResearchService bound to the current request session."""
    from aloha.services.billing_service import BillingService
    from aloha.services.research_service import ResearchService

    return ResearchService(db, BillingService(db))


def get_export_service(
    db: AsyncSession = Depends(get_db),
) -> "ExportService":
    """Return an ExportService bound to the current request session."""
    from aloha.services.export_service import ExportService

    return ExportService(db)


def get_outreach_service(
    db: AsyncSession = Depends(get_db),
) -> "OutreachService":
    """Return an OutreachService bound to the current request session."""
    from aloha.services.outreach_service import OutreachService

    return OutreachService(db)


def get_notification_service(
    db: AsyncSession = Depends(get_db),
) -> "NotificationService":
    """Return a NotificationService bound to the current request session."""
    from aloha.services.notification_service import NotificationService

    return NotificationService(db)
