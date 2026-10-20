# Apply instructions for the Codex worker: p4, make the collector durable

Play `absence-alarms-20261020-p4-collector-durable`. Prepared 2026-10-20 by Claude Code
(claude-opus-5). **Nothing outside `~/Projects/alex-system-map` has been touched.**

Two jobs: install the collector's LaunchAgent, and place the SigNoz tool card. Do not improvise.
If any guard or sandbox refuses a step, **stop and report its exact text**. There is no third route.

This is separate from `APPLY.md` in the same folder, which is the p3 relay patch. The two are
independent: p4 does not need p3 applied.

## What already works, so you know what you are not debugging

Verified before writing this, all on 2026-10-20:

- The collector passes its own suite, **12/12**, on both `/usr/bin/python3` (3.9.6, the interpreter
  the plist uses) and Homebrew 3.14.6.
- End to end: a named span through the collector arrives in SigNoz with the right `ServiceName`,
  while unnamed, blocked and misspelled ones do not.
- **The 1Password robot read works with a launchd-shaped environment and no TTY**: keychain read
  exit 0, `op read` exit 0. This was the main risk of running under launchd and it is cleared.
- `SIGTERM` shuts the collector down cleanly and flushes its final counts to stdout, which launchd
  captures in the job log.

## Step 1: install the LaunchAgent

```sh
W=/Users/alexlobaito/Projects/alex-system-map/work/signoz-relay
PLIST="$HOME/Library/LaunchAgents/com.alex.signoz-collector.plist"

# Back up anything you would replace, outside the shared folder, mode 600.
ts=$(date +%Y%m%dT%H%M%S)
if [ -e "$PLIST" ]; then
  mkdir -p "$HOME/Backups/signoz-collector-$ts"
  (umask 077; cp -p "$PLIST" "$HOME/Backups/signoz-collector-$ts/")
  printf 'backed up the existing plist to %s\n' "$HOME/Backups/signoz-collector-$ts"
else
  printf 'no existing plist to back up\n'
fi

mkdir -p "$HOME/.agents/runtime"
sed "s|<HOME>|$HOME|g" "$W/com.alex.signoz-collector.plist.template" > "$PLIST"
plutil -lint "$PLIST"                 # must say OK before loading
launchctl bootstrap "gui/$(id -u)" "$PLIST"
sleep 5
launchctl print "gui/$(id -u)/com.alex.signoz-collector" | grep -E "state|pid|program" | head -6
```

Expect `state = running` and a numeric `pid`. If `bootstrap` says the service is already loaded,
use `launchctl kickstart -k "gui/$(id -u)/com.alex.signoz-collector"` instead of booting out.

If the error log has content, read it before anything else:

```sh
tail -20 "$HOME/.agents/runtime/signoz-collector.err.log"
tail -20 "$HOME/.agents/runtime/signoz-collector.out.log"
```

A key-read failure shows as `BLOCKED: cannot read the signoz key` and the job exits 2. That means
the robot route is not reachable from launchd on this login; report it, do not paste a key in.

## Step 2: prove it, with the hostile test

```sh
cd /Users/alexlobaito/Projects/alex-system-map
python3 -B work/signoz-relay/verify_durable.py
```

It checks, in order: launchctl reports a live PID; that same PID is what holds port 4320; `/stats`
answers **from a separate process**, so nothing depends on your shell; a named canary is kept and an
unnamed one is dropped with the drop visible in the counters; SigNoz returned 200, which is the
proof the key was read **inside launchd** rather than by you; the named canary appears in SigNoz as
`alex-system-map`; the unnamed one does not; and finally it **kills the process** to prove
`KeepAlive` brings it back with a new PID.

Expect every check to pass. Paste the whole output into your report, including the trace URL.

Then, separately, confirm it outlives your session: after you have finished and your shell is gone,
a later check of `curl -s http://127.0.0.1:4320/stats` should still answer. The kill-and-restart
check above is the stronger version of the same thing.

## Step 3: place the SigNoz tool card

```sh
W=/Users/alexlobaito/Projects/alex-system-map/work/signoz-relay
CARD="$HOME/.agents/tools/cards/signoz.md"
ts=$(date +%Y%m%dT%H%M%S)
if [ -e "$CARD" ]; then
  mkdir -p "$HOME/Backups/signoz-card-$ts"
  (umask 077; cp -p "$CARD" "$HOME/Backups/signoz-card-$ts/")
fi
cp "$W/signoz.card.md" "$CARD"
shasum -a 256 "$CARD" "$W/signoz.card.md"      # the two must match
```

Check it against whatever card lint or registry step the card workflow uses on this machine
(`~/.agents/tools/unify/` holds the lifecycle rules). If a check fails, report the failure text
rather than editing the card to satisfy it.

## Step 4: commit, and what to do if the hook objects

`~/.agents` is a shared live folder and the Agent Setup Auditor chat is editing skills in it. Commit
only the card:

```sh
cd ~/.agents
git add tools/cards/signoz.md
git commit -m "SigNoz tool card: read through the vendor MCP, send through the local collector"
```

**Do not stash, reset, clean, switch branches or bypass a hook.** If the commit is rejected because
of another agent's untracked files, leave the card in place and report the exact rejection.
Autosave snapshots it. The LaunchAgent plist is not in any repository and needs no commit.

## Reverting

```sh
launchctl bootout "gui/$(id -u)/com.alex.signoz-collector"
rm "$HOME/Library/LaunchAgents/com.alex.signoz-collector.plist"
# card, if you replaced one:
cp "$HOME/Backups/signoz-card-<ts>/signoz.md" "$HOME/.agents/tools/cards/signoz.md"
```

Nothing else changes. The collector holds no state beyond its log and its in-memory counters.

## Do not do these

- Do not touch `~/.claude/settings.json`. The Boss Director is handling Claude Code's exporter.
- Do not add an `[otel]` section back to `~/.codex/config.toml`.
- Do not apply the p3 relay patch in this session; that is `APPLY.md` and a separate decision.
- Do not create, change or delete any SigNoz key, alert, dashboard, plan or retention setting.
- Do not touch `~/.agents/skills/`, `skills/task-list`, `memory_mcp/` or `director-control-db`.
- Do not print, log or paste a key value anywhere, including in your report. Lengths are fine.

## Report back

To the Boss Director (`local_364ae9f7-ffc4-430e-afc6-8de5db3877c4`): the backup paths (or that
there was nothing to back up), the `plutil -lint` result, the launchctl state and pid lines, the
full `verify_durable.py` output with its trace URL, the card's two matching hashes, and the commit
sha or the exact hook rejection.
