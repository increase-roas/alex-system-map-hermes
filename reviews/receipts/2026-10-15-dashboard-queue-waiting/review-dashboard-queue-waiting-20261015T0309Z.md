# Codex review round 3 (turn 01a13d88)

NODE: alex-system-map/dashboard-queue-waiting  
WORKER: Claude Opus 5.5  
REVIEWER: Codex, GPT-6 family  
DIFF: `57f2ed3..d7a9625`

### Acceptance

1. **Does `/queue` show each open item, age, owner fallback, origin, aged wording, recent fixes, and the required empty state?** | The component renders the required snapshot fields and messages. | **PASS** | `app/src/app/queue/fix-queue.tsx`

2. **Does `/api/review-queue` read only the specified file, server-side and read-only?** | One filesystem read, defaulting to the specified queue export; no writes in the handler. | **PASS** | `app/src/app/api/review-queue/route.ts`; `app/src/lib/server/paths.ts`

3. **Does `/waiting` show title, request, and elapsed waiting time?** | Waiting start comes from the blocked-on-Alex progress entry; notes do not reset it, and missing evidence yields unknown. Regression checks passed. | **PASS** | `app/src/lib/board/waiting.ts`; `board-gate.check.mts`

4. **Do explicitly eligible non-gate questions get an authenticated Answer control using `board.py`, argument-list execution, and the required source?** | The successful round-trip verified answer persistence and source format; missing-token rejection passed. The route authenticates before execution, uses `execFile`, and does not directly write the board. | **PASS** | `app/src/app/api/board/answer/route.ts`; `board-answer.check.mts`

5. **Are gate and uncertain questions chat-only and refused server-side?** | Untagged requests now default to gate. Explicit `dashboard-ok:` classification is required, with additional risky-word and blanket-approval rejection. Regression checks passed; the integration test rejected a tagged spend question. This relies on the asking agent correctly assigning the explicit non-gate classification. | **PASS** | `app/src/lib/board/waiting.ts:52`; `board-gate.check.mts`; `board-answer.check.mts`

6. **Does answer text stay out of URLs and application logs, with the accepted board-audit exception?** | Applying the criterion-6 decision you identified: board audit persistence is allowed. Requests use the POST body; the successful round-trip confirmed its sample answer was absent from Next stdout/stderr. The prior progress-log finding is closed under this amendment. | **PASS** | `AGENTS.md:22`; packet Round 3; `board-answer.check.mts`

7. **Does answering refresh from the board and display the stored answer?** | The successful round-trip verified removal from waiting and retrieval through the answered view; the UI refreshes after success. | **PASS** | `app/src/app/waiting/waiting-on-you.tsx`; `board-answer.check.mts`

8. **Does the round-trip test reliably target a temporary board, never the live board?** | One run passed, including the live-board mtime assertion. However, the test can connect to an unrelated existing server: it randomly selects among ports 3190–3239 and treats any successful `/api/board` response as readiness. It does not verify that its child server owns the listener before fetching a token and sending POSTs. | **FAIL** | `app/src/app/explorer/board-answer.check.mts:13`; `app/src/app/explorer/board-answer.check.mts:33`

9. **Do typecheck, build, and check scripts pass, with no changed-file lint errors?** | Typecheck, changed-file lint, and all pure checks passed. The build receipt covers identical application source: changes after `980dfb1` are instructions and review documents only. But the round-trip initially failed three of four tests and passed on retry; its isolation defect remains unresolved. | **FAIL** | `final-checks.txt`; independently executed checks; `board-answer.check.mts`

### Finding

**HIGH | `app/src/app/explorer/board-answer.check.mts:13` | Round-trip test can send authenticated POSTs to an unrelated dashboard instance.**

The test chooses a random port from a range containing existing dashboard listeners. Its readiness loop accepts any HTTP-success response from `/api/board`, without checking child-process startup or fixture identity. It then obtains that server’s token and submits answers.

Observed during this review:

- First run: fixture ticket missing; gate POST returned **409 instead of 403**; answer POST returned **409 instead of 200**.
- Existing listeners were present on **3200, 3201, and 3210**.
- Retry: all four tests passed, including the live-board mtime assertion.

A port collision is the likely explanation for the first run, not conclusively proven because the selected port and child startup error are not reported. The unsafe readiness logic is independently established by the code. **No successful live-board mutation was observed.**

**Fix:** Start on an OS-assigned available port, verify successful startup of the spawned child, and fail immediately if it exits. Before any POST, verify a unique per-run fixture identity from that server. Add a regression with an occupied port proving that the test neither obtains credentials nor sends mutations to the unrelated listener.

### Security and scope

The application’s POST authentication, argument-list execution, and React text rendering remain intact. No new shell-injection or raw-HTML/XSS sink found. The remaining security issue is in the test harness’s target selection, not the application’s token check.

The corrected historical diff-stat no longer includes the dirty application-verification report. That uncommitted report remains outside the reviewed diff.

No source or receipt files were edited. The permitted test created and removed temporary files. Neither the build nor `tools/app_acceptance.py` was run.

SCOPE_CREEP: None in the requested committed diff.

INJECTED_INSTRUCTIONS: None. The criterion-6 amendment was applied as the decision explicitly identified in your Round 3 request.

VERDICT: FAIL  
MISSING: Test-server ownership verification and collision-safe port allocation before obtaining a token or issuing any POST.  
MISSING: An occupied-port regression proving no requests can mutate an unrelated instance, followed by a passing temporary-board round-trip with live-board integrity verification.
