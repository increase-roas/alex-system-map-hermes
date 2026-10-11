# Independent actual-UI baseline browser review

Reviewed 2026-10-10T08:28:22.496542+00:00; final run `c1207d5a-d1bf-44bf-971c-738a6e36dc17` at 2026-10-10T08:24:32+00:00.

All exact prior scoped gaps verified; owner PASS was independently checked. Broader matrix remains separate.

- **VERIFIED — Exact final receipt/source/runner/build binding.** Reviewed final run c1207d5a-d1bf-44bf-971c-738a6e36dc17 at 08:24:32 UTC. Pointer hash matches immutable receipt; all twelve recorded source hashes match current bytes, runner hash matches browser source, served build before/after equals current BUILD_ID. Owner passed was treated as self-report until these checks. Evidence: `reports/run-receipts/actual-ui-valid-baseline-20261010-0820-c1207d5a-d1bf-44bf-971c-738a6e36dc17.json`, `reports/actual-ui-valid-baseline-receipt.json`

- **VERIFIED — Actual corrected-dependent DOM without API fallback.** Source applies t2 correction with unmet t1 dependency and waits for actual blocked DOM. Saved nonempty UI text contains t2, t1, corr-t2 and correction reason marker. Old count/API fallback removed. Served API independently confirms active t2 correction and pending t1; next permitted task remains t1. Evidence: `tools/browser_recovery_screening.mjs:421`, `app/src/app/explorer/workflow-panel.tsx:454`, `reports/run-receipts/actual-ui-valid-baseline-20261010-0820-c1207d5a-d1bf-44bf-971c-738a6e36dc17.json`

- **VERIFIED — Retained output identity and recheck status.** Saved nonempty output-record DOM identifies t1 and exact fixture output marker. That exact captured record is contained in captured affected-output DOM under the explicit Affected outputs needing recheck heading. API queue count is 1 with retained matching output; earlier count-only UI gap closed. This is retained fixture output-record proof, not external agent-produced artifact proof. Evidence: `tools/browser_recovery_screening.mjs:409`, `app/src/app/explorer/workflow-panel.tsx:443`, `reports/run-receipts/actual-ui-valid-baseline-20261010-0820-c1207d5a-d1bf-44bf-971c-738a6e36dc17.json`

- **VERIFIED — Historical note and job isolation.** Saved A history contains exact stale baseline; A actionable excludes stale instruction. Both A and B actual UI action strings contain full respective API actions; B has no A correction/history leakage. Earlier narrow two-job and history acceptance preserved. Evidence: `tools/browser_recovery_screening.mjs:414`, `reports/run-receipts/actual-ui-valid-baseline-20261010-0820-c1207d5a-d1bf-44bf-971c-738a6e36dc17.json`

- **VERIFIED — Required build/history/output/listener gates.** Browser pass requires build stability, A/B history, actual blocked UI and retained-output identity, listenerReleased and portRefusedObserved. Independent pure strict aggregate positive baseline passes; each of these seven booleans individually false, empty string or absent makes aggregate fail (21 controls). Correct portRefusedObserved camel-case key tested; no unknown-field control used as proof. Evidence: `tools/browser_recovery_screening.mjs:460`, `tools/acceptance_summarize_strict.py:28`

- **VERIFIED — Actual connection-refused interval.** Probe uses TCP net.connect to 127.0.0.1 and exact error code ECONNREFUSED. Successful connection and timeout explicitly return false. Stop waits for port refusal plus old served PID exit before new server starts. Saved port_probe_code is ECONNREFUSED and portRefusedObserved/listenerReleased/oldPidExited true; previous HTTP/error/timeout alias removed. Evidence: `tools/browser_recovery_screening.mjs:93`, `tools/browser_recovery_screening.mjs:126`, `reports/run-receipts/actual-ui-valid-baseline-20261010-0820-c1207d5a-d1bf-44bf-971c-738a6e36dc17.json`

- **VERIFIED — Preserved served PID and isolated DB continuity.** Actual served PID changes 72472 to 72977 independently of launcher IDs; served build and isolated DB path stable. A governing/stale/retained output state and B independent action survive restart. False bare-init DB hash does not invalidate logical continuity because initialization writes sync/trace data; no byte-identical DB claim. Evidence: `tools/browser_recovery_screening.mjs:345`, `reports/run-receipts/actual-ui-valid-baseline-20261010-0820-c1207d5a-d1bf-44bf-971c-738a6e36dc17.json`

- **VERIFIED — Final run capture integrity and safe review.** Capture suffix c1207d5ad1bf matches final run; saved network bytes/hash equal final receipt entries and binding. Screenshot hash/size match metadata; network parse errors zero. Used source and safe Boolean projections only, no raw capture/credential output and no screenshot opened. Screened raster safety/usability not independently claimed. Evidence: `reports/browser-proof/actual-ui-valid-baseline-20261010-0820/capture-c1207d5ad1bf/network-log-c1207d5ad1bf.json`, `reports/browser-proof/actual-ui-valid-baseline-20261010-0820/capture-c1207d5ad1bf/recovery-c1207d5ad1bf.png`

- **VERIFIED — Narrow acceptance boundary.** All exact prior scoped browser gaps now closed. Review performed no browser launch, app rerun/mutation, network, install or helper delegation. This acceptance preserves previous narrow passes and leaves original broader browser matrix/real SDK proof separate. Evidence: `reports/independent-strict-verdict-browser-review.json`

- **UNVERIFIED — Broader original browser matrix and real SDK input.** No broader visual audit or real SDK execution included. Their earlier open evidence requirements remain outside this narrow retest. Evidence: `reports/independent-consolidated-browser-review.json`

Pure controls: valid positive baseline passes; seven required booleans each independently fail when false, empty or missing (21 controls).

Final receipt SHA-256: `d660056727fbf2f6aedbc82d658458d7182c9825eb71773a8ce2835160564918`.

Scoped blocker: none. Remaining broader blocker: **missing_evidence** — Original broader visual/browser matrix and real SDK input proof, not exercised by this bounded retest.
