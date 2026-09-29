# Technical Blueprint & Architecture Analysis: Drizzle ORM SQLite Schema & Client Singleton

**Milestone**: Milestone 2 — Drizzle ORM SQLite Schema & Client  
**Author**: `explorer_m2_1`  
**Date**: 2026-09-29  
**Status**: Ready for Implementation  

---

## 1. Executive Summary

Milestone 2 establishes the persistence and caching foundation for the 5G Arbitrage Engine. The database layer has two critical responsibilities:
1. **Rich Retail Catalog Persistence**: Managing the relational data model for retail consumer brands (`brands`), pricing and performance tiers (`plans`), and their regulatory cross-references to the FCC Broadband Data Collection dataset (`fcc_provider_mapping`).
2. **High-Speed Query Cache Layer**: Providing persistent L2 coordinate query caching (`coordinate_lookup_cache`) using spatial hashing (`lat.toFixed(4):lng.toFixed(4)`) to deliver sub-25ms response times on repeat or neighboring queries.

This blueprint provides the exact architecture, DDL specifications, and production-ready TypeScript code for:
- `src/lib/db/schema.ts`: Drizzle SQLite table definitions, foreign keys, cascading deletions, indexes, relations, and inferred TypeScript types.
- `src/lib/db/index.ts`: A robust, hot-reloading safe `better-sqlite3` client singleton with auto-bootstrapping schema creation (zero-config, no separate migration step required), WAL pragma configuration, and seamless `:memory:` mode support for Vitest test suites.

---

## 2. Evidence & Codebase Observations

1. **`drizzle.config.ts`**:
   - Points schema to `'./src/lib/db/schema.ts'`.
   - Dialect is `'sqlite'`.
   - Credentials URL defaults to `process.env.DATABASE_URL || './data/getme5g.sqlite'`.
2. **`package.json`**:
   - Dependencies: `drizzle-orm` (`^0.33.0`), `better-sqlite3` (`^11.3.0`), `lru-cache` (`^10.4.3`).
   - DevDependencies: `drizzle-kit` (`^0.24.2`), `tsx` (`^4.19.1`), `vitest` (`^2.1.1`).
   - Script `"db:seed": "tsx src/lib/db/seed.ts"`.
3. **`tests/unit/db/cache.test.ts`**:
   - Requires `AvailabilityCacheService` which writes to and queries from SQLite coordinate cache.
   - Relies on in-memory execution during Vitest runs (`:memory:` mode).
   - Validates that clearing cache (`clearAll()`) and falling back to L2 cache (`layer: 'l2_db'`) operate reliably.
4. **`tests/fixtures/fcc-records.json` & `addresses.json`**:
   - Documents the 7 retail consumer brands:
     1. T-Mobile 5G Home Internet (`t-mobile-5g-home`)
     2. Metro by T-Mobile (`metro-by-t-mobile`)
     3. Verizon 5G Home (`verizon-5g-home`)
     4. Straight Talk Home Internet (`straight-talk-home`)
     5. Total Wireless Home Internet (`total-wireless-home`)
     6. AT&T Internet Air (`att-internet-air`)
     7. Starlink Residential (`starlink-residential`)
   - Confirms that multiple retail brands (e.g. T-Mobile Postpaid & Metro Prepaid; Verizon Postpaid, Straight Talk & Total Wireless) share identical FCC FRN and Provider IDs (`0001565480` / `130077` and `0003290673` / `130403`).

---

## 3. Schema Design (`src/lib/db/schema.ts`)

### 3.1 Entity Relationship Diagram

```
+-------------------------------------------------------------+
|                           brands                            |
+-------------------------------------------------------------+
| * id: TEXT (PK)                                             |
|   name: TEXT NOT NULL                                       |
|   slug: TEXT NOT NULL UNIQUE                                |
|   network_operator: TEXT NOT NULL                           |
|   tier_type: TEXT NOT NULL                                  |
|   logo_url: TEXT                                            |
|   credit_check_required: INTEGER NOT NULL (boolean)         |
|   official_signup_url: TEXT NOT NULL                        |
|   created_at: INTEGER (timestamp)                           |
+------------------------------+------------------------------+
                               | 1
                               |
               +---------------+---------------+
               |                               |
               | 1..*                          | 1..*
+--------------v---------------+ +-------------v---------------+
|            plans             | |    fcc_provider_mapping     |
+------------------------------+ +-----------------------------+
| * id: TEXT (PK)              | | * id: INTEGER (PK AUTOINC)  |
| * brand_id: TEXT (FK)        | |   frn: TEXT NOT NULL        |
|   plan_name: TEXT NOT NULL   | |   provider_id: INT NOT NULL |
|   monthly_price: REAL NOT NULL| | * brand_id: TEXT (FK)       |
|   autopay_discount_price: REAL| |   technology_code: INT NOT NULL
|   bundled_price: REAL        | +-----------------------------+
|   download_min_mbps: INTEGER |
|   download_max_mbps: INTEGER |
|   upload_min_mbps: INTEGER   |
|   upload_max_mbps: INTEGER   |
|   equipment_fee: REAL (def 0)|
|   equipment_upfront_cost: REAL|
|   contract_terms: TEXT NOT NULL|
|   price_guarantee: TEXT      |
+------------------------------+

+-------------------------------------------------------------+
|                  coordinate_lookup_cache                    |
+-------------------------------------------------------------+
| * cache_key: TEXT (PK)  -- "lat.toFixed(4):lng.toFixed(4)"  |
|   address_json: TEXT NOT NULL                               |
|   results_json: TEXT NOT NULL                               |
|   created_at: INTEGER NOT NULL (timestamp)                  |
|   expires_at: INTEGER NOT NULL (timestamp)                  |
+-------------------------------------------------------------+
```

### 3.2 Table Field Analysis & Rationale

#### 1. `brands` Table
Stores retail consumer identities operating on MNO cellular or satellite networks.
- `id` (Text PK): Machine-readable identifier matching test assertions (e.g. `'t-mobile-5g-home'`, `'metro-by-t-mobile'`).
- `name` (Text Not Null): Human-readable brand name (e.g. `'T-Mobile 5G Home Internet'`).
- `slug` (Text Not Null Unique): URL-safe brand slug for SEO routing and filter chips.
- `networkOperator` / `network_operator` (Text Not Null): Physical infrastructure provider (`'T-Mobile'`, `'Verizon'`, `'AT&T'`, `'Starlink'`).
- `tierType` / `tier_type` (Text Not Null): `'postpaid'`, `'prepaid'`, or `'satellite'`.
- `logoUrl` / `logo_url` (Text Nullable): Static asset path (e.g. `'/images/brands/t-mobile.svg'`).
- `creditCheckRequired` / `credit_check_required` (Integer Mode Boolean Not Null): Discriminates between postpaid (credit check required) and prepaid/satellite (no credit check), which is a key arbitrage criterion for unbanked consumers.
- `officialSignupUrl` / `official_signup_url` (Text Not Null): Official direct consumer signup link.
- `createdAt` / `created_at` (Integer Mode Timestamp): Insertion timestamp.

#### 2. `plans` Table
Stores specific consumer pricing tiers and speed disclosures.
- `id` (Text PK): e.g. `'t-mobile-5g-home-standard'`, `'vz-5g-home-plus'`.
- `brandId` / `brand_id` (Text FK Not Null): References `brands.id` with `ON DELETE CASCADE`.
- `planName` / `plan_name` (Text Not Null): Plan tier label (e.g. `'Standard Unlimited'`, `'Home Plus'`).
- `monthlyPrice` / `monthly_price` (Real Not Null): Base monthly fee before discounts.
- `autopayDiscountPrice` / `autopay_discount_price` (Real Nullable): Monthly fee with AutoPay applied.
- `bundledPrice` / `bundled_price` (Real Nullable): Discounted price if customer has qualifying mobile voice lines.
- `downloadMinMbps` / `download_min_mbps` (Integer Not Null): Bottom advertised download speed.
- `downloadMaxMbps` / `download_max_mbps` (Integer Not Null): Top advertised download speed.
- `uploadMinMbps` / `upload_min_mbps` (Integer Not Null): Bottom advertised upload speed.
- `uploadMaxMbps` / `upload_max_mbps` (Integer Not Null): Top advertised upload speed.
- `equipmentFee` / `equipment_fee` (Real Not Null Default 0): Ongoing monthly modem rental fee ($0 for all modern 5G gateways).
- `equipmentUpfrontCost` / `equipment_upfront_cost` (Real Not Null Default 0): Hardware kit or purchase cost ($0 for postpaid loaners, $49-$99 for prepaid retail purchases, $349-$599 for Starlink).
- `contractTerms` / `contract_terms` (Text Not Null): Disclosures such as `'No annual contract'` or `'Prepaid / No contract'`.
- `priceGuarantee` / `price_guarantee` (Text Nullable): Marketing price lock terms (e.g. `'2-Year Price Guarantee'`).

#### 3. `fcc_provider_mapping` Table
Connects official FCC BDC data filings to retail consumer brands.
- `id` (Integer PK Auto-increment): Surrogate key allowing multiple retail brands to map from the same carrier holding company.
- `frn` (Text Not Null): 10-digit FCC Registration Number.
- `providerId` / `provider_id` (Integer Not Null): 6-digit FCC Provider ID.
- `brandId` / `brand_id` (Text FK Not Null): References `brands.id` with `ON DELETE CASCADE`.
- `technologyCode` / `technology_code` (Integer Not Null): BDC technology code (71 = Licensed Fixed Wireless, 72 = CBRS, 70 = Unlicensed, 61 = LEO Satellite).

#### 4. `coordinate_lookup_cache` Table
Persistent L2 coordinate cache for resolved availability checks.
- `cacheKey` / `cache_key` (Text PK): Spatial coordinate hash `lat.toFixed(4) + ":" + lng.toFixed(4)`. Four decimal places yields ~11-meter precision, grouping buildings and adjoining lots without crossing cellular coverage boundaries.
- `addressJson` / `address_json` (Text Not Null): Serialized `NormalizedAddress` JSON.
- `resultsJson` / `results_json` (Text Not Null): Serialized array of `ProviderCheckResult` or availability summary response.
- `createdAt` / `created_at` (Integer Mode Timestamp Not Null): Generation timestamp.
- `expiresAt` / `expires_at` (Integer Mode Timestamp Not Null): Cache invalidation timestamp (default 24 hours).

---

## 4. SQLite Client Singleton Design (`src/lib/db/index.ts`)

### 4.1 Architecture & Requirements

1. **Auto-Bootstrapping Zero-Config DDL Execution**:
   - Rather than forcing developers or CI test harnesses to execute `drizzle-kit push` or manual migration scripts prior to running tests, the SQLite client executes embedded idempotent DDL (`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`) upon initialization.
   - This guarantees that both fresh local environments and in-memory test runners operate out-of-the-box without separate setup steps.
2. **Dual-Mode Operation (`:memory:` vs File Path)**:
   - When running under Vitest (`process.env.NODE_ENV === 'test'` or `process.env.DATABASE_URL === ':memory:'`), it opens an in-memory SQLite database.
   - When running in dev or production, it resolves the database file path (default: `./data/getme5g.sqlite`) and automatically ensures that the parent directory (`./data`) exists using `fs.mkdirSync(dir, { recursive: true })`.
3. **High-Performance SQLite Pragmas**:
   - `PRAGMA foreign_keys = ON;`: Enforces referential integrity and cascading deletes.
   - `PRAGMA journal_mode = WAL;`: Enables Write-Ahead Logging for high-concurrency readers and writers (file mode only).
   - `PRAGMA synchronous = NORMAL;`: Delivers high throughput without risking database corruption under standard operating system crashes.
4. **Hot-Reloading Resilient Singleton**:
   - In Next.js development mode, files are re-evaluated frequently. Attaching the `better-sqlite3` instance and Drizzle database instance to `globalThis` prevents opening duplicate file descriptors or encountering SQLite database lock errors (`SQLITE_BUSY`).
5. **Drizzle Relational API Integration**:
   - Drizzle ORM is initialized with the complete schema object, enabling relational queries via `db.query.brands.findMany({ with: { plans: true, fccMappings: true } })`.

---

## 5. Drop-In Code Implementation

### 5.1 `src/lib/db/schema.ts`

```typescript
import { sqliteTable, text, integer, real } from 'drizzle-orm/sqlite-core';
import { relations } from 'drizzle-orm';

/**
 * Retail consumer brands catalog
 */
export const brands = sqliteTable('brands', {
  id: text('id').primaryKey(), // e.g. 't-mobile-5g-home', 'metro-by-t-mobile'
  name: text('name').notNull(),
  slug: text('slug').notNull().unique(),
  networkOperator: text('network_operator').notNull(), // 'T-Mobile', 'Verizon', 'AT&T', 'Starlink'
  tierType: text('tier_type').notNull(), // 'postpaid', 'prepaid', 'satellite'
  logoUrl: text('logo_url'),
  creditCheckRequired: integer('credit_check_required', { mode: 'boolean' }).notNull(),
  officialSignupUrl: text('official_signup_url').notNull(),
  createdAt: integer('created_at', { mode: 'timestamp' }),
});

/**
 * Plan tiers, pricing structures, equipment policies, and speed ranges
 */
export const plans = sqliteTable('plans', {
  id: text('id').primaryKey(), // e.g. 't-mobile-5g-home-standard', 'verizon-5g-home-standard'
  brandId: text('brand_id')
    .notNull()
    .references(() => brands.id, { onDelete: 'cascade' }),
  planName: text('plan_name').notNull(),
  monthlyPrice: real('monthly_price').notNull(),
  autopayDiscountPrice: real('autopay_discount_price'),
  bundledPrice: real('bundled_price'),
  downloadMinMbps: integer('download_min_mbps').notNull(),
  downloadMaxMbps: integer('download_max_mbps').notNull(),
  uploadMinMbps: integer('upload_min_mbps').notNull(),
  uploadMaxMbps: integer('upload_max_mbps').notNull(),
  equipmentFee: real('equipment_fee').notNull().default(0),
  equipmentUpfrontCost: real('equipment_upfront_cost').notNull().default(0),
  contractTerms: text('contract_terms').notNull(),
  priceGuarantee: text('price_guarantee'),
});

/**
 * FCC Provider ID and FRN mapping to consumer retail brands
 */
export const fccProviderMapping = sqliteTable('fcc_provider_mapping', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  frn: text('frn').notNull(),
  providerId: integer('provider_id').notNull(),
  brandId: text('brand_id')
    .notNull()
    .references(() => brands.id, { onDelete: 'cascade' }),
  technologyCode: integer('technology_code').notNull(),
});

/**
 * Coordinate lookup cache for fast repeat queries (L2 SQLite Cache)
 */
export const coordinateLookupCache = sqliteTable('coordinate_lookup_cache', {
  cacheKey: text('cache_key').primaryKey(), // Spatial key: "lat.toFixed(4):lng.toFixed(4)"
  addressJson: text('address_json').notNull(),
  resultsJson: text('results_json').notNull(),
  createdAt: integer('created_at', { mode: 'timestamp' }).notNull(),
  expiresAt: integer('expires_at', { mode: 'timestamp' }).notNull(),
});

/**
 * Drizzle ORM Relational Queries Definitions
 */
export const brandsRelations = relations(brands, ({ many }) => ({
  plans: many(plans),
  fccMappings: many(fccProviderMapping),
}));

export const plansRelations = relations(plans, ({ one }) => ({
  brand: one(brands, {
    fields: [plans.brandId],
    references: [brands.id],
  }),
}));

export const fccProviderMappingRelations = relations(fccProviderMapping, ({ one }) => ({
  brand: one(brands, {
    fields: [fccProviderMapping.brandId],
    references: [brands.id],
  }),
}));

/**
 * Inferred TypeScript Types
 */
export type Brand = typeof brands.$inferSelect;
export type NewBrand = typeof brands.$inferInsert;

export type Plan = typeof plans.$inferSelect;
export type NewPlan = typeof plans.$inferInsert;

export type FccProviderMapping = typeof fccProviderMapping.$inferSelect;
export type NewFccProviderMapping = typeof fccProviderMapping.$inferInsert;

export type CoordinateLookupCache = typeof coordinateLookupCache.$inferSelect;
export type NewCoordinateLookupCache = typeof coordinateLookupCache.$inferInsert;
```

---

### 5.2 `src/lib/db/index.ts`

```typescript
import Database from 'better-sqlite3';
import { drizzle, BetterSQLite3Database } from 'drizzle-orm/better-sqlite3';
import * as schema from './schema';
import path from 'path';
import fs from 'fs';

/**
 * Embedded DDL schema to ensure immediate, zero-config availability
 * without requiring external migration commands.
 */
export const SCHEMA_DDL = `
CREATE TABLE IF NOT EXISTS brands (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  network_operator TEXT NOT NULL,
  tier_type TEXT NOT NULL,
  logo_url TEXT,
  credit_check_required INTEGER NOT NULL,
  official_signup_url TEXT NOT NULL,
  created_at INTEGER
);

CREATE TABLE IF NOT EXISTS plans (
  id TEXT PRIMARY KEY,
  brand_id TEXT NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
  plan_name TEXT NOT NULL,
  monthly_price REAL NOT NULL,
  autopay_discount_price REAL,
  bundled_price REAL,
  download_min_mbps INTEGER NOT NULL,
  download_max_mbps INTEGER NOT NULL,
  upload_min_mbps INTEGER NOT NULL,
  upload_max_mbps INTEGER NOT NULL,
  equipment_fee REAL NOT NULL DEFAULT 0,
  equipment_upfront_cost REAL NOT NULL DEFAULT 0,
  contract_terms TEXT NOT NULL,
  price_guarantee TEXT
);

CREATE TABLE IF NOT EXISTS fcc_provider_mapping (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  frn TEXT NOT NULL,
  provider_id INTEGER NOT NULL,
  brand_id TEXT NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
  technology_code INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS coordinate_lookup_cache (
  cache_key TEXT PRIMARY KEY,
  address_json TEXT NOT NULL,
  results_json TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fcc_provider_mapping_frn_tech
  ON fcc_provider_mapping (frn, technology_code);
CREATE INDEX IF NOT EXISTS idx_plans_brand_id
  ON plans (brand_id);
CREATE INDEX IF NOT EXISTS idx_coordinate_lookup_cache_expires_at
  ON coordinate_lookup_cache (expires_at);
`;

/**
 * Initializes tables and indexes idempotently on any SQLite connection.
 */
export function initDatabaseSchema(sqlite: Database.Database): void {
  sqlite.exec(SCHEMA_DDL);
}

export type AppDatabase = BetterSQLite3Database<typeof schema>;

/**
 * Determines database path based on environment variables and execution context.
 */
function resolveDatabasePath(): string {
  if (process.env.DATABASE_URL) {
    return process.env.DATABASE_URL;
  }
  if (process.env.NODE_ENV === 'test') {
    return ':memory:';
  }
  return process.env.DB_PATH || './data/getme5g.sqlite';
}

/**
 * Factory function to create a configured BetterSQLite3 connection.
 */
export function createSqliteClient(dbPath?: string): Database.Database {
  const targetPath = dbPath ?? resolveDatabasePath();
  const isMemory = targetPath === ':memory:';

  if (!isMemory) {
    const resolved = path.resolve(targetPath);
    const dir = path.dirname(resolved);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  }

  const sqlite = new Database(targetPath);

  // Always enforce foreign key integrity
  sqlite.pragma('foreign_keys = ON');

  // Configure high-performance concurrency pragmas for file databases
  if (!isMemory) {
    sqlite.pragma('journal_mode = WAL');
    sqlite.pragma('synchronous = NORMAL');
  }

  // Auto-create schema tables and indexes
  initDatabaseSchema(sqlite);

  return sqlite;
}

/**
 * Global singleton cache for Next.js hot-reloading & test runners
 */
interface GlobalWithDb {
  __sqliteClient?: Database.Database;
  __drizzleDb?: AppDatabase;
}

const globalForDb = globalThis as unknown as GlobalWithDb;

export const sqlite: Database.Database =
  globalForDb.__sqliteClient ?? createSqliteClient();

export const db: AppDatabase =
  globalForDb.__drizzleDb ?? drizzle(sqlite, { schema });

if (process.env.NODE_ENV !== 'production') {
  globalForDb.__sqliteClient = sqlite;
  globalForDb.__drizzleDb = db;
}

export { schema };
export default db;
```

---

## 6. Verification and Validation Results

We constructed and executed a comprehensive verification test suite using Python's native SQLite 3 engine (`verify_ddl.py`) to confirm:
1. **DDL Syntax & Table Creation**: Tables `brands`, `plans`, `fcc_provider_mapping`, `coordinate_lookup_cache` and their respective indexes were created without warnings or syntax errors.
2. **Referential Integrity**: Verified `brand_id` foreign keys in both `plans` and `fcc_provider_mapping`.
3. **Cascading Deletions**: Deleting a brand record from `brands` instantly and cleanly removed all associated plan tiers and FCC mappings without orphaned records.
4. **Data Types**: Confirmed integer booleans, real floating points for pricing, integer speed values, and text payloads execute correctly.

All validation tests completed with exit code 0.
