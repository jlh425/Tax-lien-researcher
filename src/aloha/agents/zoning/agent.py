"""Zoning Agent — classifies zoning, land use, and development potential.

Responsibilities:
1. Parse raw zoning codes into structured classifications
2. Map land use codes to standardised property types
3. Assess development/redevelopment potential
4. Persist zoning data on the Parcel record
5. Advance parcel to 'zoning_researched' and enqueue for scoring
"""

from __future__ import annotations

from typing import Any

import structlog

from aloha.agents.base import BaseAgent
from aloha.agents.zoning.tools import (
    assess_development_potential,
    classify_land_use,
    classify_zoning,
    summarise_zoning,
)
from aloha.db.engine import async_session_factory
from aloha.db.repositories import ParcelRepository, QueueRepository

log = structlog.get_logger().bind(agent="zoning")


class ZoningAgent(BaseAgent):
    """Classifies zoning and assesses development potential.

    Context keys expected in ``run(context)``:
    - ``parcel_id``: APN (required)
    - ``state``: two-letter state abbreviation (required)
    - ``county``: county name in lowercase (required)
    - ``zoning_code``: raw zoning code (optional, loaded from DB if missing)
    - ``land_use_code``: county land use code (optional, loaded from DB)
    - ``acreage``: parcel size in acres (optional, loaded from DB)
    - ``year_built``: structure year built (optional, loaded from DB)
    - ``assessed_total``: total assessed value (optional, loaded from DB)
    - ``market_value_est``: estimated market value (optional, loaded from DB)
    """

    def __init__(self) -> None:
        super().__init__(name="zoning")

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "classify_zoning",
                "description": "Parse a raw zoning code into a structured classification.",
                "parameters": {
                    "type": "object",
                    "properties": {"zoning_code": {"type": "string"}},
                    "required": ["zoning_code"],
                },
            },
            {
                "name": "classify_land_use",
                "description": "Map a county land use code to a property type.",
                "parameters": {
                    "type": "object",
                    "properties": {"land_use_code": {"type": "string"}},
                    "required": ["land_use_code"],
                },
            },
            {
                "name": "assess_development",
                "description": "Assess the development potential of a parcel.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "zoning_category": {"type": "string"},
                        "acreage": {"type": "number"},
                        "year_built": {"type": "integer"},
                    },
                    "required": ["zoning_category"],
                },
            },
        ]

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        parcel_id: str = context["parcel_id"]
        state: str = context["state"].upper()
        county: str = context["county"].lower()

        self.log.info("zoning_research_started", parcel_id=parcel_id)

        # Load parcel data from DB for any missing fields
        parcel_data = await self._load_parcel(parcel_id)

        zoning_code = context.get("zoning_code") or parcel_data.get("zoning")
        land_use_code = context.get("land_use_code") or parcel_data.get("land_use_code")
        acreage = context.get("acreage") or parcel_data.get("acreage")
        year_built = context.get("year_built") or parcel_data.get("year_built")
        assessed_total = context.get("assessed_total") or parcel_data.get("assessed_total")
        market_value_est = context.get("market_value_est") or parcel_data.get("market_value_est")

        # Step 1: Classify zoning code
        zoning = classify_zoning(zoning_code)

        # Step 2: Classify land use
        land_use = classify_land_use(land_use_code)

        # Step 3: Assess development potential
        development = assess_development_potential(
            zoning_category=zoning["category"],
            acreage=float(acreage) if acreage else None,
            year_built=int(year_built) if year_built else None,
            assessed_total=int(assessed_total) if assessed_total else None,
            market_value_est=int(market_value_est) if market_value_est else None,
        )

        # Step 4: Build summary and persist
        summary = summarise_zoning(
            zoning=zoning,
            land_use=land_use,
            development=development,
        )

        await self._persist(
            parcel_id=parcel_id,
            zoning_code=zoning["code"],
            zoning_notes=zoning["description"],
            property_type=land_use["property_type"],
            state=state,
            county=county,
        )

        self.log.info(
            "zoning_research_complete",
            parcel_id=parcel_id,
            category=zoning["category"],
            development=development["potential"],
        )
        return {
            "status": "complete",
            "parcel_id": parcel_id,
            **summary,
        }

    # -- DB helpers ------------------------------------------------------------

    async def _load_parcel(self, parcel_id: str) -> dict[str, Any]:
        """Load parcel fields relevant to zoning analysis."""
        async with async_session_factory() as session:
            parcel_repo = ParcelRepository(session)
            parcel = await parcel_repo.get(parcel_id)
            if not parcel:
                return {}
            return {
                "zoning": parcel.zoning,
                "land_use_code": parcel.land_use_code,
                "acreage": float(parcel.acreage) if parcel.acreage else None,
                "year_built": parcel.year_built,
                "assessed_total": parcel.assessed_total,
                "market_value_est": parcel.market_value_est,
                "property_type": parcel.property_type,
            }

    async def _persist(
        self,
        *,
        parcel_id: str,
        zoning_code: str | None,
        zoning_notes: str | None,
        property_type: str | None,
        state: str,
        county: str,
    ) -> None:
        """Update parcel with zoning data, advance status, enqueue scoring."""
        async with async_session_factory() as session:
            parcel_repo = ParcelRepository(session)
            queue_repo = QueueRepository(session)

            parcel = await parcel_repo.get(parcel_id)
            if parcel:
                if zoning_code:
                    parcel.zoning = zoning_code
                if zoning_notes:
                    parcel.zoning_notes = zoning_notes
                if property_type and property_type != "unknown":
                    parcel.property_type = property_type
                parcel.research_status = "zoning_researched"

            await queue_repo.enqueue(
                agent_name="scoring",
                stage="score",
                parcel_id=parcel_id,
                payload={
                    "parcel_id": parcel_id,
                    "state": state,
                    "county": county,
                },
                priority=5,
            )

            await session.commit()


# -- Module-level singleton ----------------------------------------------------

agent = ZoningAgent()
