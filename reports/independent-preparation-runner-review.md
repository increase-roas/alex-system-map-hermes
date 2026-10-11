# Independent preparation runner review

FAILED — goal_not_met_yet.

Bounded source-only snapshot. All seven source hashes matched at start and end. No preparation or helper was executed; no app, fixture, or shared database was mutated. Current runtime receipt was absent at the final read. Accepted transaction mechanics remain closed; full completion remains false.

- **PR01 — FAILED**: Independently fixed complete input authority and exact file/page sets. Required paths are derived from currently present data/views/index; absent top paths can disappear from validator authority. Caller rel_paths can supply a subset. Extra detection covers component Markdown only. The ordinary clone branch does explicitly reject missing declared top paths and components directory, a narrower source-level guard. Evidence: tools/catalog_isolated_manifest.py:34-51, tools/catalog_isolated_manifest.py:82-120, tools/catalog_fixture_clone.py:180-200.
  Required correction/proof: Require independently declared mandatory paths and page IDs, enforce the exact expected set, and reject all in-scope missing/extra paths before hash comparison.

- **PR02 — FAILED**: Full hashes and missing/extra/corrupt/isolated-write controls. SHA256 and byte length comparisons exist for supplied files. The only negative preparation control removes one Markdown page. Isolation helper compares only the first 20 production paths and writes a new probe; it is not required by this runtime proof. No full production hash-set isolation proof or missing/extra/corrupt control inventory is evidenced. Evidence: tools/catalog_isolated_manifest.py:54-79, tools/catalog_isolated_manifest.py:139-160, tools/catalog_preparation_runtime_proof.py:108-125, tools/catalog_preparation_runtime_proof.py:140-161.
  Required correction/proof: Retain full original path/hash sets before and after an isolated edit of an existing canonical/page file, and require separate missing, extra, corruption, and isolation controls.

- **PR03 — FAILED**: Actual interrupting overall deadline covering imports/read/copy/hash/reconcile/proof. The deadline only checks elapsed time before/after synchronous work and cannot interrupt a blocked import, read, hash, or walk. Main helper tests/imports precede its timer; post-clone manifests and negative copy work lack an interrupting deadline. Fixed cleanup budgets can extend beyond remaining time. Evidence: tools/catalog_preparation_bounded.py:23-45, tools/catalog_fixture_clone.py:130-140, tools/catalog_fixture_clone.py:149-154, tools/catalog_fixture_clone.py:202-225, tools/catalog_preparation_runtime_proof.py:23-30, tools/catalog_preparation_runtime_proof.py:128-177.
  Required correction/proof: Supervise the entire preparation worker in a captured process group with a parent deadline, including import/read/hash/reconcile/proof and bounded cleanup. Prove blocked operations are interrupted in that actual path.

- **PR04 — FAILED**: Terminate before bounded drain, exited-leader child cleanup, truthful enumeration status. Timeout source orders group termination before drain and enumeration distinguishes errors/timeout from empty groups. However text stream.read(4096) can block beyond the drain deadline. Normal run_bounded does not inspect surviving descendants, and normal npm build equates a reaped leader with a clean group. Final cleanup enumeration precedes final reaping; clone callers only require exit/timeout, not verified cleanup. Evidence: tools/subprocess_bounded.py:26-64, tools/subprocess_bounded.py:67-111, tools/subprocess_bounded.py:114-138, tools/catalog_preparation_bounded.py:79-103, tools/bounded_npm_build.py:43-62.
  Required correction/proof: Use nonblocking bounded reads, cleanup/check captured groups even after leader exit, fresh final enumeration after reaping, and require known empty-group/reaped outcomes. Enumeration error must remain unknown.

- **PR05 — FAILED**: Fail-closed runtime helper assertions and independently meaningful controls. The canary-free check includes an unconditional or True. Hanging-child deadline-fired is literal True and the leader also sleeps, so it does not cover an exited leader. A nonexistent process group is used as an enumeration-error test instead of forcing an error. helper_ok omits hanging-child result, reaping/group cleanup, actual injection, bounded-drain/order outcome, isolation, and full control inventory; checks are truthiness-based. Evidence: tools/catalog_preparation_runtime_proof.py:37-57, tools/catalog_preparation_runtime_proof.py:60-90, tools/catalog_preparation_runtime_proof.py:93-105, tools/catalog_preparation_runtime_proof.py:167-177.
  Required correction/proof: Require strict typed assertions for every required outcome from a genuinely passing baseline; force enumeration failure independently of a legitimate empty group; exercise exited-leader descendants and require injection plus redaction and benign output evidence.

- **PR06 — UNVERIFIED**: Source-bound runtime evidence. No current receipt was present at the final source check. No preparation, helper, process test, or fixture mutation was run by this reviewer. Source configuration is not runtime verification. Owner/test liveness was parent-reported and not independently rechecked. Evidence: reports/catalog-preparation-runtime-proof-receipt.json (absent at final bounded read).
  Required correction/proof: After the bounded repairs, retain an immutable source-bound receipt and complete manifests with safe typed scalar outcomes for all required controls.

Source bindings (SHA256):

- `tools/catalog_preparation_runtime_proof.py`: `bfa61f68720afbf56ca728a2e14c5b9b763713d5e0577b5fa8553c3726ce6e17`
- `tools/catalog_fixture_clone.py`: `dfcfd7ea1175b61cbd2f106e3f44f2706db704a1d5b17f065db169fa8f3a658e`
- `tools/catalog_isolated_manifest.py`: `f5cdee4a011b6e3915f68ec15a95301c67524ae1e703a9ec510eaa2bd7ad412a`
- `tools/catalog_preparation_bounded.py`: `2c37082b8c471913018cacee9f8a4a00ab7f16a5ec5c6226cfda424e2e88986b`
- `tools/subprocess_bounded.py`: `cfaeb73231f2b9982671cbf5a83761a3afe68cc624eabfb77703d88e0b360e04`
- `tools/subprocess_output.py`: `7a293e12c663ca956a77ceb00fe844834e27cea3ff6c1e6377f1b4f1b8cd4f6d`
- `tools/bounded_npm_build.py`: `b0bed866967531b0ad32dc9e55b56591067b441351893199fa65aa9821ade291`

Next action: correct the actual input authority, interrupting deadline, drain/group cleanup, and fail-closed assertions, then retain a fresh immutable runtime receipt. This report does not infer runtime success from source names or helper labels.
