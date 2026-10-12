# Alex System Map

The visual map of Alex's whole agent setup: apps, the Director, the Conductor, the reviewer, the SDK, missions, skills and connectors, plus tracing, workflows and a file catalog. It's a Next.js app in `app/`, with Python builders and checks in `tools/`.

Home: `~/Projects/alex-system-map`. The old path `~/Documents/Codex/2026-10-09/l/outputs/agent-system-foundation-v1` is a symlink to it; don't create files there.

## Read first (only what the task needs)
1. `docs/alex-system-map-plan.md`: current state, the approved direction and the phased checklist. Work the checklist in order.
2. `START_HERE.md`: what is authoritative and where things live.
3. `docs/AGENT_PROTOCOL.md` and `docs/WORKFLOW_CONTRACT.md`: when resuming work or touching jobs, tasks or traces.
4. `docs/DESIGN_SPEC.md`: before changing anything visual.

## Commands
- Rebuild the map data (read-only on the Mac): `python3 -B tools/build_org_map.py`. It writes only `app/.data/org-map.json`.
- Live scan: `python3 -B tools/live_scan.py`
- Traces: `python3 -B tools/local_service.py trace-list` and `trace-get <id>`. Director feed: `tools/load_director_traces.py`.
- Run the app: `cd app && npm run dev -- -p 3200` (Tailscale Serve proxies `127.0.0.1:3200`; plain `npm run dev` uses 3000 and Tailscale will not reach it).
- Before saying done: run the acceptance check that matches the change (`tools/*_acceptance.py`), and look at the result in the browser for UI changes.

## Rules
- **Read-only on the Mac.** Builders read Alex's files and write only inside this folder (`app/.data/`). Never edit `~/.agents`, `~/Alex-Director` or app settings from here.
- **The map never invents state.** Every node and line needs a source file. Unknown stays unknown. When two sources disagree, show a conflict; don't pick one silently.
- **Back up before editing** a file you didn't create this session.
- **No branch switching, stash, reset or clean** in this folder. Use a worktree: `git worktree add ../alex-system-map-<topic> -b <topic>`. Commit as soon as a check passes.
- **Done needs the reviewer.** Finish with a review packet (node or task ID, the acceptance text, evidence paths, your model) for `alex-reviewer`, run by the other model family. Only the Director marks it verified.
- Ask Alex before spending money, contacting anyone, or deleting data. No keys or secrets in files or chat.
- Say whether each thing is written, configured or seen working. No em or en dashes in anything Alex reads.
