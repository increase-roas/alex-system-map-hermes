INCIDENT: a `git pull --rebase` in this shared checkout dropped a verified merge commit

WHAT HAPPENED, from the reflog of ~/Projects/alex-system-map:
  2026-10-19 12:13:28/29 -0400  pull --rebase --no-autostash (pick) x9, then
                                "(finish): returning to refs/heads/main" at ea82632
Commit 4dcdf36 (the dashboard-queue-waiting merge plus its three fixes) was made just before that
and is NOT an ancestor of the resulting main. `git merge-base --is-ancestor 4dcdf36 HEAD` exits 1.
The object still exists, so nothing was lost permanently, but it was silently off the branch for
about five hours and nobody would have noticed from the app alone.

I did not run that rebase. AGENTS.md forbids branch switching, stash, reset and clean in this
folder for exactly this reason; `pull --rebase` has the same effect and is not named in the rule.

WHAT SURVIVED AND WHAT DID NOT:
  survived  - the queue and waiting pages themselves, because origin/main already carried the
              dashboard-queue-waiting commits independently (PR #9 is open for that branch)
  survived  - inputs/real-traces/director-controller/receipts.jsonl at 485 lines
  LOST      - the two top-bar buttons in app/src/app/explorer/system-explorer.tsx
  LOST      - the CEO Fix-now rewire in app/src/lib/server/ceo-dashboard.ts
  LOST      - the single-source change in app/src/app/explorer/ceo-dashboard-panel.tsx
  LOST      - this receipts folder
So the merge's visible result was gone: the two pages were back to being unreachable from the
dashboard and the CEO view was back to the double count. That is the exact failure the merge
existed to prevent.

HOW IT WAS RESTORED:
  All three target files were byte-identical to b7524f8, verified by sha256, so the patch
  `git diff b7524f8 4dcdf36 -- <the three files>` applied cleanly with `git apply --check` first.
  The receipts folder was restored file by file from the 4dcdf36 object.
  Verified live afterwards, not inferred: clicked the restored Fix-now queue button, landed on
  /queue showing "Waiting (94)"; the CEO view shows "Fix-now queue (94)" sourced from
  ~/.agents/runtime/review-queue.json and marked fresh. The two numbers agree. 94 rather than the
  earlier 93 because the queue is live and gained one item during the day.
  tsc exits 0.

WHAT TO DO ABOUT IT (for the Director, not done here):
  Add `pull --rebase` to the forbidden list in AGENTS.md alongside switch, stash, reset and clean,
  or have the guard block it. Several sessions share this one checkout and a rebase here rewrites
  history under whoever else is mid-task.
