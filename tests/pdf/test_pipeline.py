"""Tests for the PDF processing pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from aloha.pdf.pipeline import (
    ExtractionResult,
    PDFKind,
    detect_pdf_kind,
    extract_native_text,
    extract_scanned_text,
    process_pdf,
)


def _mock_doc(pages, metadata=None):
    """Build a mock pymupdf document."""
    doc = MagicMock()
    doc.__iter__ = lambda self: iter(pages)
    doc.__len__ = lambda self: len(pages)
    doc.metadata = metadata or {}
    return doc


def _text_page(text: str):
    p = MagicMock()
    p.get_text.return_value = text
    return p


# ═══════════════════════════════════════════════════════════════════════════════
# detect_pdf_kind
# ═══════════════════════════════════════════════════════════════════════════════


class TestDetectPDFKind:
    @pytest.mark.asyncio
    async def test_native_pdf(self) -> None:
        doc = _mock_doc([_text_page("Hello"), _text_page("World")])
        with patch("pymupdf.open", return_value=doc):
            kind = await detect_pdf_kind(b"fake-bytes")
        assert kind == PDFKind.NATIVE

    @pytest.mark.asyncio
    async def test_scanned_pdf(self) -> None:
        doc = _mock_doc([_text_page("   "), _text_page("")])
        with patch("pymupdf.open", return_value=doc):
            kind = await detect_pdf_kind(b"fake-bytes")
        assert kind == PDFKind.SCANNED

    @pytest.mark.asyncio
    async def test_mixed_pdf(self) -> None:
        doc = _mock_doc([_text_page("Real text"), _text_page("")])
        with patch("pymupdf.open", return_value=doc):
            kind = await detect_pdf_kind(b"fake-bytes")
        assert kind == PDFKind.MIXED


# ═══════════════════════════════════════════════════════════════════════════════
# extract_native_text
# ═══════════════════════════════════════════════════════════════════════════════


class TestExtractNativeText:
    @pytest.mark.asyncio
    async def test_extracts_text(self) -> None:
        doc = _mock_doc(
            [_text_page("Page one"), _text_page("Page two")],
            metadata={"title": "Test Doc"},
        )
        with patch("pymupdf.open", return_value=doc):
            result = await extract_native_text(b"fake-bytes")

        assert result.kind == PDFKind.NATIVE
        assert "Page one" in result.text
        assert "Page two" in result.text
        assert result.page_count == 2
        assert result.metadata["title"] == "Test Doc"


# ═══════════════════════════════════════════════════════════════════════════════
# extract_scanned_text (docling OCR)
# ═══════════════════════════════════════════════════════════════════════════════


class TestExtractScannedText:
    @pytest.mark.asyncio
    async def test_ocr_success(self) -> None:
        doc = _mock_doc([_text_page("")])
        with (
            patch("pymupdf.open", return_value=doc),
            patch(
                "aloha.pdf.pipeline._run_docling_ocr",
                return_value="OCR text from docling",
            ) as mock_ocr,
        ):
            result = await extract_scanned_text(b"fake-scanned")

        assert result.kind == PDFKind.SCANNED
        assert "OCR text from docling" in result.text
        assert result.page_count == 1
        assert result.metadata["ocr_engine"] == "rapidocr"
        mock_ocr.assert_called_once_with(b"fake-scanned")

    @pytest.mark.asyncio
    async def test_ocr_import_error(self) -> None:
        doc = _mock_doc([_text_page("")])
        with (
            patch("pymupdf.open", return_value=doc),
            patch(
                "aloha.pdf.pipeline._run_docling_ocr",
                side_effect=ImportError("no docling"),
            ),
        ):
            result = await extract_scanned_text(b"fake-bytes")

        assert result.text == ""
        assert result.metadata["ocr_engine"] == "unavailable"

    @pytest.mark.asyncio
    async def test_ocr_runtime_error(self) -> None:
        doc = _mock_doc([_text_page("")])
        with (
            patch("pymupdf.open", return_value=doc),
            patch(
                "aloha.pdf.pipeline._run_docling_ocr",
                side_effect=RuntimeError("onnx crash"),
            ),
        ):
            result = await extract_scanned_text(b"fake-bytes")

        assert result.text == ""
        assert result.metadata["ocr_engine"] == "error"
        assert "onnx crash" in result.metadata["ocr_error"]


# ═══════════════════════════════════════════════════════════════════════════════
# process_pdf
# ═══════════════════════════════════════════════════════════════════════════════


class TestProcessPDF:
    @pytest.mark.asyncio
    async def test_routes_native(self) -> None:
        expected = ExtractionResult(
            kind=PDFKind.NATIVE, text="native", page_count=1, metadata={}
        )
        with (
            patch("aloha.pdf.pipeline.detect_pdf_kind", return_value=PDFKind.NATIVE),
            patch("aloha.pdf.pipeline.extract_native_text", return_value=expected) as m,
        ):
            result = await process_pdf(b"native-pdf")
        assert result.kind == PDFKind.NATIVE
        m.assert_called_once()

    @pytest.mark.asyncio
    async def test_routes_scanned(self) -> None:
        expected = ExtractionResult(
            kind=PDFKind.SCANNED, text="ocr", page_count=1, metadata={}
        )
        with (
            patch("aloha.pdf.pipeline.detect_pdf_kind", return_value=PDFKind.SCANNED),
            patch("aloha.pdf.pipeline.extract_scanned_text", return_value=expected) as m,
        ):
            result = await process_pdf(b"scanned-pdf")
        assert result.kind == PDFKind.SCANNED
        m.assert_called_once()

    @pytest.mark.asyncio
    async def test_routes_mixed_to_native(self) -> None:
        expected = ExtractionResult(
            kind=PDFKind.NATIVE, text="mixed", page_count=2, metadata={}
        )
        with (
            patch("aloha.pdf.pipeline.detect_pdf_kind", return_value=PDFKind.MIXED),
            patch("aloha.pdf.pipeline.extract_native_text", return_value=expected) as m,
        ):
            await process_pdf(b"mixed-pdf")
        m.assert_called_once()

    @pytest.mark.asyncio
    async def test_reads_from_path(self, tmp_path) -> None:
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"fake-pdf")

        expected = ExtractionResult(
            kind=PDFKind.NATIVE, text="from file", page_count=1, metadata={}
        )
        with (
            patch("aloha.pdf.pipeline.detect_pdf_kind", return_value=PDFKind.NATIVE),
            patch("aloha.pdf.pipeline.extract_native_text", return_value=expected),
        ):
            result = await process_pdf(pdf_file)
        assert result.text == "from file"

    @pytest.mark.asyncio
    async def test_rejects_bad_type(self) -> None:
        with pytest.raises(TypeError, match="Unsupported source type"):
            await process_pdf(12345)  # type: ignore[arg-type]
