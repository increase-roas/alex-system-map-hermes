#!/usr/bin/env python3
"""Delivery core-evidence-transactions-20261010-0613 — APP-REVIEW-01/03."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
TEST_ROOT = ROOT / 'app' / '.data' / 'workflow-core-tests'
DELIVERY = 'core-evidence-transactions-20261010-0613'
REL_IDS = ['REL-01', 'REL-02', 'REL-03', 'REL-04', 'REL-05', 'REL-06']
HISTORY = REPORTS / 'workflow-core-run-history.jsonl'
PRIOR_FAILURE = REPORTS / 'workflow-core-failures' / 'APP-REVIEW-01.json'


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
    if isinstance(payload, dict) and payload.get('payload', {}).get('error'):
        err = payload['payload']['error']
        return proc.returncode or 1, {'error': err}, err
    if isinstance(payload, dict) and payload.get('error'):
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
    db = TEST_ROOT / f'{prefix}-unified.sqlite'
    if db.exists():
        db.unlink()
    subprocess.run(
        [sys.executable, str(ROOT / 'tools/local_service.py'), '--db', str(db), 'init'],
        check=True,
        capture_output=True,
        cwd=str(ROOT),
    )
    return db


def issue_fixture_record(db: Path, job_id: str, job_revision: int, task_id: str, operation_id: str) -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from reliability_store import connect
    from verification_evidence import issue_measured_rel02_record, issue_measured_workflow_verify_record
    from workflow_engine import Engine

    conn = connect(db)
    if job_id.startswith('isolated-'):
        issued = issue_measured_rel02_record(
            conn,
            job_id=job_id,
            job_revision=job_revision,
            task_id=task_id,
            operation_id=operation_id,
            verifier='workflow-core-fixture',
            fixture_only=True,
            max_age_seconds=3600,
        )
    else:
        engine = Engine(str(db))
        issued = issue_measured_workflow_verify_record(
            conn,
            engine,
            job_id=job_id,
            job_revision=job_revision,
            task_id=task_id,
            operation_id=operation_id,
            verifier='reviewer-b',
            acceptance=['proof-bound'],
        )
        engine.close()
    conn.close()
    return issued


def rel02_claim(job_id: str, job_revision: int, proof_path: str, proof_sha: str, **extra) -> dict:
    rel_hash = sha256_file(ROOT / 'data/relationships.json')
    claim = {
        'requirement_id': 'REL-02',
        'complete': True,
        'owner': 'workflow-core-acceptance',
        'job_id': job_id,
        'job_revision': job_revision,
        'requirement_set': REL_IDS,
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


def count_op_events(db: Path, operation_id: str) -> tuple[int, int]:
    conn = sqlite3.connect(db)
    ops = conn.execute('SELECT COUNT(*) FROM operations WHERE id=?', (operation_id,)).fetchone()[0]
    events = conn.execute(
        "SELECT COUNT(*) FROM events WHERE json_extract(payload, '$.operation_id')=?",
        (operation_id,),
    ).fetchone()[0]
    conn.close()
    return ops, events


def test_evidence_counterexamples() -> dict:
    db = fresh_db('evidence-neg')
    issued = issue_fixture_record(db, 'isolated-job-a', 2, 't1', 'op-verify')
    cases: dict[str, dict] = {}

    trace = ROOT / 'examples/agent-trace-fixture.json'
    bad_trace = rel02_claim('isolated-job-a', 2, str(trace.relative_to(ROOT)), sha256_file(trace))
    code, gate = run_complete(db, bad_trace)
    cases['reject_unrelated_trace_fixture'] = {
        'exit': code,
        'rejected': not gate.get('accepted'),
        'reason': gate.get('reason'),
    }

    from datetime import timedelta
    from reliability_store import connect
    from verification_evidence import issue_measured_rel02_record

    future_obs = datetime.now(timezone.utc) + timedelta(days=30)
    future_issued = issue_measured_rel02_record(
        connect(db),
        job_id='isolated-job-a',
        job_revision=2,
        task_id='t1',
        operation_id='future-op',
        verifier='workflow-core-fixture',
        fixture_only=True,
        observed_at=future_obs,
    )
    bad_future = rel02_claim(
        'isolated-job-a', 2, future_issued['path'], future_issued['record_sha256'], isolated_test_fixture=True
    )
    _, gate_f = run_complete(db, bad_future)
    cases['reject_future_via_record_validation'] = {
        'rejected': not gate_f.get('accepted'),
        'reason': gate_f.get('reason'),
    }

    old_obs = datetime.now(timezone.utc) - timedelta(days=30)
    stale_issued = issue_measured_rel02_record(
        connect(db),
        job_id='isolated-job-a',
        job_revision=2,
        task_id='t1',
        operation_id='stale-op',
        verifier='workflow-core-fixture',
        fixture_only=True,
        max_age_seconds=3600,
        observed_at=old_obs,
    )
    bad_jan = rel02_claim(
        'isolated-job-a', 2, stale_issued['path'], stale_issued['record_sha256'], isolated_test_fixture=True
    )
    _, gate_j = run_complete(db, bad_jan)
    cases['reject_stale_observed_via_max_age'] = {
        'rejected': not gate_j.get('accepted'),
        'reason': gate_j.get('reason'),
    }

    wrong_scope = rel02_claim('other-job', 99, issued['path'], issued['record_sha256'])
    _, gate_w = run_complete(db, wrong_scope)
    cases['reject_wrong_job_revision_scope'] = {
        'rejected': not gate_w.get('accepted'),
        'reason': gate_w.get('reason'),
    }

    good = rel02_claim(
        'isolated-job-a', 2, issued['path'], issued['record_sha256'], isolated_test_fixture=True
    )
    _, gate_ok = run_complete(db, good)
    cases['fixture_positive_control'] = {'accepted': gate_ok.get('accepted') is True, 'reason': gate_ok.get('reason')}

    wf = fresh_db('evidence-verify')
    job = 'evidence-verify-job'
    sys.path.insert(0, str(ROOT / 'tools'))
    from bounded_acceptance import build_declared_outcome

    ev_declared = build_declared_outcome(
        'proof-bound', 1, expected_utf8='core-evidence-proof-bound-v1\n'
    )
    run_apply(
        wf,
        {
            'job_id': job,
            'expected_revision': 0,
            'operation_id': 'ev-create',
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
        wf,
        {
            'job_id': job,
            'expected_revision': 1,
            'operation_id': 'ev-add',
            'action': 'add_task',
            'actor_owner': 'owner-a',
            'handoff_operation_id': f'{job}-handoff',
            'payload': {
                'id': 't1',
                'goal': 'g',
                'owner': 'owner-a',
                'acceptance': ['proof-bound'],
                'deps': [],
                'declared_outcomes': [ev_declared],
            },
        },
    )
    sys.path.insert(0, str(ROOT / 'tools'))
    from bounded_acceptance import bounded_output_descriptor, controlled_materialize_bounded_artifact

    conn_wf = sqlite3.connect(wf)
    ev_artifact = controlled_materialize_bounded_artifact(
        conn_wf, job, 't1', 'ev-produce', b'core-evidence-proof-bound-v1\n'
    )
    conn_wf.close()
    run_apply(
        wf,
        {
            'job_id': job,
            'expected_revision': 2,
            'operation_id': 'ev-produce',
            'action': 'update',
            'actor_owner': 'owner-a',
            'handoff_operation_id': f'{job}-handoff',
            'payload': {
                'task_id': 't1',
                'status': 'in_progress',
                'attempt': 'produce',
                'outputs': [bounded_output_descriptor(ev_artifact)],
            },
        },
    )
    issued2 = issue_fixture_record(wf, job, 3, 't1', 'ev-verify')
    claim = rel02_claim(job, 3, issued2['path'], issued2['record_sha256'])
    from verification_evidence import PERFORMED_WORK_ACTUALLY_USED

    claim['evidence']['actually_used'] = PERFORMED_WORK_ACTUALLY_USED
    code_v, res_v, err_v = run_apply(
        wf,
        {
            'job_id': job,
            'expected_revision': 3,
            'operation_id': 'ev-verify',
            'action': 'verify',
            'actor_owner': 'owner-a',
            'handoff_operation_id': f'{job}-handoff',
            'payload': {
                'id': 'cp1',
                'task_id': 't1',
                'verifier': 'reviewer-b',
                'requirement_claims': [claim],
                'evidence': [issued2['path']],
                'checks': {'proof-bound': True},
            },
        },
    )
    ops, evs = count_op_events(wf, 'ev-verify')
    cases['verify_handler_with_issued_record'] = {
        'exit': code_v,
        'accepted': code_v == 0 and not res_v.get('error'),
        'operation_count': ops,
        'matching_event_count': evs,
        'error': err_v or res_v.get('error'),
    }
    return cases


def test_transaction_counterexamples() -> dict:
    cases: dict[str, dict] = {}
    db = fresh_db('txn-handoff')
    job = 'txn-job'
    op = f'{job}-handoff'
    run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 0,
            'operation_id': 'txn-create',
            'action': 'create',
            'actor_owner': 'owner-a',
            'payload': {
                'goal': 'g',
                'scope': ['l'],
                'constraints': [],
                'owner': 'owner-a',
                'acceptance': ['check'],
            },
        },
    )
    run_apply(
        db,
        {
            'action': 'handoff_transfer',
            'operation_id': 'core-xfer-a-b',
            'actor_owner': 'owner-a',
            'payload': {
                'operation_id': op,
                'expected_owner': 'owner-a',
                'expected_revision': 1,
                'new_owner': 'owner-b',
                'job_revision': 1,
                'job_id': job,
                'acceptance': ['check'],
            },
        },
    )

    code_intr, res_intr, err_intr = run_apply(
        db,
        {
            'action': 'handoff_transfer',
            'operation_id': 'core-xfer-intruder',
            'actor_owner': 'intruder',
            'payload': {
                'operation_id': op,
                'expected_owner': 'owner-a',
                'expected_revision': 1,
                'new_owner': 'owner-c',
                'job_revision': 1,
                'job_id': job,
            },
        },
    )
    cases['reject_intruder_transfer_actor'] = {'exit': code_intr, 'rejected': code_intr != 0, 'error': err_intr}

    foreign_op = 'foreign-checkpoint-op'
    conn = sqlite3.connect(db)
    from reliability_store import connect, record_handoff

    rconn = connect(db)
    record_handoff(rconn, foreign_op, 'owner-b', 1, {'job_id': 'other-job', 'acceptance': ['x']})
    rconn.close()
    code_fop, _, err_fop = run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 1,
            'operation_id': 'txn-add',
            'action': 'add_task',
            'actor_owner': 'owner-b',
            'handoff_operation_id': foreign_op,
            'payload': {'id': 't1', 'goal': 'g', 'owner': 'owner-b', 'acceptance': ['check'], 'deps': []},
        },
    )
    cases['reject_foreign_handoff_operation'] = {'exit': code_fop, 'rejected': code_fop != 0, 'error': err_fop}
    conn.close()

    add_body = {
        'job_id': job,
        'expected_revision': 1,
        'operation_id': 'txn-op1',
        'action': 'add_task',
        'actor_owner': 'owner-b',
        'handoff_operation_id': op,
        'payload': {'id': 't1', 'goal': 'g', 'owner': 'owner-b', 'acceptance': ['check'], 'deps': []},
    }
    stale_add = dict(add_body)
    stale_add['expected_revision'] = 0
    code_fail, _, err_fail = run_apply(db, stale_add)
    ops_after_fail, _ = count_op_events(db, 'txn-op1')
    conn = sqlite3.connect(db)
    handoff_rev = conn.execute(
        'SELECT revision FROM reliability_handoffs WHERE operation_id=?', (op,)
    ).fetchone()[0]
    job_rev = conn.execute('SELECT revision FROM jobs WHERE id=?', (job,)).fetchone()[0]
    conn.close()
    cases['failed_mutation_zero_side_effects'] = {
        'exit': code_fail,
        'operation_count_after_fail': ops_after_fail,
        'handoff_revision_after_fail': handoff_rev,
        'job_revision_after_fail': job_rev,
        'error': err_fail,
    }

    code_rep, res_rep, err_rep = run_apply(db, add_body)
    code_rep2, _, _ = run_apply(db, add_body)
    ops_final, ev_final = count_op_events(db, 'txn-op1')
    conn = sqlite3.connect(db)
    handoff_rev2 = conn.execute(
        'SELECT revision, owner FROM reliability_handoffs WHERE operation_id=?', (op,)
    ).fetchone()
    acc = json.loads(
        conn.execute('SELECT checkpoint_json FROM reliability_handoffs WHERE operation_id=?', (op,)).fetchone()[0]
    ).get('acceptance')
    conn.close()
    cases['replay_after_fail_succeeds_once'] = {
        'first_success_exit': code_rep,
        'replay_exit': code_rep2,
        'operation_count': ops_final,
        'matching_event_count': ev_final,
        'handoff_owner': handoff_rev2[1] if handoff_rev2 else None,
        'acceptance_retained': acc,
        'error': err_rep or res_rep.get('error'),
    }

    barrier = threading.Barrier(2)
    results: dict[str, tuple] = {}

    def transfer_thread():
        barrier.wait()
        results['transfer'] = run_apply(
            db,
            {
                'action': 'handoff_transfer',
                'operation_id': 'core-xfer-concurrent',
                'actor_owner': 'owner-b',
                'payload': {
                    'operation_id': op,
                    'expected_owner': 'owner-b',
                    'expected_revision': handoff_rev2[0] if handoff_rev2 else 2,
                    'new_owner': 'owner-c',
                    'job_revision': 2,
                    'job_id': job,
                    'acceptance': ['check'],
                },
            },
        )

    def mutate_thread():
        barrier.wait()
        results['mutate'] = run_apply(
            db,
            {
                'job_id': job,
                'expected_revision': 2,
                'operation_id': 'txn-concurrent',
                'action': 'update',
                'actor_owner': 'owner-b',
                'handoff_operation_id': op,
                'payload': {'task_id': 't1', 'status': 'in_progress', 'attempt': 'concurrent'},
            },
        )

    t1 = threading.Thread(target=transfer_thread)
    t2 = threading.Thread(target=mutate_thread)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    ops_conc, _ = count_op_events(db, 'txn-concurrent')
    transfer_ok = results.get('transfer', (1,))[0] == 0
    mutate_ok = results.get('mutate', (1,))[0] == 0
    mutate_lost = not mutate_ok and transfer_ok
    cases['concurrent_transfer_vs_mutate'] = {
        'transfer': {'exit': results.get('transfer', (None,))[0], 'error': results.get('transfer', ({}, '', ''))[2]},
        'mutate': {'exit': results.get('mutate', (None,))[0], 'error': results.get('mutate', ({}, '', ''))[2]},
        'one_succeeded': transfer_ok ^ mutate_ok,
        'mutate_lost_race': mutate_lost,
        'loser_operation_count': ops_conc if mutate_lost else 0,
    }
    return cases


def summarize(evidence: dict, txn: dict) -> bool:
    e_ok = all(
        evidence[k].get('rejected') or evidence[k].get('accepted')
        for k in (
            'reject_unrelated_trace_fixture',
            'reject_future_via_record_validation',
            'reject_stale_observed_via_max_age',
            'reject_wrong_job_revision_scope',
            'fixture_positive_control',
        )
    )
    e_ok = e_ok and evidence['fixture_positive_control']['accepted']
    e_ok = e_ok and evidence['verify_handler_with_issued_record']['accepted']
    e_ok = e_ok and evidence['verify_handler_with_issued_record']['matching_event_count'] == 1
    t_ok = (
        txn['reject_intruder_transfer_actor']['rejected']
        and txn['reject_foreign_handoff_operation']['rejected']
        and txn['failed_mutation_zero_side_effects']['operation_count_after_fail'] == 0
        and txn['replay_after_fail_succeeds_once']['operation_count'] == 1
        and txn['replay_after_fail_succeeds_once']['matching_event_count'] == 1
        and txn['replay_after_fail_succeeds_once']['acceptance_retained'] == ['check']
        and txn['concurrent_transfer_vs_mutate']['one_succeeded']
        and (
            not txn['concurrent_transfer_vs_mutate']['mutate_lost_race']
            or txn['concurrent_transfer_vs_mutate']['loser_operation_count'] == 0
        )
    )
    return e_ok and t_ok


def main() -> int:
    run_id = str(uuid.uuid4())
    evidence = test_evidence_counterexamples()
    txn = test_transaction_counterexamples()
    ok = summarize(evidence, txn)

    failure_links = []
    if PRIOR_FAILURE.is_file():
        failure_links.append(
            {
                'path': str(PRIOR_FAILURE.relative_to(ROOT)),
                'sha256': sha256_file(PRIOR_FAILURE),
                'supervisor_copy': 'reports/supervisor-history/workflow-core-APP-REVIEW-01-failure-307fe16d0430.json',
            }
        )

    receipt = {
        'delivery_id': DELIVERY,
        'run_id': run_id,
        'at': utc_now(),
        'owner_chat': '4f32e74a-58e3-4abb-ba6f-fb151ba80cd7',
        'source_identity': {
            'tools/verification_evidence.py': sha256_file(ROOT / 'tools/verification_evidence.py'),
            'tools/workflow_apply_guard.py': sha256_file(ROOT / 'tools/workflow_apply_guard.py'),
            'tools/reliability_gate.py': sha256_file(ROOT / 'tools/reliability_gate.py'),
        },
        'APP-REVIEW-01': {'passed': ok, 'cases': evidence},
        'APP-REVIEW-03': {'passed': ok, 'cases': txn},
        'failure_artifacts_preserved': failure_links,
        'prior_attempt_hashes_linked': failure_links,
        'independent_verification': 'not_claimed',
        'overall': 'passed' if ok else 'partial',
        'queue_remaining_required': [
            'APP-REVIEW-02',
            'APP-REVIEW-04',
            'full queue browser/controlled-edit/REL-01/synthetic',
            'real SDK BLOCKED',
        ],
    }
    out = REPORTS / 'core-evidence-transactions-receipt.json'
    out.write_text(json.dumps(receipt, indent=2) + '\n')
    append_history({'delivery_id': DELIVERY, 'run_id': run_id, 'at': receipt['at'], 'overall': receipt['overall'], 'receipt_sha256': sha256_file(out)})
    if not ok:
        fail_path = REPORTS / 'workflow-core-failures' / f'{DELIVERY}-{run_id[:8]}.json'
        fail_path.parent.mkdir(parents=True, exist_ok=True)
        fail_path.write_text(json.dumps({'evidence': evidence, 'txn': txn}, indent=2) + '\n')
        failure_links.append({'path': str(fail_path.relative_to(ROOT)), 'sha256': sha256_file(fail_path)})
        receipt['failure_artifacts_preserved'] = failure_links
        out.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'overall': receipt['overall'], 'APP-REVIEW-01': ok, 'APP-REVIEW-03': ok}, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
