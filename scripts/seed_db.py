#!/usr/bin/env python3
"""Seed the database with reference data.

Seeds outreach templates used by the outreach agent for initial contact,
follow-ups, and phone scripts across both lien-certificate and tax-deed
instrument types.

Usage:
    python scripts/seed_db.py

Requires a running PostgreSQL instance configured via DATABASE_URL.
"""

import asyncio
from datetime import datetime, timezone

import structlog

log = structlog.get_logger().bind(script="seed_db")


# ── Outreach template definitions ────────────────────────────────────────────

TEMPLATES = [
    # ── Email templates ──────────────────────────────────────────────────
    {
        "template_name": "initial_contact_lien_email",
        "channel": "email",
        "instrument_type": "lien_certificate",
        "subject": "Important Notice Regarding Tax Lien on Your Property — {{ county }} County",
        "body": (
            "Dear {{ owner_name }},\n\n"
            "I am writing regarding the tax lien certificate on the property located at "
            "{{ address }} (Parcel ID: {{ parcel_id }}) in {{ county }} County, {{ state }}.\n\n"
            "Our records indicate a total of {{ total_owed }} is currently owed in delinquent "
            "taxes for tax year {{ tax_year }}. As the lien certificate holder, I wanted to "
            "reach out to discuss potential resolution options before the redemption deadline.\n\n"
            "I would welcome the opportunity to speak with you about this matter at your "
            "convenience. Please reply to this email or call me at your earliest opportunity.\n\n"
            "Best regards,\n{{ sender_name }}"
        ),
        "variables": [
            "owner_name", "address", "parcel_id", "county", "state",
            "total_owed", "tax_year", "sender_name",
        ],
    },
    {
        "template_name": "initial_contact_deed_email",
        "channel": "email",
        "instrument_type": "tax_deed",
        "subject": "Upcoming Tax Deed Auction — {{ county }} County Property",
        "body": (
            "Dear {{ owner_name }},\n\n"
            "I am contacting you regarding the property at {{ address }} "
            "(Parcel ID: {{ parcel_id }}) in {{ county }} County, {{ state }}.\n\n"
            "This property is scheduled for tax deed auction on {{ auction_date }} with an "
            "opening bid of {{ opening_bid }}. There may still be time to resolve the "
            "outstanding balance of {{ total_owed }} and prevent the sale.\n\n"
            "I would be happy to discuss the situation and explore potential options. "
            "Please feel free to reply to this email or contact me directly.\n\n"
            "Sincerely,\n{{ sender_name }}"
        ),
        "variables": [
            "owner_name", "address", "parcel_id", "county", "state",
            "total_owed", "auction_date", "opening_bid", "sender_name",
        ],
    },
    {
        "template_name": "follow_up_email",
        "channel": "email",
        "instrument_type": None,
        "subject": "Follow-Up: Tax Delinquency on {{ address }}",
        "body": (
            "Dear {{ owner_name }},\n\n"
            "I wanted to follow up on my previous message regarding the property at "
            "{{ address }} (Parcel ID: {{ parcel_id }}) in {{ county }} County.\n\n"
            "If you have any questions or would like to discuss resolution options, "
            "I am available at your convenience.\n\n"
            "Best regards,\n{{ sender_name }}"
        ),
        "variables": [
            "owner_name", "address", "parcel_id", "county", "sender_name",
        ],
    },
    # ── SMS templates ────────────────────────────────────────────────────
    {
        "template_name": "initial_contact_sms",
        "channel": "sms",
        "instrument_type": None,
        "subject": None,
        "body": (
            "Hi {{ owner_name }}, this is {{ sender_name }}. I'm reaching out about "
            "the tax delinquency on your property at {{ address }} in {{ county }} County. "
            "Please reply or call to discuss options. Thank you."
        ),
        "variables": [
            "owner_name", "address", "county", "sender_name",
        ],
    },
    {
        "template_name": "follow_up_sms",
        "channel": "sms",
        "instrument_type": None,
        "subject": None,
        "body": (
            "Hi {{ owner_name }}, following up on the tax matter for {{ address }}. "
            "Happy to help find a resolution. Reply STOP to opt out."
        ),
        "variables": ["owner_name", "address"],
    },
    # ── Phone script templates ───────────────────────────────────────────
    {
        "template_name": "phone_script_lien",
        "channel": "phone_script",
        "instrument_type": "lien_certificate",
        "subject": None,
        "body": (
            "Hello, may I speak with {{ owner_name }}?\n\n"
            "[If yes] My name is {{ sender_name }} and I'm calling about a tax lien "
            "on your property at {{ address }} in {{ county }} County, {{ state }}. "
            "The outstanding balance is {{ total_owed }} for tax year {{ tax_year }}.\n\n"
            "I wanted to reach out to discuss the situation and see if there are any "
            "resolution options that might work for you.\n\n"
            "[If voicemail] Hi {{ owner_name }}, this is {{ sender_name }} calling about "
            "the tax lien on your property in {{ county }} County. Please call me back "
            "at your convenience. Thank you."
        ),
        "variables": [
            "owner_name", "address", "county", "state",
            "total_owed", "tax_year", "sender_name",
        ],
    },
]


async def seed() -> None:
    """Seed reference data into the database."""
    from sqlalchemy import select

    from aloha.db.engine import async_session_factory
    from aloha.db.models.outreach import OutreachTemplate

    now = datetime.now(tz=timezone.utc)
    created = 0
    skipped = 0

    async with async_session_factory() as session:
        for tpl_data in TEMPLATES:
            # Check if template already exists (idempotent)
            result = await session.execute(
                select(OutreachTemplate).where(
                    OutreachTemplate.template_name == tpl_data["template_name"]
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                log.info("template_exists", name=tpl_data["template_name"])
                skipped += 1
                continue

            template = OutreachTemplate(
                template_name=tpl_data["template_name"],
                channel=tpl_data["channel"],
                instrument_type=tpl_data["instrument_type"],
                subject=tpl_data["subject"],
                body=tpl_data["body"],
                variables=tpl_data["variables"],
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            session.add(template)
            created += 1
            log.info("template_created", name=tpl_data["template_name"])

        await session.commit()

    log.info("seed_complete", created=created, skipped=skipped)


if __name__ == "__main__":
    asyncio.run(seed())
