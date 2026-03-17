"""Tool implementations for the Owner Research Agent.

All tools are pure-Python functions (no LLM needed) that the agent can call
to classify, parse, and enrich owner data from public records.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

log = structlog.get_logger().bind(agent="owner_research")

# ── Owner type classification ─────────────────────────────────────────────────

# Entity suffix patterns (US common forms)
_LLC_PATTERNS = re.compile(
    r"\b(LLC|L\.L\.C\.?|LIMITED LIABILITY|LTD LIABILITY)\b",
    re.IGNORECASE,
)
_CORP_PATTERNS = re.compile(
    r"\b(INC\.?|CORP\.?|CORPORATION|CO\.?|INCORPORATED|LTD\.?|LIMITED)\b",
    re.IGNORECASE,
)
_TRUST_PATTERNS = re.compile(
    r"\b(TRUST|TRUSTEE|TR\.?|REVOCABLE|IRREVOCABLE|FAMILY TRUST|LIVING TRUST)\b",
    re.IGNORECASE,
)
_PARTNERSHIP_PATTERNS = re.compile(
    r"\b(PARTNERSHIP|LP|LLP|L\.P\.?|L\.L\.P\.?|PARTNERS)\b",
    re.IGNORECASE,
)
_GOVERNMENT_PATTERNS = re.compile(
    r"\b(COUNTY OF|CITY OF|STATE OF|DEPT OF|DEPARTMENT|AUTHORITY|MUNICIPALITY|"
    r"HUD|FDIC|VA |USDA|USA |U\.S\.A\.?|UNITED STATES)\b",
    re.IGNORECASE,
)


def classify_owner_type(owner_name: str) -> dict[str, Any]:
    """Classify an owner name as individual, llc, trust, corporation, etc.

    Args:
        owner_name: Raw owner name string from assessor records.

    Returns:
        Dict with ``owner_type``, ``is_entity``, and ``confidence`` keys.
    """
    if not owner_name or not owner_name.strip():
        return {"owner_type": "unknown", "is_entity": False, "confidence": "low"}

    name = owner_name.strip()

    if _GOVERNMENT_PATTERNS.search(name):
        return {"owner_type": "government", "is_entity": True, "confidence": "high"}
    if _TRUST_PATTERNS.search(name):
        return {"owner_type": "trust", "is_entity": True, "confidence": "high"}
    if _LLC_PATTERNS.search(name):
        return {"owner_type": "llc", "is_entity": True, "confidence": "high"}
    if _PARTNERSHIP_PATTERNS.search(name):
        return {"owner_type": "partnership", "is_entity": True, "confidence": "high"}
    if _CORP_PATTERNS.search(name):
        return {"owner_type": "corporation", "is_entity": True, "confidence": "high"}

    # Heuristic: all-caps + no comma usually means entity; "LAST, FIRST" means individual
    if "," in name:
        return {"owner_type": "individual", "is_entity": False, "confidence": "high"}
    if name.isupper() and len(name.split()) >= 3:
        # Could be entity or individual — medium confidence
        return {"owner_type": "individual", "is_entity": False, "confidence": "medium"}

    return {"owner_type": "individual", "is_entity": False, "confidence": "medium"}


# ── Absentee detection ────────────────────────────────────────────────────────

def detect_absentee(
    property_address: str | None,
    mailing_address: str | None,
) -> dict[str, Any]:
    """Compare property and mailing addresses to detect absentee ownership.

    An owner is absentee when their mailing address differs from the property.
    This is a key signal: absentee owners are more motivated to sell / settle liens.

    Args:
        property_address: Full property street address.
        mailing_address: Owner's mailing address from assessor records.

    Returns:
        Dict with ``is_absentee`` (bool) and ``match_confidence`` keys.
    """
    if not property_address or not mailing_address:
        return {"is_absentee": None, "match_confidence": "unknown"}

    def _normalise(addr: str) -> str:
        """Strip punctuation and lowercase for fuzzy comparison."""
        return re.sub(r"[^a-z0-9\s]", "", addr.lower()).split()

    prop_tokens = set(_normalise(property_address))
    mail_tokens = set(_normalise(mailing_address))

    # Remove generic tokens that appear in both addresses
    stopwords = {"st", "ave", "blvd", "rd", "dr", "ln", "ct", "way", "fl", "ca", "tx", "ny"}
    prop_tokens -= stopwords
    mail_tokens -= stopwords

    if not prop_tokens or not mail_tokens:
        return {"is_absentee": None, "match_confidence": "unknown"}

    overlap = prop_tokens & mail_tokens
    similarity = len(overlap) / max(len(prop_tokens), len(mail_tokens))

    if similarity >= 0.75:
        return {"is_absentee": False, "match_confidence": "high"}
    if similarity >= 0.40:
        return {"is_absentee": True, "match_confidence": "medium"}
    return {"is_absentee": True, "match_confidence": "high"}


# ── Mailing address parser ─────────────────────────────────────────────────────

# Common US state abbreviations (2-letter)
_US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN",
    "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
    "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
    "WV", "WI", "WY",
}


def parse_mailing_address(raw_address: str) -> dict[str, Any]:
    """Extract city, state, and ZIP from a raw mailing address string.

    Handles formats like:
    - "123 Main St, Orlando, FL 32801"
    - "PO BOX 5 MIAMI FL 33101"
    - "123 MAIN ST ORLANDO FL 32801-1234"

    Args:
        raw_address: Raw mailing address from assessor records.

    Returns:
        Dict with ``street``, ``city``, ``state``, ``zip``, ``full`` keys.
    """
    if not raw_address or not raw_address.strip():
        return {"street": None, "city": None, "state": None, "zip": None, "full": ""}

    addr = raw_address.strip()
    result: dict[str, Any] = {"full": addr, "street": None, "city": None, "state": None, "zip": None}

    # Extract ZIP (5 or 5+4)
    zip_match = re.search(r"\b(\d{5})(?:-\d{4})?\b", addr)
    if zip_match:
        result["zip"] = zip_match.group(1)

    # Extract state abbreviation (2 uppercase letters before ZIP or at end)
    state_match = re.search(
        r"\b([A-Z]{2})\s+(?:\d{5}|\d{5}-\d{4})\b",
        addr.upper(),
    )
    if state_match and state_match.group(1) in _US_STATES:
        result["state"] = state_match.group(1)

    # Split on comma to find city
    parts = addr.split(",")
    if len(parts) >= 2:
        result["street"] = parts[0].strip()
        # City is between first comma and state/ZIP portion
        city_part = parts[1].strip()
        # Remove state and ZIP from city portion
        city_clean = re.sub(r"\b[A-Z]{2}\b\s*\d{0,9}", "", city_part.upper()).strip()
        result["city"] = city_clean if city_clean else None
    else:
        # No comma — try to split by known state abbreviation
        if result.get("state"):
            state_idx = addr.upper().rfind(result["state"])
            if state_idx > 0:
                before_state = addr[:state_idx].strip().rstrip(",").strip()
                # Last word-group before state is usually city
                tokens = before_state.split()
                if tokens:
                    result["city"] = tokens[-1].title()
                    result["street"] = " ".join(tokens[:-1])

    return result


# ── Deed type classifier ──────────────────────────────────────────────────────

_DEED_TYPE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"WARRANTY|WD\b|W\.D\.", re.IGNORECASE), "warranty"),
    (re.compile(r"QUITCLAIM|QUIT CLAIM|QC\b|Q\.C\.", re.IGNORECASE), "quitclaim"),
    (re.compile(r"TRUST DEED|DEED OF TRUST|DOT\b", re.IGNORECASE), "trust_deed"),
    (re.compile(r"GRANT DEED|GRANT\b", re.IGNORECASE), "grant"),
    (re.compile(r"SPECIAL WARRANTY|SWD\b", re.IGNORECASE), "special_warranty"),
    (re.compile(r"TAX DEED|TD\b", re.IGNORECASE), "tax_deed"),
    (re.compile(r"SHERIFF|FORECLOSURE|BANK.*DEED", re.IGNORECASE), "foreclosure"),
]


def classify_deed_type(deed_description: str | None) -> str | None:
    """Classify a deed type from a raw description string.

    Args:
        deed_description: Raw instrument/deed description text.

    Returns:
        Canonical deed type string or ``None`` if not recognised.
    """
    if not deed_description:
        return None
    for pattern, deed_type in _DEED_TYPE_PATTERNS:
        if pattern.search(deed_description):
            return deed_type
    return None
