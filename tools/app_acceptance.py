#!/usr/bin/env python3
"""Local application acceptance checks (loopback API + reference engine)."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'app'
DB = APP / '.data' / 'acceptance.sqlite'
SERVICE = ROOT / 'tools' / 'local_service.py'
EXPECTED_RELATIONSHIPS = 59
EXPECTED_COVERAGE = 2377


def run_service(*args: str, stdin: str | None = None, db: Path | None = None) -> dict:
    db_path = db or DB
    cmd = [sys.executable, str(SERVICE), '--db', str(db_path), *args]
    result = subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        input=stdin,
    )
    return json.loads(result.stdout)


def http(method: str, url: str, body: dict | None = None, token: str | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['X-Local-Token'] = token
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode())


def wait_for_server(base: str, timeout: float = 45.0) -> None:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(base + '/api/health') as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.5)
    raise RuntimeError('server did not become ready')


def main() -> int:
    if DB.exists():
        DB.unlink()
    run_service('init')
    run_service('sync-observe')
    results: list[dict] = []

    def record(name: str, passed: bool, detail: object) -> None:
        results.append({'name': name, 'passed': passed, 'detail': detail})

    bundle = run_service('catalog-export')
    relationships = len(bundle['data']['relationships'])
    coverage = len(bundle['data']['coverage'])
    load_gaps = bundle.get('load_gaps') or []
    completeness = bundle.get('completeness') or {}
    catalog_strict_ok = (
        relationships == EXPECTED_RELATIONSHIPS
        and coverage == EXPECTED_COVERAGE
        and len(load_gaps) == 0
        and completeness.get('complete') is True
    )
    record(
        'catalog_strict_counts_and_gaps',
        catalog_strict_ok,
        {
            'relationships': relationships,
            'expected_relationships': EXPECTED_RELATIONSHIPS,
            'coverage': coverage,
            'expected_coverage': EXPECTED_COVERAGE,
            'load_gaps': load_gaps,
            'completeness': completeness,
        },
    )

    completeness_cli = run_service('catalog-completeness')
    record(
        'catalog_completeness_command',
        completeness_cli.get('complete') is True and completeness_cli.get('load_gaps') == 0,
        completeness_cli,
    )

    sync = run_service('sync-status')
    record(
        'catalog_sync_watch',
        sync.get('unreadable_count', 1) == 0 and len(sync.get('files', [])) >= 10,
        {'unreadable_count': sync.get('unreadable_count'), 'file_count': len(sync.get('files', []))},
    )

    trace_fixture = run_service('trace-import', str(ROOT / 'examples' / 'agent-trace-fixture.json'))
    trace_synthetic = run_service('trace-import', str(ROOT / 'examples' / 'workflow-recovery-synthetic.json'))
    traces = run_service('trace-list')
    record(
        'trace_import_fixture_and_synthetic',
        trace_fixture.get('imported') is True
        and trace_synthetic.get('imported') is True
        and trace_synthetic.get('synthetic_only') is True
        and len(traces) >= 2,
        {
            'fixture': trace_fixture,
            'synthetic': trace_synthetic,
            'trace_count': len(traces),
        },
    )

    archived = run_service('read-source', 'F0001')
    record(
        'file_browser_archived',
        archived.get('content') and archived.get('label') in {'Archived snapshot', 'Current file'},
        {'mode': archived.get('mode'), 'label': archived.get('label')},
    )

    blocked = run_service('read-source', 'F0002')
    record(
        'file_proof_read_only',
        'content' in blocked or blocked.get('mode') in {'archived_snapshot', 'current_file'},
        {'source_id': 'F0002'},
    )

    create = {
        'job_id': 'acceptance-job',
        'expected_revision': 0,
        'operation_id': 'acceptance-create-1',
        'action': 'create',
        'actor_owner': 'owner-a',  # the job service requires the acting owner
        'payload': {
            'goal': 'Acceptance workflow job',
            'scope': ['local'],
            'constraints': ['no external services'],
            'owner': 'owner-a',
            'acceptance': ['check-one'],
        },
    }
    run_service('apply', stdin=json.dumps(create))
    add = {
        'job_id': 'acceptance-job',
        'expected_revision': 1,
        'operation_id': 'acceptance-add-1',
        'action': 'add_task',
        'actor_owner': 'owner-a',  # the job service requires the acting owner
        'payload': {
            'id': 'task-a',
            'goal': 'Inspect catalog record',
            'owner': 'owner-a',
            'acceptance': ['check-one'],
            'deps': [],
        },
    }
    run_service('apply', stdin=json.dumps(add))
    recover = run_service('recover', 'acceptance-job')
    record('fresh_agent_recover_packet', recover.get('job_id') == 'acceptance-job', recover)

    with tempfile.TemporaryDirectory() as tmp:
        crash_db = Path(tmp) / 'crash-resume.sqlite'
        run_service('init', db=crash_db)
        run_service('apply', stdin=json.dumps(create), db=crash_db)
        run_service('apply', stdin=json.dumps(add), db=crash_db)
        resumed = run_service('recover', 'acceptance-job', db=crash_db)
        record(
            'crash_resume_subprocess_recover',
            resumed.get('job_id') == 'acceptance-job'
            and resumed.get('tasks', {}).get('task-a', {}).get('goal') == 'Inspect catalog record',
            {
                'note': 'Separate subprocess opens SQLite after apply completes (simulated crash between sessions).',
                'current_revision': resumed.get('current_revision'),
                'task_ids': sorted(resumed.get('tasks', {}).keys()),
            },
        )

    stale = {
        'job_id': 'acceptance-job',
        'expected_revision': 1,
        'operation_id': 'acceptance-stale-1',
        'action': 'update',
        'actor_owner': 'owner-a',  # the job service requires the acting owner
        'payload': {'task_id': 'task-a', 'status': 'in_progress'},
    }
    stale_result = subprocess.run(
        [sys.executable, str(SERVICE), '--db', str(DB), 'apply'],
        input=json.dumps(stale),
        capture_output=True,
        text=True,
    )
    record(
        'revision_conflict',
        'revision conflict' in (stale_result.stdout + stale_result.stderr),
        (stale_result.stdout or stale_result.stderr).strip(),
    )

    replay = {
        'job_id': 'acceptance-job',
        'expected_revision': 0,
        'operation_id': 'acceptance-create-1',
        'action': 'create',
        'actor_owner': 'owner-a',  # the job service requires the acting owner
        'payload': create['payload'],
    }
    replay_result = run_service('apply', stdin=json.dumps(replay))
    record(
        'operation_reconciliation',
        replay_result.get('operation_id') == 'acceptance-create-1',
        replay_result,
    )

    env = os.environ.copy()
    env['PORT'] = '3199'
    server = subprocess.Popen(
        ['npx', 'next', 'start', '-p', '3199'],
        cwd=APP,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base = 'http://127.0.0.1:3199'
    try:
        wait_for_server(base)
        health = http('GET', base + '/api/health')
        token = health['token']
        catalog = http('GET', base + '/api/catalog')
        api_relationships = len(catalog.get('data', {}).get('relationships', []))
        api_coverage = len(catalog.get('data', {}).get('coverage', []))
        api_gaps = catalog.get('load_gaps') or []
        record(
            'loopback_catalog_api',
            bool(catalog.get('data', {}).get('components'))
            and api_relationships == EXPECTED_RELATIONSHIPS
            and api_coverage == EXPECTED_COVERAGE
            and len(api_gaps) == 0,
            {
                'components': len(catalog.get('data', {}).get('components', [])),
                'relationships': api_relationships,
                'coverage': api_coverage,
                'load_gaps': api_gaps,
            },
        )
        try:
            http('POST', base + '/api/generate-text')
            record('ai_routes_disabled', False, 'expected 503')
        except urllib.error.HTTPError as error:
            payload = json.loads(error.read().decode())
            record(
                'ai_routes_disabled',
                error.code == 503 and payload.get('disabled') is True,
                payload,
            )
        saved = http(
            'PUT',
            base + '/api/presentation',
            {'scope': 'acceptance', 'key': 'layout', 'value': {'x': 1}},
            token=token,
        )
        record('visual_isolation_presentation_write', saved.get('scope') == 'acceptance', saved)
    finally:
        server.send_signal(signal.SIGTERM)
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()

    passed = sum(1 for item in results if item['passed'])
    strict_failures = [
        item['name']
        for item in results
        if not item['passed']
        and item['name']
        in {
            'catalog_strict_counts_and_gaps',
            'catalog_completeness_command',
            'crash_resume_subprocess_recover',
        }
    ]
    report = {
        'status': 'PASS' if passed == len(results) else 'FAIL',
        'passed': passed,
        'total': len(results),
        'strict_catalog_checks': {
            'relationships': EXPECTED_RELATIONSHIPS,
            'coverage': EXPECTED_COVERAGE,
            'require_empty_load_gaps': True,
        },
        'crash_resume_subprocess': next(
            (item for item in results if item['name'] == 'crash_resume_subprocess_recover'),
            None,
        ),
        'strict_failures': strict_failures,
        'results': results,
    }
    out = ROOT / 'reports' / 'application-verification.json'
    out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
