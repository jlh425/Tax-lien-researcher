"""Discovery Agent — finds tax liens and deed auctions for a target county.

Responsibilities:
1. Classify the state's instrument type (lien cert / tax deed / hybrid)
2. Select the appropriate scraper tier (Socrata API → vendor template → adaptive)
3. Iterate discovered records and enqueue each for parcel research
4. Store raw lien/deed records in the DB with source provenance
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

from aloha.agents.base import BaseAgent
from aloha.agents.discovery.state_registry import InstrumentType, classify_instrument, get_state_info
from aloha.db.engine import async_session_factory
from aloha.db.models.crawl_log import CrawlLog
from aloha.db.models.parcel import Parcel
from aloha.db.models.tax_lien import TaxLien
from aloha.db.repositories import ParcelRepository, QueueRepository, TaxLienRepository

log = structlog.get_logger().bind(agent="discovery")


class DiscoveryAgent(BaseAgent):
    """Discovers active tax liens and deed auctions for a county.

    Context keys expected in ``run(context)``:
    - ``state``: two-letter state abbreviation (required)
    - ``county``: county name in lowercase (required)
    - ``instrument_filter``: 'lien_certificate' | 'tax_deed' | None (all)
    - ``user_id``: UUID of the requesting user
    - ``max_records``: cap on records to enqueue per run (default 5000)
    """

    def __init__(self) -> None:
        super().__init__(name="discovery")

    # ── Abstract interface ────────────────────────────────────────────────

    def get_tools(self) -> list[dict[str, Any]]:
        return []   # Discovery uses scrapers directly, not LLM tool calls

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        state: str = context["state"].upper()
        county: str = context["county"].lower()
        user_id: str | None = context.get("user_id")
        instrument_filter: str | None = context.get("instrument_filter")
        max_records: int = context.get("max_records", 5000)

        self.log.info("discovery_started", state=state, county=county)

        state_info = get_state_info(state)
        instrument = classify_instrument(state, county)

        # Respect instrument filter if provided
        if instrument_filter and instrument_filter != instrument.value:
            if instrument != InstrumentType.HYBRID:
                self.log.info(
                    "instrument_mismatch_skipping",
                    requested=instrument_filter,
                    state_instrument=instrument.value,
                )
                return {"status": "skipped", "reason": "instrument_mismatch"}

        self.log.info(
            "instrument_classified",
            state=state,
            county=county,
            instrument=instrument.value,
            platform=state_info.primary_auction_platform if state_info else "",
        )

        # ── Select and run the appropriate scraper ────────────────────────
        raw_records = await self._scrape(state, county, instrument, max_records)

        if not raw_records:
            self.log.warning("no_records_found", state=state, county=county)
            return {"status": "complete", "records_found": 0, "enqueued": 0}

        # ── Persist and enqueue ───────────────────────────────────────────
        enqueued = await self._persist_and_enqueue(
            raw_records,
            state=state,
            county=county,
            instrument=instrument,
            user_id=user_id,
        )

        self.log.info(
            "discovery_complete",
            state=state,
            county=county,
            records_found=len(raw_records),
            enqueued=enqueued,
        )
        return {
            "status": "complete",
            "state": state,
            "county": county,
            "instrument": instrument.value,
            "records_found": len(raw_records),
            "enqueued": enqueued,
        }

    # ── Scraper dispatch ──────────────────────────────────────────────────

    async def _scrape(
        self,
        state: str,
        county: str,
        instrument: InstrumentType,
        max_records: int,
    ) -> list[dict[str, Any]]:
        """Try each scraper tier in order; return first successful result."""
        from aloha.scrapers.registry import get_scraper_entry
        from aloha.scrapers.tier1_apis.socrata import SocrataDiscoveryScraper

        # Tier 1: Check for a registered scraper (may be Socrata or ArcGIS)
        entry = get_scraper_entry(state, county)
        if entry and entry.tier == 1:
            self.log.info("using_tier1_scraper", state=state, county=county)
            scraper = SocrataDiscoveryScraper(state=state, county=county)
            try:
                records = await scraper.discover(max_records=max_records)
                if records:
                    return records
            except Exception as exc:
                self.log.warning("tier1_scraper_failed", error=str(exc))

        # Tier 2: Vendor-template Playwright scraper
        if entry and entry.tier == 2:
            self.log.info("using_tier2_scraper", state=state, county=county)
            try:
                records = await self._tier2_scrape(state, county, max_records)
                if records:
                    return records
            except Exception as exc:
                self.log.warning("tier2_scraper_failed", error=str(exc))

        # Tier 3: AI-adaptive browser agent (always available as fallback)
        self.log.info("using_tier3_adaptive", state=state, county=county)
        return await self._tier3_scrape(state, county, instrument, max_records)

    async def _tier2_scrape(
        self, state: str, county: str, max_records: int
    ) -> list[dict[str, Any]]:
        """Dispatch to the appropriate vendor-template scraper."""
        from aloha.scrapers.registry import get_scraper_entry
        import importlib

        entry = get_scraper_entry(state, county)
        if entry is None:
            return []
        module = importlib.import_module(entry.scraper_class.rsplit(".", 1)[0])
        cls_name = entry.scraper_class.rsplit(".", 1)[1]
        scraper_cls = getattr(module, cls_name)
        scraper = scraper_cls(state=state, county=county)
        return await scraper.discover(max_records=max_records)

    async def _tier3_scrape(
        self,
        state: str,
        county: str,
        instrument: InstrumentType,
        max_records: int,
    ) -> list[dict[str, Any]]:
        """AI-adaptive browser scraper — uses LLM + Playwright to navigate unknown portals.

        Stub: returns empty list until tier3_adaptive is implemented.
        """
        self.log.info(
            "tier3_adaptive_stub",
            state=state,
            county=county,
            note="Tier 3 adaptive scraper not yet implemented",
        )
        return []

    # ── Persistence ───────────────────────────────────────────────────────

    async def _persist_and_enqueue(
        self,
        records: list[dict[str, Any]],
        *,
        state: str,
        county: str,
        instrument: InstrumentType,
        user_id: str | None,
    ) -> int:
        """Upsert parcel + lien records and enqueue each for parcel research."""
        enqueued = 0
        now = datetime.now(tz=timezone.utc)

        async with async_session_factory() as session:
            parcel_repo = ParcelRepository(session)
            lien_repo = TaxLienRepository(session)
            queue_repo = QueueRepository(session)

            for raw in records:
                parcel_id = raw.get("parcel_id") or raw.get("apn")
                if not parcel_id:
                    self.log.warning("record_missing_parcel_id", raw=raw)
                    continue

                # Upsert parcel stub (full details filled in by Parcel Research Agent)
                parcel = Parcel(
                    parcel_id=str(parcel_id),
                    user_id=uuid.UUID(user_id) if user_id else None,
                    county=county,
                    state=state,
                    address=raw.get("address"),
                    research_status="discovered",
                    data_freshness="fresh",
                    content_hash=_hash(raw),
                    last_crawled_at=now,
                )
                await parcel_repo.upsert(parcel)

                # Upsert lien / deed record
                lien = TaxLien(
                    parcel_id=str(parcel_id),
                    instrument_type=instrument.value,
                    lien_status=raw.get("lien_status", "active"),
                    tax_year=raw.get("tax_year"),
                    years_delinquent=raw.get("years_delinquent"),
                    principal_amount=float(raw.get("principal_amount", 0)),
                    interest_amount=_float_or_none(raw.get("interest_amount")),
                    penalty_amount=_float_or_none(raw.get("penalty_amount")),
                    total_owed=_float_or_none(raw.get("total_owed")),
                    filing_date=raw.get("filing_date"),
                    redemption_deadline=raw.get("redemption_deadline"),
                    certificate_number=raw.get("certificate_number"),
                    certificate_interest_rate=_float_or_none(raw.get("certificate_interest_rate")),
                    auction_date=raw.get("auction_date"),
                    auction_platform=raw.get("auction_platform"),
                    auction_url=raw.get("auction_url"),
                    opening_bid=_float_or_none(raw.get("opening_bid")),
                    post_sale_redemption_days=raw.get("post_sale_redemption_days", 0),
                    source_url=raw.get("source_url"),
                    content_hash=_hash(raw),
                    retrieved_at=now,
                )
                await lien_repo.upsert(lien)

                # Log the crawl
                session.add(
                    CrawlLog(
                        parcel_id=str(parcel_id),
                        source_type="tax_collector",
                        source_url=raw.get("source_url"),
                        http_status=200,
                        content_hash=_hash(raw),
                        changed=True,
                        crawled_at=now,
                    )
                )

                # Enqueue for parcel research
                existing_count = await queue_repo.get_pending_count(agent_name="parcel_research")
                # Simple dedup: only enqueue if no pending parcel research for this parcel
                await queue_repo.enqueue(
                    agent_name="parcel_research",
                    stage="parcel",
                    parcel_id=str(parcel_id),
                    payload={"parcel_id": str(parcel_id), "state": state, "county": county},
                    priority=_deadline_priority(raw),
                )
                enqueued += 1

            await session.commit()

        return enqueued


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash(data: dict[str, Any]) -> str:
    """MD5 of a dict for change detection."""
    normalised = str(sorted(data.items()))
    return hashlib.md5(normalised.encode()).hexdigest()


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _deadline_priority(raw: dict[str, Any]) -> int:
    """Return queue priority based on proximity to redemption/auction deadline."""
    from datetime import date

    deadline_str = raw.get("redemption_deadline") or raw.get("auction_date")
    if not deadline_str:
        return 5

    try:
        if isinstance(deadline_str, date):
            deadline = deadline_str
        else:
            deadline = date.fromisoformat(str(deadline_str))
        days_left = (deadline - date.today()).days
        if days_left <= 30:
            return 1   # urgent
        if days_left <= 90:
            return 2
        return 5
    except (ValueError, TypeError):
        return 5


# Module-level singleton used by the agent registry
agent = DiscoveryAgent()
