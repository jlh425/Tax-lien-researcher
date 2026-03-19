"""Tool implementations for the Zoning Agent.

Pure functions for zoning code parsing, land use classification,
and development potential assessment.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

log = structlog.get_logger().bind(agent="zoning")

# Common zoning code prefixes → category mapping
_ZONING_CATEGORIES: dict[str, str] = {
    "R": "residential",
    "RS": "residential_single",
    "RM": "residential_multi",
    "RMF": "residential_multi",
    "C": "commercial",
    "B": "commercial",  # "business" districts
    "O": "office",
    "I": "industrial",
    "M": "industrial",  # "manufacturing" districts
    "A": "agricultural",
    "AG": "agricultural",
    "PUD": "planned_unit_development",
    "PD": "planned_development",
    "MU": "mixed_use",
    "MX": "mixed_use",
    "P": "public",
    "OS": "open_space",
    "CF": "community_facility",
    "W": "waterfront",
}

# Land use codes → human-readable descriptions
_LAND_USE_DESCRIPTIONS: dict[str, str] = {
    "residential": "Residential — single or multi-family dwellings",
    "residential_single": "Single-Family Residential",
    "residential_multi": "Multi-Family Residential",
    "commercial": "Commercial — retail, office, or service businesses",
    "office": "Office / Professional",
    "industrial": "Industrial — manufacturing, warehouse, distribution",
    "agricultural": "Agricultural — farming, ranching, forestry",
    "planned_unit_development": "Planned Unit Development (PUD)",
    "planned_development": "Planned Development (PD)",
    "mixed_use": "Mixed Use — residential + commercial",
    "public": "Public / Institutional",
    "open_space": "Open Space / Conservation",
    "community_facility": "Community Facility",
    "waterfront": "Waterfront",
    "unknown": "Unknown / Unclassified",
}


def classify_zoning(raw_code: str | None) -> dict[str, Any]:
    """Parse a raw zoning code into a structured classification.

    Returns a dict with ``code``, ``category``, ``description``,
    ``density_indicator``, and ``is_residential``.
    """
    if not raw_code:
        return {
            "code": None,
            "category": "unknown",
            "description": _LAND_USE_DESCRIPTIONS["unknown"],
            "density_indicator": None,
            "is_residential": False,
        }

    code = raw_code.strip().upper()

    # Extract letter prefix and numeric suffix
    match = re.match(r"^([A-Z]+)[-\s]?(\d*)(.*)$", code)
    prefix = match.group(1) if match else code
    density = match.group(2) if match and match.group(2) else None

    # Find best matching category (longest prefix first)
    category = "unknown"
    for length in range(len(prefix), 0, -1):
        candidate = prefix[:length]
        if candidate in _ZONING_CATEGORIES:
            category = _ZONING_CATEGORIES[candidate]
            break

    is_residential = category.startswith("residential")

    return {
        "code": code,
        "category": category,
        "description": _LAND_USE_DESCRIPTIONS.get(category, _LAND_USE_DESCRIPTIONS["unknown"]),
        "density_indicator": density,
        "is_residential": is_residential,
    }


def classify_land_use(land_use_code: str | None) -> dict[str, Any]:
    """Map a county land use code to a standardised property type.

    Land use codes vary by county but often follow patterns like
    ``"0100"`` (residential), ``"1000"`` (vacant land), etc.
    """
    if not land_use_code:
        return {"land_use_code": None, "property_type": "unknown", "description": "Unknown"}

    code = land_use_code.strip()

    # Common county assessor code ranges
    if code.startswith(("01", "02", "03", "04")):
        return {
            "land_use_code": code,
            "property_type": "residential",
            "description": "Residential property",
        }
    if code.startswith(("10", "11", "12")):
        return {
            "land_use_code": code,
            "property_type": "vacant_land",
            "description": "Vacant / undeveloped land",
        }
    if code.startswith(("20", "21", "22", "23", "24", "25")):
        return {
            "land_use_code": code,
            "property_type": "commercial",
            "description": "Commercial property",
        }
    if code.startswith(("30", "31", "32", "33")):
        return {
            "land_use_code": code,
            "property_type": "industrial",
            "description": "Industrial property",
        }
    if code.startswith(("50", "51", "52", "53", "54")):
        return {
            "land_use_code": code,
            "property_type": "agricultural",
            "description": "Agricultural property",
        }
    if code.startswith(("70", "71", "72", "73", "74", "75", "76", "77", "78", "79", "80")):
        return {
            "land_use_code": code,
            "property_type": "government",
            "description": "Government / institutional property",
        }

    return {
        "land_use_code": code,
        "property_type": "other",
        "description": f"Other land use (code {code})",
    }


def assess_development_potential(
    *,
    zoning_category: str,
    acreage: float | None = None,
    year_built: int | None = None,
    assessed_total: int | None = None,
    market_value_est: int | None = None,
) -> dict[str, Any]:
    """Assess the development/redevelopment potential of a parcel.

    Returns a dict with ``potential`` (high/medium/low/none),
    ``factors`` list, and ``notes``.
    """
    factors: list[str] = []
    score = 0

    # Vacant or agricultural land has higher development potential
    if zoning_category in ("agricultural", "open_space", "unknown"):
        factors.append("undeveloped/agricultural land")
        score += 2

    # Large parcels have more potential
    if acreage and acreage > 5:
        factors.append(f"large parcel ({acreage:.1f} acres)")
        score += 2
    elif acreage and acreage > 1:
        factors.append(f"moderate parcel ({acreage:.1f} acres)")
        score += 1

    # Old structures may be candidates for redevelopment
    if year_built and year_built < 1970:
        factors.append(f"aging structure (built {year_built})")
        score += 1

    # Land value exceeds improvement value → underimproved
    if assessed_total and market_value_est:
        ratio = market_value_est / assessed_total if assessed_total > 0 else 0
        if ratio < 0.5:
            factors.append("undervalued relative to market")
            score += 1

    # Mixed use and commercial zones allow denser development
    if zoning_category in ("mixed_use", "commercial", "planned_unit_development"):
        factors.append(f"{zoning_category} zoning allows flexible development")
        score += 1

    if score >= 4:
        potential = "high"
    elif score >= 2:
        potential = "medium"
    elif score >= 1:
        potential = "low"
    else:
        potential = "none"

    return {
        "potential": potential,
        "score": min(score, 5),
        "factors": factors,
        "notes": "; ".join(factors) if factors else "no development indicators",
    }


def summarise_zoning(
    *,
    zoning: dict[str, Any],
    land_use: dict[str, Any],
    development: dict[str, Any],
) -> dict[str, Any]:
    """Combine zoning, land use, and development assessments into a summary."""
    return {
        "zoning_code": zoning.get("code"),
        "zoning_category": zoning.get("category"),
        "zoning_description": zoning.get("description"),
        "is_residential": zoning.get("is_residential", False),
        "land_use_type": land_use.get("property_type"),
        "land_use_description": land_use.get("description"),
        "development_potential": development.get("potential"),
        "development_score": development.get("score"),
        "development_factors": development.get("factors", []),
    }
