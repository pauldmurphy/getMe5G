# Project: 5G Home Internet Availability & Arbitrage Engine

## Architecture
The 5G Arbitrage Engine evaluates broadband coverage at any US address, distinguishing between distinct retail consumer brands operating on shared network operator infrastructure (e.g., T-Mobile vs. Metro; Verizon vs. Straight Talk vs. Total Wireless; AT&T Internet Air; Starlink).

### High-Level Architecture & Data Flow
```
User Query (Address)
       │
       ▼
[Address Intake / Geocoding Service]
   ├── Komoot Photon (Search-as-you-type autocomplete)
   ├── US Census Bureau Geocoder (Granular postal normalization & rooftop coords)
   ├── OSM Nominatim (Secondary open fallback)
   └── Google Places / Mapbox (Optional commercial env drop-in)
       │
       ▼
   NormalizedAddress (street_number, street_name, city, state, zip5, lat, lng)
       │
       ▼
[Availability Resolution Pipeline]
   ├── L1 Memory Cache (LRU cache, sub-5ms)
   ├── L2 SQLite Coordinate Cache (Spatial rounded coords ~11m, sub-25ms)
   │
   └── If Cache Miss:
         ├── FCC BDC Data Loader (Fixed wireless tech codes 71, 72, 70, 61)
         │
         ├── Concurrent Provider Checkers (IProviderChecker[])
         │     ├── T-Mobile Checker (Max 1.5s timeout, AbortSignal)
         │     ├── Verizon Checker (Max 1.5s timeout, AbortSignal)
         │     ├── AT&T Checker (Max 1.5s timeout, AbortSignal)
         │     └── Starlink Checker (LEO Satellite universal fallback)
         │           │
         │           └── On Timeout / 429: Fallback to FCC BDC data
         │
         └── Brand-Level Resolution & Arbitrage Engine
               ├── T-Mobile -> T-Mobile 5G Home (Postpaid) + Metro (Prepaid)
               ├── Verizon -> Verizon 5G Home (Postpaid) + Straight Talk + Total Wireless (Prepaid)
               ├── AT&T -> AT&T Internet Air
               └── Starlink -> Starlink Residential
                     │
                     ▼
         [SQLite / Drizzle ORM Catalog]
         (Fetch rich brand metadata, pricing tiers, speeds, equipment costs, signup URLs)
                     │
                     ▼
         Save to L1 & L2 Cache
                     │
                     ▼
[UI / API Response Layer]
   ├── GET /api/availability?address=... (HTTP 200 JSON < 2.0s SLA)
   └── Next.js App Router UI
         ├── Search & Autocomplete Input
         ├── Availability & Confirmation Header
         ├── Dynamic Filter & Sort Controls (Price, Speed, Network, Prepaid/Postpaid)
         ├── Comparison Grid Cards (Brand badge, price, speed, equipment fees, sign-up CTA)
         └── Satellite-Only Fallback Messaging (Rural unserved detection)
```

---

## Feature Inventory
Every feature identified during the Survey phase is mapped to a designated milestone below:

| # | Feature | Description | Milestone | Source |
|---|---|---|---|---|
| 1 | Next.js & App Setup | Next.js 14/15 App Router, TypeScript, Tailwind CSS, shadcn/ui, package.json | M1 | Survey (explorer_1) |
| 2 | US Census Bureau Geocoder | Zero-config, keyless REST geocoder for US addresses returning coords & postal components | M1 | Survey (spec_miner_2) |
| 3 | Komoot Photon Autocomplete | Free GeoJSON autocomplete API with US bounding box filtering for search-as-you-type | M1 | Survey (spec_miner_2) |
| 4 | OSM Nominatim Fallback | Open fallback geocoder with User-Agent compliance | M1 | Survey (spec_miner_2) |
| 5 | Postal Component Normalizer | Parses raw geocode data into standardized `NormalizedAddress` (street_number, street_name, city, state, zip5, lat, lng) | M1 | Survey (spec_miner_2) |
| 6 | Google Places / Mapbox Adapters | Drop-in commercial geocoding adapters activated via environment variables | M1 | Survey (spec_miner_2) |
| 7 | Geocoding API Routes | `/api/geocode/suggest` and `/api/geocode/resolve` internal proxy routes | M1 | Survey (spec_miner_2) |
| 8 | Drizzle ORM SQLite Schema | Tables for `brands`, `plans`, `fcc_provider_mapping`, `coordinate_lookup_cache` | M2 | Survey (spec_miner_2) |
| 9 | Brand & Plan Catalog Seeding | Pre-seeded database with rich retail metadata (pricing, speeds, equipment, signup links) | M2 | Survey (spec_miner_2) |
| 10 | L1 In-Memory LRU Cache | High-speed in-memory cache for exact address lookups (<5ms) | M2 | Survey (spec_miner_2) |
| 11 | L2 SQLite Coordinate Cache | Spatial coordinate cache (4-decimal rounding ~11m) with configurable TTL (<25ms) | M2 | Survey (spec_miner_2) |
| 12 | FCC BDC Fixed Data Store | Location-level FCC BDC data mapping for fixed wireless (71, 72, 70) and LEO satellite (61) | M3 | Survey (spec_miner_2) |
| 13 | Modular `IProviderChecker` Contract | Pluggable interface for carrier checks with strict 1.5s timeout via AbortController | M3 | Survey (spec_miner_2) |
| 14 | T-Mobile Dual-Brand Resolution | Maps T-Mobile footprint into T-Mobile 5G Home ($50-$60) and Metro by T-Mobile ($40-$50) | M3 | Survey (spec_miner_2) |
| 15 | Verizon Triple-Brand Resolution | Maps Verizon footprint into Verizon 5G Home, Straight Talk ($45), and Total Wireless ($45) | M3 | Survey (spec_miner_2) |
| 16 | AT&T Internet Air Resolution | Maps AT&T footprint into AT&T Internet Air ($60 or $35 bundled) | M3 | Survey (spec_miner_2) |
| 17 | Starlink Universal Satellite | Universal baseline satellite availability ($120/mo, kit purchase) with status badge | M3 | Survey (spec_miner_2) |
| 18 | Resilient Fallback to FCC Data | Catches timeouts/429 throttling and seamlessly falls back to FCC BDC data without 500 error | M3 | Survey (spec_miner_2) |
| 19 | Availability REST API | `GET /api/availability?address=...` returning structured JSON in <2 seconds | M4 | Survey (spec_miner_2) |
| 20 | Interactive Search & Autocomplete UI | Search bar with debounced suggestions, ARIA combobox, and loading states | M4 | Survey (spec_miner_2) |
| 21 | Comparison Report Grid Cards | Responsive cards with brand badges, network parent, prices, speeds, equipment upfront fees, and outbound URLs | M4 | Survey (spec_miner_2) |
| 22 | Dynamic Filter & Sort Controls | Filtering by network, account type (prepaid/postpaid), price limit, and sorting by price/speed | M4 | Survey (spec_miner_2) |
| 23 | Satellite & Unserved Fallback View | Empathetic messaging and Starlink focus banner for rural addresses without 5G FWA | M4 | Survey (spec_miner_2) |
| 24 | Vitest Unit & Integration Suites | Testing address normalization, FCC BDC parsing/brand mapping, Drizzle caching, 1.5s timeout | M5 | Survey (explorer_3) |
| 25 | Playwright E2E User Journeys | 4 required fixture journeys (Urban multi-provider, Suburban single-carrier, Rural satellite-only, Invalid address) | M5 | Survey (explorer_3) |
| 26 | Adversarial Coverage Hardening | White-box stress testing, boundary condition verification, and 100% test pass rate | M5 | Survey (explorer_3) |

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Address Intake & Pluggable Geocoding System (R1) | Project scaffolding, Next.js, TS, Tailwind, shadcn setup, Census Geocoder, Komoot Photon, OSM Nominatim, Google/Mapbox adapters, AddressNormalizer, `/api/geocode/*` routes | None | DONE |
| M2 | Provider Catalog & Multi-Tier Caching (R3) | Drizzle ORM SQLite schema, catalog seeds (all 7 brands & plans), L1 LRU memory cache, L2 coordinate cache | None | PLANNED |
| M3 | Hybrid Availability Engine & Brand Resolution (R2) | FCC BDC data loader, `IProviderChecker` implementations, 1.5s timeout enforcement, resilient fallback, multi-brand arbitrage mapper | M1, M2 | PLANNED |
| M4 | Availability API & Comparison UI (R4) | `GET /api/availability`, Search Bar, Results Header, Comparison Grid Cards, Filter/Sort Bar, Satellite Fallback Banner | M3 | PLANNED |
| M5 | E2E Testing Track Pass & Coverage Hardening | Full Vitest test suite execution, Playwright test suite execution on 4 mock fixtures, Tier 1-4 100% pass, Tier 5 adversarial coverage hardening | M4 | PLANNED |

---

## Interface Contracts

### 1. Geocoder ↔ Normalizer Contract (`src/lib/geocoding/types.ts`)
```typescript
export interface NormalizedAddress {
  streetNumber: string;
  streetName: string;
  unitNumber?: string;
  city: string;
  state: string; // 2-letter uppercase USPS code
  zip5: string;
  lat: number;
  lng: number;
  formattedAddress: string;
}

export interface AddressSuggestion {
  id: string;
  label: string;
  streetLine: string;
  city: string;
  state: string;
  zip5?: string;
  lat?: number;
  lng?: number;
  source: 'photon' | 'census' | 'nominatim' | 'google' | 'mapbox';
}

export interface IGeocoderService {
  readonly providerName: string;
  suggest(query: string, limit?: number): Promise<AddressSuggestion[]>;
  resolve(address: string): Promise<NormalizedAddress>;
  resolveCoordinates(lat: number, lng: number): Promise<NormalizedAddress>;
}
```

### 2. Provider Checkers ↔ Availability Engine (`src/lib/engine/types.ts`)
```typescript
export interface ProviderCheckInput {
  address: NormalizedAddress;
  timeoutMs?: number; // Default 1500ms
  fccCoverageHint?: {
    hasTmobile: boolean;
    hasVerizon: boolean;
    hasAtt: boolean;
    hasSatellite: boolean;
  };
}

export interface ProviderCheckResult {
  brandId: string;
  brandName: string;
  networkOperator: 'T-Mobile' | 'Verizon' | 'AT&T' | 'Starlink';
  technologyType: '5G_FWA' | 'CBRS' | 'SATELLITE_LEO';
  status: 'available' | 'waitlist' | 'unavailable' | 'fallback_available';
  confidence: 'verified_live' | 'fcc_bdc_fallback' | 'satellite_universal';
  source: 'live_preflight' | 'fcc_bdc' | 'cached';
  speeds: {
    downloadMinMbps: number;
    downloadMaxMbps: number;
    uploadMinMbps: number;
    uploadMaxMbps: number;
    displaySpeed: string;
  };
  pricing: {
    startingMonthlyPrice: number;
    autopayDiscountPrice?: number;
    bundledMobilePrice?: number | null;
    equipmentUpfrontCost: number;
    equipmentMonthlyFee: number;
    contractTerms: string;
    priceLockGuarantee?: string | null;
    creditCheckRequired: boolean;
  };
  keyFeatures: string[];
  arbitrageNotes: string;
  officialSignupUrl: string;
}

export interface IProviderChecker {
  readonly checkerName: string;
  readonly supportedBrands: string[];
  check(input: ProviderCheckInput, signal?: AbortSignal): Promise<ProviderCheckResult[]>;
}
```

### 3. Catalog & Cache Contracts (`src/lib/db/types.ts`)
```typescript
export interface BrandRecord {
  id: string; // e.g. "t-mobile-5g-home", "metro-by-t-mobile"
  name: string;
  slug: string;
  networkOperator: string;
  tierType: 'prepaid' | 'postpaid' | 'satellite';
  logoUrl?: string;
  creditCheckRequired: boolean;
  officialSignupUrl: string;
}

export interface CoordinateCacheEntry {
  cacheKey: string; // "lat.toFixed(4):lng.toFixed(4)"
  addressJson: string;
  resultsJson: string;
  createdAt: number;
  expiresAt: number;
}
```

### 4. Availability API Contract (`GET /api/availability`)
```typescript
export interface AvailabilityApiResponse {
  status: 'success' | 'error';
  query: {
    submittedAddress: string;
    resolvedAddress: NormalizedAddress;
  };
  summary: {
    totalProvidersAvailable: number;
    lowestMonthlyPrice: number;
    maxDownloadSpeedMbps: number;
    hasTerrestrial5G: boolean;
    hasSatelliteOnly: boolean;
    primaryRecommendationBrandId: string;
  };
  telemetry: {
    responseTimeMs: number;
    cacheHit: boolean;
    cacheLayer?: 'l1_memory' | 'l2_db' | 'none';
    carrierCheckStatus: Record<string, 'live_success' | 'fcc_fallback' | 'timeout' | 'error'>;
  };
  providers: ProviderCheckResult[];
}
```

---

## Code Layout

```
.
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── globals.css
│   │   └── api/
│   │       ├── geocode/
│   │       │   ├── suggest/route.ts
│   │       │   └── resolve/route.ts
│   │       └── availability/route.ts
│   ├── components/
│   │   ├── ui/ (Button, Input, Card, Badge, Tabs, Select, Skeleton, etc.)
│   │   ├── AddressSearchBar.tsx
│   │   ├── AvailabilityHeader.tsx
│   │   ├── FilterAndSortBar.tsx
│   │   ├── ProviderCard.tsx
│   │   ├── SatelliteFallbackBanner.tsx
│   │   └── ComparisonTable.tsx
│   └── lib/
│       ├── geocoding/
│       │   ├── types.ts
│       │   ├── normalizer.ts
│       │   ├── census-geocoder.ts
│       │   ├── photon-geocoder.ts
│       │   ├── nominatim-geocoder.ts
│       │   ├── google-geocoder.ts
│       │   ├── mapbox-geocoder.ts
│       │   └── service.ts
│       ├── db/
│       │   ├── schema.ts
│       │   ├── index.ts
│       │   ├── seed.ts
│       │   └── cache.ts
│       ├── engine/
│       │   ├── types.ts
│       │   ├── fcc-bdc-store.ts
│       │   ├── brand-mapper.ts
│       │   ├── checkers/
│       │   │   ├── tmobile-checker.ts
│       │   │   ├── verizon-checker.ts
│       │   │   ├── att-checker.ts
│       │   │   └── starlink-checker.ts
│       │   └── availability-engine.ts
│       └── utils.ts
├── tests/
│   ├── setup.ts
│   ├── fixtures/
│   │   ├── addresses.json
│   │   └── fcc-records.json
│   ├── unit/
│   │   ├── geocoding/
│   │   │   └── normalizer.test.ts
│   │   ├── db/
│   │   │   └── cache.test.ts
│   │   └── engine/
│   │       ├── brand-mapper.test.ts
│   │       └── timeout-fallback.test.ts
│   └── e2e/
│       ├── fixtures/
│       ├── page-objects/
│       └── journeys.spec.ts
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── postcss.config.mjs
├── drizzle.config.ts
├── vitest.config.ts
└── playwright.config.ts
```
