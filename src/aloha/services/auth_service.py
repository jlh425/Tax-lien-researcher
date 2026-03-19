"""Authentication service — registration, login, JWT, bcrypt hashing."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aloha.api.schemas.parcels import TokenResponse
from aloha.config import Settings
from aloha.db.models.user import User
from aloha.services.base import BaseService


class AuthService(BaseService):
    """Handles user registration, login, and JWT token management."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        super().__init__(session)
        self._settings = settings

    # ── Password helpers ─────────────────────────────────────────────────

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a plaintext password with bcrypt."""
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        """Verify a plaintext password against a bcrypt hash."""
        return bcrypt.checkpw(plain.encode(), hashed.encode())

    # ── JWT helpers ──────────────────────────────────────────────────────

    def create_access_token(self, user_id: str, tier: str) -> str:
        """Create a signed JWT access token."""
        expire = datetime.now(tz=timezone.utc) + timedelta(
            minutes=self._settings.access_token_expire_minutes,
        )
        payload = {"sub": user_id, "tier": tier, "exp": expire}
        return jwt.encode(
            payload,
            self._settings.secret_key,
            algorithm=self._settings.jwt_algorithm,
        )

    def decode_token(self, token: str) -> dict:
        """Decode and validate a JWT token, returning its payload."""
        try:
            return jwt.decode(
                token,
                self._settings.secret_key,
                algorithms=[self._settings.jwt_algorithm],
            )
        except JWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            ) from exc

    # ── Public API ───────────────────────────────────────────────────────

    async def register(self, email: str, password: str, name: str | None) -> TokenResponse:
        """Create a new user account and return an access token."""
        result = await self._session.execute(
            select(User).where(User.email == email),
        )
        if result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        user = User(
            id=uuid.uuid4(),
            email=email,
            display_name=name,
            hashed_password=self.hash_password(password),
            tier="free",
            is_active=True,
            created_at=datetime.now(tz=timezone.utc),
        )
        self._session.add(user)
        await self._session.flush()

        self.log.info("user_registered", user_id=str(user.id), email=email)
        token = self.create_access_token(str(user.id), user.tier)
        return TokenResponse(access_token=token, user_id=str(user.id), tier=user.tier)

    async def login(self, email: str, password: str) -> TokenResponse:
        """Authenticate a user and return an access token."""
        result = await self._session.execute(
            select(User).where(User.email == email),
        )
        user = result.scalars().first()

        if not user or not self.verify_password(password, user.hashed_password or ""):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive",
            )

        self.log.info("user_logged_in", user_id=str(user.id))
        token = self.create_access_token(str(user.id), user.tier)
        return TokenResponse(access_token=token, user_id=str(user.id), tier=user.tier)
