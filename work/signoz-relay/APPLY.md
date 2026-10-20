# Apply instructions for the Codex worker

Play `absence-alarms-20261020-p3-relay-collector`. Prepared 2026-10-20 by Claude Code
(claude-opus-5). **Nothing in `~/.agents` has been touched yet.** Everything below is built and
tested in `/Users/alexlobaito/Projects/alex-system-map/work/signoz-relay/`.

You are applying two file changes that this session is not permitted to write, then proving they
work. Do not improvise. If any step is refused, stop and report the exact refusal text.

## What this does, in one line

The local relay on `127.0.0.1:4319` becomes the one collector for this MacBook: it reads the SigNoz
key itself, drops any span with no `service.name`, refuses the ChatGPT app's `codex-worker`,
rate-guards each service separately, and sends to SigNoz while mirroring named spans to Langfuse
for one side-by-side day.

## Preconditions: confirm before you change anything

```sh
cd /Users/alexlobaito/Projects/alex-system-map/work/signoz-relay
shasum -a 256 ~/.agents/tools/connectors/codex_otel/otlp_relay.py
# must be 90e6dd0a0944003cf05f47ad2c6bd09627fa47eab4548d043d02644723768417
shasum -a 256 ~/.agents/tools/connectors/codex_otel/codex_traced.py
# must be 8eb092cceab349fc5ac5908d9ca34c4f5d03d5dd83f0e6464936391e37098d68
```

**If either hash differs, STOP.** The patches are anchored to those exact files; another agent has
edited them since and the anchors may no longer mean what they meant. Report and do not apply.

Then re-run the tests yourself rather than trusting this document:

```sh
cd /Users/alexlobaito/Projects/alex-system-map
python3 -B work/signoz-relay/make_patch.py                 # rebuilds the patched copy, 20 anchors
python3 -B work/signoz-relay/test_relay_collector.py       # expect 33/33 passed
python3 -B work/signoz-relay/make_patch_codex_traced.py     # expect PATCHED compiles cleanly
```

The tests run the real patched relay on a loopback port against two fake loopback upstreams. They
reach no network, no 1Password and no Keychain: both key loaders are injected.

## Step 1: back up the originals

Back up **outside** `~/.agents` so a later `git clean` in that shared folder cannot take the backups
with it. Use mode 600.

```sh
ts=$(date +%Y%m%dT%H%M%S)
mkdir -p "$HOME/Backups/signoz-relay-$ts"
(umask 077
 cp -p ~/.agents/tools/connectors/codex_otel/otlp_relay.py   "$HOME/Backups/signoz-relay-$ts/"
 cp -p ~/.agents/tools/connectors/codex_otel/codex_traced.py "$HOME/Backups/signoz-relay-$ts/")
shasum -a 256 "$HOME/Backups/signoz-relay-$ts"/*.py
printf 'backup dir: %s\n' "$HOME/Backups/signoz-relay-$ts"
```

Record that path. Every later step quotes it.

## Step 2: apply

Copy the tested files into place. Do not hand-edit.

```sh
W=/Users/alexlobaito/Projects/alex-system-map/work/signoz-relay
cp "$W/otlp_relay.PATCHED.py"    ~/.agents/tools/connectors/codex_otel/otlp_relay.py
cp "$W/codex_traced.PATCHED.py"  ~/.agents/tools/connectors/codex_otel/codex_traced.py
```

## Step 3: byte readback

Prove what is on disk is what was tested, not what you intended to write.

```sh
shasum -a 256 ~/.agents/tools/connectors/codex_otel/otlp_relay.py \
              /Users/alexlobaito/Projects/alex-system-map/work/signoz-relay/otlp_relay.PATCHED.py
shasum -a 256 ~/.agents/tools/connectors/codex_otel/codex_traced.py \
              /Users/alexlobaito/Projects/alex-system-map/work/signoz-relay/codex_traced.PATCHED.py
python3 -m py_compile ~/.agents/tools/connectors/codex_otel/otlp_relay.py && echo "relay compiles"
python3 -m py_compile ~/.agents/tools/connectors/codex_otel/codex_traced.py && echo "wrapper compiles"
```

**Each pair must match.** If a pair differs, restore from the backup and report.

## Step 4: confirm the SigNoz key is readable, without printing it

```sh
/usr/bin/python3 -B -c "
import sys; sys.path.insert(0,'/Users/alexlobaito/.agents/tools/connectors/codex_otel')
import otlp_relay as r
h = r.fetch_signoz_key()
k = list(h)[0]
print('header name:', k, '| value length:', len(h[k]))
print('validator accepts it:', bool(r.validate_signoz_headers(h)))
"
```

Expect header name `signoz-ingestion-key` and a non-zero length. **Never print the value.**

## Step 5: restart the relay through its own launchd job

```sh
launchctl kickstart -k "gui/$(id -u)/com.alex.codex-otlp-relay"
sleep 3
launchctl print "gui/$(id -u)/com.alex.codex-otlp-relay" | grep -E "state|program|path" | head -5
lsof -nP -iTCP:4319 | head -3
tail -5 ~/.agents/runtime/codex-otlp-relay.err.log
```

Expect `state = running`, something LISTENing on 4319, and an empty error log. If the error log has
content, restore from the backup, kickstart again, and report the log lines.

## Step 6: the acceptance canary, through the relay

Named canary. It must arrive in SigNoz as `ServiceName='codex'`.

```sh
python3 -B /Users/alexlobaito/Projects/alex-system-map/work/signoz-relay/canary_through_relay.py
```

That script sends one named span (`service.name=codex`) and one unnamed span to
`127.0.0.1:4319/v1/traces`, prints both trace ids, then reads SigNoz back with the read-only key and
reports PRESENT or ABSENT for each. Expected: the named one PRESENT with `ServiceName='codex'`, the
unnamed one ABSENT.

Then show the drop counter from the relay's own log:

```sh
tail -5 ~/.agents/runtime/codex-otlp-relay.jsonl
```

Rows now carry `kept` and `dropped` count objects. Expect a row with `"dropped":{"unnamed":1}`.
**There must be no span name, attribute or key value anywhere in that file.**

## Step 7: commit, and what to do if the hook objects

`~/.agents` is a shared live folder and the Agent Setup Auditor chat is editing skills in it right
now. Commit only the two files you changed:

```sh
cd ~/.agents
git add tools/connectors/codex_otel/otlp_relay.py tools/connectors/codex_otel/codex_traced.py
git commit -m "Relay becomes the one local collector: SigNoz, named spans only, per-service rate guard"
```

**Do not stash, reset, clean, switch branches, or bypass a hook.** If the commit is rejected because
of another agent's untracked files, leave the change applied and backed up and report the exact
rejection. Autosave snapshots it.

## Reverting

```sh
cp "$HOME/Backups/signoz-relay-<ts>/otlp_relay.py"   ~/.agents/tools/connectors/codex_otel/otlp_relay.py
cp "$HOME/Backups/signoz-relay-<ts>/codex_traced.py" ~/.agents/tools/connectors/codex_otel/codex_traced.py
launchctl kickstart -k "gui/$(id -u)/com.alex.codex-otlp-relay"
```

## Do not do these

- Do not add an `[otel]` section back to `~/.codex/config.toml`. The ChatGPT app's Codex stays
  untraced by Alex's decision of 2026-10-19.
- Do not touch `~/.claude/settings.json`. The Boss Director is handling Claude Code's exporter.
- Do not touch `~/.agents/skills/`, `skills/task-list`, `memory_mcp/` or `director-control-db`.
- Do not create, change or delete any SigNoz key, alert or plan setting.
- Do not print, log or paste a key value anywhere, including in your report.

## Report back

Give the Boss Director (`local_364ae9f7-ffc4-430e-afc6-8de5db3877c4`): the backup directory path,
the four readback hashes, the relay state line, both canary trace ids with PRESENT/ABSENT, the
`dropped` counter row, and the commit sha or the exact hook rejection.
