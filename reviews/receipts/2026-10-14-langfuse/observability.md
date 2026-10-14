# Langfuse observability: who sends traces (receipt)

Written by Claude Code (claude-opus-5-5) for branch `langfuse-observability`. Read-only. No keys anywhere in this file.

## Project
- Langfuse Cloud US, project "Increase Roas": https://us.cloud.langfuse.com/project/cmv733aoq01e7ad0mfeqexnrx
- Plan: Hobby (free, 50k units a month, 30-day retention). Source: Alex's brief, 2026-10-14. Not re-checked in the Langfuse UI here.

## Live read (2026-10-14T01:49Z UTC)
Route: Composio toolkit `custom_langfuse_mcp`, login `ca_lBDTsWLoD1qf` (card `~/.agents/tools/cards/langfuse.md`).
Tools: `CUSTOM_LANGFUSE_MCP_QUERY_METRICS` (log_UzFjwLk2cQzP) and `CUSTOM_LANGFUSE_MCP_LIST_OBSERVATIONS` (log_JjTAA_0CCx9V), both read tier T0/T1.

Observations from 2026-10-12T00:00Z to 2026-10-14T02:00Z, grouped by environment:

| environment | observations | distinct traces | example observation names |
|---|---|---|---|
| default | 83 | 3 | `claude_code.llm_request`, `claude_code.tool`, `claude_code.tool.execution` (latest 2026-10-14T01:49:07Z) |
| javar-lab | 6 | 3 | `Hermes turn` (CHAIN), `LLM call 1` (GENERATION) (latest 2026-10-14T01:45:46Z) |
| javar | 0 | 0 | none: live Javar is not wired yet |

Example trace links (open with Alex's Langfuse login):
- Claude Code: https://us.cloud.langfuse.com/project/cmv733aoq01e7ad0mfeqexnrx/traces/2e2270851f1aa893361caedf5448803a
- JAVAR-LAB: https://us.cloud.langfuse.com/project/cmv733aoq01e7ad0mfeqexnrx/traces/1a738dbee881338774fc4194a0d5384d

## Senders
| Sender | State | How | Evidence |
|---|---|---|---|
| Claude Code (Alex's Mac) | live, seen working 2026-10-13 | OpenTelemetry, traces only (metrics and logs exporters `none`); keys read from 1Password at run time by `~/.agents/tools/connectors/langfuse_otel_headers.py` (`otelHeadersHelper` in `~/.claude/settings.json`); endpoint `https://us.cloud.langfuse.com/api/public/otel/v1/traces`. Prompts redacted (Alex's brief). | `claude_code.*` observations above (env "default"); first proof 2026-10-13T23:09:48Z (`~/.agents/runtime/prove_tracing.py` run, earlier session) |
| JAVAR-LAB (Hermes 0.21.7) | live, seen working 2026-10-14 | Hermes `observability/langfuse` plugin, env "javar-lab", wrapper `/usr/local/bin/hermes-lab`; keys from 1Password vault `Agent — JAVAR-LAB` (exact 1Password name) via a read-only service account, held in memory only | `Hermes turn` observations above (env "javar-lab"); first at 2026-10-14T01:31:05Z |
| Javar, live (Hermes 0.21.5) | planned | same plugin, env "javar"; needs Alex's go for a short restart | none yet (0 observations in env "javar") |
| Codex | not wired | nothing sends from Codex | none |

## How agents use it
Agents read and write Langfuse through Composio toolkit `custom_langfuse_mcp` (Langfuse's own hosted MCP, 86 tools). Judges, deletes, prompt `production` labels and LLM connections wait for Alex (card "Ask Alex first").

## Re-read after the Codex review (2026-10-14T02:11Z UTC)
Raw output of `CUSTOM_LANGFUSE_MCP_QUERY_METRICS` (Composio log log_59xNgfORn8nf, account `ca_lBDTsWLoD1qf`,
view observations, dimension environment, metrics count/count and traceId/uniq, window 2026-10-12T00:00:00Z to 2026-10-14T02:15:00Z):

```json
[{"count_count":1095,"environment":"default","uniq_traceId":10},
 {"count_count":6,"environment":"javar-lab","uniq_traceId":3},
 {"count_count":2,"environment":"javar","uniq_traceId":1}]
```
The first read's log IDs (log_UzFjwLk2cQzP, log_JjTAA_0CCx9V) are not retrievable from the Composio CLI (Codex got 404), so this
raw block replaces the 83/6/0 snapshot as the counted evidence. Environment `javar` now has 1 trace: live Javar's first trace landed
between 01:49Z and 02:11Z.

## Prompt redaction (Claude Code)
Claude Code's monitoring docs (https://code.claude.com/docs/en/monitoring-usage, read 2026-10-14) say: spans redact user prompt
text, tool input details and tool content by default; `OTEL_LOG_USER_PROMPTS`, `OTEL_LOG_TOOL_DETAILS`, `OTEL_LOG_TOOL_CONTENT`
switch them on. `~/.claude/settings.json` sets none of them (grep count 0, 2026-10-14). Configured, not inspected trace by trace.

## Plan terms
https://langfuse.com/pricing (read 2026-10-14): Hobby is free, 50k units a month, 30 days data access, 2 users, 2 alerts.

## Javar's first trace (2026-10-14T02:12Z read)
`CUSTOM_LANGFUSE_MCP_LIST_OBSERVATIONS` env javar (log log_HQ84koC3w610): trace 4e8d8ebd34ccb494ba64e59617f00415, `Hermes turn` (CHAIN)
and `LLM call 1` (GENERATION) at 2026-10-14T02:03:15Z.

## Agent fleet dashboard (created 2026-10-14T02:08Z to 02:11Z)
https://us.cloud.langfuse.com/project/cmv733aoq01e7ad0mfeqexnrx/dashboards/cmv7h0unq0500ad0ey1io48r9
Read back with `CUSTOM_LANGFUSE_MCP_GET_DASHBOARD` (log log_59xNgfORn8nf): 7 charts (total spend, runs per agent, spend per agent,
errors per agent, p95 model latency, tokens by model, most used tools). One duplicate tile of "Spend per agent" (placement
6c558eaf) came from a retry after a 429; removing it is a delete, which the Langfuse card sends to Alex.

## Machine-read sender states (the map builder reads these lines)
LIVE: default
LIVE: javar-lab
LIVE: javar
