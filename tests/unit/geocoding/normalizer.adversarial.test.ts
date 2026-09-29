import { describe, it, expect } from 'vitest';
import {
  normalizeAddress,
  isPoBox,
  extractUnitNumber,
  AddressNormalizer,
} from '@/lib/geocoding/normalizer';

describe('Adversarial Address Normalizer Stress Tests (Challenger M1)', () => {
  describe('1. PO Box Variations & False Positive Resistance', () => {
    it('should detect standard and punctuated PO Box formats', () => {
      expect(isPoBox('P.O. Box 123')).toBe(true);
      expect(isPoBox('PO Box 999')).toBe(true);
      expect(isPoBox('Post Office Box 42')).toBe(true);
      expect(isPoBox('P.O.B 123')).toBe(true);
      expect(isPoBox('POB 456')).toBe(true);
      expect(isPoBox('PBOX 789')).toBe(true);
      expect(isPoBox('Post Office Drawer 500')).toBe(true);
    });

    it('should detect spaced P BOX format ("P BOX 10")', () => {
      // Challenged: Current PO_BOX_REGEX misses spaced "P BOX"
      expect(isPoBox('P BOX 10')).toBe(true);
    });

    it('should reject PO Box addresses in normalizeAddress with PoBoxError', () => {
      expect(() => normalizeAddress('P BOX 10, Dallas, TX 75201')).toThrow(/PO Box/i);
    });

    it('should NOT falsely identify streets containing "Box" words as PO Box', () => {
      expect(isPoBox('123 Boxwood Ln, Houston, TX 77001')).toBe(false);
      expect(isPoBox('45 Post Office Rd, Annapolis, MD 21401')).toBe(false);
      expect(isPoBox('800 Boxberry Court, Raleigh, NC 27601')).toBe(false);
      expect(isPoBox('100 Boxford St, Boston, MA 02108')).toBe(false);
    });
  });

  describe('2. Weird & Unusual Addresses', () => {
    it('should correctly parse fractional house numbers (123 1/2)', () => {
      const result = normalizeAddress('123 1/2 Maple St, Seattle, WA 98101');
      expect(result.streetNumber).toBe('123 1/2');
      expect(result.streetName).toContain('Maple St');
    });

    it('should correctly parse Wisconsin grid addresses', () => {
      const result = normalizeAddress('N12W34560 Lake Dr, Delafield, WI 53018');
      expect(result.streetNumber).toBe('N12W34560');
      expect(result.streetName).toBe('Lake Dr');
      expect(result.state).toBe('WI');
    });

    it('should correctly parse highway routes with house numbers', () => {
      const result = normalizeAddress('100 Route 66, Flagstaff, AZ 86001');
      expect(result.streetNumber).toBe('100');
      expect(result.streetName).toBe('Route 66');
    });

    it('should reject highway routes lacking building numbers', () => {
      expect(() => normalizeAddress('Route 66, Flagstaff, AZ 86001')).toThrow(/street number/i);
    });

    it('should extract unit numbers when designated with "#" (e.g. #5, #304)', () => {
      // Challenged: \b before # prevents matching when preceded by space
      const res5 = extractUnitNumber('100 Pine St #5');
      expect(res5.unitNumber).toBe('#5');
      expect(res5.baseStreet).toBe('100 Pine St');

      const res304 = extractUnitNumber('100 Pine St #304');
      expect(res304.unitNumber).toBe('#304');
      expect(res304.baseStreet).toBe('100 Pine St');
    });

    it('should correctly parse comma-separated unit numbers without corrupting city/state', () => {
      // Challenged: Multi-comma split sets city to the unit designation (e.g. city='Apt 4B')
      const res = normalizeAddress('123 Main St, Apt 4B, New York, NY 10001');
      expect(res.unitNumber).toBe('Apt 4B');
      expect(res.city).toBe('New York');
      expect(res.state).toBe('NY');
      expect(res.zip5).toBe('10001');
    });

    it('should correctly parse comma-separated suite designators', () => {
      const res = normalizeAddress('100 Pine St, Ste 100, San Francisco, CA 94111');
      expect(res.unitNumber).toMatch(/Suite 100|Ste 100/i);
      expect(res.city).toBe('San Francisco');
      expect(res.state).toBe('CA');
    });
  });

  describe('3. Security & Injection Payloads', () => {
    it('should sanitize SQL injection payloads with and without comment markers', () => {
      const withComment = normalizeAddress("123 Main St'; DROP TABLE brands;--, Boston, MA 02108");
      expect(withComment.streetName).not.toContain('DROP TABLE');

      const withoutComment = normalizeAddress("123 Main St'; DROP TABLE brands;, Boston, MA 02108");
      expect(withoutComment.streetName).not.toContain('DROP TABLE');
    });

    it('should sanitize HTML tags and image onerror XSS vectors', () => {
      // Challenged: Only <script> tags were stripped, leaving <img>/<svg> vectors intact
      const xssImg = normalizeAddress('123 Main St <img src=x onerror=alert(1)>, Miami, FL 33101');
      expect(xssImg.formattedAddress).not.toContain('<img');
      expect(xssImg.formattedAddress).not.toContain('onerror');
    });

    it('should handle large input strings without exponential backtracking', () => {
      const largeInput = '123 Main St ' + 'A'.repeat(50000) + ', Miami, FL 33101';
      const start = Date.now();
      normalizeAddress(largeInput);
      const elapsed = Date.now() - start;
      expect(elapsed).toBeLessThan(1000);
    });
  });

  describe('4. Missing Components & Incomplete Addresses', () => {
    it('should throw MissingStreetNumberError when street number is absent', () => {
      expect(() => normalizeAddress('Broadway, New York, NY 10001')).toThrow(/street number/i);
    });

    it('should handle addresses with missing ZIP code without corrupting state into zip5', () => {
      // Challenged: parseZip("NY") improperly assigns zip5="NY"
      const res = normalizeAddress('123 Main St, New York, NY');
      expect(res.state).toBe('NY');
      expect(res.zip5).toBe('');
      expect(res.formattedAddress).not.toContain('NY NY');
    });

    it('should throw AddressValidationError on empty or whitespace strings', () => {
      expect(() => normalizeAddress('')).toThrow();
      expect(() => normalizeAddress('   \t\n  ')).toThrow();
    });
  });
});
