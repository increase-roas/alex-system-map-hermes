# Review packet: Langfuse observability on the system map

For `alex-reviewer`, to be run by the other model family (this work was done by claude-opus-5-5, Anthropic).
Only the Director marks it verified.

- Node: alex-system-map/langfuse-observability
- Branch: `langfuse-observability` (worktree `~/Projects/alex-system-map-langfuse`), base origin/main 0ca5037. Not merged.
- Model: claude-opus-5-5. No spend. Langfuse was only read (two read-tier calls; log IDs in the receipt).
- Evidence folder: `reviews/receipts/2026-10-14-langfuse/` (`observability.md`, `checks.txt`, `browser-1600-langfuse-box.jpg`).

## Acceptance (Alex's brief, 2026-10-14) and result

| # | Acceptance | Result | Evidence |
|---|---|---|---|
| 1 | A Langfuse / Observability node exists on the map | Seen working: box "Langfuse (Increase Roas)" in its own "Observability" band | `tools/build_org_map.py` section 10; `checks.txt` DOM line; screenshot |
| 2 | Lines from Claude Code, JAVAR-LAB and Javar into it; Javar dashed until live | Seen working: all three solid green now, because Javar's first trace landed at 02:03Z (round 1 showed it amber and dashed). The state comes from `LIVE: <env>` lines in the receipt, so a sender without that line is drawn dashed | `observability.md` (Javar's first trace, machine-read states); `checks.txt` |
| 3 | Status badges live / planned | Seen working: LIVE for all three senders, NOT WIRED for Codex; PLANNED shows for any sender without a `LIVE:` line | `checks.txt`; screenshot |
| 4 | Link to the project | Seen working: details panel link to https://us.cloud.langfuse.com/project/cmv733aoq01e7ad0mfeqexnrx | `checks.txt` |
| 5 | Every claim has a source (AGENTS.md rule) | Round 2: unsupported text removed ("every agent run", the upgrades-first edge and its narrative, Hermes versions, host and model). Prompt redaction now cites Claude Code's docs plus the settings grep; plan terms cite langfuse.com/pricing; raw query output is pasted in the receipt. New Org Map check `tools/org_map_sources_acceptance.py obs:` passes with 0 gaps | `observability.md`; `checks.txt` |
| 6 | "Live" means traces were seen landing | Seen working 2026-10-14T01:49Z: env default has `claude_code.*` observations, env javar-lab has `Hermes turn`; env javar has none | `observability.md` live read table |
| 7 | Repo checks run | tsc PASS, build PASS, check scripts PASS, lint PRE-EXISTING (untouched files), app_acceptance FAIL pre-existing ("actor_owner required" from local_service; neither file touched here) | `checks.txt` |
| 8 | This change adds no network call or outside write (corrected wording, round 2) | Written: the new block only reads the receipt, the card and `~/.claude/settings.json`. Round 1 said "the map makes no network call", and that was my wording, not Alex's: the app's existing live scan runs `gh run list` (tools/live_scan.py:268), which predates this branch. Recorded as a finding, not changed here | diff of `tools/build_org_map.py`; `tools/live_scan.py:268` |

## Round 2 (after the Codex FAIL at 2026-10-14T02:05Z)
Review: `reviews/receipts/2026-10-14-langfuse/review-langfuse-observability-20261014T0205Z.md`. Each MISSING line was handled as follows:
- Overstated claims: removed (see row 5).
- Plan terms and redaction: now cite the official pricing and Claude Code docs pages.
- Raw outputs: the fresh raw JSON (log_59xNgfORn8nf) is in the receipt, replacing the first snapshot.
- Org Map check: added `tools/org_map_sources_acceptance.py`. The new parts pass. The whole map has 19 older nodes with no source (hub, MCP plugs, hooks, `you`, `mission:parked`, `check:github`): a finding, not changed here.
- Criterion 8: wording corrected (row 8).
Also added: the "Agent fleet stats" link to the new Langfuse dashboard.

## Things a reviewer should push on
- Hobby plan terms (50k units, 30-day retention) come from Alex's brief, not re-read in the Langfuse UI.
- JAVAR-LAB's model is shown as "not checked" on purpose.
- The "live" badge is driven by the receipt text. It will not go stale by itself if tracing stops; a later step could read a fresh count.
- The browser check used the production build (`next start`), because Turbopack refused the worktree's symlinked node_modules.
