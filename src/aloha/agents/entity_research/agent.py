"""Entity Research Agent — pierces LLC/trust/corp structures via SOS, UCC, and court data.

Responsibilities:
1. Look up the entity in the state Secretary of State database (Cobalt Intelligence)
2. Extract officers, managers, and registered agent
3. Detect commercial registered agent services (CT Corp, Northwest, etc.)
4. Search for related entities sharing the same RA or address
5. Search UCC filings for liens against the entity (financial health signal)
6. Search federal court records for litigation and bankruptcy (CourtListener)
7. Search state lien records for federal and state tax liens
8. Enrich business contact info (website, phone, email) via People Data Labs
9. Derive the best beneficial owner name for outreach
10. Persist the Entity record (including UCC, litigation, and contact data) and link to Owner
11. Enqueue for the Scoring Agent
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

        # ── Step 4: UCC filings ───────────────────────────────────────────
        ucc_filings = await self._search_ucc_filings(entity_name, state)

        # ── Step 5: Court records / litigation ────────────────────────────
        litigation_data = await self._search_litigation(entity_name, state)

        # ── Step 6: Business contact enrichment ───────────────────────────
        contact_data = await self._enrich_entity_contacts(
            sos_result, entity_name, state,
        )

        # ── Step 7: Persist Entity record ─────────────────────────────────
        entity_id = await self._persist(
            parcel_id=parcel_id,
            owner_id=owner_id,
            entity_name=entity_name,
            sos_result=sos_result,
            beneficial_owner=beneficial_owner,
            confidence=confidence,
            related_entity_ids=related_entity_ids,
            ucc_filings=ucc_filings,
            litigation_data=litigation_data,
            contact_data=contact_data,
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

    # ── UCC helpers ─────────────────────────────────────────────────────

    async def _search_ucc_filings(
        self,
        entity_name: str,
        state: str,
    ) -> list[dict[str, Any]]:
        """Search UCC filings for the entity via the UCC MCP server."""
        try:
            from aloha.mcp_servers.ucc.server import create_ucc_server

            server = create_ucc_server()
        except (ValueError, ImportError) as exc:
            self.log.warning("ucc_server_unavailable", error=str(exc))
            return []

        try:
            result = await server.search_ucc_filings(
                debtor_name=entity_name, state=state,
            )
            filings = result.get("filings", [])
            self.log.info(
                "ucc_search_complete",
                entity_name=entity_name,
                state=state,
                count=len(filings),
            )
            return filings
        except Exception as exc:
            self.log.warning("ucc_search_failed", error=str(exc))
            return []
        finally:
            await server.close()

    # ── Court records / litigation helpers ────────────────────────────────

    async def _search_litigation(
        self,
        entity_name: str,
        state: str,
    ) -> dict[str, Any]:
        """Search court records for liens, bankruptcy, and litigation.

        Returns a dict with keys: federal_tax_liens, state_tax_liens,
        bankruptcy_history, litigation_summary, pacer_results.
        On any error, returns empty results so the pipeline continues.
        """
        empty: dict[str, Any] = {
            "federal_tax_liens": [],
            "state_tax_liens": [],
            "bankruptcy_history": [],
            "litigation_summary": "",
            "pacer_results": [],
        }

        try:
            from aloha.mcp_servers.court_records.server import (
                create_court_records_server,
            )

            server = create_court_records_server()
        except (ValueError, ImportError) as exc:
            self.log.warning("court_records_server_unavailable", error=str(exc))
            return empty

        federal_tax_liens: list[dict[str, Any]] = []
        state_tax_liens: list[dict[str, Any]] = []
        bankruptcy_history: list[dict[str, Any]] = []
        litigation_entries: list[dict[str, Any]] = []
        pacer_results: list[dict[str, Any]] = []

        try:
            # ── Federal cases (litigation + bankruptcy) ───────────────
            federal_result = await server.search_federal_cases(
                party_name=entity_name, state=state,
            )
            cases = federal_result.get("cases", [])
            pacer_results = cases

            for case in cases:
                case_type = (case.get("case_type") or "").lower()
                if case_type == "bankruptcy":
                    bankruptcy_history.append(case)
                else:
                    litigation_entries.append(case)

            # ── State liens (tax liens) ───────────────────────────────
            lien_result = await server.search_state_liens(
                debtor_name=entity_name, state=state,
            )
            liens = lien_result.get("liens", [])

            for lien in liens:
                lien_type = (lien.get("lien_type") or "").lower()
                if lien_type == "federal_tax":
                    federal_tax_liens.append(lien)
                elif lien_type == "state_tax":
                    state_tax_liens.append(lien)
                else:
                    # Treat unknown lien types as state tax liens
                    state_tax_liens.append(lien)

            # ── Build litigation summary ──────────────────────────────
            summary = self._build_litigation_summary(
                entity_name=entity_name,
                federal_tax_liens=federal_tax_liens,
                state_tax_liens=state_tax_liens,
                bankruptcy_history=bankruptcy_history,
                litigation_entries=litigation_entries,
            )

            self.log.info(
                "litigation_search_complete",
                entity_name=entity_name,
                state=state,
                federal_liens=len(federal_tax_liens),
                state_liens=len(state_tax_liens),
                bankruptcies=len(bankruptcy_history),
                litigation=len(litigation_entries),
            )

            return {
                "federal_tax_liens": federal_tax_liens,
                "state_tax_liens": state_tax_liens,
                "bankruptcy_history": bankruptcy_history,
                "litigation_summary": summary,
                "pacer_results": pacer_results,
            }
        except Exception as exc:
            self.log.warning(
                "litigation_search_failed",
                entity_name=entity_name,
                state=state,
                error=str(exc),
            )
            return empty
        finally:
            await server.close()

    @staticmethod
    def _build_litigation_summary(
        *,
        entity_name: str,
        federal_tax_liens: list[dict[str, Any]],
        state_tax_liens: list[dict[str, Any]],
        bankruptcy_history: list[dict[str, Any]],
        litigation_entries: list[dict[str, Any]],
    ) -> str:
        """Build a brief text digest of all court record findings."""
        parts: list[str] = [f"Court records summary for {entity_name}:"]

        if not any([
            federal_tax_liens, state_tax_liens,
            bankruptcy_history, litigation_entries,
        ]):
            return f"No court records found for {entity_name}."

        if federal_tax_liens:
            total = sum(
                float(lien.get("amount") or 0) for lien in federal_tax_liens
            )
            parts.append(
                f"- {len(federal_tax_liens)} federal tax lien(s)"
                + (f" totaling ${total:,.0f}" if total else "")
            )

        if state_tax_liens:
            total = sum(
                float(lien.get("amount") or 0) for lien in state_tax_liens
            )
            parts.append(
                f"- {len(state_tax_liens)} state tax lien(s)"
                + (f" totaling ${total:,.0f}" if total else "")
            )

        if bankruptcy_history:
            titles = [
                b.get("case_title") or "Unknown"
                for b in bankruptcy_history[:3]
            ]
            parts.append(
                f"- {len(bankruptcy_history)} bankruptcy case(s): "
                + "; ".join(titles)
            )

        if litigation_entries:
            parts.append(
                f"- {len(litigation_entries)} other litigation case(s)"
            )

        return "\n".join(parts)

    # ── Contact enrichment ─────────────────────────────────────────────────

    async def _enrich_entity_contacts(
        self,
        sos_result: dict[str, Any],
        entity_name: str,
        state: str,
    ) -> dict[str, Any]:
        """Enrich business contact info via People Data Labs / Hunter.io.

        Strategy:
        1. Extract a beneficial owner name from sos_result officers/managers
           (skip commercial registered agents).
        2. Call enrich_person(name, company=entity_name) on the People Data server.
        3. Extract phone, email, and company website from the result.
        4. If no email found but a website domain is known, try verify_email()
           with a guessed first.last@domain pattern.

        Returns a dict with keys ``website``, ``phone``, ``email`` (all nullable).
        On any failure returns an empty dict so the pipeline is never blocked.
        """
        empty: dict[str, Any] = {"website": None, "phone": None, "email": None}

        # Find the best person name to enrich
        person_name = self._pick_enrichable_person(sos_result)
        if not person_name:
            self.log.info(
                "contact_enrichment_skipped",
                reason="no_beneficial_owner_name",
                entity_name=entity_name,
            )
            return empty

        try:
            from aloha.mcp_servers.people_data.server import (
                create_people_data_server,
            )

            server = create_people_data_server()
        except (ValueError, ImportError) as exc:
            self.log.warning("people_data_server_unavailable", error=str(exc))
            return empty

        try:
            # ── Enrich person via PDL ────────────────────────────────
            pdl_result = await server.enrich_person(
                name=person_name, company=entity_name,
            )
            if pdl_result.get("error"):
                self.log.warning(
                    "pdl_enrich_error",
                    person=person_name,
                    error=pdl_result["error"],
                )
                return empty

            # Extract contact fields
            phone_numbers = pdl_result.get("phone_numbers") or []
            emails = pdl_result.get("emails") or []
            company_name = pdl_result.get("company")

            phone = phone_numbers[0] if phone_numbers else None
            email = emails[0] if emails else None
            website = self._derive_website(company_name, emails)

            # ── Fallback: guess email via Hunter.io ──────────────────
            if not email and website:
                guessed = self._guess_email(person_name, website)
                if guessed:
                    verify_result = await server.verify_email(guessed)
                    status = verify_result.get("status", "")
                    if status in ("valid", "accept_all"):
                        email = guessed
                        self.log.info(
                            "email_guessed_and_verified",
                            email=guessed,
                            status=status,
                        )

            self.log.info(
                "contact_enrichment_complete",
                entity_name=entity_name,
                person=person_name,
                has_phone=phone is not None,
                has_email=email is not None,
                has_website=website is not None,
            )
            return {"website": website, "phone": phone, "email": email}
        except Exception as exc:
            self.log.warning(
                "contact_enrichment_failed",
                entity_name=entity_name,
                error=str(exc),
            )
            return empty
        finally:
            await server.close()

    @staticmethod
    def _pick_enrichable_person(sos_result: dict[str, Any]) -> str | None:
        """Return the first non-commercial-RA person name from SOS data."""
        if not sos_result:
            return None
        for group_key in ("officers", "managers_members"):
            people = sos_result.get(group_key, [])
            for person in people:
                name = person.get("name", "")
                if name and not _is_commercial_ra(name):
                    return name.strip()
        # Fall back to registered agent if not commercial
        ra = sos_result.get("registered_agent")
        if ra and not _is_commercial_ra(ra):
            return ra.strip()
        return None

    @staticmethod
    def _derive_website(
        company_name: str | None,
        emails: list[str],
    ) -> str | None:
        """Derive a website URL from email domains or company name."""
        # Try to extract domain from email addresses
        for email in emails:
            if "@" in email:
                domain = email.split("@", 1)[1].lower()
                # Skip common webmail providers
                if domain not in {
                    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
                    "aol.com", "icloud.com", "protonmail.com", "mail.com",
                }:
                    return f"https://{domain}"
        return None

    @staticmethod
    def _guess_email(person_name: str, website: str) -> str | None:
        """Guess a business email from a person name and website domain.

        Uses first.last@domain pattern. Returns None if name cannot be split.
        """
        # Extract domain from website URL
        domain = website.replace("https://", "").replace("http://", "").strip("/")
        parts = person_name.strip().split()
        if len(parts) < 2:
            return None
        first = parts[0].lower()
        last = parts[-1].lower()
        # Strip non-alpha chars (suffixes like Jr., III, etc.)
        first = "".join(c for c in first if c.isalpha())
        last = "".join(c for c in last if c.isalpha())
        if not first or not last:
            return None
        return f"{first}.{last}@{domain}"

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
        ucc_filings: list[dict[str, Any]] | None = None,
        litigation_data: dict[str, Any] | None = None,
        contact_data: dict[str, Any] | None = None,
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
            lit = litigation_data or {}
            contacts = contact_data or {}
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
                ucc_filings=ucc_filings or None,
                federal_tax_liens=lit.get("federal_tax_liens") or None,
                state_tax_liens=lit.get("state_tax_liens") or None,
                bankruptcy_history=lit.get("bankruptcy_history") or None,
                litigation_summary=lit.get("litigation_summary") or None,
                pacer_results=lit.get("pacer_results") or None,
                website=contacts.get("website"),
                phone=contacts.get("phone"),
                email=contacts.get("email"),
                content_hash=hashlib.md5(
                    str(sorted(sos_result.items())).encode()
                ).hexdigest(),
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
