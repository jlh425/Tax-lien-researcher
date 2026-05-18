"""Export service — PDF report (WeasyPrint + Jinja2) and CSV export."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from aloha.db.models.parcel import Parcel
from aloha.services.base import BaseService

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "pdf" / "templates"


class ExportService(BaseService):
    """PDF and CSV export for parcel data."""

    def __init__(self, session: AsyncSession, *, template_dir: Path | None = None) -> None:
        super().__init__(session)
        tpl_dir = template_dir or _TEMPLATE_DIR
        self._jinja = Environment(
            loader=FileSystemLoader(str(tpl_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    # ── Public API ───────────────────────────────────────────────────────

    async def export_parcel_pdf(self, parcel_id: str) -> bytes:
        """Generate a PDF report for a single parcel.

        Returns the PDF as raw bytes.
        """
        from weasyprint import HTML  # heavy import — deferred

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
            raise ValueError(f"Parcel {parcel_id!r} not found")

        html = self._render_html_report(
            {
                "parcel": parcel,
                "liens": sorted(
                    parcel.tax_liens, key=lambda lien: lien.tax_year or 0, reverse=True
                ),
                "owners": parcel.owners,
                "scores": sorted(parcel.scores, key=lambda s: s.scored_at, reverse=True),
                "images": parcel.property_images,
            }
        )

        self.log.info("pdf_generated", parcel_id=parcel_id)
        return HTML(string=html).write_pdf()

    async def export_parcels_csv(
        self,
        parcel_ids: list[str],
        columns: list[str] | None = None,
    ) -> bytes:
        """Export selected parcels as CSV bytes.

        If *columns* is ``None``, a default set of columns is used.
        """
        default_columns = [
            "parcel_id",
            "state",
            "county",
            "address",
            "property_type",
            "acreage",
            "assessed_total",
            "research_status",
        ]
        cols = columns or default_columns

        stmt = select(Parcel).where(Parcel.parcel_id.in_(parcel_ids))
        result = await self._session.execute(stmt)
        parcels = result.scalars().all()

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        for parcel in parcels:
            row = {col: getattr(parcel, col, None) for col in cols}
            # Convert Decimal/numeric to plain types for CSV
            for k, v in row.items():
                if v is not None and hasattr(v, "__float__"):
                    row[k] = float(v)
            writer.writerow(row)

        self.log.info("csv_exported", count=len(parcels))
        return buf.getvalue().encode("utf-8")

    # ── Private helpers ──────────────────────────────────────────────────

    def _render_html_report(self, data: dict[str, Any]) -> str:
        """Render a parcel report HTML page using Jinja2."""
        try:
            template = self._jinja.get_template("parcel_report.html")
        except TemplateNotFound:
            # Fallback to a minimal inline template if file doesn't exist
            return self._minimal_report(data)
        return template.render(**data)

    @staticmethod
    def _minimal_report(data: dict[str, Any]) -> str:
        """Minimal HTML report when no template file is available."""
        parcel = data["parcel"]
        return f"""\
<html>
<head><title>Parcel Report — {parcel.parcel_id}</title></head>
<body>
<h1>{parcel.parcel_id}</h1>
<p>{parcel.state} / {parcel.county}</p>
<p>Address: {parcel.address or "N/A"}</p>
<p>Assessed Total: {parcel.assessed_total or "N/A"}</p>
<p>Status: {parcel.research_status}</p>
</body>
</html>"""
