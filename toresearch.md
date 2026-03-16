# Tax Lien Researcher — Open Questions & Research Tasks
**Created:** 2026-03-13
**Updated:** 2026-03-15
**Status:** ACTIVE — Section A (user decisions) COMPLETE. Section B (technical research) COMPLETE (B.6.2 and B.6.4 remain open — no research agents assigned). Section C (API evaluation) updated with pricing and new APIs. D (data source mapping) and E (competitive research) remain open.

---

## SECTION A: Questions for the User (Need Answers First)

All user decisions are complete. Proceed to Section B (technical research) for implementation.

### A.1 Scope & Use Case

- [x] **A.1.1** What is the primary goal?
  - **Decision:** V1: Full discovery pipeline (liens + deeds) + deep research + scoring + guided walkthrough of pre-auction offers and auction process. V2: Agent autonomously makes and conducts pre-auction offers and auction bids. This is a **SaaS product** with subscription tiers.

- [x] **A.1.2** What geographic scope do you want to start with?
  - **Decision:** All US states targetable. When user logs in, agent asks where to search. System has built-in knowledge of state lien/deed classification and county data sources.

- [x] **A.1.3** Which state(s) are you targeting first?
  - **Decision:** All states from day one. Agent auto-detects lien vs. deed vs. hybrid per state/county.

- [x] **A.1.4** Are you interested in all property types or specific ones?
  - **Decision:** All property types — residential, commercial, vacant land, industrial, agricultural.

- [x] **A.1.5** Any minimum lien amount threshold?
  - **Decision:** No minimums. Show everything; users filter in the UI.

- [x] **A.1.6** Any minimum property value threshold?
  - **Decision:** No minimums. Show everything; users filter in the UI.

---

### A.2 Output & Delivery

- [x] **A.2.1** What format do you want the output?
  - **Decision:** Both web UI (Archon2.0 card+split view) AND PDF export (on-demand, toggleable inclusion of screenshots). Web is primary working view; PDF for sharing. See PRD §8.1.

- [x] **A.2.2** Where should results be saved?
  - **Decision:** Local PostgreSQL database (this machine). Property images + screenshots stored to local filesystem under `/data/`. DuckDB for analytics queries over the dataset.

- [x] **A.2.3** Do you want alerts when high-value liens are found?
  - **Decision:** Configurable per user in settings panel. Channels (email, SMS, in-app) and score thresholds are user preferences. Available channels scale with subscription tier.

---

### A.6 Owner Outreach & Communication

- [x] **A.6.1** Do you want the agent to contact property owners directly?
  - **Decision:** All channels — email + SMS + phone. Available channels scale with subscription tier (Starter: email; Professional: +SMS; Enterprise: +phone/AI voice).

- [x] **A.6.2** What is the primary purpose of outreach?
  - **Decision:** All purposes: prompt redemption, pre-auction offers, negotiation, and general inquiry. Purpose is selected per outreach action by the user.

- [x] **A.6.3** Do you want fully automated sending (after template approval) or manual approval per contact?
  - **Decision:** User-configurable in settings panel. Options: manual per message, template auto-send, or hybrid. Default: manual. Scales with tier.

- [x] **A.6.4** What email address/domain will outreach come from?
  - **Decision:** All options available: individual email, business email, dedicated domain, or platform pool. Implemented as BYOC (Bring Your Own Credentials) — user provides their own SendGrid API key + domain, or uses Aloha shared infrastructure.

- [x] **A.6.5** Do you have existing accounts with any communication providers?
  - **Decision:** None currently. Platform will support BYOC (user provides own Twilio/SendGrid) or platform-provided pool. Both models available.

- [x] **A.6.6** For phone calls — what mode do you prefer?
  - **Decision:** Both click-to-call and AI voice agent available as user-selectable options. AI voice agent = premium/Enterprise feature.

- [x] **A.6.7** Do you want follow-up sequences?
  - **Decision:** All configurable per user in settings. Options range from single contact to multi-channel sequences (email→SMS→phone). Sequence complexity scales with tier.

- [x] **A.6.8** What score threshold should trigger outreach eligibility?
  - **Decision:** Configurable per user in settings panel. Default: 50. User can set any threshold.

- [x] **A.6.9** Are you operating as an individual or a business entity for outreach purposes?
  - **Decision:** All options available per user — individual, LLC/business, or custom. User selects in settings. CAN-SPAM physical address is a required field.

---

### A.3 Research Depth

- [x] **A.3.1** How deep should owner research go?
  - **Decision:** Level 5 — full intelligence profile. Depth scales with subscription tier: Free/Starter = Level 1-2, Professional = Level 3-4, Enterprise = Level 5.

- [x] **A.3.2** For social media research — which platforms?
  - **Decision:** Tiered approach. V1: public records + SOS filings + court records first, then all social platforms (LinkedIn, Facebook, Instagram, Twitter/X) via browser automation. V2: add paid enrichment APIs (PeopleDataLabs, Hunter.io, Clearbit) for premium tiers.

- [x] **A.3.3** Are you comfortable with social media browser automation (potential ToS risk)?
  - **Decision:** Yes — use browser automation for public profiles. Business entities also fully researchable via all public records.

- [x] **A.3.4** For business entities — how deep on corporate structure?
  - **Decision:** Configurable per subscription tier. Starter: registered agent + officers. Professional: full ownership chain. Enterprise: full chain + related entities + paid enrichment.

---

### A.4 Operations

- [x] **A.4.1** Should the agent run:
  - **Decision:** Determined by subscription tier. Free: on-demand only. Starter: on-demand. Professional: on-demand + weekly scheduled. Enterprise: on-demand + scheduled + continuous monitoring.

- [x] **A.4.2** How many liens do you expect to research in a single run?
  - **Decision:** Scales with target area — could be 50 or 5,000+ depending on county. Batch limits scale with tier: Free ≤50, Starter ≤500, Professional ≤5,000, Enterprise unlimited.

- [x] **A.4.3** What's your budget for API calls / paid data sources?
  - **Decision:** Start with free/public data sources. Add paid sources (ATTOM, PropStream, PeopleDataLabs) when revenue supports it. Paid sources become available as tier add-ons or Enterprise-included features. API costs passed to users via usage-based billing add-ons.

---

### A.5 Technical Preferences

- [x] **A.5.1** Do you want a web UI (from Archon2.0) or CLI-only?
  - **Decision:** Web UI via Archon2.0 framework. This is the primary user-facing interface for the SaaS product.

- [x] **A.5.2** Should this integrate with Linear (issue tracking per lien found)?
  - **Decision:** Yes — Linear integration for internal development project management. Not user-facing.

- [x] **A.5.3** Do you have existing accounts with any of these?
  - **Decision:** None currently — starting from scratch with all data providers.

- [x] **A.5.4** Do you want to store all research data locally (privacy) or is cloud storage OK?
  - **Decision:** Local for development, cloud for production. SaaS model requires cloud deployment for multi-user access.

---

### A.7 SaaS Infrastructure

- [x] **A.7.1** Auth provider preference?
  - **Decision:** V1: Supabase Auth local (Supabase has a self-hosted/local option). Keep everything local for development. Revisit auth provider choice (Supabase cloud vs. Auth0 vs. Clerk) when moving to production cloud deployment.

- [x] **A.7.2** Cloud hosting provider for production?
  - **Decision:** V1: All local (Docker + docker-compose). Production cloud provider TBD — needs cost comparison research (AWS vs. GCP vs. Fly.io vs. Railway) before deploying. See B.9.6.

- [x] **A.7.3** Pricing strategy — what should tiers cost?
  - **Decision:** Decide later. Focus on building V1 locally first. Competitive research needed before setting prices (PropStream $99/mo, BatchLeads, DealMachine, etc.).

- [x] **A.7.4** Do you want a freemium model (free tier forever) or free trial only?
  - **Decision:** Freemium — free tier forever with limited features, no credit card required. Upsell to paid tiers.

- [x] **A.7.5** Domain name for the SaaS product?
  - **Decision:** Not needed yet. V1 is local only. Domain registration happens before cloud deployment.

- [x] **A.7.6** Do you want a marketing/landing page separate from the app?
  - **Decision:** Decide later. Not needed for V1 local development. Plan when going to production.

- [x] **A.7.7** Mobile support — responsive web only or native app later?
  - **Decision:** Responsive web only. Web UI works on mobile browsers — no native app planned.

---

## SECTION B: Technical Research Needed

These are things to investigate before or during implementation — not dependent on user answers.

### B.1 Government Data Access

- [x] **B.1.1** How do county tax collector sites expose lien data?
  - Does the target county have a bulk download (CSV/XML)?
  - Is there a search portal (requires browser automation)?
  - Is there a public API (rare but some counties have them)?
  - Is data behind a CAPTCHA? → Need headless browser + anti-CAPTCHA strategy
  - **Findings:** Bulk CSV/XML downloads are the exception, not the rule. State-level bulk programs exist in TX (Comptroller SIFT portal, quarterly CSV), FL (DOR Data Portal, NAL/SDF/NAP CSV files), and CO (DOR delinquent lists). County-level bulk data available from Allegheny County PA (WPRDC CSV), Mecklenburg County NC, Cuyahoga County OH. The majority of counties use JavaScript-heavy search portals requiring browser automation (Playwright/Selenium) -- Harris County TX, LA County CA, most FL/GA/NJ counties. True public APIs are extremely rare: NYC Open Data (Socrata SODA API at `data.cityofnewyork.us`), Philadelphia, Milwaukee. CAPTCHAs appear on ~20-30% of county tax sites, more common on payment portals than search portals. Many sites rely on rate limiting and IP blocking instead. TaxNetUSA offers a commercial Web API covering 300+ TX/FL counties.

- [x] **B.1.2** Map which counties/states have public bulk lien downloads vs. portal-only access
  - Florida: `dtf.state.fl.us` publishes downloadable delinquent tax lists
  - Texas: County-by-county, most have online portals
  - California: County assessor APIs vary; many use GIS portals
  - Arizona: AZTaxes.gov has some data
  - Need a coverage map for target states
  - **Findings:** **FL:** Best state for bulk data. DOR Data Portal (`floridarevenue.com/property/Pages/DataPortal.aspx`) has statewide assessment roll CSVs. LienHub.com used for county tax certificate sales. Note: `dtf.state.fl.us` is inactive; use `floridarevenue.com`. **TX:** Mixed. Comptroller SIFT portal has quarterly CSV but requires authorization. 254 individual county portals for tax sale listings. **CA:** Portal-only with PDF publications. R&T Code 3371 mandates annual delinquent lists, published as PDFs. No centralized state download; 58 individual counties. **AZ:** `AZTaxes.gov` is for sales/transaction tax, NOT property tax. Portal-only; each of 15 counties runs its own system. **CO:** County treasurers publish downloadable Excel/spreadsheets during sale season. **NJ:** Highly fragmented -- 565 separate municipal portals, no state-level database. **GA:** 159 county portals, no state-level data. **Socrata/data.gov:** NYC Tax Lien Sale Lists, Allegheny County tax liens, Pittsburgh delinquency, Philadelphia RE tax delinquencies, Milwaukee delinquent tax -- all available via SODA API or CSV.

- [x] **B.1.3** Which counties have open ArcGIS REST APIs for parcel data?
  - Most modern county GIS portals use Esri ArcGIS — can query via REST
  - Endpoint pattern: `https://{county}.gov/arcgis/rest/services/Parcels/MapServer/0/query`
  - Need to test for target counties
  - **Findings:** The ArcGIS REST pattern is extremely common. Confirmed working endpoints: Maricopa County AZ (`gis.mcassessor.maricopa.gov`), Cook County IL (`gis.cookcountyil.gov`), Florida DOT statewide parcels, Skagit/Snohomish County WA, Racine County WI, Montgomery County, St. Louis MO, Yolo County CA. Standard query supports `where`, `outFields`, `returnGeometry`, `f=json/geojson`, pagination via `resultRecordCount`/`resultOffset`. Discovery methods: ArcGIS Hub (`hub.arcgis.com/search?q=parcels`) indexes hundreds of county datasets; over half of US states have statewide GIS parcel layers. **Regrid** (`regrid.com`) is the primary nationwide aggregator with 160M+ parcels, 3,229+ counties, 99% US coverage, REST API, and multiple export formats (Shapefile, GeoJSON, CSV, Parquet). Commercial licensing required.

- [x] **B.1.4** Secretary of State APIs by state:
  - Some states have official APIs (e.g., CA BizFile, DE Division of Corporations)
  - Most require scraping their web portals
  - OpenCorporates has aggregated data with API access
  - **Findings:** Only **California** has a true developer API (`calicodev.sos.ca.gov` -- CALICO API, JSON, subscription key required, 17M+ records). Iowa has a subscription JSON API. All other states are web-portal-only requiring scraping: DE (`icis.corp.delaware.gov`, $10-$20/search), FL (Sunbiz), TX, NY, IL, NV. Each state has different auth, schema, field names, and date formats; scraper breakage rates ~10-15%/week. **Third-party aggregators:** Cobalt Intelligence (all 50 states, unified API with CAPTCHA handling -- best for scale), OpenCorporates (145+ jurisdictions, 230M+ records, API v0.4.8, free: 200 req/month; paid from GBP 2,250/yr, capped at 500/month even on paid), Middesk (all 50 states, enterprise pricing).

- [x] **B.1.5** UCC search portals by state:
  - Most states have web portals for UCC searches
  - National UCC filing search: `https://www.iaca.org/ucc-central/`
  - **Findings:** No single national UCC search portal exists. UCC filings are state-level records filed with SOS (or equivalent). NASS maintains a directory at `nass.org/business-services/ucc-filings`. IACA sets form standards at `iaca.org/secured-transactions/forms-2/`. Alogent links all 50 state databases. CA has UCC search via BizFile (`bizfileonline.sos.ca.gov/search/ucc`) and CALICO API. Other states (IL, OH, WA, ME, SC, NY, TX) provide web portals only. Strategy: use direct state portals for targeted searches; Cobalt Intelligence for programmatic access across all states.

### B.2 Data Parsing Challenges

- [x] **B.2.1** Legal description parsing
  - Metes and bounds vs. lot/block vs. section-township-range
  - Need NLP model or regex patterns to extract key fields
  - Research: are there existing Python libraries for this?
  - **Findings:** **PLSS (Section-Township-Range):** `pytrs` v2.1.0 (GitHub only, NOT on PyPI: `pip install git+https://github.com/JamesPImes/pyTRS.git@v2.1.0`). Handles abbreviations, typos, layout variations. Critical caveat: NOT licensed for commercial/for-profit use -- must contact author for commercial license. **Lot/Block:** No library exists. Format is structured enough for regex (e.g., `Lot\s+(\d+)[,\s]+Block\s+([A-Z0-9]+)`). **Metes and Bounds:** No library exists -- hardest type. Requires parsing directional bearings and distances, knowing starting coordinates, distinguishing magnetic vs. true north. Custom regex can extract bearing/distance pairs but cannot resolve to coordinates without a reference point. LLM-based approach (feeding description to Claude) may be the most practical path for low-volume use. GeoPandas community confirms only hand-rolled solutions exist.

- [x] **B.2.2** Owner name normalization
  - "SMITH JOHN" vs "John Smith" vs "SMITH, JOHN R" — need canonical form
  - Entity name matching: "Acme Holdings LLC" vs "ACME HOLDINGS, LLC"
  - Research: fuzzy matching library (RapidFuzz, thefuzz)
  - **Findings:** **Winner: RapidFuzz** (`pip install rapidfuzz`, v3.14.3). 2x faster than thefuzz (~2,500 vs ~1,200 pairs/sec), MIT-licensed (safe for commercial), API-compatible with thefuzz/fuzzywuzzy. thefuzz (v0.22.1) is GPL-2.0 -- license risk for SaaS. jellyfish (v1.1.3) adds phonetic matching (Soundex, Metaphone) but different API. For entity names, fuzzy matching alone is insufficient -- need pre-normalization: uppercase, remove punctuation, normalize suffixes (LLC/INCORPORATED/CORP), collapse whitespace, then compare. For person names, also handle prefix/suffix stripping (Dr., Jr., III) and LASTNAME,FIRSTNAME reordering.

- [x] **B.2.3** Address standardization
  - USPS address normalization API (free for < 500/day)
  - SmartyStreets API (paid, highly accurate)
  - Research: which approach is best for this use case
  - **Findings:** **USPS API v3** (`developers.usps.com`) -- old API shut down Jan 25, 2026. New API is OAuth 2.0/JSON but rate-limited to **60 requests/HOUR** -- effectively useless for any pipeline. The "500/day free" info is outdated. **Smarty** (formerly SmartyStreets, `pip install smartystreets-python-sdk` v5.1.0) -- industry-leading accuracy, USPS-certified, 250 free lookups/month, paid plans scale from there. **usaddress** (`pip install usaddress` v0.5.16) -- open-source CRF-based parser, splits unstructured addresses into labeled components (AddressNumber, StreetName, etc.). Parses well but does NOT validate. **Google Geocoding** -- 10,000 free/month, $5/1K after. **Best strategy:** Use `usaddress` for free offline parsing/normalization, then batch-validate important records via Smarty.

- [x] **B.2.4** Handling CAPTCHA on government portals
  - Some county sites use reCAPTCHA v2/v3
  - Options: manual solve, 2captcha API ($), avoid sites with CAPTCHA entirely
  - Research: how common are CAPTCHAs on tax assessor/treasurer sites?
  - **Findings:** Most county property tax sites do NOT use CAPTCHAs. A meaningful minority use reCAPTCHA v2 (larger counties in CA/TX/FL). Some use reCAPTCHA v3 (invisible). Rate limiting and IP blocking are more common defenses than CAPTCHAs. **2captcha** (`pip install 2captcha-python`): human workers solve CAPTCHAs in 10-30 sec. Pricing: image CAPTCHAs $1/1K, reCAPTCHA v2/v3 $3/1K, min deposit $3. Success rate 96-99% for v2, 90-95% for v3. **playwright-stealth** (`pip install playwright-stealth`): patches Playwright to hide automation fingerprints -- works against basic bot detection, fails against Cloudflare Turnstile. **Recommended tiered strategy:** (1) Target CAPTCHA-free sites first (majority), (2) Playwright stealth for basic bot detection (free), (3) 2captcha for reCAPTCHA v2 sites (~$30 per 10K properties), (4) Skip heavily protected sites and use bulk data alternatives (ATTOM, FOIA requests).

### B.3 Entity Research Methodology

- [x] **B.3.1** How to pierce LLC ownership efficiently?
  - Step 1: SOS filing → registered agent + manager/member names
  - Step 2: Cross-reference manager name against property records in same county
  - Step 3: Same registered agent = probable common owner (research agent's client list)
  - Step 4: Check registered agent's address for mailbox businesses (Registered Agents Inc., etc.)
  - Step 5: Social media / news search on manager names
  - **Findings:** Validated 9-step methodology: (1) SOS filing lookup, (2) check foreign entity registration in property state (often requires more disclosure), (3) cross-reference registered agent (effective ~30-40% of cases -- fails with commercial agents like CT Corporation), (4) registered agent client clustering, (5) annual report/Statement of Information mining (CA LLC-12 requires members), (6) county property records -- mortgage docs often name personal guarantors, (7) UCC filings for personal guarantors, (8) court records via PACER/state courts, (9) web/social search. **Tools:** Cobalt Intelligence (unified API, all 50 states, CAPTCHA handling -- best for scale), OpenCorporates (hierarchy mapping, rate-limited), direct SOS scraping via Playwright for V1. **Critical development:** NY LLC Transparency Act (effective Jan 1, 2026) requires beneficial ownership disclosure for all NY LLCs. FinCEN CTA narrowed to foreign entities only -- domestic BOI no longer required federally.

- [x] **B.3.2** Trust ownership research:
  - Living trusts: trustee name often in deed — research trustee
  - Land trusts (IL/FL): designed to obscure ownership — harder
  - Research: are there court records or other sources that reveal trust beneficiaries?
  - **Findings:** Trust instruments are private documents, NOT filed with any government agency during the trust's lifetime. **Publicly available:** (1) Property deeds show trustee name and trust name/date but NOT beneficiaries, (2) Probate records -- single best source for beneficiary info; wills naming beneficiaries become public when admitted to probate, (3) Court records from trust litigation may contain trust instrument excerpts. **By type:** Revocable living trusts -- research the trustee as an individual. Land trusts (IL 765 ILCS 420, FL 689.071) -- designed to obscure ownership; deed shows trustee (often title company) + trust number only; very difficult to pierce; check UCC filings where beneficial interests may be pledged as collateral. Irrevocable trusts -- separate legal entity with own EIN, similar to living trusts for research. Testamentary trusts -- created by will, fully public upon probate. **No state requires** full trust instrument recording. Some allow optional Memorandum/Certification of Trust (CA Probate Code 18100.5).

- [x] **B.3.3** Delaware / Wyoming LLCs:
  - Very minimal public disclosure — only registered agent required
  - Need different strategy: look at state where property is located for that state's registration
  - Research: does the LLC need to register as foreign entity in property state?
  - **Findings:** **DE:** Articles of Organization require only LLC name, registered agent, and filer name. No members/managers disclosed. Search costs $10-$20. **WY:** Even less disclosure; nominee managers/organizers explicitly permitted. Both are privacy jurisdictions by design. **Foreign entity registration: Almost always yes.** Owning real property = "transacting business" requiring Certificate of Authority in property state. Key insight: the foreign filing in the property state often requires MORE disclosure than the home state. **Piercing strategies:** (1) Always search property state SOS for foreign registration, (2) mortgage/deed guarantor names at county recorder, (3) UCC filings in both states, (4) court records via PACER, (5) county assessor mailing address (often leads to actual owner), (6) Google exact LLC name for permits/licenses/directories, (7) property management trail. Foreign registration fees: WY $150, DE $200, most states $100-$250.

### B.4 Social Media Research

- [x] **B.4.1** LinkedIn automation legality:
  - LinkedIn's ToS prohibits scraping
  - HiQ Labs v. LinkedIn (9th Cir.) — public data scraping may be permissible under CFAA
  - Research: current legal status, safe approach
  - Alternative: LinkedIn Sales Navigator API (paid, requires partnership)
  - **Findings:** hiQ v. LinkedIn concluded: Ninth Circuit (2022) reaffirmed scraping public data does NOT violate CFAA. However, hiQ settled for $500K + data destruction -- LinkedIn won on contract/unfair competition claims. **Practical risk is contractual, not criminal.** LinkedIn actively enforces: Apollo/Seamless.AI banned in 2025; ~23% of browser-automation users face restrictions within 90 days. **Sales Navigator API (SNAP):** exists but NOT accepting new partners as of Aug 2025. Requires Advanced Plus ($1,600+/yr) + partnership approval. **Alternatives:** Proxycurl (~$0.01-0.03/profile, HIGH risk -- active LinkedIn lawsuit), PhantomBuster ($69-$439/mo, MEDIUM risk -- uses your LinkedIn session), Bright Data ($1.5/1K records, LOWER risk -- public data only). **Recommendation:** V1: skip LinkedIn, use PeopleDataLabs/BeenVerified instead. V2: PhantomBuster with conservative rate limits (100 connections/week, 80-150 profile views/day).

- [x] **B.4.2** Facebook automation:
  - Similar ToS issues
  - Research: what public data is accessible without login?
  - Public business pages vs. personal profiles — different exposure
  - **Findings:** Facebook has progressively locked down public access. **Without login:** Public business/fan pages (name, address, phone, hours, posts), public group names/descriptions (not posts), some event pages. **NOT accessible without login:** Personal profiles (even "public" ones now require login), Marketplace, group posts, friends lists. **Graph API:** No person search endpoint exists (post-Cambridge Analytica). Page Public Content Access requires Meta app review. User data requires OAuth consent. Rate limits ~200 calls/hr. **Verdict:** Facebook is effectively unusable for programmatic person research. Business page data has limited value for identifying LLC owners. Do not invest engineering effort in Facebook scraping for person research.

- [x] **B.4.3** Alternative to social media scraping:
  - PeopleDataLabs API (aggregated social + public records data)
  - Clearbit (business data)
  - Hunter.io (email finder for businesses)
  - **Findings:** **PeopleDataLabs** -- Best API option. 10B+ data points, 90%+ accuracy for core data, 85-95% for emails. Free: 100 records/mo; Basic: $99/mo for 1K credits (~$0.28/record). Returns employers, social profiles, emails, phones. HIGH relevance. **Clearbit** -- Now "Breeze Intelligence" under HubSpot. Standalone APIs deprecated. $45-50/mo minimum for 100 credits. Requires HubSpot enterprise for API access. B2B-focused, less useful for individual property owners. Skip for this project. **Hunter.io** -- Email finder. Claims 95% accuracy but independent benchmarks show ~32.5% enrichment rate and 11.2% bounce rate. Free: 50/mo; Starter: $34/mo for 500. MEDIUM relevance. **BeenVerified** (~$27/mo) -- best consumer-grade tool for property owner research, combines property records + contact info + address history. **Pipl** -- enterprise-only, ~$0.10/query, $3K+/yr minimum, ~$58K/yr average. Best quality but cost-prohibitive. **Recommended stack:** Phase 1: free tiers of PDL + Hunter.io. Phase 2: PDL $99/mo + Hunter.io $34/mo + BeenVerified $27/mo.

### B.5 Legal & Compliance Research

- [x] **B.5.1** State-by-state rules on automated access to public records:
  - Some states explicitly permit (open records laws)
  - Some states have restrictions on bulk access
  - Research: target states' open records statutes re: automated access
  - **Findings:** No state explicitly says "automated access is permitted." Access rights derive from state FOIA equivalents which grant access to "any person" without specifying method. The right to records does NOT automatically create a right to bulk electronic data feeds. **Restrictions:** AZ (Sec. 39-121.03) requires commercial purpose disclosure; WA (RCW 42.56.070) prohibits agency-provided "lists of individuals" for commercial purposes; AL requires commercial purpose disclosure if asked. **Critical distinction:** Records are public, but the website is a delivery mechanism with its own access rules (Terms of Use). You have the right to records (via FOIA if needed) but not necessarily the right to scrape the website. **Key statutes:** CA Public Records Act (Gov. Code 7920.000+), FL Sunshine Law (Ch. 119 -- broadest), TX Public Information Act (Gov. Code Ch. 552), NY FOIL (Pub. Off. Law Art. 6). Build a state-by-state compliance matrix for each target state.

- [x] **B.5.2** FCRA applicability:
  - If results are used to make decisions about individuals, FCRA may apply
  - Research: does tax lien investing / property research trigger FCRA?
  - **Findings:** **Generally no, if structured correctly.** Pure property data (parcel ID, assessed value, lien amounts) is NOT subject to FCRA. The trigger is whether information is "used or expected to be used" for credit, insurance, employment, or housing eligibility decisions (15 U.S.C. Sec. 1681a(d)). **Crosses the line:** selling reports linking delinquency data + owner financial profiles to lenders making credit decisions; providing data to landlords for tenant screening. **Stays safe:** property-level investment analysis for lien certificate bidding; facilitating voluntary purchase/sale transactions. **Key safe harbor:** Include ToS prohibiting users from using platform data for FCRA-covered purposes. This establishes you do not "expect" the data to be used for those purposes. **Case law:** Spokeo v. Robins (2016) -- aggregating public records CAN make you a CRA if data bears on creditworthiness and is expected to be used for FCRA purposes. Critical to structure Terms of Service correctly.

- [x] **B.5.3** Data broker registration requirements:
  - Vermont requires data broker registration
  - California (CPPA) has evolving requirements
  - Research: does aggregating public records for commercial use require registration?
  - **Findings:** **Likely yes in multiple states.** If platform collects personal info (owner names, addresses, phones) from public records and makes it available to subscribers, it may meet "data broker" definitions. **Vermont** (9 V.S.A. 2430): $100/yr, Jan 31 deadline, $50/day penalty up to $10K/yr. Government records exemption exists but excludes residential property owner data. **California** (Delete Act SB 362): $6,000/yr, DROP portal live Jan 2026, must process deletion requests within 90 days starting Aug 2026, $200/day penalty. CalPrivacy launched enforcement strike force Nov 2025. **Texas** (SB 2105): $300/yr, applies if >50% revenue from data brokering OR >50K individuals processed. **Oregon** (HB 2052): $500/day penalty up to $10K/yr; government records exemption is broader than other states. **NJ, MN** also advancing legislation. **Budget ~$6,700/yr** for registration fees (CA+VT+TX+OR). Register in CA and VT immediately given active enforcement.

- [x] **B.5.4** robots.txt on target government sites:
  - Audit robots.txt for target county/state sites
  - Identify which disallow automated access (must handle accordingly)
  - **Findings:** **robots.txt is NOT legally binding** -- it is a voluntary protocol, not a contract (no consideration, no meeting of minds). However, it IS evidence in court cases. **Key case law:** Van Buren v. US (2021) narrowed CFAA -- accessing public data does not constitute "exceeding authorized access" even if contrary to ToS/robots.txt. hiQ v. LinkedIn confirmed for public data. But violating robots.txt CAN support breach-of-contract, trespass-to-chattels, or unfair-competition claims. **Best practices:** (1) Respect robots.txt as good faith, (2) use descriptive User-Agent with contact URL (e.g., `TaxLienResearchBot/1.0 (+https://yourco.com/bot-info)`), (3) rate limit: max 1 req/2-5 sec per domain, honor `Crawl-delay`, exponential backoff on 429/503, (4) crawl during off-peak hours (10PM-6AM local), (5) cap at 5K-10K pages/day for small government sites, (6) cache aggressively. Consider formal data-sharing agreements or bulk data purchases -- cleanest legal path.

### B.8 Outreach & Communication APIs

- [x] **B.8.1** Twilio account setup and number provisioning:
  - Account creation, A2P 10DLC registration (required for business SMS in US)
  - Local number provisioning strategy: match owner's area code for higher pickup rates?
  - Twilio Lookup API for phone validation (landline vs. mobile — SMS only works on mobile)
  - Pricing: SMS ~$0.0079/msg, Voice ~$0.014/min, number ~$1.15/mo
  - Research: Twilio vs. alternatives (Vonage, Plivo, Telnyx) for cost comparison
  - **Findings:** **A2P 10DLC:** 2-step registration -- Brand ($4 one-time) + Campaign ($15 one-time + $10/mo). Timeline: 2-4 weeks total. Unvetted trust score = 0.2 msg/sec, 2K/day; secondary vetting ($40) needed for Medium/High throughput. For BYOC, each tenant must complete their own registration -- significant onboarding friction. **Number provisioning:** API supports dynamic search by area_code, locality, region. Local numbers $1.15/mo, toll-free $2.15/mo. **Lookup API v2:** `line_type_intelligence` at $0.03/lookup (90-95% accuracy for mobile vs landline); CNAM at $0.01/lookup. **All-in SMS cost:** ~$0.011-0.013/msg after carrier surcharges ($0.003-0.005). **Competitors:** Telnyx is ~50% cheaper (SMS $0.004, voice $0.007/min) with WebSocket media streams support; Plivo cheapest for raw SMS ($0.005) but weaker streaming. **Recommendation:** Twilio primary (best docs/ecosystem/A2P support), Telnyx as BYOC cost-optimized alternative.

- [x] **B.8.2** SendGrid setup and email deliverability:
  - Domain authentication (SPF, DKIM, DMARC) — critical for avoiding spam folders
  - Dedicated IP vs. shared IP (dedicated = better reputation but requires volume)
  - Template engine: dynamic templates with handlebars-style variables
  - Webhook setup for delivery/open/click/bounce/unsubscribe events
  - Research: SendGrid vs. alternatives (Mailgun, Amazon SES, Postmark) for transactional email
  - **Findings:** **Domain auth:** 3 CNAME records (2 DKIM + 1 SPF) plus DMARC TXT record. Use subdomain (e.g., `notifications.yourdomain.com`) to protect root domain reputation. 15-30 min setup, DNS propagation up to 48 hrs. For BYOC tenants, build a DNS verification wizard. **Dedicated IP:** $20-90/mo, only needed at >100K emails/mo; start with shared IP. **Templates:** Handlebars syntax with `{{variable}}`, `{{#if}}`, `{{#each}}`, nested objects, `{{#equals}}` (SendGrid extension). **Webhooks:** Full event coverage -- processed, delivered, bounce, open, click, spam_report, unsubscribe. Use `unique_args` to route events to correct tenant. **Competitors:** Amazon SES ($0.10/1K) cheapest at scale but worse DX; Mailgun ($0.80/1K) good developer focus; Postmark ($1.25/1K) best deliverability but no bulk/marketing. **Recommendation:** SendGrid Pro (~$89.95/mo for 100K emails), support Mailgun as BYOC alternative.

- [x] **B.8.3** National Do Not Call Registry integration:
  - FTC provides bulk download (updated quarterly) or paid API access
  - Data format: area code + phone number, effective date
  - Must check before EVERY outbound call or SMS
  - Research: is there a real-time API, or must we download and query locally?
  - Internal DNC list management (owners who opt out)
  - **Findings:** **No real-time API** -- bulk download only via `telemarketing.donotcall.gov`. Files are plain text, one 10-digit phone per line, organized by area code. Updated daily (not quarterly as originally noted); must re-scrub lists every 31 days per FTC regs. **Cost: NOT free for commercial use.** 1-5 area codes: $72/each. 6+ area codes: $18,038/yr for nationwide access. Free exemption only for nonprofits or existing business relationships (which you won't have for cold outreach). **Best approach:** Load into PostgreSQL (`COPY` from flat files, VARCHAR(10) PK with B-tree index). ~250M numbers = ~3-4 GB storage. Lookup <1ms per number, batch scrub 10K numbers <100ms via LEFT JOIN. DNC table is shared infrastructure across all tenants (not per-tenant). Build incremental update script for daily downloads. Must also maintain internal DNC list for owners who opt out.

- [x] **B.8.4** Phone number validation and enrichment:
  - Twilio Lookup API: carrier type (mobile/landline/VoIP), caller name (CNAM)
  - Landline numbers cannot receive SMS — must route to voice-only
  - VoIP numbers: may be less reliable for SMS delivery
  - Research: accuracy of phone type detection, cost per lookup
  - **Findings:** Twilio Lookup v2 API (`/v2/PhoneNumbers/{PhoneNumber}`) with `fields="line_type_intelligence"` returns type: mobile, landline, fixedVoip, nonFixedVoip, personal, tollFree, etc. **Accuracy: 90-95%** for mobile vs landline; improved over legacy carrier lookup for ported numbers. **Costs:** line_type_intelligence $0.03/lookup, CNAM $0.01/lookup, basic formatting/validation free. Can combine fields in one call (pay per field). Researching 10K property owners costs ~$300 -- very reasonable. **Routing logic:** mobile -> SMS + voice; landline -> voice only; VoIP -> attempt SMS but deprioritize. Essential for outreach pipeline to avoid sending SMS to landlines (which silently fails).

- [x] **B.8.5** AI voice agent feasibility (Phase 3):
  - Twilio + Claude API integration for real-time voice conversation
  - Twilio Media Streams (WebSocket) for bidirectional audio
  - Speech-to-text: Twilio built-in vs. Deepgram vs. Whisper
  - Text-to-speech: Twilio built-in vs. ElevenLabs vs. OpenAI TTS
  - Latency budget: must respond within ~1 second for natural conversation
  - Research: current state of AI voice agents, latency achievable, user experience quality
  - **Findings:** **Twilio Media Streams:** WebSocket-based bidirectional audio streaming (mulaw 8kHz, 20ms chunks). Architecture: Phone -> Twilio -> WebSocket -> Your Server -> STT -> LLM -> TTS -> WebSocket -> Twilio -> Phone. Custom parameters passed via TwiML `<Stream>` element. **STT comparison:** Deepgram Nova-2 is best for real-time (~100-300ms latency, streaming mode, highest accuracy); Twilio built-in is adequate but less accurate; Whisper is batch-only (~2-5s), not suitable for real-time. **TTS comparison:** ElevenLabs (~300-500ms, most natural voice, $5-99/mo); Deepgram Aura (~200ms, good quality); OpenAI TTS (~300-400ms, good quality). **Achievable total latency: ~700ms** with Deepgram STT + Claude Sonnet (streaming) + Deepgram TTS. **Recommended framework:** Pipecat (open-source pipeline framework for voice AI agents). Budget: ~1 second response is achievable and produces natural conversation quality.

- [x] **B.8.6** State-specific telemarketing and outreach laws:
  - Some states require telemarketing registration/license
  - Some states have mini-TCPA laws stricter than federal
  - Florida: strict auto-dialer rules, $500/violation
  - California: two-party consent for call recording
  - Texas: specific rules about calls related to property
  - Research: compile a state-by-state compliance matrix for target states
  - **Findings:** **32 states + DC** require telemarketing registration. States also requiring surety bonds ($10K-$100K): AZ, CA, DE, FL, KY, ME, NY, OH, OK, PA, TX, UT. **Important TCPA exception:** Recent federal court rulings held that calls to purchase property are NOT "telephone solicitations" under TCPA (property purchase = not promoting services). However, this is unsettled and varies by jurisdiction. **Mini-TCPA states:** FL (FTSA -- strict auto-dialer rules, $500/violation, private right of action), CA (two-party consent for recording), WA (HB 1051 -- expanded restrictions), TX (updated mini-TCPA 2025). **Two-party consent states for call recording (12 states):** CA, CT, DE, FL, IL, MD, MA, MI, MT, NH, OR, PA, WA. **Budget:** Telemarketer registration across all required states = $5K-$25K+ including bond costs. Must implement all-party recording consent disclosure. **Action:** Register in all 32+ states; build state-by-state compliance matrix for telemarketing rules and recording consent requirements.

- [x] **B.8.7** CAN-SPAM vs. legitimate business inquiry:
  - Tax lien outreach may qualify as "transactional/relationship" email (not commercial)
  - If contacting about THEIR property and THEIR lien, it's arguably informational
  - Research: legal opinions on whether tax lien investor outreach is "commercial" under CAN-SPAM
  - Regardless: implement full CAN-SPAM compliance as a safety measure
  - **Findings:** **Tax lien investor outreach is almost certainly "commercial"** under CAN-SPAM (15 U.S.C. 7702). No pre-existing relationship, purpose is to initiate a commercial transaction, property owner did not agree to receive communications. FTC primary-purpose test: an unsolicited email from a tax lien investor reads as promotional. The narrow "transactional" categories are exhaustive and do not include "business inquiries to strangers." No case law specifically on tax lien emails, but real estate investor outreach is consistently treated as commercial. **Penalties: up to $53,088 per violation.** **Mandatory compliance:** (1) Accurate From/To/Reply-To/routing, (2) non-deceptive subject lines, (3) identify as advertisement, (4) include physical postal address, (5) provide opt-out mechanism honored within 10 business days, (6) maintain suppression lists. Also comply with state anti-spam laws (CA, WA, others).

### B.9 SaaS Infrastructure Research

- [x] **B.9.1** Multi-tenancy strategy:
  - Row-level security (RLS) in PostgreSQL — all tenants share tables, filtered by user_id
  - Schema-per-tenant — each user gets own schema (simpler isolation, harder management)
  - Database-per-tenant — maximum isolation (only for very large enterprise customers)
  - Research: which approach scales best for 100-10,000 users?
  - **Findings:** **RLS is the clear winner for 100-10,000 users.** Add `tenant_id` to every table, enable RLS, create policies using session variable (`current_setting('app.current_tenant_id')`) or Supabase `auth.uid()`/JWT claims. **Performance:** With B-tree indexes on `tenant_id`, RLS overhead is <1ms at 500K rows, 1-2ms at 5M rows, 2-5ms at 50M rows. Beyond 50M rows, consider hash partitioning by `tenant_id`. **Critical:** Index `tenant_id` on every table; composite indexes for common queries (e.g., `tenant_id, created_at DESC`). Shared data tables (DNC list) should NOT have tenant-scoped RLS -- use role-based access. Use `FORCE ROW LEVEL SECURITY` if app connects as table owner. Create separate policies for SELECT/INSERT/UPDATE/DELETE. **Supabase integration:** Use `auth.jwt()` claims or helper function `get_tenant_id()` with `SECURITY DEFINER`.

- [x] **B.9.2** Stripe integration architecture:
  - Subscription lifecycle: create → activate → invoice → renew → cancel
  - Usage metering: how to track parcels researched, outreach messages sent per billing period
  - Webhook handling: payment_succeeded, payment_failed, subscription_updated events
  - Research: Stripe Billing vs. Stripe Checkout vs. both
  - **Findings:** **Subscription lifecycle:** 7 states to handle (trialing, active, past_due, canceled, unpaid, incomplete, incomplete_expired). **Usage metering:** Create metered prices with `usage_type="metered"`, `aggregate_usage="sum"`. Report usage via `SubscriptionItem.create_usage_record()`. Best practice: track usage locally in DB first, sync to Stripe hourly/daily via cron (don't call Stripe on every event). **Webhooks:** Must handle `subscription.created/updated/deleted`, `invoice.payment_succeeded/failed`, `subscription.trial_will_end`. Always verify signatures, handle idempotency (deduplicate by event ID), return 200 quickly and process async. **Stripe Checkout vs Billing:** Start with Checkout (hosted payment page, lower complexity, PCI handled by Stripe) + Customer Portal (self-service sub management). Migrate to Billing Elements when needing custom pricing pages or complex proration logic. Use both: Checkout for initial payment, Billing API for metering and lifecycle management.

- [x] **B.9.3** Rate limiting and fair use per tier:
  - How to enforce batch size limits per tier
  - How to meter and cap API usage (Claude calls, data source lookups)
  - Research: token bucket vs. sliding window vs. fixed window rate limiting
  - **Findings:** Enforce via Stripe metered billing combined with application-level enforcement. Track usage per tenant in local DB with `usage_events` table (tenant_id, feature, quantity, timestamp). Sync to Stripe metered prices for billing. For real-time enforcement, use Redis-backed counters per tenant per feature. **Rate limiting algorithms:** Token bucket is best for bursty workloads (allow short bursts, enforce average rate); sliding window is best for smooth enforcement; fixed window is simplest but allows double-rate at window boundaries. **Recommendation:** Token bucket via Redis for real-time enforcement + Stripe usage metering for billing. Check tier limits before executing expensive operations (Claude calls, data source lookups). Return clear error messages with upgrade prompts when limits are hit.

- [x] **B.9.4** Credential encryption for BYOC:
  - Users store their own Twilio/SendGrid API keys — must be encrypted at rest
  - Options: PostgreSQL pgcrypto, application-level encryption (Fernet), AWS KMS, Vault
  - Research: best practice for storing user API keys in a multi-tenant SaaS
  - **Findings:** **Recommendation: Fernet for MVP, Cloud KMS for production.** pgcrypto (DB-level): simplest but encryption key visible in query logs -- avoid for credentials. **Fernet** (app-level, `cryptography` Python package): encrypt/decrypt in application, store ciphertext in DB VARCHAR column, key in env var. Use `MultiFernet` for key rotation -- first key encrypts, all keys decrypt. Store credentials in `tenant_credentials` table (tenant_id, provider, credential_name, encrypted_value) with RLS. **Cloud KMS** (AWS $1/mo/key + $0.03/10K requests): keys never leave HSM, automatic rotation, audit logging. Best security properties for production. **Vault:** highest complexity, overkill unless you have dedicated DevOps. **Key rotation with Fernet:** add new key as first in comma-separated env var; MultiFernet automatically encrypts with new key, decrypts old data with any key; optionally re-encrypt all rows with new key.

- [x] **B.9.5** Background job architecture for multi-user:
  - Multiple users running searches simultaneously
  - Need job isolation (one user's crawl doesn't block another's)
  - Research: Celery with per-user queues vs. separate worker pools vs. serverless functions
  - **Findings:** **Celery with per-user queues is the recommended approach** for this use case. Use Celery + Redis as broker. Create dynamic queues per tenant (e.g., `tenant_{id}_crawl`, `tenant_{id}_research`). Assign workers to queues with concurrency limits per tenant to prevent monopolization. Job isolation: each task carries `tenant_id` metadata, set RLS context at task start, reset on completion. **Alternative: Dramatiq** (simpler than Celery, better Python 3 support, built-in rate limiting per actor). **Serverless (Lambda/Cloud Functions):** Good for burst workloads but cold start latency (1-3s) is problematic for real-time research pipelines; better suited for scheduled batch jobs. **Recommendation:** Start with Celery + Redis for V1. Use priority queues (paid tiers get higher priority). Implement per-tenant concurrency limits. Monitor with Flower (Celery monitoring) or Langfuse for agent observability.

- [x] **B.9.6** Cloud deployment cost estimation:
  - PostgreSQL managed (Supabase, Neon, RDS) — cost per GB, connections
  - Compute (app server, worker nodes) — cost per vCPU/hour
  - Storage (property images, screenshots) — S3/R2 cost per GB
  - Research: estimate monthly cost for 100 users, 1,000 users, 10,000 users
  - **Findings:** **100 users:** Railway/Fly.io $15-30/mo (DB+compute included), Supabase+Vercel $25-50/mo, AWS $65-100/mo. **1,000 users:** Fly.io $70-100/mo (best value), Railway $90-160/mo, Supabase+Vercel $130-180/mo, AWS $200-320/mo. **10,000 users:** Fly.io $500-750/mo, Railway $500-900/mo, Supabase+Vercel $1K-1.5K/mo, AWS $1.2K-1.8K/mo. **By stage:** MVP (0-100): Supabase free/Pro + Railway or Fly.io ($20-50/mo). Growth (100-1K): Supabase Pro + Fly.io ($100-200/mo). Scale (1K-10K): plan AWS migration or scale Fly.io ($500-1.5K/mo). 10K+: AWS/GCP required for scaling primitives and compliance. **Key comparison:** Fly.io = best cost efficiency; Railway = best DX; Supabase = best for built-in RLS/auth/storage; AWS = best at very large scale but worst setup complexity.

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
| OpenCorporates API | Business entity data | Free: 200 req/mo; Paid from GBP 2,250/yr (500/mo cap) | 230M+ records, 145+ jurisdictions. Rate-limited even on paid plans |
| PeopleDataLabs | Person/company enrichment | Free: 100/mo; Basic: $99/mo for 1K credits (~$0.28/record) | 10B+ data points, 90%+ accuracy. Best API for owner enrichment |
| Smarty (SmartyStreets) | Address verification | Free: 250/mo; paid plans scale | USPS-certified. `pip install smartystreets-python-sdk` v5.1.0 |
| PACER | Federal court records | $0.10/page | Requires account. Essential for LLC/trust litigation research |
| Hunter.io | Email finder (business owners) | Free: 50/mo; Starter: $34/mo for 500 | ~32.5% effective enrichment rate per independent benchmarks |
| 2captcha | CAPTCHA solving | Image: $1/1K; reCAPTCHA v2/v3: $3/1K | `pip install 2captcha-python`. 96-99% success rate for v2 |
| Langfuse | Agent observability | Free tier | Already in stack |
| **Twilio SMS** | **Send/receive text messages** | **~$0.0079/msg + carrier surcharges ~$0.003-0.005 = ~$0.011-0.013 all-in** | **A2P 10DLC required: $4 brand + $15+$10/mo campaign. 2-4 week setup** |
| **Twilio Voice** | **Outbound calls, voicemail drop, call recording** | **~$0.014/min + $1.15/mo per number** | **Click-to-call and AI voice agent modes** |
| **Twilio Lookup v2** | **Phone number validation (line type, CNAM)** | **line_type_intelligence: $0.03/lookup; CNAM: $0.01/lookup** | **90-95% accuracy for mobile vs landline. Essential for SMS routing** |
| **SendGrid** | **Transactional email with Handlebars templates** | **Free: 100/day; Pro: ~$89.95/mo for 100K** | **Domain auth (SPF/DKIM/DMARC) required. Dedicated IP $20-90/mo** |
| **FTC DNC Registry** | **National Do Not Call list** | **$72/area code (1-5); $18,038/yr nationwide** | **Bulk download only, no real-time API. ~250M numbers. Re-scrub every 31 days** |
| **ElevenLabs** | **AI voice synthesis (Phase 3)** | **$5-99/mo; per-character** | **~300-500ms latency. Most natural voice quality** |
| **Deepgram** | **STT + TTS (Phase 3)** | **Per-minute** | **Nova-2 STT ~100-300ms; Aura TTS ~200ms. Best for real-time voice agents** |
| **Cobalt Intelligence** | **Unified SOS API across all 50 states** | **Enterprise pricing (contact sales)** | **Real-time scraping with CAPTCHA handling. Best for SOS at scale** |
| **Regrid** | **Nationwide parcel data (160M+ parcels)** | **Commercial licensing; per-county packages** | **REST API, 3,229+ counties, 99% US coverage. GeoJSON/Parquet/CSV** |
| **Telnyx** | **SMS/Voice alternative to Twilio** | **SMS ~$0.004/msg; Voice ~$0.007/min** | **~50% cheaper than Twilio. WebSocket media streams supported** |
| **BeenVerified** | **Property owner research (consumer-grade)** | **~$26.89/mo for up to 100 reports** | **Property records + contact info + address history. Good for manual research** |
| **Stripe** | **Subscription billing + usage metering** | **2.9% + $0.30 per transaction** | **Checkout + Customer Portal for MVP; Billing API for metered usage** |
| **Pipecat** | **Voice AI agent pipeline framework** | **Open-source (free)** | **Orchestrates STT -> LLM -> TTS pipeline. ~700ms total latency achievable** |
| **usaddress** | **Address parsing (offline)** | **Free (open-source)** | **`pip install usaddress` v0.5.16. CRF-based parser. Parse only, no validation** |
| **RapidFuzz** | **Fuzzy string matching** | **Free (MIT license)** | **`pip install rapidfuzz` v3.14.3. 2x faster than thefuzz. Commercial-safe** |
| **TaxNetUSA** | **Assessor + delinquent tax data API** | **Commercial (contact sales)** | **300+ counties in TX/FL. Web API for property tax data** |

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

## SECTION F: Implementation Order (Updated for SaaS)

Build order aligned with PRD §9.2 Phased Rollout and §12 Version Roadmap.

### Phase 1 — MVP (V1.0: Core Pipeline + Auth)
1. **Set up project scaffolding** — Python 3.12+, Pydantic AI, Docker, PostgreSQL, Archon2.0
2. **Build auth system** — user signup/login, OAuth (Google/GitHub), session management
3. **Build state/county knowledge base** — lien vs. deed classification, data source mapping per state
4. **Build agent onboarding flow** — user logs in → agent asks where to search → begins discovery
5. Pick 1 county → manually map and test all data sources
6. Build Stage 1 (lien/deed discovery) — generalized for all states
7. Build Stage 2 (parcel research) — assessor, recorder, GIS
8. Build Stage 3 (owner research — Level 1-2: public records only)
9. Build basic scoring (3-factor model for Free tier)
10. Build web UI — search, results list, parcel detail view, PDF export
11. **Validate pipeline** on 2-3 diverse counties (1 lien state, 1 deed state)
12. **Deploy locally** — docker-compose for development

### Phase 2 — Paying Users (V1.1-V1.2: Deep Research + Outreach + Billing)
13. **Stripe billing integration** — subscription tiers, usage metering, upgrade flows
14. **Tier enforcement** — gate features by subscription level
15. **Per-user settings panel** — alerts, outreach config, thresholds, identity
16. Build Stage 3 deep (Level 3-5: entity piercing, social media, financial health)
17. Add entity research (LLC/trust path — depth per tier)
18. Add zoning research (Stage 4)
19. Expand scoring (7-factor model + configurable weights for Starter+)
20. **Set up outreach infrastructure** — Twilio + SendGrid accounts, DNC registry download
21. **Build email outreach** (Starter+) — templates, SendGrid integration, CAN-SPAM compliance
22. **Build SMS outreach** (Professional+) — Twilio, A2P 10DLC registration, TCPA compliance
23. **Build phone click-to-call** (Enterprise) — Twilio Voice, DNC check, call logging
24. Build configurable alerts — email, SMS, in-app per user settings
25. Add Celery + Redis for distributed job execution

### Phase 3 — Scale + Premium (V1.3-V1.5: Monitoring + Teams + Cloud)
26. **Cloud deployment** — production infrastructure (chosen provider)
27. Build guided auction walkthrough UI — step-by-step flow, checklists, deadline reminders
28. Add scheduled scans (Professional) + continuous monitoring (Enterprise)
29. Add social media research (all platforms, browser automation)
30. Add team/org management (Enterprise) — invites, shared research, roles
31. Add API access (Professional+) — REST API for programmatic access
32. Add PgBouncer connection pooling
33. Add DuckDB analytics sidecar + Parquet snapshots
34. Build outreach campaign dashboard — open/reply/bounce rates

### Phase 4 — V2 Autonomous Actions
35. Build pre-auction offer generation and sending
36. Build auction platform integration (Bid4Assets, Realauction, GovEase)
37. Build automated bidding within user-defined limits
38. Add paid enrichment APIs (PeopleDataLabs, Hunter.io, Clearbit, ATTOM)
39. **Build AI voice agent** — Twilio Media Streams + Claude for phone conversations
40. **Build multi-channel outreach sequences** — email → SMS → phone automation
41. Add advanced analytics and portfolio tracking

---

## Status Legend
- [ ] Not started
- [~] In progress
- [x] Complete
- [!] Blocked
