# Langflow control dashboard

**Status: seen working locally on October 13, 2026 (nodes build).** Add, delete, connect and disconnect components, the richer setting editors, and local runs of 18 components were seen working on the real engine and in the browser (desktop 1280 px and a 375 px phone-sized viewport, both emulated in the Claude desktop app's browser on this Mac). Tailnet stays read-only, checked on the new build through Tailscale Serve (read answers, write gets 403). Other-family review: in progress (findings fixed, two acceptance decisions pending). A real phone was not required. Evidence: `reviews/receipts/2026-10-13-langflow-nodes/`. Earlier evidence (October 12): `reviews/receipts/2026-10-12-langflow-fix/RESULTS.md`.

## What it does

- Pick a saved flow, see its canvas, change the supported settings, save with a version check, import and export the Langflow JSON, and run the flow.
- Add any of the engine's 63 current components from a searchable palette (keyboard: Tab to the search box, arrow keys, Enter; Escape returns to the search box). Delete components, connect and disconnect them by dragging between their typed connection points, with the Delete key, or with the Connect, Disconnect and Delete buttons in Settings (the keyboard and touch way).
- Every unsaved change is previewed by the server with the same rules as a save (a dry run that writes nothing). A change the server refuses is taken back out, with its reason. Each change has an Undo button.
- Settings: text, long text and prompts, numbers and sliders (with their range), on/off, dropdowns and tabs, and JSON boxes for dictionaries and tables (table rows must use the table's own columns). Editing a prompt creates or removes its `{variable}` inputs the way Langflow does.
- Each run shows its status, timestamps, the flow version it used, the engine version, the output, and any error.

## Three things, kept apart

| Layer | Where it lives | Can change it |
|---|---|---|
| Saved configuration (the only copy that runs) | `app/.data/langflow/flows/<id>.json` | Save from the panel, or import a file |
| Visual graph | Built from the saved file in the browser | Move components, rename, change supported settings |
| Run state | `app/.data/langflow/runs.json` and `run-inputs/` | Only the run itself |

Each run gets its own copy of the exact bytes it ran (`run-inputs/<run-id>.json`), so a save made mid-run cannot change which version ran.

## What runs here (Alex's rule, 2026-10-13: runs stay local)

The component list and every template come from the installed engine's own `lfx/_assets/component_index.json` (`GET /api/langflow/components`). Legacy components are not offered. Tiers: `app/src/lib/langflow/tiers.ts`.

| Group | Count | Runs here |
|---|---|---|
| Local, proven on the real engine | 18 | Yes: Chat Input, Chat Output, Calculator, Current Date, Mock Data, If-Else, Notify, Listen, Loop, Character, Recursive Character and Language Recursive text splitters, HTML Link Extractor, Prompt Template, Dynamic Create Data, Parser, Split Text, Type Convert |
| Local, not proven | 4 | No: Natural Language Text Splitter (NLTK not installed), Data Operations (its settings need a Langflow server), Message History (returned nothing), Fake Embeddings (no local consumer can show its output) |
| AI model, internet, code or files, Langflow server | 41 | No: show and edit only |

- A run needs a Chat Output. Chat Input is optional (flows such as Current Date to Chat Output run without it, and the message is then not used).
- A component runs only when its code is byte-identical (full sha256) to the installed engine's built-in component. An edited, older or relabelled component is refused with the reason, so a flow from elsewhere cannot run its own Python under an enabled name. A real component labelled as a note is an error (the engine only skips `type: noteNode`).
- Runs record the engine that actually ran, read from the engine's files (for example `lfx 1.12.6rc3`).

## Not supported yet (on purpose)

- Editing the `code` field (Langflow runs it). Read-only, shown as its line count.
- Secret values. The dashboard never stores them: password fields, and values under secret-looking names (token, key, password, authorization and the like) inside JSON settings. Edits with them are refused, imports have them removed (and the count is reported), exports and the panel show `[redacted]`.
- Settings that need a running Langflow server to show their real fields (Data Operations' operation picker, Human Input's action picker) or that pick files, models or MCP servers. Read-only, with the reason.
- Running AI model, internet, code, file or server components (see above). `/api/generate-text` still points to `disabled-ai`.
- Cancel inside Langflow. Stop kills the local engine process. That path is tested with a stand-in process, and the real engine is not separately tested for Stop.

## Run it on the Mac

The app binds only to 127.0.0.1. Tailscale Serve proxies port 3200. Use the current system-map-ir checkout.

Install the pinned engine (once). Note: a plain install picks lfx 1.12.6rc3 (a release candidate), because the provider add-ons (lfx-openai and others) declare `lfx>=1.12.0.dev0`, which lets pip pick pre-releases; the second command below pins lfx 1.12.5. Alex's venv runs lfx 1.12.5 since 2026-10-13. Most October 13 receipts ran on 1.12.6rc3; the later ones (review fixes, validator proof) ran on Alex's venv after it moved to lfx 1.12.5. Code differs between the two for Type Convert and Data Operations only, so a flow saved with rc3's Type Convert must have it re-added from the palette (the run gate says so). After any engine change, rerun the live tests below:

```bash
python3.11 -m venv ~/.venvs/langflow-dashboard
```

```bash
~/.venvs/langflow-dashboard/bin/pip install langflow==1.12.5
```

```bash
~/.venvs/langflow-dashboard/bin/pip install 'lfx==1.12.5'
```

Start the app on port 3200 (the port Tailscale Serve uses):

```bash
cd ~/Projects/system-map-ir/app && LANGFLOW_LFX_BIN=$HOME/.venvs/langflow-dashboard/bin/lfx LANGFLOW_CONFIG_DIR=$HOME/.venvs/langflow-dashboard/config npm run dev -- -p 3200
```

## Start at login (set up 2026-10-13)

Two login items keep both servers running after a restart (originals backed up to `~/Backups/launchagents-20261013/`):

| Login item | Runs | Address |
|---|---|---|
| `~/Library/LaunchAgents/com.alex.system-map.plist` | `next dev` directly (no npm wrapper) from `~/Projects/system-map-ir/app`, with `LANGFLOW_LFX_BIN` and `LANGFLOW_CONFIG_DIR` set | 127.0.0.1:3200 (Tailscale Serve proxies it) |
| `~/Library/LaunchAgents/com.alex.langflow-server.plist` | `tools/langflow_server.sh` | 127.0.0.1:7860 (this Mac only) |

Restart either one: `launchctl kickstart -k gui/$(id -u)/com.alex.system-map` (or `com.alex.langflow-server`).
Logs: `app/.data/dev-server.log` and `app/.data/langflow-server.log`.

## Langflow on this Mac (Open in Langflow)

The palette's **Open this flow in Langflow** sends a copy of the saved flow to the real Langflow app on this Mac
and opens its editor in a new tab. Use it for everything that only runs in Langflow (AI models, internet, files).
Secrets are never sent. Only the owner on this Mac sees the button; the tailnet never does (403).

Start Langflow (loopback only, port 7860, data in `app/.data/langflow-server`):

```bash
~/Projects/system-map-ir/tools/langflow_server.sh
```

The dashboard finds it at `LANGFLOW_SERVER_URL` (default `http://127.0.0.1:7860`); any non-loopback address is
refused. If Langflow is not running, the button says so instead of failing.

Keys (read from 1Password at every Langflow start by `tools/langflow_server.sh`, never written to a file or printed):

| Key | 1Password item (Connectors vault) | What it does |
|---|---|---|
| OpenRouter | "OpenRouter - Langflow" (daz37abakr3thickvjpfxle5ni) | AI models in Langflow: pick the OpenRouter component and the `OPENROUTER_API_KEY` global variable. Capped at $100 a month in OpenRouter (key "Langflow (system map, $100/mo)", resets monthly). Spend approval: Alex, 2026-10-14. Langflow keeps the variable encrypted in its own database. |
| Langfuse | "Langfuse - Langflow" (rxoo6lpuxbca67oj4yofie45sm) | Traces of every Langflow run go to the Langfuse project "Langflow" (us.cloud.langfuse.com, set up 2026-10-14), kept apart from the Claude Code and Codex traces in "Increase Roas". Traces show up up to about 15 minutes after a run (seen 2026-10-14: between 5 and 15 minutes). |

AI runs happen only in Langflow, never in the dashboard; that is the only place money is spent.

The palette also has four **starter flows** (Reply template, Message router, Text chunker, Dated note) that run
here with one tap. Each is proven on the real engine in `starters-langflow.test.mts`.

## Tests

Unit and route tests (no port needed, about 2 seconds):

```bash
cd ~/Projects/system-map-ir/app && node --import ./src/lib/langflow/tests/register.mjs --test src/lib/langflow/tests/handles-policy.test.mts src/lib/langflow/tests/model.test.mts src/lib/langflow/tests/runner.test.mts src/lib/langflow/tests/store-runs.test.mts src/lib/langflow/tests/routes.test.mts src/lib/langflow/tests/network-boundary.test.mts src/lib/langflow/tests/catalog.test.mts src/lib/langflow/tests/edits.test.mts src/lib/langflow/tests/settings.test.mts src/lib/langflow/tests/review-fixes.test.mts src/lib/langflow/tests/review2.test.mts src/lib/langflow/tests/starters-langflow.test.mts
```

Live engine acceptance (runs the real `lfx` engine, about 3 seconds):

```bash
cd ~/Projects/system-map-ir/app && LANGFLOW_LIVE_ENGINE=1 LANGFLOW_LFX_BIN=$HOME/.venvs/langflow-dashboard/bin/lfx LANGFLOW_CONFIG_DIR=$HOME/.venvs/langflow-dashboard/config node --import ./src/lib/langflow/tests/register.mjs --test src/lib/langflow/tests/live-engine.test.mts src/lib/langflow/tests/live-components.test.mts src/lib/langflow/tests/components-live.test.mts
```

`live-components` builds one small flow per enabled component through the save route and runs it on the real engine (about 40 seconds). `components-live` adds each of the 63 current components through the save route and runs `lfx validate` on the saved file (about 3 minutes).

To build or serve for a check without touching the `.next` folder of a dev server that is already running from this checkout, set `NEXT_DIST_DIR=.next-verify`.

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

## Evidence (nodes build, October 13, 2026)

All in `reviews/receipts/2026-10-13-langflow-nodes/`. Engine: lfx 1.12.5 in `~/.venvs/langflow-dashboard` since 2026-10-13 (earlier rows ran on 1.12.6rc3). Latest full execution: `run-receipt-4eb50e0.txt`.

| Requirement | Status | Evidence |
|---|---|---|
| Catalog: 63 current components, tiers 22 local and 41 show only, 0 unknown | PASS (live) | `step1-catalog.txt` |
| Each of the 63 added through the save route; strict `lfx validate` levels 1 and 3 exit 0; saved code identical to the engine's | PASS (live) | `review-f3-validator.txt` (the engine's level 2 cannot run and its level 3 compares the wrong field: both upstream, recorded) |
| Each of the 18 enabled in a wired flow: `lfx validate --skip-components --skip-credentials` exit 0 (level 2 cannot run in this engine; credentials are never stored), every edge proven compatible, real run output | PASS (live, 1.12.5) | `review-f3-validator.txt`, `run-receipt-4eb50e0.txt` |
| Secrets nested in JSON settings refused, stripped on import, hidden in read, dry run and export | PASS (API) | `review2.test.mts`, executed in `run-receipt-4eb50e0.txt` |
| Every editable setting of all 63 components re-saves byte for byte (256 settings) | PASS (live sweep) | `review2.test.mts` |
| Palette by keyboard, add and save in the browser | PASS (browser, 1024 px) | `step2-palette.txt` |
| Add, delete, connect, disconnect; refused edits save nothing; Langflow-identical handle bytes | PASS (API) | `step3-edits.txt` |
| Tailnet and token-less callers get 403 on every new edit kind and on dry runs | PASS (API) | `edits.test.mts`; middleware and policy unchanged |
| Canvas wiring in the browser; rewired flow validates and runs on the engine | PASS (browser, 1280 px) | `step4-canvas.txt` |
| Setting editors; every editable setting round-trips byte for byte | PASS (API and browser) | `step5-settings.txt` |
| 18 enabled components produce their real output on the engine; 4 local ones refused with reasons | PASS (live) | `live-components.txt` |
| Security and correctness review findings fixed, one regression test each | PASS (API, live recheck) | `review-fixes.txt` |
| Desktop: build a Calculator flow, save and run (result 14) | PASS (browser, 1280 px) | `final-checks.txt`, `desktop-1280-calculator-run.jpg` |
| Phone-sized viewport: palette by tap, Undo, run (result 42), no horizontal overflow | PASS (emulated 375 px viewport, not a real phone) | `final-checks.txt`, `phone-375-calculator-run.jpg` |
| Tailnet check of this build: read answers, write refused | PASS (Alex's Terminal, Tailscale Serve) | `fix-everything.txt` |
| Real phone or second device, touch gestures on the canvas | NOT RUN (not required by the brief) | |

## Evidence (October 12, 2026)

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
- Only the 18 proven local components execute, and only with the engine's own code. Paid model and tool flows remain disabled.
- Browser reload, 390px viewport measurement and same-Mac HTTPS Serve access were tested. A physical phone, touch gestures and a separate remote device were not tested.
- A same-family independent technical check passed. Formal other-family alex-reviewer and Director acceptance are pending; no paid review was launched.

## Integration checklist

Labels: Working, Needs implementation, Blocked, Not required for this milestone, Not verified.

| Item | Label | Evidence |
|---|---|---|
| Langflow engine (`lfx` run and validate) | Working on lfx 1.12.5 (langflow 1.12.5) | Live tests PASS on 2026-10-13 on 1.12.6rc3 and 1.12.5; validator limits in `review-f3-validator.txt` |
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
