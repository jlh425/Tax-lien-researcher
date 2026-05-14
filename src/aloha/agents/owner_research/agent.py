"""Owner Research Agent — identifies and structures property owner data.

Responsibilities:
1. Classify the owner type (individual / LLC / trust / corporation / government)
2. Detect absentee ownership (mailing ≠ property address)
3. Parse and structure the mailing address for outreach
4. Classify the deed type from instrument description
5. Persist an Owner record and advance parcel to 'owner_researched'
6. If owner is an entity, enqueue for Entity Research Agent
7. If owner is an individual, enqueue for Scoring Agent directly
"""

from __future__ import annotations

from typing import Any

import structlog

from aloha.agents.base import BaseAgent
from aloha.agents.owner_research.tools import (
    classify_deed_type,
    classify_owner_type,
    detect_absentee,
    parse_mailing_address,
)
from aloha.db.engine import async_session_factory
from aloha.db.models.owner import Owner
from aloha.db.repositories import OwnerRepository, ParcelRepository, QueueRepository

log = structlog.get_logger().bind(agent="owner_research")


class OwnerResearchAgent(BaseAgent):
    """Enriches a parcel with structured owner data from public records.

    Context keys expected in ``run(context)``:
    - ``parcel_id``: APN / assessor parcel number (required)
    - ``state``: two-letter state abbreviation (required)
    - ``county``: county name in lowercase (required)
    - ``address``: property street address (optional)
    - ``owner_of_record``: raw owner name from assessor (optional)
    """

    def __init__(self) -> None:
        super().__init__(name="owner_research")

    # ── Abstract interface ────────────────────────────────────────────────

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "classify_owner_type",
                "description": "Classify the owner name as individual, llc, trust, etc.",
                "parameters": {
                    "type": "object",
                    "properties": {"owner_name": {"type": "string"}},
                    "required": ["owner_name"],
                },
            },
            {
                "name": "detect_absentee",
                "description": "Detect whether the owner is absentee.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "property_address": {"type": "string"},
                        "mailing_address": {"type": "string"},
                    },
                    "required": [],
                },
            },
            {
                "name": "parse_mailing_address",
                "description": "Parse a raw mailing address into structured fields.",
                "parameters": {
                    "type": "object",
                    "properties": {"raw_address": {"type": "string"}},
                    "required": ["raw_address"],
                },
            },
        ]

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        parcel_id: str = context["parcel_id"]
        state: str = context["state"].upper()
        county: str = context["county"].lower()
        property_address: str | None = context.get("address")
        owner_of_record: str | None = context.get("owner_of_record")

        self.log.info("owner_research_started", parcel_id=parcel_id, state=state, county=county)

        # Pull augmented owner data from the DB parcel record if caller didn't supply it
        if not owner_of_record or not property_address:
            owner_of_record, property_address = await self._load_from_db(
                parcel_id, owner_of_record, property_address
            )

        # ── Step 1: Classify owner type ───────────────────────────────────
        owner_classification = classify_owner_type(owner_of_record or "")
        owner_type: str = owner_classification["owner_type"]
        is_entity: bool = owner_classification["is_entity"]

        # ── Step 2: Detect absentee ───────────────────────────────────────
        # The mailing address lives in raw assessor data; fall back to what
        # we have from the ArcGIS query stored in the parcel record.
        raw_mailing = context.get("mailing_address") or await self._get_mailing_from_db(parcel_id)
        absentee_result = detect_absentee(property_address, raw_mailing)

        # ── Step 3: Parse mailing address ─────────────────────────────────
        parsed_mailing: dict[str, Any] = {}
        if raw_mailing:
            parsed_mailing = parse_mailing_address(raw_mailing)

        # ── Step 4: Deed type ─────────────────────────────────────────────
        deed_type = classify_deed_type(context.get("deed_description"))

        # ── Step 5: Build and persist Owner record ────────────────────────
        owner = Owner(
            parcel_id=parcel_id,
            owner_of_record=owner_of_record,
            owner_type=owner_type,
            mailing_address=parsed_mailing.get("full") or raw_mailing,
            mailing_city=parsed_mailing.get("city"),
            mailing_state=parsed_mailing.get("state"),
            mailing_zip=parsed_mailing.get("zip"),
            is_absentee=absentee_result.get("is_absentee"),
            deed_type=deed_type,
            research_depth=1,
            sources={"assessor": True},
        )
        owner_id = await self._persist(parcel_id, owner, is_entity, state, county)

        self.log.info(
            "owner_research_complete",
            parcel_id=parcel_id,
            owner_type=owner_type,
            is_entity=is_entity,
            is_absentee=absentee_result.get("is_absentee"),
        )
        return {
            "status": "complete",
            "parcel_id": parcel_id,
            "owner_id": owner_id,
            "owner_type": owner_type,
            "is_entity": is_entity,
            "is_absentee": absentee_result.get("is_absentee"),
        }

    # ── DB helpers ────────────────────────────────────────────────────────

    async def _load_from_db(
        self,
        parcel_id: str,
        owner_of_record: str | None,
        property_address: str | None,
    ) -> tuple[str | None, str | None]:
        """Pull owner name and address from the Parcel record."""
        async with async_session_factory() as session:
            parcel_repo = ParcelRepository(session)
            parcel = await parcel_repo.get(parcel_id)
            if parcel:
                owner_of_record = owner_of_record or getattr(parcel, "owner_of_record", None)
                property_address = property_address or parcel.address
        return owner_of_record, property_address

    async def _get_mailing_from_db(self, parcel_id: str) -> str | None:
        """Attempt to read mailing address from existing owner records."""
        async with async_session_factory() as session:
            owner_repo = OwnerRepository(session)
            owners = await owner_repo.get_by_parcel(parcel_id)
            for o in owners:
                if o.mailing_address:
                    return o.mailing_address
        return None

    async def _persist(
        self,
        parcel_id: str,
        owner: Owner,
        is_entity: bool,
        state: str,
        county: str,
    ) -> int | None:
        """Upsert the Owner, advance parcel status, enqueue next stage."""
        async with async_session_factory() as session:
            parcel_repo = ParcelRepository(session)
            owner_repo = OwnerRepository(session)
            queue_repo = QueueRepository(session)

            # Upsert owner
            saved = await owner_repo.upsert(owner)
            owner_id = saved.id

            # Advance parcel status
            parcel = await parcel_repo.get(parcel_id)
            if parcel:
                parcel.research_status = "owner_researched"

            # Next stage: entity → entity_research; individual → scoring
            if is_entity:
                await queue_repo.enqueue(
                    agent_name="entity_research",
                    stage="entity",
                    parcel_id=parcel_id,
                    payload={
                        "parcel_id": parcel_id,
                        "owner_id": owner_id,
                        "entity_name": owner.owner_of_record,
                        "state": state,
                        "county": county,
                    },
                    priority=5,
                )
            else:
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
            return owner_id


# ── Module-level singleton ─────────────────────────────────────────────────────

agent = OwnerResearchAgent()
