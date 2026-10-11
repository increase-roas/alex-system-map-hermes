"""Canonical catalog record and maintained document editing with journal + derived render."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager
from typing import Any, Iterator

from catalog_io import catalog_root
from output_screening import export_json_safe, screen_text

ROOT = Path(__file__).resolve().parents[1]
BACKUP_DIR = ROOT / 'app' / '.data' / 'catalog-backups'
LOCK_DIR = ROOT / 'app' / '.data' / 'catalog-edit-locks'
GLOBAL_OPS_LOG = ROOT / 'app' / '.data' / 'catalog-edit-operations.jsonl'
JOURNAL_DIR = ROOT / 'app' / '.data' / 'catalog-edit-journal'
REVISIONS_NAME = '.maintained-revisions.json'
PROBE_CANARY = 'FAKE-canary-token-res0722-emitted'
BENIGN = 'LOCAL-SCREENING-OK'

EDITABLE_TABLES = {
    'data/components.json',
    'data/catalog-metadata.json',
}
EDITABLE_LOCAL_DOCS = {
    'work/reliability/editable-fixture.json',
    'work/reliability/synthetic-sync-marker.json',
}
IMMUTABLE_RECORD_FIELDS = frozenset({'id'})
IMMUTABLE_METADATA_FIELDS = frozenset(
    {
        'schema_version',
        'snapshot_date',
        'source_workbook_sha256',
        'source_zip_sha256',
        'identity_policy',
        'category_policy',
        'default_observed_condition',
    }
)
FILE_SCOPED_TABLES = frozenset({'data/components.json'})
CATALOG_TRANSACTION_LOCK = 'catalog-root-transaction-v1'


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _root() -> Path:
    return catalog_root()


def revisions_path() -> Path:
    return _root() / 'data' / REVISIONS_NAME


def _load_revisions() -> dict[str, dict]:
    path = revisions_path()
    if not path.is_file():
        return {}
    return json.loads(path.read_text())


def _save_revisions(data: dict[str, dict]) -> None:
    path = revisions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
    tmp.replace(path)


def target_key(table: str, record_id: str | None) -> str:
    return f'{table}#{record_id or "__file__"}'


def transaction_lock_key(table: str, record_id: str | None = None) -> str:
    if table.startswith('data/') or table in EDITABLE_TABLES:
        return CATALOG_TRANSACTION_LOCK
    return target_key(table, record_id)


def ops_log_path() -> Path:
    per_root = _root() / 'data' / '.catalog-edit-operations.jsonl'
    return per_root


def _process_start_barrier() -> None:
    group = os.environ.get('CATALOG_EDIT_BARRIER_GROUP')
    if not group:
        return
    slot = os.environ.get('CATALOG_EDIT_BARRIER_SLOT', '0')
    count = int(os.environ.get('CATALOG_EDIT_BARRIER_COUNT', '2'))
    root = LOCK_DIR / 'barriers' / group
    root.mkdir(parents=True, exist_ok=True)
    (root / f'ready-{slot}').write_text(str(os.getpid()), encoding='utf-8')
    deadline = time.time() + 120.0
    while time.time() < deadline:
        if len(list(root.glob('ready-*'))) >= count:
            return
        time.sleep(0.02)
    raise TimeoutError(f'catalog edit barrier timeout group={group}')


@contextmanager
def _acquire_transaction_lock(table: str, record_id: str | None = None) -> Iterator[None]:
    lock_path = LOCK_DIR / f"{sha256_bytes(transaction_lock_key(table, record_id).encode())[:16]}.lock"
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, 'w', encoding='utf-8')
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    try:
        yield
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def resolve_table_path(relative: str) -> Path:
    rel = relative.replace('\\', '/').lstrip('/')
    allowed = EDITABLE_TABLES | EDITABLE_LOCAL_DOCS
    if rel not in allowed:
        raise ValueError('path not in canonical editable allowlist')
    raw = (_root() if rel.startswith('data/') else ROOT) / rel
    if raw.is_symlink():
        raise ValueError('symlink not allowed for editable path')
    candidate = raw.resolve()
    bound_root = (_root() if rel.startswith('data/') else ROOT).resolve()
    if os.path.commonpath([str(candidate), str(bound_root)]) != str(bound_root):
        raise ValueError('path escapes bound catalog root after resolution')
    if not candidate.is_file():
        raise ValueError('editable file missing')
    return candidate


def _read_wrapper(path: Path) -> dict:
    doc = json.loads(path.read_text())
    if not isinstance(doc, dict):
        raise ValueError('catalog file must be object wrapper')
    if doc.get('schema_version') != '1.0.0':
        raise ValueError('schema_version must be exactly 1.0.0')
    return doc


def _validate_component_record(before: dict, after: dict) -> None:
    from catalog_reference_validation import validate_component_record_contract

    for field in IMMUTABLE_RECORD_FIELDS:
        if after.get(field) != before.get(field):
            raise ValueError(f'field {field} is immutable')
    validate_component_record_contract(before, after)
    for text_key in ('purpose', 'boundary', 'fit'):
        val = after.get(text_key)
        if isinstance(val, str) and PROBE_CANARY in val:
            screened, _ = screen_text(val)
            raise ValueError(f'controlled edit rejected: {screened}')


def _validate_metadata_document(before: dict, after: dict) -> None:
    if after.get('schema_version') != '1.0.0':
        raise ValueError('schema_version must be exactly 1.0.0')
    for key in IMMUTABLE_METADATA_FIELDS:
        if after.get(key) != before.get(key):
            raise ValueError(f'metadata field {key} is immutable')
    for key in before:
        if key not in after and key != 'update_policy':
            raise ValueError(f'missing required metadata field {key}')
    policy = after.get('update_policy')
    if not isinstance(policy, str):
        raise ValueError('update_policy must be string')
    if PROBE_CANARY in policy:
        screened, _ = screen_text(policy)
        raise ValueError(f'controlled edit rejected: {screened}')


def read_state(table: str, record_id: str | None = None) -> dict:
    path = resolve_table_path(table)
    data = path.read_bytes()
    wrapper = _read_wrapper(path)
    revs = _load_revisions()
    key = target_key(table, record_id)
    revision = int(revs.get(key, {}).get('revision', 0))
    if record_id:
        records = wrapper.get('records')
        if not isinstance(records, list):
            raise ValueError('records must be array')
        match = next((r for r in records if isinstance(r, dict) and r.get('id') == record_id), None)
        if not match:
            raise ValueError('record_id not found in catalog table')
        document = match
    else:
        document = wrapper
    return {
        'path': table,
        'record_id': record_id,
        'sha256': sha256_bytes(data),
        'bytes': len(data),
        'document': document,
        'revision': revision,
        'target_key': key,
    }


def document_diff(before: dict, after: dict) -> list[dict[str, Any]]:
    keys = sorted(set(before) | set(after))
    return [
        {'field': key, 'before': before.get(key), 'after': after.get(key)}
        for key in keys
        if before.get(key) != after.get(key)
    ]


def normalized_mutation_digest(
    table: str,
    record_id: str | None,
    expected_revision: int,
    document: dict,
    expected_sha256: str,
) -> str:
    payload = {
        'catalog_root': str(_root().resolve()),
        'table': table,
        'record_id': record_id,
        'expected_revision': expected_revision,
        'expected_sha256': expected_sha256,
        'document': document,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return sha256_bytes(raw.encode())


def _latest_operation_row(operation_id: str) -> dict | None:
    ops = ops_log_path()
    if not operation_id or not ops.is_file():
        return None
    latest: dict | None = None
    for line in ops.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get('operation_id') == operation_id:
            latest = row
    return latest


def _load_operation(operation_id: str) -> dict | None:
    row = _latest_operation_row(operation_id)
    if not row or row.get('status') != 'committed':
        return None
    return row


def _invalidate_operation(operation_id: str, *, reason: str) -> None:
    if not operation_id:
        return
    _append_operation(
        {
            'operation_id': operation_id,
            'status': 'invalidated',
            'reason': reason,
            'at': utc_now(),
        }
    )


def _append_operation(row: dict) -> None:
    ops = ops_log_path()
    ops.parent.mkdir(parents=True, exist_ok=True)
    with ops.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps({**row, 'catalog_root': str(_root().resolve())}, sort_keys=True) + '\n')


def _write_journal(entry: dict) -> Path:
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    path = JOURNAL_DIR / f"{entry['journal_id']}.json"
    path.write_text(json.dumps(entry, indent=2, sort_keys=True) + '\n')
    return path


def _journal_terminal(entry: dict) -> bool:
    return entry.get('status') in {'committed', 'rolled_back', 'discarded'}


def _restore_revision_snapshot(entry: dict) -> None:
    snap = entry.get('before_revision')
    key = entry.get('target_key') or target_key(entry.get('table', ''), entry.get('record_id'))
    if not isinstance(snap, dict):
        return
    revs = _load_revisions()
    revs[key] = {
        'revision': int(snap.get('revision', 0)),
        'sha256': str(snap.get('sha256', entry.get('before_sha256', ''))),
        'at': utc_now(),
    }
    _save_revisions(revs)


def _reconcile_journals_body(*, table_filter: str | None = None) -> list[dict]:
    if not JOURNAL_DIR.is_dir():
        return []
    outcomes: list[dict] = []
    for journal in sorted(JOURNAL_DIR.glob('*.json')):
        entry = json.loads(journal.read_text())
        if entry.get('catalog_root') and entry.get('catalog_root') != str(_root()):
            continue
        if _journal_terminal(entry):
            continue
        table = entry.get('table')
        if not table or (table_filter and table != table_filter):
            continue
        entry = json.loads(journal.read_text())
        if _journal_terminal(entry):
            continue
        backup = ROOT / entry.get('backup', '')
        path = resolve_table_path(table)
        current_sha = sha256_bytes(path.read_bytes())
        if entry.get('after_sha256') and current_sha != entry.get('after_sha256'):
            if entry.get('before_sha256') and current_sha != entry.get('before_sha256'):
                entry['status'] = 'superseded'
                entry['reconciled_at'] = utc_now()
                journal.write_text(json.dumps(entry, indent=2) + '\n')
                outcomes.append({'journal_id': entry['journal_id'], 'action': 'superseded_later_commit'})
                continue
        stage = entry.get('stage')
        if stage in {
            'post_rename_pre_derived',
            'post_canonical_pre_derived',
            'post_derived_pre_revision',
            'post_revision_pre_oplog',
            'post_oplog_pre_journal_commit',
        }:
            if backup.is_file():
                tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
                shutil.copy2(backup, tmp)
                tmp.replace(path)
                _regenerate_derived(table, entry.get('record_id'))
            _restore_revision_snapshot(entry)
            if entry.get('operation_id'):
                _invalidate_operation(entry['operation_id'], reason='journal_rolled_back')
            entry['status'] = 'rolled_back'
            entry['reconciled_at'] = utc_now()
            journal.write_text(json.dumps(entry, indent=2) + '\n')
            outcomes.append({'journal_id': entry['journal_id'], 'action': 'rolled_back'})
        elif stage == 'restore_pending':
            restore_backup = ROOT / (entry.get('restore_backup') or entry.get('backup', ''))
            pre_restore_revision = int(entry.get('pre_restore_revision', 0))
            if restore_backup.is_file():
                tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
                shutil.copy2(restore_backup, tmp)
                tmp.replace(path)
                _regenerate_derived(table, entry.get('record_id'))
            after_sha = sha256_bytes(path.read_bytes())
            if os.environ.get('CATALOG_EDIT_INJECT_CRASH') == 'reconcile_mid_restore':
                entry['stage'] = 'restore_pending'
                entry['after_sha256'] = after_sha
                journal.write_text(json.dumps(entry, indent=2) + '\n')
                raise RuntimeError('injected crash reconcile_mid_restore')
            key = entry.get('target_key') or target_key(table, entry.get('record_id'))
            revs = _load_revisions()
            new_revision = pre_restore_revision + 1
            revs[key] = {'revision': new_revision, 'sha256': after_sha, 'at': utc_now()}
            _save_revisions(revs)
            entry['stage'] = 'committed'
            entry['status'] = 'committed'
            entry['after_sha256'] = after_sha
            entry['restored_revision'] = new_revision
            entry['reconciled_at'] = utc_now()
            entry['committed_at'] = entry.get('committed_at') or utc_now()
            journal.write_text(json.dumps(entry, indent=2) + '\n')
            outcomes.append({'journal_id': entry['journal_id'], 'action': 'restore_completed'})
        elif stage == 'pending':
            if backup.is_file() and current_sha != entry.get('before_sha256'):
                tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
                shutil.copy2(backup, tmp)
                tmp.replace(path)
            _restore_revision_snapshot(entry)
            if entry.get('operation_id'):
                _invalidate_operation(entry['operation_id'], reason='journal_discarded_pending')
            entry['status'] = 'discarded'
            entry['reconciled_at'] = utc_now()
            journal.write_text(json.dumps(entry, indent=2) + '\n')
            outcomes.append({'journal_id': entry.get('journal_id'), 'action': 'discarded_pending'})
    return outcomes


def reconcile_journals() -> list[dict]:
    with _acquire_transaction_lock('data/components.json'):
        return _reconcile_journals_body(table_filter=None)


def _apply_wrapper_mutation(path: Path, table: str, record_id: str | None, document: dict) -> bytes:
    wrapper = _read_wrapper(path)
    if record_id:
        records = wrapper['records']
        idx = next(i for i, r in enumerate(records) if r.get('id') == record_id)
        _validate_component_record(records[idx], document)
        records[idx] = document
    else:
        _validate_metadata_document(wrapper, document)
        wrapper = document
    out = (json.dumps(wrapper, indent=2, ensure_ascii=False) + '\n').encode()
    return out


def _regenerate_derived(table: str, record_id: str | None) -> dict:
    from canonical_derived_render import render_catalog_derived, snapshot_derived_hashes

    render_catalog_derived(record_id if table == 'data/components.json' else None)
    return snapshot_derived_hashes(table, record_id)


def preview_patch(
    table: str,
    expected_sha256: str,
    document: dict,
    *,
    record_id: str | None = None,
    next_revision: int | None = None,
) -> dict:
    if next_revision is None:
        raise ValueError('next_revision required')
    state = read_state(table, record_id)
    expected_next = state['revision'] + 1
    if next_revision != expected_next:
        raise ValueError(f'revision must be exactly {expected_next}')
    if state['sha256'] != expected_sha256:
        raise ValueError('revision conflict: file changed since expected_sha256')
    path = resolve_table_path(table)
    if record_id:
        before = state['document']
        _validate_component_record(before, document)
    else:
        _validate_metadata_document(state['document'], document)
    new_bytes = _apply_wrapper_mutation(path, table, record_id, document)
    raw = {
        'path': table,
        'record_id': record_id,
        'before_sha256': state['sha256'],
        'after_sha256': sha256_bytes(new_bytes),
        'diff': document_diff(state['document'], document),
        'valid': True,
        'expected_revision': state['revision'],
        'next_revision': state['revision'] + 1,
    }
    return export_json_safe(raw)['payload']


def _request_mutation_digest(
    table: str,
    record_id: str | None,
    document: dict,
    expected_sha256: str,
    next_revision: int | None,
    *,
    base_revision: int | None = None,
) -> str:
    rev = base_revision
    if rev is None:
        if next_revision is None:
            raise ValueError('next_revision required to bind mutation digest')
        rev = next_revision - 1
    return normalized_mutation_digest(table, record_id, rev, document, expected_sha256)


def apply_patch(
    table: str,
    expected_sha256: str,
    document: dict,
    *,
    record_id: str | None = None,
    operation_id: str | None = None,
    next_revision: int | None = None,
) -> dict:
    if next_revision is None:
        raise ValueError('next_revision required')
    _process_start_barrier()
    with _acquire_transaction_lock(table, record_id):
        _reconcile_journals_body(table_filter=None)
        if operation_id:
            prior = _load_operation(operation_id)
            if prior and prior.get('status') == 'committed':
                digest = _request_mutation_digest(
                    table,
                    record_id,
                    document,
                    expected_sha256,
                    next_revision,
                )
                if prior.get('mutation_digest') != digest:
                    raise ValueError('operation_id reused with different payload')
                return prior['result']
        state = read_state(table, record_id)
        digest = _request_mutation_digest(
            table,
            record_id,
            document,
            expected_sha256,
            next_revision,
            base_revision=state['revision'],
        )
        preview = preview_patch(
            table,
            expected_sha256,
            document,
            record_id=record_id,
            next_revision=next_revision,
        )
        path = resolve_table_path(table)
        backup_path = BACKUP_DIR / f"{path.name}.{preview['before_sha256'][:12]}.bak"
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup_path)
        key = target_key(table, record_id)
        revs = _load_revisions()
        before_revision = json.loads(
            json.dumps(revs.get(key, {'revision': state['revision'], 'sha256': preview['before_sha256']}))
        )
        sidecar = backup_path.with_suffix('.revision.json')
        sidecar.write_text(json.dumps({'target_key': key, 'before_revision': before_revision}, sort_keys=True) + '\n')
        journal_id = uuid.uuid4().hex
        journal = {
            'journal_id': journal_id,
            'catalog_root': str(_root()),
            'table': table,
            'record_id': record_id,
            'target_key': key,
            'stage': 'pending',
            'backup': str(backup_path.relative_to(ROOT)),
            'before_sha256': preview['before_sha256'],
            'before_revision': before_revision,
            'operation_id': operation_id,
            'mutation_digest': digest,
            'started_at': utc_now(),
        }
        _write_journal(journal)
        if os.environ.get('CATALOG_EDIT_INJECT_CRASH') == 'pending_before_rename':
            raise RuntimeError('injected crash pending_before_rename')
        new_bytes = _apply_wrapper_mutation(path, table, record_id, document)
        tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_bytes(new_bytes)
        readback = json.loads(tmp.read_text())
        if record_id:
            idx = next(i for i, r in enumerate(readback['records']) if r.get('id') == record_id)
            if readback['records'][idx] != document:
                tmp.unlink(missing_ok=True)
                raise ValueError('readback mismatch after write')
        elif readback != document:
            tmp.unlink(missing_ok=True)
            raise ValueError('readback mismatch after write')
        tmp.replace(path)
        after_sha = sha256_bytes(path.read_bytes())
        journal['stage'] = 'post_rename_pre_derived'
        journal['after_sha256'] = after_sha
        _write_journal(journal)
        inject = os.environ.get('CATALOG_EDIT_INJECT_CRASH')
        if inject in {'post_canonical_pre_derived', 'post_rename_pre_derived'}:
            raise RuntimeError(f'injected crash {inject}')
        derived = _regenerate_derived(table, record_id)
        journal['stage'] = 'post_derived_pre_revision'
        _write_journal(journal)
        if inject == 'post_derived_pre_revision':
            raise RuntimeError('injected crash post_derived_pre_revision')
        revs = _load_revisions()
        key = target_key(table, record_id)
        revs[key] = {'revision': state['revision'] + 1, 'sha256': after_sha, 'at': utc_now()}
        _save_revisions(revs)
        journal['stage'] = 'post_revision_pre_oplog'
        _write_journal(journal)
        if inject == 'committed_before_oplog':
            raise RuntimeError('injected crash committed_before_oplog')
        result = {
            'applied_at': utc_now(),
            'path': table,
            'record_id': record_id,
            'operation_id': operation_id,
            'mutation_digest': digest,
            'backup': str(backup_path.relative_to(ROOT)),
            'before_sha256': preview['before_sha256'],
            'after_sha256': after_sha,
            'revision': state['revision'] + 1,
            'derived': derived,
            'diagnostic_marker': BENIGN,
        }
        if operation_id:
            _append_operation(
                {
                    'operation_id': operation_id,
                    'path': table,
                    'record_id': record_id,
                    'mutation_digest': digest,
                    'status': 'committed',
                    'at': result['applied_at'],
                    'result': result,
                    'after_sha256': after_sha,
                }
            )
            journal['stage'] = 'post_oplog_pre_journal_commit'
            _write_journal(journal)
            if os.environ.get('CATALOG_EDIT_INJECT_CRASH') == 'post_oplog_pre_journal_commit':
                raise RuntimeError('injected crash post_oplog_pre_journal_commit')
        journal['stage'] = 'committed'
        journal['status'] = 'committed'
        journal['committed_at'] = utc_now()
        _write_journal(journal)
        return result


def _finish_restore_journal(
    entry: dict,
    *,
    table: str,
    record_id: str | None,
    path: Path,
    restore_backup: Path,
    pre_restore_revision: int,
) -> dict:
    inject = os.environ.get('CATALOG_EDIT_INJECT_CRASH')
    if inject == 'restore_mid_write':
        raise RuntimeError('injected crash restore_mid_write')
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    shutil.copy2(restore_backup, tmp)
    tmp.replace(path)
    if inject == 'restore_post_canonical_pre_revision':
        raise RuntimeError('injected crash restore_post_canonical_pre_revision')
    derived = _regenerate_derived(table, record_id)
    after_sha = sha256_bytes(path.read_bytes())
    key = entry['target_key']
    new_revision = pre_restore_revision + 1
    revs = _load_revisions()
    revs[key] = {'revision': new_revision, 'sha256': after_sha, 'at': utc_now()}
    _save_revisions(revs)
    entry['stage'] = 'committed'
    entry['status'] = 'committed'
    entry['after_sha256'] = after_sha
    entry['restored_revision'] = new_revision
    entry['committed_at'] = utc_now()
    _write_journal(entry)
    return {
        'restored': True,
        'sha256': after_sha,
        'path': table,
        'record_id': record_id,
        'revision': new_revision,
        'pre_restore_revision': pre_restore_revision,
        'monotonic': new_revision > pre_restore_revision,
        'derived': derived,
    }


def restore_from_backup(table: str, backup_relative: str, *, record_id: str | None = None) -> dict:
    _process_start_barrier()
    with _acquire_transaction_lock(table, record_id):
        _reconcile_journals_body(table_filter=None)
        path = resolve_table_path(table)
        backup = ROOT / backup_relative
        backup_resolved = backup.resolve()
        if os.path.commonpath([str(backup_resolved), str(BACKUP_DIR.resolve())]) != str(BACKUP_DIR.resolve()):
            raise ValueError('backup path outside catalog-backups')
        key = target_key(table, record_id)
        state = read_state(table, record_id)
        pre_restore_revision = int(state['revision'])
        pre_snapshot = BACKUP_DIR / f'pre-restore-{uuid.uuid4().hex}.bak'
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, pre_snapshot)
        journal_id = uuid.uuid4().hex
        journal = {
            'journal_id': journal_id,
            'catalog_root': str(_root()),
            'table': table,
            'record_id': record_id,
            'target_key': key,
            'stage': 'restore_pending',
            'restore_backup': backup_relative,
            'backup': backup_relative,
            'pre_restore_snapshot': str(pre_snapshot.relative_to(ROOT)),
            'before_sha256': state['sha256'],
            'before_revision': json.loads(json.dumps(_load_revisions().get(key, {'revision': pre_restore_revision}))),
            'pre_restore_revision': pre_restore_revision,
            'started_at': utc_now(),
        }
        _write_journal(journal)
        return _finish_restore_journal(
            journal,
            table=table,
            record_id=record_id,
            path=path,
            restore_backup=backup_resolved,
            pre_restore_revision=pre_restore_revision,
        )
