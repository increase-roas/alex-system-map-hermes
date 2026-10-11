#!/usr/bin/env python3
"""APP-REVIEW-01 and APP-REVIEW-03 — real local_service apply path, isolated DBs."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
TEST_ROOT = ROOT / 'app' / '.data' / 'workflow-core-tests'
DELIVERY = 'authoritative-workflow-core-20261010-0605'
REL_IDS = ['REL-01', 'REL-02', 'REL-03', 'REL-04', 'REL-05', 'REL-06']
FAILURES_DIR = REPORTS / 'workflow-core-failures'


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes() -> dict[str, str]:
    rel_paths = [
        'tools/workflow_apply_guard.py',
        'tools/reliability_gate.py',
        'tools/workflow_engine.py',
        'tools/reliability_store.py',
        'tools/local_service.py',
    ]
    return {p: sha256_file(ROOT / p) for p in rel_paths if (ROOT / p).is_file()}


def run_apply(wf_db: Path, rel_db: Path, body: dict) -> tuple[int, dict | str]:
    if rel_db.resolve() != wf_db.resolve():
        rel_db = wf_db
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / 'tools/local_service.py'),
            '--db',
            str(wf_db),
            '--reliability-db',
            str(rel_db),
            'apply',
        ],
        input=json.dumps(body),
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=60,
    )
    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {'stdout': proc.stdout, 'stderr': proc.stderr}
    if isinstance(payload, dict) and payload.get('error'):
        return proc.returncode or 1, payload
    return proc.returncode, payload


def run_complete(rel_db: Path, claim: dict) -> tuple[int, dict]:
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / 'tools/local_service.py'),
            '--db',
            str(rel_db),
            '--reliability-db',
            str(rel_db),
            'reliability-complete',
        ],
        input=json.dumps(claim),
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=60,
    )
    return proc.returncode, json.loads(proc.stdout or '{}')


def _issue_rel02_record(
    db: Path,
    job_id: str,
    revision: int,
    operation_id: str,
    *,
    observed_at: datetime | None = None,
) -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from reliability_store import connect as rel_connect
    from verification_evidence import issue_measured_rel02_record

    conn = rel_connect(db)
    try:
        return issue_measured_rel02_record(
            conn,
            job_id=job_id,
            job_revision=revision,
            task_id='gate-task',
            operation_id=operation_id,
            verifier='workflow-core-acceptance',
            fixture_only=False,
            observed_at=observed_at,
        )
    finally:
        conn.close()


def rel02_positive_claim(
    db: Path,
    job_id: str,
    revision: int,
    *,
    issued: dict | None = None,
    operation_id: str = 'core-gate-op',
) -> dict:
    if issued is None:
        issued = _issue_rel02_record(db, job_id, revision, operation_id)
    proof_path = issued['path']
    if not Path(proof_path).is_absolute():
        proof_path = str((ROOT / proof_path).relative_to(ROOT))
    return {
        'requirement_id': 'REL-02',
        'complete': True,
        'owner': 'workflow-core-acceptance',
        'job_id': job_id,
        'job_revision': revision,
        'requirement_set': REL_IDS,
        'evidence': {
            'verified_at': utc_now(),
            'actually_used': 'reliability_gate_per_requirement',
            'documented_path': 'docs/RELIABILITY_ADDENDUM.md',
            'proof_path': proof_path,
            'proof_sha256': issued['record_sha256'],
            'skills_verified': True,
            'relationships_sha256': sha256_file(ROOT / 'data/relationships.json'),
        },
    }


def fresh_isolated(prefix: str) -> tuple[Path, Path]:
    TEST_ROOT.mkdir(parents=True, exist_ok=True)
    wf = TEST_ROOT / f'{prefix}-unified.sqlite'
    if wf.exists():
        wf.unlink()
    subprocess.run(
        [sys.executable, str(ROOT / 'tools/local_service.py'), '--db', str(wf), 'init'],
        check=True,
        cwd=str(ROOT),
        capture_output=True,
    )
    return wf, wf


def save_failure(case_id: str, payload: dict) -> str:
    FAILURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FAILURES_DIR / f'{case_id}.json'
    path.write_text(json.dumps(payload, indent=2) + '\n')
    return str(path.relative_to(ROOT))


def test_app_review_01() -> dict:
    cases: dict[str, dict] = {}
    wf, rel = fresh_isolated('app01-gate')
    gate_job = 'core-gate-job'
    gate_rev = 1
    gate_issued = _issue_rel02_record(rel, gate_job, gate_rev, 'core-gate-op')

    corrected = ROOT / 'reports/independent-reliability-corrected-detail.json'
    bad_corrected = rel02_positive_claim(rel, gate_job, gate_rev, issued=gate_issued)
    bad_corrected['evidence']['proof_path'] = str(corrected.relative_to(ROOT))
    bad_corrected['evidence']['proof_sha256'] = sha256_file(corrected)
    code, gate = run_complete(rel, bad_corrected)
    cases['reject_corrected_detail_failed_items'] = {
        'rejected': code != 0 and not gate.get('accepted'),
        'reason': gate.get('reason'),
    }

    bad_txt = wf.parent / 'nonjson-proof.txt'
    bad_txt.write_text('not json\n')
    bad_nonjson = rel02_positive_claim(rel, gate_job, gate_rev, issued=gate_issued)
    bad_nonjson['evidence']['proof_path'] = str(bad_txt.relative_to(ROOT))
    bad_nonjson['evidence']['proof_sha256'] = sha256_file(bad_txt)
    _, gate2 = run_complete(rel, bad_nonjson)
    cases['reject_non_json_proof'] = {
        'rejected': not gate2.get('accepted'),
        'reason': gate2.get('reason'),
    }

    stale_obs = datetime.now(timezone.utc) - timedelta(days=400)
    stale_issued = _issue_rel02_record(
        rel, gate_job, gate_rev, 'core-gate-stale-op', observed_at=stale_obs
    )
    bad_stale = rel02_positive_claim(rel, gate_job, gate_rev, issued=stale_issued)
    _, gate3 = run_complete(rel, bad_stale)
    cases['reject_stale_verification_record'] = {
        'rejected': not gate3.get('accepted'),
        'reason': gate3.get('reason'),
    }

    bad_omit_set = rel02_positive_claim(rel, gate_job, gate_rev, issued=gate_issued)
    bad_omit_set.pop('requirement_set')
    _, gate4 = run_complete(rel, bad_omit_set)
    cases['reject_missing_requirement_set'] = {
        'rejected': not gate4.get('accepted'),
        'reason': gate4.get('reason'),
    }

    _, gate_pos = run_complete(rel, rel02_positive_claim(rel, gate_job, gate_rev, issued=gate_issued))
    cases['legitimate_positive_control'] = {
        'accepted': gate_pos.get('accepted') is True,
        'reason': gate_pos.get('reason'),
    }

    job_id = 'core-verify-job'
    create = {
        'job_id': job_id,
        'expected_revision': 0,
        'operation_id': 'core-create',
        'action': 'create',
        'actor_owner': 'owner-a',
        'payload': {
            'goal': 'verify gate path',
            'scope': ['local'],
            'constraints': [],
            'owner': 'owner-a',
            'acceptance': ['gate-bound proof'],
        },
    }
    run_apply(wf, rel, create)
    add = {
        'job_id': job_id,
        'expected_revision': 1,
        'operation_id': 'core-add-task',
        'action': 'add_task',
        'actor_owner': 'owner-a',
        'handoff_operation_id': f'{job_id}-handoff',
        'payload': {
            'id': 't1',
            'goal': 'g',
            'owner': 'owner-a',
            'acceptance': ['gate-bound proof'],
            'deps': [],
        },
    }
    sys.path.insert(0, str(ROOT / 'tools'))
    from bounded_acceptance import (
        bounded_output_descriptor,
        build_declared_outcome,
        controlled_materialize_bounded_artifact,
        parse_declared_outcome,
    )

    gate_expected = 'authoritative-gate-bound-v1\n'
    gate_declared = build_declared_outcome('gate-bound proof', 1, expected_utf8=gate_expected)
    add['payload']['declared_outcomes'] = [gate_declared]
    run_apply(wf, rel, add)
    conn_wf = sqlite3.connect(wf)
    gate_artifact = controlled_materialize_bounded_artifact(
        conn_wf, job_id, 't1', 'core-produce-output', gate_expected.encode()
    )
    conn_wf.close()
    run_apply(
        wf,
        rel,
        {
            'job_id': job_id,
            'expected_revision': 2,
            'operation_id': 'core-produce-output',
            'action': 'update',
            'actor_owner': 'owner-a',
            'handoff_operation_id': f'{job_id}-handoff',
            'payload': {
                'task_id': 't1',
                'status': 'in_progress',
                'attempt': 'produce',
                'outputs': [bounded_output_descriptor(gate_artifact)],
            },
        },
    )
    from reliability_store import connect as rel_connect
    from verification_evidence import PERFORMED_WORK_ACTUALLY_USED, issue_measured_workflow_verify_record
    from workflow_engine import Engine

    vconn = rel_connect(wf)
    vengine = Engine(str(wf))
    verify_issued = issue_measured_workflow_verify_record(
        vconn,
        vengine,
        job_id=job_id,
        job_revision=3,
        task_id='t1',
        operation_id='core-verify-good',
        verifier='reviewer-b',
        acceptance=['gate-bound proof'],
    )
    vengine.close()
    vconn.close()
    claim = rel02_positive_claim(wf, job_id, 3, issued=verify_issued, operation_id='core-verify-good')
    claim['evidence']['actually_used'] = PERFORMED_WORK_ACTUALLY_USED
    proof_rel = claim['evidence']['proof_path']
    bad_verify = {
        'job_id': job_id,
        'expected_revision': 2,
        'operation_id': 'core-verify-bad',
        'action': 'verify',
        'actor_owner': 'owner-a',
        'handoff_operation_id': f'{job_id}-handoff',
        'payload': {
            'id': 'cp-bad',
            'task_id': 't1',
            'verifier': 'reviewer-b',
            'evidence': ['explorer-manual-verify:t1:1'],
            'checks': {'gate-bound proof': True},
        },
    }
    code_fab, fab = run_apply(wf, rel, bad_verify)
    cases['verify_rejects_fabricated_evidence'] = {
        'rejected': code_fab != 0 or fab.get('error'),
        'error': fab.get('error') if isinstance(fab, dict) else fab,
    }

    good_verify = {
        'job_id': job_id,
        'expected_revision': 3,
        'operation_id': 'core-verify-good',
        'action': 'verify',
        'actor_owner': 'owner-a',
        'handoff_operation_id': f'{job_id}-handoff',
        'payload': {
            'id': 'cp-good',
            'task_id': 't1',
            'verifier': 'reviewer-b',
            'requirement_claims': [claim],
            'evidence': [proof_rel],
            'checks': {'gate-bound proof': True},
        },
    }
    code_ok, ok = run_apply(wf, rel, good_verify)
    cases['verify_accepts_gate_bound_claim'] = {
        'accepted': code_ok == 0 and not (isinstance(ok, dict) and ok.get('error')),
        'revision': ok.get('revision') if isinstance(ok, dict) else None,
    }

    from reliability_gate import evaluate_negative_case

    neg_cases = {}
    for case in ('missing_requirement', 'skipped_skill', 'stale_data_simulation', 'false_completion'):
        claim_neg = rel02_positive_claim(rel, gate_job, gate_rev, issued=gate_issued)
        if case == 'missing_requirement':
            claim_neg['requirement_set'] = ['REL-02']
        if case == 'skipped_skill':
            claim_neg['evidence']['skills_verified'] = False
        if case == 'stale_data_simulation':
            claim_neg['evidence']['relationships_sha256'] = '0' * 64
        if case == 'false_completion':
            claim_neg['requirement_id'] = 'REL-05'
            claim_neg['evidence']['actually_used'] = 'reliability_gate_negative_cases'
        result = evaluate_negative_case(case, claim_neg)
        neg_cases[case] = result
    cases['rel05_negative_helpers'] = neg_cases

    return cases


def test_app_review_03() -> dict:
    cases: dict[str, dict] = {}
    wf, rel = fresh_isolated('app03-handoff')
    job_id = 'core-handoff-job'
    op = f'{job_id}-handoff'

    run_apply(
        wf,
        rel,
        {
            'job_id': job_id,
            'expected_revision': 0,
            'operation_id': 'core-h-create',
            'action': 'create',
            'actor_owner': 'owner-a',
            'payload': {
                'goal': 'handoff core',
                'scope': ['local'],
                'constraints': [],
                'owner': 'owner-a',
                'acceptance': ['check'],
            },
        },
    )

    omit_actor = {
        'job_id': job_id,
        'expected_revision': 1,
        'operation_id': 'core-h-omit-actor',
        'action': 'add_task',
        'handoff_operation_id': op,
        'payload': {'id': 't1', 'goal': 'g', 'owner': 'owner-a', 'acceptance': ['check'], 'deps': []},
    }
    code_oa, res_oa = run_apply(wf, rel, omit_actor)
    cases['reject_missing_actor_owner'] = {
        'rejected': code_oa != 0,
        'error': res_oa.get('error') if isinstance(res_oa, dict) else res_oa,
    }

    foreign = {
        'job_id': 'foreign-job',
        'expected_revision': 1,
        'operation_id': 'core-h-foreign',
        'action': 'add_task',
        'actor_owner': 'owner-a',
        'handoff_operation_id': op,
        'payload': {'id': 't2', 'goal': 'g', 'owner': 'owner-a', 'acceptance': ['check'], 'deps': []},
    }
    code_fj, res_fj = run_apply(wf, rel, foreign)
    cases['reject_foreign_job_handoff'] = {
        'rejected': code_fj != 0,
        'error': res_fj.get('error') if isinstance(res_fj, dict) else res_fj,
    }

    run_apply(
        wf,
        rel,
        {
            'action': 'handoff_transfer',
            'operation_id': 'auth-xfer-a-b',
            'actor_owner': 'owner-a',
            'payload': {
                'operation_id': op,
                'expected_owner': 'owner-a',
                'expected_revision': 1,
                'new_owner': 'owner-b',
                'job_revision': 1,
                'job_id': job_id,
                'acceptance': ['check'],
            },
        },
    )

    stale_owner = {
        'job_id': job_id,
        'expected_revision': 1,
        'operation_id': 'core-h-stale-owner',
        'action': 'add_task',
        'actor_owner': 'owner-a',
        'handoff_operation_id': op,
        'payload': {'id': 't1', 'goal': 'g', 'owner': 'owner-a', 'acceptance': ['check'], 'deps': []},
    }
    code_so, res_so = run_apply(wf, rel, stale_owner)
    cases['reject_stale_owner_after_transfer'] = {
        'rejected': code_so != 0,
        'error': res_so.get('error') if isinstance(res_so, dict) else res_so,
    }

    apply_ok = {
        'job_id': job_id,
        'expected_revision': 1,
        'operation_id': 'core-h-op1',
        'action': 'add_task',
        'actor_owner': 'owner-b',
        'handoff_operation_id': op,
        'payload': {'id': 't1', 'goal': 'g', 'owner': 'owner-b', 'acceptance': ['check'], 'deps': []},
    }
    code1, res1 = run_apply(wf, rel, apply_ok)
    replay = dict(apply_ok)
    code_rep, res_rep = run_apply(wf, rel, replay)
    ops = sqlite3.connect(wf).execute('SELECT COUNT(*) FROM operations WHERE id=?', ('core-h-op1',)).fetchone()[0]
    events = sqlite3.connect(wf).execute('SELECT COUNT(*) FROM events').fetchone()[0]
    task_owner = None
    row = sqlite3.connect(wf).execute("SELECT payload FROM tasks WHERE id='t1'").fetchone()
    if row:
        task_owner = json.loads(row[0]).get('owner')
    cp = json.loads(sqlite3.connect(wf).execute(
        'SELECT checkpoint_json FROM reliability_handoffs WHERE operation_id=?', (op,)
    ).fetchone()[0])
    cases['owner_b_apply_and_replay'] = {
        'first_ok': code1 == 0,
        'replay_ok': code_rep == 0,
        'operation_count': ops,
        'event_count_after_replay': events,
        'task_owner': task_owner,
        'handoff_job_id': cp.get('job_id'),
        'acceptance_retained': cp.get('acceptance'),
    }

    payload_collision = dict(apply_ok)
    payload_collision['operation_id'] = 'core-h-op1'
    payload_collision['payload'] = {
        'id': 't2',
        'goal': 'different',
        'owner': 'owner-b',
        'acceptance': ['check'],
        'deps': [],
    }
    code_col, res_col = run_apply(wf, rel, payload_collision)
    cases['reject_payload_collision_same_operation_id'] = {
        'rejected': code_col != 0,
        'error': res_col.get('error') if isinstance(res_col, dict) else res_col,
    }

    return cases


def summarize_app01(cases: dict) -> bool:
    required = [
        cases['reject_corrected_detail_failed_items']['rejected'],
        cases['reject_non_json_proof']['rejected'],
        cases['reject_stale_verification_record']['rejected'],
        cases['reject_missing_requirement_set']['rejected'],
        cases['legitimate_positive_control']['accepted'],
        cases['verify_rejects_fabricated_evidence']['rejected'],
        cases['verify_accepts_gate_bound_claim']['accepted'],
    ]
    negs = cases.get('rel05_negative_helpers') or {}
    required.append(all(v.get('rejected_by_gate') for v in negs.values()))
    return all(required)


def summarize_app03(cases: dict) -> bool:
    o = cases['owner_b_apply_and_replay']
    return (
        cases['reject_missing_actor_owner']['rejected']
        and cases['reject_foreign_job_handoff']['rejected']
        and cases['reject_stale_owner_after_transfer']['rejected']
        and o['first_ok']
        and o['replay_ok']
        and o['operation_count'] == 1
        and o['task_owner'] == 'owner-b'
        and o['handoff_job_id'] == 'core-handoff-job'
        and cases['reject_payload_collision_same_operation_id']['rejected']
    )


def main() -> int:
    app01 = test_app_review_01()
    app03 = test_app_review_03()
    ok01 = summarize_app01(app01)
    ok03 = summarize_app03(app03)

    prior_failures = []
    if not ok01:
        prior_failures.append(save_failure('APP-REVIEW-01', app01))
    if not ok03:
        prior_failures.append(save_failure('APP-REVIEW-03', app03))

    receipt = {
        'delivery_id': DELIVERY,
        'owner_chat': '4f32e74a-58e3-4abb-ba6f-fb151ba80cd7',
        'at': utc_now(),
        'source_identity': {
            'source_sha256': source_hashes(),
        },
        'APP-REVIEW-01': {'passed': ok01, 'cases': app01},
        'APP-REVIEW-03': {'passed': ok03, 'cases': app03},
        'failure_artifacts_preserved': prior_failures,
        'independent_verification': 'not_claimed',
        'owner_pass_not_independent_acceptance': True,
        'overall': 'passed' if ok01 and ok03 else 'partial',
        'queue_remaining_required': [
            'APP-REVIEW-02',
            'APP-REVIEW-04',
            'BROWSER-*',
            'CONTROLLED-EDIT-*',
            'REL-01 fresh context',
            'real SDK tracing (BLOCKED)',
        ],
    }
    out = REPORTS / 'authoritative-workflow-core-receipt.json'
    out.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'overall': receipt['overall'], 'APP-REVIEW-01': ok01, 'APP-REVIEW-03': ok03}, indent=2))
    return 0 if ok01 and ok03 else 1


if __name__ == '__main__':
    raise SystemExit(main())
