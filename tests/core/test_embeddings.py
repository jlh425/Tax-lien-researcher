"""Tests for aloha.core.embeddings — configurable text embedding provider."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aloha.core import embeddings


# ── Helpers ────────────────────────────────────────────────────────────────────


def _fake_embedding_response(vector: list[float]) -> MagicMock:
    """Build a mock openai embedding response with a single data point."""
    datum = MagicMock()
    datum.embedding = vector
    resp = MagicMock()
    resp.data = [datum]
    return resp


def _mock_async_openai_cls(response: MagicMock | None = None) -> MagicMock:
    """Return a mock class whose instances have an async embeddings.create."""
    if response is None:
        response = _fake_embedding_response([0.1, 0.2, 0.3])
    client_instance = MagicMock()
    client_instance.embeddings = MagicMock()
    client_instance.embeddings.create = AsyncMock(return_value=response)
    cls = MagicMock(return_value=client_instance)
    return cls


# ── embed_text dispatch ───────────────────────────────────────────────────────


class TestEmbedTextDispatch:
    """Test that embed_text routes to the correct provider function."""

    @pytest.mark.asyncio
    async def test_openai_provider_dispatches(self) -> None:
        mock_settings = SimpleNamespace(
            embedding_provider="openai",
            embedding_model="text-embedding-3-small",
            embedding_dimensions=1536,
            openai_api_key="sk-test",
        )
        expected = [0.1, 0.2, 0.3]
        mock_cls = _mock_async_openai_cls(_fake_embedding_response(expected))

        with patch.object(embeddings, "settings", mock_settings), \
             patch.object(embeddings, "AsyncOpenAI", mock_cls):
            result = await embeddings.embed_text("hello world")

        assert result == expected

    @pytest.mark.asyncio
    async def test_ollama_provider_dispatches(self) -> None:
        mock_settings = SimpleNamespace(
            embedding_provider="ollama",
            embedding_model="mxbai-embed-large",
            embedding_dimensions=1024,
            ollama_embedding_url="http://localhost:11434",
        )
        expected = [0.4, 0.5, 0.6]
        mock_cls = _mock_async_openai_cls(_fake_embedding_response(expected))

        with patch.object(embeddings, "settings", mock_settings), \
             patch.object(embeddings, "AsyncOpenAI", mock_cls):
            result = await embeddings.embed_text("hello world")

        assert result == expected

    @pytest.mark.asyncio
    async def test_unknown_provider_returns_none(self) -> None:
        mock_settings = SimpleNamespace(embedding_provider="banana")

        with patch.object(embeddings, "settings", mock_settings), \
             patch.object(embeddings, "AsyncOpenAI", MagicMock()):
            result = await embeddings.embed_text("hello")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_sdk_not_installed(self) -> None:
        """When AsyncOpenAI is None (not installed), embed_text returns None."""
        with patch.object(embeddings, "AsyncOpenAI", None):
            result = await embeddings.embed_text("hello")
        assert result is None


# ── OpenAI provider ──────────────────────────────────────────────────────────


class TestEmbedOpenAI:
    """Test the _embed_openai internal function."""

    @pytest.mark.asyncio
    async def test_calls_openai_with_correct_params(self) -> None:
        mock_settings = SimpleNamespace(
            openai_api_key="sk-test",
            embedding_model="text-embedding-3-small",
            embedding_dimensions=1536,
        )
        expected = [0.1] * 1536
        mock_cls = _mock_async_openai_cls(_fake_embedding_response(expected))

        with patch.object(embeddings, "AsyncOpenAI", mock_cls):
            result = await embeddings._embed_openai("test text", mock_settings)

        assert result == expected
        # Verify the constructor was called with the correct api_key
        mock_cls.assert_called_once_with(api_key="sk-test")
        # Verify embeddings.create was called with correct params
        client_instance = mock_cls.return_value
        client_instance.embeddings.create.assert_awaited_once_with(
            model="text-embedding-3-small",
            input="test text",
            dimensions=1536,
        )

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_none(self) -> None:
        mock_settings = SimpleNamespace(openai_api_key=None)

        result = await embeddings._embed_openai("test text", mock_settings)
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_api_key_attr_returns_none(self) -> None:
        """When the settings object has no openai_api_key at all."""
        mock_settings = SimpleNamespace()  # no openai_api_key attribute

        result = await embeddings._embed_openai("test text", mock_settings)
        assert result is None

    @pytest.mark.asyncio
    async def test_api_error_returns_none(self) -> None:
        mock_settings = SimpleNamespace(
            openai_api_key="sk-test",
            embedding_model="text-embedding-3-small",
            embedding_dimensions=1536,
        )
        mock_cls = _mock_async_openai_cls()
        mock_cls.return_value.embeddings.create = AsyncMock(
            side_effect=ValueError("rate limit")
        )

        with patch.object(embeddings, "AsyncOpenAI", mock_cls):
            result = await embeddings._embed_openai("test text", mock_settings)

        assert result is None


# ── Ollama provider ──────────────────────────────────────────────────────────


class TestEmbedOllama:
    """Test the _embed_ollama internal function."""

    @pytest.mark.asyncio
    async def test_calls_ollama_with_correct_base_url(self) -> None:
        mock_settings = SimpleNamespace(
            ollama_embedding_url="http://gpu-server:11434",
            embedding_model="mxbai-embed-large",
        )
        expected = [0.5, 0.6]
        mock_cls = _mock_async_openai_cls(_fake_embedding_response(expected))

        with patch.object(embeddings, "AsyncOpenAI", mock_cls):
            result = await embeddings._embed_ollama("test text", mock_settings)

        assert result == expected
        # Verify the constructor was called with Ollama-specific URL and api_key
        mock_cls.assert_called_once_with(
            base_url="http://gpu-server:11434/v1",
            api_key="ollama",
        )

    @pytest.mark.asyncio
    async def test_default_base_url_when_missing(self) -> None:
        """When settings has no ollama_embedding_url, default localhost is used."""
        mock_settings = SimpleNamespace(
            embedding_model="mxbai-embed-large",
        )
        mock_cls = _mock_async_openai_cls()

        with patch.object(embeddings, "AsyncOpenAI", mock_cls):
            await embeddings._embed_ollama("test", mock_settings)

        mock_cls.assert_called_once_with(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
        )

    @pytest.mark.asyncio
    async def test_ollama_does_not_pass_dimensions(self) -> None:
        """Ollama embed call should NOT pass the dimensions parameter."""
        mock_settings = SimpleNamespace(
            ollama_embedding_url="http://localhost:11434",
            embedding_model="mxbai-embed-large",
        )
        mock_cls = _mock_async_openai_cls()

        with patch.object(embeddings, "AsyncOpenAI", mock_cls):
            await embeddings._embed_ollama("text", mock_settings)

        client_instance = mock_cls.return_value
        call_kwargs = client_instance.embeddings.create.call_args.kwargs
        assert "dimensions" not in call_kwargs

    @pytest.mark.asyncio
    async def test_api_error_returns_none(self) -> None:
        mock_settings = SimpleNamespace(
            ollama_embedding_url="http://localhost:11434",
            embedding_model="mxbai-embed-large",
        )
        mock_cls = _mock_async_openai_cls()
        mock_cls.return_value.embeddings.create = AsyncMock(
            side_effect=ConnectionError("ollama offline")
        )

        with patch.object(embeddings, "AsyncOpenAI", mock_cls):
            result = await embeddings._embed_ollama("text", mock_settings)

        assert result is None


# ── Configuration ─────────────────────────────────────────────────────────────


class TestEmbeddingConfiguration:
    """Test that embedding-related settings are correctly defined.

    We pass ``_env_file=None`` to avoid reading the local .env file, so
    we can test the *code* defaults defined in the Settings class.
    """

    def test_default_provider_is_openai(self) -> None:
        from aloha.config import Settings

        s = Settings(
            _env_file=None,
            database_url="postgresql+asyncpg://localhost:5432/test",
            database_url_sync="postgresql+psycopg2://localhost:5432/test",
        )
        assert s.embedding_provider == "openai"

    def test_default_model_is_text_embedding_3_small(self) -> None:
        from aloha.config import Settings

        s = Settings(
            _env_file=None,
            database_url="postgresql+asyncpg://localhost:5432/test",
            database_url_sync="postgresql+psycopg2://localhost:5432/test",
        )
        assert s.embedding_model == "text-embedding-3-small"

    def test_default_dimensions_is_1536(self) -> None:
        from aloha.config import Settings

        s = Settings(
            _env_file=None,
            database_url="postgresql+asyncpg://localhost:5432/test",
            database_url_sync="postgresql+psycopg2://localhost:5432/test",
        )
        assert s.embedding_dimensions == 1536

    def test_default_ollama_embedding_url(self) -> None:
        from aloha.config import Settings

        s = Settings(
            _env_file=None,
            database_url="postgresql+asyncpg://localhost:5432/test",
            database_url_sync="postgresql+psycopg2://localhost:5432/test",
        )
        assert s.ollama_embedding_url == "http://localhost:11434"

    def test_embedding_provider_can_be_ollama(self) -> None:
        from aloha.config import Settings

        s = Settings(
            _env_file=None,
            database_url="postgresql+asyncpg://localhost:5432/test",
            database_url_sync="postgresql+psycopg2://localhost:5432/test",
            embedding_provider="ollama",
            embedding_model="mxbai-embed-large",
            embedding_dimensions=1024,
        )
        assert s.embedding_provider == "ollama"
        assert s.embedding_model == "mxbai-embed-large"
        assert s.embedding_dimensions == 1024
