# Research B.6.2: Handling Dynamic Government Portals (React/Angular Search UIs)
**Date:** 2026-03-16
**Status:** COMPLETE
**Relates to:** PRD Section 5 (Data Sources), Section 9 (Tech Stack), toresearch.md B.6.2

---

## Executive Summary

County government property tax portals across the US are overwhelmingly **traditional server-rendered applications** (ASP.NET, Drupal, classic HTML/jQuery), not modern SPAs. Only ~10-15% use JavaScript-heavy frameworks. The dominant pattern is: ASP.NET backend + jQuery frontend + Google reCAPTCHA. A small number of vendor platforms (Tyler Technologies, Schneider/qPublic, Vision Government Solutions, Aumentum) power a disproportionate share of counties, making **template-based scraping by vendor platform** the highest-leverage strategy.

**Recommended architecture:** A three-tier scraping system:
1. **Tier 1 (Zero-crawl):** Bulk data feeds (Socrata, county FTP, open data APIs) — covers ~15-20% of counties
2. **Tier 2 (Template scrapers):** Playwright-based scrapers per vendor platform (Tyler/iasWorld, qPublic/Beacon, Aumentum, Vision) — covers ~50-60% of counties
3. **Tier 3 (AI-adaptive):** LLM-powered browser agents (Stagehand or browser-use on Playwright) for unknown/one-off portals — covers the remaining 20-30%

**Primary tool:** Playwright (Python) via Crawlee, with Stagehand/browser-use for AI-assisted navigation of unknown portals.

---

## 1. Government Portal Tech Stack Survey

### 1.1 Direct Inspection Results (Major Counties)

| County | Portal URL | Backend | Frontend | Bot Protection | Vendor |
|--------|-----------|---------|----------|---------------|--------|
| **Cook County, IL** | cookcountypropertyinfo.com | ASP.NET | jQuery | Google reCAPTCHA v3 | Tyler Technologies (iasWorld migration in progress, approved April 2025) |
| **Harris County, TX** | hctax.net | ASP.NET (.cshtml) | jQuery + Fancybox + jScrollPane | Google reCAPTCHA | Custom (Aumentum backend) |
| **Maricopa County, AZ** (Treasurer) | treasurer.maricopa.gov | ASP.NET Blazor | jQuery + Bootstrap + Material Icons | Standard | Custom |
| **Maricopa County, AZ** (Assessor) | mcassessor.maricopa.gov | Server-rendered | jQuery | None detected | Manavi Solutions LLC (Salesforce Service Cloud for customer portal) |
| **Los Angeles County, CA** | propertytax.lacounty.gov | Server-rendered | jQuery | None detected | Custom (Property Tax Management System) |
| **Miami-Dade County, FL** | apps.miamidadepa.gov/PropertySearch | Modern web app | Bootstrap 5 + ArcGIS JS 4.24 | Google Tag Manager | Custom (ArcGIS-powered) |
| **Georgia counties (many)** | qpublic.schneidercorp.com | ASP.NET (.aspx) | jQuery + Esri maps | Access restrictions (403 on automated requests) | Schneider Geospatial (qPublic) |

### 1.2 Government CMS Market Share (Large Counties >1.5M pop)

From available market research data:

| Platform | Market Share |
|----------|-------------|
| **Drupal** | 25.9% |
| **Microsoft SharePoint** | 11.1% |
| **WordPress** | 11.1% |
| **DNN (DotNetNuke) / ASP.NET** | 7.4% |
| **Adobe Experience Manager** | 7.4% |
| **Custom / Other** | ~37% |

**Key insight:** These CMS numbers cover the main county website, not the property tax portal specifically. Property tax portals are almost always **separate applications** built by specialized vendors (Tyler, Schneider, Aumentum, Vision) or custom .NET applications. The CMS behind the main county website is largely irrelevant.

### 1.3 Technology Distribution Estimate for Property Tax Portals

Based on direct inspection and vendor market data:

| Technology Pattern | Estimated % of 3,100+ Counties | Examples |
|-------------------|-------------------------------|----------|
| **ASP.NET + jQuery** (server-rendered) | ~40% | Cook County, Harris County, qPublic counties |
| **ASP.NET Blazor** (hybrid server/client) | ~5% | Maricopa Treasurer |
| **Classic HTML/PHP** (minimal JS) | ~15% | Small rural counties |
| **Drupal/WordPress** with property plugin | ~10% | Mid-size counties |
| **.NET + ArcGIS JS** (map-centric) | ~10% | Miami-Dade, counties with Esri |
| **Modern SPA (React/Angular/Vue)** | ~10-15% | Newer portals, recent Tyler deployments |
| **PDF-only / no web portal** | ~5-10% | Very small/rural counties |

**Bottom line:** ~80-85% of county portals are **traditional server-rendered pages** that could be scraped with simple HTTP requests + HTML parsing if not for CAPTCHAs and session requirements. Browser automation is needed primarily for: (a) JavaScript form validation, (b) CAPTCHA handling, (c) AJAX-loaded result tables, and (d) the ~15% that are actual SPAs.

---

## 2. Browser Automation Tool Comparison

### 2.1 Head-to-Head: Playwright vs Puppeteer vs Selenium

| Feature | Playwright | Puppeteer | Selenium |
|---------|-----------|-----------|----------|
| **Language support** | Python, JS/TS, Java, .NET | JS/TS only | Java, Python, C#, JS, Ruby, etc. |
| **Browser support** | Chromium, Firefox, WebKit | Chromium only | All major browsers |
| **Auto-wait** | Built-in (best-in-class) | Manual | Manual (WebDriverWait) |
| **Performance** | ~290ms/click | ~280ms/click | ~536ms/click |
| **Network interception** | Native, powerful | Native | Limited |
| **Multi-context** | BrowserContext isolation | Incognito contexts | Separate driver instances |
| **Stealth capability** | Via playwright-stealth plugin | Via puppeteer-extra-stealth | Via undetected-chromedriver |
| **Concurrent sessions** | 50-200 per node | 30-100 per node | 20-50 per node |
| **Memory per instance** | ~150-300MB | ~150-300MB | ~300-500MB |
| **Active development** | Very active (Microsoft) | Active (Google) | Active but slower |
| **Crawlee integration** | First-class (PlaywrightCrawler) | First-class (PuppeteerCrawler) | Not supported |

### 2.2 Recommendation: Playwright (Python)

**Playwright is the clear winner for this use case.** Reasons:

1. **Python ecosystem alignment** — Aloha's backend is Python-based; Playwright has first-class Python bindings with identical API to JS version
2. **Auto-wait eliminates flakiness** — Government portals have unpredictable load times; Playwright's built-in auto-wait for elements handles this automatically
3. **BrowserContext for county isolation** — Each county scrape runs in its own BrowserContext with separate cookies/sessions, on a shared browser instance (much more memory-efficient than separate browsers)
4. **Network interception** — Can intercept AJAX responses directly (critical for portals that load results via XHR/fetch), avoiding DOM parsing entirely
5. **Stealth plugins available** — `playwright-stealth` removes automation fingerprints
6. **Crawlee integration** — Crawlee's PlaywrightCrawler provides retry logic, request queuing, proxy rotation, and session management out of the box

### 2.3 Stealth / Anti-Detection

Most government portals have minimal bot protection, but some (especially qPublic and Cook County) use reCAPTCHA. Stealth techniques:

```python
# playwright-stealth integration
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

async with async_playwright() as p:
    browser = await p.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...",
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
        timezone_id="America/New_York"
    )
    page = await context.new_page()
    await stealth_async(page)  # Patches navigator.webdriver, chrome runtime, etc.
```

**Key stealth measures:**
- Remove `navigator.webdriver` flag (set to `true` by default in automation)
- Remove `HeadlessChrome` from User-Agent string
- Patch `chrome.runtime` to appear as a normal Chrome extension environment
- Randomize viewport size, language, timezone per county context
- Add realistic mouse movements and typing delays for portals with behavioral detection

### 2.4 CAPTCHA Handling Strategy

| CAPTCHA Type | Prevalence on Gov Portals | Solution |
|-------------|--------------------------|----------|
| **Google reCAPTCHA v3** | ~15-20% of portals | Score-based; stealth mode usually passes. Fallback: 2Captcha API ($2.99/1000 solves) |
| **Google reCAPTCHA v2** (checkbox) | ~5-10% | 2Captcha or Anti-Captcha API ($2.99/1000 solves, ~15s solve time) |
| **hCaptcha** | ~2-5% | CapSolver AI ($1.50/1000 solves, ~5s solve time) |
| **Simple image CAPTCHA** | ~5% (older portals) | CapSolver or local OCR (Tesseract) |
| **No CAPTCHA** | ~60-70% | No action needed |

**Recommended approach:**
1. Run with stealth mode first (handles reCAPTCHA v3 passively in most cases)
2. If CAPTCHA triggered, route to 2Captcha/CapSolver API as fallback
3. Budget: At scale (~100K searches/month), CAPTCHA solving costs ~$300-500/month
4. Some portals only CAPTCHA on initial session — maintain session cookies to avoid re-triggering

```python
# Example: 2Captcha integration with Playwright
import asyncio
from twocaptcha import TwoCaptcha

solver = TwoCaptcha("YOUR_API_KEY")

async def solve_recaptcha(page, site_key):
    result = solver.recaptcha(
        sitekey=site_key,
        url=page.url
    )
    token = result["code"]
    await page.evaluate(f'document.getElementById("g-recaptcha-response").value = "{token}"')
    await page.evaluate(f'___grecaptcha_cfg.clients[0].K.K.callback("{token}")')
```

### 2.5 Session and Cookie Management

Government portals commonly use:
- **ASP.NET session cookies** (`ASP.NET_SessionId`) — must be maintained across requests
- **ViewState** — ASP.NET postback state; must be included in form submissions
- **Anti-forgery tokens** — present in ~30% of .NET portals
- **Session timeouts** — typically 20-30 minutes; must refresh before expiry

```python
# BrowserContext preserves all cookies/sessions automatically
context = await browser.new_context(
    storage_state="county_sessions/cook_county.json"  # Load saved session
)
# ... do work ...
await context.storage_state(path="county_sessions/cook_county.json")  # Save for reuse
```

---

## 3. Specific Challenges with Government Portals

### 3.1 Form-Fill -> Search -> Paginate -> Extract Pattern

This is the universal pattern across ~90% of county portals:

```python
# Universal government portal scraping pattern
async def scrape_county_tax_data(page, county_config):
    # 1. Navigate to search page
    await page.goto(county_config["search_url"])

    # 2. Accept Terms of Service if present
    tos_button = page.locator(county_config.get("tos_selector", "#acceptTerms"))
    if await tos_button.is_visible():
        await tos_button.click()

    # 3. Fill search form
    for field_name, selector in county_config["form_fields"].items():
        await page.fill(selector, county_config["search_params"][field_name])

    # 4. Submit search
    await page.click(county_config["submit_selector"])

    # 5. Wait for results (handles both AJAX and full page reload)
    await page.wait_for_selector(
        county_config["results_selector"],
        state="visible",
        timeout=30000
    )

    # 6. Extract results + paginate
    all_results = []
    while True:
        # Extract current page
        rows = await page.query_selector_all(county_config["row_selector"])
        for row in rows:
            data = {}
            for field, sel in county_config["field_selectors"].items():
                el = await row.query_selector(sel)
                data[field] = await el.inner_text() if el else None
            all_results.append(data)

        # Check for next page
        next_btn = page.locator(county_config["next_page_selector"])
        if await next_btn.is_visible() and await next_btn.is_enabled():
            await next_btn.click()
            await page.wait_for_load_state("networkidle")
        else:
            break

    return all_results
```

### 3.2 Challenge: Dynamically-Loaded Tables (AJAX Pagination)

Many modern portals load results via AJAX rather than full page reloads. Two strategies:

**Strategy A: Intercept network requests (preferred)**
```python
# Intercept the AJAX response directly — much faster than DOM parsing
async def intercept_results(page, api_pattern):
    results = []

    async def handle_response(response):
        if api_pattern in response.url and response.status == 200:
            data = await response.json()
            results.extend(data.get("results", data.get("records", [])))

    page.on("response", handle_response)

    # Trigger the search...
    await page.click("#searchButton")
    await page.wait_for_load_state("networkidle")

    return results
```

**Strategy B: Wait for DOM updates**
```python
# For portals where you can't intercept the API
await page.wait_for_function(
    "document.querySelectorAll('.result-row').length > 0"
)
```

### 3.3 Challenge: iFrames

Some portals embed search functionality in iframes (especially Esri map viewers):

```python
# Handle iframe-embedded content
frame = page.frame_locator("#propertySearchFrame")
await frame.locator("#addressInput").fill("123 Main St")
await frame.locator("#searchBtn").click()
# Results are within the frame context
results = await frame.locator(".result-row").all_inner_texts()
```

### 3.4 Challenge: Terms of Service Clickthrough

~20-30% of portals require a TOS acceptance before searching:

```python
# Generic TOS acceptance patterns
TOS_SELECTORS = [
    "button:has-text('I Accept')",
    "button:has-text('I Agree')",
    "button:has-text('Accept')",
    "input[type='submit'][value*='Accept']",
    "a:has-text('Agree')",
    "#disclaimerAccept",
    "#btnAgree",
    ".tos-accept",
]

async def accept_tos(page):
    for selector in TOS_SELECTORS:
        btn = page.locator(selector).first
        if await btn.is_visible(timeout=2000):
            await btn.click()
            return True
    return False
```

### 3.5 Challenge: Session Timeouts

Government portals typically time out after 20-30 minutes of inactivity:

```python
# Session keepalive strategy
import asyncio

class SessionManager:
    def __init__(self, page, keepalive_url, interval=600):  # 10 min
        self.page = page
        self.keepalive_url = keepalive_url
        self.interval = interval
        self._task = None

    async def start(self):
        self._task = asyncio.create_task(self._keepalive_loop())

    async def _keepalive_loop(self):
        while True:
            await asyncio.sleep(self.interval)
            # Light request to keep session alive
            await self.page.evaluate(
                f'fetch("{self.keepalive_url}", {{credentials: "same-origin"}})'
            )

    async def stop(self):
        if self._task:
            self._task.cancel()
```

### 3.6 Rate Limiting to Avoid IP Bans

**Government portals are generally lenient** but some will block after sustained rapid access:

| Strategy | Implementation |
|----------|---------------|
| **Request throttling** | 2-5 seconds between requests to the same domain |
| **Domain-level rate limits** | Max 10-20 requests/minute per county domain |
| **IP rotation** | Rotate through residential proxies every 10-15 requests |
| **User-Agent rotation** | Pool of 20+ realistic UAs, rotate with IP |
| **Backoff on 429/503** | Exponential backoff: 30s, 60s, 120s, 300s |
| **Time-of-day scheduling** | Run heavy crawls during off-peak hours (nights, weekends) |
| **Distributed across IPs** | When scraping 3,000+ counties, distribute so each county sees <50 req/day |

```python
# Rate limiter per domain
from collections import defaultdict
import time

class DomainRateLimiter:
    def __init__(self, requests_per_minute=10):
        self.rpm = requests_per_minute
        self.timestamps = defaultdict(list)

    async def wait(self, domain):
        now = time.time()
        # Remove timestamps older than 60s
        self.timestamps[domain] = [
            t for t in self.timestamps[domain] if now - t < 60
        ]
        if len(self.timestamps[domain]) >= self.rpm:
            sleep_time = 60 - (now - self.timestamps[domain][0])
            await asyncio.sleep(sleep_time)
        self.timestamps[domain].append(time.time())
```

**Proxy recommendation for government scraping:**
- **Residential proxies** are overkill for most government sites — datacenter proxies work fine
- Start with datacenter proxies ($0.50-1/GB) and escalate to residential ($5-15/GB) only for portals that block datacenter IPs
- Recommended providers: Bright Data, Oxylabs, or IPRoyal
- Budget estimate: ~$50-200/month for 3,000 county coverage at moderate crawl frequency

---

## 4. Government Portal Vendor Platforms

### 4.1 Tyler Technologies (iasWorld / Enterprise Assessment & Tax)

**Market position:** Largest government software company. Used by ~2,000+ jurisdictions.
**Tech stack:** Oracle database, N-tiered .NET backend, ASP.NET frontend
**Public-facing module:** "Public Access" — web portal for property search
**Key features to scrape:**
- Property search by parcel number, address, owner name
- Assessment details, tax bills, payment history
- Standardized URL patterns across deployments

**Scraping approach:** Template scraper — Tyler deployments share common HTML structure
```python
# Tyler Technologies Public Access URL pattern
TYLER_SEARCH_URL = "https://{county_domain}/publicaccess/SearchByAddress.aspx"
TYLER_PARCEL_URL = "https://{county_domain}/publicaccess/PropertyDetail.aspx?ParcelID={pid}"
```

**Cook County migration:** As of April 2025, Cook County IL is actively migrating to Tyler iasWorld, meaning the largest county in the Midwest will soon be on a standard Tyler template.

### 4.2 Schneider Geospatial (qPublic / Beacon)

**Market position:** Dominant in Georgia and the Southeast, also NC, SC, IA, and others. 400+ counties.
**Tech stack:** ASP.NET Web Forms (.aspx), jQuery, Esri ArcGIS integration
**URL pattern:** `qpublic.schneidercorp.com/Application.aspx?App={CountyNameState}&Layer=Parcels&PageType=Search`
**Key challenge:** Returns 403 on automated requests — requires stealth browser automation
**Bot protection:** Session-based access restrictions, possible rate limiting

**Scraping approach:** Single template handles all qPublic counties — only the `App` parameter changes
```python
# qPublic URL generation for any county
def qpublic_url(county_name, state_abbr):
    app_name = f"{county_name.replace(' ', '')}County{state_abbr}"
    return f"https://qpublic.schneidercorp.com/Application.aspx?App={app_name}&Layer=Parcels&PageType=Search"

# Examples:
# Newton County, GA -> App=NewtonCountyGA
# Clarke County, GA -> App=ClarkeCountyGA
```

### 4.3 Aumentum Technologies

**Market position:** Strong in large counties (Harris County TX), 200+ jurisdictions
**Products:**
- **Aumentum Tax** — billing, collection, cashiering, levy management
- **Aumentum Public Access** — citizen-facing property lookup
- **Aumentum T2** — next-gen platform
- **VCS Tax** — Georgia-specific variant
- **Kansas Patriot & Countyworks** — Kansas-specific variant

**Tech stack:** .NET backend, web-based public access portal
**Scraping approach:** Template per product variant (Aumentum Public Access vs VCS Tax vs Patriot)

### 4.4 Vision Government Solutions

**Market position:** 400+ installations across 10 states, primarily New England (MA, ME, CT, NH, VT) and PA, OH
**Products:**
- **Vision CAMA** — assessment/appraisal backend
- **North Star Portal** — newer web portal
- **Vision Web Portal** — public property data access

**Tech stack:** Proprietary; web portal with configurable public access
**URL pattern:** `gis.vgsi.com/{townstate}/` for GIS views
**Scraping approach:** Template scraper for Vision portal — consistent structure across 400+ towns

### 4.5 Esri ArcGIS (GIS/Parcel Viewers)

**Market position:** Dominant GIS platform; used by nearly every county for mapping. Many counties expose parcel data through ArcGIS REST services.
**Key advantage:** **ArcGIS has a REST API** — no browser automation needed!

```python
# ArcGIS REST API query — no browser needed
import httpx

async def query_arcgis_parcels(service_url, where_clause="1=1", out_fields="*"):
    """Query county ArcGIS parcel layer directly via REST API"""
    params = {
        "where": where_clause,
        "outFields": out_fields,
        "returnGeometry": "false",
        "f": "json",
        "resultOffset": 0,
        "resultRecordCount": 1000
    }
    async with httpx.AsyncClient() as client:
        all_features = []
        while True:
            resp = await client.get(f"{service_url}/query", params=params)
            data = resp.json()
            features = data.get("features", [])
            if not features:
                break
            all_features.extend([f["attributes"] for f in features])
            params["resultOffset"] += len(features)
        return all_features

# Example: Miami-Dade parcels
# Service URL typically: https://{county}.gov/arcgis/rest/services/Parcels/MapServer/0
```

**Discovery pattern:** Many county ArcGIS servers expose a service directory at:
`https://{county-domain}/arcgis/rest/services/`

**Tool: esri2sf** — Open source tool to scrape ArcGIS REST API into structured data: https://github.com/yonghah/esri2sf

### 4.6 Vendor Platform Coverage Summary

| Vendor | Est. Counties | Template Complexity | Priority |
|--------|--------------|-------------------|----------|
| Tyler Technologies | 2,000+ | Medium (multiple products) | **P0 — highest priority** |
| Schneider (qPublic/Beacon) | 400+ | Low (uniform URL structure) | **P0 — highest priority** |
| Aumentum | 200+ | Medium (3 product variants) | **P1** |
| Vision Government Solutions | 400+ (10 states) | Low (consistent portal) | **P1** |
| Esri ArcGIS (REST API) | ~1,000+ (as GIS layer) | **None — REST API** | **P0 — use API directly** |
| Custom / Other | ~500-1,000 | High (each is unique) | **P2 — AI-adaptive tier** |

**By building template scrapers for just these 5 vendors, you cover an estimated 60-70% of all US counties.**

---

## 5. Architecture Recommendations

### 5.1 Three-Tier Scraping Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DISCOVERY AGENT                           │
│  Input: County identifier + search parameters               │
│  Output: List of parcels with tax lien/deed data            │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│              COUNTY ROUTER                                    │
│  Looks up county in registry → determines scraping strategy  │
│                                                              │
│  ┌────────────┐  ┌────────────┐  ┌─────────────────────┐    │
│  │ Tier 1:    │  │ Tier 2:    │  │ Tier 3:             │    │
│  │ API/Bulk   │  │ Template   │  │ AI-Adaptive         │    │
│  │ (~15-20%)  │  │ (~50-60%)  │  │ (~20-30%)           │    │
│  │            │  │            │  │                     │    │
│  │ Socrata    │  │ Tyler      │  │ Stagehand /         │    │
│  │ ArcGIS API │  │ qPublic    │  │ browser-use +       │    │
│  │ County FTP │  │ Aumentum   │  │ Claude for DOM      │    │
│  │ Open Data  │  │ Vision     │  │ understanding       │    │
│  │            │  │ Custom     │  │                     │    │
│  │ No browser │  │ templates  │  │ Full browser +      │    │
│  │ needed     │  │            │  │ LLM navigation      │    │
│  └────────────┘  └────────────┘  └─────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│              BROWSER POOL (Playwright)                        │
│  Managed by Crawlee's BrowserPool or custom pool             │
│  3-4 browser instances per 8GB RAM                           │
│  50-200 concurrent BrowserContexts across instances          │
│  Proxy rotation, session persistence, rate limiting          │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 County Registry / Configuration Database

The core of the system is a **county registry** that maps each of 3,100+ US counties to its scraping strategy:

```python
# County registry schema (PostgreSQL)
"""
CREATE TABLE county_portal_registry (
    county_fips      CHAR(5) PRIMARY KEY,          -- Federal county FIPS code
    state_abbr       CHAR(2) NOT NULL,
    county_name      VARCHAR(100) NOT NULL,

    -- Scraping strategy
    scrape_tier      SMALLINT NOT NULL DEFAULT 3,   -- 1=API, 2=template, 3=AI
    vendor_platform  VARCHAR(50),                    -- 'tyler', 'qpublic', 'aumentum', 'vision', 'esri', 'custom'
    template_id      VARCHAR(50),                    -- Which template scraper to use

    -- Portal URLs
    tax_collector_url    TEXT,
    assessor_url         TEXT,
    treasurer_url        TEXT,
    recorder_url         TEXT,
    gis_url              TEXT,

    -- API endpoints (Tier 1)
    socrata_domain       TEXT,                       -- e.g., 'data.cookcountyil.gov'
    arcgis_service_url   TEXT,                       -- ArcGIS REST endpoint
    bulk_download_url    TEXT,                       -- FTP/direct download

    -- Template config (Tier 2) - JSON blob for template scraper
    template_config      JSONB,

    -- Anti-bot measures detected
    has_captcha          BOOLEAN DEFAULT FALSE,
    captcha_type         VARCHAR(20),                -- 'recaptcha_v2', 'recaptcha_v3', 'hcaptcha', 'image'
    has_tos_clickthrough BOOLEAN DEFAULT FALSE,
    session_timeout_mins INTEGER DEFAULT 30,
    rate_limit_rpm       INTEGER DEFAULT 20,         -- Safe requests per minute

    -- Metadata
    last_verified        TIMESTAMP,
    last_successful_scrape TIMESTAMP,
    scrape_success_rate  FLOAT,                      -- Rolling success %
    notes                TEXT,

    -- Lien/deed classification
    instrument_type      VARCHAR(20) NOT NULL,       -- 'lien', 'deed', 'hybrid'

    created_at           TIMESTAMP DEFAULT NOW(),
    updated_at           TIMESTAMP DEFAULT NOW()
);

-- Index for routing
CREATE INDEX idx_county_vendor ON county_portal_registry(vendor_platform);
CREATE INDEX idx_county_tier ON county_portal_registry(scrape_tier);
CREATE INDEX idx_county_state ON county_portal_registry(state_abbr);
"""
```

### 5.3 Template Scraper Pattern (Tier 2)

```python
# Base template scraper class
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from playwright.async_api import Page

@dataclass
class CountyConfig:
    county_fips: str
    county_name: str
    state_abbr: str
    base_url: str
    template_config: dict  # Vendor-specific overrides

@dataclass
class ParcelRecord:
    parcel_id: str
    owner_name: Optional[str]
    property_address: Optional[str]
    assessed_value: Optional[float]
    tax_amount_due: Optional[float]
    years_delinquent: Optional[int]
    lien_amount: Optional[float]
    auction_date: Optional[str]
    instrument_type: str  # 'lien' or 'deed'
    raw_data: dict  # Full extracted fields

class BaseTemplateScraper(ABC):
    """Base class for vendor-platform template scrapers"""

    def __init__(self, config: CountyConfig):
        self.config = config

    @abstractmethod
    async def navigate_to_search(self, page: Page) -> None:
        """Navigate to the search interface"""
        pass

    @abstractmethod
    async def execute_search(self, page: Page, search_params: dict) -> None:
        """Fill and submit the search form"""
        pass

    @abstractmethod
    async def extract_results(self, page: Page) -> list[ParcelRecord]:
        """Extract results from the current page"""
        pass

    @abstractmethod
    async def has_next_page(self, page: Page) -> bool:
        """Check if there are more result pages"""
        pass

    @abstractmethod
    async def go_next_page(self, page: Page) -> None:
        """Navigate to the next result page"""
        pass

    async def scrape(self, page: Page, search_params: dict) -> list[ParcelRecord]:
        """Full scrape workflow — common across all templates"""
        await self.navigate_to_search(page)
        await self._handle_tos(page)
        await self.execute_search(page, search_params)

        all_results = []
        while True:
            results = await self.extract_results(page)
            all_results.extend(results)
            if await self.has_next_page(page):
                await self.go_next_page(page)
            else:
                break
        return all_results

    async def _handle_tos(self, page: Page):
        """Generic TOS handler — works for most portals"""
        tos_selectors = [
            "button:has-text('I Accept')",
            "button:has-text('I Agree')",
            "button:has-text('Accept')",
            "#disclaimerAccept",
            "#btnAgree",
        ]
        for sel in tos_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=3000):
                    await btn.click()
                    return
            except:
                continue


class TylerPublicAccessScraper(BaseTemplateScraper):
    """Template scraper for Tyler Technologies Public Access portals"""

    async def navigate_to_search(self, page: Page):
        url = f"{self.config.base_url}/publicaccess/SearchByAddress.aspx"
        await page.goto(url)

    async def execute_search(self, page: Page, search_params: dict):
        if "address" in search_params:
            await page.fill("#txtAddress", search_params["address"])
        if "owner_name" in search_params:
            await page.fill("#txtOwnerName", search_params["owner_name"])
        await page.click("#btnSearch")
        await page.wait_for_selector(".search-results", state="visible")

    async def extract_results(self, page: Page) -> list[ParcelRecord]:
        rows = await page.query_selector_all("table.search-results tr[data-parcelid]")
        results = []
        for row in rows:
            results.append(ParcelRecord(
                parcel_id=await row.get_attribute("data-parcelid"),
                owner_name=await (await row.query_selector(".owner-col")).inner_text(),
                property_address=await (await row.query_selector(".address-col")).inner_text(),
                assessed_value=None,  # Requires detail page
                tax_amount_due=None,
                years_delinquent=None,
                lien_amount=None,
                auction_date=None,
                instrument_type=self.config.template_config.get("instrument_type", "lien"),
                raw_data={}
            ))
        return results

    async def has_next_page(self, page: Page) -> bool:
        next_btn = page.locator("a.next-page:not(.disabled)")
        return await next_btn.is_visible()

    async def go_next_page(self, page: Page):
        await page.click("a.next-page")
        await page.wait_for_load_state("networkidle")


class QPublicScraper(BaseTemplateScraper):
    """Template scraper for Schneider Geospatial qPublic portals"""

    async def navigate_to_search(self, page: Page):
        app_name = self.config.template_config.get("app_name")
        url = f"https://qpublic.schneidercorp.com/Application.aspx?App={app_name}&Layer=Parcels&PageType=Search"
        await page.goto(url)

    async def execute_search(self, page: Page, search_params: dict):
        # qPublic uses a tabbed search interface
        if "address" in search_params:
            await page.click("a:has-text('Location Address')")
            await page.fill("#ctlBodyPane_ctl02_txtAddress", search_params["address"])
        await page.click("#ctlBodyPane_ctl02_btnSearch")
        await page.wait_for_selector("#ctlBodyPane_ctl03_grdResults", state="visible")

    async def extract_results(self, page: Page) -> list[ParcelRecord]:
        # qPublic uses ASP.NET GridView for results
        rows = await page.query_selector_all("#ctlBodyPane_ctl03_grdResults tr:not(.header)")
        results = []
        for row in rows:
            cells = await row.query_selector_all("td")
            if len(cells) >= 4:
                results.append(ParcelRecord(
                    parcel_id=await cells[0].inner_text(),
                    owner_name=await cells[1].inner_text(),
                    property_address=await cells[2].inner_text(),
                    assessed_value=None,
                    tax_amount_due=None,
                    years_delinquent=None,
                    lien_amount=None,
                    auction_date=None,
                    instrument_type=self.config.template_config.get("instrument_type", "lien"),
                    raw_data={}
                ))
        return results

    async def has_next_page(self, page: Page) -> bool:
        return await page.locator("a:has-text('Next')").is_visible()

    async def go_next_page(self, page: Page):
        await page.click("a:has-text('Next')")
        await page.wait_for_load_state("networkidle")
```

### 5.4 AI-Adaptive Scraper (Tier 3)

For unknown portals, use an LLM to understand and navigate the page:

```python
# AI-adaptive scraper using Stagehand or browser-use
# Option A: Stagehand (TypeScript, built on Playwright)
# Option B: browser-use (Python, uses vision + DOM)

# browser-use approach (Python — best fit for Aloha's stack)
from browser_use import Agent
from langchain_anthropic import ChatAnthropic

async def ai_scrape_unknown_portal(portal_url: str, search_params: dict):
    """Use AI to navigate an unknown county portal and extract tax data"""

    llm = ChatAnthropic(model="claude-sonnet-4-20250514")  # Fast + capable

    task = f"""
    Navigate to {portal_url} and search for tax lien or tax deed information.

    Steps:
    1. Accept any Terms of Service or disclaimers
    2. Find the property search form
    3. Search for properties with delinquent taxes using these parameters:
       - Address: {search_params.get('address', 'N/A')}
       - Parcel ID: {search_params.get('parcel_id', 'N/A')}
       - Owner: {search_params.get('owner_name', 'N/A')}
    4. Extract all results including:
       - Parcel/Property ID
       - Owner name
       - Property address
       - Tax amount due
       - Years delinquent
       - Lien amount
       - Auction date (if shown)
    5. If there are multiple pages of results, navigate through all pages
    6. Return all extracted data as JSON
    """

    agent = Agent(task=task, llm=llm)
    result = await agent.run()
    return result

# Cost estimate: ~$0.05-0.10 per portal navigation using Claude Sonnet
# At scale, this is 10-50x more expensive than template scrapers
# Use ONLY for counties without templates
```

**Hybrid approach (recommended):**
```python
# Use Playwright for the predictable 80%, AI for the unpredictable 20%
async def hybrid_scrape(page, county_config, search_params):
    """Playwright for structure, AI for ambiguity"""

    # Navigate with Playwright (fast, reliable)
    await page.goto(county_config["search_url"])

    # AI identifies the search form if selectors aren't configured
    if not county_config.get("form_selectors"):
        # Send page HTML to Claude for selector identification
        html = await page.content()
        selectors = await identify_selectors_with_llm(html)
        county_config["form_selectors"] = selectors
        # Cache the selectors for next time!
        await save_selectors_to_registry(county_config["county_fips"], selectors)

    # Continue with standard Playwright scraping using identified selectors
    for field, selector in county_config["form_selectors"].items():
        await page.fill(selector, search_params.get(field, ""))
    # ...
```

### 5.5 Browser Pool Management

```python
# Production browser pool configuration
from crawlee.playwright_crawler import PlaywrightCrawler
from crawlee.configuration import Configuration

# Crawlee handles browser pool automatically
crawler = PlaywrightCrawler(
    # Browser pool settings
    max_concurrency=50,           # Max concurrent pages across all browsers
    browser_pool_options={
        "max_open_pages_per_browser": 10,   # Pages per browser instance
        "retire_browser_after_page_count": 100,  # Restart browsers to prevent memory leaks
        "browser_plugins": [
            # Use stealth plugin
        ],
    },
    # Playwright launch options
    playwright_launcher_options={
        "headless": True,
        "args": [
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
        ],
    },
    # Request handling
    max_request_retries=3,
    request_handler_timeout=timedelta(seconds=120),
)
```

**Memory planning:**
| Deployment | RAM | Browser Instances | Concurrent Contexts | Counties/Hour |
|-----------|-----|-------------------|--------------------|----|
| Development (local) | 16GB | 2 | 10-20 | ~50-100 |
| Production (small) | 32GB | 4-6 | 50-80 | ~200-400 |
| Production (medium) | 64GB | 8-12 | 100-150 | ~500-800 |
| Production (large) | 128GB+ or distributed | 20+ | 200+ | ~1,000-2,000 |

At ~500 counties/hour sustained, you can cover all 3,100+ US counties in ~6 hours per full crawl cycle.

---

## 6. Existing Tools and Frameworks

### 6.1 Crawlee (Apify) — RECOMMENDED as Core Framework

**What it is:** Open-source web scraping and browser automation framework (Node.js and Python versions)
**Why it fits:**
- `PlaywrightCrawler` — handles browser lifecycle, retries, request queuing
- Built-in proxy rotation support
- Session management with cookie persistence
- Automatic retry with configurable backoff
- Request queue with deduplication
- `BrowserPool` for managing concurrent browser instances
- Python version available (though JS version is more mature)

**Limitation:** Python version is newer and less feature-complete than JS. For production, consider the Node.js version for the crawling layer even if the rest of Aloha is Python, or use the Python version with some custom extensions.

```python
# Crawlee Python example for county scraping
from crawlee.playwright_crawler import PlaywrightCrawler, PlaywrightCrawlingContext

crawler = PlaywrightCrawler(
    max_concurrency=20,
    max_request_retries=3,
)

@crawler.router.default_handler
async def handle_county_search(context: PlaywrightCrawlingContext):
    page = context.page
    county_fips = context.request.user_data.get("county_fips")

    # Route to appropriate template scraper based on vendor
    scraper = get_scraper_for_county(county_fips)
    results = await scraper.scrape(page, context.request.user_data.get("search_params"))

    # Push results to dataset
    await context.push_data({"county": county_fips, "results": results})

# Enqueue all county search URLs
await crawler.run([
    Request(url=county["search_url"], user_data={"county_fips": county["fips"]})
    for county in active_counties
])
```

### 6.2 Scrapy + Playwright Integration

**What it is:** Scrapy with scrapy-playwright plugin for JavaScript rendering
**Pros:** Scrapy's mature pipeline, middleware, and scheduling + Playwright rendering
**Cons:** More complex setup; two frameworks to learn; less natural for heavy browser interaction

```python
# scrapy-playwright settings
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}
PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {"headless": True}
PLAYWRIGHT_MAX_CONTEXTS = 10
PLAYWRIGHT_MAX_PAGES_PER_CONTEXT = 5
```

**Verdict:** Good if the team already knows Scrapy. Otherwise, Crawlee is simpler for this use case.

### 6.3 browser-use — AI Browser Automation

**What it is:** Open-source AI browser agent (50K+ GitHub stars). Uses vision models + DOM extraction for LLM-driven web navigation.
**Best for:** Tier 3 AI-adaptive scraping of unknown portals
**Supports:** OpenAI, Anthropic, Google, open-source models
**Self-hostable:** Yes, bring your own API keys

**Use case in Aloha:** Tier 3 fallback for counties without template scrapers. Also useful for initial discovery of new portal structures.

### 6.4 Stagehand (Browserbase)

**What it is:** TypeScript SDK for AI browser automation built on Playwright (v3 moved to CDP directly)
**Key features:**
- `act()` — perform an action described in natural language
- `extract()` — extract structured data from a page
- `observe()` — understand what's on the page
- `agent()` — autonomous multi-step task execution
- Intelligent caching — learned selectors reused without LLM calls

**Limitation:** TypeScript only (not Python). Could be used as a microservice if needed.

**Use case in Aloha:** Best for prototyping Tier 3 scrapers. In production, prefer browser-use (Python) or the hybrid Playwright + Claude approach for Python compatibility.

### 6.5 AgentQL — Semantic Web Scraping

**What it is:** AI-powered framework using natural language queries instead of CSS/XPath selectors
**Key feature:** `query_data()` with plain English descriptions like "find the property tax table with columns for parcel ID, owner, and amount due"
**Pricing:** Free tier: 100 queries/day. Pro: 10,000+ data points/month
**SDKs:** Python and Node.js

**Use case in Aloha:** Potential alternative to browser-use for Tier 3. The natural language query approach is elegant but may be less reliable than direct DOM manipulation for production.

### 6.6 Firecrawl

**What it is:** API that turns websites into LLM-ready markdown or structured data
**Key feature:** Zero-selector extraction — describe what you want in natural language
**Pricing:** Cloud API ($0.001-0.01 per page)
**Open source:** Yes (self-hostable)

**Use case in Aloha:** Useful for Tier 3 as a managed service, but adds dependency. Better to build extraction in-house using Playwright + Claude.

### 6.7 Skyvern

**What it is:** AI-powered browser automation platform specifically designed for form filling and government portals
**Key features:**
- Vision LLM + DOM understanding
- Specifically optimized for government forms
- 85.85% on WebVoyager benchmark
- Best-performing agent on form-filling tasks

**Use case in Aloha:** Most directly relevant to the problem. Could be used for Tier 3 government portal navigation. Open source and self-hostable.

### 6.8 Existing Open-Source Government Data Scrapers

| Project | URL | Description | Usefulness |
|---------|-----|-------------|-----------|
| **ca-property-tax** | github.com/typpo/ca-property-tax | California county property tax scrapers (Python) | **High** — reference implementation for per-county scraping patterns |
| **cook_county_address_scraper** | github.com/stevevance/cook_county_address_scraper | Cook County PIN scraper | Medium — Cook County specific |
| **hcad-property-taxes** | github.com/gboogy/hcad-property-taxes | Harris County TX property tax scraper | Medium — Harris County specific |
| **assessor-scraper (NOLA)** | github.com/codefornola/assessor-scraper | New Orleans assessor scraper (Scrapy + PostgreSQL) | **High** — good architecture reference |
| **property-tax-by-county** | github.com/TaxFoundation/property-tax-by-county | Tax Foundation county-level data | Low — aggregated data, not per-parcel |
| **esri2sf** | github.com/yonghah/esri2sf | ArcGIS REST API to structured data | **High** — direct use for Esri-based counties |

---

## 7. Final Recommendations for Aloha

### 7.1 Technology Stack for Scraping Layer

| Component | Recommendation | Rationale |
|-----------|---------------|-----------|
| **Core browser automation** | Playwright (Python) | Best auto-wait, performance, stealth, Python-native |
| **Crawling framework** | Crawlee (Python) | Browser pool, retry, proxy rotation, request queue |
| **AI navigation (Tier 3)** | browser-use or Skyvern (Python) | LLM-driven navigation for unknown portals |
| **CAPTCHA solving** | 2Captcha API (fallback only) | Most gov portals pass with stealth mode |
| **Proxy rotation** | Bright Data or IPRoyal (datacenter first) | Government sites rarely block datacenter IPs |
| **ArcGIS data** | Direct REST API via httpx | No browser needed — fastest extraction method |
| **Selector discovery** | Claude API (HTML -> selectors) | One-time cost per new portal; cache results |

### 7.2 Development Priority Order

1. **Build the county registry database** — Map all 3,100+ counties to vendor, URLs, instrument type
2. **Implement Esri/ArcGIS REST API scrapers** — Covers ~1,000 counties with zero browser overhead
3. **Build Tyler Technologies template scraper** — Covers the largest vendor (~2,000 jurisdictions)
4. **Build qPublic/Beacon template scraper** — Covers ~400 counties (uniform URL pattern)
5. **Build Vision Government Solutions template scraper** — Covers ~400 towns (New England focus)
6. **Build Aumentum template scraper** — Covers ~200 jurisdictions
7. **Implement Tier 3 AI-adaptive scraper** — For remaining ~500-1,000 unique portals
8. **Build CAPTCHA handling pipeline** — 2Captcha integration for the ~20% that need it
9. **Scale browser pool** — Production deployment with distributed browser instances

### 7.3 Cost Projections (Monthly at Scale)

| Item | Cost Estimate |
|------|-------------|
| Compute (browser pool, 64GB node) | $200-400 |
| Proxy rotation (datacenter) | $50-200 |
| CAPTCHA solving (2Captcha) | $100-500 |
| Claude API (Tier 3 AI navigation) | $200-500 |
| Claude API (selector discovery, one-time) | $50-100 |
| **Total** | **$600-1,700/month** |

This covers full scraping of 3,100+ counties with weekly refresh cycles.

### 7.4 Key Risk: Legal / Terms of Service

- Most county property records are **public records** under state open records laws
- However, automated access may violate individual portal Terms of Service
- **Mitigation:** Use bulk data downloads (Tier 1) whenever available; scrape at reasonable rates; comply with robots.txt; consider formal data-sharing agreements with major counties
- The CFAA (Computer Fraud and Abuse Act) risk is low for public records but not zero — consult legal counsel

---

## Sources

- [Selenium vs Puppeteer vs Playwright Comparison](https://dev.to/evanmorris/selenium-vs-puppeteer-vs-playwright-the-browser-automation-reality-check-404a)
- [Puppeteer vs Playwright vs Selenium: Ultimate Comparison for 2026](https://iproyal.com/blog/puppeteer-vs-playwright-vs-selenium/)
- [Playwright vs Selenium 2025](https://www.browserless.io/blog/playwright-vs-selenium-2025-browser-automation-comparison)
- [Crawlee GitHub (Node.js)](https://github.com/apify/crawlee)
- [Crawlee Python](https://crawlee.dev/python/)
- [browser-use](https://browser-use.com/)
- [Stagehand v3](https://www.browserbase.com/blog/stagehand-v3)
- [Stagehand vs Browser Use vs Playwright (2026)](https://www.nxcode.io/resources/news/stagehand-vs-browser-use-vs-playwright-ai-browser-automation-2026)
- [AgentQL](https://www.agentql.com)
- [Firecrawl](https://www.firecrawl.dev/)
- [Skyvern Government Form Automation](https://www.skyvern.com/government)
- [Tyler Technologies Appraisal & Tax](https://www.tylertech.com/solutions/public-administration/appraisal-tax)
- [Tyler Technologies iasWorld CAMA](https://www.tylertech.com/products/iasworld/cama)
- [Aumentum Technologies](https://www.aumentumtech.com/)
- [Aumentum Public Access](https://www.aumentumtech.com/aumentum-public-access)
- [Vision Government Solutions](https://www.vgsi.com/)
- [qPublic (Schneider Geospatial)](https://qpublic.schneidercorp.com/)
- [Beacon (Schneider Geospatial)](https://beacon.schneidercorp.com/)
- [Esri ArcGIS REST API](https://developers.arcgis.com/rest/)
- [esri2sf GitHub](https://github.com/yonghah/esri2sf)
- [ca-property-tax GitHub](https://github.com/typpo/ca-property-tax)
- [Cook County Property Tax Portal](https://www.cookcountypropertyinfo.com/)
- [assessor-scraper (Code for NOLA)](https://github.com/codefornola/assessor-scraper)
- [hcad-property-taxes GitHub](https://github.com/gboogy/hcad-property-taxes)
- [Avoid Bot Detection with Playwright Stealth](https://www.scrapeless.com/en/blog/avoid-bot-detection-with-playwright-stealth)
- [Playwright Stealth (Bright Data)](https://brightdata.com/blog/how-tos/avoid-bot-detection-with-playwright-stealth)
- [2Captcha](https://2captcha.com)
- [CapSolver](https://www.capsolver.com/)
- [Anti-Captcha](https://anti-captcha.com/)
- [Building a Scalable Browser Pool with Playwright](https://medium.com/@devcriston/building-a-robust-browser-pool-for-web-automation-with-playwright-2c750eb0a8e7)
- [Apify Browser Pool](https://github.com/apify/browser-pool)
- [Scrapy Playwright Tutorial (BrowserStack)](https://www.browserstack.com/guide/scrapy-playwright)
- [Rate Limiting in Web Scraping (Apify)](https://docs.apify.com/academy/anti-scraping/techniques/rate-limiting)
- [IP Rotation for Scraping (ZenRows)](https://www.zenrows.com/blog/ip-rotation-scraping)
- [Web Scraping with Claude in 2026](https://medium.com/@datajournal/web-scraping-with-claude-in-2025-automating-data-extraction-effortlessly-15f0a6c8020c)
- [AI Web Scraping in 2026 Complete Guide](https://sites.google.com/view/back-of-the-envelope/ai-web-scraping-in-2026-a-complete-guide-to-smarter-data-extraction)
- [Drupal for Government](https://new.drupal.org/industries/government)
- [8GB Was a Lie: Playwright in Production](https://medium.com/@onurmaciit/8gb-was-a-lie-playwright-in-production-c2bdbe4429d6)
