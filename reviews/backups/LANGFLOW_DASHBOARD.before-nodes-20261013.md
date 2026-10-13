# Langflow control dashboard

**Status: seen working locally and through Tailscale Serve on October 12, 2026.** Browser import, edit, save, reload and a harmless engine run passed. Tailnet viewing is read-only. Other-family review and a physical second-device check remain pending. Evidence: `reviews/receipts/2026-10-12-langflow-fix/RESULTS.md`.

## What it does

- Pick a saved flow, see its canvas, change the supported settings, save with a version check, import and export the Langflow JSON, and run the flow.
- Each run shows its status, timestamps, the flow version it used, the engine version, the output, and any error.

## Three things, kept apart

| Layer | Where it lives | Can change it |
|---|---|---|
| Saved configuration (the only copy that runs) | `app/.data/langflow/flows/<id>.json` | Save from the panel, or import a file |
| Visual graph | Built from the saved file in the browser | Move components, rename, change supported settings |
| Run state | `app/.data/langflow/runs.json` and `run-inputs/` | Only the run itself |

Each run gets its own copy of the exact bytes it ran (`run-inputs/<run-id>.json`), so a save made mid-run cannot change which version ran.

## Not supported yet (on purpose)

- Adding or deleting components or connections on the canvas. Use Langflow's own editor for that. That editor is not running in this build.
- Editing the `code` field (Langflow runs it). Read-only.
- Secret values. The dashboard never stores them. Imports have secrets removed (and the count is reported), and exports show them as `[redacted]`.
- Running flows that use a model, tool or code step. Refused until Alex approves, because AI execution is turned off in this app (`/api/generate-text` points to `disabled-ai`). Only Chat Input to Chat Output flows run.
- Cancel inside Langflow. Stop kills the local engine process. That path is tested with a stand-in process, and the real engine is not separately tested for Stop.

## Run it on the Mac

The app binds only to 127.0.0.1. Tailscale Serve proxies port 3200. Use the current system-map-ir checkout.

Install the pinned engine (once):

```bash
python3.11 -m venv ~/.venvs/langflow-dashboard
```

```bash
~/.venvs/langflow-dashboard/bin/pip install langflow==1.12.5
```

Start the app on port 3200 (the port Tailscale Serve uses):

```bash
cd ~/Projects/system-map-ir/app && LANGFLOW_LFX_BIN=$HOME/.venvs/langflow-dashboard/bin/lfx LANGFLOW_CONFIG_DIR=$HOME/.venvs/langflow-dashboard/config npm run dev -- -p 3200
```

## Tests

Unit and route tests (no port needed, about 2 seconds):

```bash
cd ~/Projects/system-map-ir/app && node --import ./src/lib/langflow/tests/register.mjs --test src/lib/langflow/tests/handles-policy.test.mts src/lib/langflow/tests/model.test.mts src/lib/langflow/tests/runner.test.mts src/lib/langflow/tests/store-runs.test.mts src/lib/langflow/tests/routes.test.mts
```

Live engine acceptance (runs the real `lfx` engine, about 3 seconds):

```bash
cd ~/Projects/system-map-ir/app && LANGFLOW_LIVE_ENGINE=1 LANGFLOW_LFX_BIN=$HOME/.venvs/langflow-dashboard/bin/lfx LANGFLOW_CONFIG_DIR=$HOME/.venvs/langflow-dashboard/config node --import ./src/lib/langflow/tests/register.mjs --test src/lib/langflow/tests/live-engine.test.mts
```

## Access

- **You, on this Mac, with the local token:** read, save, run, stop.
- **Loopback without the token:** read only.
- **Tailnet devices (Tailscale Serve adds `Tailscale-User-Login`):** read only, and only for logins listed in `app/.data/langflow/access.json`. This is Alex's rule from 2026-10-12: changes and runs stay on the Mac.
- A missing `access.json` gives the owner everything on this Mac and nobody else. A malformed file denies everything and says why.

```json
{ "owner": { "ops": ["read", "save", "run", "stop"], "flows": "*" }, "tailnet": { "you@example.com": { "ops": ["read"], "flows": "*" } } }
```

## Backup and rollback

- Every save copies the previous flow to `app/.data/langflow/history/<flow-id>/<time>-<hash>.json`. The last 50 are kept.
- Rollback: copy the chosen history file over `app/.data/langflow/flows/<flow-id>.json`. The rollback steps are documented; the restore itself has not been run as a test yet.
- Run history: `app/.data/langflow/runs.json`. A damaged file is renamed to `runs.json.corrupt-<time>` and never deleted.
- `app/.data/` is git-ignored, so backups are yours: copy that folder.

## Evidence

| Requirement | Status | Evidence |
|---|---|---|
| Existing dashboard still builds | PASS | `npm run build` exit 0 before and after the change; 728 kB explorer route |
| Existing Flow Builder checks still pass | PASS | `flow-node-kit.check.mts`: 45 PASS, 0 FAIL, before and after |
| Type check | PASS | `tsc --noEmit` 0 errors |
| Lint | No lint problems in changed files | `next lint` reports problems in four files this work did not touch; none of the new or changed files appear. No baseline lint comparison was run |
| Langflow to dashboard (import, canvas, no-edit round trip) | PASS | `model.test.mts`: no-edit apply returns the same flow; unknown fields kept |
| Dashboard to Langflow (saved file validates and runs) | PASS | `lfx validate` clean; `lfx run` returns the input |
| Edit, save, reload with version check | PASS (API) | `routes.test.mts`: stale hash gives 409; refused edit saves nothing; move saves |
| Real harmless run through the route into the real engine | PASS | `live-engine.test.mts`: succeeded in 3 s on engine 1.12.5, echoed the message, recorded the flow hash |
| Invalid wiring, missing settings, unavailable components | PASS (API) | Import refused for broken connection; run refused for model or tool steps and for errors |
| Engine missing or not configured | PASS (API) | 503 when not configured; `runner.test.mts` for missing binary |
| Duplicate clicks | PASS (API) | Second run gets 409 with the running record; same Idempotency-Key returns the first run |
| Stop | PASS (stand-in process) | `runner.test.mts`, `routes.test.mts`: process killed, record says stopped |
| Refresh and reconnect show real state | PASS (API and browser reload) | Saved setting and completed run remained visible after a browser reload; server restart recovery retains its API test coverage |
| Histories isolated per browser session | PASS (API) | Another session sees none of the runs |
| Secrets absent from responses, exports, engine environment | PASS (API) | Export and import tests; engine receives no provider keys |
| Tailnet is read-only; unlisted devices denied | PASS (synthetic headers) | `handles-policy.test.mts`, `routes.test.mts` |
| Real Tailscale private access | PASS from this Mac through Serve | Browser renders saved flow; import/save/run/stop return 403 remotely; remote health has no token |
| Desktop and narrow layout, keyboard | PASS for browser checks | Actual 390px viewport measured; no document overflow or component/aside overlap; Tab reaches Run. Physical phone/touch remains untested |

## Current access and remaining verification

- Local owner controls initialize only after the local credential loads. Status and flow-detail requests use that credential.
- Tailnet health returns a minimal health object, never the local credential or filesystem paths. Responses are not cached. Tailnet identities cannot become local owners by changing Host.
- The existing Tailscale owner login is configured for read only in the ignored local `app/.data/langflow/access.json`. Other logins are denied by the Langflow policy.
- Development and start commands bind loopback by default. Serve configuration remains private to the tailnet.
- The local credential was rotated after closing the exposure. No credential is in the receipts.
- Only harmless Chat Input to Chat Output flows execute. Paid model/tool flows remain disabled.
- Browser reload, 390px viewport measurement and same-Mac HTTPS Serve access were tested. A physical phone, touch gestures and a separate remote device were not tested.
- A same-family independent technical check passed. Formal other-family alex-reviewer and Director acceptance are pending; no paid review was launched.

## Integration checklist

Labels: Working, Needs implementation, Blocked, Not required for this milestone, Not verified.

| Item | Label | Evidence |
|---|---|---|
| Langflow 1.12.5 engine (`lfx` run and validate) | Working | Live test PASS; `lfx validate` clean |
| Langflow server API (`/api/v1/run`, `/api/v1/flows`) | Needs implementation (blocked by port) | Routes read from installed 1.12.5 source; not called live |
| Model providers (OpenAI, Anthropic, others) | Not required for this milestone | AI execution off; no provider keys stored or passed |
| Data stores | Working (local files) | `app/.data/langflow/` store and run records |
| Composio | Not required for this milestone | No Langflow component wired to it |
| MCP / Hermes | Not required for this milestone | Not wired |
| Honcho | Blocked | No package, skill or doc hit locally |
| PersonaPlex | Blocked | No local evidence; a separate streaming-audio service is needed. Microphone, playback, interruption, latency and session isolation are untested |
| Judge | Not required for this milestone | The Judge node exists only in the Flow Builder kit, not in Langflow |
| Latitude | Not verified | Grep hits were unrelated text |
| DOGA | Not verified | No meaningful hit |
