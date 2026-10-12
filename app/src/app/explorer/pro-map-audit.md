# Pro Map worktree audit - 2026-10-12

## Scope and review status

Branch: pro-map-v4. No commit, push, server, deployment, customer call or SDK query was run.
Map edits and audit artifacts are confined to app/src/app/explorer/.
Claude still owns final review, commit and merge. This is not an installed-runtime certification.

Scope exception: the Hermes research worker used a lookup CLI that automatically offloaded a documentation response to `/tmp/composio/adhoc_7ec934e6458a/EXA_GET_CONTENTS_ACTION_OUTPUT_bc2a9bd5.json`. This was outside the approved write scope. It was left untouched and disclosed to Alex; no cleanup was attempted.

## What changed

- V2 correction layer replaces contradictory merged card details only for p_ IDs. Original v1 detail tables are preserved.
- V2 adds session instructions, pending approval and blocked exits; tool cards feed results; combine follows results; learning reaches future instructions.
- Examples have async entry points and concrete AgentDefinition fields. Before-call control, after-change receipts, finish checks, session recovery, semantic handoff and rollback are separate.
- Hermes claims were checked against official docs and implementation references; built-in versus custom policies are visible. Rows use at most three cards; checkpoints sit in the rails, before writes.
- Each title shows five grades, reasons, source links/checks. Alex evidence buttons open his unchanged cards. V1 is explicitly ungraded.
- Job demos explain custom checks, evidence limits and bounded repairs rather than automatic guaranteed success.

## Grades on the map

V2 B; Hermes B; Alex real-system snapshot D; original V1 ungraded.
V2 and Hermes still need worktree browser review. SDK requests and live hook installation were not exercised. The new custom guard scripts are offline-tested, not installed. Hermes remains a restricted adapter, not a full-route agency policy.
Alex needs implemented and tested client walls, guards across every route, a kill switch, joined receipts and one clear job report. No y_ card claims were upgraded.

## Acceptance proof

See pro-map-audit-receipt.json for commands, outputs and exit codes.

- TypeScript: `node node_modules/typescript/bin/tsc --noEmit -p . --incremental false` passes. The added flag prevents a tsbuildinfo write outside the authorized folder.
- `node src/app/explorer/pro-map-audit-check.cjs --exercise-hooks` passes: 336 nodes, 152 edges, 30 displayed Python examples, 21 displayed JSON examples, 11 finish-hook cases, including infrastructure errors and missing/stale receipt rejection.
- IDs/endpoints, result/combination order, learning connection, sticky titles and actual title component rendering pass.
- Every non-title y_ card and merged detail remains byte-equivalent after JSON serialization to HEAD. Original v1 cards and sticky notes also match HEAD.
- `git diff --check` passes.
- No screenshot of localhost:3200 was counted: that server serves the main repo.

Original bytes and confined offline fixtures are in .audit-backup/. Do not include those backups in the app release by accident.

## Independent review follow-up

Reviewer flagged capped-stop wording and unhandled infrastructure failures. Both were corrected: the capped warning does not promise a revised final answer; supervisor verification is explicit. The example now handles malformed input, process errors and failed receipt storage, and uses per-run identity to reject stale receipts. Eleven offline cases pass.

Independent verifier follow-up: PASS for both corrected Stop defects. The verifier independently reviewed the code/wording; the 11 expanded executable cases were run by the parent, not rerun by the verifier.

## Enforcement add-on

The map now displays runnable, custom guard scripts, their registration, prerequisites, sources and actual local checks. Every A is still tied to its limited rubric scope; overall V2/Hermes remain B. No y_ card changed or installation status was upgraded.

- Setup checker: 31 tests pass. Skill metadata/body/reference depth; MCP type, cards and credential placeholders; explicit rule scope; subagent fields; targeted settings/hook shape; simulated Write/Edit; after-tool and final scan.
- Claude read-first gate: 31 tests pass. Exact tools only; every configured batch action checked; missing cards block; only full successful PostToolUse Read creates a receipt; session/project/agent/policy/card binding; changed and failed reads, replay/race, corrupt state and concurrency covered.
- Hermes adapter: 59 pass, 1 skipped (PyYAML unavailable for general-YAML case). Native event/payload, MCP names, skill/config checks, full successful read_file proof, policy-revision invalidation and explicit unsupported-route blocks.
- Displayed registration commands: 37 checks pass, including paths with spaces for both adapters.
- Tested-source hashes match the browser code strings. Test counts and entry cards appear in the title proof. The map checker rejects stale test/registration receipts.

The strict skill wording/size/reference rules, required subagent tools, global-scope marker and connector cards are custom policy using vendor hook formats. Secret-pattern checks do not prove all arbitrary text secret-free. Read receipts prove delivery, not understanding or authorization.

### Independent review and fixes

Three cold review passes ran. Source quality and reuse reviewers PASS after fixing Hermes policy-bound receipts. The two policy-change tests were observed failing before the fix, then pass after it. Reviewer requests for a fresh Read before every action were withdrawn: Alex explicitly requested the first call per connector, with every batch action checked.

Safe simplifications applied: dirty-only Hermes state writes; standard path containment; removed redundant recursion. Separate vendor adapters intentionally remain separate. State retention and repeated full-scan cost remain deployment limits; no fleet performance claim. Use a dedicated supervised-job state directory and retire it only after related sessions close. Additional traversal/ref-read micro-optimizations were left unchanged to avoid weakening checks without a measured runtime need.

### What still prevents A

- V2: no protected live hook installation, no paid SDK execution proof, unguarded shell/alternate routes need separate restrictions, and no browser inspection of this worktree. The shown scripts and sample decisions are tested; the whole live harness is not.
- Hermes: restricted adapter deliberately blocks terminal, patch, code execution, delegation, skill_manage and aggregate connector routes. Supporting those needs separate checked adapters. General YAML's optional dependency and native hook consent/registration remain unverified. No worktree browser proof.
- Alex: existing spend/send/delete guard evidence covers only 3 apps. Skill/config validators and successful-read markers are not proven installed. Client walls, complete route coverage, kill switch and joined evidence still need implementation.

### Changed source files for Claude to review

All paths below are under app/src/app/explorer/:

- pro-map-data.ts
- pro-map-data-hermes.ts
- pro-map-v2-corrections.ts
- pro-map-guardrail-cards.ts (new)
- pro-map-guardrail-config.ts (new)
- pro-map-guardrail-code.ts (generated)
- pro-map-all.ts
- pro-map-panel.tsx
- pro-map-sticky.ts
- pro-map-jobs.ts (earlier part of same write task)
- pro-map-audit-check.cjs
- pro-map-audit.md and pro-map-audit-receipt.json
- pro-map-guardrails/asset_guard.py, read_gate.py, hermes_guard.py
- pro-map-guardrails/test_asset_guard.py, test_read_gate.py, test_hermes_guard.py
- pro-map-guardrails/bundle.py, run_all.py, check_registration.cjs, README.md
- pro-map-guardrails/test-receipt.json and registration-receipt.json; bounded source/fixture receipts in read-fixtures/ and hermes-fixtures/

Backups remain in .audit-backup/guardrails-addon/. Test-created registration fixtures are retained under pro-map-guardrails/registration-fixture-*/ for inspection, not deployment. No new outside-scope writes were requested or performed in this add-on; the earlier research cache exception above remains disclosed. Nothing committed, pushed, installed, sent, or deployed. Claude owns final review, commit and merge.
