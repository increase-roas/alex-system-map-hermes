# Canonical repeat-failure diagnosis

**FAILED — goal_not_met_yet.**

Dated 2026-10-10T10:30:17.771910+00:00. Read-only assistance while sole owner remains active; no acceptance promotion. Exact hashes and saved projections are in the JSON.

- **VERIFIED CR01:** identical retry uses original inputs, but digest includes current state revision. Revision changes after first commit, so unchanged retry collides. Pure no-write digest reproduction confirms it. Fix request-bound revision identity and compare/replay inside lock; preserve payload collision rejection and unchanged retry arguments.
- **UNVERIFIED CR02 runtime cause:** saved UI showed intended preview and revision increase, while both APIs agreed on the old purpose. Current UI polling refresh resets draft fields; apply reconstructs a new request instead of committing immutable preview, allowing a draft overwrite race. Fix dirty/in-flight observation handling and retain validated preview request. Capture safely projected request/disk/final DOM fields to establish exact cause; keep true equality checks.

Source changed while reading: tools/canonical_edit_sync_acceptance.py, tools/browser_canonical_edit_sync.mjs. Findings are bound to the initial snapshot; final hashes are recorded, and corrections are not adjudicated. Browser and acceptance sources also differ from the cited10:27:34 receipt. Exact failed error text and apply body are missing from saved receipts. No mutating tests, app writes or browser control were performed.
