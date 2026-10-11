#!/usr/bin/env python3
"""Delivery artifact-outcome-final-bytes-20261010-0639."""
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
DELIVERY = 'artifact-outcome-final-bytes-20261010-0639'
HISTORY = REPORTS / 'workflow-core-run-history.jsonl'

SOURCE_MODULES = (
    'tools/workflow_engine.py',
    'tools/reliability_gate.py',
    'tools/local_service.py',
    'tools/reliability_store.py',
    'tools/workflow_apply_guard.py',
    'tools/verification_evidence.py',
    'tools/bounded_acceptance.py',
    'tools/receipt_immutable.py',
    'tools/artifact_outcome_final_bytes_acceptance.py',
)

PRIOR_RECEIPT_RECONCILE = [
    {
        'path': REPORTS / 'run-receipts/outcome-replay-rollback-20261010-0631-935f027b-6ab4-490c-8239-0d40b98c6475.json',
        'declared': '1a9229d667fe95150ab1015cbcf838df8d3f4a47aaa5de31a4dbfdd8e4501b10',
    },
    {
        'path': REPORTS / 'run-receipts/outcome-replay-rollback-20261010-0631-77770cf8-5b70-4c96-bd79-481c1e8725e8.json',
        'declared': '93c89af9fc428924df7ed60cee3c66645f21a14f1bbe8c7dd3164a0efdfe21ce',
    },
    {
        'path': REPORTS / 'run-receipts/outcome-replay-rollback-20261010-0631-1b203773-a375-42fe-8817-90698dc0b48e.json',
        'declared': 'c001934242a85058c763ca77cf4bb652e6e18eca39bfdf80b015541ec8e80ea1',
    },
]


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


def _proof_bound_declared(expected_utf8: str = 'expected-bytes-v1\n') -> str:
    sys.path.insert(0, str(ROOT / 'tools'))
    from bounded_acceptance import build_declared_outcome

    return build_declared_outcome('proof-bound', 1, expected_utf8=expected_utf8)


def setup_job_with_task(db: Path, job: str, op: str) -> None:
    run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 0,
            'operation_id': 'aof-create',
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
            'operation_id': 'aof-add',
            'action': 'add_task',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'id': 't1',
                'goal': 'g',
                'owner': 'owner-a',
                'acceptance': ['proof-bound'],
                'deps': [],
                'declared_outcomes': [_proof_bound_declared()],
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
        'owner': 'artifact-outcome-acceptance',
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


def issue_verify_record(db: Path, job: str, revision: int, task_id: str, operation_id: str, acceptance: list[str]):
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
        acceptance=acceptance,
    )
    engine.close()
    conn.close()
    return issued


def test_bounded_artifact_contract() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from bounded_acceptance import measure_criterion_outcome
    from verification_evidence import issue_measured_workflow_verify_record
    from reliability_store import connect
    from workflow_engine import Engine

    cases: dict = {}
    db = fresh_db('artifact-contract')
    job = 'artifact-job'
    op = f'{job}-handoff'
    setup_job_with_task(db, job, op)

    declared = _proof_bound_declared()
    pending_task = {'acceptance': ['proof-bound'], 'declared_outcomes': [declared], 'outputs': []}
    frag, _, reason = measure_criterion_outcome('proof-bound', pending_task)
    cases['pending_task_no_artifact'] = {'reason': reason, 'checks': frag}

    fake_name_task = {'acceptance': ['proof-bound'], 'declared_outcomes': [declared], 'outputs': ['missing-file.txt']}
    frag2, _, reason2 = measure_criterion_outcome('proof-bound', fake_name_task)
    cases['plain_string_output_rejected'] = {'reason': reason2, 'checks': frag2}

    descriptor = produce_artifact(db, job, op, 2, 'aof-produce-good', b'expected-bytes-v1\n')
    engine = Engine(str(db))
    frag3, proofs, reason3 = measure_criterion_outcome('proof-bound', engine.tasks(job)['t1'])
    engine.close()
    cases['real_artifact_measured'] = {
        'reason': reason3,
        'proofs': proofs,
        'descriptor_sha256': descriptor['sha256'],
    }

    bad_desc = dict(descriptor)
    bad_desc['sha256'] = '0' * 64
    bad_task = {
        'acceptance': ['proof-bound'],
        'declared_outcomes': [declared],
        'outputs': [json.dumps(bad_desc, sort_keys=True)],
    }
    frag4, _, reason4 = measure_criterion_outcome('proof-bound', bad_task)
    cases['wrong_hash_rejected'] = {'reason': reason4, 'checks': frag4}

    issued = issue_verify_record(db, job, 3, 't1', 'aof-record-good', ['proof-bound'])
    claim = rel02_verify_claim(job, 3, issued['path'], issued['record_sha256'])
    code, _, err = run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 3,
            'operation_id': 'aof-record-good',
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
    ops, evs = count_op_events(db, 'aof-record-good')
    cases['handler_positive_once'] = {
        'exit': code,
        'error': err,
        'operation_count': ops,
        'matching_event_count': evs,
        'observed_proofs_in_record': issued.get('body', {}).get('observed_proofs'),
    }
    return cases


def _scope_negative(
    db: Path,
    job: str,
    op: str,
    revision: int,
    issued: dict,
    *,
    operation_id: str,
    task_id: str,
    verifier: str,
) -> tuple[int, str, int, int]:
    claim = rel02_verify_claim(job, revision, issued['path'], issued['record_sha256'])
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
                'task_id': task_id,
                'verifier': verifier,
                'requirement_claims': [claim],
                'evidence': [issued['path']],
                'checks': {'proof-bound': True},
            },
        },
    )
    ops, evs = count_op_events(db, operation_id)
    return code, err, ops, evs


def test_handler_scope_negatives() -> dict:
    job = 'scope-job'
    op = f'{job}-handoff'

    db_task = fresh_db('scope-wrong-task')
    setup_job_with_task(db_task, job, op)
    produce_artifact(db_task, job, op, 2, 'aof-produce-wt', b'expected-bytes-v1\n')
    issued_task = issue_verify_record(db_task, job, 3, 't1', 'aof-record-wt', ['proof-bound'])
    code_wt, err_wt, ops_wt, evs_wt = _scope_negative(
        db_task,
        job,
        op,
        3,
        issued_task,
        operation_id='aof-neg-wrong-task',
        task_id='t-other',
        verifier='reviewer-b',
    )

    db_op = fresh_db('scope-wrong-op')
    setup_job_with_task(db_op, job, op)
    produce_artifact(db_op, job, op, 2, 'aof-produce-wo', b'expected-bytes-v1\n')
    issued_op = issue_verify_record(db_op, job, 3, 't1', 'aof-record-wo', ['proof-bound'])
    code_wo, err_wo, ops_wo, evs_wo = _scope_negative(
        db_op,
        job,
        op,
        3,
        issued_op,
        operation_id='aof-neg-wrong-op',
        task_id='t1',
        verifier='reviewer-b',
    )

    db_ver = fresh_db('scope-wrong-verifier')
    setup_job_with_task(db_ver, job, op)
    produce_artifact(db_ver, job, op, 2, 'aof-produce-wv', b'expected-bytes-v1\n')
    issued_ver = issue_verify_record(db_ver, job, 3, 't1', 'aof-record-wv', ['proof-bound'])
    code_wv, err_wv, ops_wv, evs_wv = _scope_negative(
        db_ver,
        job,
        op,
        3,
        issued_ver,
        operation_id='aof-record-wv',
        task_id='t1',
        verifier='wrong-verifier',
    )

    return {
        'wrong_task': {
            'exit': code_wt,
            'error': err_wt,
            'operation_count': ops_wt,
            'event_count': evs_wt,
        },
        'wrong_operation': {
            'exit': code_wo,
            'error': err_wo,
            'operation_count': ops_wo,
            'event_count': evs_wo,
        },
        'wrong_verifier': {
            'exit': code_wv,
            'error': err_wv,
            'operation_count': ops_wv,
            'event_count': evs_wv,
        },
    }


def prior_receipt_reconciliations() -> list[dict]:
    sys.path.insert(0, str(ROOT / 'tools'))
    from receipt_immutable import reconcile_receipt_hash

    return [reconcile_receipt_hash(item['path'], item['declared']) for item in PRIOR_RECEIPT_RECONCILE]


def test_receipt_immutability(run_id: str, receipt_payload: dict) -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from receipt_immutable import (
        append_manifest,
        sha256_file as imm_sha,
        write_final_receipt_once,
    )

    immutable_path = RUN_RECEIPTS / f'{DELIVERY}-{run_id}.json'
    _, digest = write_final_receipt_once(immutable_path, receipt_payload)
    hash_after_write = imm_sha(immutable_path)
    stable = hash_after_write == digest

    pointer = {
        'delivery_id': DELIVERY,
        'run_id': run_id,
        'immutable_receipt_path': str(immutable_path.relative_to(ROOT)),
        'content_sha256': digest,
    }
    append_manifest(MANIFEST, pointer)
    hash_after_manifest = imm_sha(immutable_path)
    canonical_pointer = REPORTS / 'artifact-outcome-final-bytes-receipt.json'
    canonical_pointer.write_text(json.dumps(pointer, indent=2) + '\n')
    hash_after_pointer = imm_sha(immutable_path)

    imm = receipt_payload.get('receipt_immutability') or {}
    return {
        'immutable_path': str(immutable_path.relative_to(ROOT)),
        'content_sha256': digest,
        'hash_stable_after_manifest': hash_after_manifest == digest,
        'hash_stable_after_pointer_write': hash_after_pointer == digest,
        'manifest_entry': pointer,
        'prior_receipt_reconciliation': imm.get('prior_receipt_reconciliation'),
    }


def summarize(artifact: dict, scope: dict) -> bool:
    pos = artifact['handler_positive_once']
    if pos['exit'] != 0 or pos['operation_count'] != 1 or pos['matching_event_count'] != 1:
        return False
    if not pos.get('observed_proofs_in_record'):
        return False
    if artifact['plain_string_output_rejected']['reason'] != 'artifact_descriptor_invalid':
        return False
    if artifact['wrong_hash_rejected']['reason'] not in (
        'artifact_sha256_mismatch',
        'output_declaration_binding_stale',
        'output_missing_production_identity',
    ):
        return False
    if artifact['real_artifact_measured']['reason'] is not None:
        return False
    wt = scope['wrong_task']
    wo = scope['wrong_operation']
    wv = scope['wrong_verifier']
    if wt['error'] != 'verification_record_task_id_mismatch' or wt['operation_count'] != 0:
        return False
    if wo['error'] != 'verification_record_operation_id_mismatch' or wo['operation_count'] != 0:
        return False
    if wv['error'] != 'verification_record_verifier_mismatch' or wv['operation_count'] != 0:
        return False
    return True


def receipt_immutability_ok(imm: dict) -> bool:
    if not imm.get('hash_stable_after_manifest') or not imm.get('hash_stable_after_pointer_write'):
        return False
    for row in imm.get('prior_receipt_reconciliation') or []:
        if row.get('actual_sha256') == row.get('previously_reported_sha256'):
            continue
        if not row.get('actual_sha256'):
            return False
    return True


def main() -> int:
    run_id = str(uuid.uuid4())
    artifact = test_bounded_artifact_contract()
    scope = test_handler_scope_negatives()
    cases_ok = summarize(artifact, scope)
    reconciliations = prior_receipt_reconciliations()
    recon_ok = True
    for row in reconciliations:
        rel = row.get('path') or ''
        p = Path(rel) if Path(rel).is_absolute() else ROOT / rel
        if p.is_file() and not row.get('actual_sha256'):
            recon_ok = False
    ok = cases_ok and recon_ok

    receipt_body = {
        'delivery_id': DELIVERY,
        'run_id': run_id,
        'at': utc_now(),
        'owner_chat': '4f32e74a-58e3-4abb-ba6f-fb151ba80cd7',
        'source_identity': source_identities(),
        'cases': {'bounded_artifact_contract': artifact, 'handler_scope_negatives': scope},
        'independent_verification': 'not_claimed',
        'overall': 'passed' if ok else 'partial',
        'intentional_failed_attempt_recorded': False,
    }
    if not ok:
        receipt_body['intentional_failed_attempt_recorded'] = True
        fail_cases = dict(artifact)
        fail_cases['handler_scope_negatives'] = scope
        fail_path = REPORTS / 'workflow-core-failures' / f'{DELIVERY}-{run_id[:8]}.json'
        fail_path.parent.mkdir(parents=True, exist_ok=True)
        fail_path.write_text(json.dumps(fail_cases, indent=2) + '\n')
        receipt_body['failure_artifacts_preserved'] = [
            {'path': str(fail_path.relative_to(ROOT)), 'sha256': sha256_file(fail_path)}
        ]

    immutable_rel = str((RUN_RECEIPTS / f'{DELIVERY}-{run_id}.json').relative_to(ROOT))
    receipt_body['receipt_immutability'] = {
        'immutable_path': immutable_rel,
        'prior_receipt_reconciliation': reconciliations,
    }
    imm = test_receipt_immutability(run_id, receipt_body)
    ok = ok and receipt_immutability_ok(imm)

    append_line = {
        'delivery_id': DELIVERY,
        'run_id': run_id,
        'at': receipt_body['at'],
        'overall': receipt_body['overall'],
        'immutable_receipt': imm['immutable_path'],
        'content_sha256': imm['content_sha256'],
        'hash_stable_after_manifest': imm['hash_stable_after_manifest'],
        'hash_stable_after_pointer_write': imm['hash_stable_after_pointer_write'],
    }
    with HISTORY.open('a') as handle:
        handle.write(json.dumps(append_line) + '\n')

    print(
        json.dumps(
            {
                'overall': receipt_body['overall'],
                'delivery_id': DELIVERY,
                'run_id': run_id,
                'immutable_content_sha256': imm['content_sha256'],
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
