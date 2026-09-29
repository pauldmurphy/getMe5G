# Automated Testing Harness & Test Suites Plan
**Project**: 5G Home Internet & Wireless Broadband Availability Engine & Arbitrage Comparison
**Author**: explorer_survey_3 (Quality & Test Architecture)
**Date**: 2026-09-29
**Integrity Mode**: Development / Strict Verification

---

## 1. Executive Summary & Testing Strategy

This test plan defines the end-to-end automated testing harness and multi-tier verification methodology for the **5G Home Internet Availability Engine & Comparison Web Application**.

The application must reliably:
1. Intake raw user addresses, query zero-cost open geocoders (US Census / Photon / Nominatim) with pluggable Mapbox/Google fallback, and normalize postal components and coordinates.
2. Query FCC Broadband Data Collection (BDC) fixed wireless records alongside live carrier checking architecture (`IProviderChecker`).
3. Disambiguate parent carrier networks into distinct retail consumer brands:
   - **T-Mobile Network** -> **T-Mobile 5G Home Internet** AND **Metro by T-Mobile**
   - **Verizon Network** -> **Verizon 5G Home**, **Straight Talk Home Internet**, AND **Total Wireless**
   - **AT&T Network** -> **AT&T Internet Air**
   - **Non-terrestrial / Satellite** -> **Starlink** (with clear badges and fallback messaging)
4. Cache queries in SQLite via Drizzle ORM and an in-memory LRU cache to achieve sub-second response times (<2s cold, <50ms warm).
5. Render an interactive, accessible comparison report UI with responsive brand cards, speed/price filters, sorting, and direct outbound signup links.

### Testing Architecture Stack
- **Unit & Integration Testing**: **Vitest** (v1.x/v2.x) with `happy-dom` for DOM-related hooks, in-memory SQLite (`better-sqlite3` / `@libsql/client`) for Drizzle ORM testing, and Mock Service Worker (MSW) or native `vi.fn()`/`vi.spyOn()` for deterministic HTTP mocking.
- **End-to-End (E2E) Testing**: **Playwright** (v1.40+) targeting Next.js 14/15 App Router, running headless cross-browser suites (Chromium, Firefox, WebKit, Mobile Chrome) with network route interception (`page.route()`) against deterministic mock fixtures.
- **Test Hierarchy**: 4-Tier verification hierarchy guaranteeing comprehensive feature coverage (Tier 1), boundary/adversarial resilience (Tier 2), cross-feature combinatorial stability (Tier 3), and realistic consumer journeys (Tier 4).

---

## 2. Directory Layout & Harness Configuration

### 2.1 File & Directory Tree

```
tests/
├── unit/
│   ├── geocoding/
│   │   ├── address-normalizer.test.ts      # Component parsing, unit separation, abbreviations
│   │   ├── census-geocoder.test.ts         # US Census Bureau API client, coordinate extraction
│   │   ├── photon-geocoder.test.ts         # OpenStreetMap / Komoot Photon API client
│   │   └── geocoder-factory.test.ts        # Pluggable provider selection & fallback chain
│   ├── engine/
│   │   ├── fcc-bdc-parser.test.ts          # Tech codes (70, 71, 72), FRN / holding co extraction
│   │   ├── brand-mapper.test.ts            # T-Mobile->Metro, Verizon->StraightTalk->TotalWireless
│   │   ├── provider-checker.test.ts        # IProviderChecker contract, mock carrier checks
│   │   └── timeout-fallback.test.ts        # 1.5s AbortController timeout & safe fallback to FCC
│   └── catalog/
│       ├── drizzle-schema.test.ts          # SQLite schema, relations, constraints
│       ├── brand-catalog-service.test.ts   # Catalog query, plan retrieval, pricing tiers
│       └── cache-lru-service.test.ts       # In-memory LRU + SQLite L2 cache, TTL expiration
├── integration/
│   ├── api-availability.test.ts            # GET /api/availability?address=... end-to-end route
│   ├── api-geocode.test.ts                 # GET /api/geocode?q=... autocomplete & normalization
│   └── cache-persistence.test.ts           # Coordinate hashing, sub-second repeat lookups
├── e2e/
│   ├── fixtures/
│   │   ├── urban-multi-provider.json       # T-Mobile, Metro, Verizon, StraightTalk, Total, AT&T
│   │   ├── suburban-single-carrier.json    # Only T-Mobile & Metro (or only Verizon & Total)
│   │   ├── rural-satellite-only.json       # Zero terrestrial, Starlink fallback
│   │   └── invalid-address.json            # 404 / 400 error payloads and empty states
│   ├── models/
│   │   ├── SearchPage.ts                   # Page Object Model: Input, autocomplete dropdown
│   │   └── ReportPage.ts                   # Page Object Model: Cards, filters, sorting, badges
│   ├── 01-urban-multi-provider.spec.ts     # User Journey 1: Full multi-brand comparison
│   ├── 02-suburban-single-carrier.spec.ts  # User Journey 2: Single-carrier disambiguation
│   ├── 03-rural-satellite-only.spec.ts     # User Journey 3: Satellite badge & fallback notice
│   └── 04-invalid-address-edge-cases.spec.ts # User Journey 4: Geocoding failures & validation
├── mocks/
│   ├── fcc-bdc-sample.json                 # Raw FCC BDC fixture records
│   ├── providers-catalog-seed.json         # Master brand catalog metadata
│   └── server-handlers.ts                  # MSW / fetch mock handlers for network stubbing
└── setup/
    ├── vitest.setup.ts                     # Global test setup, fetch polyfills, env defaults
    └── test-db.ts                          # In-memory SQLite Drizzle test helper
```

### 2.2 Vitest Configuration (`vitest.config.ts`)

```typescript
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'happy-dom',
    globals: true,
    setupFiles: ['./tests/setup/vitest.setup.ts'],
    include: ['tests/unit/**/*.test.ts', 'tests/integration/**/*.test.ts'],
    exclude: ['tests/e2e/**/*', 'node_modules/**/*'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      lines: 85,
      functions: 85,
      branches: 80,
      statements: 85,
      exclude: [
        'tests/**/*',
        '**/*.d.ts',
        '**/*.config.*',
        '**/types/**'
      ],
    },
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
    testTimeout: 5000,
    hookTimeout: 5000,
  },
});
```

### 2.3 Playwright Configuration (`playwright.config.ts`)

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30000,
  expect: {
    timeout: 5000,
  },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['list']
  ],
  use: {
    baseURL: process.env.PLAYWRIGHT_TEST_BASE_URL || 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
    },
  ],
  webServer: {
    command: 'npm run start',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
});
```

---

## 3. Vitest Unit & Integration Test Suites

### 3.1 Suite 1: Address Parsing & Normalization (`tests/unit/geocoding/`)

#### Objectives:
Verify that raw address input strings and external geocoder payloads (US Census Bureau Geocoder, OpenStreetMap Nominatim, Komoot Photon) parse reliably into standardized postal components (`street_number`, `street_name`, `city`, `state`, `zip5`) and coordinates (`lat`, `lng`).

#### Test Specifications:

1. **Standard Single-Line Address Parsing** (`address-normalizer.test.ts`):
   - **Input**: `"350 5th Ave, New York, NY 10118"`
   - **Expected Output**:
     ```json
     {
       "street_number": "350",
       "street_name": "5th Ave",
       "unit": null,
       "city": "New York",
       "state": "NY",
       "zip5": "10118",
       "formatted": "350 5th Ave, New York, NY 10118"
     }
     ```
   - **Assertion**: Expect exact postal component mapping, uppercase 2-letter state code, and 5-digit zip.

2. **Apartment / Suite / MDU Normalization** (`address-normalizer.test.ts`):
   - **Input**: `"742 Evergreen Terrace Apt 4B, Springfield, OR 97477"`
   - **Expected Output**: `street_number: "742"`, `street_name: "Evergreen Terrace"`, `unit: "Apt 4B"`, `city: "Springfield"`, `state: "OR"`, `zip5: "97477"`.
   - **Assertion**: Secondary unit indicator is properly segregated and does not corrupt street name.

3. **ZIP+4 Normalization & Truncation** (`address-normalizer.test.ts`):
   - **Input**: `"1600 Pennsylvania Avenue NW, Washington, DC 20500-0003"`
   - **Expected Output**: `zip5: "20500"`, `zip4: "0003"`.
   - **Assertion**: 9-digit postal codes split into standardized 5-digit base and 4-digit extension.

4. **US Census Bureau Geocoder Response Adapter** (`census-geocoder.test.ts`):
   - **Input**: Mock Census Geocoder JSON response containing `addressMatches[0].coordinates.x` (lng) and `y` (lat) and `addressComponents`.
   - **Expected Output**: Normalized address object with `lat: 40.7484`, `lng: -73.9857`, and verified accuracy score.
   - **Assertion**: Ensure x/y longitude/latitude coordinate inversion is prevented (`x` = longitude, `y` = latitude).

5. **Komoot Photon / Nominatim Autocomplete Adapter** (`photon-geocoder.test.ts`):
   - **Input**: GeoJSON feature collection from Photon autocomplete API.
   - **Expected Output**: Array of autocomplete suggestion objects: `{ id: string, label: string, lat: number, lng: number, components: NormalizedAddress }`.
   - **Assertion**: Non-paid open endpoint responses correctly populate autocomplete dropdown format without requiring external API tokens.

6. **Pluggable Provider Chain & Fallback Hierarchy** (`geocoder-factory.test.ts`):
   - **Scenario**: Primary Census Geocoder returns 503 Service Unavailable or times out.
   - **Expected Behavior**: Geocoding client automatically falls back to secondary open provider (Photon/Nominatim), logging warning without failing user request.
   - **Assertion**: `spyOn(censusClient, 'geocode').mockRejectedValueOnce(new Error('503'))`; verify `photonClient.geocode` is called and returns valid normalized address.

---

### 3.2 Suite 2: FCC BDC Response Parsing & Brand Mapping (`tests/unit/engine/`)

#### Objectives:
Verify that raw FCC Broadband Data Collection (BDC) fixed wireless records are parsed correctly, filtered by technology codes, and mapped to separate, distinct retail consumer brands. Verify that `IProviderChecker` enforces a strict 1.5s timeout and gracefully falls back to FCC data.

#### Brand Disambiguation Logic Matrix:

| Parent Network / FRN | FCC Holding Company | Technology Codes | Generated Retail Brands | Distinguishing Characteristics |
| :--- | :--- | :--- | :--- | :--- |
| **0001565480** | T-Mobile USA, Inc. | 70, 71 (5G FWA) | 1. **T-Mobile 5G Home Internet**<br>2. **Metro by T-Mobile** | • T-Mobile: Postpaid, $50/mo autopay, bundle discount with voice line, T-Life app.<br>• Metro: Prepaid, $40-$50/mo, separate Metro store/online signup, no credit check. |
| **0003290673** | Cellco Partnership (Verizon) | 71, 72 (5G Ultra Wideband FWA) | 1. **Verizon 5G Home**<br>2. **Straight Talk Home Internet**<br>3. **Total Wireless Home Internet** | • Verizon: Postpaid, $35-$60/mo, Verizon router.<br>• Straight Talk: Prepaid, $45/mo, Walmart exclusive TracFone portal.<br>• Total Wireless: Prepaid, $45/mo, Total Wireless retail portal. |
| **0005050851** | AT&T Services, Inc. | 71 (5G FWA) | 1. **AT&T Internet Air** | • AT&T: $60/mo, AT&T All-Fi Hub. |
| **0027768225** | SpaceX Services (Starlink) | 60, 61 (Satellite) | 1. **Starlink** | • Non-terrestrial, $120/mo, $599 hardware kit, global satellite coverage. |

#### Test Specifications:

1. **T-Mobile Network Brand Disambiguation** (`brand-mapper.test.ts`):
   - **Input**: BDC record with `frn: "0001565480"`, `technology: 71`, `max_advertised_download: 245`, `max_advertised_upload: 35`.
   - **Expected Output**: An array of 2 distinct provider objects:
     1. `{ id: "t-mobile-5g-home", brandName: "T-Mobile 5G Home Internet", networkParent: "T-Mobile", techType: "5G Fixed Wireless", priceMonthly: 50.00, signupUrl: "https://www.t-mobile.com/home-internet" }`
     2. `{ id: "metro-by-t-mobile", brandName: "Metro by T-Mobile", networkParent: "T-Mobile", techType: "5G Fixed Wireless", priceMonthly: 40.00, signupUrl: "https://www.metrobyt-mobile.com/home-internet" }`
   - **Assertion**: Verify both brands exist as distinct top-level entities, each retaining their unique pricing, contract conditions, and official signup URLs.

2. **Verizon Network Brand Disambiguation** (`brand-mapper.test.ts`):
   - **Input**: BDC record with `frn: "0003290673"`, `technology: 71`, `max_advertised_download: 300`, `max_advertised_upload: 50`.
   - **Expected Output**: An array of 3 distinct provider objects:
     1. `{ id: "verizon-5g-home", brandName: "Verizon 5G Home", networkParent: "Verizon", priceMonthly: 35.00 }`
     2. `{ id: "straight-talk-home", brandName: "Straight Talk Home Internet", networkParent: "Verizon", priceMonthly: 45.00 }`
     3. `{ id: "total-wireless-home", brandName: "Total Wireless Home Internet", networkParent: "Verizon", priceMonthly: 45.00 }`
   - **Assertion**: Verify 3 separate entries are created with distinct IDs, plan metadata, and brand tags.

3. **Technology Code Filtering** (`fcc-bdc-parser.test.ts`):
   - **Input**: Raw dataset containing records with technology codes `10` (Copper DSL), `40` (Coaxial Cable), `70` (Unlicensed FWA), `71` (Licensed FWA), `72` (Licensed-by-rule FWA).
   - **Expected Output**: Output contains only records with codes `70`, `71`, `72` (and satellite `60`/`61` for rural fallback). Codes `10` and `40` must be discarded.
   - **Assertion**: Validate strict fixed wireless broadband filtering.

4. **Rural Satellite Detection & Fallback Badge** (`brand-mapper.test.ts`):
   - **Input**: Location record with zero terrestrial fixed wireless entries.
   - **Expected Output**: Single provider entry:
     ```json
     {
       "id": "starlink-satellite",
       "brandName": "Starlink",
       "networkParent": "SpaceX",
       "techType": "Satellite",
       "priceMonthly": 120.00,
       "equipmentCost": 599.00,
       "isSatellite": true,
       "fallbackNotice": "No terrestrial 5G Home Internet available at this address. Showing best alternative wireless/satellite broadband: Starlink"
     }
     ```
   - **Assertion**: `isSatellite` boolean is `true`, `fallbackNotice` string is populated, and hardware kit fee is explicit.

5. **`IProviderChecker` 1.5s Timeout Enforcement** (`timeout-fallback.test.ts`):
   - **Setup**: Mock carrier API endpoint configured to artificially delay response by 2500ms.
   - **Execution**: Engine initiates provider check with 1500ms timeout budget.
   - **Expected Behavior**: AbortController signals abort at <= 1500ms; carrier check resolves with `{ status: "timeout", source: "FCC_BDC_FALLBACK" }`.
   - **Assertion**: Entire availability check finishes in < 1600ms without throwing an unhandled exception or breaking the response pipeline.

6. **Provider Checker Error Resilience** (`timeout-fallback.test.ts`):
   - **Setup**: Mock carrier endpoint returns HTTP 500 or 429 Too Many Requests.
   - **Expected Behavior**: Engine intercepts the error, flags `{ status: "fallback", data: fccData }`, and returns standard HTTP 200 payload.
   - **Assertion**: HTTP response code remains 200; error details are logged server-side; client receives verified BDC coverage data.

---

### 3.3 Suite 3: Catalog Query & Drizzle ORM Caching (`tests/unit/catalog/` & `tests/integration/`)

#### Objectives:
Verify that the SQLite database schema stores rich brand metadata, handles catalog lookups, and manages a two-tier cache (L1 in-memory LRU + L2 SQLite table) with configurable TTL to deliver sub-second (<50ms warm) responses.

#### Drizzle Schema Definition Contract:

```typescript
// brands table
export const brands = sqliteTable('brands', {
  id: text('id').primaryKey(),
  brandName: text('brand_name').notNull(),
  carrierParent: text('carrier_parent').notNull(),
  techType: text('tech_type').notNull(),
  downloadMinMbps: integer('download_min_mbps').notNull(),
  downloadMaxMbps: integer('download_max_mbps').notNull(),
  uploadMinMbps: integer('upload_min_mbps').notNull(),
  uploadMaxMbps: integer('upload_max_mbps').notNull(),
  monthlyCostCents: integer('monthly_cost_cents').notNull(),
  equipmentFeeCents: integer('equipment_fee_cents').notNull(),
  contractTermMonths: integer('contract_term_months').notNull(),
  signupUrl: text('signup_url').notNull(),
  badgeColor: text('badge_color').notNull(),
  featuresJson: text('features_json').notNull(), // stringified array
  isActive: integer('is_active', { mode: 'boolean' }).notNull().default(true),
});

// availability_cache table
export const availabilityCache = sqliteTable('availability_cache', {
  queryHash: text('query_hash').primaryKey(),
  normalizedAddress: text('normalized_address').notNull(),
  lat: real('lat').notNull(),
  lng: real('lng').notNull(),
  resultsJson: text('results_json').notNull(),
  createdAt: integer('created_at', { mode: 'timestamp' }).notNull(),
  expiresAt: integer('expires_at', { mode: 'timestamp' }).notNull(),
});
```

#### Test Specifications:

1. **Brand Catalog Seed & Query Verification** (`brand-catalog-service.test.ts`):
   - **Execution**: Initialize in-memory SQLite, run Drizzle migrations, seed brands.
   - **Assertion**: Query `getAllBrands()`; expect exactly all 7 brands (T-Mobile 5G Home, Metro by T-Mobile, Verizon 5G Home, Straight Talk, Total Wireless, AT&T Internet Air, Starlink) with valid speed ranges and signup links.

2. **L1 In-Memory LRU Cache Hit & Miss** (`cache-lru-service.test.ts`):
   - **Execution**: Query coordinate `(40.7484, -73.9857)`.
   - **First Call (Miss)**: Returns data, stores in LRU cache. Execution time ~ 50-100ms.
   - **Second Call (Hit)**: Returns cached object directly from memory in < 2ms without invoking database or external APIs.
   - **Assertion**: Spy on DB query function; ensure DB query is invoked exactly once.

3. **L2 SQLite Cache Persistence & Coordinate Hash** (`cache-persistence.test.ts`):
   - **Execution**: Compute coordinate hash using 4 decimal places of precision (`lat.toFixed(4) + ":" + lng.toFixed(4)`). Verify lookups within ~11 meters hit the same cached response.
   - **Assertion**: Insert into `availabilityCache`; query back by `queryHash`; verify `resultsJson` deserializes into identical provider payload.

4. **TTL Expiration & Eviction** (`cache-lru-service.test.ts`):
   - **Setup**: Configure TTL = 60 seconds. Store entry with `expiresAt = Date.now() - 1000`.
   - **Execution**: Call `getCachedAvailability(hash)`.
   - **Expected Output**: Returns `null`; triggers eviction/cleanup.
   - **Assertion**: Expired entry is purged from both LRU and SQLite cache.

5. **Repeat Query Sub-Second Latency Benchmark** (`api-availability.test.ts`):
   - **Execution**: Issue 20 consecutive HTTP requests to `GET /api/availability?address=350+5th+Ave+New+York+NY`.
   - **Assertion**: Requests 2 through 20 resolve with HTTP 200 in under 30ms each, with `X-Cache: HIT` header.

---

## 4. Playwright End-to-End (E2E) Test Suite Design

### 4.1 E2E Architecture & Network Interception Strategy

To ensure 100% determinism, speed, and offline capability without incurring rate limits or hitting live carrier sign-in portals, Playwright tests intercept Next.js App Router API routes (`/api/geocode` and `/api/availability`) using `page.route()`.

```typescript
// tests/e2e/helpers/mock-network.ts
import { Page } from '@playwright/test';
import urbanFixture from '../fixtures/urban-multi-provider.json';
import suburbanFixture from '../fixtures/suburban-single-carrier.json';
import ruralFixture from '../fixtures/rural-satellite-only.json';
import invalidFixture from '../fixtures/invalid-address.json';

export async function setupMockRoutes(page: Page, scenario: 'urban' | 'suburban' | 'rural' | 'invalid') {
  await page.route('**/api/geocode*', async (route) => {
    if (scenario === 'invalid') {
      return route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Address not found', suggestions: [] }),
      });
    }
    const fixtureMap = {
      urban: urbanFixture.geocoded,
      suburban: suburbanFixture.geocoded,
      rural: ruralFixture.geocoded,
    };
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(fixtureMap[scenario]),
    });
  });

  await page.route('**/api/availability*', async (route) => {
    const fixtureMap = {
      urban: urbanFixture.availability,
      suburban: suburbanFixture.availability,
      rural: ruralFixture.availability,
      invalid: invalidFixture.availability,
    };
    return route.fulfill({
      status: scenario === 'invalid' ? 400 : 200,
      contentType: 'application/json',
      body: JSON.stringify(fixtureMap[scenario]),
    });
  });
}
```

### 4.2 Page Object Models (POM)

#### SearchPage POM (`tests/e2e/models/SearchPage.ts`):
- `goto()`: Navigates to `/`.
- `fillAddressInput(address: string)`: Types address into search field.
- `waitForAutocomplete()`: Waits for suggestion dropdown menu.
- `selectAutocompleteSuggestion(index: number)`: Clicks suggestion item.
- `submitSearch()`: Clicks submit button or presses Enter.
- `getErrorMessage()`: Locates input error or validation banner.

#### ReportPage POM (`tests/e2e/models/ReportPage.ts`):
- `waitForResultsLoaded()`: Waits for skeleton loaders to resolve and comparison cards to appear.
- `getProviderCards()`: Returns Playwright locator for all provider cards (`[data-testid="provider-card"]`).
- `getProviderCardByBrand(brandName: string)`: Returns locator for specific brand card.
- `getBrandBadges()`: Locates network parent badges (`[data-testid="network-badge"]`).
- `filterByCarrier(carrier: 'All' | 'T-Mobile' | 'Verizon' | 'AT&T' | 'Starlink')`: Toggles carrier filter.
- `filterByMinSpeed(speedMbps: number)`: Adjusts speed slider/radio.
- `sortBy(criteria: 'price-asc' | 'price-desc' | 'speed-desc')`: Selects sort option.
- `getFallbackNotice()`: Returns locator for satellite/limited coverage alert.
- `clickSignupLink(brandName: string)`: Clicks outbound link and verifies destination URL attribute.

---

### 4.3 Detailed Test Scenarios & User Journeys

#### User Journey A: Urban Multi-Provider (`01-urban-multi-provider.spec.ts`)
- **Address**: `"350 5th Ave, New York, NY 10118"` (Manhattan, NY)
- **Persona**: Tech-savvy urban consumer seeking the fastest and most cost-effective 5G broadband option.
- **Fixture State**: Active coverage across T-Mobile, Verizon, and AT&T networks.
- **User Actions**:
  1. User navigates to homepage.
  2. Types `"350 5th Ave, New York, NY"`.
  3. Autocomplete shows `"350 5th Ave, New York, NY 10118"`. User clicks suggestion.
  4. User clicks "Check 5G Availability".
- **Verification Assertions**:
  1. URL updates to `/report?address=...` or results view mounts.
  2. Exactly **6 distinct brand cards** are rendered:
     - `T-Mobile 5G Home Internet` ($50/mo, 72-245 Mbps, magenta badge)
     - `Metro by T-Mobile` ($40-$50/mo, 72-245 Mbps, purple/orange badge)
     - `Verizon 5G Home` ($35-$60/mo, 85-300 Mbps, red badge)
     - `Straight Talk Home Internet` ($45/mo, 25-100 Mbps, green badge)
     - `Total Wireless Home Internet` ($45/mo, 25-100 Mbps, blue badge)
     - `AT&T Internet Air` ($60/mo, 75-225 Mbps, blue/cyan badge)
  3. **Filter Test**: User selects "T-Mobile" network family filter. Only T-Mobile and Metro cards remain visible (count = 2). Verizon and AT&T cards disappear.
  4. **Sort Test**: User selects "Sort by Price: Low to High". Cards reorder: lowest monthly cost appears first.
  5. **Outbound Signup Test**: User checks "Get Plan" button for Metro by T-Mobile. Verifies `href` points to official Metro portal with `target="_blank"` and `rel="noopener noreferrer"`.

#### User Journey B: Suburban Single-Carrier (`02-suburban-single-carrier.spec.ts`)
- **Address**: `"456 Oak Rd, Naperville, IL 60540"`
- **Persona**: Suburban homeowner with limited 5G tower line-of-sight where only one major carrier has deployed mid-band 5G FWA.
- **Fixture State**: T-Mobile network present; Verizon and AT&T absent.
- **User Actions**:
  1. User submits `"456 Oak Rd, Naperville, IL 60540"`.
  2. Availability engine completes.
- **Verification Assertions**:
  1. Exactly **2 brand cards** are displayed: `T-Mobile 5G Home Internet` and `Metro by T-Mobile`.
  2. Verizon, Straight Talk, Total Wireless, and AT&T Air cards are confirmed absent (`count() === 0`).
  3. Informational header / banner is rendered: `"2 plans available from 1 wireless network (T-Mobile)"`.
  4. Side-by-side comparison highlights the key arbitrage differences:
     - Metro: No annual contract, prepaid, lower entry cost.
     - T-Mobile: Postpaid, perks included, voice bundle discount.
  5. Inactive filters (e.g. "Verizon") are either disabled or show `(0)` available.

#### User Journey C: Rural Satellite-Only (`03-rural-satellite-only.spec.ts`)
- **Address**: `"Route 1 Box 42, Big Piney, WY 83113"`
- **Persona**: Rural resident outside terrestrial cellular fixed wireless coverage looking for broadband options.
- **Fixture State**: Zero terrestrial 5G FWA coverage; Starlink satellite available.
- **User Actions**:
  1. User enters rural address and submits query.
- **Verification Assertions**:
  1. Prominent fallback notification banner appears at the top:
     - Text: `"No terrestrial 5G Home Internet available at this address."`
     - Subtext: `"Showing best alternative wireless & satellite broadband options:"`
  2. Single primary card rendered for **Starlink**:
     - Technology badge clearly reads `"Satellite"` (distinct style from 5G badges).
     - Pricing: `$120/mo`.
     - Hardware disclosure: `$599 hardware kit required`.
     - Latency disclaimer: `Estimated Latency: 25-50ms (Low Earth Orbit)`.
  3. Outbound link points directly to Starlink order portal.
  4. No broken image links, missing pricing fields, or undefined variables in the UI.

#### User Journey D: Invalid Address Error Handling & Edge Cases (`04-invalid-address-edge-cases.spec.ts`)
- **Address Scenarios**:
  - Scenario D1: Blank submission / whitespace only.
  - Scenario D2: Non-existent address (`"99999 Nonexistent Blvd, Nowhere, ZZ 00000"`).
  - Scenario D3: Geocoder server outage / 503 HTTP response.
- **User Actions & Verification Assertions**:
  1. **Blank input**: User clicks submit without entering text. Client-side HTML5 / React hook form prevents submission, highlights input with red border, displays: `"Please enter a valid street address."`
  2. **Non-existent address**: User enters `"99999 Nonexistent Blvd, Nowhere, ZZ 00000"` and submits.
     - Geocoder returns 404 / empty match.
     - App renders friendly error state card: `"We couldn't locate this address. Please verify the street number and 5-digit zip code."`
     - "Try Another Address" button refocuses the search bar and clears the invalid query.
  3. **Service Outage**: Geocoder returns HTTP 503.
     - App renders error banner: `"Address service temporarily unavailable. Please retry in a few moments."`
     - No uncaught JavaScript exceptions appear in console logs.

---

## 5. Test Hierarchy Design (Tiers 1-4 Methodology)

The test hierarchy employs a structured 4-tier model ensuring exhaustive verification from individual methods up to complex multi-user workflows.

```
       ▲
      / \     Tier 4: Real-World Scenarios (End-to-End User Workflows)
     /   \    Tier 3: Pairwise Combinations (Cross-Feature Matrix)
    /     \   Tier 2: Boundary & Corner Cases (>=5 per feature)
   /_______\  Tier 1: Feature Coverage (>=5 per feature across 6 features)
```

### 5.1 Tier 1: Feature Coverage (>=5 Tests Per Feature)

Tier 1 covers nominal functionality across all 6 application features. Every feature must have at least 5 distinct test cases (Total: 30+ tests).

#### Feature 1: Address Intake & Autocomplete
| Test ID | Test Name | Input / Setup | Expected Outcome |
| :--- | :--- | :--- | :--- |
| `T1-F1-01` | Autocomplete Query Fetch | Input `"1600 Penn"` with debounce | Sends GET request to `/api/geocode?q=1600+Penn` |
| `T1-F1-02` | Dropdown Rendering | Geocoder returns 5 suggestions | Renders 5 selectable dropdown items in DOM |
| `T1-F1-03` | Keyboard Navigation | Press `ArrowDown` twice and `Enter` | Selects the second suggestion and populates input |
| `T1-F1-04` | Clear Button Action | Click 'X' clear button | Empties search input, resets state, focuses field |
| `T1-F1-05` | Form Submission on Selection | Click suggestion item | Triggers form submit with selected suggestion payload |

#### Feature 2: Geocoding & Address Normalization
| Test ID | Test Name | Input / Setup | Expected Outcome |
| :--- | :--- | :--- | :--- |
| `T1-F2-01` | Standard US Parsing | `"100 Pine St, San Francisco, CA 94111"` | Extracted: street, city, state, zip5, lat, lng |
| `T1-F2-02` | Directional & Abbreviation Normalization | `"123 North Main Street"` | Standardized to `"123 N Main St"` |
| `T1-F2-03` | Secondary Unit Extraction | `"450 7th Ave Suite 1501"` | Normalizes unit to `"Suite 1501"` without altering street |
| `T1-F2-04` | Coordinate Extraction (Census) | Census API response `{x: -122.4, y: 37.7}` | Mapped correctly to `{lng: -122.4, lat: 37.7}` |
| `T1-F2-05` | Pluggable Provider Selection | `GEOCODER_PROVIDER=photon` in env | Initializes Photon client as active geocoder |

#### Feature 3: FCC BDC Data Ingestion & Brand Mapping
| Test ID | Test Name | Input / Setup | Expected Outcome |
| :--- | :--- | :--- | :--- |
| `T1-F3-01` | T-Mobile Dual-Brand Splitting | T-Mobile FRN `0001565480` | Emits both "T-Mobile 5G Home" and "Metro by T-Mobile" |
| `T1-F3-02` | Verizon Triple-Brand Splitting | Verizon FRN `0003290673` | Emits "Verizon 5G Home", "Straight Talk", "Total Wireless" |
| `T1-F3-03` | AT&T Brand Resolution | AT&T FRN `0005050851` | Emits "AT&T Internet Air" with verified pricing |
| `T1-F3-04` | Tech Code 70/71 Filtering | Mixed records with tech codes 10, 40, 71 | Filters out wireline (10, 40); keeps wireless FWA (71) |
| `T1-F3-05` | Starlink Satellite Fallback | Coordinates with zero terrestrial FWA | Generates "Starlink" with satellite badge & disclaimers |

#### Feature 4: Provider Checker Engine & Timeout/Fallback
| Test ID | Test Name | Input / Setup | Expected Outcome |
| :--- | :--- | :--- | :--- |
| `T1-F4-01` | Fast Provider Check Execution | Mock carrier endpoint responds in 200ms | Returns live carrier verification status: `available` |
| `T1-F4-02` | 1.5s Timeout Abort | Mock carrier endpoint delays 2000ms | AbortController cancels request at 1500ms; falls back to FCC |
| `T1-F4-03` | Carrier 500 Error Interception | Mock carrier returns HTTP 500 | Gracefully falls back to FCC BDC data; request does not fail |
| `T1-F4-04` | Carrier 429 Rate Limit Handling | Mock carrier returns HTTP 429 | Logs rate-limit alert, falls back to FCC BDC data |
| `T1-F4-05` | Parallel Multi-Provider Dispatch | 3 carrier checkers run simultaneously | All run concurrently via `Promise.allSettled`; total time < 1.6s |

#### Feature 5: Provider Catalog & Drizzle SQLite Caching
| Test ID | Test Name | Input / Setup | Expected Outcome |
| :--- | :--- | :--- | :--- |
| `T1-F5-01` | Brand Metadata Retrieval | Query catalog for brand `metro-by-t-mobile` | Returns full metadata: price $40, no contract, signup URL |
| `T1-F5-02` | L1 In-Memory LRU Cache Insert | Fetch availability for new coordinate | Entry added to memory LRU cache with timestamp |
| `T1-F5-03` | L1 LRU Cache Hit Verification | Repeat fetch for identical coordinate | Returns result in <5ms without hitting database |
| `T1-F5-04` | L2 SQLite Cache Persistence | Write result to `availability_cache` table | Record persists to SQLite with query hash and expiration |
| `T1-F5-05` | Cache Eviction on TTL Expiry | Query entry where `expires_at < now` | Returns null, purges stale record, initiates fresh lookup |

#### Feature 6: Comparison Report UI & Filtering/Sorting
| Test ID | Test Name | Input / Setup | Expected Outcome |
| :--- | :--- | :--- | :--- |
| `T1-F6-01` | Comparison Card Rendering | Urban payload with 6 brands | Renders 6 distinct cards with title, price, speeds, CTA |
| `T1-F6-02` | Carrier Network Filter | Click "Verizon" filter badge | Renders only Verizon, Straight Talk, and Total Wireless |
| `T1-F6-03` | Price Sort Ascending | Select sort option `Price: Low to High` | Cards reordered from lowest monthly price to highest |
| `T1-F6-04` | Speed Sort Descending | Select sort option `Speed: High to Low` | Cards reordered by advertised max download speed |
| `T1-F6-05` | Outbound Signup Link Click | Click "Order Now" on T-Mobile card | Opens official T-Mobile signup portal in new tab (`_blank`) |

---

### 5.2 Tier 2: Boundary & Corner Cases (>=5 Tests Per Feature)

Tier 2 tests evaluate system behavior under extreme, invalid, or edge-case conditions (Total: 30+ tests).

#### Boundary Suite 1: Geocoding & Input Boundaries
- `T2-B1-01`: Empty string or whitespace-only input (`"   "`) -> Rejected client-side before network request.
- `T2-B1-02`: Extremely long string (500+ characters) -> Truncated/validated; rejects with HTTP 400 without buffer overflow.
- `T2-B1-03`: Address with special characters / SQL injection syntax (`"123 Main St'; DROP TABLE brands;--"` ) -> Sanitized; geocodes safely.
- `T2-B1-04`: PO Box address (`"PO Box 1234, Dallas, TX 75201"`) -> Detected as non-serviceable PO Box; displays warning: "5G Home Internet requires a physical residential street address."
- `T2-B1-05`: Military APO/FPO/DPO address (`"PSC 812 Box 2140, FPO, AE 09627"`) -> Gracefully handled with non-coverage notification.

#### Boundary Suite 2: Address Parsing & Normalization Boundaries
- `T2-B2-01`: Address missing street number (`"Broadway, New York, NY 10001"`) -> Flags missing street number, prompts user to specify house number.
- `T2-B2-02`: Address with fractional house number (`"123 1/2 Maple St, Seattle, WA 98101"`) -> Successfully normalizes house number as `"123 1/2"`.
- `T2-B2-03`: Address with vanity/alphanumeric house number (`"N12W34560 Lake Dr, Delafield, WI 53018"`) -> Parses rural Wisconsin grid coordinate address correctly.
- `T2-B2-04`: Missing ZIP code (`"100 Pine St, San Francisco, CA"`) -> Geocoder infers 94111 from street and city without failure.
- `T2-B2-05`: Latitude/Longitude bounding box limits (`lat: 90.0`, `lng: -180.0` or out-of-range coords) -> Validates coordinates within US territorial bounding box (lat: 18-72, lng: -179 to -65).

#### Boundary Suite 3: FCC BDC & Provider Engine Boundaries
- `T2-B3-01`: Exactly 1500ms response time boundary -> Verifies timer boundary condition: 1499ms accepted, 1501ms aborted.
- `T2-B3-02`: Corrupted BDC record (null FRN or missing advertised speeds) -> Fallback values applied; prevents runtime null pointer exception.
- `T2-B3-03`: Unregistered carrier FRN in BDC dataset -> Logged as unmapped carrier; excluded from branded consumer comparison without crashing.
- `T2-B3-04`: 100% of provider checker endpoints timing out simultaneously -> Graceful complete fallback to FCC BDC data; UI shows "Estimated from FCC data" badges.
- `T2-B3-05`: Duplicate BDC entries for same provider at same location -> Deduplicated by latest timestamp and highest speed tier.

#### Boundary Suite 4: Brand Resolution & Arbitrage Boundaries
- `T2-B4-01`: Exact price and speed tie between two competing brands -> Stable sorting preserved using secondary alphabetical brand key.
- `T2-B4-02`: Free tier / promotional $0 introductory pricing -> Display logic correctly formats "$0 / first mo" without displaying "NaN" or "Free".
- `T2-B4-03`: High-cost enterprise tier ($299+/mo) -> UI gracefully formats large numeric amounts without overflow or truncation.
- `T2-B4-04`: Zero upload speed reported by BDC -> Defaults to speed tier minimum (e.g. 5-10 Mbps) rather than displaying "0 Mbps upload".
- `T2-B4-05`: Missing signup link in catalog -> Renders disabled button with "Call for Availability" fallback instead of broken link.

#### Boundary Suite 5: Cache & Concurrency Boundaries
- `T2-B5-01`: High-concurrency stampede (50 simultaneous requests for same un-cached address) -> Single in-flight promise shared via request coalescing; DB queried only once.
- `T2-B5-02`: LRU cache capacity overflow (1,001 entries added to 1,000 capacity cache) -> Verified eviction of oldest entry (`tail.prev`).
- `T2-B5-03`: Expiration edge at t = `expiresAt - 1ms` vs `expiresAt + 1ms` -> Exact boundary check verifies cache hit at -1ms and cache miss at +1ms.
- `T2-B5-04`: Coordinate hash collision avoidance -> Ensures coordinates `(40.7484, -73.9857)` and `(40.7485, -73.9857)` generate distinct cache keys.
- `T2-B5-05`: SQLite disk write failure or read-only filesystem simulation -> In-memory LRU cache continues operating seamlessly even if SQLite write fails.

#### Boundary Suite 6: UI & Viewport Boundaries
- `T2-B6-01`: Narrow viewport width (320px screen) -> All cards, badges, and pricing stacks cleanly without horizontal overflow.
- `T2-B6-02`: Ultrawide viewport (2560px screen) -> Grid max-width containment prevents stretched, distorted comparison cards.
- `T2-B6-03`: Text zoom to 200% (Accessibility WCAG 2.1 AA) -> All plan details remain readable and interactive without overlapping containers.
- `T2-B6-04`: Rapid filter toggling (spam clicking carrier filters in 100ms) -> React state updates cleanly without UI freezing or stale state.
- `T2-B6-05`: Screen reader navigation (VoiceOver/NVDA) -> All cards have aria-label, sort dropdowns have role="listbox", and badges have appropriate semantic roles.

---

### 5.3 Tier 3: Cross-Feature Combinations (Pairwise Matrix)

Tier 3 validates interactions across multiple subsystems using a pairwise combinatorial matrix.

#### Pairwise Dimension Definition:
1. **Factor A (Geocoder)**: `[US Census, Komoot Photon, Mapbox]`
2. **Factor B (Coverage Profile)**: `[Urban Multi, Suburban Single, Rural Satellite, Zero Coverage]`
3. **Factor C (Provider Engine Status)**: `[All Online, Partial Timeout (1.5s), All Failed/Fallback]`
4. **Factor D (Cache State)**: `[Cold Miss, Warm L1 Hit, Expired TTL]`
5. **Factor E (Device Viewport)**: `[Desktop (1440px), Mobile (375px)]`

#### Pairwise Test Matrix (12 Targeted Cross-Cutting Tests):

| Test ID | Factor A (Geocoder) | Factor B (Coverage) | Factor C (Engine Status) | Factor D (Cache State) | Factor E (Viewport) | Expected Cross-Feature Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `T3-P-01` | US Census | Urban Multi | All Online | Cold Miss | Desktop | Geocodes via Census -> fetches 6 brands live -> populates L1 cache -> renders 3-column grid. |
| `T3-P-02` | Komoot Photon | Suburban Single | Partial Timeout | Cold Miss | Mobile | Photon autocomplete -> T-Mobile online, Verizon times out (1.5s) -> falls back to FCC -> renders mobile stack. |
| `T3-P-03` | Mapbox | Rural Satellite | All Failed/Fallback | Cold Miss | Desktop | Mapbox geocodes -> all carrier APIs 500 -> FCC shows no FWA -> Starlink fallback rendered with alert banner. |
| `T3-P-04` | US Census | Zero Coverage | All Online | Expired TTL | Mobile | Census geocodes -> TTL expired -> fresh lookup yields no coverage -> renders "No wireless broadband found" view. |
| `T3-P-05` | Komoot Photon | Urban Multi | Partial Timeout | Warm L1 Hit | Desktop | L1 hit bypasses geocoder & engine entirely -> renders instantly (<50ms) in desktop view with filter controls. |
| `T3-P-06` | Mapbox | Suburban Single | All Online | Warm L1 Hit | Mobile | Cached single-carrier result loaded instantly on mobile -> interactive sorting functions properly. |
| `T3-P-07` | US Census | Rural Satellite | Partial Timeout | Cold Miss | Mobile | Census normalizes rural route -> 1.5s timeout aborts live check -> Starlink fallback rendered with mobile hardware disclaimer. |
| `T3-P-08` | Komoot Photon | Zero Coverage | All Failed/Fallback | Warm L1 Hit | Desktop | Cached zero-coverage state returns immediately without re-triggering failing carrier endpoints. |
| `T3-P-09` | Mapbox | Urban Multi | All Failed/Fallback | Expired TTL | Mobile | Mapbox geocodes -> TTL expired -> all carriers fail -> 100% FCC BDC fallback data successfully populates 6 cards on mobile. |
| `T3-P-10` | US Census | Suburban Single | All Failed/Fallback | Cold Miss | Desktop | Census geocodes -> carrier APIs fail -> FCC provides single-carrier coverage -> renders comparison with FCC notice. |
| `T3-P-11` | Komoot Photon | Rural Satellite | All Online | Expired TTL | Desktop | Photon geocodes -> cache refreshed -> Starlink satellite card updated with current equipment pricing. |
| `T3-P-12` | Mapbox | Zero Coverage | Partial Timeout | Cold Miss | Desktop | Mapbox geocodes -> carrier timeout -> zero coverage identified -> displays email notification intake form for future rollout. |

---

### 5.4 Tier 4: Real-World Application Scenarios

Tier 4 tests model end-to-end, multi-step consumer workflows representing diverse real-world personas and use cases.

#### Scenario 1: The "Arbitrage Bargain Hunter" (Metro vs. T-Mobile)
- **Persona**: A cost-conscious renter moving into a Chicago apartment who wants high-speed home internet without credit checks or long-term contracts.
- **Workflow**:
  1. Enters `"233 S Wacker Dr, Chicago, IL 60606"`.
  2. Selects address from autocomplete suggestions.
  3. System renders available plans. User notes both **T-Mobile 5G Home Internet** ($50/mo) and **Metro by T-Mobile** ($40/mo) utilize the same T-Mobile Ultra Capacity 5G network.
  4. User clicks "Filter by Network: T-Mobile" to isolate the two sister brands.
  5. Clicks the "Compare Brand Details" toggle:
     - Notes Metro has a $40 promo rate with autopay and phone line, no contract, prepaid.
     - Notes T-Mobile has Netflix perks and Price Lock guarantee.
  6. User decides on Metro by T-Mobile and clicks "Sign Up with Metro".
  7. Verifies new browser tab opens to official Metro Home Internet portal.

#### Scenario 2: The "Remote Mountain Cabin Worker" (Starlink Fallback)
- **Persona**: A remote software engineer buying a cabin in Leadville, CO who needs reliable internet and wants to verify if cellular 5G home internet has reached the area.
- **Workflow**:
  1. Enters `"789 Mountain Pass Rd, Leadville, CO 80461"`.
  2. Submits address.
  3. System checks FCC BDC and carrier availability endpoints; detects zero terrestrial 5G FWA coverage.
  4. System gracefully renders the fallback view:
     - Alert: `"5G Fixed Wireless is not currently available at this location."`
     - Card: **Starlink Standard** displayed prominently.
     - Badges: `"Satellite Internet"` and `"Low Earth Orbit"`.
     - Specs: 50-220 Mbps download, 10-25 Mbps upload, $120/mo + $599 equipment kit.
  5. User expands the "Latency & Gaming Considerations" dropdown, verifying clear disclosure that satellite latency (25-50ms) differs from terrestrial fiber/5G.
  6. User clicks "Order Starlink Kit".

#### Scenario 3: The "Work-From-Home Suburban Power User" (Verizon vs. Straight Talk)
- **Persona**: A suburban homeowner in Dallas, TX requiring minimum 100 Mbps download for multi-party video conferencing.
- **Workflow**:
  1. Enters `"1234 Preston Rd, Dallas, TX 75230"`.
  2. Submits query.
  3. Results page displays 5 brands (Verizon, Straight Talk, Total Wireless, T-Mobile, Metro).
  4. User moves the "Minimum Download Speed" filter slider to `100 Mbps`.
  5. Lower-speed tiers filter out dynamically.
  6. User compares **Verizon 5G Home Plus** (up to 300 Mbps, $45 with mobile plan) against **Straight Talk** (up to 100 Mbps, $45 flat prepaid).
  7. User sorts by "Speed: High to Low"; verifies Verizon 5G Home appears at the top.
  8. Clicks outbound signup link for Verizon 5G Home.

#### Scenario 4: The "Multi-Unit Apartment Dweller" (MDU Unit Disambiguation)
- **Persona**: Resident living in a dense multi-family residential building in Seattle, WA.
- **Workflow**:
  1. Enters `"1900 5th Ave Apt 1204, Seattle, WA 98101"`.
  2. System normalizes address: extracts street coordinates while preserving apartment `"Apt 1204"`.
  3. Geocoder validates coordinate accurately matches building centroid.
  4. System runs carrier pre-flight check with MDU unit parameter.
  5. UI displays availability results with banner: `"Showing broadband options for Apt 1204"`.

#### Scenario 5: High-Concurrency Burst & Cache Benchmark
- **Persona**: Automated stress test / benchmark simulating launch-day traffic surge.
- **Workflow**:
  1. Dispatch 100 concurrent availability queries across 10 distinct US addresses (10 requests per address).
  2. Verifies:
     - 10 cold queries execute geocoding and DB storage in parallel without deadlock.
     - 90 warm queries hit L1 in-memory cache.
     - 100% of responses return HTTP 200 within < 2 seconds.
     - P95 response latency across all 100 requests is < 150ms.
     - Zero database corruption or unhandled promise rejections.

---

## 6. Test Fixture Datasets (Mock Schemas & Samples)

### 6.1 Urban Multi-Provider Fixture (`tests/e2e/fixtures/urban-multi-provider.json`)

```json
{
  "geocoded": {
    "formatted": "350 5th Ave, New York, NY 10118",
    "street_number": "350",
    "street_name": "5th Ave",
    "city": "New York",
    "state": "NY",
    "zip5": "10118",
    "lat": 40.7484,
    "lng": -73.9857
  },
  "availability": {
    "address": "350 5th Ave, New York, NY 10118",
    "coordinates": { "lat": 40.7484, "lng": -73.9857 },
    "totalProviders": 6,
    "hasTerrestrial5G": true,
    "providers": [
      {
        "id": "t-mobile-5g-home",
        "brandName": "T-Mobile 5G Home Internet",
        "networkParent": "T-Mobile",
        "techType": "5G Fixed Wireless",
        "downloadMinMbps": 72,
        "downloadMaxMbps": 245,
        "uploadMinMbps": 15,
        "uploadMaxMbps": 35,
        "monthlyCost": 50.00,
        "equipmentFee": 0.00,
        "contractTermMonths": 0,
        "badgeColor": "#E20074",
        "isSatellite": false,
        "signupUrl": "https://www.t-mobile.com/home-internet",
        "features": ["No annual contract", "Unlimited data", "T-Life rewards", "AutoPay discount"]
      },
      {
        "id": "metro-by-t-mobile",
        "brandName": "Metro by T-Mobile",
        "networkParent": "T-Mobile",
        "techType": "5G Fixed Wireless",
        "downloadMinMbps": 72,
        "downloadMaxMbps": 245,
        "uploadMinMbps": 15,
        "uploadMaxMbps": 35,
        "monthlyCost": 40.00,
        "equipmentFee": 0.00,
        "contractTermMonths": 0,
        "badgeColor": "#3C1053",
        "isSatellite": false,
        "signupUrl": "https://www.metrobyt-mobile.com/home-internet",
        "features": ["Prepaid monthly", "No credit check", "Requires Metro voice line for promo rate"]
      },
      {
        "id": "verizon-5g-home",
        "brandName": "Verizon 5G Home",
        "networkParent": "Verizon",
        "techType": "5G Ultra Wideband FWA",
        "downloadMinMbps": 85,
        "downloadMaxMbps": 300,
        "uploadMinMbps": 10,
        "uploadMaxMbps": 50,
        "monthlyCost": 35.00,
        "equipmentFee": 0.00,
        "contractTermMonths": 0,
        "badgeColor": "#CD040B",
        "isSatellite": false,
        "signupUrl": "https://www.verizon.com/home/internet/5g",
        "features": ["Price guarantee 2-3 years", "Verizon mobile bundle discount", "Verizon Gateway included"]
      },
      {
        "id": "straight-talk-home",
        "brandName": "Straight Talk Home Internet",
        "networkParent": "Verizon",
        "techType": "5G Fixed Wireless",
        "downloadMinMbps": 25,
        "downloadMaxMbps": 100,
        "uploadMinMbps": 5,
        "uploadMaxMbps": 10,
        "monthlyCost": 45.00,
        "equipmentFee": 99.00,
        "contractTermMonths": 0,
        "badgeColor": "#007A3D",
        "isSatellite": false,
        "signupUrl": "https://www.straighttalk.com/5g-home-internet",
        "features": ["No credit check", "Walmart exclusive refill cards", "Prepaid 30-day plan"]
      },
      {
        "id": "total-wireless-home",
        "brandName": "Total Wireless Home Internet",
        "networkParent": "Verizon",
        "techType": "5G Fixed Wireless",
        "downloadMinMbps": 25,
        "downloadMaxMbps": 100,
        "uploadMinMbps": 5,
        "uploadMaxMbps": 10,
        "monthlyCost": 45.00,
        "equipmentFee": 99.00,
        "contractTermMonths": 0,
        "badgeColor": "#002B49",
        "isSatellite": false,
        "signupUrl": "https://www.totalwireless.com/home-internet",
        "features": ["No contract", "Unlimited data on Verizon 5G network"]
      },
      {
        "id": "att-internet-air",
        "brandName": "AT&T Internet Air",
        "networkParent": "AT&T",
        "techType": "5G Fixed Wireless",
        "downloadMinMbps": 75,
        "downloadMaxMbps": 225,
        "uploadMinMbps": 10,
        "uploadMaxMbps": 25,
        "monthlyCost": 60.00,
        "equipmentFee": 0.00,
        "contractTermMonths": 0,
        "badgeColor": "#00A8E0",
        "isSatellite": false,
        "signupUrl": "https://www.att.com/internet/internet-air",
        "features": ["AT&T All-Fi Hub included", "Self-install in 15 mins", "No equipment fee"]
      }
    ]
  }
}
```

### 6.2 Rural Satellite-Only Fixture (`tests/e2e/fixtures/rural-satellite-only.json`)

```json
{
  "geocoded": {
    "formatted": "Route 1 Box 42, Big Piney, WY 83113",
    "street_number": "Route 1",
    "street_name": "Box 42",
    "city": "Big Piney",
    "state": "WY",
    "zip5": "83113",
    "lat": 42.5416,
    "lng": -110.1118
  },
  "availability": {
    "address": "Route 1 Box 42, Big Piney, WY 83113",
    "coordinates": { "lat": 42.5416, "lng": -110.1118 },
    "totalProviders": 1,
    "hasTerrestrial5G": false,
    "fallbackNotice": "No terrestrial 5G Home Internet available at this address. Showing best alternative wireless & satellite broadband:",
    "providers": [
      {
        "id": "starlink-standard",
        "brandName": "Starlink",
        "networkParent": "SpaceX",
        "techType": "Satellite",
        "downloadMinMbps": 50,
        "downloadMaxMbps": 220,
        "uploadMinMbps": 10,
        "uploadMaxMbps": 25,
        "monthlyCost": 120.00,
        "equipmentFee": 599.00,
        "contractTermMonths": 0,
        "badgeColor": "#1C1C1E",
        "isSatellite": true,
        "latencyRangeMs": "25-50ms",
        "signupUrl": "https://www.starlink.com",
        "features": [
          "Global satellite coverage",
          "Self-orienting antenna kit",
          "Low-Earth Orbit low latency",
          "No long-term contract"
        ]
      }
    ]
  }
}
```

---

## 7. Verification & Test Execution Commands

### 7.1 Vitest Unit & Integration Suites
```bash
# Run all Vitest unit and integration tests
npx vitest run

# Run with test coverage analysis
npx vitest run --coverage

# Run specific suite (e.g. brand mapping)
npx vitest run tests/unit/engine/brand-mapper.test.ts

# Watch mode during development
npx vitest
```

### 7.2 Playwright E2E Suite
```bash
# Install Playwright browsers (if not installed)
npx playwright install --with-deps

# Run all E2E test journeys headlessly
npx playwright test

# Run specific E2E journey
npx playwright test tests/e2e/01-urban-multi-provider.spec.ts

# Run with interactive UI mode
npx playwright test --ui

# Run across specific browser
npx playwright test --project=chromium
```

### 7.3 Acceptance Criteria Verification Matrix

| Acceptance Criteria Item | Target Test File | Verification Command |
| :--- | :--- | :--- |
| **Address Autocomplete (zero-cost)** | `tests/unit/geocoding/photon-geocoder.test.ts`<br>`tests/e2e/01-urban-multi-provider.spec.ts` | `npx vitest run tests/unit/geocoding` |
| **Address Normalization (`street_number`, `lat`, `lng`)** | `tests/unit/geocoding/address-normalizer.test.ts` | `npx vitest run tests/unit/geocoding/address-normalizer.test.ts` |
| **T-Mobile vs Metro Brand Separation** | `tests/unit/engine/brand-mapper.test.ts`<br>`tests/e2e/01-urban-multi-provider.spec.ts` | `npx vitest run tests/unit/engine/brand-mapper.test.ts` |
| **Verizon vs Straight Talk vs Total Wireless** | `tests/unit/engine/brand-mapper.test.ts`<br>`tests/e2e/01-urban-multi-provider.spec.ts` | `npx vitest run tests/unit/engine/brand-mapper.test.ts` |
| **Rural Starlink Satellite Fallback** | `tests/unit/engine/brand-mapper.test.ts`<br>`tests/e2e/03-rural-satellite-only.spec.ts` | `npx playwright test tests/e2e/03-rural-satellite-only.spec.ts` |
| **1.5s Provider Timeout & FCC Fallback** | `tests/unit/engine/timeout-fallback.test.ts` | `npx vitest run tests/unit/engine/timeout-fallback.test.ts` |
| **Endpoint `/api/availability` < 2s Response** | `tests/integration/api-availability.test.ts` | `npx vitest run tests/integration/api-availability.test.ts` |
| **Comparison UI Filters & Sort Controls** | `tests/e2e/01-urban-multi-provider.spec.ts` | `npx playwright test tests/e2e/01-urban-multi-provider.spec.ts` |
| **Invalid Address & Error Handling** | `tests/e2e/04-invalid-address-edge-cases.spec.ts` | `npx playwright test tests/e2e/04-invalid-address-edge-cases.spec.ts` |

---

## 8. Invalidation Conditions & Caveats

1. **Carrier API Rate Limits**: Tests must not rely on live production carrier endpoints for automated runs. All CI/CD and automated test runs must use MSW / fixture interception. Any test making live HTTP requests to Verizon/T-Mobile portals will fail due to anti-bot CAPTCHAs and is deemed invalid.
2. **Census Geocoder SLA**: The public US Census Geocoder occasionally experiences latency spikes >3 seconds. Unit tests must use recorded JSON fixtures; integration tests must verify the automatic fallback to Photon/Nominatim.
3. **Database Concurrency in SQLite**: SQLite operates with file-level or database-level write locks. In-memory databases (`:memory:`) or WAL-mode SQLite databases must be utilized during tests to avoid `SQLITE_BUSY` errors during concurrent test execution.
4. **App Router Hydration**: E2E tests must verify client-side hydration completes (`waitForLoadState('networkidle')` or specific data-testid presence) prior to executing click and sort assertions.
