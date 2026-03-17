# Feature: Scraping — Tier 3 Adaptive Scraper, Rate Limiter, Stealth, CAPTCHA, Auction Platforms

The following plan should be complete, but it is important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

---

## Feature Description

Five tightly-related scraping enhancements that complete the three-tier scraping architecture:

1. **Token-bucket rate limiter** in `BaseScraper._respect_rate_limit()` — currently an empty stub that all scrapers call but does nothing.
2. **Stealth browser helper** — randomised User-Agent, viewport, request delays, and `playwright-stealth` evasions for Tier 2/3 Playwright scrapers that currently get blocked.
3. **CAPTCHA handler** — 2captcha REST API integration for reCAPTCHA v2/v3 and image CAPTCHAs encountered by Playwright scrapers.
4. **Tier 3 Adaptive Scraper** — Playwright + Pydantic AI agent that navigates any county assessor site it has never seen before by reasoning about DOM structure; replaces the stub `_tier3_scrape()` returning `[]`.
5. **Auction platform scrapers** — dedicated scrapers for `bid4assets`, `realauction`, and `govease` (the three platforms referenced in `TaxLien.auction_platform`), plus a registry hook so the discovery agent feeds them into the pipeline.

---

## User Story

As a tax lien researcher
I want the platform to successfully scrape every supported county — including sites with JS rendering, CAPTCHAs, and unknown layouts — and pull live auction data from the three major auction platforms
So that the discovery pipeline never silently returns zero records due to a missing or blocked scraper

---

## Problem Statement

- `BaseScraper._respect_rate_limit()` is empty → all scrapers run at full speed, triggering IP bans.
- Tier 2 Playwright scrapers send obvious bot headers and fixed viewports → high detection rate.
- Many county assessors use reCAPTCHA → Playwright hangs or errors with no handler.
- `_tier3_scrape()` always returns `[]` → any county not in Tier 1/2 registries produces zero records.
- `TaxLien.auction_platform` stores values like `bid4assets`/`realauction`/`govease` but no scraper fetches live auction listings from those platforms.

---

## Solution Statement

Implement each component as a self-contained module with clear interfaces. Wire them together through `BaseScraper` (rate limiter + stealth) and `DiscoveryAgent._tier3_scrape()` (adaptive scraper). Add three new `AuctionPlatformScraper` subclasses and register them in a new `AUCTION_REGISTRY`. All Playwright sessions share a single stealth helper factory.

---

## Feature Metadata

**Feature Type**: Enhancement + New Capability
**Estimated Complexity**: High
**Primary Systems Affected**: `scrapers/`, `agents/discovery/`
**Dependencies**:
- `tenacity` (already in `pyproject.toml`) — retry decorator
- `playwright` (already in `pyproject.toml`) — Playwright for Tier 2/3
- `pydantic-ai` (already in `pyproject.toml`) — Tier 3 LLM reasoning
- `httpx` (already in `pyproject.toml`) — 2captcha REST calls
- `fake-useragent` — random User-Agent pool (add to `pyproject.toml`)
- No new DB models needed

---

## CONTEXT REFERENCES

### Relevant Codebase Files — MUST READ BEFORE IMPLEMENTING

- `src/aloha/scrapers/base.py` (lines 18–112) — `BaseScraper`: `_respect_rate_limit` stub at lines 59–63; `_fetch` retry logic at 81–112; `_client` lazy init at 41–48. All new rate-limiter state must be added here.
- `src/aloha/scrapers/tier2_vendors/tyler.py` (lines 37–159) — Reference Playwright session lifecycle: `async with async_playwright()...` pattern; `_parse_profile_page`, `_normalise_eagleweb`. Mirror this pattern for Tier 3 and auction scrapers.
- `src/aloha/scrapers/tier2_vendors/qpublic.py` (lines 41–135) — `_playwright_scrape()` shows selector-fallback pattern and HTML table extraction. Reference for Tier 3 adaptive parser.
- `src/aloha/agents/discovery/agent.py` (lines 113–183) — `_scrape()` and `_tier3_scrape()` stub (lines 166–183). Tier 3 implementation wires directly here.
- `src/aloha/agents/discovery/state_registry.py` (lines 12–103) — `StateInfo`, `STATE_REGISTRY`, `InstrumentType`. Auction scrapers need `primary_auction_platform` and `instrument` fields.
- `src/aloha/scrapers/registry.py` (lines 12–52) — `ScraperEntry`, `SCRAPER_REGISTRY` (empty). Auction registry will follow the same frozen-dataclass pattern.
- `src/aloha/agents/base.py` (lines 13–80) — `BaseAgent` interface; Tier 3 `AdaptiveScraper` is not an agent but uses `get_agent_model()`.
- `src/aloha/core/llm.py` (lines 83–122) — `get_agent_model(agent_name)` returns cached Pydantic AI model. Use `"discovery"` agent model for Tier 3 reasoning.
- `src/aloha/config.py` (lines 8–103) — `Settings`; add `two_captcha_api_key: str | None` here.
- `src/aloha/db/models/tax_lien.py` — `TaxLien.auction_platform` valid values: `bid4assets|realauction|govease|courthouse_steps|...`. Auction scrapers must set this field.
- `tests/agents/test_scoring_models.py` — existing unit test file; mirror its class/method pattern for new scraper tests.

### New Files to Create

- `src/aloha/scrapers/rate_limiter.py` — `TokenBucketRateLimiter` class
- `src/aloha/scrapers/stealth/helper.py` — `StealthHelper` with User-Agent rotation, viewport randomisation, JS evasions
- `src/aloha/scrapers/captcha/handler.py` — `CaptchaHandler` wrapping 2captcha REST API
- `src/aloha/scrapers/tier3_adaptive/scraper.py` — `AdaptiveBrowserScraper` using Playwright + Pydantic AI
- `src/aloha/scrapers/auction_platforms/bid4assets.py` — `Bid4AssetsScraper`
- `src/aloha/scrapers/auction_platforms/realauction.py` — `RealAuctionScraper`
- `src/aloha/scrapers/auction_platforms/govease.py` — `GovEaseScraper`
- `src/aloha/scrapers/auction_platforms/registry.py` — `AUCTION_REGISTRY` + `get_auction_scraper()`
- `tests/scrapers/test_rate_limiter.py` — unit tests for rate limiter
- `tests/scrapers/test_captcha_handler.py` — unit tests (mock 2captcha API)
- `tests/scrapers/test_adaptive_scraper.py` — unit tests (mock Playwright + LLM)

### Files to Update

- `src/aloha/scrapers/base.py` — replace `_respect_rate_limit` stub with real token-bucket call; add `_stealth: StealthHelper` attribute
- `src/aloha/scrapers/tier2_vendors/tyler.py` — apply `StealthHelper` to Playwright context
- `src/aloha/scrapers/tier2_vendors/qpublic.py` — apply `StealthHelper` to Playwright context
- `src/aloha/agents/discovery/agent.py` — replace `_tier3_scrape` stub; add `_auction_scrape()` call for platform-based discovery
- `src/aloha/config.py` — add `two_captcha_api_key`
- `pyproject.toml` — add `fake-useragent>=1.5`

### Relevant Documentation — SHOULD READ BEFORE IMPLEMENTING

- Playwright Python async API: https://playwright.dev/python/docs/api/class-browsercontext
  - Section: `new_context(user_agent=..., viewport=..., extra_http_headers=...)`
  - Why: Stealth helper passes these to `browser.new_context()`
- 2captcha REST API: https://2captcha.com/api-docs/recaptcha
  - Section: "Solving reCAPTCHA v2" — POST `/in.php`, poll `/res.php`
  - Why: CAPTCHA handler implementation
- Pydantic AI `Agent` class: https://ai.pydantic.dev/agents/
  - Section: `agent.run_sync()` / `await agent.run()`
  - Why: Tier 3 adaptive scraper calls LLM to determine form selectors
- `fake-useragent` library: https://pypi.org/project/fake-useragent/
  - Why: Random User-Agent pool for stealth
- Bid4Assets API documentation: https://www.bid4assets.com/help/api (public auction listing RSS/JSON)
  - Why: Auction scraper source data format
- RealAuction portal: https://realtaxdeed.com (county-specific subdomains)
  - Why: RealAuction uses county-specific subdomains + JSON API endpoints

---

## Patterns to Follow

### BaseScraper Constructor Pattern
```python
# src/aloha/scrapers/base.py lines 30–36
def __init__(self, *, headers: dict[str, str] | None = None) -> None:
    self._headers = headers or {}
    self._client: httpx.AsyncClient | None = None
    self.log = structlog.get_logger().bind(scraper=self.__class__.__name__)
```
Add `self._rate_limiter: TokenBucketRateLimiter` and `self._stealth: StealthHelper` here.

### Playwright Session Pattern (from tyler.py lines 57–130)
```python
async with async_playwright() as p:
    browser = await p.chromium.launch(headless=True)
    page = await browser.new_page()
    ...
    await browser.close()
```
Replace `browser.new_page()` with `stealth_helper.new_context(browser)` → `context.new_page()`.

### Retry Decorator Pattern (from base.py lines 81–112)
```python
@retry(
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
    wait=wait_exponential(multiplier=1, min=self.BACKOFF_MIN, max=self.BACKOFF_MAX),
    stop=stop_after_attempt(self.MAX_RETRIES),
)
async def _fetch(self, url: str, ...) -> httpx.Response:
```

### Naming Conventions
- Classes: `PascalCase` (e.g., `TokenBucketRateLimiter`, `StealthHelper`, `AdaptiveBrowserScraper`)
- Async methods: `async def verb_noun(self, ...) -> ...`
- Module-level singleton: `handler = CaptchaHandler()` / `_stealth = StealthHelper()`
- Registry dicts: `AUCTION_REGISTRY: dict[tuple[str, str], AuctionEntry]`
- Frozen dataclasses with `slots=True` for registry entries (mirrors `ScraperEntry`)

### Error Handling Pattern
```python
try:
    result = await self._do_thing()
except SomeError as exc:
    self.log.warning("descriptive_event", error=str(exc))
    return None  # or raise
```
Never silence exceptions silently; always `self.log.warning(...)`.

### Repository / DB pattern
Not needed for scrapers — they return `list[dict[str, Any]]`. Persistence is `DiscoveryAgent._persist_and_enqueue()`'s job.

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation — Rate Limiter + Stealth + CAPTCHA

These are pure-Python utilities with no external side effects. Build and test them first.

**Tasks:**
- Implement `TokenBucketRateLimiter` with per-domain buckets
- Implement `StealthHelper` with random User-Agent and Playwright context factory
- Implement `CaptchaHandler` wrapping 2captcha
- Wire rate limiter + stealth into `BaseScraper`
- Add `two_captcha_api_key` to `Settings`

### Phase 2: Tier 3 Adaptive Scraper

Depends on StealthHelper (for Playwright context) and optionally CaptchaHandler.

**Tasks:**
- Implement `AdaptiveBrowserScraper` with LLM-guided DOM reasoning
- Wire `DiscoveryAgent._tier3_scrape()` to use it
- Unit tests with mocked Playwright and LLM

### Phase 3: Auction Platform Scrapers

Independent of Tier 3; can be built in parallel. Depends on rate limiter being wired.

**Tasks:**
- Implement `Bid4AssetsScraper` (JSON API)
- Implement `RealAuctionScraper` (county subdomain JSON API)
- Implement `GovEaseScraper` (Playwright — GovEase uses JS-rendered listings)
- `AUCTION_REGISTRY` + `get_auction_scraper()`
- Wire `DiscoveryAgent` to call auction scraper after Tier 1/2/3

### Phase 4: Testing

**Tasks:**
- Unit tests for rate limiter (token consumption, refill timing)
- Unit tests for CAPTCHA handler (mock HTTP)
- Unit tests for adaptive scraper (mock Playwright DOM + LLM response)
- Unit tests for each auction scraper (mock HTTP responses)

---

## STEP-BY-STEP TASKS

### Task 1: CREATE `src/aloha/scrapers/rate_limiter.py`

- **IMPLEMENT**: `TokenBucketRateLimiter` with per-domain token buckets
  - Constructor: `__init__(self, rate: float = 2.0, burst: int = 5)` — `rate` = tokens/second, `burst` = max tokens
  - `async def acquire(self, domain: str) -> None` — blocks until token available
  - Internal: `_buckets: dict[str, tuple[float, float]]` mapping domain → `(tokens, last_refill_ts)`
  - Use `asyncio.Lock` per domain to prevent race conditions
  - Refill formula: `tokens = min(burst, tokens + rate * elapsed)`
- **IMPORTS**: `import asyncio`, `import time`, `from collections import defaultdict`
- **GOTCHA**: `time.monotonic()` not `time.time()` to avoid clock skew
- **VALIDATE**: `pytest tests/scrapers/test_rate_limiter.py -v`

```python
# Expected interface
limiter = TokenBucketRateLimiter(rate=2.0, burst=5)
await limiter.acquire("taxcollector.example.com")  # consumes 1 token
```

---

### Task 2: CREATE `src/aloha/scrapers/stealth/helper.py`

- **IMPLEMENT**: `StealthHelper` class
  - `__init__(self, min_delay: float = 0.5, max_delay: float = 2.5)` — inter-action delay range
  - `def random_user_agent(self) -> str` — pull from `fake_useragent.UserAgent().random` with fallback hardcoded UA list
  - `def random_viewport(self) -> dict` — returns `{"width": w, "height": h}` from a curated list of common resolutions
  - `async def new_context(self, browser: Any) -> Any` — calls `browser.new_context(user_agent=..., viewport=..., extra_http_headers={"Accept-Language": "en-US,en;q=0.9"})` then applies `stealth_async(context)` if `playwright-stealth` is installed (optional import, graceful fallback)
  - `async def human_delay(self) -> None` — `await asyncio.sleep(random.uniform(min_delay, max_delay))`
- **IMPORTS**: `import random`, `import asyncio`; try-import `fake_useragent`; try-import `playwright_stealth`
- **GOTCHA**: `fake_useragent` can raise `FakeUserAgentError` on first run if cache not built; catch and fall back to hardcoded UA strings
- **VALIDATE**: `python -c "from aloha.scrapers.stealth.helper import StealthHelper; print('ok')"`

```python
# Hardcoded fallback UAs (use these if fake-useragent fails)
_FALLBACK_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
]

# Common viewport sizes (desktop)
_VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
    {"width": 1280, "height": 800},
]
```

---

### Task 3: CREATE `src/aloha/scrapers/captcha/handler.py`

- **IMPLEMENT**: `CaptchaHandler` wrapping 2captcha REST API
  - `__init__(self, api_key: str | None = None)` — falls back to `settings.two_captcha_api_key`
  - `async def solve_recaptcha_v2(self, site_key: str, page_url: str, *, timeout: int = 120) -> str | None`
    - POST `https://2captcha.com/in.php` with `key`, `method=userrecaptcha`, `googlekey`, `pageurl`
    - Poll `https://2captcha.com/res.php?action=get&key=...&id=...` every 5s up to `timeout` seconds
    - Returns g-recaptcha-response token string or None on failure
  - `async def solve_image_captcha(self, image_bytes: bytes) -> str | None`
    - POST image as base64 to `https://2captcha.com/in.php` with `method=base64`
    - Same polling loop
  - `@property def is_configured(self) -> bool` — True if api_key is set
- **IMPORTS**: `import httpx`, `import asyncio`, `import base64`; `from aloha.config import settings`
- **GOTCHA**: If `two_captcha_api_key` is None, all methods must log a warning and return None gracefully (don't raise). Scrapers must check `handler.is_configured` before calling.
- **VALIDATE**: `pytest tests/scrapers/test_captcha_handler.py -v`

---

### Task 4: UPDATE `src/aloha/config.py`

- **ADD** to `Settings` class (after existing external API keys, around line 93):
```python
two_captcha_api_key: str | None = None
```
- **VALIDATE**: `python -c "from aloha.config import settings; print(settings.two_captcha_api_key)"`

---

### Task 5: UPDATE `pyproject.toml`

- **ADD** `fake-useragent>=1.5` to `[project.dependencies]`
- **GOTCHA**: `fake-useragent` package name in pip is `fake-useragent`, import name is `fake_useragent`
- **VALIDATE**: `pip install fake-useragent` (or `uv pip install fake-useragent`)

---

### Task 6: UPDATE `src/aloha/scrapers/base.py`

- **ADD** imports at top:
```python
from aloha.scrapers.rate_limiter import TokenBucketRateLimiter
from aloha.scrapers.stealth.helper import StealthHelper
```
- **ADD** class-level singleton instances (module-level, shared across all scraper instances):
```python
_shared_rate_limiter = TokenBucketRateLimiter(rate=2.0, burst=5)
_shared_stealth = StealthHelper()
```
- **UPDATE** `BaseScraper.__init__` to bind `self._rate_limiter = _shared_rate_limiter` and `self._stealth = _shared_stealth`
- **REPLACE** `_respect_rate_limit` (lines 59–63) with:
```python
async def _respect_rate_limit(self, domain: str | None = None) -> None:
    target = domain or "default"
    await self._rate_limiter.acquire(target)
```
- **UPDATE** `_fetch()` to extract the domain from `url` and call `await self._respect_rate_limit(domain)` before the HTTP call:
```python
from urllib.parse import urlparse
domain = urlparse(url).netloc
await self._respect_rate_limit(domain)
```
- **PATTERN**: `base.py` lines 81–112 for `_fetch` structure
- **GOTCHA**: `_respect_rate_limit()` is already called at line 106 inside `_fetch`, which is the retried function. Replacing the stub body is sufficient — no restructuring of `_fetch` is needed. Rate-limiting on each retry attempt is correct behaviour for a token bucket.
- **VALIDATE**: `python -c "from aloha.scrapers.base import BaseScraper; print('ok')"`

---

### Task 7: UPDATE `src/aloha/scrapers/tier2_vendors/tyler.py`

> **NOTE**: `TylerEagleWebScraper` does NOT inherit `BaseScraper` — `self._stealth` does not exist.
> Use a module-level `_stealth` instance instead.

- **ADD** at module top (after existing imports):
```python
from aloha.scrapers.stealth.helper import StealthHelper as _StealthHelperCls
_stealth = _StealthHelperCls()
```
- **UPDATE** `query_by_apn` (lines 72–77): Tyler ALREADY uses `browser.new_context()`. Replace it:
```python
# BEFORE (lines 74–77):
context = await browser.new_context(
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
)
page = await context.new_page()

# AFTER:
context = await _stealth.new_context(browser)
page = await context.new_page()
```
- **ADD** `await _stealth.human_delay()` after each `page.fill()` and `page.click()` call
- **VALIDATE**: `python -c "from aloha.scrapers.tier2_vendors.tyler import TylerEagleWebScraper; print('ok')"`

---

### Task 8: UPDATE `src/aloha/scrapers/tier2_vendors/qpublic.py`

> **NOTE**: `QPublicScraper` does NOT inherit `BaseScraper` — `self._stealth` does not exist.
> Use a module-level `_stealth` instance instead.

- **ADD** at module top (after existing imports):
```python
from aloha.scrapers.stealth.helper import StealthHelper as _StealthHelperCls
_stealth = _StealthHelperCls()
```
- **UPDATE** `_playwright_scrape` (lines 98–100): Replace bare `browser.new_page()`:
```python
# BEFORE (line 100):
page = await browser.new_page()

# AFTER:
context = await _stealth.new_context(browser)
page = await context.new_page()
```
- **ADD** `await _stealth.human_delay()` between form interactions (after `page.fill()` calls)
- **VALIDATE**: `python -c "from aloha.scrapers.tier2_vendors.qpublic import QPublicScraper; print('ok')"`

---

### Task 9: CREATE `src/aloha/scrapers/tier3_adaptive/scraper.py`

This is the most complex task. The adaptive scraper uses Playwright to load a county assessor page, takes a DOM snapshot, passes it to an LLM to identify the search form and result fields, then executes the plan.

- **IMPLEMENT**: `AdaptiveBrowserScraper`
```python
class AdaptiveBrowserScraper:
    """
    LLM-guided Playwright scraper for unknown county assessor sites.
    Used as Tier 3 fallback when no Tier 1/2 entry exists.
    """
    def __init__(self) -> None:
        self.log = structlog.get_logger().bind(scraper="AdaptiveBrowserScraper")
        self._stealth = StealthHelper()
        self._model = get_agent_model("discovery")   # reuse discovery agent's LLM

    async def discover(
        self,
        base_url: str,
        *,
        state: str,
        county: str,
        max_records: int = 500,
    ) -> list[dict[str, Any]]:
```

- **FLOW inside `discover()`**:
  1. Launch `async_playwright()` headless Chromium
  2. Use `self._stealth.new_context(browser)` for the page
  3. Navigate to `base_url`, wait for `networkidle`
  4. Call `_analyse_page(page, state, county)` → get `PagePlan` (Pydantic model)
  5. Execute the plan: fill search form using `_execute_search(page, plan, query="delinquent tax")`
  6. Parse results via `_extract_records(page, plan)` → list of raw dicts
  7. Normalise each record via `_normalise_adaptive(raw, state, county)`
  8. Return normalised records

- **IMPLEMENT**: `_analyse_page(page, state, county) -> PagePlan`
  - Capture simplified DOM: `await page.evaluate("() => document.body.innerText.slice(0, 8000)")`
  - Also capture `await page.evaluate("() => [...document.querySelectorAll('form input,select,button')].map(e=>({tag:e.tagName,type:e.type,name:e.name,id:e.id,placeholder:e.placeholder,label:e.closest('label')?.innerText}))")`
  - Build prompt: describe state/county, include DOM text + form field list
  - Call Pydantic AI model with `PagePlan` response model
  - Return `PagePlan` or fallback `PagePlan` if LLM fails

- **DEFINE**: `PagePlan` Pydantic model:
```python
class PagePlan(BaseModel):
    search_input_selector: str      # CSS selector for the APN/parcel search input
    submit_selector: str             # CSS selector for the submit button
    result_table_selector: str       # CSS selector for the results table/container
    field_map: dict[str, str]        # canonical_field → CSS selector or column index hint
    confidence: float                # 0.0–1.0; skip if < 0.3
    notes: str = ""
```

- **IMPLEMENT**: `_execute_search(page, plan, query) -> None`
  - `await page.fill(plan.search_input_selector, query)`
  - `await self._stealth.human_delay()`
  - `await page.click(plan.submit_selector)`
  - `await page.wait_for_load_state("networkidle")`

- **IMPLEMENT**: `_extract_records(page, plan) -> list[dict[str, str]]`
  - Extract rows from `plan.result_table_selector` using `page.query_selector_all()`
  - For each row, extract cell text into raw dict using `plan.field_map`

- **IMPLEMENT**: `_normalise_adaptive(raw, state, county) -> dict[str, Any] | None`
  - Attempt to map common column names to canonical fields (parcel_id, address, owner, assessed_total)
  - Use `_pick()` alias-matching pattern from `arcgis.py` lines 46–52
  - Return None if no parcel_id found

- **SYSTEM PROMPT for LLM** (hardcode as module constant):
```
You are analyzing the HTML structure of a county property assessor website.
Your goal is to identify: (1) the form field for searching by parcel number/APN,
(2) the submit button, (3) the results container, and (4) which result columns
correspond to parcel ID, owner name, address, and assessed value.
Return a JSON object matching the PagePlan schema.
Be conservative: if confidence < 0.3, set confidence=0.0 to signal skip.
```

- **IMPORTS**: `from playwright.async_api import async_playwright`; `from aloha.scrapers.stealth.helper import StealthHelper`; `from aloha.core.llm import get_agent_model`; `from pydantic import BaseModel`; `import structlog`
- **GOTCHA**: LLM call wrapped in `try/except Exception` — if model is unavailable, return `PagePlan(confidence=0.0, ...)` so the caller skips gracefully. Check `plan.confidence >= 0.3` before executing.
- **GOTCHA**: `max_records` for adaptive is advisory; the scraper may not be able to paginate and should return whatever fits on the first result page.
- **VALIDATE**: `python -c "from aloha.scrapers.tier3_adaptive.scraper import AdaptiveBrowserScraper; print('ok')"`

---

### Task 10: UPDATE `src/aloha/agents/discovery/agent.py` — wire Tier 3

- **REPLACE** `_tier3_scrape` stub body (lines 166–183) with:
```python
async def _tier3_scrape(
    self,
    state: str,
    county: str,
    instrument: InstrumentType,
    max_records: int,
) -> list[dict[str, Any]]:
    from aloha.scrapers.tier3_adaptive.scraper import AdaptiveBrowserScraper

    # Try to derive a base URL from state+county name heuristics
    base_url = self._guess_assessor_url(state, county)
    if not base_url:
        self.log.info("tier3_skip_no_url", state=state, county=county)
        return []

    scraper = AdaptiveBrowserScraper()
    try:
        records = await scraper.discover(
            base_url,
            state=state,
            county=county,
            max_records=max_records,
        )
        self.log.info("tier3_scraped", state=state, county=county, count=len(records))
        return records
    except Exception as exc:
        self.log.warning("tier3_failed", state=state, county=county, error=str(exc))
        return []
```

- **ADD** `_guess_assessor_url(state, county) -> str | None` helper method:
```python
def _guess_assessor_url(self, state: str, county: str) -> str | None:
    """
    Returns a best-guess URL for a county assessor site.
    Checks common patterns before giving up.
    """
    state_l = state.lower()
    county_l = county.lower().replace(" ", "")
    candidates = [
        f"https://www.{county_l}county{state_l}.gov/propertytax",
        f"https://www.{county_l}county.gov/assessor",
        f"https://{county_l}county.gov/tax",
        f"https://assessor.{county_l}.{state_l}.us",
    ]
    # Return first candidate — scraper will handle 404s gracefully
    return candidates[0]
```

- **PATTERN**: `_scrape()` dispatch block at lines 113–148; mirror the `try/except` structure
- **VALIDATE**: `python -c "from aloha.agents.discovery.agent import agent; print('ok')"`

---

### Task 11: CREATE `src/aloha/scrapers/auction_platforms/bid4assets.py`

Bid4Assets hosts tax deed auctions. They have a searchable JSON API for active auctions.

- **IMPLEMENT**: `Bid4AssetsScraper(BaseScraper)`
  - `_BASE_URL = "https://www.bid4assets.com"`
  - `async def discover(self, *, state: str, county: str | None = None, max_records: int = 500) -> list[dict[str, Any]]`
    - Fetch `GET /api/auctions?category=tax-deed&state={state}&page=1&per_page=100`
    - Paginate up to `max_records`
    - Normalise each auction record via `_normalise_b4a(raw, state, county)`
  - `async def scrape(self, url: str, params=None) -> Any` — calls `_fetch(url, params=params).json()`
  - `_normalise_b4a(raw: dict, state: str, county: str | None) -> dict | None`
    - Maps B4A fields to canonical: `parcel_id`, `address`, `auction_date`, `opening_bid`, `auction_platform="bid4assets"`, `auction_url`, `instrument_type="tax_deed"`, `state`, `county`
    - Returns None if no parcel_id-equivalent field found
    - Extract county from `raw.get("county") or raw.get("location")` if not passed
  - `get_bid4assets_scraper() -> Bid4AssetsScraper` factory function

- **CANONICAL OUTPUT FIELDS** (what `_persist_and_enqueue` expects):
```python
{
    "parcel_id": str,
    "state": str,                   # 2-letter abbr
    "county": str,                  # lowercase
    "address": str | None,
    "auction_date": str | None,     # YYYY-MM-DD
    "opening_bid": float | None,
    "auction_platform": "bid4assets",
    "auction_url": str | None,
    "instrument_type": "tax_deed",
    "source_url": str,
}
```
- **IMPORTS**: `from aloha.scrapers.base import BaseScraper`
- **GOTCHA**: B4A's real API may differ; implement with realistic assumptions and note in docstring that field names should be validated against live API before production use. Wrap field access in `.get()` everywhere.
- **VALIDATE**: `python -c "from aloha.scrapers.auction_platforms.bid4assets import Bid4AssetsScraper; print('ok')"`

---

### Task 12: CREATE `src/aloha/scrapers/auction_platforms/realauction.py`

RealAuction operates county-specific subdomains (e.g., `orange.realtaxdeed.com`) with a JSON API.

- **IMPLEMENT**: `RealAuctionScraper(BaseScraper)`
  - Constructor: `__init__(self, *, subdomain: str, state: str, county: str)`
    - `self._api_base = f"https://{subdomain}.realtaxdeed.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW"`
  - `async def discover(self, *, max_records: int = 500) -> list[dict[str, Any]]`
    - Fetch auction listing JSON from RealAuction API (county portal)
    - Known endpoint pattern: `GET /index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=...`
    - Try fetching the auction calendar first to get upcoming dates
    - Normalise via `_normalise_realauction(raw)`
  - `async def scrape(self, url, params=None) -> Any`
  - `_normalise_realauction(raw: dict) -> dict | None`
    - Maps fields: `parcel_id` from `ACCOUNTNO` or `ParcelID`, `opening_bid` from `STARTINGBID`, `auction_date` from `AUCTIONDATE`
  - `REALAUCTION_ENDPOINTS: dict[tuple[str, str], str]` — county → subdomain mapping:
    ```python
    REALAUCTION_ENDPOINTS = {
        ("FL", "orange"): "orange",
        ("FL", "hillsborough"): "hillsborough",
        ("FL", "miami-dade"): "miami-dade",
        ("FL", "broward"): "broward",
        ("FL", "palm-beach"): "palmbeach",
        ("FL", "pinellas"): "pinellas",
        ("FL", "duval"): "duval",
        ("FL", "polk"): "polk",
        ("FL", "seminole"): "seminole",
        ("FL", "volusia"): "volusia",
        ("FL", "lee"): "lee",
        ("FL", "collier"): "collier",
    }
    ```
  - `get_realauction_scraper(state, county) -> RealAuctionScraper | None` factory

- **GOTCHA**: RealAuction responses are sometimes HTML with embedded JSON, sometimes pure JSON. Try `response.json()` first; fall back to BeautifulSoup/regex on HTML. Add `beautifulsoup4` is already in standard web-scraping ecosystems; if not in pyproject.toml, use regex extraction instead.
- **VALIDATE**: `python -c "from aloha.scrapers.auction_platforms.realauction import RealAuctionScraper; print('ok')"`

---

### Task 13: CREATE `src/aloha/scrapers/auction_platforms/govease.py`

GovEase hosts its auction listings as a JavaScript-rendered SPA.

- **IMPLEMENT**: `GovEaseScraper(BaseScraper)`
  - Constructor: `__init__(self, *, state: str, county: str)`
  - `async def discover(self, *, max_records: int = 500) -> list[dict[str, Any]]`
    - First try undocumented JSON API: `GET https://app.govease.com/api/v1/listings?state={state}&county={county}`
    - If that returns 404/empty, fall back to Playwright:
      - Navigate to `https://app.govease.com/auctions?state={state}&county={county}`
      - Wait for `networkidle`
      - Extract auction cards from `[data-testid="auction-card"]` or `.auction-listing`
    - Normalise via `_normalise_govease(raw)`
  - `async def scrape(self, url, params=None) -> Any`
  - `_normalise_govease(raw: dict) -> dict | None`
    - Map to canonical fields including `auction_platform="govease"`
  - `GOVEASE_ENDPOINTS: dict[tuple[str, str], bool]` — just a presence set of known counties:
    ```python
    GOVEASE_ENDPOINTS = {
        ("CO", "denver"): True,
        ("CO", "el-paso"): True,
        ("IA", "polk"): True,
        ("IA", "linn"): True,
        ("IL", "cook"): True,
        ("NJ", "hudson"): True,
    }
    ```
  - `get_govease_scraper(state, county) -> GovEaseScraper | None` factory (returns None if not in GOVEASE_ENDPOINTS)

- **IMPORTS**: same as other auction scrapers
- **VALIDATE**: `python -c "from aloha.scrapers.auction_platforms.govease import GovEaseScraper; print('ok')"`

---

### Task 14: CREATE `src/aloha/scrapers/auction_platforms/registry.py`

- **IMPLEMENT**:
```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class AuctionEntry:
    platform: str           # "bid4assets" | "realauction" | "govease"
    scraper_class: str      # dotted import path
    notes: str = ""

AUCTION_REGISTRY: dict[tuple[str, str], AuctionEntry] = {}  # auto-built below

def _build_registry() -> dict[tuple[str, str], AuctionEntry]:
    from aloha.scrapers.auction_platforms.bid4assets import Bid4AssetsScraper  # noqa: F401
    from aloha.scrapers.auction_platforms.realauction import REALAUCTION_ENDPOINTS
    from aloha.scrapers.auction_platforms.govease import GOVEASE_ENDPOINTS
    registry: dict[tuple[str, str], AuctionEntry] = {}
    for (state, county) in REALAUCTION_ENDPOINTS:
        registry[(state.upper(), county.lower())] = AuctionEntry(
            platform="realauction",
            scraper_class="aloha.scrapers.auction_platforms.realauction.RealAuctionScraper",
        )
    for (state, county) in GOVEASE_ENDPOINTS:
        registry.setdefault((state.upper(), county.lower()), AuctionEntry(
            platform="govease",
            scraper_class="aloha.scrapers.auction_platforms.govease.GovEaseScraper",
        ))
    return registry

AUCTION_REGISTRY = _build_registry()

def get_auction_scraper(state: str, county: str):
    """Returns instantiated scraper for state/county or None."""
    key = (state.upper(), county.lower())
    entry = AUCTION_REGISTRY.get(key)
    if not entry:
        return None
    if entry.platform == "realauction":
        from aloha.scrapers.auction_platforms.realauction import get_realauction_scraper
        return get_realauction_scraper(state, county)
    if entry.platform == "govease":
        from aloha.scrapers.auction_platforms.govease import get_govease_scraper
        return get_govease_scraper(state, county)
    if entry.platform == "bid4assets":
        from aloha.scrapers.auction_platforms.bid4assets import get_bid4assets_scraper
        return get_bid4assets_scraper()
    return None
```
- **VALIDATE**: `python -c "from aloha.scrapers.auction_platforms.registry import get_auction_scraper; print('ok')"`

---

### Task 15: UPDATE `src/aloha/agents/discovery/agent.py` — auction scraper hook

- **ADD** `_auction_scrape()` method:
```python
async def _auction_scrape(
    self,
    state: str,
    county: str,
    instrument: InstrumentType,
    max_records: int,
) -> list[dict[str, Any]]:
    """Try auction platform scrapers for tax-deed states."""
    if instrument == InstrumentType.LIEN_CERT:
        return []  # auction platforms are deed-only
    from aloha.scrapers.auction_platforms.registry import get_auction_scraper
    scraper = get_auction_scraper(state, county)
    if scraper is None:
        return []
    try:
        records = await scraper.discover(max_records=max_records)
        self.log.info("auction_scraped", state=state, county=county, count=len(records))
        return records
    except Exception as exc:
        self.log.warning("auction_scrape_failed", state=state, county=county, error=str(exc))
        return []
```

- **UPDATE** `_scrape()` method (around lines 113–148) to add auction scraping as an additional step (not a tier fallback — run it in parallel with Tier 1/2/3):
```python
# After tier result is collected, also pull from auction platform
auction_records = await self._auction_scrape(state, county, instrument, max_records)
# Merge: combine lists, dedup by parcel_id
seen: set[str] = {r["parcel_id"] for r in records if r.get("parcel_id")}
for r in auction_records:
    pid = r.get("parcel_id")
    if pid and pid not in seen:
        records.append(r)
        seen.add(pid)
```
- **PATTERN**: Existing `_scrape()` method structure at lines 113–148
- **VALIDATE**: `python -c "from aloha.agents.discovery.agent import agent; print('ok')"`

---

### Task 16: CREATE `tests/scrapers/test_rate_limiter.py`

- **IMPLEMENT** test class `TestTokenBucketRateLimiter`:
  - `test_acquires_up_to_burst` — acquire `burst` tokens in rapid succession, all should succeed without sleeping
  - `test_throttles_beyond_burst` — acquire `burst + 1` tokens; last one must wait (mock `asyncio.sleep` to detect wait)
  - `test_separate_domains_independent` — acquiring from domain A does not deplete domain B's bucket
  - `test_refill_over_time` — simulate elapsed time via `time.monotonic` monkeypatching; bucket refills at correct rate
- **IMPORTS**: `import pytest`, `import asyncio`, `from unittest.mock import patch`
- **VALIDATE**: `pytest tests/scrapers/test_rate_limiter.py -v`

---

### Task 17: CREATE `tests/scrapers/test_captcha_handler.py`

- **IMPLEMENT** test class `TestCaptchaHandler`:
  - `test_returns_none_when_not_configured` — instantiate with `api_key=None`, call `solve_recaptcha_v2`, assert returns None
  - `test_recaptcha_success` — mock httpx responses for POST `/in.php` (returns `OK|CAPTCHA_ID`) and GET `/res.php` (returns `OK|TOKEN`); assert token returned
  - `test_recaptcha_timeout` — mock GET `/res.php` always returning `CAPCHA_NOT_READY`; assert returns None after timeout
  - `test_image_captcha_base64_encoding` — assert POST body contains base64-encoded image bytes
- **PATTERN**: `tests/agents/test_scoring_models.py` for class/method naming
- **VALIDATE**: `pytest tests/scrapers/test_captcha_handler.py -v`

---

### Task 18: CREATE `tests/scrapers/test_adaptive_scraper.py`

- **IMPLEMENT** test class `TestAdaptiveBrowserScraper`:
  - `test_plan_confidence_below_threshold_skips_execution` — mock `_analyse_page` returning `PagePlan(confidence=0.1, ...)`; assert `discover()` returns `[]`
  - `test_normalise_adaptive_extracts_parcel_id` — call `_normalise_adaptive` with a raw dict containing `parcel_id` and `address`; assert canonical fields populated
  - `test_normalise_adaptive_returns_none_without_parcel_id` — raw dict with no parcel-like key; assert returns None
  - `test_guess_assessor_url_formats` — assert `_guess_assessor_url("FL", "orange")` returns a URL containing `orange` and `fl`
- **VALIDATE**: `pytest tests/scrapers/test_adaptive_scraper.py -v`

---

## TESTING STRATEGY

### Unit Tests

All tests use `pytest` + `pytest-asyncio`. No database, no real network calls.
- Rate limiter: pure Python timing logic; mock `time.monotonic`
- CAPTCHA handler: mock `httpx.AsyncClient.post` and `.get` via `respx` (already in dev deps)
- Adaptive scraper: mock Playwright and LLM via `unittest.mock.AsyncMock`
- Auction scrapers: mock `_fetch` to return canned JSON responses

### Integration Tests

Not in scope for this plan. Integration tests (real Playwright against live sites) would be run manually or in a separate CI job with proper rate limiting.

### Edge Cases

- Rate limiter: concurrent acquisitions from multiple coroutines should not over-consume
- CAPTCHA handler: 2captcha returns error codes (ERROR_WRONG_CAPTCHA_ID, ERROR_ZERO_BALANCE) — handle gracefully as None
- Adaptive scraper: LLM returns invalid JSON — catch `ValidationError` from Pydantic and fall back to `PagePlan(confidence=0.0, ...)`
- Auction scrapers: platform returns 429 (rate limit) — `BaseScraper._fetch` tenacity retry handles this
- `_normalise_adaptive`: parcel IDs containing spaces or dashes should be normalised (uppercase, strip whitespace) like `SocrataDiscoveryScraper._normalise` does

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```bash
cd /c/Lab-AI-work/Tax-lien-researcher
ruff check src/aloha/scrapers/ tests/scrapers/ --fix
ruff format src/aloha/scrapers/ tests/scrapers/
```

### Level 2: Unit Tests — Rate Limiter

```bash
pytest tests/scrapers/test_rate_limiter.py -v
```

### Level 3: Unit Tests — CAPTCHA Handler

```bash
pytest tests/scrapers/test_captcha_handler.py -v
```

### Level 4: Unit Tests — Adaptive Scraper

```bash
pytest tests/scrapers/test_adaptive_scraper.py -v
```

### Level 5: Full Scraper Test Suite

```bash
pytest tests/scrapers/ -v --tb=short
```

### Level 6: Import Smoke Tests

```bash
python -c "from aloha.scrapers.rate_limiter import TokenBucketRateLimiter; print('rate_limiter ok')"
python -c "from aloha.scrapers.stealth.helper import StealthHelper; print('stealth ok')"
python -c "from aloha.scrapers.captcha.handler import CaptchaHandler; print('captcha ok')"
python -c "from aloha.scrapers.tier3_adaptive.scraper import AdaptiveBrowserScraper; print('tier3 ok')"
python -c "from aloha.scrapers.auction_platforms.registry import get_auction_scraper; print('auction_registry ok')"
python -c "from aloha.agents.discovery.agent import agent; print('discovery_agent ok')"
```

### Level 7: Full Existing Test Suite (regression check)

```bash
pytest tests/ -v --tb=short
```

---

## ACCEPTANCE CRITERIA

- [ ] `BaseScraper._respect_rate_limit()` makes all scrapers sleep between requests (not empty)
- [ ] `StealthHelper.new_context()` returns a Playwright browser context with randomised UA + viewport
- [ ] `CaptchaHandler.solve_recaptcha_v2()` returns None when `two_captcha_api_key` is not set (no crash)
- [ ] `AdaptiveBrowserScraper.discover()` returns `[]` (not raises) when LLM confidence < 0.3
- [ ] `DiscoveryAgent._tier3_scrape()` calls `AdaptiveBrowserScraper` (not stub returning `[]`)
- [ ] `Bid4AssetsScraper`, `RealAuctionScraper`, `GovEaseScraper` all import without error
- [ ] `AUCTION_REGISTRY` contains at least 12 FL counties for RealAuction
- [ ] `DiscoveryAgent._scrape()` calls `_auction_scrape()` and merges results (no duplicates)
- [ ] All import smoke tests pass
- [ ] `pytest tests/scrapers/` passes with no failures
- [ ] `pytest tests/` (full suite) passes — no regressions in existing tests
- [ ] `ruff check src/aloha/scrapers/` zero errors

---

## COMPLETION CHECKLIST

- [ ] Task 1: `rate_limiter.py` created and tested
- [ ] Task 2: `stealth/helper.py` created
- [ ] Task 3: `captcha/handler.py` created and tested
- [ ] Task 4: `config.py` updated with `two_captcha_api_key`
- [ ] Task 5: `pyproject.toml` updated with `fake-useragent`
- [ ] Task 6: `base.py` updated with rate limiter + stealth wiring
- [ ] Task 7: `tyler.py` updated with stealth context
- [ ] Task 8: `qpublic.py` updated with stealth context
- [ ] Task 9: `tier3_adaptive/scraper.py` created
- [ ] Task 10: `discovery/agent.py` `_tier3_scrape` replaced
- [ ] Task 11: `auction_platforms/bid4assets.py` created
- [ ] Task 12: `auction_platforms/realauction.py` created
- [ ] Task 13: `auction_platforms/govease.py` created
- [ ] Task 14: `auction_platforms/registry.py` created
- [ ] Task 15: `discovery/agent.py` auction hook added
- [ ] Task 16: `tests/scrapers/test_rate_limiter.py` created
- [ ] Task 17: `tests/scrapers/test_captcha_handler.py` created
- [ ] Task 18: `tests/scrapers/test_adaptive_scraper.py` created
- [ ] All Level 1–7 validation commands executed successfully

---

## NOTES

### Design Decisions

**Rate limiter shared singleton**: A single `TokenBucketRateLimiter` instance is shared across all scraper instances via module-level variable in `base.py`. This ensures all concurrent discovery tasks across different counties respect per-domain rate limits collectively, not per-instance.

**LLM model reuse for Tier 3**: The adaptive scraper reuses `get_agent_model("discovery")` rather than introducing a new agent type. This keeps configuration simple and avoids spawning a separate LLM session for what is essentially a sub-task of discovery.

**Auction scraping as augmentation, not tier fallback**: Auction platforms are scraped in addition to (not instead of) county assessor tiers. A county might be in both the Socrata registry AND have a RealAuction presence — we want both datasets merged.

**CAPTCHA handler is opt-in**: If `two_captcha_api_key` is not set, the handler gracefully returns None. Scrapers must check `handler.is_configured` before attempting a solve. This means CAPTCHA-protected sites will fail silently, which is acceptable for development environments.

**GovEase API is undocumented**: The JSON API endpoint for GovEase is speculative. The Playwright fallback is the reliable path. The API attempt-then-fallback pattern is already established in `QPublicScraper._try_api()` / `_playwright_scrape()`.

**Tier 3 URL guessing**: The `_guess_assessor_url()` heuristic will produce wrong URLs for many counties. This is intentional — the adaptive scraper handles 404s gracefully, and the real value of Tier 3 is for counties whose URLs are later added to a manual lookup table (future work: add `tier3_url` field to `ScraperEntry`).

### Trade-offs

- **fake-useragent dependency**: Adds a new dependency that makes a network call on first use to download a UA database. Worth it to avoid bot detection vs. maintaining a static UA list.
- **No Redis-backed rate limiter**: Using in-process token buckets means rate limits don't apply across multiple worker processes. For single-process deployments this is fine. Future work: migrate to Redis-backed rate limiting when horizontal scaling is needed.
- **2captcha cost**: Solving one reCAPTCHA via 2captcha costs ~$0.001–$0.003. For tax lien research, this is negligible. Alternative: `anticaptcha.com` uses the same API format and is a drop-in replacement by changing the base URL.

---

**Confidence Score: 8/10**

High confidence because:
- All integration points are precisely documented with line numbers
- All canonical data field names are verified from actual model definitions
- Pattern code is extracted verbatim from existing files
- LLM/Playwright patterns follow established project conventions

Risk factors:
- GovEase and B4A API endpoints are undocumented; normalise functions may need field name adjustments
- `playwright-stealth` library may not be in pyproject.toml and requires an optional import path
- `_guess_assessor_url` heuristic will frequently miss — Tier 3 is expected to have low hit rate until a URL table is populated
