"""Tests for the Image Capture MCP Server."""

from __future__ import annotations

import base64
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from aloha.mcp_servers.image_capture.server import (
    ImageCaptureMCPServer,
    _save_image,
    create_image_capture_server,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Init & Tool Registration
# ═══════════════════════════════════════════════════════════════════════════════


class TestInit:
    def test_server_name(self) -> None:
        server = ImageCaptureMCPServer()
        assert server.name == "image_capture"

    def test_tools_registered(self) -> None:
        server = ImageCaptureMCPServer()
        assert "capture_gis_map" in server.tools
        assert "capture_street_view" in server.tools
        assert "capture_satellite" in server.tools

    def test_tool_count(self) -> None:
        server = ImageCaptureMCPServer()
        assert len(server.tools) == 3

    def test_client_initially_none(self) -> None:
        server = ImageCaptureMCPServer()
        assert server._client is None

    def test_google_key_stored(self) -> None:
        server = ImageCaptureMCPServer(google_api_key="gk-123")
        assert server._google_api_key == "gk-123"


# ═══════════════════════════════════════════════════════════════════════════════
# Success Paths (mocked HTTP)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSuccessPaths:
    @pytest.mark.asyncio
    async def test_capture_gis_map(self) -> None:
        server = ImageCaptureMCPServer()
        fake_png = b"PNG-BYTES"

        mock_exporter = AsyncMock()
        mock_exporter.export = AsyncMock(return_value=fake_png)
        mock_exporter.close = AsyncMock()

        # ArcGISMapExporter is a deferred import — patch at its source module
        with patch("aloha.scrapers.tier1_apis.arcgis.ArcGISMapExporter", return_value=mock_exporter):
            with patch.object(
                type(server), "capture_gis_map",
                wraps=server.capture_gis_map,
            ):
                # Need to also mock _save_image which is module-level
                with patch("aloha.mcp_servers.image_capture.server._save_image", new_callable=AsyncMock):
                    result = await server.capture_gis_map(
                        parcel_id="P-001",
                        service_url="https://gis.example.com/MapServer",
                        bbox=[-81.5, 28.5, -81.4, 28.6],
                    )

        assert result["image_type"] == "gis_parcel_map"
        assert result["size_bytes"] == len(fake_png)
        assert result["data_b64"] == base64.b64encode(fake_png).decode()

    @pytest.mark.asyncio
    async def test_capture_street_view(self) -> None:
        server = ImageCaptureMCPServer(google_api_key="gk-test")
        fake_jpeg = b"JPEG-BYTES"

        mock_provider = MagicMock()
        mock_provider.fetch = AsyncMock(return_value=fake_jpeg)

        # Deferred import — patch at the providers module
        with patch("aloha.mcp_servers.image_capture.providers.GoogleStreetViewProvider", return_value=mock_provider):
            with patch("aloha.mcp_servers.image_capture.server._save_image", new_callable=AsyncMock):
                result = await server.capture_street_view(
                    parcel_id="P-001",
                    address="123 Main St, Orlando FL",
                )

        assert result["image_type"] == "street_view"
        assert result["mime_type"] == "image/jpeg"

    @pytest.mark.asyncio
    async def test_capture_satellite(self) -> None:
        server = ImageCaptureMCPServer(google_api_key="gk-test")
        fake_png = b"SAT-PNG"

        mock_chain = MagicMock()
        mock_chain.fetch = AsyncMock(return_value=fake_png)

        with patch("aloha.config.settings") as mock_settings:
            mock_settings.mapbox_api_key = "mapbox-test"
            with patch("aloha.mcp_servers.image_capture.providers.ProviderChain", return_value=mock_chain):
                with patch("aloha.mcp_servers.image_capture.server._save_image", new_callable=AsyncMock):
                    result = await server.capture_satellite(
                        parcel_id="P-001",
                        latitude=28.54,
                        longitude=-81.37,
                    )

        assert result["image_type"] == "satellite"
        assert result["size_bytes"] == len(fake_png)


# ═══════════════════════════════════════════════════════════════════════════════
# Error Paths
# ═══════════════════════════════════════════════════════════════════════════════


class TestErrorPaths:
    @pytest.mark.asyncio
    async def test_gis_map_exporter_fails(self) -> None:
        server = ImageCaptureMCPServer()

        mock_exporter = AsyncMock()
        mock_exporter.export = AsyncMock(side_effect=RuntimeError("export failed"))
        mock_exporter.close = AsyncMock()

        with patch("aloha.scrapers.tier1_apis.arcgis.ArcGISMapExporter", return_value=mock_exporter):
            result = await server.capture_gis_map(
                parcel_id="P-001",
                service_url="https://example.com",
                bbox=[-81.5, 28.5, -81.4, 28.6],
            )

        assert "error" in result
        assert result["image_type"] == "gis_parcel_map"

    @pytest.mark.asyncio
    async def test_street_view_no_api_key(self) -> None:
        server = ImageCaptureMCPServer(google_api_key=None)

        result = await server.capture_street_view(
            parcel_id="P-001",
            address="123 Main St",
        )

        assert "error" in result
        assert "GOOGLE_MAPS_API_KEY" in result["error"]

    @pytest.mark.asyncio
    async def test_street_view_fetch_returns_none(self) -> None:
        server = ImageCaptureMCPServer(google_api_key="gk-test")

        mock_provider = MagicMock()
        mock_provider.fetch = AsyncMock(return_value=None)

        with patch("aloha.mcp_servers.image_capture.providers.GoogleStreetViewProvider", return_value=mock_provider):
            result = await server.capture_street_view(
                parcel_id="P-001",
                address="123 Main St",
            )

        assert "error" in result
        assert "failed" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_satellite_no_providers(self) -> None:
        server = ImageCaptureMCPServer(google_api_key=None)

        with patch("aloha.config.settings") as mock_settings:
            mock_settings.mapbox_api_key = None
            result = await server.capture_satellite(
                parcel_id="P-001",
                latitude=28.54,
                longitude=-81.37,
            )

        assert "error" in result
        assert "provider" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_satellite_all_providers_fail(self) -> None:
        server = ImageCaptureMCPServer(google_api_key="gk-test")

        mock_chain = MagicMock()
        mock_chain.fetch = AsyncMock(return_value=None)

        with patch("aloha.config.settings") as mock_settings:
            mock_settings.mapbox_api_key = "mapbox-test"
            with patch("aloha.mcp_servers.image_capture.providers.ProviderChain", return_value=mock_chain):
                result = await server.capture_satellite(
                    parcel_id="P-001",
                    latitude=28.54,
                    longitude=-81.37,
                )

        assert "error" in result


# ═══════════════════════════════════════════════════════════════════════════════
# _save_image
# ═══════════════════════════════════════════════════════════════════════════════


class TestSaveImage:
    @pytest.mark.asyncio
    async def test_creates_new_image(self) -> None:
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        with patch("aloha.db.engine.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            await _save_image("P-001", "satellite", b"img-bytes", "image/png")

        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_updates_existing_image(self) -> None:
        existing = MagicMock()
        existing.file_path = "old_data"

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = existing

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with patch("aloha.db.engine.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            await _save_image("P-001", "satellite", b"new-bytes", "image/png")

        b64 = base64.b64encode(b"new-bytes").decode()
        assert existing.file_path == f"data:image/png;base64,{b64}"

    @pytest.mark.asyncio
    async def test_data_uri_format(self) -> None:
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        with patch("aloha.db.engine.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            await _save_image("P-001", "street_view", b"jpg", "image/jpeg", source_url="https://maps.google.com")

        added_obj = mock_session.add.call_args[0][0]
        assert added_obj.file_path.startswith("data:image/jpeg;base64,")
        assert added_obj.source_url == "https://maps.google.com"


# ═══════════════════════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════════════════════


class TestFactory:
    def test_creates_server(self) -> None:
        with patch("aloha.config.settings") as mock_settings:
            mock_settings.google_maps_api_key = "gk-123"
            server = create_image_capture_server()
            assert isinstance(server, ImageCaptureMCPServer)

    def test_no_google_key_still_works(self) -> None:
        with patch("aloha.config.settings") as mock_settings:
            mock_settings.google_maps_api_key = None
            server = create_image_capture_server()
            assert isinstance(server, ImageCaptureMCPServer)
            assert server._google_api_key is None
