"""Entity Research Agent — pierces LLC/trust/corp structures via SOS data.

Responsibilities:
1. Look up the entity in the state Secretary of State database (Cobalt Intelligence)
2. Extract officers, managers, and registered agent
3. Detect commercial registered agent services (CT Corp, Northwest, etc.)
4. Search for related entities sharing the same RA or address
5. Derive the best beneficial owner name for outreach
6. Persist the Entity record and link it to the Owner
7. Enqueue for the Scoring Agent
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import Any

import structlog

from aloha.agents.base import BaseAgent
from aloha.db.engine import async_session_factory
from aloha.db.models.owner import Entity, OwnerEntity
from aloha.db.repositories import OwnerRepository, ParcelRepository, QueueRepository
from aloha.db.repositories.owner import EntityRepository

log = structlog.get_logger().bind(agent="entity_research")

# Commercial registered agent names — not useful for beneficial owner lookup
_COMMERCIAL_RA_PATTERNS = frozenset({
    "CT CORPORATION",
    "CORPORATION SERVICE COMPANY",
    "CSC",
    "NORTHWEST REGISTERED AGENT",
    "REGISTERED AGENTS INC",
    "NATIONAL REGISTERED AGENTS",
    "UNITED AGENT GROUP",
    "INCORP SERVICES",
    "LEGALZOOM",
    "HARBOR COMPLIANCE",
    "COGENCY GLOBAL",
    "NRAI",
    "THE CORPORATION TRUST COMPANY",
})

# States commonly used for entity formation
_FORMATION_STATE_SEARCH_ORDER = ["FL", "TX", "CA", "DE", "NV", "WY", "GA", "NY", "AZ"]


def _is_commercial_ra(agent_name: str | None) -> bool:
    if not agent_name:
        return False
    name_upper = agent_name.upper().strip()
    return any(pattern in name_upper for pattern in _COMMERCIAL_RA_PATTERNS)


class EntityResearchAgent(BaseAgent):
    """Pierces entity ownership and identifies beneficial owners.

    Context keys expected in ``run(context)``:
    - ``parcel_id``: APN / assessor parcel number (required)
    - ``owner_id``: DB ID of the Owner record (required)
    - ``entity_name``: raw entity name from assessor (required)
    - ``state``: property state abbreviation (required)
    - ``county``: county name in lowercase (required)
    """

    def __init__(self) -> None:
        super().__init__(name="entity_research")

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "sos_lookup_entity",
                "description": "Search state SOS database for a business entity.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity_name": {"type": "string"},
                        "state": {"type": "string"},
                    },
                    "required": ["entity_name", "state"],
                },
            },
            {
                "name": "sos_get_entity_details",
                "description": "Fetch full SOS filing for a specific entity.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity_id": {"type": "string"},
                        "state": {"type": "string"},
                    },
                    "required": ["entity_id", "state"],
                },
            },
        ]

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        parcel_id: str = context["parcel_id"]
        owner_id: int = context["owner_id"]
        entity_name: str = context["entity_name"]
        state: str = context["state"].upper()
        county: str = context["county"].lower()

        self.log.info(
            "entity_research_started",
            parcel_id=parcel_id,
            entity_name=entity_name,
            state=state,
        )

        # ── Step 1: SOS lookup ────────────────────────────────────────────
        sos_result = await self._sos_lookup(entity_name, state)

        # ── Step 2: Derive beneficial owner ──────────────────────────────
        beneficial_owner, confidence = self._extract_beneficial_owner(sos_result)

        # ── Step 3: Related entities ──────────────────────────────────────
        related_entity_ids = await self._find_related_entities(sos_result, state)

        # ── Step 4: Persist Entity record ─────────────────────────────────
        entity_id = await self._persist(
            parcel_id=parcel_id,
            owner_id=owner_id,
            entity_name=entity_name,
            sos_result=sos_result,
            beneficial_owner=beneficial_owner,
            confidence=confidence,
            related_entity_ids=related_entity_ids,
            state=state,
            county=county,
        )

        self.log.info(
            "entity_research_complete",
            parcel_id=parcel_id,
            entity_id=entity_id,
            beneficial_owner=beneficial_owner,
            confidence=confidence,
        )
        return {
            "status": "complete",
            "parcel_id": parcel_id,
            "entity_id": entity_id,
            "beneficial_owner": beneficial_owner,
            "confidence": confidence,
        }

    # ── SOS helpers ───────────────────────────────────────────────────────

    async def _sos_lookup(
        self,
        entity_name: str,
        property_state: str,
    ) -> dict[str, Any]:
        """Try the property state first, then common formation states."""
        try:
            from aloha.mcp_servers.sos.server import create_sos_server

            server = create_sos_server()
        except (ValueError, ImportError) as exc:
            self.log.warning("sos_server_unavailable", error=str(exc))
            return {}

        # Try property state first
        search_states = [property_state] + [
            s for s in _FORMATION_STATE_SEARCH_ORDER if s != property_state
        ]

        try:
            for search_state in search_states:
                result = await server.sos_lookup_entity(entity_name, search_state)
                entities = result.get("entities", [])
                if entities:
                    # Fetch full detail for the first (best) match
                    top = entities[0]
                    if top.get("entity_id"):
                        detail = await server.sos_get_entity_details(
                            top["entity_id"], search_state
                        )
                        if "error" not in detail:
                            detail["_search_state"] = search_state
                            return detail
                    return top
            return {}
        finally:
            await server.close()

    def _extract_beneficial_owner(
        self,
        sos_result: dict[str, Any],
    ) -> tuple[str | None, str]:
        """Derive the best individual name to use for outreach.

        Returns (beneficial_owner_name, confidence).
        """
        if not sos_result:
            return None, "unknown"

        # Officers / managers
        for group_key in ("officers", "managers_members"):
            people = sos_result.get(group_key, [])
            for person in people:
                name = person.get("name", "")
                if name and not _is_commercial_ra(name):
                    return name.title(), "high"

        # Registered agent (only if not commercial)
        ra = sos_result.get("registered_agent")
        if ra and not _is_commercial_ra(ra):
            return ra.title(), "medium"

        # Entity name itself as last resort
        entity_name = sos_result.get("entity_name")
        if entity_name:
            return None, "low"

        return None, "unknown"

    async def _find_related_entities(
        self,
        sos_result: dict[str, Any],
        state: str,
        limit: int = 20,
    ) -> list[str]:
        """Search for other entities sharing the same registered agent."""
        ra = sos_result.get("registered_agent")
        if not ra or _is_commercial_ra(ra):
            return []

        try:
            from aloha.mcp_servers.sos.server import create_sos_server

            server = create_sos_server()
            try:
                result = await server.sos_search_by_registered_agent(ra, state, limit=limit)
                entities = result.get("entities", [])
                related_ids = [
                    str(e["entity_id"]) for e in entities if e.get("entity_id")
                ]
                return related_ids[:limit]
            finally:
                await server.close()
        except (ValueError, ImportError):
            return []
        except Exception as exc:
            self.log.warning("related_entity_search_failed", error=str(exc))
            return []

    # ── Persistence ───────────────────────────────────────────────────────

    async def _persist(
        self,
        *,
        parcel_id: str,
        owner_id: int,
        entity_name: str,
        sos_result: dict[str, Any],
        beneficial_owner: str | None,
        confidence: str,
        related_entity_ids: list[str],
        state: str,
        county: str,
    ) -> int | None:
        now = datetime.now(tz=timezone.utc)
        formation_raw = sos_result.get("formation_date")
        formation_date: date | None = None
        if formation_raw:
            try:
                formation_date = date.fromisoformat(str(formation_raw)[:10])
            except ValueError:
                pass

        async with async_session_factory() as session:
            entity_repo = EntityRepository(session)
            owner_repo = OwnerRepository(session)
            parcel_repo = ParcelRepository(session)
            queue_repo = QueueRepository(session)

            # Upsert Entity
            entity = Entity(
                entity_name=entity_name,
                entity_type=sos_result.get("entity_type"),
                state_of_formation=sos_result.get("_search_state") or sos_result.get("state"),
                sos_status=sos_result.get("status"),
                formation_date=formation_date,
                registered_agent=sos_result.get("registered_agent"),
                registered_agent_address=sos_result.get("registered_agent_address"),
                officers=sos_result.get("officers"),
                managers_members=sos_result.get("managers_members"),
                sos_filing_url=sos_result.get("sos_filing_url"),
                related_entity_ids=related_entity_ids or None,
                content_hash=hashlib.md5(str(sorted(sos_result.items())).encode()).hexdigest(),
                last_researched_at=now,
                created_at=now,
            )
            saved_entity = await entity_repo.upsert(entity)
            entity_db_id = saved_entity.id

            # Link Owner → Entity
            link = OwnerEntity(owner_id=owner_id, entity_id=entity_db_id)
            session.add(link)

            # Update Owner with beneficial owner info
            owner = await owner_repo.get(owner_id)
            if owner:
                owner.beneficial_owner = beneficial_owner
                owner.beneficial_owner_confidence = confidence
                owner.research_depth = max(owner.research_depth, 2)

            # Advance parcel status
            parcel = await parcel_repo.get(parcel_id)
            if parcel:
                parcel.research_status = "entity_researched"

            # Enqueue scoring
            await queue_repo.enqueue(
                agent_name="scoring",
                stage="score",
                parcel_id=parcel_id,
                payload={"parcel_id": parcel_id, "state": state, "county": county},
                priority=5,
            )

            await session.commit()
            return entity_db_id


# ── Module-level singleton ─────────────────────────────────────────────────────

agent = EntityResearchAgent()
