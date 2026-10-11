# Independent reliability review — acceptance withheld

Owner reported six passes. These are not independent acceptance. Read-only review of the 05:02:05 UTC receipt and current source; no test rerun.

## REL-01 — not_accepted
Explicit subprocess reads named docs and tests skill existence; no automatic entrypoint or actual fresh agent skill selection/use.

Required proof: Exercise intended context-loading path in a fresh isolated runtime, record revision, loaded skills and recovered next action. If actual agent runtime proof unavailable, mark UNVERIFIED rather than passed.

## REL-02 — not_accepted
Catalog completeness is substituted for per-requirement actual use; passing checks only document/skill existence.

Required proof: Require dated requirement-specific evidence; reject missing/mismatched proof through application completion path. Render evidence plus owner, last verified time and nonempty unresolved step when open.

## REL-03 — partial
SQLite reconnect retrieves a correction, but no recovered decision applies it over older note or invalidates affected outputs; history_retained is hardcoded.

Required proof: Restart actual recovery path with conflicting old note; assert corrected next action, retained history and affected results need rechecking.

## REL-04 — partial
Replay and stale-revision behavior exercised, but no actual owner transition/stale owner rejection or explicit exactly-one event/effect count.

Required proof: Checkpoint a real owner handoff; reject former owner/stale revision; repeat operation and assert one effect/event and recoverability.

## REL-05 — not_accepted
False-completion helper rejects absent proof, but skipped-skill and stale-data cases are standalone existence/hash comparisons; helper not application gate.

Required proof: Run all four negative cases through actual app acceptance/completion path; each fails for correct reason and exposes next unresolved step.

## REL-06 — partial
One screen_text redactor plus JSON serialization only; diagnostic/error/trace/export surfaces not each exercised.

Required proof: Fake canaries only through supported diagnostic, error, trace and export paths. Inspect emitted outputs without retrieving actual secrets.

## Additional required corrections
Current source calls observe_all and marker is allowlisted. Test checks row existence, not expected changed hash/refreshed API/UI; DB reconnect and trace dedup useful but not full observer restart/cursor evidence.
Isolated synthetic local change -> actual refresh -> trace/receipt -> restart with cursor/state persistence and no duplicate effects. Assert new fingerprint equals expected bytes. Does not replace real-source tracing.

Owner/time/path/used strings and conditional next field exist; req.evidence is not rendered. Browser proof absent.

- browser_proof_status accepts report.json existence without validating its results
- verification runner deletes reliability databases also consumed by status API; isolate tests from durable app state and preserve correction/history across reruns

Browser: Incomplete project-local Chromium framework; browser report missing. No additional installation/out-of-project changes. Assess already-installed supported route; no evidence yet that every allowed route is unavailable. Update stale README install advice.

Keep original application, sync and real-source tracing requirements open. Correct existing behavior and proof; no broader system repair, new software/service or duplicate build.
