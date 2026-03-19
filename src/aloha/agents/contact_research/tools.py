"""Tool implementations for the Contact Research Agent.

Pure functions for phone/email normalisation and scoring contact quality.
MCP server calls (PDL, Hunter) are done in agent.py.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

log = structlog.get_logger().bind(agent="contact_research")


def normalise_phone(raw: str | None) -> str | None:
    """Normalise a phone number to E.164 format (+1XXXXXXXXXX).

    Handles formats: (555) 123-4567, 555-123-4567, 5551234567, +15551234567.
    Returns None if the input can't be parsed as a US phone number.
    """
    if not raw:
        return None
    digits = re.sub(r"[^\d]", "", raw)
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return None


def normalise_email(raw: str | None) -> str | None:
    """Normalise an email address: lowercase, strip whitespace.

    Returns None if the input doesn't look like a valid email.
    """
    if not raw:
        return None
    email = raw.strip().lower()
    if re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        return email
    return None


def score_contact_quality(
    *,
    has_phone: bool,
    has_email: bool,
    email_verified: bool = False,
    phone_type: str | None = None,
) -> dict[str, Any]:
    """Score the reachability of a contact based on available info.

    Returns a dict with ``score`` (0-10), ``channels`` list, and ``notes``.
    """
    score = 0
    channels: list[str] = []
    notes: list[str] = []

    if has_email:
        score += 3
        channels.append("email")
        if email_verified:
            score += 2
            notes.append("email verified")
        else:
            notes.append("email unverified")

    if has_phone:
        score += 3
        channels.append("sms")
        channels.append("phone")
        if phone_type == "mobile":
            score += 2
            notes.append("mobile phone")
        elif phone_type == "landline":
            score += 1
            notes.append("landline")

    if not has_phone and not has_email:
        notes.append("no contact info found")

    return {
        "score": min(score, 10),
        "channels": channels,
        "notes": "; ".join(notes) if notes else "no data",
    }


def pick_best_contact(
    enrichment_data: dict[str, Any],
) -> dict[str, Any]:
    """Select the best phone and email from enrichment data.

    Prioritises mobile phones and verified emails.

    Args:
        enrichment_data: Result from PDL person enrichment.

    Returns:
        Dict with ``best_phone``, ``best_email``, ``phone_type`` keys.
    """
    phones = enrichment_data.get("phone_numbers") or []
    emails = enrichment_data.get("emails") or []

    best_phone = None
    phone_type = None
    for phone in phones:
        normalised = normalise_phone(phone if isinstance(phone, str) else phone.get("number"))
        if normalised:
            best_phone = normalised
            phone_type = phone.get("type") if isinstance(phone, dict) else "unknown"
            if phone_type == "mobile":
                break  # prefer mobile

    best_email = None
    for email in emails:
        email_str = email if isinstance(email, str) else email.get("address")
        normalised = normalise_email(email_str)
        if normalised:
            best_email = normalised
            break

    return {
        "best_phone": best_phone,
        "best_email": best_email,
        "phone_type": phone_type,
    }
