# Aloha Tax Research — TODO

## Tier 1 — Blocking (core functionality gaps)

- [x] **OCR for scanned PDFs** — PyMuPDF 300 DPI rendering + pytesseract (commit `02e88c5`)
- [x] **GIS parcel boundary** — ArcGIS Esri rings → GeoJSON Polygon (commit `c37a77a`)
- [x] **Email/SMS outreach** — SendGrid v3 + Twilio REST via httpx (commit `3664559`)
- [x] **Stripe billing** — Real Stripe SDK: customers, checkout, webhooks (commit `e0a0729`)
- [x] **County assessor owner search** — ArcGIS multi-alias owner query cascade (commit `33a798e`)

## Tier 2 — High value (tests & integration)

- [x] **Service tests** — 51 tests covering all 9 services (billing, notification, outreach, auth, parcel, export, research, base, deps)
- [x] **API route tests** — 18 tests for auth, scan, and parcels routes (commit `70d4a8f`)
- [x] **Frontend component tests** — 42 total: Dashboard, ScanForm, ParcelCard, QueueStatusBar (commit `3ad5353`)
- [x] **CI/CD** — GitHub Actions: backend (ruff + mypy + pytest) + frontend (tsc + vitest + build) (commit `a46bf2d`)
- [x] **End-to-end MCP server integration tests** — 7 tests for CourtListener, Cobalt, Google Maps (commit `1006721`)

## Tier 3 — Polish

- [ ] **Docker health checks & resource limits** — Add health checks and memory/CPU constraints to docker-compose
- [ ] **Missing frontend pages** — Settings/profile page, queue history page
- [ ] **`.env.example` completeness** — Missing `stripe_publishable_key`, Smarty credentials, Mapbox key
- [ ] **Login/auth UI** — No frontend authentication page exists
