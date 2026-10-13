# Alex System Map: reviewer, tracing, freshness and plan view

Plan for review by Astra. Written 2026-10-11 (EDT) by Claude after reading the source. **Inspection and planning only. Nothing in "Proposed" has been built.**

Map project root (called `MAP` below): `~/Documents/Codex/2026-10-09/l/outputs/agent-system-foundation-v1`
Director home: `~/Alex-Director`. Shared agent home: `~/.agents`.

Labels used throughout:
- **VERIFIED**: read in source or data on 2026-10-11/12, with a file reference.
- **PROPOSED**: a change; not built.
- **UNKNOWN**: not checked or not checkable from here.

---

## 1. Verified current state

### 1.1 The map app and how it is built
| Fact | Source |
|---|---|
| Next.js app with React Flow Pro; tabs include Map, Full Catalog, Subsystem, Files, Problems, Workflows, **Tracing**, Reliability, Maintained, Live | `MAP/app/src/app/explorer/system-explorer.tsx`, panel files in the same folder |
| The org map is one JSON file, `MAP/app/.data/org-map.json`, written only by `MAP/tools/build_org_map.py` (read-only on the Mac) | header of `build_org_map.py` lines 1-10 |
| `GET /api/org-map` serves the saved file at once, then rebuilds in the background if it is older than 2 minutes (`refreshLiveScanIfStale(2 * 60_000)`). With no file, it builds first. | `MAP/app/src/app/api/org-map/route.ts` |
| A rebuild runs `tools/live_scan.py` and then `tools/build_org_map.py`. Only one rebuild runs at a time (`once()` guard). | `MAP/app/src/lib/server/auto-refresh.ts` (`runLiveScan`) |
| The "Rescan now" button forces a rebuild | `org-map-panel.tsx` lines ~380, 434 |
| Last build seen: `built_at 2026-10-12T02:02:44Z`, 91 nodes, 190 edges, 190 of 190 edges carry evidence | `MAP/app/.data/org-map.json` (read 2026-10-12) |
| Builder inputs: live scan, catalog (`local_service.py catalog-export`), `~/.agents/skills/*/SKILL.md`, `~/.agents/tools/cards/*.md`, `~/.agents/instructions/*`, `~/Alex-Director/DIRECTOR_STATE.md`, `~/Alex-Director/mission-graphs/*`, `~/Alex-Director/AGENTS.md`, the SDK build plan, rule-audit output, `~/.codex/config.toml`, `~/.cursor/*`, `~/.claude/*` | `build_org_map.py` lines 21-35, 118-172, 261-354, 452 |
| Layers drawn: You, AI apps, Director, Conductor, Engine room (SDK, 8 build-plan parts), Customers/projects with missions, Skills, Connections. Rules and guards sit in a side rail. | `build_org_map.py` output block, lines ~680-690 |
| The Director/Conductor link is evidence-backed: Director "judges", Conductor "does the work", citing `~/Alex-Director/AGENTS.md` line 7 | `build_org_map.py` lines ~637-647 |
| Every node has a purpose line and a 3-part explanation (what / should I care / what to do). Edges without evidence are counted as unproven. | `build_org_map.py` `explain()`, `EVIDENCE` block |
| "Needs me" chips come from Director state, rule audit, login problems and SDK checks | `build_org_map.py` `needs_me` (lines 112, 351, 477-494, 616) |

### 1.2 Tracing that already exists
| Fact | Source |
|---|---|
| Trace store: SQLite at `MAP/app/.data/local.sqlite`, commands `trace-import`, `trace-list`, `trace-get` | `MAP/tools/local_service.py` lines 422-425, 680-695 |
| Trace document format: `receipt_id, trace_id, label, started_at, ended_at, status, metadata, spans[]`. Each span has `span_id, parent_span_id, name, agent_identity, tool_action, started_at, ended_at, duration_ms, status, component_ids, source_ids, evidence_ids, metadata` | `MAP/examples/agent-trace-fixture.json` |
| The Tracing tab lists traces (`/api/traces`), draws the span tree by parent link, and shows each span's agent, tool, status, duration, sources and evidence IDs | `tracing-panel.tsx` lines 20-29, 48-116, 130-141, 202-235 |
| The only real feed is the Director controller-write export. `/api/traces` re-imports it when its size or modified time changes. The Director's writer script is run at most once every 55 s. | `auto-refresh.ts` `refreshDirectorTracesIfChanged`, `runDirectorTraceWriter` |
| That export is deliberately thin: mission, action, status and timestamps only. No IDs, evidence or reasons (allowlist). Latest export: 291 records, exported 2026-10-11T04:10Z | `~/Alex-Director/scripts/export-trace-receipts.py` header; `~/Alex-Director/inputs/real-traces/director-controller/manifest.json` |
| The loader groups the export into one trace per mission; every span's agent is "Director controller", with no parent links | `MAP/tools/load_director_traces.py` lines 1-60 |
| `org-map.json` `last_trace` = `2026-10-06T07:24:59Z`, older than the export above | `org-map.json` (read 2026-10-12) |

### 1.3 Trace TR-20261012-A1 (the bridge and reviewer test)
| Fact | Source |
|---|---|
| 10 lines in `~/Alex-Director/traces/TR-20261012-A1.jsonl`, fields `trace, hop, who, model, route, what, result, review_path, capability_ids, cost_usd, pass, ts` | the file itself |
| Hops: 0 open, 1 Claude to Codex (codex-bridge), 2 Codex to Claude (script), 3 SDK claude_bridge **fail** (`operation_rejected`), 3 retry **pass** after SDK fix `1d79e3a` ($0.33), 4 Director froze node T1, 5 Codex worker (GPT-6), 6 Conductor packet, 7 Claude reviewer via SDK, **VERDICT PASS** ($0.44), 8 Director VERIFIED | same file |
| The trace has no `parent` field. The retry is a second line with the same hop number, not a linked attempt. | same file |
| A standalone page exists: `~/Alex-Director/traces/TR-20261012-A1.html`, made by `~/Alex-Director/traces/view_trace.py` (outcome, hop count, failures, metered cost, per-hop table) | both files |
| **The map does not read `~/Alex-Director/traces/` at all.** No loader, route or panel points there. | grep of `auto-refresh.ts`, `load_director_traces.py`, `build_org_map.py` |

### 1.4 Reviewer: configured vs observed
| | Configured (rules on disk) | Observed in TR-20261012-A1 |
|---|---|---|
| Where it enters | Conductor ends every COMPLETE with a review packet (`~/.agents/skills/alex-workflow-conductor/SKILL.md`, section "Review packet"); Director rule 3 sends it to `alex-reviewer` (`~/.agents/skills/alex-director/SKILL.md` lines ~29-35) | Conductor (Codex) wrote `TR-20261012-A1-T1-packet.md`; it was sent to Claude through the SDK claude_bridge |
| Who reviews | Other model family from the worker (`~/.agents/skills/alex-reviewer/SKILL.md` rule 1) | Worker GPT-6, reviewer claude-opus-5-5 |
| What it checks | Each frozen acceptance criterion: PASS / FAIL / UNVERIFIED / UNCHECKABLE, read-only, opens every pointer (rules 2-3) | 2 criteria, both PASS; it ran `ls`, `od -c`, `wc -l` itself |
| Where the result goes | `review-<node>-<UTC>.md` next to the mission's receipts; the Director writes `LAST_REVIEW: <path> <VERDICT>` in the node block (rule 5; Director rule 3) | `~/Alex-Director/traces/review-T1-20261012T0203Z.md`; **no `LAST_REVIEW` line was written** (test node, ledger left untouched on purpose) |
| After PASS | Director may mark VERIFIED | Director logged VERIFIED in the trace (hop 8) only |
| After FAIL | Reviewer lists `MISSING:` lines; per Director rule 3 the work goes back to the controller with the exact missing proof | **Not exercised.** No FAIL review has happened. |
| Gap | `LAST_REVIEW` is not defined in the ledger format (`~/.agents/skills/alex-director/references/ledger.md` has no such field); `DIRECTOR_STATE.md` has 0 `LAST_REVIEW` lines | n/a |

How the map shows the reviewer today: as `local:alex-reviewer`, layer **connectors**, label "Alex Reviewer (local route)". It is drawn as an app connection only because its passport card sits in `~/.agents/tools/cards/`. Its only edges are two "mentions" links from the `writing-plans` and `fan-out` skills. **It is not drawn as a workflow step** (source: `org-map.json`, node and edges read 2026-10-12).

### 1.5 Workflow engine that already exists (reusable for the plan view)
`MAP/docs/WORKFLOW_CONTRACT.md` and `MAP/workflows/{investigate,build,repair}.json`:
- SQLite records for jobs, tasks (owner, dependencies, acceptance, status, attempts, evidence, blockers, next action), checkpoints, corrections and events.
- `verify` requires a **verifier different from the owner**, nonempty evidence, and a check for every acceptance item.
- Corrections force downstream rechecks.

The templates have `dispatch_enabled: false`.

### 1.6 Registry and routing
- **Passports:** `~/.agents/registry/connectors/*.json` are rebuilt by `~/.agents/tools/registry/build_registry.py` from `~/.agents/tools/cards/*.md`. Proof state reads "seen working" only when the card text holds `Tested YYYY-MM-DD` (line 53). `codex-bridge`, `claude-bridge` and `alex-reviewer` are "complete" (commit `7aa995c`).
- **Conductor routing:** `~/.agents/skills/alex-workflow-conductor/references/routing.md`. Includes `ce-code-review`, then the review packet to `alex-reviewer` (restored 2026-10-11).
- **Freshness indicators already on screen** (screenshot, matched in code): "updated N min ago (auto every 2 min)" and a catalog sync bar with fingerprint (`sync-status-bar.tsx`).

### 1.7 Unknowns
- **U1:** Who or what "Astra" is, and which folder Astra reads. I saved copies in both likely places (section 9).
- **U2:** Whether the map server is running right now, versus `org-map.json` being rebuilt by a request. `built_at` changed at 02:02Z, so something triggered it. Not checked further.
- **U3:** Whether `export-trace-receipts.py` still runs. The export file is from 04:10Z, while the map's `last_trace` is 2026-10-06. Not diagnosed.
- **U4:** Behavior of `live_scan.py` exclusions in full. I read only its role, not its file list.
- **U5:** The Tailscale-hosted copy was not opened from here.
- **U6:** How the Codex hops' cost should be shown. They run on Alex's Codex plan, and no per-call cost is recorded.

---

## 2. Reviewer in the workflow (proposed design)

**PROPOSED:** draw the real chain as the spine of the map:

```
Alex -> Director (freeze outcome + ACCEPTANCE) -> Conductor (route, dispatch) -> Worker (does work)
     -> Conductor (review packet) -> Reviewer (other model family, read-only)
        -> PASS -> Director writes LAST_REVIEW PASS -> VERIFIED
        -> FAIL -> MISSING lines -> back to Conductor -> new attempt (retry) -> Reviewer again
```

Changes:
1. Add `reviewer` as a role node in the **conductor/director band**, not in connectors. Its edges:
   - Conductor -> Reviewer "sends packet". Evidence: Conductor SKILL "Review packet" section.
   - Reviewer -> Director "verdict". Evidence: alex-reviewer rule 5.
   - Director -> mission "marks VERIFIED only on PASS". Evidence: Director rule 3.
2. Keep the passport card, but stop the card from creating a connector node for `kind: skill` passports. Use the registry `kind` field to decide.
3. On each mission node, show a review badge from the ledger:
   - `LAST_REVIEW` PASS is green, FAIL is red;
   - no review on a node marked VERIFIED shows as amber "verified without review";
   - a node with no review yet shows grey.
4. Define `LAST_REVIEW: <path> <PASS|FAIL> <UTC>` in `references/ledger.md`, so builder parsing has a contract.

Configured vs observed stays visible:
- **Configured:** the badge legend cites the rule lines.
- **Observed:** comes only from review files and trace lines. The map never infers a PASS from a rule.

---

## 3. Tracing (proposed design)

**Reuse the existing trace store and Tracing tab.** Don't build a second viewer. The HTML page from `view_trace.py` stays as a portable export.

### 3.1 One trace line format for agents (extends TR-20261012-A1)
Each hop appends one JSON line to `~/Alex-Director/traces/<TRACE_ID>.jsonl`:

| Field | Required | Notes |
|---|---|---|
| `trace` | yes | `TR-YYYYMMDD-XX` |
| `hop` | yes | integer, order of events |
| `span` | proposed | unique per line, e.g. `h3a2` |
| `parent` | proposed | span of the step that caused this one (fixes the flat-retry problem) |
| `attempt` | proposed | 1, 2, ... for retries of the same step |
| `who`, `model` | yes, model if known | role + agent |
| `route` | if a bridge or tool | e.g. `SDK master_ops claude_bridge` |
| `capability_ids` | if SDK | as logged in hop 3 |
| `what`, `result` | yes | short, no secrets |
| `evidence` | proposed | list of file paths or record IDs (`review_path` becomes one of these) |
| `pass` | yes for checks | true, false or absent |
| `cost_usd` | if metered | absent means "not metered", never 0 |
| `ts` | yes | UTC ISO |

### 3.2 Map ingestion
New loader `MAP/tools/load_agent_traces.py`, modeled on `load_director_traces.py`. It converts each `traces/*.jsonl` into the existing trace document:
- `span_id` comes from `span`, or else from `trace + hop + line number`;
- `parent_span_id` comes from `parent`, or else from the previous hop (marked `metadata.inferred_parent: true`);
- `agent_identity` = `who (model)`; `tool_action` = `route`;
- `evidence_ids` from `evidence` + `review_path`;
- `metadata` holds `cost_usd`, `attempt`, `capability_ids` and `export_line`.

It runs through `trace-import`. The trigger copies `refreshDirectorTracesIfChanged`: a fingerprint of size and modified time for every file in the folder, stored in `app/.data/agent-traces.stamp`.

### 3.3 Tracing tab additions (small)
- Per-trace header: outcome (VERIFIED, OPEN or FAILED), hop count, failures, retries, metered cost total. These are the same numbers `view_trace.py` already computes.
- Retries drawn as siblings under the same parent, labeled "attempt 2".
- Review spans get a PASS or FAIL badge and a link to the review file through the existing source/evidence drawer.
- Filter by mission and by role (Director, Conductor, worker, reviewer).

**Why not adopt an outside tracing standard now:** the existing store already has the span model OpenTelemetry-style viewers use (span, parent, attributes, status). Adding a collector would mean new software and a new service for one Mac. Revisit only if traces must leave the Mac. Evidence: `MAP/examples/agent-trace-fixture.json` and `tracing-panel.tsx` already render parent/child spans.

---

## 4. Staying current (proposed rules on top of what exists)

### 4.1 Who owns each fact
| Fact on the map | Owner (source of truth) | Map behavior |
|---|---|---|
| Missions, status, NEXT_PLAY, WAITING, LAST_REVIEW | `~/Alex-Director/DIRECTOR_STATE.md` (Director only writes) | read only |
| Director, Conductor and reviewer rules | `~/.agents/skills/alex-*/SKILL.md` + references | read only, show version |
| Connector routes and logins | `~/.agents/tools/cards/*.md` | read only |
| Proof that a route works | `~/.agents/registry/connectors/*.json` (`from_card.proof`) | read only |
| What happened on a job | trace files + review files + SDK receipts | read only |
| Which apps and MCP servers exist | live scan of the Mac | read only |
| Plan tasks and status (section 5) | `MAP/app/.data/local.sqlite` workflow store | the only thing the map writes |

**Disagreement rule (proposed):** the map never picks a winner silently. When two owners disagree, the node shows a "conflict" status. The existing `conflict` status already counts as stuck in the rail. Both sources and values are listed in the node drawer.

Examples the builder should detect:
- the ledger says VERIFIED but there is no PASS review;
- a passport says "seen working" but the newest trace for that route failed;
- a card names a route that the live scan doesn't find.

Observed beats configured for "what happened". Configured beats observed for "what should happen". Both are always shown.

### 4.2 What gets scanned
- **Already scanned (verified):** the builder input list in 1.1.
- **Add (proposed):**
  - `~/Alex-Director/traces/*.jsonl` and `review-*.md`;
  - `~/.agents/registry/connectors/*.json`;
  - `~/.agents/skills/alex-reviewer/SKILL.md`;
  - `~/.agents/skills/alex-workflow-conductor/references/routing.md`.
- **Excluded (proposed, explicit list in the builder):**
  - `.git/`, `node_modules/`, `__pycache__/`, `backups/`, `_archive*`, `.runtime/` (raw claims; the export script is the sanctioned reader);
  - `*.bak*`, `.DS_Store`;
  - anything under `~/.ssh` or credential folders;
  - the content of any file over 2 MB. Its size and modified time are kept.

### 4.3 When it refreshes
- **Keep (verified):** a 2-minute stale-while-revalidate on `/api/org-map`; "Rescan now"; trace re-import on fingerprint change.
- **Add (proposed):** a fingerprint pass over the new trace and review folders, on the same `/api/traces` request path, so a new hop shows within one poll.

### 4.4 How freshness is shown
- **Keep:** "updated N min ago" and the sync bar.
- **Add (proposed):**
  - Per-source freshness: each node's drawer shows its source file, that file's modified time, and "read OK / missing / unreadable" at the last build.
  - A stale flag: when a source's modified time is newer than `built_at`, the header says "N sources changed since last build".

### 4.5 When a file changes, disappears or can't be read (proposed)
| Event | Behavior |
|---|---|
| Changed | Picked up on the next build. The node's "changed" timestamp updates. |
| Disappeared | The node stays, greyed, status `gone`, with "last seen <time>". It is never silently removed in the same build. It is dropped after 7 days, or when Alex archives it. This matches the existing "drawer gone" handling for catalog items. |
| Unreadable (permission, parse error) | The node is marked `unknown`, the reason shows in the drawer, and the item goes to the Problems tab. The last good values are kept, labeled "from <time>". The build never fails because of one file. |
| Trace line malformed | That line is skipped and counted in the trace header ("1 line unreadable"), and the rest import. |

---

## 5. The plan inside the map (proposed)

**Reuse the workflow engine** (section 1.5). Don't invent a plan format.
- This plan becomes one **job** with **tasks** in `local.sqlite` through the existing `build.json` template.
- Each task has an owner role, dependencies, acceptance, status, attempts, evidence and next action, as the contract already defines.
- `verify` already requires a verifier different from the owner, which is the reviewer rule.

How it fits the current map:
- A new band under the Conductor, **"Work in flight"**. One card per phase, a progress count, and a red dot when a task is blocked.
- Clicking a phase opens the existing Workflows panel filtered to that job. No new screen.
- Each task links to its trace (`trace_id` in task metadata) and its review file.
- The "Needs me" chips gain any task whose owner is Alex.

---

## 6. Implementation checklist

Phases run in order. Each phase is one Conductor node: the worker builds, the reviewer checks (other model family), and the Director marks VERIFIED.

### Phase 0: contracts (no app code)
- [ ] **0.1** Add the `LAST_REVIEW: <path> <PASS|FAIL> <UTC>` field to `~/.agents/skills/alex-director/references/ledger.md`.
  - **Check:** `grep LAST_REVIEW ledger.md` finds a definition.
- [ ] **0.2** Write the trace line spec (3.1) as `~/Alex-Director/traces/README.md`. Add `span`, `parent`, `attempt` and `evidence` support to `view_trace.py`, keeping the old fields valid.
  - **Check:** `view_trace.py TR-20261012-A1` still renders 10 hops, $0.77, VERIFIED.
- [ ] **0.3** Registry: add `kind: skill` handling so `alex-reviewer` is typed as a role in `registry/connectors/alex-reviewer.json` (it already says `"kind": "skill"`). No change to the builder yet.
  - **Check:** `build_registry.py --check` exits 0.

### Phase 1: reviewer on the map (depends on 0.1, 0.3)
- [ ] **1.1** `MAP/tools/build_org_map.py`: create a `reviewer` role node in the director/conductor band. Skip connector nodes for cards whose registry `kind` is `skill`. Add the three evidence-backed edges from section 2.
  - **Check:** `org-map.json` has node `reviewer` in layer `conductor`, no `local:alex-reviewer`, and all edges proven.
- [ ] **1.2** Parse `LAST_REVIEW` per mission or node into `meta.review`. Add the badge statuses, and a conflict when VERIFIED has no PASS.
  - **Check:** a fixture ledger with one PASS, one FAIL and one VERIFIED-without-review gives three different badges.
- [ ] **1.3** `org-map-panel.tsx` / `nodes.tsx`: render the badge and the legend with rule citations.
  - **Check:** visually inspected in the app, with screenshots in `MAP/reviews/`.

### Phase 2: agent traces in the Tracing tab (depends on 0.2)
- [ ] **2.1** New `MAP/tools/load_agent_traces.py` (section 3.2).
  - **Check:** importing TR-20261012-A1 gives 10 spans, the retry as attempt 2 under the same parent, and cost metadata on 2 spans.
- [ ] **2.2** `MAP/app/src/lib/server/auto-refresh.ts`: add `refreshAgentTracesIfChanged()`, a copy of the Director pattern with its own stamp, and call it from `app/api/traces/route.ts`.
  - **Check:** appending one line to a trace file shows up on the next `/api/traces` call; an unchanged folder does no import.
- [ ] **2.3** `tracing-panel.tsx`: header totals, retry grouping, review badge, mission and role filters.
  - **Check:** TR-20261012-A1 shows VERIFIED, 1 failure, 1 retry, $0.77.
- [ ] **2.4** A malformed-line test: skipped and counted, not fatal.

### Phase 3: freshness and disagreements (depends on 1, 2)
- [ ] **3.1** Builder: record for each source path its modified time, status (`ok`, `missing` or `unreadable`) and the error, under `meta.source_status`.
- [ ] **3.2** Explicit exclude list (4.2) as one constant, used by `live_scan.py` and the builder.
- [ ] **3.3** `gone` handling with "last seen" and a 7-day retention, kept in `app/.data/seen.json`.
- [ ] **3.4** The conflict checks listed in 4.1, each routed to the Problems tab.
- [ ] **3.5** Header: "N sources changed since last build".
- **Checks:** rename one card, and the node goes grey "gone". Make one file unreadable (`chmod 000` on a copy in a test home), and the node is `unknown` with a reason and the build still succeeds. Add a failing trace for `claude-bridge`, and the passport node shows a conflict.

### Phase 4: plan inside the map (depends on 2)
- [ ] **4.1** Load this plan as one job through `workflows/build.json`: phases become tasks, with dependencies as listed and acceptance taken from the checks above.
- [ ] **4.2** `build_org_map.py`: a "Work in flight" band from `local.sqlite` jobs (read only).
- [ ] **4.3** Clicking a phase opens the Workflows panel filtered to the job; tasks link to their traces and reviews.
- **Check:** completing a task through `verify` with verifier = reviewer flips the phase count, and a correction reopens downstream tasks.

### Phase 5: end-to-end proof
- [ ] **5.1** Run a new trace `TR-<date>-B1` through Director, Conductor, worker and reviewer, with one **deliberate FAIL** first. The reviewer returns MISSING lines, the Conductor retries, and the reviewer passes.
- **Checks:** the map shows the FAIL and PASS badges, the retry as attempt 2, a `LAST_REVIEW` written by the Director, and the phase marked done in Work in flight. All of it must be seen in the browser, not inferred.

---

## 7. Acceptance checks for the whole plan
1. The reviewer appears as a workflow role between Conductor and Director, with evidence on every edge, and no longer as a connector.
2. Any trace file in `~/Alex-Director/traces/` is visible in the Tracing tab within one poll of being written. It shows agents, routes, review, retries, results, evidence links and metered cost.
3. Every node can say where its facts came from, when that source last changed, and whether it was readable.
4. Disagreements show as conflicts with both sources; nothing is silently overwritten.
5. Plan phases show status, owner role, dependencies, acceptance and evidence on the map, backed by the existing workflow store.
6. A FAIL review has been seen end to end (Phase 5). Until then, the FAIL path stays labeled "configured, not yet observed".

---

## 8. Decisions needed (only the blocking ones)
- **D1, retention of `gone` nodes:** proposed 7 days. A different number changes only 3.3.
- **D2, cost display for Codex hops:** show "plan (not metered)" (proposed), or estimate from tokens. An estimate would need a pricing source per model.
- **D3, who builds:** proposed is Codex as worker (it built this map), with Claude as reviewer, per the reviewer rule. Reversing it is fine as long as the families differ.

Not blocking: who Astra is (U1); the Tailscale check (U5).

---

## 9. Where this file lives
- `~/Alex-Director/alex-system-map-plan.md`
- `MAP/docs/alex-system-map-plan.md`

Both copies are identical. No app code was changed.

## Langflow control dashboard (2026-10-12)

Requirement and evidence checklist: `docs/LANGFLOW_DASHBOARD.md`. Status: local prototype. The pinned Langflow 1.12.5 engine run is verified (live acceptance test). Browser, phone and Tailscale checks are blocked by the sandbox port binding and an unreadable Tailscale status.
