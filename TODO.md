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

The Entity Research Agent currently does SOS lookups only. The UCC and Court Records
MCP servers are **already built** but not wired into the agent. The Entity model has
JSONB fields ready to receive data. This tier connects the plumbing.

### 4.1 — Wire UCC MCP server into Entity Research Agent

**Goal**: Search for UCC filings (secured debts, liens on assets) for every entity the
agent researches. Populates `Entity.ucc_filings`.

**Files to change**:
- `src/aloha/agents/entity_research/agent.py`
  - Add `_search_ucc_filings(entity_name, state)` helper method
  - Instantiate UCC server via `from aloha.mcp_servers.ucc.server import create_ucc_server`
  - Call `search_ucc_filings(debtor_name=entity_name, state=state)` on the server
  - Add step between `_find_related_entities()` and `_persist()` in `run()`
  - Update `_persist()` to store results in `entity.ucc_filings` (JSONB)
- `src/aloha/agents/entity_research/prompts.py` — mention UCC research in system prompt

**Pattern to follow**: Look at `_sos_lookup()` and `_find_related_entities()` — they
dynamically import and instantiate the SOS server the same way.

**Graceful degradation**: UCC server works without API key (Playwright scraper fallback
for FL, IL, OH). Wrap in try/except, log failures, continue agent run.

**Data shape** (from UCC server):
```json
[{
  "filing_number": "2024-123456",
  "filing_date": "2024-01-15",
  "lapse_date": "2029-01-15",
  "filing_type": "initial",
  "debtor_name": "Entity Name Inc",
  "secured_party": "Bank of America",
  "collateral": "All assets and accounts receivable",
  "state": "FL"
}]
```

**Tests**: `tests/agents/test_entity_research.py`
- Mock `create_ucc_server()` → verify filings stored in Entity.ucc_filings
- Test graceful fallback when UCC server raises

---

### 4.2 — Wire Court Records MCP server into Entity Research Agent

**Goal**: Search for federal litigation, state tax liens, and judgment liens for every
entity. Populates `Entity.federal_tax_liens`, `Entity.state_tax_liens`,
`Entity.litigation_summary`, `Entity.bankruptcy_history`.

**Files to change**:
- `src/aloha/agents/entity_research/agent.py`
  - Add `_search_litigation(entity_name, state)` helper method
  - Instantiate court records server via `from aloha.mcp_servers.court_records.server import create_court_records_server`
  - Call `search_federal_cases(party_name=entity_name, state=state)` for litigation + bankruptcy
  - Call `search_state_liens(debtor_name=entity_name, state=state)` for tax liens
  - Filter results: separate federal_tax_liens, state_tax_liens, bankruptcy, general litigation
  - Build `litigation_summary` text from aggregated results
  - Update `_persist()` to store in Entity model fields
- `src/aloha/agents/entity_research/prompts.py` — mention litigation/lien research

**Data shape** (from Court Records server):
```json
// Federal cases
[{
  "case_id": "12345",
  "case_title": "US v. Entity Name Inc",
  "court": "N.D. Fla.",
  "case_type": "bankruptcy",
  "filing_date": "2024-01-15",
  "status": "pending",
  "parties": [{"name": "Entity Name Inc", "role": "debtor"}],
  "docket_url": "https://..."
}]

// State liens
[{
  "filing_number": "2024-001234",
  "debtor": "Entity Name Inc",
  "creditor": "IRS",
  "amount": 50000.00,
  "filing_date": "2024-03-01",
  "lien_type": "federal_tax",
  "state": "FL"
}]
```

**Filtering logic**:
- `lien_type == "federal_tax"` → `Entity.federal_tax_liens`
- `lien_type == "state_tax"` → `Entity.state_tax_liens`
- `case_type == "bankruptcy"` → `Entity.bankruptcy_history`
- Everything else → `Entity.litigation_summary` (formatted text)

**Graceful degradation**: Court Records server works without API key (Playwright scraper
fallback for FL, TX state liens). Federal case search requires `COURTLISTENER_API_KEY`
(free at courtlistener.com).

**Tests**: `tests/agents/test_entity_research.py`
- Mock `create_court_records_server()` → verify fields populated correctly
- Test lien type filtering logic
- Test bankruptcy detection
- Test graceful fallback when server unavailable

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
4.1 (UCC filings)  →  4.2 (litigation/liens)  →  4.3 (scoring)  →  4.4 (contacts)
     ~2-3 hours           ~3-4 hours                ~1-2 hours         ~TBD
```

4.1 and 4.2 are independent and can be built in parallel. 4.3 depends on both.
4.4 is a separate initiative requiring API evaluation.
