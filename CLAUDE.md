Read and follow @AGENTS.md (the shared instructions for every agent in this project).

## Claude Code harness
Index of `.claude/` (gap-fill; the rules stay in AGENTS.md). Every agent runs on Sonnet (keep cost low). Guard overrides are env vars (`ALLOW_PUSH` and the like) that only Alex sets before launch.
- Agent `planner`: file-precise plan before coding (read-only)
- Agent `app-engineer`: implements `app/` (TypeScript, React, Next)
- Agent `tools-engineer`: implements `tools/` (Python, SQLite service)
- Agent `correctness-reviewer`: TS and React, Python, untrusted input, canvas-to-API types, HTTP contract
- Agent `security-reviewer`: auth, secrets, loopback and tailnet trust, per-user access, redaction
- Agent `data-layer-guard`: SQLite and JSON persistence, migrations, writes outside `app/.data`
- Agent `silent-failure-hunter`: swallowed errors and upstream schema drift
- Agent `performance-reviewer`: bundle size, large-graph render cost, big JSON loads
- Agent `refactor-cleaner`: evidence-based dead-code sweep (reports, never deletes)
- Agent `test-writer`: `*.check.mts` and `tools/*_acceptance.py` tests
- Agent `live-repro`: drives the running app with Playwright to reproduce bugs
- Command `/verify`: tsc, lint, build, check scripts, acceptance, then READY or NOT-READY
- Command `/full-review`: parallel reviewers over the diff; any CRITICAL means NOT READY
- Hook `critical-rules` (SessionStart): prints the AGENTS.md rules that must not be forgotten
- Hook `guard-bash` (Bash): blocks git push, secret-bearing commits, stash, reset --hard, clean, switch, checkout, restore
- Hook `guard-edit` (Edit, Write): blocks `~/.agents`, `~/Alex-Director`, `~/.claude`, `.env*` and new root FINDINGS.md or REPORT.md
- Hook `warn-console-log` (Edit, Write): warns on `console.log(` in `app/src/**/*.ts(x)`
- Hook `build-gate` (Stop): `tsc --noEmit` on `app/`; blocks on type errors
- Rule `api-routes` (`app/src/app/api/**`): authorize mutations, JSON errors, no credentials out
- Rule `tools-python` (`tools/**`): read-only on Alex's files, write inside `app/.data`, no unlisted hosts
- Global skills, not duplicated here: `alex-reviewer` (finish packet), `alex-director`, `alex-workflow-conductor`, `ce-code-review`, `web-design-reviewer`, `web-design-engineer`, `verify-before-done`, `systematic-debugging`, and the built-in `/simplify`. They also cover UX review and project management.
