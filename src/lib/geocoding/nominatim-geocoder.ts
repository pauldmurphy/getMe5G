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
