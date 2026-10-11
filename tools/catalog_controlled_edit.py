"""Controlled edit for allowlisted maintained JSON (preview, CAS, lock, backup, derived views)."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from maintained_derived_views import regenerate_derived_views
from output_screening import export_json_safe, screen_text

ROOT = Path(__file__).resolve().parents[1]
BACKUP_DIR = ROOT / 'app' / '.data' / 'catalog-backups'
LOCK_DIR = ROOT / 'app' / '.data' / 'catalog-edit-locks'
OPS_LOG = ROOT / 'app' / '.data' / 'catalog-edit-operations.jsonl'
EDITABLE = {
    'work/reliability/editable-fixture.json',
    'work/reliability/synthetic-sync-marker.json',
    'work/maintained/staging-catalog-record.json',
}
PROBE_CANARY = 'FAKE-canary-token-res0722-emitted'
BENIGN = 'LOCAL-SCREENING-OK'


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def resolve_editable(relative: str) -> Path:
    rel = relative.replace('\\', '/').lstrip('/')
    if rel not in EDITABLE:
        raise ValueError('path not in editable allowlist')
    raw = ROOT / rel
    if raw.is_symlink():
        raise ValueError('symlink not allowed for editable path')
    candidate = raw.resolve()
    root_resolved = ROOT.resolve()
    if os.path.commonpath([str(candidate), str(root_resolved)]) != str(root_resolved):
        raise ValueError('path escapes project root after resolution')
    if not candidate.is_file():
        raise ValueError('editable file missing')
    return candidate


def validate_editable_document(document: dict, *, current_revision: int) -> None:
    if not isinstance(document, dict):
        raise ValueError('document must be object')
    if 'revision' not in document or not isinstance(document['revision'], int):
        raise ValueError('revision must be integer')
    if isinstance(document['revision'], bool):
        raise ValueError('revision must be integer')
    if document['revision'] < 0:
        raise ValueError('revision must be non-negative')
    if document['revision'] != current_revision + 1:
        raise ValueError(f'revision must be exactly {current_revision + 1}')
    if 'label' in document and not isinstance(document['label'], str):
        raise ValueError('label must be string')
    note = document.get('note')
    if isinstance(note, str) and PROBE_CANARY in note:
        screened, _ = screen_text(note)
        raise ValueError(f'controlled edit note rejected: {screened}')
    if rel_schema := document.get('schema_version'):
        if not isinstance(rel_schema, str):
            raise ValueError('schema_version must be string')
    record_id = document.get('record_id')
    if record_id is not None and (not isinstance(record_id, str) or not record_id.strip()):
        raise ValueError('record_id must be nonempty string when present')
    refs = document.get('source_refs')
    if refs is not None and not isinstance(refs, list):
        raise ValueError('source_refs must be array when present')


def read_state(relative: str) -> dict:
    path = resolve_editable(relative)
    data = path.read_bytes()
    doc = json.loads(data)
    return {
        'path': relative,
        'sha256': sha256_bytes(data),
        'bytes': len(data),
        'document': doc,
        'revision': int(doc.get('revision', 0)),
    }


def document_diff(before: dict, after: dict) -> list[dict[str, Any]]:
    keys = sorted(set(before) | set(after))
    changes: list[dict[str, Any]] = []
    for key in keys:
        if before.get(key) != after.get(key):
            changes.append({'field': key, 'before': before.get(key), 'after': after.get(key)})
    return changes


def _load_operation(operation_id: str) -> dict | None:
    if not operation_id or not OPS_LOG.is_file():
        return None
    for line in OPS_LOG.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get('operation_id') == operation_id:
            return row
    return None


def _append_operation(row: dict) -> None:
    OPS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with OPS_LOG.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(row) + '\n')


def preview_patch(relative: str, expected_sha256: str, document: dict) -> dict:
    state = read_state(relative)
    validate_editable_document(document, current_revision=state['revision'])
    if state['sha256'] != expected_sha256:
        raise ValueError('revision conflict: file changed since expected_sha256')
    new_bytes = (json.dumps(document, indent=2) + '\n').encode()
    changes = document_diff(state['document'], document)
    raw = {
        'path': relative,
        'before_sha256': state['sha256'],
        'after_sha256': sha256_bytes(new_bytes),
        'preview': document,
        'diff': changes,
        'valid': True,
        'expected_revision': state['revision'],
        'next_revision': document['revision'],
    }
    return export_json_safe(raw)['payload']


def apply_patch(
    relative: str,
    expected_sha256: str,
    document: dict,
    *,
    operation_id: str | None = None,
) -> dict:
    if operation_id:
        prior = _load_operation(operation_id)
        if prior and prior.get('status') == 'committed' and prior.get('path') == relative:
            return prior['result']

    lock_path = LOCK_DIR / f'{sha256_bytes(relative.encode())[:16]}.lock'
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    with open(lock_path, 'w', encoding='utf-8') as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        preview = preview_patch(relative, expected_sha256, document)
        path = resolve_editable(relative)
        backup_path = BACKUP_DIR / f"{path.name}.{preview['before_sha256'][:12]}.bak"
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup_path)
        tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_bytes((json.dumps(document, indent=2) + '\n').encode())
        readback = json.loads(tmp.read_text())
        if readback != document:
            tmp.unlink(missing_ok=True)
            raise ValueError('readback mismatch after write')
        tmp.replace(path)
        after = path.read_bytes()
        after_sha = sha256_bytes(after)
        derived = regenerate_derived_views(relative, document, source_sha256=after_sha)
        result = {
            'applied_at': utc_now(),
            'path': relative,
            'operation_id': operation_id,
            'backup': str(backup_path.relative_to(ROOT)),
            'before_sha256': preview['before_sha256'],
            'after_sha256': after_sha,
            'revision': document.get('revision'),
            'derived': derived,
            'diagnostic_marker': BENIGN,
        }
        if operation_id:
            _append_operation(
                {
                    'operation_id': operation_id,
                    'path': relative,
                    'status': 'committed',
                    'at': result['applied_at'],
                    'before_sha256': preview['before_sha256'],
                    'after_sha256': after_sha,
                    'result': result,
                }
            )
        return result


def restore_from_backup(relative: str, backup_relative: str) -> dict:
    path = resolve_editable(relative)
    backup = ROOT / backup_relative
    backup_resolved = backup.resolve()
    if os.path.commonpath([str(backup_resolved), str(BACKUP_DIR.resolve())]) != str(BACKUP_DIR.resolve()):
        raise ValueError('backup path outside catalog-backups')
    shutil.copy2(backup_resolved, path)
    data = path.read_bytes()
    return {'restored': True, 'sha256': sha256_bytes(data), 'path': relative}
