"""Parcel service — list, detail, and search with efficient eager loading."""

from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from aloha.api.schemas.parcels import (
    OwnerOut,
    ParcelDetail,
    ParcelSummary,
    PropertyImageOut,
    ScoreOut,
    TaxLienOut,
)
from aloha.db.models.document_chunk import DocumentChunk
from aloha.db.models.owner import Owner
from aloha.db.models.parcel import Parcel
from aloha.db.models.property_image import PropertyImage
from aloha.db.models.score import Score
from aloha.db.models.tax_lien import TaxLien
from aloha.services.base import BaseService


class ParcelService(BaseService):
    """Business logic for parcel listing and detail assembly."""

    # ── Public API ───────────────────────────────────────────────────────

    async def list_parcels(
        self,
        *,
        state: str | None = None,
        county: str | None = None,
        instrument_type: str | None = None,
        research_status: str | None = None,
        min_score: int | None = None,
        is_absentee: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ParcelSummary]:
        """List parcels with optional filtering using eager loading (no N+1)."""
        stmt = (
            select(Parcel)
            .options(
                selectinload(Parcel.tax_liens),
                selectinload(Parcel.owners),
                selectinload(Parcel.scores),
            )
        )

        if state:
            stmt = stmt.where(Parcel.state == state.upper())
        if county:
            stmt = stmt.where(Parcel.county == county.lower())
        if research_status:
            stmt = stmt.where(Parcel.research_status == research_status)

        stmt = stmt.order_by(
            Parcel.last_crawled_at.desc().nullslast(),
        ).offset(offset).limit(limit)

        result = await self._session.execute(stmt)
        parcels = result.scalars().unique().all()

        summaries: list[ParcelSummary] = []
        for parcel in parcels:
            # Latest lien (by tax_year descending)
            liens = sorted(
                parcel.tax_liens,
                key=lambda l: l.tax_year or 0,
                reverse=True,
            )
            lien = liens[0] if liens else None

            # Latest score (by scored_at descending)
            scores = sorted(
                parcel.scores,
                key=lambda s: s.scored_at,
                reverse=True,
            )
            score = scores[0] if scores else None

            # First owner for absentee check
            owner = parcel.owners[0] if parcel.owners else None

            # Apply post-load filters
            if instrument_type and lien and lien.instrument_type != instrument_type:
                continue
            if min_score is not None and (not score or (score.overall_score or 0) < min_score):
                continue
            if is_absentee is not None and owner and owner.is_absentee != is_absentee:
                continue

            summaries.append(
                ParcelSummary(
                    parcel_id=parcel.parcel_id,
                    state=parcel.state,
                    county=parcel.county,
                    address=parcel.address,
                    property_type=parcel.property_type,
                    zoning=parcel.zoning,
                    acreage=float(parcel.acreage) if parcel.acreage else None,
                    assessed_total=parcel.assessed_total,
                    research_status=parcel.research_status,
                    data_freshness=parcel.data_freshness,
                    latitude=float(parcel.latitude) if parcel.latitude else None,
                    longitude=float(parcel.longitude) if parcel.longitude else None,
                    instrument_type=lien.instrument_type if lien else None,
                    lien_status=lien.lien_status if lien else None,
                    total_owed=float(lien.total_owed) if lien and lien.total_owed else None,
                    redemption_deadline=lien.redemption_deadline if lien else None,
                    auction_date=lien.auction_date if lien else None,
                    overall_score=score.overall_score if score else None,
                    risk_flags=list(score.risk_flags) if score and score.risk_flags else None,
                ),
            )

        return summaries

    async def get_parcel_detail(self, parcel_id: str) -> ParcelDetail:
        """Retrieve full parcel detail including liens, owners, scores, images."""
        stmt = (
            select(Parcel)
            .where(Parcel.parcel_id == parcel_id)
            .options(
                selectinload(Parcel.tax_liens),
                selectinload(Parcel.owners),
                selectinload(Parcel.scores),
                selectinload(Parcel.property_images),
            )
        )
        result = await self._session.execute(stmt)
        parcel = result.scalars().first()

        if parcel is None:
            raise HTTPException(status_code=404, detail=f"Parcel {parcel_id!r} not found")

        # Sort relations
        liens = sorted(parcel.tax_liens, key=lambda l: l.tax_year or 0, reverse=True)
        scores = sorted(parcel.scores, key=lambda s: s.scored_at, reverse=True)

        # Load vision analysis condition summary
        chunk_stmt = (
            select(DocumentChunk)
            .where(
                DocumentChunk.parcel_id == parcel_id,
                DocumentChunk.source_type == "vision_analysis",
            )
            .order_by(DocumentChunk.created_at.desc())
            .limit(1)
        )
        chunk_result = await self._session.execute(chunk_stmt)
        vision_chunk = chunk_result.scalars().first()
        condition_summary = (
            self._extract_condition_summary(vision_chunk.content)
            if vision_chunk
            else None
        )

        return ParcelDetail(
            parcel_id=parcel.parcel_id,
            user_id=parcel.user_id,
            state=parcel.state,
            county=parcel.county,
            address=parcel.address,
            address_normalized=parcel.address_normalized,
            legal_description=parcel.legal_description,
            acreage=float(parcel.acreage) if parcel.acreage else None,
            land_use_code=parcel.land_use_code,
            property_type=parcel.property_type,
            zoning=parcel.zoning,
            zoning_notes=parcel.zoning_notes,
            assessed_land_val=parcel.assessed_land_val,
            assessed_impr_val=parcel.assessed_impr_val,
            assessed_total=parcel.assessed_total,
            market_value_est=parcel.market_value_est,
            last_sale_date=parcel.last_sale_date,
            last_sale_price=parcel.last_sale_price,
            year_built=parcel.year_built,
            latitude=float(parcel.latitude) if parcel.latitude else None,
            longitude=float(parcel.longitude) if parcel.longitude else None,
            research_status=parcel.research_status,
            data_freshness=parcel.data_freshness,
            last_crawled_at=parcel.last_crawled_at,
            created_at=parcel.created_at,
            updated_at=parcel.updated_at,
            tax_liens=[self._to_lien_out(l) for l in liens],
            owners=[self._to_owner_out(o) for o in parcel.owners],
            scores=[self._to_score_out(s) for s in scores],
            images=[PropertyImageOut.model_validate(img) for img in parcel.property_images],
            condition_summary=condition_summary,
        )

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _extract_condition_summary(content: str) -> str:
        """Extract human-readable summary from a vision analysis JSON blob."""
        try:
            summary = json.loads(content).get("summary", "")
            if summary:
                return summary
        except Exception:
            pass
        return content[:200]

    @staticmethod
    def _to_lien_out(lien: TaxLien) -> TaxLienOut:
        return TaxLienOut(
            id=lien.id,
            instrument_type=lien.instrument_type,
            lien_status=lien.lien_status,
            tax_year=lien.tax_year,
            years_delinquent=lien.years_delinquent,
            principal_amount=float(lien.principal_amount),
            interest_amount=float(lien.interest_amount) if lien.interest_amount else None,
            penalty_amount=float(lien.penalty_amount) if lien.penalty_amount else None,
            total_owed=float(lien.total_owed) if lien.total_owed else None,
            filing_date=lien.filing_date,
            redemption_deadline=lien.redemption_deadline,
            certificate_number=lien.certificate_number,
            certificate_interest_rate=(
                float(lien.certificate_interest_rate)
                if lien.certificate_interest_rate
                else None
            ),
            auction_date=lien.auction_date,
            auction_platform=lien.auction_platform,
            auction_url=lien.auction_url,
            opening_bid=float(lien.opening_bid) if lien.opening_bid else None,
            post_sale_redemption_days=lien.post_sale_redemption_days,
            title_risk_level=lien.title_risk_level,
            source_url=lien.source_url,
            retrieved_at=lien.retrieved_at,
        )

    @staticmethod
    def _to_owner_out(owner: Owner) -> OwnerOut:
        return OwnerOut(
            id=owner.id,
            owner_of_record=owner.owner_of_record,
            owner_type=owner.owner_type,
            mailing_address=owner.mailing_address,
            mailing_city=owner.mailing_city,
            mailing_state=owner.mailing_state,
            mailing_zip=owner.mailing_zip,
            is_absentee=owner.is_absentee,
            deed_type=owner.deed_type,
            beneficial_owner=owner.beneficial_owner,
            beneficial_owner_confidence=owner.beneficial_owner_confidence,
            best_phone=owner.best_phone,
            best_email=owner.best_email,
            research_depth=owner.research_depth,
        )

    @staticmethod
    def _to_score_out(score: Score) -> ScoreOut:
        return ScoreOut(
            id=score.id,
            instrument_type=score.instrument_type,
            overall_score=score.overall_score,
            score_model_version=score.score_model_version,
            property_potential=score.property_potential,
            risk_score=score.risk_score,
            lien_to_value_ratio=(
                float(score.lien_to_value_ratio) if score.lien_to_value_ratio else None
            ),
            certificate_rate=float(score.certificate_rate) if score.certificate_rate else None,
            redemption_urgency=score.redemption_urgency,
            owner_motivation=score.owner_motivation,
            contact_reachability=score.contact_reachability,
            arv_estimate=float(score.arv_estimate) if score.arv_estimate else None,
            opening_bid=float(score.opening_bid) if score.opening_bid else None,
            arv_to_bid_ratio=float(score.arv_to_bid_ratio) if score.arv_to_bid_ratio else None,
            title_clarity=score.title_clarity,
            condition_risk=score.condition_risk,
            competition_risk=score.competition_risk,
            post_sale_redemption_risk=score.post_sale_redemption_risk,
            risk_flags=list(score.risk_flags) if score.risk_flags else None,
            score_rationale=score.score_rationale,
            scored_at=score.scored_at,
        )
