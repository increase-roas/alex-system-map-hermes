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
- CEO dashboard (main checkout): `~/Library/LaunchAgents/com.alex.ceo-dashboard.plist` runs `next dev` from `~/Projects/alex-system-map/app` on `127.0.0.1:3201` (3200 stays with the Langflow checkout, `system-map-ir`, until it merges). Open http://127.0.0.1:3201/explorer and click CEO.
- Before saying done: run the acceptance check that matches the change (`tools/*_acceptance.py`), and look at the result in the browser for UI changes.

## Rules
- **Scans are read-only on the Mac.** Scanners write their snapshots only inside this folder (`app/.data/`). Alex's Review & fix request (2026-10-20) also authorizes the explicit, previewed source-repair action described in `docs/LOCAL_FILE_REPAIRS.md`; development checks use temporary sources, never his actual agent files. App settings keep their native owner. One other exception (Alex approved, 2026-10-14): the `/waiting` page's Answer button may record Alex's answer on the task board, only by running `~/.agents/tools/board/board.py answer` from `/api/board/answer` (loopback plus local token, never for gate questions). board.py records the answer text in `~/.agents/board/progress.md`; Alex accepted that (2026-10-15). It must never appear in URLs or this app's logs.
- **The map never invents state.** Every node and line needs a source file. Unknown stays unknown. When two sources disagree, show a conflict; don't pick one silently.
- **Every claim is proven by a source (Alex, 2026-10-12).** Each Pro Map card except "not checked" (unknown) needs at least one source: a web link, or a file that exists (repo-relative or ~/ path). Observations go in `reviews/receipts/<date>-<topic>` first, then the card cites that file. Mark reasoning without a source as "not checked" instead of claiming it. `node app/src/app/explorer/pro-map-audit-check.cjs` fails on any unsourced claim; Alex's own y_ cards are reported as warnings only, never edited.
- **Back up before editing** a file you didn't create this session.
- **No branch switching, stash, reset or clean** in this folder. Use a worktree: `git worktree add ../alex-system-map-<topic> -b <topic>`. Commit as soon as a check passes.
- **Done needs independent review.** A fresh reviewer checks the acceptance criteria, actual source and captured evidence. Prefer another model family within an already approved budget. When that would require new spend, use the available context-separated verifier and label its model family; do not make a paid review a prerequisite for work Alex has authorized. This follows Alex's 2026-10-20 replacement instructions about fixing our own rules when they impose stricter gates than his canonical gates. Director-assigned work keeps its actual mission requirements.
- Ask Alex before spending money, contacting anyone, or deleting data. No keys or secrets in files or chat.
- Say whether each thing is written, configured or seen working. No em or en dashes in anything Alex reads.
