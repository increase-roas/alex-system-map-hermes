# SigNoz collector: what is built, what is proven, what one person still has to do

> **SUPERSEDED IN PART, 2026-10-20.** The Boss Director ruled that there is **one door, not two**:
> the patched relay at `127.0.0.1:4319` is THE collector, because it already runs under launchd and
> has been proving 1Password robot reads there for days, so durability needs no new job.
>
> **`tools/otel_collector.py` is NOT DEPLOYED and will not be.** It stays in this repo as a test
> harness: its filter logic is the same policy, its 12-check suite is useful, and it was the vehicle
> for proving that policy end to end before any of it touched a shared file. Do not install it, and
> do not install the LaunchAgent described below.
>
> The LaunchAgent install in "What is still blocked" is **CANCELLED**. The plist template,
> `verify_durable.py` and `validate_p4.py` in `work/signoz-relay/` are kept for their checks and
> their record, not as an install path.
>
> The live plan is `work/signoz-relay/APPLY.md`: the patched relay plus the CLI wrapper, applied
> through the route Alex chooses. The SigNoz tool card waits for that same route.

2026-10-20, written by Claude Code (claude-opus-5) in `~/Projects/alex-system-map`.
Play `absence-alarms-20261020-p2-signoz-hookup`. Source of truth for the account:
`~/Documents/Codex/2026-10-19/signoz/SIGNOZ-SETUP.md`.

## In one paragraph

Agent traces now have a place to go that names them, caps them and refuses the unnamed. It is
`tools/otel_collector.py` in this repo, it is tested, and a span sent through it arrives in SigNoz
under the right service name while unnamed, blocked and misspelled ones are thrown away. What is
missing is durability and reach: it needs a LaunchAgent to stay alive, and each agent needs to be
pointed at it. Neither is writable from this project.

## Why a new collector rather than a patch to the existing relay

The existing relay, `~/.agents/tools/connectors/codex_otel/otlp_relay.py`, was reviewed on the
promise that it forwards OTLP bytes unchanged and "does not inspect or change span bodies".
Dropping spans by name and rate-limiting per service both require parsing the payload, which is
exactly the property it was reviewed for not having. It also sits under `~/.agents`, which this
project may not edit. So the filtering lives in a separate file here, where it can be read, tested
and reverted, and the reviewed relay keeps its contract.

The relay is not in the way: since the Codex app's tracing was switched off on 2026-10-19 its last
request was `2026-10-20T00:19:42Z` and it now has no clients at all.

## What it does

| Rule | Why |
|---|---|
| Drops any span group with no `service.name` | SigNoz does **not** do this. A span with no resource attributes at all was accepted with HTTP 200 on 2026-10-20, trace `271bb7f1cea12b2b365fc23aee6a034c`. |
| Refuses `codex-worker` outright | The ChatGPT app's firehose. Not to be forwarded unless sampled hard and Alex agrees. |
| Counts, and drops, names not on the known list | A typo in an agent's config becomes a number you can see, instead of silently becoming "other". |
| Rate-guards **every** service separately | The 2026-10-19 Langfuse flood came from spans that **were** labelled, at 0.9M to 1.4M an hour. Naming and capping are two different jobs. One service over budget cannot starve another. |
| Reads keys from 1Password at run time, caches an hour, re-reads on 401/403 | No key in a file, a log, a command line or this document. |
| Serves per-service counts at `GET /stats` | The per-service hourly rate can be reported without reading anything back from a vendor. |

Default cap is 600 spans a minute per service. Claude Code's measured rate is roughly 11 a minute,
so that is two orders of magnitude of headroom and still stops a runaway. Raise a service in
`RATE_OVERRIDES` deliberately, with the reason, rather than removing the cap.

## Proof, 2026-10-20

Self-test, no network: `python3 -B tools/otel_collector.py --self-test` -> **12/12 checks passed**,
including that the re-emitted payload is still parseable OTLP and that a throttled service does not
starve another.

End to end, through the collector to SigNoz on port 4320, then read back with the read-only key:

| sent as | collector | arrived in SigNoz |
|---|---|---|
| `claude-code` | kept | **PRESENT**, `ServiceName='claude-code'`, trace `1607ffd370d084cdc721618c34b762e8` |
| no `service.name` | dropped `(unnamed)` | ABSENT |
| `codex-worker` | dropped `blocked:` | ABSENT |
| `typo-agent` | dropped `unknown:` | ABSENT |

Collector `/stats` at that moment: `kept_spans {"claude-code": 1}`,
`dropped_spans {"(unnamed)": 1, "blocked:codex-worker": 1, "unknown:typo-agent": 1}`,
`upstream_responses {"signoz:200": 1}`.

Direct ingestion was proven separately, bypassing the collector: `claude-code` trace
`5c53704dc32271c551e92b6b07656fd7` and `codex` trace `1205d6991751240d270ed31b0aa416fa`, both read
back with the right `ServiceName`. The read key authenticates: `/api/v1/version` returns
`{"version":"v0.146.0","ee":"Y","setupCompleted":true}`.

The collector is **not running now.** I stopped it on purpose: it has no LaunchAgent, so a process
left running from a chat session dies with the session, and a tracing pipe that quietly dies is the
exact failure this whole project exists to remove.

**One honest blemish.** Two spans with an empty `ServiceName` do exist in SigNoz, traces
`3024ab909eecd893707866485b3c04ff` and `271bb7f1cea12b2b365fc23aee6a034c`. Both are mine, sent
before the collector existed: my first hand-rolled payload double-wrapped the protobuf KeyValue so
`service.name` never parsed. They do not appear in the services list. So "zero unnamed spans in the
window" is true for everything that went through the collector and false for the window that
contains my mistake. It is also the best argument for the collector: SigNoz will not catch that
class of error for you.

## What is still blocked, and on whom

**1. Durability. Needs someone who can write `~/Library/LaunchAgents`.**
The collector must be launched and kept alive. The narrowest change is a LaunchAgent modelled on the
existing `com.alex.codex-otlp-relay.plist`, with these `ProgramArguments`:

```
/usr/bin/python3
-B
/Users/alexlobaito/Projects/alex-system-map/tools/otel_collector.py
--port
4320
--upstream
signoz
--upstream
langfuse
--log
/Users/alexlobaito/.agents/runtime/otel-collector.jsonl
```

Both upstreams give the one day of side-by-side the play asks for. Drop `--upstream langfuse` after
that day. `KeepAlive` true, `RunAtLoad` true, stdout and stderr beside the log.

**2. Reach. Each agent has to be pointed at `127.0.0.1:4320` with its own name.**
Blocked for Claude Code: its exporter is in `~/.claude/settings.json`, which this project may not
edit. `~/.codex/` is writable from here, but the ChatGPT app's Codex stays off by Alex's decision and
is not to be re-pointed. The remaining agents (cursor, javar, javante, auditor, task-codex,
task-claude, paperclip-worker, paperclip-reviewer, dynamite-chatbot) live in config this project
cannot reach, or on other machines.

**3. Silence alerts. Needs a credential that does not exist yet.**
The MCP read key is role `signoz-viewer`. A `POST /api/v1/rules` with it returns
`HTTP 403 {"type":"forbidden","code":"authz_forbidden","message":"only editors/admins can access this resource"}`.
Creating alert rules needs an editor or admin SigNoz API key. That is a new credential, so it is
Alex's call. The `alex-email` channel already exists (`id 01a156e4-8ea5-7b8a-bbd8-190cbf8f6393`,
type email, to alex@increaseroas.com) and its delivery is confirmed: Alex saw the test in his Gmail
inbox at 2026-10-19 9:19 PM Detroit.

**4. The SigNoz tool card.** `~/.agents/tools/cards/signoz.md` is not writable from this project.

## Suggested N for each silence alert, when the key exists

Set from measured rhythm, not guessed. A threshold that cries wolf teaches him to ignore the alarm,
which is worse than no alarm.

| service | N | why |
|---|---|---|
| `claude-code` | 24 h | Ran on 7 of the last 7 days but goes quiet overnight. |
| `codex` | 24 h | CLI only now; used most days. |
| `auditor` | 6 h | It is actively fixing things; the thing fixing everything must not die quietly. |
| `task-codex`, `task-claude` | 30 min | The board health check runs every 5 minutes, so half an hour of silence is already wrong. |
| `javar` | 48 h | Reported on 4 of the last 7 days. |
| `javante`, `cursor`, `paperclip-*`, `dynamite-chatbot` | hold | Not instrumented yet; an alert on a service that has never reported fires immediately and forever. Add each one's alert when its first span arrives. |

## Not yet instrumented

`cursor`, `javante`, `auditor`, `task-codex`, `task-claude`, `paperclip-worker`,
`paperclip-reviewer`, `dynamite-chatbot` have sent nothing. `javar` and `javar-lab` report to
Langfuse from Orgo, not from this Mac. Only `claude-code` and `codex` have ever reached SigNoz, and
both only from my canaries.
