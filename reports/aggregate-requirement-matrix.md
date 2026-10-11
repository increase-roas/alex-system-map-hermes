# Aggregate requirement matrix

Updated: 2026-10-10T08:44:47.331140+00:00

Full completion: **false**. passed: 13, not-run: 17, failed: 13, blocked: 1

| ID | Requirement | Status | Next action |
| --- | --- | --- | --- |
| APP-REVIEW-01.1 | Bind proof to successful requirement-specific outcomes and source identity | passed | Preserve accepted bounded local production/proof mechanism; remaining application/UI/full gates are separate. |
| APP-REVIEW-01.2 | Enforce required claims, evidence age and source/hash binding | passed | Preserve accepted age, requirement-set and source-binding validators; later full app check still separate. |
| APP-REVIEW-01.3 | Use real proof validation through application workflow and UI | not-run | Core guard validated; actual UI proof acquisition/completion still needs end-to-end check. |
| APP-REVIEW-01.4 | Run all required regressions through actual application boundaries | not-run | Reconcile final actual application negatives; do not equate helper tests with UI proof. |
| APP-REVIEW-02.1 | Recovery UI uses current correction-governed next action | passed | Preserve independently verified correction, dependent eligibility, exact retained output UI and restart proof; full visual/sync/fresh-session requirements remain separate. |
| APP-REVIEW-02.2 | General job-specific corrections affect all outputs and survive restart | passed | Preserve independently verified correction, dependent eligibility, exact retained output UI and restart proof; full visual/sync/fresh-session requirements remain separate. |
| APP-REVIEW-03.1 | No missing-owner or handoff-field bypass in backend apply | passed | Preserve verified authoritative guard; full UI lifecycle separately required. |
| APP-REVIEW-03.2 | Bind actor/current owner and handoff to correct job | passed | Preserve verified owner/job/foreign-checkpoint validation. |
| APP-REVIEW-03.3 | Atomic workflow and handoff changes, monotonic replay and transfer retries | passed | Preserve actual postwrite rollback/replay/idempotent transfer acceptance. |
| APP-REVIEW-03.4 | Owner omission, foreign job, race and retry regressions | passed | Retain dated backend negative/race/retry proof; do not generalize to browser recovery. |
| APP-REVIEW-04.1 | Real emitted canaries, exit statuses and nonempty response shape | passed | Preserve accepted emitted screening, strict verdict and real catalog handler evidence during maintained-edit changes; broader sync/source acceptance remains separate. |
| APP-REVIEW-04.2 | Screen Node errors, stderr, trace lists and workflow events | passed | Preserve accepted emitted screening, strict verdict and real catalog handler evidence during maintained-edit changes; broader sync/source acceptance remains separate. |
| APP-REVIEW-04.3 | Trace response shape remains compatible with UI | passed | Preserve independently checked consumer shape and selected trace; full tracing gates still open. |
| APP-REVIEW-05.1 | Automatic UI refresh and observer/application restart | not-run | Prove actual observer and rendered UI lifecycle. |
| APP-REVIEW-05.2 | Synthetic observed actions retain real timing, identities and results | not-run | Record actual local execution fields; preserve synthetic label. |
| APP-REVIEW-05.3 | Restart preserves import cursor and dedup invariants | not-run | Compare before/after cursor across actual application restart. |
| EDIT-1 | Maintained catalog records and editable project documents through API/UI | failed | Implement narrow registered record/document edit API and UI; preserve source boundaries and show preview/diff/evidence. |
| EDIT-2 | Schema/ID validation and revision contract | failed | Validate intended schema, required fields/IDs and references before any write; use explicit expected source revision/hash and reject invalid proposal while preserving last good bytes. |
| EDIT-3 | Concurrent stale edits and crash/backup integrity | not-run | Serialize one write transaction or implement lock/CAS at commit with unique temp and verified backup; prove two stale writers, partial write/crash and restore/readback invariants. |
| EDIT-4 | Restart, regeneration and derived-view agreement | not-run | Exercise actual maintained record edit -> commit/readback -> restart -> render-only derived views -> canonical/map/derived agreement. |
| EDIT-5 | Rename/delete/unreadable/invalid source and original identity | not-run | Add isolated safe failure cases and readbacks preserving last-known-good state/history; compare immutable original hashes. |
| EDIT-6 | Allowlist and secret/export boundary | not-run | Resolve/restrict actual editable paths, reject symlink escape, and test allowed/denied paths and fake-canary outputs without real credentials. |
| EDIT-7 | Integrity of owner PASS | failed | Persist exact command outputs/backup/updated records and bind all checks/source hashes; require every acceptance invariant in aggregate verdict. |
| BROWSER-01 | Evidence assertion changed from REL01/evidence text checks to count()>0 on REL-01-evidence test id; this only tests DOM existence, not visibility/nonempty contents or requirement matching. No substantive evidence-render fix in reviewed change beyond test id. | failed | Assert visible nonempty actual evidence fields and requirement identity; ensure hidden/empty/failed evidence cannot pass. Keep current nonempty screenshot as narrow proof. |
| BROWSER-02 | All eight overview layers appear in top-down order | passed | Preserve independently verified eight-layer layout; final build agreement still needed. |
| BROWSER-03 | Tracing screenshot is empty with Select a trace. Runner never selects trace or checks timeline/spans/evidence/response contract. | failed | Use project synthetic observed receipt for local UI selection/contract regression now; keep real-source acceptance separately blocked. |
| BROWSER-04 | Workflow recovery check only looks for Recover packet text; does not execute correction recovery or assert displayed permitted next action. | failed | Run actual workflow/correction/restart UI path and compare displayed next action with governing correction and backend. |
| BROWSER-05 | Search/detail selection is conditional and not required; no component-detail screenshot in receipt. Subsystem expansion, accessible list, impact traversal and sync refresh not proved by screenshots. | failed | Make requested interactions required with real IDs, matching detail assertions and accessible list coverage. |
| BROWSER-06 | required[] excludes catalog_complete, stats_show_complete and dark_theme_toggled; component assertion only nonempty. No pageerror listener, errors[] only captures launch errors. | failed | Require exact catalog reconciliation and theme checks; collect/fail unexpected page/runtime errors and request failures. |
| BROWSER-07 | Reliability screenshot is2171px wide despite1400px viewport and displays tiny10px raw evidence; likely horizontal content overflow. Narrow screenshot acceptance does not satisfy readable14-16px design. | failed | Constrain evidence panel, wrap/scroll contained content, use readable body text and test no page-level horizontal overflow at chosen viewports. |
| BROWSER-08 | Server command npx next start -p3200 omits hostname; loopback URL alone does not prove server binds only loopback. Isolated-profile directory is created but not passed to chromium.launch. | failed | Bind server explicitly127.0.0.1 and verify listener; configure project-local browser artifact/profile storage correctly without installation or broader changes. |
| REL-01 | Fresh-agent automatic current context/skill loading and correct action recovery; file existence/Python helper alone insufficient. | not-run | Fresh-agent automatic current context/skill loading and correct action recovery; file existence/Python helper alone insufficient. |
| full_application_sync_tracing | Automatic UI refresh, actual observer/application restart, cursor invariants, timestamps and IDs/status from observed action, original real SDK receipt source matching; accepted synthetic CLI mechanics preserved. | not-run | Automatic UI refresh, actual observer/application restart, cursor invariants, timestamps and IDs/status from observed action, original real SDK receipt source matching; accepted synthetic CLI mechanics preserved. |
| browser_visual | Current owner to produce actual installed-Chrome assertions; awaiting new evidence. | not-run | Current owner to produce actual installed-Chrome assertions; awaiting new evidence. |
| CORE-REMAINING | Fresh production evidence originates at actual controlled producer | passed | Preserve accepted bounded local production/proof mechanism; remaining application/UI/full gates are separate. |
| FULL-CATALOG | Complete source reconciliation, factual relationships and no missing original details | not-run | Require source/manifest/workbook/catalog reconciliation and explicit gaps against complete collected source set |
| FULL-RECOVERY | Application restart, corrections, dependencies, proof and current recovery action | failed | Fix actual browser/restart failure (timeout then truncated JSON), rerun meaningful UI correction recovery; owner excluded failure from overall passed. |
| FULL-SCREENING | Actual emitted error/stdout/stderr/trace/event/export screening | failed | Inject fake canaries into each supported actual output path, require valid nonempty shape and exact redaction with no secret use |
| FULL-EDIT-SYNC | Maintained records UI editing and automatic source-to-view synchronization | not-run | Real app observer/UI edit/restart/concurrent edit/last-known-good and derived views agreement |
| FULL-VISUAL | All required views, accessibility, layout, light/dark and served-build identity | failed | Mandatory browser checks on actual build; no skipped search/theme/catalog gates |
| FULL-REAL-TRACE | Original real SDK receipt import, source matching, dedup/restart and browser trace drilldown | blocked | Receive permitted sanitized real project-local input; outside-project search authority remains unanswered |
| FULL-SYNTHETIC-TRACE | Observed local action, automatic observer/UI refresh and restart cursor invariants | not-run | Full application proof retaining actual timestamps, IDs, result, before/after cursors; synthetic label remains |
| FULL-AGENT | Fresh-session skill/context loading and correction-aware next-action recovery | not-run | Actual fresh agent selection/acknowledgment/correct recovery evidence |
| FULL-ACCEPTANCE | Full original application plus all enhancements independently verified | not-run | All above complete with exact current evidence; narrow passes never count as full completion |

Detailed dated evidence, historical failures and source hashes remain in `aggregate-requirement-matrix.json`.

Scoped update 2026-10-10T12:48:52.553718+00:00: four TS09/TS11 guard residuals independently VERIFIED (independent-transaction-final-guards-review). Prior transaction mechanics preserved. Whole requirement counts and full completion remain unchanged. Next owner milestone: browser draft/sync/LKG/restart/final derived lineage/runtime bounds.
