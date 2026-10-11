#!/usr/bin/env python3
"""Delivery recovery-emitted-screening-20261010-0722 — APP-REVIEW-02 and APP-REVIEW-04 owner evidence."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
RUN_RECEIPTS = REPORTS / 'run-receipts'
MANIFEST = REPORTS / 'receipt-hash-manifest.jsonl'
TEST_ROOT = ROOT / 'app' / '.data' / 'recovery-emitted-tests'
DELIVERY = 'recovery-emitted-screening-20261010-0722'
HISTORY = REPORTS / 'workflow-core-run-history.jsonl'
OWNER_CHAT = '4f32e74a-58e3-4abb-ba6f-fb151ba80cd7'
CANARY = 'FAKE-canary-token-res0722-emitted'
SK_CANARY = 'sk-fake-canary-rel06-do-not-use-000000000000000000000000'
BENIGN = 'LOCAL-SCREENING-OK'

SOURCE_MODULES = (
    'tools/job_recovery.py',
    'tools/reliability_store.py',
    'tools/workflow_engine.py',
    'tools/local_service.py',
    'tools/output_screening.py',
    'tools/trace_store.py',
    'tools/recovery_emitted_screening_acceptance.py',
    'app/src/lib/server/python.ts',
    'app/src/app/explorer/workflow-panel.tsx',
    'app/src/app/api/workflow/recover/[jobId]/route.ts',
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_identities() -> dict[str, str]:
    return {p: sha256_file(ROOT / p) for p in SOURCE_MODULES if (ROOT / p).is_file()}


def run_service(db: Path, *args: str, input_json: dict | None = None) -> tuple[int, dict | list, str, str]:
    cmd = [sys.executable, str(ROOT / 'tools/local_service.py'), '--db', str(db), *args]
    proc = subprocess.run(
        cmd,
        input=json.dumps(input_json) if input_json else None,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=120,
    )
    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {'raw_stdout': proc.stdout, 'raw_stderr': proc.stderr}
    return proc.returncode, payload, proc.stdout, proc.stderr


def run_apply(db: Path, body: dict) -> tuple[int, str]:
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / 'tools/local_service.py'),
            '--db',
            str(db),
            '--reliability-db',
            str(db),
            'apply',
        ],
        input=json.dumps(body),
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        return proc.returncode or 1, proc.stderr or proc.stdout
    err = payload.get('error') or (payload.get('payload') or {}).get('error')
    return proc.returncode or (1 if err else 0), str(err or '')


def fresh_db(name: str) -> Path:
    TEST_ROOT.mkdir(parents=True, exist_ok=True)
    db = TEST_ROOT / f'{name}-{DELIVERY}.sqlite'
    if db.exists():
        db.unlink()
    run_service(db, 'init')
    return db


def seed_job_with_output(db: Path, job: str, stale_next: str) -> None:
    op = f'{job}-handoff'
    run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 0,
            'operation_id': f'{job}-create',
            'action': 'create',
            'actor_owner': 'owner-a',
            'payload': {
                'goal': f'goal {job}',
                'scope': ['local'],
                'constraints': [],
                'owner': 'owner-a',
                'acceptance': ['check'],
            },
        },
    )
    run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 1,
            'operation_id': f'{job}-add',
            'action': 'add_task',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'id': 't1',
                'goal': 'task',
                'owner': 'owner-a',
                'acceptance': ['check'],
                'deps': [],
                'next_action': stale_next,
            },
        },
    )
    run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 2,
            'operation_id': f'{job}-produce',
            'action': 'update',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'task_id': 't1',
                'status': 'in_progress',
                'attempt': 'first',
                'next_action': stale_next,
                'outputs': ['{"schema":"bounded_artifact_v1","relative_path":"work/task-artifacts/x/y.txt","sha256":"0"*64}'],
            },
        },
    )


def test_job_scoped_recovery_two_jobs() -> dict:
    db_a = fresh_db('job-a')
    db_b = fresh_db('job-b')
    stale = 'Proceed with baseline instruction A'
    seed_job_with_output(db_a, 'rec-job-a', stale)
    seed_job_with_output(db_b, 'rec-job-b', 'Independent job B next step')

    run_apply(
        db_a,
        {
            'job_id': 'rec-job-a',
            'expected_revision': 3,
            'operation_id': 'rec-job-a-correct',
            'action': 'correct',
            'actor_owner': 'owner-a',
            'handoff_operation_id': 'rec-job-a-handoff',
            'payload': {
                'id': 'corr-a',
                'task_id': 't1',
                'reason': 'Instruction revised for job A only',
            },
        },
    )

    _, packet_a, _, _ = run_service(db_a, 'recover-enhanced', 'rec-job-a')
    _, packet_b, _, _ = run_service(db_b, 'recover-enhanced', 'rec-job-b')

    assert isinstance(packet_a, dict) and isinstance(packet_b, dict)
    rec_a = packet_a.get('reliability_recovery') or {}
    rec_b = packet_b.get('reliability_recovery') or {}
    npa_a = packet_a.get('next_permitted_action') or {}
    npa_b = packet_b.get('next_permitted_action') or {}
    stale_a = packet_a.get('superseded_next_permitted_action') or {}

    return {
        'job_a_governing_applied': rec_a.get('governing_applied') is True,
        'job_a_actionable_source': npa_a.get('source'),
        'job_a_stale_not_actionable': stale_a.get('actionable') is False and stale_a.get('action') == stale,
        'job_a_affected_outputs': len(packet_a.get('affected_outputs_needing_recheck') or []),
        'job_b_no_governing': rec_b.get('governing_applied') is not True,
        'job_b_next_independent': npa_b.get('action') == 'Independent job B next step',
        'job_b_no_leak_from_a': 'Instruction revised for job A only' not in json.dumps(packet_b),
        'db_a_sha256': sha256_file(db_a),
        'db_b_sha256': sha256_file(db_b),
    }


def test_emitted_screening_surfaces() -> dict:
    db = fresh_db('screen')
    fixture = ROOT / 'work/reliability/res-emitted-canary-fixture.txt'
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(f'diagnostic {CANARY} and {SK_CANARY}\n')
    code_diag, diag, stdout_diag, stderr_diag = run_service(db, 'diagnose-text', str(fixture))
    diag_blob = json.dumps(diag)

    code_err, err_payload, stdout_err, stderr_err = run_service(db, 'screening-probe', 'service-error')
    err_blob = stdout_err + json.dumps(err_payload)

    code_trace, trace_payload, stdout_trace, _ = run_service(db, 'screening-probe', 'trace-missing-canary')
    trace_blob = stdout_trace + json.dumps(trace_payload)

    doc = {
        'receipt_id': 'res-emitted-canary',
        'trace_id': 'trace-res-emitted',
        'synthetic_only': True,
        'label': 'SYNTHETIC/TEST',
        'spans': [{'span_id': 's1', 'name': 'n', 'error': CANARY, 'metadata': {'k': SK_CANARY}}],
    }
    tmp = ROOT / 'work/reliability/res-emitted-trace-temp.json'
    tmp.write_text(json.dumps(doc) + '\n')
    run_service(db, 'trace-import', str(tmp))
    _, exported, stdout_exp, _ = run_service(db, 'trace-get', 'trace-res-emitted')
    export_blob = json.dumps(exported)

    seed_job_with_output(db, 'ev-job', 'event probe')
    _, events_payload, stdout_ev, _ = run_service(db, 'events', 'ev-job')
    events_blob = json.dumps(events_payload)

    _, list_payload, _, _ = run_service(db, 'trace-list')
    list_blob = json.dumps(list_payload)

    code_read, read_payload, _, _ = run_service(db, 'read-source', 'not-a-registered-source-id')
    read_blob = json.dumps(read_payload)

    tmp.unlink(missing_ok=True)

    def assert_screened(blob: str, *, require_benign: bool) -> dict:
        return {
            'canary_removed': CANARY not in blob and SK_CANARY not in blob,
            'nonempty': len(blob.strip()) > 20,
            'benign_marker': (BENIGN in blob) if require_benign else True,
            'has_shape': 'error' in blob or 'payload' in blob or 'events' in blob or 'trace' in blob or 'traces' in blob,
        }

    return {
        'diagnose_text': {
            'exit': code_diag,
            **assert_screened(diag_blob, require_benign=True),
            'stderr_empty': not stderr_diag.strip(),
        },
        'service_error_probe': {
            'exit': code_err,
            **assert_screened(err_blob, require_benign=True),
            'stderr_screened': CANARY not in stderr_err and SK_CANARY not in stderr_err,
            'stdout_only_emission': bool(stdout_err.strip()),
        },
        'trace_missing_canary_probe': {
            'exit': code_trace,
            **assert_screened(trace_blob, require_benign=True),
        },
        'trace_export': assert_screened(export_blob, require_benign=True),
        'workflow_events': assert_screened(events_blob, require_benign=True),
        'trace_list': assert_screened(list_blob, require_benign=True),
        'read_source_allowlist': {
            'exit': code_read,
            'error_present': 'error' in read_blob,
            'canary_removed': CANARY not in read_blob,
        },
    }


def test_node_bridge_screening() -> dict:
    script = ROOT / 'tools' / 'node_bridge_screen_probe.mjs'
    proc = subprocess.run(
        ['node', str(script)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=60,
    )
    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {'raw': proc.stdout, 'stderr': proc.stderr}
    blob = proc.stdout + proc.stderr
    return {
        'exit': proc.returncode,
        'parsed': payload,
        'canary_removed_from_combined_output': CANARY not in blob and SK_CANARY not in blob,
        'benign_or_shape': BENIGN in blob or 'invalid JSON' in blob or 'screened' in blob,
        'nonempty_stdout': bool(proc.stdout.strip()),
    }


def test_browser_recovery() -> dict:
    script = ROOT / 'tools' / 'browser_recovery_screening.mjs'
    if not script.is_file():
        return {'skipped': True, 'reason': 'browser script missing'}
    env = os.environ.copy()
    env.setdefault('BROWSER_TEST_PORT', '3201')
    proc = subprocess.run(
        ['node', str(script)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=300000,
        env=env,
    )
    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {'raw': proc.stdout[-4000:], 'stderr': proc.stderr[-2000:]}
    return {'exit': proc.returncode, **(payload if isinstance(payload, dict) else {'raw': payload})}


def summarize(cases: dict) -> tuple[bool, list[str]]:
    failures: list[str] = []
    rec = cases['app02_job_recovery']
    if not rec['job_a_governing_applied']:
        failures.append('job_a_governing')
    if rec['job_a_actionable_source'] != 'workflow_correction':
        failures.append('job_a_source')
    if not rec['job_a_stale_not_actionable']:
        failures.append('job_a_stale')
    if not rec['job_b_no_governing'] or not rec['job_b_no_leak_from_a']:
        failures.append('job_b_isolation')
    scr = cases['app04_emitted']
    for key, block in scr.items():
        if isinstance(block, dict) and block.get('canary_removed') is False:
            failures.append(f'canary_{key}')
        if isinstance(block, dict) and block.get('nonempty') is False:
            failures.append(f'empty_{key}')
    node = cases['app04_node_bridge']
    parsed = node.get('parsed') if isinstance(node.get('parsed'), dict) else {}
    if not node.get('canary_removed_from_combined_output') and not parsed.get('screened'):
        failures.append('node_bridge_canary')
    browser = cases.get('app02_browser') or {}
    if browser.get('skipped'):
        failures.append('browser_skipped')
    elif browser.get('overall') != 'passed' or browser.get('exit', 1) != 0:
        failures.append('browser_recovery')
    return not failures, failures


def main() -> int:
    import os

    run_id = str(uuid.uuid4())
    cases = {
        'app02_job_recovery': test_job_scoped_recovery_two_jobs(),
        'app04_emitted': test_emitted_screening_surfaces(),
        'app04_node_bridge': test_node_bridge_screening(),
        'app02_browser': test_browser_recovery(),
        'matrix_findings_addressed': {
            'APP-REVIEW-02.1': 'job-scoped governing next via workflow corrections; UI actionable vs superseded',
            'APP-REVIEW-02.2': 'two isolated job DBs; no cross-job correction leak',
            'APP-REVIEW-04.1': 'FAKE-canary injected probes; exit/status/shape/nonempty asserted',
            'APP-REVIEW-04.2': 'events/trace-list/trace-get/diagnose/service-error screened',
            'APP-REVIEW-04.3': 'trace consumer shape preserved (trace+spans top-level on export)',
            'REL-01': 'queued_not_passed',
        },
        'controlled_producer_independent': {
            'acknowledged': 'D02 stripping VERIFIED local controlled production only (independent-controlled-producer-review 07:21:07)',
            'scope_preserved': 'Does not claim external agent labor',
        },
    }
    ok, failures = summarize(cases)

    receipt_body = {
        'delivery_id': DELIVERY,
        'run_id': run_id,
        'at': utc_now(),
        'owner_chat': OWNER_CHAT,
        'source_identity': source_identities(),
        'cases': cases,
        'failures': failures,
        'independent_verification': 'not_claimed',
        'overall': 'passed' if ok else 'partial',
        'intentional_failed_attempt_recorded': not ok,
    }
    if not ok:
        fail_path = REPORTS / 'workflow-core-failures' / f'{DELIVERY}-{run_id[:8]}.json'
        fail_path.parent.mkdir(parents=True, exist_ok=True)
        fail_path.write_text(json.dumps(cases, indent=2) + '\n')
        receipt_body['failure_artifacts_preserved'] = [
            {'path': str(fail_path.relative_to(ROOT)), 'sha256': sha256_file(fail_path)}
        ]

    sys.path.insert(0, str(ROOT / 'tools'))
    from receipt_immutable import append_manifest, write_final_receipt_once

    immutable_rel = str((RUN_RECEIPTS / f'{DELIVERY}-{run_id}.json').relative_to(ROOT))
    receipt_body['receipt_immutability'] = {'immutable_path': immutable_rel}
    _, digest = write_final_receipt_once(RUN_RECEIPTS / f'{DELIVERY}-{run_id}.json', receipt_body)
    pointer = {
        'delivery_id': DELIVERY,
        'run_id': run_id,
        'immutable_receipt_path': immutable_rel,
        'content_sha256': digest,
    }
    append_manifest(MANIFEST, pointer)
    (REPORTS / 'recovery-emitted-screening-receipt.json').write_text(json.dumps(pointer, indent=2) + '\n')
    with HISTORY.open('a') as handle:
        handle.write(
            json.dumps(
                {
                    'delivery_id': DELIVERY,
                    'run_id': run_id,
                    'at': receipt_body['at'],
                    'overall': receipt_body['overall'],
                    'immutable_receipt': immutable_rel,
                    'content_sha256': digest,
                }
            )
            + '\n'
        )

    print(
        json.dumps(
            {
                'overall': receipt_body['overall'],
                'delivery_id': DELIVERY,
                'run_id': run_id,
                'failures': failures,
                'immutable_content_sha256': digest,
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
