# Full Spectrum Audit: System Map app (agent-system-foundation-v1/app)

**Date**: 2026-10-11
**Mode**: Repo Health (folder is not a git repo)
**Lenses Run**: 8/10. Skipped: Backend (no Rust/Tauri), Accessibility (no UI change made).

## Master Verdict: APPROVE WITH CHANGES (changes applied)

The app is local-only, but its API trusted any request that reached port 3200. A web page in your browser could read the edit key from /api/health (DNS rebinding) or fire a Rescan. Blocked now and proven with live requests.

## Critical issues (fixed)

| # | Issue | File | Fix | Proof |
|---|---|---|---|---|
| 1 | /api/health hands out the edit token with no host check | api/health/route.ts | new src/middleware.ts: every /api route needs a 127.0.0.1/localhost Host | Host evil.com -> 403 |
| 2 | /api/live-setup POST (Rescan, runs a script) had no guard | api/live-setup/route.ts | middleware rejects cross-site Origin | Origin evil.com -> 403 |
| 3 | Origin check used "contains 127.0.0.1", so 127.0.0.1.evil.com passed | lib/server/local-auth.ts | exact hostname match | lookalike -> 403 |
| 4 | Auth failures threw a Response, which Next turns into a 500 | presentation, catalog/edit | mutationAuthError() returns real 401/403 | no-token PUT 500 -> 401 |

Normal use still works: /explorer, /api/health, /api/catalog, /api/live-setup all 200. TypeScript check passes.

## Recommendations (not done)

| # | Recommendation | Why |
|---|---|---|
| 1 | Put the app folder in git | No history; undo is only the backup |
| 2 | Duplicate zoom-slider and node-status-indicator in lib/pro-template | Two copies drift |
| 3 | Remove unused @ai-sdk/openai and ai deps (AI routes are disabled stubs) | Smaller install |
| 4 | /api/health hashes the whole SQLite file every call | Slows as DB grows |
| 5 | next.config ignores lint during build | Lint errors never surface |

Backup of the pre-fix app: ~/Backups/tighten-20261011/map-app


---

# Round 2 (2026-10-11): live view clarity, auto-refresh, hooks and GitHub check

**Mode**: Repo Health on the changed files (live_scan.py, auto-refresh.ts, live-setup route, traces route, live-setup-panel.tsx, tracing-panel.tsx, use-poll.ts)
**Verdict**: APPROVE (issues found while looking at the page were fixed and re-checked)

| # | Issue found | Lens | Fix | Proof |
|---|---|---|---|---|
| 1 | First load waited for a full rescan (blank 5s+) | Perf, UX | Serve last scan instantly, refresh in background, client re-polls once after 6s | API 0.22s |
| 2 | Chip click lit a card but did not zoom; card unreadable | UX | focusOn flies camera to the cards (reduced-motion aware) | Seen in browser |
| 3 | Detail box rendered below the map, off screen | UX, Design | Floating panel on the canvas with a close button | Seen in browser |
| 4 | "Clear highlight" popped in and shifted the chips (misclicks) | Design, a11y | Button always holds its space | Seen in browser |
| 5 | ReactFlow remounted on every highlight (key included focus size) | Frontend (vercel-react) | Removed remount key; nodes update in place | Code |
| 6 | Map squeezed beside the problem list at normal widths | Design | Side list only at 2xl, otherwise below the map | Seen in browser |
| 7 | Traces only reloaded by hand | Prod | Re-import when receipts.jsonl size or time changes, single in-flight job | touch test: 2.9s import, then 0.45s |

Not done (note): the Director trace export is a one-time file. The map now reloads it automatically, but nothing appends new Director records to it yet, so "newest trace" stays 5 days old until the Director exports again.
