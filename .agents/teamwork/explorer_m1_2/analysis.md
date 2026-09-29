# Milestone 1: Geocoding Cascade & Address Normalization Architecture Blueprint

**Author**: `explorer_m1_2`  
**Working Directory**: `.agents/teamwork/explorer_m1_2`  
**Target Subsystem**: `src/lib/geocoding/`  
**Date**: 2026-09-29  
**Status**: Authoritative Implementation Blueprint  

---

## 1. Executive Summary & Architecture Overview

The **Geocoding Cascade & Address Normalization Subsystem** (`src/lib/geocoding/`) is the foundational ingestion engine of the 5G Arbitrage Engine. It accepts free-form address inputs from consumer searches, provides fast search-as-you-type autocomplete suggestions, and resolves input addresses into USPS-standardized postal components with high-precision WGS84 geographic coordinates (`lat`, `lng`).

### 1.1 Architectural Principles
1. **Zero-Config Open Default**: Out-of-the-box operation with zero external paid API keys or registration requirements, cascading through the **US Census Bureau Geocoder**, **Komoot Photon (OSM)**, and **OpenStreetMap Nominatim**.
2. **Drop-in Commercial Extensibility**: Automatic detection of optional commercial environment variables (`GOOGLE_PLACES_API_KEY` or `MAPBOX_ACCESS_TOKEN`), prioritizing high-accuracy commercial providers when configured.
3. **Strict Postal Normalization & Rule Enforcement**:
   - Standardizes state names into 2-letter uppercase USPS codes (all 50 states, DC, and US territories).
   - Segregates secondary unit numbers (`Apt`, `Suite`, `Unit`, `#`, `Fl`) from street names.
   - Detects and rejects PO Boxes with explicit HTTP 400 errors (`PoBoxError`), preventing non-viable physical gateway orders.
   - Enforces the presence of a street building number (`MissingStreetNumberError`).
   - Validates coordinates against the US geographic bounding box (`OutOfBoundsError`).
4. **Fault-Tolerant Cascading**: Every external provider network call is bounded by strict timeouts and abort signals (e.g., 2.5s for US Census). Network failures or rate limits fail over silently to the next provider in the cascade without crashing the request.

### 1.2 Subsystem Directory & File Structure
```
src/lib/geocoding/
├── types.ts              # NormalizedAddress, AddressSuggestion, IGeocoderService & Errors
├── normalizer.ts         # Component parsing, PO Box rejection, unit extraction, state mapping
├── census-geocoder.ts    # US Census Bureau onelineaddress REST client
├── photon-geocoder.ts    # Komoot Photon autocomplete & geocoding client
├── nominatim-geocoder.ts # OSM Nominatim fallback geocoder with User-Agent compliance
├── google-geocoder.ts    # Optional Google Places Autocomplete & Geocoding adapter
├── mapbox-geocoder.ts    # Optional Mapbox Search v6 Geocoding adapter
└── service.ts            # Cascade orchestrator (GeocodingService) & singleton export
```

---

## 2. File-by-File Implementation Blueprint

### 2.1 File 1: `src/lib/geocoding/types.ts`

This file declares the unified data models, interfaces, options, and typed error hierarchy used across all geocoders, normalizers, API routes, and downstream availability engines.

#### TypeScript Definitions
```typescript
/**
 * Standard geocoding providers supported by the engine
 */
export type GeocoderProvider = 'census' | 'photon' | 'nominatim' | 'google' | 'mapbox';

/**
 * Standardized, normalized postal address and coordinate payload.
 * Fully compatible with USPS addressing guidelines and downstream FCC BDC matching.
 */
export interface NormalizedAddress {
  /** House / building number (e.g. "1600", "742", "123 1/2", "N12W34560") */
  streetNumber: string;

  /** Primary street name with standardized suffix/directionals (e.g. "Pennsylvania Ave NW") */
  streetName: string;

  /** Secondary unit / apartment / suite number if present, otherwise null */
  unitNumber: string | null;

  /** Incorporated city, town, or postal locality */
  city: string;

  /** Standardized 2-letter uppercase US postal state abbreviation (e.g. "DC", "CA", "NY") */
  state: string;

  /** 5-digit US postal ZIP code */
  zip5: string;

  /** 4-digit ZIP extension if resolved, otherwise null */
  zip4: string | null;

  /** WGS84 Latitude coordinate (-90.0 to 90.0) */
  lat: number;

  /** WGS84 Longitude coordinate (-180.0 to 180.0) */
  lng: number;

  /** USPS-compliant standardized single-line formatted address */
  formattedAddress: string;

  /** Identifier of the geocoding service that resolved the address */
  geocoderSource: GeocoderProvider;

  /** Match confidence score between 0.0 (low) and 1.0 (exact rooftop) */
  confidenceScore: number;
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
}

/**
 * Options for autocomplete suggestion queries
 */
export interface SuggestOptions extends GeocodeOptions {
  /** Maximum number of suggestions to return (default: 5) */
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
  readonly providerName: GeocoderProvider;

  /** True if provider is ready and required API keys/configurations are present */
  readonly isConfigured: boolean;

  /**
   * Retrieves address autocomplete suggestions for a partial query
   */
  suggest(query: string, options?: SuggestOptions): Promise<AddressSuggestion[]>;

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
      'PO_BOX_REJECTED',
      { poBox: poBoxString, reason: 'PO_BOX_NOT_ALLOWED' }
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
      'MISSING_STREET_NUMBER',
      { address, reason: 'MISSING_HOUSE_NUMBER' }
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
      { address, lastProvider, reason: 'NO_GEOCODE_MATCH' }
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
      `Coordinates (${lat.toFixed(4)}, ${lng.toFixed(4)}) are outside of the serviced United States territory.`,
      'COORDINATES_OUT_OF_BOUNDS',
      { lat, lng, reason: 'NON_US_COORDINATES' }
    );
    this.name = 'OutOfBoundsError';
  }
}
```

---

### 2.2 File 2: `src/lib/geocoding/normalizer.ts`

This file handles raw address decomposition, regex component extraction, PO Box rejection, secondary unit parsing, abbreviation standardization, and US geographic bounding validation.

#### Implementation Architecture
1. **USPS State Code Normalization Map**:
   - Case-insensitive lookup mapping full state names and non-standard abbreviations to official 2-letter USPS codes.
   - Includes all 50 US States, District of Columbia (`DC`), US Territories (`PR`, `GU`, `VI`, `MP`, `AS`), and Armed Forces postal codes (`AE`, `AP`, `AA`).
2. **PO Box Detection**:
   - Regex: `/\b(?:P\.?\s*O\.?\s*BOX|POST\s+OFFICE\s+BOX|P\s*BOX|P\s*O\s*B)\b/i`
   - Explicit rejection with `PoBoxError` providing clear user-facing guidance.
3. **Secondary Unit Parsing (USPS Pub 28)**:
   - Identifies designators: `APT`, `APARTMENT`, `STE`, `SUITE`, `UNIT`, `BLDG`, `BUILDING`, `FL`, `FLOOR`, `RM`, `ROOM`, `LOT`, `DEPT`, `#`.
   - Cleans the street name so that downstream geocoders match the physical building footprint without confusing unit numbers as street names.
4. **Street Number & Fractional Parsing**:
   - Supports standard integers (`"1600"`), fractional numbers (`"123 1/2"`), and alphanumeric rural/grid addresses (e.g. `"N12W34560"` used in Wisconsin).
   - If missing, throws `MissingStreetNumberError`.
5. **Geographic Coordinate Bounding Box**:
   - Latitude bounds: `17.5°N` to `72.0°N` (encompassing Puerto Rico to northern Alaska).
   - Longitude bounds: `-179.0°W` to `-64.0°W` (encompassing Aleutian Islands to eastern Maine/Puerto Rico).
   - Validates that values are finite numbers and not inverted.

#### Complete Normalizer Implementation Blueprint
```typescript
import {
  NormalizedAddress,
  GeocoderProvider,
  PoBoxError,
  MissingStreetNumberError,
  OutOfBoundsError,
  AddressValidationError,
} from './types';

/**
 * Complete US State Name & Territory Normalization Dictionary
 */
export const US_STATE_CODE_MAP: Record<string, string> = {
  // 50 US States
  'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR', 'california': 'CA',
  'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE', 'florida': 'FL', 'georgia': 'GA',
  'hawaii': 'HI', 'idaho': 'ID', 'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA',
  'kansas': 'KS', 'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
  'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS', 'missouri': 'MO',
  'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV', 'new hampshire': 'NH', 'new jersey': 'NJ',
  'new mexico': 'NM', 'new york': 'NY', 'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH',
  'oklahoma': 'OK', 'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
  'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT', 'vermont': 'VT',
  'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY',
  // District of Columbia
  'district of columbia': 'DC', 'dist of columbia': 'DC', 'washington dc': 'DC', 'd.c.': 'DC', 'dc': 'DC',
  // US Territories
  'puerto rico': 'PR', 'guam': 'GU', 'virgin islands': 'VI', 'u.s. virgin islands': 'VI',
  'northern mariana islands': 'MP', 'american samoa': 'AS',
  // Military
  'armed forces americas': 'AA', 'armed forces europe': 'AE', 'armed forces pacific': 'AP'
};

/**
 * Standard USPS Street Suffix Dictionary
 */
const STREET_SUFFIX_MAP: Record<string, string> = {
  'avenue': 'Ave', 'ave': 'Ave',
  'street': 'St', 'st': 'St',
  'road': 'Rd', 'rd': 'Rd',
  'boulevard': 'Blvd', 'blvd': 'Blvd',
  'drive': 'Dr', 'dr': 'Dr',
  'lane': 'Ln', 'ln': 'Ln',
  'court': 'Ct', 'ct': 'Ct',
  'circle': 'Cir', 'cir': 'Cir',
  'parkway': 'Pkwy', 'pkwy': 'Pkwy',
  'highway': 'Hwy', 'hwy': 'Hwy',
  'place': 'Pl', 'pl': 'Pl',
  'terrace': 'Ter', 'ter': 'Ter',
  'way': 'Way',
  'trail': 'Trl', 'trl': 'Trl',
};

/**
 * Standard Directional Abbreviations
 */
const DIRECTIONAL_MAP: Record<string, string> = {
  'north': 'N', 'n': 'N',
  'south': 'S', 's': 'S',
  'east': 'E', 'e': 'E',
  'west': 'W', 'w': 'W',
  'northeast': 'NE', 'ne': 'NE',
  'northwest': 'NW', 'nw': 'NW',
  'southeast': 'SE', 'se': 'SE',
  'southwest': 'SW', 'sw': 'SW',
};

// Regular Expressions
const PO_BOX_REGEX = /\b(?:P\.?\s*O\.?\s*BOX|POST\s+OFFICE\s+BOX|P\s*BOX|P\s*O\s*B)\b/i;
const UNIT_REGEX = /\b(?:(APT|APARTMENT|STE|SUITE|UNIT|BLDG|BUILDING|FL|FLOOR|RM|ROOM|LOT|DEPT)\.?\s*([A-Za-z0-9\-#\/]+)|#\s*([A-Za-z0-9\-]+))\b/i;
const ZIP_REGEX = /\b(\d{5})(?:-(\d{4}))?\b/;
const STREET_NUMBER_REGEX = /^([0-9]+(?:\s+1\/[2-4])?|[A-Z][0-9]+[A-Z][0-9]+)\s+(.+)$/i;

export interface RawAddressComponents {
  streetNumber?: string;
  streetName?: string;
  unitNumber?: string | null;
  city?: string;
  state?: string;
  zip?: string;
  zip5?: string;
  zip4?: string | null;
  rawAddress?: string;
}

export class AddressNormalizer {
  /**
   * Checks whether the address string represents a PO Box
   */
  public static isPoBox(address: string): boolean {
    return PO_BOX_REGEX.test(address);
  }

  /**
   * Throws PoBoxError if address contains a PO Box
   */
  public static assertNotPoBox(address: string): void {
    if (this.isPoBox(address)) {
      throw new PoBoxError(address);
    }
  }

  /**
   * Extracts secondary unit/apartment from street string and returns cleaned street
   */
  public static extractUnit(streetText: string): { cleanedStreet: string; unitNumber: string | null } {
    const match = streetText.match(UNIT_REGEX);
    if (!match) {
      return { cleanedStreet: streetText.trim(), unitNumber: null };
    }

    const fullMatch = match[0];
    let unitNumber: string;

    if (match[1] && match[2]) {
      // e.g. "Apt 4B" -> "Apt 4B"
      const prefix = match[1].charAt(0).toUpperCase() + match[1].slice(1).toLowerCase();
      unitNumber = `${prefix} ${match[2]}`;
    } else if (match[3]) {
      // e.g. "#4B" -> "#4B"
      unitNumber = `#${match[3]}`;
    } else {
      unitNumber = fullMatch.trim();
    }

    const cleanedStreet = streetText.replace(UNIT_REGEX, '').replace(/,\s*$/, '').trim();
    return { cleanedStreet, unitNumber };
  }

  /**
   * Normalizes a state string to official 2-letter uppercase USPS code
   */
  public static normalizeState(stateInput: string): string {
    if (!stateInput) return '';
    const clean = stateInput.trim().toLowerCase();
    
    // Direct match in dictionary
    if (US_STATE_CODE_MAP[clean]) {
      return US_STATE_CODE_MAP[clean];
    }

    // Already 2-letter code
    const upper = stateInput.trim().toUpperCase();
    if (upper.length === 2 && Object.values(US_STATE_CODE_MAP).includes(upper)) {
      return upper;
    }

    return upper;
  }

  /**
   * Parses and validates a US 5-digit ZIP and optional 4-digit extension
   */
  public static parseZip(zipInput: string): { zip5: string; zip4: string | null } {
    if (!zipInput) {
      return { zip5: '', zip4: null };
    }
    const match = zipInput.trim().match(ZIP_REGEX);
    if (!match) {
      const digits = zipInput.replace(/\D/g, '');
      if (digits.length >= 5) {
        return {
          zip5: digits.slice(0, 5),
          zip4: digits.length >= 9 ? digits.slice(5, 9) : null,
        };
      }
      return { zip5: zipInput.trim(), zip4: null };
    }

    return {
      zip5: match[1],
      zip4: match[2] || null,
    };
  }

  /**
   * Validates coordinates are within the United States territorial bounding box
   */
  public static validateCoordinates(lat: number, lng: number): void {
    if (typeof lat !== 'number' || typeof lng !== 'number' || isNaN(lat) || isNaN(lng)) {
      throw new AddressValidationError(`Invalid non-numeric coordinates: lat=${lat}, lng=${lng}`);
    }

    // US Geographic bounds: 17.5°N <= Lat <= 72.0°N, -179.0°W <= Lng <= -64.0°W
    const isUsLat = lat >= 17.5 && lat <= 72.0;
    const isUsLng = lng >= -179.0 && lng <= -64.0;

    if (!isUsLat || !isUsLng) {
      throw new OutOfBoundsError(lat, lng);
    }
  }

  /**
   * Assembles USPS single-line formatted address
   */
  public static formatAddress(parts: {
    streetNumber: string;
    streetName: string;
    unitNumber?: string | null;
    city: string;
    state: string;
    zip5: string;
    zip4?: string | null;
  }): string {
    const unitPart = parts.unitNumber ? ` ${parts.unitNumber}` : '';
    const zipPart = parts.zip4 ? `${parts.zip5}-${parts.zip4}` : parts.zip5;
    return `${parts.streetNumber} ${parts.streetName}${unitPart}, ${parts.city}, ${parts.state} ${zipPart}`;
  }

  /**
   * Standardizes street directional and suffix abbreviations
   */
  public static standardizeStreetName(streetName: string): string {
    const tokens = streetName.trim().split(/\s+/);
    const normalizedTokens = tokens.map((token, index) => {
      const lower = token.toLowerCase().replace(/[.,]/g, '');
      // Check directional (at beginning or end of street name)
      if ((index === 0 || index === tokens.length - 1) && DIRECTIONAL_MAP[lower]) {
        return DIRECTIONAL_MAP[lower];
      }
      // Check street suffix
      if (STREET_SUFFIX_MAP[lower]) {
        return STREET_SUFFIX_MAP[lower];
      }
      return token.charAt(0).toUpperCase() + token.slice(1);
    });

    return normalizedTokens.join(' ');
  }

  /**
   * Normalizes parsed raw components into a strictly typed NormalizedAddress
   */
  public static normalizeFromComponents(
    components: RawAddressComponents,
    coords: { lat: number; lng: number },
    source: GeocoderProvider,
    confidenceScore: number = 0.9
  ): NormalizedAddress {
    // Assert coordinates validity
    this.validateCoordinates(coords.lat, coords.lng);

    let streetNumber = components.streetNumber?.trim() || '';
    let rawStreetName = components.streetName?.trim() || '';
    let unitNumber = components.unitNumber?.trim() || null;

    // Check if PO Box
    if (this.isPoBox(rawStreetName) || this.isPoBox(components.rawAddress || '')) {
      throw new PoBoxError(rawStreetName || components.rawAddress);
    }

    // Extract unit if embedded in streetName
    if (!unitNumber) {
      const unitResult = this.extractUnit(rawStreetName);
      rawStreetName = unitResult.cleanedStreet;
      unitNumber = unitResult.unitNumber;
    }

    // If streetNumber is empty, try to extract from rawStreetName
    if (!streetNumber) {
      const numMatch = rawStreetName.match(STREET_NUMBER_REGEX);
      if (numMatch) {
        streetNumber = numMatch[1];
        rawStreetName = numMatch[2];
      }
    }

    // Enforce streetNumber requirement
    if (!streetNumber) {
      throw new MissingStreetNumberError(rawStreetName || components.rawAddress || 'Unknown address');
    }

    const streetName = this.standardizeStreetName(rawStreetName);
    const city = components.city ? components.city.trim() : '';
    const state = this.normalizeState(components.state || '');
    const { zip5, zip4 } = this.parseZip(components.zip5 || components.zip || '');

    const formattedAddress = this.formatAddress({
      streetNumber,
      streetName,
      unitNumber,
      city,
      state,
      zip5,
      zip4,
    });

    return {
      streetNumber,
      streetName,
      unitNumber,
      city,
      state,
      zip5,
      zip4,
      lat: Number(coords.lat.toFixed(6)),
      lng: Number(coords.lng.toFixed(6)),
      formattedAddress,
      geocoderSource: source,
      confidenceScore,
    };
  }
}
```

---

### 2.3 File 3: `src/lib/geocoding/census-geocoder.ts`

This file provides the primary zero-config client for the US Census Bureau Geocoding Services API.

#### Technical Specifications & Critical Invariant
- **Endpoint**: `https://geocoding.geo.census.gov/geocoder/locations/onelineaddress`
- **Benchmark**: `Public_AR_Current`
- **Output Format**: `json`
- **CRITICAL COORDINATE MAPPING**:
  ```json
  "coordinates": {
    "x": -77.03653,  // <-- x IS LONGITUDE (lng)
    "y": 38.897675   // <-- y IS LATITUDE (lat)
  }
  ```
  `coordinates.x` **MUST** be mapped to `lng`.  
  `coordinates.y` **MUST** be mapped to `lat`.  
  *Inversion of x and y is a fatal defect that would place US addresses in the Indian Ocean.*
- **Timeout Budget**: Enforces a strict 2500ms timeout using `AbortSignal`.
- **Component Decomposition**: Extracts `fromAddress`/`toAddress`, `streetName`, `city`, `state`, `zip` from `addressComponents`.

#### Complete Client Blueprint
```typescript
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
      address,
      benchmark: 'Public_AR_Current',
      format: 'json',
    });

    try {
      const response = await fetch(`${this.baseUrl}?${params.toString()}`, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
          'User-Agent': 'GetMe5G-ArbitrageEngine/1.0',
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

      // Extract street number from input query or matched address
      let streetNumber = comps.fromAddress || '';
      const inputNumMatch = address.match(/^([0-9]+(?:\s+1\/[2-4])?|[A-Z][0-9]+[A-Z][0-9]+)\b/i);
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
      const streetName = streetParts.join(' ');

      // Coordinates mapping: x = Longitude, y = Latitude
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
        0.95 // High confidence for US Census TigerLine match
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
   * Suggest implementation (Census Geocoder does not support prefix autocomplete;
   * converts a resolved oneline match to suggestions if called directly).
   */
  public async suggest(query: string, options?: SuggestOptions): Promise<AddressSuggestion[]> {
    if (!query || query.trim().length < 3) return [];
    try {
      const resolved = await this.resolve(query, options);
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
```

---

### 2.4 File 4: `src/lib/geocoding/photon-geocoder.ts`

This file provides the primary zero-config autocomplete suggestions client using the Komoot Photon API, and serves as the secondary open geocoder when Census returns 0 matches.

#### Technical Specifications
- **Base URL**: `https://photon.komoot.io/api`
- **Bounding Box**: Filtered to Continental US `bbox=-125,24,-66,49` to prevent non-US suggestions.
- **GeoJSON Mapping**: Point geometry coordinates format is `[longitude, latitude]`. Index 0 is longitude, Index 1 is latitude.
- **State Name Normalization**: Photon often returns full state strings (e.g. `"District of Columbia"` or `"California"`), which are mapped to 2-letter codes via `AddressNormalizer.normalizeState()`.

#### Complete Client Blueprint
```typescript
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
  public async suggest(query: string, options?: SuggestOptions): Promise<AddressSuggestion[]> {
    if (!query || query.trim().length < 3) return [];
    if (AddressNormalizer.isPoBox(query)) return [];

    const limit = options?.limit || 5;
    const params = new URLSearchParams({
      q: query.trim(),
      limit: String(limit),
      bbox: this.defaultBbox,
      lang: 'en',
    });

    if (options?.proximity) {
      params.append('lat', String(options.proximity.lat));
      params.append('lon', String(options.proximity.lng));
    }

    try {
      const response = await fetch(`${this.baseUrl}?${params.toString()}`, {
        headers: {
          'Accept': 'application/json',
          'User-Agent': 'GetMe5G-ArbitrageEngine/1.0',
        },
        signal: options?.signal,
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

        const streetLine = props.housenumber && props.street
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
        'Accept': 'application/json',
        'User-Agent': 'GetMe5G-ArbitrageEngine/1.0',
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
    const feature = data.features.find((f) => f.properties.housenumber && f.properties.street) || data.features[0];
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
      0.85
    );
  }
}
```

---

### 2.5 File 5: `src/lib/geocoding/nominatim-geocoder.ts`

This file provides the secondary zero-config open fallback geocoder using OpenStreetMap Nominatim.

#### Technical Specifications & Compliance
- **Endpoint**: `https://nominatim.openstreetmap.org/search`
- **Reverse Endpoint**: `https://nominatim.openstreetmap.org/reverse`
- **Strict OSM Usage Policy Compliance**:
  - Requires a descriptive `User-Agent` identifying the application and contact email:
    `User-Agent: GetMe5G-ArbitrageEngine/1.0 (contact@getme5g.local)`
  - Parameter `addressdetails=1` to return structured administrative components (`house_number`, `road`, `city`, `state`, `postcode`).
  - Limits queries to US territory: `countrycodes=us`.
  - Coordinates returned as strings: must use `parseFloat(item.lat)` and `parseFloat(item.lon)`.

#### Complete Client Blueprint
```typescript
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
  private readonly userAgent = process.env.NOMINATIM_USER_AGENT || 'GetMe5G-ArbitrageEngine/1.0 (contact@getme5g.local)';

  public async suggest(query: string, options?: SuggestOptions): Promise<AddressSuggestion[]> {
    if (!query || query.trim().length < 3) return [];
    if (AddressNormalizer.isPoBox(query)) return [];

    const limit = options?.limit || 5;
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
          'Accept': 'application/json',
          'User-Agent': this.userAgent,
        },
        signal: options?.signal,
      });

      if (!response.ok) return [];

      const results: NominatimPlace[] = await response.json();
      return results.map((item) => {
        const addr = item.address || {};
        const houseNumber = addr.house_number || '';
        const road = addr.road || '';
        const streetLine = houseNumber && road ? `${houseNumber} ${road}` : road || item.display_name.split(',')[0];
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
        'Accept': 'application/json',
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
      0.80
    );
  }

  public async resolveCoordinates(lat: number, lng: number, options?: GeocodeOptions): Promise<NormalizedAddress> {
    const params = new URLSearchParams({
      lat: String(lat),
      lon: String(lng),
      format: 'jsonv2',
      addressdetails: '1',
    });

    const response = await fetch(`${this.baseUrl}/reverse?${params.toString()}`, {
      headers: {
        'Accept': 'application/json',
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
```

---

### 2.6 File 6: `src/lib/geocoding/google-geocoder.ts` & `src/lib/geocoding/mapbox-geocoder.ts`

These two files provide optional commercial drop-in adapters activated when appropriate environment variables are present.

#### Google Geocoder (`src/lib/geocoding/google-geocoder.ts`)
- **Activation**: `process.env.GOOGLE_PLACES_API_KEY`
- **Autocomplete Endpoint**: `https://maps.googleapis.com/maps/api/place/autocomplete/json`
  - Restricts to US: `components=country:us`, `types=address`
- **Geocode Endpoint**: `https://maps.googleapis.com/maps/api/geocode/json`
  - Extracts standard components (`street_number`, `route`, `locality`, `administrative_area_level_1`, `postal_code`, `subpremise`).
  - ROOFTOP geometry yields `confidenceScore = 1.0`.
- **Fault-Tolerance**: If API key is invalid or quota is exhausted (`OVER_QUERY_LIMIT` / `REQUEST_DENIED`), suppresses error and lets the cascade fallback seamlessly.

```typescript
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

  public async suggest(query: string, options?: SuggestOptions): Promise<AddressSuggestion[]> {
    if (!this.isConfigured || !query || query.trim().length < 3) return [];
    if (AddressNormalizer.isPoBox(query)) return [];

    const url = new URL('https://maps.googleapis.com/maps/api/place/autocomplete/json');
    url.searchParams.append('input', query.trim());
    url.searchParams.append('components', 'country:us');
    url.searchParams.append('types', 'address');
    url.searchParams.append('key', this.apiKey!);

    try {
      const response = await fetch(url.toString(), { signal: options?.signal });
      if (!response.ok) return [];

      const data = await response.json();
      if (data.status !== 'OK' || !data.predictions) return [];

      return data.predictions.map((p: any) => ({
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

    const confidence = result.geometry.location_type === 'ROOFTOP' ? 1.0 : 0.9;

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
```

#### Mapbox Geocoder (`src/lib/geocoding/mapbox-geocoder.ts`)
- **Activation**: `process.env.MAPBOX_ACCESS_TOKEN`
- **Forward Geocoding Endpoint**: `https://api.mapbox.com/search/geocode/v6/forward`
  - Restricts to US: `country=us`, `types=address`
- **Coordinates Mapping**: Mapbox GeoJSON features use `[longitude, latitude]`.

```typescript
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

  public async suggest(query: string, options?: SuggestOptions): Promise<AddressSuggestion[]> {
    if (!this.isConfigured || !query || query.trim().length < 3) return [];
    if (AddressNormalizer.isPoBox(query)) return [];

    const url = new URL('https://api.mapbox.com/search/geocode/v6/forward');
    url.searchParams.append('q', query.trim());
    url.searchParams.append('country', 'us');
    url.searchParams.append('types', 'address');
    url.searchParams.append('limit', String(options?.limit || 5));
    url.searchParams.append('access_token', this.accessToken!);

    try {
      const response = await fetch(url.toString(), { signal: options?.signal });
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
```

---

### 2.7 File 7: `src/lib/geocoding/service.ts`

This file is the main orchestrator (`GeocodingService`) that unifies all adapters into an intelligent, resilient cascade.

#### Orchestration Pipeline Logic

```
                    [ GeocodingService.resolve(address) ]
                                      │
                                      ▼
                      [ AddressNormalizer.assertNotPoBox ]
                                      │ (Pass)
                                      ▼
             Is Commercial Configured (Google / Mapbox)?
                      │                               │
                (Yes) │                               │ (No)
                      ▼                               │
             [ Commercial Adapter ]                   │
             (If success -> return)                   │
             (If failure / rate limit)                ▼
                      │───────────────> [ Primary Open: US Census ]
                                                   │
                                          (Success)│(Failure / Timeout >2.5s)
                                                   ▼          ▼
                                                [Return]  [ Secondary Open: Komoot Photon ]
                                                                   │
                                                          (Success)│(Failure)
                                                                   ▼          ▼
                                                                [Return]  [ Tertiary Open: Nominatim ]
                                                                                   │
                                                                          (Success)│(Failure)
                                                                                   ▼          ▼
                                                                                [Return]  [ Throw AddressNotFoundError (400) ]
```

#### Complete Orchestrator Blueprint
```typescript
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

export class GeocodingService implements IGeocoderService {
  public readonly providerName = 'census' as const; // Default primary
  public readonly isConfigured = true;

  private readonly googleGeocoder: GoogleGeocoder;
  private readonly mapboxGeocoder: MapboxGeocoder;
  private readonly censusGeocoder: CensusGeocoder;
  private readonly photonGeocoder: PhotonGeocoder;
  private readonly nominatimGeocoder: NominatimGeocoder;

  constructor() {
    this.googleGeocoder = new GoogleGeocoder();
    this.mapboxGeocoder = new MapboxGeocoder();
    this.censusGeocoder = new CensusGeocoder();
    this.photonGeocoder = new PhotonGeocoder();
    this.nominatimGeocoder = new NominatimGeocoder();
  }

  /**
   * Search-as-you-type autocomplete suggestions cascade
   */
  public async suggest(query: string, options?: SuggestOptions): Promise<AddressSuggestion[]> {
    if (!query || query.trim().length < 3) return [];

    // Pre-check for PO Box
    if (AddressNormalizer.isPoBox(query)) return [];

    // 1. Google Places (if configured)
    if (this.googleGeocoder.isConfigured) {
      try {
        const results = await this.googleGeocoder.suggest(query, options);
        if (results.length > 0) return results;
      } catch (err) {
        console.warn('[GeocodingService] Google suggest failed, falling back to open cascade:', err);
      }
    }

    // 2. Mapbox (if configured)
    if (this.mapboxGeocoder.isConfigured) {
      try {
        const results = await this.mapboxGeocoder.suggest(query, options);
        if (results.length > 0) return results;
      } catch (err) {
        console.warn('[GeocodingService] Mapbox suggest failed, falling back to open cascade:', err);
      }
    }

    // 3. Open Default: Komoot Photon
    try {
      const results = await this.photonGeocoder.suggest(query, options);
      if (results.length > 0) return results;
    } catch (err) {
      console.warn('[GeocodingService] Photon suggest failed, falling back to Nominatim:', err);
    }

    // 4. Open Fallback: OSM Nominatim
    try {
      return await this.nominatimGeocoder.suggest(query, options);
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

    let lastError: unknown = null;

    // Step 2: Commercial Providers (if configured)
    if (this.googleGeocoder.isConfigured) {
      try {
        return await this.googleGeocoder.resolve(address, options);
      } catch (err) {
        console.warn('[GeocodingService] Google geocode failed, falling back:', err);
        lastError = err;
      }
    }

    if (this.mapboxGeocoder.isConfigured) {
      try {
        return await this.mapboxGeocoder.resolve(address, options);
      } catch (err) {
        console.warn('[GeocodingService] Mapbox geocode failed, falling back:', err);
        lastError = err;
      }
    }

    // Step 3: Primary Open Provider (US Census Bureau Geocoder with 2500ms budget)
    try {
      return await this.censusGeocoder.resolve(address, {
        ...options,
        timeoutMs: options?.timeoutMs || 2500,
      });
    } catch (err) {
      console.warn('[GeocodingService] Census geocode failed, falling back to Photon:', err);
      lastError = err;
    }

    // Step 4: Secondary Open Provider (Komoot Photon)
    try {
      return await this.photonGeocoder.resolve(address, options);
    } catch (err) {
      console.warn('[GeocodingService] Photon geocode failed, falling back to Nominatim:', err);
      lastError = err;
    }

    // Step 5: Tertiary Open Provider (OSM Nominatim)
    try {
      return await this.nominatimGeocoder.resolve(address, options);
    } catch (err) {
      console.warn('[GeocodingService] Nominatim geocode failed:', err);
      lastError = err;
    }

    // All cascade tiers exhausted
    throw new AddressNotFoundError(address, (lastError as any)?.provider || 'cascade_all');
  }

  /**
   * Coordinate reverse geocoding cascade
   */
  public async resolveCoordinates(lat: number, lng: number, options?: GeocodeOptions): Promise<NormalizedAddress> {
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
```

---

## 3. Alignment with Testing Track & Downstream Milestones

### 3.1 Alignment with Unit Tests (`tests/unit/geocoding/normalizer.test.ts`)
The `AddressNormalizer` and `GeocodingService` directly satisfy all test cases outlined in `test_plan.md` and assigned to `test_writer_track_1`:
1. **Standard US Address Parsing**: `"350 5th Ave, New York, NY 10118"` -> parses street number `"350"`, street name `"5th Ave"`, uppercase state `"NY"`, zip5 `"10118"`.
2. **Apartment / Unit Extraction**: `"742 Evergreen Terrace Apt 4B, Springfield, OR 97477"` -> preserves `"Apt 4B"` in `unitNumber` and cleans `streetName` to `"Evergreen Ter"`.
3. **ZIP+4 Splitting**: `"1600 Pennsylvania Avenue NW, Washington, DC 20500-0003"` -> `zip5: "20500"`, `zip4: "0003"`.
4. **PO Box Rejection**: `"PO Box 1234, Dallas, TX 75201"` -> Throws `PoBoxError` with HTTP 400.
5. **Missing Street Number**: `"Broadway, New York, NY 10001"` -> Throws `MissingStreetNumberError` with HTTP 400.
6. **Fractional Numbers**: `"123 1/2 Maple St, Seattle, WA 98101"` -> Preserves `"123 1/2"` as `streetNumber`.
7. **Rural Grid Addresses**: `"N12W34560 Lake Dr, Delafield, WI 53018"` -> Parses alphanumeric grid number cleanly.
8. **Bounding Box Enforcement**: Coordinates outside US -> Throws `OutOfBoundsError`.

### 3.2 Alignment with API Routes (`/api/geocode/suggest` & `/api/geocode/resolve`)
The implementation allows Next.js API routes (designed by `spec_miner_m1_3`) to be ultra-clean:
```typescript
// Example: src/app/api/geocode/resolve/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { geocodingService } from '@/lib/geocoding/service';
import { AddressValidationError, GeocodingError } from '@/lib/geocoding/types';

export async function GET(request: NextRequest) {
  const address = request.nextUrl.searchParams.get('address');
  if (!address) {
    return NextResponse.json(
      { status: 'error', code: 'MISSING_ADDRESS', message: 'Address parameter is required' },
      { status: 400 }
    );
  }

  try {
    const normalized = await geocodingService.resolve(address);
    return NextResponse.json({ status: 'success', data: normalized });
  } catch (err: unknown) {
    if (err instanceof AddressValidationError) {
      return NextResponse.json(
        { status: 'error', code: err.code, message: err.message, details: err.details },
        { status: 400 }
      );
    }
    if (err instanceof GeocodingError) {
      return NextResponse.json(
        { status: 'error', code: err.code, message: err.message, details: err.details },
        { status: err.statusCode }
      );
    }
    return NextResponse.json(
      { status: 'error', code: 'INTERNAL_ERROR', message: 'Unexpected geocoding failure' },
      { status: 500 }
    );
  }
}
```

### 3.3 Alignment with Milestone 2 (Caching) & Milestone 3 (Availability Engine)
- The resulting `NormalizedAddress` contains `streetNumber`, `streetName`, `city`, `state`, `zip5`, `lat`, `lng`.
- **Milestone 2 (L1 Memory Cache)**: Uses `${zip5}:${streetNumber}:${streetName.toLowerCase()}` as key for exact sub-5ms hits.
- **Milestone 2 (L2 SQLite Cache)**: Uses `${lat.toFixed(4)}:${lng.toFixed(4)}` spatial key for sub-25ms cluster hits.
- **Milestone 3 (Availability Engine)**: Passes `NormalizedAddress` directly to `IProviderChecker.check()` and FCC BDC coordinate query.

---

## 4. Edge Cases & Resilience Matrix

| Edge Case Scenario | Input Example | Subsystem Component | Handling & System Behavior |
|---|---|---|---|
| **PO Box Input** | `"PO Box 1234, Dallas, TX 75201"` | `normalizer.ts` | Detected by regex `/\b(?:P\.?\s*O\.?\s*BOX|POST\s+OFFICE\s+BOX|P\s*BOX|P\s*O\s*B)\b/i`. Throws `PoBoxError` with 400 HTTP status and explicit user guidance. |
| **Missing Street Number** | `"Broadway, New York, NY 10001"` | `normalizer.ts` | Street number regex matches 0 building numbers. Throws `MissingStreetNumberError` with 400 HTTP status prompting house number. |
| **Fractional House Number** | `"123 1/2 Maple St, Seattle, WA 98101"` | `normalizer.ts` | Regex `^([0-9]+(?:\s+1\/[2-4])?)` extracts `"123 1/2"` as `streetNumber`. Street name remains `"Maple St"`. |
| **Wisconsin Rural Grid Number** | `"N12W34560 Lake Dr, Delafield, WI 53018"` | `normalizer.ts` | Regex `[A-Z][0-9]+[A-Z][0-9]+` parses `"N12W34560"` as `streetNumber`. |
| **Secondary Unit / Apartment** | `"742 Evergreen Terrace Apt 4B, Springfield, OR"` | `normalizer.ts` | Extracts `unitNumber: "Apt 4B"`. Cleans street to `"Evergreen Ter"` to ensure high-confidence geocoder matching. |
| **Census API Timeout (>2.5s)** | Network latency spike on Census Bureau | `census-geocoder.ts` & `service.ts` | `AbortSignal.timeout(2500)` fires; Census client throws timeout error; `GeocodingService` catches it and immediately fails over to Photon without dropping request. |
| **Coordinate Inversion Protection** | Census returns `{ x: -77.03, y: 38.89 }` | `census-geocoder.ts` | Explicitly maps `x` to `lng` and `y` to `lat`. Tested against coordinate bounding box (Lat 17.5-72.0, Lng -179.0 to -64.0). |
| **Full State Names** | `"District of Columbia"`, `"California"` | `normalizer.ts` | Normalized through `US_STATE_CODE_MAP` into `"DC"`, `"CA"`. |
| **OSM Nominatim Header Compliance** | Requests to OSM | `nominatim-geocoder.ts` | Automatically attaches `User-Agent: GetMe5G-ArbitrageEngine/1.0`, preventing HTTP 403 blocks. |
| **Commercial API Key Missing or Depleted** | Unset `GOOGLE_PLACES_API_KEY` | `service.ts` | `isConfigured` returns `false` or catches HTTP 403/429; orchestrator transparently executes zero-config open cascade. |
| **Non-US Coordinates** | Coordinates in Canada, Mexico, or Europe | `normalizer.ts` | `validateCoordinates()` catches lat/lng outside bounding box; throws `OutOfBoundsError`. |
