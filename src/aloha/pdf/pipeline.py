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
    """Run OCR on a scanned PDF using PyMuPDF rendering + pytesseract.

    Renders each page to a high-DPI image, then runs Tesseract OCR via
    pytesseract.  Falls back to empty text (with a warning) if Tesseract
    is not installed on the host.

    Args:
        data: Raw PDF bytes.

    Returns:
        An ``ExtractionResult`` with OCR'd text.
    """
    import pymupdf

    log.info("ocr_extraction_started", size_bytes=len(data))

    doc = pymupdf.open(stream=data, filetype="pdf")
    page_count = len(doc)
    metadata = dict(doc.metadata) if doc.metadata else {}
    pages_text: list[str] = []

    try:
        import pytesseract
        from PIL import Image

        for i, page in enumerate(doc):
            # Render at 300 DPI for good OCR accuracy
            pix = page.get_pixmap(dpi=300)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            text = pytesseract.image_to_string(img)
            pages_text.append(text)
            log.debug("ocr_page_done", page=i + 1, chars=len(text))

        metadata["ocr_engine"] = "tesseract"
    except ImportError:
        log.warning("pytesseract_not_installed, OCR unavailable")
        metadata["ocr_engine"] = "unavailable"
    except Exception as exc:
        log.warning("ocr_failed", error=str(exc))
        metadata["ocr_engine"] = "error"
        metadata["ocr_error"] = str(exc)
    finally:
        doc.close()

    return ExtractionResult(
        kind=PDFKind.SCANNED,
        text="\n\n".join(pages_text),
        page_count=page_count,
        metadata=metadata,
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
