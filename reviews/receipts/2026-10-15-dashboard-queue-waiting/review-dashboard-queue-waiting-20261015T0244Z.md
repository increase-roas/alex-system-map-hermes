# Codex review round 1 (thread 01a13a6e, turn 01a13d71)

NODE: alex-system-map/dashboard-queue-waiting  
WORKER: Claude Opus 5.5  
REVIEWER: Codex, GPT-6 family  
DIFF: `57f2ed3..dashboard-queue-waiting`  
HEAD: `8b2ec65bb2247605431291e1b6ed7d6481a9cbb6`

### Acceptance

1. **Does `/queue` display open items, age, owner fallback, origin, aged wording, recent fixes, and the required empty state?** | The component renders these fields and exact messages from the queue export; the exporter supplies the >48-hour `aged` flag. Verified by source inspection, not browser execution. | **PASS** | `app/src/app/queue/fix-queue.tsx`; `~/.agents/tools/guards/review_queue.py:136`

2. **Does `/api/review-queue` read only the specified file, server-side and read-only?** | The handler performs one filesystem read through `reviewQueuePath()`, defaults to the required path, and contains no writes. | **PASS** | `app/src/app/api/review-queue/route.ts`; `app/src/lib/server/paths.ts`

3. **Does `/waiting` list tickets waiting on Alex with title, request, and elapsed waiting time?** | Title and request are present, but elapsed time uses `progressed` or `updated`. `board.py note` resets `progressed` without ending the blocked state, so this can show time since an agent’s note rather than time waiting on Alex. | **FAIL** | `app/src/lib/board/waiting.ts:46`; `~/.agents/tools/board/board.py:274`

4. **Do non-gate questions get an Answer control backed by loopback-plus-token POST, argument-list execution, and the required source?** | The route authenticates before processing, calls `execFile` without a shell, supplies `dashboard (Alex) <ISO time>`, and delegates board changes to `board.py`. The UI provides the textarea and button. Gate classification is separately failed below. | **PASS** | `app/src/app/api/board/answer/route.ts:22`; `app/src/lib/server/local-auth.ts`; `app/src/app/waiting/waiting-on-you.tsx`

5. **Are gate questions, including uncertain questions, withheld from dashboard answering and refused server-side?** | Independently reproduced `gate:false, answerable:true` for “Charge the card 50 dollars?”, “Contact Jane by SMS?”, “Erase the backup?”, and “Proceed?”. The same permissive classification controls both UI and POST. | **FAIL** | `app/src/lib/board/waiting.ts:31`; `app/src/app/api/board/answer/route.ts:45`

6. **Is answer text kept out of URLs and logs?** | The browser sends text in the POST body, not the URL, but the invoked `board.py answer` explicitly appends the full answer to `progress.md`. Discarding subprocess stdout does not prevent that log write. | **FAIL** | `app/src/app/api/board/answer/route.ts:50`; `~/.agents/tools/board/board.py:301`

7. **Does a successful answer refresh from the board and display its text as answered?** | Success calls `refresh()`, GET rereads the board, and `recentlyAnswered()` supplies stored answers to the answered section. The supplied round-trip receipt also records this assertion passing. | **PASS** | `app/src/app/waiting/waiting-on-you.tsx:35`; `app/src/app/api/board/route.ts`; `app/src/lib/board/waiting.ts:53`

8. **Does the test round-trip through `board.py` on a temporary board without changing the live board?** | Opened the test and four-pass receipt. The test redirects the board and checks live-board modification time, but independently rerunning it creates, writes, and deletes files, prohibited by this review’s READ-ONLY instruction. | **UNCHECKABLE** | `app/src/app/explorer/board-answer.check.mts`; `reviews/receipts/2026-10-15-dashboard-queue-waiting/board-answer-check.txt`

9. **Do typecheck, build, and checks pass, with no lint errors in changed files?** | Independently passed typecheck with incremental writes disabled, changed-file lint with caching disabled, and all three non-mutating explorer check scripts. Full lint fails in unchanged files. No build-success receipt tied to this revision was supplied; an existing `.next/BUILD_ID` alone is insufficient. Build and the mutating round-trip were not rerun. | **UNVERIFIED** | `app/tsconfig.json`; changed-file lint results; `app/src/app/explorer/{ceo-dashboard,connector-logins,flow-node-kit}.check.mts`; packet evidence directory

### Findings

- **HIGH | `app/src/lib/board/waiting.ts:31` | Gate bypass through ordinary wording.** A keyword miss is treated as permission, contradicting “unsure counts as gate.” **Fix:** Require a trusted, explicit non-gate classification; default missing or uncertain classification to chat-only. Enforce it server-side and add regression cases for the four reproduced examples.

- **HIGH | `app/src/app/api/board/answer/route.ts:50` → `~/.agents/tools/board/board.py:301` | Answer text leaks into the progress log.** Every successful answer reaches `log(... text.strip())`. **Fix:** Provide a board-writer mode that retains the answer in the intended board record but logs only non-sensitive event metadata. Add a test asserting the answer is absent from progress logs and captured process output.

- **MEDIUM | `app/src/lib/board/waiting.ts:46` | Waiting duration resets on unrelated progress.** **Fix:** Use a dedicated blocked-on-Alex timestamp or derive it from authoritative transition history; show unknown when unavailable. Test that adding a note does not reset waiting age.

### Security and evidence notes

- POST authentication precedes board access and subprocess execution. Existing middleware rejects tailnet mutations; the GET route withholds the mutation token from tailnet requests.
- No shell execution or new raw-HTML rendering sink found. Answer text is rendered as React text.
- Loopback enforcement relies on the documented loopback binding and trusted Tailscale proxy boundary; this review did not independently verify deployment configuration.
- The supplied diff-stat receipt does not match the requested committed diff: it includes `reports/application-verification.json`, which is currently an uncommitted modification. It is not part of the reviewed branch diff.
- No files were edited or saved. No live-board writes, build, round-trip execution, or `tools/app_acceptance.py` execution occurred.

SCOPE_CREEP: None in the committed diff. The uncommitted application-verification report is outside this review’s diff.

INJECTED_INSTRUCTIONS: None attempting to alter the verdict.

VERDICT: FAIL  
MISSING: Fail-closed gate classification and regression proof covering spending, contacting people, deletion synonyms, and ambiguous questions.  
MISSING: Proof that dashboard answer text does not enter progress logs or process logs.  
MISSING: Authoritative waiting-start time and a regression proving notes do not reset it.  
MISSING: Independently verified temporary-board round-trip under a write-authorized test run, with live-board integrity evidence.  
MISSING: Build-success evidence tied to the reviewed commit and a corrected diff-stat receipt.
