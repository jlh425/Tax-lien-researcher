"""Pydantic schemas for UCC filing API requests and responses."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

# ── Shared constants ──────────────────────────────────────────────────────────

_US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC", "PR", "VI", "GU", "AS", "MP",
}

# Reusable annotated types for Query() parameters in the route layer.
DebtorNameQuery = Annotated[
    str,
    Field(
        min_length=1,
        max_length=200,
        description="Name of the debtor (person or entity)",
    ),
]
StateQuery = Annotated[
    str,
    Field(
        min_length=2,
        max_length=2,
        pattern=r"^[A-Z]{2}$",
        description="Two-letter US state abbreviation (uppercase)",
    ),
]
FilingNumberQuery = Annotated[
    str,
    Field(
        min_length=1,
        max_length=50,
        description="UCC filing number",
    ),
]
FilingTypeQuery = Annotated[
    str | None,
    Field(
        max_length=50,
        description="Filter: initial, amendment, continuation",
    ),
]
ResultLimitQuery = Annotated[
    int,
    Field(
        ge=1,
        le=1000,
        description="Maximum number of results to return",
    ),
]


# ── Response schemas ──────────────────────────────────────────────────────────

class UCCFilingOut(BaseModel):
    filing_number: str | None = Field(default=None, max_length=50)
    filing_date: str | None = Field(default=None, max_length=30)
    lapse_date: str | None = Field(default=None, max_length=30)
    filing_type: str | None = Field(default=None, max_length=50)
    debtor_name: str | None = Field(default=None, max_length=200)
    secured_party: str | None = Field(default=None, max_length=200)
    collateral: str | None = Field(default=None, max_length=5000)
    state: str | None = Field(default=None, min_length=2, max_length=2)


class UCCSearchResponse(BaseModel):
    filings: list[UCCFilingOut] = Field(default_factory=list)
    error: str | None = None


class UCCDetailResponse(UCCFilingOut):
    error: str | None = None
