import {
  IGeocoderService,
  NormalizedAddress,
  AddressSuggestion,
  GeocodeOptions,
  SuggestOptions,
  AddressNotFoundError,
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

export class PhotonGeocoder implements IGeocoderService {
  public readonly providerName = 'photon' as const;
  public readonly isConfigured = true;

  private readonly baseUrl = 'https://photon.komoot.io/api';
  private readonly defaultBbox = '-125,24,-66,49'; // Continental US

  /**
   * Search-as-you-type autocomplete suggestions
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
      if (!data.features) return [];

      const suggestions: AddressSuggestion[] = [];

      for (const feature of data.features) {
        const props = feature.properties;
        const [lon, lat] = feature.geometry.coordinates;

        // Skip non-US results
        if (props.countrycode && props.countrycode.toUpperCase() !== 'US') {
          continue;
        }

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
   * Geocode an address into normalized postal components
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
