## 2026-09-29T22:10:57Z
You are challenger_m1_1, a teamwork_preview_challenger subagent.
Your Working Directory: /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/challenger_m1_1
Read:
- /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/ORIGINAL_REQUEST.md verbatim.
- /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/PROJECT.md
- /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/worker_m1_1/handoff.md

Scope: Stress Test & Adversarial Verification of Address Normalizer
Objective:
Empirically stress-test `src/lib/geocoding/normalizer.ts` with adversarial inputs:
1. PO Box variations: "P.O. Box 123", "PO Box 999", "Post Office Box 42", "P BOX 10", while verifying "Boxwood Ln" or "Boxford St" are NOT rejected.
2. Weird/unusual addresses: Fractional numbers ("123 1/2 Main St"), grid addresses ("N12W34560 Lake Dr"), highway routes ("Route 66"), unit numbers ("Apt 4B", "Ste 100", "#5").
3. Security/Injection payloads: SQL injection syntax (`'; DROP TABLE brands;--`), XSS script tags (`<script>alert(1)</script>`), buffer length limits.
4. Missing components (missing street number, missing zip code, missing city/state).
Document test script/execution and verdict (APPROVE or CHALLENGE_FAILED) in handoff.md. Send completion message to parent.
