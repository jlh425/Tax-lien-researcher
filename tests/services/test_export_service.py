"""Comprehensive tests for the ExportService.

Covers CSV export edge cases (empty list, custom columns, None/Decimal values),
PDF export, HTML rendering fallback, and the minimal report template.

Existing tests in test_services.py cover:
  - export_parcels_csv (basic 2-parcel happy path)
This file covers everything else.
"""

from __future__ import annotations

import csv
import io
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aloha.services.export_service import ExportService


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_service(session: AsyncMock | None = None) -> tuple[ExportService, AsyncMock]:
    """Instantiate ExportService with a mocked session."""
    session = session or AsyncMock()
    svc = ExportService(session)
    return svc, session


def _make_parcel(
    *,
    parcel_id: str = "P001",
    state: str = "FL",
    county: str = "miami-dade",
    address: str | None = "123 Palm Ave",
    property_type: str | None = "residential",
    acreage: float | Decimal | None = 0.25,
    assessed_total: int | None = 150000,
    research_status: str = "scored",
    zoning: str | None = None,
) -> MagicMock:
    """Build a mock Parcel for export tests."""
    parcel = MagicMock()
    parcel.parcel_id = parcel_id
    parcel.state = state
    parcel.county = county
    parcel.address = address
    parcel.property_type = property_type
    parcel.acreage = acreage
    parcel.assessed_total = assessed_total
    parcel.research_status = research_status
    parcel.zoning = zoning
    return parcel


# ═══════════════════════════════════════════════════════════════════════════════
# export_parcels_csv
# ═══════════════════════════════════════════════════════════════════════════════


class TestExportParcelsCSV:
    """Tests for export_parcels_csv."""

    @pytest.mark.asyncio
    async def test_csv_empty_parcel_list(self) -> None:
        """CSV with no matching parcels returns header-only output."""
        svc, session = _make_service()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_result

        csv_bytes = await svc.export_parcels_csv([])
        csv_text = csv_bytes.decode("utf-8")
        lines = csv_text.strip().split("\n")

        # Header only
        assert len(lines) == 1
        assert "parcel_id" in lines[0]

    @pytest.mark.asyncio
    async def test_csv_custom_columns(self) -> None:
        """CSV uses custom columns when specified."""
        svc, session = _make_service()
        parcel = _make_parcel()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [parcel]
        session.execute.return_value = mock_result

        csv_bytes = await svc.export_parcels_csv(
            ["P001"],
            columns=["parcel_id", "state", "county"],
        )
        csv_text = csv_bytes.decode("utf-8")
        lines = csv_text.strip().split("\n")

        assert len(lines) == 2
        header = lines[0]
        assert "parcel_id" in header
        assert "state" in header
        assert "county" in header
        # Default columns that weren't requested should be absent
        assert "property_type" not in header

    @pytest.mark.asyncio
    async def test_csv_none_values(self) -> None:
        """CSV handles None values in parcel fields."""
        svc, session = _make_service()
        parcel = _make_parcel(
            address=None,
            property_type=None,
            acreage=None,
            assessed_total=None,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [parcel]
        session.execute.return_value = mock_result

        csv_bytes = await svc.export_parcels_csv(["P001"])
        csv_text = csv_bytes.decode("utf-8")

        reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["parcel_id"] == "P001"

    @pytest.mark.asyncio
    async def test_csv_decimal_values_converted(self) -> None:
        """CSV converts Decimal values to float for serialisation."""
        svc, session = _make_service()
        parcel = _make_parcel(acreage=Decimal("1.750"))
        # Ensure hasattr(__float__) works on the mock
        parcel.acreage = Decimal("1.750")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [parcel]
        session.execute.return_value = mock_result

        csv_bytes = await svc.export_parcels_csv(["P001"])
        csv_text = csv_bytes.decode("utf-8")

        reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(reader)
        assert float(rows[0]["acreage"]) == 1.75

    @pytest.mark.asyncio
    async def test_csv_multiple_parcels(self) -> None:
        """CSV correctly exports multiple parcels."""
        svc, session = _make_service()
        parcels = [
            _make_parcel(parcel_id="P001", state="FL", county="orange"),
            _make_parcel(parcel_id="P002", state="TX", county="harris"),
            _make_parcel(parcel_id="P003", state="CA", county="los-angeles"),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = parcels
        session.execute.return_value = mock_result

        csv_bytes = await svc.export_parcels_csv(["P001", "P002", "P003"])
        csv_text = csv_bytes.decode("utf-8")
        lines = csv_text.strip().split("\n")

        # Header + 3 data rows
        assert len(lines) == 4

    @pytest.mark.asyncio
    async def test_csv_utf8_encoding(self) -> None:
        """CSV output is valid UTF-8."""
        svc, session = _make_service()
        parcel = _make_parcel(address="Caf\u00e9 del Sol, 123 \u00d1u\u00f1ez Ave")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [parcel]
        session.execute.return_value = mock_result

        csv_bytes = await svc.export_parcels_csv(["P001"])
        csv_text = csv_bytes.decode("utf-8")
        assert "Caf\u00e9" in csv_text

    @pytest.mark.asyncio
    async def test_csv_extra_columns_ignored(self) -> None:
        """Columns not present on parcel are written as None."""
        svc, session = _make_service()
        parcel = _make_parcel()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [parcel]
        session.execute.return_value = mock_result

        csv_bytes = await svc.export_parcels_csv(
            ["P001"],
            columns=["parcel_id", "nonexistent_field"],
        )
        csv_text = csv_bytes.decode("utf-8")

        reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(reader)
        assert rows[0]["parcel_id"] == "P001"


# ═══════════════════════════════════════════════════════════════════════════════
# export_parcel_pdf
# ═══════════════════════════════════════════════════════════════════════════════


class TestExportParcelPDF:
    """Tests for export_parcel_pdf."""

    @pytest.mark.asyncio
    async def test_pdf_not_found_raises(self) -> None:
        """export_parcel_pdf raises ValueError when parcel doesn't exist."""
        svc, session = _make_service()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        session.execute.return_value = mock_result

        with pytest.raises(ValueError, match="not found"):
            await svc.export_parcel_pdf("NONEXISTENT")

    @pytest.mark.asyncio
    async def test_pdf_happy_path(self) -> None:
        """export_parcel_pdf generates PDF bytes for a valid parcel."""
        svc, session = _make_service()

        parcel = MagicMock()
        parcel.parcel_id = "P001"
        parcel.state = "FL"
        parcel.county = "orange"
        parcel.address = "123 Palm Ave"
        parcel.assessed_total = 150000
        parcel.research_status = "scored"
        parcel.tax_liens = []
        parcel.owners = []
        parcel.scores = []
        parcel.property_images = []

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = parcel
        session.execute.return_value = mock_result

        with patch("aloha.services.export_service.ExportService._render_html_report") as mock_render:
            mock_render.return_value = "<html><body>Test</body></html>"
            mock_pdf_bytes = b"%PDF-1.4 fake content"
            with patch("weasyprint.HTML") as MockHTML:
                mock_html_instance = MagicMock()
                mock_html_instance.write_pdf.return_value = mock_pdf_bytes
                MockHTML.return_value = mock_html_instance

                result = await svc.export_parcel_pdf("P001")

        assert result == mock_pdf_bytes
        MockHTML.assert_called_once()
        mock_html_instance.write_pdf.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# _render_html_report and _minimal_report
# ═══════════════════════════════════════════════════════════════════════════════


class TestHTMLRendering:
    """Tests for _render_html_report and _minimal_report."""

    def test_minimal_report_contains_parcel_info(self) -> None:
        """_minimal_report includes parcel ID, state, county, address."""
        parcel = MagicMock()
        parcel.parcel_id = "P-MINIMAL"
        parcel.state = "TX"
        parcel.county = "harris"
        parcel.address = "456 Oak St"
        parcel.assessed_total = 200000
        parcel.research_status = "complete"

        html = ExportService._minimal_report({"parcel": parcel})

        assert "P-MINIMAL" in html
        assert "TX" in html
        assert "harris" in html
        assert "456 Oak St" in html
        assert "200000" in html

    def test_minimal_report_na_for_none_address(self) -> None:
        """_minimal_report shows 'N/A' when address is None."""
        parcel = MagicMock()
        parcel.parcel_id = "P-NOADDR"
        parcel.state = "FL"
        parcel.county = "orange"
        parcel.address = None
        parcel.assessed_total = None
        parcel.research_status = "pending"

        html = ExportService._minimal_report({"parcel": parcel})

        assert "N/A" in html

    def test_render_html_report_fallback(self) -> None:
        """_render_html_report falls back to minimal when template is missing."""
        svc, _ = _make_service()

        parcel = MagicMock()
        parcel.parcel_id = "P-FALLBACK"
        parcel.state = "CA"
        parcel.county = "los-angeles"
        parcel.address = "789 Sunset Blvd"
        parcel.assessed_total = 300000
        parcel.research_status = "scored"

        data = {"parcel": parcel, "liens": [], "owners": [], "scores": [], "images": []}
        html = svc._render_html_report(data)

        # Should get the minimal report since template file doesn't exist
        assert "P-FALLBACK" in html
        assert "<html>" in html
