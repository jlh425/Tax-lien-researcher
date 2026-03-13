# Tax Lien Researcher — Open Questions & Research Tasks
**Created:** 2026-03-13
**Status:** ACTIVE — answers needed before PRD can be finalized

---

## SECTION A: Questions for the User (Need Answers First)

These block PRD finalization. Answer these before proceeding to implementation.

### A.1 Scope & Use Case

- [ ] **A.1.1** What is the primary goal?
  - Tax lien investing (buy certificates at auction)?
  - Pre-foreclosure / distressed property identification?
  - Due diligence before purchasing a property?
  - Asset tracing / skip tracing?
  - Other?

- [ ] **A.1.2** What geographic scope do you want to start with?
  - Single county (name it)?
  - All counties in a single state?
  - Multi-state?
  - Should location be a configurable input at runtime?

- [ ] **A.1.3** Which state(s) are you targeting first?
  - Tax lien law varies enormously by state. Some states sell lien certificates (FL, AZ, NJ, CO), others sell the deed directly (TX, GA). Knowing the state shapes the entire research strategy.

- [ ] **A.1.4** Are you interested in all property types or specific ones?
  - Residential (houses, condos)
  - Commercial (retail, office)
  - Vacant land / raw land
  - Industrial
  - Agricultural
  - All of the above

- [ ] **A.1.5** Any minimum lien amount threshold?
  - (e.g., only find liens > $1,000 or > $5,000?)

- [ ] **A.1.6** Any minimum property value threshold?
  - (e.g., only research parcels with assessed value > $50,000?)

---

### A.2 Output & Delivery

- [x] **A.2.1** What format do you want the output?
  - **Decision:** Both web UI (Archon2.0 card+split view) AND PDF export (on-demand, toggleable inclusion of screenshots). Web is primary working view; PDF for sharing. See PRD §8.1.

- [x] **A.2.2** Where should results be saved?
  - **Decision:** Local PostgreSQL database (this machine). Property images + screenshots stored to local filesystem under `/data/`. DuckDB for analytics queries over the dataset.

- [ ] **A.2.3** Do you want alerts when high-value liens are found?
  - Email?
  - Slack/Telegram?
  - Desktop notification?

---

### A.3 Research Depth

- [ ] **A.3.1** How deep should owner research go?
  - Level 1: Owner name + mailing address only (from assessor)
  - Level 2: + entity details (SOS filing) if owner is LLC/trust
  - Level 3: + beneficial owner research (pierce the entity)
  - Level 4: + social media / contact research
  - Level 5: Full intelligence profile

- [ ] **A.3.2** For social media research — which platforms?
  - LinkedIn (professional/business)
  - Facebook (personal/local business)
  - Instagram
  - Twitter/X
  - All of the above
  - None (stick to public records only)

- [ ] **A.3.3** Are you comfortable with social media browser automation (potential ToS risk)?

- [ ] **A.3.4** For business entities — how deep on corporate structure?
  - Just registered agent + manager/officer names
  - Full ownership chain (parent companies, subsidiaries)
  - Related entities under same registered agent

---

### A.4 Operations

- [ ] **A.4.1** Should the agent run:
  - On-demand only (you trigger it when you want research done)?
  - On a schedule (e.g., weekly scan of a target county)?
  - Continuous monitoring (always watching for new liens)?

- [ ] **A.4.2** How many liens do you expect to research in a single run?
  - < 10 (deep research on a handful)
  - 10-100 (medium batch)
  - 100-1,000+ (bulk discovery)

- [ ] **A.4.3** What's your budget for API calls / paid data sources?
  - Claude API cost: ~$3-15 per deeply researched parcel
  - Paid data sources: ATTOM ($), PropStream ($), Whitepages Pro ($)
  - Are you open to using paid property data APIs if they save crawling time?

---

### A.5 Technical Preferences

- [ ] **A.5.1** Do you want a web UI (from Archon2.0) or CLI-only?

- [ ] **A.5.2** Should this integrate with Linear (issue tracking per lien found)?

- [ ] **A.5.3** Do you have existing accounts with any of these?
  - ATTOM Data Solutions
  - PropStream
  - CoreLogic
  - BeenVerified / Whitepages Pro
  - PACER (federal court records)

- [ ] **A.5.4** Do you want to store all research data locally (privacy) or is cloud storage OK?

---

## SECTION B: Technical Research Needed

These are things to investigate before or during implementation — not dependent on user answers.

### B.1 Government Data Access

- [ ] **B.1.1** How do county tax collector sites expose lien data?
  - Does the target county have a bulk download (CSV/XML)?
  - Is there a search portal (requires browser automation)?
  - Is there a public API (rare but some counties have them)?
  - Is data behind a CAPTCHA? → Need headless browser + anti-CAPTCHA strategy

- [ ] **B.1.2** Map which counties/states have public bulk lien downloads vs. portal-only access
  - Florida: `dtf.state.fl.us` publishes downloadable delinquent tax lists
  - Texas: County-by-county, most have online portals
  - California: County assessor APIs vary; many use GIS portals
  - Arizona: AZTaxes.gov has some data
  - Need a coverage map for target states

- [ ] **B.1.3** Which counties have open ArcGIS REST APIs for parcel data?
  - Most modern county GIS portals use Esri ArcGIS — can query via REST
  - Endpoint pattern: `https://{county}.gov/arcgis/rest/services/Parcels/MapServer/0/query`
  - Need to test for target counties

- [ ] **B.1.4** Secretary of State APIs by state:
  - Some states have official APIs (e.g., CA BizFile, DE Division of Corporations)
  - Most require scraping their web portals
  - OpenCorporates has aggregated data with API access

- [ ] **B.1.5** UCC search portals by state:
  - Most states have web portals for UCC searches
  - National UCC filing search: `https://www.iaca.org/ucc-central/`

### B.2 Data Parsing Challenges

- [ ] **B.2.1** Legal description parsing
  - Metes and bounds vs. lot/block vs. section-township-range
  - Need NLP model or regex patterns to extract key fields
  - Research: are there existing Python libraries for this?

- [ ] **B.2.2** Owner name normalization
  - "SMITH JOHN" vs "John Smith" vs "SMITH, JOHN R" — need canonical form
  - Entity name matching: "Acme Holdings LLC" vs "ACME HOLDINGS, LLC"
  - Research: fuzzy matching library (RapidFuzz, thefuzz)

- [ ] **B.2.3** Address standardization
  - USPS address normalization API (free for < 500/day)
  - SmartyStreets API (paid, highly accurate)
  - Research: which approach is best for this use case

- [ ] **B.2.4** Handling CAPTCHA on government portals
  - Some county sites use reCAPTCHA v2/v3
  - Options: manual solve, 2captcha API ($), avoid sites with CAPTCHA entirely
  - Research: how common are CAPTCHAs on tax assessor/treasurer sites?

### B.3 Entity Research Methodology

- [ ] **B.3.1** How to pierce LLC ownership efficiently?
  - Step 1: SOS filing → registered agent + manager/member names
  - Step 2: Cross-reference manager name against property records in same county
  - Step 3: Same registered agent = probable common owner (research agent's client list)
  - Step 4: Check registered agent's address for mailbox businesses (Registered Agents Inc., etc.)
  - Step 5: Social media / news search on manager names

- [ ] **B.3.2** Trust ownership research:
  - Living trusts: trustee name often in deed — research trustee
  - Land trusts (IL/FL): designed to obscure ownership — harder
  - Research: are there court records or other sources that reveal trust beneficiaries?

- [ ] **B.3.3** Delaware / Wyoming LLCs:
  - Very minimal public disclosure — only registered agent required
  - Need different strategy: look at state where property is located for that state's registration
  - Research: does the LLC need to register as foreign entity in property state?

### B.4 Social Media Research

- [ ] **B.4.1** LinkedIn automation legality:
  - LinkedIn's ToS prohibits scraping
  - HiQ Labs v. LinkedIn (9th Cir.) — public data scraping may be permissible under CFAA
  - Research: current legal status, safe approach
  - Alternative: LinkedIn Sales Navigator API (paid, requires partnership)

- [ ] **B.4.2** Facebook automation:
  - Similar ToS issues
  - Research: what public data is accessible without login?
  - Public business pages vs. personal profiles — different exposure

- [ ] **B.4.3** Alternative to social media scraping:
  - PeopleDataLabs API (aggregated social + public records data)
  - Clearbit (business data)
  - Hunter.io (email finder for businesses)

### B.5 Legal & Compliance Research

- [ ] **B.5.1** State-by-state rules on automated access to public records:
  - Some states explicitly permit (open records laws)
  - Some states have restrictions on bulk access
  - Research: target states' open records statutes re: automated access

- [ ] **B.5.2** FCRA applicability:
  - If results are used to make decisions about individuals, FCRA may apply
  - Research: does tax lien investing / property research trigger FCRA?

- [ ] **B.5.3** Data broker registration requirements:
  - Vermont requires data broker registration
  - California (CPPA) has evolving requirements
  - Research: does aggregating public records for commercial use require registration?

- [ ] **B.5.4** robots.txt on target government sites:
  - Audit robots.txt for target county/state sites
  - Identify which disallow automated access (must handle accordingly)

### B.6 RAG Architecture Decisions

- [x] **B.6.1** Should we use a knowledge base (crawl-then-query) or live query approach?
  - **Decision:** Hybrid. Live crawl for specific parcel/lien data (always fresh). PostgreSQL+pgvector KB for zoning rules, SOS filings, entity research (crawled, indexed, cached with TTL). DuckDB Parquet snapshots for fast analytics queries across full dataset.

- [ ] **B.6.2** How to handle dynamic government portals (React/Angular search UIs)?
  - Many county portals are JavaScript-heavy search interfaces
  - agent-browser needed for form-fill → results extraction
  - Research: target counties' portal tech stack

- [x] **B.6.3** Document freshness strategy:
  - **Decision:** 3-layer approach (see PRD §9.3):
    1. Socrata/county FTP bulk exports when available (preferred — zero crawl)
    2. Content hash (MD5 of whitespace-normalized HTML) — works on 100% of sites
    3. Structural field hash (status|paid_date|auction_date|amount) for key fields only
  - TTLs: lien status = weekly re-verify; parcel data = 7-day stale threshold; lien discovery = 24h

- [ ] **B.6.4** Handling PDFs:
  - Many county recorders serve deed images as PDFs (scanned)
  - Need PDF OCR pipeline (docling, pytesseract, or Azure Document Intelligence)
  - Research: how common are scanned vs. native PDF deeds in target counties?

### B.7 Scoring & Prioritization

- [x] **B.7.1** What factors should drive opportunity score?
  - **Decision:** All 7 factors incorporated in PRD §9.6 `scores` table:
    - Lien-to-value ratio (principal driver)
    - Years delinquent
    - Property type (vacant land premium)
    - Zoning / development potential
    - Owner motivation (absentee, LLC, dissolved entity, multiple liens)
    - Market appreciation / comps
    - Time to redemption deadline (urgency factor)
    - Contact reachability (can we actually reach the owner?)

- [x] **B.7.2** Should scoring be configurable?
  - **Decision:** Yes — scoring weights stored as configurable parameters. Each factor scored 0-10, combined into overall_score 0-100. Investors can reweight via UI settings panel (Phase 3 feature).

---

## SECTION C: Third-Party APIs to Evaluate

| API | Purpose | Cost Model | Notes |
|-----|---------|-----------|-------|
| ATTOM Data API | Comprehensive property data | Per-request / subscription | Most complete; expensive |
| PropStream | Tax liens, pre-foreclosure | $99/mo subscription | Popular with investors |
| Melissa Data | Address + owner lookup | Per-lookup | Good for address verification |
| OpenCorporates API | Business entity data | Free tier + paid | 55M+ companies |
| PeopleDataLabs | Person/company enrichment | Per-match | Good for owner research |
| SmartyStreets | Address verification | Per-lookup | USPS-certified |
| PACER | Federal court records | $0.10/page | Requires account |
| Hunter.io | Email finder (business owners) | Per-lookup | Good for LLC owners |
| 2captcha | CAPTCHA solving | Per-solve | Only if needed |
| Langfuse | Agent observability | Free tier | Already in stack |

---

## SECTION D: County/State Data Source Mapping (To Be Built)

This table needs to be populated for the target geographic area.

| County/State | Tax Lien Source | Parcel/Assessor Source | GIS Source | SOS Source | Notes |
|--------------|-----------------|----------------------|-----------|-----------|-------|
| [TBD] | [URL] | [URL] | [URL] | [URL] | |

---

## SECTION E: Competitive Research

- [ ] **E.1** How do existing tools handle this? (PropStream, ATTOM, RealtyTrac)
- [ ] **E.2** What do tax lien investors currently do manually that this agent automates?
- [ ] **E.3** Are there existing open-source tax lien scrapers to build on?
  - Check GitHub for county-specific scrapers
  - Check PyPI for property research libraries

---

## SECTION F: Implementation Order (Draft)

Once questions answered, suggested build order:

1. Pick 1 county → manually map all data sources
2. Build Stage 1 (lien discovery) for that county only
3. Build Stage 2 (parcel research) for same county
4. Validate output quality before adding more stages
5. Build Stage 3 (owner research — public records only first)
6. Add entity research (Stage 3 LLC/trust path)
7. Add zoning research (Stage 4)
8. Add scoring and report generation (Stage 5)
9. Generalize to additional counties/states
10. Add social media research (if approved)
11. Add monitoring mode (if needed)
12. Add web UI via Archon2.0 (if needed)

---

## Status Legend
- [ ] Not started
- [~] In progress
- [x] Complete
- [!] Blocked
