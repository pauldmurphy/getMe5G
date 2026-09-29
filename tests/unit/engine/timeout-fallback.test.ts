import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  executeProviderCheckWithTimeout,
  runConcurrentProviderChecks,
} from '@/lib/engine/availability-engine';
import { IProviderChecker, ProviderCheckInput, ProviderCheckResult } from '@/lib/engine/types';
import fccRecordsFixture from '../../fixtures/fcc-records.json';

describe('Timeout Enforcement & FCC BDC Resilient Fallback Tests', () => {
  const mockAddress = {
    streetNumber: '350',
    streetName: '5th Ave',
    unitNumber: null,
    city: 'New York',
    state: 'NY',
    zip5: '10118',
    lat: 40.7484,
    lng: -73.9857,
    formattedAddress: '350 5th Ave, New York, NY 10118',
  };

  const mockInput: ProviderCheckInput = {
    address: mockAddress,
    timeoutMs: 1500,
    fccCoverageHint: {
      hasTmobile: true,
      hasVerizon: true,
      hasAtt: true,
      hasSatellite: true,
    },
  };

  describe('1.5s Hard Timeout Enforcement (Tier 1 & 2)', () => {
    it('should abort carrier check and fallback to FCC BDC when carrier takes > 1500ms', async () => {
      // Create a slow checker that simulates a hanging network socket
      const slowChecker: IProviderChecker = {
        checkerName: 'MockHangingCarrierChecker',
        supportedBrands: ['t-mobile-5g-home'],
        check: vi.fn(async (_input: ProviderCheckInput, signal?: AbortSignal) => {
          return new Promise<ProviderCheckResult[]>((resolve, reject) => {
            const timer = setTimeout(() => {
              resolve([
                {
                  brandId: 't-mobile-5g-home',
                  brandName: 'T-Mobile 5G Home Internet',
                  networkOperator: 'T-Mobile',
                  technologyType: '5G_FWA',
                  status: 'available',
                  confidence: 'verified_live',
                  source: 'live_preflight',
                  speeds: {
                    downloadMinMbps: 72,
                    downloadMaxMbps: 245,
                    uploadMinMbps: 15,
                    uploadMaxMbps: 31,
                    displaySpeed: '72 - 245 Mbps',
                  },
                  pricing: {
                    startingMonthlyPrice: 50,
                    equipmentUpfrontCost: 0,
                    equipmentMonthlyFee: 0,
                    contractTerms: 'No contract',
                    creditCheckRequired: true,
                  },
                  keyFeatures: [],
                  arbitrageNotes: '',
                  officialSignupUrl: 'https://www.t-mobile.com',
                },
              ]);
            }, 3000); // Exceeds 1.5s limit

            if (signal) {
              signal.addEventListener('abort', () => {
                clearTimeout(timer);
                reject(new Error('Operation aborted due to 1.5s timeout'));
              });
            }
          });
        }),
      };

      const startTime = Date.now();
      const results = await executeProviderCheckWithTimeout(
        slowChecker,
        mockInput,
        fccRecordsFixture
      );
      const elapsed = Date.now() - startTime;

      // Ensure execution completed around 1.5s (with small buffer) and did not wait 3s
      expect(elapsed).toBeLessThan(2000);
      expect(results.length).toBeGreaterThan(0);

      // Verify result indicates FCC fallback
      const fallbackResult = results[0];
      expect(fallbackResult.status).toBe('fallback_available');
      expect(fallbackResult.confidence).toBe('fcc_bdc_fallback');
      expect(fallbackResult.source).toBe('fcc_bdc');
    });

    it('should successfully return live carrier data when response arrives under 1500ms', async () => {
      const fastChecker: IProviderChecker = {
        checkerName: 'MockFastChecker',
        supportedBrands: ['verizon-5g-home'],
        check: vi.fn(async () => {
          return [
            {
              brandId: 'verizon-5g-home',
              brandName: 'Verizon 5G Home',
              networkOperator: 'Verizon',
              technologyType: '5G_FWA',
              status: 'available',
              confidence: 'verified_live',
              source: 'live_preflight',
              speeds: {
                downloadMinMbps: 85,
                downloadMaxMbps: 300,
                uploadMinMbps: 10,
                uploadMaxMbps: 20,
                displaySpeed: '85 - 300 Mbps',
              },
              pricing: {
                startingMonthlyPrice: 50,
                equipmentUpfrontCost: 0,
                equipmentMonthlyFee: 0,
                contractTerms: 'No contract',
                creditCheckRequired: true,
              },
              keyFeatures: [],
              arbitrageNotes: '',
              officialSignupUrl: 'https://www.verizon.com',
            },
          ];
        }),
      };

      const results = await executeProviderCheckWithTimeout(
        fastChecker,
        mockInput,
        fccRecordsFixture
      );
      expect(results.length).toBe(1);
      expect(results[0].status).toBe('available');
      expect(results[0].confidence).toBe('verified_live');
      expect(results[0].source).toBe('live_preflight');
    });
  });

  describe('Error & Rate-Limiting Resilience (Tier 2 & 5)', () => {
    it('should intercept HTTP 500 error from carrier endpoint and seamlessly fallback to FCC BDC', async () => {
      const failingChecker: IProviderChecker = {
        checkerName: 'Mock500FailingChecker',
        supportedBrands: ['att-internet-air'],
        check: vi.fn(async () => {
          throw new Error('500 Internal Server Error: Carrier gateway unavailable');
        }),
      };

      // Must not throw unhandled exception
      const results = await executeProviderCheckWithTimeout(
        failingChecker,
        mockInput,
        fccRecordsFixture
      );

      expect(results.length).toBeGreaterThan(0);
      const attResult = results.find((r) => r.brandId === 'att-internet-air');
      expect(attResult).toBeDefined();
      expect(attResult?.confidence).toBe('fcc_bdc_fallback');
      expect(attResult?.source).toBe('fcc_bdc');
    });

    it('should intercept HTTP 429 Too Many Requests throttle and fallback to FCC BDC', async () => {
      const throttledChecker: IProviderChecker = {
        checkerName: 'Mock429ThrottledChecker',
        supportedBrands: ['t-mobile-5g-home'],
        check: vi.fn(async () => {
          const err: any = new Error('429 Too Many Requests');
          err.statusCode = 429;
          throw err;
        }),
      };

      const results = await executeProviderCheckWithTimeout(
        throttledChecker,
        mockInput,
        fccRecordsFixture
      );

      expect(results.length).toBeGreaterThan(0);
      expect(results[0].confidence).toBe('fcc_bdc_fallback');
    });
  });

  describe('Concurrent Parallel Execution (Tier 3)', () => {
    it('should dispatch all checkers concurrently and complete in under 2.0s even when one hangs', async () => {
      const fastChecker1: IProviderChecker = {
        checkerName: 'Fast1',
        supportedBrands: ['t-mobile-5g-home'],
        check: vi.fn(async () => [
          {
            brandId: 't-mobile-5g-home',
            brandName: 'T-Mobile 5G Home Internet',
            networkOperator: 'T-Mobile',
            technologyType: '5G_FWA',
            status: 'available',
            confidence: 'verified_live',
            source: 'live_preflight',
            speeds: {
              downloadMinMbps: 72,
              downloadMaxMbps: 245,
              uploadMinMbps: 15,
              uploadMaxMbps: 31,
              displaySpeed: '72 - 245 Mbps',
            },
            pricing: {
              startingMonthlyPrice: 50,
              equipmentUpfrontCost: 0,
              equipmentMonthlyFee: 0,
              contractTerms: 'No contract',
              creditCheckRequired: true,
            },
            keyFeatures: [],
            arbitrageNotes: '',
            officialSignupUrl: 'https://www.t-mobile.com',
          },
        ]),
      };

      const hangingChecker: IProviderChecker = {
        checkerName: 'Hanging',
        supportedBrands: ['verizon-5g-home'],
        check: vi.fn(
          (_input: ProviderCheckInput, signal?: AbortSignal) =>
            new Promise<ProviderCheckResult[]>((_, reject) => {
              if (signal) {
                signal.addEventListener('abort', () => reject(new Error('Aborted')));
              }
            })
        ),
      };

      const fastChecker2: IProviderChecker = {
        checkerName: 'Fast2',
        supportedBrands: ['att-internet-air'],
        check: vi.fn(async () => [
          {
            brandId: 'att-internet-air',
            brandName: 'AT&T Internet Air',
            networkOperator: 'AT&T',
            technologyType: '5G_FWA',
            status: 'available',
            confidence: 'verified_live',
            source: 'live_preflight',
            speeds: {
              downloadMinMbps: 75,
              downloadMaxMbps: 225,
              uploadMinMbps: 10,
              uploadMaxMbps: 25,
              displaySpeed: '75 - 225 Mbps',
            },
            pricing: {
              startingMonthlyPrice: 60,
              equipmentUpfrontCost: 0,
              equipmentMonthlyFee: 0,
              contractTerms: 'No contract',
              creditCheckRequired: true,
            },
            keyFeatures: [],
            arbitrageNotes: '',
            officialSignupUrl: 'https://www.att.com',
          },
        ]),
      };

      const startTime = Date.now();
      const combinedResults = await runConcurrentProviderChecks(
        [fastChecker1, hangingChecker, fastChecker2],
        mockInput,
        fccRecordsFixture
      );
      const totalElapsed = Date.now() - startTime;

      expect(totalElapsed).toBeLessThan(2000);
      expect(combinedResults.providers.length).toBeGreaterThan(0);

      const brandIds = combinedResults.providers.map((p) => p.brandId);
      expect(brandIds).toContain('t-mobile-5g-home');
      expect(brandIds).toContain('att-internet-air');
      // Verizon should be populated from FCC fallback
      expect(brandIds).toContain('verizon-5g-home');
    });
  });
});
