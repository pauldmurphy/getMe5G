# BRIEFING — 2026-09-29T22:35:45Z

## Mission
Author complete specifications and exact TypeScript seed dataset for `src/lib/db/seed.ts` for all 7 retail consumer brands and `fcc_provider_mapping` table using database schema, ORIGINAL_REQUEST.md, PROJECT.md, spec_miner_survey_2/specs.md, and tests/fixtures/fcc-records.json.

## 🔒 My Identity
- Archetype: teamwork_preview_spec_miner
- Roles: Specification Miner
- Working directory: /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/spec_miner_m2_3
- Original parent: 097744dd-87b6-414e-a580-658af286e0dd
- Milestone: Milestone 2 — Brand Catalog & Plans Seeding Specifications

## 🔒 Key Constraints
- Do NOT implement anything in src/ (spec miner is read-only regarding implementation; write specs in own folder: specs.md and handoff.md)
- Follow exact schema types and relations from schema.ts
- Cover all 7 retail consumer brands:
  1. T-Mobile 5G Home Internet (`t-mobile-5g-home`)
  2. Metro by T-Mobile (`metro-by-t-mobile`)
  3. Verizon 5G Home Internet (`verizon-5g-home`)
  4. Straight Talk Home Internet (`straight-talk-home`)
  5. Total Wireless Home Internet (`total-wireless-home`)
  6. AT&T Internet Air (`att-internet-air`)
  7. Starlink Residential (`starlink-residential`)
- Map FRN/Provider IDs from `tests/fixtures/fcc-records.json` into `fcc_provider_mapping`
- Document complete TypeScript objects for `seed.ts` in specs.md and handoff.md

## Current Parent
- Conversation ID: 097744dd-87b6-414e-a580-658af286e0dd
- Updated: 2026-09-29T22:35:45Z

## Task Summary
- **What to build**: Author specs and complete TypeScript objects for seed data (brands, plans, fcc_provider_mapping)
- **Success criteria**: Exhaustive, production-ready TypeScript seed objects aligning with Drizzle schema and project requirements
- **Interface contracts**: /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/PROJECT.md
- **Code layout**: src/lib/db/schema.ts, src/lib/db/seed.ts

## Key Decisions Made
- Standardized brand IDs strictly matching unit/e2e tests: `t-mobile-5g-home`, `metro-by-t-mobile`, `verizon-5g-home`, `straight-talk-home`, `total-wireless-home`, `att-internet-air`, `starlink-residential`.
- Extracted exact speed boundaries and equipment fee distinctions (postpaid $0 equipment rental vs. prepaid $49 Metro, $99 Straight Talk / Total, $599 Starlink kit).
- Mapped FCC BDC records from `tests/fixtures/fcc-records.json`: T-Mobile (FRN 0001565480, ID 130077) to T-Mobile & Metro; Verizon (FRN 0003290673, ID 130403, Tech 71 & 72) to Verizon, Straight Talk, & Total Wireless; AT&T (FRN 0005050851, ID 130079) to AT&T Internet Air; SpaceX (FRN 0027768225, ID 131444) to Starlink.
- Authored drop-in verbatim `src/lib/db/seed.ts` blueprint supporting both CLI invocation (`tsx src/lib/db/seed.ts`) and programmatic testing with in-memory SQLite.

## Artifact Index
- DISPATCH.md — Assignment instructions
- BRIEFING.md — Situational awareness
- progress.md — Liveness heartbeat
- specs.md — Detailed brand catalog, plan matrix, FCC provider mapping, and complete TypeScript seed objects
- handoff.md — Authoritative 5-component handoff report with drop-in code
