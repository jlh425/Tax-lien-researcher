"""Tool implementations for the Outreach Agent.

Pure functions for channel selection, message personalisation, and
outreach scheduling logic. Actual sending is done via MCP server calls
in agent.py.
"""

from __future__ import annotations

from typing import Any

import structlog

log = structlog.get_logger().bind(agent="outreach")


def select_channels(
    *,
    best_phone: str | None,
    best_email: str | None,
    owner_type: str | None = None,
    reachability_score: int = 0,
) -> list[str]:
    """Choose which outreach channels to use, ordered by preference.

    Returns a list of channels: ``["email", "sms", "phone_call"]``.
    """
    channels: list[str] = []

    # Email is always preferred when available
    if best_email:
        channels.append("email")

    # SMS for mobile phones
    if best_phone:
        channels.append("sms")

    # Phone call as a fallback or for high-value targets
    if best_phone and reachability_score >= 5:
        channels.append("phone_call")

    return channels


def build_template_variables(
    *,
    owner_name: str | None,
    property_address: str | None,
    county: str | None,
    state: str | None,
    tax_amount: float | None = None,
    sale_date: str | None = None,
    instrument_type: str | None = None,
) -> dict[str, str]:
    """Build the Jinja2 variable dict for outreach templates.

    Missing values are replaced with sensible defaults so templates
    always render without errors.
    """
    first_name = _extract_first_name(owner_name)

    return {
        "owner_name": owner_name or "Property Owner",
        "first_name": first_name,
        "property_address": property_address or "your property",
        "county": (county or "").title(),
        "state": (state or "").upper(),
        "tax_amount": f"${tax_amount:,.2f}" if tax_amount else "the outstanding amount",
        "sale_date": sale_date or "the upcoming sale date",
        "instrument_type": instrument_type or "tax lien",
    }


def _extract_first_name(full_name: str | None) -> str:
    """Extract first name from an owner name string.

    Handles formats: "SMITH, JOHN", "John Smith", "JOHN A SMITH".
    Falls back to "there" for templates like "Hi {first_name}".
    """
    if not full_name:
        return "there"

    name = full_name.strip()

    # Handle "LAST, FIRST" format
    if "," in name:
        parts = name.split(",", 1)
        if len(parts) > 1:
            first = parts[1].strip().split()[0] if parts[1].strip() else ""
            if first:
                return first.title()

    # Handle "FIRST LAST" or "FIRST MIDDLE LAST" format
    parts = name.split()
    if parts:
        return parts[0].title()

    return "there"


def choose_template(
    *,
    channel: str,
    instrument_type: str | None = None,
    attempt_number: int = 1,
) -> str:
    """Select the appropriate template name for the outreach attempt.

    Returns a template name like ``"email_lien_initial"`` that maps to
    an ``OutreachTemplate.template_name`` in the DB.
    """
    instrument = instrument_type or "lien"
    instrument = instrument.replace("lien_certificate", "lien").replace("tax_deed", "deed")

    suffix = "initial" if attempt_number <= 1 else f"followup_{min(attempt_number, 3)}"

    return f"{channel}_{instrument}_{suffix}"


def should_skip_outreach(
    *,
    owner_type: str | None,
    best_phone: str | None,
    best_email: str | None,
) -> dict[str, Any]:
    """Determine if outreach should be skipped for this owner.

    Returns ``{"skip": True/False, "reason": "..."}``
    """
    if owner_type == "government":
        return {"skip": True, "reason": "government-owned property"}

    if not best_phone and not best_email:
        return {"skip": True, "reason": "no contact info available"}

    return {"skip": False, "reason": None}


def format_outreach_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarise the results of outreach attempts across channels.

    Args:
        results: List of per-channel result dicts from agent.run().

    Returns:
        Summary with counts by status.
    """
    scheduled = [r for r in results if r.get("status") == "scheduled"]
    skipped = [r for r in results if r.get("status") == "skipped"]
    failed = [r for r in results if r.get("status") == "failed"]

    return {
        "total_attempts": len(results),
        "scheduled": len(scheduled),
        "skipped": len(skipped),
        "failed": len(failed),
        "channels_used": [r["channel"] for r in scheduled],
        "skip_reasons": [r.get("reason") for r in skipped if r.get("reason")],
        "errors": [r.get("error") for r in failed if r.get("error")],
    }
