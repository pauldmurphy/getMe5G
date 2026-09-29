# Handoff Report: Milestone 1 Geocoding API Routes & Edge Cases (`spec_miner_m1_3`)

**Author**: `spec_miner_m1_3`  
**Working Directory**: `/home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/spec_miner_m1_3`  
**Target Milestone**: Milestone 1 (Address Intake & Pluggable Geocoding System)  
**Date**: 2026-09-29  
**Specification File**: `.agents/teamwork/spec_miner_m1_3/specs.md`

---

## 1. Observation

1. **`ORIGINAL_REQUEST.md` (lines 12–14, 32–35)**:
   - *"R1. Address Intake & Pluggable Geocoding System: Build a responsive address intake interface using Next.js App Router (TypeScript, React, Tailwind CSS, and shadcn/ui). Implement a pluggable geocoding service with a zero-config open default (US Census Bureau Geocoder / OpenStreetMap Nominatim/Photon) and drop-in support for Google Places / Mapbox via environment variables. The service must normalize input addresses into standardized postal components and latitude/longitude coordinates."*
   - Acceptance Criteria: *"Address search input provides autocomplete suggestions for valid US addresses without requiring paid API keys out of the box."* and *"Address submission successfully returns normalized components (`street_number`, `street_name`, `city`, `state`, `zip5`) and coordinates (`lat`, `lng`)."*

2. **`PROJECT.md` (lines 73, 110–142, 254–256)**:
   - Lists Feature #7: *"Geocoding API Routes: `/api/geocode/suggest` and `/api/geocode/resolve` internal proxy routes"*.
   - Specifies Interface Contracts:
     - `NormalizedAddress`: `{ streetNumber: string; streetName: string; unitNumber?: string; city: string; state: string; zip5: string; lat: number; lng: number; formattedAddress: string; }`
     - `AddressSuggestion`: `{ id: string; label: string; streetLine: string; city: string; state: string; zip5?: string; lat?: number; lng?: number; source: 'photon' | 'census' | 'nominatim' | 'google' | 'mapbox'; }`
     - `IGeocoderService`: `{ suggest(query: string, limit?: number): Promise<AddressSuggestion[]>; resolve(address: string): Promise<NormalizedAddress>; resolveCoordinates(lat: number, lng: number): Promise<NormalizedAddress>; }`
   - Defines route file paths: `src/app/api/geocode/suggest/route.ts` and `src/app/api/geocode/resolve/route.ts`.

3. **`spec_miner_survey_2/specs.md` (lines 29–87, 88–130, 132–176, 828–839, 963–979)**:
   - Documents the US Census Bureau Geocoder API schema: coordinates returned as `coordinates.x` (Longitude) and `coordinates.y` (Latitude).
   - Documents Komoot Photon API schema (`FeatureCollection` with bounding box `bbox=-125,24,-66,49`).
   - Documents OpenStreetMap Nominatim API requirements: mandatory `User-Agent: GetMe5G-ArbitrageEngine/1.0 (contact@getme5g.local)` to avoid HTTP 429.
   - Discloses crucial edge cases:
     - PO Box rejection regex `/\bP(OST)?\s*O(FFICE)?\s*BOX\b/i` because 5G home gateways require physical rooftop coordinates for radio frequency propagation.
     - Missing street number handling returning `400 Bad Request` (`STREET_NUMBER_REQUIRED`).
     - Census Geocoder coordinate inversion guard (`x` = longitude, `y` = latitude).

4. **Peer Subagent Coordination**:
   - `explorer_m1_1` is responsible for project scaffolding, configurations (`package.json`, `tsconfig.json`, `tailwind.config.ts`, `vitest.config.ts`).
   - `explorer_m1_2` is responsible for core library modules (`src/lib/geocoding/*`).
   - `test_writer_track_1` is responsible for `tests/unit/geocoding/normalizer.test.ts` and mock fixtures in `tests/fixtures/addresses.json`.

---

## 2. Logic Chain

1. **Need for Dedicated Next.js Internal Proxy Routes**:
   - External open geocoders (such as the US Census Bureau Geocoder) do not provide permissive browser CORS headers, making direct client-side browser fetches fail.
   - Exposing commercial API keys (Google Maps / Mapbox) directly to client browsers introduces severe security and financial leak risks.
   - Therefore, Next.js internal App Router endpoints `GET /api/geocode/suggest` and `GET /api/geocode/resolve` must act as secure, CORS-compliant server-side proxies and validation filters.

2. **Debouncing & Query Limits in `/api/geocode/suggest`**:
   - User typing in `AddressSearchBar.tsx` emits rapid input events (200–500ms intervals).
   - Direct requests for single characters (e.g. `"1"`, `"16"`) produce high-entropy, meaningless results and unnecessarily consume rate limits on free public APIs (Komoot Photon / Nominatim).
   - Therefore, a double protection layer is required:
     - **Client-Side**: 300ms debounce timer + `AbortController` cancellation of previous in-flight requests.
     - **Server-Side**: If `q.trim().length < 3`, the route returns `HTTP 200 OK` with an empty array `{"suggestions": []}` immediately, bypassing upstream network calls. If `q` is absent, it returns `HTTP 400 Bad Request`.
     - Limits: Default limit is 5 suggestions, with a maximum clamp of 10 (`limit = Math.min(Math.max(limit, 1), 10)`).

3. **Domain-Specific Validation in `/api/geocode/resolve`**:
   - Unlike generic geocoders that accept PO Boxes or bare street names, 5G Home Internet availability relies on cellular RF propagation from cell towers to rooftop or window receiver units.
   - PO Boxes have no discrete cellular coordinates and telecom carriers refuse gateway shipments to them. Thus, regex pre-validation must intercept PO Boxes before calling geocoders, returning `HTTP 400 Bad Request` with `code: "PO_BOX_NOT_SUPPORTED"`.
   - Bare street intersections or street centerlines (e.g. `"Main St, Springfield, IL"`) lack rooftop precision; they must be rejected with `HTTP 400 Bad Request` and `code: "STREET_NUMBER_REQUIRED"`.

4. **Multi-Stage Geocoder Cascade Resilience**:
   - Upstream public services can suffer transient downtime or rate limits (e.g. Census Geocoder 503 or latency >2.5s).
   - The cascade orchestrator must execute a prioritized fallback:
     - Priority 1: Drop-in commercial adapter if env vars are present (`GOOGLE_PLACES_API_KEY` or `MAPBOX_ACCESS_TOKEN`).
     - Priority 2 (Default Zero-Config): US Census Bureau Geocoder (`/locations/onelineaddress`) with 2.5s timeout.
     - Priority 3: Komoot Photon API (`photon.komoot.io/api`) with 2.0s timeout.
     - Priority 4: OSM Nominatim (`nominatim.openstreetmap.org/search`) with 2.5s timeout and compliant `User-Agent`.
   - Any single upstream failure must be caught, logged, and seamlessly escalated to the next stage without returning an unhandled 500 server error to the user.

5. **Coordinate Inversion Prevention**:
   - Census Geocoder returns `{ "x": -77.03653, "y": 38.897675 }`.
   - In geographic systems, standard GeoJSON and Cartesian coordinates use `(x, y) = (lng, lat)`.
   - If accidentally assigned as `lat = x` and `lng = y`, latitude becomes `-77.0` (Antarctica), corrupting subsequent FCC BDC queries.
   - The specification mandates explicit mapping: `lat = coordinates.y`, `lng = coordinates.x`.

---

## 3. Caveats

- **Upstream Rate Limiting on Nominatim**: Nominatim has an official policy of max 1 request per second. The cascade uses Nominatim purely as a tertiary fallback behind the US Census Geocoder and Komoot Photon, minimizing traffic.
- **US Coverage Boundary**: The engine is strictly architected for US broadband availability (including PR). International addresses return `HTTP 400 Bad Request` (`OUT_OF_COVERAGE_AREA`).
- **Unit/Apartment Precision**: While unit numbers (e.g. `Apt 4B`) are extracted and preserved for checkout/signup flow, RF cell sector propagation evaluates the building's physical rooftop footprint.

---

## 4. Conclusion

The specification for `GET /api/geocode/suggest` and `GET /api/geocode/resolve` is fully documented in `.agents/teamwork/spec_miner_m1_3/specs.md`. It provides:
1. Complete parameter specifications, typing, default values, bounds, and sanitization rules.
2. Complete JSON schemas for both successful operations (`200 OK`) and validation failures (`400 Bad Request`, `422 Unprocessable Entity`, `502 Bad Gateway`, `504 Gateway Timeout`).
3. Concrete rules for PO Box rejection, building number enforcement, apartment unit segregation, ZIP+4 handling, and Census coordinate inversion guards.
4. An authoritative table of 15 discovered features and 30 granular edge cases with verified behaviors.

---

## 5. Verification Method

1. **Inspect Specification Artifact**:
   - Check file `.agents/teamwork/spec_miner_m1_3/specs.md` for complete schema definitions, status codes, and edge case directory.
2. **Unit Test Verification (`vitest`)**:
   - Once workers implement `normalizer.ts` and test writers implement `tests/unit/geocoding/normalizer.test.ts`, run:
     ```bash
     npx vitest run tests/unit/geocoding/normalizer.test.ts
     ```
   - Ensure all edge cases (PO Box variations, missing street number, apartment units, Queens hyphenated numbers, Census coordinate inversion) pass.
3. **Route Integration Verification**:
   - Once route handlers are implemented in `src/app/api/geocode/suggest/route.ts` and `src/app/api/geocode/resolve/route.ts`, verify with HTTP requests:
     ```bash
     # 1. Autocomplete short query test (returns empty suggestions, status 200)
     curl -i "http://localhost:3000/api/geocode/suggest?q=16"
     
     # 2. Autocomplete valid query test (returns suggestions, status 200)
     curl -i "http://localhost:3000/api/geocode/suggest?q=1600+Pennsylvania+Ave"
     
     # 3. PO Box rejection test (returns status 400 with PO_BOX_NOT_SUPPORTED)
     curl -i "http://localhost:3000/api/geocode/resolve?address=PO+Box+1234,+Dallas,+TX+75201"
     
     # 4. Missing street number test (returns status 400 with STREET_NUMBER_REQUIRED)
     curl -i "http://localhost:3000/api/geocode/resolve?address=Main+St,+Springfield,+IL+62701"
     
     # 5. Valid resolution test (returns status 200 with NormalizedAddress)
     curl -i "http://localhost:3000/api/geocode/resolve?address=1600+Pennsylvania+Ave+NW,+Washington,+DC+20500"
     ```
