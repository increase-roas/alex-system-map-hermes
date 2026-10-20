ACCEPTANCE, frozen, for absence-alarms-20261020-p4-refresh.

The high-severity finding from the R3 review of absence-alarms-20261020-p4-apply:

  SEVERITY: high IN_SCOPE: no | Sustained operation beyond the four frozen checks: the
  in-memory keys expire after 3,600 seconds, the warmer exits after initial success, and
  forwarding only calls peek. After expiry, both upstreams become unavailable without an
  automatic refresh. Add periodic refresh and an expiry-path check in a separately
  scoped repair.

Verbatim from the Boss Director, authorising this repair:

  One change: keys refresh on a schedule before KEY_TTL instead of the warmer exiting,
  plus an offline expiry-path test that runs past the TTL and proves forwarding
  continues. Acceptance: (1) that test green, with the suites captured first; (2) one
  captured bootout+bootstrap (cleared); (3) a live canary forwards signoz:200 and the
  refresh thread is alive; (4) codex_review.py cross-family PASS on that acceptance.
  Tripwire and op-only-via-robot_env still hold.

So, the four criteria:

(1) The offline expiry-path test is green, and the suites were captured BEFORE the
    bootstrap. The test must run past the TTL and prove a header is still available,
    with no network and no 1Password call.
(2) One captured bootout and bootstrap, with command, context, UTC time and exit status.
(3) A live canary forwards with signoz:200, and the refresh thread is alive.
(4) This review.

Properties that must survive the change, from the component's own design:

  The request path uses peek() only and NEVER blocks on a credential. A failed read goes
  through KeyCache's exponential backoff, doubling from KEY_BACKOFF_BASE to
  KEY_BACKOFF_MAX, so 1Password is never hammered. The process NEVER exits because a key
  read failed. SIGTERM shuts down cleanly. The suite passes on /usr/bin/python3 3.9.6,
  the interpreter the launchd job uses, as well as on 3.14.6.

Standing project rules that also bind this work:

  Read-only on the Mac. Never edit ~/.agents, ~/Alex-Director or app settings from here.
  No keys, tokens or secrets in chat, files or logs.
  Say whether each thing is written, configured or seen working.

Honest limit on criterion 1, declared rather than discovered: the refresh across the TTL
is proven with an injected clock and a stubbed reader, NOT by a real hour-long run. The
live job has been up for minutes. A reviewer should treat "refreshes across the TTL" as
proven in logic and unproven in wall-clock, and the claim here is deliberately the
former.
