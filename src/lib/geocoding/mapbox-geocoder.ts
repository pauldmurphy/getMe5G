import {
  IGeocoderService,
  NormalizedAddress,
  AddressSuggestion,
  GeocodeOptions,
  SuggestOptions,
  AddressNotFoundError,
} from './types';
import { AddressNormalizer } from './normalizer';

export class MapboxGeocoder implements IGeocoderService {
  public readonly providerName = 'mapbox' as const;

  private get accessToken(): string | undefined {
    return process.env.MAPBOX_ACCESS_TOKEN;
  }

  public get isConfigured(): boolean {
    return Boolean(this.accessToken && this.accessToken.trim().length > 0);
  }

  public async suggest(query: string, options?: SuggestOptions | number): Promise<AddressSuggestion[]> {
    if (!this.isConfigured || !query || query.trim().length < 3) return [];
    if (AddressNormalizer.isPoBox(query)) return [];

    const opts: SuggestOptions = typeof options === 'number' ? { limit: options } : options || {};
    const limit = Math.min(Math.max(opts.limit || 5, 1), 10);

    const url = new URL('https://api.mapbox.com/search/geocode/v6/forward');
    url.searchParams.append('q', query.trim());
    url.searchParams.append('country', 'us');
    url.searchParams.append('types', 'address');
    url.searchParams.append('limit', String(limit));
    url.searchParams.append('access_token', this.accessToken!);

    try {
      const response = await fetch(url.toString(), { signal: opts.signal });
      if (!response.ok) return [];

      const data = await response.json();
      if (!data.features) return [];

      return data.features.map((f: any) => {
        const props = f.properties || {};
        const [lon, lat] = f.geometry.coordinates;
        return {
          id: `mapbox-${f.id}`,
          label: props.full_address || props.name,
          streetLine: props.name || '',
          city: props.context?.place?.name || '',
          state: props.context?.region?.region_code || '',
          zip5: props.context?.postcode?.name,
          lat,
          lng: lon,
          source: this.providerName,
          secondaryText: `${props.context?.place?.name || ''}, ${props.context?.region?.region_code || ''}`,
        };
      });
    } catch {
      return [];
    }
  }

  public async resolve(address: string, options?: GeocodeOptions): Promise<NormalizedAddress> {
    if (!this.isConfigured) {
      throw new Error('Mapbox Geocoder is not configured (missing MAPBOX_ACCESS_TOKEN)');
    }
    AddressNormalizer.assertNotPoBox(address);

    const url = new URL('https://api.mapbox.com/search/geocode/v6/forward');
    url.searchParams.append('q', address.trim());
    url.searchParams.append('country', 'us');
    url.searchParams.append('types', 'address');
    url.searchParams.append('limit', '1');
    url.searchParams.append('access_token', this.accessToken!);

    const response = await fetch(url.toString(), { signal: options?.signal });
    if (!response.ok) {
      throw new Error(`Mapbox returned HTTP ${response.status}`);
    }

    const data = await response.json();
    if (!data.features || data.features.length === 0) {
      throw new AddressNotFoundError(address, this.providerName);
    }

    const f = data.features[0];
    const props = f.properties || {};
    const [lon, lat] = f.geometry.coordinates;

    const ctx = props.context || {};
    const streetNumber = ctx.address?.address_number || '';
    const streetName = ctx.street?.name || props.name || '';
    const city = ctx.place?.name || '';
    const state = AddressNormalizer.normalizeState(ctx.region?.region_code || ctx.region?.name || '');
    const zip5 = ctx.postcode?.name || '';

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
      0.95
    );
  }
}
