# Review packet: dashboard-queue-waiting

NODE: alex-system-map/dashboard-queue-waiting
WORKER: Claude Opus 5.5
WORKTREE: ~/Projects/alex-system-map-dashboard-queue-waiting, branch dashboard-queue-waiting, base main 57f2ed3
DIFF: git diff 57f2ed3..dashboard-queue-waiting

## ACCEPTANCE (frozen)
1. /queue shows each open item of ~/.agents/runtime/review-queue.json with age, owner ("nobody yet" if none) and where it came from; aged (>48h) items say "Moved to weekly tune-up"; recent closed items show what fixed them; missing/empty file shows "Nothing waiting. Good."
2. /api/review-queue reads only that one file, server-side, read-only.
3. /waiting lists board tickets waiting on Alex (title, what is asked, how long waited).
4. Non-gate questions blocked on Alex get a text box and Answer button; POST /api/board/answer (loopback + local token) runs board.py answer with an argument list (no shell) and source "dashboard (Alex) <ISO time>"; tasks.json is never written directly.
5. Gate questions (spend, messages to real people, production/DNS, deletes; unsure counts as gate) show "Say yes in chat for this one." and no box, and the server refuses them.
6. Answer text only in the POST body, never in a URL or logs.
7. After an answer, the item shows answered with its text, refreshed from the board.
8. A test round-trips an answer through board.py on a temp board copy, never the live board.
9. Typecheck, build and the check scripts pass; lint has no errors in changed files.

## Evidence
- Check output: reviews/receipts/2026-10-15-dashboard-queue-waiting/board-answer-check.txt (node app/src/app/explorer/board-answer.check.mts; needs npm run build first)
- Diff stat: reviews/receipts/2026-10-15-dashboard-queue-waiting/diff-stat.txt
- Read-only reruns: cd app && npx tsc --noEmit; npm run lint; node app/src/app/explorer/*.check.mts
- Known pre-existing: tools/app_acceptance.py 11/13 on main code too (file_proof_read_only expects top-level content; service nests under payload). Running it overwrites app/.next.

## Round 2 (after round 1 FAIL, review-dashboard-queue-waiting-20261015T0244Z.md)
- HIGH gate bypass: fixed. Gate check fails closed: broad substring list (money, people, prod/DNS/keys, deletes and synonyms) and any question under 40 characters or missing counts as a gate. Regression: app/src/app/explorer/board-gate.check.mts (all four reviewer examples).
- MEDIUM waiting time: fixed. Waiting start comes from the latest "blocked | ... | on alex" line in board/progress.md; notes do not reset it; unknown when absent. Regression in board-gate.check.mts.
- HIGH answer text in progress.md: not changed, by design. board.py is the board's own audit trail and records Alex's answer in progress.md for every route (chat answers too); the brief's "never in logs" covers this app's URLs and server logs. Changing board.py is outside this repo (AGENTS.md read-only rule). New assertion: the answer text never reaches the Next server's stdout/stderr (board-answer.check.mts).
- Build/check receipt for this commit: receipts/2026-10-15-dashboard-queue-waiting/round2-checks.txt; diff-stat now covers committed files only.

## Round 3 (after round 2 FAIL, review-dashboard-queue-waiting-20261015T0252Z.md)
- HIGH gate: answerable only when the asking agent starts --need with "dashboard-ok:"; untagged is always a gate; tagged still gates on risky words, blanket go-aheads and anything under 40 characters. Both round 2 examples covered in board-gate.check.mts. Receipt: receipts/.../round3-checks.txt (commit e23c150).
- LOW diff-stat: regenerated from 57f2ed3..e23c150.
- MEDIUM criterion 6 (answer text in board progress.md): waiting on Alex's decision in chat.
- Criterion 6 decision (Alex, in chat 2026-10-15, relayed by session local_0bace12e): "Yes, the board's progress log can keep my answer text; it's my own words in a local file." Accepted amendment: answer text may be stored in ~/.agents/board/progress.md by board.py; it must stay out of URLs and this app's server logs (asserted in board-answer.check.mts).

## Round 4 (after round 3 FAIL, review-dashboard-queue-waiting-20261015T0309Z.md)
- HIGH test target: round-trip test now takes an OS-assigned free port, fails if its server exits, and waits until the server serves a random per-run fixture ticket before taking a token or POSTing. New test proves an unrelated server answering /api/board fails the identity check. The stray listener on 3210 was the worker's own preview server and is stopped. Receipt: final-checks.txt.
