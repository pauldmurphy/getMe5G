import {
  IGeocoderService,
  NormalizedAddress,
  AddressSuggestion,
  GeocodeOptions,
  SuggestOptions,
  AddressNotFoundError,
  AddressValidationError,
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
      console.warn('[GeocodingService] Census geocode failed, falling back to Photon:', err);
      lastError = err;
    }

    // Step 4: Secondary Open Provider (Komoot Photon)
    try {
      const result = await this.photonGeocoder.resolve(address, options);
      this.cache.set(cacheKey, { address: result, timestamp: Date.now() });
      return result;
    } catch (err) {
      console.warn('[GeocodingService] Photon geocode failed, falling back to Nominatim:', err);
      lastError = err;
    }

    // Step 5: Tertiary Open Provider (OSM Nominatim)
    try {
      const result = await this.nominatimGeocoder.resolve(address, options);
      this.cache.set(cacheKey, { address: result, timestamp: Date.now() });
      return result;
    } catch (err) {
      console.warn('[GeocodingService] Nominatim geocode failed:', err);
      lastError = err;
    }

    // All cascade tiers exhausted
    if (lastError instanceof AddressNotFoundError) {
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
      console.warn('[GeocodingService] Nominatim reverse geocode failed:', err);
      throw new AddressNotFoundError(`Coordinates (${lat}, ${lng})`, 'nominatim');
    }
  }
}

/**
 * Singleton export for application-wide consumption
 */
export const geocodingService = new GeocodingService();
