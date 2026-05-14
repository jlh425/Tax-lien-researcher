"""Parcel API routes — list, detail, and search endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Query

from aloha.api.deps import get_current_user, get_db
from aloha.api.schemas.parcels import ParcelDetail, ParcelSummary
from aloha.services.parcel_service import ParcelService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/parcels", tags=["parcels"])


def _parcel_service(db: AsyncSession = Depends(get_db)) -> ParcelService:
    return ParcelService(db)


@router.get("", response_model=list[ParcelSummary])
async def list_parcels(
    state: str | None = Query(None),
    county: str | None = Query(None),
    instrument_type: str | None = Query(None),
    research_status: str | None = Query(None, alias="research_status"),
    min_score: int | None = Query(None, ge=0, le=100),
    is_absentee: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    svc: ParcelService = Depends(_parcel_service),
    _user: Annotated[None, Depends(get_current_user)] = None,
) -> list[ParcelSummary]:
    """List parcels with optional filtering."""
    return await svc.list_parcels(
        state=state,
        county=county,
        instrument_type=instrument_type,
        research_status=research_status,
        min_score=min_score,
        is_absentee=is_absentee,
        limit=limit,
        offset=offset,
    )


@router.get("/{parcel_id}", response_model=ParcelDetail)
async def get_parcel(
    parcel_id: str,
    svc: ParcelService = Depends(_parcel_service),
    _user: Annotated[None, Depends(get_current_user)] = None,
) -> ParcelDetail:
    """Retrieve full parcel detail including liens, owners, and scores."""
    return await svc.get_parcel_detail(parcel_id)
