"""Pydantic schemas for UCC filing API responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class UCCFilingOut(BaseModel):
    filing_number: str | None = None
    filing_date: str | None = None
    lapse_date: str | None = None
    filing_type: str | None = None
    debtor_name: str | None = None
    secured_party: str | None = None
    collateral: str | None = None
    state: str | None = None


class UCCSearchResponse(BaseModel):
    filings: list[UCCFilingOut] = Field(default_factory=list)
    error: str | None = None


class UCCDetailResponse(UCCFilingOut):
    error: str | None = None
