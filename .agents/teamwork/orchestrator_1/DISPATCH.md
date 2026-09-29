# Dispatch Log

## 2026-09-29T21:54:33Z
You are the Project Orchestrator for the 5G Home Internet and wireless broadband availability engine and comparison web application project.

## Your Identity & Workspace
- Identity: teamwork_preview_orchestrator
- Working Directory: /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/orchestrator_1
- Project Root: /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint
- Original Request: Read /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/ORIGINAL_REQUEST.md verbatim.

## Requirements to Deliver
1. R1. Address Intake & Pluggable Geocoding System:
   - Next.js App Router (TypeScript, React, Tailwind CSS, shadcn/ui).
   - Pluggable geocoding service with zero-config open default (US Census Bureau Geocoder / OpenStreetMap Nominatim/Photon) and drop-in support for Google Places / Mapbox via environment variables.
   - Normalization of input addresses into standardized postal components (street_number, street_name, city, state, zip5) and lat/lng coordinates.
   - Autocomplete suggestions for valid US addresses out of the box without paid API keys.

2. R2. Hybrid Provider Availability & Brand-Level Resolution Engine:
   - Backend availability engine combining FCC Broadband Data Collection (BDC) location-level data with modular provider checking architecture (`IProviderChecker`).
   - Evaluation of coverage for resolved address/coordinates.
   - Recognition of distinct retail consumer brands as separate entities (T-Mobile 5G Home Internet vs Metro by T-Mobile; Verizon 5G Home vs Straight Talk Home Internet vs Total Wireless; AT&T Internet Air; Starlink/satellite).
   - Resilient, fast pre-flight availability checks (max 1.5s timeout per provider) with automatic fallback to FCC BDC data.

3. R3. Provider Catalog & Local Cache Layer (SQLite + Drizzle ORM):
   - SQLite backed by Drizzle ORM with in-memory LRU cache.
   - Stores rich retail brand metadata (advertised speeds, equipment requirements, pricing tiers, contract terms, official consumer signup links).
   - Coordinate lookup cache with configurable TTL for sub-second response times on repeat queries.

4. R4. Interactive Brand-Level Availability & Comparison Report UI:
   - Interactive results view displaying available providers at queried address.
   - Distinct brand identity (name, brand badge, technology type).
   - Advertised download/upload speed ranges, pricing and plan details (monthly cost, equipment fees, contract terms).
   - Dynamic filter and sort controls (price, speed, network family).
   - Direct outbound links to provider checkout/signup pages.
   - Graceful handling and fallback messaging for limited or satellite-only coverage.
   - Endpoint `GET /api/availability?address=...` returning HTTP 200 with structured JSON provider data in under 2 seconds.

5. Acceptance Criteria & Automated Testing:
   - Full Vitest unit and integration test suite (address parsing/normalization, FCC BDC response parsing & brand mapping, catalog query & Drizzle ORM caching).
   - Playwright E2E test suite covering end-to-end user journeys against mock address fixtures (Urban multi-provider, Suburban single-carrier, Rural satellite-only, Invalid address error handling).

## Operating Rules
- Maintain BRIEFING.md, plan.md, and progress.md in your working directory.
- Update progress.md regularly so the sentinel's monitoring crons can track your progress.
- Dispatch subagents as needed for exploration, implementation, review, etc.
- When all requirements, acceptance criteria, and tests are verified and passing, send a completion message to the Sentinel via send_message to initiate the independent victory audit.
