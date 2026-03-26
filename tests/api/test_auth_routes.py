"""Tests for auth API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient


def _make_test_app(mock_auth_svc=None):
    """Build a minimal FastAPI app with the auth router and overridden deps."""
    from fastapi import FastAPI

    from aloha.api.routes.auth import _auth_service, router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    if mock_auth_svc is not None:
        app.dependency_overrides[_auth_service] = lambda: mock_auth_svc
    return app


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_success(self) -> None:
        mock_svc = AsyncMock()
        mock_svc.register.return_value = MagicMock(
            access_token="tok-123",
            token_type="bearer",
            user_id="user-abc",
            tier="free",
        )

        app = _make_test_app(mock_svc)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/auth/register",
                json={"email": "new@example.com", "password": "longpassword", "name": "Test"},
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["access_token"] == "tok-123"
        assert data["tier"] == "free"

    @pytest.mark.asyncio
    async def test_register_short_password_422(self) -> None:
        app = _make_test_app(AsyncMock())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/auth/register",
                json={"email": "x@x.com", "password": "short"},
            )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_missing_email_422(self) -> None:
        app = _make_test_app(AsyncMock())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/auth/register",
                json={"password": "longpassword"},
            )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_duplicate_email_409(self) -> None:
        from fastapi import HTTPException

        mock_svc = AsyncMock()
        mock_svc.register.side_effect = HTTPException(
            status_code=409, detail="Email already registered"
        )

        app = _make_test_app(mock_svc)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/auth/register",
                json={"email": "taken@x.com", "password": "longpassword"},
            )
        assert resp.status_code == 409


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success(self) -> None:
        mock_svc = AsyncMock()
        mock_svc.login.return_value = MagicMock(
            access_token="tok-456",
            token_type="bearer",
            user_id="user-xyz",
            tier="pro",
        )

        app = _make_test_app(mock_svc)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/auth/login",
                json={"email": "user@example.com", "password": "correct"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "tok-456"
        assert data["tier"] == "pro"

    @pytest.mark.asyncio
    async def test_login_missing_fields_422(self) -> None:
        app = _make_test_app(AsyncMock())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_login_wrong_password_401(self) -> None:
        from fastapi import HTTPException

        mock_svc = AsyncMock()
        mock_svc.login.side_effect = HTTPException(
            status_code=401, detail="Invalid credentials"
        )

        app = _make_test_app(mock_svc)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/auth/login",
                json={"email": "user@x.com", "password": "wrong"},
            )
        assert resp.status_code == 401
