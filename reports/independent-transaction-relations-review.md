# Independent transaction relation review

Receipt `40ded520-af4a-4452-9da5-4cab8b320d7a` at `2026-10-10T12:34:17+00:00`; SHA `6b1b2e4dddefe518ad0d5cfb51ac04dd6ef1f978f69950e5b5215234dbea7a4b`.

FAILED — goal_not_met_yet. All12 module/schema bindings including finalguardmock and immutable receipt match at start/end. TS03/05/07/08 preserved.

- **TS09 — FAILED**: Coverage verifier requires a nonempty failure list but does not verify that its content names the intended failure/path. A row with failures=[unrelated failure] and targets_path=true remains accepted. targets_path=1 also passes because the guard checks truthiness instead of exact Boolean type. These are the same requested intended-rejection/type boundaries, not new implementation scope.
  Evidence: tools/canonical_transaction_invariants.py:442-489 (especially483-486); tools/canonical_transaction_registry.py control_row_spec_by_id; receipt cases.control_coverage.inventory / expected_control_count385.
  Supported gains: Every reproduced prior scalar/null/control metadata counterexample rejects. Sidecar lookup uses storage_key and required reader; saved postoplog revision1 and replay revision2 were read successfully. Registry now covers the requested exits and required hash/revision fields;385 stored scalar/relation/example controls and passing baseline are source-bound.
  Exact remaining correction: Validate failures as nonempty strings containing the expected invariant/path or explicit expected relation failure; require targets_path is exactlyTrue and consistent with those failures. Add only these exact missing controls to the existing registry/coverage verification.
- **TS11 — FAILED**: Required file/case sets are not independently enforced. Omitting the required component Markdown entry from stage manifest and recomputing its manifest SHA is accepted because verifier only iterates recorded derived entries. Adding unexpected_case=[] to evidence_index.cases also passes full acceptance.
  Evidence: tools/canonical_transaction_evidence.py:190-206,342-354; tools/canonical_transaction_spec.py REQUIRED_EVIDENCE_STAGES / required derived contract; receipt cases.evidence_index; app/.data/canonical-transaction-enforcement-20261010-0828/evidence/40ded520-af4a-4452-9da5-4cab8b320d7a/same_op_concurrent/final.
  Supported gains: Verifier now checks all recorded derived entries including Markdown, requires journals directory when present, checks raw named file/cardinality/hash relationships and explicit canonical absence markers. Actual missing-MD-file and missing-journals-directory mocks reject. All46 retained stage copies/manifests/raw journal bundles match independent readback.
  Exact remaining correction: Require the exact expected per-stage derived/file set independently of recorded manifest keys, and exact evidence case/stage sets independently of supplied index. Add omission/extra-set controls; preserve all actual retained artifacts.
- **SOURCE-BINDING — VERIFIED**: All12 declared module/schema hashes including final guardmock match at start/end; immutable receipt SHA matches pointer. No writing guard-mock execution was performed by reviewer.
  Evidence: reports/run-receipts/canonical-transaction-enforcement-20261010-0828-40ded520-af4a-4452-9da5-4cab8b320d7a.json; tools/canonical_transaction_guard_mocks.py.

All prior reproduced scalar/null/control metadata and missing-file guards now reject; the correct saved sidecar reader returns postoplog1/replay2. All46 retained artifact hashes match. Remaining controls used pure dictionary mutations and no-write filesystem mocks; no app/server/DB mutations, acceptance reruns or writing guardmocks were used.

Do not promote whole EDIT. Promote only prior exact scalar/null/file/binding repairs; residual intended-failure and required-set guards remain. Broader browser/draft/restart/sync/LKG/derived/serveridentity/timeout/freshagent/trace/visual gates are still explicitly pending.

Same owner: finish actual intended failure validation/exact target Boolean and required derived/file/case/stage set guards. Preserve mechanics,46 snapshots and source binding; collect fresh bound receipt, then advance broader queue only after scoped acceptance.
