"""Scoring Agent — produces an instrument-aware investment opportunity score.

Responsibilities:
1. Load parcel, tax lien, and owner records from the DB
2. Select the correct scoring model (lien certificate vs. tax deed)
3. Run the model to produce a ScoringResult
4. Persist the Score record
5. Advance parcel research_status to 'scored'
6. Enqueue the parcel for Report Agent
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select

from aloha.agents.base import BaseAgent
from aloha.agents.discovery.state_registry import get_state_info
from aloha.agents.scoring.models import ScoringResult, score_lien_certificate, score_tax_deed
from aloha.db.engine import async_session_factory
from aloha.db.models.owner import OwnerEntity
from aloha.db.models.score import Score
from aloha.db.repositories import (
    EntityRepository,
    ParcelRepository,
    QueueRepository,
    TaxLienRepository,
)
from aloha.db.repositories.owner import OwnerRepository

log = structlog.get_logger().bind(agent="scoring")


class ScoringAgent(BaseAgent):
    """Scores a fully-researched parcel using the instrument-appropriate model.

    Context keys expected in ``run(context)``:
    - ``parcel_id``: APN / assessor parcel number (required)
    - ``state``: two-letter state abbreviation (required)
    - ``county``: county name in lowercase (required)
    """

    def __init__(self) -> None:
        super().__init__(name="scoring")

    def get_tools(self) -> list[dict[str, Any]]:
        return []  # Scoring is deterministic — no LLM tools needed

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        parcel_id: str = context["parcel_id"]
        state: str = context["state"].upper()
        county: str = context["county"].lower()

        self.log.info("scoring_started", parcel_id=parcel_id, state=state)

        # ── Load data ─────────────────────────────────────────────────────
        parcel_dict, lien_dict, owner_dict, entity_dict = await self._load_data(
            parcel_id,
        )

        if not lien_dict:
            self.log.warning("no_lien_found", parcel_id=parcel_id)
            return {"status": "skipped", "reason": "no_lien_record", "parcel_id": parcel_id}

        # ── Select model ──────────────────────────────────────────────────
        instrument_type = lien_dict.get("instrument_type", "lien_certificate")
        state_info = get_state_info(state)

        if instrument_type == "tax_deed":
            post_sale_days = state_info.post_sale_redemption_days if state_info else 0
            result = score_tax_deed(
                parcel_dict,
                lien_dict,
                owner_dict,
                post_sale_days,
                entity_data=entity_dict,
            )
        else:
            cert_cap = state_info.cert_rate_cap if state_info else None
            result = score_lien_certificate(
                parcel_dict,
                lien_dict,
                owner_dict,
                cert_cap,
                entity_data=entity_dict,
            )

        # ── Persist ───────────────────────────────────────────────────────
        score_id = await self._persist(parcel_id, result, state, county)

        self.log.info(
            "scoring_complete",
            parcel_id=parcel_id,
            instrument=result.instrument_type,
            score=result.overall_score,
            flags=result.risk_flags,
        )
        return {
            "status": "complete",
            "parcel_id": parcel_id,
            "score_id": score_id,
            "instrument_type": result.instrument_type,
            "overall_score": result.overall_score,
            "risk_flags": result.risk_flags,
        }

    # ── Data loading ──────────────────────────────────────────────────────

    async def _load_data(
        self, parcel_id: str
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any] | None]:
        """Load parcel, most recent lien, primary owner, and linked entity.

        Returns:
            (parcel_dict, lien_dict, owner_dict, entity_dict_or_None)
        """
        async with async_session_factory() as session:
            parcel_repo = ParcelRepository(session)
            lien_repo = TaxLienRepository(session)
            owner_repo = OwnerRepository(session)
            entity_repo = EntityRepository(session)

            parcel = await parcel_repo.get(parcel_id)
            parcel_dict = _model_to_dict(parcel) if parcel else {}

            liens = await lien_repo.get_by_parcel(parcel_id)
            # Pick the most recent / most complete lien
            lien = _pick_best_lien(liens)
            lien_dict = _model_to_dict(lien) if lien else {}

            owners = await owner_repo.get_by_parcel(parcel_id)
            owner = owners[0] if owners else None
            owner_dict = _model_to_dict(owner) if owner else {}

            # Load linked entity via OwnerEntity join table
            entity_dict: dict[str, Any] | None = None
            if owner and owner.id:
                stmt = (
                    select(OwnerEntity.entity_id).where(OwnerEntity.owner_id == owner.id).limit(1)
                )
                row = (await session.execute(stmt)).scalar_one_or_none()
                if row:
                    entity = await entity_repo.get(row)
                    entity_dict = _model_to_dict(entity) if entity else None

        return parcel_dict, lien_dict, owner_dict, entity_dict

    # ── Persistence ───────────────────────────────────────────────────────

    async def _persist(
        self,
        parcel_id: str,
        result: ScoringResult,
        state: str,
        county: str,
    ) -> int | None:
        now = datetime.now(tz=UTC)

        async with async_session_factory() as session:
            parcel_repo = ParcelRepository(session)
            queue_repo = QueueRepository(session)

            score = Score(
                parcel_id=parcel_id,
                instrument_type=result.instrument_type,
                overall_score=result.overall_score,
                score_model_version=result.score_model_version,
                property_potential=result.property_potential,
                risk_score=result.risk_score,
                # Lien cert factors
                lien_to_value_ratio=result.lien_to_value_ratio,
                certificate_rate=result.certificate_rate,
                years_delinquent=result.years_delinquent,
                owner_motivation=result.owner_motivation,
                contact_reachability=result.contact_reachability,
                redemption_urgency=result.redemption_urgency,
                # Deed factors
                arv_estimate=result.arv_estimate,
                opening_bid=result.opening_bid,
                arv_to_bid_ratio=result.arv_to_bid_ratio,
                title_clarity=result.title_clarity,
                condition_risk=result.condition_risk,
                competition_risk=result.competition_risk,
                post_sale_redemption_risk=result.post_sale_redemption_risk,
                # Output
                risk_flags=result.risk_flags or None,
                flags_detail=result.flags_detail or None,
                score_rationale=result.score_rationale,
                scored_at=now,
            )
            session.add(score)

            # Advance parcel status
            parcel = await parcel_repo.get(parcel_id)
            if parcel:
                parcel.research_status = "scored"

            # Enqueue report generation
            await queue_repo.enqueue(
                agent_name="report",
                stage="report",
                parcel_id=parcel_id,
                payload={"parcel_id": parcel_id, "state": state, "county": county},
                priority=5,
            )

            await session.flush()
            score_id = score.id
            await session.commit()

        return score_id


# ── Module-level singleton ─────────────────────────────────────────────────────

agent = ScoringAgent()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _model_to_dict(obj: Any) -> dict[str, Any]:
    """Convert a SQLAlchemy model instance to a plain dict."""
    if obj is None:
        return {}
    result = {}
    for col in obj.__table__.columns:
        result[col.name] = getattr(obj, col.name, None)
    return result


def _pick_best_lien(liens: Any) -> Any:
    """Return the most relevant lien: prefer active with latest tax_year."""
    if not liens:
        return None
    active = [lien for lien in liens if getattr(lien, "lien_status", "") == "active"]
    pool = active if active else list(liens)
    # Sort by tax_year descending, None last
    pool.sort(key=lambda lien: getattr(lien, "tax_year", None) or 0, reverse=True)
    return pool[0]
