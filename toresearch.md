# Tax Lien Researcher — Open Questions & Research Tasks
**Created:** 2026-03-13
**Updated:** 2026-03-15
**Status:** ACTIVE — Section A (user decisions) COMPLETE. Section B (technical research), C (API evaluation), D (data source mapping), and E (competitive research) remain open.

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

### B.8 Outreach & Communication APIs

- [ ] **B.8.1** Twilio account setup and number provisioning:
  - Account creation, A2P 10DLC registration (required for business SMS in US)
  - Local number provisioning strategy: match owner's area code for higher pickup rates?
  - Twilio Lookup API for phone validation (landline vs. mobile — SMS only works on mobile)
  - Pricing: SMS ~$0.0079/msg, Voice ~$0.014/min, number ~$1.15/mo
  - Research: Twilio vs. alternatives (Vonage, Plivo, Telnyx) for cost comparison

- [ ] **B.8.2** SendGrid setup and email deliverability:
  - Domain authentication (SPF, DKIM, DMARC) — critical for avoiding spam folders
  - Dedicated IP vs. shared IP (dedicated = better reputation but requires volume)
  - Template engine: dynamic templates with handlebars-style variables
  - Webhook setup for delivery/open/click/bounce/unsubscribe events
  - Research: SendGrid vs. alternatives (Mailgun, Amazon SES, Postmark) for transactional email

- [ ] **B.8.3** National Do Not Call Registry integration:
  - FTC provides bulk download (updated quarterly) or paid API access
  - Data format: area code + phone number, effective date
  - Must check before EVERY outbound call or SMS
  - Research: is there a real-time API, or must we download and query locally?
  - Internal DNC list management (owners who opt out)

- [ ] **B.8.4** Phone number validation and enrichment:
  - Twilio Lookup API: carrier type (mobile/landline/VoIP), caller name (CNAM)
  - Landline numbers cannot receive SMS — must route to voice-only
  - VoIP numbers: may be less reliable for SMS delivery
  - Research: accuracy of phone type detection, cost per lookup

- [ ] **B.8.5** AI voice agent feasibility (Phase 3):
  - Twilio + Claude API integration for real-time voice conversation
  - Twilio Media Streams (WebSocket) for bidirectional audio
  - Speech-to-text: Twilio built-in vs. Deepgram vs. Whisper
  - Text-to-speech: Twilio built-in vs. ElevenLabs vs. OpenAI TTS
  - Latency budget: must respond within ~1 second for natural conversation
  - Research: current state of AI voice agents, latency achievable, user experience quality

- [ ] **B.8.6** State-specific telemarketing and outreach laws:
  - Some states require telemarketing registration/license
  - Some states have mini-TCPA laws stricter than federal
  - Florida: strict auto-dialer rules, $500/violation
  - California: two-party consent for call recording
  - Texas: specific rules about calls related to property
  - Research: compile a state-by-state compliance matrix for target states

- [ ] **B.8.7** CAN-SPAM vs. legitimate business inquiry:
  - Tax lien outreach may qualify as "transactional/relationship" email (not commercial)
  - If contacting about THEIR property and THEIR lien, it's arguably informational
  - Research: legal opinions on whether tax lien investor outreach is "commercial" under CAN-SPAM
  - Regardless: implement full CAN-SPAM compliance as a safety measure

### B.9 SaaS Infrastructure Research

- [ ] **B.9.1** Multi-tenancy strategy:
  - Row-level security (RLS) in PostgreSQL — all tenants share tables, filtered by user_id
  - Schema-per-tenant — each user gets own schema (simpler isolation, harder management)
  - Database-per-tenant — maximum isolation (only for very large enterprise customers)
  - Research: which approach scales best for 100-10,000 users?

- [ ] **B.9.2** Stripe integration architecture:
  - Subscription lifecycle: create → activate → invoice → renew → cancel
  - Usage metering: how to track parcels researched, outreach messages sent per billing period
  - Webhook handling: payment_succeeded, payment_failed, subscription_updated events
  - Research: Stripe Billing vs. Stripe Checkout vs. both

- [ ] **B.9.3** Rate limiting and fair use per tier:
  - How to enforce batch size limits per tier
  - How to meter and cap API usage (Claude calls, data source lookups)
  - Research: token bucket vs. sliding window vs. fixed window rate limiting

- [ ] **B.9.4** Credential encryption for BYOC:
  - Users store their own Twilio/SendGrid API keys — must be encrypted at rest
  - Options: PostgreSQL pgcrypto, application-level encryption (Fernet), AWS KMS, Vault
  - Research: best practice for storing user API keys in a multi-tenant SaaS

- [ ] **B.9.5** Background job architecture for multi-user:
  - Multiple users running searches simultaneously
  - Need job isolation (one user's crawl doesn't block another's)
  - Research: Celery with per-user queues vs. separate worker pools vs. serverless functions

- [ ] **B.9.6** Cloud deployment cost estimation:
  - PostgreSQL managed (Supabase, Neon, RDS) — cost per GB, connections
  - Compute (app server, worker nodes) — cost per vCPU/hour
  - Storage (property images, screenshots) — S3/R2 cost per GB
  - Research: estimate monthly cost for 100 users, 1,000 users, 10,000 users

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
| **Twilio SMS** | **Send/receive text messages** | **~$0.0079/msg + $1.15/mo per number** | **A2P 10DLC registration required for US business SMS** |
| **Twilio Voice** | **Outbound calls, voicemail drop, call recording** | **~$0.014/min + $1.15/mo per number** | **Click-to-call and AI voice agent modes** |
| **Twilio Lookup** | **Phone number validation (carrier, type, CNAM)** | **~$0.01/lookup** | **Identify landline vs mobile before SMS** |
| **SendGrid** | **Transactional email with template engine** | **Free tier 100/day; $19.95/mo for 50K** | **Domain auth (SPF/DKIM) required for deliverability** |
| **FTC DNC Registry** | **National Do Not Call list** | **Free bulk download / paid API** | **Must check before every outbound call/SMS** |
| **ElevenLabs** | **AI voice synthesis (for AI voice agent Phase 3)** | **Per-character** | **Natural-sounding voice for phone calls** |
| **Deepgram** | **Speech-to-text (for AI voice agent Phase 3)** | **Per-minute** | **Real-time transcription for voice calls** |

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
