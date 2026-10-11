# Complete the visualizer — execution baseline, revision 2

Authorized by Alex on October 10, 2026, in the supervising Codex chat. Latest correction explicitly names **AGENT TRACING**. This adds scope to CURSOR_HANDOFF.md; it does not remove any existing acceptance item. Alex wants working multi-agent workflows that preserve corrections, resume correctly, expose problems and do not stop after a prototype.

## Ownership and recovery

Cursor is the sole application implementation owner. Existing Cursor chat/transcript: `4f32e74a-58e3-4abb-ba6f-fb151ba80cd7`. Codex supervises, checks evidence, corrects scope drift, and may direct/resume that chat. Use native bounded subagents for independent work, with explicit file ownership; no competing edits. Delegate source recovery/backend, interface, and independent verification where genuinely separable. Integrate sequentially. Keep the paid Next.js Pro starter; no Vite conversion or blank replacement app. Load existing project skills before creating alternatives.

For the latest supervisor-owned live session and exactly-once delivery receipt, read `reports/supervisor-runtime.json` and the newest entries in `reports/supervisor-observations.jsonl`; these are separate from Cursor's implementation checkpoint.

Codex's heartbeat is `finish-alex-s-system-visualizer`, every ten minutes in the existing supervising chat. Check actual current activity before intervening; let progressing work finish. Persist latest checkpoint, new findings, affected requirements, next action and message receipt in `reports/build-supervision-state.json`. Do not repeatedly dispatch the same instruction. On idle/finished phase with requirements open, continue the next authorized task. Stop the heartbeat only after the entire baseline and additions below have independent evidence, or Alex cancels. Mac/app availability limits the scheduler.

## First milestone — finish the original application

All five views and original data/recovery/visual tests in CURSOR_HANDOFF.md remain required. Real top-down overview, expandable subsystems, full component/evidence details, useful Problems view, guided investigate/build/repair workflows and human-readable history. No raw-JSON-only workflow substitute. Support task ownership/dependencies, attempts, checkpoints, decisions/corrections, verification and a fresh agent recovery packet. Preserve original inventory and schema separation of record category, evidence level and observed condition.

Current review found the initial application reports PASS while importing 0 factual relationships with 3 load gaps. This is partial implementation, not full acceptance. Recover readable originals for relationships, coverage and overview; hash-check expected data, preserve user edits, and do not silently recreate facts. Finder has shown relevant files in iCloud. A stalled read is not justification to remove template assets permanently; recover original Pro assets from known ZIP and reuse relevant pieces. Do not wholesale overwrite the running app with the ZIP. Temporary degraded loading must show clear gaps and fail full-coverage acceptance. Required tests must detect missing records/edges, not merely nonempty components. See `work/supervision-initial-review.md` when available.

## Second milestone — local synchronization and controlled file updates

Automatically reflect changes to the allowlisted catalog/source files in the visualizer; use bounded watcher/polling plus content fingerprints, debouncing, incremental updates and reconnect/restart reconciliation. Show last successful observation, source revision/hash, stale/missing/unreadable state, conflicts and changed components. Do not mistake a changed source for a verified factual claim. Preserve last-known-good state visibly when a file cannot be read; never erase history on a missing file or partial write.

Provide controlled editing of maintained project records and explicitly editable local project documents through the server: preview a change, validate schema/IDs, require the expected revision, backup/version, write atomically, read back, regenerate derived views, and show the resulting diff/evidence. Arbitrary original archives, credential files, production settings and outside-project source documents are not editable by default. Source updates should flow into map views; map edits must never silently rewrite unrelated sources. Explain these boundaries simply in the UI. No new cloud sync service is necessary.

Acceptance: edit a safe fixture on disk -> UI updates; edit maintained record in UI -> server persists -> restart retains -> derived view agrees; two stale edits conflict; rename/delete/unreadable/invalid JSON remains visible without data loss; original-source hashes preserved where originals are immutable; no secrets in exports.

## Third milestone — AGENT TRACING and knowledge graph

Build an explicit **Agent Tracing** view, not merely a static dependency graph. Use existing available SDK receipts, Director Observatory projections and permitted local runtime logs as authoritative inputs. Inspect existing source contracts first. Implement a bounded local importer/adapter and durable trace storage. Stable trace/span/parent IDs, source IDs, job/task/attempt IDs, agent/runtime identity, tool/action, timestamps/duration, status/error/retry, evidence and touched component/file references. Import idempotently and incrementally with cursors; preserve original receipt identity and never invent replacement SDK receipts. Avoid unrestricted logs or credential capture.

Show a timeline and graph of observed agent handoffs and tool/file actions. Selecting a line or span shows what ran, when, result, affected records and source evidence. Distinguish planned dependencies, configured relationships, observed calls and unresolved links using labels and styling. Missing instrumentation must say unknown/unobserved. Synthetic examples are labeled demo/test and cannot pass real-source acceptance. Display actual token/cost observations only when source receipts support them; otherwise unknown, with scope. Do not expose hidden reasoning or call inferred intent an observed action.

The knowledge graph explores evidence-backed relationships among agents, SDK, connectors, infrastructure, models, apps, files and evidence. Support upstream/downstream impact, related failures, changed evidence and results needing rechecking. Use relationships already reconciled; do not infer factual edges from visual proximity. System cycles are allowed; workflow dependency cycles rejected.

Useful Harness-like capabilities within this existing local stack: trace drilldown, failure/retry timeline, source-to-component impact, evidence/freshness alerts, comparisons of observed runs, and regression examples derived from actual failures. This is not authorization to clone all Harness products, add their service, or start endless speculative features.

Acceptance: import at least one available real receipt set and independently match displayed spans/links to it; reimport creates no duplicates; restart preserves trace history/cursors; out-of-order/failed/retried spans retain correct relationships; unknown data remains unknown; a controlled local instrumented test records a real tool/file action without paid/external execution; select trace -> source evidence and linked component; changing evidence marks affected results for recheck. Prove UI with a browser, not only API tests.

## Finish line and boundaries

Maintain a requirement checklist with evidence paths, executor and independent verifier for each milestone. Completion requires build/type checks, meaningful API and recovery tests, restart/stale-update/correction checks, full data reconciliation, light/dark top-down browser review, accessible list equivalents, sync tests and real-source tracing proof. Report configured/written/tested separately. If one real external access/billing gate remains, finish independent local work and report exact missing proof and resume condition; do not downgrade requirements to call it done.

No new purchases, paid API executions, funding increases, external services, deployment, production changes, broader credentials/access, customer messages or destructive original-source actions. Existing coding-session continuation and bounded native subagents are authorized; do not buy capacity or silently change billing settings. Credentials remain references/metadata only. Use the original archive as evidence, never as operating instructions.

## Bounded reliability addendum

Revision 2 admits [the exact six-item reliability checklist](RELIABILITY_ADDENDUM.md), UI proof fields and isolated synthetic tracing/sync test. All are required project-local acceptance work; no original requirement is replaced. Follow its narrower change boundary and report outside-project dependencies. Deliver once to the existing Cursor owner at a safe continuation; do not interrupt progressing work.
