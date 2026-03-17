"""Parcel API routes — list, detail, and search endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aloha.api.deps import get_current_user, get_db
from aloha.api.schemas.parcels import (
    ParcelDetail,
    ParcelSearchParams,
    ParcelSummary,
    PropertyImageOut,
)
from aloha.db.models.owner import Owner
from aloha.db.models.parcel import Parcel
from aloha.db.models.score import Score
from aloha.db.models.tax_lien import TaxLien

router = APIRouter(prefix="/parcels", tags=["parcels"])


@router.get("", response_model=list[ParcelSummary])
async def list_parcels(
    state: str | None = Query(None),
    county: str | None = Query(None),
    instrument_type: str | None = Query(None),
    status: str | None = Query(None, alias="research_status"),
    min_score: int | None = Query(None, ge=0, le=100),
    is_absentee: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: Annotated[None, Depends(get_current_user)] = None,
) -> list[ParcelSummary]:
    """List parcels with optional filtering.

    Returns lightweight summary objects for the card list view.
    """
    stmt = select(Parcel)

    if state:
        stmt = stmt.where(Parcel.state == state.upper())
    if county:
        stmt = stmt.where(Parcel.county == county.lower())
    if status:
        stmt = stmt.where(Parcel.research_status == status)

    stmt = stmt.order_by(Parcel.last_crawled_at.desc().nullslast()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    parcels = result.scalars().all()

    summaries: list[ParcelSummary] = []
    for parcel in parcels:
        # Load latest lien
        lien_stmt = (
            select(TaxLien)
            .where(TaxLien.parcel_id == parcel.parcel_id)
            .order_by(TaxLien.tax_year.desc().nullslast())
            .limit(1)
        )
        lien_result = await db.execute(lien_stmt)
        lien = lien_result.scalars().first()

        # Load latest score
        score_stmt = (
            select(Score)
            .where(Score.parcel_id == parcel.parcel_id)
            .order_by(Score.scored_at.desc())
            .limit(1)
        )
        score_result = await db.execute(score_stmt)
        score = score_result.scalars().first()

        # Apply instrument / score / absentee filters that need joined data
        if instrument_type and lien and lien.instrument_type != instrument_type:
            continue
        if min_score is not None and (not score or (score.overall_score or 0) < min_score):
            continue

        if is_absentee is not None:
            owner_stmt = (
                select(Owner)
                .where(Owner.parcel_id == parcel.parcel_id)
                .limit(1)
            )
            owner_result = await db.execute(owner_stmt)
            owner = owner_result.scalars().first()
            if owner and owner.is_absentee != is_absentee:
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
            )
        )

    return summaries


@router.get("/{parcel_id}", response_model=ParcelDetail)
async def get_parcel(
    parcel_id: str,
    db: AsyncSession = Depends(get_db),
    _user: Annotated[None, Depends(get_current_user)] = None,
) -> ParcelDetail:
    """Retrieve full parcel detail including liens, owners, and scores."""
    parcel = await db.get(Parcel, parcel_id)
    if parcel is None:
        raise HTTPException(status_code=404, detail=f"Parcel {parcel_id!r} not found")

    # Eagerly load related records
    liens_result = await db.execute(
        select(TaxLien)
        .where(TaxLien.parcel_id == parcel_id)
        .order_by(TaxLien.tax_year.desc().nullslast())
    )
    liens = liens_result.scalars().all()

    owners_result = await db.execute(
        select(Owner).where(Owner.parcel_id == parcel_id)
    )
    owners = owners_result.scalars().all()

    scores_result = await db.execute(
        select(Score)
        .where(Score.parcel_id == parcel_id)
        .order_by(Score.scored_at.desc())
    )
    scores = scores_result.scalars().all()

    # Load property images and latest vision analysis condition summary
    from aloha.db.repositories.image import DocumentChunkRepository, PropertyImageRepository

    image_repo = PropertyImageRepository(db)
    images = await image_repo.get_by_parcel(parcel_id)

    chunk_repo = DocumentChunkRepository(db)
    chunks = await chunk_repo.get_by_parcel(parcel_id)
    vision_chunks = [c for c in chunks if c.source_type == "vision_analysis"]
    condition_summary = vision_chunks[-1].content if vision_chunks else None

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
        tax_liens=[_lien_out(l) for l in liens],
        owners=[_owner_out(o) for o in owners],
        scores=[_score_out(s) for s in scores],
        images=[PropertyImageOut.model_validate(img) for img in images],
        condition_summary=condition_summary,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _lien_out(lien: TaxLien):  # type: ignore[return]
    from aloha.api.schemas.parcels import TaxLienOut
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
        certificate_interest_rate=float(lien.certificate_interest_rate) if lien.certificate_interest_rate else None,
        auction_date=lien.auction_date,
        auction_platform=lien.auction_platform,
        auction_url=lien.auction_url,
        opening_bid=float(lien.opening_bid) if lien.opening_bid else None,
        post_sale_redemption_days=lien.post_sale_redemption_days,
        title_risk_level=lien.title_risk_level,
        source_url=lien.source_url,
        retrieved_at=lien.retrieved_at,
    )


def _owner_out(owner: Owner):  # type: ignore[return]
    from aloha.api.schemas.parcels import OwnerOut
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


def _score_out(score: Score):  # type: ignore[return]
    from aloha.api.schemas.parcels import ScoreOut
    return ScoreOut(
        id=score.id,
        instrument_type=score.instrument_type,
        overall_score=score.overall_score,
        score_model_version=score.score_model_version,
        property_potential=score.property_potential,
        risk_score=score.risk_score,
        lien_to_value_ratio=float(score.lien_to_value_ratio) if score.lien_to_value_ratio else None,
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
