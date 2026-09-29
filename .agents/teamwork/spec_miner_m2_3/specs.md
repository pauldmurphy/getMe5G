# Milestone 2 Technical Specification: Brand Catalog, Plans & FCC Provider Seeding

**Author**: `spec_miner_m2_3`  
**Working Directory**: `.agents/teamwork/spec_miner_m2_3`  
**Date**: 2026-09-29  
**Status**: Authoritative Milestone 2 Specification  
**Reference Sources**: `ORIGINAL_REQUEST.md`, `PROJECT.md`, `tests/fixtures/fcc-records.json`, `tests/fixtures/addresses.json`, `tests/unit/engine/brand-mapper.test.ts`, `tests/unit/engine/timeout-fallback.test.ts`, `tests/e2e/journeys.spec.ts`, `spec_miner_survey_2/specs.md`.

---

## 1. Overview & Scope

Milestone 2 establishes the database foundation and persistent catalog for the 5G Arbitrage Engine. The core requirement is providing an authoritative, pre-seeded dataset containing:
1. **7 Distinct Retail Consumer Brands** across 4 network infrastructures (T-Mobile, Verizon, AT&T, Starlink).
2. **Comprehensive Plan Offerings** with granular arbitrage data: regular price, autopay discount price, mobile bundle price, advertised download/upload speed ranges, equipment rental vs. purchase fees, contract terms, price locks, and official signup URLs.
3. **FCC Provider ID and FRN Mappings** connecting location-level BDC records (`fcc-records.json`) to consumer retail brands, enabling the hybrid availability engine to disambiguate carrier infrastructure into retail offerings.

---

## 2. Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|---|---|---|---|---|---|---|
| 1 | Catalog Seeding | 7 Retail Brand Definitions | Canonical retail brand metadata distinguishing MNO and MVNO retail identities. | Brand ID, Name, Slug, Network Operator, Tier, Logo, Credit Check, URL | Typed `BrandRecord` rows inserted into SQLite `brands` table | Rejects duplicate primary keys or missing required fields (`NOT NULL`) | ORIGINAL_REQUEST.md §R2, §R3 |
| 2 | Catalog Seeding | T-Mobile Dual-Brand Seeding | Seed entries for T-Mobile 5G Home (Postpaid) and Metro by T-Mobile (Prepaid). | Brand and Plan data objects | 2 `brands` rows, 2 `plans` rows, linked by `brandId` | Foreign key constraint fails if brand is inserted after plans | PROJECT.md, addresses.json, brand-mapper.test.ts |
| 3 | Catalog Seeding | Verizon Triple-Brand Seeding | Seed entries for Verizon 5G Home (Postpaid), Straight Talk (Prepaid), and Total Wireless (Prepaid). | Brand and Plan data objects | 3 `brands` rows, 3 `plans` rows | Foreign key constraint fails if brand ID does not match | PROJECT.md, brand-mapper.test.ts |
| 4 | Catalog Seeding | AT&T Internet Air Seeding | Seed entries for AT&T Internet Air ($60 standard, $35 bundled, All-Fi Hub included). | Brand and Plan data objects | 1 `brands` row, 1 `plans` row | Fails on null required columns | PROJECT.md, addresses.json, brand-mapper.test.ts |
| 5 | Catalog Seeding | Starlink Universal Satellite Seeding | Seed entries for Starlink Residential ($120/mo, $599 hardware kit, LEO satellite). | Brand and Plan data objects | 1 `brands` row, 1 `plans` row | Fails on null required columns | PROJECT.md, brand-mapper.test.ts, timeout-fallback.test.ts |
| 6 | Catalog Seeding | Pricing & Arbitrage Model | Stores 3 pricing tiers per plan: regular, autopay discount, and bundled mobile discount. | Plan pricing numerical values | Stored real numbers with currency precision | Negative prices disallowed; bundled requirement required if bundled price set | ORIGINAL_REQUEST.md §R3 |
| 7 | Catalog Seeding | Equipment Cost Transparency | Explicitly models equipment upfront purchase cost vs. monthly rental fee. | `equipmentUpfrontCost`, `equipmentFeeMonthly`, `equipmentPolicy` | Differentiates $0 rental (T-Mobile, Verizon, AT&T) from hardware purchase (Metro $49, Straight Talk $99, Total $99, Starlink $599) | Throws error if non-numeric cost provided | PROJECT.md §3.2, brand-mapper.test.ts |
| 8 | FCC Mapping | T-Mobile FCC BDC Mapping | Maps FRN `0001565480` / Provider ID `130077` (Tech 71) to `t-mobile-5g-home` and `metro-by-t-mobile`. | `fcc-records.json` record | 2 mapping records: primary (`t-mobile-5g-home`) and secondary (`metro-by-t-mobile`) | Mapping fails if brandId foreign key does not exist | fcc-records.json, brand-mapper.test.ts |
| 9 | FCC Mapping | Verizon FCC BDC Mapping | Maps FRN `0003290673` / Provider ID `130403` (Tech 71 and 72) to `verizon-5g-home`, `straight-talk-home`, `total-wireless-home`. | `fcc-records.json` records | 6 mapping records (3 brands × 2 tech codes 71 & 72) | Mapping fails on missing foreign key | fcc-records.json, brand-mapper.test.ts |
| 10 | FCC Mapping | AT&T FCC BDC Mapping | Maps FRN `0005050851` / Provider ID `130079` (Tech 71) to `att-internet-air`. | `fcc-records.json` record | 1 mapping record (primary) | Mapping fails on missing foreign key | fcc-records.json, brand-mapper.test.ts |
| 11 | FCC Mapping | Starlink FCC BDC Mapping | Maps FRN `0027768225` / Provider ID `131444` (Tech 61) to `starlink-residential`. | `fcc-records.json` record | 1 mapping record (primary) | Mapping fails on missing foreign key | fcc-records.json, brand-mapper.test.ts |
| 12 | FCC Mapping | Wireline & Unlicensed Filtering | Filters out wireline (Tech 10 Copper, Tech 40 Cable) from mapping to consumer 5G FWA brands. | `fcc-records.json` wireline records | Omitted from fixed wireless provider mappings | Prevent spurious wireline brand mapping | fcc-records.json, brand-mapper.test.ts |
| 13 | Seed Script | Idempotent Seeding Execution | Seed script `seedDatabase()` can be run repeatedly without duplicating rows or violating unique constraints. | SQLite database instance | Truncates or replaces existing seed records safely | Handles existing database without throwing primary key collision error | drizzle.config.ts, package.json `npm run db:seed` |
| 14 | Seed Script | Test Suite In-Memory Seeder | Seed module can be imported and executed against better-sqlite3 in-memory database (`:memory:`) in `tests/setup.ts`. | In-memory Drizzle DB instance | Populates test database instantly (<15ms) | Works identically in memory and on disk | tests/setup.ts, vitest.config.ts |

---

## 3. Edge Cases & Observed Behaviors

| # | Feature | Input | Observed Behavior |
|---|---|---|---|
| 1 | Idempotent Re-seeding | Running `tsx src/lib/db/seed.ts` twice on existing database | If table already contains records, seed script uses delete-then-insert within a transaction or `onConflictDoUpdate` to prevent `SQLITE_CONSTRAINT: UNIQUE constraint failed`. |
| 2 | Foreign Key Ordering | Inserting `plans` before `brands` | SQLite foreign key constraint `FOREIGN KEY(brand_id) REFERENCES brands(id)` rejects insert. Seeding script MUST insert all `brands` prior to `plans` and `fcc_provider_mapping`. |
| 3 | Bundled Price Nullability | Straight Talk has no mobile bundle option | `monthlyPriceBundled` and `bundledRequirement` are stored as `null`. UI and API consumers handle `null` without crashing. |
| 4 | Speed Range Boundaries | Straight Talk speed cap (max 100 Mbps) vs. Verizon Postpaid (max 300 Mbps) | Both operate on Verizon network, but Straight Talk `downloadSpeedMax` is strictly 100, verified by `brand-mapper.test.ts` (`expect(st.speeds.downloadMaxMbps).toBeLessThanOrEqual(100)`). |
| 5 | Shared Network Multiple Tech Codes | Verizon operates on Tech 71 (Licensed 5G) and Tech 72 (CBRS) | Both technology codes map to all 3 Verizon retail brands (`verizon-5g-home`, `straight-talk-home`, `total-wireless-home`), allowing resolution regardless of whether cell sector is reported under 71 or 72. |
| 6 | Equipment Ownership Semantics | Postpaid rental ($0 rental, return required) vs. Prepaid purchase ($49-$99 one-time) | Captured accurately in `equipmentUpfrontCost`, `equipmentFeeMonthly`, and `equipmentPolicy`. Tests assert upfront cost is 0 for postpaid and > 0 for prepaid. |
| 7 | Satellite Universal Hardware | Starlink standard kit purchase | Upfront cost is $599.00 (`expect(starlink.pricing.equipmentUpfrontCost).toBe(599)` in `brand-mapper.test.ts`), with policy clarifying standard self-install kit. |
| 8 | Unlicensed WISP in FCC Fixture | Prairie Wireless (Tech 70, Provider ID 139999) | Fixture contains unlicensed fixed wireless; seed mapping can either record Prairie Wireless as independent brand or omit it since it is not one of the 7 core retail brands. |

---

## 4. Retail Consumer Brand Catalog Specifications

The 7 retail consumer brands defined below represent the complete retail catalog for the application:

### Brand 1: T-Mobile 5G Home Internet (`t-mobile-5g-home`)
- **Brand ID**: `t-mobile-5g-home`
- **Name**: `T-Mobile 5G Home Internet`
- **Slug**: `t-mobile-5g-home`
- **Network Operator**: `T-Mobile`
- **Parent Company**: `T-Mobile US, Inc.`
- **Technology**: `5G_FWA`
- **Tier Type**: `postpaid`
- **Badge Color**: `magenta` (#E20074)
- **Credit Check Required**: `true` (soft credit check)
- **Official Signup URL**: `https://www.t-mobile.com/home-internet`
- **Logo URL**: `/images/brands/t-mobile.svg`
- **Website URL**: `https://www.t-mobile.com/home-internet`
- **Arbitrage Notes**: Flagship postpaid fixed wireless on T-Mobile Ultra Capacity 5G. Free gateway rental, soft credit check, $50/mo w/ autopay, $40/mo if bundled with Go5G Plus voice line.

### Brand 2: Metro by T-Mobile (`metro-by-t-mobile`)
- **Brand ID**: `metro-by-t-mobile`
- **Name**: `Metro by T-Mobile`
- **Slug**: `metro-by-t-mobile`
- **Network Operator**: `T-Mobile`
- **Parent Company**: `T-Mobile US, Inc.`
- **Technology**: `5G_FWA`
- **Tier Type**: `prepaid`
- **Badge Color**: `purple` (#4F2683)
- **Credit Check Required**: `false` (no credit check)
- **Official Signup URL**: `https://www.metrobyt-mobile.com/home-internet`
- **Logo URL**: `/images/brands/metro.svg`
- **Website URL**: `https://www.metrobyt-mobile.com/home-internet`
- **Arbitrage Notes**: Prepaid alternative sharing identical T-Mobile 5G cell tower infrastructure. No credit check, $50/mo standard ($40/mo with phone line promo), requires $49 upfront promotional router purchase.

### Brand 3: Verizon 5G Home Internet (`verizon-5g-home`)
- **Brand ID**: `verizon-5g-home`
- **Name**: `Verizon 5G Home Internet`
- **Slug**: `verizon-5g-home`
- **Network Operator**: `Verizon`
- **Parent Company**: `Verizon Communications Inc.`
- **Technology**: `5G_FWA`
- **Tier Type**: `postpaid`
- **Badge Color**: `red` (#EE0000)
- **Credit Check Required**: `true` (soft credit check)
- **Official Signup URL**: `https://www.verizon.com/home/5g`
- **Logo URL**: `/images/brands/verizon.svg`
- **Website URL**: `https://www.verizon.com/home/5g`
- **Arbitrage Notes**: Flagship postpaid 5G Home Internet on Verizon C-Band and mmWave. Free gateway included, soft credit check, 2-year price guarantee, $50/mo w/ autopay ($60 regular), $35/mo with qualifying Verizon mobile plan.

### Brand 4: Straight Talk Home Internet (`straight-talk-home`)
- **Brand ID**: `straight-talk-home`
- **Name**: `Straight Talk Home Internet`
- **Slug**: `straight-talk-home`
- **Network Operator**: `Verizon`
- **Parent Company**: `TracFone Wireless / Verizon`
- **Technology**: `5G_FWA`
- **Tier Type**: `prepaid`
- **Badge Color**: `green` (#008752)
- **Credit Check Required**: `false` (no credit check)
- **Official Signup URL**: `https://www.straighttalk.com/5g-home-internet`
- **Logo URL**: `/images/brands/straight-talk.svg`
- **Website URL**: `https://www.straighttalk.com/5g-home-internet`
- **Arbitrage Notes**: Prepaid Verizon network access through Walmart exclusive partnership. Flat $45/mo ($40 w/ autopay), no credit check, no mobile plan required, 100 Mbps speed cap, $99 router purchase at Walmart.

### Brand 5: Total Wireless Home Internet (`total-wireless-home`)
- **Brand ID**: `total-wireless-home`
- **Name**: `Total Wireless Home Internet`
- **Slug**: `total-wireless-home`
- **Network Operator**: `Verizon`
- **Parent Company**: `TracFone Wireless / Verizon`
- **Technology**: `5G_FWA`
- **Tier Type**: `prepaid`
- **Badge Color**: `orange` (#FF6600)
- **Credit Check Required**: `false` (no credit check)
- **Official Signup URL**: `https://www.totalwireless.com/home-internet`
- **Logo URL**: `/images/brands/total-wireless.svg`
- **Website URL**: `https://www.totalwireless.com/home-internet`
- **Arbitrage Notes**: Prepaid brand on Verizon 5G Ultra Wideband. Up to 200 Mbps speeds (higher than Straight Talk), 5-year price guarantee, $60 regular ($45 w/ autopay), $35/mo when bundled with Total Wireless Unlimited mobile line, $99 router purchase.

### Brand 6: AT&T Internet Air (`att-internet-air`)
- **Brand ID**: `att-internet-air`
- **Name**: `AT&T Internet Air`
- **Slug**: `att-internet-air`
- **Network Operator**: `AT&T`
- **Parent Company**: `AT&T Inc.`
- **Technology**: `5G_FWA`
- **Tier Type**: `postpaid`
- **Badge Color**: `blue` (#009FDB)
- **Credit Check Required**: `true` (soft credit check)
- **Official Signup URL**: `https://www.att.com/internet/internet-air/`
- **Logo URL**: `/images/brands/att.svg`
- **Website URL**: `https://www.att.com/internet/internet-air/`
- **Arbitrage Notes**: AT&T mid-band 5G fixed wireless offering. All-Fi Hub included free ($0 rental), soft credit check, $60/mo standard, $35/mo bundled with eligible AT&T postpaid mobile line.

### Brand 7: Starlink Residential (`starlink-residential`)
- **Brand ID**: `starlink-residential`
- **Name**: `Starlink Residential`
- **Slug**: `starlink-residential`
- **Network Operator**: `Starlink`
- **Parent Company**: `Space Exploration Technologies Corp. (SpaceX)`
- **Technology**: `SATELLITE_LEO`
- **Tier Type**: `satellite`
- **Badge Color**: `slate` (#0F172A)
- **Credit Check Required**: `false` (no credit check)
- **Official Signup URL**: `https://www.starlink.com/residential`
- **Logo URL**: `/images/brands/starlink.svg`
- **Website URL**: `https://www.starlink.com/residential`
- **Arbitrage Notes**: Nationwide Low Earth Orbit satellite broadband. 100% universal continental US coverage baseline, no contract (30-day trial), no credit check, $120/mo, $599 hardware kit purchase.

---

## 5. Plans Catalog Detailed Matrix

| Brand ID | Plan ID | Plan Name | Regular Price | Autopay Price | Bundled Price | Bundled Requirement | Down Min / Max (Mbps) | Up Min / Max (Mbps) | Upfront Equip. | Monthly Equip. | Contract | Price Guarantee | Credit Check |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `t-mobile-5g-home` | `t-mobile-5g-home-unlimited` | Unlimited 5G Home Internet | $60.00 | $50.00 | $40.00 | Eligible voice line (Go5G Plus / Next) | 72 / 245 | 15 / 31 | $0.00 | $0.00 | No annual contract | Price Lock Guarantee | Soft check (true) |
| `metro-by-t-mobile` | `metro-5g-home-prepaid` | Metro 5G Home Internet | $55.00 | $50.00 | $40.00 | Active Metro voice phone line | 72 / 245 | 15 / 31 | $49.00 | $0.00 | Prepaid / No contract | Flat rate pricing | None (false) |
| `verizon-5g-home` | `verizon-5g-home-standard` | Verizon 5G Home | $60.00 | $50.00 | $35.00 | Verizon Unlimited Plus / Ultimate mobile plan | 85 / 300 | 10 / 20 | $0.00 | $0.00 | No annual contract | 2-Year Price Guarantee | Soft check (true) |
| `straight-talk-home` | `straight-talk-home-standard` | Straight Talk 5G Home Internet | $45.00 | $40.00 | null | None (unbundled) | 25 / 100 | 5 / 10 | $99.00 | $0.00 | Prepaid / No contract | Flat rate pricing | None (false) |
| `total-wireless-home` | `total-wireless-home-standard` | Total Wireless 5G Home Internet | $60.00 | $45.00 | $35.00 | Total Wireless Unlimited mobile plan | 50 / 200 | 10 / 20 | $99.00 | $0.00 | Prepaid / No contract | 5-Year Price Guarantee | None (false) |
| `att-internet-air` | `att-internet-air-standard` | AT&T Internet Air | $60.00 | $60.00 | $35.00 | Eligible AT&T postpaid wireless phone plan | 75 / 225 | 10 / 25 | $0.00 | $0.00 | No annual contract | None | Soft check (true) |
| `starlink-residential` | `starlink-residential-standard` | Starlink Residential Standard | $120.00 | $120.00 | null | None (unbundled) | 50 / 220 | 5 / 25 | $599.00 | $0.00 | No contract (30-day trial) | None | None (false) |

---

## 6. FCC Provider Mapping Matrix (`fcc-records.json` Mapping)

Derived from `tests/fixtures/fcc-records.json`:

| ID | FRN | Provider ID | FCC Holding Name | FCC Technology | Target Brand ID | Is Primary Brand | Notes |
|---|---|---|---|---|---|---|---|
| 1 | `0001565480` | `130077` | T-Mobile USA, Inc. | 71 (Licensed Fixed Wireless) | `t-mobile-5g-home` | `true` | Primary flagship brand for T-Mobile 5G |
| 2 | `0001565480` | `130077` | T-Mobile USA, Inc. | 71 (Licensed Fixed Wireless) | `metro-by-t-mobile` | `false` | Prepaid sister brand on same T-Mobile towers |
| 3 | `0003290673` | `130403` | Cellco Partnership (Verizon) | 71 (Licensed Fixed Wireless) | `verizon-5g-home` | `true` | Primary flagship brand for Verizon 5G C-Band |
| 4 | `0003290673` | `130403` | Cellco Partnership (Verizon) | 71 (Licensed Fixed Wireless) | `straight-talk-home` | `false` | TracFone/Walmart prepaid brand on Verizon 5G |
| 5 | `0003290673` | `130403` | Cellco Partnership (Verizon) | 71 (Licensed Fixed Wireless) | `total-wireless-home` | `false` | TracFone prepaid brand on Verizon 5G |
| 6 | `0003290673` | `130403` | Cellco Partnership (Verizon CBRS) | 72 (Licensed-by-Rule CBRS) | `verizon-5g-home` | `true` | Verizon CBRS Band 48 coverage |
| 7 | `0003290673` | `130403` | Cellco Partnership (Verizon CBRS) | 72 (Licensed-by-Rule CBRS) | `straight-talk-home` | `false` | TracFone/Walmart prepaid on CBRS |
| 8 | `0003290673` | `130403` | Cellco Partnership (Verizon CBRS) | 72 (Licensed-by-Rule CBRS) | `total-wireless-home` | `false` | TracFone prepaid on CBRS |
| 9 | `0005050851` | `130079` | AT&T Services, Inc. | 71 (Licensed Fixed Wireless) | `att-internet-air` | `true` | AT&T Internet Air mid-band 5G |
| 10 | `0027768225` | `131444` | SpaceX Services, Inc. | 61 (NGSO LEO Satellite) | `starlink-residential` | `true` | Starlink universal satellite fallback |

*(Note: FRN `0020123456` Prairie Wireless is unlicensed WISP Tech 70 and wireline entries Tech 10 and 40 are excluded from retail 5G FWA provider mappings).*

---

## 7. Complete TypeScript Data Objects for `src/lib/db/seed.ts`

```typescript
/**
 * TypeScript Data Definitions & Complete Seed Data for 5G Arbitrage Engine
 * Target file: src/lib/db/seed.ts
 */

export interface BrandSeed {
  id: string;
  name: string;
  slug: string;
  networkOperator: string;
  parentCompany: string;
  technology: string;
  tierType: 'postpaid' | 'prepaid' | 'satellite';
  badgeColor: string;
  logoUrl?: string;
  websiteUrl: string;
  officialSignupUrl: string;
  creditCheckRequired: boolean;
  createdAt: Date;
}

export interface PlanSeed {
  id: string;
  brandId: string;
  planName: string;
  monthlyPrice: number;
  monthlyPriceRegular: number;
  monthlyPriceAutopay: number | null;
  monthlyPriceBundled: number | null;
  bundledRequirement: string | null;
  downloadMinMbps: number;
  downloadMaxMbps: number;
  uploadMinMbps: number;
  uploadMaxMbps: number;
  dataCapGb: number | null;
  isUnlimited: boolean;
  contractTerms: string;
  priceGuarantee: string | null;
  equipmentFee: number;
  equipmentFeeMonthly: number;
  equipmentUpfrontCost: number;
  equipmentPolicy: string;
  creditCheckRequired: boolean;
  officialSignupUrl: string;
  keyFeatures: string[];
  arbitrageNotes: string;
  promotionalDetails: string | null;
}

export interface FccProviderMappingSeed {
  frn: string;
  providerId: number;
  fccHoldingName: string;
  technologyCode: number;
  brandId: string;
  isPrimaryBrand: boolean;
}

// -------------------------------------------------------------------------
// 1. BRAND SEEDS (All 7 Retail Consumer Brands)
// -------------------------------------------------------------------------
export const BRAND_SEEDS: BrandSeed[] = [
  {
    id: 't-mobile-5g-home',
    name: 'T-Mobile 5G Home Internet',
    slug: 't-mobile-5g-home',
    networkOperator: 'T-Mobile',
    parentCompany: 'T-Mobile US, Inc.',
    technology: '5G_FWA',
    tierType: 'postpaid',
    badgeColor: 'magenta',
    logoUrl: '/images/brands/t-mobile.svg',
    websiteUrl: 'https://www.t-mobile.com/home-internet',
    officialSignupUrl: 'https://www.t-mobile.com/home-internet',
    creditCheckRequired: true,
    createdAt: new Date('2026-01-01T00:00:00Z'),
  },
  {
    id: 'metro-by-t-mobile',
    name: 'Metro by T-Mobile',
    slug: 'metro-by-t-mobile',
    networkOperator: 'T-Mobile',
    parentCompany: 'T-Mobile US, Inc.',
    technology: '5G_FWA',
    tierType: 'prepaid',
    badgeColor: 'purple',
    logoUrl: '/images/brands/metro.svg',
    websiteUrl: 'https://www.metrobyt-mobile.com/home-internet',
    officialSignupUrl: 'https://www.metrobyt-mobile.com/home-internet',
    creditCheckRequired: false,
    createdAt: new Date('2026-01-01T00:00:00Z'),
  },
  {
    id: 'verizon-5g-home',
    name: 'Verizon 5G Home Internet',
    slug: 'verizon-5g-home',
    networkOperator: 'Verizon',
    parentCompany: 'Verizon Communications Inc.',
    technology: '5G_FWA',
    tierType: 'postpaid',
    badgeColor: 'red',
    logoUrl: '/images/brands/verizon.svg',
    websiteUrl: 'https://www.verizon.com/home/5g',
    officialSignupUrl: 'https://www.verizon.com/home/5g',
    creditCheckRequired: true,
    createdAt: new Date('2026-01-01T00:00:00Z'),
  },
  {
    id: 'straight-talk-home',
    name: 'Straight Talk Home Internet',
    slug: 'straight-talk-home',
    networkOperator: 'Verizon',
    parentCompany: 'TracFone Wireless / Verizon',
    technology: '5G_FWA',
    tierType: 'prepaid',
    badgeColor: 'green',
    logoUrl: '/images/brands/straight-talk.svg',
    websiteUrl: 'https://www.straighttalk.com/5g-home-internet',
    officialSignupUrl: 'https://www.straighttalk.com/5g-home-internet',
    creditCheckRequired: false,
    createdAt: new Date('2026-01-01T00:00:00Z'),
  },
  {
    id: 'total-wireless-home',
    name: 'Total Wireless Home Internet',
    slug: 'total-wireless-home',
    networkOperator: 'Verizon',
    parentCompany: 'TracFone Wireless / Verizon',
    technology: '5G_FWA',
    tierType: 'prepaid',
    badgeColor: 'orange',
    logoUrl: '/images/brands/total-wireless.svg',
    websiteUrl: 'https://www.totalwireless.com/home-internet',
    officialSignupUrl: 'https://www.totalwireless.com/home-internet',
    creditCheckRequired: false,
    createdAt: new Date('2026-01-01T00:00:00Z'),
  },
  {
    id: 'att-internet-air',
    name: 'AT&T Internet Air',
    slug: 'att-internet-air',
    networkOperator: 'AT&T',
    parentCompany: 'AT&T Inc.',
    technology: '5G_FWA',
    tierType: 'postpaid',
    badgeColor: 'blue',
    logoUrl: '/images/brands/att.svg',
    websiteUrl: 'https://www.att.com/internet/internet-air/',
    officialSignupUrl: 'https://www.att.com/internet/internet-air/',
    creditCheckRequired: true,
    createdAt: new Date('2026-01-01T00:00:00Z'),
  },
  {
    id: 'starlink-residential',
    name: 'Starlink Residential',
    slug: 'starlink-residential',
    networkOperator: 'Starlink',
    parentCompany: 'Space Exploration Technologies Corp. (SpaceX)',
    technology: 'SATELLITE_LEO',
    tierType: 'satellite',
    badgeColor: 'slate',
    logoUrl: '/images/brands/starlink.svg',
    websiteUrl: 'https://www.starlink.com/residential',
    officialSignupUrl: 'https://www.starlink.com/residential',
    creditCheckRequired: false,
    createdAt: new Date('2026-01-01T00:00:00Z'),
  },
];

// -------------------------------------------------------------------------
// 2. PLAN SEEDS
// -------------------------------------------------------------------------
export const PLAN_SEEDS: PlanSeed[] = [
  {
    id: 't-mobile-5g-home-unlimited',
    brandId: 't-mobile-5g-home',
    planName: 'Unlimited 5G Home Internet',
    monthlyPrice: 60.0,
    monthlyPriceRegular: 60.0,
    monthlyPriceAutopay: 50.0,
    monthlyPriceBundled: 40.0,
    bundledRequirement: 'Eligible T-Mobile voice line (e.g., Go5G Plus / Next)',
    downloadMinMbps: 72,
    downloadMaxMbps: 245,
    uploadMinMbps: 15,
    uploadMaxMbps: 31,
    dataCapGb: null,
    isUnlimited: true,
    contractTerms: 'No annual contract',
    priceGuarantee: 'Price Lock Guarantee',
    equipmentFee: 0.0,
    equipmentFeeMonthly: 0.0,
    equipmentUpfrontCost: 0.0,
    equipmentPolicy: 'Wi-Fi 6 Gateway included at no extra charge; return required upon cancellation',
    creditCheckRequired: true,
    officialSignupUrl: 'https://www.t-mobile.com/home-internet',
    keyFeatures: [
      'Wi-Fi 6 Gateway included free ($0 rental)',
      'Unlimited 5G data with no speed or data caps',
      '$50/mo with AutoPay, or $40/mo with qualifying mobile line',
      'Price Lock Guarantee protects your monthly rate',
    ],
    arbitrageNotes: 'Flagship postpaid service on T-Mobile Ultra Capacity 5G. Included gateway rental and soft credit check.',
    promotionalDetails: '$40/mo if bundled with Go5G Plus / Next postpaid mobile voice line.',
  },
  {
    id: 'metro-5g-home-prepaid',
    brandId: 'metro-by-t-mobile',
    planName: 'Metro 5G Home Internet',
    monthlyPrice: 55.0,
    monthlyPriceRegular: 55.0,
    monthlyPriceAutopay: 50.0,
    monthlyPriceBundled: 40.0,
    bundledRequirement: 'Active Metro by T-Mobile phone line',
    downloadMinMbps: 72,
    downloadMaxMbps: 245,
    uploadMinMbps: 15,
    uploadMaxMbps: 31,
    dataCapGb: null,
    isUnlimited: true,
    contractTerms: 'Prepaid / No contract',
    priceGuarantee: 'Flat rate pricing',
    equipmentFee: 0.0,
    equipmentFeeMonthly: 0.0,
    equipmentUpfrontCost: 49.0,
    equipmentPolicy: 'Promotional gateway purchase ($49 with instant rebate, regular $99); customer owns equipment',
    creditCheckRequired: false,
    officialSignupUrl: 'https://www.metrobyt-mobile.com/home-internet',
    keyFeatures: [
      'No credit check required',
      'Uses same physical T-Mobile 5G network towers',
      '$40/mo promotional price when bundled with Metro phone line',
      'Customer owns router hardware after purchase',
    ],
    arbitrageNotes: 'Identical cell tower footprint to T-Mobile Postpaid at lower monthly cost, with $49 upfront hardware purchase.',
    promotionalDetails: '$40/mo promo rate available with active Metro phone line.',
  },
  {
    id: 'verizon-5g-home-standard',
    brandId: 'verizon-5g-home',
    planName: 'Verizon 5G Home',
    monthlyPrice: 60.0,
    monthlyPriceRegular: 60.0,
    monthlyPriceAutopay: 50.0,
    monthlyPriceBundled: 35.0,
    bundledRequirement: 'Verizon Unlimited Plus or Unlimited Ultimate mobile plan',
    downloadMinMbps: 85,
    downloadMaxMbps: 300,
    uploadMinMbps: 10,
    uploadMaxMbps: 20,
    dataCapGb: null,
    isUnlimited: true,
    contractTerms: 'No annual contract',
    priceGuarantee: '2-Year Price Guarantee',
    equipmentFee: 0.0,
    equipmentFeeMonthly: 0.0,
    equipmentUpfrontCost: 0.0,
    equipmentPolicy: 'Verizon Internet Gateway included at $0 cost; return required upon cancellation',
    creditCheckRequired: true,
    officialSignupUrl: 'https://www.verizon.com/home/5g',
    keyFeatures: [
      'Verizon Internet Gateway included at $0 cost',
      '$35/mo with qualifying Verizon Unlimited mobile plan',
      '2-Year Price Guarantee with no hidden price hikes',
      'Unlimited high-speed 5G data',
    ],
    arbitrageNotes: 'Postpaid flagship on Verizon 5G Ultra Wideband. Maximum savings ($35/mo) requires existing Verizon mobile voice line.',
    promotionalDetails: 'Save up to $25/mo when bundled with select 5G mobile phone plans.',
  },
  {
    id: 'straight-talk-home-standard',
    brandId: 'straight-talk-home',
    planName: 'Straight Talk 5G Home Internet',
    monthlyPrice: 45.0,
    monthlyPriceRegular: 45.0,
    monthlyPriceAutopay: 40.0,
    monthlyPriceBundled: null,
    bundledRequirement: null,
    downloadMinMbps: 25,
    downloadMaxMbps: 100,
    uploadMinMbps: 5,
    uploadMaxMbps: 10,
    dataCapGb: null,
    isUnlimited: true,
    contractTerms: 'Prepaid / No contract',
    priceGuarantee: 'Flat rate pricing',
    equipmentFee: 0.0,
    equipmentFeeMonthly: 0.0,
    equipmentUpfrontCost: 99.0,
    equipmentPolicy: 'Router purchase required ($99 one-time at Walmart or online); customer owns router',
    creditCheckRequired: false,
    officialSignupUrl: 'https://www.straighttalk.com/5g-home-internet',
    keyFeatures: [
      'No credit check, no annual contracts',
      'Runs on Verizon 5G and 4G LTE network',
      'Flat $45/mo ($40/mo with Auto-Refill)',
      'Speeds up to 100 Mbps downstream',
    ],
    arbitrageNotes: 'Prepaid Verizon network access through Walmart. Flat $45/mo without requiring mobile line, speed-capped at 100 Mbps.',
    promotionalDetails: '$40/mo with Auto-Refill enrollment.',
  },
  {
    id: 'total-wireless-home-standard',
    brandId: 'total-wireless-home',
    planName: 'Total Wireless 5G Home Internet',
    monthlyPrice: 60.0,
    monthlyPriceRegular: 60.0,
    monthlyPriceAutopay: 45.0,
    monthlyPriceBundled: 35.0,
    bundledRequirement: 'Active Total Wireless Unlimited mobile plan',
    downloadMinMbps: 50,
    downloadMaxMbps: 200,
    uploadMinMbps: 10,
    uploadMaxMbps: 20,
    dataCapGb: null,
    isUnlimited: true,
    contractTerms: 'Prepaid / No contract',
    priceGuarantee: '5-Year Price Guarantee',
    equipmentFee: 0.0,
    equipmentFeeMonthly: 0.0,
    equipmentUpfrontCost: 99.0,
    equipmentPolicy: 'Router purchase required ($99 one-time); customer owns equipment',
    creditCheckRequired: false,
    officialSignupUrl: 'https://www.totalwireless.com/home-internet',
    keyFeatures: [
      'No credit check, no contract',
      'Runs on Verizon 5G Ultra Wideband network',
      '5-Year Price Guarantee protects rate',
      '$35/mo when bundled with Total Wireless Unlimited mobile line',
    ],
    arbitrageNotes: 'Higher speed tier (up to 200 Mbps) than Straight Talk on Verizon towers, with 5-year price guarantee and $35 mobile bundle.',
    promotionalDetails: '$35/mo with Total Wireless Unlimited mobile plan.',
  },
  {
    id: 'att-internet-air-standard',
    brandId: 'att-internet-air',
    planName: 'AT&T Internet Air',
    monthlyPrice: 60.0,
    monthlyPriceRegular: 60.0,
    monthlyPriceAutopay: 60.0,
    monthlyPriceBundled: 35.0,
    bundledRequirement: 'Eligible AT&T postpaid wireless phone plan',
    downloadMinMbps: 75,
    downloadMaxMbps: 225,
    uploadMinMbps: 10,
    uploadMaxMbps: 25,
    dataCapGb: null,
    isUnlimited: true,
    contractTerms: 'No annual contract',
    priceGuarantee: null,
    equipmentFee: 0.0,
    equipmentFeeMonthly: 0.0,
    equipmentUpfrontCost: 0.0,
    equipmentPolicy: 'AT&T All-Fi Hub included at $0 extra charge; return required upon cancellation',
    creditCheckRequired: true,
    officialSignupUrl: 'https://www.att.com/internet/internet-air/',
    keyFeatures: [
      'AT&T All-Fi Hub included free ($0 equipment fee)',
      '$35/mo bundled with AT&T postpaid mobile phone plan',
      'Unlimited data with no overage fees',
      'Quick and easy self-installation via mobile app',
    ],
    arbitrageNotes: 'AT&T 5G fixed wireless offering. Competitive $35/mo rate for existing AT&T mobile subscribers.',
    promotionalDetails: '$25/mo monthly discount when bundled with qualifying AT&T Unlimited mobile voice line.',
  },
  {
    id: 'starlink-residential-standard',
    brandId: 'starlink-residential',
    planName: 'Starlink Residential Standard',
    monthlyPrice: 120.0,
    monthlyPriceRegular: 120.0,
    monthlyPriceAutopay: 120.0,
    monthlyPriceBundled: null,
    bundledRequirement: null,
    downloadMinMbps: 50,
    downloadMaxMbps: 220,
    uploadMinMbps: 5,
    uploadMaxMbps: 25,
    dataCapGb: null,
    isUnlimited: true,
    contractTerms: 'No contract / 30-day trial',
    priceGuarantee: null,
    equipmentFee: 0.0,
    equipmentFeeMonthly: 0.0,
    equipmentUpfrontCost: 599.0,
    equipmentPolicy: 'Standard hardware kit purchase required ($599 one-time); customer owns equipment',
    creditCheckRequired: false,
    officialSignupUrl: 'https://www.starlink.com/residential',
    keyFeatures: [
      '100% universal continental US coverage',
      'Low Earth Orbit (LEO) satellite with 25-50ms latency',
      'No long-term contract (30-day trial)',
      'High-speed rural broadband anywhere with clear sky view',
    ],
    arbitrageNotes: 'Universal satellite baseline for rural areas outside cellular fixed wireless coverage. High equipment purchase cost ($599).',
    promotionalDetails: '30-day trial period with full hardware refund if not satisfied.',
  },
];

// -------------------------------------------------------------------------
// 3. FCC PROVIDER MAPPING SEEDS (Derived from tests/fixtures/fcc-records.json)
// -------------------------------------------------------------------------
export const FCC_PROVIDER_MAPPINGS: FccProviderMappingSeed[] = [
  // T-Mobile USA, Inc. (FRN: 0001565480, Provider ID: 130077, Tech: 71 Licensed Fixed Wireless)
  {
    frn: '0001565480',
    providerId: 130077,
    fccHoldingName: 'T-Mobile USA, Inc.',
    technologyCode: 71,
    brandId: 't-mobile-5g-home',
    isPrimaryBrand: true,
  },
  {
    frn: '0001565480',
    providerId: 130077,
    fccHoldingName: 'T-Mobile USA, Inc.',
    technologyCode: 71,
    brandId: 'metro-by-t-mobile',
    isPrimaryBrand: false,
  },

  // Cellco Partnership (Verizon) (FRN: 0003290673, Provider ID: 130403, Tech: 71 Licensed Fixed Wireless)
  {
    frn: '0003290673',
    providerId: 130403,
    fccHoldingName: 'Cellco Partnership (Verizon)',
    technologyCode: 71,
    brandId: 'verizon-5g-home',
    isPrimaryBrand: true,
  },
  {
    frn: '0003290673',
    providerId: 130403,
    fccHoldingName: 'Cellco Partnership (Verizon)',
    technologyCode: 71,
    brandId: 'straight-talk-home',
    isPrimaryBrand: false,
  },
  {
    frn: '0003290673',
    providerId: 130403,
    fccHoldingName: 'Cellco Partnership (Verizon)',
    technologyCode: 71,
    brandId: 'total-wireless-home',
    isPrimaryBrand: false,
  },

  // Cellco Partnership (Verizon CBRS) (FRN: 0003290673, Provider ID: 130403, Tech: 72 CBRS Shared Wireless)
  {
    frn: '0003290673',
    providerId: 130403,
    fccHoldingName: 'Cellco Partnership (Verizon CBRS)',
    technologyCode: 72,
    brandId: 'verizon-5g-home',
    isPrimaryBrand: true,
  },
  {
    frn: '0003290673',
    providerId: 130403,
    fccHoldingName: 'Cellco Partnership (Verizon CBRS)',
    technologyCode: 72,
    brandId: 'straight-talk-home',
    isPrimaryBrand: false,
  },
  {
    frn: '0003290673',
    providerId: 130403,
    fccHoldingName: 'Cellco Partnership (Verizon CBRS)',
    technologyCode: 72,
    brandId: 'total-wireless-home',
    isPrimaryBrand: false,
  },

  // AT&T Services, Inc. (FRN: 0005050851, Provider ID: 130079, Tech: 71 Licensed Fixed Wireless)
  {
    frn: '0005050851',
    providerId: 130079,
    fccHoldingName: 'AT&T Services, Inc.',
    technologyCode: 71,
    brandId: 'att-internet-air',
    isPrimaryBrand: true,
  },

  // SpaceX Services, Inc. (FRN: 0027768225, Provider ID: 131444, Tech: 61 NGSO LEO Satellite)
  {
    frn: '0027768225',
    providerId: 131444,
    fccHoldingName: 'SpaceX Services, Inc.',
    technologyCode: 61,
    brandId: 'starlink-residential',
    isPrimaryBrand: true,
  },
];
```

---

## 8. Verbatim Source Blueprint: `src/lib/db/seed.ts`

Below is the complete, drop-in TypeScript implementation for `src/lib/db/seed.ts`:

```typescript
import { db } from './index';
import { brands, plans, fccProviderMapping } from './schema';

export interface BrandSeed {
  id: string;
  name: string;
  slug: string;
  networkOperator: string;
  parentCompany: string;
  technology: string;
  tierType: 'postpaid' | 'prepaid' | 'satellite';
  badgeColor: string;
  logoUrl?: string;
  websiteUrl: string;
  officialSignupUrl: string;
  creditCheckRequired: boolean;
  createdAt: Date;
}

export interface PlanSeed {
  id: string;
  brandId: string;
  planName: string;
  monthlyPrice: number;
  monthlyPriceRegular: number;
  monthlyPriceAutopay: number | null;
  monthlyPriceBundled: number | null;
  bundledRequirement: string | null;
  downloadMinMbps: number;
  downloadMaxMbps: number;
  uploadMinMbps: number;
  uploadMaxMbps: number;
  dataCapGb: number | null;
  isUnlimited: boolean;
  contractTerms: string;
  priceGuarantee: string | null;
  equipmentFee: number;
  equipmentFeeMonthly: number;
  equipmentUpfrontCost: number;
  equipmentPolicy: string;
  creditCheckRequired: boolean;
  officialSignupUrl: string;
  keyFeatures: string[];
  arbitrageNotes: string;
  promotionalDetails: string | null;
}

export interface FccProviderMappingSeed {
  frn: string;
  providerId: number;
  fccHoldingName: string;
  technologyCode: number;
  brandId: string;
  isPrimaryBrand: boolean;
}

export const BRAND_SEEDS: BrandSeed[] = [
  {
    id: 't-mobile-5g-home',
    name: 'T-Mobile 5G Home Internet',
    slug: 't-mobile-5g-home',
    networkOperator: 'T-Mobile',
    parentCompany: 'T-Mobile US, Inc.',
    technology: '5G_FWA',
    tierType: 'postpaid',
    badgeColor: 'magenta',
    logoUrl: '/images/brands/t-mobile.svg',
    websiteUrl: 'https://www.t-mobile.com/home-internet',
    officialSignupUrl: 'https://www.t-mobile.com/home-internet',
    creditCheckRequired: true,
    createdAt: new Date('2026-01-01T00:00:00Z'),
  },
  {
    id: 'metro-by-t-mobile',
    name: 'Metro by T-Mobile',
    slug: 'metro-by-t-mobile',
    networkOperator: 'T-Mobile',
    parentCompany: 'T-Mobile US, Inc.',
    technology: '5G_FWA',
    tierType: 'prepaid',
    badgeColor: 'purple',
    logoUrl: '/images/brands/metro.svg',
    websiteUrl: 'https://www.metrobyt-mobile.com/home-internet',
    officialSignupUrl: 'https://www.metrobyt-mobile.com/home-internet',
    creditCheckRequired: false,
    createdAt: new Date('2026-01-01T00:00:00Z'),
  },
  {
    id: 'verizon-5g-home',
    name: 'Verizon 5G Home Internet',
    slug: 'verizon-5g-home',
    networkOperator: 'Verizon',
    parentCompany: 'Verizon Communications Inc.',
    technology: '5G_FWA',
    tierType: 'postpaid',
    badgeColor: 'red',
    logoUrl: '/images/brands/verizon.svg',
    websiteUrl: 'https://www.verizon.com/home/5g',
    officialSignupUrl: 'https://www.verizon.com/home/5g',
    creditCheckRequired: true,
    createdAt: new Date('2026-01-01T00:00:00Z'),
  },
  {
    id: 'straight-talk-home',
    name: 'Straight Talk Home Internet',
    slug: 'straight-talk-home',
    networkOperator: 'Verizon',
    parentCompany: 'TracFone Wireless / Verizon',
    technology: '5G_FWA',
    tierType: 'prepaid',
    badgeColor: 'green',
    logoUrl: '/images/brands/straight-talk.svg',
    websiteUrl: 'https://www.straighttalk.com/5g-home-internet',
    officialSignupUrl: 'https://www.straighttalk.com/5g-home-internet',
    creditCheckRequired: false,
    createdAt: new Date('2026-01-01T00:00:00Z'),
  },
  {
    id: 'total-wireless-home',
    name: 'Total Wireless Home Internet',
    slug: 'total-wireless-home',
    networkOperator: 'Verizon',
    parentCompany: 'TracFone Wireless / Verizon',
    technology: '5G_FWA',
    tierType: 'prepaid',
    badgeColor: 'orange',
    logoUrl: '/images/brands/total-wireless.svg',
    websiteUrl: 'https://www.totalwireless.com/home-internet',
    officialSignupUrl: 'https://www.totalwireless.com/home-internet',
    creditCheckRequired: false,
    createdAt: new Date('2026-01-01T00:00:00Z'),
  },
  {
    id: 'att-internet-air',
    name: 'AT&T Internet Air',
    slug: 'att-internet-air',
    networkOperator: 'AT&T',
    parentCompany: 'AT&T Inc.',
    technology: '5G_FWA',
    tierType: 'postpaid',
    badgeColor: 'blue',
    logoUrl: '/images/brands/att.svg',
    websiteUrl: 'https://www.att.com/internet/internet-air/',
    officialSignupUrl: 'https://www.att.com/internet/internet-air/',
    creditCheckRequired: true,
    createdAt: new Date('2026-01-01T00:00:00Z'),
  },
  {
    id: 'starlink-residential',
    name: 'Starlink Residential',
    slug: 'starlink-residential',
    networkOperator: 'Starlink',
    parentCompany: 'Space Exploration Technologies Corp. (SpaceX)',
    technology: 'SATELLITE_LEO',
    tierType: 'satellite',
    badgeColor: 'slate',
    logoUrl: '/images/brands/starlink.svg',
    websiteUrl: 'https://www.starlink.com/residential',
    officialSignupUrl: 'https://www.starlink.com/residential',
    creditCheckRequired: false,
    createdAt: new Date('2026-01-01T00:00:00Z'),
  },
];

export const PLAN_SEEDS: PlanSeed[] = [
  {
    id: 't-mobile-5g-home-unlimited',
    brandId: 't-mobile-5g-home',
    planName: 'Unlimited 5G Home Internet',
    monthlyPrice: 60.0,
    monthlyPriceRegular: 60.0,
    monthlyPriceAutopay: 50.0,
    monthlyPriceBundled: 40.0,
    bundledRequirement: 'Eligible T-Mobile voice line (e.g., Go5G Plus / Next)',
    downloadMinMbps: 72,
    downloadMaxMbps: 245,
    uploadMinMbps: 15,
    uploadMaxMbps: 31,
    dataCapGb: null,
    isUnlimited: true,
    contractTerms: 'No annual contract',
    priceGuarantee: 'Price Lock Guarantee',
    equipmentFee: 0.0,
    equipmentFeeMonthly: 0.0,
    equipmentUpfrontCost: 0.0,
    equipmentPolicy: 'Wi-Fi 6 Gateway included at no extra charge; return required upon cancellation',
    creditCheckRequired: true,
    officialSignupUrl: 'https://www.t-mobile.com/home-internet',
    keyFeatures: [
      'Wi-Fi 6 Gateway included free ($0 rental)',
      'Unlimited 5G data with no speed or data caps',
      '$50/mo with AutoPay, or $40/mo with qualifying mobile line',
      'Price Lock Guarantee protects your monthly rate',
    ],
    arbitrageNotes: 'Flagship postpaid service on T-Mobile Ultra Capacity 5G. Included gateway rental and soft credit check.',
    promotionalDetails: '$40/mo if bundled with Go5G Plus / Next postpaid mobile voice line.',
  },
  {
    id: 'metro-5g-home-prepaid',
    brandId: 'metro-by-t-mobile',
    planName: 'Metro 5G Home Internet',
    monthlyPrice: 55.0,
    monthlyPriceRegular: 55.0,
    monthlyPriceAutopay: 50.0,
    monthlyPriceBundled: 40.0,
    bundledRequirement: 'Active Metro by T-Mobile phone line',
    downloadMinMbps: 72,
    downloadMaxMbps: 245,
    uploadMinMbps: 15,
    uploadMaxMbps: 31,
    dataCapGb: null,
    isUnlimited: true,
    contractTerms: 'Prepaid / No contract',
    priceGuarantee: 'Flat rate pricing',
    equipmentFee: 0.0,
    equipmentFeeMonthly: 0.0,
    equipmentUpfrontCost: 49.0,
    equipmentPolicy: 'Promotional gateway purchase ($49 with instant rebate, regular $99); customer owns equipment',
    creditCheckRequired: false,
    officialSignupUrl: 'https://www.metrobyt-mobile.com/home-internet',
    keyFeatures: [
      'No credit check required',
      'Uses same physical T-Mobile 5G network towers',
      '$40/mo promotional price when bundled with Metro phone line',
      'Customer owns router hardware after purchase',
    ],
    arbitrageNotes: 'Identical cell tower footprint to T-Mobile Postpaid at lower monthly cost, with $49 upfront hardware purchase.',
    promotionalDetails: '$40/mo promo rate available with active Metro phone line.',
  },
  {
    id: 'verizon-5g-home-standard',
    brandId: 'verizon-5g-home',
    planName: 'Verizon 5G Home',
    monthlyPrice: 60.0,
    monthlyPriceRegular: 60.0,
    monthlyPriceAutopay: 50.0,
    monthlyPriceBundled: 35.0,
    bundledRequirement: 'Verizon Unlimited Plus or Unlimited Ultimate mobile plan',
    downloadMinMbps: 85,
    downloadMaxMbps: 300,
    uploadMinMbps: 10,
    uploadMaxMbps: 20,
    dataCapGb: null,
    isUnlimited: true,
    contractTerms: 'No annual contract',
    priceGuarantee: '2-Year Price Guarantee',
    equipmentFee: 0.0,
    equipmentFeeMonthly: 0.0,
    equipmentUpfrontCost: 0.0,
    equipmentPolicy: 'Verizon Internet Gateway included at $0 cost; return required upon cancellation',
    creditCheckRequired: true,
    officialSignupUrl: 'https://www.verizon.com/home/5g',
    keyFeatures: [
      'Verizon Internet Gateway included at $0 cost',
      '$35/mo with qualifying Verizon Unlimited mobile plan',
      '2-Year Price Guarantee with no hidden price hikes',
      'Unlimited high-speed 5G data',
    ],
    arbitrageNotes: 'Postpaid flagship on Verizon 5G Ultra Wideband. Maximum savings ($35/mo) requires existing Verizon mobile voice line.',
    promotionalDetails: 'Save up to $25/mo when bundled with select 5G mobile phone plans.',
  },
  {
    id: 'straight-talk-home-standard',
    brandId: 'straight-talk-home',
    planName: 'Straight Talk 5G Home Internet',
    monthlyPrice: 45.0,
    monthlyPriceRegular: 45.0,
    monthlyPriceAutopay: 40.0,
    monthlyPriceBundled: null,
    bundledRequirement: null,
    downloadMinMbps: 25,
    downloadMaxMbps: 100,
    uploadMinMbps: 5,
    uploadMaxMbps: 10,
    dataCapGb: null,
    isUnlimited: true,
    contractTerms: 'Prepaid / No contract',
    priceGuarantee: 'Flat rate pricing',
    equipmentFee: 0.0,
    equipmentFeeMonthly: 0.0,
    equipmentUpfrontCost: 99.0,
    equipmentPolicy: 'Router purchase required ($99 one-time at Walmart or online); customer owns router',
    creditCheckRequired: false,
    officialSignupUrl: 'https://www.straighttalk.com/5g-home-internet',
    keyFeatures: [
      'No credit check, no annual contracts',
      'Runs on Verizon 5G and 4G LTE network',
      'Flat $45/mo ($40/mo with Auto-Refill)',
      'Speeds up to 100 Mbps downstream',
    ],
    arbitrageNotes: 'Prepaid Verizon network access through Walmart. Flat $45/mo without requiring mobile line, speed-capped at 100 Mbps.',
    promotionalDetails: '$40/mo with Auto-Refill enrollment.',
  },
  {
    id: 'total-wireless-home-standard',
    brandId: 'total-wireless-home',
    planName: 'Total Wireless 5G Home Internet',
    monthlyPrice: 60.0,
    monthlyPriceRegular: 60.0,
    monthlyPriceAutopay: 45.0,
    monthlyPriceBundled: 35.0,
    bundledRequirement: 'Active Total Wireless Unlimited mobile plan',
    downloadMinMbps: 50,
    downloadMaxMbps: 200,
    uploadMinMbps: 10,
    uploadMaxMbps: 20,
    dataCapGb: null,
    isUnlimited: true,
    contractTerms: 'Prepaid / No contract',
    priceGuarantee: '5-Year Price Guarantee',
    equipmentFee: 0.0,
    equipmentFeeMonthly: 0.0,
    equipmentUpfrontCost: 99.0,
    equipmentPolicy: 'Router purchase required ($99 one-time); customer owns equipment',
    creditCheckRequired: false,
    officialSignupUrl: 'https://www.totalwireless.com/home-internet',
    keyFeatures: [
      'No credit check, no contract',
      'Runs on Verizon 5G Ultra Wideband network',
      '5-Year Price Guarantee protects rate',
      '$35/mo when bundled with Total Wireless Unlimited mobile line',
    ],
    arbitrageNotes: 'Higher speed tier (up to 200 Mbps) than Straight Talk on Verizon towers, with 5-year price guarantee and $35 mobile bundle.',
    promotionalDetails: '$35/mo with Total Wireless Unlimited mobile plan.',
  },
  {
    id: 'att-internet-air-standard',
    brandId: 'att-internet-air',
    planName: 'AT&T Internet Air',
    monthlyPrice: 60.0,
    monthlyPriceRegular: 60.0,
    monthlyPriceAutopay: 60.0,
    monthlyPriceBundled: 35.0,
    bundledRequirement: 'Eligible AT&T postpaid wireless phone plan',
    downloadMinMbps: 75,
    downloadMaxMbps: 225,
    uploadMinMbps: 10,
    uploadMaxMbps: 25,
    dataCapGb: null,
    isUnlimited: true,
    contractTerms: 'No annual contract',
    priceGuarantee: null,
    equipmentFee: 0.0,
    equipmentFeeMonthly: 0.0,
    equipmentUpfrontCost: 0.0,
    equipmentPolicy: 'AT&T All-Fi Hub included at $0 extra charge; return required upon cancellation',
    creditCheckRequired: true,
    officialSignupUrl: 'https://www.att.com/internet/internet-air/',
    keyFeatures: [
      'AT&T All-Fi Hub included free ($0 equipment fee)',
      '$35/mo bundled with AT&T postpaid mobile phone plan',
      'Unlimited data with no overage fees',
      'Quick and easy self-installation via mobile app',
    ],
    arbitrageNotes: 'AT&T 5G fixed wireless offering. Competitive $35/mo rate for existing AT&T mobile subscribers.',
    promotionalDetails: '$25/mo monthly discount when bundled with qualifying AT&T Unlimited mobile voice line.',
  },
  {
    id: 'starlink-residential-standard',
    brandId: 'starlink-residential',
    planName: 'Starlink Residential Standard',
    monthlyPrice: 120.0,
    monthlyPriceRegular: 120.0,
    monthlyPriceAutopay: 120.0,
    monthlyPriceBundled: null,
    bundledRequirement: null,
    downloadMinMbps: 50,
    downloadMaxMbps: 220,
    uploadMinMbps: 5,
    uploadMaxMbps: 25,
    dataCapGb: null,
    isUnlimited: true,
    contractTerms: 'No contract / 30-day trial',
    priceGuarantee: null,
    equipmentFee: 0.0,
    equipmentFeeMonthly: 0.0,
    equipmentUpfrontCost: 599.0,
    equipmentPolicy: 'Standard hardware kit purchase required ($599 one-time); customer owns equipment',
    creditCheckRequired: false,
    officialSignupUrl: 'https://www.starlink.com/residential',
    keyFeatures: [
      '100% universal continental US coverage',
      'Low Earth Orbit (LEO) satellite with 25-50ms latency',
      'No long-term contract (30-day trial)',
      'High-speed rural broadband anywhere with clear sky view',
    ],
    arbitrageNotes: 'Universal satellite baseline for rural areas outside cellular fixed wireless coverage. High equipment purchase cost ($599).',
    promotionalDetails: '30-day trial period with full hardware refund if not satisfied.',
  },
];

export const FCC_PROVIDER_MAPPINGS: FccProviderMappingSeed[] = [
  {
    frn: '0001565480',
    providerId: 130077,
    fccHoldingName: 'T-Mobile USA, Inc.',
    technologyCode: 71,
    brandId: 't-mobile-5g-home',
    isPrimaryBrand: true,
  },
  {
    frn: '0001565480',
    providerId: 130077,
    fccHoldingName: 'T-Mobile USA, Inc.',
    technologyCode: 71,
    brandId: 'metro-by-t-mobile',
    isPrimaryBrand: false,
  },
  {
    frn: '0003290673',
    providerId: 130403,
    fccHoldingName: 'Cellco Partnership (Verizon)',
    technologyCode: 71,
    brandId: 'verizon-5g-home',
    isPrimaryBrand: true,
  },
  {
    frn: '0003290673',
    providerId: 130403,
    fccHoldingName: 'Cellco Partnership (Verizon)',
    technologyCode: 71,
    brandId: 'straight-talk-home',
    isPrimaryBrand: false,
  },
  {
    frn: '0003290673',
    providerId: 130403,
    fccHoldingName: 'Cellco Partnership (Verizon)',
    technologyCode: 71,
    brandId: 'total-wireless-home',
    isPrimaryBrand: false,
  },
  {
    frn: '0003290673',
    providerId: 130403,
    fccHoldingName: 'Cellco Partnership (Verizon CBRS)',
    technologyCode: 72,
    brandId: 'verizon-5g-home',
    isPrimaryBrand: true,
  },
  {
    frn: '0003290673',
    providerId: 130403,
    fccHoldingName: 'Cellco Partnership (Verizon CBRS)',
    technologyCode: 72,
    brandId: 'straight-talk-home',
    isPrimaryBrand: false,
  },
  {
    frn: '0003290673',
    providerId: 130403,
    fccHoldingName: 'Cellco Partnership (Verizon CBRS)',
    technologyCode: 72,
    brandId: 'total-wireless-home',
    isPrimaryBrand: false,
  },
  {
    frn: '0005050851',
    providerId: 130079,
    fccHoldingName: 'AT&T Services, Inc.',
    technologyCode: 71,
    brandId: 'att-internet-air',
    isPrimaryBrand: true,
  },
  {
    frn: '0027768225',
    providerId: 131444,
    fccHoldingName: 'SpaceX Services, Inc.',
    technologyCode: 61,
    brandId: 'starlink-residential',
    isPrimaryBrand: true,
  },
];

/**
 * Idempotently seeds the SQLite database with brands, plans, and FCC mappings.
 * Can be called programmatically (in test setups) or executed directly via CLI (`npm run db:seed`).
 */
export async function seedDatabase(database = db): Promise<void> {
  // Execute within transaction or sequential clean-insert to ensure foreign key integrity
  // 1. Clean existing records in reverse dependency order
  await database.delete(fccProviderMapping).execute();
  await database.delete(plans).execute();
  await database.delete(brands).execute();

  // 2. Insert Brands
  for (const brand of BRAND_SEEDS) {
    await database.insert(brands).values({
      id: brand.id,
      name: brand.name,
      slug: brand.slug,
      networkOperator: brand.networkOperator,
      parentCompany: brand.parentCompany,
      technology: brand.technology,
      tierType: brand.tierType,
      badgeColor: brand.badgeColor,
      logoUrl: brand.logoUrl,
      websiteUrl: brand.websiteUrl,
      officialSignupUrl: brand.officialSignupUrl,
      creditCheckRequired: brand.creditCheckRequired,
      createdAt: brand.createdAt,
    }).execute();
  }

  // 3. Insert Plans
  for (const plan of PLAN_SEEDS) {
    await database.insert(plans).values({
      id: plan.id,
      brandId: plan.brandId,
      planName: plan.planName,
      monthlyPrice: plan.monthlyPrice,
      monthlyPriceRegular: plan.monthlyPriceRegular,
      monthlyPriceAutopay: plan.monthlyPriceAutopay,
      monthlyPriceBundled: plan.monthlyPriceBundled,
      bundledRequirement: plan.bundledRequirement,
      downloadMinMbps: plan.downloadMinMbps,
      downloadMaxMbps: plan.downloadMaxMbps,
      uploadMinMbps: plan.uploadMinMbps,
      uploadMaxMbps: plan.uploadMaxMbps,
      dataCapGb: plan.dataCapGb,
      isUnlimited: plan.isUnlimited,
      contractTerms: plan.contractTerms,
      priceGuarantee: plan.priceGuarantee,
      equipmentFee: plan.equipmentFee,
      equipmentFeeMonthly: plan.equipmentFeeMonthly,
      equipmentUpfrontCost: plan.equipmentUpfrontCost,
      equipmentPolicy: plan.equipmentPolicy,
      creditCheckRequired: plan.creditCheckRequired,
      officialSignupUrl: plan.officialSignupUrl,
      promotionalDetails: plan.promotionalDetails,
    }).execute();
  }

  // 4. Insert FCC Provider Mappings
  for (const mapping of FCC_PROVIDER_MAPPINGS) {
    await database.insert(fccProviderMapping).values({
      frn: mapping.frn,
      providerId: mapping.providerId,
      fccHoldingName: mapping.fccHoldingName,
      technologyCode: mapping.technologyCode,
      brandId: mapping.brandId,
      isPrimaryBrand: mapping.isPrimaryBrand,
    }).execute();
  }
}

// Auto-run if executed directly via CLI: `tsx src/lib/db/seed.ts`
if (require.main === module || (typeof process !== 'undefined' && process.argv[1]?.includes('seed.ts'))) {
  seedDatabase()
    .then(() => {
      console.log('✓ Successfully seeded 7 retail brands, 7 plans, and 10 FCC provider mappings.');
      process.exit(0);
    })
    .catch((err) => {
      console.error('✗ Failed to seed database:', err);
      process.exit(1);
    });
}
```
