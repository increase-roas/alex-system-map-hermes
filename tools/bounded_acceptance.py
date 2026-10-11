"""Typed bounded acceptance: in-project artifacts + predeclared outcome contracts.

Supported criteria: proof-bound, gate-bound proof.

declared_outcome_v1 (stored on task before produce, via add_task.declared_outcomes):
  - criterion: must match an entry in task.acceptance
  - revision: integer >= 1; must increase when contract_sha256 changes after production
  - expected_utf8: exact bytes required in the artifact file (UTF-8)
  - expected_result: optional JSON object; compared with type-preserving JSON equality
    (boolean true/false are not equal to numeric 1/0)
  - contract_sha256: hash of canonical body fields (excluding contract_sha256)

bounded_artifact_v1 outputs must resolve strictly inside work/task-artifacts/ (no traversal/symlink escape).

Production identity (server-sealed on workflow update, not client-editable):
  production_id, production_operation_id, production_job_revision, production_job_id, production_task_id,
  declared_contract_revision, declared_contract_sha256 — stored in task.production_history and on descriptors.
  Relabeling contract fields without a matching production_history row is rejected.

Controlled producer receipts (SQLite controlled_producer_receipts, issued only by controlled_materialize_bounded_artifact):
  Output attachment for proof-bound tasks requires an unconsumed receipt matching job/task, committed declaration
  revision+hash, and artifact path+SHA from an actual materialization after that declaration. Stripped old descriptors
  cannot receive fresh seals without a new controlled materialize. Identical bytes after revision require a new receipt.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from verification_evidence import sha256_bytes, sha256_file

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'bounded_artifact_v1'
DECLARED_SCHEMA = 'declared_outcome_v1'
PRODUCER_RECEIPT_SCHEMA = 'controlled_producer_receipt_v1'
ARTIFACT_ROOT = ROOT / 'work' / 'task-artifacts'
ARTIFACT_ALLOWLIST_PREFIX = 'work/task-artifacts/'
ARTIFACT_ROOT_RESOLVED = ARTIFACT_ROOT.resolve()
MAX_ARTIFACT_BYTES = 4 * 1024 * 1024

SUPPORTED_CRITERIA = frozenset({'proof-bound', 'gate-bound proof'})
SAFE_IDENTIFIER = re.compile(r'^[A-Za-z0-9._-]+$')
SAFE_SUFFIX = re.compile(r'^[A-Za-z0-9._-]{1,16}$')

CLIENT_FORBIDDEN_DESCRIPTOR_KEYS = frozenset(
    {
        'production_id',
        'production_operation_id',
        'production_job_revision',
        'production_job_id',
        'production_task_id',
        'declared_contract_revision',
        'declared_contract_sha256',
        'producer_receipt_id',
        'controlled_producer_receipt_id',
    }
)

PRODUCTION_IDENTITY_KEYS = frozenset(
    {
        'production_id',
        'production_operation_id',
        'production_job_revision',
        'production_job_id',
        'production_task_id',
    }
)


class BoundedAcceptanceError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _normalize_relative(relative_path: str) -> str:
    return relative_path.replace('\\', '/').lstrip('/')


def _is_under_artifact_root(resolved: Path) -> bool:
    try:
        return resolved.is_relative_to(ARTIFACT_ROOT_RESOLVED)
    except AttributeError:
        return str(resolved).startswith(str(ARTIFACT_ROOT_RESOLVED))


def resolve_bounded_artifact_path(
    relative_path: str,
    *,
    must_exist: bool = True,
) -> tuple[bool, str, Path | None]:
    rel = _normalize_relative(relative_path)
    if '..' in Path(rel).parts:
        return False, 'artifact_path_traversal', None
    if not rel.startswith(ARTIFACT_ALLOWLIST_PREFIX):
        return False, 'artifact_not_allowlisted', None
    candidate = (ROOT / rel).resolve()
    if not _is_under_artifact_root(candidate):
        return False, 'artifact_outside_artifact_root', None
    if not must_exist:
        return True, 'ok', candidate
    if candidate.is_symlink():
        return False, 'artifact_symlink_not_allowed', None
    if not candidate.exists():
        return False, 'artifact_missing', None
    real = candidate.resolve()
    if not _is_under_artifact_root(real):
        return False, 'artifact_symlink_escape', None
    if not real.is_file():
        return False, 'artifact_not_regular_file', None
    size = real.stat().st_size
    if size > MAX_ARTIFACT_BYTES:
        return False, 'artifact_too_large', None
    return True, 'ok', real


def json_values_equal(expected: object, actual: object) -> bool:
    """Type-preserving JSON equality (bool is not int)."""
    if type(expected) is not type(actual):
        return False
    if isinstance(expected, dict):
        if set(expected.keys()) != set(actual.keys()):
            return False
        return all(json_values_equal(expected[k], actual[k]) for k in expected)
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return False
        return all(json_values_equal(a, b) for a, b in zip(expected, actual))
    return expected == actual


def _contract_body_for_hash(obj: dict) -> dict:
    return {
        'schema': DECLARED_SCHEMA,
        'criterion': obj['criterion'],
        'revision': obj['revision'],
        'expected_utf8': obj.get('expected_utf8'),
        'expected_result': obj.get('expected_result'),
    }


def contract_sha256(obj: dict) -> str:
    canonical = json.dumps(_contract_body_for_hash(obj), sort_keys=True, separators=(',', ':'))
    return sha256_bytes(canonical.encode())


def parse_declared_outcome(raw: object) -> dict | None:
    if isinstance(raw, dict):
        obj = raw
    elif isinstance(raw, str):
        raw = raw.strip()
        if not raw.startswith('{'):
            return None
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            return None
    else:
        return None
    if obj.get('schema') != DECLARED_SCHEMA:
        return None
    criterion = obj.get('criterion')
    revision = obj.get('revision')
    if criterion not in SUPPORTED_CRITERIA:
        return None
    if not isinstance(revision, int) or revision < 1:
        return None
    has_utf8 = isinstance(obj.get('expected_utf8'), str)
    has_result = isinstance(obj.get('expected_result'), dict)
    if not has_utf8 and not has_result:
        return None
    stored = obj.get('contract_sha256')
    if not isinstance(stored, str) or len(stored) != 64:
        return None
    if contract_sha256(obj) != stored:
        return None
    return obj


def build_declared_outcome(
    criterion: str,
    revision: int,
    *,
    expected_utf8: str | None = None,
    expected_result: dict | None = None,
) -> str:
    body = {
        'schema': DECLARED_SCHEMA,
        'criterion': criterion.strip(),
        'revision': revision,
    }
    if expected_utf8 is not None:
        body['expected_utf8'] = expected_utf8
    if expected_result is not None:
        body['expected_result'] = expected_result
    body['contract_sha256'] = contract_sha256(body)
    return json.dumps(body, sort_keys=True, separators=(',', ':'))


def declared_outcomes_index(task: dict) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for raw in task.get('declared_outcomes') or []:
        parsed = parse_declared_outcome(raw)
        if parsed:
            index[parsed['criterion']] = parsed
    return index


def validate_task_declared_outcomes(acceptance: list[str], declared_raw: list | None) -> tuple[bool, str]:
    declared_list = declared_raw or []
    index: dict[str, dict] = {}
    for raw in declared_list:
        parsed = parse_declared_outcome(raw)
        if not parsed:
            return False, 'declared_outcomes_invalid'
        if parsed['criterion'] in index:
            return False, 'declared_outcomes_duplicate_criterion'
        index[parsed['criterion']] = parsed
    for criterion in acceptance:
        name = criterion.strip()
        if name not in SUPPORTED_CRITERIA:
            continue
        if name not in index:
            return False, 'declared_outcome_required_before_production'
    return True, 'ok'


def contract_change_allowed(
    old_index: dict[str, dict],
    new_index: dict[str, dict],
    *,
    had_outputs: bool,
) -> tuple[bool, str]:
    for criterion, new_c in new_index.items():
        old_c = old_index.get(criterion)
        if not old_c:
            continue
        if new_c['contract_sha256'] == old_c['contract_sha256']:
            continue
        if new_c['revision'] <= old_c['revision']:
            return False, 'declared_outcome_revision_unchanged'
    return True, 'ok'


def archive_superseded_declarations(
    old_index: dict[str, dict],
    new_index: dict[str, dict],
    *,
    superseded_at_job_revision: int,
) -> list[dict]:
    history: list[dict] = []
    for criterion, old_c in old_index.items():
        new_c = new_index.get(criterion)
        if new_c and new_c['contract_sha256'] != old_c['contract_sha256']:
            history.append(
                {
                    'criterion': criterion,
                    'revision': old_c['revision'],
                    'contract_sha256': old_c['contract_sha256'],
                    'superseded_at_job_revision': superseded_at_job_revision,
                    'snapshot': _contract_body_for_hash(old_c),
                }
            )
    return history


def attach_contract_binding(descriptor: dict, contract: dict) -> dict:
    """Legacy helper for tests simulating relabel attacks; not valid for workflow submission."""
    bound = dict(descriptor)
    bound['declared_contract_revision'] = contract['revision']
    bound['declared_contract_sha256'] = contract['contract_sha256']
    return bound


def validate_safe_identifier(value: str, field: str) -> None:
    if not isinstance(value, str) or not SAFE_IDENTIFIER.match(value):
        raise BoundedAcceptanceError(f'{field}_unsafe')
    if value in ('.', '..') or '/' in value or '\\' in value:
        raise BoundedAcceptanceError(f'{field}_unsafe')


def validate_materialization_target(
    job_id: str,
    task_id: str,
    content: bytes,
    *,
    suffix: str = 'txt',
) -> tuple[Path, str]:
    validate_safe_identifier(job_id, 'job_id')
    validate_safe_identifier(task_id, 'task_id')
    if not SAFE_SUFFIX.match(suffix):
        raise BoundedAcceptanceError('artifact_suffix_unsafe')
    rel = Path('work/task-artifacts') / job_id / f'{task_id}-{sha256_bytes(content)[:12]}.{suffix}'
    rel_str = _normalize_relative(str(rel))
    ok, reason, planned = resolve_bounded_artifact_path(rel_str, must_exist=False)
    if not ok or planned is None:
        raise BoundedAcceptanceError(reason)
    parent = planned.parent
    parent.mkdir(parents=True, exist_ok=True)
    if parent.is_symlink():
        raise BoundedAcceptanceError('artifact_parent_symlink_escape')
    parent_resolved = parent.resolve()
    if not _is_under_artifact_root(parent_resolved):
        raise BoundedAcceptanceError('artifact_outside_artifact_root')
    return planned, rel_str


def client_descriptor_has_forbidden_metadata(descriptor: dict) -> bool:
    return any(key in descriptor for key in CLIENT_FORBIDDEN_DESCRIPTOR_KEYS)


def ensure_controlled_producer_receipts_table(db: sqlite3.Connection) -> None:
    db.execute(
        '''
        CREATE TABLE IF NOT EXISTS controlled_producer_receipts(
            receipt_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            producer_operation_id TEXT NOT NULL,
            job_revision_at_production INTEGER NOT NULL,
            declared_contract_revision INTEGER NOT NULL,
            declared_contract_sha256 TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            artifact_sha256 TEXT NOT NULL,
            byte_length INTEGER NOT NULL,
            production_kind TEXT NOT NULL,
            consumed_by_operation_id TEXT,
            created_at TEXT NOT NULL
        )
        '''
    )


def producer_receipt_body(record: dict) -> dict:
    return {
        'schema': PRODUCER_RECEIPT_SCHEMA,
        'job_id': record['job_id'],
        'task_id': record['task_id'],
        'producer_operation_id': record['producer_operation_id'],
        'job_revision_at_production': record['job_revision_at_production'],
        'declared_contract_revision': record['declared_contract_revision'],
        'declared_contract_sha256': record['declared_contract_sha256'],
        'relative_path': record['relative_path'],
        'artifact_sha256': record['artifact_sha256'],
        'byte_length': record['byte_length'],
        'production_kind': record['production_kind'],
    }


def compute_producer_receipt_id(record: dict) -> str:
    return sha256_bytes(
        json.dumps(producer_receipt_body(record), sort_keys=True, separators=(',', ':')).encode()
    )


def _task_contract_for_binding(task: dict) -> dict | None:
    contracts = declared_outcomes_index(task)
    if not contracts:
        return None
    for criterion in task.get('acceptance') or []:
        name = criterion.strip()
        if name in contracts:
            return contracts[name]
    return None


def controlled_materialize_bounded_artifact(
    db: sqlite3.Connection,
    job_id: str,
    task_id: str,
    producer_operation_id: str,
    content: bytes,
    *,
    suffix: str = 'txt',
) -> dict:
    """Controlled materialization: write artifact and register server producer receipt (not client-submittable)."""
    ensure_controlled_producer_receipts_table(db)
    row = db.execute('SELECT payload FROM tasks WHERE id=? AND job_id=?', (task_id, job_id)).fetchone()
    if not row:
        raise BoundedAcceptanceError('unknown_task')
    task = json.loads(row[0])
    if not task_requires_declaration_binding(task):
        return materialize_bounded_artifact(job_id, task_id, content, suffix=suffix)
    contract = _task_contract_for_binding(task)
    if contract is None:
        raise BoundedAcceptanceError('declared_outcome_missing')
    job_row = db.execute('SELECT revision FROM jobs WHERE id=?', (job_id,)).fetchone()
    job_revision = int(job_row[0]) if job_row else 0
    descriptor = materialize_bounded_artifact(job_id, task_id, content, suffix=suffix)
    rel = _normalize_relative(descriptor['relative_path'])
    receipt_row = {
        'job_id': job_id,
        'task_id': task_id,
        'producer_operation_id': producer_operation_id,
        'job_revision_at_production': job_revision,
        'declared_contract_revision': contract['revision'],
        'declared_contract_sha256': contract['contract_sha256'],
        'relative_path': rel,
        'artifact_sha256': descriptor['sha256'],
        'byte_length': descriptor['byte_length'],
        'production_kind': 'materialized',
    }
    receipt_id = compute_producer_receipt_id(receipt_row)
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    try:
        db.execute(
            '''
            INSERT INTO controlled_producer_receipts(
                receipt_id, job_id, task_id, producer_operation_id, job_revision_at_production,
                declared_contract_revision, declared_contract_sha256, relative_path,
                artifact_sha256, byte_length, production_kind, consumed_by_operation_id, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''',
            (
                receipt_id,
                job_id,
                task_id,
                producer_operation_id,
                job_revision,
                contract['revision'],
                contract['contract_sha256'],
                rel,
                descriptor['sha256'],
                descriptor['byte_length'],
                'materialized',
                None,
                created_at,
            ),
        )
        db.commit()
    except sqlite3.IntegrityError as exc:
        raise BoundedAcceptanceError('controlled_producer_receipt_duplicate') from exc
    return descriptor


def consume_controlled_producer_receipt(
    db: sqlite3.Connection,
    job_id: str,
    task_id: str,
    attach_operation_id: str,
    contract: dict,
    descriptor: dict,
) -> tuple[sqlite3.Row | None, str | None]:
    ensure_controlled_producer_receipts_table(db)
    rel = _normalize_relative(descriptor['relative_path'])
    row = db.execute(
        '''
        SELECT * FROM controlled_producer_receipts
        WHERE job_id=? AND task_id=? AND consumed_by_operation_id IS NULL
          AND declared_contract_revision=? AND declared_contract_sha256=?
          AND relative_path=? AND artifact_sha256=?
        ORDER BY created_at DESC LIMIT 1
        ''',
        (
            job_id,
            task_id,
            contract['revision'],
            contract['contract_sha256'],
            rel,
            descriptor['sha256'],
        ),
    ).fetchone()
    if not row:
        return None, 'controlled_producer_evidence_missing'
    db.execute(
        'UPDATE controlled_producer_receipts SET consumed_by_operation_id=? WHERE receipt_id=?',
        (attach_operation_id, row['receipt_id']),
    )
    return row, None


def strip_to_client_draft_descriptor(descriptor: dict) -> dict:
    """Test helper: draft fields only (simulates stripping server seal metadata)."""
    allowed = {'schema', 'relative_path', 'sha256', 'byte_length'}
    return {k: descriptor[k] for k in allowed if k in descriptor}


def production_record_body(record: dict) -> dict:
    body = {
        'production_job_id': record['production_job_id'],
        'production_task_id': record['production_task_id'],
        'production_operation_id': record['production_operation_id'],
        'production_job_revision': record['production_job_revision'],
        'declared_contract_revision': record['declared_contract_revision'],
        'declared_contract_sha256': record['declared_contract_sha256'],
        'relative_path': record['relative_path'],
        'artifact_sha256': record['artifact_sha256'],
    }
    if record.get('producer_receipt_id'):
        body['producer_receipt_id'] = record['producer_receipt_id']
    return body


def compute_production_id(record: dict) -> str:
    return sha256_bytes(
        json.dumps(production_record_body(record), sort_keys=True, separators=(',', ':')).encode()
    )


def verify_descriptor_production_identity(
    descriptor: dict,
    task: dict,
) -> tuple[bool, str]:
    if task_requires_declaration_binding(task):
        pid = descriptor.get('production_id')
        if not isinstance(pid, str) or len(pid) != 64:
            return False, 'output_missing_production_identity'
        record = None
        for row in task.get('production_history') or []:
            if row.get('production_id') == pid:
                record = row
                break
        if not record:
            return False, 'production_identity_unknown'
        task_id = task.get('id')
        if task_id and record.get('production_task_id') != task_id:
            return False, 'production_task_identity_mismatch'
        pairs = (
            ('production_job_id', 'production_job_id'),
            ('production_task_id', 'production_task_id'),
            ('production_operation_id', 'production_operation_id'),
            ('production_job_revision', 'production_job_revision'),
            ('declared_contract_revision', 'declared_contract_revision'),
            ('declared_contract_sha256', 'declared_contract_sha256'),
            ('relative_path', 'relative_path'),
            ('sha256', 'artifact_sha256'),
        )
        for desc_key, rec_key in pairs:
            if descriptor.get(desc_key) != record.get(rec_key):
                return False, 'production_declaration_relabel_forbidden'
    return True, 'ok'


def seal_production_outputs(
    job_id: str,
    task_id: str,
    job_revision: int,
    operation_id: str,
    task: dict,
    outputs_raw: list,
    db: sqlite3.Connection,
) -> tuple[list[str], list[dict], str | None]:
    contracts = declared_outcomes_index(task)
    if not contracts:
        return [], [], 'declared_outcome_missing'
    sealed: list[str] = []
    records: list[dict] = []
    for raw in outputs_raw:
        descriptor = parse_output_descriptor(raw)
        if descriptor is None:
            return [], [], 'artifact_descriptor_invalid'
        if client_descriptor_has_forbidden_metadata(descriptor):
            return [], [], 'client_production_metadata_forbidden'
        ok, reason, _ = resolve_bounded_artifact_path(descriptor['relative_path'], must_exist=True)
        if not ok:
            return [], [], reason
        measured = sha256_file(ROOT / _normalize_relative(descriptor['relative_path']))
        if measured != descriptor['sha256']:
            return [], [], 'artifact_sha256_mismatch'
        contract = None
        for criterion in task.get('acceptance') or []:
            name = criterion.strip()
            if name in contracts:
                contract = contracts[name]
                break
        if contract is None:
            return [], [], 'declared_outcome_missing'
        receipt_row, receipt_reason = consume_controlled_producer_receipt(
            db, job_id, task_id, operation_id, contract, descriptor
        )
        if receipt_reason:
            return [], [], receipt_reason
        producer_op = receipt_row['producer_operation_id']
        body = {
            'production_job_id': job_id,
            'production_task_id': task_id,
            'production_operation_id': producer_op,
            'production_job_revision': job_revision,
            'declared_contract_revision': contract['revision'],
            'declared_contract_sha256': contract['contract_sha256'],
            'relative_path': _normalize_relative(descriptor['relative_path']),
            'artifact_sha256': descriptor['sha256'],
            'producer_receipt_id': receipt_row['receipt_id'],
            'production_kind': receipt_row['production_kind'],
        }
        pid = compute_production_id(body)
        body['production_id'] = pid
        sealed_desc = {
            **descriptor,
            'declared_contract_revision': contract['revision'],
            'declared_contract_sha256': contract['contract_sha256'],
            'production_id': pid,
            'production_operation_id': producer_op,
            'production_job_revision': job_revision,
            'production_job_id': job_id,
            'production_task_id': task_id,
        }
        sealed.append(bounded_output_descriptor(sealed_desc))
        records.append(body)
    return sealed, records, None


def task_requires_declaration_binding(task: dict) -> bool:
    for criterion in task.get('acceptance') or []:
        if criterion.strip() in SUPPORTED_CRITERIA:
            return True
    return False


def validate_output_descriptors_for_task(task: dict, outputs_raw: list) -> tuple[bool, str]:
    if not task_requires_declaration_binding(task):
        return True, 'ok'
    if not declared_outcomes_index(task):
        return False, 'declared_outcome_missing'
    for raw in outputs_raw:
        descriptor = parse_output_descriptor(raw)
        if descriptor is None:
            return False, 'artifact_descriptor_invalid'
        if client_descriptor_has_forbidden_metadata(descriptor):
            return False, 'client_production_metadata_forbidden'
        ok, reason, _ = resolve_bounded_artifact_path(descriptor['relative_path'], must_exist=False)
        if not ok:
            return False, reason
    return True, 'ok'


def materialize_bounded_artifact(
    job_id: str,
    task_id: str,
    content: bytes,
    *,
    suffix: str = 'txt',
    contract: dict | None = None,
) -> dict:
    """Write artifact bytes after prewrite containment checks. Returns draft descriptor (no production identity)."""
    if contract is not None:
        raise BoundedAcceptanceError('contract_not_allowed_on_materialize')
    path, rel_str = validate_materialization_target(job_id, task_id, content, suffix=suffix)
    path.write_bytes(content)
    file_sha = sha256_file(path)
    return {
        'schema': SCHEMA,
        'relative_path': rel_str,
        'sha256': file_sha,
        'byte_length': len(content),
    }


def bounded_output_descriptor(descriptor: dict) -> str:
    return json.dumps(descriptor, sort_keys=True, separators=(',', ':'))


def parse_output_descriptor(raw: object) -> dict | None:
    if isinstance(raw, dict):
        obj = raw
    elif isinstance(raw, str):
        raw = raw.strip()
        if not raw.startswith('{'):
            return None
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            return None
    else:
        return None
    if obj.get('schema') != SCHEMA:
        return None
    rel = obj.get('relative_path')
    expected_sha = obj.get('sha256')
    if not isinstance(rel, str) or not isinstance(expected_sha, str) or len(expected_sha) != 64:
        return None
    return obj


def measure_declared_content(
    content: bytes,
    contract: dict,
) -> tuple[bool, str, dict]:
    checks: dict = {
        'contract_revision': contract['revision'],
        'contract_sha256': contract['contract_sha256'],
    }
    if 'expected_utf8' in contract:
        expected = contract['expected_utf8'].encode('utf-8')
        if content != expected:
            return False, 'declared_content_mismatch', {**checks, 'content_matches_declaration': False}
        checks['content_matches_declaration'] = True
    if 'expected_result' in contract:
        try:
            parsed = json.loads(content.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False, 'declared_result_not_valid_json', {**checks, 'result_matches_declaration': False}
        if not json_values_equal(contract['expected_result'], parsed):
            return False, 'declared_result_mismatch', {**checks, 'result_matches_declaration': False}
        checks['result_matches_declaration'] = True
    return True, 'ok', checks


def measure_bounded_artifact(descriptor: dict) -> tuple[bool, str, dict | None]:
    ok, reason, path = resolve_bounded_artifact_path(descriptor['relative_path'], must_exist=True)
    if not ok or path is None:
        return False, reason, None
    measured_sha = sha256_file(path)
    if measured_sha != descriptor['sha256']:
        return False, 'artifact_sha256_mismatch', {
            'relative_path': _normalize_relative(descriptor['relative_path']),
            'expected_sha256': descriptor['sha256'],
            'measured_sha256': measured_sha,
        }
    content = path.read_bytes()
    return True, 'ok', {
        'relative_path': _normalize_relative(descriptor['relative_path']),
        'sha256': measured_sha,
        'byte_length': len(content),
        'content': content,
    }


def measure_criterion_outcome(criterion: str, task: dict) -> tuple[dict[str, bool], list[dict], str | None]:
    name = criterion.strip()
    if name not in SUPPORTED_CRITERIA:
        return {f'criterion_{name.replace(" ", "_")}_unsupported': False}, [], 'acceptance_criterion_unsupported'
    contracts = declared_outcomes_index(task)
    contract = contracts.get(name)
    if contract is None:
        return {'declared_outcome_present': False}, [], 'declared_outcome_missing'
    outputs = task.get('outputs') or []
    if not outputs:
        return {'artifact_present': False}, [], 'artifact_missing'
    proofs: list[dict] = []
    for raw in outputs:
        descriptor = parse_output_descriptor(raw)
        if descriptor is None:
            return {'artifact_descriptor_valid': False}, proofs, 'artifact_descriptor_invalid'
        rev = descriptor.get('declared_contract_revision')
        sha = descriptor.get('declared_contract_sha256')
        if rev != contract['revision'] or sha != contract['contract_sha256']:
            return {'output_declaration_binding_stale': False}, proofs, 'output_declaration_binding_stale'
        ok_prod, prod_reason = verify_descriptor_production_identity(descriptor, task)
        if not ok_prod:
            return {prod_reason: False}, proofs, prod_reason
        ok, reason, observed = measure_bounded_artifact(descriptor)
        if not ok:
            key = {
                'artifact_missing': 'artifact_present',
                'artifact_sha256_mismatch': 'artifact_hash_matches',
                'artifact_outside_artifact_root': 'artifact_within_allowlist',
                'artifact_not_allowlisted': 'artifact_within_allowlist',
                'artifact_path_traversal': 'artifact_within_allowlist',
                'artifact_symlink_escape': 'artifact_within_allowlist',
                'artifact_symlink_not_allowed': 'artifact_within_allowlist',
            }.get(reason, 'artifact_valid')
            return {key: False}, proofs, reason
        content = observed.pop('content')
        ok_decl, decl_reason, decl_checks = measure_declared_content(content, contract)
        if not ok_decl:
            return {decl_reason: False}, proofs, decl_reason
        proofs.append(
            {
                'criterion': name,
                'relative_path': observed['relative_path'],
                'sha256': observed['sha256'],
                'byte_length': observed['byte_length'],
                'production_id': descriptor.get('production_id'),
                **decl_checks,
            }
        )
    key = 'outcome_' + name.replace('-', '_').replace(' ', '_')
    return {key: True, 'artifact_hash_matches': True, 'declared_outcome_verified': True}, proofs, None


def remeasure_observed_proofs_for_task(record: dict, task: dict) -> tuple[bool, str]:
    stored = record.get('observed_proofs') or []
    if not stored:
        return False, 'verification_record_observed_proofs_missing'
    scope = record.get('scope') or {}
    task_id = scope.get('task_id')
    if task_id and task.get('id') != task_id:
        return False, 'verification_record_task_binding_mismatch'
    contracts = declared_outcomes_index(task)
    for entry in stored:
        criterion = entry.get('criterion')
        if not criterion:
            return False, 'verification_record_observed_proof_incomplete'
        contract = contracts.get(criterion)
        if not contract:
            return False, 'declared_outcome_missing'
        if entry.get('contract_sha256') != contract['contract_sha256']:
            return False, 'declared_outcome_contract_changed'
        if entry.get('contract_revision') != contract['revision']:
            return False, 'declared_outcome_contract_changed'
        stored_pid = entry.get('production_id')
        if stored_pid:
            known = any(r.get('production_id') == stored_pid for r in task.get('production_history') or [])
            if not known:
                return False, 'production_identity_unknown'
        rel = entry.get('relative_path')
        if not rel:
            return False, 'observed_artifact_not_allowlisted'
        ok, reason, path = resolve_bounded_artifact_path(rel, must_exist=True)
        if not ok or path is None:
            return False, reason
        live_sha = sha256_file(path)
        if live_sha != entry.get('sha256'):
            return False, 'observed_artifact_changed_at_consumption'
        ok_decl, decl_reason, _ = measure_declared_content(path.read_bytes(), contract)
        if not ok_decl:
            return False, decl_reason
    return True, 'ok'
