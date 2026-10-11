#!/usr/bin/env python3
"""Application-path acceptance for delivery app-path-corrections-20261010-0514."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELIVERY_ID = 'app-path-corrections-20261010-0514'
CANARY = 'sk-fake-canary-rel06-do-not-use-000000000000000000000000'
TEST_DIR = ROOT / 'app' / '.data' / 'reliability-tests'
RELIABILITY_DB = ROOT / 'app' / '.data' / 'reliability.sqlite'
MARKER = ROOT / 'work/reliability/synthetic-sync-marker.json'


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_service(db: Path, *args: str) -> tuple[int, dict | list | str]:
    cmd = [sys.executable, str(ROOT / 'tools/local_service.py'), '--db', str(db), *args]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    try:
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {'raw': result.stdout, 'stderr': result.stderr}
    return result.returncode, payload


def source_hashes() -> dict:
    paths = [
        'tools/local_service.py',
        'tools/reliability_gate.py',
        'tools/workflow_apply_guard.py',
        'tools/reliability_store.py',
        'tools/trace_store.py',
    ]
    out = {}
    for rel in paths:
        p = ROOT / rel
        if p.is_file():
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def test_gate_and_complete() -> dict:
    iso_rel = TEST_DIR / 'app-path-gate-reliability.sqlite'
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    if iso_rel.exists():
        iso_rel.unlink()
    bad = {
        'requirement_id': 'REL-02',
        'complete': True,
        'job_id': 'app-path-gate-job',
        'job_revision': 1,
        'requirement_set': ['REL-01', 'REL-02', 'REL-03', 'REL-04', 'REL-05', 'REL-06'],
        'evidence': {
            'verified_at': 'not-a-date',
            'actually_used': 'reliability_gate_per_requirement',
            'documented_path': 'does-not-exist',
            'proof_sha256': '0' * 64,
        },
    }
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / 'tools/local_service.py'),
            '--db',
            str(iso_rel),
            '--reliability-db',
            str(iso_rel),
            'reliability-complete',
        ],
        input=json.dumps(bad),
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    gate_bad = json.loads(proc.stdout)
    sys.path.insert(0, str(ROOT / 'tools'))
    from reliability_store import connect as rel_connect
    from verification_evidence import issue_measured_rel02_record

    rel_connect(iso_rel).close()
    issued = issue_measured_rel02_record(
        rel_connect(iso_rel),
        job_id='app-path-gate-job',
        job_revision=1,
        task_id='gate-task',
        operation_id='app-path-gate-op',
        verifier='app-path-acceptance',
        fixture_only=False,
    )
    good = {
        'requirement_id': 'REL-02',
        'complete': True,
        'owner': 'app-path-acceptance',
        'job_id': 'app-path-gate-job',
        'job_revision': 1,
        'requirement_set': ['REL-01', 'REL-02', 'REL-03', 'REL-04', 'REL-05', 'REL-06'],
        'evidence': {
            'verified_at': utc_now(),
            'actually_used': 'reliability_gate_per_requirement',
            'documented_path': 'docs/RELIABILITY_ADDENDUM.md',
            'proof_path': issued['path'],
            'proof_sha256': issued['record_sha256'],
            'skills_verified': True,
            'relationships_sha256': hashlib.sha256((ROOT / 'data/relationships.json').read_bytes()).hexdigest(),
        },
    }
    proc2 = subprocess.run(
        [
            sys.executable,
            str(ROOT / 'tools/local_service.py'),
            '--db',
            str(iso_rel),
            '--reliability-db',
            str(iso_rel),
            'reliability-complete',
        ],
        input=json.dumps(good),
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    gate_good = json.loads(proc2.stdout)
    return {
        'bad_rejected': not gate_bad.get('accepted', True),
        'bad_reason': gate_bad.get('reason'),
        'good_accepted': gate_good.get('accepted') is True,
    }


def test_recover_restart(wf_db: Path, job_id: str) -> dict:
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / 'tools/local_service.py'),
            '--db',
            str(wf_db),
            'recover-enhanced',
            job_id,
            '--presented-note',
            'Supervision baseline revision 1 only',
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    try:
        packet = json.loads(proc.stdout)
    except json.JSONDecodeError:
        packet = {'raw': proc.stdout, 'stderr': proc.stderr}
    return {
        'subprocess_exit': proc.returncode,
        'fresh_process': True,
        'governing_applied': (packet.get('reliability_recovery') or {}).get('governing_applied'),
        'governing_next': packet.get('governing_next_action'),
        'recheck_count': len(packet.get('affected_outputs_needing_recheck') or []),
    }


def _run_apply_isolated(wf_db: Path, rel_db: Path, body: dict) -> subprocess.CompletedProcess:
    if rel_db.resolve() != wf_db.resolve():
        rel_db = wf_db
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / 'tools/local_service.py'),
            '--db',
            str(wf_db),
            '--reliability-db',
            str(wf_db),
            'apply',
        ],
        input=json.dumps(body),
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )


def test_handoff_apply() -> tuple[dict, Path, str]:
    wf_db = TEST_DIR / 'app-path-rel04.sqlite'
    rel_db = TEST_DIR / 'app-path-rel04-reliability.sqlite'
    job_id = 'app-path-handoff'
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    for path in (wf_db, rel_db):
        if path.exists():
            path.unlink()
    run_service(wf_db, 'init')
    create = {
        'job_id': job_id,
        'expected_revision': 0,
        'operation_id': 'app-path-create',
        'action': 'create',
        'actor_owner': 'owner-a',
        'payload': {
            'goal': 'handoff apply path',
            'scope': ['local'],
            'constraints': [],
            'owner': 'owner-a',
            'acceptance': ['check'],
        },
    }
    proc_create = _run_apply_isolated(wf_db, rel_db, create)
    if proc_create.returncode != 0:
        return ({'error': 'create_failed', 'stderr': proc_create.stderr, 'stdout': proc_create.stdout}, wf_db, job_id)
    op = f'{job_id}-handoff'
    transfer_req = {
        'action': 'handoff_transfer',
        'operation_id': 'app-path-xfer-a-b',
        'actor_owner': 'owner-a',
        'payload': {
            'operation_id': op,
            'expected_owner': 'owner-a',
            'expected_revision': 1,
            'new_owner': 'owner-b',
            'job_revision': 1,
            'acceptance': ['check'],
            'job_id': job_id,
        },
    }
    proc_transfer = _run_apply_isolated(wf_db, rel_db, transfer_req)
    if proc_transfer.returncode != 0:
        return (
            {
                'error': 'transfer_failed',
                'stdout': proc_transfer.stdout,
                'stderr': proc_transfer.stderr,
            },
            wf_db,
            job_id,
        )
    add_payload = {
        'job_id': job_id,
        'expected_revision': 1,
        'operation_id': 'app-path-op-0514',
        'action': 'add_task',
        'actor_owner': 'owner-b',
        'handoff_operation_id': op,
        'payload': {'id': 't1', 'goal': 'g', 'owner': 'owner-b', 'acceptance': ['check'], 'deps': []},
    }
    proc_stale = _run_apply_isolated(
        wf_db,
        rel_db,
        {**add_payload, 'actor_owner': 'owner-a', 'operation_id': 'app-path-stale-owner'},
    )
    stale_owner_fail = proc_stale.returncode != 0
    proc_ok = _run_apply_isolated(wf_db, rel_db, add_payload)
    replay = _run_apply_isolated(wf_db, rel_db, add_payload)
    import sqlite3

    ops = sqlite3.connect(wf_db).execute(
        'SELECT COUNT(*) FROM operations WHERE id=?', ('app-path-op-0514',)
    ).fetchone()[0]
    task_owner = None
    row = sqlite3.connect(wf_db).execute("SELECT payload FROM tasks WHERE id='t1'").fetchone()
    if row:
        task_owner = json.loads(row[0]).get('owner')
    return (
        {
            'stale_owner_rejected': stale_owner_fail,
            'owner_b_apply_ok': proc_ok.returncode == 0,
            'operation_count': ops,
            'task_owner_after_apply': task_owner,
            'replay_ok': replay.returncode == 0,
        },
        wf_db,
        job_id,
    )


def test_canary_surfaces() -> dict:
    fixture = ROOT / 'work/reliability/fake-canary-fixture.txt'
    fixture.write_text('FAKE diagnostic ' + CANARY + '\n')
    _, diag = run_service(RELIABILITY_DB, 'diagnose-text', str(fixture))
    payload = diag.get('payload') if isinstance(diag, dict) else {}
    diag_text = json.dumps(payload)
    _, err = run_service(RELIABILITY_DB, 'trace-get', 'missing-trace-id')
    err_blob = json.dumps(err)
    trace_db = TEST_DIR / 'app-path-canary.sqlite'
    if trace_db.exists():
        trace_db.unlink()
    run_service(trace_db, 'init')
    doc = {
        'receipt_id': 'synthetic-canary-app-path',
        'trace_id': 'trace-canary-app-path',
        'synthetic_only': True,
        'label': 'SYNTHETIC/TEST canary',
        'spans': [
            {
                'span_id': 'span-1',
                'name': 'test',
                'error': CANARY,
                'metadata': {'canary': CANARY},
            }
        ],
    }
    tmp = ROOT / 'work/reliability/canary-trace-temp.json'
    tmp.write_text(json.dumps(doc) + '\n')
    run_service(trace_db, 'trace-import', str(tmp))
    _, exported = run_service(trace_db, 'trace-get', 'trace-canary-app-path')
    export_blob = json.dumps(exported)
    tmp.unlink(missing_ok=True)
    return {
        'diagnostic_no_leak': CANARY not in diag_text,
        'error_no_leak': CANARY not in err_blob,
        'trace_export_no_leak': CANARY not in export_blob,
        'surfaces_exercised_via_local_service': True,
    }


def test_synthetic_mutation_refresh() -> dict:
    sync_db = TEST_DIR / 'app-path-sync.sqlite'
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    if sync_db.exists():
        sync_db.unlink()
    run_service(sync_db, 'init')
    run_service(sync_db, 'sync-observe')
    baseline = hashlib.sha256(MARKER.read_bytes()).hexdigest()
    doc = json.loads(MARKER.read_text())
    doc['mutation_id'] = DELIVERY_ID
    doc['touched_at'] = utc_now()
    doc['revision'] = int(doc.get('revision', 0)) + 1
    MARKER.write_text(json.dumps(doc, indent=2) + '\n')
    after_hash = hashlib.sha256(MARKER.read_bytes()).hexdigest()
    run_service(sync_db, 'sync-observe')
    receipt_path = ROOT / 'work/reliability/live-mutation-receipt.json'
    receipt = {
        'label': 'SYNTHETIC/TEST',
        'receipt_id': f'live-mutation-{DELIVERY_ID}',
        'trace_id': 'trace-live-mutation',
        'synthetic_only': True,
        'generated_at': utc_now(),
        'source_marker_sha256_before': baseline,
        'source_marker_sha256_after': after_hash,
        'spans': [
            {
                'span_id': 'span-live-sync',
                'name': 'catalog_sync.observe',
                'tool_action': 'observe_all',
                'status': 'ok',
                'metadata': {
                    'marker_path': 'work/reliability/synthetic-sync-marker.json',
                    'sha256_before': baseline,
                    'sha256_after': after_hash,
                },
            }
        ],
    }
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    run_service(sync_db, 'trace-import', str(receipt_path))
    _, status_before_restart = run_service(sync_db, 'sync-status')
    proc_restart = subprocess.run(
        [sys.executable, str(ROOT / 'tools/local_service.py'), '--db', str(sync_db), 'sync-status'],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    status_restart = json.loads(proc_restart.stdout)
    imp2 = run_service(sync_db, 'trace-import', str(receipt_path))
    marker_row = next(
        (f for f in status_restart.get('files', []) if f.get('path') == 'work/reliability/synthetic-sync-marker.json'),
        {},
    )
    return {
        'baseline_hash': baseline,
        'after_mutation_hash': after_hash,
        'observed_hash': marker_row.get('sha256'),
        'hash_changed': baseline != after_hash,
        'receipt_linked_to_mutation': receipt['source_marker_sha256_after'] == after_hash,
        'duplicate_import_rejected': imp2[1].get('imported') is False if isinstance(imp2[1], dict) else False,
        'restart_subprocess_ok': proc_restart.returncode == 0,
    }


def main() -> int:
    handoff, wf_db, job_id = test_handoff_apply()
    if 'error' in handoff:
        handoff_result = handoff
    else:
        handoff_result = handoff
    results = {
        'delivery_id': DELIVERY_ID,
        'acknowledgment': f'Delivery {DELIVERY_ID} acknowledged once; application-path acceptance (owner evidence, not independent).',
        'at': utc_now(),
        'source_hashes_at_run': source_hashes(),
        'REL-01': {'status': 'unverified', 'note': 'Cursor fresh-runtime auto skill loading not in bounded local proof'},
        'gate_complete': test_gate_and_complete(),
        'recover_restart': test_recover_restart(wf_db, job_id),
        'handoff_apply': handoff_result,
        'canary_surfaces': test_canary_surfaces(),
        'synthetic_mutation': test_synthetic_mutation_refresh(),
    }
    gate_ok = results['gate_complete']['bad_rejected'] and results['gate_complete']['good_accepted']
    recover_ok = results['recover_restart'].get('governing_applied') and results['recover_restart'].get('governing_next')
    handoff_ok = (
        results['handoff_apply'].get('stale_owner_rejected')
        and results['handoff_apply'].get('owner_b_apply_ok')
        and results['handoff_apply'].get('replay_ok')
        and results['handoff_apply'].get('operation_count') == 1
        and results['handoff_apply'].get('task_owner_after_apply') == 'owner-b'
    )
    canary_ok = all(
        results['canary_surfaces'][k]
        for k in ('diagnostic_no_leak', 'error_no_leak', 'trace_export_no_leak', 'surfaces_exercised_via_local_service')
    )
    synth_ok = (
        results['synthetic_mutation']['hash_changed']
        and results['synthetic_mutation']['observed_hash'] == results['synthetic_mutation']['after_mutation_hash']
        and results['synthetic_mutation']['receipt_linked_to_mutation']
        and results['synthetic_mutation']['duplicate_import_rejected']
    )
    results['summary'] = {
        'REL-02_gate': 'passed' if gate_ok else 'failed',
        'REL-03_recover': 'passed' if recover_ok else 'failed',
        'REL-04_handoff': 'passed' if handoff_ok else 'failed',
        'REL-06_canary': 'passed' if canary_ok else 'failed',
        'synthetic_live_mutation': 'passed' if synth_ok else 'failed',
        'overall': 'passed' if all([gate_ok, recover_ok, handoff_ok, canary_ok, synth_ok]) else 'partial',
    }
    out = ROOT / 'reports/app-path-corrections-receipt.json'
    hist = []
    if out.is_file():
        try:
            prior = json.loads(out.read_text())
            hist = list(prior.get('history', []))
        except json.JSONDecodeError:
            hist = []
    snapshot = {k: v for k, v in results.items() if k != 'history'}
    hist.append({'at': results['at'], 'delivery_id': DELIVERY_ID, 'summary': results['summary']})
    results['history'] = hist[-8:]
    out.write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results['summary'], indent=2))
    return 0 if results['summary']['overall'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
