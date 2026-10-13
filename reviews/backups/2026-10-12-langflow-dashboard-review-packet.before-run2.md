# Review packet: Langflow control dashboard

For: alex-reviewer. Run it on a different model family from the preparer.
Prepared by: claude-haiku-5-5 (Anthropic family), Claude Code session in ~/Projects/system-map-ir.
Note: the harness index in CLAUDE.md says every agent runs on Sonnet. This session ran on Haiku 5.5.
Date: 2026-10-12
Branch: langflow-dashboard, HEAD 56e0c65
Task or node ID: none in the brief. The Director supplies it.

**Status: NOT DONE.** Browser checks are BLOCKED. Tailscale checks are UNVERIFIED. Nothing is pushed.

## Commits (seen this session with git log)

- 2bf1a7e Add gap-fill Claude harness for alex-system-map (23 files, harness only)
- d63becc Add Langflow control dashboard prototype (local, lfx engine) (29 files)
- 56e0c65 Point operator commands at the renamed folder system-map-ir (docs/LANGFLOW_DASHBOARD.md only)

Push state (seen): `git remote -v` prints nothing and `git branch -r` lists no remote branches. Nothing could have been pushed from this checkout.

## Acceptance, from Alex's brief (2026-10-12)

1. Browser checks, desktop and phone, keyboard and touch, on 127.0.0.1:3200 only. **BLOCKED.** The app has not been started. It waits for Alex to confirm `sandbox.network.allowLocalBinding: true`.
2. Tailscale private access and denial checks. **UNVERIFIED (BLOCKED).** `tailscale serve status` and `tailscale status` both print "The Tailscale CLI failed to start: Failed to load preferences." The exit code printed as 0, so the message is the evidence. The cause is not known. The sandbox may be the cause, and I did not bypass it.
3. Do not change the /api/health token exposure or the tailnet read-only rule without Alex's approval. **HELD.** No change made in this session.
4. Do not push, do not mark done, send nothing outside this machine. **MET in this session.** No push is possible, no done marking, no outside messages.
5. Ask before spend or outside messages. **MET in this session.** No spend, no outside messages.

## Previously reported results (from docs/LANGFLOW_DASHBOARD.md, NOT re-run in this session)

The brief said not to redo these. They are reported, not re-observed here:
- `tsc --noEmit`: 0 errors
- `npm run build`: exit 0
- `flow-node-kit.check.mts`: 45 PASS, 0 FAIL
- Unit and route tests: 53 pass
- Live engine test (`live-engine.test.mts`): succeeded on lfx 1.12.5 in about 3 s

## Evidence paths

- docs/LANGFLOW_DASHBOARD.md: status, evidence table, blockers, open decisions
- app/src/lib/langflow/: model.ts, policy.ts, runner.ts, runs.ts, store.ts, redact.ts, api.ts, handles.ts, fixtures/
- app/src/lib/langflow/tests/: handles-policy, model, runner, store-runs, routes, live-engine (.test.mts), plus register.mjs and resolve-hook.mjs
- app/src/app/api/langflow/**: routes for flows, runs, stop, status, export
- app/src/app/explorer/langflow-panel.tsx and system-explorer.tsx
- app/.data/langflow/access.json: ABSENT in this checkout, so the owner-only rule applies
- app/.data/langflow/: ABSENT in this checkout, so there are no saved flows or run records here

## Findings for the reviewer

1. **The documented start command listens on every interface.** docs/LANGFLOW_DASHBOARD.md line 45 runs `npm run dev -- -p 3200` with no `-H 127.0.0.1`. Next 15.5.25 sets no default host. Its own comment says so: "We do not set a default host value here" (app/node_modules/next/dist/cli/next-dev.js lines 192 to 194). The server therefore listens on the LAN too. Tailscale Serve identity headers only exist on traffic through Serve. Direct LAN access was not tested, so its read-only treatment is not verified. Recommended fix: add `-H 127.0.0.1` to the documented command. The browser checks will use it.
2. **Tailscale access rules are unverified on a real tailnet.** The "PASS (synthetic headers)" rows used fake headers only.
3. **/api/health returns the local mutation token.** Middleware also lets tailnet devices read /api/*. The doc recommends removing the token from /api/health. That is an authentication change, so it is held for Alex.
4. **Rollback has not been run as a test.** docs/LANGFLOW_DASHBOARD.md line 76 says so.
5. **Lint evidence is weak.** The doc says no lint problems in changed files, but no baseline comparison was run (line 87).
6. **Open decisions for Alex** (doc lines 108 to 112): may tailnet devices save or run; may LLM-calling flows run; keep lfx or move to the Langflow server API; remove the token from /api/health.

## Commands the reviewer can run (not run by the preparer)

- Unit and route tests, no port needed: the command in docs/LANGFLOW_DASHBOARD.md under "Tests".
- Live engine test: needs `LANGFLOW_LFX_BIN` set to the lfx binary in the venv. The venv path is set in the doc. Not run here.

## Still needed from Alex before the checks can finish

- Confirm `sandbox.network.allowLocalBinding: true` in Claude settings. It applies without a restart.
- Run `tailscale serve status` in his own terminal, outside the Claude sandbox, and share the output. Redact anything he does not want in chat.
- Decide the open items in finding 6.
