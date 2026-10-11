#!/usr/bin/env python3
"""Delivery declared-outcome-live-proof-20261010-0650."""
from __future__ import annotations

import hashlib
import json
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
TEST_ROOT = ROOT / 'app' / '.data' / 'workflow-core-tests'
DELIVERY = 'declared-outcome-live-proof-20261010-0650'
HISTORY = REPORTS / 'workflow-core-run-history.jsonl'
OWNER_CHAT = '4f32e74a-58e3-4abb-ba6f-fb151ba80cd7'

SOURCE_MODULES = (
    'tools/workflow_engine.py',
    'tools/reliability_gate.py',
    'tools/local_service.py',
    'tools/reliability_store.py',
    'tools/workflow_apply_guard.py',
    'tools/verification_evidence.py',
    'tools/bounded_acceptance.py',
    'tools/receipt_immutable.py',
    'tools/declared_outcome_live_proof_acceptance.py',
)

EXPECTED_UTF8 = 'declared-live-proof-v1\n'


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_identities() -> dict[str, str]:
    return {p: sha256_file(ROOT / p) for p in SOURCE_MODULES if (ROOT / p).is_file()}


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
    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {'stdout': proc.stdout, 'stderr': proc.stderr}
    nested = (payload.get('payload') or {}).get('error')
    if nested:
        return proc.returncode or 1, payload, str(nested)
    if isinstance(payload, dict) and payload.get('error'):
        return proc.returncode or 1, payload, str(payload.get('error'))
    return proc.returncode, payload if isinstance(payload, dict) else {'raw': payload}, proc.stderr.strip()


def count_op_events(db: Path, operation_id: str) -> tuple[int, int]:
    conn = sqlite3.connect(db)
    ops = conn.execute('SELECT COUNT(*) FROM operations WHERE id=?', (operation_id,)).fetchone()[0]
    events = conn.execute(
        "SELECT COUNT(*) FROM events WHERE json_extract(payload, '$.operation_id')=?",
        (operation_id,),
    ).fetchone()[0]
    conn.close()
    return ops, events


def proof_bound_declared(revision: int = 1, expected_utf8: str = EXPECTED_UTF8) -> str:
    sys.path.insert(0, str(ROOT / 'tools'))
    from bounded_acceptance import build_declared_outcome

    return build_declared_outcome('proof-bound', revision, expected_utf8=expected_utf8)


def setup_job_with_task(db: Path, job: str, op: str, *, expected_utf8: str = EXPECTED_UTF8) -> None:
    run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 0,
            'operation_id': 'dolp-create',
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
            'operation_id': 'dolp-add',
            'action': 'add_task',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'id': 't1',
                'goal': 'Return exactly declared UTF-8 artifact',
                'owner': 'owner-a',
                'acceptance': ['proof-bound'],
                'deps': [],
                'declared_outcomes': [proof_bound_declared(expected_utf8=expected_utf8)],
            },
        },
    )


def produce_artifact(db: Path, job: str, op: str, revision: int, operation_id: str, content: bytes) -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from bounded_acceptance import bounded_output_descriptor, controlled_materialize_bounded_artifact

    conn = sqlite3.connect(db)
    descriptor = controlled_materialize_bounded_artifact(conn, job, 't1', operation_id, content)
    conn.close()
    run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': revision,
            'operation_id': operation_id,
            'action': 'update',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'task_id': 't1',
                'status': 'in_progress',
                'attempt': 'produce',
                'outputs': [bounded_output_descriptor(descriptor)],
            },
        },
    )
    return descriptor


def rel02_verify_claim(job: str, revision: int, proof_path: str, proof_sha: str) -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from verification_evidence import PERFORMED_WORK_ACTUALLY_USED

    return {
        'requirement_id': 'REL-02',
        'complete': True,
        'owner': 'declared-outcome-acceptance',
        'job_id': job,
        'job_revision': revision,
        'requirement_set': ['REL-01', 'REL-02', 'REL-03', 'REL-04', 'REL-05', 'REL-06'],
        'evidence': {
            'verified_at': utc_now(),
            'actually_used': PERFORMED_WORK_ACTUALLY_USED,
            'documented_path': 'docs/RELIABILITY_ADDENDUM.md',
            'proof_path': proof_path,
            'proof_sha256': proof_sha,
            'skills_verified': True,
            'relationships_sha256': sha256_file(ROOT / 'data/relationships.json'),
        },
    }


def issue_verify_record(db: Path, job: str, revision: int, task_id: str, operation_id: str) -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from reliability_store import connect
    from verification_evidence import issue_measured_workflow_verify_record
    from workflow_engine import Engine

    conn = connect(db)
    engine = Engine(str(db))
    issued = issue_measured_workflow_verify_record(
        conn,
        engine,
        job_id=job,
        job_revision=revision,
        task_id=task_id,
        operation_id=operation_id,
        verifier='reviewer-b',
        acceptance=['proof-bound'],
    )
    engine.close()
    conn.close()
    return issued


def test_predeclared_outcome_contract() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from bounded_acceptance import bounded_output_descriptor, measure_criterion_outcome
    from verification_evidence import sha256_file as ve_sha

    cases: dict = {}
    db = fresh_db('declared-contract')
    job = 'decl-job'
    op = f'{job}-handoff'
    setup_job_with_task(db, job, op)

    pending = {'acceptance': ['proof-bound'], 'declared_outcomes': [proof_bound_declared()], 'outputs': []}
    _, _, reason_pending = measure_criterion_outcome('proof-bound', pending)
    cases['missing_artifact'] = {'reason': reason_pending}

    from bounded_acceptance import parse_declared_outcome

    addendum = ROOT / 'docs/RELIABILITY_ADDENDUM.md'
    addendum_sha = ve_sha(addendum)
    fake_task = {
        'acceptance': ['proof-bound'],
        'declared_outcomes': [proof_bound_declared()],
        'outputs': [
            bounded_output_descriptor(
                {
                    'schema': 'bounded_artifact_v1',
                    'relative_path': 'work/task-artifacts/../../docs/RELIABILITY_ADDENDUM.md',
                    'sha256': addendum_sha,
                    'byte_length': addendum.stat().st_size,
                }
            )
        ],
    }
    _, _, reason_unrelated = measure_criterion_outcome('proof-bound', fake_task)
    cases['unrelated_allowlisted_path_rejected'] = {'reason': reason_unrelated}

    produce_artifact(db, job, op, 2, 'dolp-produce-wrong', b'wrong-bytes-not-declared\n')
    from workflow_engine import Engine

    engine = Engine(str(db))
    wrong_task = engine.tasks(job)['t1']
    engine.close()
    _, _, reason_wrong = measure_criterion_outcome('proof-bound', wrong_task)
    cases['wrong_content_rejected'] = {'reason': reason_wrong}

    db_ok = fresh_db('declared-positive')
    setup_job_with_task(db_ok, job, op)
    produce_artifact(db_ok, job, op, 2, 'dolp-produce-good', EXPECTED_UTF8.encode())
    issued = issue_verify_record(db_ok, job, 3, 't1', 'dolp-record-good')
    claim = rel02_verify_claim(job, 3, issued['path'], issued['record_sha256'])
    code, _, err = run_apply(
        db_ok,
        {
            'job_id': job,
            'expected_revision': 3,
            'operation_id': 'dolp-record-good',
            'action': 'verify',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'id': 'cp-good',
                'task_id': 't1',
                'verifier': 'reviewer-b',
                'requirement_claims': [claim],
                'evidence': [issued['path']],
                'checks': {'proof-bound': True},
            },
        },
    )
    ops, evs = count_op_events(db_ok, 'dolp-record-good')
    cases['handler_positive_once'] = {
        'exit': code,
        'error': err,
        'operation_count': ops,
        'event_count': evs,
        'observed_proofs': issued.get('body', {}).get('observed_proofs'),
    }
    return cases


def test_consumption_recheck() -> dict:
    job = 'live-job'
    op = f'{job}-handoff'
    db = fresh_db('consumption-recheck')
    setup_job_with_task(db, job, op)
    descriptor = produce_artifact(db, job, op, 2, 'dolp-produce-live', EXPECTED_UTF8.encode())
    issued = issue_verify_record(db, job, 3, 't1', 'dolp-live-record')
    artifact_path = ROOT / descriptor['relative_path']
    artifact_path.write_bytes(b'tampered-after-record-issue\n')

    claim = rel02_verify_claim(job, 3, issued['path'], issued['record_sha256'])
    code_tamper, _, err_tamper = run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 3,
            'operation_id': 'dolp-live-record',
            'action': 'verify',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'id': 'cp-tamper',
                'task_id': 't1',
                'verifier': 'reviewer-b',
                'requirement_claims': [claim],
                'evidence': [issued['path']],
                'checks': {'proof-bound': True},
            },
        },
    )
    ops_t, evs_t = count_op_events(db, 'dolp-live-record')

    artifact_path.write_bytes(EXPECTED_UTF8.encode())
    issued2 = issue_verify_record(db, job, 3, 't1', 'dolp-live-record-2')
    claim2 = rel02_verify_claim(job, 3, issued2['path'], issued2['record_sha256'])
    code_ok, _, err_ok = run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 3,
            'operation_id': 'dolp-live-record-2',
            'action': 'verify',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'id': 'cp-ok',
                'task_id': 't1',
                'verifier': 'reviewer-b',
                'requirement_claims': [claim2],
                'evidence': [issued2['path']],
                'checks': {'proof-bound': True},
            },
        },
    )
    ops_ok, evs_ok = count_op_events(db, 'dolp-live-record-2')

    proof_copy = REPORTS / 'declared-outcome-live-proof-proofs' / f'{DELIVERY}-consumption-artifact.txt'
    proof_copy.parent.mkdir(parents=True, exist_ok=True)
    proof_copy.write_bytes(artifact_path.read_bytes())

    return {
        'after_tamper_verify': {
            'exit': code_tamper,
            'error': err_tamper,
            'operation_count': ops_t,
            'event_count': evs_t,
        },
        'after_restore_and_fresh_record': {
            'exit': code_ok,
            'error': err_ok,
            'operation_count': ops_ok,
            'event_count': evs_ok,
        },
        'artifact_proof_path': str(proof_copy.relative_to(ROOT)),
        'artifact_sha256': sha256_file(proof_copy),
    }


def test_wrong_task_single_variable() -> dict:
    job = 'wt-job'
    op = f'{job}-handoff'
    db = fresh_db('wrong-task-only')
    setup_job_with_task(db, job, op)
    produce_artifact(db, job, op, 2, 'dolp-produce-wt', EXPECTED_UTF8.encode())
    issued = issue_verify_record(db, job, 3, 't1', 'dolp-record-wt')
    claim = rel02_verify_claim(job, 3, issued['path'], issued['record_sha256'])
    code, _, err = run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 3,
            'operation_id': 'dolp-record-wt',
            'action': 'verify',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'id': 'cp-wt',
                'task_id': 't-other',
                'verifier': 'reviewer-b',
                'requirement_claims': [claim],
                'evidence': [issued['path']],
                'checks': {'proof-bound': True},
            },
        },
    )
    ops, evs = count_op_events(db, 'dolp-record-wt')
    return {
        'exit': code,
        'error': err,
        'operation_count': ops,
        'event_count': evs,
        'record_operation_id': 'dolp-record-wt',
        'request_operation_id': 'dolp-record-wt',
    }


def summarize(cases: dict) -> bool:
    pre = cases['predeclared_outcome']
    if pre['missing_artifact']['reason'] != 'artifact_missing':
        return False
    if pre['unrelated_allowlisted_path_rejected']['reason'] not in (
        'artifact_not_allowlisted',
        'artifact_path_traversal',
        'artifact_outside_artifact_root',
    ):
        return False
    if pre['wrong_content_rejected']['reason'] != 'declared_content_mismatch':
        return False
    pos = pre['handler_positive_once']
    if pos['exit'] != 0 or pos['operation_count'] != 1 or pos['event_count'] != 1:
        return False
    if not pos.get('observed_proofs'):
        return False
    live = cases['consumption_recheck']
    tamper = live['after_tamper_verify']
    if tamper['exit'] == 0 or tamper['operation_count'] != 0 or tamper['event_count'] != 0:
        return False
    if tamper['error'] != 'observed_artifact_changed_at_consumption':
        return False
    ok = live['after_restore_and_fresh_record']
    if ok['exit'] != 0 or ok['operation_count'] != 1:
        return False
    wt = cases['wrong_task_single_variable']
    if wt['error'] != 'verification_record_task_id_mismatch' or wt['operation_count'] != 0:
        return False
    return True


def main() -> int:
    run_id = str(uuid.uuid4())
    cases = {
        'predeclared_outcome': test_predeclared_outcome_contract(),
        'consumption_recheck': test_consumption_recheck(),
        'wrong_task_single_variable': test_wrong_task_single_variable(),
    }
    ok = summarize(cases)

    receipt_body = {
        'delivery_id': DELIVERY,
        'run_id': run_id,
        'at': utc_now(),
        'owner_chat': OWNER_CHAT,
        'source_identity': source_identities(),
        'cases': cases,
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
    (REPORTS / 'declared-outcome-live-proof-receipt.json').write_text(json.dumps(pointer, indent=2) + '\n')
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
                'immutable_content_sha256': digest,
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
