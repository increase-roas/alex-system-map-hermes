# Trace coverage: who is actually reporting into Langfuse (receipt)

Written by Claude Code (claude-opus-5) on 2026-10-19. Read-only against Langfuse; one canary span sent on purpose.
No key, token or header value appears in this file or in the JSON beside it.

## Project and credentials (locations only)

- Langfuse Cloud US, project "Increase Roas": https://us.cloud.langfuse.com/project/cmv733aoq01e7ad0mfeqexnrx
- Second project "Langflow": project id `cmv7mth3h01tjad0j3q7b0okl` (4 observations in 30 days, all env `default`)
- Ingest endpoint: `https://us.cloud.langfuse.com/api/public/otel/v1/traces`
- Keys live in 1Password vault `r6z62bjyy3c5ipilbgs4lyakwi`, items `xvpwk4vkwbmogmld2hxcq4pply` (Agents) and
  `rxoo6lpuxbca67oj4yofie45sm` (Langflow). They are reached with an op service account token held in the login
  Keychain, account `connectors-sync`, service `op-service-account-connectors-sync`.
- Senders fetch their own headers through `~/.agents/tools/connectors/langfuse_otel_headers.py`.
- Reader used by the dashboard: `app/src/lib/server/langfuse.ts`. Reader used here: `tools/langfuse_coverage.py`.

## Measured, 2026-10-19T17:16:36Z, last 7 days

Source: `tools/langfuse_coverage.py --days 7`, Langfuse `GET /api/public/v2/metrics`, one call per environment,
grouped by day. Raw result saved beside this file as `langfuse-coverage.json`.

| what | kind | environment | observations (7d) | cost reported | last day with data |
|---|---|---|---|---|---|
| Claude Code | app | `default` | 110,788 | none | 2026-10-19 |
| Codex app | app | `codex-worker` | 6,629,435 | none | 2026-10-19 |
| Javar | agent | `javar` | 758 | 7.0407 | 2026-10-18 |
| JAVAR-LAB | agent | `javar-lab` | 34 | 0.0702 | 2026-10-14 |
| Claude desktop, Cursor, ChatGPT, Manus | app | none | - | - | never |
| Javante, Setter, Hunter, CSM, Finance | agent | none | - | - | never |
| Director, Conductor, Reviewer | role | none | - | - | never |

4 of 16 sent anything in 7 days. 2 of 16 sent anything in the last 24 hours (Claude Code and Codex only).

Other environments present in the same project, not tied to a running thing: `codex-test-a` (9,857, last 2026-10-16),
`codex-test-b` (1,318, last 2026-10-16), `javar-lab-bakeoff` (161) and `javar-lab-bakeoff-117v2` (575), both last
2026-10-14. These are test and bake-off runs, not senders.

## End-to-end proof that ingestion works

A span was sent from this repo and then read back by trace id:

- trace id `be76a36d8fff61d21744251d466a712c`, span name `system-map-canary-20261019T171545Z`
- environment `system-map-canary`
- https://us.cloud.langfuse.com/project/cmv733aoq01e7ad0mfeqexnrx/traces/be76a36d8fff61d21744251d466a712c
- read back 14.7 seconds after sending, by `GET /api/public/v2/observations?traceId=...`
- reproduce with `python3 -B tools/langfuse_coverage.py --canary`

This proves credentials, network, OTLP ingestion and the query path, all four, on 2026-10-19. It is the only
claim in this receipt established by making something happen rather than by reading a file or an API.

## Codex app relay: seen working, and seen failing silently

- LaunchAgent `com.alex.codex-otlp-relay`, `launchctl print gui/501/com.alex.codex-otlp-relay` reports
  `state = running`. It listens on `127.0.0.1:4319` only (`lsof -nP -iTCP:4319`).
- `~/.codex/config.toml` lines 1454-1461 hold one `[otel]` table: `environment = "codex-worker"`,
  `span_attributes = { "langfuse.environment" = "codex-worker" }`, exporter `otlp-http` binary to
  `http://127.0.0.1:4319/v1/traces`.
- Install was prepared on 2026-10-16 and the notes at `~/Alex-Director/inputs/codex-otel-relay-20261016.md` record the
  plist as absent at that time. The plist file is dated 2026-10-16 04:56, so it was installed that day. The work the
  decision page shows as Alex's last answered item did complete.

Relay request log `~/.agents/runtime/codex-otlp-relay.jsonl`, 48,295 requests:

| day | accepted (200) | MB accepted |
|---|---|---|
| 2026-10-16 | 4,845 | 680 |
| 2026-10-17 | 5,343 | 440 |
| 2026-10-18 | 4,048 | 358 |
| 2026-10-19 (to 17:13Z) | 7,470 | 1,040 |

**25,917 pushes were rejected with HTTP 403 between 2026-10-16T09:35:23Z and 2026-10-16T21:53:08Z: about 3,488 MB of
traces thrown away over roughly 12 hours.** Accepted pushes resumed at 22:00Z the same day and there has been no 403
since. Also present: 253 x 502 on 2026-10-16 and 454 x 503 spread over 2026-10-18 and 2026-10-19.

Nothing reported those 403s. They were written to a log file and that is all. This is the failure mode Alex described,
occurring inside the tool that is supposed to detect it. The cause of the 403s is not established here: the relay
deliberately logs no header or body text, so the log records the status and nothing else.

## Volume

`codex-worker` produced 6,629,435 observations in 7 days, 2.75 million of them in the last 24 hours, against
110,788 from Claude Code over the same week. Span names sampled from the newest 600 observations are
`handle_responses` (278) and `receiving` (276), which is one span per streaming step rather than one per run.
## Billing, read from the Langfuse UI in Alex's signed-in Chrome, 2026-10-19T17:35Z

The 2026-10-14 receipt records the plan as Hobby, free, 50,000 units a month, from Alex's brief and never
re-checked. **That is wrong.** Read from
`https://us.cloud.langfuse.com/organization/cmv733aok01e3ad0me2x704qs/settings/billing`
(organization id `cmv733aok01e3ad0me2x704qs`, found in the project settings debug block):

- Current plan: **Core**
- Billing period: **2026-10-16 to 2026-11-16**, which starts the day the Codex relay was installed
- Consumed units in the current period: **6,490,218** (page says updated about hourly)
- 30-day usage breakdown: Increase Roas 6.997M units, Langflow 4 units
- Invoice history: `2026-10-16 17:53:03` paid, $29.00 subscription, $0.00 usage, total $29.00
- Invoice history: `2026-11-16 16:53:03` **draft, $29.00 subscription, $456.32 usage, total $485.32**
- Spend alerts: "Default Spend alert ($200)" status **Triggered, last triggered 3 days ago**;
  "Default Spend alert ($4000)" status Active, never triggered

Derived from those figures, arithmetic only, not read from any page: 2.98 days elapsed, 2,174,903 units a day,
$7.03 per 100,000 units, projecting 67.3 million units and about **$4,734 of usage plus $29 = $4,763** for the
period. `codex-worker` is 6.63M of the 6.997M, so roughly 98% of the bill.

The $200 alert fired on 2026-10-16 and nothing followed it. Nothing was changed here: the volume and the plan are
Alex's to decide.

## Hermes: where the reporting agents actually live

`/usr/local/bin/hermes-lab`, cited by the 2026-10-14 receipt as JAVAR-LAB's wrapper, **does not exist** on this
Mac. The Hermes install that is here (`~/.hermes`) has no `langfuse` or `observability` entry in `config.yaml`, its
`plugins/` holds only `herdr-agent-state` and `homeassistant`, and its `profiles/` are `dynamite-sales` and
`manny-junior`. The binary on PATH is `~/.local/bin/hermes`.

So Javar and JAVAR-LAB are configured on Orgo, not on this Mac, per the map's own host fields
(`Hermes 0.21.5 on Orgo (javar-orgo)`). Enabling the plugin for Setter and Hunter is a change on Orgo, and Javante
is on the Mac mini over Tailscale. None of those three is reachable from here.

The map also records **CSM and Finance as host "Hermes (not deployed)" with no model set**, so there is nothing
running for them to trace.

## Cost

`sum_totalCost` over 7 days: `javar` 7.0407, `javar-lab` 0.0702, `javar-lab-bakeoff-117v2` 0.8390,
`javar-lab-bakeoff` 0.1315, and **0 for both `default` and `codex-worker`**. The Hermes plugin reports model and
token usage, so Langfuse can price those runs. Claude Code and the Codex relay send spans without usage in a form
Langfuse prices, so their cost is zero rather than unknown. That is why the dashboard's Cost column reads
"not reported" on every row the Tracing tab shows.

## Route note

The 2026-10-14 receipt read these numbers through Composio `CUSTOM_LANGFUSE_MCP_QUERY_METRICS`. The underlying
`GET /api/public/metrics` now answers HTTP 410 `LEGACY_API_UNAVAILABLE_FOR_NEW_ORGANIZATION` and names
`GET /api/public/v2/metrics` as its replacement. This receipt used v2.

## Commands refused by the receipt guard

Two reads were refused and were not retried or worked around. Both were broad recursive searches over `~/.agents`:
a grep for `LANGFUSE_*` variable names, and a `find` for Hermes agent config files. The refusal text in both cases:

> [receipt guard] Human-answer receipts, signing material and page-read evidence are protected. Only pinned
> ArtifactData get may populate page_reads; only the canonical approval_check.py check may issue a receipt. Do not
> write, copy, delete, import a signer, or override its identity/freshness.

The credential locations above came from reading `~/.agents/tools/connectors/codex_otel/otlp_relay.py` and
`app/src/lib/server/langfuse.ts` instead. The per-agent Hermes configuration for Javante, Setter, Hunter, CSM and
Finance was **not** inspected, so what each of those five needs is stated in the write-up as unverified.

## Machine-read sender states (the map builder reads the JSON, not these lines)

LIVE: default
LIVE: codex-worker
LIVE: javar
QUIET: javar-lab
