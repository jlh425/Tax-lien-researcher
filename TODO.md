# Aloha Tax Research — TODO

## Tier 1 — Blocking (core functionality gaps)

- [x] **OCR for scanned PDFs** — Docling RapidOCR, pure-Python ONNX (commit `2e71e97`, replaces pytesseract)
- [x] **GIS parcel boundary** — ArcGIS Esri rings → GeoJSON Polygon (commit `c37a77a`)
- [x] **Email/SMS outreach** — SendGrid v3 + Twilio REST via httpx (commit `3664559`)
- [x] **Stripe billing** — Real Stripe SDK: customers, checkout, webhooks (commit `e0a0729`)
- [x] **County assessor owner search** — ArcGIS multi-alias owner query cascade (commit `33a798e`)
- [x] **County URL resolver** — 4-layer pipeline: DB cache → static registry → SearXNG → LLM validation (commit `2e71e97`)

## Tier 2 — High value (tests & integration)

- [x] **Service tests** — 51 tests covering all 9 services (billing, notification, outreach, auth, parcel, export, research, base, deps)
- [x] **API route tests** — 18 tests for auth, scan, and parcels routes (commit `70d4a8f`)
- [x] **Frontend component tests** — 42 total: Dashboard, ScanForm, ParcelCard, QueueStatusBar (commit `3ad5353`)
- [x] **CI/CD** — GitHub Actions: backend (ruff + mypy + pytest) + frontend (tsc + vitest + build) (commit `a46bf2d`)
- [x] **End-to-end MCP server integration tests** — 7 tests for CourtListener, Cobalt, Google Maps (commit `1006721`)

## Tier 3 — Polish

- [x] **Docker health checks & resource limits** — postgres/redis/backend/frontend health checks + memory/CPU limits (commit `37d15f6`)
- [x] **Missing frontend pages** — Settings (profile, subscription, API keys) + Queue History (status cards, agent breakdown) (commit `e5a5975`)
- [x] **`.env.example` completeness** — Added all missing keys: Stripe, SendGrid, Cobalt, Maps, Captcha (commit `3ee64a4`)
- [x] **Login/auth UI** — Login/register page, Zustand auth store, route protection, Sign Out (commit `44cc956`)

---

## Tier 4 — Business Intelligence (Entity Research expansion)

- [x] **4.1 — Wire UCC MCP server** — search_ucc_filings integrated into Entity Research Agent (commit `8ce9880`)
- [x] **4.2 — Wire Court Records MCP server** — federal cases, state liens, bankruptcy filtered into Entity fields (commit `8ce9880`)
- [ ] **4.3 — Scoring Agent financial health signals** — Factor UCC, liens, bankruptcy into scoring models
- [ ] **4.4 — Business Contact Enrichment** — Populate Entity.website/phone/email via People Data Labs

---

### 4.3 — Scoring Agent: incorporate financial health signals

**Goal**: The Scoring Agent should factor UCC filings, liens, and litigation into the
investment opportunity score. An entity with heavy debt, active tax liens, or
bankruptcy is a different risk profile.

**Files to change**:
- `src/aloha/agents/scoring/agent.py` — read Entity financial fields when computing score
- `src/aloha/agents/scoring/prompts.py` — add scoring rubric for financial health signals:
  - Active UCC filings → higher likelihood of motivated seller
  - Federal/state tax liens → very high priority lead
  - Bankruptcy → potential complication (title issues) but also motivated seller
  - Active litigation → risk factor for title insurance

**Tests**: `tests/agents/test_scoring.py` — test score adjustments for entities with/without financial data

---

### 4.4 — Business Contact Enrichment (future)

**Goal**: Populate `Entity.website`, `Entity.phone`, `Entity.email` for outreach
to business entities (currently only individual owners get contact enrichment).

**Approach options** (pick one when implementing):
- **A. Web scrape SOS filing** — many states include website/phone in annual reports
- **B. People Data Labs / Hunter.io** — existing MCP server may have business data
- **C. New provider** — ZoomInfo, Clearbit, or D&B API for business contact data
- **D. LLM web search** — SearXNG + LLM to find business contact pages

**Files to change**:
- `src/aloha/agents/entity_research/agent.py` — add `_enrich_contact()` step
- Possibly a new MCP server or extend existing People Data Labs server

---

### Implementation order

```
4.1 (UCC filings)  ✅  →  4.3 (scoring)  →  4.4 (contacts)
4.2 (litigation)   ✅       ~1-2 hours         ~TBD
```

4.1 and 4.2 are done. 4.3 depends on both (now unblocked).
4.4 is a separate initiative requiring API evaluation.
