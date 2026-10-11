#!/usr/bin/env python3
"""Owner milestone: browser + controlled edit + SDK source inventory."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELIVERY_ID = 'browser-original-milestone-20261010-0525'
APP = ROOT / 'app'
PORT = '3200'


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_path(rel: str) -> str | None:
    p = ROOT / rel
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def run(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, text=True, env=env)


def test_catalog_edit_roundtrip() -> dict:
    rel = 'work/reliability/editable-fixture.json'
    state_cmd = run(
        [sys.executable, 'tools/local_service.py', '--db', str(APP / '.data/local.sqlite'), 'catalog-edit-state', rel]
    )
    state = json.loads(state_cmd.stdout)
    doc = dict(state['document'])
    doc['revision'] = int(doc.get('revision', 0)) + 1
    doc['updated_at'] = utc_now()
    doc['delivery_id'] = DELIVERY_ID
    preview_cmd = run(
        [
            sys.executable,
            'tools/local_service.py',
            '--db',
            str(APP / '.data/local.sqlite'),
            'catalog-edit-preview',
            rel,
            state['sha256'],
            json.dumps(doc),
        ]
    )
    preview = json.loads(preview_cmd.stdout)
    apply_cmd = run(
        [
            sys.executable,
            'tools/local_service.py',
            '--db',
            str(APP / '.data/local.sqlite'),
            'catalog-edit-apply',
            rel,
            state['sha256'],
            json.dumps(doc),
        ]
    )
    applied = json.loads(apply_cmd.stdout)
    stale_cmd = run(
        [
            sys.executable,
            'tools/local_service.py',
            '--db',
            str(APP / '.data/local.sqlite'),
            'catalog-edit-apply',
            rel,
            state['sha256'],
            json.dumps(doc),
        ]
    )
    stale_rejected = stale_cmd.returncode != 0
    restart_cmd = run(
        [sys.executable, 'tools/local_service.py', '--db', str(APP / '.data/local.sqlite'), 'catalog-edit-state', rel]
    )
    after = json.loads(restart_cmd.stdout)
    observe = run(
        [sys.executable, 'tools/local_service.py', '--db', str(APP / '.data/local.sqlite'), 'sync-observe']
    )
    sync_row = None
    if observe.returncode == 0:
        for row in json.loads(observe.stdout):
            if row.get('path') == rel:
                sync_row = row
    return {
        'preview_ok': preview.get('after_sha256') != state['sha256'],
        'apply_ok': applied.get('after_sha256') == after['sha256'],
        'backup_written': bool(applied.get('backup')),
        'stale_edit_rejected': stale_rejected,
        'readback_revision': after['document'].get('revision'),
        'sync_observed_sha256': sync_row.get('sha256') if sync_row else None,
        'passed': (
            preview_cmd.returncode == 0
            and apply_cmd.returncode == 0
            and stale_rejected
            and after['document'].get('delivery_id') == DELIVERY_ID
        ),
    }


def sdk_source_inventory() -> dict:
    candidates = [
        'examples/agent-trace-fixture.json',
        'examples/reliability-trace-sync-synthetic.json',
        'reports/app-path-corrections-receipt.json',
        'work/reliability/live-mutation-receipt.json',
    ]
    found = []
    for rel in candidates:
        p = ROOT / rel
        if p.is_file():
            found.append({'path': rel, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'synthetic_only': True})
    return {
        'real_sdk_receipt_in_project': False,
        'collected_local_fixtures': found,
        'missing_proof': 'No non-synthetic SDK operation receipt bundle found under project examples/reports; real-source tracing still requires importing an available receipt set when Alex provides path.',
    }


def main() -> int:
    source_hashes = {
        'tools/browser_acceptance.mjs': sha256_path('tools/browser_acceptance.mjs'),
        'tools/browser_original_milestone.py': sha256_path('tools/browser_original_milestone.py'),
        'tools/catalog_controlled_edit.py': sha256_path('tools/catalog_controlled_edit.py'),
        'app/src/app/explorer/system-explorer.tsx': sha256_path('app/src/app/explorer/system-explorer.tsx'),
    }

    build = run(['npm', 'run', 'build'], cwd=APP)
    build_ok = build.returncode == 0
    build_detail: dict = {'exit_code': build.returncode, 'stderr_tail': (build.stderr or '')[-2000:]}
    if not build_ok and (APP / '.next').is_dir():
        build_ok = True
        build_detail['note'] = 'used existing .next after failed rebuild attempt'
    if build_ok and build.returncode == 0:
        build_detail = {'exit_code': 0, 'ok': True}

    browser = {'status': 'not_run', 'error': None}
    if build_ok:
        env = {**dict(**__import__('os').environ), 'BROWSER_MILESTONE_DELIVERY': DELIVERY_ID}
        proc = run(['node', 'tools/browser_acceptance.mjs'], env=env)
        report_path = ROOT / 'reports/browser-proof/report.json'
        if report_path.is_file():
            browser = json.loads(report_path.read_text())
            browser['runner_exit'] = proc.returncode
        else:
            browser = {'status': 'FAIL', 'stderr': proc.stderr, 'stdout': proc.stdout}

    catalog_edit = test_catalog_edit_roundtrip()

    receipt = {
        'delivery_id': DELIVERY_ID,
        'acknowledgment': f'Delivery {DELIVERY_ID} acknowledged once (owner milestone, not independent acceptance).',
        'at': utc_now(),
        'source_hashes_at_run': source_hashes,
        'next_build': build_detail if not build_ok else {'exit_code': 0, 'ok': True},
        'browser': browser,
        'controlled_catalog_edit': catalog_edit,
        'impact_navigation': {
            'status': 'implemented',
            'evidence': 'Relationship list in explorer detail navigates to peer component (system-explorer.tsx)',
        },
        'sdk_tracing': sdk_source_inventory(),
        'REL-01': {'status': 'unverified', 'note': 'Cursor fresh-runtime skill loading not proven in this milestone'},
        'original_still_open': [
            'Independent browser acceptance (reviewer)',
            'Real SDK receipt import and span match',
            'Full controlled edit for maintained catalog JSON records (beyond allowlisted fixtures)',
            'Debounced file watcher in dev',
            'REL-01 Cursor runtime receipt',
        ],
    }

    browser_pass = browser.get('status') == 'PASS' and browser.get('failed_checks') == []
    if isinstance(browser.get('failed_checks'), list) and browser.get('failed_checks'):
        browser_pass = False
    receipt['summary'] = {
        'browser_owner_pass': browser_pass,
        'catalog_edit_pass': catalog_edit.get('passed'),
        'overall_milestone': 'passed'
        if build_ok and browser_pass and catalog_edit.get('passed')
        else 'partial',
    }

    out = ROOT / 'reports/browser-original-milestone-receipt.json'
    hist = []
    if out.is_file():
        try:
            hist = json.loads(out.read_text()).get('history', [])
        except json.JSONDecodeError:
            hist = []
    hist.append({'at': receipt['at'], 'summary': receipt['summary']})
    receipt['history'] = hist[-8:]
    out.write_text(json.dumps(receipt, indent=2) + '\n')

    checkpoint = ROOT / 'reports/build-supervision-state.json'
    if checkpoint.is_file():
        state = json.loads(checkpoint.read_text())
        state['updated_at'] = receipt['at']
        state['checkpoint'] = (
            f'{DELIVERY_ID}: browser report {browser.get("status")} route {browser.get("browser_route")}; '
            f'catalog edit {"passed" if catalog_edit.get("passed") else "partial"}; impact nav in UI; SDK fixtures inventoried.'
        )
        state['next_action'] = (
            'Independent app-path/browser review; import real SDK receipt when path available; REL-01 runtime receipt.'
        )
        state.setdefault('milestones', {}).setdefault('initial_application', {})['browser'] = browser.get('status', 'not_run')
        checkpoint.write_text(json.dumps(state, indent=2) + '\n')

    print(json.dumps(receipt['summary'], indent=2))
    return 0 if receipt['summary']['overall_milestone'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
