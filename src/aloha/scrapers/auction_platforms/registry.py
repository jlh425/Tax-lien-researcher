"""Auction platform scraper registry.

Maps (state, county) tuples to their auction platform and provides a factory
function ``get_auction_scraper()`` that returns an instantiated scraper.

Usage::

    scraper = get_auction_scraper("FL", "orange")
    if scraper:
        records = await scraper.discover(max_records=500)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


@dataclass(frozen=True, slots=True)
class AuctionEntry:
    """Registry entry for an auction platform scraper."""

    platform: str   # "bid4assets" | "realauction" | "govease"
    notes: str = ""


def _build_registry() -> dict[tuple[str, str], AuctionEntry]:
    from aloha.scrapers.auction_platforms.realauction import REALAUCTION_ENDPOINTS
    from aloha.scrapers.auction_platforms.govease import GOVEASE_ENDPOINTS

    registry: dict[tuple[str, str], AuctionEntry] = {}

    for state, county in REALAUCTION_ENDPOINTS:
        registry[(state.upper(), county.lower())] = AuctionEntry(platform="realauction")

    for state, county in GOVEASE_ENDPOINTS:
        key = (state.upper(), county.lower())
        # Don't overwrite RealAuction entries (prefer RealAuction for FL)
        registry.setdefault(key, AuctionEntry(platform="govease"))

    return registry


# Build once at import time
AUCTION_REGISTRY: dict[tuple[str, str], AuctionEntry] = _build_registry()


def get_auction_scraper(state: str, county: str) -> Any | None:
    """Return an instantiated auction scraper for state/county, or None.

    Args:
        state: Two-letter state abbreviation.
        county: County name in lowercase.

    Returns:
        An instantiated scraper with a ``discover()`` method, or ``None`` if
        no auction platform is registered for this county.
    """
    key = (state.upper(), county.lower())
    entry = AUCTION_REGISTRY.get(key)

    if entry is None:
        # Check if Bid4Assets covers this state (broad coverage, no county-specific registry)
        from aloha.scrapers.auction_platforms.bid4assets import get_bid4assets_scraper
        from aloha.agents.discovery.state_registry import classify_instrument, InstrumentType
        instrument = classify_instrument(state)
        if instrument == InstrumentType.TAX_DEED:
            return get_bid4assets_scraper(state, county)
        return None

    if entry.platform == "realauction":
        from aloha.scrapers.auction_platforms.realauction import get_realauction_scraper
        return get_realauction_scraper(state, county)

    if entry.platform == "govease":
        from aloha.scrapers.auction_platforms.govease import get_govease_scraper
        return get_govease_scraper(state, county)

    if entry.platform == "bid4assets":
        from aloha.scrapers.auction_platforms.bid4assets import get_bid4assets_scraper
        return get_bid4assets_scraper(state, county)

    return None
