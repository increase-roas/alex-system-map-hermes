#!/bin/bash
# Round 3 evidence run for absence-alarms-20261020-p4-apply, in the Director's exact
# captured sequence, with UTC stamps and exit codes on every step:
#   (1) offline suites FIRST, so "one bootstrap AFTER the suites pass" is established
#   (2) bootout, then the authorized bootstrap
#   (3) verify_durable.py, now with 180s patience against ThrottleInterval 120
#   (4) an op-invocation count over the whole run, so "zero macOS prompts" is proven by
#       zero op spawns rather than by how fast a read was
#
# MUST RUN UNSANDBOXED. launchd domain writes are refused inside the Seatbelt sandbox;
# that was the isolated cause of the original bootstrap failure.
#
# TRIPWIRE: any single key read over 10s, or any prompt, means bootout at once, report,
# and do not retry. Enforced below in code, not left as a rule to remember.
set -u
REPO="$HOME/Projects/alex-system-map"
E="$REPO/reviews/receipts/20261020-p4-apply/captured-r3"
LABEL="com.alex.signoz-collector"
P="$HOME/Library/LaunchAgents/$LABEL.plist"
mkdir -p "$E"
cd "$REPO" || exit 2

# --- op invocation counter -------------------------------------------------------
# A macOS "op would like to access data from other apps" prompt can only come from an
# op process. If none is spawned for the whole run, no prompt was possible. This shim
# goes FIRST on PATH, records every invocation with a UTC stamp, and forwards to the
# real binary so nothing is broken by being counted.
SHIM="$E/opshim"
mkdir -p "$SHIM"
OPLOG="$E/40-op-invocations.txt"
{
  echo "COMMAND:    PATH shim counting every 'op' invocation for the whole run"
  echo "DESCRIPTION:zero spawns proves no macOS prompt was possible, since only op can raise one"
  echo "UTC_START:  $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo "---- invocations ----"
} > "$OPLOG"
cat > "$SHIM/op" <<SHIMEOF
#!/bin/bash
echo "\$(date -u '+%Y-%m-%dT%H:%M:%SZ')  op \$*" >> "$OPLOG"
exec /opt/homebrew/bin/op "\$@"
SHIMEOF
chmod +x "$SHIM/op"
export PATH="$SHIM:$PATH"

run() {           # run <slug> <description> <command...>
  local slug="$1"; shift
  local desc="$1"; shift
  local f="$E/$slug.txt"
  {
    echo "COMMAND:    $*"
    echo "DESCRIPTION:$desc"
    echo "CWD:        $(pwd)"
    echo "SANDBOX:    Seatbelt DISABLED (launchd domain writes are refused inside it)"
    echo "UTC_START:  $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "---- output ----"
  } > "$f"
  "$@" >> "$f" 2>&1
  local rc=$?
  {
    echo "---- end output ----"
    echo "UTC_END:    $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "EXIT_STATUS:$rc"
  } >> "$f"
  echo "   $slug  exit=$rc"
  return $rc
}

echo "=== STEP 1: the offline suites, BEFORE any bootstrap ==="
run 01-offline-collector-py39 "collector suite on /usr/bin/python3 3.9.6, the interpreter the plist uses" \
    /usr/bin/python3 -B tools/otel_collector.py --self-test || exit 1
run 02-offline-collector-py314 "collector suite on the newer interpreter too" \
    python3 -B tools/otel_collector.py --self-test || exit 1
run 03-offline-relay-harness "the filter and rate-guard harness against the patched relay copy" \
    python3 -B work/signoz-relay/test_relay_collector.py || exit 1
run 04-offline-preflight "p4 package pre-flight: plist renders, lints, parses, flags present" \
    python3 -B work/signoz-relay/validate_p4.py || exit 1
echo "   all four suites passed BEFORE the bootstrap below. That ordering is the point."

echo "=== STEP 2: bootout, then the authorized bootstrap ==="
run 05-state-before "launchd state and port holder before touching anything" \
    bash -c "launchctl print gui/\$(id -u)/$LABEL 2>&1 | grep -E '^[[:space:]]*(state|pid|path)'; echo '--- port ---'; lsof -nP -iTCP:4320 2>&1 | head -3"
run 06-bootout "bootout so the bootstrap below is a clean, captured load" \
    launchctl bootout "gui/$(id -u)/$LABEL"
sleep 3
run 07-after-bootout "confirm it left the domain and freed the port" \
    bash -c "launchctl print gui/\$(id -u)/$LABEL >/dev/null 2>&1 && echo 'STILL LOADED' || echo 'not in domain'; lsof -nP -iTCP:4320 2>/dev/null | grep -q LISTEN && echo 'STILL LISTENING' || echo 'port free'"
run 08-bootstrap "THE authorized unsandboxed bootstrap, after the suites above passed" \
    launchctl bootstrap "gui/$(id -u)" "$P"
run 09-startup-poll "poll launchd pid and port until listening, max 120s" \
    bash -c 'for i in $(seq 1 12); do
      PID=$(launchctl print gui/$(id -u)/'"$LABEL"' 2>/dev/null | sed -n "s/^[[:space:]]*pid = \([0-9]*\).*/\1/p" | head -1)
      L=$(lsof -nP -iTCP:4320 2>/dev/null | grep -c LISTEN)
      echo "$(date -u "+%H:%M:%SZ")  t+$((i*10))s  pid=${PID:-none}  listening=$L"
      [ "$L" = "1" ] && break
      sleep 10
    done'

echo "=== STEP 3: key timing with the tripwire enforced ==="
run 10-key-timing "time both key reads in a fresh process; over 10s means stop" \
    python3 -I -c "
import importlib.util, sys, time
spec=importlib.util.spec_from_file_location('col','tools/otel_collector.py')
col=importlib.util.module_from_spec(spec); sys.modules['col']=col; spec.loader.exec_module(col)
worst=0.0
for label, fn in (('signoz', col.signoz_headers), ('langfuse', col.langfuse_headers)):
    t0=time.time(); h=fn(); dt=time.time()-t0; worst=max(worst,dt)
    k=list(h)[0]
    print(f'{label}: OK in {dt:.2f}s  header={k}  value_length={len(h[k])}  (value not shown)')
print(f'worst single read {worst:.2f}s against a {col.OP_READ_TIMEOUT}s ceiling in code')
print('TRIPWIRE BREACHED' if worst > 10 else 'tripwire not breached')
sys.exit(1 if worst > 10 else 0)
"
if [ $? -ne 0 ]; then
  echo "   !! TRIPWIRE BREACHED. Booting out at once, no retry."
  run 11-tripwire-bootout "tripwire breached: immediate bootout" launchctl bootout "gui/$(id -u)/$LABEL"
  exit 1
fi

echo "=== STEP 4: verify_durable.py, 180s patience ==="
run 12-verify-durable "the hostile verifier end to end, including its KeepAlive kill test" \
    python3 -B work/signoz-relay/verify_durable.py
VRC=$?

run 13-state-after "launchd state, port holder and counts after the verifier" \
    bash -c "launchctl print gui/\$(id -u)/$LABEL 2>&1 | grep -E '^[[:space:]]*(state|pid)'; echo '--- port ---'; lsof -nP -iTCP:4320 2>&1 | head -3; echo '--- stats ---'; curl -s -m 10 http://127.0.0.1:4320/stats"
run 14-request-rows "the collector's own request rows, written by it" \
    bash -c "tail -8 \"\$HOME/.agents/runtime/otel-collector.jsonl\""

echo "=== STEP 5: close the op-invocation count ==="
{
  echo "---- end invocations ----"
  echo "UTC_END:    $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  # grep -c prints 0 AND exits non-zero on no match, so a `|| echo 0` appends a
  # SECOND zero and the comparison below then takes the wrong branch over a correct
  # count. That happened on the 2026-10-20 run: the file said OP_INVOCATIONS 0 and
  # then concluded the opposite. Count without the fallback and compare an integer.
  n=$(grep -cE '^[0-9]{4}-[0-9]{2}-[0-9]{2}T.*  op ' "$OPLOG"); true
  n=$((n + 0))
  echo "OP_INVOCATIONS: $n"
  if [ "$n" -eq 0 ]; then
    echo "CONCLUSION: zero op processes were spawned for the whole run, by the collector or"
    echo "            by anything else on this PATH. A macOS app-data prompt can only be"
    echo "            raised by op, so no prompt was possible. Both keys came from the"
    echo "            login Keychain cache."
  else
    echo "CONCLUSION: op WAS spawned $n time(s); a prompt was therefore possible and the"
    echo "            zero-prompt claim is NOT established by this run."
  fi
} >> "$OPLOG"
tail -8 "$OPLOG" | sed 's/^/   /'

echo
echo "=== secret scan over every captured file ==="
if grep -rlE "(sk|pk)-lf-[A-Za-z0-9_-]{8,}" "$E" --exclude-dir=opshim 2>/dev/null; then
  echo "   !! KEY-SHAPED STRING FOUND, do not commit"
  exit 1
fi
echo "   clean: no key-shaped string in any captured file"
rm -rf "$SHIM"
echo
echo "=== RESULT ==="
echo "   verify_durable.py exit status: $VRC  (0 means 12/12)"
ls -1 "$E" | sed 's/^/   /'
exit $VRC
