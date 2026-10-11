#!/usr/bin/env python3
"""Delivery contract-provenance-types-containment-20261010-0658."""
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
DELIVERY = 'contract-provenance-types-containment-20261010-0658'
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
    'tools/contract_provenance_types_containment_acceptance.py',
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
            'operation_id': 'cptc-create',
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
            'operation_id': 'cptc-add',
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
        'owner': 'cptc-acceptance',
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


def produce_bound(db: Path, job: str, op: str, rev: int, op_id: str, content: bytes) -> dict:
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


def verify_with_record(db: Path, job: str, op: str, revision: int, operation_id: str, issued: dict) -> tuple[int, str, int, int]:
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


def test_provenance_revision() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from bounded_acceptance import build_declared_outcome

    job = 'prov-job'
    op = f'{job}-handoff'
    db = fresh_db('provenance')
    wrong_bytes = b'wrong-but-already-written\n'
    expected_v1 = 'contract-provenance-v1\n'
    decl_v1 = build_declared_outcome('proof-bound', 1, expected_utf8=expected_v1)
    setup_job(db, job, op, [decl_v1])
    produce_bound(db, job, op, 2, 'cptc-produce-wrong', wrong_bytes)
    from workflow_engine import Engine

    engine_sealed = Engine(str(db))
    saved_wrong_outputs = list(engine_sealed.tasks(job)['t1']['outputs'])
    engine_sealed.close()

    rewrite_same_rev = build_declared_outcome('proof-bound', 1, expected_utf8=wrong_bytes.decode())
    code_rw, _, err_rw = run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 3,
            'operation_id': 'cptc-rewrite-same-rev',
            'action': 'update',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'task_id': 't1',
                'declared_outcomes': [rewrite_same_rev],
            },
        },
    )
    ops_rw, evs_rw = count_op_events(db, 'cptc-rewrite-same-rev')

    decl_v2 = build_declared_outcome('proof-bound', 2, expected_utf8=expected_v1)
    code_d2, _, err_d2 = run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 3,
            'operation_id': 'cptc-decl-v2',
            'action': 'update',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {'task_id': 't1', 'declared_outcomes': [decl_v2]},
        },
    )
    ops_d2, evs_d2 = count_op_events(db, 'cptc-decl-v2')

    from workflow_engine import Engine

    engine = Engine(str(db))
    task_after_decl = engine.tasks(job)['t1']
    engine.close()
    history_len = len(task_after_decl.get('declaration_history') or [])
    outputs_cleared = not task_after_decl.get('outputs')

    db_ok = fresh_db('provenance-positive')
    setup_job(db_ok, job, op, [decl_v1])
    produce_bound(db_ok, job, op, 2, 'cptc-produce-v1-good', expected_v1.encode())
    issued_v1 = issue_record(db_ok, job, 3, 'cptc-v1-record-op')
    decl_v2b = build_declared_outcome('proof-bound', 2, expected_utf8=expected_v1)
    run_apply(
        db_ok,
        {
            'job_id': job,
            'expected_revision': 3,
            'operation_id': 'cptc-decl-v2b',
            'action': 'update',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {'task_id': 't1', 'declared_outcomes': [decl_v2b]},
        },
    )
    code_old, err_old, ops_old, evs_old = verify_with_record(
        db_ok, job, op, 4, 'cptc-verify-old-proof', issued_v1
    )
    produce_bound(db_ok, job, op, 4, 'cptc-produce-v2-good', expected_v1.encode())
    verify_op = 'cptc-verify-new'
    issued_new = issue_record(db_ok, job, 5, verify_op)
    code_ok, err_ok, ops_ok, evs_ok = verify_with_record(db_ok, job, op, 5, verify_op, issued_new)

    code_reuse, _, err_reuse = run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 4,
            'operation_id': 'cptc-reuse-old-binding',
            'action': 'update',
            'actor_owner': 'owner-a',
            'handoff_operation_id': op,
            'payload': {
                'task_id': 't1',
                'status': 'in_progress',
                'attempt': 'reuse',
                'outputs': saved_wrong_outputs,
            },
        },
    )

    return {
        'same_revision_rewrite_rejected': {
            'exit': code_rw,
            'error': err_rw,
            'operation_count': ops_rw,
            'event_count': evs_rw,
        },
        'revisioned_declaration_committed': {
            'exit': code_d2,
            'error': err_d2,
            'operation_count': ops_d2,
            'declaration_history_entries': history_len,
            'outputs_cleared': outputs_cleared,
            'task_status': task_after_decl.get('status'),
        },
        'old_proof_after_contract_change': {
            'exit': code_old,
            'error': err_old,
            'operation_count': ops_old,
            'event_count': evs_old,
        },
        'fresh_proof_positive': {
            'exit': code_ok,
            'error': err_ok,
            'operation_count': ops_ok,
            'event_count': evs_ok,
        },
        'stale_descriptor_reuse_rejected': {'exit': code_reuse, 'error': err_reuse},
    }


def test_json_type_equality() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from bounded_acceptance import (
        build_declared_outcome,
        json_values_equal,
        measure_criterion_outcome,
    )

    cases: dict = {}
    cases['pure_ok_one_vs_true'] = {
        'equal': json_values_equal({'ok': True}, json.loads('{"ok":1}')),
    }
    cases['pure_ok_false_vs_zero'] = {
        'equal': json_values_equal({'ok': False}, json.loads('{"ok":0}')),
    }

    decl = build_declared_outcome('proof-bound', 1, expected_result={'ok': True, 'nested': {'flag': False}})
    job = 'json-job'
    op = f'{job}-handoff'
    db = fresh_db('json-types')
    setup_job(db, job, op, [decl])
    produce_bound(db, job, op, 2, 'cptc-json-bad', b'{"ok":1,"nested":{"flag":false}}\n')
    from workflow_engine import Engine

    engine = Engine(str(db))
    bad_task = engine.tasks(job)['t1']
    engine.close()
    _, _, reason_bad = measure_criterion_outcome('proof-bound', bad_task)
    cases['handler_path_wrong_numeric'] = {'reason': reason_bad}

    db_ok = fresh_db('json-types-ok')
    setup_job(db_ok, job, op, [decl])
    good_body = json.dumps({'ok': True, 'nested': {'flag': False}}).encode() + b'\n'
    produce_bound(db_ok, job, op, 2, 'cptc-json-good', good_body)
    json_verify_op = 'cptc-json-verify'
    issued = issue_record(db_ok, job, 3, json_verify_op)
    code, err, ops, evs = verify_with_record(db_ok, job, op, 3, json_verify_op, issued)
    cases['handler_path_matching_json'] = {
        'exit': code,
        'error': err,
        'operation_count': ops,
        'event_count': evs,
    }
    return cases


def test_artifact_root_containment() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from bounded_acceptance import (
        bounded_output_descriptor,
        build_declared_outcome,
        measure_bounded_artifact,
        measure_criterion_outcome,
        parse_declared_outcome,
    )
    from verification_evidence import sha256_file

    decl = build_declared_outcome('proof-bound', 1, expected_utf8='in-root-bytes\n')
    contract = parse_declared_outcome(decl)
    job = 'root-job'
    op = f'{job}-handoff'
    db = fresh_db('artifact-root')
    setup_job(db, job, op, [decl])

    addendum = ROOT / 'docs/RELIABILITY_ADDENDUM.md'
    traversal_desc = {
        'schema': 'bounded_artifact_v1',
        'relative_path': 'work/task-artifacts/../../docs/RELIABILITY_ADDENDUM.md',
        'sha256': sha256_file(addendum),
        'byte_length': addendum.stat().st_size,
        'declared_contract_revision': contract['revision'],
        'declared_contract_sha256': contract['contract_sha256'],
    }
    ok_trav, reason_trav, _ = measure_bounded_artifact(traversal_desc)
    task_trav = {
        'acceptance': ['proof-bound'],
        'declared_outcomes': [decl],
        'outputs': [bounded_output_descriptor(traversal_desc)],
    }
    _, _, reason_task_trav = measure_criterion_outcome('proof-bound', task_trav)

    escape_dir = ARTIFACT_ROOT / 'escape-test'
    escape_dir.mkdir(parents=True, exist_ok=True)
    link_path = escape_dir / 'link-out.txt'
    target = ROOT / 'docs' / 'RELIABILITY_ADDENDUM.md'
    if link_path.exists() or link_path.is_symlink():
        link_path.unlink()
    os.symlink(target, link_path)
    link_desc = {
        'schema': 'bounded_artifact_v1',
        'relative_path': 'work/task-artifacts/escape-test/link-out.txt',
        'sha256': sha256_file(addendum),
        'byte_length': addendum.stat().st_size,
        'declared_contract_revision': contract['revision'],
        'declared_contract_sha256': contract['contract_sha256'],
    }
    ok_link, reason_link, _ = measure_bounded_artifact(link_desc)

    code_issue = 0
    err_issue = ''
    try:
        produce_bound(db, job, op, 2, 'cptc-in-root-good', b'in-root-bytes\n')
        root_verify_op = 'cptc-root-verify'
        issued = issue_record(db, job, 3, root_verify_op)
        code_issue, err_issue, ops_i, evs_i = verify_with_record(db, job, op, 3, root_verify_op, issued)
    except Exception as exc:
        code_issue = 1
        err_issue = str(exc)
        ops_i = evs_i = -1

    return {
        'traversal_descriptor_rejected': {
            'measure_ok': ok_trav,
            'measure_reason': reason_trav,
            'criterion_reason': reason_task_trav,
        },
        'symlink_escape_rejected': {'measure_ok': ok_link, 'measure_reason': reason_link},
        'in_root_positive': {
            'exit': code_issue,
            'error': err_issue,
            'operation_count': ops_i,
            'event_count': evs_i,
        },
    }


def summarize(cases: dict) -> bool:
    prov = cases['provenance_revision']
    if prov['same_revision_rewrite_rejected']['error'] != 'declared_outcome_revision_unchanged':
        return False
    if prov['same_revision_rewrite_rejected']['operation_count'] != 0:
        return False
    if prov['revisioned_declaration_committed']['exit'] != 0:
        return False
    if not prov['revisioned_declaration_committed']['outputs_cleared']:
        return False
    if prov['revisioned_declaration_committed']['declaration_history_entries'] < 1:
        return False
    old_err = prov['old_proof_after_contract_change']['error']
    if prov['old_proof_after_contract_change']['exit'] == 0:
        return False
    if old_err not in (
        'declared_outcome_contract_changed',
        'output_declaration_binding_stale',
        'verification_record_revision_mismatch',
    ):
        return False
    if prov['old_proof_after_contract_change']['operation_count'] != 0:
        return False
    if prov['fresh_proof_positive']['exit'] != 0 or prov['fresh_proof_positive']['operation_count'] != 1:
        return False
    if prov['stale_descriptor_reuse_rejected']['exit'] == 0:
        return False
    if prov['stale_descriptor_reuse_rejected']['error'] not in (
        'output_declaration_binding_stale',
        'declared_outcome_revision_unchanged',
        'client_production_metadata_forbidden',
    ):
        return False

    js = cases['json_type_equality']
    if js['pure_ok_one_vs_true']['equal']:
        return False
    if js['pure_ok_false_vs_zero']['equal']:
        return False
    if js['handler_path_wrong_numeric']['reason'] != 'declared_result_mismatch':
        return False
    if js['handler_path_matching_json']['exit'] != 0:
        return False

    root = cases['artifact_root_containment']
    if root['traversal_descriptor_rejected']['measure_ok']:
        return False
    if root['traversal_descriptor_rejected']['criterion_reason'] not in (
        'artifact_path_traversal',
        'artifact_outside_artifact_root',
        'artifact_not_allowlisted',
        'output_missing_production_identity',
    ):
        return False
    if root['symlink_escape_rejected']['measure_ok']:
        return False
    if root['symlink_escape_rejected']['measure_reason'] not in (
        'artifact_symlink_not_allowed',
        'artifact_symlink_escape',
        'artifact_outside_artifact_root',
    ):
        return False
    if root['in_root_positive']['exit'] != 0:
        return False
    return True


def main() -> int:
    run_id = str(uuid.uuid4())
    cases = {
        'provenance_revision': test_provenance_revision(),
        'json_type_equality': test_json_type_equality(),
        'artifact_root_containment': test_artifact_root_containment(),
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
    (REPORTS / 'contract-provenance-types-containment-receipt.json').write_text(json.dumps(pointer, indent=2) + '\n')
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
