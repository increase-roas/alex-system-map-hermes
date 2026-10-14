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
| 2 | Lines from Claude Code, JAVAR-LAB and Javar into it; Javar dashed until live | Seen working: two solid green lines (live); Javar line amber and dashed (planned) | `checks.txt` edge lines |
| 3 | Status badges live / planned | Seen working: LIVE, LIVE, PLANNED, plus NOT WIRED for Codex, on the box and in the details panel | `checks.txt`; screenshot |
| 4 | Link to the project | Seen working: details panel link to https://us.cloud.langfuse.com/project/cmv733aoq01e7ad0mfeqexnrx | `checks.txt` |
| 5 | Every claim has a source (AGENTS.md rule) | Written: each new node and line cites the receipt or the Langfuse card; every line carries evidence; audit check errors [] | `observability.md`; `checks.txt` |
| 6 | "Live" means traces were seen landing | Seen working 2026-10-14T01:49Z: env default has `claude_code.*` observations, env javar-lab has `Hermes turn`; env javar has none | `observability.md` live read table |
| 7 | Repo checks run | tsc PASS, build PASS, check scripts PASS, lint PRE-EXISTING (untouched files), app_acceptance FAIL pre-existing ("actor_owner required" from local_service; neither file touched here) | `checks.txt` |
| 8 | The map stays read-only and makes no network call | Written: the builder only reads the receipt, the card and `~/.claude/settings.json` (to confirm the OTel helper is configured) | diff of `tools/build_org_map.py` |

## Things a reviewer should push on
- Hobby plan terms (50k units, 30-day retention) come from Alex's brief, not re-read in the Langfuse UI.
- JAVAR-LAB's model is shown as "not checked" on purpose.
- The "live" badge is driven by the receipt text. It will not go stale by itself if tracing stops; a later step could read a fresh count.
- The browser check used the production build (`next start`), because Turbopack refused the worktree's symlinked node_modules.
