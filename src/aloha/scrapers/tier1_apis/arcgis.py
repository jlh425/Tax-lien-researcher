"""Tier 1 — ArcGIS REST API scraper.

Two capabilities:

1. **Parcel query** (``ArcGISParcelScraper``) — queries the county's ArcGIS
   parcel feature layer to retrieve assessed value, owner, zoning, acreage,
   and lat/lng from the geometry centroid.

2. **Parcel map export** (``ArcGISMapExporter``) — calls the ArcGIS
   ``exportImage`` endpoint to produce a static PNG of the parcel with zoning
   and parcel-boundary overlays.  Used by the Image Capture pipeline.

Usage:
    scraper = ArcGISParcelScraper(
        service_url="https://gis.ocgov.com/arcgis/rest/services/Parcels/MapServer/0",
    )
    record = await scraper.query_by_apn("123-456-789")

    exporter = ArcGISMapExporter(
        service_url="https://gis.ocgov.com/arcgis/rest/services/Parcels/MapServer",
    )
    png_bytes = await exporter.export(bbox=(-117.9, 33.7, -117.8, 33.8))
"""

from __future__ import annotations

from typing import Any

import structlog

from aloha.scrapers.base import BaseScraper

log = structlog.get_logger().bind(scraper="arcgis")

# Well-known ArcGIS field aliases → our canonical names
# Counties use different column names; this table covers the most common ones.
_APN_FIELD_ALIASES = ("APN", "PARCEL_NO", "PARCELID", "PIN", "PARCEL_ID", "ASSESSOR_PARCEL_NO")
_ADDRESS_FIELD_ALIASES = ("SITUS_ADDR", "SITE_ADDRESS", "PROP_ADDR", "ADDRESS", "FULLADDRESS")
_OWNER_FIELD_ALIASES = ("OWNER", "OWNER_NAME", "OWN_NAME", "OWNERNAME")
_ASSESSED_FIELD_ALIASES = ("TOTAL_AV", "ASSESSED_VALUE", "TOTAL_ASSESSED", "ASSR_VAL", "AV_TOTAL")
_ZONING_FIELD_ALIASES = ("ZONE_CODE", "ZONING", "ZONE", "ZONING_CODE", "ZONE_CLASS")
_ACREAGE_FIELD_ALIASES = ("ACREAGE", "CALC_ACRES", "ACRES", "LOT_SIZE_ACRES")
_LAND_USE_FIELD_ALIASES = ("LAND_USE", "LANDUSE", "USE_CODE", "LUC")

# ── ArcGIS parcel layer registry ──────────────────────────────────────────────
# Maps (STATE, county_lower) → ArcGIS feature layer URL for parcel enrichment.
# The ArcGISParcelScraper handles arbitrary endpoints; this table provides the
# service URL so callers can look up the right layer for a given county.
ARCGIS_PARCEL_LAYERS: dict[tuple[str, str], str] = {
    # Natrona County, WY — City of Casper Open Data hub
    ("WY", "natrona"): (
        "https://services.arcgis.com/YkVYBaX0zmYbMEMQ/"
        "arcgis/rest/services/Parcels/FeatureServer/0"
    ),
}


def get_arcgis_parcel_url(state: str, county: str) -> str | None:
    """Look up the ArcGIS parcel layer URL for a state/county pair."""
    return ARCGIS_PARCEL_LAYERS.get((state.upper(), county.lower()))


def _pick(fields: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    """Return the first matching alias value from a fields dict."""
    for alias in aliases:
        val = fields.get(alias) or fields.get(alias.lower())
        if val is not None:
            return val
    return None


class ArcGISParcelScraper(BaseScraper):
    """Queries a county ArcGIS parcel feature layer by APN or bounding box."""

    def __init__(self, *, service_url: str) -> None:
        """
        Args:
            service_url: Full URL to the ArcGIS feature layer endpoint.
                         Example: ``https://gis.example.gov/arcgis/rest/services/Parcels/MapServer/0``
        """
        super().__init__()
        self.service_url = service_url.rstrip("/")

    # ── BaseScraper interface ─────────────────────────────────────────────

    async def scrape(self, url: str, params: dict[str, Any] | None = None) -> Any:
        response = await self._fetch(url, params=params)
        return response.json()

    # ── Public API ────────────────────────────────────────────────────────

    async def query_by_apn(self, apn: str) -> dict[str, Any] | None:
        """Fetch parcel attributes for a single APN.

        Returns a normalised dict or ``None`` if not found.
        """
        apn_clean = apn.replace("-", "").replace(" ", "").upper()
        # Try exact match first, then LIKE match
        for where in (
            f"APN = '{apn_clean}'",
            f"UPPER(REPLACE(APN,'-','')) = '{apn_clean}'",
            f"UPPER(APN) LIKE '%{apn_clean}%'",
        ):
            result = await self._query(where_clause=where, return_geometry=True, out_sr=4326)
            features = result.get("features", [])
            if features:
                return self._normalise(features[0])
        return None

    async def query_by_address(self, address: str) -> list[dict[str, Any]]:
        """Fuzzy address search (returns up to 5 candidates)."""
        # Remove unit/apt portions for broader match
        addr_clean = address.split(",")[0].strip().upper()
        where = f"UPPER(SITUS_ADDR) LIKE '%{addr_clean}%'"
        result = await self._query(where_clause=where, result_record_count=5, return_geometry=True)
        return [self._normalise(f) for f in result.get("features", [])]

    async def query_bbox(
        self,
        bbox: tuple[float, float, float, float],
        *,
        max_records: int = 1000,
    ) -> list[dict[str, Any]]:
        """Spatial query — return all parcels within a bounding box.

        Args:
            bbox: (xmin, ymin, xmax, ymax) in WGS84 decimal degrees.
        """
        xmin, ymin, xmax, ymax = bbox
        geometry = f"{xmin},{ymin},{xmax},{ymax}"
        result = await self._query(
            where_clause="1=1",
            geometry=geometry,
            geometry_type="esriGeometryEnvelope",
            spatial_rel="esriSpatialRelIntersects",
            in_sr=4326,
            result_record_count=max_records,
            return_geometry=True,
        )
        return [self._normalise(f) for f in result.get("features", [])]

    # ── Internal helpers ──────────────────────────────────────────────────

    async def _query(self, *, where_clause: str = "1=1", **kwargs: Any) -> dict[str, Any]:
        """Execute an ArcGIS REST ``/query`` request."""
        params: dict[str, Any] = {
            "where": where_clause,
            "outFields": "*",
            "returnGeometry": kwargs.get("return_geometry", False),
            "outSR": kwargs.get("out_sr", 4326),
            "f": "json",
        }
        if "geometry" in kwargs:
            params["geometry"] = kwargs["geometry"]
            params["geometryType"] = kwargs.get("geometry_type", "esriGeometryEnvelope")
            params["spatialRel"] = kwargs.get("spatial_rel", "esriSpatialRelIntersects")
            params["inSR"] = kwargs.get("in_sr", 4326)
        if "result_record_count" in kwargs:
            params["resultRecordCount"] = kwargs["result_record_count"]

        url = f"{self.service_url}/query"
        log.debug("arcgis_query", url=url, where=where_clause)
        return await self.scrape(url, params=params)

    def _normalise(self, feature: dict[str, Any]) -> dict[str, Any]:
        """Map an ArcGIS feature to our canonical parcel fields."""
        attrs = feature.get("attributes", {})
        geo = feature.get("geometry")

        lat = lng = None
        if geo:
            # Point geometry
            lng = geo.get("x")
            lat = geo.get("y")
            # Polygon geometry — use centroid rings[0][0] as rough centroid
            if not lng and "rings" in geo:
                rings = geo["rings"]
                if rings and rings[0]:
                    pts = rings[0]
                    lng = sum(p[0] for p in pts) / len(pts)
                    lat = sum(p[1] for p in pts) / len(pts)

        return {
            "parcel_id": _pick(attrs, _APN_FIELD_ALIASES),
            "address": _pick(attrs, _ADDRESS_FIELD_ALIASES),
            "owner_of_record": _pick(attrs, _OWNER_FIELD_ALIASES),
            "assessed_total": _to_int(_pick(attrs, _ASSESSED_FIELD_ALIASES)),
            "zoning": _pick(attrs, _ZONING_FIELD_ALIASES),
            "acreage": _to_float(_pick(attrs, _ACREAGE_FIELD_ALIASES)),
            "land_use_code": _pick(attrs, _LAND_USE_FIELD_ALIASES),
            "latitude": lat,
            "longitude": lng,
            "raw_attributes": attrs,   # keep original for fallback field extraction
        }


class _ImageFetcher(BaseScraper):
    """Minimal concrete BaseScraper used internally by ArcGISMapExporter."""

    async def scrape(self, url: str, params: dict[str, Any] | None = None) -> Any:
        resp = await self._fetch(url, params=params)
        return resp.content


class ArcGISMapExporter:
    """Exports a static PNG map image from an ArcGIS MapServer.

    Used by the Image Capture pipeline to get the GIS parcel map
    (parcel boundaries + zoning overlay) for a property report.
    """

    def __init__(self, *, service_url: str, layer_ids: str = "show:0,1") -> None:
        """
        Args:
            service_url: URL to the ArcGIS MapServer (not the layer).
                         Example: ``https://gis.example.gov/arcgis/rest/services/Parcels/MapServer``
            layer_ids: Layers to show, e.g. ``"show:0,1,2"`` (parcels + zoning).
        """
        self._base = _ImageFetcher()
        self.service_url = service_url.rstrip("/")
        self.layer_ids = layer_ids

    async def export(
        self,
        bbox: tuple[float, float, float, float],
        *,
        width: int = 800,
        height: int = 600,
    ) -> bytes:
        """Export a map image for the given bounding box.

        Args:
            bbox: (xmin, ymin, xmax, ymax) in WGS84 decimal degrees.
            width: Image width in pixels.
            height: Image height in pixels.

        Returns:
            PNG image bytes.
        """
        xmin, ymin, xmax, ymax = bbox
        params = {
            "bbox": f"{xmin},{ymin},{xmax},{ymax}",
            "bboxSR": "4326",
            "layers": self.layer_ids,
            "size": f"{width},{height}",
            "imageSR": "4326",
            "format": "png",
            "f": "image",
        }
        url = f"{self.service_url}/export"
        log.debug("arcgis_export", url=url, bbox=bbox)
        response = await self._base._fetch(url, params=params)
        return response.content

    async def close(self) -> None:
        await self._base.close()


# ── Type coercion helpers ─────────────────────────────────────────────────────

def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return None
