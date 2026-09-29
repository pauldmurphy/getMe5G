import {
  IGeocoderService,
  NormalizedAddress,
  AddressSuggestion,
  GeocodeOptions,
  SuggestOptions,
  AddressNotFoundError,
} from './types';
import { AddressNormalizer } from './normalizer';

interface CensusApiResponse {
  result?: {
    addressMatches?: Array<{
      matchedAddress: string;
      coordinates: {
        x: number; // Longitude
        y: number; // Latitude
      };
      tigerLine?: {
        tigerLineId: string;
        side: string;
      };
      addressComponents: {
        fromAddress?: string;
        toAddress?: string;
        preDirection?: string;
        preType?: string;
        streetName?: string;
        suffixType?: string;
        suffixDirection?: string;
        city?: string;
        state?: string;
        zip?: string;
      };
    }>;
  };
}

export class CensusGeocoder implements IGeocoderService {
  public readonly providerName = 'census' as const;
  public readonly isConfigured = true; // Always available zero-config

  private readonly baseUrl = 'https://geocoding.geo.census.gov/geocoder/locations/onelineaddress';
  private readonly defaultTimeoutMs = 2500;

  /**
   * Resolves a physical address using the US Census Bureau API
   */
  public async resolve(address: string, options?: GeocodeOptions): Promise<NormalizedAddress> {
    AddressNormalizer.assertNotPoBox(address);

    const timeout = options?.timeoutMs || this.defaultTimeoutMs;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    // Combine caller signal with timeout
    if (options?.signal) {
      options.signal.addEventListener('abort', () => controller.abort());
    }

    const params = new URLSearchParams({
      address: address.trim(),
      benchmark: 'Public_AR_Current',
      format: 'json',
    });

    try {
      const response = await fetch(`${this.baseUrl}?${params.toString()}`, {
        method: 'GET',
        headers: {
          Accept: 'application/json',
          'User-Agent': 'GetMe5G-ArbitrageEngine/1.0 (contact@getme5g.local)',
        },
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`Census API returned HTTP ${response.status}`);
      }

      const data: CensusApiResponse = await response.json();
      const matches = data.result?.addressMatches;

      if (!matches || matches.length === 0) {
        throw new AddressNotFoundError(address, this.providerName);
      }

      const match = matches[0];
      const comps = match.addressComponents;

      // Extract street number from matched address or input query
      let streetNumber = comps.fromAddress || '';
      const inputNumMatch = address.match(/^([0-9]+(?:\s+1\/[2-4])?|[0-9]+-[0-9]+|[A-Z][0-9]+[A-Z][0-9]+)\b/i);
      if (inputNumMatch) {
        streetNumber = inputNumMatch[1];
      }

      // Reconstruct street name from Tiger components
      const streetParts: string[] = [];
      if (comps.preDirection) streetParts.push(comps.preDirection);
      if (comps.preType) streetParts.push(comps.preType);
      if (comps.streetName) streetParts.push(comps.streetName);
      if (comps.suffixType) streetParts.push(comps.suffixType);
      if (comps.suffixDirection) streetParts.push(comps.suffixDirection);
      const streetName = streetParts.length > 0 ? streetParts.join(' ') : address.split(',')[0].replace(/^\d+\s*/, '');

      // CRITICAL COORDINATES MAPPING: x = Longitude, y = Latitude
      const coords = {
        lat: match.coordinates.y,
        lng: match.coordinates.x,
      };

      return AddressNormalizer.normalizeFromComponents(
        {
          streetNumber,
          streetName,
          city: comps.city,
          state: comps.state,
          zip5: comps.zip,
          rawAddress: address,
        },
        coords,
        this.providerName,
        0.98 // High confidence for US Census TigerLine match
      );
    } catch (err: unknown) {
      if ((err as Error).name === 'AbortError') {
        throw new Error(`Census Geocoder timed out after ${timeout}ms`);
      }
      throw err;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * Suggest implementation: Census does not have a native autocomplete endpoint,
   * but if called with a resolvable address, converts match to suggestion.
   */
  public async suggest(query: string, options?: SuggestOptions | number): Promise<AddressSuggestion[]> {
    if (!query || query.trim().length < 3) return [];
    if (AddressNormalizer.isPoBox(query)) return [];

    const geocodeOpts: GeocodeOptions = typeof options === 'number' ? { timeoutMs: 2500 } : options || {};

    try {
      const resolved = await this.resolve(query, geocodeOpts);
      return [
        {
          id: `census-${resolved.zip5}-${resolved.streetNumber}`,
          label: resolved.formattedAddress,
          streetLine: `${resolved.streetNumber} ${resolved.streetName}`,
          city: resolved.city,
          state: resolved.state,
          zip5: resolved.zip5,
          lat: resolved.lat,
          lng: resolved.lng,
          source: this.providerName,
          secondaryText: `${resolved.city}, ${resolved.state} ${resolved.zip5}`,
        },
      ];
    } catch {
      return [];
    }
  }
}
