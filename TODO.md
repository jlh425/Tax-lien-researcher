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

- [x] **Docker health checks & resource limits** — postgres/redis/backend/frontend health checks + memory/CPU limits (commit `37d15f6`)
- [x] **Missing frontend pages** — Settings (profile, subscription, API keys) + Queue History (status cards, agent breakdown) (commit `e5a5975`)
- [x] **`.env.example` completeness** — Added all missing keys: Stripe, SendGrid, Cobalt, Maps, Captcha (commit `3ee64a4`)
- [x] **Login/auth UI** — Login/register page, Zustand auth store, route protection, Sign Out (commit `44cc956`)
