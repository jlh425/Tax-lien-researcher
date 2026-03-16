# Product Requirements Document: Aloha — Tax Lien Research Agent
**Version:** 0.6
**Date:** 2026-03-15
**Status:** ACTIVE DEVELOPMENT — SaaS platform with tiered subscriptions, multi-state coverage

---

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Use Cases & Goals](#2-use-cases--goals)
3. [Agent Architecture](#3-agent-architecture)
4. [Research Pipeline](#4-research-pipeline)
5. [Data Sources](#5-data-sources)
6. [Feature Requirements](#6-feature-requirements)
7. [RAG Design](#7-rag-design)
8. [Output & Reporting](#8-output--reporting)
9. [Tech Stack](#9-tech-stack)
10. [Security & Legal Considerations](#10-security--legal-considerations)
11. [Subscription Tiers & User Management](#11-subscription-tiers--user-management)
12. [Version Roadmap (V1 / V2)](#12-version-roadmap-v1--v2)
13. [Open Questions](#13-open-questions)

---

## 1. Executive Summary

**Aloha** is a **multi-tier SaaS platform** powered by AI agents that autonomously discovers **tax liens and tax deeds** on land parcels across all US states, performs deep property and owner research, scores investment opportunities, and enables direct owner outreach — all from a web-based interface.

### Product Model

Aloha is a **subscription-based SaaS product** with tiered access. Users log in, select a target geography (any US county/state), and the agent begins discovery and research. Features, research depth, run modes, and outreach capabilities scale with subscription tier. See [Section 11](#11-subscription-tiers--user-management) for full tier breakdown.

### Version Roadmap

| Version | Scope |
|---------|-------|
| **V1** | Full discovery pipeline (liens + deeds, all states) + deep research + scoring + guided walkthrough of pre-auction offers and auction process + owner outreach (email, SMS, phone) |
| **V2** | Agent autonomously makes and conducts pre-auction offers and auction bids on behalf of the user |

### Instrument Coverage

Aloha covers both primary tax-delinquency instruments:
- **Tax Lien Certificates** — government sells the right to collect the debt at auction; investor earns interest during a redemption window and can foreclose if unpaid *(FL, AZ, NJ, CO, IL, IA, and others)*
- **Tax Deeds** — government forecloses and sells the actual property deed at auction after the lien goes unpaid *(TX, GA, MI, MO, MN, WA, OR, and others)*
- **Hybrid states** — some states use both mechanisms depending on the county or circumstance

### Core Capabilities

The agent combines:
- **RAG over government websites** — county tax collector, treasurer, assessor, and recorder sites to find active liens and scheduled deed auctions
- **Owner research (Level 5 full intelligence)** — public records, Secretary of State filings, social media, court records, financial health, and deed history to build complete owner profiles
- **Zoning & land use research** — municipal planning and zoning databases
- **Business entity research** — LLC/trust/corp piercing with depth configurable per subscription tier
- **Instrument-aware scoring** — separate scoring models for lien certificates vs. deed opportunities
- **Owner outreach** — email, SMS/text, and phone calls (click-to-call + AI voice agent) to contact property owners directly
- **All property types** — residential, commercial, vacant land, industrial, agricultural
- **No minimum thresholds** — all liens/deeds discovered; users filter in the UI
- **Configurable alerts** — email, SMS, or in-app notifications per user settings

### Deployment Model

- **Development:** Local (PostgreSQL, Docker, this machine)
- **Production:** Cloud deployment (managed database, CDN, auth provider)
- **User-facing:** Web UI via Archon2.0 framework
- **Internal tracking:** Linear integration for development project management

---

## 2. Use Cases & Goals

### 2.1 Primary Use Case: Tax Delinquency Investment Research

The agent's primary purpose is **investment due diligence** — providing deep, actionable intelligence to evaluate both types of tax delinquency opportunities:

#### Tax Lien Certificate Investing
- Find lien certificates before or at auction
- Evaluate interest rate earned + redemption likelihood
- Assess lien-to-value ratio (safety margin if forced to foreclose)
- Identify owner motivation: are they likely to redeem or walk away?
- Owner reachability is critical — direct outreach can prompt redemption or negotiated purchase
- **Key metric:** Lien-to-value ratio, years delinquent, redemption deadline urgency

#### Tax Deed Investing
- Find properties scheduled for government deed auction (delinquency reached the foreclosure stage)
- Evaluate property value vs. auction starting bid (the government's minimum)
- Assess title risk — tax deed sales can convey title with clouds; title research is critical
- Evaluate property condition (vacant land vs. structure — different rehab/resale thesis)
- Owner research still valuable but secondary — the government is selling the deed, not the owner
- **Key metric:** After Repair Value (ARV) vs. starting bid + estimated rehab + title risk

**All property types included:** residential, commercial, vacant land, industrial, agricultural. No minimum lien amount or property value thresholds — all opportunities are surfaced and users filter in the UI.

**Geographic scope:** All US states targetable. When a user logs in, the agent asks where to start searching. The system has built-in knowledge of how each state handles tax delinquency (lien vs. deed vs. hybrid) and which data sources to query per county. Instrument type is auto-detected from state law and county data.

#### US State Classification (built into Discovery Agent)

| Instrument | Primary States |
|-----------|---------------|
| **Tax Lien Certificate** | FL, AZ, NJ, CO, IL, IA, IN, KY, MD, MS, MO (partial), NE, NY (partial), OH, SC, VT, WY |
| **Tax Deed** | TX, GA, MI, MN, MO (partial), NY (partial), OR, WA, WI, CA, AR, TN, VA, NC |
| **Hybrid** | Some counties within otherwise lien/deed states — Discovery Agent checks county-level |

### 2.2 Agent Goals

#### V1 Goals (Current Scope)
1. **Discovery** — Find parcels with active tax liens OR scheduled deed auctions in a user-selected geographic area (any US state/county)
2. **Instrument classification** — Determine whether the opportunity is a lien certificate or tax deed (drives scoring model)
3. **Owner identification** — Level 5 full intelligence: beneficial owner, contact info, financial health, litigation, relatives (depth scales with subscription tier)
4. **Lien/deed valuation** — Capture amount, years delinquent, redemption deadline (liens) or auction date + starting bid (deeds)
5. **Property characterization** — Zoning, land use, acreage, assessed value, market value estimate, condition
6. **Title chain research** — For tax deeds: full title chain review to identify clouds or competing claims
7. **Entity piercing** — For LLC/trust owners: identify beneficial owner through SOS, deed chains, registered agents (depth configurable per tier)
8. **Risk assessment** — Environmental flags, litigation, title issues, competing liens, condition risk
9. **Market context** — Comparable sales, neighborhood trends, development potential
10. **Instrument-aware scoring** — Lien model (LTV, interest rate, redemption likelihood) or deed model (ARV vs. bid, title clarity, condition)
11. **Owner outreach** — Email, SMS/text, and phone calls (click-to-call + AI voice agent) for direct contact, negotiation, or redemption prompting — all configurable per user
12. **Guided auction walkthrough** — Walk users through the pre-auction offer process and auction bidding process step by step
13. **Configurable alerts** — Email, SMS, or in-app notifications when high-value opportunities are found (thresholds set per user)
14. **Continuous monitoring** — Database maintained by subagent; stale records auto-refreshed on schedule (tier-dependent: on-demand, scheduled, or continuous)

#### V2 Goals (Future Scope)
15. **Autonomous pre-auction offers** — Agent drafts, sends, and negotiates pre-auction purchase offers on behalf of the user
16. **Autonomous auction bidding** — Agent registers for and places bids at online tax deed auctions (Bid4Assets, Realauction, GovEase) per user-defined bid limits
17. **Paid data enrichment** — PeopleDataLabs, Hunter.io, Clearbit, ATTOM API integrations for premium-tier research depth

---

## 3. Agent Architecture

### 3.1 Fluid Pipeline Design Principles

The pipeline is **state-machine-driven**, not sequential. Every parcel record in the database tracks its research stage. The pipeline can:
- Start, stop, and resume at any stage without data loss
- Handle failures at any stage with automatic retry + backoff
- Process new data sources without re-running completed stages
- Work on thousands of parcels concurrently via parallel subagents
- Be interrupted (network down, rate-limited) and resume exactly where it left off

```
PARCEL RESEARCH STATES:
  discovered → parcel_researched → owner_researched → enriched → scored → outreach_ready → complete
       ↑               ↑                 ↑                ↑          ↑
    [retry]         [retry]           [retry]          [retry]    [retry]
       ↓               ↓                 ↓                ↓          ↓
    failed_1       failed_2          failed_3         failed_4   failed_5

INSTRUMENT TYPES (set at discovery, drives scoring model):
  lien_certificate   → scoring: LTV ratio, interest rate, redemption likelihood, owner reachability
  tax_deed           → scoring: ARV vs. starting bid, title clarity, condition risk
  hybrid_pending     → instrument TBD until county data confirms

LIEN/DEED STATUS (separate from parcel research state):
  [Certificate] active → redeemed | sold_at_auction | foreclosed | expired
  [Deed]        scheduled_auction → sold | withdrawn | postponed | no_bid

DATABASE STATES (managed by Refresh Subagent):
  fresh (< 24h) → stale (24h-7d) → expired (> 7d) → needs_recrawl
```

### 3.2 High-Level Flow

```
[Target Location Input]
        │
        ▼
┌──────────────────────────────────────────────┐
│  DATABASE SUBAGENT (always running)          │
│  - Schedules crawl jobs                      │
│  - Marks stale records for refresh           │
│  - Detects lien status changes (paid/active) │
│  - Manages rate limiting per domain          │
└──────────────┬───────────────────────────────┘
               │ writes to / reads from
               ▼
┌──────────────────────────────────────────────┐
│  ALOHA CENTRAL DATABASE (PostgreSQL)         │
│  parcels | liens | owners | entities |       │
│  research_queue | crawl_log | scores         │
└──────────────┬───────────────────────────────┘
               │
       ┌───────┴───────┐
       │               │
       ▼               ▼
┌────────────┐  ┌────────────────────────────────────┐
│  Stage 1   │  │  Parallel Research Workers         │
│  Discovery │  │  (each pulls from research_queue)  │
│  Agent     │  │                                    │
│            │  │  ┌──────────┐  ┌──────────┐        │
│  Discovers │  │  │ Parcel   │  │ Owner    │        │
│  liens →   │  │  │ Research │  │ Research │        │
│  writes to │  │  │ Agent    │  │ Agent    │        │
│  queue     │  │  └──────────┘  └──────────┘        │
└────────────┘  │  ┌──────────┐  ┌──────────┐        │
                │  │ Entity   │  │ Enrichmt │        │
                │  │ Research │  │ Agent    │        │
                │  │ Agent    │  │          │        │
                │  └──────────┘  └──────────┘        │
                └────────────────────────────────────┘
                               │
                               ▼
                    ┌──────────────────┐
                    │  Scoring Agent   │
                    │  + Report Agent  │
                    └──────────────────┘
```

### 3.3 Agent Types

| Agent | Role | Tools | Runs |
|-------|------|-------|------|
| **Database Subagent** | Maintains DB freshness, schedules crawl jobs, detects changes | PostgreSQL, crawl4ai, scheduler | Always (background) |
| **Orchestrator** | Coordinates all stages, pulls from research queue | All | On-demand + scheduled |
| **Lien Discovery Agent** | Crawls county tax/treasurer sites for active liens | crawl4ai, agent-browser | Per target county |
| **Parcel Research Agent** | Extracts parcel details from assessor/recorder/GIS | crawl4ai, ArcGIS API | Per parcel |
| **Owner Research Agent** | Deep owner identification — public records, deed chains | crawl4ai, search APIs | Per parcel |
| **Entity Research Agent** | LLC/trust/corp research — SOS, UCC, related entities | SOS APIs, crawl4ai | Per entity owner |
| **Contact Research Agent** | Find phone, email, social profiles for owners | People APIs, browser | Per owner |
| **Outreach Agent** | Send emails, SMS/text, and initiate phone calls to property owners | Twilio (voice/SMS), SendGrid (email), templates | Per owner (human-approved) |
| **Zoning Research Agent** | Zoning, permits, development potential | GIS APIs, crawl4ai | Per parcel |
| **Enrichment Agent** | Comps, news mentions, litigation, environmental | Zillow, EPA, courts | Per parcel |
| **Scoring Agent** | Ranks liens by investment potential | LLM reasoning | Per parcel |
| **Report Agent** | Compiles findings into structured investment brief | LLM + templates | On-demand |

### 3.4 Orchestration Pattern
- **Queue-driven** — Each parcel is a job in the research queue; agents pull and process
- **Parallel execution** — Owner + Entity + Zoning research run concurrently after parcel data is retrieved
- **State machine** — Each parcel has a research_status; agents only pick up parcels in the right state
- **Idempotent stages** — Re-running a stage updates existing records, never creates duplicates
- **Human-in-the-loop** — Pause for review when beneficial ownership cannot be determined, or lien value exceeds configurable threshold
- **Failure isolation** — One parcel failing doesn't block others; failed parcels retry with exponential backoff

---

## 4. Research Pipeline

### 4.1 Stage 1: Discovery (Liens & Deeds)

The Discovery Agent identifies the target state's instrument type first, then queries the appropriate sources.

#### 4.1a Tax Lien Certificate Discovery

**Target sources (priority order):**
1. County Tax Collector / Treasurer website — delinquent tax list
2. State-level tax delinquency bulk download (FL, AZ, CO publish these)
3. County Tax Assessor website
4. State tax authority delinquency portal
5. Socrata / county open data API (when available — preferred, zero crawl)
6. Third-party aggregators (PropStream, ATTOM) — if API access available

**Data to capture per lien certificate:**
- Parcel ID / APN
- Property address
- Legal description
- Tax year(s) delinquent
- Principal owed, interest, penalties, total owed
- Lien filing date
- Redemption deadline
- Certificate number
- Interest rate on certificate (varies by state — set at auction)
- Auction date (if upcoming)

#### 4.1b Tax Deed Discovery

**Target sources (priority order):**
1. County Tax Collector / Treasurer — upcoming deed sale / auction list
2. County Sheriff's sale list (some states use Sheriff's deeds)
3. State comptroller / land office (TX uses this model)
4. County Clerk / Recorder — lis pendens filings indicating pending tax foreclosure
5. Socrata / county open data API (TX counties publish deed sale lists)

**Data to capture per tax deed listing:**
- Parcel ID / APN
- Property address + legal description
- Auction date and time
- Auction location (courthouse steps, online platform)
- Auction starting bid (minimum bid set by government)
- Opening bid components: back taxes + interest + fees + costs
- Online auction platform (many counties now use Realauction, Bid4Assets, GovEase)
- Redemption period post-sale (some states allow post-sale redemption)
- Any known title encumbrances noted by county

**Online deed auction platforms to monitor:**
| Platform | States/Counties |
|----------|----------------|
| Bid4Assets | TX, GA, WA, OR, and others |
| Realauction | FL (deeds), NJ, and others |
| GovEase | Multiple states |
| SRI Tax | IN, IL, and others |
| County-direct portals | TX county-by-county |

**Crawl strategy (both instruments):**
- Use Socrata / bulk API exports first (zero crawl, highest quality)
- Use crawl4ai for structured government listing pages
- Use agent-browser for JavaScript-heavy portals and online auction platforms
- Cache results with TTL (24-48h)
- Respect robots.txt; throttle requests (1-2 req/sec)

### 4.2 Stage 2: Parcel Research

**Target sources:**
1. County Assessor database (parcel details, assessed value, land use code)
2. County Recorder / Register of Deeds (deed history, title chain)
3. GIS/mapping portals (many counties have public ArcGIS)
4. State GIS data portals

**Data to capture (all instruments):**
- Current owner name(s) of record
- Mailing address of owner
- Property legal description
- Acreage / lot size
- Land use code / property type
- Assessed land value + improvement value
- Year built (if structure exists)
- Last sale date + price
- Deed type (warranty, quitclaim, trust deed)
- Mortgage / deed of trust filings

**Additional data for Tax Deed opportunities:**
- Full title chain (every deed transfer on record — critical for tax deed title risk assessment)
- Any IRS federal tax liens (survive tax deed sale in some states — must check)
- HOA liens (survive or not depending on state — must check)
- Mechanics liens, judgment liens (senior/junior priority relative to tax deed)
- Lis pendens filings (competing foreclosure actions)
- Code enforcement violations, demolition orders
- Estimated condition (vacant/occupied, structure visible in Street View)
- Prior tax deed sales on same parcel (title already has clouds?)

### 4.3 Stage 3: Deep Owner Research

Owner research is the most critical stage for investment purposes — knowing the real owner enables direct outreach, negotiation, and risk assessment. The goal is to identify not just the recorded owner but the **beneficial human** behind any entity, and find a way to contact them.

#### 3a. Individual Owner Research

**Layer 1 — Public Records (fastest, always first):**
- County assessor mailing address (from Stage 2)
- Voter registration records (public in most states)
- Property records cross-reference (same owner, other counties — find pattern of tax delinquency)
- Deed chain history (when did they acquire? at what price? what type of deed?)
- Court records: civil judgments, bankruptcies, foreclosures — PACER + state court portals
- Death records / obituaries (is owner deceased? estate situation?)
- UCC filings (secured debts against the individual)

**Layer 2 — People Research:**
- Whitepages / Spokeo / BeenVerified — phone, address, relatives, associates
- USPS address verification on mailing address
- Reverse address lookup (who else lives there?)
- Reverse phone lookup
- Email finder (Hunter.io, Clearbit Reveal)
- Relative network mapping (family members who may hold related properties)

**Layer 3 — Social & Professional:** *(V1: browser automation on public profiles; V2: paid APIs for enrichment)*

*V1 — Direct platform research (all tiers with social access):*
- LinkedIn — professional history, current employer, connections
- Facebook — local presence, business pages
- Instagram — business/personal presence
- Twitter/X — mentions of property or local real estate activity
- Google search: `"[owner name]" "[city/state]"` news/mentions
- Business affiliations (are they connected to any LLCs/entities?)

*V2 — Paid enrichment APIs (premium tiers):*
- PeopleDataLabs — aggregated social + public records data
- Hunter.io — email finder for businesses and individuals
- Clearbit — company and person enrichment

**Layer 4 — Financial Health:**
- Federal tax liens (IRS public lien search)
- State tax liens
- Judgment liens from court records
- Bankruptcy history (PACER)
- Pattern of delinquency on other properties

#### 3b. Entity Owner Research (LLC / Corporation)

**Layer 1 — Formation Documents:**
- Secretary of State filing: registered agent, organizer, managers/members, officers
- State of formation vs. state where property is located (foreign entity? registered in both?)
- Date of formation, duration, status (active/dissolved/revoked)
- Annual report filings (disclose current managers in many states)

**Layer 2 — Beneficial Owner Identification:**
- Cross-reference manager/member names against assessor records in same county
- Same registered agent = probable common owner (research agent's other clients)
- Registered agent is a professional service (CT Corp, Northwest Registered Agent) → harder, but agent's client list sometimes obtainable
- Related LLCs: same address, same manager, same phone — map the entity network
- OpenCorporates API: find all entities associated with same address or manager name
- Delaware/Wyoming LLCs: minimal disclosure → check state where property is located for foreign registration

**Layer 3 — Financial & Operational:**
- UCC filings: who has security interests in the entity's assets? (reveals lenders and structure)
- Federal tax lien search (IRS) against entity name and EIN
- State tax liens against entity
- Litigation: PACER + state courts — as plaintiff and defendant
- Business news, press releases, LinkedIn company page
- Glassdoor, Indeed reviews (reveals operational status)
- BBB complaints, Yelp, Google Business (is this an active business?)
- Real estate license checks (if owner appears to be a developer/broker)

**Layer 4 — Contact Resolution:**
- Manager name → individual research (Layer 1-3 above)
- Registered office address → Google Maps, street view (real office or mailbox?)
- Phone number from SOS filing, business listings, website
- Email from domain associated with entity (Hunter.io email finder)
- Website: `[entityname].com` — check WHOIS for registrant contact

#### 3c. Trust Owner Research

**Layer 1 — Trust Identification:**
- Trust name in deed (e.g., "Smith Family Living Trust dated 2015")
- Trustee name from deed (often an individual — research as individual above)
- Trust instrument (sometimes recorded at county recorder — search for it)
- Date of trust = approximate age/estate planning timeline

**Layer 2 — Trustee Research:**
- Apply full individual or entity research to the trustee
- Professional trustee (bank/trust company) → contact the trust department
- Successor trustee (named in trust instrument if found)

**Layer 3 — Beneficiary Research:**
- If trustee is deceased: probate records may reveal beneficiaries
- Property transfers out of trust: who received it? (deed chain)
- Court records: trust disputes often filed publicly

#### 3d. Research Confidence Scoring

Every owner research result gets a confidence score:

| Score | Meaning | Criteria |
|-------|---------|---------|
| **High (80-100)** | Highly confident in true owner identity | Individual named in deed + address verified + phone/email confirmed |
| **Medium (50-79)** | Probable owner identified, contact method found | Entity pierced to individual + one contact method found |
| **Low (20-49)** | Owner identified but contact info unconfirmed | Name found, address undeliverable, no phone/email |
| **Unknown (0-19)** | Ownership obscured, could not pierce | DE LLC with professional registered agent, no usable contacts |

### 4.4 Stage 4: Enrichment

**Zoning research:**
- Municipal/county zoning maps (GIS)
- Zoning classification (residential, commercial, agricultural, industrial)
- Overlay districts (historic, etc.)
- Development potential / permitted uses
- Recent variance or permit activity

**Market context:**
- Comparable sales (Zillow, county assessor)
- Estimated market value / ARV
- Days on market for similar properties
- Neighborhood trend (appreciating/depreciating)

**News and legal mentions:**
- Property address in news
- Owner name in litigation
- Business mentions (if entity owner)
- Environmental issues / EPA records

### 4.5 Stage 5: Instrument-Aware Scoring

The Scoring Agent uses different models depending on `instrument_type`.

#### Lien Certificate Scoring Model

| Factor | Weight | Notes |
|--------|--------|-------|
| Lien-to-value ratio | High | Lower % = more collateral protection |
| Years delinquent | Medium | More years = owner more likely disengaged |
| Interest rate on certificate | High | Varies by state; AZ up to 16%, FL up to 18% |
| Redemption deadline urgency | High | Closer deadline = time pressure on owner |
| Owner motivation score | High | Absentee + LLC + multiple liens = motivated seller |
| Contact reachability | Medium | High confidence contact = can negotiate |
| Property type | Medium | Vacant land = simpler foreclosure if unredeemed |
| Title encumbrances | Medium | Competing senior liens reduce net recovery |

**Scoring output:** 0-100 composite score + `lien_certificate` rationale string.

#### Tax Deed Scoring Model

| Factor | Weight | Notes |
|--------|--------|-------|
| ARV vs. opening bid | Very High | Spread = potential profit margin |
| Opening bid / assessed value | High | Government minimums often < market |
| Title clarity | Very High | IRS liens, HOA liens, lis pendens all reduce score |
| Property condition | High | Vacant/structure, estimated rehab need |
| Competing bidder likelihood | Medium | High-value visible properties attract competition |
| Post-sale redemption risk | Medium | Some states allow 1-3 year post-sale redemption |
| Zoning / development potential | Medium | Upside beyond current use |
| Online vs. in-person auction | Low | Online = broader competition; in-person = local only |

**Scoring output:** 0-100 composite score + `tax_deed` rationale string.

### 4.6 Stage 6: Owner Outreach

Once a parcel is scored and owner contact info is confirmed, the **Outreach Agent** can initiate direct contact with property owners. All outreach requires explicit human approval before sending.

#### Outreach Channels

| Channel | Provider | Use Case | Cost |
|---------|----------|----------|------|
| **Email** | SendGrid API | First contact, formal offers, documentation | ~$0.001/email |
| **SMS / Text** | Twilio SMS API | Quick follow-ups, time-sensitive alerts (auction deadlines) | ~$0.0079/msg |
| **Phone Call** | Twilio Voice API | Direct negotiation, warm follow-up after email/SMS | ~$0.014/min |
| **Voicemail Drop** | Twilio Voice API | Leave pre-recorded message if no answer | ~$0.014/min |

#### Outreach Workflow

```
1. Contact Research Agent confirms best_phone, best_email (Stage 3)
2. Scoring Agent scores parcel ≥ configurable threshold (e.g., 60+)
3. Outreach Agent generates personalized message from template
4. → HUMAN APPROVAL GATE ← (review message + recipient before send)
5. Send via selected channel (email, SMS, or phone)
6. Log outcome (delivered, opened, replied, bounced, declined, no_answer)
7. Schedule follow-up if no response (configurable: 3, 7, 14 days)
8. Track all interactions in outreach_log table
```

#### Email Outreach

- **Provider:** SendGrid API (or SMTP fallback)
- **Templates:** Configurable per instrument type (lien vs. deed) and outreach purpose:
  - `lien_redemption_prompt` — "Your property has an outstanding tax lien..."
  - `lien_purchase_offer` — "I'm interested in purchasing the tax lien on your property..."
  - `deed_pre_auction_offer` — "Your property is scheduled for tax deed auction on {date}..."
  - `general_inquiry` — "I'm researching properties in {county} and would like to discuss..."
  - `follow_up` — "Following up on my previous message regarding {address}..."
- **Personalization fields:** owner name, property address, lien amount, deadline/auction date, parcel ID
- **Compliance:** CAN-SPAM compliant (unsubscribe link, physical address, honest subject lines)
- **Tracking:** Open tracking, click tracking, bounce handling, unsubscribe management

#### SMS / Text Outreach

- **Provider:** Twilio Messaging API
- **Number type:** Local number matching owner's area code (when possible) for higher response rates
- **Templates:** Short, compliant messages (160 char optimal):
  - "Hi {name}, I'm reaching out about {address} in {county}. There's an outstanding tax matter I'd like to discuss. Reply STOP to opt out."
- **Compliance:** TCPA compliant — prior express consent required for marketing; informational messages have more flexibility
- **Opt-out:** Automatic STOP keyword handling (Twilio built-in)
- **Rate limits:** Max 1 SMS per owner per 7 days (configurable)

#### Phone Call Outreach

- **Provider:** Twilio Voice API
- **Modes:**
  1. **Click-to-call** — Agent dials owner, connects to your phone when answered (you speak live)
  2. **Voicemail drop** — If no answer, leave a pre-recorded voicemail via Twilio
  3. **AI-assisted call** (Phase 3) — Claude-powered voice agent handles initial conversation, escalates to human for negotiation
- **Compliance:** TCPA and Do Not Call (DNC) registry compliance required
  - Check owner's number against National DNC Registry before calling
  - No calls before 8am or after 9pm local time (owner's timezone)
  - No robocalling without prior express written consent
- **Call logging:** Record call outcome (answered, voicemail, no_answer, wrong_number, declined), duration, notes

#### Outreach Rules & Safety

- **Human-in-the-loop:** ALL outreach requires explicit user approval before first contact with any owner
- **Frequency caps:** Max contacts per owner per channel per time period (configurable, default: email 1/week, SMS 1/week, phone 1/2 weeks)
- **Do Not Contact list:** Maintain internal DNC list — owners who opt out are permanently excluded
- **Compliance checks:** Agent validates CAN-SPAM, TCPA, and state-specific telemarketing rules before any outreach
- **Audit trail:** Every outreach attempt logged with timestamp, channel, template used, message content, and outcome

#### Score Display in UI

```
[LIEN CERT]  Score: 72/100  •  LTV: 4.6%  •  Rate: 18%  •  Deadline: 9mo
[TAX DEED ]  Score: 85/100  •  ARV: $310K  •  Bid: $42K  •  Title: Clear
```

---

## 5. Data Sources

### 5.1 Official Government Sources (Highest Priority)

| Source Type | Access Method | Data Available |
|-------------|---------------|----------------|
| County Tax Collector/Treasurer | Web crawl + some have APIs | Active liens, delinquency lists, deed auction schedules |
| County Assessor | Web crawl + ArcGIS REST APIs | Parcel data, ownership, assessed value |
| County Recorder/Clerk | Web crawl | Deed history, title chain, mortgage filings |
| State Revenue/Tax Dept | Web crawl | State tax liens (separate from property tax) |
| Secretary of State | Web crawl + some APIs | Entity registration, officers, registered agent |
| State UCC Filing Office | Web crawl | Secured party liens on personal property |
| County GIS Portal | ArcGIS REST API | Parcel boundaries, zoning, land use |
| Municipal Planning Dept | Web crawl | Zoning codes, permits, variances |
| PACER (Federal Courts) | API ($0.10/page) | Federal tax liens (IRS), federal litigation |
| State Court Portals | Web crawl | Civil/criminal filings, lis pendens |
| **Bid4Assets** | Web crawl + API | Tax deed auction listings (TX, GA, WA, OR) |
| **Realauction** | Web crawl | Tax deed/lien auctions (FL deeds, NJ, others) |
| **GovEase** | Web crawl | Tax deed auction listings (multiple states) |
| **SRI Tax** | Web crawl | Tax lien/deed auctions (IN, IL, and others) |

### 5.2 Semi-Official / Aggregator Sources

| Source | Data | Notes |
|--------|------|-------|
| Zillow / Realtor.com | Market value estimates, sale history | Secondary verification |
| ATTOM Data | Comprehensive property data | **Paid API — TBD if available** |
| PropStream | Tax liens, pre-foreclosure | **Paid — TBD** |
| FEMA Flood Map | Flood zone designation | Free |
| EPA ECHO | Environmental compliance | Free API |
| OpenCorporates | Business entity data | Free tier + paid |

### 5.3 Social Media Sources

| Platform | Use Case | Method |
|----------|----------|--------|
| LinkedIn | Business owner identity, company info | Browser automation (no official API for scraping) |
| Facebook | Personal owner research, local business pages | Browser automation |
| Instagram | Business owner research | Browser automation |
| Twitter/X | Mentions of owner or property | API (paid) or browser |

> **⚠️ Legal note:** Social media scraping may violate ToS. See Section 10.

### 5.4 Public Records Aggregators

| Source | Data | Cost |
|--------|------|------|
| Whitepages Pro | Phone, address, relatives | Paid API |
| BeenVerified | Background, associates | Paid |
| Spokeo | Contact info, social profiles | Paid |
| TruthFinder | Background data | Paid |
| Melissa Data | Address verification, owner lookup | Paid API |

> **⚠️ TBD:** Budget for paid data sources not yet determined. See `toresearch.md`.

---

## 6. Feature Requirements

### 6.1 Core Features (Must-Have)

| Feature | Description | Priority | Tier |
|---------|-------------|----------|------|
| **User authentication** | OAuth + email/password login, session management | P0 | All |
| **Location-based search** | Agent asks user where to search; input: county + state (or ZIP); discover all liens/deeds | P0 | All |
| **State/county auto-detection** | Agent knows which states are lien vs. deed vs. hybrid; auto-selects data sources per county | P0 | All |
| **Parcel data extraction** | Extract APN, address, owner, assessed value, legal description | P0 | All |
| **Lien data extraction** | Capture amount, year, deadline, certificate number | P0 | All |
| **Owner identification** | Identify individual or entity owner from public records (depth per tier) | P0 | All (depth varies) |
| **Entity piercing** | For LLC/trust owners: find beneficial owner via SOS and related filings | P0 | Starter+ |
| **Zoning lookup** | Retrieve zoning classification and permitted uses per parcel | P1 | Professional+ |
| **Structured report** | Output per-parcel research report in web UI and exportable PDF | P0 | All |
| **Source citation** | Every data point includes its source URL and retrieval date | P0 | All |
| **Rate limiting / politeness** | Throttle crawl requests; respect government site limits | P0 | All |
| **Progress persistence** | Save state so research can resume after interruption | P1 | All |
| **Email outreach** | Send templated emails to property owners via SendGrid API | P1 | Starter+ |
| **SMS/text outreach** | Send text messages to owners via Twilio SMS API | P1 | Professional+ |
| **Phone call outreach** | Click-to-call and voicemail drop via Twilio Voice API | P2 | Enterprise |
| **Outreach approval gate** | Configurable: manual per-message, template auto-send, or hybrid | P0 | Starter+ |
| **Do Not Contact list** | Track opt-outs and ensure no re-contact across all channels | P0 | All |
| **Subscription billing** | Stripe integration: plans, usage metering, upgrade prompts | P0 | All |
| **Per-user settings** | Configurable alerts, outreach rules, thresholds, identity | P0 | All |
| **Guided auction walkthrough** | Step-by-step guides for pre-auction offers and auction bidding process | P1 | All |

### 6.2 Advanced Features (Nice-to-Have)

| Feature | Description | Priority | Tier |
|---------|-------------|----------|------|
| **Opportunity scoring** | Score each lien by investment potential (configurable weights) | P1 | Starter+ |
| **Social media owner research** | LinkedIn/Facebook/Instagram/Twitter search for owner identity and contact | P2 | Professional+ |
| **Paid enrichment APIs** | PeopleDataLabs, Hunter.io, Clearbit for premium owner data | P2 | Enterprise (V2) |
| **Comparable sales** | Pull recent comparable sales for market context | P2 | Professional+ |
| **Monitoring mode** | Continuously monitor for new liens in a target area | P2 | Enterprise |
| **Configurable alerts** | Email, SMS, in-app notifications — channels and thresholds per user settings | P2 | Starter+ (channels vary) |
| **Bulk processing** | Research hundreds/thousands of parcels in a single run | P1 | Starter+ (limits vary) |
| **Deduplication** | Avoid re-researching already-known parcels | P1 | All |
| **News mentions** | Search news for owner or property mentions | P2 | Professional+ |
| **Environmental flags** | Flag parcels with EPA records or brownfield status | P2 | Professional+ |
| **Litigation research** | Check court records for lawsuits against owner | P2 | Professional+ |
| **Multi-county search** | Expand search across multiple counties in one run | P2 | Starter+ (count varies) |
| **AI voice agent** | Claude-powered voice agent for initial owner conversations | P3 | Enterprise (V2) |
| **Outreach campaign tracking** | Dashboard showing open/reply/bounce rates across all contacts | P2 | Professional+ |
| **Follow-up automation** | Auto-schedule follow-ups if no response within configurable window | P2 | Professional+ |
| **Multi-channel sequences** | Automated outreach sequences (email → SMS → call) with configurable delays | P3 | Enterprise |
| **Autonomous offers (V2)** | Agent drafts and sends pre-auction purchase offers on user's behalf | P3 | Enterprise (V2) |
| **Autonomous auction bidding (V2)** | Agent registers and bids at online tax deed auctions per user limits | P3 | Enterprise (V2) |
| **Team / org management** | Invite members, share research, assign roles | P2 | Enterprise |
| **API access** | REST API for programmatic access to research data | P2 | Professional+ |

---

## 7. RAG Design

### 7.1 Knowledge Base Structure

```
tax-lien-kb/
├── government-sites/
│   ├── {county}-{state}/
│   │   ├── tax-collector/      # Crawled lien data
│   │   ├── assessor/           # Parcel data
│   │   ├── recorder/           # Deed records
│   │   └── gis/                # Zoning/parcel maps
├── entity-research/
│   ├── sos-filings/            # Secretary of State records
│   └── ucc-filings/            # UCC liens
├── owner-research/
│   ├── public-records/
│   └── social-media-summaries/ # Summarized findings (not raw scrapes)
└── market-data/
    └── comps/                  # Comparable sales data
```

### 7.2 Chunking Strategy

| Document Type | Chunk Strategy | Chunk Size |
|---------------|---------------|------------|
| Tax lien listings | Per lien record | ~200 tokens |
| Parcel data pages | Per field group (owner, value, description) | ~300 tokens |
| Deed documents | Per grantor/grantee transaction | ~400 tokens |
| SOS filings | Per filing/entity | ~300 tokens |
| Zoning codes | Per zone definition | ~500 tokens |
| News articles | Sliding window | ~400 tokens, 50 overlap |

### 7.3 Embedding & Vector Search

```
Embedding model:  text-embedding-3-small (local via Ollama or OpenAI)
Vector store:     PostgreSQL + pgvector
Index:            HNSW (fast approximate nearest neighbor)
Retrieval:        Top-k = 5-10 chunks per query
Re-ranking:       Cross-encoder re-rank for precision-critical lookups
```

### 7.4 Query Types

| Query | Strategy |
|-------|---------|
| "Find all liens in {county} with amount > $5,000" | Structured filter + vector search |
| "Who owns parcel {APN}?" | Direct lookup + vector fallback |
| "What is the zoning for this address?" | Vector search + GIS API |
| "What entities is {owner name} associated with?" | Graph traversal + vector search |

---

## 8. Output & Reporting

### 8.1 Delivery Formats

Every fully-researched parcel produces two output artifacts:

| Format | Purpose | When |
|--------|---------|------|
| **Web report** (Archon2.0 UI) | Live working view — images inline, citations clickable, data refreshable | Always generated |
| **PDF export** | Shareable report — images embedded, citations listed, printable | On-demand (toggle per parcel or batch) |

The PDF mirrors the web report but excludes live interactive elements (map embeds become static images, links become footnoted URLs).

---

### 8.2 Property Imagery Pipeline

Every parcel report includes visual evidence captured by the **Image Capture Agent** in this priority order:

#### Priority 1 — GIS Parcel Map (always attempted first)
- **Source:** County ArcGIS portal export endpoint or Regrid API
- **What it shows:** Exact parcel boundaries, neighboring lots, zoning overlay (color-coded by zone), street names
- **Method:** ArcGIS REST `exportImage` endpoint (most counties support this):
  ```
  GET https://{county}.gov/arcgis/rest/services/Parcels/MapServer/export
      ?bbox={parcel_bbox}
      &layers=show:0,1,2          (parcels + zoning layers)
      &size=800,600
      &f=image
  ```
- **Fallback:** Playwright screenshot of the county's online GIS viewer

#### Priority 2 — Google Street View
- **Source:** Google Street View Static API
- **What it shows:** Ground-level photo of the structure (or nearest road point for vacant land)
- **Method:**
  ```
  GET https://maps.googleapis.com/maps/api/streetview
      ?size=800x500
      &location={address}
      &heading=auto
      &fov=90
      &key={GOOGLE_MAPS_API_KEY}
  ```
- **Fallback:** Bing Maps Street View (same concept, different API)
- **Vacant land handling:** If Street View returns a "no imagery" response, skip gracefully and note in report

#### Priority 3 — Satellite / Aerial
- **Source:** Google Maps Static API (`maptype=satellite`)
- **What it shows:** Overhead view — structure footprint, lot size, surrounding context
- **Method:**
  ```
  GET https://maps.googleapis.com/maps/api/staticmap
      ?center={lat},{lng}
      &zoom=18
      &size=800x500
      &maptype=satellite
      &key={GOOGLE_MAPS_API_KEY}
  ```

#### Priority 4 — Zillow / Listing Photos (when available)
- **Source:** Zillow property page (crawl4ai or agent-browser)
- **What it shows:** Listing photos from most recent sale (exterior, interior if captured)
- **Method:** Crawl Zillow property page by address → extract primary listing photo URL(s)
- **Note:** Only available for properties that have been listed on Zillow. Vacant land rarely has listing photos. Store up to 3 photos.
- **Legal:** Zillow photos are scraping-gray-area. Store URL references; fetch image on display (don't bulk-store Zillow images locally).

#### Image Storage
```
/data/property-images/
  {parcel_id}/
    gis_parcel_map.png          # ArcGIS or GIS viewer screenshot
    street_view.jpg             # Google Street View
    satellite.jpg               # Google satellite
    zillow_1.jpg                # Zillow listing photos (when available)
    zillow_2.jpg
    zillow_3.jpg
```

---

### 8.3 Evidence & Citation Model

Every data point in the report has a citation. Citations are stored as structured objects, not just URLs.

#### Citation structure (per data point)
```json
{
  "source_type": "tax_collector",
  "source_name": "Orange County Tax Collector",
  "url": "https://octaxcol.com/taxbills/parcel/123-456-789",
  "retrieved_at": "2026-03-13T14:22:00Z",
  "screenshot_path": "/data/screenshots/123-456-789/tax_collector_20260313.png",
  "screenshot_crop": {"x": 120, "y": 340, "w": 680, "h": 210},
  "data_extracted": ["lien_amount", "tax_year", "redemption_deadline"]
}
```

#### Screenshot behavior
- **Agent captures:** Full-page Playwright screenshot of every source page at time of data extraction
- **Stored locally:** Full PNG at `/data/screenshots/{parcel_id}/{source_type}_{date}.png`
- **UI shows:** Cropped region (`screenshot_crop` bounding box) highlighting the relevant data
- **Mouseover / click:** Expands to full-page screenshot in a modal overlay
- **In PDF export:** Cropped screenshot embedded inline next to the cited data (toggleable — default ON for personal use, optional for shareable reports)

#### Source types and their screenshots
| Source Type | What gets screenshotted |
|-------------|------------------------|
| `tax_collector` | Page showing lien amount, year, deadline |
| `assessor` | Parcel detail page with owner and assessed value |
| `recorder` | Deed entry showing grantor/grantee and date |
| `sos` | Secretary of State entity filing page |
| `court` | Case summary page (if litigation found) |
| `gis` | GIS portal map view of the parcel |
| `zillow` | Property listing page (if present) |

---

### 8.4 Per-Parcel Report Schema (updated)

```json
{
  "parcel_id": "123-456-789",
  "address": "123 Main St, Anytown, CA 90210",
  "coordinates": {"lat": 33.7490, "lng": -117.8678},

  "images": {
    "gis_parcel_map": "/data/property-images/123-456-789/gis_parcel_map.png",
    "street_view": "/data/property-images/123-456-789/street_view.jpg",
    "satellite": "/data/property-images/123-456-789/satellite.jpg",
    "zillow": ["/data/property-images/123-456-789/zillow_1.jpg"],
    "captured_at": "2026-03-13T14:22:00Z"
  },

  "lien": {
    "amount": 12500.00,
    "years_delinquent": 3,
    "interest_penalties": 1875.00,
    "total_owed": 14375.00,
    "filing_date": "2023-01-15",
    "redemption_deadline": "2026-01-15",
    "certificate_number": "2023-001234",
    "citation": {
      "url": "https://octaxcol.com/taxbills/parcel/123-456-789",
      "screenshot_path": "/data/screenshots/123-456-789/tax_collector_20260313.png",
      "screenshot_crop": {"x": 120, "y": 340, "w": 680, "h": 210},
      "retrieved_at": "2026-03-13T14:22:00Z"
    }
  },

  "property": {
    "legal_description": "Lot 5, Block 3, Sunset Subdivision",
    "acreage": 0.25,
    "land_use": "Single Family Residential",
    "zoning": "R-1",
    "zoning_notes": "Min lot size 6,000 sqft. Max height 35ft.",
    "assessed_value": 185000,
    "estimated_market_value": 310000,
    "last_sale_date": "2018-06-01",
    "last_sale_price": 220000,
    "citation": {
      "url": "https://assessor.ocgov.com/parcel/123-456-789",
      "screenshot_path": "/data/screenshots/123-456-789/assessor_20260313.png",
      "screenshot_crop": {"x": 0, "y": 200, "w": 900, "h": 400},
      "retrieved_at": "2026-03-13T14:25:00Z"
    }
  },

  "owner": {
    "owner_of_record": "Acme Holdings LLC",
    "owner_type": "entity",
    "entity": {
      "type": "LLC",
      "state_of_formation": "DE",
      "registered_in_state": "CA",
      "registered_agent": "National Registered Agents Inc.",
      "officers": ["John Smith (Manager)"],
      "sos_filing_url": "https://bizfile.sos.ca.gov/...",
      "status": "Active",
      "formation_date": "2015-03-22",
      "citation": {
        "url": "https://bizfile.sos.ca.gov/...",
        "screenshot_path": "/data/screenshots/123-456-789/sos_20260313.png",
        "screenshot_crop": {"x": 0, "y": 100, "w": 800, "h": 350},
        "retrieved_at": "2026-03-13T14:30:00Z"
      }
    },
    "beneficial_owner_research": {
      "probable_owner": "John Smith",
      "confidence": "medium",
      "evidence": [
        {"fact": "SOS filing lists John Smith as Manager", "citation_index": 2},
        {"fact": "LinkedIn: John Smith lists Acme Holdings on profile", "citation_index": 4}
      ],
      "contact_info": {
        "phone": "TBD",
        "email": "TBD",
        "mailing_address": "456 Oak Ave, Beverly Hills, CA 90210"
      }
    }
  },

  "outreach": {
    "status": "pending",
    "contacts_attempted": 0,
    "last_contact_date": null,
    "last_channel": null,
    "owner_response": null,
    "do_not_contact": false,
    "history": []
  },

  "opportunity_score": 72,
  "score_rationale": "High lien-to-value ratio (4.6%). 3 years delinquent. LLC owner with obscured beneficial ownership. Zoning allows development.",
  "flags": ["Owner entity delinquent", "No active mortgage found", "Possible absentee owner"],

  "all_citations": [
    {
      "index": 1,
      "source_type": "tax_collector",
      "source_name": "Orange County Tax Collector",
      "url": "https://octaxcol.com/taxbills/parcel/123-456-789",
      "screenshot_path": "/data/screenshots/123-456-789/tax_collector_20260313.png",
      "retrieved_at": "2026-03-13T14:22:00Z"
    },
    {
      "index": 2,
      "source_type": "sos",
      "source_name": "California Secretary of State BizFile",
      "url": "https://bizfile.sos.ca.gov/...",
      "screenshot_path": "/data/screenshots/123-456-789/sos_20260313.png",
      "retrieved_at": "2026-03-13T14:30:00Z"
    }
  ]
}
```

---

### 8.5 Summary Report (batch run)

```markdown
# Tax Lien Research Report
**Location:** {County}, {State}
**Run Date:** {date}
**Total Liens Found:** {n}
**Liens Fully Researched:** {n}
**High-Priority Opportunities:** {n}

## Top 10 Opportunities
| Rank | Address | Lien Amount | Owner | Score | Notes |
|------|---------|-------------|-------|-------|-------|
| 1    | ...     | $14,375     | LLC   | 72    | ...   |
...

## Research Gaps
- {n} parcels where owner could not be identified
- {n} parcels where zoning data was unavailable
```

---

## 9. Tech Stack

### 9.1 Core Stack

```
Agent Name:       Aloha
Language:         Python 3.12+
Agent Framework:  Pydantic AI (type-safe tools) + Claude Agent SDK (multi-agent coordination)
LLM:              Claude Sonnet 4.6 (deep research/reasoning), Haiku 4.5 (fast structured lookups)
Web Crawling:     crawl4ai (structured sites) + agent-browser (JS-heavy portals, forms)
Screenshots:      Playwright (full-page capture of every source page at extraction time)
Primary DB:       PostgreSQL 16 + pgvector (parcels, liens, owners, research state, embeddings)
Analytical Layer: DuckDB sidecar — queries Parquet snapshots exported from PostgreSQL
Job Queue:        Phase 1: PostgreSQL SKIP LOCKED (built-in, no extra infra)
                  Phase 2: Celery + Redis (added when scheduling UI and rate-limit features needed)
ORM:              SQLAlchemy 2.0 async (Python backend)
MCP Servers:      Custom MCP for county assessor APIs, SOS APIs, GIS/ArcGIS
Observability:    Langfuse (trace all agent steps, token costs per parcel)
Containerization: Docker + docker-compose
UI:               Archon2.0 framework (React + TanStack Query + FastAPI)
Scheduler:        APScheduler (Python) for database subagent cron jobs
Connection Pool:  Phase 3: PgBouncer (added at 100K+ parcels for connection scaling)
PDF Export:       WeasyPrint (Python, HTML→PDF with embedded images)

--- Imagery APIs ---
GIS Parcel Maps:  County ArcGIS REST exportImage endpoint (primary)
                  Playwright screenshot of county GIS viewer (fallback)
Street View:      Google Street View Static API ($7/1K requests)
Satellite:        Google Maps Static API — maptype=satellite ($2/1K requests)
Listing Photos:   Zillow crawl via crawl4ai (URL reference only; fetch on display)
Geocoding:        Google Geocoding API (address → lat/lng for all image requests)

--- Outreach / Communication ---
Email:            SendGrid API (transactional + template engine, CAN-SPAM compliant)
SMS/Text:         Twilio Messaging API (SMS, local number provisioning, STOP handling)
Voice/Phone:      Twilio Voice API (click-to-call, voicemail drop, call recording)
DNC Registry:     FTC DNC API or data.gov bulk download (National Do Not Call Registry)
Phone Validation: Twilio Lookup API (carrier type, line type, caller name)
Templates:        Jinja2 (Python template engine for personalized messages)

--- SaaS Infrastructure ---
Auth:             Supabase Auth or Auth0 (OAuth 2.0 + email/password)
Payments:         Stripe (subscriptions + usage-based billing)
User DB:          PostgreSQL (same cluster, separate schema or RLS)
Multi-tenancy:    Row-level security (RLS) in PostgreSQL — all tenants share tables
Deployment (dev): Local Docker + docker-compose
Deployment (prod):Cloud — TBD (AWS/GCP/Fly.io/Railway)
CDN:              Cloudflare or Vercel Edge
Monitoring:       Sentry (errors) + Langfuse (agent traces) + Stripe Dashboard (billing)
Project Tracking: Linear (internal development tracking)
```

### 9.2 Phased Rollout Plan

The system grows in phases aligned with the V1/V2 roadmap and SaaS tier rollout.

#### Phase 1 — Core Pipeline + Auth (MVP)
- **Target:** All-state discovery, 1-2 counties deep-tested, ≤ 10K parcels
- **Stack:** PostgreSQL 16 + pgvector, APScheduler, SQLAlchemy async
- **Auth:** Supabase Auth or Auth0 (OAuth + email/password)
- **Job queue:** `SELECT ... FOR UPDATE SKIP LOCKED` — built into PostgreSQL, no Redis needed
- **UI:** Archon2.0 web interface with user login, search, results view
- **Tiers:** Free + Starter only (no billing yet — early access)
- **Goal:** Validate pipeline correctness, data quality, scoring accuracy, user experience

#### Phase 2 — Outreach + Billing + Multi-County
- **Trigger:** Pipeline validated, ready for paying users
- **Add:** Stripe billing (subscription tiers + usage metering)
- **Add:** Email outreach (SendGrid), SMS (Twilio), DNC compliance
- **Add:** Celery + Redis for distributed job execution and rate limit management
- **Add:** pgvector HNSW indexes (activate after Phase 1 data validates embedding approach)
- **Add:** Per-user settings panel (alerts, outreach config, thresholds)
- **Tiers:** All 4 tiers active with billing enforcement
- **Retain:** PostgreSQL as primary store; DuckDB begins receiving Parquet exports for analytics

#### Phase 3 — Production Scale + Premium Features (100K+ Parcels)
- **Add:** PgBouncer connection pooling (PostgreSQL connections become the bottleneck at scale)
- **Add:** DuckDB as primary analytics engine (column-scan performance dominates at this scale)
- **Add:** Parquet snapshot pipeline: PostgreSQL → nightly export → DuckDB queries
- **Add:** Phone outreach (click-to-call + AI voice agent)
- **Add:** Continuous monitoring mode (Enterprise tier)
- **Add:** Team/org management (Enterprise tier)
- **Add:** Paid data source integrations (ATTOM, PropStream, PeopleDataLabs)
- **Cloud:** Production deployment on cloud infrastructure

#### Phase 4 — V2 Autonomous Actions
- **Add:** Pre-auction offer generation and sending
- **Add:** Auction platform registration and automated bidding
- **Add:** Multi-channel outreach sequences
- **Add:** API access for programmatic integrations

### 9.3 Database Subagent Architecture

The **Database Subagent** runs continuously in the background and is responsible for keeping the Aloha database current. It is Aloha's "heartbeat."

```
Database Subagent Responsibilities:
  ┌─────────────────────────────────────────────────────┐
  │  SCHEDULER (APScheduler cron jobs)                  │
  │                                                     │
  │  Every 15 min:  Check research_queue for stalled    │
  │                 jobs (> 1h without progress) →      │
  │                 reset to retry                      │
  │                                                     │
  │  Every 1 hour:  Check liens table for approaching   │
  │                 redemption deadlines → escalate     │
  │                 priority                            │
  │                                                     │
  │  Every 24h:     Mark parcel records > 7 days old    │
  │                 as "stale" → queue for recrawl      │
  │                                                     │
  │  Every 24h:     Re-crawl county tax site for NEW    │
  │                 liens added since last run           │
  │                 (differential crawl via content hash)│
  │                                                     │
  │  Weekly:        Re-verify lien status (redeemed?    │
  │                 auctioned?) for all active liens     │
  │                                                     │
  │  On-demand:     Triggered by Orchestrator when a    │
  │                 specific parcel needs refresh        │
  └─────────────────────────────────────────────────────┘
```

**Change detection strategy (3-layer approach):**

1. **Bulk data exports first (preferred):** Many counties publish Socrata datasets or FTP CSV/XML exports. When available, download the full list and diff it — zero crawling needed.
   ```python
   # Socrata Open Data API (works for counties on data.gov / county data portals)
   response = requests.get(
       "https://{county}.data.socrata.com/resource/{dataset_id}.json",
       params={"$where": "delinquent_date > '2026-01-01'", "$limit": 50000}
   )
   ```

2. **Content hash (always stored, works on 100% of sites):**
   ```python
   import hashlib
   normalized = ' '.join(new_html_content.split())   # collapse whitespace
   new_hash = hashlib.md5(normalized.encode()).hexdigest()
   if new_hash == stored_hash:
       return  # skip — page unchanged
   ```

3. **Structural field hash (for high-precision change detection on key fields only):**
   ```python
   # Only hash fields that matter for investment decisions
   key_fields = f"{status}|{paid_date}|{auction_date}|{face_amount}"
   structural_hash = hashlib.md5(key_fields.encode()).hexdigest()
   ```
   This avoids false positives from cosmetic site changes (footer updates, ad content, etc.).

4. **HTTP cache headers (bonus ~30% of county sites):** Check `ETag` / `Last-Modified` headers before fetching full page body. Saves bandwidth on sites that support it.

**⚠️ Critical concurrency warning:** Never use `SELECT WHERE status='pending' LIMIT 1` without `FOR UPDATE SKIP LOCKED`. Without it, multiple agents will claim the same job simultaneously, causing duplicate work and data corruption.

**Research queue design:**

```sql
CREATE TABLE research_queue (
  id SERIAL PRIMARY KEY,
  parcel_id TEXT NOT NULL,
  stage TEXT NOT NULL,           -- discover | parcel | owner | entity | enrich | score
  priority INTEGER DEFAULT 5,    -- 1=urgent (deadline <30d), 10=low
  status TEXT DEFAULT 'pending', -- pending | in_progress | done | failed | retry
  attempts INTEGER DEFAULT 0,
  last_error TEXT,
  next_retry_at TIMESTAMP,
  claimed_by TEXT,               -- agent instance ID (for concurrency safety)
  claimed_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_queue_pickup ON research_queue(status, priority, next_retry_at)
  WHERE status IN ('pending', 'retry');
```

**Agent claims jobs atomically:**
```sql
-- Atomic job claim (prevents two agents grabbing same job)
UPDATE research_queue
SET status = 'in_progress', claimed_by = $agent_id, claimed_at = NOW()
WHERE id = (
  SELECT id FROM research_queue
  WHERE status IN ('pending', 'retry')
    AND (next_retry_at IS NULL OR next_retry_at <= NOW())
  ORDER BY priority ASC, created_at ASC
  LIMIT 1
  FOR UPDATE SKIP LOCKED
)
RETURNING *;
```

### 9.4 DuckDB Analytics Sidecar

DuckDB is **not** an operational database — it's a fast analytical layer that queries Parquet snapshots. It runs in-process (no server needed) and provides 10-100x faster column-scan performance for investment screening queries.

```python
# Nightly export from PostgreSQL to Parquet
# (run by Database Subagent)
import duckdb

conn = duckdb.connect()
conn.execute("""
    INSTALL postgres;
    LOAD postgres;
    ATTACH 'host=localhost dbname=aloha' AS pg (TYPE postgres);

    -- Export parcels + liens + scores as Parquet snapshot
    COPY (
        SELECT p.*, l.principal_amount, l.total_owed, l.redemption_deadline,
               s.overall_score, s.lien_to_value_ratio
        FROM pg.parcels p
        JOIN pg.tax_liens l USING (parcel_id)
        LEFT JOIN pg.scores s USING (parcel_id)
        WHERE l.lien_status = 'active'
    ) TO '/data/snapshots/parcels_latest.parquet' (FORMAT PARQUET);
""")
```

**Analytical queries served by DuckDB (examples):**
```sql
-- Top 50 opportunities by score in a county
SELECT parcel_id, address, total_owed, lien_to_value_ratio, overall_score
FROM read_parquet('/data/snapshots/parcels_latest.parquet')
WHERE county = 'Orange' AND state = 'FL'
ORDER BY overall_score DESC
LIMIT 50;

-- Redemption deadlines in next 60 days
SELECT parcel_id, address, total_owed, redemption_deadline
FROM read_parquet('/data/snapshots/parcels_latest.parquet')
WHERE redemption_deadline BETWEEN current_date AND current_date + INTERVAL '60 days'
ORDER BY redemption_deadline ASC;
```

### 9.5 MCP Servers to Build

| Server | Purpose | Transport |
|--------|---------|-----------|
| `county-assessor-mcp` | Query county assessor APIs by parcel ID | stdio |
| `sos-mcp` | Secretary of State business entity lookup | stdio |
| `gis-mcp` | ArcGIS REST API wrapper for zoning/parcel lookup + parcel map export | stdio |
| `court-records-mcp` | State court public record search | stdio |
| `ucc-mcp` | UCC lien filing search | stdio |
| `image-capture-mcp` | Orchestrates all image capture: GIS map, Street View, satellite, Zillow; stores files; returns paths + crop hints | stdio |
| `outreach-mcp` | Send emails (SendGrid), SMS (Twilio), initiate calls (Twilio Voice); log all interactions; check DNC registry; manage opt-outs | stdio |

### 9.6 Database Schema (Full)

```sql
-- =============================================
-- USERS & SUBSCRIPTIONS
-- =============================================
CREATE TABLE users (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email             TEXT NOT NULL UNIQUE,
  display_name      TEXT,
  auth_provider     TEXT,               -- google|github|email
  auth_provider_id  TEXT,               -- external auth ID
  -- Subscription
  tier              TEXT DEFAULT 'free', -- free|starter|professional|enterprise
  stripe_customer_id TEXT,
  stripe_subscription_id TEXT,
  subscription_status TEXT DEFAULT 'active', -- active|past_due|canceled|trialing
  -- Outreach identity
  outreach_mode     TEXT DEFAULT 'individual', -- individual|business|byoc
  outreach_email    TEXT,               -- sending email address
  outreach_domain   TEXT,               -- sending domain
  sendgrid_api_key  TEXT,               -- encrypted; null = use platform pool
  twilio_account_sid TEXT,              -- encrypted; null = use platform pool
  twilio_auth_token TEXT,               -- encrypted
  twilio_phone_number TEXT,             -- user's outreach phone number
  physical_address  TEXT,               -- CAN-SPAM required physical address
  -- Settings (JSON blob for flexibility)
  settings          JSONB DEFAULT '{}', -- alert_channels, score_thresholds, outreach_rules, etc.
  created_at        TIMESTAMP DEFAULT NOW(),
  updated_at        TIMESTAMP DEFAULT NOW()
);

-- =============================================
-- CORE PARCEL TABLE
-- =============================================
CREATE TABLE parcels (
  parcel_id         TEXT PRIMARY KEY,    -- APN or county-assigned ID
  user_id           UUID REFERENCES users(id), -- which user discovered this parcel
  county            TEXT NOT NULL,
  state             TEXT NOT NULL,
  address           TEXT,
  legal_description TEXT,
  acreage           DECIMAL,
  land_use_code     TEXT,
  property_type     TEXT,               -- residential, commercial, land, industrial, agricultural
  zoning            TEXT,
  zoning_notes      TEXT,
  assessed_land_val INTEGER,
  assessed_impr_val INTEGER,
  assessed_total    INTEGER,
  market_value_est  INTEGER,            -- from comps/Zillow
  last_sale_date    DATE,
  last_sale_price   INTEGER,
  year_built        INTEGER,
  -- Research pipeline state
  research_status   TEXT DEFAULT 'discovered',  -- discovered|parcel_researched|owner_researched|enriched|scored|complete
  data_freshness    TEXT DEFAULT 'fresh',        -- fresh|stale|expired
  content_hash      TEXT,              -- MD5 of last crawl for change detection
  last_crawled_at   TIMESTAMP,
  created_at        TIMESTAMP DEFAULT NOW(),
  updated_at        TIMESTAMP DEFAULT NOW()
);

-- =============================================
-- TAX LIEN RECORDS
-- =============================================
CREATE TABLE tax_liens (
  id                 SERIAL PRIMARY KEY,
  parcel_id          TEXT REFERENCES parcels(parcel_id) ON DELETE CASCADE,
  -- Instrument classification (drives scoring model)
  instrument_type    TEXT NOT NULL DEFAULT 'lien_certificate',
                     -- lien_certificate | tax_deed | hybrid_pending
  -- Shared fields
  lien_status        TEXT DEFAULT 'active',
                     -- [cert] active|redeemed|sold_at_auction|foreclosed|expired
                     -- [deed] scheduled_auction|sold|withdrawn|postponed|no_bid
  tax_year           INTEGER,
  years_delinquent   INTEGER,
  principal_amount   DECIMAL NOT NULL,
  interest_amount    DECIMAL,
  penalty_amount     DECIMAL,
  total_owed         DECIMAL,
  filing_date        DATE,
  -- Lien Certificate specific
  redemption_deadline DATE,
  certificate_number  TEXT,
  certificate_interest_rate DECIMAL,        -- interest rate earned on the certificate (e.g. 0.18 for 18%)
  lien_holder         TEXT DEFAULT 'county',-- 'county' until sold at auction, then investor name
  -- Tax Deed specific
  auction_date        DATE,
  auction_time        TEXT,                 -- e.g. '10:00 AM ET'
  auction_platform    TEXT,                 -- courthouse_steps|bid4assets|realauction|govease|sri|county_online
  auction_url         TEXT,                 -- direct URL to the auction listing
  opening_bid         DECIMAL,              -- government's minimum starting bid
  post_sale_redemption_days INTEGER,        -- days owner has to redeem after deed sale (0 if none)
  title_encumbrances  JSONB,               -- IRS liens, HOA, mechanics, lis pendens found in title search
  title_risk_level    TEXT,                 -- clear|minor|significant|clouded
  -- Source tracking
  source_url          TEXT,
  content_hash        TEXT,
  retrieved_at        TIMESTAMP DEFAULT NOW(),
  last_verified_at    TIMESTAMP,
  UNIQUE(parcel_id, tax_year, certificate_number)
);

-- =============================================
-- OWNER RECORDS (one per research attempt)
-- =============================================
CREATE TABLE owners (
  id                   SERIAL PRIMARY KEY,
  parcel_id            TEXT REFERENCES parcels(parcel_id) ON DELETE CASCADE,
  owner_of_record      TEXT,            -- exactly as on deed
  owner_type           TEXT,            -- individual|llc|trust|corporation|government|unknown
  mailing_address      TEXT,
  mailing_city         TEXT,
  mailing_state        TEXT,
  mailing_zip          TEXT,
  is_absentee          BOOLEAN,         -- mailing address != property address
  deed_type            TEXT,            -- warranty|quitclaim|trust|grant
  acquisition_date     DATE,
  acquisition_price    INTEGER,
  -- Beneficial owner (pierced through entity)
  beneficial_owner     TEXT,
  beneficial_owner_confidence TEXT,     -- high|medium|low|unknown
  -- Contact info (best found)
  best_phone           TEXT,
  best_email           TEXT,
  best_contact_address TEXT,
  -- Research metadata
  research_depth       INTEGER DEFAULT 0,  -- layers completed (1-4)
  sources              JSONB,
  created_at           TIMESTAMP DEFAULT NOW(),
  updated_at           TIMESTAMP DEFAULT NOW()
);

-- =============================================
-- ENTITY RESEARCH (for LLC/trust/corp owners)
-- =============================================
CREATE TABLE entities (
  id                  SERIAL PRIMARY KEY,
  entity_name         TEXT NOT NULL,
  entity_type         TEXT,             -- llc|corporation|trust|partnership|nonprofit
  state_of_formation  TEXT,
  sos_status          TEXT,             -- active|dissolved|revoked|suspended
  formation_date      DATE,
  registered_agent    TEXT,
  registered_agent_address TEXT,
  officers            JSONB,            -- array of {name, title}
  managers_members    JSONB,
  sos_filing_url      TEXT,
  -- Related entities (same manager/address)
  related_entity_ids  INTEGER[],
  -- Financials
  ucc_filings         JSONB,
  federal_tax_liens   JSONB,
  state_tax_liens     JSONB,
  bankruptcy_history  JSONB,
  -- Litigation
  litigation_summary  TEXT,
  pacer_results       JSONB,
  -- Contact
  website             TEXT,
  phone               TEXT,
  email               TEXT,
  -- Meta
  content_hash        TEXT,
  last_researched_at  TIMESTAMP,
  created_at          TIMESTAMP DEFAULT NOW(),
  UNIQUE(entity_name, state_of_formation)
);

-- Link entity to owner record
CREATE TABLE owner_entities (
  owner_id   INTEGER REFERENCES owners(id),
  entity_id  INTEGER REFERENCES entities(id),
  PRIMARY KEY (owner_id, entity_id)
);

-- =============================================
-- OPPORTUNITY SCORES
-- =============================================
CREATE TABLE scores (
  id                   SERIAL PRIMARY KEY,
  parcel_id            TEXT REFERENCES parcels(parcel_id),
  instrument_type      TEXT,             -- lien_certificate | tax_deed
  overall_score        INTEGER,          -- 0-100 (comparable across both instrument types)
  score_model_version  TEXT,             -- e.g. 'lien_v1', 'deed_v1' (for reproducibility)

  -- Shared scoring factors (0-10 each)
  property_potential   INTEGER,          -- zoning, location, development upside
  risk_score           INTEGER,          -- 0-10 where 10 = highest risk (inverted for display)

  -- Lien Certificate factors (null for tax deed records)
  lien_to_value_ratio  DECIMAL,          -- total_owed / market_value (e.g. 0.046 = 4.6%)
  certificate_rate     DECIMAL,          -- interest rate on certificate (e.g. 0.18)
  years_delinquent     INTEGER,
  owner_motivation     INTEGER,          -- 0-10 (absentee, LLC, dissolved, multiple liens)
  contact_reachability INTEGER,          -- 0-10 (high = found direct contact info)
  redemption_urgency   INTEGER,          -- 0-10 (10 = deadline < 30 days)

  -- Tax Deed factors (null for lien certificate records)
  arv_estimate         DECIMAL,          -- After Repair Value estimate
  opening_bid          DECIMAL,          -- government starting bid
  arv_to_bid_ratio     DECIMAL,          -- arv / opening_bid (e.g. 7.4 = 7.4x spread)
  title_clarity        INTEGER,          -- 0-10 (10 = perfectly clear title)
  condition_risk       INTEGER,          -- 0-10 (10 = known demolition order / severe issues)
  competition_risk     INTEGER,          -- 0-10 (10 = high-profile property, many bidders likely)
  post_sale_redemption_risk INTEGER,     -- 0-10 (10 = long redemption period post-sale)

  -- Common output
  risk_flags           TEXT[],           -- environmental, title_cloud, irs_lien, lis_pendens, hoa_lien, etc.
  flags_detail         JSONB,
  score_rationale      TEXT,
  scored_at            TIMESTAMP DEFAULT NOW()
);

-- =============================================
-- RESEARCH QUEUE (fluid pipeline)
-- =============================================
CREATE TABLE research_queue (
  id            SERIAL PRIMARY KEY,
  parcel_id     TEXT NOT NULL,
  stage         TEXT NOT NULL,           -- discover|parcel|owner|entity|contact|enrich|score|outreach
  priority      INTEGER DEFAULT 5,       -- 1=urgent, 10=low
  status        TEXT DEFAULT 'pending',  -- pending|in_progress|done|failed|retry|skipped
  attempts      INTEGER DEFAULT 0,
  last_error    TEXT,
  next_retry_at TIMESTAMP,
  claimed_by    TEXT,                    -- agent instance ID
  claimed_at    TIMESTAMP,
  created_at    TIMESTAMP DEFAULT NOW(),
  updated_at    TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_queue_pickup ON research_queue(status, priority, next_retry_at)
  WHERE status IN ('pending', 'retry');

-- =============================================
-- CRAWL LOG (audit trail + change detection)
-- =============================================
CREATE TABLE crawl_log (
  id            SERIAL PRIMARY KEY,
  parcel_id     TEXT,
  source_type   TEXT,           -- tax_collector|assessor|recorder|sos|gis|court|social
  source_url    TEXT,
  http_status   INTEGER,
  content_hash  TEXT,
  changed       BOOLEAN,        -- true if hash differs from previous crawl
  error_message TEXT,
  crawled_at    TIMESTAMP DEFAULT NOW()
);

-- =============================================
-- VECTOR STORE FOR RAG
-- =============================================
CREATE TABLE document_chunks (
  id          SERIAL PRIMARY KEY,
  parcel_id   TEXT,
  entity_id   INTEGER,
  source_type TEXT,
  source_url  TEXT,
  content     TEXT,
  embedding   vector(1536),
  created_at  TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_chunks_parcel ON document_chunks(parcel_id);
CREATE INDEX idx_chunks_embedding ON document_chunks USING hnsw (embedding vector_cosine_ops);

-- =============================================
-- ALERTS (deadline tracking)
-- =============================================
CREATE TABLE alerts (
  id           SERIAL PRIMARY KEY,
  parcel_id    TEXT REFERENCES parcels(parcel_id),
  alert_type   TEXT,   -- redemption_deadline|auction_date|lien_status_change|new_high_score
  alert_date   DATE,
  message      TEXT,
  sent         BOOLEAN DEFAULT FALSE,
  created_at   TIMESTAMP DEFAULT NOW()
);

-- =============================================
-- PROPERTY IMAGES (GIS map, street view, satellite, listing)
-- =============================================
CREATE TABLE property_images (
  id            SERIAL PRIMARY KEY,
  parcel_id     TEXT REFERENCES parcels(parcel_id) ON DELETE CASCADE,
  image_type    TEXT NOT NULL,  -- gis_parcel_map|street_view|satellite|zillow_listing
  file_path     TEXT NOT NULL,  -- local path: /data/property-images/{parcel_id}/{type}.jpg
  source_url    TEXT,           -- API endpoint or page URL used to generate image
  width         INTEGER,
  height        INTEGER,
  captured_at   TIMESTAMP DEFAULT NOW(),
  -- For GIS maps: record which overlays were active
  overlays      TEXT[],         -- e.g. ['zoning', 'parcel_boundaries']
  UNIQUE(parcel_id, image_type)
);

-- =============================================
-- SOURCE SCREENSHOTS (evidence capture)
-- =============================================
CREATE TABLE source_screenshots (
  id              SERIAL PRIMARY KEY,
  parcel_id       TEXT REFERENCES parcels(parcel_id) ON DELETE CASCADE,
  source_type     TEXT NOT NULL,  -- tax_collector|assessor|recorder|sos|court|gis|zillow
  source_name     TEXT,           -- human-readable: "Orange County Tax Collector"
  source_url      TEXT NOT NULL,
  file_path       TEXT NOT NULL,  -- full-page PNG: /data/screenshots/{parcel_id}/{type}_{date}.png
  -- Crop hint for UI display (highlights the relevant data region)
  crop_x          INTEGER,
  crop_y          INTEGER,
  crop_w          INTEGER,
  crop_h          INTEGER,
  -- Fields confirmed from this screenshot
  data_extracted  TEXT[],         -- e.g. ['lien_amount', 'tax_year', 'redemption_deadline']
  captured_at     TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_screenshots_parcel ON source_screenshots(parcel_id);

-- =============================================
-- OUTREACH LOG (all owner communications)
-- =============================================
CREATE TABLE outreach_log (
  id              SERIAL PRIMARY KEY,
  user_id         UUID REFERENCES users(id),  -- which user initiated this outreach
  parcel_id       TEXT REFERENCES parcels(parcel_id),
  owner_id        INTEGER REFERENCES owners(id),
  -- Channel
  channel         TEXT NOT NULL,       -- email|sms|phone_call|voicemail
  -- Contact info used
  contact_value   TEXT NOT NULL,       -- email address, phone number
  -- Message
  template_name   TEXT,                -- e.g. 'lien_redemption_prompt', 'deed_pre_auction_offer'
  subject         TEXT,                -- email subject line (null for SMS/phone)
  message_body    TEXT,                -- full message content sent
  -- Status
  status          TEXT DEFAULT 'pending',  -- pending|approved|sent|delivered|opened|replied|bounced|failed|declined
  approved_by     TEXT,                -- user who approved (human-in-the-loop)
  approved_at     TIMESTAMP,
  sent_at         TIMESTAMP,
  -- Delivery tracking
  delivery_status TEXT,                -- provider delivery status
  opened_at       TIMESTAMP,          -- email open tracking
  replied_at      TIMESTAMP,
  bounce_reason   TEXT,               -- bounce/failure reason
  -- Phone call specific
  call_duration   INTEGER,            -- seconds (for phone calls)
  call_outcome    TEXT,               -- answered|voicemail|no_answer|busy|wrong_number|declined
  call_notes      TEXT,               -- agent or user notes from the call
  call_recording_url TEXT,            -- Twilio recording URL (if recorded with consent)
  -- Follow-up scheduling
  follow_up_date  DATE,               -- scheduled follow-up date
  follow_up_sent  BOOLEAN DEFAULT FALSE,
  -- Provider references
  provider        TEXT,               -- sendgrid|twilio
  provider_msg_id TEXT,               -- SendGrid message ID or Twilio SID
  -- Meta
  created_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_outreach_parcel ON outreach_log(parcel_id);
CREATE INDEX idx_outreach_owner ON outreach_log(owner_id);
CREATE INDEX idx_outreach_followup ON outreach_log(follow_up_date)
  WHERE follow_up_sent = FALSE AND follow_up_date IS NOT NULL;

-- =============================================
-- DO NOT CONTACT LIST (opt-outs)
-- =============================================
CREATE TABLE do_not_contact (
  id              SERIAL PRIMARY KEY,
  contact_value   TEXT NOT NULL,       -- email or phone number
  contact_type    TEXT NOT NULL,       -- email|phone|sms
  reason          TEXT,                -- opt_out|unsubscribe|dnc_registry|manual|bounced
  source          TEXT,                -- how they were added (twilio_stop, sendgrid_unsub, manual, dnc_check)
  owner_id        INTEGER REFERENCES owners(id),
  created_at      TIMESTAMP DEFAULT NOW(),
  UNIQUE(contact_value, contact_type)
);
CREATE INDEX idx_dnc_lookup ON do_not_contact(contact_value, contact_type);

-- =============================================
-- OUTREACH TEMPLATES
-- =============================================
CREATE TABLE outreach_templates (
  id              SERIAL PRIMARY KEY,
  template_name   TEXT NOT NULL UNIQUE,  -- e.g. 'lien_redemption_prompt'
  channel         TEXT NOT NULL,         -- email|sms|phone_script
  instrument_type TEXT,                  -- lien_certificate|tax_deed|null (both)
  subject         TEXT,                  -- email subject (supports {{variables}})
  body            TEXT NOT NULL,         -- message body (supports {{variables}})
  variables       TEXT[],               -- list of template variables: owner_name, address, amount, etc.
  is_active       BOOLEAN DEFAULT TRUE,
  created_at      TIMESTAMP DEFAULT NOW(),
  updated_at      TIMESTAMP DEFAULT NOW()
);
```

---

## 10. Security & Legal Considerations

### 10.1 Legal Framework
- **Public records doctrine** — Government tax/assessor/recorder data is public record in all US states
- **robots.txt compliance** — Agent must respect crawl restrictions on government sites
- **Rate limiting** — Must throttle requests to avoid overwhelming government servers (DoS risk)
- **Terms of service** — Social media scraping may violate platform ToS (LinkedIn, Facebook)
- **CCPA/state privacy laws** — Aggregating personal data creates compliance obligations
- **DPPA (Driver's Privacy Protection Act)** — DMV records off-limits without permissible purpose
- **FCRA (Fair Credit Reporting Act)** — If used for credit/tenant screening, FCRA compliance required

### 10.1a Outreach & Communication Legal Framework

#### Email (CAN-SPAM Act)
- **Required:** Physical mailing address in every email
- **Required:** Clear unsubscribe mechanism (one-click, processed within 10 business days)
- **Required:** Accurate "From" and "Subject" headers — no deceptive content
- **Required:** Identify message as an ad/solicitation (if applicable)
- **Prohibited:** Harvested email addresses cannot be used without consent
- **Penalty:** Up to $51,744 per email violation

#### SMS / Text (TCPA — Telephone Consumer Protection Act)
- **Required:** Prior express consent before sending marketing texts
- **Required:** Identify sender in every message
- **Required:** Honor STOP/opt-out requests immediately (Twilio handles automatically)
- **Prohibited:** Sending to numbers on the Do Not Call registry for marketing
- **Gray area:** Informational texts about a property the owner holds (not marketing per se) — consult counsel
- **Penalty:** $500-$1,500 per unsolicited text
- **State laws:** Some states (FL, CA, WA) have stricter rules than federal TCPA

#### Phone Calls (TCPA + TSR + State Laws)
- **Required:** Check National Do Not Call Registry before calling
- **Required:** No calls before 8:00 AM or after 9:00 PM (recipient's local time)
- **Required:** Identify yourself and purpose within first 30 seconds
- **Required:** Provide phone number or address for opt-out requests
- **Prohibited:** Prerecorded voice messages to cell phones without prior express written consent
- **Prohibited:** Auto-dialing cell phones without consent (ATDS restrictions)
- **Click-to-call (recommended):** You manually initiate and speak live — fewest legal restrictions
- **Voicemail drop:** Legal gray area — treated as a call by FCC; use with caution
- **State-specific:** Some states require two-party consent for call recording (CA, FL, IL, PA, others)
- **Penalty:** $500-$1,500 per violation

#### Do Not Call (DNC) Compliance
- **National DNC Registry:** Download quarterly from FTC (data.gov) or use API
- **Internal DNC list:** Maintain your own — owners who request no contact must be added within 30 days
- **DNC check before every call/text:** Agent must verify number is not on either list
- **Retention:** Keep DNC records for 5 years minimum

#### Best Practices for Aloha Outreach
1. **Start with email** — lowest legal risk, highest documentation trail
2. **SMS only with caution** — informational messages about their own property are lower risk than marketing
3. **Phone calls: click-to-call only** — you speak live, identify yourself, state purpose
4. **Always human approval** — no fully automated outreach without user clicking "approve"
5. **Log everything** — every outreach attempt, response, opt-out recorded in `outreach_log`
6. **Respect immediately** — any opt-out = permanent DNC for that contact across all channels

### 10.2 Permissible Use
This agent is designed for:
- Investment research (permissible — public records)
- Due diligence (permissible — public records)
- Property research (permissible — public records)

This agent is **NOT** designed for:
- Harassment or stalking of property owners
- Consumer credit/background screening (FCRA territory)
- Any purpose prohibited by applicable state law

### 10.3 Data Storage
- No storage of SSNs, driver's license numbers, or financial account numbers
- Social media findings stored as summaries, not raw scraped profiles
- Data retention policy: TBD (see `toresearch.md`)
- Access control: TBD

### 10.4 Technical Safety
- User-agent string identifies the agent honestly
- Delay between requests: 2-5 seconds minimum
- Max concurrent requests per domain: 2
- Automatic backoff on 429/503 responses
- No credential stuffing or authentication bypass

---

## 11. Subscription Tiers & User Management

### 11.1 Tier Structure

Aloha is a SaaS product with tiered subscriptions. Every capability — research depth, run mode, outreach, alerts — scales with the user's plan.

| Feature | Free / Trial | Starter | Professional | Enterprise |
|---------|-------------|---------|--------------|------------|
| **Discovery** | 1 county, on-demand | 5 counties, on-demand | Unlimited counties, scheduled | Unlimited, continuous monitoring |
| **Batch size** | Up to 50 parcels/run | Up to 500/run | Up to 5,000/run | Unlimited |
| **Research depth** | Level 1-2 (owner name + entity basics) | Level 3 (entity piercing) | Level 4 (+ social/contact) | Level 5 (full intelligence) |
| **Entity research** | Registered agent + officers only | Full ownership chain | Full chain + related entities | Full chain + paid enrichment APIs |
| **Social media** | None | Public records only | All platforms (browser) | All platforms + PeopleDataLabs/Hunter.io/Clearbit |
| **Scoring** | Basic (3 factors) | Standard (7 factors) | Full model + configurable weights | Custom scoring models |
| **Outreach channels** | None | Email only | Email + SMS | Email + SMS + Phone (click-to-call + AI voice) |
| **Outreach approval** | N/A | Manual per message | Configurable (manual/template/hybrid) | Fully configurable + auto-sequences |
| **Follow-up sequences** | N/A | Single contact | Up to 3 follow-ups | Multi-channel sequences (email→SMS→phone) |
| **Alerts** | In-app only | In-app + email | In-app + email + SMS | All channels, configurable |
| **Run mode** | On-demand only | On-demand | On-demand + weekly scheduled | On-demand + scheduled + continuous monitoring |
| **Data export** | None | PDF reports | PDF + CSV + API access | Full API + webhooks + bulk export |
| **Auction walkthrough** | Read-only guides | Guided step-by-step | Guided + checklists + reminders | Guided + agent-assisted prep |
| **Paid data sources** | None | None | Optional add-on (ATTOM, PropStream) | Included |
| **Support** | Community | Email | Priority email | Dedicated |

### 11.2 User Management

| Component | Implementation |
|-----------|---------------|
| **Authentication** | OAuth 2.0 (Google, GitHub) + email/password via Supabase Auth or Auth0 |
| **Authorization** | Role-based: `viewer` (read-only), `researcher` (run searches), `admin` (manage team, billing) |
| **Multi-tenancy** | Each user/org has isolated data (row-level security in PostgreSQL) |
| **Session management** | JWT tokens, refresh tokens, session timeout configurable |
| **Team support** | Enterprise tier: invite team members, shared research, role assignments |

### 11.3 Per-User Configuration (Settings Panel)

Users configure these in their settings — the agent reads them at runtime:

| Setting | Options | Default |
|---------|---------|---------|
| **Alert channels** | In-app, email, SMS (by tier) | In-app only |
| **Alert score threshold** | 0-100 slider | 70 |
| **Outreach approval mode** | Manual per message / Template auto-send / Hybrid | Manual |
| **Outreach frequency caps** | Contacts per owner per channel per time period | Email: 1/week, SMS: 1/week, Phone: 1/2 weeks |
| **Follow-up rules** | Number of follow-ups, delays between, channel escalation | 3 follow-ups, 3/7/14 day delays |
| **Score threshold for outreach** | Minimum score to be eligible for outreach | 50 |
| **Outreach identity** | Individual investor / Business entity / Custom | — |
| **Email sending domain** | User's own domain (BYOD) or Aloha subdomain | — |
| **Twilio credentials** | User provides own Twilio SID/token (BYOC) or uses Aloha shared pool | — |
| **SendGrid credentials** | User provides own API key (BYOC) or uses Aloha shared | — |
| **Phone call mode** | Click-to-call / AI voice agent / Both | Click-to-call |
| **Do Not Contact list** | User-managed list of opt-outs | Empty |
| **Research depth override** | Cap research at lower level than tier allows | Tier max |

### 11.4 Outreach Identity Models

| Model | How It Works | Best For |
|-------|-------------|----------|
| **BYOC (Bring Your Own Credentials)** | User provides their own Twilio account + SendGrid API key + sending domain. Full control, messages come from their identity. | Professional/Enterprise users who want branded outreach |
| **Platform pool** | Aloha provides shared Twilio numbers + SendGrid sending domain. User's name appears in message but Aloha infrastructure sends it. | Starter users, quick onboarding |
| **Hybrid** | User provides email domain (SendGrid BYOC) but uses Aloha Twilio pool for SMS/calls | Most common setup |

### 11.5 Billing & Payments

| Component | Implementation |
|-----------|---------------|
| **Payment processor** | Stripe (subscriptions + usage-based add-ons) |
| **Billing model** | Monthly subscription per tier + optional usage add-ons |
| **Usage add-ons** | Extra parcels beyond tier limit, paid data source lookups (ATTOM, PropStream), extra outreach credits |
| **Metering** | Track parcels researched, outreach messages sent, API calls consumed per billing period |
| **Trial** | Free tier with limited features (no credit card required) → upgrade prompt |

---

## 12. Version Roadmap (V1 / V2)

### V1 — Discovery + Research + Guided Walkthrough + Outreach

**Goal:** Users discover tax liens/deeds, research properties and owners deeply, receive scored recommendations, contact owners via email/SMS/phone, and get guided through the pre-auction and auction process.

| Phase | Deliverables |
|-------|-------------|
| **V1.0 — Core Pipeline** | Lien/deed discovery (all states), parcel research, owner research (Level 1-3), scoring, web UI, user auth |
| **V1.1 — Deep Research** | Level 4-5 owner research, entity piercing, social media, zoning, enrichment |
| **V1.2 — Outreach** | Email outreach (SendGrid), SMS (Twilio), phone click-to-call, DNC compliance, templates |
| **V1.3 — Guided Auction** | Step-by-step auction walkthrough UI, pre-auction offer templates, auction prep checklists, deadline reminders |
| **V1.4 — Monitoring + Alerts** | Scheduled scans, continuous monitoring (premium), configurable alerts across channels |
| **V1.5 — Subscription Tiers** | Stripe billing, tier enforcement, usage metering, team management (Enterprise) |

### V2 — Autonomous Offers + Bidding

**Goal:** Agent acts on behalf of the user — drafts and sends offers, registers for auctions, places bids within user-defined limits.

| Phase | Deliverables |
|-------|-------------|
| **V2.0 — Pre-Auction Offers** | Agent generates offer letters, sends via email/mail, tracks responses, negotiates within parameters |
| **V2.1 — Auction Bidding** | Agent registers on auction platforms (Bid4Assets, Realauction, GovEase), places bids per user limits |
| **V2.2 — Paid Enrichment** | PeopleDataLabs, Hunter.io, Clearbit, ATTOM API integrations for premium research |
| **V2.3 — AI Voice Agent** | Claude-powered voice calls for initial owner contact, escalation to human for negotiation |
| **V2.4 — Multi-Channel Sequences** | Automated outreach campaigns: email → SMS → phone with configurable delays and escalation |

---

## 13. Open Questions

All user decisions (Section A) are complete. See `toresearch.md` for remaining technical research:
- [x] Auth provider — V1: Supabase Auth local; revisit for production
- [x] Cloud hosting — V1: all local; production provider TBD (needs cost comparison)
- [x] Pricing — decide later, competitive research needed first
- [x] Freemium model — yes, free tier forever
- [ ] Stripe integration details (subscription plans, usage metering) — Phase 2
- [ ] Multi-tenancy strategy (RLS vs. schema-per-tenant) — see B.9.1
- [ ] State-by-state outreach compliance matrix — see B.8.6
- [ ] AI voice agent latency feasibility (Twilio + Claude) — see B.8.5
- [ ] Cloud deployment cost estimation — see B.9.6
- [ ] Credential encryption for BYOC user API keys — see B.9.4
