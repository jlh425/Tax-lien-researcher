"""Contact Research Agent — finds owner phone/email for outreach.

Responsibilities:
1. Enrich owner name+location via People Data Labs (PDL) MCP server
2. Verify discovered emails via Hunter.io MCP server
3. Score contact quality (phone type, email deliverability)
4. Persist best_phone + best_email on the Owner record
5. Advance parcel to 'contact_researched' and enqueue for enrichment
"""

from __future__ import annotations

from typing import Any

import structlog

from aloha.agents.base import BaseAgent
from aloha.agents.contact_research.tools import (
    pick_best_contact,
    score_contact_quality,
)
from aloha.db.engine import async_session_factory
from aloha.db.repositories import OwnerRepository, ParcelRepository, QueueRepository

log = structlog.get_logger().bind(agent="contact_research")


class ContactResearchAgent(BaseAgent):
    """Finds and verifies owner contact info for outreach.

    Context keys expected in ``run(context)``:
    - ``parcel_id``: APN (required)
    - ``owner_id``: Owner record ID (required)
    - ``state``: two-letter state abbreviation (required)
    - ``county``: county name in lowercase (required)
    - ``owner_name``: raw owner name (optional, loaded from DB if missing)
    - ``location``: city/state hint for PDL (optional)
    """

    def __init__(self) -> None:
        super().__init__(name="contact_research")

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "enrich_person",
                "description": "Enrich a person via PDL to find contact info.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "location": {"type": "string"},
                        "company": {"type": "string"},
                    },
                    "required": ["name"],
                },
            },
            {
                "name": "verify_email",
                "description": "Verify an email address via Hunter.io.",
                "parameters": {
                    "type": "object",
                    "properties": {"email": {"type": "string"}},
                    "required": ["email"],
                },
            },
            {
                "name": "search_phone",
                "description": "Search for a person by phone via PDL.",
                "parameters": {
                    "type": "object",
                    "properties": {"phone": {"type": "string"}},
                    "required": ["phone"],
                },
            },
        ]

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        parcel_id: str = context["parcel_id"]
        owner_id: int = context["owner_id"]
        state: str = context["state"].upper()
        county: str = context["county"].lower()
        owner_name: str | None = context.get("owner_name")
        location: str | None = context.get("location")

        self.log.info("contact_research_started", parcel_id=parcel_id, owner_id=owner_id)

        # Load owner from DB if name not provided
        if not owner_name:
            owner_name, location = await self._load_owner(owner_id, state, county)

        if not owner_name:
            self.log.warning("no_owner_name", parcel_id=parcel_id)
            return {"status": "skipped", "reason": "no owner name available"}

        # Step 1: Enrich via PDL MCP server
        enrichment = await self._enrich_person(owner_name, location)

        # Step 2: Extract best contact info
        contact = pick_best_contact(enrichment)
        best_phone = contact["best_phone"]
        best_email = contact["best_email"]

        # Step 3: Verify email if found
        email_verified = False
        if best_email:
            verification = await self._verify_email(best_email)
            email_verified = verification.get("status") in ("valid", "deliverable")
            if not email_verified:
                self.log.info(
                    "email_unverified", email=best_email, status=verification.get("status")
                )

        # Step 4: Score contact quality
        quality = score_contact_quality(
            has_phone=best_phone is not None,
            has_email=best_email is not None,
            email_verified=email_verified,
            phone_type=contact.get("phone_type"),
        )

        # Step 5: Persist and advance
        await self._persist(
            parcel_id=parcel_id,
            owner_id=owner_id,
            best_phone=best_phone,
            best_email=best_email,
            reachability_score=quality["score"],
            state=state,
            county=county,
        )

        self.log.info(
            "contact_research_complete",
            parcel_id=parcel_id,
            owner_id=owner_id,
            has_phone=best_phone is not None,
            has_email=best_email is not None,
            quality_score=quality["score"],
        )
        return {
            "status": "complete",
            "parcel_id": parcel_id,
            "owner_id": owner_id,
            "best_phone": best_phone,
            "best_email": best_email,
            "email_verified": email_verified,
            "quality": quality,
        }

    # -- MCP server calls ------------------------------------------------------

    async def _enrich_person(self, name: str, location: str | None) -> dict[str, Any]:
        """Call the people_data MCP server's enrich_person tool."""
        try:
            from aloha.mcp_servers.people_data.server import create_people_data_server

            server = create_people_data_server()
            try:
                return await server.enrich_person(name=name, location=location)
            finally:
                await server.close()
        except (ValueError, Exception) as exc:
            self.log.warning("pdl_enrich_unavailable", error=str(exc))
            return {}

    async def _verify_email(self, email: str) -> dict[str, Any]:
        """Call the people_data MCP server's verify_email tool."""
        try:
            from aloha.mcp_servers.people_data.server import create_people_data_server

            server = create_people_data_server()
            try:
                return await server.verify_email(email=email)
            finally:
                await server.close()
        except (ValueError, Exception) as exc:
            self.log.warning("hunter_verify_unavailable", error=str(exc))
            return {}

    # -- DB helpers ------------------------------------------------------------

    async def _load_owner(
        self, owner_id: int, state: str, county: str
    ) -> tuple[str | None, str | None]:
        """Load owner name and build location hint from DB."""
        async with async_session_factory() as session:
            owner_repo = OwnerRepository(session)
            owner = await owner_repo.get(owner_id)
            if owner:
                location = None
                if owner.mailing_city and owner.mailing_state:
                    location = f"{owner.mailing_city}, {owner.mailing_state}"
                elif state and county:
                    location = f"{county.title()}, {state}"
                return owner.owner_of_record, location
        return None, None

    async def _persist(
        self,
        *,
        parcel_id: str,
        owner_id: int,
        best_phone: str | None,
        best_email: str | None,
        reachability_score: int,
        state: str,
        county: str,
    ) -> None:
        """Update owner contact info, advance parcel, enqueue next stage."""
        async with async_session_factory() as session:
            owner_repo = OwnerRepository(session)
            parcel_repo = ParcelRepository(session)
            queue_repo = QueueRepository(session)

            owner = await owner_repo.get(owner_id)
            if owner:
                owner.best_phone = best_phone
                owner.best_email = best_email
                owner.research_depth = max(owner.research_depth or 0, 3)

            parcel = await parcel_repo.get(parcel_id)
            if parcel:
                parcel.research_status = "contact_researched"

            await queue_repo.enqueue(
                agent_name="enrichment",
                stage="enrich",
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

agent = ContactResearchAgent()
