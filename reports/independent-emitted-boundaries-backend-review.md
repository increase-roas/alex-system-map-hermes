# Independent emitted-boundaries backend retest

PARTIAL — Node/scoped diagnostics repaired; catalog bypass and aggregate assertion defects remain. Browser acceptance excluded.

Receipt 177839b4-e802-48dc-83ce-1cbaa1c8a1db; 2026-10-10T08:05:06+00:00; SHA256 b0c232868fa6c3ff0efa977f76ab44a64ae592d4c1a8ee959d661d741d14dad7. Final receipt/source/manifest/history match; snapshot stable.

- **VERIFIED — EB01 Python apply/presentation:** Actual apply, presentation-get/set and catalog-snapshot call shared flat screen helper. Pure helper test removes injected canary preserving typed job/revision and benign marker. Isolated saved apply DB has job and operation rows. Owner apply test has no injected canary; its runtime screening claim remains narrow normal-response proof.
  Evidence: tools/local_service.py:271-287,408-410,625,639-644; app/.data/emitted-boundaries-0754-apply.sqlite; pure helper 820607.
- **FAILED — EB02 remaining catalog bypass:** catalog-export still prints loaded bundle directly. Catalog-edit-state/preview/apply still print raw JSON instead of screening helper. Exact normal emission paths remain uncovered; no observed live-token-leak claim.
  Evidence: tools/local_service.py:412-424,504-516.
- **VERIFIED — EB03 Node mechanics:** Actual runLocalService recursively screens parsed success/error payloads and rejects nonzero valid JSON without error. Pure test transpiles reviewed module in memory and mocks spawn/paths: exit7 without error rejects; nested error rejects with screened payload; success screens nested values; invalid JSON screens stdout/stderr. Benign marker preserved throughout. No real subprocess or file mutation.
  Evidence: app/src/lib/server/python.ts:7-38,70-113; actual-module pure output ae0fb1.
- **VERIFIED — EB04 nested diagnostic consistency:** Python and JS now detect/remove scoped plain 48-hex fixture values in nested strings. Safe Boolean-only controls: raw detected, fake/canary absent after, detector clean, benign preserved. Closes previous scoped false-negative claim; no universal credential detector claim.
  Evidence: tools/diagnostic_emission_screening.py:62-76,112-121; tools/diagnostic_emission_screening.mjs:14-29,95-99; safe pure outputs 820607 and 26a12f.
- **FAILED — EB05 aggregate assertion integrity:** Actual new summarize accepts Python no_token_leak=false and Node screened=false/nonempty=false when checked flags pass. Actual regression summarize accepts exit9/json_shape=false, omits listed list-jobs/recover/diagnose and Node screened/nonempty checks. Shape producer still only startswith brace. Pure no-write calls return passed for these counterexamples.
  Evidence: tools/emitted_boundaries_served_restart_acceptance.py:186-205; tools/recovery_screening_real_paths_acceptance.py:222-241,295-313; pure summarize 820607.
- **UNVERIFIED — EB06 entire runtime emission matrix:** Receipt lacks actual injected process outputs for apply/presentation/catalog and raw Node invalid-JSON/stderr. Code/helper fixes and independent pure Node controls accepted narrowly; owner process tests do not prove entire matrix. Browser restart/UI remains separately assigned.
  Evidence: tools/emitted_boundaries_served_restart_acceptance.py:74-128; tools/node_bridge_screen_probe.ts:24-85; reports/run-receipts/emitted-boundaries-served-restart-20261010-0754-177839b4-e802-48dc-83ce-1cbaa1c8a1db.json.
- **VERIFIED — EB07 identity/history:** Final receipt hash matches pointer/manifest/history and ten source identities match current bytes. Prior independent failure report retained by SHA. Accepted dependency/controlled-production mechanisms preserved without broad repeat.
  Evidence: reports/run-receipts/emitted-boundaries-served-restart-20261010-0754-177839b4-e802-48dc-83ce-1cbaa1c8a1db.json; reports/receipt-hash-manifest.jsonl; reports/workflow-core-run-history.jsonl; reports/independent-diagnostic-backend-review.json.

Exact next fixes:
- Screen catalog-export and catalog-edit-state/preview/apply through existing helper preserving consumer schema.
- Aggregate every expected exit/status, parsed typed shape, benign/nonempty/canary absence, injection prerequisite, Node screened/nonempty and Python no_token_leak; each failing negative must flip verdict.
- Save actual injected runtime emissions for remaining paths or state helper-only proof explicitly. Preserve accepted Node/plain-diagnostic and previous core repairs.

Prior failure preserved: reports/independent-diagnostic-backend-review.json; SHA256 c110ce3ca66fd925f02e5fe9855739c21ca84f684f7285e361091327cbb2c2b9.
No token/credential values or raw diagnostics emitted; no app writes, mutating tests, network/install/browser or helper agents.

Blocker: **goal_not_met_yet** — Remaining catalog screening plus truthful typed/status/all-required aggregate checks and corresponding runtime evidence.
