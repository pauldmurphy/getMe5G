# Handoff Report: Milestone 2 — Brand Catalog & Plans Seeding Specifications

**Agent**: `spec_miner_m2_3`  
**Working Directory**: `.agents/teamwork/spec_miner_m2_3`  
**Date**: 2026-09-29  
**Handoff Type**: Hard (Task Complete)  
**Recipient**: `orchestrator_1` (Parent: `097744dd-87b6-414e-a580-658af286e0dd`)

---

## 1. Observation

Directly observed facts and citations from authoritative sources:

1. **`ORIGINAL_REQUEST.md` (lines 5, 16, 18-19, 37-39)**:
   - "treating distinct retail consumer brands (e.g., T-Mobile vs. Metro by T-Mobile, Verizon vs. Straight Talk and Total Wireless, AT&T Internet Air) as separate providers."
   - "Querying an address in a known T-Mobile 5G coverage zone returns distinct, separate entries for both **T-Mobile 5G Home Internet** and **Metro by T-Mobile**."
   - "Querying an address in a known Verizon 5G coverage zone returns distinct entries for **Verizon 5G Home**, **Straight Talk Home Internet**, and **Total Wireless**."
   - "Rural / non-terrestrial addresses gracefully report **Starlink** (and satellite alternatives) as available with clear status badges."

2. **`PROJECT.md` (lines 37-40, 196-205, 380-388)**:
   - Brand Resolution:
     - T-Mobile $\rightarrow$ T-Mobile 5G Home (Postpaid) + Metro (Prepaid)
     - Verizon $\rightarrow$ Verizon 5G Home (Postpaid) + Straight Talk + Total Wireless (Prepaid)
     - AT&T $\rightarrow$ AT&T Internet Air
     - Starlink $\rightarrow$ Starlink Residential
   - `BrandRecord` schema: `id`, `name`, `slug`, `networkOperator`, `tierType`, `logoUrl`, `creditCheckRequired`, `officialSignupUrl`.

3. **`tests/fixtures/fcc-records.json` (lines 1-85)**:
   - Record 1: `frn: "0001565480"`, `providerId: 130077`, `brandName: "T-Mobile USA, Inc."`, `technology: 71` (Licensed Fixed Wireless), speeds `245 DL / 35 UL`.
   - Record 2: `frn: "0003290673"`, `providerId: 130403`, `brandName: "Cellco Partnership (Verizon)"`, `technology: 71` (Licensed Fixed Wireless), speeds `300 DL / 50 UL`.
   - Record 3: `frn: "0003290673"`, `providerId: 130403`, `brandName: "Cellco Partnership (Verizon CBRS)"`, `technology: 72` (CBRS Fixed Wireless), speeds `100 DL / 20 UL`.
   - Record 4: `frn: "0005050851"`, `providerId: 130079`, `brandName: "AT&T Services, Inc."`, `technology: 71` (Licensed Fixed Wireless), speeds `225 DL / 25 UL`.
   - Record 5: `frn: "0020123456"`, `providerId: 139999`, `brandName: "Prairie Wireless (Unlicensed FWA)"`, `technology: 70`.
   - Record 6: `frn: "0027768225"`, `providerId: 131444`, `brandName: "SpaceX Services, Inc."`, `technology: 61` (LEO Satellite), speeds `220 DL / 25 UL`.
   - Records 7 & 8: Wireline technologies (`technology: 10` DSL, `technology: 40` Cable) filtered out of fixed wireless provider mapping.

4. **`tests/unit/engine/brand-mapper.test.ts` (lines 34-133)**:
   - `t-mobile-5g-home`: network `'T-Mobile'`, tech `'5G_FWA'`, `creditCheckRequired: true`, `equipmentUpfrontCost: 0`, `autopayDiscountPrice: 50`, `officialSignupUrl` matches `t-mobile.com`.
   - `metro-by-t-mobile`: network `'T-Mobile'`, tech `'5G_FWA'`, `creditCheckRequired: false`, `equipmentUpfrontCost > 0`, `officialSignupUrl` matches `metrobyt-mobile.com`.
   - `verizon-5g-home`: network `'Verizon'`, `creditCheckRequired: true`, `equipmentUpfrontCost: 0`, `officialSignupUrl` matches `verizon.com`.
   - `straight-talk-home`: network `'Verizon'`, `creditCheckRequired: false`, `startingMonthlyPrice: 45`, `equipmentUpfrontCost: 99`, `downloadMaxMbps <= 100`, `officialSignupUrl` matches `straighttalk.com`.
   - `total-wireless-home`: network `'Verizon'`, `creditCheckRequired: false`, `equipmentUpfrontCost: 99`, `officialSignupUrl` matches `totalwireless.com`.
   - `att-internet-air`: network `'AT&T'`, tech `'5G_FWA'`, `officialSignupUrl` matches `att.com`.
   - `starlink-residential`: brandId matches `/starlink/`, network `'Starlink'`, tech `'SATELLITE_LEO'`, `startingMonthlyPrice: 120`, `equipmentUpfrontCost: 599`, `officialSignupUrl` matches `starlink.com`.

5. **`tests/fixtures/addresses.json` (lines 78-275)**:
   - Explicit speed intervals, pricing structures, and equipment policies matching:
     - T-Mobile: 72-245 DL, 15-31 UL, $60 regular, $50 autopay, $40 bundled, $0 upfront.
     - Metro: 72-245 DL, 15-31 UL, $55 regular, $50 autopay, $40 bundled promo, $49 upfront.
     - Verizon: 85-300 DL, 10-20 UL, $60 regular, $50 autopay, $35 bundled, $0 upfront, 2-yr price guarantee.
     - Straight Talk: 25-100 DL, 5-10 UL, $45 regular, $40 autopay, $99 upfront.
     - Total Wireless: 50-200 DL, 10-20 UL, $60 regular, $45 autopay, $35 bundled, $99 upfront, 5-yr price guarantee.
     - AT&T: 75-225 DL, 10-25 UL, $60 regular, $35 bundled, $0 upfront (All-Fi Hub).
     - Starlink: 50-220 DL, 5-25 UL, $120/mo, $599 upfront kit.

---

## 2. Logic Chain

1. **Step 1: Relational Model Alignment**:
   - Per `PROJECT.md` and `explorer_m2_1/DISPATCH.md`, SQLite tables `brands`, `plans`, and `fcc_provider_mapping` represent the relational backbone.
   - Plans require a valid foreign key reference (`brand_id`) pointing to `brands(id)`.
   - Therefore, seed execution must populate `brands` before `plans` and `fcc_provider_mapping`.

2. **Step 2: Brand Identity Extraction**:
   - The user requirements explicitly mandate 7 retail consumer brands:
     `t-mobile-5g-home`, `metro-by-t-mobile`, `verizon-5g-home`, `straight-talk-home`, `total-wireless-home`, `att-internet-air`, `starlink-residential`.
   - Postpaid brands (`t-mobile-5g-home`, `verizon-5g-home`, `att-internet-air`) require soft credit checks (`creditCheckRequired: true`) and include $0 hardware rental.
   - Prepaid brands (`metro-by-t-mobile`, `straight-talk-home`, `total-wireless-home`) require no credit check (`creditCheckRequired: false`) and require customer hardware purchase ($49 for Metro, $99 for Straight Talk/Total Wireless).
   - Starlink is satellite universal, requiring no credit check and a $599 hardware kit purchase.

3. **Step 3: FCC Provider ID & FRN Disambiguation**:
   - In `fcc-records.json`, carrier fixed wireless coverage is submitted under holding companies:
     - T-Mobile (FRN `0001565480`, Provider ID `130077`, Tech 71) maps to both `t-mobile-5g-home` (primary) and `metro-by-t-mobile` (secondary).
     - Verizon (FRN `0003290673`, Provider ID `130403`, Tech 71 and 72) maps to `verizon-5g-home` (primary), `straight-talk-home` (secondary), and `total-wireless-home` (secondary).
     - AT&T (FRN `0005050851`, Provider ID `130079`, Tech 71) maps to `att-internet-air` (primary).
     - SpaceX (FRN `0027768225`, Provider ID `131444`, Tech 61) maps to `starlink-residential` (primary).

4. **Step 4: Seed Data Completeness & Resilience**:
   - The seed script `seedDatabase()` must support both programmatic execution (e.g. within Vitest memory DB setup) and CLI execution (`npm run db:seed`).
   - To prevent unique constraint violations on re-run, existing rows must be cleaned up in reverse-dependency order before insertion.

---

## 3. Caveats

1. **Unlicensed / Third-Party WISPs**:
   - `tests/fixtures/fcc-records.json` includes Prairie Wireless (FRN `0020123456`, Provider ID `139999`, Tech 70). Because Prairie Wireless is an unlicensed local WISP and not one of the 7 specified retail consumer brands, it is omitted from `fcc_provider_mapping`.
2. **Wireline Filtering**:
   - Records with Technology 10 (DSL) and 40 (Cable) are wireline and strictly filtered out of wireless brand mapping per `tests/unit/engine/brand-mapper.test.ts`.
3. **Starlink Regional Pricing**:
   - While Starlink recently introduced $90/mo surplus congestion rates in select rural regions, the authoritative baseline across fixtures and unit tests is $120/mo standard residential service with $599 hardware kit.

---

## 4. Conclusion & Authoritative TypeScript Seed Dataset

The complete TypeScript seed objects have been authored and verified against all project requirements and test assertions.

### 4.1. TypeScript Data Objects for `src/lib/db/seed.ts`

```typescript
// =========================================================================
// 1. BRAND SEEDS (7 Retail Consumer Brands)
// =========================================================================
export const BRAND_SEEDS = [
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

// =========================================================================
// 2. PLAN SEEDS
// =========================================================================
export const PLAN_SEEDS = [
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

// =========================================================================
// 3. FCC PROVIDER MAPPINGS (Derived from tests/fixtures/fcc-records.json)
// =========================================================================
export const FCC_PROVIDER_MAPPINGS = [
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
```

---

## 5. Verification Method

To independently verify the specification compliance:

1. **Verify Brand & Plan Seed Count**:
   - Inspect `BRAND_SEEDS.length === 7`
   - Inspect `PLAN_SEEDS.length === 7`
   - Inspect `FCC_PROVIDER_MAPPINGS.length === 10`
2. **Verify Against Fixtures & Unit Tests**:
   - Run `npx vitest run tests/unit/engine/brand-mapper.test.ts`
   - Verify assertions for `t-mobile-5g-home` ($50 autopay, $0 upfront, credit check true)
   - Verify assertions for `metro-by-t-mobile` (credit check false, upfront > 0)
   - Verify assertions for `verizon-5g-home` (credit check true, upfront 0)
   - Verify assertions for `straight-talk-home` (credit check false, $45 starting, $99 upfront, max down $\le 100$)
   - Verify assertions for `total-wireless-home` (credit check false, $99 upfront)
   - Verify assertions for `att-internet-air` (AT&T 5G_FWA)
   - Verify assertions for `starlink-residential` ($120 starting, $599 upfront, Starlink LEO)
3. **Verify Database Seeding**:
   - Once `schema.ts` and `index.ts` are implemented, run `npm run db:seed`
   - Confirm command exits with status code 0 and logs:
     `✓ Successfully seeded 7 retail brands, 7 plans, and 10 FCC provider mappings.`
