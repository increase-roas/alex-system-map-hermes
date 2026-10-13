#!/usr/bin/env python3
"""Acceptance for the Connector logins view exporter (tools/composio_logins_export.py).

Offline: a fake curl stands in for Composio, so no network call and no real key is used. Checks pagination,
status passes, dedupe, the safe-field whitelist, secrets kept off argv and out of the snapshot, card mapping,
and the red/fix flags. Writes reports/connector-logins-acceptance.json; exit 0 only when every check passed.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import composio_logins_export as exp  # noqa: E402

REPORT = ROOT / 'reports' / 'connector-logins-acceptance.json'
FAKE_KEY = 'ak_FAKE-acceptance-key-not-real-0000'
FAKE_ORG = 'org_FAKE-acceptance'
TOKEN = 'FAKE-ACCESS-TOKEN-must-never-appear'


def item(i: str, slug: str, status: str, **extra) -> dict:
    return {'id': i, 'toolkit': {'slug': slug}, 'status': status, 'word_id': f'{slug}_word-{i}', 'alias': None,
            'updated_at': '2026-10-13T12:00:00Z', 'status_reason': None, 'user_id': 'u',
            'data': {'access_token': TOKEN, 'refresh_token': TOKEN}, 'state': {'val': {'api_key': TOKEN}}, **extra}


# Unfiltered pass: two pages joined by a cursor. Status passes return the dead ones again (dedupe) plus one only they see.
PAGES = {
    (None, None): {'items': [item('ca_1', 'gmail', 'ACTIVE'), item('ca_2', 'gmail', 'EXPIRED')], 'next_cursor': 'c2'},
    (None, 'c2'): {'items': [item('ca_3', 'custom_ga4_admin', 'ACTIVE', alias='ga4 main')], 'next_cursor': None},
    ('EXPIRED', None): {'items': [item('ca_2', 'gmail', 'EXPIRED')], 'next_cursor': None},
    ('FAILED', None): {'items': [item('ca_4', 'unknowntool', 'FAILED', status_reason='refresh failed')], 'next_cursor': None},
}


def main() -> int:
    calls: list[dict] = []

    def fake_run(argv, input=None, **kw):
        from urllib.parse import parse_qs, urlparse
        url = next(l.split('=', 1)[1].strip().strip('"') for l in input.splitlines() if l.startswith('url'))
        q = parse_qs(urlparse(url).query)
        calls.append({'argv': list(argv), 'stdin': input, 'host': urlparse(url).hostname, 'q': q})
        page = PAGES[(q.get('statuses', [None])[0], q.get('cursor', [None])[0])]
        return SimpleNamespace(returncode=0, stdout=json.dumps(page) + '\n200', stderr='')

    creds = {'api_key': FAKE_KEY, 'org_id': FAKE_ORG}
    items = exp.fetch_all(creds, run=fake_run)
    index, card_for = exp.load_card_mapper()
    snap = exp.build_snapshot(items, index(), card_for, now='2026-10-13T12:00:00+00:00')
    text = json.dumps(snap)
    rows = {a['account_id']: a for g in snap['groups'] for a in g['accounts']}

    # A non-200 must fail loudly without echoing the body.
    def http_401(argv, input=None, **kw):
        return SimpleNamespace(returncode=0, stdout='{"error":"' + FAKE_KEY + '"}\n401', stderr=FAKE_KEY)
    try:
        exp.fetch_page(exp.build_url(None, None), creds, run=http_401)
        err = ''
    except RuntimeError as e:
        err = str(e)

    checks = [
        ('follows next_cursor', any(c['q'].get('cursor') == ['c2'] for c in calls)),
        ('status passes for EXPIRED and FAILED', {c['q'].get('statuses', [None])[0] for c in calls} == {None, 'EXPIRED', 'FAILED'}),
        ('dedupes by account id', len(items) == 4 and snap['summary']['total'] == 4),
        ('only allowlisted host', {c['host'] for c in calls} == {exp.ALLOWED_HOST}),
        ('project header sent', all(f'x-project-id: {exp.PROJECT_ID}' in c['stdin'] for c in calls)),
        ('curl uses --compressed and -K -', all('--compressed' in c['argv'] and c['argv'][-2:] == ['-K', '-'] for c in calls)),
        ('key never on argv', all(FAKE_KEY not in ' '.join(c['argv']) and FAKE_ORG not in ' '.join(c['argv']) for c in calls)),
        ('key only on stdin', all(FAKE_KEY in c['stdin'] for c in calls)),
        ('no key, org or token in snapshot', FAKE_KEY not in text and FAKE_ORG not in text and TOKEN not in text),
        ('whitelisted fields only', all(set(r) == set(exp.SAFE_FIELDS) | {'card', 'ok', 'fix'} for r in rows.values())),
        ('EXPIRED is red with fix', rows['ca_2']['ok'] is False and rows['ca_2']['fix'] == exp.FIX),
        ('FAILED is red with fix and reason', rows['ca_4']['ok'] is False and rows['ca_4']['status_reason'] == 'refresh failed'),
        ('ACTIVE has no fix', rows['ca_1']['ok'] is True and rows['ca_1']['fix'] is None),
        ('gmail maps to google-workspace card', rows['ca_1']['card'] == 'google-workspace'),
        ('custom toolkit maps to its card', rows['ca_3']['card'] == 'ga4' and rows['ca_3']['alias'] == 'ga4 main'),
        ('unknown toolkit has no card', rows['ca_4']['card'] is None),
        ('summary counts not ACTIVE', snap['summary']['not_active'] == 2 and snap['summary']['by_status'] == {'ACTIVE': 2, 'EXPIRED': 1, 'FAILED': 1}),
        ('groups with dead logins first', [g['toolkit'] for g in snap['groups']][:2] == ['gmail', 'unknowntool']),
        ('HTTP error raised without body or key', 'HTTP 401' in err and FAKE_KEY not in err),
    ]
    # Live snapshot, when present, must also be free of the real key (read in memory only, never printed).
    live = ROOT / 'app' / '.data' / 'connector-logins.json'
    if live.exists():
        real = json.loads((Path.home() / '.composio' / 'user_data.json').read_text())
        body = live.read_text()
        checks.append(('live snapshot has no real key or org id', real['api_key'] not in body and real['org_id'] not in body
                       and 'access_token' not in body))
        del real

    results = [{'name': n, 'passed': bool(p), 'detail': ''} for n, p in checks]
    report = {'check': 'connector-logins', 'ran_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
              'passed': all(r['passed'] for r in results), 'results': results}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
