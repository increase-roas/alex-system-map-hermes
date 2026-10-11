#!/usr/bin/env python3
"""Delivery atomic-failure-fixture-boundary-20261010-0622."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
TEST_ROOT = ROOT / 'app' / '.data' / 'workflow-core-tests'
DELIVERY = 'atomic-failure-fixture-boundary-20261010-0622'
HISTORY = REPORTS / 'workflow-core-run-history.jsonl'
PRIOR_FAILURE = REPORTS / 'workflow-core-failures' / 'APP-REVIEW-01.json'
SUPERVISOR_COPY = 'reports/supervisor-history/workflow-core-APP-REVIEW-01-failure-307fe16d0430.json'


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def append_history(entry: dict) -> None:
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY.open('a') as handle:
        handle.write(json.dumps(entry) + '\n')


def run_apply(db: Path, body: dict) -> tuple[int, dict, str]:
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
        timeout=90,
    )
    stderr = proc.stderr.strip()
    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {'stdout': proc.stdout, 'stderr': stderr}
    if isinstance(payload, dict):
        nested = (payload.get('payload') or {}).get('error')
        if nested:
            return proc.returncode or 1, payload, str(nested)
        if payload.get('error'):
            return proc.returncode or 1, payload, str(payload.get('error'))
    return proc.returncode, payload if isinstance(payload, dict) else {'raw': payload}, stderr


def run_complete(db: Path, claim: dict) -> tuple[int, dict]:
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / 'tools/local_service.py'),
            '--db',
            str(db),
            '--reliability-db',
            str(db),
            'reliability-complete',
        ],
        input=json.dumps(claim),
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=60,
    )
    try:
        return proc.returncode, json.loads(proc.stdout or '{}')
    except json.JSONDecodeError:
        return proc.returncode, {'stdout': proc.stdout, 'stderr': proc.stderr}


def fresh_db(prefix: str) -> Path:
    TEST_ROOT.mkdir(parents=True, exist_ok=True)
    db = TEST_ROOT / f'{prefix}-{DELIVERY}.sqlite'
    if db.exists():
        db.unlink()
    subprocess.run(
        [sys.executable, str(ROOT / 'tools/local_service.py'), '--db', str(db), 'init'],
        check=True,
        capture_output=True,
        cwd=str(ROOT),
    )
    return db


def db_snapshot(db: Path) -> dict:
    conn = sqlite3.connect(db)
    job = conn.execute('SELECT id, revision FROM jobs ORDER BY id').fetchall()
    handoffs = conn.execute(
        'SELECT operation_id, owner, revision FROM reliability_handoffs ORDER BY operation_id'
    ).fetchall()
    ops = conn.execute('SELECT id FROM operations ORDER BY id').fetchall()
    events = conn.execute('SELECT rowid FROM events').fetchone()
    event_count = conn.execute('SELECT COUNT(*) FROM events').fetchone()[0]
    tasks = conn.execute('SELECT id FROM tasks ORDER BY id').fetchall()
    conn.close()
    return {
        'jobs': [{'id': r[0], 'revision': r[1]} for r in job],
        'handoffs': [{'operation_id': r[0], 'owner': r[1], 'revision': r[2]} for r in handoffs],
        'operation_ids': [r[0] for r in ops],
        'event_count': event_count,
        'task_ids': [r[0] for r in tasks],
        'has_events': events is not None,
    }


def count_op_events(db: Path, operation_id: str) -> tuple[int, int]:
    conn = sqlite3.connect(db)
    ops = conn.execute('SELECT COUNT(*) FROM operations WHERE id=?', (operation_id,)).fetchone()[0]
    events = conn.execute(
        "SELECT COUNT(*) FROM events WHERE json_extract(payload, '$.operation_id')=?",
        (operation_id,),
    ).fetchone()[0]
    conn.close()
    return ops, events


def rel02_claim(job_id: str, job_revision: int, proof_path: str, proof_sha: str, **extra) -> dict:
    rel_hash = sha256_file(ROOT / 'data/relationships.json')
    claim = {
        'requirement_id': 'REL-02',
        'complete': True,
        'owner': 'atomic-boundary-acceptance',
        'job_id': job_id,
        'job_revision': job_revision,
        'requirement_set': ['REL-01', 'REL-02', 'REL-03', 'REL-04', 'REL-05', 'REL-06'],
        'evidence': {
            'verified_at': utc_now(),
            'actually_used': 'reliability_gate_per_requirement',
            'documented_path': 'docs/RELIABILITY_ADDENDUM.md',
            'proof_path': proof_path,
            'proof_sha256': proof_sha,
            'skills_verified': True,
            'relationships_sha256': rel_hash,
        },
    }
    claim.update(extra)
    return claim


def _build_ab_declared() -> str:
    sys.path.insert(0, str(ROOT / 'tools'))
    from bounded_acceptance import build_declared_outcome

    return build_declared_outcome('proof-bound', 1, expected_utf8='atomic-boundary-proof-bound-v1\n')


def setup_job(db: Path, job: str, op: str) -> None:
    run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 0,
            'operation_id': 'ab-create',
            'action': 'create',
            'actor_owner': 'owner-a',
            'payload': {
                'goal': 'g',
                'scope': ['l'],
                'constraints': [],
                'owner': 'owner-a',
                'acceptance': ['proof-bound'],
            },
        },
    )
    run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 1,
            'operation_id': 'ab-add',
            'action': 'add_task',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'id': 't1',
                'goal': 'g',
                'owner': 'owner-a',
                'acceptance': ['proof-bound'],
                'deps': [],
                'declared_outcomes': [_build_ab_declared()],
            },
        },
    )


def test_atomic_failures() -> dict:
    cases: dict[str, dict] = {}
    db = fresh_db('atomic')
    job = 'atomic-job'
    op = f'{job}-handoff'
    setup_job(db, job, op)
    run_apply(
        db,
        {
            'action': 'handoff_transfer',
            'operation_id': 'ab-xfer-a-b',
            'actor_owner': 'owner-a',
            'payload': {
                'operation_id': op,
                'expected_owner': 'owner-a',
                'expected_revision': 2,
                'new_owner': 'owner-b',
                'job_revision': 2,
                'job_id': job,
                'acceptance': ['proof-bound'],
            },
        },
    )
    before = db_snapshot(db)
    fail_body = {
        'job_id': job,
        'expected_revision': 1,
        'operation_id': 'ab-fail-cas',
        'action': 'add_task',
        'actor_owner': 'owner-b',
        'handoff_operation_id': op,
        'payload': {'id': 't2', 'goal': 'g', 'owner': 'owner-b', 'acceptance': ['x'], 'deps': []},
    }
    code_fail, res_fail, err_fail = run_apply(db, fail_body)
    after_fail = db_snapshot(db)
    ops_fail, ev_fail = count_op_events(db, 'ab-fail-cas')
    cases['cas_failure_zero_side_effects'] = {
        'exit': code_fail,
        'error': err_fail or res_fail.get('error'),
        'operation_count': ops_fail,
        'matching_event_count': ev_fail,
        'job_revision_unchanged': after_fail['jobs'] == before['jobs'],
        'handoff_unchanged': after_fail['handoffs'] == before['handoffs'],
        'no_new_operations': 'ab-fail-cas' not in after_fail['operation_ids'],
    }

    ok_body = dict(fail_body)
    ok_body['expected_revision'] = 2
    code_rep, _, err_rep = run_apply(db, ok_body)
    code_rep2, _, _ = run_apply(db, ok_body)
    ops_rep, ev_rep = count_op_events(db, 'ab-fail-cas')
    after_rep = db_snapshot(db)
    cases['authorized_retry_once'] = {
        'first_success_exit': code_rep,
        'replay_exit': code_rep2,
        'error': err_rep,
        'operation_count': ops_rep,
        'matching_event_count': ev_rep,
        'handoff_revision': after_rep['handoffs'][0]['revision'] if after_rep['handoffs'] else None,
    }

    db2 = fresh_db('concurrent')
    job2 = 'concurrent-job'
    op2 = f'{job2}-handoff'
    setup_job(db2, job2, op2)
    run_apply(
        db2,
        {
            'action': 'handoff_transfer',
            'operation_id': 'ab-xfer-a-b',
            'actor_owner': 'owner-a',
            'payload': {
                'operation_id': op2,
                'expected_owner': 'owner-a',
                'expected_revision': 2,
                'new_owner': 'owner-b',
                'job_revision': 2,
                'job_id': job2,
                'acceptance': ['proof-bound'],
            },
        },
    )
    snap_before = db_snapshot(db2)
    barrier = threading.Barrier(2)
    results: dict[str, tuple] = {}

    def transfer_thread():
        barrier.wait()
        results['transfer'] = run_apply(
            db2,
            {
                'action': 'handoff_transfer',
                'operation_id': 'ab-xfer-concurrent',
                'actor_owner': 'owner-b',
                'payload': {
                    'operation_id': op2,
                    'expected_owner': 'owner-b',
                    'expected_revision': 2,
                    'new_owner': 'owner-c',
                    'job_revision': 2,
                    'job_id': job2,
                    'acceptance': ['proof-bound'],
                },
            },
        )

    def mutate_thread():
        barrier.wait()
        results['mutate'] = run_apply(
            db2,
            {
                'job_id': job2,
                'expected_revision': 2,
                'operation_id': 'ab-concurrent',
                'action': 'update',
                'actor_owner': 'owner-b',
                'handoff_operation_id': op2,
                'payload': {'task_id': 't1', 'status': 'in_progress', 'attempt': 'race'},
            },
        )

    t1 = threading.Thread(target=transfer_thread)
    t2 = threading.Thread(target=mutate_thread)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    snap_after = db_snapshot(db2)
    ops_conc, ev_conc = count_op_events(db2, 'ab-concurrent')
    transfer_ok = results.get('transfer', (1,))[0] == 0
    mutate_ok = results.get('mutate', (1,))[0] == 0
    mutate_lost = not mutate_ok and transfer_ok
    cases['concurrent_transfer_vs_mutate'] = {
        'transfer_exit': results.get('transfer', (None,))[0],
        'mutate_exit': results.get('mutate', (None,))[0],
        'transfer_error': results.get('transfer', ({}, '', ''))[2],
        'mutate_error': results.get('mutate', ({}, '', ''))[2],
        'exactly_one_succeeded': transfer_ok ^ mutate_ok,
        'mutate_lost_race': mutate_lost,
        'loser_operation_count': ops_conc if mutate_lost else 0,
        'handoff_job_revision_consistent': len(snap_after['jobs']) == 1
        and len(snap_after['handoffs']) == 1
        and abs(snap_after['jobs'][0]['revision'] - snap_after['handoffs'][0]['revision']) <= 1,
        'snapshot_before_event_count': snap_before['event_count'],
        'snapshot_after_event_count': snap_after['event_count'],
    }
    return cases


def test_fixture_boundary() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from reliability_store import connect
    from verification_evidence import (
        ISOLATED_JOB_PREFIX,
        issue_measured_rel02_record,
        issue_measured_workflow_verify_record,
        issue_record,
        measure_rel02_gate_checks,
    )
    from workflow_engine import Engine

    cases: dict[str, dict] = {}
    db = fresh_db('fixture')
    job = 'real-verify-job'
    op = f'{job}-handoff'
    setup_job(db, job, op)

    conn = connect(db)
    fixture = issue_record(
        conn,
        requirement_id='REL-02',
        job_id=job,
        job_revision=2,
        task_id='t1',
        operation_id='wrong-op',
        verifier='wrong-verifier',
        checks=measure_rel02_gate_checks(),
        actually_used='reliability_gate_per_requirement',
        skills_verified=True,
        fixture_only=True,
    )
    conn.close()
    claim = rel02_claim(job, 2, fixture['path'], fixture['record_sha256'])
    code_fv, _, err_fv = run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 2,
            'operation_id': 'ab-verify-fixture',
            'action': 'verify',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'id': 'cp-fixture',
                'task_id': 't1',
                'verifier': 'reviewer-b',
                'requirement_claims': [claim],
                'evidence': [fixture['path']],
                'checks': {'proof-bound': True},
            },
        },
    )
    ops_f, ev_f = count_op_events(db, 'ab-verify-fixture')
    conn = sqlite3.connect(db)
    task_status = json.loads(conn.execute('SELECT payload FROM tasks WHERE id=?', ('t1',)).fetchone()[0]).get(
        'status'
    )
    conn.close()
    cases['reject_fixture_on_real_verify'] = {
        'exit': code_fv,
        'error': err_fv,
        'operation_count': ops_f,
        'task_status': task_status,
        'rejected': code_fv != 0 and task_status != 'verified',
    }

    iso_job = ISOLATED_JOB_PREFIX + 'gate-only'
    conn = connect(db)
    iso_fixture = issue_record(
        conn,
        requirement_id='REL-02',
        job_id=iso_job,
        job_revision=1,
        task_id=None,
        operation_id='iso-op',
        verifier='iso-verifier',
        checks=measure_rel02_gate_checks(),
        actually_used='reliability_gate_per_requirement',
        skills_verified=True,
        fixture_only=True,
    )
    conn.close()
    iso_claim = rel02_claim(
        iso_job,
        1,
        iso_fixture['path'],
        iso_fixture['record_sha256'],
        isolated_test_fixture=True,
    )
    _, gate_iso = run_complete(db, iso_claim)
    cases['isolated_fixture_gate_only'] = {
        'accepted': gate_iso.get('accepted') is True,
        'reason': gate_iso.get('reason'),
    }

    sys.path.insert(0, str(ROOT / 'tools'))
    from bounded_acceptance import bounded_output_descriptor, controlled_materialize_bounded_artifact

    conn_wf = sqlite3.connect(db)
    ab_artifact = controlled_materialize_bounded_artifact(
        conn_wf, job, 't1', 'ab-produce-output', b'atomic-boundary-proof-bound-v1\n'
    )
    conn_wf.close()
    run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 2,
            'operation_id': 'ab-produce-output',
            'action': 'update',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'task_id': 't1',
                'status': 'in_progress',
                'attempt': 'produce',
                'outputs': [bounded_output_descriptor(ab_artifact)],
            },
        },
    )
    conn = connect(db)
    engine = Engine(str(db))
    measured = issue_measured_workflow_verify_record(
        conn,
        engine,
        job_id=job,
        job_revision=3,
        task_id='t1',
        operation_id='ab-verify-good',
        verifier='reviewer-b',
        acceptance=['proof-bound'],
    )
    engine.close()
    conn.close()
    from verification_evidence import PERFORMED_WORK_ACTUALLY_USED

    good_claim = rel02_claim(job, 3, measured['path'], measured['record_sha256'])
    good_claim['evidence']['actually_used'] = PERFORMED_WORK_ACTUALLY_USED
    code_ok, _, err_ok = run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 3,
            'operation_id': 'ab-verify-good',
            'action': 'verify',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'id': 'cp-good',
                'task_id': 't1',
                'verifier': 'reviewer-b',
                'requirement_claims': [good_claim],
                'evidence': [measured['path']],
                'checks': {'proof-bound': True},
            },
        },
    )
    ops_ok, ev_ok = count_op_events(db, 'ab-verify-good')
    cases['measured_positive_verify'] = {
        'exit': code_ok,
        'error': err_ok,
        'operation_count': ops_ok,
        'matching_event_count': ev_ok,
        'accepted': code_ok == 0,
    }

    conn = connect(db)
    wrong_scope = issue_measured_rel02_record(
        conn,
        job_id=job,
        job_revision=2,
        task_id='other-task',
        operation_id='other-op',
        verifier='other-verifier',
    )
    conn.close()
    bad_scope_claim = rel02_claim(job, 2, wrong_scope['path'], wrong_scope['record_sha256'])
    code_ws, _, err_ws = run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 3,
            'operation_id': 'ab-verify-scope',
            'action': 'verify',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'id': 'cp-scope',
                'task_id': 't1',
                'verifier': 'reviewer-b',
                'requirement_claims': [bad_scope_claim],
                'evidence': [wrong_scope['path']],
                'checks': {'proof-bound': True},
            },
        },
    )
    cases['reject_wrong_task_operation_verifier_scope'] = {
        'exit': code_ws,
        'error': err_ws,
        'rejected': code_ws != 0,
    }

    conn = connect(db)
    tampered = issue_measured_rel02_record(
        conn,
        job_id=job,
        job_revision=3,
        task_id='t1',
        operation_id='ab-verify-tamper',
        verifier='reviewer-b',
    )
    conn.close()
    path = ROOT / tampered['path']
    body = json.loads(path.read_text())
    body['checks']['relationships_catalog_present'] = False
    path.write_text(json.dumps(body, indent=2) + '\n')
    tamper_claim = rel02_claim(job, 3, tampered['path'], sha256_file(path))
    code_t, _, err_t = run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 3,
            'operation_id': 'ab-verify-tamper',
            'action': 'verify',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'id': 'cp-tamper',
                'task_id': 't1',
                'verifier': 'reviewer-b',
                'requirement_claims': [tamper_claim],
                'evidence': [tampered['path']],
                'checks': {'proof-bound': True},
            },
        },
    )
    cases['reject_tampered_record_checks'] = {
        'exit': code_t,
        'error': err_t,
        'rejected': code_t != 0,
    }

    return cases


def summarize(atomic: dict, fixture: dict) -> bool:
    a = atomic['cas_failure_zero_side_effects']
    if a['operation_count'] != 0 or not a['no_new_operations']:
        return False
    if not a['job_revision_unchanged'] or not a['handoff_unchanged']:
        return False
    r = atomic['authorized_retry_once']
    if r['operation_count'] != 1 or r['matching_event_count'] != 1:
        return False
    if r['first_success_exit'] != 0 or r['replay_exit'] != 0:
        return False
    c = atomic['concurrent_transfer_vs_mutate']
    if not c['exactly_one_succeeded']:
        return False
    if c.get('mutate_lost_race') and c['loser_operation_count'] > 0:
        return False
    if not c['handoff_job_revision_consistent']:
        return False
    f = fixture['reject_fixture_on_real_verify']
    if not f['rejected'] or f['operation_count'] != 0:
        return False
    if not fixture['measured_positive_verify']['accepted']:
        return False
    if not fixture['reject_wrong_task_operation_verifier_scope']['rejected']:
        return False
    if not fixture['reject_tampered_record_checks']['rejected']:
        return False
    if not fixture['isolated_fixture_gate_only']['accepted']:
        return False
    return True


def main() -> int:
    run_id = str(uuid.uuid4())
    atomic = test_atomic_failures()
    fixture = test_fixture_boundary()
    ok = summarize(atomic, fixture)

    failure_links = []
    if PRIOR_FAILURE.is_file():
        failure_links.append(
            {
                'path': str(PRIOR_FAILURE.relative_to(ROOT)),
                'sha256': sha256_file(PRIOR_FAILURE),
                'supervisor_copy': SUPERVISOR_COPY,
            }
        )

    receipt = {
        'delivery_id': DELIVERY,
        'run_id': run_id,
        'at': utc_now(),
        'owner_chat': '4f32e74a-58e3-4abb-ba6f-fb151ba80cd7',
        'isolated_db_prefix': str(TEST_ROOT / f'*-{DELIVERY}.sqlite'),
        'source_identity': {
            'tools/reliability_store.py': sha256_file(ROOT / 'tools/reliability_store.py'),
            'tools/verification_evidence.py': sha256_file(ROOT / 'tools/verification_evidence.py'),
            'tools/workflow_apply_guard.py': sha256_file(ROOT / 'tools/workflow_apply_guard.py'),
            'tools/atomic_failure_fixture_boundary_acceptance.py': sha256_file(Path(__file__)),
        },
        'atomic_failures': atomic,
        'fixture_boundary': fixture,
        'failure_artifacts_preserved': failure_links,
        'prior_attempt_hashes_linked': failure_links,
        'independent_verification': 'not_claimed',
        'overall': 'passed' if ok else 'partial',
        'queue_remaining_required': [
            'APP-REVIEW-02',
            'APP-REVIEW-04',
            'controlled-edit/CAS/derived',
            'browser/REL-01/synthetic',
            'real SDK BLOCKED',
        ],
    }
    out = REPORTS / 'atomic-failure-fixture-boundary-receipt.json'
    out.write_text(json.dumps(receipt, indent=2) + '\n')
    append_history(
        {
            'delivery_id': DELIVERY,
            'run_id': run_id,
            'at': receipt['at'],
            'overall': receipt['overall'],
            'receipt_sha256': sha256_file(out),
        }
    )
    if not ok:
        fail_path = REPORTS / 'workflow-core-failures' / f'{DELIVERY}-{run_id[:8]}.json'
        fail_path.parent.mkdir(parents=True, exist_ok=True)
        fail_path.write_text(json.dumps({'atomic': atomic, 'fixture': fixture}, indent=2) + '\n')
        failure_links.append({'path': str(fail_path.relative_to(ROOT)), 'sha256': sha256_file(fail_path)})
        receipt['failure_artifacts_preserved'] = failure_links
        out.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'overall': receipt['overall'], 'delivery_id': DELIVERY}, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
