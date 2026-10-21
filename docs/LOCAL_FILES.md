# Local file evidence view

Current extensions: [Review and fix local instructions](LOCAL_FILE_REPAIRS.md) adds explicit reviewed source writes, and [AI proposals](LOCAL_FILE_AI_PROPOSALS.md) makes source-grounded AI recommendations the default before Alex approves an exact diff. Both were requested on 2026-10-20. The original scanner and eight read-only acceptance criteria below remain historical for the initial viewer; each extension has its own acceptance criteria. Alex's replacement instructions also supersede an unconditional paid other-family completion prerequisite; context-separated independent review remains required.

Request: Alex wants the system map to show his actual local agent files so he can inspect duplicates and contradictory instructions.

Scope: read-only inventory of local agent rules, skills, hook definitions/scripts, configs and selected handoffs. Never modify scanned source files. Do not change protected Pro Map owner cards, shared settings, remote machines or customer systems.

Design: Python standard-library scanner plus existing Next.js server patterns. No external AI/service calls or new dependencies. A new Local files tab is the default Explorer view, with a direct /explorer?view=local-files URL. Keep the existing archive/catalog and other views.

Contract: app/src/lib/types/local-files.ts. API GET /api/local-files returns LocalFileIndex, GET /api/local-files?id=<stable id> returns LocalFileContent, and authenticated local POST refreshes the snapshot. The server controls scan roots; clients cannot submit arbitrary paths. Snapshot lives only in app/.data/local-files.json. Content is read on demand, screened, and reports current versus scanned hash.

Coverage: explicitly enumerate included roots and exclusions. Include ~/.agents instructions, skills, cards, guards/unify source; ~/.codex agent/config/hook/skill metadata; ~/.claude settings/rules/skills/hooks; ~/.cursor rules/skills/hooks; ~/AGENTS.md, ~/AGENT-CONTEXT.md, ~/Alex-Director rules and selected ~/Documents/Codex handoffs. Omit credential stores, .env/auth files, transcripts/databases/runtime logs, dependency/build/.git trees. Bound files/depth/bytes. Resolve permitted symlinks and report missing/unreadable/too-large/changed files and truncated coverage. This is an exact bounded inventory, never a claim to cover every file on the Mac.

Frozen acceptance:
1. Files show actual absolute lexical and resolved paths, type, scan time, mtime/bytes and SHA-256 when readable. Symlink aliases remain visible.
2. Same resolved file is shown as shared links, distinct identical bytes as exact copies; generated distribution is identified instead of silently called a defect.
3. Repeated rules and possible conflicting instructions show both file/line excerpts. Language-level contradictions remain candidates, not proven defects or automatic authority decisions.
4. Selecting a file shows safely read current contents with line numbers and scanned/current hash mismatch. No scanned source is edited/deleted/executed.
5. Local files default/direct URL, search/filter, duplicate/candidate selection, related-file navigation and side-by-side evidence work in a real browser at desktop and narrow widths.
6. Included roots, exclusions, limits, scan failures and partial coverage are visible. No empty/error/limited scan is called all-clear.
7. Reuse local-only authorization and token protection for refresh. Never return raw credentials or arbitrary-path file access. No write/cleanup controls.
8. Focused fixture tests prove exact versus linked duplicates, changed/read failure handling, secret screening, allowed-path boundaries, generated references and evidence-bearing candidate detection. Type check and browser proof match the final code.

Implementation owners: backend worker owns tools/local_files.py, tools/test_local_files.py, app/src/lib/server/local-files.ts, app/src/app/api/local-files/route.ts; frontend worker owns app/src/app/explorer/local-files-panel.tsx, app/src/app/explorer/system-explorer.tsx and its type addition in catalog.ts. Parent owns this spec and the shared contract types. Do not revert others' changes or change the contract without coordination.

Validation: backend focused unittest first red then green; one TypeScript check after integration; browser journey on an isolated server using the intended checkout; independent source review. Source-driven privacy/path safeguards are required behavior, not a new on-machine guard system. Formal other-family review route may need an approval per the current Claude bridge card; prepare the concrete packet before any question.
