#!/usr/bin/env python3
"""Read-only snapshot of every Composio connected account (login) for the Connector logins view.

Calls GET /api/v3/connected_accounts on backend.composio.dev (Alex's request, 2026-10-13), keeps a fixed
list of safe fields (toolkit slug, account id, alias, word id, status, updated_at, status reason) and maps
each toolkit to its tool card with card_index()/card_for() from ~/.agents/tools/guards/composio_guard.py.

Keys: read from ~/.composio/user_data.json into memory only and handed to curl on stdin (`-K -`), so they
never reach argv, disk, the snapshot or logs. The raw reply holds access tokens; it is never written.
Writes only app/.data/connector-logins.json (temp file, then os.replace). Never changes or deletes a login.
Run: python3 -B tools/composio_logins_export.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from output_screening import redact_value  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'app' / '.data' / 'connector-logins.json'
HOME = Path.home()
USER_DATA = HOME / '.composio' / 'user_data.json'
GUARD = HOME / '.agents' / 'tools' / 'guards' / 'composio_guard.py'

# Network allowlist for this file (Alex named this host and route in chat, 2026-10-13).
ALLOWED_HOST = 'backend.composio.dev'
PROJECT_ID = 'pr_JDtrNq9tUa_i'  # main project (card: ~/.agents/tools/cards/composio.md)
PATH = '/api/v3/connected_accounts'
PAGE_LIMIT = 100
MAX_PAGES = 50
# The unfiltered list is the main pass; the status passes make sure dead logins are never missed
# (the card notes some list routes return ACTIVE only).
STATUS_PASSES: tuple[str | None, ...] = (None, 'EXPIRED', 'FAILED')
OK_STATUS = 'ACTIVE'
FIX = 'reconnect, or back up to ~/Backups and delete'
SAFE_FIELDS = ('toolkit', 'account_id', 'alias', 'word_id', 'status', 'updated_at', 'status_reason')


def load_card_mapper():
    """card_index()/card_for() from Alex's guard, loaded read-only by path (never edited)."""
    spec = importlib.util.spec_from_file_location('composio_guard_readonly', GUARD)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'cannot load {GUARD}')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.card_index, mod.card_for


def curl_config(url: str, creds: dict) -> str:
    """curl -K config. Holds the keys, so it only ever goes to curl's stdin."""
    def q(v: str) -> str:
        return '"' + str(v).replace('\\', '\\\\').replace('"', '\\"') + '"'
    return '\n'.join([
        f'url = {q(url)}',
        f'header = {q("x-user-api-key: " + creds["api_key"])}',
        f'header = {q("x-org-id: " + creds["org_id"])}',
        f'header = {q("x-project-id: " + PROJECT_ID)}',
        '',
    ])


def build_url(status: str | None, cursor: str | None) -> str:
    params = {'limit': str(PAGE_LIMIT)}
    if status:
        params['statuses'] = status
    if cursor:
        params['cursor'] = cursor
    url = f'https://{ALLOWED_HOST}{PATH}?{urllib.parse.urlencode(params)}'
    if urllib.parse.urlparse(url).hostname != ALLOWED_HOST:
        raise RuntimeError('host not allowlisted')
    return url


def fetch_page(url: str, creds: dict, run=subprocess.run) -> dict:
    argv = ['curl', '--compressed', '-sS', '--max-time', '30', '--write-out', '\n%{http_code}', '-K', '-']
    proc = run(argv, input=curl_config(url, creds), capture_output=True, text=True, timeout=60)
    body, _, code = proc.stdout.rpartition('\n')
    if proc.returncode != 0:
        raise RuntimeError(f'curl exit {proc.returncode}')  # stderr withheld: it can echo config lines
    if code.strip() != '200':
        raise RuntimeError(f'Composio answered HTTP {code.strip()}')
    return json.loads(body)


def fetch_all(creds: dict, run=subprocess.run) -> list[dict]:
    """Every login across the passes, deduped by id, following next_cursor until it runs out."""
    seen: dict[str, dict] = {}
    for status in STATUS_PASSES:
        cursor = None
        for _ in range(MAX_PAGES):
            page = fetch_page(build_url(status, cursor), creds, run)
            for item in page.get('items') or []:
                if isinstance(item, dict) and item.get('id'):
                    seen[str(item['id'])] = item
            cursor = page.get('next_cursor') or None
            if not cursor or not page.get('items'):
                break
        else:
            raise RuntimeError(f'more than {MAX_PAGES} pages for status {status or "all"}')
    return list(seen.values())


def safe_row(item: dict, index: dict, card_for) -> dict:
    """Whitelist only; tokens, auth data and state never leave this function."""
    slug = str(((item.get('toolkit') or {}).get('slug')) or 'unknown')
    status = str(item.get('status') or 'UNKNOWN').upper()
    reason = item.get('status_reason')
    row = {
        'toolkit': slug,
        'account_id': str(item.get('id') or ''),
        'alias': item.get('alias') if isinstance(item.get('alias'), str) else None,
        'word_id': item.get('word_id') if isinstance(item.get('word_id'), str) else None,
        'status': status,
        'updated_at': item.get('updated_at') if isinstance(item.get('updated_at'), str) else None,
        'status_reason': str(reason)[:200] if reason else None,
    }
    assert tuple(row) == SAFE_FIELDS
    row['card'] = card_for(slug, index)
    row['ok'] = status == OK_STATUS
    row['fix'] = None if row['ok'] else FIX
    return row


def build_snapshot(items: list[dict], index: dict, card_for, now: str | None = None) -> dict:
    rows = sorted((safe_row(i, index, card_for) for i in items), key=lambda r: (r['toolkit'], r['status'], r['account_id']))
    groups: dict[str, dict] = {}
    for r in rows:
        g = groups.setdefault(r['toolkit'], {'toolkit': r['toolkit'], 'card': r['card'], 'accounts': []})
        g['accounts'].append(r)
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r['status']] = by_status.get(r['status'], 0) + 1
    not_ok = [r for r in rows if not r['ok']]
    snapshot = {
        'generated_at': now or datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'source': f'GET https://{ALLOWED_HOST}{PATH} (project {PROJECT_ID}), read-only',
        'card_source': '~/.agents/tools/guards/composio_guard.py card_index()/card_for()',
        'alarm': '~/.agents/tools/connectors/health/health_check.py check composio:no-expired-logins',
        'summary': {'total': len(rows), 'toolkits': len(groups), 'not_active': len(not_ok), 'by_status': by_status},
        'groups': sorted(groups.values(), key=lambda g: (all(a['ok'] for a in g['accounts']), g['toolkit'])),
    }
    screened, notes = redact_value(snapshot)
    if notes:
        screened['screening'] = sorted(set(notes))
    return screened


def write_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.connector-logins-', suffix='.json')
    with os.fdopen(fd, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, indent=2)
        fh.write('\n')
    os.replace(tmp, path)


def main() -> int:
    try:
        with open(USER_DATA, 'r', encoding='utf-8') as fh:
            raw = json.load(fh)
        creds = {'api_key': raw['api_key'], 'org_id': raw['org_id']}
        del raw
        items = fetch_all(creds)
        del creds
        card_index, card_for = load_card_mapper()
        snapshot = build_snapshot(items, card_index(), card_for)
    except Exception as exc:  # message only: never the config, stderr or reply body
        print(json.dumps({'ok': False, 'error': f'{type(exc).__name__}: {str(exc)[:200]}'}))
        return 1
    write_atomic(OUT, snapshot)
    print(json.dumps({'ok': True, 'file': str(OUT.relative_to(ROOT)), 'summary': snapshot['summary']}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
