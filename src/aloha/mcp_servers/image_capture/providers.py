"""Multi-provider image fetch — Mapbox (free tier) + Google Maps (paid fallback).

Provider priority for satellite imagery:
    1. MapboxSatelliteProvider  — free, 50k req/month, no credit card needed
    2. GoogleSatelliteProvider  — paid, ~$2/1k; used when Mapbox unavailable

ProviderChain tries each provider in order and returns the first successful bytes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import httpx
import structlog

log = structlog.get_logger().bind(component="image_providers")

_MAPBOX_STATIC_URL = (
    "https://api.mapbox.com/styles/v1/mapbox/satellite-v9/static"
    "/{lon},{lat},{zoom}/{width}x{height}"
)
_GOOGLE_STATIC_URL = "https://maps.googleapis.com/maps/api/staticmap"
_GOOGLE_STREETVIEW_URL = "https://maps.googleapis.com/maps/api/streetview"
_TIMEOUT = 30.0


class ImageProvider(ABC):
    """Abstract interface for a single image source."""

    @abstractmethod
    async def fetch(
        self,
        *,
        latitude: float,
        longitude: float,
        zoom: int = 18,
        width: int = 800,
        height: int = 600,
    ) -> bytes | None:
        """Return raw image bytes, or None if the provider cannot fulfil the request."""


class MapboxSatelliteProvider(ImageProvider):
    """Fetch satellite images from the Mapbox Static Images API (free tier).

    IMPORTANT: Mapbox uses **longitude, latitude** order in the URL path —
    the opposite of Google which uses lat,lng in query params. Never swap these.
    """

    def __init__(self, access_token: str) -> None:
        self._token = access_token

    async def fetch(
        self,
        *,
        latitude: float,
        longitude: float,
        zoom: int = 18,
        width: int = 800,
        height: int = 600,
    ) -> bytes | None:
        url = _MAPBOX_STATIC_URL.format(
            lon=longitude,  # NOTE: lon first!
            lat=latitude,
            zoom=zoom,
            width=width,
            height=height,
        )
        params = {"access_token": self._token}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(_TIMEOUT)) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                # Mapbox returns JSON {"message":"Not Authorized"} on bad token
                # instead of HTTP 4xx — detect by content-type.
                ct = response.headers.get("content-type", "")
                if "application/json" in ct:
                    log.warning("mapbox_auth_error", body=response.text[:200])
                    return None
                return response.content
        except Exception as exc:
            log.warning("mapbox_satellite_failed", error=str(exc))
            return None


class GoogleSatelliteProvider(ImageProvider):
    """Fetch satellite images from the Google Maps Static API (paid)."""

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    async def fetch(
        self,
        *,
        latitude: float,
        longitude: float,
        zoom: int = 18,
        width: int = 800,
        height: int = 600,
    ) -> bytes | None:
        params = {
            "center": f"{latitude},{longitude}",
            "zoom": str(zoom),
            "size": f"{width}x{height}",
            "maptype": "satellite",
            "key": self._key,
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(_TIMEOUT)) as client:
                response = await client.get(_GOOGLE_STATIC_URL, params=params)
                response.raise_for_status()
                return response.content
        except Exception as exc:
            log.warning("google_satellite_failed", error=str(exc))
            return None


class GoogleStreetViewProvider(ImageProvider):
    """Fetch street-level images from the Google Street View Static API (paid)."""

    def __init__(self, api_key: str, address: str) -> None:
        self._key = api_key
        self._address = address

    async def fetch(
        self,
        *,
        latitude: float,
        longitude: float,
        zoom: int = 18,
        width: int = 800,
        height: int = 600,
    ) -> bytes | None:
        params = {
            "size": f"{width}x{height}",
            "location": self._address,
            "key": self._key,
            "source": "outdoor",
            "return_error_code": "true",
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(_TIMEOUT)) as client:
                response = await client.get(_GOOGLE_STREETVIEW_URL, params=params)
                response.raise_for_status()
                return response.content
        except Exception as exc:
            log.warning("google_street_view_failed", error=str(exc))
            return None


class ProviderChain:
    """Try providers in order; return the first successful bytes result.

    Any individual provider that raises or returns None is silently skipped.
    Returns None only if every provider fails.
    """

    def __init__(self, providers: list[ImageProvider]) -> None:
        self._providers = providers

    async def fetch(self, **kwargs: object) -> bytes | None:
        for provider in self._providers:
            try:
                result = await provider.fetch(**kwargs)  # type: ignore[arg-type]
                if result:
                    return result
            except Exception as exc:
                log.warning(
                    "provider_failed",
                    provider=type(provider).__name__,
                    error=str(exc),
                )
                continue
        return None
