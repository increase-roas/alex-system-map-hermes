# Independent actual-baseline backend retest

PARTIAL — real baseline and actual export/preview repaired; strict types/control-set and actual edit-error proof fail.

Final receipt c1207d5a-d1bf-44bf-971c-738a6e36dc17; 2026-10-10T08:24:32+00:00; SHA256 d660056727fbf2f6aedbc82d658458d7182c9825eb71773a8ce2835160564918. Twelve source hashes and pointer/manifest/history match. Browser excluded.

- **VERIFIED — AB01 genuine positive baseline:** Control generation now calls core summarizer that excludes control-report requirement, explicitly proves baseline core pass, then flips one field at a time. Independent saved-positive reproduction confirms core/final pass and all ten listed emitted flips fail. Empty control case list now rejects. This closes earlier circular/missing-control baseline defect.
  Evidence: tools/acceptance_summarize_strict.py:201-239; tools/actual_ui_valid_baseline_acceptance.py:77-103,106-124; pure output fb08d7.
- **FAILED — AB02 exact control-set validation:** Validator checks list nonempty/count and all_must_fail, but does not validate exact unique paths/flip identities, count field, must_fail or per-row expected failure. Repeating first control row ten times passes final summary. Missing/empty controls fixed; exact independent set remains unproved.
  Evidence: tools/acceptance_summarize_strict.py:174-189; pure duplicate_control_paths result fb08d7.
- **FAILED — AB03 strict Boolean/status/schema assertions:** Required flags remain truthiness checks: Node screened="false" accepted. Exit=False compares equal to zero and accepted; nonzero_exit="0" also accepted. Catalog eval regards generic dict containing marker/error as json_shape and its state/preview checks do not require success exits/consumer schemas. Prior requirement for strict types and actual result shapes remains incomplete.
  Evidence: tools/acceptance_summarize_strict.py:10-25,52-89; tools/catalog_screening_probe.py:58-70,112-121; pure wrong_boolean_type/wrong_exit_type/wrong_nonzero_exit_type fb08d7.
- **VERIFIED — AB04 actual catalog-export canary:** Saved isolated catalog components contain fake canary before export; probe now passes fixture root through real subprocess loader. Independent read-only correctly formed catalog-export removes canary, returns exit0, benign marker and one redaction note. No helper substitution for this narrow export proof.
  Evidence: tools/catalog_screening_probe.py:22-44,74-89; tools/catalog_io.py:13-17,61-69; app/.data/catalog-fixture-actual-ui-0820-catalog/data/components.json; safe source fixture projection fb08d7; actual readonly process metadata b80116.
- **FAILED — AB05 edit probe wrong-handler claim:** Probe edit-state/preview/error calls omit required --db. They hit ScreeningArgumentParser, not edit handler. State/preview result flags ignore exit status, so argparse exit2 plus marker is counted as real handler pass. Independent identical state invocation confirms exit2, error JSON and no document schema. Owner flags are invalid actual-edit evidence.
  Evidence: tools/catalog_screening_probe.py:47-55,97-108,117-121; tools/local_service.py:322-337; independent parser-only safe metadata.
- **VERIFIED — AB06 independent edit preview/error:** Correctly formed read-only preview with --db and canary in request reaches actual handler: exit0, preview dict and redacted note, marker retained. Existing marker bytes unchanged. This supplies narrow normal-preview proof independently; state/apply and injected error reflection are not proven by flawed owner probes.
  Evidence: actual readonly preview metadata b80116 and 450d7e; tools/local_service.py:505-508.
- **FAILED — AB07 genuine stale-edit error marker:** Correctly formed stale preview with --db reaches actual error handler and returns exit1/error JSON with empty stderr, but no required benign diagnostic marker. Error itself is static revision-conflict text, so canary absence does not prove error-text redaction. Owner error flag instead observes argparse marker at exit2.
  Evidence: tools/catalog_controlled_edit.py:62-66; tools/local_service.py:658-661; actual readonly error metadata b80116.
- **VERIFIED — AB08 final identity/history:** Final c1207d5a receipt dated08:24:32 matches pointer/manifest/history; all twelve source hashes match current bytes. Prior failed review preserved and hash-bound. Existing accepted code/core retained. Browser acceptance excluded.
  Evidence: reports/run-receipts/actual-ui-valid-baseline-20261010-0820-c1207d5a-d1bf-44bf-971c-738a6e36dc17.json; reports/receipt-hash-manifest.jsonl; reports/workflow-core-run-history.jsonl; reports/independent-strict-verdict-backend-review.json.

Exact next corrections:
- Validate Boolean flags with is True, statuses as actual integer values, and per-consumer parsed schemas.
- Validate exact unique control path/value set and intended failure cause against independently passing core baseline; duplicate/malformed/empty sets must reject.
- Supply --db for actual edit subprocesses; require state/preview/apply success statuses and schemas, error expected status/shape/benign marker. Keep source-bound input/output proof and restoration receipt.
- Add benign diagnostic marker to genuine early catalog error handler. Do not label static errors/parser errors as injected edit-error screening proof.

Prior failure retained: reports/independent-strict-verdict-backend-review.json; SHA256 480ebb5e591017be66455a9ef12fd629d2f20d7587077079706219690564cf0a.
Read-only commands used early-return catalog paths; marker bytes verified unchanged. No raw diagnostics/token values emitted; no app writes, credentials, browser/network/install/helpers.

Blocker: **goal_not_met_yet** — Strict typed/status/exact-control-set assertions and genuine catalog-edit normal/error process proof with required benign error marker.
