"""Scraper registry — maps (state, county) to scraper class + tier metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aloha.scrapers.base import BaseScraper


@dataclass(frozen=True, slots=True)
class ScraperEntry:
    """Metadata for a registered scraper."""

    scraper_class: str          # Dotted import path, e.g. "aloha.scrapers.fl.duval.DuvalScraper"
    tier: int                   # 1 = simple HTML, 2 = JS-rendered, 3 = CAPTCHA / login
    notes: str = ""


# Keys are (state_fips_or_abbr, county_name_lower) tuples.
SCRAPER_REGISTRY: dict[tuple[str, str], ScraperEntry] = {
    # ── Examples (uncomment as scrapers are implemented) ──────────────────
    # ("FL", "duval"): ScraperEntry(
    #     scraper_class="aloha.scrapers.fl.duval.DuvalScraper",
    #     tier=1,
    #     notes="Simple HTML table, no auth required.",
    # ),
    # ("TX", "harris"): ScraperEntry(
    #     scraper_class="aloha.scrapers.tx.harris.HarrisScraper",
    #     tier=2,
    #     notes="Requires Playwright for JS-rendered content.",
    # ),
    # ("CA", "los_angeles"): ScraperEntry(
    #     scraper_class="aloha.scrapers.ca.los_angeles.LACountyScraper",
    #     tier=3,
    #     notes="CAPTCHA gate; needs solver integration.",
    # ),
}


def get_scraper_entry(state: str, county: str) -> ScraperEntry | None:
    """Look up the scraper entry for a given state/county pair.

    Args:
        state: Two-letter state abbreviation (e.g. ``"FL"``).
        county: Lower-cased county name (e.g. ``"duval"``).

    Returns:
        The ``ScraperEntry`` if registered, otherwise ``None``.
    """
    return SCRAPER_REGISTRY.get((state.upper(), county.lower()))
