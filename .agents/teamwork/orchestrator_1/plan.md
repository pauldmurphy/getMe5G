# Master Plan: 5G Availability & Arbitrage Engine

## Objectives
Deliver a high-performance, robust Next.js application that evaluates 5G Home Internet availability across consumer brands, combining FCC BDC data and live provider checks, backed by SQLite/Drizzle and verified by Vitest and Playwright test suites.

## Execution Tracks & Phases

### Phase 0: Survey & Scoping
- Dispatch 3 Explorers (or Spec Miners) in parallel to inspect repo root, package.json, existing configs, API structures, mock data, and test environments.
- Synthesize findings into `PROJECT.md` (Architecture, Feature Inventory, Milestones, Code Layout, Interface Contracts).

### Track 1: E2E & Verification Track
- Design Vitest unit/integration test harness (address parsing, FCC mapping, Drizzle caching).
- Design Playwright E2E suite covering user journeys across mock address fixtures (Urban, Suburban, Rural, Invalid).
- Publish `TEST_READY.md`.

### Track 2: Implementation Track
- Milestone 1: Address Intake & Pluggable Geocoding System (Census / OSM Nominatim / Photon defaults, Google Places / Mapbox env hooks, normalization).
- Milestone 2: Provider Catalog & Drizzle ORM Cache Layer (SQLite schema, seeds, in-memory LRU cache, sub-second lookups).
- Milestone 3: Hybrid Availability Engine & Brand-Level Resolution (FCC BDC data loader, `IProviderChecker` architecture, brand separation: T-Mobile vs Metro, Verizon vs Straight Talk vs Total Wireless, AT&T Air, Starlink, 1.5s timeout & fallback).
- Milestone 4: Interactive Comparison Report UI & Availability API (`GET /api/availability?address=...`, filter/sort, brand cards, plan details, fallback messaging).
- Milestone 5: E2E Integration Pass (Tiers 1-4) & Adversarial Coverage Hardening (Tier 5).
