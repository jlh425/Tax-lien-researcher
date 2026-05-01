"""Tests for aloha.core.vector_store — Qdrant wrapper with graceful degradation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aloha.core import vector_store


# ── Helpers ────────────────────────────────────────────────────────────────────


def _mock_client() -> AsyncMock:
    """Return a mock AsyncQdrantClient."""
    client = AsyncMock()
    client.collection_exists = AsyncMock(return_value=False)
    client.create_collection = AsyncMock()
    client.upsert = AsyncMock()
    client.delete = AsyncMock()
    return client


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the module-level singleton between tests."""
    vector_store._client = None
    yield
    vector_store._client = None


# ── ensure_collection ──────────────────────────────────────────────────────────


class TestEnsureCollection:
    @pytest.mark.asyncio
    async def test_creates_collection_when_missing(self) -> None:
        client = _mock_client()
        client.collection_exists.return_value = False

        with patch.object(vector_store, "get_vector_store", return_value=client):
            await vector_store.ensure_collection()

        client.create_collection.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_when_collection_exists(self) -> None:
        client = _mock_client()
        client.collection_exists.return_value = True

        with patch.object(vector_store, "get_vector_store", return_value=client):
            await vector_store.ensure_collection()

        client.create_collection.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_graceful_on_error(self) -> None:
        client = _mock_client()
        client.collection_exists.side_effect = RuntimeError("connection refused")

        with patch.object(vector_store, "get_vector_store", return_value=client):
            await vector_store.ensure_collection()  # should not raise


# ── upsert ────────────────────────────────────────────────────────────────────


class TestUpsert:
    @pytest.mark.asyncio
    async def test_upserts_point(self) -> None:
        client = _mock_client()

        with patch.object(vector_store, "get_vector_store", return_value=client):
            await vector_store.upsert(42, [0.1, 0.2, 0.3], {"parcel_id": "P-1"})

        client.upsert.assert_awaited_once()
        call_kwargs = client.upsert.call_args.kwargs
        assert call_kwargs["points"][0].id == 42
        assert call_kwargs["points"][0].payload == {"parcel_id": "P-1"}

    @pytest.mark.asyncio
    async def test_graceful_on_error(self) -> None:
        client = _mock_client()
        client.upsert.side_effect = RuntimeError("timeout")

        with patch.object(vector_store, "get_vector_store", return_value=client):
            await vector_store.upsert(1, [0.1])  # should not raise

    @pytest.mark.asyncio
    async def test_noop_when_client_unavailable(self) -> None:
        with patch.object(vector_store, "get_vector_store", return_value=None):
            await vector_store.upsert(1, [0.1])  # should not raise


# ── search ────────────────────────────────────────────────────────────────────


class TestSearch:
    @pytest.mark.asyncio
    async def test_returns_results(self) -> None:
        client = _mock_client()
        mock_point = MagicMock()
        mock_point.id = 10
        mock_point.score = 0.95
        mock_point.payload = {"parcel_id": "P-1"}
        mock_response = MagicMock()
        mock_response.points = [mock_point]
        client.query_points = AsyncMock(return_value=mock_response)

        with patch.object(vector_store, "get_vector_store", return_value=client):
            results = await vector_store.search([0.1, 0.2], limit=5)

        assert len(results) == 1
        assert results[0]["id"] == 10
        assert results[0]["score"] == 0.95

    @pytest.mark.asyncio
    async def test_applies_filter(self) -> None:
        client = _mock_client()
        mock_response = MagicMock()
        mock_response.points = []
        client.query_points = AsyncMock(return_value=mock_response)

        with patch.object(vector_store, "get_vector_store", return_value=client):
            await vector_store.search(
                [0.1], limit=5, filter_conditions={"parcel_id": "P-1"}
            )

        call_kwargs = client.query_points.call_args.kwargs
        assert call_kwargs["query_filter"] is not None

    @pytest.mark.asyncio
    async def test_graceful_on_error(self) -> None:
        client = _mock_client()
        client.query_points = AsyncMock(side_effect=RuntimeError("down"))

        with patch.object(vector_store, "get_vector_store", return_value=client):
            results = await vector_store.search([0.1])

        assert results == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_client_unavailable(self) -> None:
        with patch.object(vector_store, "get_vector_store", return_value=None):
            results = await vector_store.search([0.1])
        assert results == []


# ── delete ────────────────────────────────────────────────────────────────────


class TestDelete:
    @pytest.mark.asyncio
    async def test_deletes_points(self) -> None:
        client = _mock_client()

        with patch.object(vector_store, "get_vector_store", return_value=client):
            await vector_store.delete([1, 2, 3])

        client.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_noop_on_empty_list(self) -> None:
        client = _mock_client()

        with patch.object(vector_store, "get_vector_store", return_value=client):
            await vector_store.delete([])

        client.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_graceful_on_error(self) -> None:
        client = _mock_client()
        client.delete.side_effect = RuntimeError("timeout")

        with patch.object(vector_store, "get_vector_store", return_value=client):
            await vector_store.delete([1])  # should not raise
