## 2026-09-29T22:16:33Z
You are explorer_m1_r2_2, a teamwork_preview_explorer subagent.
Your Working Directory: /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/explorer_m1_r2_2
Read:
- /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/ORIGINAL_REQUEST.md verbatim.
- /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/PROJECT.md
- /home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/.agents/teamwork/reviewer_m1_2/handoff.md
- src/lib/geocoding/service.ts
- src/app/api/geocode/resolve/route.ts

Objective:
Formulate exact code fixes for `src/lib/geocoding/service.ts` error handling:
In `resolve()`, lines 176-179, the cascade currently catches all errors and rethrows a generic `AddressNotFoundError` (`ADDRESS_NOT_RESOLVED`), which swallows specific validation errors like `MissingStreetNumberError` (`STREET_NUMBER_REQUIRED`) and `PoBoxError` (`PO_BOX_NOT_SUPPORTED`).
Design the fix to rethrow AddressValidationError immediately without wrapping it into AddressNotFoundError, so that `/api/geocode/resolve` returns the correct HTTP 400 with the exact error code.
Document the exact drop-in replacement code in analysis.md and handoff.md. Send completion message to parent.
