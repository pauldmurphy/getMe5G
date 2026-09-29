import {
  IGeocoderService,
  NormalizedAddress,
  AddressSuggestion,
  GeocodeOptions,
  SuggestOptions,
  AddressNotFoundError,
} from './types';
import { AddressNormalizer } from './normalizer';

export class GoogleGeocoder implements IGeocoderService {
  public readonly providerName = 'google' as const;

  private get apiKey(): string | undefined {
    return process.env.GOOGLE_PLACES_API_KEY;
  }

  public get isConfigured(): boolean {
    return Boolean(this.apiKey && this.apiKey.trim().length > 0);
  }

  public async suggest(query: string, options?: SuggestOptions | number): Promise<AddressSuggestion[]> {
    if (!this.isConfigured || !query || query.trim().length < 3) return [];
    if (AddressNormalizer.isPoBox(query)) return [];

    const opts: SuggestOptions = typeof options === 'number' ? { limit: options } : options || {};
    const url = new URL('https://maps.googleapis.com/maps/api/place/autocomplete/json');
    url.searchParams.append('input', query.trim());
    url.searchParams.append('components', 'country:us');
    url.searchParams.append('types', 'address');
    url.searchParams.append('key', this.apiKey!);

    try {
      const response = await fetch(url.toString(), { signal: opts.signal });
      if (!response.ok) return [];

      const data = await response.json();
      if (data.status !== 'OK' || !data.predictions) return [];

      return data.predictions.slice(0, opts.limit || 5).map((p: any) => ({
        id: `google-${p.place_id}`,
        label: p.description,
        streetLine: p.structured_formatting?.main_text || p.description.split(',')[0],
        city: '',
        state: '',
        source: this.providerName,
        secondaryText: p.structured_formatting?.secondary_text || '',
      }));
    } catch {
      return [];
    }
  }

  public async resolve(address: string, options?: GeocodeOptions): Promise<NormalizedAddress> {
    if (!this.isConfigured) {
      throw new Error('Google Geocoder is not configured (missing GOOGLE_PLACES_API_KEY)');
    }
    AddressNormalizer.assertNotPoBox(address);

    const url = new URL('https://maps.googleapis.com/maps/api/geocode/json');
    url.searchParams.append('address', address.trim());
    url.searchParams.append('components', 'country:us');
    url.searchParams.append('key', this.apiKey!);

    const response = await fetch(url.toString(), { signal: options?.signal });
    if (!response.ok) {
      throw new Error(`Google API returned HTTP ${response.status}`);
    }

    const data = await response.json();
    if (data.status !== 'OK' || !data.results || data.results.length === 0) {
      throw new AddressNotFoundError(address, this.providerName);
    }

    const result = data.results[0];
    const getComponent = (type: string, useShort = false) => {
      const c = result.address_components.find((comp: any) => comp.types.includes(type));
      return c ? (useShort ? c.short_name : c.long_name) : '';
    };

    const streetNumber = getComponent('street_number');
    const streetName = getComponent('route');
    const unitNumber = getComponent('subpremise') ? `Apt ${getComponent('subpremise')}` : null;
    const city = getComponent('locality') || getComponent('sublocality');
    const state = getComponent('administrative_area_level_1', true);
    const zip5 = getComponent('postal_code');
    const zip4 = getComponent('postal_code_suffix');
    const lat = result.geometry.location.lat;
    const lng = result.geometry.location.lng;

    const confidence = result.geometry.location_type === 'ROOFTOP' ? 1.0 : 0.95;

    return AddressNormalizer.normalizeFromComponents(
      {
        streetNumber,
        streetName,
        unitNumber,
        city,
        state,
        zip5,
        zip4,
        rawAddress: address,
      },
      { lat, lng },
      this.providerName,
      confidence
    );
  }
}
