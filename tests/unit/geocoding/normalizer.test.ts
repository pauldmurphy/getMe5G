import { describe, it, expect } from 'vitest';
import {
  normalizeAddress,
  isPoBox,
  normalizeState,
  extractUnitNumber,
} from '@/lib/geocoding/normalizer';

describe('Address Normalizer Unit Tests (Tier 1 & Tier 2)', () => {
  describe('Standard Address Parsing & Formatting (Tier 1)', () => {
    it('should parse standard single-line address with street, city, state, zip', () => {
      const input = '350 5th Ave, New York, NY 10118';
      const result = normalizeAddress(input, { lat: 40.7484, lng: -73.9857 });

      expect(result.streetNumber).toBe('350');
      expect(result.streetName).toContain('5th Ave');
      expect(result.city).toBe('New York');
      expect(result.state).toBe('NY');
      expect(result.zip5).toBe('10118');
      expect(result.lat).toBeCloseTo(40.7484, 4);
      expect(result.lng).toBeCloseTo(-73.9857, 4);
    });

    it('should parse directional street names and expand or retain standard USPS format', () => {
      const input = '1600 Pennsylvania Avenue NW, Washington, DC 20500';
      const result = normalizeAddress(input);

      expect(result.streetNumber).toBe('1600');
      expect(result.streetName).toMatch(/Pennsylvania (Avenue|Ave) NW/i);
      expect(result.city).toBe('Washington');
      expect(result.state).toBe('DC');
      expect(result.zip5).toBe('20500');
    });

    it('should parse 9-digit ZIP+4 code into base zip5 and zip4', () => {
      const input = '1600 Pennsylvania Ave NW, Washington, DC 20500-0003';
      const result = normalizeAddress(input);

      expect(result.zip5).toBe('20500');
      expect(result.zip4).toBe('0003');
    });

    it('should standardize full state name to 2-letter postal code', () => {
      expect(normalizeState('California')).toBe('CA');
      expect(normalizeState('california')).toBe('CA');
      expect(normalizeState('New York')).toBe('NY');
      expect(normalizeState('Texas')).toBe('TX');
      expect(normalizeState('District of Columbia')).toBe('DC');
      expect(normalizeState('Puerto Rico')).toBe('PR');
    });

    it('should preserve already valid 2-letter uppercase state codes', () => {
      expect(normalizeState('IL')).toBe('IL');
      expect(normalizeState('wy')).toBe('WY');
      expect(normalizeState('FL')).toBe('FL');
    });
  });

  describe('Secondary Unit & Apartment Extraction', () => {
    it('should extract "Apt" unit indicator without corrupting street name', () => {
      const extracted = extractUnitNumber('742 Evergreen Terrace Apt 4B');
      expect(extracted.unitNumber).toMatch(/4B/i);
      expect(extracted.baseStreet).toBe('742 Evergreen Terrace');
    });

    it('should extract "Suite" unit indicator', () => {
      const extracted = extractUnitNumber('450 7th Ave Suite 1501');
      expect(extracted.unitNumber).toMatch(/1501/i);
      expect(extracted.baseStreet).toBe('450 7th Ave');
    });

    it('should extract "#" unit symbol indicator', () => {
      const extracted = extractUnitNumber('100 Pine St #304');
      expect(extracted.unitNumber).toMatch(/304/i);
      expect(extracted.baseStreet).toBe('100 Pine St');
    });

    it('should extract "Unit" designation', () => {
      const extracted = extractUnitNumber('123 Main St Unit 2');
      expect(extracted.unitNumber).toMatch(/2/i);
      expect(extracted.baseStreet).toBe('123 Main St');
    });

    it('should extract "Floor" or "Fl" indicator', () => {
      const extracted = extractUnitNumber('500 W Madison St Fl 2');
      expect(extracted.unitNumber).toMatch(/2/i);
      expect(extracted.baseStreet).toBe('500 W Madison St');
    });

    it('should return null unitNumber when no secondary indicator is present', () => {
      const extracted = extractUnitNumber('456 Oak Rd');
      expect(extracted.unitNumber).toBeNull();
      expect(extracted.baseStreet).toBe('456 Oak Rd');
    });
  });

  describe('PO Box Rejection & Validation (Tier 2 Boundary)', () => {
    it('should identify standard "PO Box" address', () => {
      expect(isPoBox('PO Box 1234, Dallas, TX 75201')).toBe(true);
      expect(isPoBox('po box 500')).toBe(true);
    });

    it('should identify punctuated "P.O. Box" address', () => {
      expect(isPoBox('P.O. Box 999, Atlanta, GA 30301')).toBe(true);
      expect(isPoBox('P. O. Box 101, Chicago, IL 60601')).toBe(true);
    });

    it('should identify spelled out "Post Office Box" address', () => {
      expect(isPoBox('Post Office Box 42, Denver, CO 80201')).toBe(true);
    });

    it('should reject PO Box in normalizeAddress by throwing or error flag', () => {
      expect(() => {
        normalizeAddress('PO Box 1234, Dallas, TX 75201');
      }).toThrow(/PO Box/i);
    });

    it('should NOT falsely identify streets containing "Boxwood" or "Post Office" as PO Box', () => {
      expect(isPoBox('123 Boxwood Lane, Houston, TX 77001')).toBe(false);
      expect(isPoBox('45 Post Office Rd, Annapolis, MD 21401')).toBe(false);
      expect(isPoBox('800 Boxberry Court, Raleigh, NC 27601')).toBe(false);
    });
  });

  describe('Edge Cases, Irregular Addresses & Adversarial Inputs (Tier 2 & 5)', () => {
    it('should handle fractional house numbers (e.g. 123 1/2)', () => {
      const input = '123 1/2 Maple St, Seattle, WA 98101';
      const result = normalizeAddress(input);
      expect(result.streetNumber).toBe('123 1/2');
      expect(result.streetName).toContain('Maple St');
    });

    it('should parse Wisconsin alphanumeric grid coordinate addresses', () => {
      const input = 'N12W34560 Lake Dr, Delafield, WI 53018';
      const result = normalizeAddress(input);
      expect(result.streetNumber).toBe('N12W34560');
      expect(result.streetName).toBe('Lake Dr');
      expect(result.state).toBe('WI');
    });

    it('should parse rural route box addresses', () => {
      const input = 'Route 1 Box 42, Big Piney, WY 83113';
      const result = normalizeAddress(input);
      expect(result.streetName).toContain('Route 1');
      expect(result.streetNumber).toBe('Box 42');
      expect(result.city).toBe('Big Piney');
      expect(result.state).toBe('WY');
      expect(result.zip5).toBe('83113');
    });

    it('should clean and handle excessive whitespace and messy punctuation', () => {
      const input = '   350    5th   Ave ,   New   York  ,   NY    10118   ';
      const result = normalizeAddress(input);
      expect(result.streetNumber).toBe('350');
      expect(result.city).toBe('New York');
      expect(result.state).toBe('NY');
      expect(result.zip5).toBe('10118');
    });

    it('should sanitize SQL injection meta-characters safely without crash', () => {
      const malicious = "123 Main St'; DROP TABLE brands;--, Boston, MA 02108";
      const result = normalizeAddress(malicious);
      expect(result.city).toBe('Boston');
      expect(result.state).toBe('MA');
      expect(result.zip5).toBe('02108');
    });

    it('should sanitize XSS script tags safely', () => {
      const xssInput = '<script>alert("xss")</script> 123 Main St, Miami, FL 33101';
      const result = normalizeAddress(xssInput);
      expect(result.streetNumber).toBe('123');
      expect(result.city).toBe('Miami');
      expect(result.state).toBe('FL');
    });

    it('should throw an error on empty string or whitespace-only input', () => {
      expect(() => normalizeAddress('')).toThrow();
      expect(() => normalizeAddress('    ')).toThrow();
    });

    it('should throw an error on missing street number when required', () => {
      expect(() => normalizeAddress('Broadway, New York, NY 10001')).toThrow(/street number/i);
    });

    it('should validate US geographic coordinate bounding box', () => {
      const validCoords = { lat: 40.7484, lng: -73.9857 };
      const normalized = normalizeAddress('350 5th Ave, New York, NY 10118', validCoords);
      expect(normalized.lat).toBeGreaterThan(18);
      expect(normalized.lat).toBeLessThan(72);
      expect(normalized.lng).toBeGreaterThan(-180);
      expect(normalized.lng).toBeLessThan(-65);
    });
  });
});
