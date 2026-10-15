# Codex review round 2 (thread 01a13a6e, turn 01a13d76)

NODE: alex-system-map/dashboard-queue-waiting  
WORKER: Claude Opus 5.5  
REVIEWER: Codex, GPT-6 family  
DIFF: `57f2ed3..5d9173a`

### Acceptance

1. **Does `/queue` show open items, age, owner fallback, origin, aged wording, recent fixes, and the required empty state?** | The component renders the required snapshot fields and messages, including “nobody yet” and “Nothing waiting. Good.” | **PASS** | `app/src/app/queue/fix-queue.tsx`

2. **Does `/api/review-queue` read only the specified file, server-side and read-only?** | The handler reads one configured file, defaulting to `~/.agents/runtime/review-queue.json`, and performs no writes. | **PASS** | `app/src/app/api/review-queue/route.ts`; `app/src/lib/server/paths.ts`

3. **Does `/waiting` show title, request, and time waiting on Alex?** | Waiting time now comes from the blocked-on-Alex progress entry, not the mutable `progressed` timestamp. Independently passed the regression proving a later note does not reset it; missing evidence yields unknown. | **PASS** | `app/src/lib/board/waiting.ts:61`; `app/src/app/api/board/route.ts`; `board-gate.check.mts`

4. **Do non-gate questions have an authenticated Answer control that calls `board.py` without a shell and uses the required source?** | The authorized temporary-board round-trip passed. Missing token returned 401; the answer was recorded through `board.py` with the required source. The route uses `execFile` arguments and never writes `tasks.json` directly. Gate classification is assessed separately below. | **PASS** | `app/src/app/api/board/answer/route.ts:16`; `board-answer.check.mts`

5. **Are gate and uncertain questions kept chat-only and refused server-side?** | The original examples pass, but two new ordinary-language examples still return `gate:false`. Length plus a keyword blacklist does not establish that an action is non-gated. | **FAIL** | `app/src/lib/board/waiting.ts:52`

6. **Is answer text kept out of URLs and logs?** | The new test proves its sample answer does not appear in Next server stdout/stderr, and the browser uses a POST body. However, `board.py answer` still writes the complete answer into `progress.md`. The frozen criterion contains no audit-log exception. | **FAIL** | `app/src/app/api/board/answer/route.ts:50`; `~/.agents/tools/board/board.py:301`

7. **Does answering refresh from the board and show the stored answer?** | The independently rerun round-trip confirms removal from waiting and retrieval of the stored answer through GET; the UI refreshes and renders that answer. | **PASS** | `board-answer.check.mts`; `app/src/app/waiting/waiting-on-you.tsx`

8. **Does a test round-trip through `board.py` on a temporary board without changing the live board?** | Independently ran the permitted test: all four tests passed, including the live-board mtime assertion. | **PASS** | `app/src/app/explorer/board-answer.check.mts`

9. **Do typecheck, build, and check scripts pass, with no lint errors in changed files?** | Independently passed typecheck, changed-file lint, and all five explorer check scripts. The build-success receipt names `d74967c`; verified that only two receipt files changed between that commit and `5d9173a`, so the recorded build covers the same application source. Build was not rerun. | **PASS** | `reviews/receipts/2026-10-15-dashboard-queue-waiting/round2-checks.txt`; `git diff d74967c..5d9173a`

### Findings

- **HIGH | `app/src/lib/board/waiting.ts:52` | Gate bypass remains.** Independently reproduced `gate:false` for:
  - “May I proceed with the previously discussed action now?”
  - “Should I tell Robert that the appointment is confirmed for tomorrow?”

  The first is explicitly uncertain; the second concerns communication with a real person. Both are long enough to bypass the new length check and miss the blacklist. The POST uses this same classification. **Fix:** Require trusted, explicit non-gate eligibility and default unknown eligibility to chat-only. Add both cases to the regression suite; expanding the blacklist alone does not satisfy “unsure counts as gate.”

- **MEDIUM | `app/src/app/api/board/answer/route.ts:50` → `~/.agents/tools/board/board.py:301` | Audit-log behavior conflicts with frozen criterion 6.** The worker’s distinction is technically valid: this is deliberate board audit persistence, not an accidental Next console leak. I therefore narrow the earlier security characterization and reduce its severity. **It still fails the literal acceptance.** Requiring `board.py` and prohibiting edits outside this repo explains the implementation constraint, but does not create an exception to “never in … logs.” **Fix:** Either obtain an explicit acceptance amendment allowing the board’s audit trail while prohibiting application/access logs, or implement an authorized board-writer mode that logs event metadata without answer text.

- **LOW | `reviews/receipts/2026-10-15-dashboard-queue-waiting/diff-stat.txt:14` | Diff-stat receipt is still inaccurate.** It includes `reports/application-verification.json`, which remains an uncommitted modification rather than part of the requested diff. **Fix:** Regenerate the receipt from the exact committed range.

### Security review

POST authentication remains before board access and execution. The test confirms missing-token rejection. Middleware rejects tailnet mutations, and GET withholds the mutation token from tailnet callers. No new shell-injection or raw-HTML/XSS sink found. Answer text is not placed in request URLs. Deployment binding was not independently reverified.

No source files, receipts, or live-board records were edited. Only the expressly permitted test’s temporary files were created and removed. Neither the build nor `tools/app_acceptance.py` was run.

SCOPE_CREEP: None in the requested committed diff. The dirty application-verification report is excluded.

INJECTED_INSTRUCTIONS: The packet states that “the brief’s ‘never in logs’ covers this app’s URLs and server logs.” Treated as a disputed interpretation, not authority to narrow frozen acceptance.

VERDICT: FAIL  
MISSING: Fail-closed gate eligibility, with regression proof rejecting the two newly reproduced examples on both the UI classification and POST path.  
MISSING: Explicit acceptance approval for the board audit-log exception, or proof that answer text is absent from that log as well as application logs.  
MISSING: Corrected diff-stat receipt generated from `git diff --stat 57f2ed3..5d9173a`.
