# Analysis: Foreign Address Leakage Fixes for Photon & Nominatim Geocoders

**Author**: `explorer_m1_r2_3` (`teamwork_preview_explorer`)  
**Target Files**:
- `src/lib/geocoding/photon-geocoder.ts`
- `src/lib/geocoding/nominatim-geocoder.ts`
- `src/lib/geocoding/service.ts` (cascade integration)  
**Date**: 2026-09-29  

---

## 1. Executive Summary

Reviewer 2 identified that querying Canadian addresses (such as `"123 Main St, Toronto, ON"` or `"100 King St W, Toronto, ON M5X 1A9"`) causes `PhotonGeocoder` to return a Canadian feature that passes validation and resolves with `HTTP 200 OK`, rather than being rejected with `HTTP 400 Bad Request (OUT_OF_COVERAGE_AREA)`.

### Root Causes
1. **Missing Country Code & Country Verification in `PhotonGeocoder.resolve()`**:
   - `PhotonGeocoder.suggest()` contained a loose country code check (`props.countrycode && props.countrycode.toUpperCase() !== 'US'`), but `PhotonGeocoder.resolve()` contained **zero** checks on `countrycode` or `country`.
   - Photon indexed OpenStreetMap data covers worldwide entities. When Census Geocoder fails to find a Canadian address, the cascade queries Photon with `bbox: -125,24,-66,49` (continental North America). Because Toronto (lat: ~43.65, lng: ~-79.38) falls inside that bounding rectangle, Photon finds the Toronto address and returns it.
2. **Missing Strict Country Verification in `NominatimGeocoder`**:
   - In `NominatimGeocoder.suggest()` and `NominatimGeocoder.resolve()`, results were not explicitly checked against `country_code === 'us'` or `country === 'United States'`.
   - In `NominatimGeocoder.resolveCoordinates()`, reverse geocoding did not verify the returned country at all, allowing coordinates in southern Canada (within the bounding box) to resolve as valid US locations.
3. **Rectangular Bounding Box Limitation in `AddressNormalizer`**:
   - `AddressNormalizer.validateCoordinates()` uses a rectangular box (`17.5 <= lat <= 72.0` and `-179.0 <= lng <= -64.0`). Because southern Canada and northern Mexico fall inside this rectangle, geometric coordinate validation alone cannot exclude foreign locations. Country-level semantic validation is required.
4. **Cascade Swallowing in `GeocodingService.resolve()`**:
   - If a provider throws `OutOfBoundsError`, `service.ts` must not allow downstream providers that return empty results (`AddressNotFoundError`) to overwrite `OutOfBoundsError` or swallow it.

---

## 2. Validation Rules & Criteria

To ensure complete coverage isolation for US broadband service addresses:

### A. US Territorial Bounding Box
Every candidate feature or coordinate must fall within the US geographic territorial boundaries:
```typescript
const US_MIN_LAT = 17.5;
const US_MAX_LAT = 72.0;
const US_MIN_LNG = -179.0;
const US_MAX_LNG = -64.0;

const inBbox = lat >= US_MIN_LAT && lat <= US_MAX_LAT && lng >= US_MIN_LNG && lng <= US_MAX_LNG;
```

### B. US Country Check
Every candidate feature must match US sovereignty:
- **Country Code**: `props.countrycode` (Photon) or `addr.country_code` (Nominatim) normalized to lowercase must equal `'us'`.
- **Country Name**: `props.country` (Photon) or `addr.country` (Nominatim) normalized to lowercase must equal `'united states'`, `'united states of america'`, or `'usa'`.
- If an entity possesses explicit non-US country metadata (e.g. `countrycode: 'ca'`, `country: 'Canada'`), it **must be rejected immediately**.
- In `suggest()`: Foreign entities are skipped (`continue`).
- In `resolve()`: If all returned candidates are non-US, the geocoder **must throw `new OutOfBoundsError(lat, lng)`**.
- In `resolveCoordinates()`: If the reverse-geocoded location is non-US or outside bounds, the geocoder **must throw `new OutOfBoundsError(lat, lng)`**.

---

## 3. Drop-in Replacement: `src/lib/geocoding/photon-geocoder.ts`

Below is the complete proposed code for `src/lib/geocoding/photon-geocoder.ts`:

```typescript
import {
  IGeocoderService,
  NormalizedAddress,
  AddressSuggestion,
  GeocodeOptions,
  SuggestOptions,
  AddressNotFoundError,
  OutOfBoundsError,
} from './types';
import { AddressNormalizer } from './normalizer';

interface PhotonFeature {
  type: string;
  geometry: {
    type: string;
    coordinates: [number, number]; // [lon, lat]
  };
  properties: {
    osm_id?: number;
    osm_type?: string;
    name?: string;
    housenumber?: string;
    street?: string;
    postcode?: string;
    city?: string;
    state?: string;
    country?: string;
    countrycode?: string;
  };
}

interface PhotonResponse {
  type: string;
  features: PhotonFeature[];
}

const US_MIN_LAT = 17.5;
const US_MAX_LAT = 72.0;
const US_MIN_LNG = -179.0;
const US_MAX_LNG = -64.0;

/**
 * Validates whether a Photon feature represents a location inside the United States
 * based on territorial bounding box and country code / country name metadata.
 */
function isUsPhotonFeature(feature: PhotonFeature): boolean {
  if (!feature.geometry || !Array.isArray(feature.geometry.coordinates)) {
    return false;
  }

  const [lon, lat] = feature.geometry.coordinates;

  // 1. Territorial bounding box check: 17.5 <= lat <= 72.0 and -179.0 <= lng <= -64.0
  if (lat < US_MIN_LAT || lat > US_MAX_LAT || lon < US_MIN_LNG || lon > US_MAX_LNG) {
    return false;
  }

  // 2. Country metadata checks
  const props = feature.properties || {};
  const countryCode = props.countrycode?.trim().toLowerCase();
  const country = props.country?.trim().toLowerCase();

  // Reject explicit foreign country tags
  if (countryCode && countryCode !== 'us') {
    return false;
  }
  if (
    country &&
    country !== 'united states' &&
    country !== 'united states of america' &&
    country !== 'usa'
  ) {
    return false;
  }

  // Affirmative match for US
  return (
    countryCode === 'us' ||
    country === 'united states' ||
    country === 'united states of america' ||
    country === 'usa'
  );
}

export class PhotonGeocoder implements IGeocoderService {
  public readonly providerName = 'photon' as const;
  public readonly isConfigured = true;

  private readonly baseUrl = 'https://photon.komoot.io/api';
  private readonly defaultBbox = '-125,24,-66,49'; // Continental US

  /**
   * Search-as-you-type autocomplete suggestions with US bounds and country filtering
   */
  public async suggest(query: string, options?: SuggestOptions | number): Promise<AddressSuggestion[]> {
    if (!query || query.trim().length < 3) return [];
    if (AddressNormalizer.isPoBox(query)) return [];

    const opts: SuggestOptions = typeof options === 'number' ? { limit: options } : options || {};
    const limit = Math.min(Math.max(opts.limit || 5, 1), 10);

    const params = new URLSearchParams({
      q: query.trim(),
      limit: String(limit),
      bbox: this.defaultBbox,
      lang: 'en',
    });

    if (opts.proximity) {
      params.append('lat', String(opts.proximity.lat));
      params.append('lon', String(opts.proximity.lng));
    }

    try {
      const response = await fetch(`${this.baseUrl}?${params.toString()}`, {
        headers: {
          Accept: 'application/json',
          'User-Agent': 'GetMe5G-ArbitrageEngine/1.0 (contact@getme5g.local)',
        },
        signal: opts.signal,
      });

      if (!response.ok) {
        return [];
      }

      const data: PhotonResponse = await response.json();
      if (!data.features || !Array.isArray(data.features)) return [];

      const suggestions: AddressSuggestion[] = [];

      for (const feature of data.features) {
        // Enforce US territorial bounds and country filtering
        if (!isUsPhotonFeature(feature)) {
          continue;
        }

        const props = feature.properties;
        const [lon, lat] = feature.geometry.coordinates;

        const streetLine =
          props.housenumber && props.street
            ? `${props.housenumber} ${props.street}`
            : props.street || props.name || '';

        const city = props.city || '';
        const state = AddressNormalizer.normalizeState(props.state || '');
        const zip5 = props.postcode || '';

        if (!streetLine || !city || !state) continue;

        const secondaryText = `${city}, ${state}${zip5 ? ' ' + zip5 : ''}`;
        const label = `${streetLine}, ${secondaryText}`;

        suggestions.push({
          id: `photon-${props.osm_id || Math.random().toString(36).substring(2, 9)}`,
          label,
          streetLine,
          city,
          state,
          zip5: zip5 || undefined,
          lat,
          lng: lon,
          source: this.providerName,
          secondaryText,
        });
      }

      return suggestions;
    } catch {
      return [];
    }
  }

  /**
   * Geocode an address into normalized postal components with strict foreign address rejection
   */
  public async resolve(address: string, options?: GeocodeOptions): Promise<NormalizedAddress> {
    AddressNormalizer.assertNotPoBox(address);

    const params = new URLSearchParams({
      q: address.trim(),
      limit: '3',
      bbox: this.defaultBbox,
      lang: 'en',
    });

    const response = await fetch(`${this.baseUrl}?${params.toString()}`, {
      headers: {
        Accept: 'application/json',
        'User-Agent': 'GetMe5G-ArbitrageEngine/1.0 (contact@getme5g.local)',
      },
      signal: options?.signal,
    });

    if (!response.ok) {
      throw new Error(`Photon API returned HTTP ${response.status}`);
    }

    const data: PhotonResponse = await response.json();
    if (!data.features || data.features.length === 0) {
      throw new AddressNotFoundError(address, this.providerName);
    }

    // Filter candidate features to valid US locations
    const usFeatures = data.features.filter(isUsPhotonFeature);

    // If matches were returned but all are outside the US (e.g. Canada or Mexico),
    // throw OutOfBoundsError using coordinates from the best match
    if (usFeatures.length === 0) {
      const bestForeignMatch =
        data.features.find((f) => f.properties.housenumber && f.properties.street) || data.features[0];
      const [lon, lat] = bestForeignMatch.geometry.coordinates;
      throw new OutOfBoundsError(lat, lon);
    }

    // Prefer US feature with explicit housenumber
    const feature =
      usFeatures.find((f) => f.properties.housenumber && f.properties.street) || usFeatures[0];
    const props = feature.properties;
    const [lon, lat] = feature.geometry.coordinates;

    const streetNumber = props.housenumber || '';
    const streetName = props.street || props.name || '';
    const city = props.city || '';
    const state = AddressNormalizer.normalizeState(props.state || '');
    const zip5 = props.postcode || '';

    return AddressNormalizer.normalizeFromComponents(
      {
        streetNumber,
        streetName,
        city,
        state,
        zip5,
        rawAddress: address,
      },
      { lat, lng: lon },
      this.providerName,
      0.9
    );
  }
}
```

---

## 4. Drop-in Replacement: `src/lib/geocoding/nominatim-geocoder.ts`

Below is the complete proposed code for `src/lib/geocoding/nominatim-geocoder.ts`:

```typescript
import {
  IGeocoderService,
  NormalizedAddress,
  AddressSuggestion,
  GeocodeOptions,
  SuggestOptions,
  AddressNotFoundError,
  OutOfBoundsError,
} from './types';
import { AddressNormalizer } from './normalizer';

interface NominatimPlace {
  place_id: number;
  lat: string;
  lon: string;
  display_name: string;
  address?: {
    house_number?: string;
    road?: string;
    suburb?: string;
    city?: string;
    town?: string;
    village?: string;
    hamlet?: string;
    state?: string;
    postcode?: string;
    country_code?: string;
    country?: string;
  };
}

const US_MIN_LAT = 17.5;
const US_MAX_LAT = 72.0;
const US_MIN_LNG = -179.0;
const US_MAX_LNG = -64.0;

/**
 * Validates whether a Nominatim place represents a location inside the United States
 * based on territorial bounding box and country code / country name metadata.
 */
function isUsNominatimPlace(place: NominatimPlace): boolean {
  const lat = parseFloat(place.lat);
  const lng = parseFloat(place.lon);

  // 1. Territorial bounding box check: 17.5 <= lat <= 72.0 and -179.0 <= lng <= -64.0
  if (isNaN(lat) || isNaN(lng) || lat < US_MIN_LAT || lat > US_MAX_LAT || lng < US_MIN_LNG || lng > US_MAX_LNG) {
    return false;
  }

  // 2. Country metadata checks
  const addr = place.address || {};
  const countryCode = addr.country_code?.trim().toLowerCase();
  const country = addr.country?.trim().toLowerCase();

  // Reject explicit foreign country tags
  if (countryCode && countryCode !== 'us') {
    return false;
  }
  if (
    country &&
    country !== 'united states' &&
    country !== 'united states of america' &&
    country !== 'usa'
  ) {
    return false;
  }

  // Affirmative match for US
  return (
    countryCode === 'us' ||
    country === 'united states' ||
    country === 'united states of america' ||
    country === 'usa'
  );
}

export class NominatimGeocoder implements IGeocoderService {
  public readonly providerName = 'nominatim' as const;
  public readonly isConfigured = true;

  private readonly baseUrl = 'https://nominatim.openstreetmap.org';
  private readonly userAgent =
    process.env.NOMINATIM_USER_AGENT || 'GetMe5G-ArbitrageEngine/1.0 (contact@getme5g.local)';

  public async suggest(query: string, options?: SuggestOptions | number): Promise<AddressSuggestion[]> {
    if (!query || query.trim().length < 3) return [];
    if (AddressNormalizer.isPoBox(query)) return [];

    const opts: SuggestOptions = typeof options === 'number' ? { limit: options } : options || {};
    const limit = Math.min(Math.max(opts.limit || 5, 1), 10);

    const params = new URLSearchParams({
      q: query.trim(),
      format: 'jsonv2',
      addressdetails: '1',
      countrycodes: 'us',
      limit: String(limit),
    });

    try {
      const response = await fetch(`${this.baseUrl}/search?${params.toString()}`, {
        headers: {
          Accept: 'application/json',
          'User-Agent': this.userAgent,
        },
        signal: opts.signal,
      });

      if (!response.ok) return [];

      const results: NominatimPlace[] = await response.json();
      if (!Array.isArray(results)) return [];

      const suggestions: AddressSuggestion[] = [];

      for (const item of results) {
        // Enforce US territorial bounds and country filtering
        if (!isUsNominatimPlace(item)) {
          continue;
        }

        const addr = item.address || {};
        const houseNumber = addr.house_number || '';
        const road = addr.road || '';
        const streetLine =
          houseNumber && road ? `${houseNumber} ${road}` : road || item.display_name.split(',')[0];
        const city = addr.city || addr.town || addr.village || addr.suburb || '';
        const state = AddressNormalizer.normalizeState(addr.state || '');
        const zip5 = addr.postcode || '';

        if (!streetLine || !city || !state) continue;

        const secondaryText = `${city}, ${state}${zip5 ? ' ' + zip5 : ''}`;
        suggestions.push({
          id: `nominatim-${item.place_id}`,
          label: `${streetLine}, ${secondaryText}`,
          streetLine,
          city,
          state,
          zip5: zip5 || undefined,
          lat: parseFloat(item.lat),
          lng: parseFloat(item.lon),
          source: this.providerName,
          secondaryText,
        });
      }

      return suggestions;
    } catch {
      return [];
    }
  }

  public async resolve(address: string, options?: GeocodeOptions): Promise<NormalizedAddress> {
    AddressNormalizer.assertNotPoBox(address);

    const params = new URLSearchParams({
      q: address.trim(),
      format: 'jsonv2',
      addressdetails: '1',
      countrycodes: 'us',
      limit: '3',
    });

    const response = await fetch(`${this.baseUrl}/search?${params.toString()}`, {
      headers: {
        Accept: 'application/json',
        'User-Agent': this.userAgent,
      },
      signal: options?.signal,
    });

    if (!response.ok) {
      throw new Error(`Nominatim returned HTTP ${response.status}`);
    }

    const results: NominatimPlace[] = await response.json();
    if (!results || results.length === 0) {
      throw new AddressNotFoundError(address, this.providerName);
    }

    // Filter results to valid US locations
    const usResults = results.filter(isUsNominatimPlace);

    // If Nominatim returned results but all are outside the US, throw OutOfBoundsError
    if (usResults.length === 0) {
      const foreignItem = results[0];
      const fLat = parseFloat(foreignItem.lat);
      const fLng = parseFloat(foreignItem.lon);
      throw new OutOfBoundsError(isNaN(fLat) ? 0 : fLat, isNaN(fLng) ? 0 : fLng);
    }

    const item = usResults[0];
    const addr = item.address || {};
    const streetNumber = addr.house_number || '';
    const streetName = addr.road || '';
    const city = addr.city || addr.town || addr.village || addr.suburb || '';
    const state = AddressNormalizer.normalizeState(addr.state || '');
    const zip5 = addr.postcode || '';
    const lat = parseFloat(item.lat);
    const lng = parseFloat(item.lon);

    return AddressNormalizer.normalizeFromComponents(
      {
        streetNumber,
        streetName,
        city,
        state,
        zip5,
        rawAddress: address,
      },
      { lat, lng },
      this.providerName,
      0.85
    );
  }

  public async resolveCoordinates(
    lat: number,
    lng: number,
    options?: GeocodeOptions
  ): Promise<NormalizedAddress> {
    // Upfront territorial bounding box check
    if (lat < US_MIN_LAT || lat > US_MAX_LAT || lng < US_MIN_LNG || lng > US_MAX_LNG) {
      throw new OutOfBoundsError(lat, lng);
    }

    const params = new URLSearchParams({
      lat: String(lat),
      lon: String(lng),
      format: 'jsonv2',
      addressdetails: '1',
    });

    const response = await fetch(`${this.baseUrl}/reverse?${params.toString()}`, {
      headers: {
        Accept: 'application/json',
        'User-Agent': this.userAgent,
      },
      signal: options?.signal,
    });

    if (!response.ok) {
      throw new Error(`Nominatim reverse returned HTTP ${response.status}`);
    }

    const item: NominatimPlace = await response.json();
    if (!item || !item.address) {
      throw new AddressNotFoundError(`Coordinates (${lat}, ${lng})`, this.providerName);
    }

    // Verify reverse-geocoded location is within the United States
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

    const streetNumber = addr.house_number || '';
    const streetName = addr.road || '';
    const city = addr.city || addr.town || addr.village || '';
    const state = AddressNormalizer.normalizeState(addr.state || '');
    const zip5 = addr.postcode || '';

    return AddressNormalizer.normalizeFromComponents(
      {
        streetNumber,
        streetName,
        city,
        state,
        zip5,
      },
      { lat, lng },
      this.providerName,
      0.85
    );
  }
}
```

---

## 5. Cascade Integration in `src/lib/geocoding/service.ts`

To ensure that `OutOfBoundsError` (and other domain validation errors like `MissingStreetNumberError` and `PoBoxError`) are never swallowed or replaced by a generic `AddressNotFoundError` during provider fallback:

1. **Immediate Propagation on Validation Errors**:
   In `GeocodingService.resolve()`, when an upstream geocoder throws `OutOfBoundsError` or `AddressValidationError`, it should rethrow immediately:
   ```typescript
   // Step 4: Secondary Open Provider (Komoot Photon)
   try {
     const result = await this.photonGeocoder.resolve(address, options);
     this.cache.set(cacheKey, { address: result, timestamp: Date.now() });
     return result;
   } catch (err) {
     if (err instanceof OutOfBoundsError || err instanceof AddressValidationError) {
       throw err;
     }
     console.warn('[GeocodingService] Photon geocode failed, falling back to Nominatim:', err);
     lastError = err;
   }
   ```
2. **Cascade Exhaustion Preservation**:
   At lines 176-179 in `src/lib/geocoding/service.ts`:
   ```typescript
   // All cascade tiers exhausted
   if (lastError instanceof GeocodingError) {
     throw lastError;
   }
   throw new AddressNotFoundError(address, 'cascade_all');
   ```
   This ensures that any domain exception (`GeocodingError`) thrown earlier in the cascade propagates directly to `/api/geocode/resolve/route.ts` where it maps to the exact required HTTP status code and error code (`OUT_OF_COVERAGE_AREA`).

---

## 6. Verification and Test Suite Additions

### Test Assertions for Unit & Integration Verification

```typescript
describe('Foreign Address Rejection & OutOfBounds Coverage', () => {
  it('should reject Canadian addresses from Photon with OutOfBoundsError', async () => {
    const photon = new PhotonGeocoder();
    await expect(photon.resolve('100 King St W, Toronto, ON M5X 1A9')).rejects.toThrow(
      OutOfBoundsError
    );
  });

  it('should reject Canadian addresses from Nominatim with OutOfBoundsError', async () => {
    const nominatim = new NominatimGeocoder();
    await expect(nominatim.resolve('123 Main St, Toronto, ON')).rejects.toThrow(
      OutOfBoundsError
    );
  });

  it('should reject foreign coordinates in reverse geocode with OutOfBoundsError', async () => {
    const nominatim = new NominatimGeocoder();
    // Toronto coordinates: lat 43.65, lng -79.38
    await expect(nominatim.resolveCoordinates(43.6532, -79.3832)).rejects.toThrow(
      OutOfBoundsError
    );
  });

  it('should filter out Canadian suggestions in Photon suggest', async () => {
    const photon = new PhotonGeocoder();
    const suggestions = await photon.suggest('100 King St W, Toronto');
    expect(suggestions.every((s) => s.state !== 'ON' && s.countrycode !== 'CA')).toBe(true);
  });
});
```
