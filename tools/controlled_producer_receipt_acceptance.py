#!/usr/bin/env python3
"""Delivery controlled-producer-receipt-20261010-0713 — D02 stripping / controlled producer evidence."""
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
DELIVERY = 'controlled-producer-receipt-20261010-0713'
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
    'tools/controlled_producer_receipt_acceptance.py',
)


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


def setup_job(db: Path, job: str, op: str, declared: list[str]) -> None:
    run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 0,
            'operation_id': 'cpr-create',
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
            'operation_id': 'cpr-add',
            'action': 'add_task',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'id': 't1',
                'goal': 'g',
                'owner': 'owner-a',
                'acceptance': ['proof-bound'],
                'deps': [],
                'declared_outcomes': declared,
            },
        },
    )


def controlled_produce(db: Path, job: str, op: str, rev: int, op_id: str, content: bytes) -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from bounded_acceptance import bounded_output_descriptor, controlled_materialize_bounded_artifact

    conn = sqlite3.connect(db)
    descriptor = controlled_materialize_bounded_artifact(conn, job, 't1', op_id, content)
    conn.close()
    run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': rev,
            'operation_id': op_id,
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


def rel02_claim(job: str, revision: int, proof_path: str, proof_sha: str) -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from verification_evidence import PERFORMED_WORK_ACTUALLY_USED

    return {
        'requirement_id': 'REL-02',
        'complete': True,
        'owner': 'cpr-acceptance',
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


def issue_record(db: Path, job: str, revision: int, operation_id: str) -> dict:
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
        task_id='t1',
        operation_id=operation_id,
        verifier='reviewer-b',
        acceptance=['proof-bound'],
    )
    engine.close()
    conn.close()
    return issued


def verify_record(db: Path, job: str, op: str, revision: int, operation_id: str, issued: dict) -> tuple[int, str, int, int]:
    claim = rel02_claim(job, revision, issued['path'], issued['record_sha256'])
    code, _, err = run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': revision,
            'operation_id': operation_id,
            'action': 'verify',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'id': f'cp-{operation_id}',
                'task_id': 't1',
                'verifier': 'reviewer-b',
                'requirement_claims': [claim],
                'evidence': [issued['path']],
                'checks': {'proof-bound': True},
            },
        },
    )
    ops, evs = count_op_events(db, operation_id)
    return code, err, ops, evs


def read_producer_receipts(db: Path) -> list[dict]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT receipt_id, producer_operation_id, declared_contract_revision, consumed_by_operation_id, created_at FROM controlled_producer_receipts ORDER BY created_at'
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def test_stripped_old_descriptor_rejected() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from bounded_acceptance import bounded_output_descriptor, build_declared_outcome, strip_to_client_draft_descriptor

    job = 'cpr-strip-job'
    op = f'{job}-handoff'
    db = fresh_db('strip')
    v1 = 'controlled-producer-v1\n'
    decl_v1 = build_declared_outcome('proof-bound', 1, expected_utf8=v1)
    setup_job(db, job, op, [decl_v1])
    controlled_produce(db, job, op, 2, 'cpr-produce-v1', v1.encode())
    engine_path = str(db)
    from workflow_engine import Engine

    engine = Engine(engine_path)
    sealed = engine.tasks(job)['t1']['outputs'][0]
    engine.close()
    sealed_obj = json.loads(sealed)

    decl_v2 = build_declared_outcome('proof-bound', 2, expected_utf8=v1)
    run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 3,
            'operation_id': 'cpr-decl-v2',
            'action': 'update',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {'task_id': 't1', 'declared_outcomes': [decl_v2]},
        },
    )
    stripped = strip_to_client_draft_descriptor(sealed_obj)
    code, _, err = run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 4,
            'operation_id': 'cpr-strip-attack',
            'action': 'update',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'task_id': 't1',
                'status': 'in_progress',
                'attempt': 'strip-reattach',
                'outputs': [bounded_output_descriptor(stripped)],
            },
        },
    )
    ops, evs = count_op_events(db, 'cpr-strip-attack')

    fake_id = dict(stripped)
    fake_id['producer_receipt_id'] = 'f' * 64
    code_fake, _, err_fake = run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 4,
            'operation_id': 'cpr-fake-receipt-id',
            'action': 'update',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'task_id': 't1',
                'outputs': [bounded_output_descriptor(fake_id)],
            },
        },
    )
    ops_fake, evs_fake = count_op_events(db, 'cpr-fake-receipt-id')

    return {
        'stripped_old_path_sha_rejected': {
            'exit': code,
            'error': err,
            'operation_count': ops,
            'event_count': evs,
        },
        'client_producer_receipt_id_rejected': {
            'exit': code_fake,
            'error': err_fake,
            'operation_count': ops_fake,
            'event_count': evs_fake,
        },
    }


def test_cross_contract_receipt_rejected() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from bounded_acceptance import bounded_output_descriptor, build_declared_outcome, strip_to_client_draft_descriptor

    job = 'cpr-cross-job'
    op = f'{job}-handoff'
    db = fresh_db('cross')
    body = b'cross-contract-bytes\n'
    decl_v1 = build_declared_outcome('proof-bound', 1, expected_utf8=body.decode())
    setup_job(db, job, op, [decl_v1])
    desc_v1 = controlled_produce(db, job, op, 2, 'cpr-cross-produce-v1', body)
    decl_v2 = build_declared_outcome('proof-bound', 2, expected_utf8=body.decode())
    run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 3,
            'operation_id': 'cpr-cross-decl-v2',
            'action': 'update',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {'task_id': 't1', 'declared_outcomes': [decl_v2]},
        },
    )
    draft = strip_to_client_draft_descriptor(desc_v1)
    code, _, err = run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 4,
            'operation_id': 'cpr-cross-stale-receipt',
            'action': 'update',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'task_id': 't1',
                'outputs': [bounded_output_descriptor(draft)],
            },
        },
    )
    ops, evs = count_op_events(db, 'cpr-cross-stale-receipt')
    return {
        'stale_v1_receipt_under_v2_declaration': {
            'exit': code,
            'error': err,
            'operation_count': ops,
            'event_count': evs,
        },
    }


def test_legitimate_controlled_producer_path() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from bounded_acceptance import build_declared_outcome

    job = 'cpr-legit-job'
    op = f'{job}-handoff'
    db = fresh_db('legit')
    v1 = 'controlled-producer-legit\n'
    decl_v1 = build_declared_outcome('proof-bound', 1, expected_utf8=v1)
    setup_job(db, job, op, [decl_v1])
    controlled_produce(db, job, op, 2, 'cpr-legit-produce-v1', v1.encode())

    decl_v2 = build_declared_outcome('proof-bound', 2, expected_utf8=v1)
    run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 3,
            'operation_id': 'cpr-legit-decl-v2',
            'action': 'update',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {'task_id': 't1', 'declared_outcomes': [decl_v2]},
        },
    )
    receipts_before = read_producer_receipts(db)
    controlled_produce(db, job, op, 4, 'cpr-legit-produce-v2', v1.encode())
    receipts_after = read_producer_receipts(db)
    verify_op = 'cpr-legit-verify'
    issued = issue_record(db, job, 5, verify_op)
    code, err, ops, evs = verify_record(db, job, op, 5, verify_op, issued)

    from workflow_engine import Engine

    engine = Engine(str(db))
    task = engine.tasks(job)['t1']
    job_rev = engine.job(job)['revision']
    engine.close()

    v2_receipts = [r for r in receipts_after if r['declared_contract_revision'] == 2]
    return {
        'producer_ordering': {
            'declaration_op': 'cpr-legit-decl-v2',
            'materialize_op': 'cpr-legit-produce-v2',
            'receipts_before_count': len(receipts_before),
            'receipts_after_count': len(receipts_after),
            'v2_receipt_consumed_by': v2_receipts[-1]['consumed_by_operation_id'] if v2_receipts else None,
            'v2_receipt_producer_op': v2_receipts[-1]['producer_operation_id'] if v2_receipts else None,
        },
        'attach_and_verify': {
            'exit': code,
            'error': err,
            'operation_count': ops,
            'event_count': evs,
            'job_revision': job_rev,
            'production_history_len': len(task.get('production_history') or []),
            'task_status': task.get('status'),
        },
        'db_readback_sha256': sha256_file(db),
    }


def summarize(cases: dict) -> bool:
    strip = cases['stripped_descriptor']
    s = strip['stripped_old_path_sha_rejected']
    if s['exit'] == 0 or s['operation_count'] != 0 or s['event_count'] != 0:
        return False
    if s['error'] != 'controlled_producer_evidence_missing':
        return False
    fake = strip['client_producer_receipt_id_rejected']
    if fake['exit'] == 0 or fake['operation_count'] != 0:
        return False
    if fake['error'] != 'client_production_metadata_forbidden':
        return False

    cross = cases['cross_contract']['stale_v1_receipt_under_v2_declaration']
    if cross['exit'] == 0 or cross['operation_count'] != 0:
        return False
    if cross['error'] != 'controlled_producer_evidence_missing':
        return False

    legit = cases['legitimate_path']
    order = legit['producer_ordering']
    if order['receipts_after_count'] != order['receipts_before_count'] + 1:
        return False
    if order['v2_receipt_consumed_by'] != 'cpr-legit-produce-v2':
        return False
    if order['v2_receipt_producer_op'] != 'cpr-legit-produce-v2':
        return False
    pos = legit['attach_and_verify']
    if pos['exit'] != 0 or pos['operation_count'] != 1 or pos['task_status'] != 'verified':
        return False
    if pos['production_history_len'] < 2:
        return False
    return True


def main() -> int:
    run_id = str(uuid.uuid4())
    cases = {
        'stripped_descriptor': test_stripped_old_descriptor_rejected(),
        'cross_contract': test_cross_contract_receipt_rejected(),
        'legitimate_path': test_legitimate_controlled_producer_path(),
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
        'scope_note': 'Proves local controlled materialize receipt consumed on attach; not external agent labor.',
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
    (REPORTS / 'controlled-producer-receipt.json').write_text(json.dumps(pointer, indent=2) + '\n')
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
