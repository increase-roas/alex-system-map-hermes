DECISION on reports/application-verification.json (stated deliberately, as the play required)

COMMIT IT.

Why: this run is accurate and green against the current tree. The script rewrites this tracked
receipt by design, and the receipt's job is to record the result of the last verification run.
Committing it makes the repository's record true.

Why this differs from the previous commit (4dcdf36): there the same script produced FAIL 11/13 for
a reason that had nothing to do with that change, so committing it would have replaced a receipt
with unrelated noise. I restored main's version then and said so. The reason for that restore is
exactly what this play fixed, so the restore no longer applies.

Also committed: tools/app_acceptance.py (the fix itself) and this receipts folder.
Not touched: the 20 pre-existing `next lint` findings in connector-logins-panel.tsx,
pro-map-audit-check.cjs, pro-map-guardrails/check_registration.cjs, pro-map-panel.tsx and
vendor/libavoid/index.js.
No push, no PR, no branch switch, no branch deleted.
