## 2026-09-29T22:32:37Z
You are spec_miner_m2_3, a teamwork_preview_spec_miner subagent.
Your Working Directory: /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/spec_miner_m2_3
Read:
- /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/ORIGINAL_REQUEST.md verbatim.
- /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/PROJECT.md
- /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/spec_miner_survey_2/specs.md
- tests/fixtures/fcc-records.json

Scope: Milestone 2 — Brand Catalog & Plans Seeding Specifications
Objective:
Author the complete seed dataset in `src/lib/db/seed.ts` for all 7 retail consumer brands:
1. T-Mobile 5G Home Internet (`t-mobile-5g-home`): Postpaid, $50/mo w/ autopay ($60 standard), 72-245 Mbps down, 15-31 Mbps up, $0 equipment rental, soft credit check, official URL.
2. Metro by T-Mobile (`metro-by-t-mobile`): Prepaid, $50/mo ($40 w/ phone line promo), 72-245 Mbps down, $49 promo router purchase, no credit check, official URL.
3. Verizon 5G Home Internet (`verizon-5g-home`): Postpaid, $35-$50/mo w/ mobile bundle ($60 standard), 85-300 Mbps down, 10-20 Mbps up, $0 gateway included, 2-yr price guarantee, soft credit check, official URL.
4. Straight Talk Home Internet (`straight-talk-home`): Prepaid, $45/mo flat ($40 autopay), 25-100 Mbps down, 5-10 Mbps up, $99 router purchase, no credit check, official URL.
5. Total Wireless Home Internet (`total-wireless-home`): Prepaid, $45-$60/mo ($35 w/ mobile bundle), 50-200 Mbps down, 10-20 Mbps up, $99 router purchase, no credit check, official URL.
6. AT&T Internet Air (`att-internet-air`): Postpaid, $60/mo or $35 bundled, 75-225 Mbps down, 10-25 Mbps up, All-Fi Hub included ($0 fee), official URL.
7. Starlink Residential (`starlink-residential`): Satellite universal, $120/mo, 50-220 Mbps down, 5-25 Mbps up, $349-$599 standard hardware kit, no contract, official URL.
Also map FRN/Provider IDs from `tests/fixtures/fcc-records.json` into `fcc_provider_mapping`.
Document complete TypeScript objects for `seed.ts` in specs.md and handoff.md. Send completion message to parent when done.
