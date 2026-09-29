# Handoff Report: Milestone 1 Geocoding Cascade & Address Normalization Blueprint

**Agent ID**: `explorer_m1_2`  
**Working Directory**: `/home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/explorer_m1_2`  
**Date**: 2026-09-29  
**Handoff Type**: Hard (Exploration & Design Task Complete)  

---

## 1. Observation

1. **User Request & Requirements**:
   - `ORIGINAL_REQUEST.md`: Lines 12-14: "R1. Address Intake & Pluggable Geocoding System: Build a responsive address intake interface using Next.js App Router (TypeScript, React, Tailwind CSS, and shadcn/ui). Implement a pluggable geocoding service with a zero-config open default (US Census Bureau Geocoder / OpenStreetMap Nominatim/Photon) and drop-in support for Google Places / Mapbox via environment variables. The service must normalize input addresses into standardized postal components and latitude/longitude coordinates."
   - `ORIGINAL_REQUEST.md`: Lines 32-35: Acceptance criteria specify: "Address search input provides autocomplete suggestions for valid US addresses without requiring paid API keys out of the box" and "Address submission successfully returns normalized components (`street_number`, `street_name`, `city`, `state`, `zip5`) and coordinates (`lat`, `lng`)."

2. **Project Specification Contracts**:
   - `PROJECT.md`: Lines 110-142 defines the Geocoder ↔ Normalizer Contract (`src/lib/geocoding/types.ts`):
     - `NormalizedAddress` (`streetNumber`, `streetName`, `unitNumber?`, `city`, `state`, `zip5`, `lat`, `lng`, `formattedAddress`).
     - `AddressSuggestion` (`id`, `label`, `streetLine`, `city`, `state`, `zip5?`, `lat?`, `lng?`, `source`).
     - `IGeocoderService` (`providerName`, `suggest`, `resolve`, `resolveCoordinates`).
   - `PROJECT.md`: Lines 267-275 lays out the exact file paths under `src/lib/geocoding/`:
     - `types.ts`, `normalizer.ts`, `census-geocoder.ts`, `photon-geocoder.ts`, `nominatim-geocoder.ts`, `google-geocoder.ts`, `mapbox-geocoder.ts`, `service.ts`.
   - `spec_miner_survey_2/specs.md`: Lines 29-176 details exact public REST schemas for US Census Bureau Geocoder (`/locations/onelineaddress`), Komoot Photon (`/api`), and OSM Nominatim (`/search`).
   - `spec_miner_survey_2/specs.md`: Lines 86 notes: "In Census Geocoder, `coordinates.x` is **Longitude** (negative for US) and `coordinates.y` is **Latitude**."
   - `spec_miner_survey_2/specs.md`: Lines 967-970 details edge case handling: PO Box rejection regex `/\bP(OST)?\s*O(FFICE)?\s*BOX\b/i` returning HTTP 400, multi-family unit extraction, and Census 2.5s timeout.

3. **Testing Harness Expectations**:
   - `explorer_survey_3/test_plan.md`: Lines 172-220 & `test_writer_track_1/DISPATCH.md`: Lines 17-18 assign `tests/unit/geocoding/normalizer.test.ts` (20+ test cases covering postal parsing, PO Box rejection, unit/apt extraction, fractional house numbers, rural grid addresses, and coordinate validation).

---

## 2. Logic Chain

1. **Pluggable & Zero-Config Architecture**:
   - *Observation 1 & 2*: Consumers must be able to run the application immediately after cloning without acquiring commercial API keys.
   - *Deduction*: The geocoding system must default to a three-tier open cascade: US Census Bureau (high accuracy physical postal addresses) -> Komoot Photon (fast search-as-you-type autocomplete and fallback) -> OSM Nominatim (secondary open fallback). Commercial adapters (Google Places and Mapbox) must check `isConfigured` dynamically based on environment variables (`GOOGLE_PLACES_API_KEY`, `MAPBOX_ACCESS_TOKEN`) and prepend to the cascade when available.

2. **Postal Normalization & Coordinate Integrity**:
   - *Observation 2 (Census coordinate mapping & specs)*: Census coordinates use `x` for longitude and `y` for latitude; GeoJSON uses `[lon, lat]`. Any inverted mapping would misplace coordinates by thousands of miles.
   - *Deduction*: Normalization must enforce strict typed parameter extraction: explicitly mapping Census `x` to `lng` and `y` to `lat`, and GeoJSON `coordinates[0]` to `lng` and `coordinates[1]` to `lat`. Furthermore, an explicit US territorial bounding box check (`17.5 <= lat <= 72.0` and `-179.0 <= lng <= -64.0`) guarantees immediate rejection of inverted or non-US coordinates.

3. **Strict PO Box & Street Number Validation**:
   - *Observation 2 (PO Box and street number constraints)*: 5G Home Internet and fixed wireless gateways require physical delivery to a serviced rooftop and line-of-sight cell sector propagation analysis. Gateways cannot be delivered or activated at PO Boxes.
   - *Deduction*: `AddressNormalizer` must detect PO Boxes via regex `/\b(?:P\.?\s*O\.?\s*BOX|POST\s+OFFICE\s+BOX|P\s*BOX|P\s*O\s*B)\b/i` and throw a dedicated `PoBoxError` with HTTP 400 status. In addition, addresses missing a street number must throw `MissingStreetNumberError` (HTTP 400), prompting the user for a valid building number.

4. **Multi-Unit / Apartment Segregation**:
   - *Observation 2 & 3*: Apartment dwellers query addresses like `"742 Evergreen Terrace Apt 4B"`. Passing `"Evergreen Terrace Apt 4B"` to geocoding services often results in failed geocode matches because the street name database only knows `"Evergreen Terrace"`.
   - *Deduction*: `AddressNormalizer.extractUnit()` isolates secondary unit identifiers (`Apt`, `Suite`, `Unit`, `#`, `Fl`) into `unitNumber: string | null` and cleans `streetName` prior to geocoding, preserving building centroid resolution while keeping the apartment number intact for customer order placement.

5. **Fault-Tolerant Cascade Execution**:
   - *Observation 2 (Census latency and availability)*: Government geocoders can occasionally experience latency spikes or service maintenance.
   - *Deduction*: `CensusGeocoder` must apply an `AbortController` timeout capped at 2500ms. If Census times out or returns 0 matches, the `GeocodingService` catches the exception and immediately falls back to Photon, followed by Nominatim, before throwing `AddressNotFoundError` (HTTP 400).

---

## 3. Caveats

1. **Non-Continental US Availability**:
   - While the normalizer supports Alaska, Hawaii, and Puerto Rico (`PR`), terrestrial 5G FWA (T-Mobile/Verizon) has distinct regional deployment profiles in non-continental territories; in those locations, the system will gracefully yield Starlink universal satellite availability.
2. **Census Bureau Autocomplete Limitations**:
   - The US Census Bureau Geocoding Services API is designed for batch and one-line full address geocoding, not keystroke-by-keystroke prefix autocomplete. Therefore, `suggest()` relies primarily on Google Places / Mapbox (when configured) or Komoot Photon as the zero-config autocomplete default.
3. **No Code Written to `src/`**:
   - In accordance with the Explorer read-only constraint, all blueprints, exact TypeScript code skeletons, and architectural designs have been documented exclusively in `analysis.md` and this handoff report. No files in `src/` or `tests/` were created or modified.

---

## 4. Conclusion

A complete, production-ready, fully typed blueprint for Milestone 1 Geocoding Cascade & Address Normalization has been designed and documented in `analysis.md`.

The blueprint provides comprehensive specifications for all 7 target files:
1. `src/lib/geocoding/types.ts`: `NormalizedAddress`, `AddressSuggestion`, `IGeocoderService`, `GeocodeOptions`, `SuggestOptions`, and structured custom error classes (`GeocodingError`, `AddressValidationError`, `PoBoxError`, `MissingStreetNumberError`, `AddressNotFoundError`, `OutOfBoundsError`).
2. `src/lib/geocoding/normalizer.ts`: `AddressNormalizer` with USPS state mapping (50 states + DC + territories), PO Box detection/rejection, apartment unit extraction, street number/fractional parsing, coordinate validation bounding box, and USPS single-line address assembly.
3. `src/lib/geocoding/census-geocoder.ts`: Client for US Census Bureau REST API with 2500ms timeout budget, component parsing, and protected `x=lng, y=lat` coordinate mapping.
4. `src/lib/geocoding/photon-geocoder.ts`: Komoot Photon GeoJSON client providing search-as-you-type autocomplete with continental US bounding box filtering (`-125,24,-66,49`) and address resolution.
5. `src/lib/geocoding/nominatim-geocoder.ts`: OpenStreetMap Nominatim fallback client with strict User-Agent header compliance, address decomposition, and reverse geocoding.
6. `src/lib/geocoding/google-geocoder.ts` & `src/lib/geocoding/mapbox-geocoder.ts`: Drop-in commercial adapters activated via `GOOGLE_PLACES_API_KEY` and `MAPBOX_ACCESS_TOKEN` with graceful error suppression.
7. `src/lib/geocoding/service.ts`: `GeocodingService` cascade orchestrator implementing `suggest()`, `resolve()`, and `resolveCoordinates()` with pre/post-validation and automatic failover.

The blueprint seamlessly connects with `spec_miner_m1_3`'s API routes (`/api/geocode/suggest`, `/api/geocode/resolve`), satisfies `test_writer_track_1`'s test specifications (`tests/unit/geocoding/normalizer.test.ts`), and prepares clean data for Milestone 2 (caching) and Milestone 3 (hybrid availability engine).

---

## 5. Verification Method

Once the implementation worker translates this blueprint into `src/lib/geocoding/`:

1. **Inspect Blueprint Artifacts**:
   - View `/home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/explorer_m1_2/analysis.md` for complete file implementations, interfaces, and algorithms.

2. **Automated Unit Test Execution**:
   - Run: `npm run test:unit` or `npx vitest run tests/unit/geocoding/normalizer.test.ts`.
   - Expected Result: 100% pass across all 20+ test cases covering standard parsing, unit extraction, ZIP+4 handling, PO Box rejection, fractional street numbers, and rural grid addresses.

3. **Integration Verification**:
   - Test zero-config autocomplete: Query `geocodingService.suggest("1600 Penn")` -> Returns Photon suggestions array with US addresses.
   - Test Census geocoding: Query `geocodingService.resolve("1600 Pennsylvania Ave NW, Washington, DC 20500")` -> Returns `NormalizedAddress` with `lat: ~38.8976`, `lng: ~-77.0365`, `state: "DC"`, `streetNumber: "1600"`.
   - Test PO Box rejection: Query `geocodingService.resolve("PO Box 1234, Dallas, TX 75201")` -> Throws `PoBoxError`.
   - Test Census timeout failover: Mock Census with 3000ms delay -> Orchestrator aborts at 2500ms and successfully resolves via Photon without throwing.

4. **Invalidation Conditions**:
   - The design is invalidated if Census coordinates are inverted (`x` assigned to `lat`), if PO Boxes are accepted without throwing `PoBoxError`, if unit numbers fail to be stripped from `streetName`, or if missing commercial API keys cause unhandled runtime exceptions.
