/**
 * Standard geocoding providers supported by the engine
 */
export type GeocoderProvider = 'census' | 'photon' | 'nominatim' | 'google' | 'mapbox';

/**
 * Standardized, normalized postal address and coordinate payload.
 * Fully compatible with USPS addressing guidelines and downstream FCC BDC matching.
 */
export interface NormalizedAddress {
  /** House / building number (e.g. "1600", "742", "123 1/2", "N12W34560", Queens hyphenated "120-05") */
  streetNumber: string;

  /** Primary street name with standardized suffix/directionals (e.g. "Pennsylvania Ave NW") */
  streetName: string;

  /** Secondary unit / apartment / suite number if present, otherwise null */
  unitNumber?: string | null;

  /** Incorporated city, town, or postal locality */
  city: string;

  /** Standardized 2-letter uppercase US postal state abbreviation (e.g. "DC", "CA", "NY") */
  state: string;

  /** 5-digit US postal ZIP code */
  zip5: string;

  /** 4-digit ZIP extension if resolved, otherwise null */
  zip4?: string | null;

  /** WGS84 Latitude coordinate (-90.0 to 90.0) */
  lat: number;

  /** WGS84 Longitude coordinate (-180.0 to 180.0) */
  lng: number;

  /** USPS-compliant standardized single-line formatted address */
  formattedAddress: string;

  /** Identifier of the geocoding service that resolved the address */
  geocoderSource?: GeocoderProvider;

  /** Match confidence score between 0.0 (low) and 1.0 (exact rooftop) */
  confidenceScore?: number;
}

/**
 * Autocomplete address suggestion for search dropdowns
 */
export interface AddressSuggestion {
  /** Unique suggestion ID (e.g. "photon-123456" or "google-ChIJ...") */
  id: string;

  /** Full formatted display string (e.g. "1600 Pennsylvania Ave NW, Washington, DC 20500") */
  label: string;

  /** Primary street line (e.g. "1600 Pennsylvania Ave NW") */
  streetLine: string;

  /** City / locality */
  city: string;

  /** Standardized 2-letter uppercase state code */
  state: string;

  /** 5-digit ZIP code if available */
  zip5?: string;

  /** Latitude if pre-resolved by provider */
  lat?: number;

  /** Longitude if pre-resolved by provider */
  lng?: number;

  /** Provider that yielded the suggestion */
  source: GeocoderProvider;

  /** UI secondary helper text (e.g. "Washington, DC 20500") */
  secondaryText?: string;
}

/**
 * Options for geocoding operations
 */
export interface GeocodeOptions {
  /** Optional AbortSignal for cancellation */
  signal?: AbortSignal;
  /** Maximum timeout in milliseconds */
  timeoutMs?: number;
  /** If true, bypasses in-memory cache and forces live cascade */
  fresh?: boolean;
}

/**
 * Options for autocomplete suggestion queries
 */
export interface SuggestOptions extends GeocodeOptions {
  /** Maximum number of suggestions to return (default: 5, max: 10) */
  limit?: number;
  /** Optional user coordinate bias for proximity search */
  proximity?: {
    lat: number;
    lng: number;
  };
}

/**
 * Pluggable Geocoder Interface Contract
 */
export interface IGeocoderService {
  /** Human-readable identifier of the geocoder provider */
  readonly providerName: GeocoderProvider | string;

  /** True if provider is ready and required API keys/configurations are present */
  readonly isConfigured?: boolean;

  /**
   * Retrieves address autocomplete suggestions for a partial query
   */
  suggest(query: string, options?: SuggestOptions | number): Promise<AddressSuggestion[]>;

  /**
   * Resolves a physical address into normalized postal components and coordinates
   */
  resolve(address: string, options?: GeocodeOptions): Promise<NormalizedAddress>;

  /**
   * Optional reverse geocoding from coordinates to normalized address
   */
  resolveCoordinates?(lat: number, lng: number, options?: GeocodeOptions): Promise<NormalizedAddress>;
}

// ---------------------------------------------------------------------------
// Error Class Hierarchy
// ---------------------------------------------------------------------------

/**
 * Base Geocoding Error
 */
export class GeocodingError extends Error {
  readonly code: string;
  readonly statusCode: number;
  readonly details?: Record<string, unknown>;

  constructor(
    message: string,
    code: string = 'GEOCODING_ERROR',
    statusCode: number = 500,
    details?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'GeocodingError';
    this.code = code;
    this.statusCode = statusCode;
    this.details = details;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

/**
 * Validation error thrown when an address violates formatting or physical constraints
 */
export class AddressValidationError extends GeocodingError {
  constructor(message: string, code: string = 'ADDRESS_VALIDATION_ERROR', details?: Record<string, unknown>) {
    super(message, code, 400, details);
    this.name = 'AddressValidationError';
  }
}

/**
 * Thrown when user submits a PO Box or postal box address
 */
export class PoBoxError extends AddressValidationError {
  constructor(poBoxString?: string) {
    super(
      'Fixed wireless home internet requires a physical residential street address. PO Boxes are not eligible.',
      'PO_BOX_NOT_SUPPORTED',
      {
        submittedAddress: poBoxString,
        poBox: poBoxString,
        field: 'address',
        reason: 'PO Boxes do not possess discrete physical rooftop coordinates for cellular RF line-of-sight analysis or home gateway delivery.',
      }
    );
    this.name = 'PoBoxError';
  }
}

/**
 * Thrown when an address is missing a building/street number
 */
export class MissingStreetNumberError extends AddressValidationError {
  constructor(address: string) {
    super(
      'Please provide a full street address including building number.',
      'STREET_NUMBER_REQUIRED',
      {
        submittedAddress: address,
        address,
        field: 'address',
        reason: 'Building or house number is missing from the query.',
      }
    );
    this.name = 'MissingStreetNumberError';
  }
}

/**
 * Thrown when all geocoding providers fail to find a matching location
 */
export class AddressNotFoundError extends GeocodingError {
  constructor(address: string, lastProvider?: string) {
    super(
      `Unable to geocode the submitted address into a valid US physical location: "${address}".`,
      'ADDRESS_NOT_RESOLVED',
      400,
      {
        submittedAddress: address,
        address,
        lastProvider,
        field: 'address',
        reason: 'Zero matches returned across geocoding cascade (Census, Photon, Nominatim).',
      }
    );
    this.name = 'AddressNotFoundError';
  }
}

/**
 * Thrown when coordinates fall outside the supported US territorial bounding box
 */
export class OutOfBoundsError extends AddressValidationError {
  constructor(lat: number, lng: number) {
    super(
      `Address coordinates (${lat.toFixed(4)}, ${lng.toFixed(4)}) are outside the United States broadband coverage area.`,
      'OUT_OF_COVERAGE_AREA',
      {
        lat,
        lng,
        reason: 'Only US postal addresses are supported for 5G Home Internet availability.',
      }
    );
    this.name = 'OutOfBoundsError';
  }
}

/**
 * Thrown when coordinate inputs fail numerical validity
 */
export class InvalidCoordinatesError extends GeocodingError {
  constructor(lat: number, lng: number, reason?: string) {
    super(
      'Provided latitude or longitude coordinate is outside valid geographical boundaries.',
      'INVALID_COORDINATES',
      422,
      {
        lat,
        lng,
        reason: reason || 'Latitude must be between -90.0 and 90.0 and Longitude between -180.0 and 180.0 degrees.',
      }
    );
    this.name = 'InvalidCoordinatesError';
  }
}

/**
 * Thrown when upstream geocoders time out
 */
export class GeocoderTimeoutError extends GeocodingError {
  constructor(message: string = 'Upstream geocoding providers timed out. Please retry shortly.', details?: Record<string, unknown>) {
    super(message, 'GEOCODER_UPSTREAM_TIMEOUT', 504, details);
    this.name = 'GeocoderTimeoutError';
  }
}
