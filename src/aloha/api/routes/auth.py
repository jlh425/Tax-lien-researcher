"""Authentication routes — register, login, and token refresh."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aloha.api.deps import get_db
from aloha.api.schemas.parcels import LoginRequest, RegisterRequest, TokenResponse
from aloha.config import settings
from aloha.db.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


def _hash_password(password: str) -> str:
    """SHA-256 password hash with a fixed pepper from SECRET_KEY.

    Note: In production use a proper password hasher like bcrypt/argon2.
    This is a placeholder that avoids pulling in bcrypt as a dependency
    during initial build.  Replace before shipping.
    """
    salted = f"{settings.secret_key}:{password}"
    return hashlib.sha256(salted.encode()).hexdigest()


def _create_access_token(user_id: str, tier: str) -> str:
    """Create a signed JWT access token."""
    expire = datetime.now(tz=timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": user_id,
        "tier": tier,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Create a new user account and return an access token."""
    # Check for existing user
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        id=uuid.uuid4(),
        email=body.email,
        display_name=body.name,
        hashed_password=_hash_password(body.password),
        tier="free",
        is_active=True,
        created_at=datetime.now(tz=timezone.utc),
    )
    db.add(user)
    await db.flush()

    token = _create_access_token(str(user.id), user.tier)
    return TokenResponse(access_token=token, user_id=str(user.id), tier=user.tier)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate a user and return an access token."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalars().first()

    if not user or user.hashed_password != _hash_password(body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    token = _create_access_token(str(user.id), user.tier)
    return TokenResponse(access_token=token, user_id=str(user.id), tier=user.tier)
