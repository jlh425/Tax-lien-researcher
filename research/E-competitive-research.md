# Section E — Competitive Research
**Created:** 2026-03-16
**Status:** COMPLETE

---

## E.1 — How Existing Tools Handle This

### The Competitive Landscape

The market splits into three tiers: **general real estate investor platforms** (PropStream, BatchLeads, DealMachine), **enterprise data APIs** (ATTOM), and **tax-sale-specific tools** (Tax Sale Resources, Lumentum). None of them do what Aloha does.

---

### PropStream — $99/mo (Most Popular Retail Tool)

**Website:** propstream.com

**What it does:**
- Nationwide property database (primarily from public records + MLS)
- 165+ property filters including tax lien, pre-foreclosure, vacant, absentee owner
- Skip tracing (finds phone/email for property owners) — $0.12/record
- Basic outreach: ringless voicemail ($0.10), postcards ($0.40), email ($0.02)
- Comparable sales / AVM (automated valuation model)
- List Automator add-on ($27/mo) — auto-monitors saved searches for new matches

**How it handles tax liens:**
- Surfaces properties flagged as tax delinquent by county assessors via public records
- Does NOT have live auction data — data lags by weeks/months
- Does NOT distinguish lien certificate vs. tax deed by state
- No scoring model — user has to evaluate manually
- No deep owner research — gives one name + skip-traced phone/email
- No entity research (LLC, trust, corporation structure)
- No property imagery beyond a static map thumbnail

**Gaps vs. Aloha:**
- Stale data (batch updates, not live) — misses auctions already happened
- No instrument classification — investor must know state law themselves
- Skip tracing is basic consumer-grade — no LLC/trust piercing
- No scoring — user looks at raw data and guesses
- No evidence trail / screenshots of source data
- No automated outreach beyond simple direct mail/voicemail blasts
- No GIS parcel map, Street View, satellite, or zoning overlay imagery

---

### BatchLeads — ~$119-$299/mo

**Website:** batchleads.io

**What it does:**
- List builder with tax delinquency, pre-foreclosure, and vacancy filters
- BatchRank AI — proprietary lead scoring based on likelihood-to-sell signals
- SMS marketing campaigns — primary differentiator (bulk texting)
- Skip tracing ($0.19-0.29/record)
- Team collaboration (unlimited users on higher plans)

**How it handles tax liens:**
- Tax delinquency as one of many lead filters — not specialized
- No auction data, no instrument type, no lien-specific scoring
- Focus is on motivated seller marketing, not investment due diligence
- SMS campaigns are the product — research is secondary

**Gaps vs. Aloha:**
- Marketed as a wholesaler/marketing tool, not a tax lien investment tool
- No deep research — data point is "this property has a tax lien"; that's it
- No county data source integration, no live auction data
- BatchRank AI scores likelihood-to-sell (general), not lien investment merit

---

### DealMachine — $49-$199/mo

**Website:** dealmachine.com

**What it does:**
- Mobile-first "driving for dollars" app — photograph properties while driving
- List builder with tax delinquency, pre-foreclosure filters
- CRM + direct mail integration
- AI-powered property analysis (basic)
- Skip tracing built in

**How it handles tax liens:**
- Tax delinquency as a filter, not a core use case
- No live auction data, no instrument type awareness
- Mobile-first design optimized for wholesalers, not tax lien certificate investors

**Gaps vs. Aloha:**
- Not built for tax lien investing specifically
- No deep research, no entity piercing, no scoring model
- No auction platform integration

---

### ATTOM Data Solutions — Enterprise ($500-$50,000+/yr depending on usage)

**Website:** attomdata.com

**What it does:**
- Enterprise property data API: 158M+ US properties, 99% population coverage
- Tax assessment, deed history, mortgage, foreclosure, AVM, school ratings, climate risk
- REST API (JSON/XML), bulk data delivery, cloud data licensing
- 10 years of sales history
- Developer platform with full API documentation

**How it handles tax liens:**
- Tax assessment and delinquency data included as a data field
- This is raw data infrastructure — ATTOM sells data TO tools like PropStream
- No investor-facing UI, no scoring, no outreach, no imagery
- Expensive for individual investors — designed for enterprise and data resellers

**Strategic note:** ATTOM is a potential data source for Aloha (paid add-on tier), not a competitor in the user-facing sense. Users of Aloha would never interact with ATTOM directly.

---

### Tax Sale Resources — Undisclosed pricing (free trial available)

**Website:** taxsaleresources.com

**What it does:**
- The most specialized tax lien platform in the market
- **Research:** Nationwide tax sale data, county-by-county auction schedules and results
- **Management:** Portfolio tracking for held lien certificates
- **Financing:** Pre-clear-title financing for investors
- **Trade:** Secondary market brokerage for lien certificates

**How it handles tax liens:**
- Live auction data and schedules — better than PropStream on timing
- Property detail, lien status, basic filtering and search
- Portfolio management for investors who already hold liens
- Automated alerts for auction dates and property changes

**Gaps vs. Aloha:**
- No deep owner research — identifies lien, not beneficial owner
- No entity/trust research
- No AI scoring — manual evaluation
- No property imagery pipeline
- No evidence/screenshot capture
- No owner outreach integration
- Focused on institutional/professional investors; pricing reflects that
- Still not AI-driven — human analyst workflow assumed

---

### Lumentum / DigiPan 8.0 — Institutional only

**Website:** lumentumllc.com

**What it does:**
- Aggregated, normalized distressed real estate and tax lien certificate data
- Secondary market trading of lien certificate portfolios
- Servicing solutions for institutional lien holders
- DigiPan 8.0 platform for due diligence at institutional scale

**Gaps vs. Aloha:**
- Institutional only (banks, hedge funds, large operators) — not consumer SaaS
- Focused on managing existing lien portfolios, not discovering new opportunities
- No self-serve, no tiered pricing, no small investor access

---

### RealtyTrac — Consumer-grade ($49/mo)

**What it does:**
- Pre-foreclosure and foreclosure listing aggregator
- Basic property data, neighborhood stats
- Primarily consumer/agent-facing

**How it handles tax liens:**
- Tax delinquency and pre-foreclosure listings
- Very surface-level — just the property address and basic status
- No deep research, no scoring, no owner contact, no imagery

---

### Competitive Summary Table

| Feature | PropStream | BatchLeads | Tax Sale Resources | ATTOM API | **Aloha** |
|---------|-----------|-----------|-------------------|-----------|-----------|
| Live auction data | ❌ (batch) | ❌ | ✅ | ❌ | ✅ |
| Lien cert vs. deed classification | ❌ | ❌ | Partial | ❌ | ✅ (all 50 states) |
| Deep owner research | ❌ | ❌ | ❌ | ❌ | ✅ (4 layers) |
| LLC/trust entity piercing | ❌ | ❌ | ❌ | ❌ | ✅ |
| AI scoring (instrument-aware) | ❌ | Basic | ❌ | ❌ | ✅ |
| GIS parcel map imagery | ❌ | ❌ | ❌ | ❌ | ✅ |
| Street View + satellite | ❌ | ❌ | ❌ | ❌ | ✅ |
| Screenshot evidence trail | ❌ | ❌ | ❌ | ❌ | ✅ |
| Multi-channel outreach (SMS/voice) | Partial | ✅ SMS | ❌ | ❌ | ✅ |
| AI voice agent | ❌ | ❌ | ❌ | ❌ | ✅ (Phase 3) |
| PDF report export | ❌ | ❌ | ❌ | ❌ | ✅ |
| Tiered SaaS (freemium) | ❌ | ❌ | ❌ | ❌ | ✅ |
| All-states fluid pipeline | ❌ | ❌ | Partial | ✅ data only | ✅ |
| **Price** | **$99/mo** | **$119-299/mo** | **Undisclosed** | **$500+/yr** | **Freemium** |

---

## E.2 — What Investors Do Manually (What Aloha Automates)

This is the core product validation: tax lien investing is predominantly a **manual, time-consuming, error-prone research process**. Here is the full investor workflow today:

### Step 1: Find the auction list (1-3 hours per county)

**What investors do:**
- Google "[county name] tax lien sale 2025"
- Navigate to county tax collector website (often broken, poorly organized)
- Find the delinquent property list — sometimes a PDF, sometimes a search portal
- Download or manually copy rows of data (parcel ID, address, amount owed)
- If online auction (Bid4Assets, GovEase, etc.): register on the platform, browse listings one by one

**Pain points:** Inconsistent formats per county. PDFs require manual parsing. Some portals require registration. Lists only posted weeks before auction. No single source covers all states.

**Aloha automates:** Discovery Agent crawls the source for any US county, normalizes data, detects instrument type, and queues all properties for research automatically.

---

### Step 2: Research each property (15-45 min per property)

**What investors do:**
- Open county assessor website → search parcel ID → copy owner name + mailing address + assessed value
- Open county GIS → search parcel → screenshot the map (or just look at it)
- Open Google Maps → search address → check Street View manually
- Look up Zillow → get market value estimate, recent sales
- Manually record all of this in a spreadsheet

**Pain points:** 3-5 websites per property. Lots of copy-paste. Manual errors. Assessor sites go down or change format. GIS sites require different search syntax per county.

**Aloha automates:** Parcel Research Agent pulls assessor data via API/scraper, GIS map captured automatically with zoning overlay and parcel boundary lines, Street View and satellite captured via API, Zillow data pulled as available — all linked to the parcel record with source URLs and screenshots.

---

### Step 3: Research the owner (30 min to 4 hours per property)

**What investors do:**

*If individual owner:*
- Google name + city → look for LinkedIn, Facebook, news mentions
- Check WhitePages/BeenVerified → try to find phone number and email
- Sometimes pay for skip trace ($0.12-0.30 per record via PropStream)
- Build a one-pager with whatever they found

*If LLC/entity owner:*
- Visit Secretary of State website for the relevant state
- Search the LLC name → find registered agent + manager/member names (if disclosed)
- If DE or WY LLC: essentially nothing disclosed — give up or pay attorney
- Google the manager names → try to find contact info
- This step alone can take hours with no guarantee of finding anything

*If trust:*
- Almost always give up — trust instruments are private, trustees often title companies
- Most investors skip trust-owned properties entirely

**Pain points:** Every state's SOS website works differently. DE/WY LLCs designed to obscure. No tool currently does automated LLC piercing for small investors. Social media research is all manual. Takes so long that investors only do it for their top-ranked properties.

**Aloha automates:** Owner Research Agent + Entity Research Agent handle all of this systematically: 4-layer individual research, 4-layer entity research (SOS → registered agent clustering → deed chain → UCC → court records → social), confidence scoring on every piece of contact info found.

---

### Step 4: Score and rank opportunities (1-2 hours per batch)

**What investors do:**
- Build an Excel spreadsheet with columns: address, lien amount, assessed value, LTV ratio, years delinquent, owner type, contact found (Y/N)
- Manually calculate LTV = lien / assessed value
- Sort by LTV ascending to find the best collateral coverage
- Add subjective notes ("LLC, couldn't find owner — skip", "nice neighborhood", "vacant lot")
- Highlight best ones manually

**Pain points:** Fully manual. No weights or formula. Different investors use different intuitions. Doesn't account for redemption deadline urgency. Doesn't separate lien cert logic from deed logic.

**Aloha automates:** Scoring Agent uses instrument-aware model (separate cert vs. deed formulas) with configurable weights. Score 0-100 with full rationale text. Sorted and filterable in the UI.

---

### Step 5: Contact the owner (30 min to 2 hours per contact)

**What investors do:**
- Write a letter manually or use a template
- Mail it via USPS (or PropStream's postcard service at $0.40/card)
- Wait 2-4 weeks for response
- If phone number found: call manually (no DNC check usually)
- Track responses in a spreadsheet or basic CRM

**Pain points:** No DNC checking for most small investors (legal risk). Slow turnaround on mail. No follow-up sequencing. No tracking of open/read rates. Writing individual letters is tedious.

**Aloha automates:** Outreach Agent handles email (with DNC/CAN-SPAM compliance), SMS (with A2P 10DLC, DNC check), phone (click-to-call with call logging), and AI voice (Phase 3). Multi-channel sequences with configurable delays. Full deliverability tracking.

---

### Step 6: Attend the auction

**What investors do:**
- Show up to courthouse steps (or log into online auction platform)
- Reference their handwritten notes / spreadsheet
- Bid based on gut + pre-computed max bid limit
- Win or lose, track results manually

**Pain points:** Lots of properties, fast decisions, limited reference material on hand. Easy to overbid in the heat of the moment. No systematic tracking of bids vs. outcomes.

**Aloha automates (Phase 4):** Guided walkthrough UI with checklist, pre-computed max bid recommendations, and eventually automated bidding within user-defined limits on Bid4Assets, GovEase, and RealAuction.

---

### Time Savings Summary

| Task | Manual Time | Aloha Time |
|------|------------|-----------|
| County auction list collection | 1-3 hrs/county | ~5 min (automated) |
| Per-property research (assessor, GIS, imagery) | 15-45 min/property | ~2 min (automated) |
| Per-owner research (individual) | 30-60 min/property | ~5 min (automated) |
| Per-owner research (LLC/entity) | 1-4 hrs/property | ~15 min (automated) |
| Scoring and ranking 50 properties | 1-2 hrs | ~30 sec (automated) |
| Writing and sending outreach | 30-120 min/batch | ~5 min (template + send) |
| **Total for 50 properties** | **40-120+ hours** | **~2-3 hours (review + approve)** |

---

## E.3 — Existing Open Source Scrapers to Build On

### What Exists

| Project | Language | Scope | Status | Build-On Value |
|---------|---------|-------|--------|---------------|
| [tedbeck/web-scraper](https://github.com/tedbeck/web-scraper) | Python | Tax lien notices from newspaper aggregator | Narrow, old | Low — newspaper-specific |
| [codefornola/assessor-scraper](https://github.com/codefornola/assessor-scraper) | Python | Orleans Parish (New Orleans) assessor | Single county, old | Medium — parcel_id_extractor pattern useful |
| [ottinger/ok-assessor-scraper](https://github.com/ottinger/ok-assessor-scraper) | Python | Oklahoma County assessor | Single county | Low — county-specific |
| [ZacharyHampton/HomeHarvest](https://github.com/ZacharyHampton/HomeHarvest) | Python (PyPI) | Zillow/Redfin/Realtor.com listing scraper | Active (PyPI) | Medium — Zillow photo/listing scraper useful |
| [typpo/ca-property-tax](https://github.com/typpo/ca-property-tax) | Python | CA property tax visualization | Old | Low |
| GitHub topic: `tax-lien` | Mixed | Mostly state classification lists, no scrapers | Various | Reference only |
| GitHub topic: `property-tax` | Mixed | Individual county scrapers, no aggregation | Various | Pattern reference |

### Key Finding: No Multi-State Tax Lien Scraper Exists

There is no open-source tool that:
- Covers multiple counties or states
- Handles the Discovery stage (finding liens/deeds for auction)
- Integrates with auction platforms (Bid4Assets, GovEase, LienHub, LGBS)
- Handles instrument type detection (lien cert vs. deed)

**Aloha has a clear greenfield.** No open source project to fork — must build from scratch. However, useful patterns can be borrowed:

### What to Borrow

**From `codefornola/assessor-scraper`:**
- The `parcel_id_extractor.py` pattern — using owner-name search to enumerate all parcel IDs, then batch-fetching each. Useful for assessor portals with no bulk export.

**From `HomeHarvest`:**
- Zillow listing/photo scraper approach. HomeHarvest is active on PyPI (`pip install homeharvest`). Can be adapted or called directly for the Zillow photo layer in Aloha's imagery pipeline.

**From Playwright/browser-use community:**
- Many single-county scrapers in the wild (not packaged) use Playwright. The B.6.2 research identified that Tyler Technologies (~2,000 jurisdictions) and qPublic (~400 counties) use vendor-template portals — template scrapers for these platforms would cover a large percentage of all US counties.

### PyPI Libraries Relevant to Aloha

| Package | Use Case | Status |
|---------|---------|--------|
| `homeharvest` | Zillow/Redfin listing + photo scraping | Active |
| `usaddress` | Address parsing/normalization | Active (v0.5.16) |
| `rapidfuzz` | Owner name fuzzy matching | Active (v3.14.3) |
| `docling` | PDF OCR + table extraction | Active (IBM, MIT) |
| `playwright` | Browser automation for portals | Active |
| `crawlee` | Playwright-based scraping framework | Active |
| `pydantic-ai` | Agent framework | Active |
| `apscheduler` | Database Subagent cron scheduling | Active |
| `smartystreets-python-sdk` | Address validation | Active (v5.1.0) |
| `2captcha-python` | CAPTCHA solving fallback | Active |

No tax-lien-specific PyPI package exists. Aloha will be the first.

---

## E.4 — Pricing Benchmarks for Aloha Tiers

Based on competitive research, here is where Aloha should position:

| Competitor | Price | What's Included |
|-----------|-------|----------------|
| PropStream | $99/mo | Property data, basic skip trace, basic outreach |
| BatchLeads | $119-299/mo | List building, SMS campaigns, team features |
| DealMachine | $49-199/mo | Mobile driving for dollars, CRM, mail |
| Tax Sale Resources | Undisclosed | Specialized tax sale data, portfolio management |
| RealtyTrac | $49/mo | Basic foreclosure listings |

**Aloha positioning:**
- **Free:** 50 properties/mo, Level 1-2 owner research, basic scoring, no outreach — lower barrier than any competitor
- **Starter ($49/mo):** 500 properties/mo, Level 1-2 research, email outreach — below PropStream, with deeper tax lien focus
- **Professional ($99/mo):** 5,000 properties/mo, Level 3-4 research (entity piercing), email+SMS outreach — matches PropStream price with dramatically more capability
- **Enterprise ($249/mo):** Unlimited, Level 5 research (full depth), all outreach channels (phone + AI voice), continuous monitoring, team access

Aloha is the only tool that combines **discovery + deep research + imagery + scoring + outreach** in a single workflow specifically designed for tax lien/deed investing.

---

*Sources: PropStream.com, PropStream pricing page, SparkRental PropStream review, BatchLeads.io, DealMachine.com, ATTOMdata.com, TaxSaleResources.com, Lumentumllc.com, GitHub tax-lien topic, HomeHarvest PyPI, Tax Sale Resources blog, Anderson Advisors tax lien investing guide*
