# Independent declared outcome review

Receipt 2026-10-10T06:53:05+00:00; run 6b83d885-e2da-4955-b1de-70eaf67ee859; SHA 7d56a2cfdf84e744b3b7cef04def0ee122517d4ca792ebcd200ae398c02b2022.

Snapshot stable: all9 source hashes match. No shared state writes or mutating acceptance reruns. Prior transactions/hash writer/scope passes retained.

- **VERIFIED D01 — Saved expectation precedes production and is bound to proof**. Saved add_task event revision2 declares expected UTF8/contract revision1 and hash00ed639c...; output event revision3 occurs later; measured proof records contract hash/revision within job/task/op/verifier-scoped registered proof.
  Evidence: tools/workflow_engine.py:139-152; tools/declared_outcome_live_proof_acceptance.py:129-168; tools/bounded_acceptance.py:279-286.
- **FAILED D02 — Enforced preproduction provenance and monotonic expectation revision**. Update accepts valid declared_outcomes after existing production, without comparison to prior contract revision/hash; invalidation changes status but keeps or replaces outputs. Replacing expected bytes with already-produced wrong bytes at revision1 validates and measures true. Cannot claim predeclared expectation enforcement; no producer declaration revision is attached to output descriptor. Actual recorded positive ordering alone does not close permitted update path.
  Evidence: tools/workflow_engine.py:172-195; tools/bounded_acceptance.py:120-137.
- **VERIFIED D03 — Exact UTF8 outcome, missing/unrelated literal path/wrongcontent refusal, unsupported noncompletion**. Positive saved verified task/content and registered proof match23bytes declared-live-proof-v1 newline; missing artifact and wrongcontent remain incomplete; literal docs path rejected; unsupported criterion returns false acceptance_criterion_unsupported. JSON pure positive and wrong value return expected true/false.
  Evidence: tools/bounded_acceptance.py:197-218; tools/bounded_acceptance.py:246-289; reports/run-receipts/declared-outcome-live-proof-20261010-0650-6b83d885-e2da-4955-b1de-70eaf67ee859.json.
- **FAILED D04 — Exact supported JSON result semantics**. Python equality conflates boolean/numeric JSON values. Pure expected_result={ok:true} with content={ok:1} returns true/result_matches_declaration. {ok:false} correctly fails. Need type-preserving JSON comparison. No saved handler JSON-result case exists; owner receipt covers UTF8 only.
  Evidence: tools/bounded_acceptance.py:210-216.
- **VERIFIED D05 — Live artifact and contract remeasurement at actual workflow consumption**. Consumption calls registered proof resolver then reloads task and remeasures artifact/declared contract. Saved tamper operation has0operations/0events; restored fresh record has1/1. Pure changed-artifact SHA produces observed_artifact_changed_at_consumption; changed contract produces declared_outcome_contract_changed. Proof/check fields are not accepted without live reread. No mutating rerun performed.
  Evidence: tools/verification_evidence.py:442-481; tools/bounded_acceptance.py:292-325; tools/declared_outcome_live_proof_acceptance.py:299-353.
- **FAILED D06 — Resolved artifact-directory allowlist**. Text prefix is checked before resolution and resolved path only constrained to project. work/task-artifacts/../../docs/RELIABILITY_ADDENDUM.md resolves outside artifact directory yet measures true with matching declaration. Bound resolved path to ARTIFACT_ROOT using path containment; reject traversal/symlink escapes. This is a concrete in-project counterexample, no external path was read.
  Evidence: tools/bounded_acceptance.py:34-40; tools/bounded_acceptance.py:190-194.
- **VERIFIED D07 — Isolated single-variable wrongtask with matching remaining scope and0effects**. Saved wt-job revision3 in_progress, record/request operation dolp-record-wt both equal, verifier reviewer-b/job/revision match; request changes only task t1 to t-other, exact reason verification_record_task_id_mismatch; requested operations/events0.
  Evidence: tools/declared_outcome_live_proof_acceptance.py:377-412; reports/run-receipts/declared-outcome-live-proof-20261010-0650-6b83d885-e2da-4955-b1de-70eaf67ee859.json.
- **VERIFIED D08 — Source identity and final-byte history/pointer**. All9 current source hashes match receipt; immutable bytes and both links match7d56a2cfdf84e744b3b7cef04def0ee122517d4ca792ebcd200ae398c02b2022. Prior accepted immutable writer/history and transaction fixes retained; no broad repeat.
  Evidence: reports/run-receipts/declared-outcome-live-proof-20261010-0650-6b83d885-e2da-4955-b1de-70eaf67ee859.json; reports/receipt-hash-manifest.jsonl; reports/workflow-core-run-history.jsonl.

Next action: enforce declaration timing/revision and invalidate produced output reuse; compare JSON results with exact types; contain resolved artifact paths. Record these three bounded regression cases.

Blocker: `goal_not_met_yet` — retroactive expectation rewrite, wrong JSON result type acceptance, and resolved allowlist escape.
