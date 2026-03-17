"""State instrument registry — maps every US state to its tax instrument type.

This is the source of truth the Discovery Agent uses to decide which scraper
strategy to apply for a given state/county.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum, auto


class InstrumentType(StrEnum):
    LIEN_CERT = "lien_certificate"
    TAX_DEED = "tax_deed"
    HYBRID = "hybrid"      # Some counties within the state differ


@dataclass(frozen=True, slots=True)
class StateInfo:
    """Instrument metadata for a US state."""

    instrument: InstrumentType
    cert_rate_cap: float | None = None    # max interest rate on lien certs (e.g. 0.18 = 18%)
    post_sale_redemption_days: int = 0    # days owner can redeem AFTER deed sale (0 = none)
    primary_auction_platform: str = ""   # e.g. 'realauction', 'bid4assets', 'govease'
    notes: str = ""


# ── All 50 states ──────────────────────────────────────────────────────────────
# Sources: National Tax Lien Association, NTLA state guides, PRD Section D
STATE_REGISTRY: dict[str, StateInfo] = {
    # ── Lien Certificate States ────────────────────────────────────────────
    "AZ": StateInfo(InstrumentType.LIEN_CERT, cert_rate_cap=0.16, primary_auction_platform="realauction", notes="16% max; county treasurer auctions Feb–Mar"),
    "CO": StateInfo(InstrumentType.LIEN_CERT, cert_rate_cap=0.18, primary_auction_platform="realauction", notes="18% max; county treasurer; sold at premium"),
    "FL": StateInfo(InstrumentType.LIEN_CERT, cert_rate_cap=0.18, primary_auction_platform="lienhub,realauction", notes="Bid-down rate auction; 2yr redemption; June sale"),
    "IA": StateInfo(InstrumentType.LIEN_CERT, cert_rate_cap=0.24, primary_auction_platform="govease,iowataxauction", notes="24% max; June sale; 2yr redemption"),
    "IL": StateInfo(InstrumentType.LIEN_CERT, cert_rate_cap=0.36, primary_auction_platform="sri", notes="Bid-down penalty system; 3yr redemption; county circuits"),
    "IN": StateInfo(InstrumentType.LIEN_CERT, cert_rate_cap=0.15, primary_auction_platform="sri", notes="15% max; annual fall sale"),
    "KY": StateInfo(InstrumentType.LIEN_CERT, cert_rate_cap=0.12, notes="12% fixed; sheriff's sale"),
    "MD": StateInfo(InstrumentType.LIEN_CERT, cert_rate_cap=0.24, notes="6-24% varies by county; annual May–Jun sale"),
    "MS": StateInfo(InstrumentType.LIEN_CERT, cert_rate_cap=0.18, notes="18% fixed; annual Aug sale"),
    "MT": StateInfo(InstrumentType.LIEN_CERT, cert_rate_cap=0.10, notes="10% max; 3yr redemption"),
    "NE": StateInfo(InstrumentType.LIEN_CERT, cert_rate_cap=0.14, notes="14% max; annual Mar sale"),
    "NJ": StateInfo(InstrumentType.LIEN_CERT, cert_rate_cap=0.18, primary_auction_platform="newjerseytaxsale", notes="Municipality-level sales (565 municipalities); 18% max + 6% penalty"),
    "OH": StateInfo(InstrumentType.HYBRID, cert_rate_cap=0.18, primary_auction_platform="sri", notes="Hybrid: lien cert counties + deed counties; check county level"),
    "SC": StateInfo(InstrumentType.LIEN_CERT, cert_rate_cap=0.12, notes="12% fixed; annual Oct–Dec sale"),
    "SD": StateInfo(InstrumentType.LIEN_CERT, cert_rate_cap=0.12, notes="12% fixed; 3yr or 60-day redemption"),
    "WV": StateInfo(InstrumentType.LIEN_CERT, cert_rate_cap=0.12, notes="12% fixed; sheriff's sale"),
    "WY": StateInfo(InstrumentType.LIEN_CERT, cert_rate_cap=0.15, notes="15% fixed; annual Aug sale"),

    # ── Tax Deed States ───────────────────────────────────────────────────
    "AK": StateInfo(InstrumentType.TAX_DEED, notes="Foreclosure action required; sporadic sales"),
    "AR": StateInfo(InstrumentType.TAX_DEED, post_sale_redemption_days=0, notes="State Land Office handles forfeited land"),
    "CA": StateInfo(InstrumentType.TAX_DEED, post_sale_redemption_days=0, notes="5yr delinquency; county auctions; online via county portals"),
    "GA": StateInfo(InstrumentType.TAX_DEED, post_sale_redemption_days=365, primary_auction_platform="bid4assets", notes="Redeemable deed; 1yr redemption; courthouse steps + online"),
    "HI": StateInfo(InstrumentType.TAX_DEED, notes="County-level; relatively rare"),
    "ID": StateInfo(InstrumentType.TAX_DEED, post_sale_redemption_days=0, notes="County commissioners manage sales"),
    "KS": StateInfo(InstrumentType.TAX_DEED, post_sale_redemption_days=0, notes="Court-supervised process"),
    "LA": StateInfo(InstrumentType.HYBRID, notes="Complex: lien cert then deed if not redeemed"),
    "ME": StateInfo(InstrumentType.TAX_DEED, post_sale_redemption_days=0, notes="Municipality acquires deed; occasional surplus sales"),
    "MI": StateInfo(InstrumentType.TAX_DEED, post_sale_redemption_days=0, primary_auction_platform="bid4assets", notes="County Treasurer forfeiture; Wayne Co on Bid4Assets; Jul sale"),
    "MN": StateInfo(InstrumentType.TAX_DEED, post_sale_redemption_days=0, primary_auction_platform="minnbidapi", notes="Tax-forfeited land (not 'tax deed'); MN Dept of Admin sells via minnbidapi"),
    "MO": StateInfo(InstrumentType.HYBRID, notes="Collector deeds (deed-like); check county"),
    "NC": StateInfo(InstrumentType.TAX_DEED, post_sale_redemption_days=0, notes="Foreclosure action; upset bid period"),
    "ND": StateInfo(InstrumentType.TAX_DEED, notes="County holds 3yr before sale"),
    "NH": StateInfo(InstrumentType.TAX_DEED, notes="Municipality acquires; occasional auctions"),
    "NM": StateInfo(InstrumentType.TAX_DEED, notes="State Land Office; annual Aug sale"),
    "NV": StateInfo(InstrumentType.TAX_DEED, post_sale_redemption_days=0, notes="County auctions; competitive for residential"),
    "NY": StateInfo(InstrumentType.HYBRID, notes="In Rem foreclosure; NYC vs. upstate differ"),
    "OK": StateInfo(InstrumentType.TAX_DEED, post_sale_redemption_days=0, notes="County commissioners; annual Oct sale"),
    "OR": StateInfo(InstrumentType.TAX_DEED, post_sale_redemption_days=0, primary_auction_platform="bid4assets", notes="County sheriff's sales; online via Bid4Assets"),
    "PA": StateInfo(InstrumentType.TAX_DEED, post_sale_redemption_days=0, notes="Upset sale + judicial sale process"),
    "RI": StateInfo(InstrumentType.TAX_DEED, notes="Municipality forecloses; town council auctions"),
    "TN": StateInfo(InstrumentType.TAX_DEED, post_sale_redemption_days=365, notes="1yr right of redemption after sale"),
    "TX": StateInfo(InstrumentType.TAX_DEED, post_sale_redemption_days=730, primary_auction_platform="lgbs,bid4assets", notes="Redeemable deed; 2yr homestead/ag, 6mo others; 1st Tue monthly"),
    "UT": StateInfo(InstrumentType.TAX_DEED, post_sale_redemption_days=0, notes="County treasurer; competitive urban counties"),
    "VA": StateInfo(InstrumentType.TAX_DEED, post_sale_redemption_days=0, notes="Circuit court proceedings; land book"),
    "WA": StateInfo(InstrumentType.TAX_DEED, post_sale_redemption_days=0, primary_auction_platform="bid4assets", notes="County treasurer; Pierce/Snohomish on Bid4Assets"),
    "WI": StateInfo(InstrumentType.TAX_DEED, post_sale_redemption_days=0, notes="County Land Division manages forfeited land"),

    # ── Additional states (primarily deed / varied) ────────────────────────
    "AL": StateInfo(InstrumentType.LIEN_CERT, cert_rate_cap=0.12, notes="12% max; state holds cert 3yr then issues deed"),
    "CT": StateInfo(InstrumentType.TAX_DEED, notes="Municipality forecloses"),
    "DC": StateInfo(InstrumentType.LIEN_CERT, cert_rate_cap=0.18, notes="18% max; annual Jul sale"),
    "DE": StateInfo(InstrumentType.TAX_DEED, notes="County sheriff's sale"),
    "VT": StateInfo(InstrumentType.TAX_DEED, notes="Town-level; occasional surplus auctions"),
    "GA": StateInfo(InstrumentType.TAX_DEED, post_sale_redemption_days=365, primary_auction_platform="bid4assets"),
    "PR": StateInfo(InstrumentType.HYBRID, notes="Puerto Rico territory — lien cert system"),
}


def get_state_info(state: str) -> StateInfo | None:
    """Return instrument metadata for a state abbreviation (case-insensitive)."""
    return STATE_REGISTRY.get(state.upper())


def classify_instrument(state: str, county: str | None = None) -> InstrumentType:
    """Return the instrument type for a state, defaulting to HYBRID if unknown."""
    info = get_state_info(state)
    if info is None:
        return InstrumentType.HYBRID
    return info.instrument
