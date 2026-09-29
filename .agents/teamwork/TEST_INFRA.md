# Test Infrastructure Specification (TEST_INFRA.md)

**Project**: 5G Home Internet Availability & Arbitrage Engine  
**Track**: Track 1 — E2E Testing Track  
**Author**: `test_writer_track_1`  
**Status**: Authoritative Testing Infrastructure Baseline  
**Date**: 2026-09-29  

---

## 1. Overview & Testing Strategy

The **5G Arbitrage Engine** provides address geocoding, multi-brand fixed wireless & satellite broadband resolution, catalog queries, multi-tier caching (L1 in-memory LRU + L2 SQLite via Drizzle ORM), and an interactive comparison report UI.

Testing follows a strict **5-Tier Quality Hierarchy**:
- **Tier 1: Feature Coverage** (Nominal happy path for every feature)
- **Tier 2: Boundary & Corner Cases** (Extreme, boundary, invalid inputs, and security edge cases)
- **Tier 3: Pairwise Combinations** (Cross-system interactions between geocoders, coverage states, timeouts, and caches)
- **Tier 4: Real-World Scenarios** (End-to-end consumer journeys across realistic address personas)
- **Tier 5: Adversarial & Stress Hardening** (Timeout enforcement, fault injection, rate limit handling)

---

## 2. Directory Layout

The automated testing harness is organized under `tests/` and structured as follows:

```
tests/
├── fixtures/
│   ├── addresses.json                 # Standardized address scenarios & geocode payloads
│   └── fcc-records.json               # FCC BDC records (Tech 71, 72, 70, 61, 10, 40)
├── unit/
│   ├── geocoding/
│   │   └── normalizer.test.ts         # 20+ address normalization & PO Box rejection tests
│   ├── engine/
│   │   ├── brand-mapper.test.ts       # Multi-brand resolution (T-Mobile/Metro, Verizon/StraightTalk/Total, Starlink)
│   │   └── timeout-fallback.test.ts   # 1.5s timeout abort & FCC BDC fallback resilience
│   └── db/
│       └── cache.test.ts              # SQLite Drizzle ORM coordinate cache & LRU memory cache
└── e2e/
    └── journeys.spec.ts               # Playwright E2E specs for Urban, Suburban, Rural, & Invalid journeys
```

---

## 3. Test Harness Frameworks

### 3.1 Unit & Integration Testing: Vitest
- **Runner**: Vitest (`vitest run`)
- **Environment**: `happy-dom` for DOM-compatible helper tests and Node.js for backend unit/integration tests
- **Database Isolation**: In-memory SQLite (`:memory:`) via `better-sqlite3` / Drizzle ORM
- **HTTP Mocking**: Native `vi.fn()` / `vi.spyOn()` and mock route abstractions for deterministic pre-flight carrier checks

### 3.2 End-to-End (E2E) Testing: Playwright
- **Runner**: Playwright (`npx playwright test`)
- **Network Interception**: `page.route()` stubs `/api/geocode*` and `/api/availability*` to deliver hermetic, instant, offline-capable test runs
- **Browsers**: Chromium, Firefox, WebKit, and Mobile Chrome

---

## 4. Test Execution Commands

| Target | Command | Purpose |
|---|---|---|
| **All Unit & Integration Tests** | `npm run test` or `npx vitest run` | Execute complete Vitest suite |
| **Normalizer Unit Tests** | `npx vitest run tests/unit/geocoding/normalizer.test.ts` | Test postal component normalization |
| **Brand Mapper Tests** | `npx vitest run tests/unit/engine/brand-mapper.test.ts` | Test multi-brand retail disambiguation |
| **Cache & DB Tests** | `npx vitest run tests/unit/db/cache.test.ts` | Test Drizzle ORM & LRU cache operations |
| **Timeout & Fallback Tests** | `npx vitest run tests/unit/engine/timeout-fallback.test.ts` | Test 1.5s timeout and FCC BDC fallback |
| **Coverage Report** | `npx vitest run --coverage` | Generate V8 code coverage report |
| **Playwright E2E Tests** | `npm run test:e2e` or `npx playwright test` | Run headless browser E2E journeys |
| **Playwright E2E UI** | `npx playwright test --ui` | Interactive Playwright test runner |

---

## 5. Mock Fixture Strategy

### 5.1 `tests/fixtures/addresses.json`
Provides deterministic address fixtures representing distinct geographical and coverage profiles:
1. **Urban Multi-Provider** (`"350 5th Ave, New York, NY 10118"`):
   - Dense urban rooftop in Manhattan
   - Active coverage: T-Mobile, Verizon, and AT&T networks
   - Resolved brands: T-Mobile 5G Home, Metro by T-Mobile, Verizon 5G Home, Straight Talk, Total Wireless, AT&T Internet Air
2. **Suburban Single-Carrier** (`"456 Oak Rd, Naperville, IL 60540"`):
   - Suburban residential location
   - Active coverage: T-Mobile network only
   - Resolved brands: T-Mobile 5G Home, Metro by T-Mobile
3. **Rural Satellite-Only** (`"Route 1 Box 42, Big Piney, WY 83113"`):
   - Rural location with zero terrestrial fixed wireless coverage
   - Resolved brands: Starlink Residential (with fallback alert banner)
4. **Invalid Address Scenarios**:
   - Nonexistent address (`"99999 Nonexistent Blvd, Nowhere, ZZ 00000"`)
   - Empty/whitespace string (`"   "`)
   - PO Box address (`"PO Box 1234, Dallas, TX 75201"`)

### 5.2 `tests/fixtures/fcc-records.json`
Contains mock FCC Broadband Data Collection (BDC) fixed broadband records:
- **Technology 71 (Licensed Fixed Wireless)**:
  - T-Mobile USA, Inc. (`frn: "0001565480"`, `provider_id: 130077`)
  - Cellco Partnership / Verizon (`frn: "0003290673"`, `provider_id: 130403`)
  - AT&T Services, Inc. (`frn: "0005050851"`, `provider_id: 130079`)
- **Technology 72 (Licensed-by-Rule CBRS Fixed Wireless)**:
  - Shared spectrum CBRS fixed wireless provider
- **Technology 70 (Unlicensed Fixed Wireless)**:
  - Unlicensed spectrum WISP
- **Technology 61 (Non-Geostationary LEO Satellite)**:
  - SpaceX Services / Starlink (`frn: "0027768225"`, `provider_id: 131444`)
- **Technology 10 & 40 (Wireline Baseline)**:
  - Legacy copper DSL (10) and coaxial cable (40) used to verify that wireline technologies are discarded by the wireless engine.

---

## 6. Progressive Testability & Verification Protocol

- **Self-Contained Isolation**: Every test creates its own fixtures or imports deterministic fixtures from `tests/fixtures/`.
- **No Shared State**: In-memory caches are cleared via `beforeEach` hooks; in-memory SQLite tables are created per test suite.
- **Strict Network Isolation**: Unit and integration tests never make external network calls to carrier APIs. Timers are controlled via `vi.useFakeTimers()` or explicit mock delay promises.
- **Deterministic Assertions**: Expected outputs are derived from authoritative contracts in `PROJECT.md` and `specs.md`.
