# Test Suite Readiness Report (TEST_READY.md)

**Project**: 5G Home Internet Availability & Arbitrage Engine  
**Track**: Track 1 — E2E Testing Track  
**Author**: `test_writer_track_1`  
**Date**: 2026-09-29  
**Status**: COMPLETE & READY FOR IMPLEMENTATION VERIFICATION  

---

## 1. Executive Summary

The automated testing harness and test suites for the 5G Arbitrage Engine have been established and are fully configured. The test suites cover all functional requirements (R1–R4) across unit, integration, boundary/adversarial, and end-to-end user journey tiers.

All test suites operate against deterministic mock fixtures and network route interception, guaranteeing 100% reproducible, hermetic execution without requiring live external carrier credentials or paid geocoding tokens.

---

## 2. Test File Inventory & Artifacts

| File Path | Category | Purpose | Test Count / Scope |
|---|---|---|---|
| `.agents/teamwork/TEST_INFRA.md` | Infrastructure | Authoritative test infrastructure spec | Frameworks, commands, mocking |
| `tests/fixtures/addresses.json` | Fixture | Standardized address scenarios | Urban, Suburban, Rural, Invalid |
| `tests/fixtures/fcc-records.json` | Fixture | FCC BDC fixed wireless records | Tech codes 71, 72, 70, 61, 10, 40 |
| `tests/unit/geocoding/normalizer.test.ts` | Unit / Security | Postal parsing, PO Box rejection, sanitization | 22 tests |
| `tests/unit/engine/brand-mapper.test.ts` | Unit / Logic | Dual/triple brand disambiguation & Starlink | 8 tests |
| `tests/unit/db/cache.test.ts` | Unit / DB | Multi-tier L1 LRU & L2 SQLite coordinate cache | 10 tests |
| `tests/unit/engine/timeout-fallback.test.ts` | Unit / Resilience | 1.5s timeout abort & FCC BDC fallback | 5 tests |
| `tests/e2e/journeys.spec.ts` | E2E | Playwright browser user journeys | 4 major user journeys |
| `TEST_READY.md` | Documentation | Master test readiness report | Comprehensive overview |

---

## 3. Tier Coverage Breakdown

### 3.1 Tier 1: Feature Coverage
- **Address Normalization**: Parses single-line addresses into `streetNumber`, `streetName`, `city`, `state`, `zip5`, and `lat`/`lng`.
- **Directional & Unit Parsing**: Standardizes street suffixes and extracts secondary apartment/suite units (`Apt 4B`, `Suite 1501`, `#304`, `Fl 2`).
- **T-Mobile Dual-Brand Splitting**: Resolves single T-Mobile coverage into `t-mobile-5g-home` (postpaid, $50/mo, Wi-Fi 6 gateway included) and `metro-by-t-mobile` (prepaid, $40/mo, gateway purchase, no credit check).
- **Verizon Triple-Brand Splitting**: Resolves single Verizon coverage into `verizon-5g-home` (postpaid), `straight-talk-home` (prepaid $45 flat), and `total-wireless-home` (prepaid $45-$60).
- **AT&T Brand Mapping**: Maps AT&T coverage to `att-internet-air` ($60/mo, All-Fi Hub).
- **Universal Satellite Baseline**: Returns Starlink Residential ($120/mo, $599 kit) when terrestrial FWA is absent.
- **Drizzle & Cache Persistence**: Stores entries in SQLite L2 cache with spatial keys and retrieves via L1 memory LRU cache.

### 3.2 Tier 2: Boundary & Corner Cases
- **PO Box Rejection**: Rejects "PO Box 1234", "P.O. Box 999", and "Post Office Box 42" with explicit warnings, while avoiding false positives on "Boxwood Ln".
- **Irregular Addresses**: Successfully parses fractional house numbers ("123 1/2 Maple St") and Wisconsin grid coordinates ("N12W34560 Lake Dr").
- **Adversarial Input Sanitization**: Defends against SQL injection syntax (`'; DROP TABLE brands;--`) and XSS script tags without application crashes.
- **Cache Eviction**: Tests LRU cache capacity limits (oldest entry evicted on overflow) and TTL expiry.
- **Timeout Boundaries**: Tests that carrier calls exceeding 1500ms trigger AbortController signal and immediately fall back to FCC BDC data.

### 3.3 Tier 3: Pairwise Combinations
- **Concurrent Dispatch Under Partial Failure**: Tests parallel dispatch where one carrier hangs (>1500ms), one fails (HTTP 500), and one succeeds, verifying that the aggregated response succeeds in <2.0s without unhandled exceptions.
- **Two-Tier Cache Cascade**: Tests L1 miss $\rightarrow$ L2 hit $\rightarrow$ L1 backfill cascade.

### 3.4 Tier 4: Real-World User Journeys (Playwright E2E)
- **Journey 1: Urban Multi-Provider (`350 5th Ave, New York, NY 10118`)**:
  - Verifies 6 distinct brand cards rendered.
  - Verifies interactive filtering by network family (T-Mobile filter shows only T-Mobile and Metro).
  - Verifies outbound signup links have `target="_blank"` and `rel="noopener noreferrer"`.
- **Journey 2: Suburban Single-Carrier (`456 Oak Rd, Naperville, IL 60540`)**:
  - Verifies single-carrier footprint displays both sister brands (T-Mobile & Metro) while competing carriers are absent.
- **Journey 3: Rural Satellite-Only (`Route 1 Box 42, Big Piney, WY 83113`)**:
  - Verifies fallback notification banner is displayed.
  - Verifies Starlink card with satellite badge and explicit $599 hardware kit disclosure.
- **Journey 4: Invalid Address & Edge Cases**:
  - Verifies blank input validation ("Please enter a valid street address").
  - Verifies PO Box rejection message.
  - Verifies nonexistent address 404 friendly error card.

---

## 4. How to Run the Tests

Once dependencies are installed by Milestone 1 (`npm install`):

```bash
# 1. Run all unit and integration tests (Vitest)
npm run test
# or
npx vitest run

# 2. Run tests with code coverage
npx vitest run --coverage

# 3. Run individual unit test files
npx vitest run tests/unit/geocoding/normalizer.test.ts
npx vitest run tests/unit/engine/brand-mapper.test.ts
npx vitest run tests/unit/db/cache.test.ts
npx vitest run tests/unit/engine/timeout-fallback.test.ts

# 4. Run Playwright End-to-End tests
npx playwright test

# 5. Run Playwright in interactive UI mode
npx playwright test --ui
```

---

## 5. Implementation Track Handoff

The E2E Testing Track is complete. The test suites define unambiguous behavioral contracts for:
1. **Milestone 1**: Address normalizer, PO Box validator, and geocoder service (`src/lib/geocoding/`).
2. **Milestone 2**: Drizzle ORM cache service, LRU in-memory cache, and brand catalog (`src/lib/db/`).
3. **Milestone 3**: Brand mapper, FCC BDC data loader, and timeout fallback engine (`src/lib/engine/`).
4. **Milestone 4**: Interactive search UI, comparison cards, and `/api/availability` endpoint (`src/app/`, `src/components/`).
