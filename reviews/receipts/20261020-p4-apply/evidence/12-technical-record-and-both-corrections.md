# SigNoz collector: what is built, what is proven, what one person still has to do

> **RULING, 2026-10-20, and it reverses an earlier banner on this same file.** The standalone
> collector in this repo, `tools/otel_collector.py` on `127.0.0.1:4320` under LaunchAgent
> `com.alex.signoz-collector`, **IS the one door.** Install it. Everything below describing that
> install is live, not cancelled.
>
> The earlier banner here said the opposite: that the patched relay was the collector and this
> file's install was cancelled. That is **withdrawn.** It was written on a ruling that crossed with
> the p4 evidence; once the launchd-shaped 1Password read, clean SIGTERM handling, the Python 3.9.6
> suite and the hostile verifier with its KeepAlive kill test were all in hand, the standalone
> collector was the stronger package, and it leaves a reviewed shared component untouched. I am
> leaving the reversal visible rather than quietly rewriting history, because anyone who read this
> file in the last hour was told not to install the thing that is now the plan.
>
> **What is NOT applied:** the relay patch in `work/signoz-relay/APPLY.md` and
> `make_patch.py`. `~/.agents/.../otlp_relay.py` and `codex_traced.py` stay byte-identical, except
> for one named step pointing the CLI wrapper at port 4320, which now lives in `APPLY-p4.md`.
>
> **The relay keeps running** with zero clients. Retiring it comes after Alex cancels Langfuse, as
> a proposal, not an action.
>
> The live plan is `work/signoz-relay/APPLY-p4.md`, applied through the route Alex chooses.

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

## Apply attempt, 2026-10-20: blocked at launchctl bootstrap

Alex approved the Codex-worker route in his own chat. A worker ran APPLY-p4.md through
`codex_traced.py` with narrow writable roots (`-C ~/.agents`, plus `--add-dir` for
`~/Library/LaunchAgents`, `~/Backups` and this repo; `--approve-for-me`, which is workspace-write,
never `danger-full-access`).

It installed the plist, `plutil -lint` said OK, and then stopped at step 1 with:

```
Bootstrap failed: 5: Input/output error
Try re-running the command as root for richer errors.
```

followed by `Could not find service "com.alex.signoz-collector" in domain for user gui: 501`.

The worker did the right thing: it stopped, reported, retried nothing and took no other route.

### What has been ruled out

| candidate | ruled out by |
|---|---|
| the plist is malformed | `plutil -lint` OK, and `plistlib` parses it; Label, KeepAlive, RunAtLoad and all arguments read back correct |
| already loaded | `launchctl print` says the service is not in the domain |
| disabled | not present in `launchctl print-disabled gui/501` |
| the sandbox | the identical error appears with the sandbox switched off |
| our plist specifically | the same error appears for a path that does not exist, **and** for the already-loaded relay plist, which should have said "already loaded" |
| session context | `launchctl managername` is `Aqua`, and `launchctl print gui/501` reads the whole domain, 467 active services |

So `EIO 5` is launchctl's generic failure here and carries no information, and **the cause is not
established.** What is established is narrower and still useful: `launchctl bootstrap` cannot
perform any domain write from a process in this harness, by any route available to it, while
`launchctl print` reads the same domain perfectly.

### State left behind

- `~/Library/LaunchAgents/com.alex.signoz-collector.plist` **is installed but not loaded.** An
  unloaded plist does nothing at all, so this is inert rather than half-working. It is left in place
  so the one remaining command is a single step.
- `otlp_relay.py` still hashes to `90e6dd0a0944003cf05f47ad2c6bd09627fa47eab4548d043d02644723768417`
  and the old relay is still running, pid unchanged, unharmed by the bootstrap attempts.
- `codex_traced.py` unchanged at `8eb092cc...`; the tool card not placed; nothing committed in
  `~/.agents`. Steps 2 to 5 were never reached.

### The one command that finishes it

Run from Terminal.app, as Alex, not through an agent:

```sh
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.alex.signoz-collector.plist
launchctl print "gui/$(id -u)/com.alex.signoz-collector" | grep -E "state|pid"
```

Then the rest of APPLY-p4.md from step 2, which an agent can do: `verify_durable.py` needs no
launchd write, only reads and HTTP.

## Cause isolated, 2026-10-20: two separate causes, and a third problem I caused

### Cause 1, the bootstrap failure: the Seatbelt sandbox blocks launchd domain writes

One variable, same bytes, same label:

| attempt | result |
|---|---|
| real plist, **inside** the Seatbelt sandbox | `Bootstrap failed: 5: Input/output error`, not registered |
| same plist, **outside** the sandbox | loaded, `state = running`, a live pid |
| a throwaway plist (`/usr/bin/true`, RunAtLoad false), outside the sandbox | loaded fine, so domain writes are not blocked in general |

The Codex worker ran under `--approve-for-me`, which **is** a workspace-write sandbox, which is why
it failed. So the fix for the bootstrap step is simply that it must run unsandboxed.

**Correcting an earlier entry in this file:** I previously recorded "the sandbox" as ruled out,
because the same EIO appeared with the sandbox off. That test used a **path that does not exist**,
which fails for its own reason, so it was never a valid control. A negative control that fails twice
over proves nothing. The sandbox was the cause all along.

`EIO 5` is launchctl's generic failure here: it is returned for a missing file, for an
already-loaded service, and for a sandbox refusal alike, so the error text carries no information
and the cause has to be found by changing one variable at a time.

### Cause 2: `op read` does not complete under real launchd

With the bootstrap problem solved the job started, and then died waiting on its keys. Under launchd
the 1Password read did not finish in 90 seconds; from a shell the same read had taken under 14.

**Correcting a second earlier claim, and this one I reported twice as a cleared risk:** I said the
1Password robot read was "proven to work with a launchd-shaped environment and no TTY". That test
ran a child process with a scrubbed environment. **It was a simulation of launchd, not launchd.** A
working session never proves a separate launch path is healthy, and here it did not.

### Problem 3, self-inflicted: the 1Password service account stopped answering

While isolating cause 2 the account stopped responding to anything authenticated:

| command | result |
|---|---|
| `op --version` (local, no auth) | exit 0 in 0.2s |
| `op whoami` | hangs, no answer in 25s |
| `op vault list` | hangs, no answer in 25s |

So it is not key-specific, not `HOME`, and not launchd. The authenticated path itself is hanging,
and the most likely reason is the volume of reads I generated: every collector launch reads three
secrets (SigNoz, plus the Langfuse public and secret halves), and with `KeepAlive` restarting a
failing job, a crash loop multiplies that. The robot account has a documented daily cap. I stopped
making 1Password calls rather than deepening it, so this should recover on its own; it is not
established as a permanent fault and no key was changed.

**This is a design flaw in the collector, not just an accident.** Reading every upstream's secret
eagerly at startup, under a `KeepAlive` that relaunches on failure, makes the job an amplifier
against its own credential source. Before this runs durably it needs: exponential backoff rather
than a fixed five-second retry, a cap on launches per hour (`ThrottleInterval` alone is not
enough), and lazy per-upstream reads so a failure on one does not re-read the others.

### State left behind

Clean. The service is **not** in the launchd domain, nothing listens on 4320, and no stray collector
process is running. The plist remains installed but unloaded, which is inert. `otlp_relay.py` is
still `90e6dd0a...`, `codex_traced.py` still `8eb092cc...`, no tool card placed, nothing committed in
`~/.agents`.

### What p5 inherits from this

The Mac mini will hit cause 1 identically: whatever applies its LaunchAgent must be unsandboxed.
It will hit cause 2 as well if it reads 1Password at startup the same way, and that needs solving
before the mini is wired, not after.
