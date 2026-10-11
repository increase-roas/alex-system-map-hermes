# Independent typed-controls/edit review

PARTIAL — named handler/type/control repairs verified; two precise metadata/status assertions remain.

Final receipt 9555e22e-b62f-4902-a95b-905bef94bfee; 2026-10-10T08:34:24+00:00; SHA256 31281a736f82ded1b7967170bc556f6691e4e4b92f141f1b5b1583a8183ef94c. Seven recorded sources stable; pointer/manifest/history match.

- **VERIFIED — TC01 passing baseline and exact path set:** Independent actual saved core/final baseline passes; recomputed ten known single-field flips all fail. Empty/duplicate path reports reject. Validator now requires exact unique path set/specs/count and failed rows with causes. Circular baseline and duplicate-path failures repaired within the known local generated-control protocol.
  Evidence: tools/acceptance_summarize_strict.py:241-280,292-333; pure output fd8544.
- **FAILED — TC02 remaining row flip identity:** Changing first generated row value_type from bool to str still passes final summary. expected_flip_specs is compared as a separate declared list, but individual row type is never matched to corresponding expected spec. Exact path+flip identity requirement remains partial; require each row type to match spec (and keep fixed flip values bound by generator).
  Evidence: tools/acceptance_summarize_strict.py:237-280; pure control_row_wrong_flip_type result fd8544.
- **VERIFIED — TC03 strict Node/catalog types and schemas:** Actual saved-positive counterexamples for screened="false", node exit=False, nonzero_exit="0", catalog state document=[] and catalog parser exit2 now reject. Catalog export/edit validators require handler labels, integer exits/revisions and actual dict preview/document plus restoration. This closes the named Node and catalog schema/status failures narrowly.
  Evidence: tools/acceptance_summarize_strict.py:10-106,144-161; pure output fd8544.
- **FAILED — TC04 remaining recovery suite status type:** recovery_regression.exit=False still passes complete emitted summary because its check compares !=0 without exact int type. Use the same strict integer-zero guard already applied to Node/apply/catalog. No browser proof is invalidated by this isolated malformed summary input.
  Evidence: tools/acceptance_summarize_strict.py:179-181; pure recovery_exit_false result fd8544.
- **VERIFIED — TC05 correct real edit handler and error paths:** Catalog probe now supplies --db for state/preview/apply/stale/canary error commands and checks expected exit0/1 plus handler-specific shapes; parser substitutions reject. Saved state has injected stored canary redaction note. Genuine preview validation rejects canary note, and dedicated actual edit error emitter yields exit1, benign marker and redacted error string/notes. Stale error is separately labelled static; no static-error redaction claim. Preview/apply success docs are clean, so their canary_removed flags prove only absence, not injected-value redaction. This is narrow local fixture handler proof, not maintained-catalog/CAS acceptance.
  Evidence: tools/catalog_screening_probe.py:132-209; tools/catalog_controlled_edit.py:42-53; tools/local_service.py:516-537; final receipt catalog handler blocks.
- **VERIFIED — TC06 apply and fixture restoration readback:** Saved apply result is success with revision23 and before/after/restored hashes. Current marker SHA exactly matches receipt before/restored SHA. Actual project backup matches the independently computed injected on-disk preimage used by the probe. This supports scoped fixture apply/restoration; no mutation rerun performed.
  Evidence: tools/catalog_screening_probe.py:123-180,210-234; work/reliability/synthetic-sync-marker.json; app/.data/catalog-backups/synthetic-sync-marker.json.7253f42fda1b.bak; safe hash readback fd8544.
- **VERIFIED — TC07 final identity/history and preserved acceptance:** Final9555e22e receipt dated08:34:24 matches pointer/manifest/history and all seven recorded source hashes. Prior failed review retained and hash-bound. Build/Node/browser behavior not re-audited; owner changes are validation helper/probe plus early edit-error output handling, so prior accepted browser/core mechanisms remain preserved.
  Evidence: reports/run-receipts/typed-controls-real-edit-20261010-0831-9555e22e-b62f-4902-a95b-905bef94bfee.json; reports/receipt-hash-manifest.jsonl; reports/workflow-core-run-history.jsonl; reports/independent-actual-ui-baseline-backend-review.json.

Exact final corrections:
- Compare each control row value_type to expected flip spec for that exact unique path; malformed row identity must fail.
- Apply strict type(value) is int and exit==0 guard to recovery_regression.exit; Boolean False must reject. Preserve all accepted handler/error/fixture repairs and then advance maintained-edit/CAS.

Prior failure retained: reports/independent-actual-ui-baseline-backend-review.json; SHA256 58dadfae6a5ec7c77fcf42c24f6749dd70c452e8336ac99494d52dc8fd87f375.
No app writes, mutating tests, browser/outside/network/install/helpers/credential operations or raw diagnostic/token output.

Blocker: **goal_not_met_yet** — Per-row flip type identity and strict recovery-suite exit type validation; two bounded assertion fixes.
