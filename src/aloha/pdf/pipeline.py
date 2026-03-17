"""Document processing pipeline — detect PDF type and route to extractor."""

from __future__ import annotations

import io
from dataclasses import dataclass
from enum import StrEnum, auto
from pathlib import Path
from typing import Any

import structlog

log: structlog.stdlib.BoundLogger = structlog.get_logger().bind(component="pdf_pipeline")


class PDFKind(StrEnum):
    """Classification of a PDF's text layer."""

    NATIVE = auto()     # Selectable / searchable text
    SCANNED = auto()    # Image-only; needs OCR
    MIXED = auto()      # Some pages native, some scanned


@dataclass(slots=True)
class ExtractionResult:
    """Outcome of running a PDF through the pipeline."""

    kind: PDFKind
    text: str
    page_count: int
    metadata: dict[str, Any]


async def detect_pdf_kind(data: bytes) -> PDFKind:
    """Heuristically determine whether a PDF contains native text or is scanned.

    Args:
        data: Raw PDF bytes.

    Returns:
        The detected ``PDFKind``.
    """
    try:
        import pymupdf  # PyMuPDF / fitz

        doc = pymupdf.open(stream=data, filetype="pdf")
        pages_with_text = sum(1 for page in doc if page.get_text().strip())
        total = len(doc)
        doc.close()

        if pages_with_text == 0:
            return PDFKind.SCANNED
        if pages_with_text == total:
            return PDFKind.NATIVE
        return PDFKind.MIXED
    except ImportError:
        log.warning("pymupdf_not_installed, defaulting to NATIVE")
        return PDFKind.NATIVE


async def extract_native_text(data: bytes) -> ExtractionResult:
    """Extract text from a native / searchable PDF.

    Args:
        data: Raw PDF bytes.

    Returns:
        An ``ExtractionResult`` with the extracted text.
    """
    import pymupdf

    doc = pymupdf.open(stream=data, filetype="pdf")
    pages_text = [page.get_text() for page in doc]
    metadata = dict(doc.metadata) if doc.metadata else {}
    page_count = len(doc)
    doc.close()

    return ExtractionResult(
        kind=PDFKind.NATIVE,
        text="\n\n".join(pages_text),
        page_count=page_count,
        metadata=metadata,
    )


async def extract_scanned_text(data: bytes) -> ExtractionResult:
    """Run OCR on a scanned PDF.

    Placeholder -- will integrate Tesseract or a cloud OCR service.

    Args:
        data: Raw PDF bytes.

    Returns:
        An ``ExtractionResult`` with OCR'd text.
    """
    log.info("ocr_extraction_started")
    # TODO: integrate Tesseract / Google Vision / AWS Textract
    return ExtractionResult(
        kind=PDFKind.SCANNED,
        text="",
        page_count=0,
        metadata={"ocr": "not_yet_implemented"},
    )


async def process_pdf(source: str | Path | bytes) -> ExtractionResult:
    """Top-level entry point: detect PDF kind and route to the right extractor.

    Args:
        source: A file path, URL string, or raw bytes.

    Returns:
        An ``ExtractionResult`` with extracted / OCR'd text.
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        data = path.read_bytes()
    elif isinstance(source, bytes):
        data = source
    else:
        raise TypeError(f"Unsupported source type: {type(source)}")

    kind = await detect_pdf_kind(data)
    log.info("pdf_classified", kind=kind.value, size_bytes=len(data))

    match kind:
        case PDFKind.NATIVE | PDFKind.MIXED:
            return await extract_native_text(data)
        case PDFKind.SCANNED:
            return await extract_scanned_text(data)
