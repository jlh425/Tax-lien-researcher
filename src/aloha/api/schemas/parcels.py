"""Pydantic schemas for parcel, lien, owner, and score API responses."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ── Shared config ─────────────────────────────────────────────────────────────

class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Lien ─────────────────────────────────────────────────────────────────────

class TaxLienOut(_Base):
    id: int
    instrument_type: str
    lien_status: str
    tax_year: int | None
    years_delinquent: int | None
    principal_amount: float
    interest_amount: float | None
    penalty_amount: float | None
    total_owed: float | None
    filing_date: date | None
    redemption_deadline: date | None
    certificate_number: str | None
    certificate_interest_rate: float | None
    auction_date: date | None
    auction_platform: str | None
    auction_url: str | None
    opening_bid: float | None
    post_sale_redemption_days: int | None
    title_risk_level: str | None
    source_url: str | None
    retrieved_at: datetime


# ── Owner ─────────────────────────────────────────────────────────────────────

class OwnerOut(_Base):
    id: int
    owner_of_record: str | None
    owner_type: str | None
    mailing_address: str | None
    mailing_city: str | None
    mailing_state: str | None
    mailing_zip: str | None
    is_absentee: bool | None
    deed_type: str | None
    beneficial_owner: str | None
    beneficial_owner_confidence: str | None
    best_phone: str | None
    best_email: str | None
    research_depth: int


# ── Score ─────────────────────────────────────────────────────────────────────

class ScoreOut(_Base):
    id: int
    instrument_type: str
    overall_score: int | None
    score_model_version: str | None
    property_potential: int | None
    risk_score: int | None
    # Lien cert factors
    lien_to_value_ratio: float | None
    certificate_rate: float | None
    redemption_urgency: int | None
    owner_motivation: int | None
    contact_reachability: int | None
    # Deed factors
    arv_estimate: float | None
    opening_bid: float | None
    arv_to_bid_ratio: float | None
    title_clarity: int | None
    condition_risk: int | None
    competition_risk: int | None
    post_sale_redemption_risk: int | None
    # Output
    risk_flags: list[str] | None
    score_rationale: str | None
    scored_at: datetime


# ── Parcel (summary — card list) ──────────────────────────────────────────────

class ParcelSummary(_Base):
    parcel_id: str
    state: str
    county: str
    address: str | None
    property_type: str | None
    zoning: str | None
    acreage: float | None
    assessed_total: int | None
    research_status: str
    data_freshness: str
    latitude: float | None
    longitude: float | None
    # Denormalised from latest lien
    instrument_type: str | None = None
    lien_status: str | None = None
    total_owed: float | None = None
    redemption_deadline: date | None = None
    auction_date: date | None = None
    # Denormalised from latest score
    overall_score: int | None = None
    risk_flags: list[str] | None = None


# ── Parcel (detail — full pane) ───────────────────────────────────────────────

class ParcelDetail(_Base):
    parcel_id: str
    user_id: UUID | None
    state: str
    county: str
    address: str | None
    address_normalized: str | None
    legal_description: str | None
    acreage: float | None
    land_use_code: str | None
    property_type: str | None
    zoning: str | None
    zoning_notes: str | None
    assessed_land_val: int | None
    assessed_impr_val: int | None
    assessed_total: int | None
    market_value_est: int | None
    last_sale_date: date | None
    last_sale_price: int | None
    year_built: int | None
    latitude: float | None
    longitude: float | None
    research_status: str
    data_freshness: str
    last_crawled_at: datetime | None
    created_at: datetime
    updated_at: datetime
    # Nested
    tax_liens: list[TaxLienOut] = Field(default_factory=list)
    owners: list[OwnerOut] = Field(default_factory=list)
    scores: list[ScoreOut] = Field(default_factory=list)


# ── Search / Scan request ─────────────────────────────────────────────────────

class ScanRequest(BaseModel):
    """Request body for POST /run — trigger a new discovery scan."""
    state: str = Field(..., min_length=2, max_length=2, description="Two-letter state code")
    county: str = Field(..., min_length=1, description="County name")
    instrument_filter: str | None = Field(
        None,
        description="Filter by 'lien_certificate' or 'tax_deed'",
    )
    max_records: int = Field(5000, ge=1, le=50000)


class ScanResponse(BaseModel):
    """Response from a scan trigger."""
    status: str
    state: str
    county: str
    records_found: int = 0
    enqueued: int = 0
    message: str = ""


# ── Search request ────────────────────────────────────────────────────────────

class ParcelSearchParams(BaseModel):
    """Query parameters for GET /parcels (search/filter)."""
    state: str | None = None
    county: str | None = None
    instrument_type: str | None = None     # lien_certificate | tax_deed
    status: str | None = None              # research pipeline status
    min_score: int | None = Field(None, ge=0, le=100)
    max_score: int | None = Field(None, ge=0, le=100)
    is_absentee: bool | None = None
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)


# ── Queue status ──────────────────────────────────────────────────────────────

class QueueStatusOut(BaseModel):
    """Queue depth snapshot."""
    pending: int
    processing: int
    failed: int
    complete: int
    agents: dict[str, int] = Field(default_factory=dict)


# ── Auth ──────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=8)
    name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    tier: str
