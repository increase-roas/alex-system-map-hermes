# What `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1` does to span volume

Measured 2026-10-20 by Claude Code (claude-opus-5), read-only against Langfuse. Asked for before
Claude Code is pointed at the local collector, because the last time something started sending
more than expected it cost about $159 a day.

## The answer

**No sign that the flag increases span volume, and no new kind of span appeared.** Claude Code runs
at roughly **6 to 9 spans a minute**, which is about **70 times under** the collector's 600 a minute
per-service guard, and costs around **$1 a day** at Langfuse's $8 per 100,000 units. Pointing it at
the collector is safe on volume grounds.

That is a different conclusion from the Codex app, which ran at 15,000 to 23,000 spans a minute.
There is no resemblance.

## When the flag appeared

`~/.claude/settings.json` was last written **2026-10-19 16:42 Detroit, which is 20:42 UTC**. The
flag was absent when I read that file at 17:35 UTC the same day and present at 02:25 UTC the next,
so 20:42 UTC is when it arrived. There are no backups of that file to date it more precisely, and
Langfuse's audit log is an Enterprise feature, so this is the best available timestamp.

## The strongest evidence: the span names did not change

This is the part that is not affected by how busy the session was.

| span name | before the flag | after the flag |
|---|---|---|
| `claude_code.llm_request` | 1,549 | 615 |
| `claude_code.tool.blocked_on_user` | 1,441 | 502 |
| `claude_code.tool` | 1,440 | 490 |
| `claude_code.tool.execution` | 1,416 | 484 |
| `claude_code.interaction` | 132 | 102 |

The same five names, in the same proportions, before and after. **The beta added no new span
type and changed no ratio.** If it were inflating volume by instrumenting something extra, a new
name or a shifted ratio is what that would look like, and neither is there.

## Spans per trace

With the flag on, over a window I read to completion: **2,204 spans across 103 traces = 21.4 spans
per trace.**

The before-window figure was 42.6 spans per trace, but **I do not trust it and it should not be
quoted.** That read stopped at my 60-page limit with 6,000 spans and more still waiting, and paging
through a truncated, ordered sample counts all the spans of some traces and only part of others, so
the ratio is biased by an unknown amount. The after-window read completed, so only that one is
sound.

## Hourly rate

Observations per hour in Langfuse environment `default`, which is Claude Code:

- **before the flag:** 34 hours with data, 17,871 spans, mean 526/hour, median 482, peak 1,451
- **after the flag:** 6 hours with data, 2,175 spans, mean 362/hour, median 265, peak 909

That looks like a fall, and **I am not claiming the flag reduced anything.** Hourly span counts
track how hard the tool was being used, not the flag: the quiet overnight hours of 2026-10-19
produced 6 to 74 spans an hour while the busy afternoon produced 1,451. Six hours after the change
against thirty-four before is not a comparison, it is two different workloads. The number worth
keeping from this is the magnitude, not the direction: a few hundred spans an hour, in both states.

## What this means for the collector

- `service.name` **must** be set to exactly `claude-code`. The collector counts an unlisted name
  and drops it, so a missing or misspelled name would look exactly like Claude Code going silent.
  Confirm it on the first canary rather than assuming the resource carries it.
- At 6 to 9 spans a minute against a 600 a minute ceiling, no rate override is needed.
- Remove `otelHeadersHelper` when the endpoint changes to loopback. The collector supplies the key;
  leaving the helper means a pointless 1Password read on every session that can fail.

## How this was measured, so it can be repeated or disputed

Langfuse `GET /api/public/v2/metrics` with an hourly time dimension for the rate, and
`GET /api/public/v2/observations` with `environment=default` for the span shape. The environment
filter is applied **server-side**; I checked that before relying on it, because an earlier attempt
filtered client-side and returned nothing, having spent all twenty of its pages inside the 6.6
million `codex-worker` rows.
