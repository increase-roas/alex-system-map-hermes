# Independent core evidence/transactions review

Latest receipt **06:18:10 UTC**, run206c63f9: **FAILED independent acceptance**. Three recorded hashes match sampled source; full independent hashes in JSON include unrecorded Engine/local_service/reliability_store/test helper. This review is bounded toAPP01/03, read-only; no mutating rerun.

| Item | Verdict | Accepted | Remaining |
| --- | --- | --- | --- |
| APP01 | FAILED | Versioned record, mandatory job/revision/requirement, observed age/future checks, live relationship fingerprint, issued registry/file match | Hardcoded fixture checks; fixture accepted for actual completion; no task/operation/verifier/acceptance binding; registry checks record ID only |
| APP03 | FAILED | SameDB guard, transfer actor/canonicaljob/acceptance, rowcount CAS, saved1op+1event dedup | Schema helper commits inside transaction; actual failed concurrent mutation persists; historical replay can downgrade handoff |

**Decisive stored contradiction:** app/.data/workflow-core-tests/txn-handoff-unified.sqlite contains txn-concurrent operation and1 matching event atrevision3; txn-job revision3; txn-job-handoff owner-c revision2. Owner receipt says concurrent mutate exit1 with handoff revision advance lost race, transfer exit0. One successful exit does not mean one durable effect.

Exact commit path: workflow_apply_guard.py:94 starts BEGIN IMMEDIATE; get_handoff/find_handoff calls reliability_store.ensure_schema (24-57), which uses executescript and commits an existing transaction before its script. After Engine writes with manage_tx=False (guard151-153; engine197-205), advance_handoff_revision_cas invokes ensure_schema again (store244) before UPDATE. That commits Engine writes before failedCAS; guard rollback164-166 cannot remove them. Fault test substitutes throw before real helper ensure_schema (acceptance402-435), hiding this path. Initialize schema before BEGIN; ensure in-transaction helpers never commit. Require loser operation/event0 and final job/handoff equality in real concurrency/fault assertions.

Replay also changes any differing checkpoint revision to stored old result (guard96-111), permitting a downward revision after newer actions. Transfer reads Engine revision before BEGIN (193-197) and has no operation replay ledger. Create allows noncanonical handoff ID but later mutation requires canonical ID.

**Proof scope:** saved verification record1dd78145 is fixture_only=true; taskt1/operationev-verify, jobrevision2, age bound3600 seconds, fileSHA matches registry. Actual handler produces1 operation/event and final job/handoffrevision3, proving local fixture wiring. However issue_fixture_record hardcodes3True checks (acceptance106-129), including gate_bad_rejected before the bad gate check. No observed check outputs authenticate those values. Record verifierworkflow-core-fixture differs from payload reviewer-b; recordchecks differ from task acceptance proof-bound. Validator checks job/revision/requirement but not task/operation/verifier/acceptance. Registry SELECTs record_id existence only (verification_evidence196-203), not issued SHA/path/scope. Source set onlyrelationships/addendum; bodyhash/source entries optional. Constrain fixtures and bind measured check results, task/op scope and exact registry identity. This is local protocol correctness, not hostile-agent security.

Legacy --reliability-db mismatch is explicitly refused by _ensure_unified_db (guard60-67); no bypass through actual apply/transfer found in source. These paths deserve retained negative proof but no mutating command rerun occurred.

History improves:6 JSONL append entries and run-specific failure filenames. Original307fe failure remains in supervisor copy; fixedAPP01 path now416816, so they are distinct artifacts. Latest history hash matches receipt; prior hashes alone do not retain immutable original receipts, and failed-run history hash is recorded before receipt rewrite adds failure links. Sourceanchors acceptance33-36,539-581. Keep full per-run receipts with explicit prior/copy hashes.

Blocker: **goal_not_met_yet** — transaction-preserving helpers and real rollback/concurrency proof; truthful task/op-bound measured records with exact registry identity; safe historical/transfer replay and retained immutable attempts. No outside dependency needed.
