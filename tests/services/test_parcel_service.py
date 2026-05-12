"""Comprehensive tests for the ParcelService.

Covers list_parcels (filtering, post-load filters, empty results),
get_parcel_detail (happy path, not found, with/without vision analysis),
and static helper edge cases.

Existing tests in test_services.py cover:
  - _extract_condition_summary (JSON / fallback)
  - _to_lien_out, _to_owner_out, _to_score_out (static converters)
This file covers the async methods.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from aloha.services.parcel_service import ParcelService


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_service(session: AsyncMock | None = None) -> tuple[ParcelService, AsyncMock]:
    """Instantiate ParcelService with a mocked session."""
    session = session or AsyncMock()
    svc = ParcelService(session)
    return svc, session


def _make_parcel(
    *,
    parcel_id: str = "P001",
    state: str = "FL",
    county: str = "orange",
    address: str | None = "123 Palm Ave",
    property_type: str | None = "residential",
    zoning: str | None = None,
    acreage: float | None = 0.25,
    assessed_total: int | None = 150000,
    research_status: str = "scored",
    data_freshness: str = "fresh",
    latitude: float | None = 28.5383,
    longitude: float | None = -81.3792,
    user_id: uuid.UUID | None = None,
    address_normalized: str | None = None,
    legal_description: str | None = None,
    land_use_code: str | None = None,
    zoning_notes: str | None = None,
    assessed_land_val: int | None = None,
    assessed_impr_val: int | None = None,
    market_value_est: int | None = None,
    last_sale_date: date | None = None,
    last_sale_price: int | None = None,
    year_built: int | None = None,
    last_crawled_at: datetime | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    tax_liens: list | None = None,
    owners: list | None = None,
    scores: list | None = None,
    property_images: list | None = None,
) -> MagicMock:
    """Build a mock Parcel with all fields needed for detail assembly."""
    parcel = MagicMock()
    parcel.parcel_id = parcel_id
    parcel.state = state
    parcel.county = county
    parcel.address = address
    parcel.address_normalized = address_normalized
    parcel.legal_description = legal_description
    parcel.property_type = property_type
    parcel.zoning = zoning
    parcel.zoning_notes = zoning_notes
    parcel.acreage = acreage
    parcel.land_use_code = land_use_code
    parcel.assessed_land_val = assessed_land_val
    parcel.assessed_impr_val = assessed_impr_val
    parcel.assessed_total = assessed_total
    parcel.market_value_est = market_value_est
    parcel.last_sale_date = last_sale_date
    parcel.last_sale_price = last_sale_price
    parcel.year_built = year_built
    parcel.research_status = research_status
    parcel.data_freshness = data_freshness
    parcel.latitude = latitude
    parcel.longitude = longitude
    parcel.user_id = user_id
    parcel.last_crawled_at = last_crawled_at
    parcel.created_at = created_at or datetime.now(tz=timezone.utc)
    parcel.updated_at = updated_at or datetime.now(tz=timezone.utc)
    parcel.tax_liens = tax_liens or []
    parcel.owners = owners or []
    parcel.scores = scores or []
    parcel.property_images = property_images or []
    return parcel


def _make_lien(
    *,
    tax_year: int = 2024,
    instrument_type: str = "lien_certificate",
    lien_status: str = "active",
    total_owed: float | None = 5000.0,
    redemption_deadline: date | None = None,
    auction_date: date | None = None,
) -> MagicMock:
    """Build a mock TaxLien for listing tests."""
    lien = MagicMock()
    lien.tax_year = tax_year
    lien.instrument_type = instrument_type
    lien.lien_status = lien_status
    lien.total_owed = total_owed
    lien.redemption_deadline = redemption_deadline
    lien.auction_date = auction_date
    return lien


def _make_score(
    *,
    overall_score: int = 85,
    scored_at: datetime | None = None,
    risk_flags: list[str] | None = None,
) -> MagicMock:
    """Build a mock Score for listing tests."""
    score = MagicMock()
    score.overall_score = overall_score
    score.scored_at = scored_at or datetime.now(tz=timezone.utc)
    score.risk_flags = risk_flags
    return score


def _make_owner(
    *,
    is_absentee: bool = False,
) -> MagicMock:
    """Build a mock Owner for listing tests."""
    owner = MagicMock()
    owner.is_absentee = is_absentee
    return owner


# ═══════════════════════════════════════════════════════════════════════════════
# list_parcels
# ═══════════════════════════════════════════════════════════════════════════════


class TestListParcels:
    """Tests for list_parcels with filtering and post-load filters."""

    @pytest.mark.asyncio
    async def test_list_empty_results(self) -> None:
        """list_parcels returns empty list when no parcels match."""
        svc, session = _make_service()

        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = []
        session.execute.return_value = mock_result

        summaries = await svc.list_parcels()
        assert summaries == []

    @pytest.mark.asyncio
    async def test_list_basic_parcel(self) -> None:
        """list_parcels returns summaries for parcels without liens/scores."""
        svc, session = _make_service()

        parcel = _make_parcel()
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = [parcel]
        session.execute.return_value = mock_result

        summaries = await svc.list_parcels()

        assert len(summaries) == 1
        assert summaries[0].parcel_id == "P001"
        assert summaries[0].state == "FL"
        assert summaries[0].instrument_type is None
        assert summaries[0].overall_score is None

    @pytest.mark.asyncio
    async def test_list_with_liens_and_scores(self) -> None:
        """list_parcels includes latest lien and score data."""
        svc, session = _make_service()

        lien = _make_lien(tax_year=2024, instrument_type="tax_deed", total_owed=8000.0)
        score = _make_score(overall_score=92, risk_flags=["title_issue"])
        parcel = _make_parcel(tax_liens=[lien], scores=[score])

        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = [parcel]
        session.execute.return_value = mock_result

        summaries = await svc.list_parcels()

        assert len(summaries) == 1
        assert summaries[0].instrument_type == "tax_deed"
        assert summaries[0].total_owed == 8000.0
        assert summaries[0].overall_score == 92
        assert summaries[0].risk_flags == ["title_issue"]

    @pytest.mark.asyncio
    async def test_list_instrument_type_filter(self) -> None:
        """Post-load instrument_type filter excludes non-matching parcels."""
        svc, session = _make_service()

        lien_deed = _make_lien(instrument_type="tax_deed")
        lien_cert = _make_lien(instrument_type="lien_certificate")

        parcel_deed = _make_parcel(parcel_id="P-DEED", tax_liens=[lien_deed])
        parcel_cert = _make_parcel(parcel_id="P-CERT", tax_liens=[lien_cert])

        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = [
            parcel_deed, parcel_cert,
        ]
        session.execute.return_value = mock_result

        summaries = await svc.list_parcels(instrument_type="tax_deed")

        assert len(summaries) == 1
        assert summaries[0].parcel_id == "P-DEED"

    @pytest.mark.asyncio
    async def test_list_min_score_filter(self) -> None:
        """Post-load min_score filter excludes low-score parcels."""
        svc, session = _make_service()

        high_score = _make_score(overall_score=90)
        low_score = _make_score(overall_score=40)

        parcel_high = _make_parcel(parcel_id="P-HIGH", scores=[high_score])
        parcel_low = _make_parcel(parcel_id="P-LOW", scores=[low_score])
        parcel_none = _make_parcel(parcel_id="P-NONE", scores=[])

        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = [
            parcel_high, parcel_low, parcel_none,
        ]
        session.execute.return_value = mock_result

        summaries = await svc.list_parcels(min_score=80)

        assert len(summaries) == 1
        assert summaries[0].parcel_id == "P-HIGH"

    @pytest.mark.asyncio
    async def test_list_is_absentee_filter(self) -> None:
        """Post-load is_absentee filter keeps only matching parcels."""
        svc, session = _make_service()

        absentee_owner = _make_owner(is_absentee=True)
        local_owner = _make_owner(is_absentee=False)

        parcel_abs = _make_parcel(parcel_id="P-ABS", owners=[absentee_owner])
        parcel_local = _make_parcel(parcel_id="P-LOCAL", owners=[local_owner])

        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = [
            parcel_abs, parcel_local,
        ]
        session.execute.return_value = mock_result

        summaries = await svc.list_parcels(is_absentee=True)

        assert len(summaries) == 1
        assert summaries[0].parcel_id == "P-ABS"

    @pytest.mark.asyncio
    async def test_list_multiple_liens_uses_latest(self) -> None:
        """list_parcels selects the lien with highest tax_year."""
        svc, session = _make_service()

        old_lien = _make_lien(tax_year=2020, instrument_type="lien_certificate")
        new_lien = _make_lien(tax_year=2024, instrument_type="tax_deed")

        parcel = _make_parcel(tax_liens=[old_lien, new_lien])

        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = [parcel]
        session.execute.return_value = mock_result

        summaries = await svc.list_parcels()

        assert summaries[0].instrument_type == "tax_deed"

    @pytest.mark.asyncio
    async def test_list_with_none_acreage_and_coordinates(self) -> None:
        """list_parcels handles None acreage, latitude, longitude."""
        svc, session = _make_service()

        parcel = _make_parcel(acreage=None, latitude=None, longitude=None)

        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = [parcel]
        session.execute.return_value = mock_result

        summaries = await svc.list_parcels()

        assert summaries[0].acreage is None
        assert summaries[0].latitude is None
        assert summaries[0].longitude is None

    @pytest.mark.asyncio
    async def test_list_with_none_total_owed(self) -> None:
        """list_parcels handles lien with total_owed=None."""
        svc, session = _make_service()

        lien = _make_lien(total_owed=None)
        parcel = _make_parcel(tax_liens=[lien])

        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = [parcel]
        session.execute.return_value = mock_result

        summaries = await svc.list_parcels()

        assert summaries[0].total_owed is None


# ═══════════════════════════════════════════════════════════════════════════════
# get_parcel_detail
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetParcelDetail:
    """Tests for get_parcel_detail."""

    @pytest.mark.asyncio
    async def test_detail_not_found(self) -> None:
        """get_parcel_detail raises HTTPException 404 for missing parcel."""
        svc, session = _make_service()

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await svc.get_parcel_detail("NONEXISTENT")

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_detail_happy_path_no_vision(self) -> None:
        """get_parcel_detail returns detail without vision analysis."""
        svc, session = _make_service()

        parcel = _make_parcel(
            parcel_id="P-DETAIL",
            user_id=uuid.uuid4(),
            assessed_total=200000,
        )

        # First execute: parcel query
        parcel_result = MagicMock()
        parcel_result.scalars.return_value.first.return_value = parcel
        # Second execute: vision chunk query (none found)
        chunk_result = MagicMock()
        chunk_result.scalars.return_value.first.return_value = None

        session.execute.side_effect = [parcel_result, chunk_result]

        detail = await svc.get_parcel_detail("P-DETAIL")

        assert detail.parcel_id == "P-DETAIL"
        assert detail.assessed_total == 200000
        assert detail.condition_summary is None
        assert detail.tax_liens == []
        assert detail.owners == []
        assert detail.scores == []

    @pytest.mark.asyncio
    async def test_detail_with_vision_analysis(self) -> None:
        """get_parcel_detail includes condition_summary from vision chunk."""
        import json

        svc, session = _make_service()

        parcel = _make_parcel(parcel_id="P-VISION")

        parcel_result = MagicMock()
        parcel_result.scalars.return_value.first.return_value = parcel

        vision_chunk = MagicMock()
        vision_chunk.content = json.dumps({
            "summary": "Property appears well-maintained, minor roof damage"
        })

        chunk_result = MagicMock()
        chunk_result.scalars.return_value.first.return_value = vision_chunk

        session.execute.side_effect = [parcel_result, chunk_result]

        detail = await svc.get_parcel_detail("P-VISION")

        assert detail.condition_summary == "Property appears well-maintained, minor roof damage"

    @pytest.mark.asyncio
    async def test_detail_with_liens_sorted_by_year(self) -> None:
        """get_parcel_detail sorts liens by tax_year descending."""
        svc, session = _make_service()

        lien_old = MagicMock()
        lien_old.id = 1
        lien_old.instrument_type = "lien_certificate"
        lien_old.lien_status = "active"
        lien_old.tax_year = 2020
        lien_old.years_delinquent = 4
        lien_old.principal_amount = 3000.0
        lien_old.interest_amount = None
        lien_old.penalty_amount = None
        lien_old.total_owed = None
        lien_old.filing_date = None
        lien_old.redemption_deadline = None
        lien_old.certificate_number = None
        lien_old.certificate_interest_rate = None
        lien_old.auction_date = None
        lien_old.auction_platform = None
        lien_old.auction_url = None
        lien_old.opening_bid = None
        lien_old.post_sale_redemption_days = None
        lien_old.title_risk_level = None
        lien_old.source_url = None
        lien_old.retrieved_at = datetime(2024, 1, 1, tzinfo=timezone.utc)

        lien_new = MagicMock()
        lien_new.id = 2
        lien_new.instrument_type = "tax_deed"
        lien_new.lien_status = "active"
        lien_new.tax_year = 2024
        lien_new.years_delinquent = 1
        lien_new.principal_amount = 5000.0
        lien_new.interest_amount = None
        lien_new.penalty_amount = None
        lien_new.total_owed = None
        lien_new.filing_date = None
        lien_new.redemption_deadline = None
        lien_new.certificate_number = None
        lien_new.certificate_interest_rate = None
        lien_new.auction_date = None
        lien_new.auction_platform = None
        lien_new.auction_url = None
        lien_new.opening_bid = None
        lien_new.post_sale_redemption_days = None
        lien_new.title_risk_level = None
        lien_new.source_url = None
        lien_new.retrieved_at = datetime(2024, 6, 1, tzinfo=timezone.utc)

        parcel = _make_parcel(parcel_id="P-SORT", tax_liens=[lien_old, lien_new])

        parcel_result = MagicMock()
        parcel_result.scalars.return_value.first.return_value = parcel
        chunk_result = MagicMock()
        chunk_result.scalars.return_value.first.return_value = None

        session.execute.side_effect = [parcel_result, chunk_result]

        detail = await svc.get_parcel_detail("P-SORT")

        # Newest first
        assert detail.tax_liens[0].tax_year == 2024
        assert detail.tax_liens[1].tax_year == 2020

    @pytest.mark.asyncio
    async def test_detail_handles_none_acreage(self) -> None:
        """get_parcel_detail handles None acreage without error."""
        svc, session = _make_service()

        parcel = _make_parcel(parcel_id="P-NOACRE", acreage=None)

        parcel_result = MagicMock()
        parcel_result.scalars.return_value.first.return_value = parcel
        chunk_result = MagicMock()
        chunk_result.scalars.return_value.first.return_value = None

        session.execute.side_effect = [parcel_result, chunk_result]

        detail = await svc.get_parcel_detail("P-NOACRE")
        assert detail.acreage is None


# ═══════════════════════════════════════════════════════════════════════════════
# _extract_condition_summary — additional edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestExtractConditionSummary:
    """Edge cases beyond test_services.py."""

    def test_empty_summary_key(self) -> None:
        """Empty summary string falls back to truncated content."""
        import json

        content = json.dumps({"summary": "", "details": "stuff"})
        result = ParcelService._extract_condition_summary(content)
        # Empty summary string means it falls through to content[:200]
        assert result == content[:200]

    def test_json_without_summary_key(self) -> None:
        """JSON without 'summary' key falls back to truncated content."""
        import json

        content = json.dumps({"analysis": "roof damage detected"})
        result = ParcelService._extract_condition_summary(content)
        assert result == content[:200]

    def test_very_long_non_json_content(self) -> None:
        """Non-JSON content longer than 200 chars is truncated."""
        content = "A" * 500
        result = ParcelService._extract_condition_summary(content)
        assert len(result) == 200

    def test_short_non_json_content(self) -> None:
        """Short non-JSON content is returned as-is (within 200 chars)."""
        content = "Property looks fine"
        result = ParcelService._extract_condition_summary(content)
        assert result == "Property looks fine"
