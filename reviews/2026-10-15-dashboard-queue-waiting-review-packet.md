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
