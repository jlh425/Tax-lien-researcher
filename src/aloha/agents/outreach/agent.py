"""Outreach Agent — orchestrates multi-channel owner outreach.

Responsibilities:
1. Check skip conditions (government owner, no contact info)
2. Select outreach channels based on available contact data
3. Choose templates and build personalised variables
4. Schedule outreach via OutreachService (DNC + frequency cap enforcement)
5. Advance parcel to 'outreach_scheduled'
"""

from __future__ import annotations

from typing import Any

import structlog

from aloha.agents.base import BaseAgent
from aloha.agents.outreach.tools import (
    build_template_variables,
    choose_template,
    format_outreach_summary,
    select_channels,
    should_skip_outreach,
)
from aloha.db.engine import async_session_factory
from aloha.db.repositories import OwnerRepository, ParcelRepository, QueueRepository

log = structlog.get_logger().bind(agent="outreach")


class OutreachAgent(BaseAgent):
    """Orchestrates multi-channel outreach to property owners.

    Context keys expected in ``run(context)``:
    - ``parcel_id``: APN (required)
    - ``owner_id``: Owner record ID (required)
    - ``user_id``: User UUID string (required, for outreach service)
    - ``state``: two-letter state abbreviation (required)
    - ``county``: county name in lowercase (required)
    - ``owner_name``: raw owner name (optional, loaded from DB if missing)
    - ``owner_type``: individual/llc/trust/etc (optional)
    - ``best_phone``: E.164 phone (optional, loaded from DB if missing)
    - ``best_email``: email address (optional, loaded from DB if missing)
    - ``property_address``: street address (optional)
    - ``tax_amount``: outstanding tax amount (optional)
    - ``sale_date``: auction date string (optional)
    - ``instrument_type``: lien_certificate/tax_deed (optional)
    - ``attempt_number``: outreach attempt number, default 1 (optional)
    """

    def __init__(self) -> None:
        super().__init__(name="outreach")

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "schedule_email",
                "description": "Schedule an email outreach via OutreachService.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "email": {"type": "string"},
                        "template_name": {"type": "string"},
                        "variables": {"type": "object"},
                    },
                    "required": ["email"],
                },
            },
            {
                "name": "schedule_sms",
                "description": "Schedule an SMS outreach via OutreachService.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "phone": {"type": "string"},
                        "template_name": {"type": "string"},
                        "variables": {"type": "object"},
                    },
                    "required": ["phone"],
                },
            },
            {
                "name": "check_skip",
                "description": "Check if outreach should be skipped for this owner.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "owner_type": {"type": "string"},
                        "best_phone": {"type": "string"},
                        "best_email": {"type": "string"},
                    },
                    "required": [],
                },
            },
        ]

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        parcel_id: str = context["parcel_id"]
        owner_id: int = context["owner_id"]
        user_id: str = context["user_id"]
        state: str = context["state"].upper()
        county: str = context["county"].lower()
        attempt_number: int = context.get("attempt_number", 1)

        self.log.info("outreach_started", parcel_id=parcel_id, owner_id=owner_id)

        # Load owner data from DB if not fully provided
        owner_data = await self._load_owner(owner_id)
        owner_name = context.get("owner_name") or owner_data.get("owner_name")
        owner_type = context.get("owner_type") or owner_data.get("owner_type")
        best_phone = context.get("best_phone") or owner_data.get("best_phone")
        best_email = context.get("best_email") or owner_data.get("best_email")
        property_address = context.get("property_address") or owner_data.get("address")

        # Step 1: Check if outreach should be skipped
        skip_check = should_skip_outreach(
            owner_type=owner_type,
            best_phone=best_phone,
            best_email=best_email,
        )
        if skip_check["skip"]:
            self.log.info("outreach_skipped", parcel_id=parcel_id, reason=skip_check["reason"])
            return {
                "status": "skipped",
                "parcel_id": parcel_id,
                "reason": skip_check["reason"],
            }

        # Step 2: Select channels
        channels = select_channels(
            best_phone=best_phone,
            best_email=best_email,
            owner_type=owner_type,
            reachability_score=owner_data.get("reachability_score", 0),
        )

        # Step 3: Build template variables
        variables = build_template_variables(
            owner_name=owner_name,
            property_address=property_address,
            county=county,
            state=state,
            tax_amount=context.get("tax_amount"),
            sale_date=context.get("sale_date"),
            instrument_type=context.get("instrument_type"),
        )

        # Step 4: Schedule outreach for each channel
        results: list[dict[str, Any]] = []
        for channel in channels:
            template_name = choose_template(
                channel=channel,
                instrument_type=context.get("instrument_type"),
                attempt_number=attempt_number,
            )
            contact_value = best_email if channel == "email" else best_phone

            result = await self._schedule_channel(
                user_id=user_id,
                parcel_id=parcel_id,
                owner_id=owner_id,
                channel=channel,
                contact_value=contact_value,
                template_name=template_name,
                variables=variables,
            )
            results.append(result)

        # Step 5: Advance parcel and summarise
        summary = format_outreach_summary(results)
        if summary["scheduled"] > 0:
            await self._advance_parcel(parcel_id)

        self.log.info(
            "outreach_complete",
            parcel_id=parcel_id,
            owner_id=owner_id,
            scheduled=summary["scheduled"],
            skipped=summary["skipped"],
        )
        return {
            "status": "complete",
            "parcel_id": parcel_id,
            "owner_id": owner_id,
            "summary": summary,
        }

    # -- Scheduling helpers ----------------------------------------------------

    async def _schedule_channel(
        self,
        *,
        user_id: str,
        parcel_id: str,
        owner_id: int,
        channel: str,
        contact_value: str | None,
        template_name: str,
        variables: dict[str, str],
    ) -> dict[str, Any]:
        """Schedule outreach for a single channel via OutreachService."""
        if not contact_value:
            return {"channel": channel, "status": "skipped", "reason": "no contact value"}

        try:
            from aloha.services.outreach_service import OutreachService

            async with async_session_factory() as session:
                service = OutreachService(session)
                outreach_id = await service.schedule_outreach(
                    user_id=user_id,
                    parcel_id=parcel_id,
                    owner_id=owner_id,
                    channel=channel,
                    contact_value=contact_value,
                    template_name=template_name,
                    variables=variables,
                )
                await session.commit()

            self.log.info(
                "channel_scheduled",
                channel=channel,
                outreach_id=outreach_id,
                contact_value=contact_value[:3] + "***",
            )
            return {
                "channel": channel,
                "status": "scheduled",
                "outreach_id": outreach_id,
            }
        except Exception as exc:
            self.log.warning(
                "channel_schedule_failed",
                channel=channel,
                error=str(exc),
            )
            return {
                "channel": channel,
                "status": "failed" if "blocked" not in str(exc).lower() else "skipped",
                "reason": str(exc) if "blocked" in str(exc).lower() else None,
                "error": str(exc) if "blocked" not in str(exc).lower() else None,
            }

    # -- DB helpers ------------------------------------------------------------

    async def _load_owner(self, owner_id: int) -> dict[str, Any]:
        """Load owner contact info and related parcel data from DB."""
        async with async_session_factory() as session:
            owner_repo = OwnerRepository(session)
            parcel_repo = ParcelRepository(session)

            owner = await owner_repo.get(owner_id)
            if not owner:
                return {}

            address = None
            parcel = await parcel_repo.get(owner.parcel_id)
            if parcel:
                address = parcel.address

            return {
                "owner_name": owner.owner_of_record,
                "owner_type": owner.owner_type,
                "best_phone": owner.best_phone,
                "best_email": owner.best_email,
                "address": address,
                "reachability_score": owner.research_depth or 0,
            }

    async def _advance_parcel(self, parcel_id: str) -> None:
        """Advance parcel status to 'outreach_scheduled'."""
        async with async_session_factory() as session:
            parcel_repo = ParcelRepository(session)
            parcel = await parcel_repo.get(parcel_id)
            if parcel:
                parcel.research_status = "outreach_scheduled"
            await session.commit()


# -- Module-level singleton ----------------------------------------------------

agent = OutreachAgent()
