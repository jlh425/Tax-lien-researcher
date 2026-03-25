# Aloha Tax Research — TODO

## Tier 1 — Blocking (core functionality gaps)

- [ ] **OCR for scanned PDFs** — `src/aloha/pdf/pipeline.py` `extract_scanned_text()` is a stub; integrate Tesseract or cloud OCR
- [ ] **GIS parcel boundary** — `src/aloha/mcp_servers/gis/server.py` `get_parcel_boundary()` returns stub data; implement ArcGIS geometry retrieval
- [ ] **Email/SMS outreach** — `src/aloha/services/outreach_service.py` + `notification_service.py` use stub providers; wire real SendGrid/Twilio dispatch
- [ ] **Stripe billing** — `src/aloha/services/billing_service.py` returns mock customer IDs and webhook handler is a no-op; implement real Stripe integration
- [ ] **County assessor owner search** — `src/aloha/mcp_servers/county_assessor/server.py` `search_by_owner()` is a stub; implement name-based search via scrapers

## Tier 2 — High value (tests & integration)

- [ ] **Service tests** — Only 1 test file for 9 services; add tests for billing, notification, outreach, auth, parcel, export services
- [ ] **API route tests** — Parcels, scan, and auth routes have no tests
- [ ] **Frontend component tests** — Dashboard, ScanForm, ParcelCard, ParcelDetailPane, QueueStatusBar untested
- [ ] **CI/CD** — No GitHub Actions workflows; add automated testing, linting, and deploy pipelines
- [ ] **End-to-end MCP server integration tests** — Verify CourtListener & Cobalt APIs work with real keys

## Tier 3 — Polish

- [ ] **Docker health checks & resource limits** — Add health checks and memory/CPU constraints to docker-compose
- [ ] **Missing frontend pages** — Settings/profile page, queue history page
- [ ] **`.env.example` completeness** — Missing `stripe_publishable_key`, Smarty credentials, Mapbox key
- [ ] **Login/auth UI** — No frontend authentication page exists
