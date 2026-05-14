"""GIS MCP Server — Google Geocoding + ArcGIS parcel geometry.

Provides geocoding (address → lat/lng) and reverse geocoding (lat/lng → address)
via the Google Maps Geocoding API, plus parcel boundary retrieval via county
ArcGIS feature layers.

Tools exposed:
- geocode_address: convert a street address to coordinates
- reverse_geocode: convert lat/lng to a formatted address
- get_parcel_boundary: retrieve parcel polygon geometry (GeoJSON)
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from aloha.mcp_servers.base import BaseMCPServer, ToolDefinition

log = structlog.get_logger().bind(component="gis_mcp")

_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
_TIMEOUT = 15.0


class GISMCPServer(BaseMCPServer):
    """MCP server wrapping the Google Maps Geocoding API."""

    def __init__(self, api_key: str) -> None:
        super().__init__(name="gis")
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None
        self._register_tools()

    def _register_tools(self) -> None:
        self.register_tool(
            ToolDefinition(
                name="geocode_address",
                description=(
                    "Convert a street address to geographic coordinates using "
                    "the Google Geocoding API."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "address": {
                            "type": "string",
                            "description": "Full street address to geocode.",
                        },
                    },
                    "required": ["address"],
                },
                handler=self.geocode_address,
            )
        )

        self.register_tool(
            ToolDefinition(
                name="reverse_geocode",
                description=(
                    "Convert latitude/longitude coordinates to a formatted address "
                    "using the Google Geocoding API."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "latitude": {
                            "type": "number",
                            "description": "Latitude in decimal degrees.",
                        },
                        "longitude": {
                            "type": "number",
                            "description": "Longitude in decimal degrees.",
                        },
                    },
                    "required": ["latitude", "longitude"],
                },
                handler=self.reverse_geocode,
            )
        )

        self.register_tool(
            ToolDefinition(
                name="get_parcel_boundary",
                description=(
                    "Retrieve the parcel boundary polygon (GeoJSON) for a given "
                    "parcel ID via county ArcGIS feature layers."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "parcel_id": {
                            "type": "string",
                            "description": "Assessor parcel number.",
                        },
                        "state": {
                            "type": "string",
                            "description": "Two-letter US state abbreviation.",
                        },
                        "county": {
                            "type": "string",
                            "description": "County name.",
                        },
                    },
                    "required": ["parcel_id", "state", "county"],
                },
                handler=self.get_parcel_boundary,
            )
        )

    # -- HTTP client -----------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(_TIMEOUT))
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # -- Tool handlers ---------------------------------------------------------

    async def geocode_address(self, address: str) -> dict[str, Any]:
        """Geocode an address via Google Maps Geocoding API."""
        try:
            client = await self._get_client()
            response = await client.get(
                _GEOCODE_URL,
                params={"address": address, "key": self._api_key},
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "OK":
                return {"error": f"Geocoding failed: {data.get('status')}", "results": []}

            results = [_normalise_geocode_result(r) for r in data.get("results", [])]
            log.info("geocode_complete", address=address, count=len(results))
            return {"results": results}
        except httpx.HTTPStatusError as exc:
            log.warning("geocode_api_error", status=exc.response.status_code)
            return {"error": f"API error {exc.response.status_code}", "results": []}
        except Exception as exc:
            log.error("geocode_failed", error=str(exc))
            return {"error": str(exc), "results": []}

    async def reverse_geocode(self, latitude: float, longitude: float) -> dict[str, Any]:
        """Reverse geocode coordinates via Google Maps Geocoding API."""
        try:
            client = await self._get_client()
            response = await client.get(
                _GEOCODE_URL,
                params={"latlng": f"{latitude},{longitude}", "key": self._api_key},
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "OK":
                return {"error": f"Reverse geocoding failed: {data.get('status')}", "results": []}

            results = [_normalise_geocode_result(r) for r in data.get("results", [])]
            log.info("reverse_geocode_complete", lat=latitude, lng=longitude, count=len(results))
            return {"results": results}
        except httpx.HTTPStatusError as exc:
            log.warning("reverse_geocode_api_error", status=exc.response.status_code)
            return {"error": f"API error {exc.response.status_code}", "results": []}
        except Exception as exc:
            log.error("reverse_geocode_failed", error=str(exc))
            return {"error": str(exc), "results": []}

    async def get_parcel_boundary(
        self,
        parcel_id: str,
        state: str,
        county: str,
    ) -> dict[str, Any]:
        """Retrieve parcel boundary polygon via county ArcGIS feature layer.

        Queries the county ArcGIS parcel service with ``returnGeometry=True``
        and converts the Esri rings to a GeoJSON Polygon.
        """
        from aloha.agents.parcel_research.tools import _ARCGIS_ENDPOINTS
        from aloha.scrapers.tier1_apis.arcgis import ArcGISParcelScraper

        key = (state.upper(), county.lower())
        service_url = _ARCGIS_ENDPOINTS.get(key)
        if not service_url:
            log.info("no_arcgis_endpoint", state=state, county=county)
            return {
                "error": f"No ArcGIS endpoint for {state}/{county}",
                "parcel_id": parcel_id,
                "boundary": None,
            }

        scraper = ArcGISParcelScraper(service_url=service_url)
        try:
            result = await scraper.query_by_apn(parcel_id)
            if result is None:
                return {
                    "error": f"Parcel {parcel_id!r} not found in {state}/{county}",
                    "parcel_id": parcel_id,
                    "boundary": None,
                }

            result.get("raw_attributes", {})
            # The scraper's _normalise already extracted centroid; we need
            # the raw geometry rings from a direct query.
            # Re-query with geometry explicitly for the raw rings.
            apn_clean = parcel_id.replace("-", "").replace(" ", "").upper()
            query_result = await scraper._query(
                where_clause=f"UPPER(REPLACE(APN,'-','')) = '{apn_clean}'",
                return_geometry=True,
                out_sr=4326,
            )
            features = query_result.get("features", [])
            if not features:
                # Fall back to the already-found result with centroid only
                return {
                    "parcel_id": parcel_id,
                    "boundary": _point_geojson(result.get("latitude"), result.get("longitude")),
                    "centroid": {
                        "latitude": result.get("latitude"),
                        "longitude": result.get("longitude"),
                    },
                }

            geometry = features[0].get("geometry", {})
            rings = geometry.get("rings")
            if rings:
                # Convert Esri rings to GeoJSON Polygon
                geojson = {
                    "type": "Polygon",
                    "coordinates": rings,
                }
            else:
                # Point geometry fallback
                geojson = _point_geojson(geometry.get("y"), geometry.get("x"))

            log.info(
                "parcel_boundary_found",
                parcel_id=parcel_id,
                state=state,
                county=county,
                has_polygon=bool(rings),
            )
            return {
                "parcel_id": parcel_id,
                "boundary": geojson,
                "centroid": {
                    "latitude": result.get("latitude"),
                    "longitude": result.get("longitude"),
                },
            }
        except Exception as exc:
            log.warning(
                "parcel_boundary_failed",
                parcel_id=parcel_id,
                error=str(exc),
            )
            return {"error": str(exc), "parcel_id": parcel_id, "boundary": None}
        finally:
            await scraper.close()


# -- Geometry helpers ----------------------------------------------------------


def _point_geojson(lat: float | None, lng: float | None) -> dict[str, Any] | None:
    """Build a GeoJSON Point from lat/lng, or None."""
    if lat is not None and lng is not None:
        return {"type": "Point", "coordinates": [lng, lat]}
    return None


# -- Normalisation helpers -----------------------------------------------------


def _normalise_geocode_result(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a Google Geocoding API result to canonical fields."""
    geometry = raw.get("geometry", {})
    location = geometry.get("location", {})

    components: dict[str, str] = {}
    for comp in raw.get("address_components", []):
        for comp_type in comp.get("types", []):
            components[comp_type] = comp.get("long_name", "")

    return {
        "formatted_address": raw.get("formatted_address"),
        "latitude": location.get("lat"),
        "longitude": location.get("lng"),
        "place_id": raw.get("place_id"),
        "location_type": geometry.get("location_type"),
        "components": components,
    }


# -- Factory -------------------------------------------------------------------


def create_gis_server() -> GISMCPServer:
    """Build the GIS MCP server from settings.

    Raises:
        ValueError: If ``GOOGLE_MAPS_API_KEY`` is not configured.
    """
    from aloha.config import settings

    api_key = settings.google_maps_api_key
    if not api_key:
        raise ValueError("GOOGLE_MAPS_API_KEY is required to use the GIS MCP server.")
    return GISMCPServer(api_key=api_key)
