"""Scoring models for lien certificates and tax deeds.

Each model is a pure function: takes parcel/lien/owner dicts and returns a
ScoringResult dataclass.  No DB access or LLM calls — deterministic math.

Lien Certificate Score (0-100):
  - Lien-to-Value Ratio        25 pts  (lower LTV = lower risk for investor)
  - Certificate Interest Rate  20 pts  (higher rate = better return)
  - Redemption Urgency         20 pts  (days to deadline)
  - Owner Motivation           20 pts  (absentee + entity + delinquency years)
  - Contact Reachability        15 pts  (we have address/phone/email)

Tax Deed Score (0-100):
  - ARV-to-Bid Ratio           30 pts  (higher spread = better deal)
  - Title Clarity              25 pts  (clear > minor > significant > clouded)
  - Post-Sale Redemption Risk  20 pts  (shorter = better for investor)
  - Condition Risk             15 pts  (land use / year built proxy)
  - Competition Risk           10 pts  (platform + opening bid relative to ARV)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(slots=True)
class ScoringResult:
    """Output of a scoring model run."""

    instrument_type: str               # lien_certificate | tax_deed
    overall_score: int                 # 0–100
    score_model_version: str

    # Shared
    property_potential: int = 0        # 0–10
    risk_score: int = 0                # 0–10 (lower = less risky)

    # Lien cert factors
    lien_to_value_ratio: float | None = None
    certificate_rate: float | None = None
    years_delinquent: int | None = None
    owner_motivation: int = 0          # 0–10
    contact_reachability: int = 0      # 0–10
    redemption_urgency: int = 0        # 0–10

    # Deed factors
    arv_estimate: float | None = None
    opening_bid: float | None = None
    arv_to_bid_ratio: float | None = None
    title_clarity: int = 0             # 0–10
    condition_risk: int = 0            # 0–10
    competition_risk: int = 0          # 0–10
    post_sale_redemption_risk: int = 0 # 0–10

    # Flags
    risk_flags: list[str] = field(default_factory=list)
    flags_detail: dict[str, Any] = field(default_factory=dict)
    score_rationale: str = ""


# ── Lien Certificate Model ────────────────────────────────────────────────────

def score_lien_certificate(
    parcel: dict[str, Any],
    lien: dict[str, Any],
    owner: dict[str, Any],
    state_cert_rate_cap: float | None = None,
    entity_data: dict[str, Any] | None = None,
) -> ScoringResult:
    """Score a tax lien certificate opportunity.

    Args:
        parcel: Canonical Parcel dict (assessed_total, address, etc.)
        lien: Canonical TaxLien dict (principal_amount, certificate_interest_rate,
              redemption_deadline, years_delinquent, etc.)
        owner: Canonical Owner dict (is_absentee, owner_type, best_phone, etc.)
        state_cert_rate_cap: Maximum certificate rate for the state (e.g. 0.18 = 18%).
        entity_data: Optional Entity dict with financial health fields
            (ucc_filings, federal_tax_liens, state_tax_liens, bankruptcy_history,
            litigation_summary).

    Returns:
        ScoringResult with all lien certificate fields populated.
    """
    flags: list[str] = []
    flags_detail: dict[str, Any] = {}
    rationale_parts: list[str] = []

    # ── 1. Lien-to-Value Ratio (25 pts) ──────────────────────────────────
    assessed_total = parcel.get("assessed_total") or 0
    principal = float(lien.get("principal_amount") or 0)
    total_owed = float(lien.get("total_owed") or principal)

    ltv: float | None = None
    ltv_score = 0
    if assessed_total and assessed_total > 0:
        ltv = total_owed / assessed_total
        if ltv <= 0.02:          # <2% = tiny lien relative to value → very safe
            ltv_score = 25
        elif ltv <= 0.05:
            ltv_score = 22
        elif ltv <= 0.10:
            ltv_score = 18
        elif ltv <= 0.20:
            ltv_score = 12
        elif ltv <= 0.40:
            ltv_score = 6
        else:
            ltv_score = 2
            flags.append("high_lien_to_value")
        rationale_parts.append(f"LTV={ltv:.1%} → {ltv_score}/25pts")
    else:
        ltv_score = 10  # neutral when no assessed value
        flags.append("assessed_value_unknown")
        rationale_parts.append("LTV unknown (no assessed value) → 10/25pts")

    # ── 2. Certificate Rate (20 pts) ─────────────────────────────────────
    cert_rate = lien.get("certificate_interest_rate")
    rate_score = 0
    if cert_rate is not None:
        # Higher rate = better return; normalise against state cap
        cap = state_cert_rate_cap or 0.18
        normalised = min(cert_rate / cap, 1.0)
        rate_score = round(normalised * 20)
        rationale_parts.append(f"rate={cert_rate:.1%} → {rate_score}/20pts")
    else:
        rate_score = 10
        rationale_parts.append("cert rate unknown → 10/20pts")

    # ── 3. Redemption Urgency (20 pts) ────────────────────────────────────
    redemption_urgency = 5
    deadline = lien.get("redemption_deadline")
    if deadline:
        if isinstance(deadline, str):
            try:
                deadline = date.fromisoformat(deadline[:10])
            except ValueError:
                deadline = None
    if isinstance(deadline, date):
        days_left = (deadline - date.today()).days
        flags_detail["days_to_redemption"] = days_left
        if days_left < 0:
            redemption_urgency = 10
            flags.append("redemption_expired")
            rationale_parts.append("deadline expired → 20/20pts")
        elif days_left <= 30:
            redemption_urgency = 10
            flags.append("redemption_urgent")
            rationale_parts.append(f"deadline in {days_left}d → 20/20pts")
        elif days_left <= 90:
            redemption_urgency = 8
            rationale_parts.append(f"deadline in {days_left}d → 16/20pts")
        elif days_left <= 180:
            redemption_urgency = 5
            rationale_parts.append(f"deadline in {days_left}d → 10/20pts")
        else:
            redemption_urgency = 2
            rationale_parts.append(f"deadline in {days_left}d → 4/20pts")
    urgency_pts = round(redemption_urgency * 2)  # scale 0-10 → 0-20

    # ── 4. Owner Motivation (20 pts) ──────────────────────────────────────
    motivation = 0
    if owner.get("is_absentee"):
        motivation += 4
        flags_detail["absentee"] = True
    owner_type = owner.get("owner_type", "unknown")
    if owner_type in ("llc", "trust", "corporation", "partnership"):
        motivation += 2   # entities often want to sell vs. fight a lien
    years_delinquent = lien.get("years_delinquent") or 0
    if isinstance(years_delinquent, (int, float)):
        motivation += min(int(years_delinquent), 4)  # cap at 4 pts

    # ── Financial health signals from Entity ─────────────────────────────
    if entity_data:
        _apply_financial_health(
            entity_data, motivation, flags, flags_detail, rationale_parts,
        )
        motivation = flags_detail.get("_motivation_after_entity", motivation)
        # Clean up internal key
        flags_detail.pop("_motivation_after_entity", None)

    motivation = min(motivation, 10)
    motivation_pts = round(motivation * 2)
    rationale_parts.append(f"motivation={motivation}/10 → {motivation_pts}/20pts")

    # ── 5. Contact Reachability (15 pts) ──────────────────────────────────
    reachability = 0
    if owner.get("mailing_address"):
        reachability += 5
    if owner.get("best_phone"):
        reachability += 5
    if owner.get("best_email"):
        reachability += 5
    reachability = min(reachability, 10)
    reachability_pts = round(reachability * 1.5)  # scale 0-10 → 0-15
    if reachability == 0:
        flags.append("no_contact_info")

    # ── Composite score ───────────────────────────────────────────────────
    raw = ltv_score + rate_score + urgency_pts + motivation_pts + reachability_pts
    overall = min(max(raw, 0), 100)

    # ── Risk score (0-10, lower = less risky) ─────────────────────────────
    risk = 0
    if "high_lien_to_value" in flags:
        risk += 4
    if "assessed_value_unknown" in flags:
        risk += 2
    if "no_contact_info" in flags:
        risk += 2
    if owner_type == "government":
        risk += 3
        flags.append("government_owned")
    risk = min(risk, 10)

    # Property potential (0-10)
    property_type = parcel.get("property_type", "unknown")
    potential = {"residential": 8, "commercial": 7, "land": 5, "industrial": 6, "agricultural": 4}.get(
        property_type, 5
    )

    return ScoringResult(
        instrument_type="lien_certificate",
        overall_score=overall,
        score_model_version="lien_v1",
        property_potential=potential,
        risk_score=risk,
        lien_to_value_ratio=round(ltv, 4) if ltv is not None else None,
        certificate_rate=cert_rate,
        years_delinquent=int(years_delinquent) if years_delinquent else None,
        owner_motivation=motivation,
        contact_reachability=reachability,
        redemption_urgency=redemption_urgency,
        risk_flags=flags,
        flags_detail=flags_detail,
        score_rationale=" | ".join(rationale_parts),
    )


# ── Tax Deed Model ────────────────────────────────────────────────────────────

def score_tax_deed(
    parcel: dict[str, Any],
    lien: dict[str, Any],
    owner: dict[str, Any],
    post_sale_redemption_days: int = 0,
    entity_data: dict[str, Any] | None = None,
) -> ScoringResult:
    """Score a tax deed auction opportunity.

    Args:
        parcel: Canonical Parcel dict.
        lien: Canonical TaxLien dict (opening_bid, auction_date, title_risk_level).
        owner: Canonical Owner dict.
        post_sale_redemption_days: Days owner can redeem after sale (from state registry).
        entity_data: Optional Entity dict with financial health fields
            (ucc_filings, federal_tax_liens, state_tax_liens, bankruptcy_history,
            litigation_summary).

    Returns:
        ScoringResult with all tax deed fields populated.
    """
    flags: list[str] = []
    flags_detail: dict[str, Any] = {}
    rationale_parts: list[str] = []

    # ── 1. ARV-to-Bid Ratio (30 pts) ─────────────────────────────────────
    assessed_total = parcel.get("assessed_total") or 0
    market_value = parcel.get("market_value_est") or assessed_total
    # Rough ARV proxy: market value or 1.2x assessed (Florida DOR ratio heuristic)
    arv = float(market_value) if market_value else None
    if arv and arv < assessed_total * 0.5:
        arv = float(assessed_total) * 1.1  # floor: don't let bad market data tank score

    opening_bid = float(lien.get("opening_bid") or lien.get("total_owed") or 0)

    arv_ratio: float | None = None
    ratio_score = 0
    if arv and opening_bid and opening_bid > 0:
        arv_ratio = arv / opening_bid
        flags_detail["arv_to_bid"] = round(arv_ratio, 2)
        if arv_ratio >= 3.0:
            ratio_score = 30
        elif arv_ratio >= 2.0:
            ratio_score = 24
        elif arv_ratio >= 1.5:
            ratio_score = 18
        elif arv_ratio >= 1.2:
            ratio_score = 10
        elif arv_ratio >= 1.0:
            ratio_score = 4
            flags.append("low_margin")
        else:
            ratio_score = 0
            flags.append("bid_exceeds_arv")
        rationale_parts.append(f"ARV/bid={arv_ratio:.1f}x → {ratio_score}/30pts")
    else:
        ratio_score = 12  # neutral
        flags.append("arv_unknown")
        rationale_parts.append("ARV/bid unknown → 12/30pts")

    # ── 2. Title Clarity (25 pts) ─────────────────────────────────────────
    title_risk = lien.get("title_risk_level") or "unknown"
    title_map = {"clear": 10, "minor": 7, "significant": 3, "clouded": 0, "unknown": 5}
    title_val = title_map.get(str(title_risk).lower(), 5)
    title_pts = round(title_val * 2.5)
    if title_risk in ("significant", "clouded"):
        flags.append(f"title_{title_risk}")
    rationale_parts.append(f"title={title_risk} → {title_pts}/25pts")

    # ── 3. Post-Sale Redemption Risk (20 pts) ─────────────────────────────
    # Shorter redemption period = better for investor; 0 days = best
    if post_sale_redemption_days == 0:
        redemption_val = 10
        redemption_pts = 20
    elif post_sale_redemption_days <= 180:
        redemption_val = 7
        redemption_pts = 14
    elif post_sale_redemption_days <= 365:
        redemption_val = 5
        redemption_pts = 10
        flags.append("long_redemption_period")
    else:
        redemption_val = 2
        redemption_pts = 4
        flags.append("very_long_redemption_period")
    flags_detail["post_sale_redemption_days"] = post_sale_redemption_days
    rationale_parts.append(f"redemption={post_sale_redemption_days}d → {redemption_pts}/20pts")

    # ── 4. Condition Risk (15 pts) ────────────────────────────────────────
    # Proxy: year built (older = potentially worse condition)
    year_built = parcel.get("year_built")
    property_type = parcel.get("property_type", "unknown")
    if property_type == "land":
        condition_val = 8  # land doesn't deteriorate structurally
        condition_pts = 12
    elif year_built:
        age = 2025 - int(year_built)
        if age < 10:
            condition_val = 9
            condition_pts = 14
        elif age < 25:
            condition_val = 7
            condition_pts = 11
        elif age < 50:
            condition_val = 5
            condition_pts = 8
        elif age < 75:
            condition_val = 3
            condition_pts = 5
            flags.append("older_structure")
        else:
            condition_val = 1
            condition_pts = 2
            flags.append("very_old_structure")
    else:
        condition_val = 5
        condition_pts = 8  # neutral
    rationale_parts.append(f"condition≈{condition_val}/10 → {condition_pts}/15pts")

    # ── 5. Competition Risk (10 pts) ──────────────────────────────────────
    auction_platform = lien.get("auction_platform") or ""
    # Online platforms = more competition; courthouse steps = less
    online_platforms = {"bid4assets", "realauction", "govease", "sri", "lienhub", "lgbs"}
    if any(p in str(auction_platform).lower() for p in online_platforms):
        competition_val = 4   # higher online competition
        competition_pts = 4
        flags.append("online_auction_competition")
    elif "courthouse" in str(auction_platform).lower():
        competition_val = 7
        competition_pts = 7
    else:
        competition_val = 6
        competition_pts = 6
    rationale_parts.append(f"competition≈{competition_val}/10 → {competition_pts}/10pts")

    # ── 6. Financial Health (owner motivation + risk flags) ────────────────
    motivation = 0
    if entity_data:
        _apply_financial_health(
            entity_data, motivation, flags, flags_detail, rationale_parts,
        )
        motivation = flags_detail.pop("_motivation_after_entity", motivation)
    motivation = min(motivation, 10)

    # ── Composite ─────────────────────────────────────────────────────────
    raw = ratio_score + title_pts + redemption_pts + condition_pts + competition_pts
    overall = min(max(raw, 0), 100)

    # Risk score
    risk = 0
    if "bid_exceeds_arv" in flags:
        risk += 5
    if "title_clouded" in flags:
        risk += 4
    elif "title_significant" in flags:
        risk += 2
    if "very_long_redemption_period" in flags:
        risk += 2
    if "very_old_structure" in flags:
        risk += 2
    risk = min(risk, 10)

    potential_map = {
        "residential": 8, "commercial": 7, "land": 6,
        "industrial": 5, "agricultural": 4,
    }
    potential = potential_map.get(property_type, 5)

    return ScoringResult(
        instrument_type="tax_deed",
        overall_score=overall,
        score_model_version="deed_v1",
        property_potential=potential,
        risk_score=risk,
        arv_estimate=round(arv, 2) if arv else None,
        opening_bid=opening_bid if opening_bid else None,
        arv_to_bid_ratio=round(arv_ratio, 2) if arv_ratio else None,
        title_clarity=title_val,
        condition_risk=condition_val,
        competition_risk=competition_val,
        post_sale_redemption_risk=redemption_val,
        owner_motivation=motivation,
        risk_flags=flags,
        flags_detail=flags_detail,
        score_rationale=" | ".join(rationale_parts),
    )


# ── Shared Financial Health Helper ────────────────────────────────────────────

def _apply_financial_health(
    entity_data: dict[str, Any],
    motivation: int,
    flags: list[str],
    flags_detail: dict[str, Any],
    rationale_parts: list[str],
) -> None:
    """Apply financial health signals from entity data to scoring components.

    Mutates *flags*, *flags_detail*, and *rationale_parts* in place.
    Stores the updated motivation value in ``flags_detail["_motivation_after_entity"]``
    so the caller can retrieve it (avoids returning a tuple).
    """
    health_notes: list[str] = []

    # UCC filings → financial stress signal
    ucc = entity_data.get("ucc_filings")
    if ucc and isinstance(ucc, list) and len(ucc) > 0:
        motivation += 2
        flags.append("entity_ucc_filings")
        flags_detail["entity_ucc_filing_count"] = len(ucc)
        health_notes.append(f"{len(ucc)} UCC filing(s)")

    # Federal / state tax liens → very motivated seller
    fed_liens = entity_data.get("federal_tax_liens") or []
    state_liens = entity_data.get("state_tax_liens") or []
    all_tax_liens = (
        (fed_liens if isinstance(fed_liens, list) else [])
        + (state_liens if isinstance(state_liens, list) else [])
    )
    if all_tax_liens:
        motivation += 3
        total_amount = sum(
            float(tl.get("amount") or 0) for tl in all_tax_liens
        )
        flags.append("entity_tax_liens")
        flags_detail["entity_tax_lien_total"] = round(total_amount, 2)
        health_notes.append(
            f"{len(all_tax_liens)} tax lien(s) totalling ${total_amount:,.0f}"
        )

    # Bankruptcy history → distressed
    bankruptcy = entity_data.get("bankruptcy_history")
    if bankruptcy and isinstance(bankruptcy, list) and len(bankruptcy) > 0:
        motivation += 2
        flags.append("entity_bankruptcy")
        health_notes.append(f"{len(bankruptcy)} bankruptcy case(s)")

    # Litigation summary → active litigation flag
    litigation = entity_data.get("litigation_summary") or ""
    if isinstance(litigation, str) and litigation.strip():
        flags.append("entity_active_litigation")
        health_notes.append("active litigation noted")

    if health_notes:
        rationale_parts.append(
            "Financial health: " + "; ".join(health_notes)
        )

    # Store updated motivation for caller
    flags_detail["_motivation_after_entity"] = motivation
