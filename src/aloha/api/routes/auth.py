"""Authentication routes — register, login, and token refresh."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from aloha.api.deps import get_db, get_settings
from aloha.api.schemas.parcels import LoginRequest, RegisterRequest, TokenResponse
from aloha.config import Settings
from aloha.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _auth_service(
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthService:
    return AuthService(db, settings)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    svc: AuthService = Depends(_auth_service),
) -> TokenResponse:
    """Create a new user account and return an access token."""
    return await svc.register(body.email, body.password, body.name)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    svc: AuthService = Depends(_auth_service),
) -> TokenResponse:
    """Authenticate a user and return an access token."""
    return await svc.login(body.email, body.password)
