# Handoff Report — 5G Arbitrage Engine Specifications

**Agent**: `spec_miner_survey_2` (`teamwork_preview_spec_miner`)  
**Parent / Caller**: `097744dd-87b6-414e-a580-658af286e0dd` (`parent`)  
**Workspace**: `/home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint`  
**Working Directory**: `/home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/spec_miner_survey_2`  
**Date**: 2026-09-29  
**Type**: Hard Handoff (Task Complete)

---

## 1. Observation

1. **Original User Request & Requirements**:
   - `ORIGINAL_REQUEST.md:12-29`:
     - R1 requires Next.js App Router (TypeScript, React, Tailwind CSS, shadcn/ui) with a pluggable geocoding service featuring open zero-config defaults (US Census Bureau Geocoder / OpenStreetMap Nominatim/Photon) and drop-in Google Places / Mapbox env configs.
     - R2 requires backend availability engine combining FCC Broadband Data Collection (BDC) location-level data with `IProviderChecker`, recognizing distinct retail consumer brands (T-Mobile 5G Home vs Metro by T-Mobile; Verizon 5G Home vs Straight Talk vs Total Wireless; AT&T Internet Air; Starlink), with 1.5s max timeout and resilient fallback to FCC BDC data.
     - R3 requires SQLite + Drizzle ORM catalog for brands, plans, pricing tiers, speeds, equipment requirements, and official signup links, paired with an in-memory LRU cache and coordinate lookup cache with configurable TTL.
     - R4 requires interactive brand-level availability comparison UI and `GET /api/availability?address=...` returning in under 2 seconds.

2. **Authoritative Geocoding Endpoints**:
   - **US Census Bureau Geocoding Services API**:
     Endpoint: `https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?address={address}&benchmark=Public_AR_Current&format=json`. Zero API keys required. Returns `addressMatches` with `coordinates.x` (longitude) and `coordinates.y` (latitude), alongside granular `addressComponents` (`streetName`, `suffixType`, `city`, `state`, `zip`, etc.). Does not provide permissive CORS headers for client-side direct AJAX, necessitating server-side proxying via `/api/geocode`.
   - **Komoot Photon API**:
     Endpoint: `https://photon.komoot.io/api?q={query}&bbox=-125,24,-66,49&limit=5&lang=en`. Returns GeoJSON `FeatureCollection` with `Point` coordinates `[lng, lat]` and properties (`housenumber`, `street`, `postcode`, `city`, `state`, `country`).
   - **OSM Nominatim Search API**:
     Endpoint: `https://nominatim.openstreetmap.org/search?q={query}&format=jsonv2&addressdetails=1&countrycodes=us`. Requires a descriptive `User-Agent` header per OSM policy.

3. **FCC Broadband Data Collection (BDC) Specs**:
   - FCC BDC defines fixed wireless technology codes:
     - `71`: Licensed Terrestrial Fixed Wireless (MNO mid-band / mmWave 5G Home Internet).
     - `72`: Licensed-by-Rule Terrestrial Fixed Wireless (CBRS GAA).
     - `70`: Unlicensed Terrestrial Fixed Wireless (WISPs).
     - `61`: Non-Geostationary Satellite (SpaceX Starlink LEO).
     - `60`: Geostationary Satellite (Viasat/HughesNet).
   - Core BDC record attributes: `frn`, `provider_id`, `brand_name`, `technology`, `max_advertised_download_speed`, `max_advertised_upload_speed`, `low_latency`, `business_residential_code`, `latitude`, `longitude`.

4. **Multi-Brand Arbitrage Relationships**:
   - **T-Mobile Network**: T-Mobile 5G Home Internet (Postpaid, $50-$60/mo, included gateway, soft credit check) vs. Metro by T-Mobile 5G Home (Prepaid, $50-$55/mo, no credit check, gateway purchase $49-$99 promo).
   - **Verizon Network**: Verizon 5G Home Internet (Postpaid, $60-$80/mo or $35-$45 bundled, included gateway, soft credit check) vs. Straight Talk Home Internet (Prepaid Walmart exclusive, $45/mo flat or $40 autopay, $99 router purchase, 100 Mbps cap, no credit check) vs. Total Wireless Home Internet (Prepaid, $45-$60/mo or $35 bundled, $99 router, 200 Mbps cap, no credit check).
   - **AT&T Network**: AT&T Internet Air (Postpaid, $60/mo or $35-$47 bundled, All-Fi Hub included).
   - **Satellite Baseline**: Starlink Residential (Non-geostationary satellite, universal continental US coverage, $120/mo, $349-$599 equipment kit).

5. **Sandbox Runtime & File System State**:
   - `ORIGINAL_REQUEST.md` and repository root inspected; no source code or package.json files exist yet. The workspace is at blueprint/greenfield phase.
   - Node binary was not in `/usr/bin` within this sandbox, but `python3` is present. All specifications were mined and verified using authoritative upstream documentation and web search.

---

## 2. Logic Chain

1. **Geocoding Cascade & Normalization (R1)**:
   - *Premise*: Acceptance criteria stipulate that address autocomplete and geocoding must operate out of the box without paid API keys, yet support drop-in Google Places or Mapbox via environment variables.
   - *Deduction*: An `IGeocoderService` adapter pattern allows seamless runtime selection. If `GOOGLE_PLACES_API_KEY` or `MAPBOX_ACCESS_TOKEN` is detected, the commercial adapter handles requests. Otherwise, the zero-config open cascade triggers: Komoot Photon handles debounced search-as-you-type autocomplete, and US Census Bureau Geocoder handles final coordinate and postal decomposition, falling back to OSM Nominatim if needed.
   - *Result*: Standardized `NormalizedAddress` interface guarantees uniform inputs (`streetNumber`, `streetName`, `city`, `state`, `zip5`, `lat`, `lng`) to downstream engines regardless of which geocoder was invoked.

2. **Carrier Pre-Flight Checking with FCC Fallback (R2)**:
   - *Premise*: Live carrier address qualification APIs are prone to rate limiting, bot protection, and latency spikes, but the engine must return responses in under 2.0 seconds and never fail on carrier throttling.
   - *Deduction*: By bounding every provider checker to a strict 1.5-second timeout via `AbortController` and running them in parallel via `Promise.allSettled`, the system guarantees completion within the SLA. If a carrier endpoint aborts, throws HTTP 429, or fails, the checker catches the exception and inspects pre-loaded FCC BDC records for technology 71. If coverage is verified in FCC BDC, the status is resolved to `fallback_available` with `source: 'fcc_bdc_fallback'`.
   - *Result*: Zero single points of failure; 100% resilient response delivery.

3. **Distinct Brand Resolution Rules (R2/R3)**:
   - *Premise*: Consumers are often unaware that prepaid MVNO or sub-brand options run on the exact same physical cell towers as expensive postpaid services, or that prepaid brands offer no-credit-check alternatives.
   - *Deduction*: When T-Mobile 5G coverage is detected, the engine must emit both T-Mobile Postpaid and Metro Prepaid. When Verizon 5G coverage is detected, it must emit Verizon Postpaid, Straight Talk, and Total Wireless. Each must reference distinct plan rows in the SQLite catalog with separate pricing, equipment upfront costs ($0 rental vs $99 purchase), credit check requirements, and direct checkout URLs.
   - *Result*: Transparent consumer arbitrage comparison directly meeting R2 and R4 requirements.

4. **Multi-Tier Caching Architecture (R3)**:
   - *Premise*: Sub-second repeat response times are mandatory.
   - *Deduction*: Memory cache (L1) provides sub-5ms responses for identical address queries. SQLite coordinate cache (L2) with 4-decimal rounded coordinates (~11m spatial radius) provides sub-25ms responses for neighboring queries in the same building or parcel without re-invoking external APIs.

5. **API & UI Architecture (R4)**:
   - *Premise*: The UI needs to present high-density comparison data clearly with filtering by network family, account type (prepaid/postpaid), price, and speed, with fallback messaging for rural satellite-only locations.
   - *Deduction*: A structured JSON contract for `GET /api/availability` containing a summary banner, resolved address, execution telemetry, and an array of brand cards with arbitrage annotations enables full reactive filtering and sorting on the client.

---

## 3. Caveats

1. **CORS Restrictions on US Census Geocoder**: The US Census Bureau Geocoding API does not return CORS headers for direct browser execution. All client-side calls must be proxied through the Next.js server route (`/api/geocode`) or use Komoot Photon for client-side autocomplete.
2. **FCC BDC Location Fabric Licensing**: Raw BSL (Broadband Serviceable Location) fabric IDs are proprietary to CostQuest, but publicly available FCC BDC availability data aggregated by Census Block FIPS or geographic coordinates can be freely queried and stored in the local SQLite database.
3. **Carrier API Bot Protection**: Direct carrier check APIs (e.g. T-Mobile/Verizon coverage tools) change frontend anti-bot defenses over time. The engine's architecture relies on FCC BDC data as the rock-solid fallback foundation whenever live carrier endpoints block or throttle.

---

## 4. Conclusion

All specifications, data contracts, and schemas for Requirements R1 through R4 have been authoritatively defined, rigorously cross-referenced against authoritative sources, and compiled into `/home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/spec_miner_survey_2/specs.md`.

The deliverables provide full TypeScript definitions for:
- `NormalizedAddress`, `AddressSuggestion`, and `IGeocoderService` (R1)
- `IProviderChecker`, `ProviderCheckInput`, `ProviderCheckResult`, and FCC BDC technology codes (R2)
- Drizzle ORM SQLite tables `brands`, `plans`, `fcc_provider_mapping`, `coordinate_lookup_cache` (R3)
- Multi-tier L1 memory LRU + L2 SQLite coordinate caching (R3)
- `GET /api/availability` JSON response contract and error schemas (R4)
- Responsive UI component hierarchy and dynamic filtering/sorting behavior (R4)
- 21 discovered features and 12 edge cases fully documented.

---

## 5. Verification Method

To independently verify the completeness and accuracy of these specifications:

1. **Inspect Specification Artifacts**:
   - Inspect `/home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/spec_miner_survey_2/specs.md`.
   - Verify every requirement in `ORIGINAL_REQUEST.md` (R1, R2, R3, R4) has a corresponding section with typed interfaces and field mappings.
   - Verify that all distinct retail brands (`t-mobile-5g-home`, `metro-by-t-mobile-5g`, `verizon-5g-home`, `straight-talk-home-internet`, `total-wireless-home-internet`, `att-internet-air`, `starlink-residential`) are represented with their pricing, equipment models, and resolution rules.

2. **Verify Against Upstream Documentation**:
   - US Census Bureau Geocoder API: `https://geocoding.geo.census.gov/geocoder/locations/onelineaddress`
   - Komoot Photon API: `https://photon.komoot.io/api`
   - FCC BDC Technology Codes: 71 (Licensed Terrestrial Fixed Wireless), 72 (CBRS), 61 (LEO Satellite).

3. **Subsequent Implementation Verification**:
   - When the implementation agents build the application, verify that unit tests in `vitest` and E2E journeys in `playwright` test:
     - Address normalizer against edge case addresses (PO Box rejection, missing street number, apartment units).
     - Carrier timeout aborting at $\le 1500$ms and activating FCC BDC fallback.
     - `GET /api/availability` completing in $< 2000$ms on cold query and $< 50$ms on repeat query.
