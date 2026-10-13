---
paths:
  - "app/src/app/api/**"
---

# API routes (app/src/app/api/**)

Facts below were read at base commit c833d7f. If a name has moved, re-read the file before relying on this.

- **Authorize every mutation (POST, PUT, PATCH, DELETE) before reading the body or touching data.** Use `assertMutationAuthorized(request)` from `src/lib/server/local-auth.ts`: loopback Host, loopback or absent Origin, and a matching `x-local-token`. Existing examples: `api/workflow`, `api/catalog/edit`, `api/presentation`. The planned Langflow proxy authorizes through its own per-user check instead; say so in a comment at the top of that handler, and still require a verified identity.
- **Return JSON errors, never a thrown `Response`.** Next turns a thrown `Response` into a 500. Call `mutationAuthError(request)` (same file: wraps the assert, returns a JSON `Response` or `null`) and return its result when it is not null. A bare `assertMutationAuthorized` in a handler is a bug unless a try/catch converts it.
- **Error shape is `Response.json({ error: '<short message>' }, { status })`.** 400 bad input, 401 missing or wrong token, 403 non-loopback host or origin, 404 unknown id, 409 revision conflict, 500 only for a real server fault. Do not change the shape or status of an existing route without saying so: the UI and `tools/*_acceptance.py` read them.
- **No credentials in responses, errors or logs.** No token, key, header value, env value or raw child-process stderr. Output that comes back through `runLocalService` (`src/lib/server/python.ts`) is already screened there. Anything else that reaches a response or log (a Langflow reply, a file read, an error message) must use that same screening. `screenServiceText` and `screenParsedValue` are module-private at base: export them, do not write a second regex.
- **Known exception, do not copy:** `GET /api/health` returns the local mutation token. `middleware.ts` lets tailnet GET and HEAD requests through (Host ending `.ts.net` plus a `Tailscale-User-Login` header), so every GET handler is readable by any tailnet viewer. Keep secrets and per-user data out of GET responses unless the handler checks the Tailscale-User-Login identity.
- **Validate untrusted input** (query, body, uploaded flow JSON) with zod, which is already a dependency. Cap the size. Never build a file path or shell command from it. Python is reached only through `runLocalService` (fixed script, fixed argv, 120 s deadline).
- **Keep handlers thin:** parse, authorize, call a function in `src/lib/server/`, return JSON. Logic that `tools/*_acceptance.py` must exercise belongs in lib code, not inline.
- `/api/generate-text` and `/api/generate-image` are rewritten to `/api/disabled-ai` in `next.config.ts`. Do not wire a model call back in without Alex.
