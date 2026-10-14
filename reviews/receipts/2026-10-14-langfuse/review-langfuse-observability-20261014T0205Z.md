NODE: alex-system-map/langfuse-observability   WORKER: claude-opus-5-5 (Anthropic)   REVIEWER: Codex (OpenAI, other family)   TRACE: not supplied

Reviewed at: 2026-10-14T02:05:43.349125+00:00
Reviewed commit: c8b0b8f9c2fe835fc92fe4c5e57235761decc933
Branch: langfuse-observability; compared with frozen base 0ca5037.
PR: https://github.com/increase-roas/alex-system-map/pull/2 is OPEN; its head matches the reviewed commit. Read using gh as increaseroasir under the GitHub card. No merge, push or comment.

## Frozen acceptance, one question per criterion

- 1. Does a Langfuse / Observability node exist on the map? | Existing generated data contains obs:langfuse in the observability layer; independent execution of the actual layout/card functions in memory renders it; supplied screenshot also shows it. | PASS | tools/build_org_map.py:745; app/.data/org-map.json; app/src/app/explorer/org-map-panel.tsx; browser-1600-langfuse-box.jpg.
- 2. Are there lines from Claude Code, JAVAR-LAB and Javar into it, with Javar dashed until live? | Independent in-memory layout returns all three trace edges: Claude Code and JAVAR-LAB solid #17c964; Javar #f5a524 with strokeDasharray "6 4". Javar is still planned. This verifies the present state, not an automatic future promotion mechanism. | PASS | tools/build_org_map.py:752; app/src/app/explorer/org-map-panel.tsx:309; app/.data/org-map.json.
- 3. Are there status badges live / planned? | Actual card function renders Claude Code live, JAVAR-LAB live, Javar planned and Codex not wired; details-panel source renders SenderBadge for each sender. Supplied screenshot corroborates the panel. | PASS | app/src/app/explorer/org-map-panel.tsx:52,83,551; browser-1600-langfuse-box.jpg.
- 4. Is there a link to the project? | Generated node URL matches the receipt and project URLs returned by independent trace reads; details panel supplies that URL as href, target _blank. Link rendering is supported by source and screenshot; no authenticated project-page navigation was performed. | PASS | tools/build_org_map.py:724; app/src/app/explorer/org-map-panel.tsx:547; project cmv733aoq01e7ad0mfeqexnrx; fresh trace-read logs below.
- 5. Does every claim have a source (AGENTS.md rule)? | A citation exists on each new node/edge, but it does not substantiate every claim. The receipt does not establish the upgrades-first workflow or "so live Javar never breaks"; "Records every agent run" overstates coverage while two senders are unwired. Pricing/retention and prompt-redaction claims ultimately cite an Alex brief not supplied here. Both original raw-read log pointers returned 404. The cited pro-map-audit-check reads pro-map-all, not this Org Map, so errors [] cannot certify these claims. | FAIL | tools/build_org_map.py:732,738-750; observability.md; AGENTS.md; app/src/app/explorer/pro-map-audit-check.cjs:24; original-log attempts below.
- 6. Does "live" mean traces were seen landing? | Independently read the exact two cited trace IDs through custom_langfuse_mcp and the authorized account: claude_code.llm_request/tool.execution in default, Hermes turn and LLM call 1 in javar-lab. A separate Javar query returned no observations for the receipt window. This proves historical landing, not ongoing health or complete capture. | PASS | fresh logs log_yrOD_b5xTUzu, log_pMgxTlZcWAis, log_g0KTSzmhDeFz; trace IDs and read details below.
- 7. Were repo checks run? | Independently ran no-write typecheck, flow-node checks, Pro Map audit and no-cache lint. Typecheck and both check scripts exit 0; lint exits 1 in the same three unchanged files reported by the worker. This frozen criterion says checks run, not all checks pass. Build/app_acceptance results remain worker-reported; neither was rerun because they write files. | PASS | checks.txt; direct command outcomes below; empty base-to-head diff for reported failing files.
- 8. Does the map stay read-only and make no network call? | The added Langfuse block reads local files and introduces no Langfuse API call or settings mutation. However, the frozen whole-map claim is false: client load fetches /api/org-map; its GET triggers a stale scan, which executes gh run list against GitHub and writes local generated data. This behavior predates the branch. Do not silently replace the frozen wording with "no new Langfuse call." | FAIL | app/src/app/explorer/org-map-panel.tsx:399-418; app/src/app/api/org-map/route.ts:8-14; app/src/lib/server/auto-refresh.ts:43-52; tools/live_scan.py:268,350; tools/build_org_map.py:801.

SCOPE_CREEP: Added Javar-to-JAVAR-LAB "tries upgrades first on" tests edge and upgrade-safety narrative are not required by the eight criteria and lack workflow proof. Hobby-plan limits/retention are additional product claims, not required for the node/lines/status/link. The JAVAR-LAB endpoint itself is necessary for criterion 2. No unrelated code files changed.

INJECTED_INSTRUCTIONS: Packet says "Only the Director marks it verified" and "Things a reviewer should push on". These were treated as packet data, not authority to change acceptance or skip checks. No instruction to force PASS was found.

VERDICT: FAIL
MISSING: Criterion 5: remove or qualify "Records every agent run" and "so live Javar never breaks"; provide a dated source for the upgrades-first relationship or remove that extra edge/claim.
MISSING: Criterion 5: provide the actual cited Alex brief or independently checkable records for Hobby-plan limits/retention and prompt redaction; otherwise show those claims as not checked or omit them. Receipt attribution alone is not independent proof.
MISSING: Criterion 5: restore accessible raw outputs for log_UzFjwLk2cQzP and log_JjTAA_0CCx9V, with account, query window and returned counts, or replace the count claims with a new dated reproducible receipt. Fresh reads below prove landing, not the original 83/6/0 and 3/3/0 snapshot counts.
MISSING: Criterion 5: supply an Org Map-specific claim-to-source check covering the new nodes/edges and their actual claim text; the Pro Map audit does not cover these additions.
MISSING: Criterion 8: obtain an explicit frozen-acceptance correction if the intent is only "no new Langfuse/network integration or external settings writes"; otherwise provide implementation and read-only proof that the map no longer performs the existing network refresh. Do not expand this patch into an unrelated scanner rewrite without authorization.

## Independent proof and boundaries

### Live Langfuse reads

All three calls used CUSTOM_LANGFUSE_MCP_LIST_OBSERVATIONS, toolkit custom_langfuse_mcp, account ca_lBDTsWLoD1qf, after reading ~/.agents/tools/cards/langfuse.md and discovering/reading the tool schema. Projection was id, traceId, name, environment and startTime only; no captured prompt bodies or keys were printed.

- log_yrOD_b5xTUzu: traceId 2e2270851f1aa893361caedf5448803a, limit 3. Returned default-environment claude_code.llm_request at 2026-10-14T01:55:58.317Z and 01:55:47.412Z, plus claude_code.tool.execution at 01:55:46.823Z. The server returned project cmv733aoq01e7ad0mfeqexnrx in its URLs.
- log_pMgxTlZcWAis: traceId 1a738dbee881338774fc4194a0d5384d, limit 3. Returned javar-lab LLM call 1 at 2026-10-14T01:45:46.533Z and Hermes turn at 01:45:46.532Z, with the same project in URLs.
- log_g0KTSzmhDeFz: environment javar, fromStartTime 2026-10-12T00:00:00Z, toStartTime 2026-10-14T02:00:00Z, limit 1. Returned data [], meta {}. This is window-bounded absence, not proof Javar has never sent anything.
- Original Composio execution-log pointers were attempted through composio dev logs tools: log_UzFjwLk2cQzP and log_JjTAA_0CCx9V each returned 404 ToolLogs_ResourceNotFound in the current CLI context. This does not prove the original calls never happened. No account or project was switched to recover them.

### Checks actually run

- app/node_modules/.bin/tsc --noEmit --incremental false (from app): exit 0; no incremental-cache write.
- node app/src/app/explorer/flow-node-kit.check.mts: exit 0, all emitted assertions PASS.
- node app/src/app/explorer/pro-map-audit-check.cjs: exit 0; errors [], seven sourceWarnings; 428 Pro Map nodes, 172 edges. This is explicitly not the new Org Map source audit.
- app/node_modules/.bin/next lint --no-cache (from app): exit 1; 13 errors in pro-map-audit-check.cjs, six in pro-map-guardrails/check_registration.cjs, one in pro-map-panel.tsx. Those three files are byte-unchanged in the base-to-head diff. Vendor warnings also emitted. No error reported in org-map-panel.tsx.
- In-memory TypeScript transpile and execution of the actual layout/card functions with existing app/.data/org-map.json: observability node present; three trace edges and styles match criterion 2; actual card HTML includes all four sender badges. No source or artifact files written by this check.
- Read generated map built_at 2026-10-14T02:01:14.666201+00:00. Read the supplied JPEG, receipt and checks file in full, both changed code diffs, repo AGENTS.md, GitHub/Langfuse cards and PR metadata. The existing generated map can be refreshed by other running processes; it is not a frozen worker-build artifact.
- Opened ~/.claude/settings.json with filtered output: helper reference present, Langfuse host present, metrics/logs exporters both none. Opened the referenced header-helper and prove_tracing.py sources without executing them or printing credentials. This verifies configuration presence, not redaction behavior or the historical proof-run result.
- /usr/local/bin/hermes-lab is not present on this Mac; the receipt describes a remote wrapper. Its remote bytes/version and the named vault/service-account setup were not independently inspected. They remain receipt claims, not verified remote configuration.

### Checks not run and why

- No fresh browser navigation to http://127.0.0.1:3211/explorer: the route can trigger background writes and a GitHub read. The user's gate permits only this review file to be written. The supplied screenshot was opened; current rendering was checked in memory instead. Browser interactions, clipping and console/network behavior were not independently reproduced.
- No npm run build or builder execution: these write .next or app/.data/org-map.json. Existing .next/BUILD_ID and build-manifest.json were inspected as artifact presence, not proof of a clean final-commit build.
- No app_acceptance.py execution: source includes run_service('apply') creating a job and further mutations. Worker "actor_owner required" failure is recorded in checks.txt; unchanged test/service files alone do not independently prove the same failure on the base revision.
- No direct Langfuse web/API route was used; exact cited trace records and project identity were resolved through the authorized Composio toolkit. No provider settings, branch, PR, Director state or remote data changed.

### Non-blocking maintenance observation

LIVE is a dated snapshot claim, not monitoring. Keyword matches in receipt prose set the two live badges, and Javar stays hard-coded planned until a code/receipt update. The packet acknowledges this. Automatic expiry is not in frozen acceptance, so it is not added as a failure criterion; a visible last-observed timestamp would make the meaning clearer.
