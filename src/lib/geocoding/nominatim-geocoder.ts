import {
  IGeocoderService,
  NormalizedAddress,
  AddressSuggestion,
  GeocodeOptions,
  SuggestOptions,
  AddressNotFoundError,
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
  };
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
      return results.map((item) => {
        const addr = item.address || {};
        const houseNumber = addr.house_number || '';
        const road = addr.road || '';
        const streetLine =
          houseNumber && road ? `${houseNumber} ${road}` : road || item.display_name.split(',')[0];
        const city = addr.city || addr.town || addr.village || addr.suburb || '';
        const state = AddressNormalizer.normalizeState(addr.state || '');
        const zip5 = addr.postcode || '';

        const secondaryText = `${city}, ${state}${zip5 ? ' ' + zip5 : ''}`;
        return {
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
        };
      });
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
      limit: '1',
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

    const item = results[0];
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
    const addr = item.address || {};
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
