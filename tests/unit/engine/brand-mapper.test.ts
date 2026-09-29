import { describe, it, expect } from 'vitest';
import {
  mapFccRecordsToBrands,
  filterValidWirelessRecords,
  getSatelliteFallbackBrand,
} from '@/lib/engine/brand-mapper';
import fccRecordsFixture from '../../fixtures/fcc-records.json';

describe('Brand Mapper & Multi-Brand Arbitrage Engine Unit Tests', () => {
  describe('Technology Code Filtering (Tier 1)', () => {
    it('should filter out wireline technologies (DSL 10, Cable 40) and keep wireless (71, 72, 70, 61)', () => {
      const filtered = filterValidWirelessRecords(fccRecordsFixture);
      const techCodes = filtered.map((r: any) => r.technology);

      expect(techCodes).toContain(71);
      expect(techCodes).toContain(72);
      expect(techCodes).toContain(70);
      expect(techCodes).toContain(61);
      expect(techCodes).not.toContain(10);
      expect(techCodes).not.toContain(40);
    });
  });

  describe('T-Mobile Network Dual-Brand Disambiguation (Tier 1 & 4)', () => {
    it('should split single T-Mobile coverage record into T-Mobile 5G Home and Metro by T-Mobile', () => {
      const tmobileRecord = fccRecordsFixture.filter(
        (r: any) => r.frn === '0001565480' && r.technology === 71
      );
      expect(tmobileRecord.length).toBeGreaterThan(0);

      const brands = mapFccRecordsToBrands(tmobileRecord);
      const brandIds = brands.map((b) => b.brandId);

      expect(brandIds).toContain('t-mobile-5g-home');
      expect(brandIds).toContain('metro-by-t-mobile');

      // T-Mobile Postpaid Checks
      const tmo = brands.find((b) => b.brandId === 't-mobile-5g-home')!;
      expect(tmo.networkOperator).toBe('T-Mobile');
      expect(tmo.technologyType).toBe('5G_FWA');
      expect(tmo.pricing.creditCheckRequired).toBe(true);
      expect(tmo.pricing.equipmentUpfrontCost).toBe(0);
      expect(tmo.pricing.autopayDiscountPrice).toBe(50);
      expect(tmo.officialSignupUrl).toMatch(/t-mobile\.com/);

      // Metro Prepaid Checks
      const metro = brands.find((b) => b.brandId === 'metro-by-t-mobile')!;
      expect(metro.networkOperator).toBe('T-Mobile');
      expect(metro.technologyType).toBe('5G_FWA');
      expect(metro.pricing.creditCheckRequired).toBe(false);
      expect(metro.pricing.equipmentUpfrontCost).toBeGreaterThan(0);
      expect(metro.officialSignupUrl).toMatch(/metrobyt-mobile\.com/);
    });
  });

  describe('Verizon Network Triple-Brand Disambiguation (Tier 1 & 4)', () => {
    it('should split Verizon coverage record into Verizon 5G Home, Straight Talk, and Total Wireless', () => {
      const vzRecord = fccRecordsFixture.filter(
        (r: any) => r.frn === '0003290673' && r.technology === 71
      );
      expect(vzRecord.length).toBeGreaterThan(0);

      const brands = mapFccRecordsToBrands(vzRecord);
      const brandIds = brands.map((b) => b.brandId);

      expect(brandIds).toContain('verizon-5g-home');
      expect(brandIds).toContain('straight-talk-home');
      expect(brandIds).toContain('total-wireless-home');

      // Verizon Postpaid Checks
      const vz = brands.find((b) => b.brandId === 'verizon-5g-home')!;
      expect(vz.networkOperator).toBe('Verizon');
      expect(vz.pricing.creditCheckRequired).toBe(true);
      expect(vz.pricing.equipmentUpfrontCost).toBe(0);
      expect(vz.officialSignupUrl).toMatch(/verizon\.com/);

      // Straight Talk Prepaid Checks
      const st = brands.find((b) => b.brandId === 'straight-talk-home')!;
      expect(st.networkOperator).toBe('Verizon');
      expect(st.pricing.creditCheckRequired).toBe(false);
      expect(st.pricing.startingMonthlyPrice).toBe(45);
      expect(st.pricing.equipmentUpfrontCost).toBe(99);
      expect(st.speeds.downloadMaxMbps).toBeLessThanOrEqual(100);
      expect(st.officialSignupUrl).toMatch(/straighttalk\.com/);

      // Total Wireless Prepaid Checks
      const total = brands.find((b) => b.brandId === 'total-wireless-home')!;
      expect(total.networkOperator).toBe('Verizon');
      expect(total.pricing.creditCheckRequired).toBe(false);
      expect(total.pricing.equipmentUpfrontCost).toBe(99);
      expect(total.officialSignupUrl).toMatch(/totalwireless\.com/);
    });
  });

  describe('AT&T Internet Air Resolution', () => {
    it('should map AT&T fixed wireless records to AT&T Internet Air', () => {
      const attRecord = fccRecordsFixture.filter(
        (r: any) => r.frn === '0005050851' && r.technology === 71
      );
      expect(attRecord.length).toBeGreaterThan(0);

      const brands = mapFccRecordsToBrands(attRecord);
      const att = brands.find((b) => b.brandId === 'att-internet-air');

      expect(att).toBeDefined();
      expect(att?.networkOperator).toBe('AT&T');
      expect(att?.technologyType).toBe('5G_FWA');
      expect(att?.officialSignupUrl).toMatch(/att\.com/);
    });
  });

  describe('Universal Satellite & Rural Fallback (Tier 1 & 4)', () => {
    it('should return Starlink as universal satellite provider when no terrestrial FWA exists', () => {
      const brands = mapFccRecordsToBrands([]);
      expect(brands.length).toBe(1);

      const starlink = brands[0];
      expect(starlink.brandId).toMatch(/starlink/);
      expect(starlink.networkOperator).toBe('Starlink');
      expect(starlink.technologyType).toBe('SATELLITE_LEO');
      expect(starlink.pricing.startingMonthlyPrice).toBe(120);
      expect(starlink.pricing.equipmentUpfrontCost).toBe(599);
      expect(starlink.officialSignupUrl).toMatch(/starlink\.com/);
    });

    it('should provide helper getSatelliteFallbackBrand returning standard Starlink payload', () => {
      const fallback = getSatelliteFallbackBrand();
      expect(fallback.brandId).toMatch(/starlink/);
      expect(fallback.networkOperator).toBe('Starlink');
      expect(fallback.technologyType).toBe('SATELLITE_LEO');
      expect(fallback.pricing.startingMonthlyPrice).toBe(120);
      expect(fallback.pricing.equipmentUpfrontCost).toBe(599);
    });
  });

  describe('Multi-Carrier Coexistence & Sorting', () => {
    it('should return all distinct brands when multiple carriers cover an address', () => {
      const allWireless = filterValidWirelessRecords(fccRecordsFixture);
      const brands = mapFccRecordsToBrands(allWireless);

      // Urban multi-provider should contain T-Mobile, Metro, Verizon, Straight Talk, Total Wireless, AT&T Air, Starlink
      const brandIds = brands.map((b) => b.brandId);
      expect(brandIds).toContain('t-mobile-5g-home');
      expect(brandIds).toContain('metro-by-t-mobile');
      expect(brandIds).toContain('verizon-5g-home');
      expect(brandIds).toContain('straight-talk-home');
      expect(brandIds).toContain('total-wireless-home');
      expect(brandIds).toContain('att-internet-air');
    });

    it('should assign unique non-colliding brand IDs to sister brands on the same network', () => {
      const allWireless = filterValidWirelessRecords(fccRecordsFixture);
      const brands = mapFccRecordsToBrands(allWireless);
      const idSet = new Set(brands.map((b) => b.brandId));

      expect(idSet.size).toBe(brands.length);
    });
  });
});
