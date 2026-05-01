"""Unit tests for EnrichmentAgent and supporting utilities.

All tests mock DB, network, and LLM — no real external calls.
"""

from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aloha.agents.enrichment.prompts import (
    PropertyConditionReport,
    VISION_SYSTEM_PROMPT,
    build_vision_task,
)


# ── PropertyConditionReport model ─────────────────────────────────────────────


class TestPropertyConditionReport:
    def test_all_fields_present(self) -> None:
        report = PropertyConditionReport(
            occupancy_status="vacant",
            structural_condition="poor",
            lot_condition="overgrown",
            property_type_confirmed="single_family",
            visible_issues=["broken_windows", "overgrown_vegetation"],
            neighborhood_context="Mostly residential, several vacant lots nearby.",
            confidence=0.75,
            summary="Vacant single-family home in poor condition with broken windows.",
        )
        assert report.occupancy_status == "vacant"
        assert report.structural_condition == "poor"
        assert "broken_windows" in report.visible_issues
        assert report.confidence == 0.75
        assert report.summary != ""

    def test_defaults_applied(self) -> None:
        report = PropertyConditionReport(
            occupancy_status="unknown",
            structural_condition="unknown",
            lot_condition="unknown",
            property_type_confirmed="unknown",
        )
        assert report.visible_issues == []
        assert report.neighborhood_context == ""
        assert report.confidence == 0.0
        assert report.summary == ""

    def test_model_dump_is_json_serialisable(self) -> None:
        report = PropertyConditionReport(
            occupancy_status="occupied",
            structural_condition="good",
            lot_condition="average",
            property_type_confirmed="single_family",
            confidence=0.9,
            summary="Well-maintained occupied home.",
        )
        text = json.dumps(report.model_dump(), indent=2)
        assert "occupied" in text
        assert "Well-maintained" in text


# ── build_vision_task ──────────────────────────────────────────────────────────


class TestBuildVisionTask:
    def test_includes_parcel_id(self) -> None:
        task = build_vision_task("123-ABC", None, ["satellite"])
        assert "123-ABC" in task

    def test_includes_address_when_provided(self) -> None:
        task = build_vision_task("123-ABC", "456 Oak Ave, Miami FL", ["satellite"])
        assert "456 Oak Ave" in task

    def test_omits_address_when_none(self) -> None:
        task = build_vision_task("123-ABC", None, ["satellite"])
        assert " at " not in task

    def test_includes_image_types(self) -> None:
        task = build_vision_task("X", "addr", ["satellite", "street_view"])
        assert "satellite" in task
        assert "street_view" in task


# ── Data URI decode helpers ───────────────────────────────────────────────────


class TestDataUriDecode:
    """Test the _decode_data_uri and _mime_from_data_uri helpers directly."""

    def test_decode_roundtrip(self) -> None:
        from aloha.agents.enrichment.agent import _decode_data_uri

        original = b"fake-image-bytes"
        b64 = base64.b64encode(original).decode()
        data_uri = f"data:image/jpeg;base64,{b64}"
        assert _decode_data_uri(data_uri) == original

    def test_decode_returns_none_on_malformed(self) -> None:
        from aloha.agents.enrichment.agent import _decode_data_uri

        assert _decode_data_uri("not-a-data-uri") is None
        assert _decode_data_uri("") is None

    def test_mime_extraction(self) -> None:
        from aloha.agents.enrichment.agent import _mime_from_data_uri

        assert _mime_from_data_uri("data:image/png;base64,abc") == "image/png"
        assert _mime_from_data_uri("data:image/jpeg;base64,abc") == "image/jpeg"

    def test_mime_defaults_to_jpeg_on_error(self) -> None:
        from aloha.agents.enrichment.agent import _mime_from_data_uri

        assert _mime_from_data_uri("garbage") == "image/jpeg"


# ── _pick_best_image ──────────────────────────────────────────────────────────


class TestPickBestImage:
    def _make_image(self, image_type: str) -> MagicMock:
        img = MagicMock()
        img.image_type = image_type
        return img

    def test_prefers_street_view(self) -> None:
        from aloha.agents.enrichment.agent import _pick_best_image

        images = [self._make_image("satellite"), self._make_image("street_view")]
        best = _pick_best_image(images)
        assert best.image_type == "street_view"

    def test_falls_back_to_satellite(self) -> None:
        from aloha.agents.enrichment.agent import _pick_best_image

        images = [self._make_image("satellite"), self._make_image("gis_parcel_map")]
        best = _pick_best_image(images)
        assert best.image_type == "satellite"

    def test_returns_none_on_empty_list(self) -> None:
        from aloha.agents.enrichment.agent import _pick_best_image

        assert _pick_best_image([]) is None


# ── ProviderChain ─────────────────────────────────────────────────────────────


class TestProviderChain:
    @pytest.mark.asyncio
    async def test_returns_first_successful_provider(self) -> None:
        from aloha.mcp_servers.image_capture.providers import ProviderChain

        p1 = AsyncMock()
        p1.fetch = AsyncMock(return_value=None)  # fails
        p2 = AsyncMock()
        p2.fetch = AsyncMock(return_value=b"real-image-bytes")  # succeeds

        chain = ProviderChain([p1, p2])
        result = await chain.fetch(latitude=25.0, longitude=-80.0)
        assert result == b"real-image-bytes"

    @pytest.mark.asyncio
    async def test_skips_raising_provider(self) -> None:
        from aloha.mcp_servers.image_capture.providers import ProviderChain

        p1 = AsyncMock()
        p1.fetch = AsyncMock(side_effect=RuntimeError("network error"))
        p2 = AsyncMock()
        p2.fetch = AsyncMock(return_value=b"ok-bytes")

        chain = ProviderChain([p1, p2])
        result = await chain.fetch(latitude=25.0, longitude=-80.0)
        assert result == b"ok-bytes"

    @pytest.mark.asyncio
    async def test_returns_none_when_all_fail(self) -> None:
        from aloha.mcp_servers.image_capture.providers import ProviderChain

        p1 = AsyncMock()
        p1.fetch = AsyncMock(return_value=None)
        p2 = AsyncMock()
        p2.fetch = AsyncMock(return_value=None)

        chain = ProviderChain([p1, p2])
        result = await chain.fetch(latitude=25.0, longitude=-80.0)
        assert result is None


# ── MapboxSatelliteProvider — lon/lat order ────────────────────────────────────


class TestMapboxLonLatOrder:
    @pytest.mark.asyncio
    async def test_url_uses_lon_before_lat(self) -> None:
        """Mapbox URL must have lon,lat NOT lat,lon."""
        from aloha.mcp_servers.image_capture.providers import MapboxSatelliteProvider

        captured_urls: list[str] = []

        async def fake_get(url: str, **kwargs: object) -> MagicMock:
            captured_urls.append(url)
            resp = MagicMock()
            resp.headers = {"content-type": "image/png"}
            resp.content = b"fake-png"
            resp.raise_for_status = MagicMock()
            return resp

        provider = MapboxSatelliteProvider(access_token="fake-token")

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=fake_get)

        with patch("aloha.mcp_servers.image_capture.providers.httpx.AsyncClient", return_value=mock_client):
            await provider.fetch(latitude=25.77, longitude=-80.19)

        assert captured_urls, "No URL was captured"
        url = captured_urls[0]
        # lon comes before lat in the URL path: /{lon},{lat},{zoom}/...
        lon_idx = url.index("-80.19")
        lat_idx = url.index("25.77")
        assert lon_idx < lat_idx, f"Expected lon before lat in URL: {url}"


# ── embed_text — graceful None without key ────────────────────────────────────


class TestEmbedText:
    @pytest.mark.asyncio
    async def test_openai_returns_none_without_key(self) -> None:
        from aloha.core.embeddings import embed_text

        with patch("aloha.core.embeddings.settings") as mock_settings:
            mock_settings.embedding_provider = "openai"
            mock_settings.openai_api_key = None
            result = await embed_text("test text")

        assert result is None

    @pytest.mark.asyncio
    async def test_openai_returns_none_on_api_error(self) -> None:
        from aloha.core.embeddings import embed_text

        mock_client = AsyncMock()
        mock_client.embeddings.create = AsyncMock(side_effect=RuntimeError("API down"))

        with patch("aloha.core.embeddings.settings") as mock_settings:
            mock_settings.embedding_provider = "openai"
            mock_settings.openai_api_key = "fake-key"
            mock_settings.embedding_model = "text-embedding-3-small"
            mock_settings.embedding_dimensions = 1536
            with patch("aloha.core.embeddings.AsyncOpenAI", return_value=mock_client):
                result = await embed_text("test text")

        assert result is None

    @pytest.mark.asyncio
    async def test_ollama_returns_none_on_api_error(self) -> None:
        from aloha.core.embeddings import embed_text

        mock_client = AsyncMock()
        mock_client.embeddings.create = AsyncMock(side_effect=RuntimeError("connection refused"))

        with patch("aloha.core.embeddings.settings") as mock_settings:
            mock_settings.embedding_provider = "ollama"
            mock_settings.ollama_embedding_url = "http://localhost:11434"
            mock_settings.embedding_model = "mxbai-embed-large"
            with patch("aloha.core.embeddings.AsyncOpenAI", return_value=mock_client):
                result = await embed_text("test text")

        assert result is None

    @pytest.mark.asyncio
    async def test_unknown_provider_returns_none(self) -> None:
        from aloha.core.embeddings import embed_text

        with patch("aloha.core.embeddings.settings") as mock_settings:
            mock_settings.embedding_provider = "unsupported"
            result = await embed_text("test text")

        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# EnrichmentAgent integration tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestEnrichmentAgentRun:
    @pytest.fixture
    def agent(self):
        from aloha.agents.enrichment.agent import EnrichmentAgent
        return EnrichmentAgent()

    @pytest.fixture
    def base_context(self):
        return {"parcel_id": "TEST-001", "state": "FL", "county": "orange"}

    @pytest.mark.asyncio
    async def test_parcel_not_found(self, agent, base_context):
        mock_parcel_repo = MagicMock()
        mock_parcel_repo.get = AsyncMock(return_value=None)
        mock_session = AsyncMock()

        with patch("aloha.agents.enrichment.agent.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch("aloha.agents.enrichment.agent.ParcelRepository", return_value=mock_parcel_repo):
                result = await agent.run(base_context)

        assert result["status"] == "failed"
        assert result["reason"] == "parcel_not_found"

    @pytest.mark.asyncio
    async def test_already_enriched_skipped(self, agent, base_context):
        mock_parcel = MagicMock()
        mock_parcel.research_status = "enriched"
        mock_parcel_repo = MagicMock()
        mock_parcel_repo.get = AsyncMock(return_value=mock_parcel)
        mock_session = AsyncMock()

        with patch("aloha.agents.enrichment.agent.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch("aloha.agents.enrichment.agent.ParcelRepository", return_value=mock_parcel_repo):
                result = await agent.run(base_context)

        assert result["status"] == "skipped"
        assert result["reason"] == "already_enriched"

    @pytest.mark.asyncio
    async def test_no_images_captured(self, agent, base_context):
        mock_parcel = MagicMock()
        mock_parcel.research_status = "owner_researched"
        mock_parcel.latitude = None
        mock_parcel.longitude = None
        mock_parcel.address = None

        mock_parcel_repo = MagicMock()
        mock_parcel_repo.get = AsyncMock(return_value=mock_parcel)
        mock_image_repo = MagicMock()
        mock_image_repo.get_by_parcel = AsyncMock(return_value=[])
        mock_image_server = AsyncMock()
        mock_image_server.close = AsyncMock()
        mock_session = AsyncMock()

        with patch("aloha.agents.enrichment.agent.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch("aloha.agents.enrichment.agent.ParcelRepository", return_value=mock_parcel_repo):
                with patch("aloha.agents.enrichment.agent.PropertyImageRepository", return_value=mock_image_repo):
                    # ImageCaptureMCPServer + settings are deferred imports → patch at source
                    with patch("aloha.mcp_servers.image_capture.server.ImageCaptureMCPServer", return_value=mock_image_server):
                        with patch("aloha.config.settings") as mock_settings:
                            mock_settings.google_maps_api_key = None
                            result = await agent.run(base_context)

        assert result["status"] == "no_images"
