# Review packet: Langflow nodes build (audit steps 1 to 7)

For `alex-reviewer`, to be run by the other model family (this work was done by claude-opus-5-5, Anthropic).
Only the Director marks it verified.

- Task: Langflow nodes build, `reviews/2026-10-13-langflow-nodes-audit.md` steps 1 to 7.
- Branch and commits: `langflow-dashboard` in `~/Projects/system-map-ir`, base 3572d39.
  8fcf028 step 1, f65c051 step 2, 05933fe step 3, 5dd4c5e step 4, 43db48a step 5, 9a9ff8c step 6,
  678bb56 review fixes, then the step 7 docs commit. Nothing pushed or deployed. No spend.
- Model: claude-opus-5-5. In-session reviewers: security-reviewer and correctness-reviewer (Sonnet, same family).
- Evidence folder: `reviews/receipts/2026-10-13-langflow-nodes/`.

## Acceptance text (from the audit) and result

| Step | Acceptance | Result | Evidence |
|---|---|---|---|
| 1 Catalog | Route returns the 63 current components and the audited tier counts | Seen working (live): 63, local 22, show only 41, unknown 0 | `step1-catalog.txt` |
| 2 Palette | Searchable, keyboard reachable; each of the 63 added and accepted by `lfx validate` | Seen working: 63/63 added through the save route, levels 1 and 3 clean; keyboard add and save in the browser | `step2-palette.txt` |
| 3 Edit kinds | addNode, deleteNode, connect (type checked, Langflow handles), disconnect; refused edits save nothing | Seen working (API); handle bytes match Langflow's own fixtures | `step3-edits.txt` |
| 4 Canvas wiring | Owner can wire; tailnet gets 403 on every new edit kind | Seen working (browser 1280 px; API 403 tests); middleware and policy unchanged | `step4-canvas.txt` |
| 5 Setting editors | Multiline, slider, tab, dict, table; secrets never stored; untouched round trip unchanged | Seen working (API and browser); byte-identical round trip of every editable setting | `step5-settings.txt` |
| 6 Run scope | One live engine test per enabled local component; failures stay off and are listed | Seen working (live): 18/18 enabled produce real output; 4 stay off with reasons | `live-components.txt` |
| 7 Docs and checks | Doc updated; tsc, build, unit and route tests, live tests, desktop and phone browser checks | Historical first result: acceptance scripts FAIL. Current: tsc and build PASS, lint PRE-EXISTING in untouched files, checks PASS, 108/108 unit, 6/6 live, browser PASS, four acceptance scripts PASS (Codex, outside the sandbox) | `final-checks.txt`, `docs/LANGFLOW_DASHBOARD.md` |

## Response to the other-family review (FAIL, 2026-10-13T17:50Z)

Review: `reviews/receipts/2026-10-13-langflow-nodes/review-langflow-nodes-20261013T1750Z.md` (Codex, alex-reviewer).

| Finding | Fix | Proof |
|---|---|---|
| F1 high: secrets nested in lists or objects under a secret-looking key passed edit, import, export and display | Any non-empty text or number anywhere under such a key, or inside an Authorization-style row value, is a secret: refused on edit, emptied on import before disk, redacted in read, dry run and export (commit 1a21322) | `review2.test.mts` (fake canaries: edit refusal, file on disk, read, dry run, export, canvas; benign nested values still round-trip); execution: `run-receipt-4eb50e0.txt` |
| F2 medium: round trip proven for 12 component types; 2 of 256 defaults refused | Optional numbers may stay empty (never 0); "no value" for a setting without one is no change (1a21322) | Live sweep over all 63 installed components: 256 editable settings re-saved byte for byte, 0 refused (`review2.test.mts` F2 LIVE) |
| F3 medium: validator test ignored exit status and allowed errors | Exit status checked in every run; strict levels 1 and 3 for each of the 63; all levels for the 18 wired flows; saved code identity replaces the engine's broken level 2 (1af26c7) | `review-f3-validator.txt`. Needs a decision: full level 4 is impossible for a lone component, so row 2 is proven in the scoped form stated there |
| F4 medium: four acceptance scripts red, no base comparison | Same scripts run on base 3572d39 and on the current code in the same environment | `review-f4-baseline.txt`: all four fail identically on base and current (same failing checks); causes are the sandbox (/tmp, headless Chrome). Not run outside the sandbox |
| Stale docs and packet (engine now 1.12.5) | Doc and packet updated | `docs/LANGFLOW_DASHBOARD.md` |

## What to look at hardest

1. The run gate (`app/src/lib/langflow/model.ts` `executionPlan`): runs need every component enabled AND its code
   byte-identical (full sha256) to the installed engine's built-in one. A note is only `type: noteNode`.
   The security review found a real bypass (a component labelled as a note); it was reproduced live, fixed, and
   rechecked through the running server (`review-fixes.txt`, `final-checks.txt`). Please try to break it again.
2. Prompt variables (`syncPromptVariables`) imitate what Langflow's server does when a prompt is edited.
   Proven live for one variable fed by Chat Input; not compared field by field with a Langflow server.
3. Secret handling inside JSON settings is name-based (token, key, password, authorization and similar).
   A secret under an innocent name would not be caught.

## Follow-up ("fix everything", same day)

Commits 651e6b4 (Run disabled for unrunnable flows, home paths stripped from engine errors, steady prompt typing)
and ec2abd0 (full live suite also passes on lfx 1.12.5). Acceptance-script leftovers removed from the repo.
Evidence: `reviews/receipts/2026-10-13-langflow-nodes/fix-everything.txt`, `engine-1125.txt`.

## Current status (as of the second response, commit 4eb50e0 and later)

- Engine: Alex's venv runs lfx 1.12.5 (langflow 1.12.5). Earlier receipts ran on 1.12.6rc3 and are historical.
- Tailnet: checked on the new build by Alex in his Terminal: the new component route answers through Tailscale
  Serve and a dry-run write is refused with 403 (`fix-everything.txt`).
- Acceptance scripts: they fail identically on base and current inside Claude's sandbox (`review-f4-baseline.txt`);
  outside it, after Codex's fixes, all four pass (Decision 2 below).
- Validator: proof and limits in `review-f3-validator.txt`; the latest execution is `run-receipt-4eb50e0.txt`.
- Real device: not required by the brief (dropped by Alex); the 375 px emulated check stands.
- Decision 1, APPROVED by Alex in chat 2026-10-13 (answer: "Approve scoped wording"): acceptance row 2 is met by
  "All 63: strict `lfx validate --level 3 --skip-components --strict` exits 0 and the saved code is byte-identical
  to the engine's built-in component. All 18 runnable: `lfx validate --skip-components --skip-credentials` exits 0
  in a wired flow, every edge proven compatible, and the real run gives the expected output. Skipped checks are
  named: level 2 (cannot run in this engine), credentials (never stored)." Evidence: `review-f3-validator.txt`,
  `run-receipt-4eb50e0.txt`.
- Decision 2 (Alex in chat 2026-10-13): the four baseline-failing acceptance scripts are not waived; Codex was
  asked through the codex-bridge to get them passing outside Claude's sandbox. RESOLVED: Codex found they also
  failed outside the sandbox (real pre-existing regressions, present at base), fixed product code only
  (maintained-edit-panel.tsx, system-explorer.tsx accessible names, catalog_fixture_clone.py per-file hashes; no
  acceptance script or browser helper changed, verified by git diff), and all four now exit 0 with empty failures:
  `acceptance-gate-codex.txt` and `codex-acceptance-runs/commit-check/`. Commits 01f2f61, e3760c0 on branch
  acceptance-gate-fix, fast-forwarded into langflow-dashboard after Claude reviewed the diff. On the combined code:
  tsc exit 0, lint on the changed files clean, Langflow unit and route 108/108, flow-node-kit 0 FAIL, Pro Map audit
  exit 0, build exit 0 (Claude's sandbox; the four scripts themselves were run by Codex outside it).

## Historical notes (superseded, kept for the record)

- Before 16:40 UTC the venv had lfx 1.12.6rc3 and the sandbox refused the switch; Alex switched it later.
- Before the F4 comparison, the acceptance scripts had not been run at base.
- Before Alex's Terminal checks, the tailnet check of the new build had not been run.
- Not proven: whether Langflow's own server UI opens these saved flows identically (no Langflow server ran).

## Second response (re-review FAIL, 2026-10-13T18:06Z)

Review: `reviews/receipts/2026-10-13-langflow-nodes/review-langflow-nodes-20261013T1806Z.md`.
- Execution receipt for review2 and the whole suite: `run-receipt-4eb50e0.txt` (commit 4eb50e0, lfx 1.12.5,
  index sha256 recorded; unit and route 108/108 exit 0; live 6/6 exit 0; tsc exit 0).
- Combined-flow exit status now asserted on both validator runs; live negative controls prove a broken file
  exits non-zero and is reported (commit 4eb50e0).
- Loop-feedback proof now reads the target loop's types and loop_types (`tests/edge-compat.mts`); unit negatives
  (Embeddings into a loop, a feedback onto a missing loop output) are reported (commit 4eb50e0).
- Doc and packet status reconciled; historical statements labelled.
- The two decisions are resolved: see "Current status" (Decision 1 approved by Alex, Decision 2 passing).

## Third review (2026-10-13T18:48Z): PASS

`reviews/receipts/2026-10-13-langflow-nodes/review-langflow-nodes-20261013T184854Z.md` (Codex, alex-reviewer v1.1):
VERDICT PASS, all seven rows PASS under the approved acceptance, MISSING none. Not a Director VERIFIED state.
The two stale lines it noted are corrected in this packet.
