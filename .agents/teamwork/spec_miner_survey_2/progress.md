# Progress — spec_miner_survey_2

Last visited: 2026-09-29T21:56:10Z

## Status
Initializing specification mining for R1 (Geocoding), R2 (Availability Engine & FCC BDC), R3 (Catalog & Cache), R4 (API & UI).

## Steps Completed
- [x] Initialized workspace: DISPATCH.md, BRIEFING.md, progress.md.
- [x] Analyzed ORIGINAL_REQUEST.md requirements and acceptance criteria.

## Steps in Progress
- [ ] Investigate authoritative geocoding endpoints: US Census Bureau Geocoder API, OSM Nominatim, Komoot Photon.
- [ ] Investigate FCC Broadband Data Collection (BDC) public API / dataset format, technology codes (5G / Licensed Fixed Wireless), provider mapping.
- [ ] Formalize distinct retail brand mapping rules (T-Mobile vs Metro; Verizon vs Straight Talk vs Total Wireless; AT&T Internet Air; Starlink/satellite).
- [ ] Specify `IProviderChecker` interface, timeout handling, fallback strategy.
- [ ] Specify Drizzle ORM schema for SQLite (brands, plans, pricing tiers, speeds, equipment, signup links) + LRU / coordinate cache.
- [ ] Specify Next.js API `/api/availability` request/response JSON schema and error responses.
- [ ] Specify UI component structure, state management, sorting/filtering, and fallback messaging.
- [ ] Compile full `specs.md` and `handoff.md`.
