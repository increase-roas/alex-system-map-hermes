#!/usr/bin/env python3
"""Delivery outcome-replay-rollback-20261010-0631."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
RUN_RECEIPTS = REPORTS / 'run-receipts'
TEST_ROOT = ROOT / 'app' / '.data' / 'workflow-core-tests'
DELIVERY = 'outcome-replay-rollback-20261010-0631'
HISTORY = REPORTS / 'workflow-core-run-history.jsonl'
SUPERVISOR_COPY = 'reports/supervisor-history/workflow-core-APP-REVIEW-01-failure-307fe16d0430.json'
PRIOR_FAILURE = REPORTS / 'workflow-core-failures' / 'APP-REVIEW-01.json'

SOURCE_MODULES = (
    'tools/workflow_engine.py',
    'tools/reliability_gate.py',
    'tools/local_service.py',
    'tools/reliability_store.py',
    'tools/workflow_apply_guard.py',
    'tools/verification_evidence.py',
    'tools/outcome_replay_rollback_acceptance.py',
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_identities() -> dict[str, str]:
    return {p: sha256_file(ROOT / p) for p in SOURCE_MODULES if (ROOT / p).is_file()}


def append_history(entry: dict) -> None:
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY.open('a') as handle:
        handle.write(json.dumps(entry) + '\n')


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


def db_state(db: Path) -> dict:
    conn = sqlite3.connect(db)
    jobs = conn.execute('SELECT id, revision FROM jobs ORDER BY id').fetchall()
    handoffs = conn.execute(
        'SELECT operation_id, owner, revision, checkpoint_json FROM reliability_handoffs ORDER BY operation_id'
    ).fetchall()
    ops = [r[0] for r in conn.execute('SELECT id FROM operations ORDER BY id').fetchall()]
    events = conn.execute('SELECT COUNT(*) FROM events').fetchone()[0]
    tasks = {}
    for row in conn.execute('SELECT id, payload FROM tasks').fetchall():
        tasks[row[0]] = json.loads(row[1])
    conn.close()
    return {
        'jobs': [{'id': j, 'revision': r} for j, r in jobs],
        'handoffs': [
            {
                'operation_id': h[0],
                'owner': h[1],
                'revision': h[2],
                'acceptance': json.loads(h[3]).get('acceptance'),
            }
            for h in handoffs
        ],
        'operation_ids': ops,
        'event_count': events,
        'tasks': {k: {'status': v.get('status'), 'outputs': v.get('outputs')} for k, v in tasks.items()},
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


def run_apply(db: Path, body: dict, *, env: dict | None = None) -> tuple[int, dict, str]:
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
        env=env or os.environ.copy(),
    )
    stderr = proc.stderr.strip()
    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {'stdout': proc.stdout, 'stderr': stderr}
    nested = (payload.get('payload') or {}).get('error')
    if nested:
        return proc.returncode or 1, payload, str(nested)
    if isinstance(payload, dict) and payload.get('error'):
        return proc.returncode or 1, payload, str(payload.get('error'))
    return proc.returncode, payload if isinstance(payload, dict) else {'raw': payload}, stderr


def _orr_declared() -> str:
    sys.path.insert(0, str(ROOT / 'tools'))
    from bounded_acceptance import build_declared_outcome

    return build_declared_outcome('proof-bound', 1, expected_utf8='outcome-replay-proof-bound-v1\n')


def setup_job(db: Path, job: str, op: str) -> None:
    run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 0,
            'operation_id': 'orr-create',
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
            'operation_id': 'orr-add',
            'action': 'add_task',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'id': 't1',
                'goal': 'g',
                'owner': 'owner-a',
                'acceptance': ['proof-bound'],
                'deps': [],
                'declared_outcomes': [_orr_declared()],
            },
        },
    )


def test_post_write_cas_rollback() -> dict:
    db = fresh_db('post-write-cas')
    proof_dir = REPORTS / 'outcome-replay-rollback-proofs' / str(uuid.uuid4())
    proof_dir.mkdir(parents=True, exist_ok=True)
    job = 'post-write-job'
    op = f'{job}-handoff'
    setup_job(db, job, op)
    run_apply(
        db,
        {
            'action': 'handoff_transfer',
            'operation_id': 'orr-xfer-b',
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
    before_path = proof_dir / 'before-failed-attempt.sqlite'
    shutil.copy2(db, before_path)
    before = db_state(db)
    fail_op = 'orr-post-write-fail'
    fail_body = {
        'job_id': job,
        'expected_revision': 2,
        'operation_id': fail_op,
        'action': 'add_task',
        'actor_owner': 'owner-b',
        'handoff_operation_id': op,
        'payload': {'id': 't2', 'goal': 'g', 'owner': 'owner-b', 'acceptance': ['x'], 'deps': []},
    }
    env = os.environ.copy()
    env['AGENT_WF_TEST_CAS_FAIL'] = '1'
    env['AGENT_WF_TEST_CAS_FAIL_OP'] = fail_op
    code_fail, _, err_fail = run_apply(db, fail_body, env=env)
    after_fail_path = proof_dir / 'after-failed-attempt.sqlite'
    shutil.copy2(db, after_fail_path)
    after_fail = db_state(db)
    ops_fail, ev_fail = count_op_events(db, fail_op)
    ok_body = dict(fail_body)
    env_ok = os.environ.copy()
    env_ok.pop('AGENT_WF_TEST_CAS_FAIL', None)
    env_ok.pop('AGENT_WF_TEST_CAS_FAIL_OP', None)
    code_ok, _, _ = run_apply(db, ok_body, env=env_ok)
    code_rep, _, _ = run_apply(db, ok_body, env=env_ok)
    ops_final, ev_final = count_op_events(db, fail_op)
    return {
        'before_snapshot_sha256': sha256_file(before_path),
        'after_failed_snapshot_sha256': sha256_file(after_fail_path),
        'before_state': before,
        'after_failed_state': after_fail,
        'failed_exit': code_fail,
        'failed_error': err_fail,
        'failed_operation_count': ops_fail,
        'failed_matching_event_count': ev_fail,
        'state_unchanged_after_fail': before == after_fail,
        'authorized_first_success_exit': code_ok,
        'replay_exit': code_rep,
        'final_operation_count': ops_final,
        'final_matching_event_count': ev_final,
        'proof_paths': {
            'before': str(before_path.relative_to(ROOT)),
            'after_failed': str(after_fail_path.relative_to(ROOT)),
        },
    }


def test_historical_replay() -> dict:
    db = fresh_db('historical-replay')
    job = 'replay-job'
    op = f'{job}-handoff'
    setup_job(db, job, op)
    early = {
        'job_id': job,
        'expected_revision': 2,
        'operation_id': 'orr-early-update',
        'action': 'update',
        'actor_owner': 'owner-a',
        'handoff_operation_id': op,
        'payload': {
            'task_id': 't1',
            'status': 'in_progress',
            'attempt': 'early',
            'outputs': ['early-artifact.txt'],
        },
    }
    run_apply(db, early)
    mid = {
        'action': 'handoff_transfer',
        'operation_id': 'orr-xfer-b',
        'actor_owner': 'owner-a',
        'payload': {
            'operation_id': op,
            'expected_owner': 'owner-a',
            'expected_revision': 3,
            'new_owner': 'owner-b',
            'job_revision': 3,
            'job_id': job,
            'acceptance': ['proof-bound'],
        },
    }
    run_apply(db, mid)
    late = {
        'job_id': job,
        'expected_revision': 3,
        'operation_id': 'orr-late-update',
        'action': 'update',
        'actor_owner': 'owner-b',
        'handoff_operation_id': op,
        'payload': {
            'task_id': 't1',
            'status': 'in_progress',
            'attempt': 'late',
            'outputs': ['late-artifact.txt'],
        },
    }
    run_apply(db, late)
    run_apply(
        db,
        {
            'action': 'handoff_transfer',
            'operation_id': 'orr-xfer-c',
            'actor_owner': 'owner-b',
            'payload': {
                'operation_id': op,
                'expected_owner': 'owner-b',
                'expected_revision': 4,
                'new_owner': 'owner-c',
                'job_revision': 4,
                'job_id': job,
                'acceptance': ['proof-bound'],
            },
        },
    )
    run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 4,
            'operation_id': 'orr-progress',
            'action': 'update',
            'actor_owner': 'owner-c',
            'handoff_operation_id': op,
            'payload': {
                'task_id': 't1',
                'status': 'in_progress',
                'attempt': 'progress',
                'outputs': ['progress-artifact.txt'],
            },
        },
    )
    before = db_state(db)
    replay_owner_a = dict(early)
    replay_owner_a['actor_owner'] = 'owner-a'
    code_rep, res_rep, err_rep = run_apply(db, replay_owner_a)
    after = db_state(db)
    return {
        'replay_exit': code_rep,
        'replay_error': err_rep,
        'stored_revision': res_rep.get('revision') if isinstance(res_rep, dict) else None,
        'handoff_before': before['handoffs'],
        'handoff_after': after['handoffs'],
        'handoff_unchanged': before['handoffs'] == after['handoffs'],
        'job_revision_unchanged': before['jobs'] == after['jobs'],
    }


def test_transfer_idempotency() -> dict:
    db = fresh_db('transfer-idem')
    job = 'transfer-job'
    op = f'{job}-handoff'
    setup_job(db, job, op)
    xfer = {
        'action': 'handoff_transfer',
        'operation_id': 'orr-transfer-attempt-1',
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
    }
    code1, res1, _ = run_apply(db, xfer)
    code2, res2, _ = run_apply(db, xfer)
    xfer_bad = dict(xfer)
    xfer_bad['payload'] = dict(xfer['payload'])
    xfer_bad['payload']['new_owner'] = 'owner-c'
    code3, _, err3 = run_apply(db, xfer_bad)
    conn = sqlite3.connect(db)
    xfer_rows = conn.execute('SELECT COUNT(*) FROM reliability_transfer_operations').fetchone()[0]
    handoff = conn.execute(
        'SELECT owner, revision FROM reliability_handoffs WHERE operation_id=?', (op,)
    ).fetchone()
    conn.close()
    return {
        'first_exit': code1,
        'retry_exit': code2,
        'retry_same_result': res1 == res2,
        'collision_exit': code3,
        'collision_error': err3,
        'transfer_ledger_rows': xfer_rows,
        'final_handoff_owner': handoff[0] if handoff else None,
        'final_handoff_revision': handoff[1] if handoff else None,
    }


def test_truthful_outcomes() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from reliability_store import connect
    from verification_evidence import (
        PERFORMED_WORK_ACTUALLY_USED,
        issue_measured_workflow_verify_record,
        measure_workflow_verify_checks,
    )
    from workflow_engine import Engine

    db = fresh_db('truthful-outcomes')
    job = 'truth-job'
    op = f'{job}-handoff'
    setup_job(db, job, op)
    engine = Engine(str(db))
    pending_checks = measure_workflow_verify_checks(engine, job, 't1', ['proof-bound'])
    engine.close()
    pending_issue_failed = False
    try:
        conn = connect(db)
        issue_measured_workflow_verify_record(
            conn,
            Engine(str(db)),
            job_id=job,
            job_revision=2,
            task_id='t1',
            operation_id='orr-should-not-issue',
            verifier='reviewer-b',
            acceptance=['proof-bound'],
        )
        conn.close()
    except ValueError:
        pending_issue_failed = True
    from bounded_acceptance import bounded_output_descriptor, controlled_materialize_bounded_artifact

    conn_wf = sqlite3.connect(db)
    orr_artifact = controlled_materialize_bounded_artifact(
        conn_wf, job, 't1', 'orr-produce-output', b'outcome-replay-proof-bound-v1\n'
    )
    conn_wf.close()
    run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 2,
            'operation_id': 'orr-produce-output',
            'action': 'update',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'task_id': 't1',
                'status': 'in_progress',
                'attempt': 'produce',
                'outputs': [bounded_output_descriptor(orr_artifact)],
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
        operation_id='orr-verify-good',
        verifier='reviewer-b',
        acceptance=['proof-bound'],
    )
    engine.close()
    conn.close()
    rel_hash = sha256_file(ROOT / 'data/relationships.json')
    base_claim = {
        'requirement_id': 'REL-02',
        'complete': True,
        'owner': 'outcome-acceptance',
        'job_id': job,
        'job_revision': 3,
        'requirement_set': ['REL-01', 'REL-02', 'REL-03', 'REL-04', 'REL-05', 'REL-06'],
        'evidence': {
            'verified_at': utc_now(),
            'actually_used': PERFORMED_WORK_ACTUALLY_USED,
            'documented_path': 'docs/RELIABILITY_ADDENDUM.md',
            'proof_path': measured['path'],
            'proof_sha256': measured['record_sha256'],
            'skills_verified': True,
            'relationships_sha256': rel_hash,
        },
    }

    def verify_with_claim(claim: dict, operation_id: str) -> tuple[int, dict, str]:
        return run_apply(
            db,
            {
                'job_id': job,
                'expected_revision': 3,
                'operation_id': operation_id,
                'action': 'verify',
                'actor_owner': 'owner-a',
                'handoff_operation_id': op,
                'payload': {
                    'id': f'cp-{operation_id}',
                    'task_id': 't1',
                    'verifier': 'reviewer-b',
                    'requirement_claims': [claim],
                    'evidence': [claim['evidence']['proof_path']],
                    'checks': {'proof-bound': True},
                },
            },
        )

    code_ok, _, _ = verify_with_claim(base_claim, 'orr-verify-good')
    wrong_task = dict(base_claim)
    wrong_task['evidence'] = dict(base_claim['evidence'])
    conn = connect(db)
    wrong_task_rec = issue_measured_workflow_verify_record(
        conn,
        Engine(str(db)),
        job_id=job,
        job_revision=3,
        task_id='t1',
        operation_id='orr-wrong-task-rec',
        verifier='reviewer-b',
        acceptance=['proof-bound'],
    )
    conn.close()
    wrong_task_claim = dict(base_claim)
    wrong_task_claim['evidence'] = dict(base_claim['evidence'])
    wrong_task_claim['evidence']['proof_path'] = wrong_task_rec['path']
    wrong_task_claim['evidence']['proof_sha256'] = wrong_task_rec['record_sha256']
    code_wt, _, err_wt = run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 3,
            'operation_id': 'orr-wrong-task',
            'action': 'verify',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'id': 'cp-wt',
                'task_id': 't-other',
                'verifier': 'reviewer-b',
                'requirement_claims': [wrong_task_claim],
                'evidence': [wrong_task_claim['evidence']['proof_path']],
                'checks': {'proof-bound': True},
            },
        },
    )
    conn = connect(db)
    wrong_op_rec = issue_measured_workflow_verify_record(
        conn,
        Engine(str(db)),
        job_id=job,
        job_revision=3,
        task_id='t1',
        operation_id='orr-wrong-op-record',
        verifier='reviewer-b',
        acceptance=['proof-bound'],
    )
    conn.close()
    wrong_op_claim = dict(base_claim)
    wrong_op_claim['evidence'] = dict(base_claim['evidence'])
    wrong_op_claim['evidence']['proof_path'] = wrong_op_rec['path']
    wrong_op_claim['evidence']['proof_sha256'] = wrong_op_rec['record_sha256']
    code_wo, _, err_wo = run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 3,
            'operation_id': 'orr-wrong-op-record',
            'action': 'verify',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'id': 'cp-wo',
                'task_id': 't1',
                'verifier': 'reviewer-b',
                'requirement_claims': [wrong_op_claim],
                'evidence': [wrong_op_rec['path']],
                'checks': {'proof-bound': True},
            },
        },
    )
    code_wv, _, err_wv = run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 3,
            'operation_id': 'orr-verify-good',
            'action': 'verify',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'id': 'cp-wv',
                'task_id': 't1',
                'verifier': 'wrong-verifier',
                'requirement_claims': [base_claim],
                'evidence': [measured['path']],
                'checks': {'proof-bound': True},
            },
        },
    )
    return {
        'pending_without_output_issue_failed': pending_issue_failed,
        'pending_checks': pending_checks,
        'positive_verify_exit': code_ok,
        'wrong_task_rejected': code_wt != 0,
        'wrong_task_reason': err_wt,
        'wrong_operation_rejected': code_wo != 0,
        'wrong_operation_reason': err_wo,
        'wrong_verifier_rejected': code_wv != 0,
        'wrong_verifier_reason': err_wv,
        'measured_record_checks': measured.get('body', {}).get('checks'),
    }


def summarize(cases: dict) -> bool:
    p = cases['post_write_cas']
    if not p['state_unchanged_after_fail'] or p['failed_operation_count'] != 0:
        return False
    if p['authorized_first_success_exit'] != 0 or p['final_operation_count'] != 1:
        return False
    if p['final_matching_event_count'] != 1 or p['replay_exit'] != 0:
        return False
    h = cases['historical_replay']
    if not h['handoff_unchanged'] or not h['job_revision_unchanged'] or h['replay_exit'] != 0:
        return False
    t = cases['transfer_idempotency']
    if t['first_exit'] != 0 or t['retry_exit'] != 0 or not t['retry_same_result']:
        return False
    if t['collision_exit'] == 0 or t['transfer_ledger_rows'] != 1 or t['final_handoff_owner'] != 'owner-b':
        return False
    o = cases['truthful_outcomes']
    if not o['pending_without_output_issue_failed'] or o['positive_verify_exit'] != 0:
        return False
    if not o['wrong_task_rejected'] or not o['wrong_operation_rejected'] or not o['wrong_verifier_rejected']:
        return False
    return True


def main() -> int:
    run_id = str(uuid.uuid4())
    cases = {
        'post_write_cas': test_post_write_cas_rollback(),
        'historical_replay': test_historical_replay(),
        'transfer_idempotency': test_transfer_idempotency(),
        'truthful_outcomes': test_truthful_outcomes(),
    }
    ok = summarize(cases)
    failure_links = []
    if PRIOR_FAILURE.is_file():
        failure_links.append(
            {
                'path': str(PRIOR_FAILURE.relative_to(ROOT)),
                'sha256': sha256_file(PRIOR_FAILURE),
                'supervisor_copy': SUPERVISOR_COPY,
            }
        )
    supervisor_path = ROOT / SUPERVISOR_COPY
    if supervisor_path.is_file():
        failure_links.append(
            {
                'path': SUPERVISOR_COPY,
                'sha256': sha256_file(supervisor_path),
                'note': 'immutable supervisor snapshot preserved',
            }
        )

    receipt = {
        'delivery_id': DELIVERY,
        'run_id': run_id,
        'at': utc_now(),
        'owner_chat': '4f32e74a-58e3-4abb-ba6f-fb151ba80cd7',
        'source_identity': source_identities(),
        'cases': cases,
        'failure_artifacts_preserved': failure_links,
        'prior_attempt_hashes_linked': failure_links,
        'independent_verification': 'not_claimed',
        'overall': 'passed' if ok else 'partial',
        'still_open_for_independent': [
            'APP-REVIEW-02 recovery UI',
            'APP-REVIEW-04 screening',
            'controlled-edit/CAS/derived views',
            'browser/REL-01/synthetic full queue',
            'real SDK traces BLOCKED',
        ],
    }
    if not ok:
        fail_path = REPORTS / 'workflow-core-failures' / f'{DELIVERY}-{run_id[:8]}.json'
        fail_path.write_text(json.dumps(cases, indent=2) + '\n')
        failure_links.append({'path': str(fail_path.relative_to(ROOT)), 'sha256': sha256_file(fail_path)})
        receipt['failure_artifacts_preserved'] = failure_links

    sys.path.insert(0, str(ROOT / 'tools'))
    from receipt_immutable import append_manifest, write_final_receipt_once

    RUN_RECEIPTS.mkdir(parents=True, exist_ok=True)
    MANIFEST = REPORTS / 'receipt-hash-manifest.jsonl'
    immutable_path = RUN_RECEIPTS / f'{DELIVERY}-{run_id}.json'
    _, content_sha256 = write_final_receipt_once(immutable_path, receipt)
    pointer = {
        'delivery_id': DELIVERY,
        'run_id': run_id,
        'immutable_receipt_path': str(immutable_path.relative_to(ROOT)),
        'content_sha256': content_sha256,
    }
    append_manifest(MANIFEST, pointer)
    canonical_path = REPORTS / 'outcome-replay-rollback-receipt.json'
    canonical_path.write_text(json.dumps(pointer, indent=2) + '\n')
    append_history(
        {
            'delivery_id': DELIVERY,
            'run_id': run_id,
            'at': receipt['at'],
            'overall': receipt['overall'],
            'immutable_receipt': str(immutable_path.relative_to(ROOT)),
            'content_sha256': content_sha256,
        }
    )
    print(json.dumps({'overall': receipt['overall'], 'delivery_id': DELIVERY, 'run_id': run_id}, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
