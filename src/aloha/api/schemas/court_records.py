"""Pydantic schemas for court records and lien API responses."""

from __future__ import annotations

from pydantic import BaseModel, Field

# ── Cases ─────────────────────────────────────────────────────────────────────


class PartyOut(BaseModel):
    name: str | None = None
    role: str | None = None


class CaseOut(BaseModel):
    case_id: str | None = None
    case_title: str | None = None
    court: str | None = None
    case_type: str | None = None
    filing_date: str | None = None
    status: str | None = None
    parties: list[PartyOut] = Field(default_factory=list)
    docket_url: str | None = None


class CaseDetailResponse(CaseOut):
    error: str | None = None


class CaseSearchResponse(BaseModel):
    cases: list[CaseOut] = Field(default_factory=list)
    error: str | None = None


# ── Liens ─────────────────────────────────────────────────────────────────────


class LienOut(BaseModel):
    filing_number: str | None = None
    debtor: str | None = None
    creditor: str | None = None
    amount: float | None = None
    filing_date: str | None = None
    lien_type: str | None = None
    state: str | None = None


class LienSearchResponse(BaseModel):
    liens: list[LienOut] = Field(default_factory=list)
    error: str | None = None
