# Original User Request

## 2026-09-29T21:54:01Z

A web application that collects a service address and generates a clean, comprehensive availability report of every 5G Home Internet and wireless broadband provider available at that address, treating distinct retail consumer brands (e.g., T-Mobile vs. Metro by T-Mobile, Verizon vs. Straight Talk and Total Wireless, AT&T Internet Air) as separate providers.

Working directory: /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint
Integrity mode: development

## Requirements

### R1. Address Intake & Pluggable Geocoding System
Build a responsive address intake interface using Next.js App Router (TypeScript, React, Tailwind CSS, and shadcn/ui). Implement a pluggable geocoding service with a zero-config open default (US Census Bureau Geocoder / OpenStreetMap Nominatim/Photon) and drop-in support for Google Places / Mapbox via environment variables. The service must normalize input addresses into standardized postal components and latitude/longitude coordinates.

### R2. Hybrid Provider Availability & Brand-Level Resolution Engine
Implement a backend provider availability engine combining FCC Broadband Data Collection (BDC) location-level data with a modular provider checking architecture (`IProviderChecker`). The engine must evaluate coverage for a resolved address/coordinate, recognize distinct retail consumer brands as separate entities (T-Mobile 5G Home Internet, Metro by T-Mobile, Verizon 5G Home, Straight Talk Home Internet, Total Wireless, AT&T Internet Air, Starlink), and execute fast pre-flight availability checks with resilient, automatic fallback to FCC BDC data if carrier endpoints throttle or timeout.

### R3. Provider Catalog & Local Cache Layer (SQLite + Drizzle ORM)
Create a provider catalog and query cache backed by SQLite using Drizzle ORM with an in-memory LRU cache. The catalog stores rich metadata for each retail brand (advertised speeds, equipment requirements, pricing tiers, contract terms, and official consumer signup links). The cache stores recent coordinate lookups with a configurable TTL to ensure sub-second response times on repeat queries.

### R4. Interactive Brand-Level Availability & Comparison Report UI
Build an interactive results view displaying all available providers at the queried address. The UI must feature:
- Distinct retail brand identity (name, brand badge, technology type)
- Advertised download/upload speed ranges
- Pricing and plan details (monthly cost, equipment fees, contract terms)
- Dynamic filter and sort controls (by price, speed, and network family)
- Direct outbound links to provider checkout/signup pages
- Graceful handling and fallback messaging when an address has limited or satellite-only coverage (e.g., Starlink)

## Acceptance Criteria

### Address Resolution & Geocoding
- [ ] Address search input provides autocomplete suggestions for valid US addresses without requiring paid API keys out of the box.
- [ ] Address submission successfully returns normalized components (`street_number`, `street_name`, `city`, `state`, `zip5`) and coordinates (`lat`, `lng`).

### Multi-Brand Availability Engine
- [ ] Querying an address in a known T-Mobile 5G coverage zone returns distinct, separate entries for both **T-Mobile 5G Home Internet** and **Metro by T-Mobile**.
- [ ] Querying an address in a known Verizon 5G coverage zone returns distinct entries for **Verizon 5G Home**, **Straight Talk Home Internet**, and **Total Wireless**.
- [ ] Rural / non-terrestrial addresses gracefully report **Starlink** (and satellite alternatives) as available with clear status badges.
- [ ] Each provider checker implements timeout handling (max 1.5s per provider) and falls back safely to FCC BDC data without crashing the request.

### Report UI & API Performance
- [ ] Endpoint `GET /api/availability?address=...` returns HTTP 200 with structured JSON provider data in under 2 seconds.
- [ ] Provider comparison view renders responsive cards with clear pricing, speeds, and direct signup links.
- [ ] Users can filter results by provider brand, speed tier, and sort by monthly price.

### Automated Test Harness & Verification
- [ ] Vitest test suite executes unit and integration tests covering:
  - Address parsing and normalization.
  - FCC BDC response parsing and brand mapping.
  - Catalog query and Drizzle ORM caching logic.
- [ ] Playwright E2E test suite executes end-to-end user journeys against mock address fixtures (Urban multi-provider, Suburban single-carrier, Rural satellite-only, and Invalid address error handling).
