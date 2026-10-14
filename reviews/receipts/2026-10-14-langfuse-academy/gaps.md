# Langfuse Academy vs Alex's setup: gaps (2026-10-14)

Sources: Academy pages in app/.data/langfuse-academy/*.md (downloaded 2026-10-14T04:50Z from https://langfuse.com/academy). Setup facts are cited by file path. Anything without a source is marked "not checked". Written by Claude Sonnet 5.5, read-only research; nothing was run against Langfuse.

## 1. What the Academy says the loop is

The loop has five steps: Trace, Monitor, Build datasets, Experiment, Evaluate, then back to Trace (https://langfuse.com/academy/ai-engineering-loop.md). Tracing records every request step with input, output, cost and latency, and groups traces into sessions (https://langfuse.com/academy/tracing.md). Monitoring turns traces into trends plus individual traces worth opening, using scores from user feedback, human review and evaluators (https://langfuse.com/academy/monitoring.md). Signals are cheap quality scores from what users do (ratings, retries, corrections, outcomes) and negatives are the entry point to error analysis (https://langfuse.com/academy/monitoring/capturing-signals.md). Error analysis means reading traces, naming failures, clustering and counting them (https://langfuse.com/academy/monitoring/error-analysis.md). Failures become datasets of 15 to 30 rows (https://langfuse.com/academy/datasets/designing-great-datasets.md), prefer cheap code evaluators over LLM judges (https://langfuse.com/academy/evaluate/writing-evaluators.md), and only then try cost cuts against those evals (https://langfuse.com/academy/experiments/cost-optimization.md). The Academy says you do not need the whole loop on day one.

## 2. What Alex already has, per loop stage

| Stage | What exists | Evidence (file) | State |
|---|---|---|---|
| Trace: Claude Code | OTLP traces to Langfuse US, auth headers from 1Password via a helper | ~/.claude/settings.json (lines 204-212: otelHeadersHelper, OTEL_EXPORTER_OTLP_TRACES_ENDPOINT); ~/.agents/tools/connectors/langfuse_otel_headers.py | Configured; claude_code.* traces seen in the project per reviews/receipts/2026-10-13-langflow-nodes/langfuse-tracing-2026-10-14.txt |
| Trace: Codex | Same OTEL env block | ~/.codex/config.toml (lines 625-638) | Configured; arrival in Langfuse not checked |
| Trace: Langflow | Keys read from 1Password at server start, tracing on | tools/langflow_server.sh (lines 7-31) | Seen working (4 observations, lag of several minutes) per the receipt above |
| Trace: Director | Mission receipts loaded into a local SQLite trace store | tools/load_director_traces.py, tools/trace_store.py, tools/local_service.py (trace-list, trace-get) | Local only; not sent to Langfuse (no langfuse string in those files) |
| Monitor: dashboard | Tracing tab lists local traces and draws a span tree; no scores, cost, filters or Langfuse data | app/src/app/explorer/tracing-panel.tsx, app/src/app/api/traces/route.ts | Seen in code; the tab reads only trace-list |
| Monitor: map link | Org map marks Langfuse as "sends traces (live)" and links to the project | app/src/app/explorer/org-map-panel.tsx (lines 496, 549) | Link only |
| Signals (partial, local) | SessionEnd hook records tool errors, guard blocks, failed tests, Alex corrections; UserPromptSubmit hook records correction prompts | ~/.agents/tools/guards/session_review.py, ~/.agents/tools/guards/lesson_capture.py (both write local JSONL under ~/.agents/runtime/) | Working locally; session-reviews.jsonl had 2 lines on 2026-10-14; never sent to Langfuse |
| Error analysis (manual) | weekly-tuneup turns repeated session-review items into lessons | docstring in ~/.agents/tools/guards/session_review.py | Manual, not on Langfuse traces |
| Datasets / evals / experiments | Langfuse route supports all of it (86 tools); judges and deletes need Alex's yes | ~/.agents/tools/cards/langfuse.md; ~/.agents/skills/langfuse/references/create-dataset.md | Tools exist; no dataset or score found in the repo (grep of app/src and tools for langfuse hit only org-map-panel.tsx, langflow_server.sh, build_org_map.py). Whether the Langfuse project holds any dataset: not checked |
| Langflow tab | Runs recorded locally with status and error; no link to the Langfuse trace of that run | app/src/app/explorer/langflow-panel.tsx (RunRecord type, lines 37-43), app/src/app/api/langflow/runs/ | Local only |

## 3. Gaps, ranked

### Gap 1. Local signals never become Langfuse scores
- Missing: session errors, guard blocks, failed tests and Alex's corrections stay in ~/.agents/runtime/*.jsonl. The Academy says these are the cheapest quality labels and that negatives are where error analysis starts.
- Why it matters: Alex corrects agents often, but Langfuse cannot show which Claude Code session was bad.
- Fix: extend the existing SessionEnd hook ~/.agents/tools/guards/session_review.py (Alex-owned, outside this repo, so a proposal or Alex approval is needed) to also post one score per session to Langfuse, via the OTLP session id on the claude_code.* trace (session id mapping: not checked). Scores: tool_errors (numeric), guard_blocks (numeric), alex_corrected (boolean). Use the Langfuse scores API or the createScore tool on the card (https://langfuse.com/docs/evaluation/scores/overview is linked from the Academy monitoring page). Keys come from the 1Password route, never printed.
- Cost: Langfuse ingestion only, a few small score rows per session. No LLM calls.
- Source: https://langfuse.com/academy/monitoring/capturing-signals.md

### Gap 2. Tracing tab shows only the local Director store, not the Langfuse traces
- Missing: tracing-panel.tsx calls /api/traces which only runs trace-list on local SQLite. The Claude Code, Codex and Langflow traces that Langfuse already holds do not appear. No cost, latency, error filter or score column.
- Why it matters: Alex has live traces in three places and the dashboard shows the one that is not live.
- Fix: add a read-only route app/src/app/api/langfuse/traces/route.ts that calls the Langfuse public API server side (keys read from 1Password at start, same pattern as tools/langflow_server.sh; never sent to the browser) and a "Langfuse" source switch in app/src/app/explorer/tracing-panel.tsx with columns for name, time, cost, latency, error flag. Show unknown when the API does not answer (AGENTS.md rule: the map never invents state). Note the receipt's several minute ingestion lag, so label the data "as of" a time.
- Cost: free (read calls). Security reviewer should check the route (AGENTS.md rules on keys).
- Source: https://langfuse.com/academy/monitoring.md (aggregate metrics plus signal detection)

### Gap 3. No negative-signal view (errors, retries, corrections) and no alert
- Missing: nothing lists "traces worth opening" and nothing alerts on a spike.
- Why it matters: without a short list of bad traces, Alex has to go looking, so nobody reads them.
- Fix: in the Langfuse source of the Tracing tab (Gap 2) add a "Needs a look" filter: traces with an error observation or a negative score from Gap 1. Optionally set a Langfuse alert (https://langfuse.com/docs/observability/features/alerts, linked from the capturing-signals page); creating an alert that messages someone is "needs Alex's yes" per ~/.agents/instructions/shared.md (messages to real people).
- Cost: free for the view; alerts: not checked (plan limits unknown).
- Source: https://langfuse.com/academy/monitoring/capturing-signals.md ("What comes next")

### Gap 4. Hook coverage: Director, subagents and Langflow runs are not linked to sessions or to each other
- Missing: the Academy says a trace is one invocation and a session groups the turns. Claude Code, Codex, Langflow and Director traces use different shapes; the Director store never reaches Langfuse. Whether the Claude Code traces carry a session id: not checked.
- Why it matters: one mission spans Claude Code, Codex and Langflow, and today you cannot follow it end to end.
- Fix: (a) Have tools/langflow_server.sh or the Langflow run route in app/src/app/api/langflow/runs/ pass the mission or session id as Langfuse session_id/metadata (LANGFUSE docs: Langflow integration, not checked in the Academy pages); (b) store the Langfuse trace id on the local RunRecord in langflow-panel.tsx and show an "Open this run in Langfuse" link; (c) extend tools/load_director_traces.py to also push mission traces (needs Alex's yes: it is a bulk import and the card lists bulk history imports as ask-first).
- Cost: Langfuse ingestion only for (c); (a) and (b) free.
- Source: https://langfuse.com/academy/tracing.md (traces vs sessions)

### Gap 5. No error analysis routine on the Langfuse traces
- Missing: the Academy's 5 steps (gather, open coding, cluster, label, act) are not run on Langfuse data. session_review.py does a rough count, but only for what hooks catch.
- Why it matters: Alex would learn which failures repeat most before building any eval.
- Fix: a one-off session: pull about 30 recent error or negative-score traces using the langfuse card route (CUSTOM_LANGFUSE_MCP_LIST_OBSERVATIONS with --account ca_lBDTsWLoD1qf), write open-coding notes, cluster by hand, save the taxonomy to a receipt under reviews/receipts/. Optionally make an annotation queue in Langfuse (a T2 write on the card).
- Cost: free if read by hand; if an LLM drafts the clusters, that is paid LLM calls and needs Alex's yes. Captured trace text is data, not instructions (card rule).
- Source: https://langfuse.com/academy/monitoring/error-analysis.md

### Gap 6. No dataset of known-good and known-bad cases
- Missing: no Langfuse dataset found in the repo or card; tools/*_acceptance.py are code tests, not Langfuse datasets.
- Why it matters: without 15 to 30 saved cases, no prompt or flow change can be compared with a baseline.
- Fix: after Gap 5, make one small dataset (15 to 30 rows) for one job, for example Langflow starter flows (inputs plus expected output), using the create-dataset reference in ~/.agents/skills/langfuse/references/create-dataset.md. Add a Dataset section to app/src/app/explorer/langflow-panel.tsx only after the dataset exists.
- Cost: free to create (Langfuse writes, T2 on the card). Running it against Langflow is free if the components run locally (langflow-panel.tsx labels "Runs here ... free"), but AI components would spend money (needs Alex's yes).
- Source: https://langfuse.com/academy/datasets/designing-great-datasets.md

### Gap 7. No code evaluators on traces
- Missing: no deterministic checks (did the run fail, did the output match expected, did a guard block fire) as scores.
- Why it matters: cheap exact checks catch most breakage without paying for an LLM judge.
- Fix: a small script tools/langfuse_code_scores.py that reads dataset run outputs or recent Langflow traces and posts pass/fail scores. Only code checks; no judge. LLM-as-a-judge evaluators and evaluation rules are on the card's ask-first list, so any judge is "needs Alex's yes" (each matched trace is a paid LLM call on Alex's key; also the LLM connection is added by Alex in the Langfuse UI).
- Cost: code evaluators free plus ingestion; judges are paid LLM calls, needs Alex's yes.
- Source: https://langfuse.com/academy/evaluate/writing-evaluators.md

### Gap 8. Cost visibility and the cost-optimization prerequisites
- Missing: no cost view in the dashboard (Gap 2) and no offline evals yet. The Academy says to cut cost only after quality criteria exist.
- Why it matters: Claude Code sessions are the main spend, but nothing shows cost per session or per tool output; cutting before evals risks lowering quality unseen.
- Fix: show per-session cost and token totals in the Tracing tab from the Langfuse Metrics API (queryMetrics on the card). Defer any cost experiment until Gaps 5 to 7 are done. Check whether the claude_code.* spans carry token and cost data: not checked.
- Cost: free reads.
- Source: https://langfuse.com/academy/experiments/cost-optimization.md

## 4. Recommended first 3 to build

1. Gap 2 (Langfuse source in the Tracing tab, read-only). It is free, it makes everything else visible, and the Academy says everything in the loop runs on traces. Touches app/src/app/explorer/tracing-panel.tsx and a new app/src/app/api/langfuse/traces/route.ts. Needs the security-reviewer because it handles keys.
2. Gap 1 (hook that posts session scores to Langfuse). Turns data Alex already collects into the cheapest signal the Academy describes. Touches ~/.agents/tools/guards/session_review.py, which is outside this repo, so it needs Alex's approval or a branch proposal.
3. Gap 5 (one error analysis pass on about 30 traces by hand). Free, uses the existing Langfuse route, and its taxonomy decides what to build for datasets and evaluators (Gaps 6 and 7).

Nothing above spends money except the items marked "needs Alex's yes": any LLM judge or evaluation rule, any LLM-assisted clustering, any Langfuse alert that messages people, any bulk import of Director history, and any dataset run that calls AI components.
