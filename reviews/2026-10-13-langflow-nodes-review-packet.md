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
| 7 Docs and checks | Doc updated; tsc, build, unit and route tests, live tests, desktop and phone browser checks | tsc PASS, build PASS (into .next-verify), lint PRE-EXISTING, checks PASS, 99/99 unit, 5/5 live, browser PASS; acceptance scripts FAIL (see below) | `final-checks.txt`, `docs/LANGFLOW_DASHBOARD.md` |

## What to look at hardest

1. The run gate (`app/src/lib/langflow/model.ts` `executionPlan`): runs need every component enabled AND its code
   byte-identical (full sha256) to the installed engine's built-in one. A note is only `type: noteNode`.
   The security review found a real bypass (a component labelled as a note); it was reproduced live, fixed, and
   rechecked through the running server (`review-fixes.txt`, `final-checks.txt`). Please try to break it again.
2. Prompt variables (`syncPromptVariables`) imitate what Langflow's server does when a prompt is edited.
   Proven live for one variable fed by Chat Input; not compared field by field with a Langflow server.
3. Secret handling inside JSON settings is name-based (token, key, password, authorization and similar).
   A secret under an innocent name would not be caught.

## Not done, and why

- Real phone, real touch gestures, second device: not available here. Phone result is a 375 px emulated viewport.
- Tailnet check of this build: not run this session. Code path unchanged (middleware.ts, policy.ts) and covered by
  route tests with synthetic Tailscale headers only.
- 4 acceptance scripts selected by `/verify` (they match only on the generic file name route.ts) exit 1:
  sandbox /tmp write denied and headless Chrome blocked are the seen causes; not run at base to compare.
  They rewrote tracked receipts under `reports/` and created `work/maintained/derived/`; left uncommitted.
- Engine drift: the venv has lfx 1.12.6rc3 (pulled in because provider add-ons declare `lfx>=1.12.0.dev0`);
  all evidence ran on it. lfx 1.12.5 exists on PyPI. Its `lfx validate` cannot load its registry
  (`lfx/cli/validation/semantic.py` imports a missing `initialize_components`), so level 2 is skipped by the
  engine. Downgrading is Alex's call; the exact commands are in the doc.
- Not proven: whether Langflow's own server UI opens these saved flows identically (no Langflow server ran).
