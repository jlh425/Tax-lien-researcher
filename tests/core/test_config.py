"""Tests for Settings security: CORS configuration and secret key validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aloha.config import Settings


# ═══════════════════════════════════════════════════════════════════════════════
# CORS configuration
# ═══════════════════════════════════════════════════════════════════════════════


class TestCorsConfig:
    def test_default_cors_origins(self):
        """Default cors_allowed_origins includes the Vite dev server."""
        s = Settings(environment="development")
        assert s.cors_allowed_origins == ["http://localhost:5173"]

    def test_custom_cors_origins(self):
        """cors_allowed_origins can be overridden."""
        s = Settings(
            environment="production",
            secret_key="real-secret-key-here",
            cors_allowed_origins=["https://app.example.com"],
        )
        assert s.cors_allowed_origins == ["https://app.example.com"]

    def test_cors_origins_multiple(self):
        """Multiple origins are supported."""
        origins = ["https://app.example.com", "https://staging.example.com"]
        s = Settings(
            environment="production",
            secret_key="real-secret-key-here",
            cors_allowed_origins=origins,
        )
        assert s.cors_allowed_origins == origins


# ═══════════════════════════════════════════════════════════════════════════════
# Secret key validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestSecretKeyValidation:
    def test_production_default_secret_raises(self):
        """Production with the default secret key must raise ValueError."""
        with pytest.raises(ValidationError, match="SECRET_KEY must be explicitly set"):
            Settings(environment="production")

    def test_production_explicit_secret_passes(self):
        """Production with a real secret key should not raise."""
        s = Settings(environment="production", secret_key="my-very-secure-key-123")
        assert s.secret_key == "my-very-secure-key-123"
        assert s.environment == "production"

    def test_development_default_secret_allowed(self):
        """Development environment allows the default secret key."""
        s = Settings(environment="development")
        assert s.secret_key == "change-me-in-production"

    def test_test_environment_default_secret_allowed(self):
        """Test environment allows the default secret key."""
        s = Settings(environment="test")
        assert s.secret_key == "change-me-in-production"
