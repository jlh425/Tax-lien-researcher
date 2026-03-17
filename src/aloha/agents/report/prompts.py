"""Prompts for the Report Agent LLM narrative generation."""

from __future__ import annotations

from typing import Any

REPORT_SYSTEM_PROMPT = """\
You are an expert real estate investment analyst specialising in tax lien certificates
and tax deed auctions.

Write a concise, professional investment memo (3-4 paragraphs) for the given property.
Cover: property overview, ownership situation, lien/deed details, score rationale,
and a clear recommended action (buy / research further / monitor / pass).

Use plain English. Be factual — only report what the data shows. Do not invent
contact info, valuations, or legal opinions. Flag anything that warrants legal review.
"""


def build_report_task(data: dict[str, Any], report: dict[str, Any]) -> str:
    """Build the LLM task prompt from compiled report data."""
    parcel = data.get("parcel", {})
    owner = data.get("owners", [{}])[0] if data.get("owners") else {}
    lien = data.get("liens", [{}])[0] if data.get("liens") else {}
    score_data = data.get("score", {})

    return f"""\
Write an investment memo for the following property:

PROPERTY
- Parcel ID: {parcel.get('parcel_id', 'N/A')}
- Address: {parcel.get('address', 'N/A')}
- Type: {parcel.get('property_type', 'N/A')}
- Zoning: {parcel.get('zoning', 'N/A')}
- Acreage: {parcel.get('acreage', 'N/A')}
- Year built: {parcel.get('year_built', 'N/A')}
- Assessed value: ${parcel.get('assessed_total', 0):,}
- Legal: {parcel.get('legal_description', 'N/A')}

LIEN / DEED
- Instrument: {lien.get('instrument_type', 'N/A')}
- Status: {lien.get('lien_status', 'N/A')}
- Tax year: {lien.get('tax_year', 'N/A')}
- Total owed: ${lien.get('total_owed') or lien.get('principal_amount', 0):,.2f}
- Cert rate: {lien.get('certificate_interest_rate', 'N/A')}
- Redemption deadline: {lien.get('redemption_deadline', 'N/A')}
- Auction date: {lien.get('auction_date', 'N/A')} via {lien.get('auction_platform', 'N/A')}
- Opening bid: ${lien.get('opening_bid', 'N/A')}

OWNER
- Owner of record: {owner.get('owner_of_record', 'N/A')}
- Type: {owner.get('owner_type', 'N/A')}
- Absentee: {owner.get('is_absentee', 'N/A')}
- Beneficial owner: {owner.get('beneficial_owner', 'N/A')} ({owner.get('beneficial_owner_confidence', 'N/A')} confidence)
- Mailing: {owner.get('mailing_address', 'N/A')}

SCORE
- Overall: {score_data.get('overall_score', 'N/A')}/100 ({score_data.get('score_model_version', 'N/A')})
- Risk flags: {', '.join(score_data.get('risk_flags') or []) or 'None'}
- Rationale: {score_data.get('score_rationale', 'N/A')}

Write the memo. End with a one-line recommended action:
ACTION: [high_priority_buy | research_further | monitor | pass]
"""
