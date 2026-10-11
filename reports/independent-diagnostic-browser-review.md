# Independent diagnostic browser review

Read-only review of final diagnostic33729ebf and recovery881140a1 receipts at07:48:54UTC. No raw capture/token output or screenshot viewing.

| Item | Status | Accepted evidence / remaining gap |
| --- | --- | --- |
| Capture/sanitization metadata | VERIFIED | Eight scoped JSON captures/receipts parse and contain no tested raw local-mutation-token or fake-canary patterns. Current network array equals same-run browser receipt; 12 HTTP200 responses parse successfully. Pattern and metadata proof only; backend reviewer evaluates screening internals. Raster token-free proof absent, so screenshot not opened. |
| Sanitization amendment truth | VERIFIED | Six amendment entries explicitly declare immutable bytes amended; five historical files match recorded after hashes. Before/after hashes differ. Fixed network-log path was overwritten by latest run, so its amendment after hash no longer matches current capture. Current capture matches latest receipt. Original unsanitized preimages are not retained; original-byte/semantic preservation cannot be independently reconstructed from declaration alone. |
| Actual job A correction/history UI | VERIFIED | Saved UI action text matches recorded API action, task t1 and workflow_correction source; stale UI text exactly matches old instruction on t1. Runner performs mutations, API recovery and Playwright UI selection. Screenshot hash/size accepted, not visual inspection. Runner does not check computed line-through or historical actionability; exact measured UI strings are independently compared here. |
| Two-job API versus actual B UI | FAILED | Source creates two jobs in same isolated served DB and records B independent API next. Runner only selects job A in UI. api_b.no_leak compares Revise downstream instruction although injected reason is Revise upstream instruction after output, so wrong-string comparison cannot prove A-to-B isolation. Missing actual job B UI selection and exact retained next/history assertion. |
| Dependency-ready actionable / affected outputs | FAILED | Separate receipt records dependency regression booleans; other verifier owns backend correctness. Browser fixture corrects upstream t1; it does not exercise corrected downstream t2 while dependency t1 remains unverified. Browser outputs[] leaves no real retained output to invalidate; affected length>=0 is vacuous and absent from overall. Require exact eligible action/task/dependency state and retained actual test output with nonzero affected-output recheck. |
| Genuine served-process restart | UNVERIFIED | Runner launches twice and records changed launcher PID plus health before process PID. process_restarted compares spawned npx PIDs. health-after process.pid not retained/compared to health-before; child exit/listener release not awaited. A new launcher can fail against old listener and still pass. Require before/after true served PID, old process exit/new listener identity, same isolated DB path/hash expectations. |
| Isolated served DB identity | VERIFIED | Health runtime path equals exact project fixture DB and differs from default. Source passes LOCAL_DATA_DIR/WORKFLOW_SQLITE_PATH; readonly metadata readback found2jobs. Fresh-init DB hash check is false and omitted from pass gate. Health initialization can change bytes; exact cause not established. Before/after actual served DB identity/content continuity and correct expected initialization state remain required. |
| Build/runner/source binding | VERIFIED | Two immutable final pointers match bytes. All recorded source hashes, current BUILD_ID and runner hash match; screenshot size/hash match. Build ID now materially stronger than old present fallback. Recorded current source hashes do not alone reconstruct compiler inputs; no broader build/release claim accepted. |
| Mandatory aggregate fail/pass integrity | VERIFIED | Parent summarize now requires browser overall passed and exit0; browser exceptions set failed/exit1. Final recorded browser exit0. This corrects prior exclusion of browser failure and passed_api fallback. Runner overall still omits genuine served PID comparison, fresh-init/build stability gate, exact B UI/correction string/dependency/affected output checks. Thus its mandatory subset can pass while full requested browser acceptance fails. |
| Prior browser matrix / real source | UNVERIFIED | Historical independent reports remain present and authoritative for unmet items. This narrow recovery/screening milestone does not close original browser matrix, observer/UI cursor restart or real SDK source acceptance. |

## Machine identity checks

| Path | Status | SHA256 |
| --- | --- | --- |
| reports/run-receipts/diagnostic-screening-20261010-0747-33729ebf-1890-4590-93ca-741943ce3586.json | VERIFIED | 0bbee737493d38dc12e1b931d994c273ea86eb163377e7cb6677a7963e868ec6 |
| reports/run-receipts/recovery-screening-real-paths-20261010-0738-881140a1-79f4-44d5-a4e0-739f189d02d5.json | VERIFIED | 6320931b6602bdce8f382e835828c5b3a9f60ec886bb16a103aeac0d80638c8f |
| app/.next/BUILD_ID | VERIFIED | 140f64e07ea220a4c2e7f899d2fe017a2cba9f16319a588bbf2d93e6822eb4e0 |
| app/src/lib/server/local-auth.ts | VERIFIED | 877292a3771fa6a031ba9337bf33c34a3b485612e9563a62ef83d35cabcc61b2 |
| tools/browser_recovery_screening.mjs | VERIFIED | 6125f8010fd9f275cc410e02e8d4144ecdb9b532c6df19572779ccc6d93e62ec |
| tools/diagnostic_emission_screening.mjs | VERIFIED | 26fdbabf7c4297b70f19558bb0485606d17816a4440677d58015dad7893b163e |
| tools/diagnostic_emission_screening.py | VERIFIED | 7aff897ad1847d72c6b5b51d9ba7d13795c2242af3480e7b5b767cfaaa74b527 |
| tools/diagnostic_screening_acceptance.py | VERIFIED | e9e4b0bc3bd7d4610915075819aa06195f87a60bf5deaba2406ed3f3f177f0b5 |
| tools/recovery_screening_real_paths_acceptance.py | VERIFIED | bb44036024385ea522d65df78afa8d0c76dad8e08382bc9a7563c3879faf2411 |
| tools/sanitize_exposed_diagnostic_artifacts.py | VERIFIED | 5ead93bae2fbeb67e2bfeb98990e9cbb975e8254d3894fc8a5c9256e168d2599 |
| app/src/app/api/health/route.ts | VERIFIED | 5a9b3b89545eaab786cb43bd62baec848027140eadb41dfd38f9f3d1d42496e2 |
| app/src/app/api/workflow/route.ts | VERIFIED | cc7cb6e5c915fcd47dc8e3de90e38ca7357f7c89527abd31fd48e9a2a163983b |
| app/src/app/explorer/workflow-panel.tsx | VERIFIED | 0febaf970fe1d0935f5c48898c8c0b01ec7d96654edd554ea8d805b7c61bca78 |
| app/src/lib/server/paths.ts | VERIFIED | 6c41081170f9aa33bfc95ef602be082a12221ba5b73fbd18b188a917871febed |
| app/src/lib/server/python.ts | VERIFIED | f69c42bdf024ec139c2e9da7fcdeb0fe00a8c141d09fc7e5d8205e23a5438f32 |
| tools/browser_recovery_screening.mjs | VERIFIED | 6125f8010fd9f275cc410e02e8d4144ecdb9b532c6df19572779ccc6d93e62ec |
| tools/job_recovery.py | VERIFIED | 7b68031865878c6332ee9275d537d271abd6dd9731e2cda4962fed4a91f50c5a |
| tools/local_service.py | VERIFIED | 980d971e9cfdb316368bdabaf2b162aea5e3dfd0731048bc8e485e16e03fc337 |
| tools/node_bridge_screen_probe.ts | VERIFIED | 426b3a7787d23ba00aa0b3c6192b84d25cf78f7cc26a14c9bcf8d0e1894ba2a2 |
| tools/output_screening.py | VERIFIED | a61fd00e23340e3129eab78b56c33aa8d72ca2428e7764406ba7cf018bea0c4a |
| tools/recovery_screening_real_paths_acceptance.py | VERIFIED | bb44036024385ea522d65df78afa8d0c76dad8e08382bc9a7563c3879faf2411 |
| tools/trace_store.py | VERIFIED | c2cf53be803f225fe42d9b0bbe88c1fa76c05bde62191593a926b9ff0b58ecc6 |
| reports/browser-proof/recovery-screening-real-paths-20261010-0738/recovery-real-paths.png | VERIFIED | abf208cd21ba236f6578102dcc82ac622d8a89c854f26f3ba0121bd12b2eb6bc |

**goal_not_met_yet:** True served PID/old-process-exit/new-listener proof, actual B UI with correct A correction-string exclusion, nonvacuous dependency-ready action and retained-output recheck, before/after served DB continuity; full original browser matrix remains open.
