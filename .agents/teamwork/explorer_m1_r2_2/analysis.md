# Detailed Technical Analysis: Geocoding Cascade Error Handling Fix

**File**: `src/lib/geocoding/service.ts`  
**Subagent**: `explorer_m1_r2_2` (`teamwork_preview_explorer`)  
**Parent / Recipient**: `097744dd-87b6-414e-a580-658af286e0dd` (`parent`)  
**Date**: 2026-09-29  

---

## 1. Executive Summary & Problem Definition

In the 5G Arbitrage Engine, address intake is governed by strict postal and physical feasibility requirements. Users submitting incomplete addresses (e.g. `"Main St, Springfield, IL 62701"` lacking a building number), PO Boxes, or locations outside broadband coverage must receive precise, actionable HTTP 400 status codes with granular error codes (`STREET_NUMBER_REQUIRED`, `PO_BOX_NOT_SUPPORTED`, `OUT_OF_COVERAGE_AREA`).

While `src/app/api/geocode/resolve/route.ts` contains dedicated handlers for each domain error type, `src/lib/geocoding/service.ts` suffered from an error-swallowing defect:
1. At cascade exhaustion (lines 176–179), `resolve()` only checked `if (lastError instanceof AddressNotFoundError)` before unconditionally overwriting any other error with `throw new AddressNotFoundError(address, 'cascade_all')`.
2. Because `MissingStreetNumberError`, `PoBoxError`, and `OutOfBoundsError` extend `AddressValidationError` (and `GeocodingError`), they are **not** instances of `AddressNotFoundError`.
3. Furthermore, within the cascade `try / catch` blocks for each provider tier (Google, Mapbox, Census, Photon, Nominatim), catching all exceptions without inspecting `AddressValidationError` forced the engine to make wasteful external API calls to subsequent tiers (adding up to 7 seconds of latency) before overwriting the validation error with a generic `AddressNotFoundError` or subsequent network failure.

---

## 2. Error Class Inheritance & Route Error Mapping

The type hierarchy defined in `src/lib/geocoding/types.ts`:

```
Error
 └── GeocodingError (statusCode: 500, code: "GEOCODING_ERROR")
      ├── AddressValidationError (statusCode: 400, code: "ADDRESS_VALIDATION_ERROR")
      │    ├── PoBoxError (statusCode: 400, code: "PO_BOX_NOT_SUPPORTED")
      │    ├── MissingStreetNumberError (statusCode: 400, code: "STREET_NUMBER_REQUIRED")
      │    └── OutOfBoundsError (statusCode: 400, code: "OUT_OF_COVERAGE_AREA")
      ├── AddressNotFoundError (statusCode: 400, code: "ADDRESS_NOT_RESOLVED")
      ├── InvalidCoordinatesError (statusCode: 422, code: "INVALID_COORDINATES")
      └── GeocoderTimeoutError (statusCode: 504, code: "GEOCODER_UPSTREAM_TIMEOUT")
```

In `src/app/api/geocode/resolve/route.ts:150–248`:
- `PoBoxError` $\rightarrow$ HTTP 400 `PO_BOX_NOT_SUPPORTED`
- `MissingStreetNumberError` $\rightarrow$ HTTP 400 `STREET_NUMBER_REQUIRED`
- `OutOfBoundsError` $\rightarrow$ HTTP 400 `OUT_OF_COVERAGE_AREA`
- `AddressNotFoundError` $\rightarrow$ HTTP 400 `ADDRESS_NOT_RESOLVED`
- `AddressValidationError` $\rightarrow$ HTTP 400 `ADDRESS_VALIDATION_ERROR` (or `err.code`)
- `GeocodingError` $\rightarrow$ HTTP `err.statusCode` with `err.code`

---

## 3. Root Cause & Defects in `src/lib/geocoding/service.ts`

### Defect 1: Error Swallowing at Cascade Exhaustion (lines 176–179)
```typescript
// CURRENT DEFECTIVE CODE:
// All cascade tiers exhausted
if (lastError instanceof AddressNotFoundError) {
  throw lastError;
}
throw new AddressNotFoundError(address, 'cascade_all');
```
If `lastError` was `MissingStreetNumberError`, `lastError instanceof AddressNotFoundError` evaluates to `false`. Line 179 constructs a brand new `AddressNotFoundError(address, 'cascade_all')`, erasing the original exception.

### Defect 2: Blind Catching and Fallback on Validation Failures
```typescript
// CURRENT DEFECTIVE PATTERN in tiers 2, 3, 4, 5:
try {
  const result = await this.photonGeocoder.resolve(address, options);
  ...
} catch (err) {
  console.warn('[GeocodingService] Photon geocode failed, falling back to Nominatim:', err);
  lastError = err;
}
```
When an upstream provider (e.g., Census or Photon) resolves a road segment without a building number, `AddressNormalizer.normalizeFromComponents` throws `MissingStreetNumberError`. This is an invariant physical validation failure of the user's input—no subsequent provider can magically synthesize the missing house number.
Catching it and falling back causes:
- Up to 5–7 seconds of unnecessary latency querying Nominatim.
- If Nominatim returns an HTTP 500 or network timeout, `lastError` is overwritten with a generic network `Error`, permanently destroying the `MissingStreetNumberError` evidence.

### Defect 3: Swallowed Reverse Geocode Validation Errors (lines 192–198)
```typescript
// CURRENT DEFECTIVE CODE in resolveCoordinates:
try {
  return await this.nominatimGeocoder.resolveCoordinates(lat, lng, options);
} catch (err) {
  console.warn('[GeocodingService] Nominatim reverse geocode failed:', err);
  throw new AddressNotFoundError(`Coordinates (${lat}, ${lng})`, 'nominatim');
}
```
If `nominatimGeocoder.resolveCoordinates` throws `AddressValidationError` (or `OutOfBoundsError`), it is caught and wrapped into `AddressNotFoundError`.

---

## 4. Architectural Solution: Dual-Layer Error Propagation

The fix implements **Dual-Layer Error Propagation**:

1. **Layer 1: Fail-Fast in Catch Blocks (Immediate Propagation)**
   In each provider tier's catch block, immediately check:
   ```typescript
   if (err instanceof AddressValidationError) {
     throw err;
   }
   ```
   If the address is invalid (missing house number, PO Box, out of US coverage bounds), the cascade terminates **immediately**. No unnecessary network round-trips to downstream geocoders occur, and `lastError` cannot be corrupted by subsequent network failures.

2. **Layer 2: Cascade Exhaustion Preservation (Safety Net)**
   At lines 176–180:
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
   Any typed domain error (`AddressValidationError`, `AddressNotFoundError`, `GeocodingError`) is preserved and rethrown verbatim. Only unclassified errors (or null) fall back to the synthetic `AddressNotFoundError(address, 'cascade_all')`.

3. **Layer 3: Reverse Geocoding Preservation**
   In `resolveCoordinates`:
   ```typescript
   try {
     return await this.nominatimGeocoder.resolveCoordinates(lat, lng, options);
   } catch (err) {
     if (err instanceof AddressValidationError) {
       throw err;
     }
     console.warn('[GeocodingService] Nominatim reverse geocode failed:', err);
     throw new AddressNotFoundError(`Coordinates (${lat}, ${lng})`, 'nominatim');
   }
   ```

---

## 5. Exact Drop-In Replacement Code

Below is the complete, drop-in replacement file content for `src/lib/geocoding/service.ts`:

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
import { AddressNormalizer } from './normalizer';
import { CensusGeocoder } from './census-geocoder';
import { PhotonGeocoder } from './photon-geocoder';
import { NominatimGeocoder } from './nominatim-geocoder';
import { GoogleGeocoder } from './google-geocoder';
import { MapboxGeocoder } from './mapbox-geocoder';

interface CacheEntry {
  address: NormalizedAddress;
  timestamp: number;
}

export class GeocodingService implements IGeocoderService {
  public readonly providerName = 'census' as const; // Default primary
  public readonly isConfigured = true;

  private readonly googleGeocoder: GoogleGeocoder;
  private readonly mapboxGeocoder: MapboxGeocoder;
  private readonly censusGeocoder: CensusGeocoder;
  private readonly photonGeocoder: PhotonGeocoder;
  private readonly nominatimGeocoder: NominatimGeocoder;

  // L1 In-memory cache for fast sub-5ms repeat lookups
  private readonly cache = new Map<string, CacheEntry>();
  private readonly ttlMs = 3600 * 1000; // 1 hour TTL

  constructor() {
    this.googleGeocoder = new GoogleGeocoder();
    this.mapboxGeocoder = new MapboxGeocoder();
    this.censusGeocoder = new CensusGeocoder();
    this.photonGeocoder = new PhotonGeocoder();
    this.nominatimGeocoder = new NominatimGeocoder();
  }

  private getCacheKey(address: string): string {
    return address.trim().toLowerCase().replace(/\s+/g, ' ');
  }

  /**
   * Search-as-you-type autocomplete suggestions cascade
   */
  public async suggest(query: string, options?: SuggestOptions | number): Promise<AddressSuggestion[]> {
    if (!query || query.trim().length < 3) return [];

    // Pre-check for PO Box
    if (AddressNormalizer.isPoBox(query)) return [];

    const opts: SuggestOptions = typeof options === 'number' ? { limit: options } : options || {};

    // 1. Google Places (if configured)
    if (this.googleGeocoder.isConfigured) {
      try {
        const results = await this.googleGeocoder.suggest(query, opts);
        if (results.length > 0) return results;
      } catch (err) {
        console.warn('[GeocodingService] Google suggest failed, falling back to open cascade:', err);
      }
    }

    // 2. Mapbox (if configured)
    if (this.mapboxGeocoder.isConfigured) {
      try {
        const results = await this.mapboxGeocoder.suggest(query, opts);
        if (results.length > 0) return results;
      } catch (err) {
        console.warn('[GeocodingService] Mapbox suggest failed, falling back to open cascade:', err);
      }
    }

    // 3. Open Default: Komoot Photon
    try {
      const results = await this.photonGeocoder.suggest(query, opts);
      if (results.length > 0) return results;
    } catch (err) {
      console.warn('[GeocodingService] Photon suggest failed, falling back to Nominatim:', err);
    }

    // 4. Open Fallback: OSM Nominatim
    try {
      return await this.nominatimGeocoder.suggest(query, opts);
    } catch (err) {
      console.warn('[GeocodingService] Nominatim suggest failed:', err);
      return [];
    }
  }

  /**
   * Address resolution cascade: Commercial -> Census -> Photon -> Nominatim
   */
  public async resolve(address: string, options?: GeocodeOptions): Promise<NormalizedAddress> {
    if (!address || !address.trim()) {
      throw new AddressValidationError('Please provide a valid street address.');
    }

    // Step 1: Pre-validation - reject PO Boxes immediately
    AddressNormalizer.assertNotPoBox(address);

    const cacheKey = this.getCacheKey(address);

    // Check L1 In-Memory Cache unless fresh is requested
    if (!options?.fresh) {
      const cached = this.cache.get(cacheKey);
      if (cached && Date.now() - cached.timestamp < this.ttlMs) {
        return cached.address;
      }
    }

    let lastError: unknown = null;

    // Step 2: Commercial Providers (if configured)
    if (this.googleGeocoder.isConfigured) {
      try {
        const result = await this.googleGeocoder.resolve(address, options);
        this.cache.set(cacheKey, { address: result, timestamp: Date.now() });
        return result;
      } catch (err) {
        if (err instanceof AddressValidationError) {
          throw err;
        }
        console.warn('[GeocodingService] Google geocode failed, falling back:', err);
        lastError = err;
      }
    }

    if (this.mapboxGeocoder.isConfigured) {
      try {
        const result = await this.mapboxGeocoder.resolve(address, options);
        this.cache.set(cacheKey, { address: result, timestamp: Date.now() });
        return result;
      } catch (err) {
        if (err instanceof AddressValidationError) {
          throw err;
        }
        console.warn('[GeocodingService] Mapbox geocode failed, falling back:', err);
        lastError = err;
      }
    }

    // Step 3: Primary Open Provider (US Census Bureau Geocoder with 2500ms budget)
    try {
      const result = await this.censusGeocoder.resolve(address, {
        ...options,
        timeoutMs: options?.timeoutMs || 2500,
      });
      this.cache.set(cacheKey, { address: result, timestamp: Date.now() });
      return result;
    } catch (err) {
      if (err instanceof AddressValidationError) {
        throw err;
      }
      console.warn('[GeocodingService] Census geocode failed, falling back to Photon:', err);
      lastError = err;
    }

    // Step 4: Secondary Open Provider (Komoot Photon)
    try {
      const result = await this.photonGeocoder.resolve(address, options);
      this.cache.set(cacheKey, { address: result, timestamp: Date.now() });
      return result;
    } catch (err) {
      if (err instanceof AddressValidationError) {
        throw err;
      }
      console.warn('[GeocodingService] Photon geocode failed, falling back to Nominatim:', err);
      lastError = err;
    }

    // Step 5: Tertiary Open Provider (OSM Nominatim)
    try {
      const result = await this.nominatimGeocoder.resolve(address, options);
      this.cache.set(cacheKey, { address: result, timestamp: Date.now() });
      return result;
    } catch (err) {
      if (err instanceof AddressValidationError) {
        throw err;
      }
      console.warn('[GeocodingService] Nominatim geocode failed:', err);
      lastError = err;
    }

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
  }

  /**
   * Coordinate reverse geocoding cascade
   */
  public async resolveCoordinates(
    lat: number,
    lng: number,
    options?: GeocodeOptions
  ): Promise<NormalizedAddress> {
    AddressNormalizer.validateCoordinates(lat, lng);

    try {
      return await this.nominatimGeocoder.resolveCoordinates(lat, lng, options);
    } catch (err) {
      if (err instanceof AddressValidationError) {
        throw err;
      }
      console.warn('[GeocodingService] Nominatim reverse geocode failed:', err);
      throw new AddressNotFoundError(`Coordinates (${lat}, ${lng})`, 'nominatim');
    }
  }
}

/**
 * Singleton export for application-wide consumption
 */
export const geocodingService = new GeocodingService();
```

---

## 6. Git Diff Patch

```patch
--- a/src/lib/geocoding/service.ts
+++ b/src/lib/geocoding/service.ts
@@ -6,6 +6,7 @@
   SuggestOptions,
   AddressNotFoundError,
   AddressValidationError,
+  GeocodingError,
 } from './types';
 import { AddressNormalizer } from './normalizer';
 import { CensusGeocoder } from './census-geocoder';
@@ -124,6 +125,9 @@
         this.cache.set(cacheKey, { address: result, timestamp: Date.now() });
         return result;
       } catch (err) {
+        if (err instanceof AddressValidationError) {
+          throw err;
+        }
         console.warn('[GeocodingService] Google geocode failed, falling back:', err);
         lastError = err;
       }
@@ -134,6 +138,9 @@
         this.cache.set(cacheKey, { address: result, timestamp: Date.now() });
         return result;
       } catch (err) {
+        if (err instanceof AddressValidationError) {
+          throw err;
+        }
         console.warn('[GeocodingService] Mapbox geocode failed, falling back:', err);
         lastError = err;
       }
@@ -148,6 +155,9 @@
       this.cache.set(cacheKey, { address: result, timestamp: Date.now() });
       return result;
     } catch (err) {
+      if (err instanceof AddressValidationError) {
+        throw err;
+      }
       console.warn('[GeocodingService] Census geocode failed, falling back to Photon:', err);
       lastError = err;
     }
@@ -158,6 +168,9 @@
       this.cache.set(cacheKey, { address: result, timestamp: Date.now() });
       return result;
     } catch (err) {
+      if (err instanceof AddressValidationError) {
+        throw err;
+      }
       console.warn('[GeocodingService] Photon geocode failed, falling back to Nominatim:', err);
       lastError = err;
     }
@@ -168,11 +181,20 @@
       this.cache.set(cacheKey, { address: result, timestamp: Date.now() });
       return result;
     } catch (err) {
+      if (err instanceof AddressValidationError) {
+        throw err;
+      }
       console.warn('[GeocodingService] Nominatim geocode failed:', err);
       lastError = err;
     }
 
     // All cascade tiers exhausted
+    if (lastError instanceof AddressValidationError) {
+      throw lastError;
+    }
+    if (lastError instanceof AddressNotFoundError) {
+      throw lastError;
+    }
+    if (lastError instanceof GeocodingError) {
+      throw lastError;
+    }
-    if (lastError instanceof AddressNotFoundError) {
-      throw lastError;
-    }
     throw new AddressNotFoundError(address, 'cascade_all');
   }
 
@@ -192,6 +214,9 @@
     try {
       return await this.nominatimGeocoder.resolveCoordinates(lat, lng, options);
     } catch (err) {
+      if (err instanceof AddressValidationError) {
+        throw err;
+      }
       console.warn('[GeocodingService] Nominatim reverse geocode failed:', err);
       throw new AddressNotFoundError(`Coordinates (${lat}, ${lng})`, 'nominatim');
     }
```

---

## 7. Verification & Boundary Testing Matrix

| Scenario | Input | Thrown By | Behavior in `service.ts` | Handled By `route.ts` | Expected HTTP Code & Response |
|---|---|---|---|---|---|
| **Missing Street Number** | `"Main St, Springfield, IL 62701"` | `CensusGeocoder` or `PhotonGeocoder` via `normalizeFromComponents` | `catch (err)` encounters `MissingStreetNumberError` (instance of `AddressValidationError`), halts cascade immediately, throws `MissingStreetNumberError`. | `handleGeocodeError` line 166 | `HTTP 400 Bad Request`<br>`code: "STREET_NUMBER_REQUIRED"` |
| **PO Box Query** | `"PO Box 1234, Dallas, TX 75201"` | `AddressNormalizer.assertNotPoBox` line 105 | Thrown at pre-validation step before network cascade. | `handleGeocodeError` line 151 | `HTTP 400 Bad Request`<br>`code: "PO_BOX_NOT_SUPPORTED"` |
| **Foreign / Canadian** | `"100 King St W, Toronto, ON M5X 1A9"` | `normalizeFromComponents` via `validateCoordinates` | Throws `OutOfBoundsError` (instance of `AddressValidationError`), caught and immediately rethrown. | `handleGeocodeError` line 182 | `HTTP 400 Bad Request`<br>`code: "OUT_OF_COVERAGE_AREA"` |
| **Nonexistent Address** | `"99999 Nonexistent Blvd, Nowhere, ZZ 00000"` | All providers return 0 matches | All providers throw `AddressNotFoundError`. Caught, logs warning, cascade completes. Line 186 rethrows `lastError`. | `handleGeocodeError` line 197 | `HTTP 400 Bad Request`<br>`code: "ADDRESS_NOT_RESOLVED"` |
| **Valid Address** | `"350 5th Ave, New York, NY 10118"` | None | Census resolves successfully. Normalized address cached and returned. | Route handler line 92 | `HTTP 200 OK`<br>`status: "success"` |
| **Reverse Geocode Out of Bounds** | `lat: 51.5074, lng: -0.1278` (London) | `AddressNormalizer.validateCoordinates` line 190 | Throws `OutOfBoundsError` immediately prior to reverse geocode fetch. | `handleGeocodeError` line 182 | `HTTP 400 Bad Request`<br>`code: "OUT_OF_COVERAGE_AREA"` |
