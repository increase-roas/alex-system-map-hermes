---
description: Run the repo's real gates in order (tsc, lint, build, check scripts, acceptance) and report READY or NOT-READY with the exact failing lines
argument-hint: "[all]  (all = run every tools/*_acceptance.py)"
allowed-tools: Bash, Read, Grep, Glob
---

Decide whether the current tree is READY or NOT-READY. Run from the repo root. Every command below was copied from `app/package.json` and the scripts in this repo. If one is missing or fails to start, report that line; never invent a substitute. Give each Bash call a timeout of 240000 ms; if a step needs longer, run it in the background and poll.

Arguments: `$ARGUMENTS`

## Gates, in order
Run (a) to (d) even if an earlier one fails, so the report is complete. Skip (c) only when (a) failed, and mark it SKIPPED.

**(a) Types.** `cd app && npx tsc --noEmit`. Pass = exit 0 with no output.

**(b) Lint.** `cd app && npm run lint` (runs `next lint` with `app/.eslintrc.json`). `next.config.ts` ignores ESLint during builds, so this is the only lint gate. If it asks a setup question or reports ESLint is not configured, that is a failure: report the line and do not edit config.
At base (c833d7f) lint already exits 1 with 20 errors in three files nobody changed: `app/src/app/explorer/pro-map-audit-check.cjs` (13, `require()` imports), `app/src/app/explorer/pro-map-guardrails/check_registration.cjs` (6) and `app/src/app/explorer/pro-map-panel.tsx` line 290 (1). To keep the gate useful, split the errors by file. The output groups lines under `./src/...` headers (paths relative to `app/`); compare each header with the changed-file list (compute it first, with the command in (e) step 1).
- Any `Error:` line in a changed or new file = (b) FAIL.
- `Error:` lines only in untouched files = (b) PRE-EXISTING: list the count and files, and do not fail the verdict on them. Warnings never fail.

**(c) Build.** `cd app && npm run build` (`next build`). Pass = exit 0. This writes `app/.next/` (gitignored).

**(d) Check scripts.** Run each with `node` from the repo root; pass = exit 0 and no line starting with `FAIL`.
- Every `app/src/app/explorer/*.check.mts`: `node app/src/app/explorer/<name>.check.mts` (list them with Glob; at base there is one, `flow-node-kit.check.mts`). Node strips the types itself.
- `node app/src/app/explorer/pro-map-audit-check.cjs` (named in AGENTS.md; it prints JSON and exits 1 when `errors` is not empty). Report the `errors` array verbatim and the count of `sourceWarnings` (warnings on Alex's own `y_` cards never fail the gate).

**(e) Acceptance.** `tools/*_acceptance.py` (26 at base). AGENTS.md says to run the one that matches the change.
1. Changed files: `git diff --name-only c833d7f` plus `git ls-files --others --exclude-standard`. (`c833d7f` is this branch's base; use another ref if the user gave one.)
2. If `$ARGUMENTS` contains `all`, run every `tools/*_acceptance.py`. Otherwise select the scripts that mention the base name of a changed file under `tools/`, `app/src/app/api/` or `app/src/lib/server/` (`grep -l -F "<name>" tools/*_acceptance.py`), plus any changed acceptance script. If none match but one of those folders changed, run `tools/app_acceptance.py`. If no change reaches those folders, mark (e) SKIPPED (UI-only change) and say a browser check is still needed.
3. Run each selected script as `python3 -B tools/<name>.py`. Pass = exit 0. `app_acceptance.py` and `maintained_edit_cas_acceptance.py` start `next start` on a loopback port and need (c) to have passed.
4. These scripts write receipts under `reports/` (tracked files). Afterwards run `git status --short reports/` and list the receipts that changed. Do not revert or commit them; tell the caller.

## Report
Print one line per gate: `(a) tsc: PASS | FAIL | SKIPPED`, then the same for (b) to (e) (with `PRE-EXISTING` allowed for (b)), and the count of scripts run for (d) and (e). If (b) is PRE-EXISTING, add one line saying lint is red at base. Then:

- `VERDICT: READY` only when (a) to (d) pass (or (b) is PRE-EXISTING) and (e) passed or was legitimately skipped.
- Otherwise `VERDICT: NOT-READY`, followed by the exact failing lines: the first 20 lines of output of each failing command, verbatim, with the command above them.

Add one line: READY here means these gates are green. It is not "verified": for UI changes the result still has to be looked at in the browser, and finishing needs an `alex-reviewer` packet; only the Director marks work verified. Label what you ran as seen working, and what you skipped as not run.
