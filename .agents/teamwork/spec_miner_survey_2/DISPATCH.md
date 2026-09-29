## 2026-09-29T21:55:44Z
You are spec_miner_survey_2, a teamwork_preview_spec_miner subagent.
Your Working Directory: /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/spec_miner_survey_2
Original Request: Read /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/ORIGINAL_REQUEST.md verbatim.

Objective:
Extract and authoritatively specify all technical specifications, data contracts, and schemas required by the requirements:
1. R1 Geocoding System: Open zero-config endpoints (US Census Bureau Geocoder, OSM Nominatim/Photon), request/response schemas, postal component normalization schema (street_number, street_name, city, state, zip5, lat, lng), and drop-in Google Places / Mapbox env configs.
2. R2 Hybrid Availability Engine:
   - FCC Broadband Data Collection (BDC) data formats and coverage mapping.
   - Distinct brand-level resolution rules: T-Mobile 5G Home Internet vs Metro by T-Mobile; Verizon 5G Home vs Straight Talk Home Internet vs Total Wireless; AT&T Internet Air; Starlink/satellite.
   - `IProviderChecker` interface contract: check method, input address/coordinates, timeout (1.5s max), fallback logic to FCC BDC data.
3. R3 Provider Catalog & Local Cache Layer:
   - SQLite schema via Drizzle ORM (brands, plans, pricing tiers, speeds, equipment requirements, official links).
   - In-memory LRU cache + coordinate lookup cache with configurable TTL.
4. R4 UI & API:
   - `GET /api/availability?address=...` JSON response schema.
   - UI component specifications, filtering/sorting criteria, fallback messaging.

Operating Constraints:
- Read-only exploration and specification mining. DO NOT write or modify implementation code.
- Maintain progress.md in your working directory with timestamps for liveness.
- Document detailed specifications in specs.md and summarize in handoff.md in your working directory.
- When finished, send a message to parent with your handoff summary and path to your handoff.md.
