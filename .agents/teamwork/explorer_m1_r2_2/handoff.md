# Handoff Report: Geocoding Service Error Handling Fix

**Agent**: `explorer_m1_r2_2` (`teamwork_preview_explorer`)  
**Parent / Recipient**: `097744dd-87b6-414e-a580-658af286e0dd` (`parent`)  
**Timestamp**: 2026-09-29T22:20:00Z  
**Type**: Hard Handoff  

---

## 1. Observation

1. **Observed in `src/lib/geocoding/service.ts`**:
   - Lines 6–9:
     ```typescript
     AddressNotFoundError,
     AddressValidationError,
     ```
     `AddressValidationError` is imported from `./types` but only used at line 101 for blank address checks (`throw new AddressValidationError('Please provide a valid street address.')`).
   - Lines 125–128, 136–139, 150–153, 160–163, 170–173:
     Provider catch blocks blindly swallow all thrown errors, log warnings, assign `lastError = err`, and fall back to subsequent tiers:
     ```typescript
     } catch (err) {
       console.warn('[GeocodingService] Photon geocode failed, falling back to Nominatim:', err);
       lastError = err;
     }
     ```
   - Lines 176–179:
     ```typescript
     // All cascade tiers exhausted
     if (lastError instanceof AddressNotFoundError) {
       throw lastError;
     }
     throw new AddressNotFoundError(address, 'cascade_all');
     ```
   - Lines 192–198:
     In `resolveCoordinates`, Nominatim errors are unconditionally rethrown as `AddressNotFoundError`:
     ```typescript
     try {
       return await this.nominatimGeocoder.resolveCoordinates(lat, lng, options);
     } catch (err) {
       console.warn('[GeocodingService] Nominatim reverse geocode failed:', err);
       throw new AddressNotFoundError(`Coordinates (${lat}, ${lng})`, 'nominatim');
     }
     ```

2. **Observed in `src/lib/geocoding/types.ts`**:
   - Lines 141–159: `GeocodingError extends Error` (base class, default status 500).
   - Lines 164–169: `AddressValidationError extends GeocodingError` (status 400).
   - Lines 174–188: `PoBoxError extends AddressValidationError` (`code: 'PO_BOX_NOT_SUPPORTED'`).
   - Lines 193–207: `MissingStreetNumberError extends AddressValidationError` (`code: 'STREET_NUMBER_REQUIRED'`).
   - Lines 212–228: `AddressNotFoundError extends GeocodingError` (`code: 'ADDRESS_NOT_RESOLVED'`). Note: `AddressNotFoundError` does **NOT** inherit from `AddressValidationError`.
   - Lines 233–246: `OutOfBoundsError extends AddressValidationError` (`code: 'OUT_OF_COVERAGE_AREA'`).

3. **Observed in `src/app/api/geocode/resolve/route.ts`**:
   - Lines 150–248: `handleGeocodeError` has granular handlers:
     - Lines 151–164: `if (err instanceof PoBoxError)` $\rightarrow$ returns HTTP 400 with `code: 'PO_BOX_NOT_SUPPORTED'`.
     - Lines 166–180: `if (err instanceof MissingStreetNumberError)` $\rightarrow$ returns HTTP 400 with `code: 'STREET_NUMBER_REQUIRED'`.
     - Lines 182–195: `if (err instanceof OutOfBoundsError)` $\rightarrow$ returns HTTP 400 with `code: 'OUT_OF_COVERAGE_AREA'`.
     - Lines 197–211: `if (err instanceof AddressNotFoundError)` $\rightarrow$ returns HTTP 400 with `code: 'ADDRESS_NOT_RESOLVED'`.
     - Lines 225–235: `if (err instanceof AddressValidationError)` $\rightarrow$ returns HTTP 400 with `code: err.code`.
     - Lines 237–247: `if (err instanceof GeocodingError)` $\rightarrow$ returns HTTP `err.statusCode` with `code: err.code`.

---

## 2. Logic Chain

1. **Premise 1**: When an address lacking a street number (e.g., `"Broadway, New York, NY 10001"`) or an out-of-bounds address is queried, `AddressNormalizer.normalizeFromComponents` throws `MissingStreetNumberError` or `OutOfBoundsError` (both subclasses of `AddressValidationError`).
2. **Premise 2**: In `service.ts:176–179`, the cascade termination logic only checks `if (lastError instanceof AddressNotFoundError) throw lastError;`. Because `MissingStreetNumberError` is an instance of `AddressValidationError` and not `AddressNotFoundError`, this check evaluates to `false`.
3. **Premise 3**: Line 179 unconditionally executes `throw new AddressNotFoundError(address, 'cascade_all')`, erasing `MissingStreetNumberError` and substituting a generic `AddressNotFoundError`.
4. **Premise 4**: In `resolve/route.ts:197–211`, `handleGeocodeError` catches `AddressNotFoundError` and emits `HTTP 400 ADDRESS_NOT_RESOLVED` instead of the expected `HTTP 400 STREET_NUMBER_REQUIRED`.
5. **Premise 5**: In addition, during the cascade, each tier's `catch` block catches `AddressValidationError` and continues to query subsequent providers (Census $\rightarrow$ Photon $\rightarrow$ Nominatim). If a downstream provider fails with a network error or timeout, `lastError` is overwritten with a generic network `Error`, permanently destroying the validation failure.
6. **Inference**: To prevent error swallowing and eliminate redundant cascade latency:
   - Every provider `catch` block in `service.ts` must check `if (err instanceof AddressValidationError) throw err;` to fail-fast immediately.
   - At cascade exhaustion (lines 176–180), `lastError` must be rethrown if it is an instance of `AddressValidationError`, `AddressNotFoundError`, or `GeocodingError`.
   - In `resolveCoordinates`, `if (err instanceof AddressValidationError) throw err;` must prevent wrapping coordinate validation errors into `AddressNotFoundError`.

---

## 3. Caveats

- **Scope boundary**: This investigation is strictly read-only and scoped to formulating the fix for `src/lib/geocoding/service.ts`. Source files were not directly modified; the complete drop-in replacement and diff patch are documented in `analysis.md` and below.
- **Node runtime**: As noted in reviewer reports, `node` is not installed in the standard `$PATH` in this environment. Static verification and AST analysis were used to validate syntax and typing.
- **Related Normalizer Bugs**: As identified by `reviewer_m1_2`, `normalizer.ts` has a separate `UNIT_REGEX` defect affecting `#` parsing and street name prefix mangling (`tests/unit/geocoding/normalizer.test.ts:72-76`). That is tracked under a distinct explorer task (`explorer_m1_r2_1`). The error-handling fix in `service.ts` is fully orthogonal and independent.

---

## 4. Conclusion

The exact code fix has been formulated, statically verified, and documented.

### Proposed Code Changes in `src/lib/geocoding/service.ts`:

1. **Import `GeocodingError`**:
   ```typescript
   import {
     IGeocoderService,
     NormalizedAddress,
     AddressSuggestion,
     GeocodeOptions,
     SuggestOptions,
     AddressNotFoundError,
     AddressValidationError,
     GeocodingError,
   } from './types';
   ```

2. **Immediate Fail-Fast in Provider Catch Blocks**:
   Add `if (err instanceof AddressValidationError) throw err;` in each tier's catch block:
   - Google Geocoder catch (line 125)
   - Mapbox Geocoder catch (line 136)
   - Census Geocoder catch (line 150)
   - Photon Geocoder catch (line 160)
   - Nominatim Geocoder catch (line 170)
   - Reverse Geocoder catch in `resolveCoordinates` (line 194)

3. **Preserve Validation and Typed Domain Errors at Cascade Exhaustion (lines 176–180)**:
   ```typescript
   // All cascade tiers exhausted
   if (lastError instanceof AddressValidationError) {
     throw lastError;
   }
   if (lastError instanceof AddressNotFoundError) {
     throw lastError;
   }
   if (lastError instanceof GeocodingError) {
     throw lastError;
   }
   throw new AddressNotFoundError(address, 'cascade_all');
   ```

The full drop-in replacement file and unified git diff patch are available in `analysis.md` in this directory.

---

## 5. Verification Method

Once applied by the coder / implementer:

1. **Static Typecheck**:
   ```bash
   npx tsc --noEmit
   ```
   *Expected*: Zero TypeScript compilation errors.

2. **Integration Verification via API Route**:
   - Query: `GET /api/geocode/resolve?address=Main%20St,%20Springfield,%20IL%2062701`
     *Expected Response*: `HTTP 400 Bad Request` with:
     ```json
     {
       "status": "error",
       "code": "STREET_NUMBER_REQUIRED",
       "message": "Please provide a full street address including building number."
     }
     ```
   - Query: `GET /api/geocode/resolve?address=PO%20Box%201234,%20Dallas,%20TX%2075201`
     *Expected Response*: `HTTP 400 Bad Request` with `code: "PO_BOX_NOT_SUPPORTED"`.
   - Query: `GET /api/geocode/resolve?address=99999%20Nonexistent%20Blvd,%20Nowhere,%20ZZ%2000000`
     *Expected Response*: `HTTP 400 Bad Request` with `code: "ADDRESS_NOT_RESOLVED"`.

3. **Invalidation Condition**:
   If an address missing a street number yields `HTTP 400 ADDRESS_NOT_RESOLVED` instead of `HTTP 400 STREET_NUMBER_REQUIRED`, the fix has failed.
