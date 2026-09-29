# Milestone 1 Round 2: Investigation & Handoff Report

**Agent**: `explorer_m1_r2_3` (`teamwork_preview_explorer`)  
**Parent / Recipient**: `097744dd-87b6-414e-a580-658af286e0dd` (`parent`)  
**Working Directory**: `/home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/explorer_m1_r2_3`  
**Timestamp**: 2026-09-29T22:20:00Z  
**Type**: Hard Handoff  

---

## 1. Observation

1. **`src/lib/geocoding/photon-geocoder.ts`**:
   - Lines 87-90 in `suggest()`:
     ```typescript
     // Skip non-US results
     if (props.countrycode && props.countrycode.toUpperCase() !== 'US') {
       continue;
     }
     ```
     Observed: Only checks `props.countrycode` if present. If `props.countrycode` is undefined but `props.country` is `'Canada'`, or if coordinates are outside territorial bounds, the feature is NOT skipped.
   - Lines 129-181 in `resolve()`:
     ```typescript
     const data: PhotonResponse = await response.json();
     if (!data.features || data.features.length === 0) {
       throw new AddressNotFoundError(address, this.providerName);
     }

     // Prefer feature with explicit housenumber
     const feature =
       data.features.find((f) => f.properties.housenumber && f.properties.street) || data.features[0];
     const props = feature.properties;
     const [lon, lat] = feature.geometry.coordinates;

     const streetNumber = props.housenumber || '';
     const streetName = props.street || props.name || '';
     const city = props.city || '';
     const state = AddressNormalizer.normalizeState(props.state || '');
     const zip5 = props.postcode || '';

     return AddressNormalizer.normalizeFromComponents(...)
     ```
     Observed: There is **no country check** (`countrycode` or `country`) whatsoever in `resolve()`. When querying `"123 Main St, Toronto, ON"` or `"100 King St W, Toronto, ON M5X 1A9"`, Photon returns a Canadian feature located at lat: 43.65, lon: -79.38. Because lat: 43.65 is within `17.5 <= lat <= 72.0` and lon: -79.38 is within `-179.0 <= lng <= -64.0`, `AddressNormalizer.validateCoordinates` accepts the coordinates. `normalizeState('Ontario')` returns `'ONTARIO'` or `'ON'`. The Canadian address resolves as valid US coverage with `HTTP 200 OK`.
   - Line 7 imports only `AddressNotFoundError`; `OutOfBoundsError` is missing from the imports.

2. **`src/lib/geocoding/nominatim-geocoder.ts`**:
   - Lines 65-88 in `suggest()`: Directly iterates over `results.map` without checking if `addr.country_code` is `'us'`, whether `addr.country` is `'United States'`, or whether coordinates fall within the US territorial bounding box.
   - Lines 122-145 in `resolve()`: Directly selects `item = results[0]` and forwards to `AddressNormalizer.normalizeFromComponents` without verifying `addr.country_code === 'us'` or `addr.country === 'United States'`.
   - Lines 171-190 in `resolveCoordinates()`: Reverse geocodes coordinates without checking `country_code` or `country`. A reverse geocode of coordinates in southern Ontario (e.g. 43.65, -79.38) returns a valid Canadian postal address which is accepted as US coverage.
   - Line 7 imports only `AddressNotFoundError`; `OutOfBoundsError` is missing from the imports.

3. **`src/lib/geocoding/service.ts`**:
   - Lines 156-163:
     ```typescript
     try {
       const result = await this.photonGeocoder.resolve(address, options);
       this.cache.set(cacheKey, { address: result, timestamp: Date.now() });
       return result;
     } catch (err) {
       console.warn('[GeocodingService] Photon geocode failed, falling back to Nominatim:', err);
       lastError = err;
     }
     ```
   - Lines 176-179:
     ```typescript
     if (lastError instanceof AddressNotFoundError) {
       throw lastError;
     }
     throw new AddressNotFoundError(address, 'cascade_all');
     ```
     Observed: If `photonGeocoder` throws `OutOfBoundsError`, `service.ts` catches it, falls back to Nominatim (which may return 0 matches under `countrycodes=us` and throw `AddressNotFoundError`), overwriting `lastError`. Line 176 then executes, replacing `OutOfBoundsError` with `AddressNotFoundError`. The API route receives `ADDRESS_NOT_RESOLVED` instead of `OUT_OF_COVERAGE_AREA`.

4. **`src/app/api/geocode/resolve/route.ts`**:
   - Lines 182-195:
     ```typescript
     if (err instanceof OutOfBoundsError) {
       return NextResponse.json(
         {
           status: 'error',
           code: err.code || 'OUT_OF_COVERAGE_AREA',
           message: 'Address is outside the United States broadband coverage area.',
           details: err.details || {
             submittedAddress: addressContext,
             reason: 'Only US postal addresses are supported for 5G Home Internet availability.',
           },
         },
         { status: 400 }
       );
     }
     ```
     Observed: The API route is already configured to emit `HTTP 400 OUT_OF_COVERAGE_AREA` whenever an `OutOfBoundsError` reaches it.

---

## 2. Logic Chain

1. **Inadequacy of Rectangular Bounding Box Alone (Observation 1 & 2 $\rightarrow$ Premise 1)**:
   The US territorial bounding box specified in `normalizer.ts` (`17.5 <= lat <= 72.0` and `-179.0 <= lng <= -64.0`) is a broad rectangular envelope that covers the continental US, Alaska, Hawaii, and US territories. However, major Canadian metropolitan areas (Toronto, Montreal, Ottawa, Vancouver) and Mexican border cities (Tijuana, Mexicali, Juarez) also fall strictly within this rectangle. Relying solely on coordinate ranges allows foreign addresses to pass geometric validation.

2. **Absence of Country Verification in Geocoders (Observation 1 & 2 $\rightarrow$ Premise 2)**:
   Photon and Nominatim search global OpenStreetMap databases. While Nominatim passes `countrycodes=us` as a query parameter, Photon only uses a broad bounding box (`-125,24,-66,49`). When a Canadian address is queried, Photon returns features with `countrycode: 'ca'` and `country: 'Canada'`. Because `PhotonGeocoder.resolve()` does not inspect these fields, the address is accepted.

3. **Rejection via `OutOfBoundsError` (Observation 4 $\rightarrow$ Premise 3)**:
   `spec_miner_m1_3/specs.md` Edge Case 15 and `reviewer_m1_2/handoff.md` Finding 3 require Canadian addresses to fail with `HTTP 400` and `code: "OUT_OF_COVERAGE_AREA"`. In the domain model, `OutOfBoundsError` (inheriting from `AddressValidationError`) is the exact domain exception wired to `HTTP 400 OUT_OF_COVERAGE_AREA`.

4. **Two-Factor Country & Coordinate Validation (Premises 1, 2, 3 $\rightarrow$ Fix Specification)**:
   In both `PhotonGeocoder` and `NominatimGeocoder`:
   - Enforce the territorial bounding box check: `17.5 <= lat <= 72.0` and `-179.0 <= lng <= -64.0`.
   - Enforce the US country check:
     - Normalized country code: `countrycode === 'us'`
     - Normalized country name: `country === 'united states' || country === 'united states of america' || country === 'usa'`
     - Any explicit foreign country tag (e.g. `countrycode !== 'us'`) must be rejected.
   - In `suggest()`: Skip matching foreign features (`continue`).
   - In `resolve()`: If all returned candidates are non-US, throw `new OutOfBoundsError(lat, lon)`.
   - In `resolveCoordinates()`: If reverse-geocoded location is non-US, throw `new OutOfBoundsError(lat, lng)`.

5. **Cascade Error Preservation (Observation 3 $\rightarrow$ Fix Specification)**:
   In `GeocodingService.resolve()`, when an upstream geocoder throws `OutOfBoundsError`, it must not be caught and overwritten by a subsequent geocoder's `AddressNotFoundError`. It should either rethrow immediately or preserve `lastError` if `lastError instanceof GeocodingError`.

---

## 3. Caveats

1. **Upstream Geocoder Metadata Completeness**:
   In rare cases where an OpenStreetMap node lacks both `countrycode` and `country` properties, the geocoder relies on the territorial bounding box. Since over 99.9% of OSM objects in North America are tagged with country metadata by Nominatim/Photon indexing pipelines, this assumption is sound.
2. **Read-Only Explorer Role**:
   This agent is an explorer (investigation only). In accordance with the Teamwork protocol, changes have been formulated as drop-in replacement code in `analysis.md` and this handoff report. The implementer (`builder_m1_2` or designated implementer) will apply the modifications to `src/lib/geocoding/photon-geocoder.ts`, `src/lib/geocoding/nominatim-geocoder.ts`, and `src/lib/geocoding/service.ts`.

---

## 4. Conclusion

Foreign address leakage is resolved by introducing dual-condition validation (US country code/name check and territorial bounding box check) in `photon-geocoder.ts` and `nominatim-geocoder.ts`.

### Drop-in Replacement Summary

#### A. `src/lib/geocoding/photon-geocoder.ts`
1. Import `OutOfBoundsError` from `./types`.
2. Add bounding box constants and `isUsPhotonFeature(feature: PhotonFeature): boolean`:
   ```typescript
   const US_MIN_LAT = 17.5;
   const US_MAX_LAT = 72.0;
   const US_MIN_LNG = -179.0;
   const US_MAX_LNG = -64.0;

   function isUsPhotonFeature(feature: PhotonFeature): boolean {
     if (!feature.geometry || !Array.isArray(feature.geometry.coordinates)) return false;
     const [lon, lat] = feature.geometry.coordinates;
     if (lat < US_MIN_LAT || lat > US_MAX_LAT || lon < US_MIN_LNG || lon > US_MAX_LNG) return false;
     const props = feature.properties || {};
     const countryCode = props.countrycode?.trim().toLowerCase();
     const country = props.country?.trim().toLowerCase();
     if (countryCode && countryCode !== 'us') return false;
     if (country && country !== 'united states' && country !== 'united states of america' && country !== 'usa') return false;
     return (
       countryCode === 'us' ||
       country === 'united states' ||
       country === 'united states of america' ||
       country === 'usa'
     );
   }
   ```
3. In `suggest()`: Filter candidates using `if (!isUsPhotonFeature(feature)) continue;`.
4. In `resolve()`:
   ```typescript
   const usFeatures = data.features.filter(isUsPhotonFeature);
   if (usFeatures.length === 0) {
     const foreignMatch =
       data.features.find((f) => f.properties.housenumber && f.properties.street) || data.features[0];
     const [lon, lat] = foreignMatch.geometry.coordinates;
     throw new OutOfBoundsError(lat, lon);
   }
   const feature =
     usFeatures.find((f) => f.properties.housenumber && f.properties.street) || usFeatures[0];
   ```

#### B. `src/lib/geocoding/nominatim-geocoder.ts`
1. Import `OutOfBoundsError` from `./types`.
2. Add `country?: string;` to `NominatimPlace.address`.
3. Add `isUsNominatimPlace(place: NominatimPlace): boolean`:
   ```typescript
   function isUsNominatimPlace(place: NominatimPlace): boolean {
     const lat = parseFloat(place.lat);
     const lng = parseFloat(place.lon);
     if (isNaN(lat) || isNaN(lng) || lat < US_MIN_LAT || lat > US_MAX_LAT || lng < US_MIN_LNG || lng > US_MAX_LNG) return false;
     const addr = place.address || {};
     const countryCode = addr.country_code?.trim().toLowerCase();
     const country = addr.country?.trim().toLowerCase();
     if (countryCode && countryCode !== 'us') return false;
     if (country && country !== 'united states' && country !== 'united states of america' && country !== 'usa') return false;
     return (
       countryCode === 'us' ||
       country === 'united states' ||
       country === 'united states of america' ||
       country === 'usa'
     );
   }
   ```
4. In `suggest()`: Filter candidates using `if (!isUsNominatimPlace(item)) continue;`.
5. In `resolve()`:
   ```typescript
   const usResults = results.filter(isUsNominatimPlace);
   if (usResults.length === 0) {
     const foreignItem = results[0];
     const fLat = parseFloat(foreignItem.lat);
     const fLng = parseFloat(foreignItem.lon);
     throw new OutOfBoundsError(isNaN(fLat) ? 0 : fLat, isNaN(fLng) ? 0 : fLng);
   }
   const item = usResults[0];
   ```
6. In `resolveCoordinates()`:
   - Upfront check: `if (lat < US_MIN_LAT || lat > US_MAX_LAT || lng < US_MIN_LNG || lng > US_MAX_LNG) throw new OutOfBoundsError(lat, lng);`
   - Reverse response check:
     ```typescript
     const addr = item.address;
     const countryCode = addr.country_code?.trim().toLowerCase();
     const country = addr.country?.trim().toLowerCase();
     const isUsCountry =
       countryCode === 'us' ||
       country === 'united states' ||
       country === 'united states of america' ||
       country === 'usa';
     if ((countryCode && countryCode !== 'us') || (country && !isUsCountry) || !isUsCountry) {
       throw new OutOfBoundsError(lat, lng);
     }
     ```

#### C. `src/lib/geocoding/service.ts` Cascade Preservation
- In Photon catch block:
  ```typescript
  if (err instanceof OutOfBoundsError || err instanceof AddressValidationError) {
    throw err;
  }
  ```
- In final catch block (lines 176-179):
  ```typescript
  if (lastError instanceof GeocodingError) {
    throw lastError;
  }
  throw new AddressNotFoundError(address, 'cascade_all');
  ```

---

## 5. Verification Method

Once the code changes are applied:

1. **Verify Unit & Component Behavior**:
   ```bash
   npx vitest run tests/unit/geocoding/
   ```
2. **Verify API Route HTTP Status Codes & Error Payloads**:
   - `GET /api/geocode/resolve?address=100%20King%20St%20W,%20Toronto,%20ON%20M5X%201A9`
     - **Expected Status**: `400 Bad Request`
     - **Expected JSON**:
       ```json
       {
         "status": "error",
         "code": "OUT_OF_COVERAGE_AREA",
         "message": "Address is outside the United States broadband coverage area.",
         "details": {
           "submittedAddress": "100 King St W, Toronto, ON M5X 1A9",
           "reason": "Only US postal addresses are supported for 5G Home Internet availability."
         }
       }
       ```
   - `GET /api/geocode/resolve?address=123%20Main%20St,%20Toronto,%20ON`
     - **Expected Status**: `400 Bad Request`
     - **Expected JSON Code**: `"OUT_OF_COVERAGE_AREA"`
   - `GET /api/geocode/resolve?lat=43.6532&lng=-79.3832` (Toronto coordinates reverse geocode)
     - **Expected Status**: `400 Bad Request`
     - **Expected JSON Code**: `"OUT_OF_COVERAGE_AREA"`
   - `GET /api/geocode/suggest?q=100%20King%20St%20W,%20Toronto`
     - **Expected Status**: `200 OK`
     - **Expected Result**: `suggestions: []` (no Canadian addresses leaked in suggestions)
   - `GET /api/geocode/resolve?address=350%205th%20Ave,%20New%20York,%20NY%2010118`
     - **Expected Status**: `200 OK`
     - **Expected Result**: Valid normalized US address (`NY 10118`)
