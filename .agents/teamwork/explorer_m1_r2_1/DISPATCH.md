## 2026-09-29T22:16:32Z
You are explorer_m1_r2_1, a teamwork_preview_explorer subagent.
Your Working Directory: /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/explorer_m1_r2_1
Read:
- /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/ORIGINAL_REQUEST.md verbatim.
- /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/PROJECT.md
- /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/reviewer_m1_1/handoff.md
- /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/challenger_m1_1/handoff.md
- src/lib/geocoding/normalizer.ts
- tests/unit/geocoding/normalizer.test.ts

Objective:
Formulate exact code fixes for `src/lib/geocoding/normalizer.ts`:
1. Fix UNIT_REGEX so it matches `#304` and `#5` after whitespace (fixing test failure at line 72 of normalizer.test.ts).
2. Fix prefix ordering in UNIT_REGEX: check `FLOOR` before `FL`.
3. Fix street suffix replacement in standardizeStreetName so it only matches at the end of the street name, not within words (e.g. "Court St" must not become "Ct St").
4. Fix comma-separated unit parsing so "123 Main St, Apt 4B, New York, NY 10001" correctly extracts unitNumber: "Apt 4B" and leaves city as "New York".
5. Fix missing ZIP handling: if ZIP is absent, do not copy state into zip5.
6. Fix PO_BOX_REGEX to match "P BOX 10".
Document the exact drop-in replacement code in analysis.md and handoff.md. Send completion message to parent.
