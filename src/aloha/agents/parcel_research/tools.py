"""Tool implementations for the Parcel Research Agent.

Each tool is a plain async function.  The agent calls them via Pydantic AI's
tool-call mechanism.  All tools return dicts so the LLM can read and act on
the data.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

from aloha.scrapers.tier1_apis.arcgis import ArcGISParcelScraper

log = structlog.get_logger().bind(agent="parcel_research")

# ── ArcGIS county endpoint registry ──────────────────────────────────────────
# Maps (STATE, county_lower) → ArcGIS feature layer URL.
# Populated on demand; this is a seed list — more added as they're discovered.
_ARCGIS_ENDPOINTS: dict[tuple[str, str], str] = {
    # Florida
    ("FL", "orange"): "https://maps.ocfl.net/arcgis/rest/services/Parcels/MapServer/0",
    ("FL", "miami-dade"): "https://giswebservices.miamidade.gov/gis/rest/services/MDC_Parcels/MapServer/0",
    ("FL", "broward"): "https://gisweb.broward.org/arcgis/rest/services/PropertyAppraiser/MapServer/0",
    ("FL", "duval"): "https://maps.coj.net/arcgis/rest/services/PropertyAppraiser/MapServer/0",
    ("FL", "hillsborough"): "https://maps.hcpafl.org/arcgis/rest/services/MapServices/Parcel_Data/MapServer/0",
    # Texas
    ("TX", "harris"): "https://arcgis.hcad.org/arcgis/rest/services/Parcels/MapServer/0",
    ("TX", "travis"): "https://services.arcgis.com/0L95CJ0VTaxqcmED/arcgis/rest/services/Travis_County_Parcels/FeatureServer/0",
    ("TX", "bexar"): "https://maps.bcad.org/arcgis/rest/services/Parcels/MapServer/0",
    # California
    ("CA", "los angeles"): "https://mapping.gis.lacounty.gov/hosting/rest/services/Assessor/Parcels/MapServer/0",
    ("CA", "san diego"): "https://gis.sdarcc.gov/arcgis/rest/services/Parcels/MapServer/0",
    # Georgia
    ("GA", "fulton"): "https://gis.fultoncountyga.gov/arcgis/rest/services/Parcels/MapServer/0",
    ("GA", "gwinnett"): "https://maps.gwinnettcounty.com/arcgis/rest/services/Parcels/MapServer/0",
    # Arizona
    ("AZ", "maricopa"): "https://maps.maricopa.gov/arcgis/rest/services/Assessor/Parcels/MapServer/0",
    # Illinois
    ("IL", "cook"): "https://gisapps.cookcountyil.gov/arcgis/rest/services/AssessorWarehouse/MapServer/0",
    # Colorado
    ("CO", "denver"): "https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/Parcels/FeatureServer/0",
    # Ohio
    ("OH", "franklin"): "https://apps.franklincountyauditor.com/arcgis/rest/services/Parcels/MapServer/0",
    ("OH", "cuyahoga"): "https://gis.cuyahogacounty.us/arcgis/rest/services/Parcels/MapServer/0",
}


async def query_arcgis_parcel(
    parcel_id: str,
    state: str,
    county: str,
) -> dict[str, Any]:
    """Query the county ArcGIS parcel service for property details.

    Args:
        parcel_id: The assessor parcel number / APN.
        state: Two-letter state abbreviation.
        county: County name (case-insensitive).

    Returns:
        Normalised parcel dict, or ``{"error": "..."}`` if unavailable.
    """
    key = (state.upper(), county.lower())
    service_url = _ARCGIS_ENDPOINTS.get(key)

    if not service_url:
        log.debug("no_arcgis_endpoint", state=state, county=county)
        return {"error": f"No ArcGIS endpoint registered for {state}/{county}"}

    scraper = ArcGISParcelScraper(service_url=service_url)
    try:
        result = await scraper.query_by_apn(parcel_id)
        if result is None:
            return {"error": f"APN {parcel_id!r} not found in {state}/{county} ArcGIS layer"}
        log.info("arcgis_parcel_found", parcel_id=parcel_id, state=state, county=county)
        return result
    except Exception as exc:
        log.warning("arcgis_query_failed", parcel_id=parcel_id, error=str(exc))
        return {"error": str(exc)}
    finally:
        await scraper.close()


async def query_assessor_web(
    parcel_id: str,
    state: str,
    county: str,
    address: str | None = None,
) -> dict[str, Any]:
    """Scrape the county assessor website for parcel data.

    Falls back to this when no ArcGIS endpoint exists.  This is a stub that
    returns a placeholder; the actual Playwright implementation lives in
    Tier 2/3 scrapers and will be wired in when those are built.

    Args:
        parcel_id: The assessor parcel number.
        state: Two-letter state code.
        county: County name.
        address: Property address (optional, used for fallback search).

    Returns:
        Partial parcel dict from assessor website, or ``{"error": "..."}`` if unavailable.
    """
    log.info(
        "assessor_web_stub",
        parcel_id=parcel_id,
        state=state,
        county=county,
        note="Tier 2 Playwright scraper not yet wired in",
    )
    # Will be replaced by dynamic Playwright scraper dispatch once Tier 2 is built.
    return {
        "error": "assessor_web scraper not yet implemented for this county",
        "parcel_id": parcel_id,
        "state": state,
        "county": county,
    }


def parse_legal_description(legal_description: str) -> dict[str, Any]:
    """Parse a legal description string into structured components.

    Handles three common formats:
    - **Lot/Block/Subdivision**: "LOT 5 BLK 3 SUNRISE ESTATES"
    - **Metes and Bounds**: "COM AT NW COR SEC 14 T2S R3E ..."
    - **Condo/Unit**: "UNIT 12B BLDG 3 HARBOR TOWERS CONDO"

    Args:
        legal_description: Raw legal description text from assessor records.

    Returns:
        Dict with ``format``, ``subdivision``, ``lot``, ``block``, ``section``,
        ``township``, ``range``, ``unit``, ``building``, and ``raw`` keys.
    """
    if not legal_description:
        return {"format": "unknown", "raw": ""}

    desc = legal_description.strip().upper()
    result: dict[str, Any] = {"format": "unknown", "raw": legal_description.strip()}

    # ── Lot / Block / Subdivision ─────────────────────────────────────────
    lot_match = re.search(r"\bLOT\s+(\w+)\b", desc)
    block_match = re.search(r"\b(?:BLK|BLOCK)\s+(\w+)\b", desc)
    if lot_match or block_match:
        result["format"] = "lot_block"
        result["lot"] = lot_match.group(1) if lot_match else None
        result["block"] = block_match.group(1) if block_match else None

        # Extract subdivision name — text after LOT/BLK tokens before trailing info
        sub_match = re.search(
            r"(?:BLK|BLOCK)\s+\w+\s+([A-Z][A-Z0-9\s]+?)(?:\s+(?:UNIT|BLDG|PH|PLAT|PB|PG)|\s*$)",
            desc,
        )
        if not sub_match:
            sub_match = re.search(
                r"LOT\s+\w+\s+([A-Z][A-Z0-9\s]+?)(?:\s+(?:LOT|BLK|UNIT|BLDG)|\s*$)",
                desc,
            )
        result["subdivision"] = sub_match.group(1).strip() if sub_match else None
        return result

    # ── Metes and Bounds (Section/Township/Range) ─────────────────────────
    sec_match = re.search(r"\bSEC(?:TION)?\s+(\d+)\b", desc)
    twp_match = re.search(r"\bT(\d+[NS])\b", desc)
    rng_match = re.search(r"\bR(\d+[EW])\b", desc)
    if sec_match:
        result["format"] = "metes_bounds"
        result["section"] = sec_match.group(1) if sec_match else None
        result["township"] = twp_match.group(1) if twp_match else None
        result["range"] = rng_match.group(1) if rng_match else None
        return result

    # ── Condo / Unit ──────────────────────────────────────────────────────
    unit_match = re.search(r"\bUNIT\s+([\w-]+)\b", desc)
    bldg_match = re.search(r"\bBLDG\s+([\w-]+)\b", desc)
    if unit_match:
        result["format"] = "condo"
        result["unit"] = unit_match.group(1) if unit_match else None
        result["building"] = bldg_match.group(1) if bldg_match else None
        # Condo name: everything after BLDG token up to CONDO keyword
        condo_match = re.search(r"(?:BLDG\s+\w+\s+)([A-Z][A-Z0-9\s]+?)(?:\s+CONDO|\s*$)", desc)
        result["subdivision"] = condo_match.group(1).strip() if condo_match else None
        return result

    return result


def classify_property_type(
    land_use_code: str | None,
    zoning: str | None,
    legal_description: str | None,
) -> str:
    """Derive a canonical property_type from land use code and zoning.

    Returns one of: ``residential``, ``commercial``, ``land``, ``industrial``,
    ``agricultural``, or ``unknown``.
    """
    # Land use code takes priority — most assessors use IAAO standard codes
    if land_use_code:
        luc = str(land_use_code).strip().upper()
        # IAAO / Florida DOR land use codes
        if re.match(r"^0[0-9]$|^1[0-9]$|^SINGLE|^CONDO|^MULTI|^MOBILE|^RES", luc):
            return "residential"
        if re.match(r"^2[0-9]$|^COMM|^RETAIL|^OFFICE|^HOTEL|^STRIP", luc):
            return "commercial"
        if re.match(r"^3[0-9]$|^IND|^WAREHOUSE|^MANUF|^LIGHT IND", luc):
            return "industrial"
        if re.match(r"^4[0-9]$|^AG|^FARM|^CROP|^RANCH|^TIMBER", luc):
            return "agricultural"
        if re.match(r"^5[0-9]$|^VAC|^LAND|^UNDEVELOPED|^ACREAGE", luc):
            return "land"

    # Fall back to zoning code
    if zoning:
        z = str(zoning).strip().upper()
        if re.match(r"^R[SF1-4]|^RS|^RM|^MF|^A-R|^SFR|^MFR", z):
            return "residential"
        if re.match(r"^C[1-5]|^B[1-3]|^CB|^GC|^NC|^COMM", z):
            return "commercial"
        if re.match(r"^M[1-3]|^I[1-3]|^LI|^HI|^IND", z):
            return "industrial"
        if re.match(r"^A[G1-3]|^AG|^FARM|^RU|^RR", z):
            return "agricultural"

    # Legal description clue
    if legal_description:
        ld = legal_description.upper()
        if "CONDO" in ld or "UNIT" in ld:
            return "residential"
        if "ACREAGE" in ld or "TRACT" in ld:
            return "land"

    return "unknown"
