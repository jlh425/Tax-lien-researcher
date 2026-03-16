# Research B.6.4: Handling PDFs from County Recorder and Government Sites
**Date:** 2026-03-16
**Status:** COMPLETE
**Relates to:** PRD Section 5 (Data Sources), Section 9 (Tech Stack), toresearch.md B.6.4

---

## Executive Summary

County recorder offices across the US serve deeds, liens, tax certificates, and plat maps predominantly as **scanned image PDFs** (TIFF-origin, 300 DPI, B&W bi-tonal). Newer recordings (post-2015) from counties with eRecording adoption (~90% of US population covered) are increasingly native digital PDFs, but the historical backfile (which is critical for title chain research) remains scanned imagery. The recommended pipeline is a **three-tier architecture**: (1) PyMuPDF for native PDF text extraction, (2) **marker** + **surya** (open-source, by Vik Paruchuri / Datalab) for high-quality OCR of scanned documents, and (3) **Claude API** for structured field extraction from OCR'd text. For plat maps and handwritten annotations, fall back to **PaddleOCR-VL** or **Azure Document Intelligence**. At scale (100K docs/month), self-hosted open-source OCR on GPU is **167x cheaper** than cloud APIs while delivering comparable or better accuracy.

**Recommended stack:**
- **PDF detection/routing:** PyMuPDF (fitz) -- detect native vs. scanned
- **Native PDF extraction:** PyMuPDF direct text extraction
- **Scanned PDF OCR (primary):** marker (PDF-to-markdown, uses surya internally)
- **Scanned PDF OCR (fallback for handwriting/maps):** PaddleOCR-VL-0.9B or Azure Document Intelligence
- **Structured extraction:** Claude API with structured output schema
- **Preprocessing:** OpenCV (deskew, denoise, binarize)
- **Storage:** S3 (originals) + PostgreSQL (extracted text/fields) + pgvector (embeddings)

---

## 1. Scanned vs. Native PDF Prevalence Across US Counties

### 1.1 Overall Distribution

| Document Era | Format | Estimated % | Notes |
|-------------|--------|-------------|-------|
| **Pre-2000** | Scanned TIFF/PDF (from microfilm or paper) | ~95% | Backfile digitization projects, often 200-300 DPI B&W |
| **2000-2015** | Mixed scanned + early digital | ~70% scanned | eRecording adoption was growing; many counties still paper-first |
| **2015-present** | Digital-native PDF increasing | ~40-60% scanned | Counties with eRecording receive native PDFs; but stamps/annotations create hybrid |
| **Current new recordings** | Native digital via eRecording | ~60-70% native | 90% of US population in eRecording-capable jurisdictions |

**Key insight:** Even "native" PDFs from eRecording often become hybrid documents after the recorder adds stamps, page numbers, and recording information as image overlays. The pipeline must handle both native text layers and stamped image regions.

### 1.2 eRecording Adoption

- Counties representing ~90% of the US population accept eRecordings (Property Records Industry Association data)
- ~1,600-1,700 jurisdictions still do not accept electronic recordings (~18% of population)
- As of 2020, only half of US recording jurisdictions accepted eRecorded documents; adoption has accelerated significantly since then
- Maricopa County AZ: >90% of documents now recorded digitally

### 1.3 Specific County Analysis

| County | Population | Document Format | Image Specs | eRecording | Notes |
|--------|-----------|----------------|-------------|------------|-------|
| **Cook County, IL** | 5.2M | TIFF (required for eRecording), PDF for retrieval | 300 DPI min, B&W | Yes (via Simplifile) | Recorder merged with County Clerk Dec 2020; documents must be "clearly scanned as TIFF only" |
| **Maricopa County, AZ** | 4.5M | PDF or TIFF Group 4 | 300x300 DPI min, portrait mode, 8.47-8.53" width | Yes (90%+ digital) | Digital Recording Program requires MOU; strict dimension requirements |
| **Los Angeles County, CA** | 10M | PDF (via approved eRecording vendors) | Standard county specs | Yes (via Simplifile, ICE) | Registrar-Recorder/County Clerk; high volume |
| **Harris County, TX** | 4.7M | PDF (via eRecording vendors) | Standard specs | Yes | $25 first page + $4/additional; eRecording through approved vendors only |
| **Miami-Dade County, FL** | 2.7M | Scanned PDF (submitter scans, uploads via vendor) | Standard specs | Yes | $10 first page + $8.50/additional; recorded image available within 24 hours |

### 1.4 Image Quality Characteristics

| Characteristic | Typical Value | Range |
|---------------|---------------|-------|
| **Resolution** | 300 DPI | 200-400 DPI (200 DPI minimum in some states like Mississippi) |
| **Color mode** | B&W bi-tonal (1-bit) | B&W for text docs; grayscale/color for plat maps |
| **Format** | TIFF Group 4 (archival) / PDF (delivery) | Some counties use JPEG for color pages |
| **Skew** | 0-3 degrees typical | Up to 5+ degrees for older scans |
| **Noise** | Low-medium for post-2000; high for microfilm conversions | Speckle noise common in older records |
| **Legibility** | Up to 25% of older TIFF images contain illegible data | Modern scans generally clean |

### 1.5 Alternative Formats

- **TIFF Group 4:** Primary archival format for most county recording systems; converted to PDF for public delivery
- **DJVU:** Extremely rare in US county recording; not encountered in major counties
- **JPEG:** Used by some counties for color pages within multi-page TIFF/PDF documents
- **PDF/A:** Increasingly required for long-term archival by some jurisdictions
- Output formats from digitization vendors: PDF, PDF/A, JPG, TIFF, and GIF

---

## 2. OCR Tools and Libraries Comparison (2025-2026)

### 2.1 Comprehensive Comparison Matrix

| Tool | Type | Accuracy (typed) | Accuracy (handwritten) | Speed (per page) | Cost | Table Extraction | Setup Complexity | Best For |
|------|------|------------------|----------------------|-------------------|------|-----------------|-----------------|----------|
| **Tesseract 5.x** | Open source (CPU) | ~90-93% | Poor (~60%) | 3-6 sec/page (CPU) | Free | Basic (hOCR) | Low | Clean typed text, batch processing |
| **PaddleOCR PP-OCRv5** | Open source (GPU/CPU) | ~95-97% | Good (~80%) | ~2 sec/page (GPU) | Free | Good (PP-StructureV3) | Medium | Complex layouts, multilingual |
| **PaddleOCR-VL-0.9B** | Open source VLM | ~97%+ | Very good | ~2-3 sec/page (GPU) | Free | Excellent | Medium | Document understanding, tables |
| **EasyOCR** | Open source (GPU/CPU) | ~95% | Fair (~70%) | ~1.5 sec/page (GPU) | Free | None built-in | Very low | Quick prototyping, noisy images |
| **Surya** | Open source (GPU) | ~97.7% | Good | ~0.4 sec/image (A10 GPU) | Free* | Yes (table recognition) | Low | Line-level detection, 90+ languages |
| **marker** | Open source (GPU) | ~97%+ | Good (via surya) | 25 pages/sec (H100 batch) | Free* | Yes (via surya) | Low | PDF-to-markdown conversion |
| **Docling (IBM)** | Open source | ~97-100% (typed) | Fair | ~6 sec/page | Free | 97.9% cell accuracy | Medium | Enterprise document conversion |
| **Azure Document Intelligence** | Cloud API | ~99%+ | Very good | ~2-3 sec/page | $1.50/1K pages (Read) | Excellent | Low (API) | Production accuracy, handwriting |
| **Google Document AI** | Cloud API | ~98.7% | ~92.3% | ~2-3 sec/page | $1.50/1K pages (OCR) | Good | Low (API) | Multilingual, high accuracy |
| **AWS Textract** | Cloud API | ~97-99% | Good | ~2-3 sec/page | $1.50/1K pages (text) | Excellent ($65/1K) | Low (API) | AWS ecosystem, forms/tables |

*Surya and marker use modified AI2 Open Rail-M license for model weights (free for research, personal use, startups <$2M); GPL for code. Commercial licensing available.

### 2.2 Detailed Tool Analysis

#### Tesseract / pytesseract
- **Strengths:** Mature, well-documented, broad language support (100+ languages), CPU-only (no GPU needed), zero cost
- **Weaknesses:** Accuracy degrades on complex layouts, poor handwriting recognition, no built-in table extraction, cannot handle curved/distorted text, requires good preprocessing
- **Setup:** `apt-get install tesseract-ocr && pip install pytesseract`
- **RAM:** ~25MB per page at 300 DPI
- **Verdict:** Adequate baseline for clean typed deeds; insufficient for complex documents or handwritten annotations

#### Docling (IBM Granite-Docling)
- **Strengths:** Full document understanding (not just OCR), 100% text fidelity on dense paragraphs, 97.9% table cell accuracy, 258M parameter model (tiny), 30x speedup vs. traditional OCR in time-to-solution, trained on 81K labeled pages (patents, manuals, 10-K filings)
- **Weaknesses:** 6.28 sec/page processing speed (moderate), linear scaling, less mature ecosystem than Tesseract
- **Setup:** `pip install docling`
- **Verdict:** Excellent for structured document conversion; strong table extraction makes it good for tax documents

#### Azure Document Intelligence
- **Strengths:** 99%+ accuracy for text/handwriting/tables, 12+ prebuilt models (invoices, contracts, tax forms, mortgages, checks), confidence scores per field, handles mortgage documents natively
- **Weaknesses:** Cloud-only (data leaves your infrastructure), cost scales with volume, no legal-description-specific prebuilt model
- **Pricing:** $1.50/1,000 pages (Read/OCR), $10/1,000 pages (Layout), $12.50/1,000 pages (General Document), commitment discounts available
- **Verdict:** Best cloud option for production accuracy; ideal fallback for difficult documents

#### Google Document AI
- **Strengths:** 98.7% accuracy on clean documents, 92.3% on handwritten notes, Form Parser for structured extraction, good API
- **Weaknesses:** Accuracy drops on highly variable documents, Form Parser pricing is expensive ($30/1K pages standard)
- **Pricing:** $1.50/1,000 pages (OCR), $30/1,000 pages (Form Parser)
- **Verdict:** Good alternative to Azure; slightly lower accuracy on handwriting

#### AWS Textract
- **Strengths:** Excellent table/form extraction, Queries feature for targeted field extraction, deep AWS integration, async batch processing
- **Weaknesses:** Per-feature billing adds up (Forms + Tables = $65/1K pages), outputs expire after 7 days
- **Pricing:** $1.50/1,000 pages (text), $50/1,000 pages (tables), $50/1,000 pages (forms), combined features stack
- **Verdict:** Best if already in AWS ecosystem; Queries feature useful for targeted extraction

#### PaddleOCR / PaddleOCR-VL
- **Strengths:** 92.86% on OmniDocBench (vs GPT-4o's 85.80), PP-StructureV3 for tables/handwriting, PP-OCRv5 latest iteration, extremely lightweight models (~2MB for English), VLM version handles complex document understanding
- **Weaknesses:** Documentation primarily in Chinese, Baidu ecosystem, 4.2 sec model initialization time, somewhat slower than Tesseract on simple text
- **Setup:** `pip install paddleocr paddlepaddle-gpu`
- **Verdict:** Best open-source option for complex documents and tables; VLM version is state-of-the-art

#### EasyOCR
- **Strengths:** Simplest API (`reader.readtext(image)`), better than Tesseract on noisy images (~95% accuracy), handles multi-line text well, fastest local OCR on GPU
- **Weaknesses:** No table extraction, no layout analysis, limited customization, CRNN architecture less sophisticated than transformer-based models
- **Setup:** `pip install easyocr`
- **Verdict:** Good for quick prototyping; use PaddleOCR or surya for production

#### Surya
- **Strengths:** 97.7% overall accuracy (best on invoices), line-level text detection, layout analysis, table recognition, reading order detection, 90+ languages, outperforms Tesseract in both speed and accuracy
- **Weaknesses:** Modified license restricts commercial use for companies >$2M revenue/funding, line-level (not word-level) detection, requires GPU for reasonable speed
- **Benchmarks:** 0.97114 precision, 0.96225 recall (text detection); outperforms Google Cloud Vision on many languages
- **Verdict:** Excellent overall OCR; used internally by marker

#### marker (by Vik Paruchuri / Datalab)
- **Strengths:** PDF-to-markdown conversion (ideal for LLM consumption), 25 pages/sec on H100 GPU, handles tables/forms/equations/links, optional LLM mode for higher accuracy, built on surya, processes PDF/image/PPTX/DOCX/XLSX/HTML/EPUB
- **Weaknesses:** Same license restrictions as surya (commercial >$2M requires license), GPU recommended for batch processing, relatively new project
- **Setup:** `pip install marker-pdf`
- **Verdict:** **Top recommendation for the Aloha pipeline** -- converts PDFs directly to LLM-ready markdown

### 2.3 Best Tool by Document Type

| Document Type | Primary Recommendation | Fallback | Rationale |
|--------------|----------------------|----------|-----------|
| **(a) Typed legal text** (deeds, liens) | **marker** (surya internally) | Tesseract 5 (CPU fallback) | 97%+ accuracy on typed text, markdown output ideal for LLM extraction |
| **(b) Handwritten notes on deeds** | **Azure Document Intelligence** | PaddleOCR-VL-0.9B | Azure leads at ~99% handwriting accuracy; PaddleOCR-VL strong open-source alternative |
| **(c) Plat maps with text labels** | **PaddleOCR** + OpenCV | Azure Document Intelligence | PaddleOCR handles rotated/curved text on maps; OpenCV for diagram region detection |
| **(d) Tables in tax documents** | **Docling** or **marker** | AWS Textract (Queries) | Docling: 97.9% cell accuracy; marker handles tables well in markdown output |

---

## 3. PDF Processing Pipeline Architecture

### 3.1 Native vs. Scanned Detection

**Recommended approach using PyMuPDF:**

```python
import fitz  # PyMuPDF

def classify_pdf(pdf_path: str) -> str:
    """Classify PDF as 'native', 'scanned', or 'hybrid'."""
    doc = fitz.open(pdf_path)
    results = []

    for page in doc:
        text = page.get_text().strip()
        images = page.get_images()

        # Calculate image coverage
        image_area = 0
        page_area = abs(page.rect)
        for img in images:
            xref = img[0]
            try:
                bbox = page.get_image_bbox(img)
                image_area += abs(bbox)
            except:
                pass

        coverage = image_area / page_area if page_area > 0 else 0
        has_text = len(text) > 50  # Meaningful text threshold
        is_full_page_image = coverage >= 0.85

        if is_full_page_image and not has_text:
            results.append("scanned")
        elif has_text and not is_full_page_image:
            results.append("native")
        else:
            results.append("hybrid")

    doc.close()

    # Classify overall document
    if all(r == "native" for r in results):
        return "native"
    elif all(r == "scanned" for r in results):
        return "scanned"
    else:
        return "hybrid"
```

**Classification logic:**
1. Extract text with PyMuPDF -- if substantial text exists, it is native or hybrid
2. Enumerate images and calculate page coverage ratio (`image_bbox_area / page_rect_area`)
3. If image coverage >= 85% and text < 50 chars, classify as scanned
4. If both text and images present, classify as hybrid (process both ways)
5. Resolution check: if image dimensions >> page dimensions, calculate DPI to confirm scan

### 3.2 Pre-processing Pipeline for Scanned Documents

```python
import cv2
import numpy as np

def preprocess_for_ocr(image: np.ndarray) -> np.ndarray:
    """Full preprocessing pipeline for scanned deed images."""

    # 1. Grayscale conversion
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # 2. Denoise (median blur for speckle noise common in scanned docs)
    denoised = cv2.medianBlur(gray, 3)

    # 3. Deskew
    coords = np.column_stack(np.where(denoised > 0))
    if len(coords) > 100:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        if abs(angle) > 0.5:  # Only deskew if significant
            h, w = denoised.shape
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            denoised = cv2.warpAffine(
                denoised, M, (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE
            )

    # 4. Binarize (Otsu's method -- adaptive for varying scan quality)
    _, binary = cv2.threshold(
        denoised, 0, 255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    # 5. Ensure minimum 300 DPI equivalent resolution
    h, w = binary.shape
    if w < 2550:  # Less than 8.5" * 300 DPI
        scale = 2550 / w
        binary = cv2.resize(
            binary, None, fx=scale, fy=scale,
            interpolation=cv2.INTER_CUBIC
        )

    return binary
```

**Preprocessing steps in order:**
1. **Grayscale conversion** -- remove color channel noise
2. **Denoise** -- median blur (3x3 kernel) for speckle noise; Gaussian blur for scanner artifacts
3. **Deskew** -- calculate rotation angle via `minAreaRect`, apply `warpAffine`; skip if angle < 0.5 degrees
4. **Binarize** -- Otsu's thresholding adapts to varying scan quality automatically
5. **Resolution scaling** -- upscale to 300 DPI equivalent if below threshold
6. **(Optional) unpaper** -- specialized tool for removing paper artifacts from scans

### 3.3 Multi-page Document Handling

Deeds typically range from 2-20+ pages. The pipeline should:

```python
from pathlib import Path
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict

def process_multipage_deed(pdf_path: str) -> dict:
    """Process a multi-page deed with marker."""

    # Step 1: Classify the PDF
    doc_type = classify_pdf(pdf_path)

    if doc_type == "native":
        # Direct text extraction (fast path)
        return extract_native_text(pdf_path)

    # Step 2: Use marker for scanned/hybrid documents
    converter = PdfConverter(artifact_dict=create_model_dict())
    rendered = converter(pdf_path)

    return {
        "markdown": rendered.markdown,
        "metadata": rendered.metadata,
        "pages": len(rendered.pages),
        "images": rendered.images,  # Extracted images (stamps, signatures)
    }

def extract_native_text(pdf_path: str) -> dict:
    """Fast path for native PDFs using PyMuPDF."""
    import fitz
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        pages.append({
            "page_num": page.number + 1,
            "text": page.get_text("text"),
            "blocks": page.get_text("dict")["blocks"],  # Structured blocks
        })
    doc.close()
    return {"pages": pages, "type": "native"}
```

**Key considerations for multi-page deeds:**
- Process pages in parallel where possible (marker supports batch mode)
- Maintain page order for legal validity
- Extract recording stamps (usually on first page) separately
- Handle cover sheets (recording office adds these) -- detect and skip or process separately
- Legal description may span multiple pages -- concatenate before parsing
- Signature pages contain critical data (notary stamps, execution dates)

### 3.4 Field Extraction from Deeds

Target fields for extraction:

| Field | Location in Deed | Extraction Difficulty |
|-------|-----------------|---------------------|
| **Grantor** (seller) | First paragraph or preamble | Medium -- name formatting varies |
| **Grantee** (buyer) | First paragraph or preamble | Medium -- same as grantor |
| **Legal description** | Body of deed (often multi-line) | High -- complex formats (metes & bounds, lot/block, section-township-range) |
| **Recording date** | Recorder's stamp (first page) | Low -- structured format |
| **Document number** | Recorder's stamp (first page) | Low -- numeric, structured |
| **Consideration amount** | Transfer tax declaration or deed body | Medium -- may say "$10 and other good and valuable consideration" |
| **Property address** | Body or preamble | Medium -- may not be present (legal description used instead) |
| **Document type** | Title or preamble | Low -- "Warranty Deed", "Quitclaim Deed", etc. |
| **APN / Parcel number** | Body or tax declaration | Medium -- format varies by county |
| **Notary information** | Last page(s) | Medium -- signatures, stamps, dates |

### 3.5 Plat Map and Survey Document Handling

Plat maps require special processing because they contain both text labels and diagrams:

1. **Region detection:** Use surya's layout analysis to identify text regions vs. diagram regions
2. **Text extraction:** Apply OCR only to text regions (lot numbers, dimensions, street names, legal descriptions in margins)
3. **Diagram preservation:** Store the original image for visual reference; do not attempt to OCR diagram lines
4. **Orientation handling:** Text labels on plat maps can appear at any angle; PaddleOCR handles rotated text well
5. **Scale/dimension extraction:** Extract scale bars and dimension annotations as separate fields

### 3.6 Caching Strategy

**"OCR once, serve many" principle:**

```
Original PDF (S3/MinIO)
    |
    v
classify_pdf() --> native? --> extract_text() --> store in PostgreSQL
                    |
                    v
                  scanned/hybrid
                    |
                    v
                preprocess() --> marker OCR --> markdown text
                    |
                    v
              Claude extraction --> structured fields
                    |
                    v
              PostgreSQL (extracted_text, structured_fields, confidence_scores)
```

- **Original PDFs:** Store in S3/MinIO with content-addressable hash (SHA-256) as key
- **Extracted text:** Store in PostgreSQL `document_extractions` table with full-text search index (tsvector)
- **Structured fields:** Store in normalized tables (deeds, liens, etc.)
- **Confidence scores:** Store per-field confidence for quality monitoring
- **Cache key:** SHA-256 hash of PDF content + OCR engine version
- **Invalidation:** Re-OCR only when engine version changes or quality review flags issues

---

## 4. Structured Data Extraction from Legal Documents

### 4.1 LLM-Based Extraction (Claude)

**Can Claude reliably extract structured fields from OCR'd deed text?** Yes, with high reliability when combined with proper prompting.

**Recommended approach:**

```python
import anthropic

DEED_EXTRACTION_PROMPT = """Extract the following fields from this recorded deed text.
Return a JSON object with these fields. Use null for any field not found.

Fields:
- document_type: string (e.g., "Warranty Deed", "Quitclaim Deed", "Trust Deed")
- recording_date: string (ISO 8601 format, e.g., "2024-03-15")
- document_number: string (recording/instrument number)
- book_page: string (if recorded by book/page, e.g., "Book 1234, Page 567")
- grantor: array of objects [{name: string, entity_type: "individual"|"corporation"|"llc"|"trust"}]
- grantee: array of objects [{name: string, entity_type: "individual"|"corporation"|"llc"|"trust"}]
- legal_description: string (full legal description, preserve formatting)
- property_address: string or null
- parcel_number: string or null (APN/tax ID)
- consideration: string (dollar amount or description, e.g., "$450,000" or "$10 and other valuable consideration")
- county: string
- state: string
- notary_date: string (ISO 8601) or null
- notary_name: string or null
- deed_restrictions: array of strings or null
- easements_mentioned: array of strings or null

IMPORTANT:
- Preserve exact spelling of names as they appear in the document
- For legal descriptions, preserve the full text including all metes and bounds, lot/block references, or section-township-range
- If OCR quality is poor and a field is uncertain, include it but add a _confidence field (0.0-1.0)
- Do not hallucinate or infer data not present in the text

Deed text:
{deed_text}
"""

async def extract_deed_fields(deed_text: str) -> dict:
    client = anthropic.AsyncAnthropic()
    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": DEED_EXTRACTION_PROMPT.format(deed_text=deed_text)
        }],
    )
    return json.loads(message.content[0].text)
```

**Accuracy expectations:**
- **GPT-4/Claude on clean OCR text:** 95-99% field-level accuracy
- **On poor OCR text:** 80-90% accuracy (OCR errors propagate)
- **Cost:** ~$0.003-0.01 per deed page with Claude Sonnet 4 (input tokens dominate)
- **Latency:** 2-5 seconds per deed

**Key advantages of LLM extraction over regex/NER:**
- Handles natural language variation ("hereby grants and conveys" vs. "does grant, bargain, sell, and convey")
- Understands context (distinguishes grantor from grantee based on deed structure)
- Handles entity names with complex formatting ("JOHN R. SMITH, as Trustee of the Smith Family Trust dated January 1, 2020")
- Can extract from poor OCR by inferring from context

### 4.2 NER for Legal Documents

**Specialized models available:**
- **LegNER:** Domain-adapted transformer for legal NER and text anonymization (F1: 0.96)
- **Legal-BERT / CaseLawBERT / ContractBERT:** Pretrained transformers for legal domain
- **John Snow Labs Legal NLP:** Commercial; recognizes grantor, grantee, legal descriptions, dates, amounts
- **OpenNyAI Legal NER:** Open source (focused on Indian legal system, but architecture adaptable)
- **IBM Granite 4 for Legal NER:** Small language model approach, promising results

**Recommendation:** Use Claude API for extraction (more flexible, higher accuracy on varied formats) rather than training domain-specific NER models. Reserve NER for high-volume batch processing where API costs become prohibitive (>500K pages/month).

### 4.3 Regex Patterns for Common Deed Fields

```python
import re

# Recording stamp patterns
RECORDING_DATE = re.compile(
    r'(?:recorded|filed|received)\s*(?:on)?\s*'
    r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\w+\s+\d{1,2},?\s+\d{4})',
    re.IGNORECASE
)

DOCUMENT_NUMBER = re.compile(
    r'(?:instrument|document|recording)\s*(?:no|number|#)\.?\s*[:.]?\s*'
    r'(\d{4,}[-]?\d*)',
    re.IGNORECASE
)

BOOK_PAGE = re.compile(
    r'(?:book|volume|liber)\s*(\d+)\s*(?:,\s*)?(?:page|pg)\s*(\d+)',
    re.IGNORECASE
)

# Legal description patterns
SECTION_TOWNSHIP_RANGE = re.compile(
    r'(?:Section|Sec\.?)\s*(\d+),?\s*'
    r'(?:Township|Twp\.?|T\.?)\s*(\d+[NS]?),?\s*'
    r'(?:Range|Rng\.?|R\.?)\s*(\d+[EW]?)',
    re.IGNORECASE
)

LOT_BLOCK = re.compile(
    r'(?:Lot|Lots)\s*([\d,\s&and]+),?\s*'
    r'(?:Block|Blk\.?)\s*([\w\d]+),?\s*'
    r'(?:of\s+)?(.+?)(?:,\s*(?:as\s+)?(?:recorded|filed|per\s+plat))',
    re.IGNORECASE
)

# Parcel/APN patterns (varies by county)
APN_PATTERNS = [
    re.compile(r'(?:APN|Parcel\s*(?:No|Number|ID|#))\.?\s*[:.]?\s*'
               r'([\d]+-[\d]+-[\d]+(?:-[\d]+)?)', re.IGNORECASE),
    re.compile(r'(?:Tax\s*(?:ID|Map|Parcel))\.?\s*[:.]?\s*'
               r'([\d.]+[-][\d.]+[-][\d.]+)', re.IGNORECASE),
]

# Consideration/transfer tax
CONSIDERATION = re.compile(
    r'(?:consideration|sum)\s+of\s+'
    r'(?:\$\s*)?(\$?[\d,]+(?:\.\d{2})?)',
    re.IGNORECASE
)

# Grantor/Grantee (basic pattern -- LLM extraction preferred)
GRANTOR_PATTERN = re.compile(
    r'(?:grantor|seller|party of the first part)[:\s]*'
    r'([A-Z][A-Za-z\s,\.]+?)(?=\s*(?:,\s*(?:a|an|the)|hereinafter|grants?))',
    re.IGNORECASE
)

GRANTEE_PATTERN = re.compile(
    r'(?:grantee|buyer|party of the second part)[:\s]*'
    r'([A-Z][A-Za-z\s,\.]+?)(?=\s*(?:,\s*(?:a|an|the)|hereinafter|the following))',
    re.IGNORECASE
)
```

**Note:** Regex patterns are useful for pre-filtering and validation but insufficient as the sole extraction method. Deed language varies enormously across states, time periods, and document types. Use regex for recording stamps (standardized format) and LLM for semantic fields (grantor, grantee, legal description).

### 4.4 Handling Poor OCR Quality

**Confidence score architecture:**

```python
class ExtractionResult:
    """Result of field extraction with confidence scoring."""

    def __init__(self):
        self.fields: dict = {}
        self.field_confidences: dict = {}
        self.overall_confidence: float = 0.0
        self.needs_review: bool = False
        self.review_reasons: list[str] = []

    def add_field(self, name: str, value: str, confidence: float):
        self.fields[name] = value
        self.field_confidences[name] = confidence
        if confidence < 0.7:
            self.needs_review = True
            self.review_reasons.append(
                f"Low confidence ({confidence:.0%}) for field '{name}'"
            )

# Confidence thresholds
THRESHOLDS = {
    "auto_accept": 0.90,    # Accept without review
    "auto_review": 0.70,    # Flag for human review
    "auto_reject": 0.50,    # Reject -- re-process with different OCR engine or manual entry
}
```

**Quality recovery strategies:**
1. **Multi-engine OCR:** If primary OCR (marker/surya) produces low-confidence result, retry with Azure Document Intelligence
2. **Image enhancement:** Apply additional preprocessing (higher-contrast binarization, morphological operations) and re-OCR
3. **Confidence voting:** Run two OCR engines, compare outputs, use higher-confidence result per field
4. **Human review queue:** Route low-confidence documents to a review interface; store corrections as training data
5. **Partial extraction:** Accept high-confidence fields, flag only low-confidence ones for review

---

## 5. Performance and Cost at Scale

### 5.1 Processing Speed Comparison

| Tool | Speed (per page) | Hardware | Throughput (pages/hour) | Batch Mode |
|------|-----------------|----------|------------------------|------------|
| **PyMuPDF (native text)** | ~0.01 sec | CPU | ~360,000 | N/A |
| **Tesseract 5** | 3-6 sec | CPU (4 cores) | 600-1,200 | Yes |
| **PaddleOCR PP-OCRv5** | ~2 sec | GPU (A10) | ~1,800 | Yes |
| **PaddleOCR-VL-0.9B** | ~2-3 sec | GPU (A10) | ~1,200-1,800 | Yes |
| **EasyOCR** | ~1.5 sec | GPU | ~2,400 | Limited |
| **Surya** | ~0.4 sec | GPU (A10) | ~9,000 | Yes |
| **marker** | 0.04 sec/page (batch) | GPU (H100) | ~90,000 | Yes (optimized) |
| **marker** | ~2-3 sec/page | GPU (A10, serial) | ~1,200-1,800 | Yes |
| **Docling** | ~6 sec | CPU/GPU | ~600 | Yes |
| **Unstructured** | ~51 sec (1 page!) | CPU/GPU | ~70 | Yes |
| **Azure Doc Intelligence** | ~2-3 sec | Cloud | ~1,200-1,800 | Yes (async) |
| **Google Document AI** | ~2-3 sec | Cloud | ~1,200-1,800 | Yes (batch) |
| **AWS Textract** | ~2-3 sec | Cloud | ~1,200-1,800 | Yes (async) |

### 5.2 Cost Analysis at Scale

**Scenario: 100,000 documents/month, average 4 pages/document = 400,000 pages/month**

| Approach | Monthly Cost | Notes |
|----------|-------------|-------|
| **marker/surya (self-hosted, A10 GPU)** | ~$200-400 | Lambda Labs A10 ~$0.60/hr; ~220 hours for 400K pages at 1,800 pages/hr |
| **marker/surya (self-hosted, H100)** | ~$100-200 | Lambda Labs H100 ~$2.50/hr; ~4.4 hours at 90K pages/hr (batch) |
| **PaddleOCR (self-hosted, A10 GPU)** | ~$200-400 | Similar compute profile to marker |
| **Tesseract (self-hosted, CPU)** | ~$150-300 | 4-core VM ~$0.15/hr; ~333 hours for 400K pages |
| **Azure Document Intelligence (Read)** | ~$600 | $1.50/1K pages x 400K pages; commitment tier may reduce |
| **Google Document AI (OCR)** | ~$600 | $1.50/1K pages x 400K pages |
| **AWS Textract (text + tables)** | ~$26,000 | $65/1K pages for Forms+Tables x 400K pages |
| **AWS Textract (text only)** | ~$600 | $1.50/1K pages x 400K pages |
| **Claude Sonnet 4 (extraction only)** | ~$400-1,200 | ~$0.003-0.01/page for structured extraction of pre-OCR'd text |
| **Docling (self-hosted)** | ~$400-600 | ~667 hours at 600 pages/hr |

**Self-hosted open-source OCR (marker on GPU) is 167x cheaper per page than vendor cloud APIs** while delivering comparable or better accuracy on document parsing tasks (PaddleOCR-VL scores 92.86 on OmniDocBench vs GPT-4o's 85.80).

### 5.3 Recommended Cost Architecture

| Volume Tier | Primary OCR | Extraction | Estimated Monthly Cost |
|------------|------------|------------|----------------------|
| **MVP (1K docs/month)** | marker (single A10 GPU, shared) | Claude Sonnet 4 | ~$50-100 |
| **Growth (10K docs/month)** | marker (dedicated A10 GPU) | Claude Sonnet 4 | ~$150-300 |
| **Scale (100K docs/month)** | marker (H100 batch) + Azure fallback | Claude Sonnet 4 (batch API) | ~$500-1,200 |
| **Enterprise (500K+ docs/month)** | marker cluster (multi-GPU) + PaddleOCR-VL | Claude + fine-tuned NER | ~$2,000-5,000 |

### 5.4 Storage Considerations

| Item | Size Per Document | 100K Docs/Month | Annual Storage |
|------|------------------|-----------------|----------------|
| **Original PDF** | ~500KB-2MB (avg ~800KB) | ~80 GB | ~960 GB |
| **Extracted text (markdown)** | ~5-20KB | ~1.5 GB | ~18 GB |
| **Structured JSON fields** | ~1-3KB | ~200 MB | ~2.4 GB |
| **Extracted images (stamps, signatures)** | ~50-200KB | ~15 GB | ~180 GB |
| **Total per month** | | ~97 GB | ~1.16 TB |

**Storage costs (AWS S3):**
- S3 Standard: $0.023/GB = ~$2.23/month for 97 GB = ~$27/year growing
- S3 Intelligent-Tiering: Automatic cost optimization for mixed access patterns
- S3 Glacier Deep Archive: $0.00099/GB for originals older than 90 days = ~$0.10/month for old originals
- **Estimated annual storage cost at 100K docs/month: $50-100/year** (with lifecycle policies)

---

## 6. Existing Solutions and Frameworks

### 6.1 County Recorder Document Processing Tools

**No open-source tools exist specifically for county recorder document processing.** This is a gap in the market. The closest available tools are:

- **Tyler Technologies Eagle Recorder / iasWorld:** Commercial. Powers ~2,000 jurisdictions. Handles document imaging, indexing, and search. Not available as standalone API.
- **Cott Systems:** Commercial. Provides recording, indexing, and digitization services to county recorders. Back-file scanning services.
- **US Imaging / BMI Imaging:** Commercial scanning vendors. Convert paper/microfilm to digital at 300 DPI TIFF. Not processing tools.
- **Revolution Data Systems:** Commercial. Deed book scanning and indexing services.

### 6.2 Specialized Commercial Solutions

| Solution | Focus | Key Feature | Pricing |
|----------|-------|-------------|---------|
| **Affinda** | Property deed extraction | >99% accuracy claimed, extracts grantor/grantee/legal description/APN, handles low-quality scans | Custom enterprise pricing |
| **V7 Go** | Deed analysis agent | Trained on county recorder scans, extracts chain of title, flags encumbrances, 12x faster than manual | Custom pricing |
| **ABBYY Vantage** | General IDP | Handles 200+ languages, complex tables, handwriting, checkmarks; legal document classification | Enterprise ($34.50-$49.50/user/year for basic) |
| **Kofax/Tungsten TotalAgility** | Enterprise automation | Deep customization, multi-step workflows, highest scalability | Enterprise pricing |
| **Docsumo** | Document extraction | Human-in-the-loop verification for accuracy | Pay-per-document |

**V7 Go's Deed Analysis Agent** is the most directly relevant commercial solution:
- Specifically trained for county recorder documents
- Handles low-quality scans, faded historical documents, handwritten script
- Extracts grantor, grantee, chain of title, easements, liens, restrictive covenants
- Extracts execution date, recording date, parcel/tax ID, witness/notary info
- OCR fine-tuned for legal and property terminology
- Does not train on customer data

### 6.3 Unstructured.io

- **Strengths:** Open-source ETL for document processing; handles PDF, HTML, Word, images; OCR integration; chunking for RAG; SOC 2/HIPAA/GDPR compliant
- **Weaknesses:** Very slow (51 seconds for 1 page!); 75% accuracy on complex tables; inconsistent column handling
- **Government PDF handling:** Can process them, but speed makes it impractical for batch processing
- **Verdict:** Use Unstructured only as a LangChain/LlamaIndex document loader for non-critical paths; do NOT use as primary OCR pipeline

### 6.4 LlamaIndex / LangChain Document Loaders

**LlamaIndex:**
- `LlamaParse`: Cloud service for PDF parsing; fast (~6 sec even for large documents); 35% better retrieval accuracy than LangChain in benchmarks; but requires sending data to LlamaIndex cloud
- `SimpleDirectoryReader` with PDF parser: Basic, uses PyMuPDF or pdfminer
- `DoclingReader`: Integration with IBM Docling
- **LlamaHub:** 160+ data connectors

**LangChain:**
- `UnstructuredPDFLoader`: Best for scanned documents with complex layouts; uses Unstructured.io
- `PyPDFLoader`: Basic native PDF extraction
- `AmazonTextractPDFLoader`: AWS Textract integration
- `AzureAIDocumentIntelligenceLoader`: Azure integration

**Verdict:** These loaders are adequate for feeding documents into RAG pipelines but are NOT adequate as the primary OCR/extraction pipeline. They lack:
- Fine-grained control over preprocessing
- Multi-engine fallback
- Confidence scoring
- Batch processing optimization
- Domain-specific extraction logic

Use them as optional output adapters (convert extracted text to LlamaIndex/LangChain Document objects) rather than as the processing engine.

### 6.5 October 2025 Wave: New Open-Source OCR Models

Six major open-source OCR models released in October 2025:
1. **Nanonets OCR2-3B:** Trained on 3M+ pages (research, financial, legal, healthcare, tax forms); strong on complex documents
2. **PaddleOCR-VL-0.9B:** Leading OmniDocBench scores; handles handwriting and historical documents
3. **DeepSeek-OCR-3B:** Competitive accuracy; good for structured documents
4. **Chandra-OCR-8B:** Highest olmOCR-Bench score (83.1) among open-source models
5. **OlmOCR-2-7B:** Good general-purpose OCR
6. **LightOnOCR-1B:** Ultra-lightweight, fastest inference

These models represent a significant leap in open-source OCR capability and should be evaluated for the Aloha pipeline as they mature.

---

## 7. Recommended Architecture

### 7.1 Pipeline Design

```
                        +------------------+
                        |  PDF Ingestion   |
                        |  (from scraper)  |
                        +--------+---------+
                                 |
                        +--------v---------+
                        |  SHA-256 Hash    |
                        |  Dedup Check     |
                        +--------+---------+
                                 |
                   Already processed?
                        |              |
                       Yes             No
                        |              |
                   Return cached  +----v-----+
                   results        | Store in  |
                                  | S3/MinIO  |
                                  +----+------+
                                       |
                              +--------v---------+
                              | classify_pdf()   |
                              | (PyMuPDF)        |
                              +--+------+---+----+
                                 |      |   |
                              native  hybrid scanned
                                 |      |   |
                     +-----------+   +--+   +----------+
                     |               |                  |
             +-------v------+  +-----v------+  +-------v-------+
             | PyMuPDF text | | PyMuPDF +   |  | preprocess()  |
             | extraction   | | marker OCR  |  | + marker OCR  |
             +--------------+ +-----+-------+  +-------+-------+
                     |              |                    |
                     +------+-------+--------------------+
                            |
                   +--------v----------+
                   | Markdown text     |
                   | (full document)   |
                   +--------+----------+
                            |
                   +--------v----------+
                   | Claude Sonnet 4   |
                   | Structured        |
                   | Extraction        |
                   +--------+----------+
                            |
                   +--------v----------+
                   | Confidence Check  |
                   | (thresholds)      |
                   +---+-------+-------+
                       |       |
                   >= 0.90  < 0.70
                       |       |
              +--------v--+ +--v----------+
              | Auto-save | | Human Review|
              | to DB     | | Queue       |
              +-----------+ +-------------+
```

### 7.2 Technology Stack Summary

| Component | Primary Tool | Fallback | Rationale |
|-----------|-------------|----------|-----------|
| **PDF storage** | S3/MinIO | Local filesystem | Content-addressable, scalable |
| **PDF classification** | PyMuPDF (fitz) | -- | Fast, reliable, no dependencies |
| **Native PDF extraction** | PyMuPDF | pdfminer.six | Fastest option for native text |
| **Scanned PDF preprocessing** | OpenCV | unpaper | Industry standard; Otsu binarization |
| **Scanned PDF OCR** | marker (surya) | Azure Document Intelligence | Best accuracy/cost ratio; markdown output |
| **Handwriting OCR** | Azure Document Intelligence | PaddleOCR-VL | Azure leads on handwriting; PaddleOCR-VL strong OSS option |
| **Plat map processing** | PaddleOCR + OpenCV | Azure Document Intelligence | Handles rotated text; diagram separation |
| **Table extraction** | Docling or marker | AWS Textract Queries | 97.9% cell accuracy (Docling) |
| **Structured extraction** | Claude Sonnet 4 API | Regex patterns + NER | Highest accuracy on varied deed formats |
| **Confidence scoring** | Custom (per-field) | -- | Threshold-based routing |
| **Human review UI** | Custom web interface | -- | For low-confidence results |
| **Batch processing** | Celery + Redis | -- | Async task queue for large volumes |
| **Text search** | PostgreSQL tsvector + pgvector | Elasticsearch | Already in stack; full-text + semantic |

### 7.3 Implementation Priority

| Phase | Scope | Timeline |
|-------|-------|----------|
| **Phase 1 (MVP)** | PyMuPDF classification + marker OCR + Claude extraction for typed deeds | 2-3 weeks |
| **Phase 2** | Preprocessing pipeline (OpenCV) + confidence scoring + human review queue | 1-2 weeks |
| **Phase 3** | Multi-engine fallback (Azure for handwriting) + batch processing (Celery) | 2-3 weeks |
| **Phase 4** | Plat map handling + table extraction + PaddleOCR-VL integration | 2-3 weeks |
| **Phase 5** | Scale optimization (H100 batch mode, caching, dedup) | 1-2 weeks |

### 7.4 Key Dependencies and Considerations

1. **License compliance:** marker and surya use modified AI2 Open Rail-M license -- free for startups under $2M revenue/funding. Budget for commercial license if/when crossing this threshold.
2. **GPU infrastructure:** marker/surya require GPU for production speed. Options: Lambda Labs ($0.60/hr A10), RunPod, AWS g5.xlarge ($1.006/hr), or on-prem.
3. **Claude API costs:** At 100K docs/month, Claude extraction costs ~$400-1,200/month. Use Claude's batch API (50% discount) for non-urgent processing.
4. **Data privacy:** All county recorder documents are public records. No PII concerns for the documents themselves, though extracted owner names should be handled carefully in the platform.
5. **OCR model updates:** The October 2025 wave of models (PaddleOCR-VL, Nanonets OCR2, Chandra) should be benchmarked on county recorder documents. Expect further improvements in 2026.

---

## 8. Sources and References

### County Recorder Portals and Standards
- Cook County Clerk: https://www.cookcountyclerkil.gov/recordings
- Maricopa County Recorder Digital Recording Program: https://recorder.maricopa.gov/recording/digital-recording-program.html
- Miami-Dade County Clerk Official Records: https://www.miamidadeclerk.gov/clerk/official-records.page
- Harris County Clerk: https://www.cclerk.hctx.net/RealProperty.aspx
- Los Angeles County Registrar-Recorder: https://www.lavote.gov
- PRIA Standards: https://www.hendersoncountyky.gov/437/PRIA-Standards-for-Recording-Documents

### OCR Tools
- Surya GitHub: https://github.com/datalab-to/surya
- marker GitHub: https://github.com/datalab-to/marker
- Docling: https://docling-project.github.io/docling/
- PaddleOCR: https://github.com/PaddlePaddle/PaddleOCR
- Tesseract: https://github.com/tesseract-ocr/tesseract

### Benchmarks and Comparisons
- PDF Data Extraction Benchmark 2025 (Docling vs Unstructured vs LlamaParse): https://procycons.com/en/blogs/pdf-data-extraction-benchmark/
- OCR Benchmark 2025 (Qnovi): https://www.qnovi.de/en/blog/ocr-benchmarks-2025-the-best-open-source-models-in-a-practical-test/
- 7 Best Open-Source OCR Models 2025: https://www.e2enetworks.com/blog/complete-guide-open-source-ocr-models-2025
- 8 Top Open-Source OCR Models Compared: https://modal.com/blog/8-top-open-source-ocr-models-compared

### Cloud Services
- Azure Document Intelligence Pricing: https://azure.microsoft.com/en-us/pricing/details/document-intelligence/
- Google Document AI Pricing: https://cloud.google.com/document-ai/pricing
- AWS Textract Pricing: https://aws.amazon.com/textract/pricing/
- AWS S3 Pricing: https://aws.amazon.com/s3/pricing/

### Commercial Solutions
- Affinda Property Title Deed Processing: https://www.affinda.com/documents/property-title-deed
- V7 Go Deed Analysis Agent: https://www.v7labs.com/agents/deed-analysis-agent
- ABBYY Legal Document Automation: https://www.abbyy.com/solutions/legal/

### Legal NER and Extraction
- LegNER: https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1638971/full
- John Snow Labs Legal NLP: https://nlp.johnsnowlabs.com/legal_entity_recognition
- Document Data Extraction LLMs vs OCRs (2026): https://www.vellum.ai/blog/document-data-extraction-llms-vs-ocrs
