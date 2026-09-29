# Changes Applied — Milestone 1 Iteration 2

**Agent**: `worker_m1_2` (`teamwork_preview_worker`)  
**Timestamp**: 2026-09-29T22:26:00Z  

## Target Files Modified

1. `src/lib/geocoding/normalizer.ts`
2. `src/lib/geocoding/service.ts`
3. `src/lib/geocoding/photon-geocoder.ts`
4. `src/lib/geocoding/nominatim-geocoder.ts`

---

## Detailed Summary of Changes

### 1. `src/lib/geocoding/normalizer.ts`
- **PO Box Regex Enhancement**:
  - Modified `PO_BOX_REGEX` to match `P BOX` variations (`\b(?:P(?:OST)?\.?\s*(?:O(?:FFICE)?\.?\s*)?BOX|P\.?\s*O\.?\s*B(?:\.|\b)|POST\s+OFFICE\s+DRAWER|PBOX)\b`).
  - Added PO Box check on `streetNumber` in `AddressNormalizer.normalizeFromComponents` (`this.isPoBox(streetNumber)`).
- **Unit Parsing & `#` Symbol Support**:
  - Modified `UNIT_REGEX` so that the word boundary `\b` is inside keyword alternations, preventing non-word `#` boundary failure (`#304`, `#5`).
  - Ordered compound keywords before short aliases (`FLOOR` before `FL`, `APARTMENT` before `APT`, `SUITE` before `STE`, `BUILDING` before `BLDG`).
  - Added standalone comma segment extraction for secondary units (e.g. `"123 Main St, Apt 4B, New York, NY 10001"` correctly separates unit `"Apt 4B"` and leaves city as `"New York"`).
- **Security & Sanitization**:
  - Added stripping of arbitrary HTML tags (`cleaned.replace(/<[^>]+>/g, '').trim()`) to eliminate `<img onerror>` vectors.
  - Enhanced SQL injection stripping regex with boundary options.
- **Postal Validation**:
  - In `AddressNormalizer.parseZip`, returned `{ zip5: '', zip4: null }` when neither digits nor zip regex match, eliminating state code duplication into zip5.
  - In `AddressNormalizer.standardizeStreetName`, computed `suffixIndex` based on post-directional presence (`hasPostDirectional ? len - 2 : len - 1`), preventing street names like `"Court Street"` from being corrupted to `"Ct Street"`.

### 2. `src/lib/geocoding/service.ts`
- **Imported `GeocodingError`**:
  - Added `GeocodingError` to `./types` imports.
- **Immediate Fail-Fast in Cascade Catch Blocks**:
  - Added `if (err instanceof AddressValidationError) throw err;` in:
    - Google Geocoder catch block
    - Mapbox Geocoder catch block
    - Census Geocoder catch block
    - Photon Geocoder catch block
    - Nominatim Geocoder catch block
    - Reverse geocoding in `resolveCoordinates`
  - Eliminates unnecessary multi-second cascades when user inputs are inherently invalid (missing street number, PO Box, out of coverage).
- **Cascade Exhaustion Preservation**:
  - Rethrows `lastError` if it is an instance of `AddressValidationError`, `AddressNotFoundError`, or `GeocodingError`.
  - Prevents overwriting validation domain exceptions with generic synthetic `AddressNotFoundError`.

### 3. `src/lib/geocoding/photon-geocoder.ts`
- **Imported `OutOfBoundsError`**:
  - Added `OutOfBoundsError` to `./types` imports.
- **Territorial Bounding Box & Country Filter Function**:
  - Added US territorial bounding box constants (`US_MIN_LAT = 17.5`, `US_MAX_LAT = 72.0`, `US_MIN_LNG = -179.0`, `US_MAX_LNG = -64.0`).
  - Implemented `isUsPhotonFeature(feature: PhotonFeature): boolean` validating coordinate boundaries and verifying `countrycode === 'us'` or `country` is United States.
- **Filtering in `suggest()`**:
  - Replaced loose check with `isUsPhotonFeature` check to omit foreign addresses from autocomplete suggestions.
- **Foreign Address Rejection in `resolve()`**:
  - Filtered candidates using `isUsPhotonFeature`.
  - If matches exist but all are foreign (e.g. Toronto, Canada), throws `new OutOfBoundsError(lat, lon)` using coordinates from the best match, triggering HTTP 400 `OUT_OF_COVERAGE_AREA`.

### 4. `src/lib/geocoding/nominatim-geocoder.ts`
- **Imported `OutOfBoundsError`**:
  - Added `OutOfBoundsError` to `./types` imports.
- **Added `country?: string;` to `NominatimPlace.address`**.
- **Territorial Bounding Box & Country Filter Function**:
  - Added US territorial bounding box constants.
  - Implemented `isUsNominatimPlace(place: NominatimPlace): boolean` validating coordinate boundaries and verifying `country_code === 'us'` or `country` is United States.
- **Filtering in `suggest()`**:
  - Skipped non-US results using `isUsNominatimPlace`.
- **Foreign Address Rejection in `resolve()`**:
  - Increased query limit to `3` to evaluate top candidates.
  - Filtered candidates with `isUsNominatimPlace`.
  - If candidates exist but all are foreign, throws `new OutOfBoundsError(fLat, fLng)`.
- **Reverse Geocoding Bounds & Country Enforcement**:
  - Added upfront bounding box check in `resolveCoordinates` throwing `OutOfBoundsError`.
  - Added reverse geocoded address country check verifying US sovereignty, throwing `OutOfBoundsError` on non-US reverse results.

---

## Verification
- Executed `python3 .agents/teamwork/explorer_m1_r2_1/verify_patch.py`:
  - Stress suite: 36 passed, 0 failed.
  - Reviewer unit suite: 69 passed, 0 failed.
- Executed `python3 .agents/teamwork/worker_m1_2/verify_all.py`:
  - All 4 modified source files verified against regex, syntax, error preservation, and country bounds logic with 100% pass rate.
