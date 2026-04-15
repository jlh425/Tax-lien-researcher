"""End-to-end integration test for the Natrona County, WY pipeline.

Validates the full discovery pipeline:
1. PDF download (mocked with fixture data)
2. Text extraction + parsing
3. Normalised record output
4. Discovery agent dispatches via scraper registry

Run with:
    pytest tests/integration/test_natrona_pipeline.py -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from aloha.scrapers.wy.natrona import (
    NatronaCountyDiscoveryScraper,
    _parse_delinquent_list,
    _parse_line,
)

# ── Fixture data ──────────────────────────────────────────────────────────────
# Simulates the text content of the Natrona County delinquent tax list PDF.

FIXTURE_PDF_TEXT = """\
NATRONA COUNTY TREASURER
DELINQUENT TAX LIST - 2025
Published pursuant to Wyoming Statute 39-13-108

Parcel ID          Owner                      Tax Year   Principal    Penalty    Interest    Total Due
35-1N-79-0020      SMITH JOHN A               2023       $1,245.67    $62.28     $186.85     $1,494.80
35-1N-79-0145      JONES MARY L & DAVID       2022       $3,891.00    $194.55    $583.65     $4,669.20
35-2S-80-0310      ABC PROPERTIES LLC          2023       $756.42      $37.82     $113.46     $907.70
35-2S-80-0311      WILLIAMS ROBERT             2021       $12,450.00   $622.50    $3,735.00   $16,807.50
36-1N-78-0044      BROWN ESTATE OF JAMES       2023       $2,100.33    $105.02    $315.05     $2,520.40
"""


# ═══════════════════════════════════════════════════════════════════════════════
# Text parsing tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseDelinquentList:
    def test_parses_fixture_records(self):
        records = _parse_delinquent_list(FIXTURE_PDF_TEXT)
        assert len(records) == 5

    def test_max_records_limit(self):
        records = _parse_delinquent_list(FIXTURE_PDF_TEXT, max_records=2)
        assert len(records) == 2

    def test_parcel_ids_normalised(self):
        records = _parse_delinquent_list(FIXTURE_PDF_TEXT)
        ids = [r["parcel_id"] for r in records]
        # Should be uppercase, no separators
        assert "351N790020" in ids
        assert "351N790145" in ids
        assert "352S800310" in ids

    def test_tax_year_extracted(self):
        records = _parse_delinquent_list(FIXTURE_PDF_TEXT)
        years = [r["tax_year"] for r in records]
        assert 2023 in years
        assert 2022 in years
        assert 2021 in years

    def test_amounts_extracted(self):
        records = _parse_delinquent_list(FIXTURE_PDF_TEXT)
        # First record should have principal and total
        first = records[0]
        assert first["principal_amount"] is not None
        assert first["total_owed"] is not None
        assert first["principal_amount"] > 0
        assert first["total_owed"] >= first["principal_amount"]

    def test_owner_extracted(self):
        records = _parse_delinquent_list(FIXTURE_PDF_TEXT)
        owners = [r.get("owner_of_record") for r in records]
        # At least some owners should be extracted
        assert any(o and "SMITH" in o.upper() for o in owners if o)

    def test_lien_status_default(self):
        records = _parse_delinquent_list(FIXTURE_PDF_TEXT)
        for r in records:
            assert r["lien_status"] == "active"

    def test_certificate_rate(self):
        records = _parse_delinquent_list(FIXTURE_PDF_TEXT)
        for r in records:
            assert r["certificate_interest_rate"] == 0.15

    def test_empty_text(self):
        records = _parse_delinquent_list("")
        assert records == []

    def test_header_only_text(self):
        records = _parse_delinquent_list(
            "Parcel ID  Owner  Address  Tax Year  Principal  Total\n"
        )
        assert records == []


class TestParseLine:
    def test_valid_line(self):
        line = "35-1N-79-0020  SMITH JOHN A  2023  $1,245.67  $62.28  $186.85  $1,494.80"
        result = _parse_line(line)
        assert result is not None
        assert result["parcel_id"] == "351N790020"

    def test_no_parcel_id(self):
        assert _parse_line("This is just text with no parcel ID") is None

    def test_blank_line(self):
        assert _parse_line("") is None


# ═══════════════════════════════════════════════════════════════════════════════
# Scraper integration tests (mocked HTTP)
# ═══════════════════════════════════════════════════════════════════════════════


class TestNatronaCountyDiscoveryScraper:
    @pytest.fixture
    def scraper(self):
        return NatronaCountyDiscoveryScraper()

    @pytest.mark.asyncio
    async def test_discover_with_mocked_pdf(self, scraper):
        """Mock the PDF download and verify end-to-end parsing."""
        # Create a minimal valid PDF with our fixture text using pymupdf
        pdf_bytes = _make_fixture_pdf(FIXTURE_PDF_TEXT)

        scraper.scrape = AsyncMock(return_value=pdf_bytes)
        records = await scraper.discover(max_records=50)

        assert len(records) > 0
        for r in records:
            assert "parcel_id" in r
            assert "source_url" in r
            assert r["source_url"] == scraper.pdf_url

    @pytest.mark.asyncio
    async def test_discover_returns_empty_on_download_failure(self, scraper):
        """If PDF download fails, return empty list."""
        scraper.scrape = AsyncMock(side_effect=Exception("404 Not Found"))
        records = await scraper.discover()
        assert records == []

    @pytest.mark.asyncio
    async def test_discover_max_records_respected(self, scraper):
        pdf_bytes = _make_fixture_pdf(FIXTURE_PDF_TEXT)
        scraper.scrape = AsyncMock(return_value=pdf_bytes)
        records = await scraper.discover(max_records=2)
        assert len(records) <= 2


# ═══════════════════════════════════════════════════════════════════════════════
# Registry integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestNatronaRegistry:
    def test_registered_in_scraper_registry(self):
        from aloha.scrapers.registry import get_scraper_entry

        entry = get_scraper_entry("WY", "natrona")
        assert entry is not None
        assert entry.tier == 3
        assert "NatronaCountyDiscoveryScraper" in entry.scraper_class

    def test_arcgis_layer_registered(self):
        from aloha.scrapers.tier1_apis.arcgis import get_arcgis_parcel_url

        url = get_arcgis_parcel_url("WY", "natrona")
        assert url is not None
        assert "arcgis" in url.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Discovery agent dispatch
# ═══════════════════════════════════════════════════════════════════════════════


class TestDiscoveryAgentNatrona:
    @pytest.mark.asyncio
    async def test_agent_dispatches_to_natrona_scraper(self):
        """Verify the discovery agent uses the registered scraper for Natrona County."""
        from aloha.agents.discovery.agent import DiscoveryAgent

        agent = DiscoveryAgent()
        # Mock _registered_scrape to verify it's called for tier 3
        agent._registered_scrape = AsyncMock(return_value=[
            {"parcel_id": "351N790020", "address": "123 Test St"},
        ])
        agent._persist_and_enqueue = AsyncMock(return_value=1)
        agent._auction_scrape = AsyncMock(return_value=[])

        result = await agent.run({"state": "WY", "county": "natrona"})

        assert result["status"] == "complete"
        assert result["records_found"] == 1
        agent._registered_scrape.assert_called_once()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_fixture_pdf(text: str) -> bytes:
    """Create a minimal PDF containing the given text using pymupdf."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    # Insert text at top-left
    page.insert_text((50, 50), text, fontsize=8)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
