# Independent recovery and emitted screening review

FAILED bounded milestone. Owner PASS is not accepted. Prior core acceptance is preserved.

Receipt: reports/run-receipts/recovery-emitted-screening-20261010-0722-a7b9637c-ed4d-430e-80dd-a10b7d5e22ad.json; 2026-10-10T07:31:54+00:00; SHA256 dedb4d329ba163fbbe34fbb52614e30e16a97b93586942947961db03d539963c.
Completed review matched all ten receipt source hashes. Finalization snapshot became unstable after owner resumed; these findings bind the completed earlier snapshot, not changing current bytes.

- **VERIFIED — APP02 narrow job-scoped recovery:** Saved A retains correction, attempt/output and nonactionable stale baseline. Separate B retains independent next action and no correction. Actual merge consumes Engine job-scoped packet, not global reliability correction.
  Evidence: tools/job_recovery.py:5-61; tools/workflow_engine.py:192-205,341-367; tools/reliability_store.py:231-236; app/.data/recovery-emitted-tests/job-a-recovery-emitted-screening-20261010-0722.sqlite; app/.data/recovery-emitted-tests/job-b-recovery-emitted-screening-20261010-0722.sqlite.
- **FAILED — APP02 actual next-action eligibility:** Latest correction unconditionally replaces Engine eligible next action, ignoring pending dependencies/status. Pure no-write packet: parent pending, corrected needs_rechecking with dependency parent; Engine next parent/finish dependency becomes corrected/recheck output. Actual recover-enhanced uses this helper.
  Evidence: tools/job_recovery.py:64-93; tools/workflow_engine.py:362-367.
- **UNVERIFIED — APP02 downstream/verified-checkpoint runtime proof:** New fixture uses one task per separate DB, never initially verified, no valid checkpoint, and placeholder output string containing non-JSON expression "0"*64. No downstream or same-DB cross-job runtime proof added. Preserve previously accepted core invalidation mechanisms.
  Evidence: tools/recovery_emitted_screening_acceptance.py:161-205; saved job-a/job-b DBs above.
- **VERIFIED — APP04 narrow genuine trace export:** Saved span error and metadata contain actual injected fake canaries; actual export_trace_safe screens values and preserves trace/spans shape. This supports this function narrowly. Pure readonly export executed with schema initialization disabled; process-wide emission is not proven.
  Evidence: tools/trace_store.py:206-229; app/.data/recovery-emitted-tests/screen-recovery-emitted-screening-20261010-0722.sqlite; saved spans s1: error FAKE-canary-token-res0722-emitted and metadata sk-fake-canary.
- **FAILED — APP04 actual emission coverage:** Normal recover/recover-enhanced/list-jobs/read-source paths print bare JSON. Argparse, pre-try Engine initialization and uncaught Python errors can emit raw stderr. Node resolves success payload unchanged, spreads unscreened nested payload when replacing top-level error, and does not enforce nonzero process status for valid JSON without error. Shared real emission boundary remains incomplete.
  Evidence: tools/local_service.py:458-466,476-489,540-562; app/src/lib/server/python.ts:46-80.
- **FAILED — APP04 injected canary and verdict integrity:** Service-error/missing-trace checks are fabricated screening-probe routes. Events rows contain no canary; trace-list reads trace rows with no injected canary, not the injected span fields. Unknown-source error is static. Shape check is substring membership. Acceptance summary omits benign/shape/status requirements; Node parsed.benign=false yet exit0/overall passed. Node probe uses already screened Python output and no injected raw stderr/invalid JSON canary. These are invalid full-screening proofs.
  Evidence: tools/local_service.py:410-440; tools/recovery_emitted_screening_acceptance.py:208-253,327-350; tools/node_bridge_screen_probe.ts:19-44; reports/run-receipts/recovery-emitted-screening-20261010-0722-a7b9637c-ed4d-430e-80dd-a10b7d5e22ad.json.
- **UNVERIFIED — APP02 browser:** Receipt records browser exit1, Unexpected end of JSON input and app02_browser unverified. Separate reviewer owns diagnosis.
  Evidence: reports/run-receipts/recovery-emitted-screening-20261010-0722-a7b9637c-ed4d-430e-80dd-a10b7d5e22ad.json.

Exact next fixes:
- Preserve Engine eligible dependency/status next action while applying correction context; prove blocked/dependency and downstream recovery cases.
- Screen actual Python/Node normal/error/stdout/stderr emission boundaries, preserving typed schema, benign text and expected status.
- Inject canaries into fields actually consumed by events/trace-list and real exception/Node stderr/invalid-JSON paths; save before/after outputs. Require all benign/nonempty/typed shape/status checks, including parsed.benign, before PASS.

Read-only source/SQLite and pure helper checks only. No owner source/shared DB mutation, browser operation or acceptance rerun.

Blocker: **goal_not_met_yet** — Eligible correction-aware recovery and genuine real-path emitted-screening/status/shape evidence; browser proof remains separate.
