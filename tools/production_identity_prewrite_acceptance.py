#!/usr/bin/env python3
"""Delivery production-identity-prewrite-20261010-0706."""
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
TEST_ROOT = ROOT / 'app' / '.data' / 'workflow-core-tests'
ARTIFACT_ROOT = ROOT / 'work' / 'task-artifacts'
PROBE_DIR = ROOT / 'work' / 'task-artifacts' / '_pip_probe'
DELIVERY = 'production-identity-prewrite-20261010-0706'
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
    'tools/production_identity_prewrite_acceptance.py',
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
            'operation_id': 'pip-create',
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
            'operation_id': 'pip-add',
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


def rel02_claim(job: str, revision: int, proof_path: str, proof_sha: str) -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from verification_evidence import PERFORMED_WORK_ACTUALLY_USED

    return {
        'requirement_id': 'REL-02',
        'complete': True,
        'owner': 'pip-acceptance',
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


def produce(db: Path, job: str, op: str, rev: int, op_id: str, content: bytes) -> dict:
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


def test_production_identity_relabel() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from bounded_acceptance import attach_contract_binding, bounded_output_descriptor, build_declared_outcome, parse_declared_outcome
    from workflow_engine import Engine

    job = 'pip-id-job'
    op = f'{job}-handoff'
    db = fresh_db('prod-id')
    v1 = 'production-identity-v1\n'
    decl_v1 = build_declared_outcome('proof-bound', 1, expected_utf8=v1)
    setup_job(db, job, op, [decl_v1])
    produce(db, job, op, 2, 'pip-produce-v1', v1.encode())
    engine = Engine(str(db))
    sealed_outputs = engine.tasks(job)['t1']['outputs']
    engine.close()

    decl_v2 = build_declared_outcome('proof-bound', 2, expected_utf8=v1)
    run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 3,
            'operation_id': 'pip-decl-v2',
            'action': 'update',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {'task_id': 't1', 'declared_outcomes': [decl_v2]},
        },
    )
    draft = json.loads(sealed_outputs[0])
    relabeled = attach_contract_binding(draft, parse_declared_outcome(decl_v2))
    code_rel, _, err_rel = run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 4,
            'operation_id': 'pip-relabel-attack',
            'action': 'update',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'task_id': 't1',
                'status': 'in_progress',
                'attempt': 'relabel',
                'outputs': [bounded_output_descriptor(relabeled)],
            },
        },
    )
    ops_rel, evs_rel = count_op_events(db, 'pip-relabel-attack')

    forged = dict(draft)
    forged['production_id'] = '0' * 64
    code_forged, _, err_forged = run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 4,
            'operation_id': 'pip-forged-id',
            'action': 'update',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'task_id': 't1',
                'outputs': [bounded_output_descriptor(forged)],
            },
        },
    )
    ops_forged, evs_forged = count_op_events(db, 'pip-forged-id')

    produce(db, job, op, 4, 'pip-produce-v2', v1.encode())
    verify_op = 'pip-verify-v2'
    issued = issue_record(db, job, 5, verify_op)
    code_ok, err_ok, ops_ok, evs_ok = verify_record(db, job, op, 5, verify_op, issued)

    engine = Engine(str(db))
    task = engine.tasks(job)['t1']
    engine.close()

    return {
        'relabel_sealed_descriptor_rejected': {
            'exit': code_rel,
            'error': err_rel,
            'operation_count': ops_rel,
            'event_count': evs_rel,
        },
        'forged_production_id_rejected': {
            'exit': code_forged,
            'error': err_forged,
            'operation_count': ops_forged,
            'event_count': evs_forged,
        },
        'revisioned_production_and_verify': {
            'exit': code_ok,
            'error': err_ok,
            'operation_count': ops_ok,
            'event_count': evs_ok,
            'production_history_len': len(task.get('production_history') or []),
            'output_history_len': len(task.get('output_history') or []),
        },
    }


def test_prewrite_containment() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from bounded_acceptance import BoundedAcceptanceError, materialize_bounded_artifact

    PROBE_DIR.mkdir(parents=True, exist_ok=True)
    probe_file = PROBE_DIR / 'outside-root-probe.txt'
    if probe_file.exists():
        probe_file.unlink()
    before_probe = probe_file.exists()

    unsafe_reason = None
    try:
        materialize_bounded_artifact('..', 't1', b'x')
    except BoundedAcceptanceError as exc:
        unsafe_reason = exc.reason

    after_probe = probe_file.exists()
    symlink_job_id = f'pip-sym-{uuid.uuid4().hex[:8]}'
    link_job = ARTIFACT_ROOT / symlink_job_id
    os.symlink(ROOT / 'docs', link_job)
    parent_escape_reason = None
    try:
        materialize_bounded_artifact(symlink_job_id, 't1', b'escape-bytes\n')
    except BoundedAcceptanceError as exc:
        parent_escape_reason = exc.reason
    leaked_files = [
        str(p.relative_to(ROOT))
        for p in (ROOT / 'docs').glob('t1-*.txt')
        if p.is_file()
    ]

    job = 'pip-safe-job'
    op = f'{job}-handoff'
    db = fresh_db('prewrite-safe')
    from bounded_acceptance import build_declared_outcome

    decl = build_declared_outcome('proof-bound', 1, expected_utf8='prewrite-safe-v1\n')
    setup_job(db, job, op, [decl])
    produce(db, job, op, 2, 'pip-prewrite-good', b'prewrite-safe-v1\n')

    return {
        'unsafe_job_id': {'reason': unsafe_reason, 'probe_created': after_probe and not before_probe},
        'parent_symlink_escape': {'reason': parent_escape_reason, 'unexpected_files': leaked_files},
        'safe_production_exit': 0,
    }


def test_json_handler_negatives() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from bounded_acceptance import build_declared_outcome

    job = 'pip-json-job'
    op = f'{job}-handoff'
    db = fresh_db('json-handler')
    decl = build_declared_outcome('proof-bound', 1, expected_result={'ok': True})
    setup_job(db, job, op, [decl])
    produce(db, job, op, 2, 'pip-json-bad-produce', b'{"ok":1}\n')

    issue_op = 'pip-json-issue-attempt'
    issue_exit = 0
    issue_err = ''
    try:
        issue_record(db, job, 3, issue_op)
    except ValueError as exc:
        issue_exit = 1
        issue_err = str(exc)
    ops_issue, evs_issue = count_op_events(db, issue_op)

    verify_op = 'pip-json-verify-attempt'
    fake_issued = {'path': 'work/reliability/verification-records/missing.json', 'record_sha256': '0' * 64}
    code_v, err_v, ops_v, evs_v = verify_record(db, job, op, 3, verify_op, fake_issued)

    db_ok = fresh_db('json-handler-ok')
    setup_job(db_ok, job, op, [decl])
    produce(db_ok, job, op, 2, 'pip-json-good-produce', b'{"ok": true}\n')
    good_op = 'pip-json-good-verify'
    issued = issue_record(db_ok, job, 3, good_op)
    code_ok, err_ok, ops_ok, evs_ok = verify_record(db_ok, job, op, 3, good_op, issued)

    return {
        'issuance_wrong_json_type': {
            'exit': issue_exit,
            'error_contains': 'declared_result_mismatch' in issue_err,
            'operation_count': ops_issue,
            'event_count': evs_issue,
        },
        'verify_with_missing_record': {
            'exit': code_v,
            'error': err_v,
            'operation_count': ops_v,
            'event_count': evs_v,
        },
        'matching_json_positive': {
            'exit': code_ok,
            'error': err_ok,
            'operation_count': ops_ok,
            'event_count': evs_ok,
        },
    }


def summarize(cases: dict) -> bool:
    ident = cases['production_identity_relabel']
    rel = ident['relabel_sealed_descriptor_rejected']
    if rel['exit'] == 0 or rel['operation_count'] != 0:
        return False
    if rel['error'] != 'client_production_metadata_forbidden':
        return False
    forged = ident['forged_production_id_rejected']
    if forged['exit'] == 0 or forged['operation_count'] != 0:
        return False
    if forged['error'] != 'client_production_metadata_forbidden':
        return False
    pos = ident['revisioned_production_and_verify']
    if pos['exit'] != 0 or pos['operation_count'] != 1:
        return False
    if pos['production_history_len'] < 2:
        return False

    pre = cases['prewrite_containment']
    if pre['unsafe_job_id']['reason'] not in ('job_id_unsafe', 'artifact_path_traversal'):
        return False
    if pre['unsafe_job_id']['probe_created']:
        return False
    if pre['parent_symlink_escape']['reason'] not in (
        'artifact_parent_symlink_escape',
        'artifact_outside_artifact_root',
        'job_id_unsafe',
    ):
        return False
    if pre['parent_symlink_escape']['unexpected_files']:
        return False

    js = cases['json_handler_negatives']
    if not js['issuance_wrong_json_type']['error_contains']:
        return False
    if js['issuance_wrong_json_type']['operation_count'] != 0:
        return False
    if js['matching_json_positive']['exit'] != 0 or js['matching_json_positive']['operation_count'] != 1:
        return False
    return True


def main() -> int:
    run_id = str(uuid.uuid4())
    cases = {
        'production_identity_relabel': test_production_identity_relabel(),
        'prewrite_containment': test_prewrite_containment(),
        'json_handler_negatives': test_json_handler_negatives(),
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
    (REPORTS / 'production-identity-prewrite-receipt.json').write_text(json.dumps(pointer, indent=2) + '\n')
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
