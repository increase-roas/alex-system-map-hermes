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
