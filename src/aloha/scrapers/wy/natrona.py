"""Natrona County, WY — PDF-based delinquent tax list discovery scraper.

Natrona County (Casper, WY) is a **lien certificate** state with a 15% fixed
interest rate and annual August sale.  The county publishes its delinquent tax
list as a PDF on its website.  This scraper downloads the PDF, extracts text
via ``pymupdf`` (with ``pytesseract`` OCR fallback for scanned pages), parses
the structured table rows, and returns normalised records matching the
canonical field names used by the rest of the pipeline.

Data sources:
- Delinquent list PDF: natronacounty-wy.gov/DocumentCenter/View/12592/Delinquent-List-2025
- Assessor search: assessorsearch.natronacounty-wy.gov (Tier 3)
- Treasurer search: treasurersearch.natronacounty-wy.gov (Tier 3)
- ArcGIS Open Data: data-cityofcasper.opendata.arcgis.com (Tier 1 enrichment)

Usage:
    scraper = NatronaCountyDiscoveryScraper()
    records = await scraper.discover(max_records=50)
"""

from __future__ import annotations

import io
import re
from typing import Any

import structlog

from aloha.scrapers.base import BaseScraper

log = structlog.get_logger().bind(scraper="natrona_county")

# The county's delinquent tax list PDF URL.
DELINQUENT_LIST_URL = (
    "https://www.natronacounty-wy.gov/DocumentCenter/View/12592/"
    "Delinquent-List-2025"
)

# Canonical field names for the pipeline (matches Socrata normalisation).
# Natrona PDF columns typically include:
#   Parcel ID | Owner | Address | Tax Year | Principal | Penalty | Interest | Total
_HEADER_PATTERNS = re.compile(
    r"parcel|owner|address|tax\s*year|principal|penalty|interest|total",
    re.IGNORECASE,
)

# Regex for a WY-style parcel ID: digits with optional hyphens/dots/spaces
# e.g. "35-1N-79-0020" or "351N790020"
_PARCEL_RE = re.compile(r"\d{1,3}[\s\-.]?\d{1,2}[NSEW]?[\s\-.]?\d{1,3}[\s\-.]?\d{2,6}")


class NatronaCountyDiscoveryScraper(BaseScraper):
    """Downloads and parses the Natrona County delinquent tax list PDF."""

    def __init__(self, *, pdf_url: str = DELINQUENT_LIST_URL) -> None:
        super().__init__()
        self.pdf_url = pdf_url

    async def scrape(self, url: str, params: dict[str, Any] | None = None) -> Any:
        """Low-level fetch — returns raw response bytes."""
        response = await self._fetch(url, params=params)
        return response.content

    async def discover(self, *, max_records: int = 5000) -> list[dict[str, Any]]:
        """Download the delinquent list PDF, parse it, and return normalised records.

        Returns a list of dicts with canonical field names.  Returns an empty
        list if the PDF cannot be downloaded or parsed.
        """
        log.info("downloading_pdf", url=self.pdf_url)
        try:
            pdf_bytes = await self.scrape(self.pdf_url)
        except Exception as exc:
            log.warning("pdf_download_failed", error=str(exc))
            return []

        text = _extract_text(pdf_bytes)
        if not text:
            log.warning("pdf_text_extraction_empty")
            return []

        records = _parse_delinquent_list(text, max_records=max_records)
        log.info(
            "natrona_discovery_done",
            records_parsed=len(records),
            max_records=max_records,
        )

        # Attach source provenance
        for r in records:
            r["source_url"] = self.pdf_url

        return records


# ── PDF text extraction ───────────────────────────────────────────────────────


def _extract_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes using pymupdf, falling back to OCR."""
    import fitz  # pymupdf

    text_parts: list[str] = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    for page in doc:
        page_text = page.get_text("text")
        if page_text and len(page_text.strip()) > 50:
            text_parts.append(page_text)
        else:
            # Scanned page — fall back to OCR
            ocr_text = _ocr_page(page)
            if ocr_text:
                text_parts.append(ocr_text)

    doc.close()
    return "\n".join(text_parts)


def _ocr_page(page: Any) -> str:
    """OCR a single PDF page using pytesseract."""
    try:
        import pytesseract
        from PIL import Image

        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return pytesseract.image_to_string(img)
    except ImportError:
        log.debug("pytesseract_not_available")
        return ""
    except Exception as exc:
        log.warning("ocr_failed", error=str(exc))
        return ""


# ── Table parsing ─────────────────────────────────────────────────────────────


def _parse_delinquent_list(
    text: str, *, max_records: int = 5000
) -> list[dict[str, Any]]:
    """Parse the extracted text into normalised records.

    The Natrona County delinquent list is a columnar table.  We detect the
    header row to learn column positions, then parse each subsequent line.
    When exact column positions aren't detectable, we fall back to
    regex-based extraction.
    """
    lines = text.splitlines()
    records: list[dict[str, Any]] = []

    for line in lines:
        if len(records) >= max_records:
            break

        line = line.strip()
        if not line:
            continue

        # Skip header / title rows
        if _HEADER_PATTERNS.search(line):
            continue

        record = _parse_line(line)
        if record:
            records.append(record)

    return records


def _parse_line(line: str) -> dict[str, Any] | None:
    """Attempt to extract a record from a single line of the delinquent list.

    Returns ``None`` if the line doesn't contain a valid parcel ID.
    """
    parcel_match = _PARCEL_RE.search(line)
    if not parcel_match:
        return None

    raw_parcel_id = parcel_match.group(0)
    # Normalise: strip separators, uppercase
    parcel_id = re.sub(r"[\s\-\./]", "", raw_parcel_id).upper()

    # Extract dollar amounts from the line
    amounts = re.findall(r"\$?([\d,]+\.?\d*)", line)
    dollar_values = []
    for a in amounts:
        try:
            val = float(a.replace(",", ""))
            # Filter out values that are clearly years (1900-2099)
            if not (1900 <= val <= 2099):
                dollar_values.append(val)
        except ValueError:
            continue

    # Extract tax year (4-digit number between 2000 and current+1)
    year_match = re.search(r"\b(20[0-2]\d)\b", line)
    tax_year: int | None = int(year_match.group(1)) if year_match else None

    # Extract the owner name: text between parcel ID and first dollar amount
    # or year.  This is heuristic.
    after_parcel = line[parcel_match.end():].strip()
    # Try to get the text before numeric content
    owner_match = re.match(r"^([A-Za-z\s,.&']+?)(?=\s+\d|\s*$)", after_parcel)
    owner: str | None = owner_match.group(1).strip() if owner_match else None

    # Address: text between owner and amounts (often not present in summary PDFs)
    address: str | None = None

    # Map dollar values to canonical fields based on count
    principal: float | None = None
    total_owed: float | None = None

    if len(dollar_values) >= 2:
        # Usually: principal first, total last
        principal = dollar_values[0]
        total_owed = dollar_values[-1]
    elif len(dollar_values) == 1:
        total_owed = dollar_values[0]
        principal = dollar_values[0]

    if not parcel_id:
        return None

    return {
        "parcel_id": parcel_id,
        "owner_of_record": owner,
        "address": address,
        "tax_year": tax_year,
        "principal_amount": principal,
        "total_owed": total_owed,
        "lien_status": "active",
        "certificate_interest_rate": 0.15,  # Wyoming: 15% fixed
    }
