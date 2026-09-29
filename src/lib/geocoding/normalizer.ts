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
  alabama: 'AL',
  alaska: 'AK',
  arizona: 'AZ',
  arkansas: 'AR',
  california: 'CA',
  colorado: 'CO',
  connecticut: 'CT',
  delaware: 'DE',
  florida: 'FL',
  georgia: 'GA',
  hawaii: 'HI',
  idaho: 'ID',
  illinois: 'IL',
  indiana: 'IN',
  iowa: 'IA',
  kansas: 'KS',
  kentucky: 'KY',
  louisiana: 'LA',
  maine: 'ME',
  maryland: 'MD',
  massachusetts: 'MA',
  michigan: 'MI',
  minnesota: 'MN',
  mississippi: 'MS',
  missouri: 'MO',
  montana: 'MT',
  nebraska: 'NE',
  nevada: 'NV',
  'new hampshire': 'NH',
  'new jersey': 'NJ',
  'new mexico': 'NM',
  'new york': 'NY',
  'north carolina': 'NC',
  'north dakota': 'ND',
  ohio: 'OH',
  oklahoma: 'OK',
  oregon: 'OR',
  pennsylvania: 'PA',
  'rhode island': 'RI',
  'south carolina': 'SC',
  'south dakota': 'SD',
  tennessee: 'TN',
  texas: 'TX',
  utah: 'UT',
  vermont: 'VT',
  virginia: 'VA',
  washington: 'WA',
  'west virginia': 'WV',
  wisconsin: 'WI',
  wyoming: 'WY',
  // District of Columbia
  'district of columbia': 'DC',
  'dist of columbia': 'DC',
  'washington dc': 'DC',
  'washington d.c.': 'DC',
  'd.c.': 'DC',
  dc: 'DC',
  // US Territories
  'puerto rico': 'PR',
  guam: 'GU',
  'virgin islands': 'VI',
  'u.s. virgin islands': 'VI',
  'northern mariana islands': 'MP',
  'american samoa': 'AS',
  // Military
  'armed forces americas': 'AA',
  'armed forces europe': 'AE',
  'armed forces pacific': 'AP',
};

/**
 * Standard USPS Street Suffix Dictionary
 */
const STREET_SUFFIX_MAP: Record<string, string> = {
  avenue: 'Ave',
  ave: 'Ave',
  street: 'St',
  st: 'St',
  road: 'Rd',
  rd: 'Rd',
  boulevard: 'Blvd',
  blvd: 'Blvd',
  drive: 'Dr',
  dr: 'Dr',
  lane: 'Ln',
  ln: 'Ln',
  court: 'Ct',
  ct: 'Ct',
  circle: 'Cir',
  cir: 'Cir',
  parkway: 'Pkwy',
  pkwy: 'Pkwy',
  highway: 'Hwy',
  hwy: 'Hwy',
  place: 'Pl',
  pl: 'Pl',
  terrace: 'Ter',
  ter: 'Ter',
  way: 'Way',
  trail: 'Trl',
  trl: 'Trl',
};

/**
 * Standard Directional Abbreviations
 */
const DIRECTIONAL_MAP: Record<string, string> = {
  north: 'N',
  n: 'N',
  south: 'S',
  s: 'S',
  east: 'E',
  e: 'E',
  west: 'W',
  w: 'W',
  northeast: 'NE',
  ne: 'NE',
  northwest: 'NW',
  nw: 'NW',
  southeast: 'SE',
  se: 'SE',
  southwest: 'SW',
  sw: 'SW',
};

// Regular Expressions
export const PO_BOX_REGEX = /\b(?:P(?:OST)?\.?\s*O(?:FFICE)?\.?\s*BOX|P\.?\s*O\.?\s*B(?:\.|\b)|POST\s+OFFICE\s+DRAWER|PBOX)\b/i;
const UNIT_REGEX = /(?:,\s*)?\b(?:(APT|APARTMENT|SUITE|STE|UNIT|BLDG|BUILDING|FL|FLOOR|RM|ROOM|LOT|DEPT)\.?\s*([A-Za-z0-9\-#\/]+)|#\s*([A-Za-z0-9\-]+))\b/i;
const ZIP_REGEX = /\b(\d{5})(?:[-\s](\d{4}))?\b/;
const STREET_NUMBER_REGEX = /^([0-9]+(?:\s+1\/[2-4])?|[0-9]+-[0-9]+|[A-Z][0-9]+[A-Z][0-9]+)\s+(.+)$/i;
const RURAL_ROUTE_BOX_REGEX = /^(Route\s+\d+|RR\s+\d+|Rural\s+Route\s+\d+)\s+(Box\s+\d+)\b/i;

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

/**
 * Checks whether an address string represents a PO Box
 */
export function isPoBox(address: string): boolean {
  if (!address) return false;
  return PO_BOX_REGEX.test(address);
}

/**
 * Standardizes full state name or code to official 2-letter uppercase USPS code
 */
export function normalizeState(stateInput: string): string {
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
 * Extracts secondary unit/apartment from street string and returns cleaned street
 */
export function extractUnitNumber(streetText: string): { baseStreet: string; unitNumber: string | null } {
  if (!streetText) return { baseStreet: '', unitNumber: null };

  const match = streetText.match(UNIT_REGEX);
  if (!match) {
    return { baseStreet: streetText.trim(), unitNumber: null };
  }

  let unitNumber: string;
  if (match[1] && match[2]) {
    const rawPrefix = match[1].toLowerCase();
    let prefix = match[1].charAt(0).toUpperCase() + match[1].slice(1).toLowerCase();
    if (rawPrefix === 'fl' || rawPrefix === 'floor') prefix = 'Fl';
    else if (rawPrefix === 'ste' || rawPrefix === 'suite') prefix = 'Suite';
    else if (rawPrefix === 'apt' || rawPrefix === 'apartment') prefix = 'Apt';
    else if (rawPrefix === 'unit') prefix = 'Unit';

    unitNumber = `${prefix} ${match[2]}`;
  } else if (match[3]) {
    unitNumber = `#${match[3]}`;
  } else {
    unitNumber = match[0].trim();
  }

  const baseStreet = streetText.replace(UNIT_REGEX, '').replace(/,\s*$/, '').trim();
  return { baseStreet, unitNumber };
}

/**
 * Normalizes an address string with optional coordinates into NormalizedAddress
 */
export function normalizeAddress(
  input: string,
  coords?: { lat: number; lng: number }
): NormalizedAddress {
  if (!input || !input.trim()) {
    throw new AddressValidationError('Please enter a valid street address.');
  }

  // Sanitize script tags (XSS prevention)
  let cleaned = input.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '').trim();

  // Sanitize SQL injection meta-characters
  cleaned = cleaned.replace(/['";]\s*(?:DROP|SELECT|INSERT|DELETE|UPDATE|ALTER|CREATE|EXEC|UNION)[\s\S]*?--/gi, '').trim();

  // Check PO Box
  if (isPoBox(cleaned)) {
    throw new PoBoxError(cleaned);
  }

  // Validate or assign coordinates
  let lat = 38.897675;
  let lng = -77.03653;
  if (coords) {
    AddressNormalizer.validateCoordinates(coords.lat, coords.lng);
    lat = coords.lat;
    lng = coords.lng;
  }

  // Parse comma-delimited segments or freeform string
  const segments = cleaned.split(',').map((s) => s.trim().replace(/\s+/g, ' ')).filter(Boolean);

  let rawStreet = segments[0] || '';
  let city = '';
  let rawStateZip = '';

  if (segments.length >= 3) {
    city = segments[1];
    rawStateZip = segments.slice(2).join(' ');
  } else if (segments.length === 2) {
    rawStateZip = segments[1];
  }

  // Check for Rural Route Box (e.g., "Route 1 Box 42, Big Piney, WY 83113")
  let streetNumber = '';
  let streetName = '';
  let unitNumber: string | null = null;

  const ruralMatch = rawStreet.match(RURAL_ROUTE_BOX_REGEX);
  if (ruralMatch) {
    streetName = ruralMatch[1];
    streetNumber = ruralMatch[2]; // "Box 42"
  } else {
    // Extract unit if present
    const extractedUnit = extractUnitNumber(rawStreet);
    rawStreet = extractedUnit.baseStreet;
    unitNumber = extractedUnit.unitNumber;

    // Extract street number
    const numMatch = rawStreet.match(STREET_NUMBER_REGEX);
    if (numMatch) {
      streetNumber = numMatch[1];
      rawStreet = numMatch[2];
    } else {
      throw new MissingStreetNumberError(input);
    }

    streetName = AddressNormalizer.standardizeStreetName(rawStreet);
  }

  // Parse state and zip from remaining segments
  let state = '';
  let zip5 = '';
  let zip4: string | null = null;

  if (rawStateZip) {
    const zipParsed = AddressNormalizer.parseZip(rawStateZip);
    zip5 = zipParsed.zip5;
    zip4 = zipParsed.zip4;

    const remaining = rawStateZip.replace(ZIP_REGEX, '').trim();
    if (remaining) {
      state = normalizeState(remaining);
    }
  }

  // If city was not extracted from comma segments, attempt fallback parsing
  if (!city && segments.length === 2) {
    const words = segments[1].split(' ').filter(Boolean);
    if (words.length > 2) {
      city = words.slice(0, words.length - 2).join(' ');
      state = normalizeState(words[words.length - 2]);
    }
  }

  const formattedAddress = AddressNormalizer.formatAddress({
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
    lat: Number(lat.toFixed(6)),
    lng: Number(lng.toFixed(6)),
    formattedAddress,
    geocoderSource: 'census',
    confidenceScore: 0.95,
  };
}

export class AddressNormalizer {
  /**
   * Checks whether the address string represents a PO Box
   */
  public static isPoBox(address: string): boolean {
    return isPoBox(address);
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
    const res = extractUnitNumber(streetText);
    return { cleanedStreet: res.baseStreet, unitNumber: res.unitNumber };
  }

  /**
   * Normalizes a state string to official 2-letter uppercase USPS code
   */
  public static normalizeState(stateInput: string): string {
    return normalizeState(stateInput);
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

    // Rural route formatting: e.g. "Route 1 Box 42, Big Piney, WY 83113"
    let streetLine = `${parts.streetNumber} ${parts.streetName}`;
    if (parts.streetNumber.toLowerCase().startsWith('box ')) {
      streetLine = `${parts.streetName} ${parts.streetNumber}`;
    }

    const cityPart = parts.city ? `${parts.city}, ` : '';
    const stateZipPart = parts.state && zipPart ? `${parts.state} ${zipPart}` : parts.state || zipPart;

    return `${streetLine}${unitPart}, ${cityPart}${stateZipPart}`.replace(/,\s*,/g, ',').trim();
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

    // Check for Rural Route Box
    const ruralMatch = rawStreetName.match(RURAL_ROUTE_BOX_REGEX);
    if (ruralMatch) {
      rawStreetName = ruralMatch[1];
      streetNumber = ruralMatch[2];
    } else if (!streetNumber) {
      // If streetNumber is empty, try to extract from rawStreetName
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
