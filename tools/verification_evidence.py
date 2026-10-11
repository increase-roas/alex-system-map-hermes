"""Versioned verification records — authoritative proof for completion gates."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 'verification_record_v1'
DEFAULT_MAX_AGE_SECONDS = 7 * 24 * 3600
FUTURE_SKEW_SECONDS = 300
RECORD_DIR = ROOT / 'work' / 'reliability' / 'verification-records'
ISOLATED_JOB_PREFIX = 'isolated-'
REL02_PRECONDITION_ACTUALLY_USED = 'reliability_gate_precondition_checks'
PERFORMED_WORK_ACTUALLY_USED = 'workflow_verify_performed_work'
_PREPARED_REGISTRY_IDS: set[int] = set()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def ensure_registry(conn: sqlite3.Connection) -> None:
    conn_id = id(conn)
    if conn_id in _PREPARED_REGISTRY_IDS:
        return
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS verification_records(
            record_id TEXT PRIMARY KEY,
            requirement_id TEXT NOT NULL,
            job_id TEXT NOT NULL,
            job_revision INTEGER NOT NULL,
            record_sha256 TEXT NOT NULL,
            path TEXT NOT NULL,
            issued_at TEXT NOT NULL
        )
        '''
    )
    _PREPARED_REGISTRY_IDS.add(conn_id)


def prepare_registry(conn: sqlite3.Connection) -> sqlite3.Connection:
    ensure_registry(conn)
    return conn


def catalog_fingerprints() -> dict[str, str]:
    fps: dict[str, str] = {}
    rel_path = ROOT / 'data' / 'relationships.json'
    if rel_path.is_file():
        fps['data/relationships.json'] = sha256_file(rel_path)
    doc = ROOT / 'docs' / 'RELIABILITY_ADDENDUM.md'
    if doc.is_file():
        fps['docs/RELIABILITY_ADDENDUM.md'] = sha256_file(doc)
    return fps


def measure_rel02_gate_checks() -> dict[str, bool]:
    """Run REL-02 gate preconditions; values are measured, not asserted by callers."""
    rel_path = ROOT / 'data' / 'relationships.json'
    addendum = ROOT / 'docs' / 'RELIABILITY_ADDENDUM.md'
    gate_module = ROOT / 'tools' / 'reliability_gate.py'
    skills_ok, _missing = _required_skills_present()
    live_hash = sha256_file(rel_path) if rel_path.is_file() else ''
    return {
        'relationships_catalog_present': rel_path.is_file(),
        'relationships_hash_matches_live': bool(live_hash)
        and live_hash == catalog_fingerprints().get('data/relationships.json'),
        'reliability_addendum_present': addendum.is_file(),
        'gate_module_present': gate_module.is_file(),
        'required_skills_installed': skills_ok,
    }


def measure_workflow_verify_checks(
    engine,
    job_id: str,
    task_id: str,
    acceptance: list[str],
) -> tuple[dict[str, bool], list[dict], list[str]]:
    from bounded_acceptance import measure_criterion_outcome

    tasks = engine.tasks(job_id)
    task = tasks.get(task_id)
    if not task:
        return {'task_exists': False}, [], ['task_missing']
    checks: dict[str, bool] = {'task_exists': True}
    listed = set(task.get('acceptance') or [])
    checks['acceptance_criteria_declared'] = listed == set(acceptance)
    observed_proofs: list[dict] = []
    failure_reasons: list[str] = []
    for criterion in acceptance:
        if criterion not in listed:
            checks['acceptance_criteria_declared'] = False
            failure_reasons.append('acceptance_criterion_not_declared')
            continue
        fragment, proofs, reason = measure_criterion_outcome(criterion, task)
        checks.update(fragment)
        observed_proofs.extend(proofs)
        if reason:
            failure_reasons.append(reason)
    checks['all_acceptance_outcomes_verified'] = (
        not failure_reasons
        and all(v is True for k, v in checks.items() if k not in ('task_exists',))
    )
    return checks, observed_proofs, failure_reasons


def _required_skills_present() -> tuple[bool, list[str]]:
    from project_context_loader import parse_skills_from_docs

    missing = []
    for rel in parse_skills_from_docs():
        if not (ROOT / rel).is_file():
            missing.append(rel)
    return not missing, missing


def issue_record(
    conn: sqlite3.Connection,
    *,
    requirement_id: str,
    job_id: str,
    job_revision: int,
    task_id: str | None,
    operation_id: str | None,
    verifier: str,
    checks: dict[str, bool],
    actually_used: str,
    skills_verified: bool,
    fixture_only: bool,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    observed_at: datetime | None = None,
    commit: bool = True,
    observed_proofs: list[dict] | None = None,
) -> dict:
    """Issue a record only after caller has executed checks (outcome derived from checks)."""
    if not checks or not all(checks.values()):
        failed = {key: value for key, value in checks.items() if not value}
        raise ValueError('checks failed before issuing verification record: ' + json.dumps(failed))
    prepare_registry(conn)
    observed = (observed_at or utc_now()).replace(microsecond=0)
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    record_id = str(uuid.uuid4())
    scope = {
        'job_id': job_id,
        'job_revision': job_revision,
        'task_id': task_id,
        'operation_id': operation_id,
        'verifier': verifier,
    }
    body = {
        'schema_version': SCHEMA_VERSION,
        'record_id': record_id,
        'fixture_only': fixture_only,
        'outcome': 'passed',
        'requirement_id': requirement_id.upper(),
        'scope': scope,
        'source_fingerprints': catalog_fingerprints(),
        'checks': checks,
        'actually_used': actually_used,
        'skills_verified_at_issue': skills_verified,
        'verifier': verifier,
        'observed_at': observed.isoformat(),
        'max_age_seconds': max_age_seconds,
    }
    if observed_proofs:
        body['observed_proofs'] = observed_proofs
    body_for_hash = dict(body)
    canonical = json.dumps(body_for_hash, sort_keys=True, separators=(',', ':'))
    content_sha = sha256_bytes(canonical.encode())
    body['record_sha256'] = content_sha
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    rel_path = Path('work/reliability/verification-records') / f'{record_id}.json'
    path = ROOT / rel_path
    path.write_text(json.dumps(body, indent=2) + '\n')
    file_sha = sha256_file(path)
    conn.execute(
        'INSERT INTO verification_records VALUES(?,?,?,?,?,?,?)',
        (record_id, requirement_id.upper(), job_id, job_revision, file_sha, str(rel_path), observed.isoformat()),
    )
    if commit:
        conn.commit()
    return {'record_id': record_id, 'path': str(rel_path), 'record_sha256': file_sha, 'body': body}


def issue_measured_rel02_record(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    job_revision: int,
    task_id: str | None,
    operation_id: str | None,
    verifier: str,
    fixture_only: bool = False,
    observed_at: datetime | None = None,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> dict:
    checks = measure_rel02_gate_checks()
    skills_ok, _ = _required_skills_present()
    return issue_record(
        conn,
        requirement_id='REL-02',
        job_id=job_id,
        job_revision=job_revision,
        task_id=task_id,
        operation_id=operation_id,
        verifier=verifier,
        checks=checks,
        actually_used=REL02_PRECONDITION_ACTUALLY_USED,
        skills_verified=skills_ok,
        fixture_only=fixture_only,
        observed_at=observed_at,
        max_age_seconds=max_age_seconds,
    )


def issue_measured_workflow_verify_record(
    conn: sqlite3.Connection,
    engine,
    *,
    job_id: str,
    job_revision: int,
    task_id: str,
    operation_id: str,
    verifier: str,
    acceptance: list[str],
) -> dict:
    checks, observed_proofs, failure_reasons = measure_workflow_verify_checks(
        engine, job_id, task_id, acceptance
    )
    if failure_reasons:
        raise ValueError(
            'workflow verify checks failed: ' + json.dumps({'reasons': failure_reasons, 'checks': checks})
        )
    return issue_record(
        conn,
        requirement_id='REL-02',
        job_id=job_id,
        job_revision=job_revision,
        task_id=task_id,
        operation_id=operation_id,
        verifier=verifier,
        checks=checks,
        actually_used=PERFORMED_WORK_ACTUALLY_USED,
        skills_verified=False,
        fixture_only=False,
        observed_proofs=observed_proofs,
    )


def load_record(path: Path) -> dict:
    return json.loads(path.read_text())


def _fixture_only_allowed(record: dict, claim: dict, *, for_workflow_verify: bool) -> tuple[bool, str]:
    if not record.get('fixture_only'):
        return True, 'ok'
    if for_workflow_verify:
        return False, 'verification_record_fixture_only'
    if not claim.get('isolated_test_fixture'):
        return False, 'verification_record_fixture_only'
    job = (record.get('scope') or {}).get('job_id') or claim.get('job_id')
    if not str(job or '').startswith(ISOLATED_JOB_PREFIX):
        return False, 'fixture_only_requires_isolated_job_id'
    return True, 'ok'


def validate_record_against_claim(
    record: dict,
    claim: dict,
    now: datetime | None = None,
    *,
    workflow_scope: dict | None = None,
    for_workflow_verify: bool = False,
) -> tuple[bool, str]:
    now = now or utc_now()
    if record.get('schema_version') != SCHEMA_VERSION:
        return False, 'verification_record_schema_mismatch'
    if record.get('outcome') != 'passed':
        return False, 'verification_record_not_passed'
    ok_fixture, reason_fixture = _fixture_only_allowed(
        record, claim, for_workflow_verify=for_workflow_verify
    )
    if not ok_fixture:
        return False, reason_fixture
    req = str(claim.get('requirement_id', '')).upper()
    if record.get('requirement_id') != req:
        return False, 'verification_record_requirement_mismatch'
    scope = record.get('scope') or {}
    claim_job = claim.get('job_id')
    claim_rev = claim.get('job_revision')
    if not claim_job or claim_rev is None:
        return False, 'claim_job_scope_required'
    if scope.get('job_id') != claim_job:
        return False, 'verification_record_job_mismatch'
    if scope.get('job_revision') != claim_rev:
        return False, 'verification_record_revision_mismatch'
    record_verifier = scope.get('verifier') or record.get('verifier')
    if workflow_scope:
        for key in ('task_id', 'operation_id', 'verifier'):
            expected = workflow_scope.get(key)
            if expected is None:
                continue
            actual = scope.get(key) if key != 'verifier' else record_verifier
            if actual != expected:
                return False, f'verification_record_{key}_mismatch'
    try:
        observed = datetime.fromisoformat(str(record.get('observed_at', '')).replace('Z', '+00:00'))
    except ValueError:
        return False, 'verification_record_invalid_observed_at'
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    age = (now - observed).total_seconds()
    max_age = int(record.get('max_age_seconds') or DEFAULT_MAX_AGE_SECONDS)
    if age > max_age:
        return False, 'verification_record_stale'
    if age < -FUTURE_SKEW_SECONDS:
        return False, 'verification_record_future_observed_at'
    live = catalog_fingerprints()
    stored = record.get('source_fingerprints') or {}
    for key, expected in stored.items():
        if live.get(key) != expected:
            return False, 'verification_record_source_fingerprint_stale'
    content_sha = record.get('record_sha256')
    if content_sha:
        body = dict(record)
        body.pop('record_sha256', None)
        actual = sha256_bytes(json.dumps(body, sort_keys=True, separators=(',', ':')).encode())
        if actual != content_sha:
            return False, 'verification_record_content_sha256_mismatch'
    evidence = claim.get('evidence') or {}
    claim_used = evidence.get('actually_used')
    record_used = record.get('actually_used')
    if record_used != claim_used:
        legacy_precondition = (
            claim_used == 'reliability_gate_per_requirement'
            and record_used == REL02_PRECONDITION_ACTUALLY_USED
        )
        if not legacy_precondition:
            return False, 'verification_record_actually_used_mismatch'
    if for_workflow_verify and record.get('actually_used') != PERFORMED_WORK_ACTUALLY_USED:
        return False, 'verification_record_not_performed_work'
    if (
        not for_workflow_verify
        and req == 'REL-02'
        and record.get('actually_used')
        not in (
            REL02_PRECONDITION_ACTUALLY_USED,
            'reliability_gate_per_requirement',
            PERFORMED_WORK_ACTUALLY_USED,
        )
    ):
        return False, 'verification_record_actually_used_mismatch'
    if req == 'REL-02' and record.get('skills_verified_at_issue') is not True:
        if record.get('actually_used') == REL02_PRECONDITION_ACTUALLY_USED:
            return False, 'verification_record_skills_not_verified'
    checks = record.get('checks') or {}
    if not checks or not all(checks.values()):
        return False, 'verification_record_checks_incomplete'
    return True, 'ok'


def verify_registry_row(
    conn: sqlite3.Connection,
    record: dict,
    file_sha256: str,
    proof_path: str = '',
) -> tuple[bool, str]:
    row = conn.execute(
        'SELECT record_id, requirement_id, job_id, job_revision, record_sha256, path '
        'FROM verification_records WHERE record_id=?',
        (record.get('record_id'),),
    ).fetchone()
    if not row:
        return False, 'verification_record_not_registered'
    scope = record.get('scope') or {}
    if row['record_sha256'] != file_sha256:
        return False, 'verification_record_registry_hash_mismatch'
    if row['requirement_id'] != record.get('requirement_id'):
        return False, 'verification_record_registry_requirement_mismatch'
    if row['job_id'] != scope.get('job_id'):
        return False, 'verification_record_registry_job_mismatch'
    if int(row['job_revision']) != int(scope.get('job_revision')):
        return False, 'verification_record_registry_revision_mismatch'
    registered_path = str(row['path']).replace('\\', '/').lstrip('/')
    if proof_path and registered_path != proof_path.replace('\\', '/').lstrip('/'):
        return False, 'verification_record_registry_path_mismatch'
    return True, 'ok'


def resolve_proof_evidence(
    evidence: dict,
    claim: dict,
    conn: sqlite3.Connection | None = None,
    *,
    workflow_scope: dict | None = None,
    for_workflow_verify: bool = False,
) -> tuple[bool, str]:
    proof_path = evidence.get('proof_path')
    if not proof_path:
        return False, 'proof_path_required'
    path = ROOT / proof_path
    if not path.is_file():
        return False, 'proof_path_missing'
    expected = evidence.get('proof_sha256')
    if not expected:
        return False, 'proof_sha256_required'
    actual = sha256_file(path)
    if actual != expected:
        return False, 'proof_sha256_mismatch'
    try:
        record = load_record(path)
    except json.JSONDecodeError:
        return False, 'proof_not_valid_json'
    normalized_path = str(proof_path).replace('\\', '/').lstrip('/')
    ok, reason = validate_record_against_claim(
        record,
        claim,
        workflow_scope=workflow_scope,
        for_workflow_verify=for_workflow_verify,
    )
    if not ok:
        return False, reason
    if conn is not None:
        ok_reg, reg_reason = verify_registry_row(conn, record, actual, normalized_path)
        if not ok_reg:
            return False, reg_reason
    if for_workflow_verify and conn is not None and workflow_scope:
        ok_live, live_reason = _remeasure_observed_proofs_at_consumption(
            conn, record, workflow_scope
        )
        if not ok_live:
            return False, live_reason
    return True, 'ok'


def _workflow_db_path(conn: sqlite3.Connection) -> str | None:
    row = conn.execute('PRAGMA database_list').fetchone()
    if not row or not row[2]:
        return None
    return str(row[2])


def _remeasure_observed_proofs_at_consumption(
    conn: sqlite3.Connection,
    record: dict,
    workflow_scope: dict,
) -> tuple[bool, str]:
    from bounded_acceptance import remeasure_observed_proofs_for_task
    from workflow_engine import Engine

    db_path = _workflow_db_path(conn)
    task_id = workflow_scope.get('task_id')
    scope = record.get('scope') or {}
    job_id = scope.get('job_id')
    if not db_path or not task_id or not job_id:
        return False, 'workflow_live_remeasure_scope_incomplete'
    if task_id != scope.get('task_id'):
        return False, 'verification_record_task_id_mismatch'
    engine = Engine(db_path)
    try:
        task = engine.tasks(job_id).get(task_id)
    finally:
        engine.close()
    if not task:
        return False, 'task_missing_at_consumption'
    return remeasure_observed_proofs_for_task(record, task)
