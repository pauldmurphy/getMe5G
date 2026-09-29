# Technical Specification & Data Contracts: 5G Home Internet Arbitrage & Availability Engine

**Author**: `spec_miner_survey_2`  
**Working Directory**: `.agents/teamwork/spec_miner_survey_2`  
**Date**: 2026-09-29  
**Status**: Authoritative Technical Specification  
**Reference Document**: `ORIGINAL_REQUEST.md`

---

## 1. Executive Summary & Architecture Overview

The **5G Arbitrage Engine** is a high-performance web application designed to evaluate broadband availability at any US street address, specifically distinguishing between distinct retail consumer brands operating over the same physical mobile network operator (MNO) infrastructure (e.g. T-Mobile vs. Metro by T-Mobile; Verizon vs. Straight Talk vs. Total Wireless).

The system consists of four primary technical subsystems:
1. **R1: Address Intake & Pluggable Geocoding System** — Open zero-config geocoding cascading to US Census Bureau and OpenStreetMap (Photon/Nominatim), with drop-in Google Places and Mapbox adapters.
2. **R2: Hybrid Availability & Brand-Level Resolution Engine** — Concurrently executes modular provider pre-flight checks (`IProviderChecker`) with hard 1.5-second timeouts and automatic fallback to FCC Broadband Data Collection (BDC) fixed wireless dataset.
3. **R3: Provider Catalog & Multi-Tier Cache Layer** — SQLite relational database managed via Drizzle ORM storing retail brands, plan tiers, equipment policies, and outbound links, combined with an in-memory L1 LRU cache and L2 SQLite coordinate cache.
4. **R4: Interactive Availability & Comparison UI & REST API** — A Next.js App Router UI and `GET /api/availability` endpoint delivering structured availability reports in under 2 seconds.

---

## 2. R1: Address Intake & Pluggable Geocoding System

### 2.1. Open Zero-Config Endpoints Specification

The system requires no mandatory paid API keys. Out of the box, address ingestion and geocoding operate through a cascade of free, public US government and open-source geocoders.

#### Endpoint 1: US Census Bureau Geocoding Services API (Primary US Geocoder)
- **Base URL**: `https://geocoding.geo.census.gov/geocoder/locations/onelineaddress`
- **Method**: `GET`
- **Authentication**: None (Open Public Service)
- **Protocol Requirements**: HTTP/1.1 or HTTP/2, standard user-agent. (Note: Census Geocoder does not send permissive browser CORS headers; all browser calls must route through the Next.js internal API proxy `/api/geocode`).
- **Query Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `address` | string | Yes | — | Full one-line US address string (URL encoded) |
  | `benchmark` | string | Yes | `Public_AR_Current` | Address locator database vintage |
  | `format` | string | Yes | `json` | Output response format |

- **Authoritative JSON Response Schema**:
  ```json
  {
    "result": {
      "input": {
        "address": {
          "address": "1600 Pennsylvania Ave NW, Washington, DC 20500"
        },
        "benchmark": {
          "id": "4",
          "benchmarkName": "Public_AR_Current",
          "benchmarkDescription": "Public Address Ranges - Current Benchmark",
          "isDefault": false
        }
      },
      "addressMatches": [
        {
          "tigerLine": {
            "tigerLineId": "76225345",
            "side": "L"
          },
          "coordinates": {
            "x": -77.03653,
            "y": 38.897675
          },
          "addressComponents": {
            "zip": "20500",
            "streetName": "PENNSYLVANIA",
            "preType": "",
            "city": "WASHINGTON",
            "preDirection": "",
            "suffixDirection": "NW",
            "fromAddress": "1600",
            "toAddress": "1698",
            "state": "DC",
            "suffixType": "AVE",
            "preQualifier": "",
            "suffixQualifier": ""
          },
          "matchedAddress": "1600 PENNSYLVANIA AVE NW, WASHINGTON, DC, 20500"
        }
      ]
    }
  }
  ```
- **Coordinate Mapping Note**: In Census Geocoder, `coordinates.x` is **Longitude** (negative for US) and `coordinates.y` is **Latitude**.

#### Endpoint 2: Komoot Photon API (Primary Zero-Config Autocomplete & Search)
- **Base URL**: `https://photon.komoot.io/api`
- **Method**: `GET`
- **Authentication**: None (Free OSM-based geocoder)
- **Query Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `q` | string | Yes | — | Partial or full address input query |
  | `limit` | integer | No | `5` | Maximum suggestions returned (1-10) |
  | `bbox` | string | No | `-125,24,-66,49` | Continental US bounding box filter `[minLon,minLat,maxLon,maxLat]` |
  | `lang` | string | No | `en` | Result language code |
  | `lat` / `lon` | float | No | — | Optional user location coordinates for proximity bias |

- **Authoritative JSON Response Schema (GeoJSON FeatureCollection)**:
  ```json
  {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "geometry": {
          "type": "Point",
          "coordinates": [-77.03653, 38.897675]
        },
        "properties": {
          "osm_id": 2382442,
          "osm_type": "W",
          "osm_key": "building",
          "osm_value": "yes",
          "name": "White House",
          "housenumber": "1600",
          "street": "Pennsylvania Avenue Northwest",
          "postcode": "20500",
          "city": "Washington",
          "state": "District of Columbia",
          "country": "United States",
          "countrycode": "US",
          "extent": [-77.0368, 38.8974, -77.0362, 38.8979]
        }
      }
    ]
  }
  ```

#### Endpoint 3: OpenStreetMap Nominatim API (Secondary Zero-Config Fallback)
- **Base URL**: `https://nominatim.openstreetmap.org/search`
- **Method**: `GET`
- **Authentication**: None (Strict User-Agent header required by OSM Usage Policy)
- **Required Header**: `User-Agent: GetMe5G-ArbitrageEngine/1.0 (contact@getme5g.local)`
- **Query Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `q` | string | Yes | — | Free-form address string |
  | `format` | string | Yes | `jsonv2` | Output format |
  | `addressdetails` | integer | Yes | `1` | Include decomposed address breakdown |
  | `countrycodes` | string | No | `us` | Limit results to United States |
  | `limit` | integer | No | `5` | Maximum number of results |

- **Authoritative JSON Response Schema**:
  ```json
  [
    {
      "place_id": 312891921,
      "licence": "Data © OpenStreetMap contributors, ODbL 1.0. https://osm.org/copyright",
      "osm_type": "way",
      "osm_id": 2382442,
      "lat": "38.897675",
      "lon": "-77.036530",
      "category": "building",
      "type": "yes",
      "place_rank": 30,
      "importance": 0.85,
      "addresstype": "building",
      "name": "The White House",
      "display_name": "1600, Pennsylvania Avenue Northwest, Downtown, Washington, District of Columbia, 20500, United States",
      "address": {
        "house_number": "1600",
        "road": "Pennsylvania Avenue Northwest",
        "suburb": "Downtown",
        "city": "Washington",
        "state": "District of Columbia",
        "ISO3166-2-lvl4": "US-DC",
        "postcode": "20500",
        "country": "United States",
        "country_code": "us"
      }
    }
  ]
  ```

---

### 2.2. Postal Component Normalization Schema

All geocoding adapters must map raw vendor outputs into a single, uniform TypeScript interface: `NormalizedAddress`.

```typescript
export interface NormalizedAddress {
  /** House / building number (e.g. "1600", "742") */
  streetNumber: string;

  /** Primary street name and suffix (e.g. "Pennsylvania Ave NW", "Evergreen Terrace") */
  streetName: string;

  /** Secondary unit / apartment / suite number if present, otherwise null */
  unitNumber: string | null;

  /** Incorporated city, town, or postal locality */
  city: string;

  /** Standardized 2-letter uppercase US postal state abbreviation (e.g. "DC", "CA", "NY") */
  state: string;

  /** 5-digit US ZIP code */
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
  geocoderSource: 'census' | 'photon' | 'nominatim' | 'google' | 'mapbox';

  /** Quality / match confidence score between 0.0 (low) and 1.0 (exact rooftop) */
  confidenceScore: number;
}
```

#### State Abbreviation Normalization Dictionary
If a geocoder returns full state names (e.g., "District of Columbia" or "California"), the normalization layer maps to ISO 3166-2 two-letter codes:
```typescript
export const US_STATE_CODE_MAP: Record<string, string> = {
  'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR', 'california': 'CA',
  'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE', 'district of columbia': 'DC',
  'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID', 'illinois': 'IL',
  'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS', 'kentucky': 'KY', 'louisiana': 'LA',
  'maine': 'ME', 'maryland': 'MD', 'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN',
  'mississippi': 'MS', 'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV',
  'new hampshire': 'NH', 'new jersey': 'NJ', 'new mexico': 'NM', 'new york': 'NY',
  'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK', 'oregon': 'OR',
  'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC', 'south dakota': 'SD',
  'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT', 'vermont': 'VT', 'virginia': 'VA',
  'washington': 'WA', 'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY',
  'puerto rico': 'PR', 'guam': 'GU', 'virgin islands': 'VI'
};
```

---

### 2.3. Pluggable Geocoder Architecture (`IGeocoderService`)

```typescript
export interface AddressSuggestion {
  id: string;
  primaryText: string;     // e.g. "1600 Pennsylvania Ave NW"
  secondaryText: string;   // e.g. "Washington, DC 20500"
  fullText: string;        // e.g. "1600 Pennsylvania Ave NW, Washington, DC 20500"
  provider: 'photon' | 'google' | 'mapbox' | 'nominatim';
}

export interface IGeocoderService {
  readonly providerName: string;
  readonly isConfigured: boolean;

  suggest(query: string, signal?: AbortSignal): Promise<AddressSuggestion[]>;
  geocode(address: string, signal?: AbortSignal): Promise<NormalizedAddress>;
}
```

#### Cascade Execution Pipeline:
1. **Autocomplete Suggestions**:
   - If `GOOGLE_PLACES_API_KEY` is set $\rightarrow$ Call Google Places Autocomplete API.
   - Else if `MAPBOX_ACCESS_TOKEN` is set $\rightarrow$ Call Mapbox Search JS forward geocode.
   - Default (Zero-Config) $\rightarrow$ Call Komoot Photon `/api?q=...&bbox=-125,24,-66,49&limit=5`.
2. **Address Resolution & Coordinate Geocoding**:
   - Step 1: If Google/Mapbox configured, attempt resolution.
   - Step 2: Open Cascade Default:
     - Primary: US Census Bureau Geocoder (`/locations/onelineaddress`).
     - If Census Geocoder returns 0 matches or times out (2.5s) $\rightarrow$ Photon `/api`.
     - If Photon fails $\rightarrow$ OpenStreetMap Nominatim `/search`.
   - Step 3: Run address components through postal normalizer and coordinate boundary checks.

---

### 2.4. Drop-In Commercial Geocoder Configurations

#### Google Places / Geocoding API
- **Environment Variables**:
  - `GOOGLE_PLACES_API_KEY`: API Key with Geocoding and Places API enabled.
- **Autocomplete Endpoint**: `https://maps.googleapis.com/maps/api/place/autocomplete/json?input={query}&components=country:us&types=address&key={key}`
- **Geocode Endpoint**: `https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={key}`

#### Mapbox Geocoding API
- **Environment Variables**:
  - `MAPBOX_ACCESS_TOKEN`: Mapbox public or secret access token (`pk.ey...`).
- **Endpoint**: `https://api.mapbox.com/search/geocode/v6/forward?q={query}&country=us&types=address&access_token={token}`

---

## 3. R2: Hybrid Provider Availability & Brand-Level Resolution Engine

### 3.1. FCC Broadband Data Collection (BDC) Specifications

The FCC National Broadband Map and BDC system record fixed broadband availability submitted biannually by telecommunications carriers.

#### BDC Fixed Technology Codes
| Technology Code | Classification | Description | Typical Use in 5G Arbitrage Engine |
|---|---|---|---|
| **71** | Licensed Terrestrial Fixed Wireless | Fixed broadband over exclusive licensed spectrum (e.g. 5G Ultra Capacity n41, C-Band n77, mmWave n260/n261, CBRS PAL). | **Primary target** for MNO 5G Home Internet (T-Mobile, Verizon, AT&T Air). |
| **72** | Licensed-by-Rule Terrestrial Fixed Wireless | Fixed broadband over shared spectrum frameworks (e.g., CBRS Band 48 GAA). | Secondary 5G/LTE fixed wireless coverage. |
| **70** | Unlicensed Terrestrial Fixed Wireless | Fixed broadband over 900MHz, 2.4GHz, 5GHz, 6GHz, or 60GHz unlicensed spectrum (WISPs). | Third-party terrestrial wireless. |
| **61** | Non-Geostationary Satellite (NGSO) | Low-Earth Orbit (LEO) satellite broadband (e.g. SpaceX Starlink). | **Universal alternative** for unserved/rural areas. |
| **60** | Geostationary Satellite (GEO) | High-Earth Orbit satellite broadband (Viasat, HughesNet). | High-latency satellite baseline. |
| **50** | Optical Carrier / Fiber to the Home | Wireline optical fiber (FTTH). | Wireline comparison marker. |
| **40** | Coaxial Cable / HFC | DOCSIS 3.1/4.0 hybrid fiber-coax cable. | Wireline comparison marker. |

#### FCC BDC Data Record Schema (Location-Level Availability)
```typescript
export interface FccBdcRecord {
  /** FCC Registration Number (10 digits) */
  frn: string;

  /** Unique 6-digit FCC Provider ID */
  providerId: number;

  /** Legal or advertised holding company name */
  brandName: string;

  /** BDC Fixed Technology Code (71 = Licensed Fixed Wireless, 61 = LEO Satellite, etc.) */
  technology: number;

  /** Maximum advertised downstream throughput in Mbps */
  maxAdvertisedDownloadSpeed: number;

  /** Maximum advertised upstream throughput in Mbps */
  maxAdvertisedUploadSpeed: number;

  /** 1 if provider certifies low latency (<100ms round trip), 0 otherwise */
  lowLatency: number;

  /** Offering code: 'R' (Residential), 'B' (Business), 'X' (Both) */
  businessResidentialCode: 'R' | 'B' | 'X';

  /** Broadband Serviceable Location Fabric ID */
  locationId?: string;

  /** Census 2020 15-digit Census Block FIPS Code */
  blockFips?: string;

  /** WGS84 Latitude and Longitude */
  latitude: number;
  longitude: number;
}
```

---

### 3.2. Distinct Retail Brand Resolution Matrix

Carriers often sell access to identical cell tower sectors under multiple consumer brand identities with drastically different price structures, equipment policies, and credit requirements. The Arbitrage Engine resolves single MNO coverage into distinct retail brand offerings:

```
+-----------------------------------------------------------------------------------------+
|                                    CARRIER INFRASTRUCTURE                               |
|                               (FCC BDC Technology 71 / MNO)                            |
+----------------------------+-----------------------------+------------------------------+
                             |                             |
             +---------------+--------------+              |
             |                              |              |
             v                              v              v
     +---------------+              +---------------+     +---------------+
     |   T-Mobile    |              |    Verizon    |     |     AT&T      |
     |  Network FWA  |              |  Network FWA  |     |  Network FWA  |
     +-------+-------+              +-------+-------+     +-------+-------+
             |                              |                     |
     +-------+-------+          +-----------+-----------+         v
     |               |          |           |           |  [AT&T Internet Air]
     v               v          v           v           v
[T-Mobile 5G]     [Metro]   [Verizon 5G] [Straight]  [Total]
[Home Internet]   [5G FWA]  [Home Int.]  [  Talk  ]  [Wireless]
```

#### Brand Resolution Rules Table:

| Brand Identifier | Retail Consumer Brand | Underlying MNO Network | Target Demographic & Arbitrage Model | Monthly Price Range | Upfront Equipment Cost | Credit Check Required | Speeds (Typical DL / UL) |
|---|---|---|---|---|---|---|---|
| `t-mobile-5g-home` | **T-Mobile 5G Home Internet** | T-Mobile | Postpaid consumer; discounts for T-Mobile mobile voice customers. | $50.00 - $60.00 / mo | $0.00 (Rental included) | Yes (Soft check) | 72 - 245 Mbps DL / 15 - 31 Mbps UL |
| `metro-by-t-mobile-5g` | **Metro by T-Mobile 5G Home** | T-Mobile | Prepaid consumer; no credit check, no contract; gateway purchase model. | $50.00 - $55.00 / mo | $49.00 - $99.00 (Promotional purchase) | No | 72 - 245 Mbps DL / 15 - 31 Mbps UL |
| `verizon-5g-home` | **Verizon 5G Home Internet** | Verizon | Postpaid consumer; steep discount with Verizon Unlimited Plus/Ultimate. | $60.00 - $80.00 / mo ($35 - $45 with mobile) | $0.00 (Rental included) | Yes (Soft check) | 85 - 300 Mbps DL (Up to 1,000 Mbps mmWave) / 10 - 50 Mbps UL |
| `straight-talk-home-internet` | **Straight Talk Home Internet** | Verizon (via TracFone) | Prepaid retail (Walmart exclusive partnership); fixed $45/mo flat pricing; speed-capped at 100 Mbps. | $45.00 / mo ($40 with autopay) | $99.00 (Router purchased at Walmart) | No | Up to 100 Mbps DL / Up to 10 Mbps UL |
| `total-wireless-home-internet` | **Total Wireless Home Internet** | Verizon (via TracFone) | Prepaid retail brand; $60 standalone or $35 bundled with Total Wireless Unlimited mobile plan. | $45.00 - $60.00 / mo ($35 bundled) | $99.00 (Router purchase or promo) | No | Up to 200 Mbps DL / Up to 15 Mbps UL |
| `att-internet-air` | **AT&T Internet Air** | AT&T | Fixed wireless offering replacing legacy DSL and expanding mid-band 5G footprint. | $60.00 / mo ($35 - $47 with mobile) | $0.00 (All-Fi Hub included) | Yes (Soft check) | 75 - 225 Mbps DL / 10 - 25 Mbps UL |
| `starlink-residential` | **Starlink Residential** | SpaceX | Non-geostationary low-latency satellite; universal coverage baseline across 100% of US geography. | $120.00 / mo ($90 in surplus areas) | $349.00 - $599.00 (Hardware kit) | No | 50 - 220 Mbps DL / 5 - 25 Mbps UL |

---

### 3.3. `IProviderChecker` Interface Contract & Fallback Protocol

```typescript
export type AvailabilityStatus =
  | 'available'             // Verified available for order
  | 'waitlist'              // Cell sector capacity constrained; waitlist open
  | 'unavailable'           // Not serviced or out of footprint
  | 'fallback_available'    // Carrier endpoint timed out or throttled; FCC BDC certifies coverage
  | 'unknown';

export type AvailabilityDataSource =
  | 'live_carrier'          // Verified directly via live carrier API
  | 'fcc_bdc_primary'       // Resolved via FCC Broadband Data Collection
  | 'fcc_bdc_fallback'      // Fallback activated after carrier timeout/throttle
  | 'satellite_universal';  // Universal LEO satellite coverage model

export interface ProviderCheckInput {
  address: NormalizedAddress;
  fccCoverageSummary: FccBdcRecord[];
  timeoutMs: number; // Maximum timeout allocated (default 1500ms)
}

export interface SpeedRange {
  downloadMinMbps: number;
  downloadMaxMbps: number;
  uploadMinMbps: number;
  uploadMaxMbps: number;
}

export interface ProviderCheckResult {
  brandId: string;
  brandName: string;
  networkOperator: 'T-Mobile' | 'Verizon' | 'AT&T' | 'Starlink' | 'Other';
  technologyType: '5G_FWA' | '4G_LTE' | 'SATELLITE_LEO' | 'SATELLITE_GEO';
  status: AvailabilityStatus;
  source: AvailabilityDataSource;
  latencyMs: number;
  speeds: SpeedRange;
  plans: string[]; // List of plan IDs available
  arbitrageNotes?: string;
  errorMessage?: string;
}

export interface IProviderChecker {
  readonly providerId: string;
  readonly supportedBrandIds: string[];
  readonly timeoutMs: number; // Strictly <= 1500ms

  /**
   * Executes pre-flight check against carrier or fallback database.
   * MUST respect signal and abort if timeoutMs is exceeded.
   */
  check(input: ProviderCheckInput, signal: AbortSignal): Promise<ProviderCheckResult[]>;
}
```

#### Resilient Timeout & Fallback Execution Logic
1. **Parallel Dispatch**: Orchestrator initiates checks across all registered providers via `Promise.allSettled`.
2. **Hard Timeout Enforcement**: Each provider checker wraps its network call with an `AbortController` set to abort at exactly `Math.min(input.timeoutMs, 1500)` milliseconds.
3. **Throttling / Error Interception**: If a carrier returns HTTP 429 (Too Many Requests), HTTP 403 (Cloudflare/Bot Block), network timeout, or socket hangup:
   - The checker does NOT throw or crash the request.
   - It intercepts the error, logs a diagnostic warning, and checks the pre-loaded `fccCoverageSummary`.
   - If the carrier's FCC Provider ID or FRN has a matching BDC record with `technology === 71` within the geocoded Census Block:
     - Sets `status = 'fallback_available'`
     - Sets `source = 'fcc_bdc_fallback'`
     - Derives speed ranges from the FCC record (`maxAdvertisedDownloadSpeed`, etc.).
   - If no FCC record is present:
     - Sets `status = 'unavailable'`.

---

## 4. R3: Provider Catalog & Local Cache Layer (SQLite + Drizzle ORM)

### 4.1. SQLite Schema Definition (Drizzle ORM)

The relational catalog and caching engine are persisted locally using SQLite via Drizzle ORM (`drizzle-orm/sqlite-core`).

```typescript
import { sqliteTable, text, integer, real } from 'drizzle-orm/sqlite-core';

/**
 * Retail consumer brands catalog
 */
export const brands = sqliteTable('brands', {
  id: text('id').primaryKey(), // e.g. 't-mobile-5g-home', 'metro-by-t-mobile-5g'
  name: text('name').notNull(),
  slug: text('slug').notNull().unique(),
  networkOperator: text('network_operator').notNull(), // 'T-Mobile', 'Verizon', 'AT&T', 'Starlink'
  parentCompany: text('parent_company').notNull(),
  technology: text('technology').notNull(), // '5G_FWA', 'SATELLITE_LEO', etc.
  tierType: text('tier_type').notNull(), // 'postpaid', 'prepaid', 'satellite'
  badgeColor: text('badge_color').notNull().default('blue'), // 'magenta', 'red', 'blue', 'slate'
  logoUrl: text('logo_url'),
  websiteUrl: text('website_url').notNull(),
  createdAt: integer('created_at', { mode: 'timestamp' }).notNull(),
});

/**
 * Plan tiers, pricing structures, equipment terms, and outbound URLs
 */
export const plans = sqliteTable('plans', {
  id: text('id').primaryKey(), // e.g. 't-mobile-home-standard', 'vz-5g-home-plus'
  brandId: text('brand_id').notNull().references(() => brands.id),
  planName: text('plan_name').notNull(),
  monthlyPriceRegular: real('monthly_price_regular').notNull(),
  monthlyPriceAutopay: real('monthly_price_autopay'),
  monthlyPriceBundled: real('monthly_price_bundled'),
  bundledRequirement: text('bundled_requirement'),
  downloadSpeedMin: integer('download_speed_min').notNull(), // Mbps
  downloadSpeedMax: integer('download_speed_max').notNull(), // Mbps
  uploadSpeedMin: integer('upload_speed_min').notNull(),     // Mbps
  uploadSpeedMax: integer('upload_speed_max').notNull(),     // Mbps
  dataCapGb: integer('data_cap_gb'), // null if unlimited
  isUnlimited: integer('is_unlimited', { mode: 'boolean' }).notNull().default(true),
  contractTermMonths: integer('contract_term_months').notNull().default(0),
  priceGuaranteeMonths: integer('price_guarantee_months'), // e.g. 24, 36
  equipmentFeeMonthly: real('equipment_fee_monthly').notNull().default(0.0),
  equipmentUpfrontCost: real('equipment_upfront_cost').notNull().default(0.0),
  equipmentPolicy: text('equipment_policy').notNull(),
  creditCheckRequired: integer('credit_check_required', { mode: 'boolean' }).notNull(),
  officialSignupUrl: text('official_signup_url').notNull(),
  promotionalDetails: text('promotional_details'),
});

/**
 * FCC Provider ID and FRN mapping to consumer retail brands
 */
export const fccProviderMapping = sqliteTable('fcc_provider_mapping', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  fccProviderId: integer('fcc_provider_id').notNull(),
  fccFrn: text('fcc_frn').notNull(),
  fccHoldingName: text('fcc_holding_name').notNull(),
  fccTechnology: integer('fcc_technology').notNull(),
  targetBrandId: text('target_brand_id').notNull().references(() => brands.id),
  isPrimaryBrand: integer('is_primary_brand', { mode: 'boolean' }).notNull().default(false),
});

/**
 * Coordinate lookup cache for fast repeat queries
 */
export const coordinateLookupCache = sqliteTable('coordinate_lookup_cache', {
  // Spatial hash: SHA-256 of rounded coordinates (e.g. `lat.toFixed(4) + ":" + lng.toFixed(4)`)
  cacheKey: text('cache_key').primaryKey(),
  latitudeRounded: real('latitude_rounded').notNull(),
  longitudeRounded: real('longitude_rounded').notNull(),
  normalizedAddressJson: text('normalized_address_json').notNull(),
  availabilityResultsJson: text('availability_results_json').notNull(),
  hitCount: integer('hit_count').notNull().default(1),
  cachedAt: integer('cached_at', { mode: 'timestamp' }).notNull(),
  expiresAt: integer('expires_at', { mode: 'timestamp' }).notNull(),
});
```

---

### 4.2. Multi-Tier Cache Layer Specification

```
Incoming Request -> [ L1 In-Memory LRU Cache ] -> HIT (< 5ms)
                            | MISS
                            v
                    [ L2 SQLite Coordinate Cache ] -> HIT (< 25ms)
                            | MISS
                            v
            [ L3 Hybrid Availability Engine ] (< 1800ms)
                    |
                    +--> Writes to L1 (Memory, 1h TTL)
                    +--> Writes to L2 (SQLite, 24h TTL)
```

1. **L1 In-Memory LRU Cache**:
   - Implemented via `lru-cache` package or custom high-speed doubly linked list map.
   - Capacity: Max 1,000 resolved query objects.
   - TTL: 3,600,000 ms (1 hour).
   - Key: Hash of normalized address string (`zip5 + ":" + streetNumber + ":" + streetName`).
   - Latency: $\le 5$ milliseconds.

2. **L2 SQLite Persistent Coordinate Cache**:
   - Stored in `coordinate_lookup_cache` table.
   - Spatial Key: `lat.toFixed(4) + ":" + lng.toFixed(4)` (4 decimal places provides ~11 meter accuracy, grouping adjoining parcels without false cross-cell contamination).
   - TTL: Configurable via `AVAILABILITY_CACHE_TTL_HOURS` environment variable (default: 24 hours).
   - Latency: $\le 25$ milliseconds.

---

## 5. R4: Interactive Availability & Comparison UI & REST API

### 5.1. `GET /api/availability` REST Endpoint Specification

- **Path**: `/api/availability`
- **Method**: `GET`
- **SLA**: $\le 2.0$ seconds total execution time on cold query; $\le 50$ milliseconds on cached repeat query.
- **Query Parameters**:
  | Parameter | Type | Required | Description |
  |---|---|---|---|
  | `address` | string | Yes | Raw input address or normalized address string |
  | `lat` | float | No | Latitude if pre-geocoded |
  | `lng` | float | No | Longitude if pre-geocoded |
  | `fresh` | boolean | No | If `true`, bypasses L1/L2 cache (default `false`) |

- **HTTP Status Codes**:
  - `200 OK`: Availability successfully determined.
  - `400 Bad Request`: Missing address parameter, unresolvable address, or invalid coordinates.
  - `500 Internal Server Error`: Unhandled server exception with structured error details.

#### Authoritative Success Response JSON Schema (`200 OK`)
```json
{
  "status": "success",
  "timestamp": "2026-09-29T21:58:00.000Z",
  "query": {
    "raw": "1600 Pennsylvania Ave NW, Washington, DC 20500"
  },
  "address": {
    "streetNumber": "1600",
    "streetName": "Pennsylvania Ave NW",
    "unitNumber": null,
    "city": "Washington",
    "state": "DC",
    "zip5": "20500",
    "zip4": null,
    "lat": 38.897675,
    "lng": -77.03653,
    "formattedAddress": "1600 Pennsylvania Ave NW, Washington, DC 20500",
    "geocoderSource": "census",
    "confidenceScore": 0.98
  },
  "executionTimeMs": 680,
  "cache": {
    "hit": false,
    "layer": "none"
  },
  "summary": {
    "totalProvidersAvailable": 4,
    "lowestMonthlyPrice": 45.0,
    "maxDownloadSpeedMbps": 300,
    "has5gFixedWireless": true,
    "hasSatelliteAlternative": true,
    "hasCapacityConstraints": false
  },
  "providers": [
    {
      "brandId": "straight-talk-home-internet",
      "brandName": "Straight Talk Home Internet",
      "brandSlug": "straight-talk",
      "networkOperator": "Verizon",
      "technologyType": "5G_FWA",
      "tierType": "prepaid",
      "status": "available",
      "statusBadge": {
        "label": "Available Now",
        "variant": "success"
      },
      "confidence": "verified_live",
      "speeds": {
        "downloadMinMbps": 50,
        "downloadMaxMbps": 100,
        "uploadMinMbps": 5,
        "uploadMaxMbps": 10,
        "displaySpeed": "Up to 100 Mbps"
      },
      "pricing": {
        "startingMonthlyPrice": 45.0,
        "autopayDiscountPrice": 40.0,
        "bundledMobilePrice": null,
        "equipmentUpfrontCost": 99.0,
        "equipmentMonthlyFee": 0.0,
        "contractTerms": "No contract",
        "priceLockGuarantee": "Flat rate pricing",
        "creditCheckRequired": false
      },
      "keyFeatures": [
        "No credit check",
        "Uses Verizon 5G Network",
        "Walmart router purchase ($99)",
        "Flat $40/mo with Auto-Refill"
      ],
      "arbitrageNotes": "Prepaid Verizon network access at $45/mo flat without contract or credit check.",
      "officialSignupUrl": "https://www.straighttalk.com/5g-home-internet"
    },
    {
      "brandId": "t-mobile-5g-home",
      "brandName": "T-Mobile 5G Home Internet",
      "brandSlug": "t-mobile",
      "networkOperator": "T-Mobile",
      "technologyType": "5G_FWA",
      "tierType": "postpaid",
      "status": "available",
      "statusBadge": {
        "label": "Available Now",
        "variant": "success"
      },
      "confidence": "verified_live",
      "speeds": {
        "downloadMinMbps": 72,
        "downloadMaxMbps": 245,
        "uploadMinMbps": 15,
        "uploadMaxMbps": 31,
        "displaySpeed": "72 - 245 Mbps"
      },
      "pricing": {
        "startingMonthlyPrice": 60.0,
        "autopayDiscountPrice": 50.0,
        "bundledMobilePrice": 40.0,
        "equipmentUpfrontCost": 0.0,
        "equipmentMonthlyFee": 0.0,
        "contractTerms": "No annual contract",
        "priceLockGuarantee": "Price Lock Guarantee",
        "creditCheckRequired": true
      },
      "keyFeatures": [
        "Wi-Fi 6 Gateway included free",
        "Unlimited data with no caps",
        "$40/mo if bundled with Go5G Plus voice line"
      ],
      "arbitrageNotes": "Flagship postpaid service on T-Mobile Ultra Capacity 5G.",
      "officialSignupUrl": "https://www.t-mobile.com/home-internet"
    },
    {
      "brandId": "metro-by-t-mobile-5g",
      "brandName": "Metro by T-Mobile Home Internet",
      "brandSlug": "metro-t-mobile",
      "networkOperator": "T-Mobile",
      "technologyType": "5G_FWA",
      "tierType": "prepaid",
      "status": "available",
      "statusBadge": {
        "label": "Available Now",
        "variant": "success"
      },
      "confidence": "verified_live",
      "speeds": {
        "downloadMinMbps": 72,
        "downloadMaxMbps": 245,
        "uploadMinMbps": 15,
        "uploadMaxMbps": 31,
        "displaySpeed": "72 - 245 Mbps"
      },
      "pricing": {
        "startingMonthlyPrice": 55.0,
        "autopayDiscountPrice": 50.0,
        "bundledMobilePrice": 50.0,
        "equipmentUpfrontCost": 49.0,
        "equipmentMonthlyFee": 0.0,
        "contractTerms": "Prepaid / No contract",
        "priceLockGuarantee": null,
        "creditCheckRequired": false
      },
      "keyFeatures": [
        "Prepaid - No credit check",
        "Uses identical T-Mobile 5G network towers",
        "Gateway hardware purchase ($49-$99 promo)"
      ],
      "arbitrageNotes": "Identical coverage to T-Mobile Home Internet for prepaid consumers.",
      "officialSignupUrl": "https://www.metrobyt-mobile.com/home-internet"
    },
    {
      "brandId": "verizon-5g-home",
      "brandName": "Verizon 5G Home Internet",
      "brandSlug": "verizon",
      "networkOperator": "Verizon",
      "technologyType": "5G_FWA",
      "tierType": "postpaid",
      "status": "available",
      "statusBadge": {
        "label": "Available Now",
        "variant": "success"
      },
      "confidence": "verified_live",
      "speeds": {
        "downloadMinMbps": 85,
        "downloadMaxMbps": 300,
        "uploadMinMbps": 10,
        "uploadMaxMbps": 20,
        "displaySpeed": "85 - 300 Mbps"
      },
      "pricing": {
        "startingMonthlyPrice": 60.0,
        "autopayDiscountPrice": 50.0,
        "bundledMobilePrice": 35.0,
        "equipmentUpfrontCost": 0.0,
        "equipmentMonthlyFee": 0.0,
        "contractTerms": "No annual contract",
        "priceLockGuarantee": "2-Year Price Guarantee",
        "creditCheckRequired": true
      },
      "keyFeatures": [
        "Verizon Internet Gateway included",
        "$35/mo with Verizon Unlimited Plus mobile plan",
        "2-Year price guarantee"
      ],
      "arbitrageNotes": "Postpaid option with deep bundling discounts for Verizon mobile subscribers.",
      "officialSignupUrl": "https://www.verizon.com/home/5g"
    },
    {
      "brandId": "starlink-residential",
      "brandName": "Starlink",
      "brandSlug": "starlink",
      "networkOperator": "Starlink",
      "technologyType": "SATELLITE_LEO",
      "tierType": "satellite",
      "status": "available",
      "statusBadge": {
        "label": "Universal Satellite",
        "variant": "secondary"
      },
      "confidence": "satellite_universal",
      "speeds": {
        "downloadMinMbps": 50,
        "downloadMaxMbps": 220,
        "uploadMinMbps": 5,
        "uploadMaxMbps": 25,
        "displaySpeed": "50 - 220 Mbps"
      },
      "pricing": {
        "startingMonthlyPrice": 120.0,
        "autopayDiscountPrice": 120.0,
        "bundledMobilePrice": null,
        "equipmentUpfrontCost": 349.0,
        "equipmentMonthlyFee": 0.0,
        "contractTerms": "No contract (30-day trial)",
        "priceLockGuarantee": null,
        "creditCheckRequired": false
      },
      "keyFeatures": [
        "Nationwide universal coverage",
        "Low Earth Orbit satellite (25-50ms latency)",
        "Standard kit hardware self-install"
      ],
      "arbitrageNotes": "Universal alternative if terrestrial 5G FWA is unavailable or congested.",
      "officialSignupUrl": "https://www.starlink.com/residential"
    }
  ]
}
```

#### Authoritative Error Response JSON Schema (`400 Bad Request`)
```json
{
  "status": "error",
  "code": "ADDRESS_NOT_RESOLVED",
  "message": "Unable to geocode the submitted address into a valid US physical location.",
  "details": {
    "submittedAddress": "Main St, Anywhere",
    "reason": "Missing street number or unparseable street name"
  }
}
```

---

### 5.2. UI Component Hierarchy & Interaction Specification

The frontend is architected as responsive Next.js App Router client and server components styled with Tailwind CSS and shadcn/ui.

```
+-------------------------------------------------------------------------------+
|                            5G Arbitrage Engine UI                             |
+-------------------------------------------------------------------------------+
| [Search Bar] "1600 Pennsylvania Ave NW, Washington, DC"  [ Check Availability ]|
|  * Dropdown: Photon/Census autocomplete suggestions with debounced input      |
+-------------------------------------------------------------------------------+
|  Confirmed Address: 1600 Pennsylvania Ave NW, Washington, DC 20500            |
|  Status: 4 Available Providers • Lowest: $40/mo • Max: 300 Mbps • L1 Hit (4ms) |
+-------------------------------------------------------------------------------+
| [Filter Bar]                                                                  |
| Network: [ All | T-Mobile | Verizon | AT&T | Satellite ]                      |
| Account: [ All | Prepaid (No Credit Check) | Postpaid ]                       |
| Sort By: [ Price (Low to High) v ]                                            |
+-------------------------------------------------------------------------------+
|                                                                               |
|  +-------------------------------------+  +---------------------------------+  |
|  | Straight Talk Home Internet         |  | T-Mobile 5G Home Internet       |  |
|  | [Verizon 5G Network] [Prepaid]      |  | [T-Mobile Network] [Postpaid]   |  |
|  |                                     |  |                                 |  |
|  | $40 /mo                             |  | $50 /mo                         |  |
|  | ($45 standard / $40 with Auto-Pay)  |  | ($60 standard / $50 w/ AutoPay) |  |
|  |                                     |  |                                 |  |
|  | Speed: Up to 100 Mbps               |  | Speed: 72 - 245 Mbps            |  |
|  | Hardware: $99 (Walmart Router)      |  | Hardware: Included ($0 rental)  |  |
|  | Credit Check: No                    |  | Credit Check: Soft check        |  |
|  |                                     |  |                                 |  |
|  | [ View Official Sign Up -> ]        |  | [ View Official Sign Up -> ]    |  |
|  +-------------------------------------+  +---------------------------------+  |
|                                                                               |
|  +-------------------------------------+  +---------------------------------+  |
|  | Metro by T-Mobile Home Internet     |  | Verizon 5G Home Internet        |  |
|  | [T-Mobile 5G Network] [Prepaid]     |  | [Verizon 5G Network] [Postpaid] |  |
|  |                                     |  |                                 |  |
|  | $50 /mo                             |  | $50 /mo                         |  |
|  | ($55 standard / $50 w/ phone line)  |  | ($35 with mobile / $60 stand.)  |  |
|  |                                     |  |                                 |  |
|  | Speed: 72 - 245 Mbps                |  | Speed: 85 - 300 Mbps            |  |
|  | Hardware: $49 promo purchase        |  | Hardware: Included ($0 rental)  |  |
|  | Credit Check: No                    |  | Credit Check: Soft check        |  |
|  |                                     |  |                                 |  |
|  | [ View Official Sign Up -> ]        |  | [ View Official Sign Up -> ]    |  |
|  +-------------------------------------+  +---------------------------------+  |
+-------------------------------------------------------------------------------+
| [Satellite / Rural Fallback Banner]                                           |
| "Starlink Satellite is available everywhere with 100% continental coverage."  |
+-------------------------------------------------------------------------------+
```

#### Component Specifications:

1. `AddressSearchBar.tsx`:
   - State: `inputQuery`, `suggestions[]`, `isLoading`, `selectedSuggestion`.
   - Debounce: 300ms throttle on input change.
   - Behavior: Triggers `/api/geocode/suggest?q=...`. Selecting an item triggers form submit.
   - Accessibility: ARIA combobox pattern (`role="combobox"`, `aria-expanded`, keyboard Up/Down/Enter navigation).

2. `AvailabilityHeader.tsx`:
   - Visual banner confirming resolved postal address (`NormalizedAddress.formattedAddress`).
   - Summary pills: Count of available brands, minimum monthly cost, maximum download speed.
   - Cache indicator badge: Discreet badge showing `Live Verified` or `Cached (<10ms)`.

3. `FilterAndSortBar.tsx`:
   - Sorting options:
     - `price_asc`: "Price: Low to High" (Arbitrage priority).
     - `price_desc`: "Price: High to Low".
     - `speed_desc`: "Download Speed: Fast to Slow".
     - `best_value`: "Best Value (Speed / Price ratio)".
   - Filtering chips:
     - Network Family: `All`, `T-Mobile Network`, `Verizon Network`, `AT&T Network`, `Satellite`.
     - Account Type: `All`, `Prepaid (No Credit Check)`, `Postpaid`.
     - Max Monthly Price: Slider or buttons (`<$45`, `<$60`, `Any`).

4. `ProviderCard.tsx`:
   - Distinct Brand Logo & Network Parent indicator.
   - Hero pricing display with clear autopay vs bundled price breakdown.
   - Speed tier visualization with download/upload range bars.
   - Equipment transparency block: Explicitly highlights whether gateway is free rental or requires upfront router purchase (crucial arbitrage distinction).
   - Direct CTA: Outbound hyperlink button with `target="_blank"` and `rel="noopener noreferrer"`.

5. `SatelliteFallbackBanner.tsx` & Rural Unserved View:
   - Activates when 0 terrestrial 5G FWA providers are available at address.
   - Displays clear, non-alarmist notification: "5G Home Internet has not yet expanded to this cell sector."
   - Prominently showcases **Starlink Residential** with transparent pricing ($120/mo + hardware kit) and latency expectations.
   - Provides an alert signup form ("Notify me when 5G Home reaches this address").

---

## 6. Features Discovered & Mined Table

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|---|---|---|---|---|---|---|
| 1 | R1 Geocoding | US Census Bureau Geocoder | Zero-config, free REST geocoder for US addresses returning rooftop/interpolated coords and TigerLine components. | `address`, `benchmark=Public_AR_Current`, `format=json` | `x` (lng), `y` (lat), `addressComponents` (street, city, state, zip) | Returns empty `addressMatches: []` on unrecognized address. | Census Bureau Official REST API Spec |
| 2 | R1 Geocoding | Komoot Photon Autocomplete | Free GeoJSON autocomplete API powered by OSM with US bounding box filtering. | `q`, `bbox`, `limit`, `lang=en` | GeoJSON `FeatureCollection` with `Point` coordinates and address properties | Returns empty `features: []` on non-match. | Photon Komoot Open API Spec |
| 3 | R1 Geocoding | OSM Nominatim Structured Search | Structured open geocoding fallback returning granular administrative hierarchy. | `q`, `format=jsonv2`, `addressdetails=1`, `User-Agent` | Array of geocoded places with `address` object | HTTP 429 if User-Agent header is missing or rate limited. | Nominatim OSM API Documentation |
| 4 | R1 Geocoding | Postal Component Normalizer | Decomposes and standardizes raw address components to `NormalizedAddress`. | Raw vendor geocode object | Typed `NormalizedAddress` with standard 2-letter state | Throws `ValidationError` if street number or ZIP code is absent. | USPS Postal Addressing Standard / ORIGINAL_REQUEST.md |
| 5 | R1 Geocoding | Drop-in Google Places Adapter | High-accuracy commercial geocoding and autocomplete adapter activated via env variable. | `GOOGLE_PLACES_API_KEY`, search string | Google Places autocomplete predictions and geocode lat/lng | Fails over to Census/Photon if API key is invalid or quota exceeded. | Google Maps Platform API Docs |
| 6 | R1 Geocoding | Drop-in Mapbox Geocoding Adapter | Alternative commercial geocoder activated via `MAPBOX_ACCESS_TOKEN`. | `MAPBOX_ACCESS_TOKEN`, search string | Mapbox Geocoding v6 forward feature collection | Fails over to Census/Photon on HTTP 401/403. | Mapbox Search API Docs |
| 7 | R2 Engine | FCC BDC Fixed Technology Mapping | Identifies Fixed Wireless (71 licensed, 72 CBRS, 70 unlicensed) and LEO Satellite (61). | FCC BDC CSV or API record with `technology` code | Categorized broadband technology tier | Ignores obsolete copper (10) or non-relevant technologies. | FCC Broadband Data Collection Technical Guide |
| 8 | R2 Engine | T-Mobile Dual-Brand Resolution | Maps T-Mobile 5G FWA footprint into T-Mobile 5G Home (postpaid) and Metro (prepaid). | Confirmed T-Mobile 5G cell coverage | 2 distinct provider entries: T-Mobile Postpaid ($50-$60) and Metro Prepaid ($50-$55) | If cell sector is capacity-constrained, flags postpaid waitlist while evaluating prepaid. | Carrier Product Catalogs & FCC BDC |
| 9 | R2 Engine | Verizon Triple-Brand Resolution | Maps Verizon C-band/mmWave coverage into Verizon Postpaid, Straight Talk, and Total Wireless. | Confirmed Verizon 5G cell coverage | 3 distinct entries: Verizon 5G ($50-$80), Straight Talk ($45/mo, 100Mbps cap), Total Wireless ($45-$60) | Emits distinct equipment requirements for each ($0 gateway vs $99 router). | Verizon/TracFone Retail Disclosures |
| 10 | R2 Engine | AT&T Internet Air Resolution | Maps AT&T mid-band 5G coverage to AT&T Internet Air fixed wireless. | Confirmed AT&T 5G FWA coverage | AT&T Internet Air entry ($60/mo or $35 bundled, All-Fi Hub) | Returns unavailable if outside AT&T Air footprint. | AT&T Wholesale & Consumer Specs |
| 11 | R2 Engine | Starlink Universal Satellite Baseline | Evaluates nationwide LEO satellite coverage as resilient broadband baseline. | Any valid continental US coordinate | Starlink Residential entry ($120/mo, 50-220 Mbps, kit purchase) | Never fails for continental US; marked `satellite_universal`. | SpaceX / FCC BDC Technology 61 Filings |
| 12 | R2 Engine | `IProviderChecker` Contract | Modular interface for carrier pre-flight availability checks. | `ProviderCheckInput` (NormalizedAddress, FCC summary, timeoutMs) | `Promise<ProviderCheckResult[]>` | Hard 1.5s timeout with `AbortController` cancellation. | ORIGINAL_REQUEST.md R2 |
| 13 | R2 Engine | Resilient Fallback to FCC BDC | Automatic fallback when carrier endpoint hangs, throttles (429), or errors. | Error or timeout during carrier check | Generates `fallback_available` result using FCC BDC database | Request completes successfully without throwing HTTP 500. | ORIGINAL_REQUEST.md Acceptance Criteria |
| 14 | R3 Catalog | Drizzle SQLite Schema | Tables for `brands`, `plans`, `fcc_provider_mapping`, `coordinate_lookup_cache`. | Drizzle ORM model definitions | SQLite schema migrations and typed queries | Schema constraint checks prevent orphaned plan records. | Drizzle ORM Documentation |
| 15 | R3 Catalog | L1 In-Memory LRU Cache | High-speed memory cache storing recent availability JSON responses. | Normalized address cache key, TTL 1 hr | Immediate cache hit in < 5ms | Evicts least-recently-used entry when max capacity (1,000) reached. | Node.js LRU Cache Standards |
| 16 | R3 Catalog | L2 SQLite Coordinate Cache | Persistent coordinate lookup cache using 4-decimal rounded coordinates (~11m). | Rounded `lat:lng`, TTL 24 hrs | Sub-25ms response for repeat queries in same vicinity | Automatic expiration check against `expires_at` timestamp. | Spatial Caching Architecture |
| 17 | R4 API | `GET /api/availability` REST Endpoint | Returns structured JSON availability report in under 2 seconds. | `address` string, optional `lat`/`lng`/`fresh` | HTTP 200 with address, summary, and providers array | HTTP 400 with structured JSON error if address unparseable. | ORIGINAL_REQUEST.md Acceptance Criteria |
| 18 | R4 UI | Debounced Address Autocomplete Search | Search bar with 300ms debounce and suggestions dropdown. | User keystrokes in input field | Address suggestions list | Graceful empty list if search returns 0 matches. | shadcn/ui & Next.js Client Components |
| 19 | R4 UI | Arbitrage Comparison Grid Cards | Displays brand badges, network parent, prices, speeds, and equipment terms. | Array of `ProviderAvailabilityItem` | Responsive grid of formatted comparison cards | Displays distinct styling for prepaid vs postpaid vs satellite. | ORIGINAL_REQUEST.md R4 |
| 20 | R4 UI | Dynamic Filtering & Sorting | Multi-parameter filters by network family, prepaid/postpaid, speed, and price. | User filter and sort selections | Instantly filtered and re-ordered list of cards | Displays "No matching providers for selected filters" if all excluded. | React State / URL Query Sync |
| 21 | R4 UI | Satellite-Only Fallback View | Empathetic, clear messaging for rural or unserved locations. | Availability result with 0 5G FWA providers | Banner highlighting Starlink Residential + notification signup | Prevents confusing "service error" UI for rural users. | ORIGINAL_REQUEST.md Acceptance Criteria |

---

## 7. Edge Cases & Observed Behaviors Table

| # | Feature | Input | Observed / Specified Behavior |
|---|---|---|---|
| 1 | Geocoding | Address without street number (e.g. `"Main St, Springfield, IL"`) | Census Geocoder returns street segment without discrete rooftop point. Normalizer flags `streetNumber` missing and returns HTTP 400: `"Please provide a full street address including building number."` |
| 2 | Geocoding | PO Box address (e.g. `"PO Box 1234, Dallas, TX 75201"`) | Detected by regex `/\bP(OST)?\s*O(FFICE)?\s*BOX\b/i`. Fixed Wireless Gateways cannot be delivered to PO Boxes. Engine returns HTTP 400: `"Fixed wireless home internet requires a physical residential street address."` |
| 3 | Geocoding | Multi-family unit/apartment (e.g. `"123 Elm St Apt 4B, Chicago, IL"`) | Normalizer extracts `streetNumber: "123"`, `streetName: "Elm St"`, and preserves `unitNumber: "Apt 4B"`. Coordinates are resolved for building footprint to ensure valid cell tower propagation check. |
| 4 | Geocoding | Census Bureau Geocoder Outage or Timeout (> 2.5s) | Geocoder cascade catches Census network error/timeout and falls back immediately to Komoot Photon, completing geocode within SLA. |
| 5 | Availability Engine | Carrier API Throttling (HTTP 429 Too Many Requests) | Provider checker catches HTTP 429, logs warning, suppresses exception, and reads FCC BDC coverage table for the provider's FRN, returning `status: 'fallback_available'` and `source: 'fcc_bdc_fallback'`. |
| 6 | Availability Engine | Carrier API Latency Spike (> 1.5s) | AbortSignal triggers at 1500ms. Pending fetch is terminated. Engine falls back to FCC BDC data without delaying the response past the 2.0s overall SLA. |
| 7 | Brand Resolution | Cell Tower Sector Congestion (T-Mobile reports "Waitlist") | Direct carrier check reports `waitlist`. T-Mobile 5G Home card renders `Waitlist Open` badge. Metro by T-Mobile card notes retail store walk-in alternative or capacity limit. |
| 8 | Brand Resolution | Rural / Non-Terrestrial Address (No 5G FWA coverage) | 0 terrestrial MNOs report coverage. Engine returns Starlink with `satellite_universal` status and renders `SatelliteFallbackBanner` with equipment cost breakdown ($349 kit). |
| 9 | Cache Layer | Repeat query for exact same address within 1 hour | L1 in-memory LRU cache intercepts query and serves full response in under 5ms (`cache.layer: 'l1_memory'`). |
| 10 | Cache Layer | Repeat query for adjoining townhouse (same building, slight coord delta) | Coordinates round to identical 4-decimal spatial key (`lat.toFixed(4) + ":" + lng.toFixed(4)`), hitting L2 SQLite cache in < 25ms (`cache.layer: 'l2_db'`). |
| 11 | API Validation | Query with coordinates outside continental US (e.g. Hawaii/Alaska/Overseas) | Coordinate boundary validator flags out-of-footprint coordinates for fixed wireless (Hawaii/Alaska have specific distinct FWA networks) and returns Starlink availability where applicable. |
| 12 | UI Display | User applies conflicting filter (e.g. "Prepaid" + "AT&T Network" where AT&T currently has no prepaid FWA) | Filter bar displays empty state card: `"No providers match this combination. Try clearing your filters to see all 4 available providers."` with a "Reset Filters" action button. |

---

## 8. Verification & Validation Protocol

To independently verify the specification compliance during implementation:

1. **Unit Testing (`vitest`)**:
   - `test/geocoding/normalizer.test.ts`: Verify address parsing across 20 canonical US test addresses (including DC, PO Boxes, multi-word street names, apartment units).
   - `test/engine/brand-resolution.test.ts`: Verify T-Mobile coverage yields distinct T-Mobile Postpaid and Metro entries; Verizon coverage yields Verizon Postpaid, Straight Talk, and Total Wireless entries.
   - `test/engine/timeout-fallback.test.ts`: Mock carrier checker with simulated 2000ms delay; verify that checker aborts at $\le 1500$ms and activates FCC BDC fallback without failing request.
   - `test/catalog/drizzle-cache.test.ts`: Verify Drizzle SQLite schema creation, insertion, spatial key querying, and L1 LRU eviction.

2. **Integration & API Testing**:
   - Execute `GET /api/availability?address=1600+Pennsylvania+Ave+NW,+Washington,+DC+20500`. Verify response status is 200, response time is $< 2000$ms, and `providers` array contains distinct brand identities.
   - Execute repeat query; verify response time is $< 50$ms and `cache.hit === true`.

3. **End-to-End Testing (`playwright`)**:
   - Journey 1 (Urban Multi-Carrier): Search valid urban address; verify comparison grid displays T-Mobile, Metro, Verizon, Straight Talk, and Starlink cards with active outbound links.
   - Journey 2 (Filtering & Sorting): Filter by "Prepaid"; verify only Metro, Straight Talk, and Total Wireless are visible. Sort by "Price: Low to High"; verify $40/mo Straight Talk appears first.
   - Journey 3 (Rural Satellite-Only): Search rural coordinate fixture; verify graceful satellite fallback banner renders with Starlink pricing and no broken carrier cards.
