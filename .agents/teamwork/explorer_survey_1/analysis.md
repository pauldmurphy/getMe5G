# Codebase & Repository Survey Analysis

**Date**: 2026-09-29  
**Agent**: `explorer_survey_1` (`teamwork_preview_explorer`)  
**Workspace**: `/home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint`  
**Working Directory**: `/home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/explorer_survey_1`  
**Objective**: Survey repository root, investigate existing codebase state, determine package manager/dependency status, evaluate state of Next.js, React, TypeScript, Tailwind CSS, shadcn/ui, Drizzle ORM, SQLite, Vitest, and Playwright, and identify all missing packages, configurations, and setup needed.

---

## 1. Executive Summary

A comprehensive read-only survey of the repository root at `/home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint` was conducted using filesystem inspection tools (`list_dir`, `find_by_name`, `view_file`, `grep_search`).

The repository is currently in a **clean greenfield (Day 0) state**:
- **Existing Files**: Only `.git` (worktree pointer), `.gitignore` (generic template), `LICENSE` (MIT), `ORIGINAL_REQUEST.md`, and an empty `README.md` (9 bytes) exist in the root.
- **Agent Metadata**: `.agents/teamwork/` houses multi-agent orchestration metadata (`orchestrator_1`, `spec_miner_survey_2`, `explorer_survey_3`, `explorer_survey_1`, `sentinel`).
- **Source Code & Templates**: **0% present**. No application source files (`src/`, `app/`, `components/`, `lib/`), no configuration files (`package.json`, `tsconfig.json`, `next.config.*`, `tailwind.config.*`, `drizzle.config.*`), and no test files exist.
- **Runtime Environment**: The system is running Ubuntu 22.04.5 LTS under WSL2. A Node environment must be bootstrapped along with a complete `package.json` package manifest.

This analysis provides the complete architectural baseline, exact file inventory, dependency manifest, configuration specifications, and directory layout needed for immediate bootstrapping by implementation agents.

---

## 2. Current Repository Inventory & Filesystem State

### 2.1 File & Directory Manifest

Direct inspection of `/home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint` yields the following exact inventory:

| Path | Type | Size | Status / Content |
|---|---|---|---|
| `.git` | File | 80 B | Git worktree pointer: `gitdir: /home/pauld/github/getMe5G/.git/worktrees/5g_arbitrage_engine_blueprint` |
| `.gitignore` | File | 7,454 B | Visual Studio / generic template; includes `node_modules/` at line 316. |
| `LICENSE` | File | 1,070 B | MIT License copyright 2026 Paul D Murphy. |
| `ORIGINAL_REQUEST.md` | File | 4,606 B | Authoritative project requirements (R1–R4) and acceptance criteria. |
| `README.md` | File | 9 B | Single line: `# getMe5G`. |
| `.agents/` | Directory | N/A | Multi-agent coordination directory (contains `teamwork/` metadata). |

### 2.2 Git & Worktree Status
- The directory is a secondary git worktree linked to `/home/pauld/github/getMe5G/.git/worktrees/5g_arbitrage_engine_blueprint`.
- No feature branches, uncommitted code files, or prior commit trees exist within this worktree.

### 2.3 Search for Pre-Existing Source / Assets
- Search for `package*.json`: **0 results**.
- Search for `*.ts`, `*.tsx`, `*.js`, `*.jsx`, `*.json`, `*.css` outside `.agents`: **0 results**.
- Search for mock data fixtures or assets: **0 results**.

---

## 3. Tech Stack Gap Analysis

Each component mandated by `ORIGINAL_REQUEST.md` was evaluated against the current repository state:

### 3.1 Next.js App Router (TypeScript & React)
- **Current State**: Not initialized. No `app/` directory, no `layout.tsx`, no `page.tsx`, no `next.config.mjs`.
- **Target Version**: Next.js 14.2+ (or 15.x) App Router with React 18/19 and TypeScript 5+.
- **Required API Endpoints**:
  - `GET /api/geocode?q=...` — Open geocoding proxy/adapter (Census Geocoder, Komoot Photon, OSM Nominatim; Mapbox/Google Places fallback).
  - `GET /api/availability?address=...` & `GET /api/availability?lat=...&lng=...` — Multi-brand 5G & satellite availability engine returning structured JSON in under 2 seconds.

### 3.2 Tailwind CSS & shadcn/ui
- **Current State**: Not initialized. No `tailwind.config.ts`, no `postcss.config.mjs`, no `components.json`, no `globals.css`.
- **Required Styling Layer**:
  - Tailwind CSS with `@tailwindcss/typography` or custom brand color palette (T-Mobile magenta, Verizon red, AT&T blue, Starlink dark slate).
  - Utility library `clsx` and `tailwind-merge` (`cn` helper).
  - Essential UI primitives for shadcn/ui: Button, Card, Badge, Input, Select, Tabs, Skeleton, Tooltip, Dialog.

### 3.3 Drizzle ORM & SQLite Database Layer
- **Current State**: Not initialized. No `drizzle.config.ts`, no database file, no migration scripts, no schema definitions.
- **Required Data Layer**:
  - Drizzle ORM with SQLite driver (`better-sqlite3` or universal `@libsql/client` / `sql.js`).
  - In-memory SQLite support for Vitest unit test isolation (`:memory:`).
  - Schema tables:
    - `brands` / `providers`: Metadata for T-Mobile, Metro, Verizon, Straight Talk, Total Wireless, AT&T Internet Air, Starlink.
    - `plans`: Pricing tiers, speed minimums/maximums, equipment fees, contract terms, official signup URLs.
    - `fcc_bdc_records`: Local seed database of FCC fixed wireless / satellite coverage records for fallback.
    - `availability_cache`: Coordinate lookup cache with TTL and spatial coordinates.
  - In-memory LRU cache (`lru-cache`) to ensure sub-second response times on repeat queries.

### 3.4 Vitest Test Harness
- **Current State**: Not initialized. No `vitest.config.ts`, no test files.
- **Required Test Suites**:
  - Unit tests for address normalization, Komoot Photon / Census response parsing.
  - Unit tests for FCC BDC technology code parsing (70, 71, 72, 61) and brand-level disambiguation.
  - Integration tests for Drizzle SQLite repository queries and LRU cache hit/miss/expiry.
  - Provider checker timeout resilience tests (verifying 1.5s max timeout and FCC fallback).

### 3.5 Playwright E2E Test Suite
- **Current State**: Not initialized. No `playwright.config.ts`, no test specs, no mock fixtures.
- **Required E2E Journeys**:
  - Urban Multi-Provider Journey (T-Mobile + Metro + Verizon + Straight Talk + Total Wireless + AT&T Air).
  - Suburban Single-Carrier Journey.
  - Rural Satellite-Only Journey (Starlink).
  - Invalid Address / Error Handling Journey.
  - Filter & Sort Interaction Journey (filtering by price, speed, network family).

---

## 4. Package Manifest & Dependency Specifications

To satisfy all requirements and acceptance criteria, the following `package.json` specification is recommended for Track 1/Track 2 bootstrapping:

```json
{
  "name": "get-me-5g",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage",
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui",
    "db:generate": "drizzle-kit generate",
    "db:migrate": "drizzle-kit migrate",
    "db:push": "drizzle-kit push",
    "db:studio": "drizzle-kit studio",
    "db:seed": "tsx src/lib/db/seed.ts"
  },
  "dependencies": {
    "next": "^14.2.13",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "drizzle-orm": "^0.33.0",
    "better-sqlite3": "^11.3.0",
    "lru-cache": "^10.4.3",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.5.2",
    "class-variance-authority": "^0.7.0",
    "lucide-react": "^0.446.0",
    "@radix-ui/react-slot": "^1.1.0",
    "@radix-ui/react-dialog": "^1.1.1",
    "@radix-ui/react-dropdown-menu": "^2.1.1",
    "@radix-ui/react-select": "^2.1.1",
    "@radix-ui/react-tabs": "^1.1.0",
    "@radix-ui/react-tooltip": "^1.1.2"
  },
  "devDependencies": {
    "typescript": "^5.6.2",
    "@types/node": "^22.5.5",
    "@types/react": "^18.3.8",
    "@types/react-dom": "^18.3.0",
    "@types/better-sqlite3": "^7.6.11",
    "tailwindcss": "^3.4.12",
    "postcss": "^8.4.47",
    "autoprefixer": "^10.4.20",
    "drizzle-kit": "^0.24.2",
    "tsx": "^4.19.1",
    "vitest": "^2.1.1",
    "@vitejs/plugin-react": "^4.3.1",
    "happy-dom": "^15.7.4",
    "@testing-library/react": "^16.0.1",
    "@testing-library/jest-dom": "^6.5.0",
    "@playwright/test": "^1.47.2",
    "eslint": "^8.57.1",
    "eslint-config-next": "^14.2.13"
  }
}
```

---

## 5. Configuration File Specifications

### 5.1 `tsconfig.json`
```json
{
  "compilerOptions": {
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [
      {
        "name": "next"
      }
    ],
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": [
    "next-env.d.ts",
    "**/*.ts",
    "**/*.tsx",
    ".next/types/**/*.ts"
  ],
  "exclude": [
    "node_modules"
  ]
}
```

### 5.2 `next.config.mjs`
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    serverComponentsExternalPackages: ['better-sqlite3']
  }
};

export default nextConfig;
```

### 5.3 `tailwind.config.ts`
```typescript
import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: ['class'],
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    container: {
      center: true,
      padding: '2rem',
      screens: {
        '2xl': '1400px',
      },
    },
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        // Provider brand identities
        carrier: {
          tmobile: '#E20074',
          metro: '#27348B',
          verizon: '#CD040B',
          straighttalk: '#0079C1',
          totalwireless: '#FF671B',
          att: '#00A8E0',
          starlink: '#000000',
        }
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
    },
  },
  plugins: [],
};

export default config;
```

### 5.4 `postcss.config.mjs`
```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

### 5.5 `components.json` (shadcn/ui configuration)
```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "src/app/globals.css",
    "baseColor": "slate",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  }
}
```

### 5.6 `drizzle.config.ts`
```typescript
import { defineConfig } from 'drizzle-kit';

export default defineConfig({
  schema: './src/lib/db/schema.ts',
  out: './drizzle',
  dialect: 'sqlite',
  dbCredentials: {
    url: process.env.DATABASE_URL || './data/getme5g.sqlite',
  },
});
```

### 5.7 `vitest.config.ts`
```typescript
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'happy-dom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
    include: ['tests/unit/**/*.{test,spec}.ts', 'tests/unit/**/*.{test,spec}.tsx'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: ['node_modules/', '.next/', 'tests/'],
    },
  },
});
```

### 5.8 `playwright.config.ts`
```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'Mobile Safari',
      use: { ...devices['iPhone 13'] },
    },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
});
```

### 5.9 `.env.example`
```bash
# Database Configuration
DATABASE_URL="./data/getme5g.sqlite"

# Optional Commercial Geocoding Services (defaults to zero-config Census + Photon)
GOOGLE_PLACES_API_KEY=""
MAPBOX_ACCESS_TOKEN=""

# Cache Configuration
CACHE_TTL_SECONDS=3600
LRU_CACHE_MAX_ITEMS=1000

# Provider Engine Timeout (milliseconds)
PROVIDER_CHECK_TIMEOUT_MS=1500
```

---

## 6. Target Directory Architecture (`src/`)

```
/home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/
├── .env.example
├── .gitignore
├── LICENSE
├── ORIGINAL_REQUEST.md
├── README.md
├── package.json
├── tsconfig.json
├── next.config.mjs
├── tailwind.config.ts
├── postcss.config.mjs
├── components.json
├── drizzle.config.ts
├── vitest.config.ts
├── playwright.config.ts
├── data/
│   ├── getme5g.sqlite              # Local SQLite database (gitignored)
│   └── seeds/
│       ├── providers.json           # Catalog of 7 retail brands & plans
│       └── mock_fcc_bdc.json        # FCC BDC sample dataset for test coverage
├── drizzle/                         # Auto-generated Drizzle migrations
├── src/
│   ├── app/
│   │   ├── layout.tsx               # Root App Router layout
│   │   ├── page.tsx                 # Landing & Address Intake View
│   │   ├── globals.css              # Tailwind base + CSS variable design tokens
│   │   ├── report/
│   │   │   └── page.tsx             # Interactive Availability & Comparison Report UI
│   │   └── api/
│   │       ├── geocode/
│   │       │   └── route.ts         # GET /api/geocode?q=... (Census / Photon / Nominatim)
│   │       └── availability/
│   │           └── route.ts         # GET /api/availability?address=... | ?lat=...&lng=...
│   ├── components/
│   │   ├── ui/                      # shadcn/ui primitives
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── badge.tsx
│   │   │   ├── input.tsx
│   │   │   ├── select.tsx
│   │   │   ├── tabs.tsx
│   │   │   ├── skeleton.tsx
│   │   │   └── tooltip.tsx
│   │   ├── address-intake/
│   │   │   ├── address-input.tsx    # Autocomplete input with debounced suggestions
│   │   │   └── address-badge.tsx    # Resolved address pill / verification status
│   │   └── report/
│   │       ├── provider-card.tsx    # Retail brand card (speeds, pricing, CTA)
│   │       ├── brand-badge.tsx      # Carrier network badge (T-Mobile / Verizon / AT&T)
│   │       ├── filter-toolbar.tsx   # Filter by speed, price sort, network family
│   │       └── fallback-banner.tsx  # Graceful banner when satellite-only
│   ├── lib/
│   │   ├── utils.ts                 # cn() class merging utility
│   │   ├── cache/
│   │   │   └── lru.ts               # In-memory LRU coordinate & query cache
│   │   ├── db/
│   │   │   ├── index.ts             # SQLite / Drizzle client singleton
│   │   │   ├── schema.ts            # Drizzle schema (providers, plans, cache, logs)
│   │   │   └── seed.ts              # Database seeding script for retail brands
│   │   ├── geocoding/
│   │   │   ├── types.ts             # NormalizedAddress, GeocodeResult interfaces
│   │   │   ├── census.ts            # US Census Bureau Geocoding Service adapter
│   │   │   ├── photon.ts            # Komoot Photon autocomplete adapter
│   │   │   ├── nominatim.ts         # OpenStreetMap Nominatim adapter
│   │   │   ├── commercial.ts        # Google Places / Mapbox optional adapter
│   │   │   └── index.ts             # Cascading geocoding factory
│   │   └── engine/
│   │       ├── types.ts             # IProviderChecker, ProviderAvailability, CoverageStatus
│   │       ├── brand-mapper.ts      # Multi-brand resolution (T-Mobile -> Metro, VZ -> ST/TW)
│   │       ├── fcc-bdc.ts           # FCC BDC data evaluation & tech codes (70, 71, 72, 61)
│   │       ├── checkers/
│   │       │   ├── tmobile.ts       # T-Mobile 5G Home checker
│   │       │   ├── metro.ts         # Metro by T-Mobile checker
│   │       │   ├── verizon.ts       # Verizon 5G Home checker
│   │       │   ├── straighttalk.ts  # Straight Talk checker
│   │       │   ├── totalwireless.ts # Total Wireless checker
│   │       │   ├── att-air.ts       # AT&T Internet Air checker
│   │       │   └── starlink.ts      # Starlink satellite checker
│   │       └── runner.ts            # Parallel execution with 1.5s timeout & FCC fallback
│   └── types/
│       ├── brand.ts                 # Brand identity & pricing types
│       └── report.ts                # Availability report response payload
└── tests/
    ├── setup.ts                     # Vitest global setup (DOM matchers, in-memory DB)
    ├── fixtures/
    │   ├── addresses.json           # Urban, Suburban, Rural, Invalid address test fixtures
    │   └── fcc-records.json         # Mock FCC records for technology codes 71, 72, 61
    ├── unit/
    │   ├── geocoding/
    │   │   ├── address-normalizer.test.ts
    │   │   └── census-geocoder.test.ts
    │   ├── engine/
    │   │   ├── brand-mapper.test.ts
    │   │   ├── fcc-bdc-parser.test.ts
    │   │   └── provider-checker.test.ts
    │   ├── db/
    │   │   └── drizzle-cache.test.ts
    │   └── cache/
    │       └── lru-cache.test.ts
    └── e2e/
        ├── urban-multi-provider.spec.ts
        ├── suburban-single-carrier.spec.ts
        ├── rural-satellite.spec.ts
        ├── invalid-address.spec.ts
        └── filter-and-sort.spec.ts
```

---

## 7. Actionable Implementation Recommendations

1. **Bootstrap Phase**:
   - Write `package.json` with exact pinned dependencies and scripts.
   - Configure `tsconfig.json`, `next.config.mjs`, `tailwind.config.ts`, `postcss.config.mjs`, `components.json`, and `.env.example`.
   - Setup Vitest (`vitest.config.ts`, `tests/setup.ts`) and Playwright (`playwright.config.ts`).
2. **Track 1 (Verification & Tests)**:
   - Scaffold `tests/fixtures/addresses.json` and `tests/fixtures/fcc-records.json`.
   - Implement unit test suites verifying geocoding normalization, brand mapping, and fallback logic before or in lockstep with feature implementation.
3. **Track 2 (Implementation)**:
   - **Milestone 1**: Geocoding cascade (`src/lib/geocoding/`) & `GET /api/geocode`.
   - **Milestone 2**: SQLite schema, Drizzle client, seeds (`src/lib/db/`), and LRU cache (`src/lib/cache/lru.ts`).
   - **Milestone 3**: Multi-brand engine, `IProviderChecker`, 1.5s timeout, FCC BDC fallback (`src/lib/engine/`).
   - **Milestone 4**: Interactive Report UI and `GET /api/availability` endpoint.
   - **Milestone 5**: Full E2E verification pass across Urban, Suburban, Rural, and Invalid journeys.
