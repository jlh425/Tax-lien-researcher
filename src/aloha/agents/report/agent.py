"""Report Agent — compiles a structured investment report for a scored parcel.

Responsibilities:
1. Load all research data for a parcel (parcel, liens, owners, score, entity)
2. Use the LLM to synthesise a narrative investment memo
3. Emit structured report sections: summary, property details, owner analysis,
   lien/deed details, score breakdown, risk flags, recommended action
4. Advance parcel research_status to 'complete'
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from aloha.agents.base import BaseAgent
from aloha.agents.report.prompts import REPORT_SYSTEM_PROMPT, build_report_task
from aloha.db.engine import async_session_factory
from aloha.db.repositories import ParcelRepository, TaxLienRepository
from aloha.db.repositories.owner import OwnerRepository

log = structlog.get_logger().bind(agent="report")


class ReportAgent(BaseAgent):
    """Generates a per-parcel investment memo from all accumulated research.

    Context keys expected in ``run(context)``:
    - ``parcel_id``: APN / assessor parcel number (required)
    - ``state``: two-letter state abbreviation (required)
    - ``county``: county name (required)
    """

    def __init__(self) -> None:
        super().__init__(name="report")

    def get_tools(self) -> list[dict[str, Any]]:
        return []  # Report is LLM-driven narrative, no tool calls needed

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        parcel_id: str = context["parcel_id"]
        state: str = context["state"].upper()
        county: str = context["county"].lower()

        self.log.info("report_started", parcel_id=parcel_id)

        # ── Load all research data ────────────────────────────────────────
        data = await self._load_all_data(parcel_id)
        if not data["parcel"]:
            self.log.warning("parcel_not_found", parcel_id=parcel_id)
            return {"status": "failed", "reason": "parcel_not_found"}

        # ── Build report sections ─────────────────────────────────────────
        report = self._compile_report(data, state, county)
        if data.get("property_condition"):
            report["property_condition"] = data["property_condition"]

        # ── LLM narrative (optional — only if model configured) ──────────
        try:
            report["narrative"] = await self._generate_narrative(data, report)
        except Exception as exc:
            self.log.warning("narrative_generation_failed", error=str(exc))
            report["narrative"] = _fallback_narrative(data, report)

        # ── Persist and advance status ─────────────────────────────────────
        await self._complete_parcel(parcel_id)

        self.log.info(
            "report_complete",
            parcel_id=parcel_id,
            overall_score=(report.get("score") or {}).get("overall_score"),
            recommended_action=report.get("recommended_action"),
        )
        return {
            "status": "complete",
            "parcel_id": parcel_id,
            "report": report,
        }

    # ── Data loading ──────────────────────────────────────────────────────

    async def _load_all_data(self, parcel_id: str) -> dict[str, Any]:
        async with async_session_factory() as session:
            parcel_repo = ParcelRepository(session)
            lien_repo = TaxLienRepository(session)
            owner_repo = OwnerRepository(session)

            parcel = await parcel_repo.get(parcel_id)
            liens = await lien_repo.get_by_parcel(parcel_id)
            owners = await owner_repo.get_by_parcel(parcel_id)

            # Latest score — load separately
            from sqlalchemy import select

            from aloha.db.models.score import Score

            score_result = await session.execute(
                select(Score)
                .where(Score.parcel_id == parcel_id)
                .order_by(Score.scored_at.desc())
                .limit(1)
            )
            score = score_result.scalars().first()

            # Load latest vision analysis condition summary from DocumentChunks
            from aloha.db.repositories.image import DocumentChunkRepository

            chunk_repo = DocumentChunkRepository(session)
            chunks = await chunk_repo.get_by_parcel(parcel_id)
            vision_chunks = [c for c in chunks if c.source_type == "vision_analysis"]
            condition_summary = (
                _extract_condition_summary(vision_chunks[-1].content) if vision_chunks else None
            )

        return {
            "parcel": _obj_to_dict(parcel),
            "liens": [_obj_to_dict(lien) for lien in liens],
            "owners": [_obj_to_dict(o) for o in owners],
            "score": _obj_to_dict(score),
            "property_condition": condition_summary,
        }

    # ── Report compilation ────────────────────────────────────────────────

    def _compile_report(self, data: dict[str, Any], state: str, county: str) -> dict[str, Any]:
        """Build structured report sections without LLM."""
        parcel = data["parcel"]
        liens = data["liens"]
        owners = data["owners"]
        score = data["score"]

        lien = liens[0] if liens else {}
        owner = owners[0] if owners else {}

        instrument_type = lien.get("instrument_type", "lien_certificate")
        overall_score = score.get("overall_score")

        # Recommended action based on score
        if overall_score is None:
            action = "pending_scoring"
        elif overall_score >= 75:
            action = "high_priority_buy"
        elif overall_score >= 55:
            action = "research_further"
        elif overall_score >= 35:
            action = "monitor"
        else:
            action = "pass"

        return {
            "parcel_id": parcel.get("parcel_id"),
            "generated_at": datetime.now(tz=UTC).isoformat(),
            "instrument_type": instrument_type,
            "recommended_action": action,
            "property": {
                "address": parcel.get("address"),
                "county": county,
                "state": state,
                "property_type": parcel.get("property_type"),
                "zoning": parcel.get("zoning"),
                "acreage": parcel.get("acreage"),
                "year_built": parcel.get("year_built"),
                "assessed_total": parcel.get("assessed_total"),
                "market_value_est": parcel.get("market_value_est"),
                "legal_description": parcel.get("legal_description"),
            },
            "lien": {
                "instrument_type": lien.get("instrument_type"),
                "lien_status": lien.get("lien_status"),
                "tax_year": lien.get("tax_year"),
                "principal_amount": lien.get("principal_amount"),
                "total_owed": lien.get("total_owed"),
                "certificate_interest_rate": lien.get("certificate_interest_rate"),
                "redemption_deadline": str(lien.get("redemption_deadline") or ""),
                "auction_date": str(lien.get("auction_date") or ""),
                "auction_platform": lien.get("auction_platform"),
                "opening_bid": lien.get("opening_bid"),
                "source_url": lien.get("source_url"),
            },
            "owner": {
                "owner_of_record": owner.get("owner_of_record"),
                "owner_type": owner.get("owner_type"),
                "is_absentee": owner.get("is_absentee"),
                "mailing_address": owner.get("mailing_address"),
                "beneficial_owner": owner.get("beneficial_owner"),
                "beneficial_owner_confidence": owner.get("beneficial_owner_confidence"),
                "best_phone": owner.get("best_phone"),
                "best_email": owner.get("best_email"),
            },
            "score": {
                "overall_score": overall_score,
                "instrument_type": score.get("instrument_type"),
                "model_version": score.get("score_model_version"),
                "risk_flags": score.get("risk_flags") or [],
                "score_rationale": score.get("score_rationale"),
                "property_potential": score.get("property_potential"),
                "risk_score": score.get("risk_score"),
            },
        }

    async def _generate_narrative(self, data: dict[str, Any], report: dict[str, Any]) -> str:
        """Use the LLM to produce a human-readable investment memo."""
        from pydantic_ai import Agent

        pydantic_agent = Agent(
            model=self.model,
            system_prompt=REPORT_SYSTEM_PROMPT,
        )
        task = build_report_task(data, report)
        result = await pydantic_agent.run(task)
        return result.output

    # ── Persistence ───────────────────────────────────────────────────────

    async def _complete_parcel(self, parcel_id: str) -> None:
        async with async_session_factory() as session:
            parcel_repo = ParcelRepository(session)
            parcel = await parcel_repo.get(parcel_id)
            if parcel:
                parcel.research_status = "complete"
            await session.commit()


# ── Module-level singleton ─────────────────────────────────────────────────────

agent = ReportAgent()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _extract_condition_summary(content: str) -> str:
    """Extract the human-readable summary from a vision analysis JSON blob."""
    import json

    try:
        summary = json.loads(content).get("summary", "")
        if summary:
            return summary
    except (json.JSONDecodeError, TypeError, AttributeError) as e:
        log.warning(
            "condition_summary_parse_failed",
            error=str(e),
            content_length=len(content) if content else 0,
        )
    return content[:200]


def _obj_to_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    result = {}
    for col in obj.__table__.columns:
        result[col.name] = getattr(obj, col.name, None)
    return result


def _fallback_narrative(data: dict[str, Any], report: dict[str, Any]) -> str:
    """Generate a minimal narrative without LLM when model is unavailable."""
    try:
        prop = report.get("property") if isinstance(report.get("property"), dict) else {}
        lien = report.get("lien") if isinstance(report.get("lien"), dict) else {}
        score = report.get("score") if isinstance(report.get("score"), dict) else {}
        owner = report.get("owner") if isinstance(report.get("owner"), dict) else {}

        instrument_type = report.get("instrument_type") or "N/A"
        action = report.get("recommended_action") or "N/A"

        # Format total_owed safely — it might be non-numeric
        total_owed = lien.get("total_owed")
        amount_line = ""
        if total_owed is not None:
            try:
                amount_line = f"Amount Owed: ${float(total_owed):,.2f}"
            except (ValueError, TypeError):
                amount_line = f"Amount Owed: {total_owed}"

        risk_flags = score.get("risk_flags")
        if not isinstance(risk_flags, list):
            risk_flags = []

        parts = [
            f"INVESTMENT MEMO — {report.get('parcel_id', 'N/A')}",
            f"Address: {prop.get('address', 'Unknown')}",
            f"Instrument: {str(instrument_type).replace('_', ' ').title()}",
            f"Score: {score.get('overall_score', 'N/A')}/100",
            f"Action: {str(action).replace('_', ' ').upper()}",
            "",
            f"Owner: {owner.get('owner_of_record', 'N/A')} ({owner.get('owner_type', 'N/A')})",
            f"Absentee: {owner.get('is_absentee', 'Unknown')}",
            "",
            amount_line,
            f"Risk Flags: {', '.join(str(f) for f in risk_flags) or 'None'}",
        ]
        return "\n".join(p for p in parts if p is not None)
    except Exception as exc:
        log.warning("fallback_narrative_failed", error=str(exc))
        return f"INVESTMENT MEMO — {report.get('parcel_id', 'N/A')} (report error)"
