# Real-rule review corrections

Alex requested a real Review & fix run against current agent rules, with an AI-written proposed correction waiting for approval. No actual agent Apply was requested.

## Confirmed blockers and corrections

1. Cursor MDC `description` metadata was falsely treated as a script key. The ordinary metadata value now remains visible while credential/command content screening still applies. Source: Cursor official rule format, https://cursor.com/docs/rules (read 2026-10-21). Commit `532a03d`.
2. The canonical gate file was omitted because an unrelated authorization example was screened. The supporting-context reader and frozen-context validator now use the same deterministic named policy section, preserving original citation lines and binding the entire raw file hash. Other targets/peers retain full-file screening. Commit `b0a9c74`.
3. A real AI review with canonical evidence still deferred a supported scoped correction because it treated declared precedence as ambiguous and blocked on an unrelated issue. The server now identifies included registered gate evidence explicitly; review instructions permit supported scoped proposals, preserve outside protections and historical quotations, and leave unrelated ambiguities unchanged. This is analytical guidance, never runtime permission. Commit `cf35389`.

## Checks

- Description regression failed before correction; full relevant suite passed 40 tests. Raw output: description-tests.txt.
- Canonical-context regression failed before correction and exposed the freeze-validator mismatch; after both used the same view, the full relevant suite passed 42 tests. Raw output: context-tests.txt.
- Authority-metadata regressions failed before correction; the full relevant suite passed 43 tests. Raw output: authority-tests.txt.
- A context-separated GPT-6.1 verifier inspected each actual diff and raw output, including sensitive-value preservation, scoped canonical excerpt, whole-file freshness, authority provenance and unchanged explicit approval/provider boundaries.
- The first two real model results were honest needs_decision outcomes, not fake proposals. Their local browser captures are retained with this task's visualization artifacts.

The final actual model run produced a valid frozen proposal against the live shared instruction source. The independent verifier compared its two scoped edits with current source citations, all seven bound context hashes, the exact frozen diff and proposal fingerprint. The enabled Approve control is left in the dedicated browser tab; no Apply was clicked. All nine tracked agent-source fingerprints captured at the start remain unchanged. Local screenshots and the raw DOM proposal capture are retained in this task's visualization artifacts, and the final checks are detailed in FINAL_REVIEW.md. The preview expires at 2026-10-21 00:51 EDT; stale or expired previews require fresh analysis. Actual source application and subsequent generated-copy synchronization remain Alex's decision.

Official OpenAI guidance checked for the review change: https://developers.openai.com/api/docs/guides/agent-builder-safety (structured data flow and clear policy guidance; no model or provider change).
