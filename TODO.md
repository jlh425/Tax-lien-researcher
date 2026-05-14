# Aloha Tax Research — TODO

## Tier 1 — Blocking (core functionality gaps)

- [x] **OCR for scanned PDFs** — Docling RapidOCR, pure-Python ONNX (commit `2e71e97`)
- [x] **GIS parcel boundary** — ArcGIS Esri rings → GeoJSON Polygon (commit `c37a77a`)
- [x] **Email/SMS outreach** — SendGrid v3 + Twilio REST via httpx (commit `3664559`)
- [x] **Stripe billing** — Real Stripe SDK: customers, checkout, webhooks (commit `e0a0729`)
- [x] **County assessor owner search** — ArcGIS multi-alias owner query cascade (commit `33a798e`)
- [x] **County URL resolver** — 4-layer pipeline: DB cache → static registry → SearXNG → LLM validation (commit `2e71e97`)

## Tier 2 — High value (tests & integration)

- [x] **Service tests** — 51 tests covering all 9 services
- [x] **API route tests** — 18 tests for auth, scan, and parcels routes
- [x] **Frontend component tests** — 42 total: Dashboard, ScanForm, ParcelCard, QueueStatusBar
- [x] **CI/CD** — GitHub Actions: backend (ruff + mypy + pytest) + frontend (tsc + vitest + build)
- [x] **End-to-end MCP server integration tests** — 7 tests for CourtListener, Cobalt, Google Maps

## Tier 3 — Polish

- [x] **Docker health checks & resource limits** — health checks + memory/CPU limits
- [x] **Missing frontend pages** — Settings + Queue History
- [x] **`.env.example` completeness** — All missing keys added
- [x] **Login/auth UI** — Login/register, Zustand auth store, route protection

## Tier 4 — Business Intelligence (Entity Research expansion)

- [x] **4.1 — Wire UCC MCP server** — search_ucc_filings integrated into Entity Research Agent
- [x] **4.2 — Wire Court Records MCP server** — federal cases, state liens, bankruptcy
- [x] **4.3 — Scoring Agent financial health signals** — UCC/liens/bankruptcy boost motivation
- [x] **4.4 — Business Contact Enrichment** — People Data Labs + Hunter.io email verification

## Tier 5 — Code Quality & Hardening

- [x] **CORS configuration** — Replaced permissive wildcard CORS with configurable `CORS_ALLOWED_ORIGINS`
- [x] **Secret key validation** — Production validator rejects default `SECRET_KEY`
- [x] **Exception handling audit** — Replaced 8+ silent `except: pass` blocks with structured logging
- [x] **Narrowed exception handlers** — Bare `except Exception` replaced with specific types in core modules
- [x] **Report agent error handling** — Added proper logging for template and PDF generation failures
- [x] **Circuit breaker for scrapers** — `CircuitBreaker` class with configurable thresholds in `BaseScraper`
- [x] **UCC input validation** — Added Pydantic field constraints to UCC API schemas
- [x] **Missing `__init__.py` files** — Added to migrations, versions, and report templates directories
- [x] **README** — Replaced empty README with proper project documentation
- [x] **`.gitignore` cleanup** — Added `uv.lock`, `.claude/worktrees/`, `Aloha/`
- [x] **`.env.example` updates** — Added `CORS_ALLOWED_ORIGINS` and `SEARXNG_URL`
- [x] **Expanded test coverage** — 1300+ backend tests, 160+ frontend tests across all layers
