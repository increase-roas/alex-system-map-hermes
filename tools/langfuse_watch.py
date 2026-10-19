#!/usr/bin/env python3
"""Shout when one of Alex's systems stops reporting, or when the Langfuse bill runs away.

This is the thing Langfuse cannot do for itself. Its own alerts fire when something
HAPPENS: a run failed, a run was slow. Silence is not an event, so nothing fires when
a system dies. That is why four systems could fail in one week without a sound.

Run it:
    python3 -B tools/langfuse_watch.py

It exits 0 when everything is fine and 1 when something needs attention, so a
scheduled job can act on it. Every line it prints is meant to be read by Alex, not
by an engineer.

Two things it watches:

1. SILENCE. Each sender gets its own patience, because they are not alike. Claude Code
   goes quiet overnight; Javar might legitimately not run for a day. A single global
   "silent for an hour" rule would cry wolf all night and get muted inside a week.

2. SPEND. Langfuse Core is $29/month with 100,000 units included and $8 per additional
   100,000 (langfuse.com/pricing). Units are traces plus observations plus scores. This
   projects the month from the units used so far and shouts before the bill lands, which
   is what Langfuse's own $200 alert failed to do on 2026-10-16.

Read-only against Langfuse. Credentials come from 1Password at run time through
langfuse_coverage.auth_header. No key is ever printed. It changes no Langfuse setting
and spends nothing.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from langfuse_coverage import (  # noqa: E402  (local module, path set above)
    Blocked,
    SENDERS,
    auth_header,
    last_seen,
)

# Langfuse Core, read from langfuse.com/pricing on 2026-10-19 by the Director.
# Every tier above Core includes the same 100,000 units, so upgrading buys history and
# rate limits, never volume. The only lever is sending less.
INCLUDED_UNITS = 100_000
USD_PER_100K = 8.0
SUBSCRIPTION_USD = 29.0

# How long each sender may stay quiet before it counts as a problem. Hours.
# These are a starting point, set from the measured 7-day behaviour on 2026-10-19, not
# from Alex. He should correct any that nag him; a threshold that cries wolf is worse
# than none, because it teaches him to ignore the alarm.
PATIENCE_HOURS = {
    'default': 24,        # Claude Code. Quiet overnight is normal.
    'codex-worker': 0,    # Off on purpose. See CODEX_OFF below.
    'javar': 48,          # Ran on 4 of the last 7 days.
    'javar-lab': 48,      # Was silent 5 days when measured. Expected to alarm.
}

# A silence nobody wrote down is the failure this whole exercise exists to remove:
# a sender that was switched off looks exactly like a sender that died. So any
# environment set to patience 0 must say here why, when, and on whose decision.
# The watcher prints this every run, so the reason travels with the silence.
DELIBERATE_SILENCE = {
    'codex-worker': (
        'Codex app tracing was switched off on 2026-10-19 on Alex\'s decision, in his words '
        '"turn off tracing for the Codex app inside ChatGPT", to stop a spend measured at '
        '$159 a day, about $4,900 a month: 6,829,135 units and $480.04 accrued in the first '
        '3.02 days of the billing period. (An earlier $670 a day figure was withdrawn: it came '
        'from treating the billing counter, which refreshes hourly, as a live meter.) '
        'Its spans carried no per-run session id and 91% were filesystem '
        'calls and streaming chunks, and Codex 0.162 has no span filter or sampler, so the '
        'only lever was off. Codex CLI tracing is unaffected. This silence is a decision, '
        'not a failure. To reverse it, uncomment the [otel] block in ~/.codex/config.toml '
        'and restart the ChatGPT app.'
    ),
}

# Where the last result is kept, so "it went quiet just now" can be told from
# "it has been quiet for days and you already know".
STATE = Path(__file__).resolve().parent.parent / 'app' / '.data' / 'langfuse-watch-state.json'


def read_state() -> dict:
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def write_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(state, indent=2) + '\n')
    tmp.replace(STATE)


def project_spend(total_units: int, period_start: dt.date, period_days: int,
                  now: dt.datetime) -> dict:
    """What this month lands at if the current rate holds."""
    elapsed = max((now.date() - period_start).days + (now.hour / 24), 0.25)
    rate = total_units / elapsed
    projected = rate * period_days
    billable_now = max(total_units - INCLUDED_UNITS, 0)
    billable_proj = max(projected - INCLUDED_UNITS, 0)
    return {
        'units_so_far': int(total_units),
        'units_per_day': int(rate),
        'projected_units': int(projected),
        'usd_so_far': round(billable_now / 100_000 * USD_PER_100K + SUBSCRIPTION_USD, 2),
        'projected_usd': round(billable_proj / 100_000 * USD_PER_100K + SUBSCRIPTION_USD, 2),
        'elapsed_days': round(elapsed, 2),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--spend-limit', type=float, default=300.0,
                        help='shout if the month projects above this many dollars (default 300)')
    parser.add_argument('--period-start', default='2026-10-16',
                        help='first day of the Langfuse billing period (default 2026-10-16)')
    parser.add_argument('--period-days', type=int, default=31)
    parser.add_argument('--quiet-ok', action='store_true',
                        help='report silence but do not treat it as a failure')
    args = parser.parse_args(argv)

    now = dt.datetime.now(dt.timezone.utc)
    try:
        auth = auth_header('agents')
    except Blocked as err:
        # A credential failure is itself an alarm: it means nobody is watching.
        print(f'ALARM: the watcher cannot reach Langfuse, so nothing is being watched. {err}')
        return 1

    alarms: list[str] = []
    notes: list[str] = []
    total_units = 0
    rows = []

    for name, kind, environment in SENDERS:
        if not environment:
            continue
        patience = PATIENCE_HOURS.get(environment)
        try:
            seen = last_seen(auth, environment, days=30)
        except Blocked as err:
            alarms.append(f'{name}: could not be checked ({err})')
            continue
        total_units += seen['observations']
        last_day = seen['last_day']
        rows.append({'name': name, 'environment': environment, **seen})
        if patience == 0:
            reason = DELIBERATE_SILENCE.get(environment)
            if reason:
                notes.append(f'{name}: not watched on purpose. {reason}')
            else:
                # Patience 0 with no recorded reason is itself a problem: it means
                # someone muted a sender and left no note saying why.
                alarms.append(
                    f'{name} is set to be ignored but no reason was recorded for it. '
                    f'Add one to DELIBERATE_SILENCE in tools/langfuse_watch.py, or it will '
                    f'look fine forever whether it is off on purpose or broken.')
            continue
        if not last_day:
            if patience is not None:
                alarms.append(f'{name} has never reported. Nothing is set up to send for it.')
            continue
        # last_day is a date bucket, so age is measured generously: a sender seen
        # "today" is 0 hours old. This under-reports age by up to a day and will not
        # produce a false alarm.
        age_h = (now.date() - dt.date.fromisoformat(last_day[:10])).days * 24
        if patience is not None and age_h > patience:
            days = age_h // 24
            alarms.append(
                f'{name} has said nothing for {days} day{"s" if days != 1 else ""} '
                f'(last heard {last_day}). It is either idle or broken, and nothing else '
                f'will tell you which.')

    period_start = dt.date.fromisoformat(args.period_start)
    spend = project_spend(total_units, period_start, args.period_days, now)
    if spend['projected_usd'] > args.spend_limit:
        alarms.append(
            f'Langfuse is on track to cost about ${spend["projected_usd"]:,.0f} this month '
            f'(limit set here: ${args.spend_limit:,.0f}). {spend["units_per_day"]:,} units a day. '
            f'About ${spend["usd_so_far"]:,.0f} accrued so far.')

    print(f'Langfuse watch, {now:%Y-%m-%d %H:%M} UTC')
    print()
    for row in rows:
        print(f'  {row["name"]:16} last heard {row["last_day"] or "never":12} '
              f'{row["observations"]:>10,} units in 30 days')
    print()
    print(f'  Spend: {spend["units_so_far"]:,} units in {spend["elapsed_days"]} days, '
          f'about ${spend["usd_so_far"]:,.0f} so far, '
          f'projecting ${spend["projected_usd"]:,.0f} for the month.')
    print()

    for note in notes:
        print(f'  note: {note}')
    if notes:
        print()

    state = read_state()
    previous = set(state.get('alarms', []))
    if alarms:
        fresh = [a for a in alarms if a not in previous]
        print('SOMETHING NEEDS YOU:')
        for alarm in alarms:
            flag = 'NEW ' if alarm in fresh else '    '
            print(f'  {flag}{alarm}')
    else:
        print('All watched systems reported inside their normal gap, and spend is under the limit.')

    write_state({'checked_at': now.isoformat(), 'alarms': alarms,
                 'spend': spend, 'senders': rows})
    if alarms and not args.quiet_ok:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
