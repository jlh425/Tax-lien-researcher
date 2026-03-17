"""Image Capture MCP Server — GIS parcel map, Street View, and satellite images.

Exposes three tools:
- capture_gis_map: ArcGIS exportImage → PNG of parcel boundaries + zoning
- capture_street_view: Google Street View Static API → JPEG of street-facing view
- capture_satellite: Google Maps Static API → satellite PNG centred on parcel

Images are saved to the DB (PropertyImage) keyed by (parcel_id, image_type).
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from aloha.mcp_servers.base import BaseMCPServer, ToolDefinition

log = structlog.get_logger().bind(component="image_capture_mcp")

_GOOGLE_STATIC_URL = "https://maps.googleapis.com/maps/api/staticmap"
_GOOGLE_STREETVIEW_URL = "https://maps.googleapis.com/maps/api/streetview"
_TIMEOUT = 30.0


class ImageCaptureMCPServer(BaseMCPServer):
    """MCP server for capturing property images from GIS, Street View, and satellite."""

    def __init__(self, google_api_key: str | None = None) -> None:
        super().__init__(name="image_capture")
        self._google_api_key = google_api_key
        self._client: httpx.AsyncClient | None = None
        self._register_tools()

    def _register_tools(self) -> None:
        self.register_tool(ToolDefinition(
            name="capture_gis_map",
            description=(
                "Export a GIS parcel map PNG from an ArcGIS MapServer. "
                "Returns base64-encoded PNG bytes and saves to the DB."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "parcel_id": {"type": "string"},
                    "service_url": {
                        "type": "string",
                        "description": "ArcGIS MapServer URL (not feature layer).",
                    },
                    "bbox": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 4,
                        "maxItems": 4,
                        "description": "[xmin, ymin, xmax, ymax] in WGS84.",
                    },
                    "width": {"type": "integer", "default": 800},
                    "height": {"type": "integer", "default": 600},
                },
                "required": ["parcel_id", "service_url", "bbox"],
            },
            handler=self.capture_gis_map,
        ))

        self.register_tool(ToolDefinition(
            name="capture_street_view",
            description=(
                "Capture a Google Street View image for a property address. "
                "Requires GOOGLE_MAPS_API_KEY. Returns base64-encoded JPEG."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "parcel_id": {"type": "string"},
                    "address": {"type": "string", "description": "Full street address."},
                    "width": {"type": "integer", "default": 800},
                    "height": {"type": "integer", "default": 600},
                },
                "required": ["parcel_id", "address"],
            },
            handler=self.capture_street_view,
        ))

        self.register_tool(ToolDefinition(
            name="capture_satellite",
            description=(
                "Capture a Google Maps satellite image centred on a lat/lng. "
                "Requires GOOGLE_MAPS_API_KEY. Returns base64-encoded PNG."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "parcel_id": {"type": "string"},
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                    "zoom": {"type": "integer", "default": 18},
                    "width": {"type": "integer", "default": 800},
                    "height": {"type": "integer", "default": 600},
                },
                "required": ["parcel_id", "latitude", "longitude"],
            },
            handler=self.capture_satellite,
        ))

    # ── HTTP client ───────────────────────────────────────────────────────

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(_TIMEOUT))
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # ── Tool handlers ─────────────────────────────────────────────────────

    async def capture_gis_map(
        self,
        parcel_id: str,
        service_url: str,
        bbox: list[float],
        width: int = 800,
        height: int = 600,
    ) -> dict[str, Any]:
        """Export a GIS parcel boundary map via ArcGIS /export."""
        from aloha.scrapers.tier1_apis.arcgis import ArcGISMapExporter

        try:
            exporter = ArcGISMapExporter(service_url=service_url)
            png_bytes = await exporter.export(
                tuple(bbox),  # type: ignore[arg-type]
                width=width,
                height=height,
            )
            await exporter.close()

            await _save_image(parcel_id, "gis_parcel_map", png_bytes, "image/png", source_url=service_url)
            log.info("gis_map_captured", parcel_id=parcel_id, size=len(png_bytes))
            return {
                "parcel_id": parcel_id,
                "image_type": "gis_parcel_map",
                "size_bytes": len(png_bytes),
                "data_b64": base64.b64encode(png_bytes).decode(),
                "mime_type": "image/png",
            }
        except Exception as exc:
            log.warning("gis_map_failed", parcel_id=parcel_id, error=str(exc))
            return {"error": str(exc), "parcel_id": parcel_id, "image_type": "gis_parcel_map"}

    async def capture_street_view(
        self,
        parcel_id: str,
        address: str,
        width: int = 800,
        height: int = 600,
    ) -> dict[str, Any]:
        """Fetch a Google Street View image for a street address."""
        if not self._google_api_key:
            return {"error": "GOOGLE_MAPS_API_KEY not configured", "parcel_id": parcel_id}

        params = {
            "size": f"{width}x{height}",
            "location": address,
            "key": self._google_api_key,
            "source": "outdoor",
            "return_error_code": "true",
        }
        try:
            client = await self._get_client()
            response = await client.get(_GOOGLE_STREETVIEW_URL, params=params)
            response.raise_for_status()

            jpeg_bytes = response.content
            await _save_image(
                parcel_id, "street_view", jpeg_bytes, "image/jpeg",
                source_url=_GOOGLE_STREETVIEW_URL,
            )
            log.info("street_view_captured", parcel_id=parcel_id, size=len(jpeg_bytes))
            return {
                "parcel_id": parcel_id,
                "image_type": "street_view",
                "size_bytes": len(jpeg_bytes),
                "data_b64": base64.b64encode(jpeg_bytes).decode(),
                "mime_type": "image/jpeg",
            }
        except httpx.HTTPStatusError as exc:
            log.warning("street_view_failed", parcel_id=parcel_id, status=exc.response.status_code)
            return {"error": f"HTTP {exc.response.status_code}", "parcel_id": parcel_id}
        except Exception as exc:
            log.warning("street_view_failed", parcel_id=parcel_id, error=str(exc))
            return {"error": str(exc), "parcel_id": parcel_id}

    async def capture_satellite(
        self,
        parcel_id: str,
        latitude: float,
        longitude: float,
        zoom: int = 18,
        width: int = 800,
        height: int = 600,
    ) -> dict[str, Any]:
        """Capture a Google Maps satellite tile centred on lat/lng."""
        if not self._google_api_key:
            return {"error": "GOOGLE_MAPS_API_KEY not configured", "parcel_id": parcel_id}

        params = {
            "center": f"{latitude},{longitude}",
            "zoom": str(zoom),
            "size": f"{width}x{height}",
            "maptype": "satellite",
            "key": self._google_api_key,
        }
        try:
            client = await self._get_client()
            response = await client.get(_GOOGLE_STATIC_URL, params=params)
            response.raise_for_status()

            png_bytes = response.content
            await _save_image(
                parcel_id, "satellite", png_bytes, "image/png",
                source_url=_GOOGLE_STATIC_URL,
            )
            log.info("satellite_captured", parcel_id=parcel_id, size=len(png_bytes))
            return {
                "parcel_id": parcel_id,
                "image_type": "satellite",
                "size_bytes": len(png_bytes),
                "data_b64": base64.b64encode(png_bytes).decode(),
                "mime_type": "image/png",
            }
        except httpx.HTTPStatusError as exc:
            log.warning("satellite_failed", parcel_id=parcel_id, status=exc.response.status_code)
            return {"error": f"HTTP {exc.response.status_code}", "parcel_id": parcel_id}
        except Exception as exc:
            log.warning("satellite_failed", parcel_id=parcel_id, error=str(exc))
            return {"error": str(exc), "parcel_id": parcel_id}


# ── DB persistence helper ─────────────────────────────────────────────────────

async def _save_image(
    parcel_id: str,
    image_type: str,
    image_bytes: bytes,
    mime_type: str,
    source_url: str | None = None,
) -> None:
    """Upsert a PropertyImage record (parcel_id + image_type unique).

    Stores the image as a data URI in file_path (development convenience).
    Production deployments should upload to S3 and store the S3 URL instead.
    """
    from sqlalchemy import select as sa_select

    from aloha.db.engine import async_session_factory
    from aloha.db.models.property_image import PropertyImage

    b64 = base64.b64encode(image_bytes).decode()
    data_uri = f"data:{mime_type};base64,{b64}"
    now = datetime.now(tz=timezone.utc)

    async with async_session_factory() as session:
        existing = await session.execute(
            sa_select(PropertyImage).where(
                PropertyImage.parcel_id == parcel_id,
                PropertyImage.image_type == image_type,
            )
        )
        prop_image = existing.scalars().first()

        if prop_image:
            prop_image.file_path = data_uri
            prop_image.captured_at = now
            prop_image.source_url = source_url
        else:
            prop_image = PropertyImage(
                parcel_id=parcel_id,
                image_type=image_type,
                file_path=data_uri,
                captured_at=now,
                source_url=source_url,
            )
            session.add(prop_image)

        await session.commit()


# ── Factory ───────────────────────────────────────────────────────────────────

def create_image_capture_server() -> ImageCaptureMCPServer:
    """Build the Image Capture MCP server from settings."""
    from aloha.config import settings
    return ImageCaptureMCPServer(google_api_key=settings.google_maps_api_key)
