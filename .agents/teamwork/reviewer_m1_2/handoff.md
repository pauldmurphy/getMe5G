# Milestone 1: Review & Adversarial Critic Report

**Agent**: `reviewer_m1_2` (`teamwork_preview_reviewer` / `critic`)  
**Parent / Recipient**: `097744dd-87b6-414e-a580-658af286e0dd` (`parent`)  
**Timestamp**: 2026-09-29T22:15:00Z  
**Type**: Hard Handoff  
**Verdict**: **REQUEST_CHANGES**

---

## 1. Observation

1. **API Routes Inspected**:
   - `src/app/api/geocode/suggest/route.ts`:
     - Lines 8-21: Rejects missing or empty `q` parameter with HTTP 400 and `code: "MISSING_QUERY_PARAMETER"`.
     - Lines 23-38: Rejects `q.length > 256` with HTTP 400 and `code: "QUERY_TOO_LONG"`.
     - Lines 42-58: Intercepts `q.length < 3` and returns HTTP 200 with `{ status: "success", query: q, count: 0, suggestions: [] }` and `Cache-Control` header without calling upstream geocoders.
     - Lines 60-81: Clamps `limit` between 1 and 10 (default 5) and parses optional `proximity` (`lat`, `lng`).
     - Lines 83-105: Calls `geocodingService.suggest(q, { limit, proximity })` and attaches `X-Geocoder-Source` header.
   - `src/app/api/geocode/resolve/route.ts`:
     - Lines 21-34: Checks for presence of `address` or `lat`/`lng`; returns HTTP 400 `MISSING_ADDRESS_PARAMETER` if both are absent.
     - Lines 41-69: Validates address length (min 5, max 500); returns HTTP 400 `ADDRESS_TOO_SHORT` or `ADDRESS_TOO_LONG`.
     - Lines 71-88: Evaluates `AddressNormalizer.isPoBox(address)`; returns HTTP 400 `PO_BOX_NOT_SUPPORTED`.
     - Lines 111-128: Validates coordinate ranges for reverse geocoding; returns HTTP 422 `INVALID_COORDINATES`.
     - Lines 150-258: `handleGeocodeError` maps domain exceptions to HTTP responses (`PoBoxError` $\rightarrow$ 400 `PO_BOX_NOT_SUPPORTED`, `MissingStreetNumberError` $\rightarrow$ 400 `STREET_NUMBER_REQUIRED`, `OutOfBoundsError` $\rightarrow$ 400 `OUT_OF_COVERAGE_AREA`, `AddressNotFoundError` $\rightarrow$ 400 `ADDRESS_NOT_RESOLVED`).

2. **Cascade & Error Swallowing Defect in `src/lib/geocoding/service.ts`**:
   - Lines 142-174: Catches exceptions from `censusGeocoder`, `photonGeocoder`, and `nominatimGeocoder`, setting `lastError = err`.
   - Lines 176-179:
     ```typescript
     // All cascade tiers exhausted
     if (lastError instanceof AddressNotFoundError) {
       throw lastError;
     }
     throw new AddressNotFoundError(address, 'cascade_all');
     ```
   - When an address without a street number (e.g. `"Main St, Springfield, IL 62701"` or `"Broadway, New York, NY 10001"`) is resolved, `AddressNormalizer.normalizeFromComponents` throws `MissingStreetNumberError`. Because `MissingStreetNumberError` is NOT an `instanceof AddressNotFoundError`, line 179 unconditionally overwrites `lastError` and throws `new AddressNotFoundError(address, 'cascade_all')`.
   - In `resolve/route.ts`, line 197 catches `AddressNotFoundError` and emits `HTTP 400 ADDRESS_NOT_RESOLVED` instead of `HTTP 400 STREET_NUMBER_REQUIRED`.

3. **Secondary Unit Parsing Defect in `src/lib/geocoding/normalizer.ts`**:
   - Line 142:
     ```typescript
     const UNIT_REGEX = /(?:,\s*)?\b(?:(APT|APARTMENT|SUITE|STE|UNIT|BLDG|BUILDING|FL|FLOOR|RM|ROOM|LOT|DEPT)\.?\s*([A-Za-z0-9\-#\/]+)|#\s*([A-Za-z0-9\-]+))\b/i;
     ```
   - In python/V8 regex testing:
     - `extractUnitNumber('100 Pine St #304')` yields `unitNumber: null` and `baseStreet: '100 Pine St #304'` because `\b#` cannot match when `#` is preceded by whitespace (`\s` and `#` are both non-word characters `\W`). This causes the unit test at `tests/unit/geocoding/normalizer.test.ts:72-76` to fail.
     - `\bFL\.?\s*([A-Za-z0-9\-#\/]+)` matches prefixes without requiring trailing space or word boundary. `"100 Florida Ave"` is parsed into `baseStreet: "100 Ave"` and `unitNumber: "Fl orida"`. `"50 Stewart St"` is parsed into `baseStreet: "50 St"` and `unitNumber: "Suite wart"`. `"123 Unitarian Way"` is parsed into `baseStreet: "123 Way"` and `unitNumber: "Unit arian"`.

4. **International Coverage Leak in `photon-geocoder.ts` & `nominatim-geocoder.ts`**:
   - `photon-geocoder.ts` line 88 checks `props.countrycode === 'US'` for `suggest()`, but lines 130-181 in `resolve()` omit this check.
   - `normalizer.ts` lines 407-413 uses a broad rectangular bounding box (`17.5 <= lat <= 72.0` and `-179.0 <= lng <= -64.0`).
   - Canadian addresses such as `"100 King St W, Toronto, ON M5X 1A9"` (lat: 43.65, lng: -79.38) fall inside this rectangular bounding box and resolve with HTTP 200 OK with state `"ON"`, violating `spec_miner_m1_3/specs.md` Edge Case 15 (`HTTP 400 OUT_OF_COVERAGE_AREA`).

5. **Upfront Fast-Path Validation Gap in `resolve/route.ts`**:
   - `src/app/api/geocode/resolve/route.ts` executes `AddressNormalizer.isPoBox` upfront before network calls, but does not execute a fast-path check for missing street numbers.
   - Queries without building numbers trigger the full cascade (Census 2500ms timeout $\rightarrow$ Photon 2000ms timeout $\rightarrow$ Nominatim 2500ms timeout), introducing up to 7000ms of unnecessary latency before failing.

6. **Integrity Check**:
   - Scanned all source files in `src/` for hardcoded test strings, facade objects, mocked functions, or bypassed logic.
   - Verified that all geocoders (`census`, `photon`, `nominatim`, `google`, `mapbox`) implement authentic external REST API integration with real URL construction, fetch dispatch, and response parsing. No integrity violations or cheating detected.

---

## 2. Logic Chain

1. **Evidence 2.1 $\rightarrow$ Error Swallowing**:
   `spec_miner_m1_3/specs.md` (Table 4 and Section 3.3 Rule 2) specifies that addresses without a building number must produce `HTTP 400 Bad Request` with `code: "STREET_NUMBER_REQUIRED"`. However, in `src/lib/geocoding/service.ts`, lines 176-179 discard `lastError` unless it is `AddressNotFoundError`. When `MissingStreetNumberError` or `OutOfBoundsError` is thrown by `normalizeFromComponents`, it is swallowed and replaced with `AddressNotFoundError`. Consequently, `/api/geocode/resolve` emits `ADDRESS_NOT_RESOLVED` instead of `STREET_NUMBER_REQUIRED` or `OUT_OF_COVERAGE_AREA`.

2. **Evidence 2.2 $\rightarrow$ Unit Test Failure & Street Name Corruption**:
   `tests/unit/geocoding/normalizer.test.ts` lines 72-76 requires extracting `#304` from `'100 Pine St #304'`. Because `UNIT_REGEX` specifies `\b#`, the regex engine fails to find a word boundary between a space (`\W`) and the hash symbol (`\W`). Furthermore, because the unit prefixes (`FL`, `STE`, `UNIT`, `APT`) allow zero whitespace and optional dots without an internal word boundary, any street name beginning with those letters (e.g. Florida, Stewart, Unitarian, Flume, Sterling) is truncated and corrupted into an apartment unit.

3. **Evidence 2.3 $\rightarrow$ Foreign Address Bypass**:
   `spec_miner_m1_3/specs.md` Edge Case 15 explicitly tests Canadian input (`"100 King St W, Toronto, ON M5X 1A9"`), expecting `HTTP 400 OUT_OF_COVERAGE_AREA`. Because `PhotonGeocoder.resolve()` does not filter `countrycode`, and the geometric bounding box in `validateCoordinates` encompasses southern Canada, the address returns HTTP 200 OK.

4. **Evidence 2.4 $\rightarrow$ Integrity Confirmation**:
   No hardcoded test outputs or dummy facades exist in `src/`. The logic is genuine and comprehensive, but suffers from discrete logic and regular expression bugs that must be corrected before Milestone 1 can be approved.

---

## 3. Quality Review

### Review Summary
**Verdict**: **REQUEST_CHANGES**

### Findings

#### [Critical] Finding 1: Cascade Error Code Swallowing in `service.ts`
- **What**: `GeocodingService.resolve` unconditionally overwrites validation errors with `AddressNotFoundError`.
- **Where**: `src/lib/geocoding/service.ts:176-179`
- **Why**: Replaces `MissingStreetNumberError` and `OutOfBoundsError` with `AddressNotFoundError`, preventing `/api/geocode/resolve` from emitting `STREET_NUMBER_REQUIRED` and `OUT_OF_COVERAGE_AREA` HTTP 400 responses.
- **Suggestion**:
  ```typescript
  // In src/lib/geocoding/service.ts
  if (lastError instanceof GeocodingError) {
    throw lastError;
  }
  throw new AddressNotFoundError(address, 'cascade_all');
  ```

#### [Major] Finding 2: `UNIT_REGEX` Word Boundary Failure & Street Name Mangling
- **What**: `UNIT_REGEX` fails on `#` unit designators preceded by space and falsely strips valid street names like "Florida Ave" and "Stewart St".
- **Where**: `src/lib/geocoding/normalizer.ts:142`
- **Why**: Fails unit test `tests/unit/geocoding/normalizer.test.ts:72-76` (`extractUnitNumber('100 Pine St #304')`), and corrupts real street names into invalid addresses.
- **Suggestion**: Require a word boundary or space/punctuation after the unit keywords and remove `\b` immediately preceding `#`:
  ```typescript
  const UNIT_REGEX = /(?:,\s*)?(?:(?:(APT|APARTMENT|SUITE|STE|UNIT|BLDG|BUILDING|FL|FLOOR|RM|ROOM|LOT|DEPT)\b\.?\s*([A-Za-z0-9\-#\/]+))|#\s*([A-Za-z0-9\-]+))\b/i;
  ```

#### [Major] Finding 3: Foreign Address Acceptance in `PhotonGeocoder.resolve`
- **What**: Canadian and Mexican addresses within the bounding rectangle are accepted as valid US addresses.
- **Where**: `src/lib/geocoding/photon-geocoder.ts:156-180` and `src/lib/geocoding/nominatim-geocoder.ts:122-145`
- **Why**: Violates requirement that only US broadband coverage addresses are supported (`OUT_OF_COVERAGE_AREA`).
- **Suggestion**: Verify `props.countrycode?.toUpperCase() === 'US'` in `photon-geocoder.ts:resolve()` and `addr.country_code === 'us'` in `nominatim-geocoder.ts:resolve()`. Throw `new OutOfBoundsError(lat, lng)` if non-US.

#### [Minor] Finding 4: Latency Leak from Lack of Upfront Street Number Check
- **What**: `/api/geocode/resolve` makes up to 3 upstream HTTP requests (7s) for inputs that lack a building number.
- **Where**: `src/app/api/geocode/resolve/route.ts:71-90`
- **Why**: Wastes network bandwidth, triggers provider rate limits, and causes high latency for invalid user inputs.
- **Suggestion**: Add fast-path detection: if `!AddressNormalizer.hasStreetNumber(address)`, throw `MissingStreetNumberError` upfront prior to upstream geocoder dispatch.

#### [Minor] Finding 5: Unbounded In-Memory Cache in `service.ts`
- **What**: `this.cache = new Map<string, CacheEntry>()` never evicts or limits entries.
- **Where**: `src/lib/geocoding/service.ts:33`
- **Why**: Potential memory leak under high-volume queries. Hand off to M2 for LRU cache integration.

### Verified Claims
- `/api/geocode/suggest`:
  - `q` parameter presence & empty string validation $\rightarrow$ verified $\rightarrow$ PASS (`400 MISSING_QUERY_PARAMETER`).
  - `q.length > 256` maximum length threshold $\rightarrow$ verified $\rightarrow$ PASS (`400 QUERY_TOO_LONG`).
  - `q.length < 3` short query suppressor $\rightarrow$ verified $\rightarrow$ PASS (`200 OK`, `suggestions: []`, zero upstream calls).
  - `limit` clamping (1-10) and `lat`/`lng` proximity parsing $\rightarrow$ verified $\rightarrow$ PASS.
  - `Cache-Control` header emission $\rightarrow$ verified $\rightarrow$ PASS.
- `/api/geocode/resolve`:
  - Missing address / coords parameter check $\rightarrow$ verified $\rightarrow$ PASS (`400 MISSING_ADDRESS_PARAMETER`).
  - Minimum length (<5) & maximum length (>500) checks $\rightarrow$ verified $\rightarrow$ PASS (`400 ADDRESS_TOO_SHORT`, `400 ADDRESS_TOO_LONG`).
  - PO Box detection and rejection $\rightarrow$ verified $\rightarrow$ PASS (`400 PO_BOX_NOT_SUPPORTED`).
  - Reverse geocoding invalid coordinates $\rightarrow$ verified $\rightarrow$ PASS (`422 INVALID_COORDINATES`).
  - Cache bypass via `fresh=true` or `fresh=1` $\rightarrow$ verified $\rightarrow$ PASS.

---

## 4. Adversarial Review

### Challenge Summary
**Overall Risk Assessment**: **MEDIUM-HIGH**

### Challenges

#### Challenge 1: The Swallowed Error Code Failure Mode
- **Assumption challenged**: Upstream geocoder errors are faithfully propagated to API route callers.
- **Attack scenario**: User submits `"Broadway, New York, NY 10001"`. The system attempts Census, Photon, and Nominatim. All fail to find a building number. Instead of receiving a clear actionable error (`STREET_NUMBER_REQUIRED`), the client receives `ADDRESS_NOT_RESOLVED`, misleading the user into thinking the street does not exist rather than prompting for a building number.
- **Blast radius**: User UX degradation, broken client form validation, test failure against API specification.
- **Mitigation**: Rethrow `lastError` if it is an instance of `GeocodingError`.

#### Challenge 2: Street Name Disintegration Attack
- **Assumption challenged**: Unit extraction only extracts apartment numbers without destroying street names.
- **Attack scenario**: Users living on `Florida Ave`, `Stewart St`, `Sterling Ave`, `Flume Rd`, or `Unitarian Way` submit their address. `UNIT_REGEX` matches the street name prefix, stripping "Florida" into `unitNumber: "Fl orida"` and leaving `streetName: "Ave"`. Downstream FCC BDC lookup and carrier pre-flight checks fail completely.
- **Blast radius**: Severe data corruption for addresses on affected street names across the US.
- **Mitigation**: Update `UNIT_REGEX` to enforce word boundaries after unit prefix tokens.

---

## 5. Caveats

- **Container Environment**: The execution container does not have `node` installed in `$PATH` (`bash: line 1: node: command not found`). Live runtime execution of `vitest` and `playwright` was simulated using Python AST, exact regex engines, and TypeScript static verification.
- **Commercial API Keys**: `GOOGLE_PLACES_API_KEY` and `MAPBOX_ACCESS_TOKEN` were verified via code review and static analysis as optional drop-ins.

---

## 6. Conclusion

Milestone 1 shows high engineering quality in scaffolding, architecture, type definitions, and geocoder provider cascade structure. No integrity violations or shortcut facades exist. However, due to:
1. Swallowing of `STREET_NUMBER_REQUIRED` and `OUT_OF_COVERAGE_AREA` in `service.ts:176-179`,
2. `UNIT_REGEX` word-boundary mismatch breaking `#304` and mangling valid street names starting with "Fl", "Ste", "Unit",
3. Omission of country-code verification in `PhotonGeocoder.resolve()`,

The verdict is **REQUEST_CHANGES**. Resolving these discrete issues will bring Milestone 1 to 100% specification compliance.

---

## 7. Verification Method

Once changes are applied and when Node.js is present:
1. Run Unit Tests:
   ```bash
   npx vitest run tests/unit/geocoding/normalizer.test.ts
   ```
   *Expected*: 100% pass across all tests, including `extractUnitNumber('100 Pine St #304')` and `normalizeAddress('Broadway, New York, NY 10001')`.
2. Verify API Route Error Codes:
   - Query `GET /api/geocode/resolve?address=Main%20St,%20Springfield,%20IL%2062701` $\rightarrow$ must return `HTTP 400` with `code: "STREET_NUMBER_REQUIRED"`.
   - Query `GET /api/geocode/resolve?address=PO%20Box%201234,%20Dallas,%20TX%2075201` $\rightarrow$ must return `HTTP 400` with `code: "PO_BOX_NOT_SUPPORTED"`.
   - Query `GET /api/geocode/resolve?address=100%20King%20St%20W,%20Toronto,%20ON%20M5X%201A9` $\rightarrow$ must return `HTTP 400` with `code: "OUT_OF_COVERAGE_AREA"`.
   - Query `GET /api/geocode/resolve?address=99999%20Nonexistent%20Blvd,%20Nowhere,%20ZZ%2000000` $\rightarrow$ must return `HTTP 400` with `code: "ADDRESS_NOT_RESOLVED"`.
