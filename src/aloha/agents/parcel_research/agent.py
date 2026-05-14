"""Parcel Research Agent — fills in property details for a discovered parcel.

Responsibilities:
1. Query the county ArcGIS parcel service (Tier 1) for assessor data
2. Fall back to county assessor web scraper (Tier 2/3) if no ArcGIS endpoint
3. Parse the legal description into structured components
4. Classify the property type (residential/commercial/land/industrial/agricultural)
5. Update the Parcel record in the DB and advance research_status to 'parcel_researched'
6. Enqueue the parcel for Owner Research
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

import structlog

from aloha.agents.base import BaseAgent
from aloha.agents.parcel_research.tools import (
    classify_property_type,
    parse_legal_description,
    query_arcgis_parcel,
    query_assessor_web,
)
from aloha.db.engine import async_session_factory
from aloha.db.repositories import ParcelRepository, QueueRepository

log = structlog.get_logger().bind(agent="parcel_research")


class ParcelResearchAgent(BaseAgent):
    """Enriches a parcel stub with assessor data and legal description details.

    Context keys expected in ``run(context)``:
    - ``parcel_id``: APN / assessor parcel number (required)
    - ``state``: two-letter state abbreviation (required)
    - ``county``: county name in lowercase (required)
    - ``address``: known address string (optional, helps fallback scrapers)
    """

    def __init__(self) -> None:
        super().__init__(name="parcel_research")

    # ── Abstract interface ────────────────────────────────────────────────

    def get_tools(self) -> list[dict[str, Any]]:
        """Tool schemas for Pydantic AI — returned as JSON-schema dicts."""
        return [
            {
                "name": "query_arcgis_parcel",
                "description": "Query the county ArcGIS parcel feature layer by APN.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "parcel_id": {"type": "string"},
                        "state": {"type": "string"},
                        "county": {"type": "string"},
                    },
                    "required": ["parcel_id", "state", "county"],
                },
            },
            {
                "name": "query_assessor_web",
                "description": "Scrape the county assessor website for parcel data.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "parcel_id": {"type": "string"},
                        "state": {"type": "string"},
                        "county": {"type": "string"},
                        "address": {"type": "string"},
                    },
                    "required": ["parcel_id", "state", "county"],
                },
            },
            {
                "name": "parse_legal_description",
                "description": "Parse a raw legal description string into structured fields.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "legal_description": {"type": "string"},
                    },
                    "required": ["legal_description"],
                },
            },
        ]

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        parcel_id: str = context["parcel_id"]
        state: str = context["state"].upper()
        county: str = context["county"].lower()
        address: str | None = context.get("address")

        self.log.info("parcel_research_started", parcel_id=parcel_id, state=state, county=county)

        # ── Step 1: Fetch assessor data ───────────────────────────────────
        raw = await self._fetch_assessor_data(parcel_id, state, county, address)

        if "error" in raw and not raw.get("parcel_id"):
            # Both ArcGIS and web scraper failed — record what we know and move on
            self.log.warning(
                "assessor_data_unavailable",
                parcel_id=parcel_id,
                error=raw.get("error"),
            )
            await self._update_status(parcel_id, "parcel_research_failed")
            return {
                "status": "failed",
                "parcel_id": parcel_id,
                "reason": raw.get("error"),
            }

        # ── Step 2: Parse legal description ──────────────────────────────
        legal_desc = (
            raw.get("legal_description")
            or raw.get("raw_attributes", {}).get("LEGAL_DESC")
            or raw.get("raw_attributes", {}).get("LEGAL")
        )
        parsed_legal = parse_legal_description(legal_desc or "")

        # ── Step 3: Classify property type ────────────────────────────────
        property_type = classify_property_type(
            raw.get("land_use_code"),
            raw.get("zoning"),
            legal_desc,
        )

        # ── Step 4: Merge and persist ─────────────────────────────────────
        updates = self._build_updates(raw, parsed_legal, property_type, legal_desc)
        await self._persist(parcel_id, updates)

        self.log.info(
            "parcel_research_complete",
            parcel_id=parcel_id,
            property_type=property_type,
            assessed_total=updates.get("assessed_total"),
        )
        return {
            "status": "complete",
            "parcel_id": parcel_id,
            "property_type": property_type,
            "assessed_total": updates.get("assessed_total"),
            "legal_format": parsed_legal.get("format"),
        }

    # ── Data fetching ─────────────────────────────────────────────────────

    async def _fetch_assessor_data(
        self,
        parcel_id: str,
        state: str,
        county: str,
        address: str | None,
    ) -> dict[str, Any]:
        """Try ArcGIS first, fall back to web scraper."""
        result = await query_arcgis_parcel(parcel_id, state, county)
        if "error" not in result:
            return result

        self.log.info(
            "arcgis_unavailable_falling_back",
            parcel_id=parcel_id,
            arcgis_error=result.get("error"),
        )
        return await query_assessor_web(parcel_id, state, county, address)

    # ── Data shaping ──────────────────────────────────────────────────────

    def _build_updates(
        self,
        raw: dict[str, Any],
        parsed_legal: dict[str, Any],
        property_type: str,
        legal_desc: str | None,
    ) -> dict[str, Any]:
        """Merge raw assessor data with parsed fields into Parcel update dict."""
        updates: dict[str, Any] = {
            "property_type": property_type,
            "research_status": "parcel_researched",
            "last_crawled_at": datetime.now(tz=UTC),
        }

        # Direct field mappings from ArcGIS normalised output
        _copy_if_present(raw, updates, "zoning")
        _copy_if_present(raw, updates, "acreage")
        _copy_if_present(raw, updates, "land_use_code")
        _copy_if_present(raw, updates, "assessed_total")
        _copy_if_present(raw, updates, "latitude")
        _copy_if_present(raw, updates, "longitude")

        # Address — prefer what we already have if raw doesn't improve it
        if raw.get("address"):
            updates["address"] = raw["address"]

        # Legal description — raw text + parsed subdivision reference
        if legal_desc:
            updates["legal_description"] = legal_desc

        # Zoning notes from subdivision name if parsed
        if parsed_legal.get("subdivision"):
            updates["zoning_notes"] = f"Subdivision: {parsed_legal['subdivision']}"

        # Geometry from raw_attributes fallback (extra fields assessors expose)
        raw_attrs = raw.get("raw_attributes", {})
        _try_int(raw_attrs, updates, "assessed_land_val", ("LAND_VAL", "ASSD_LND", "LAND_VALUE"))
        _try_int(raw_attrs, updates, "assessed_impr_val", ("IMPR_VAL", "ASSD_BLD", "BLDG_VALUE"))
        _try_int(
            raw_attrs, updates, "market_value_est", ("JUST_VALUE", "MARKET_VALUE", "MARKET_VAL")
        )
        _try_int(raw_attrs, updates, "year_built", ("YEAR_BLT", "YR_BUILT", "YEAR_BUILT"))
        _try_int(
            raw_attrs, updates, "last_sale_price", ("SALE_PRICE", "LAST_SALE_PRICE", "SALES_PRICE")
        )

        # Content hash for change detection
        updates["content_hash"] = _hash(raw)
        return updates

    # ── Persistence ───────────────────────────────────────────────────────

    async def _persist(self, parcel_id: str, updates: dict[str, Any]) -> None:
        """Write update fields to the Parcel record and enqueue owner research."""
        async with async_session_factory() as session:
            parcel_repo = ParcelRepository(session)
            queue_repo = QueueRepository(session)

            parcel = await parcel_repo.get(parcel_id)
            if parcel is None:
                self.log.warning("parcel_not_found_in_db", parcel_id=parcel_id)
                return

            for field, value in updates.items():
                if hasattr(parcel, field) and value is not None:
                    setattr(parcel, field, value)

            # Advance to parcel_researched and enqueue owner research
            parcel.research_status = "parcel_researched"

            await queue_repo.enqueue(
                agent_name="owner_research",
                stage="owner",
                parcel_id=parcel_id,
                payload={
                    "parcel_id": parcel_id,
                    "state": parcel.state,
                    "county": parcel.county,
                    "address": parcel.address,
                    "owner_of_record": updates.get("owner_of_record"),
                },
                priority=5,
            )

            # Trigger image capture + vision analysis in parallel (lower priority)
            await queue_repo.enqueue(
                agent_name="enrichment",
                stage="enrich",
                parcel_id=parcel_id,
                payload={
                    "parcel_id": parcel_id,
                    "state": parcel.state,
                    "county": parcel.county,
                },
                priority=8,
            )

            await session.commit()

    async def _update_status(self, parcel_id: str, status: str) -> None:
        async with async_session_factory() as session:
            parcel_repo = ParcelRepository(session)
            await parcel_repo.update_status(parcel_id, status)
            await session.commit()


# ── Module-level singleton ─────────────────────────────────────────────────────

agent = ParcelResearchAgent()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _copy_if_present(src: dict[str, Any], dst: dict[str, Any], key: str) -> None:
    val = src.get(key)
    if val is not None:
        dst[key] = val


def _try_int(
    attrs: dict[str, Any],
    dst: dict[str, Any],
    dst_key: str,
    aliases: tuple[str, ...],
) -> None:
    """Try each alias in a raw_attributes dict and coerce to int."""
    for alias in aliases:
        val = attrs.get(alias) or attrs.get(alias.lower())
        if val is not None:
            try:
                dst[dst_key] = int(float(str(val).replace(",", "")))
                return
            except (TypeError, ValueError) as e:
                log.debug("int_coercion_failed", key=dst_key, value=val, error=str(e))


def _hash(data: dict[str, Any]) -> str:
    normalised = str(sorted(data.items()))
    return hashlib.md5(normalised.encode()).hexdigest()
