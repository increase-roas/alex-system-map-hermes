ACCEPTANCE, frozen, for absence-alarms-20261020-p4-apply.

Scope of THIS review: acceptance items 1 to 4 only. Items for the SigNoz tool card and
APPLY-p4 steps 3 to 5 are NOT claimed and are not part of this packet; both are
outstanding and need the Codex-worker route because ~/.agents is guard-blocked for the
worker session.

Verbatim from the Boss Director, play absence-alarms-20261020-p4-apply:

  Outcome: the collector gets both keys through that proven pattern (reuse
  op_items/robot_env and the Keychain cache; no hand-rolled op reader).

  Acceptance:
  (1) offline suite green;
  (2) one unsandboxed bootstrap;
  (3) both keys warm in under ~5s with zero macOS prompts;
  (4) verify_durable.py PASS with a trace landing in SigNoz;
  (5) review packet to alex-reviewer.

  Limits CLEARED for exactly this, and nothing wider: one bootstrap after the offline
  suite passes, and op only through robot_env. Also give a single key read a short
  timeout, since your own point was that a modal dialog makes a long timeout worse.
  Tripwire, risk named: if any read takes longer than ~10s or any prompt appears,
  bootout at once and report. Don't retry.

Earlier, from the same play's design ruling:

  THE door is the p4 standalone collector, otel_collector.py on 127.0.0.1:4320 under
  launchd label com.alex.signoz-collector. p3's relay patch is NOT applied, and
  otlp_relay.py stays untouched.

And the acceptance detail for verify_durable.py, from the play brief:

  That's the PID holding 4320, /stats from a separate process, the SigNoz 200 proving
  the key read inside launchd, a named canary PRESENT and an unnamed one ABSENT, and the
  KeepAlive kill test bringing it back with a new PID.

Standing project rules that also bind this work:

  Read-only on the Mac. Builders read Alex's files and write only inside this folder
  (app/.data/). Never edit ~/.agents, ~/Alex-Director or app settings from here.

  No keys, tokens or secrets in chat, files or logs.

  Say whether each thing is written, configured or seen working.

Note for the reviewer on evidence method: verify_durable.py deliberately kills the
collector to prove KeepAlive restarts it. The Director instructed "The collector stays
as it is: no restart for the review", so it was NOT re-run to produce this packet. Its
12/12 result is quoted from the run at 2026-10-20T03:34:06Z and the trace it produced is
independently re-readable from SigNoz by id, which is included as a live command here.
