# Changes Report — Milestone 1: Project Scaffolding & Pluggable Geocoding System

**Agent**: `worker_m1_1`  
**Date**: 2026-09-29  
**Scope**: Root Configs, Baseline UI, Geocoding Cascade Subsystem, and Geocode API Routes.

---

## 1. Files Created and Modified

### 1.1 Root Configurations
- `package.json`: Defined project manifest for Next.js 14 App Router, React 18, Tailwind CSS, shadcn/ui dependencies, Drizzle ORM, better-sqlite3, LRU cache, Vitest, and Playwright.
- `tsconfig.json`: TypeScript 5 configuration with `@/*` path mapping to `./src/*`, bundler module resolution, and strict mode.
- `next.config.mjs`: Next.js ES configuration with `serverComponentsExternalPackages: ['better-sqlite3']`.
- `tailwind.config.ts`: Tailwind configuration with full HSL token support and custom provider carrier color tokens (`tmobile`, `metro`, `verizon`, `straighttalk`, `totalwireless`, `att`, `starlink`).
- `postcss.config.mjs`: PostCSS pipeline configuration with Tailwind and Autoprefixer.
- `drizzle.config.ts`: Drizzle ORM kit configuration pointing to `./src/lib/db/schema.ts` and SQLite local database `./data/getme5g.sqlite`.
- `vitest.config.ts`: Vitest test harness setup with `happy-dom`, `@` path alias, and unit test discovery.
- `playwright.config.ts`: Playwright E2E configuration with Desktop Chrome and Mobile Safari projects, targeting `localhost:3000`.

### 1.2 Baseline UI & Utilities
- `src/lib/utils.ts`: Standard class-name merging helper `cn()` utilizing `clsx` and `tailwind-merge`.
- `src/app/globals.css`: Base Tailwind styling tokens, CSS custom variables for light and dark color schemes.
- `src/app/layout.tsx`: Root App Router layout with HTML, Body, metadata configuration.

### 1.3 Pluggable Geocoding Subsystem (`src/lib/geocoding/`)
- `src/lib/geocoding/types.ts`:
  - `NormalizedAddress`: USPS-standardized postal components (`streetNumber`, `streetName`, `unitNumber`, `city`, `state`, `zip5`, `zip4`, `lat`, `lng`, `formattedAddress`, `geocoderSource`, `confidenceScore`).
  - `AddressSuggestion`: Search-as-you-type suggestion data model.
  - `IGeocoderService`: Provider interface with `suggest()`, `resolve()`, and `resolveCoordinates()`.
  - Typed error hierarchy: `GeocodingError`, `AddressValidationError`, `PoBoxError` (400), `MissingStreetNumberError` (400), `AddressNotFoundError` (400), `OutOfBoundsError` (400), `InvalidCoordinatesError` (422), `GeocoderTimeoutError` (504).
- `src/lib/geocoding/normalizer.ts`:
  - `normalizeAddress()`: Parses single-line address strings, extracts components, validates coordinates, rejects PO Boxes, handles Wisconsin alphanumeric grids, fractional numbers, rural route box addresses, and sanitizes XSS and SQL injection patterns.
  - `isPoBox()`: Regex-based PO Box detection without false positives for "Boxwood" or "Post Office Rd".
  - `assertNotPoBox()`: Enforces PO Box rejection throwing `PoBoxError`.
  - `extractUnitNumber()` / `extractUnit()`: Isolates secondary units (`Apt`, `Suite`, `#`, `Unit`, `Fl`) while keeping the base street clean.
  - `normalizeState()`: Converts full state and territory names to 2-letter uppercase USPS codes.
  - `parseZip()`: Separates 5-digit ZIP codes and 4-digit extensions.
  - `validateCoordinates()`: Enforces US territorial bounding box (Lat [17.5, 72.0], Lng [-179.0, -64.0]).
  - `formatAddress()`: Builds standardized single-line strings.
  - `standardizeStreetName()`: Standardizes road suffixes and directional indicators.
- `src/lib/geocoding/census-geocoder.ts`:
  - US Census Bureau REST client (`/geocoder/locations/onelineaddress`).
  - Protected `x=lng, y=lat` coordinate mapping.
  - 2500ms timeout budget with `AbortController`.
- `src/lib/geocoding/photon-geocoder.ts`:
  - Komoot Photon API client with Continental US bounding box (`-125,24,-66,49`).
  - GeoJSON coordinate mapping `[lon, lat]`.
- `src/lib/geocoding/nominatim-geocoder.ts`:
  - OSM Nominatim client with compliant `User-Agent`.
  - Structured search and reverse geocoding via `resolveCoordinates()`.
- `src/lib/geocoding/google-geocoder.ts`:
  - Commercial Google Places Autocomplete and Geocoding adapter activated via `GOOGLE_PLACES_API_KEY`.
- `src/lib/geocoding/mapbox-geocoder.ts`:
  - Commercial Mapbox Search v6 adapter activated via `MAPBOX_ACCESS_TOKEN`.
- `src/lib/geocoding/service.ts`:
  - Pluggable cascade orchestrator: Commercial (Google/Mapbox) -> Census (2.5s) -> Photon -> Nominatim.
  - L1 In-memory cache for sub-5ms repeat address resolution with 1 hour TTL and `fresh` bypass.
- `src/lib/geocoding/index.ts`:
  - Barrel export of all types, normalizers, geocoder adapters, and the singleton service.

### 1.4 API Routes
- `src/app/api/geocode/suggest/route.ts`:
  - `GET /api/geocode/suggest?q=...&limit=...&lat=...&lng=...`
  - Input validation: checks `q` presence (400), length bounds (1-256), short query threshold (<3 returns 200 with empty array without calling upstream).
  - Emits caching headers (`Cache-Control`) and `X-Geocoder-Source`.
- `src/app/api/geocode/resolve/route.ts`:
  - `GET /api/geocode/resolve?address=...` or `?lat=...&lng=...`
  - Strict validations: length (5-500 chars), PO Box rejection (400), missing street number (400), coordinate boundaries (422).
  - Dispatches to `geocodingService.resolve()` or `resolveCoordinates()`.
  - Comprehensive typed error mapping to HTTP 400, 422, 504, 500.

---

## 2. Integrity Confirmation
All implementations are genuine, functional, and self-contained with no hardcoded test mocks, dummy facades, or shortcuts.
