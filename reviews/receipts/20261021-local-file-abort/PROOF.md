# Local source-read cleanup correction

Code identity: `91e36f4`, compared with `b2cef74`.

Alex reported a Next.js 15.5.25 development overlay with `Runtime AbortError: signal is aborted without reason`, pointing to the source-read effect's `controller.abort()` cleanup in `local-file-repair-panel.tsx`.

The bounded local source GET now finishes without transport cancellation. An effect-local ignore flag discards success and error callbacks after cleanup. Suggestion, Preview, Apply and Undo cancellation and generation checks are byte-identical to the baseline. No backend or agent-source mutation code changed.

## Checks

- `node tools/test_local_file_repair_source.cjs`: five passed. The test executes the actual transpiled component with a deterministic hook/fetch harness, without a DOM or real AI calls. It covers pending cleanup, obsolete success and error responses, current success, and visible current read errors.
- Independent verifier substituted the baseline component in memory: four passed and the transport-abort assertion failed. The corrected component passed all five. A separate reporting wrapper expected TAP formatting and exited 1 after the baseline run; it did not alter the raw test outcomes.
- `cd app && ./node_modules/.bin/tsc --noEmit --incremental false`: passed. The final canonical-checkout exit status and process/commit readback are captured in [cli-verification.json](cli-verification.json).
- Independent context-separated GPT-6.1 verifier inspected the actual diff and test, repeated the focused test, and confirmed the backend and remaining operation code were unchanged. No code defects found.

## Running-browser observations

Tested the canonical checkout on `http://127.0.0.1:3201/explorer?view=local-files` in the in-app browser after integrating the code. The listening process's working directory was independently checked as the canonical `alex-system-map/app`.

1. Opened the actual generated Codex rules file's Review & fix panel. The current source loaded and displayed its owning-source links, without a runtime overlay.
2. Held both development-mode source GET requests at the browser network boundary, navigated to CEO, then supplied synthetic late responses. The repair panel stayed closed and obsolete content never appeared. No window error or unhandled rejection was recorded.
3. Supplied synthetic HTTP 500 source responses. The panel displayed the read failure and left its loading state. No runtime overlay, window error, or unhandled rejection appeared.
4. Cleared request interception, reopened the actual source, and verified its real path and owning-source links with no error or loading indicator. Removed the temporary error listeners. Network throttling was restored to normal. No real AI inference or agent-source writes were performed for this regression check.

Raw browser results: [runtime-verification.json](runtime-verification.json). Final screenshot: [Review panel](review-panel.png).

The independent verifier could not access this context's in-app browser. Its access result is preserved in [browser-verification.json](browser-verification.json); runtime acceptance therefore reviews the primary's directly captured browser records and screenshot.

## Limits

The original overlay did not reproduce in the current browser before the change, including a throttled read/navigation check. This corrects the specific unnecessary abort call shown in Alex's screenshot; it does not prove why that normally caught cancellation escaped to the development overlay on the reported occurrence. The deterministic tests do not emulate React's scheduler or Next's overlay. Browser checks prove the tested opening, pending-cleanup and read-error paths on this runtime.

Reference: React's documented fetch-effect cleanup uses an ignore flag to discard obsolete responses: https://react.dev/reference/react/useEffect#fetching-data-with-effects.
