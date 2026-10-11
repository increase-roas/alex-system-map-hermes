"""Local agent trace span storage (import idempotent by receipt_id)."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_trace_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        '''
        CREATE TABLE IF NOT EXISTS trace_imports(
            receipt_id TEXT PRIMARY KEY,
            source_path TEXT NOT NULL,
            imported_at TEXT NOT NULL,
            synthetic_only INTEGER NOT NULL,
            payload_sha256 TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS traces(
            trace_id TEXT PRIMARY KEY,
            receipt_id TEXT NOT NULL,
            label TEXT,
            started_at TEXT,
            ended_at TEXT,
            status TEXT,
            synthetic_only INTEGER NOT NULL,
            job_id TEXT,
            metadata TEXT
        );
        CREATE TABLE IF NOT EXISTS spans(
            span_id TEXT PRIMARY KEY,
            trace_id TEXT NOT NULL,
            parent_span_id TEXT,
            name TEXT NOT NULL,
            agent_identity TEXT,
            tool_action TEXT,
            started_at TEXT,
            ended_at TEXT,
            duration_ms INTEGER,
            status TEXT,
            error TEXT,
            component_ids TEXT,
            source_ids TEXT,
            evidence_ids TEXT,
            metadata TEXT
        );
        CREATE TABLE IF NOT EXISTS trace_cursors(
            source_path TEXT PRIMARY KEY,
            last_receipt_id TEXT,
            updated_at TEXT NOT NULL
        );
        '''
    )


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def _is_workflow_recovery_document(doc: dict) -> bool:
    return (
        doc.get('contract') == 'local-reference-v1'
        and isinstance(doc.get('tasks'), dict)
        and 'spans' not in doc
    )


def _workflow_recovery_to_trace_doc(path: Path, doc: dict) -> dict:
    job_id = doc.get('job_id') or path.stem
    receipt_id = f'workflow-recovery-{job_id}'
    spans = []
    for task_id, task in sorted(doc.get('tasks', {}).items()):
        spans.append(
            {
                'span_id': f'synthetic-task-{task_id}',
                'parent_span_id': None,
                'name': f'workflow.task.{task_id}',
                'agent_identity': 'local-reference-engine',
                'tool_action': task.get('next_action') or task.get('status', 'pending'),
                'started_at': None,
                'ended_at': None,
                'duration_ms': None,
                'status': task.get('status', 'unknown'),
                'component_ids': [],
                'source_ids': [],
                'evidence_ids': [],
                'metadata': {
                    'file_ref': str(path.relative_to(ROOT)),
                    'synthetic_only': True,
                    'task_goal': task.get('goal'),
                },
            }
        )
    return {
        'receipt_id': receipt_id,
        'trace_id': f'trace-{job_id}',
        'label': f'Synthetic workflow recovery ({job_id})',
        'synthetic_only': True,
        'started_at': None,
        'ended_at': None,
        'status': 'synthetic',
        'job_id': job_id,
        'metadata': {
            'import_kind': 'workflow_recovery_synthetic',
            'file_ref': str(path.relative_to(ROOT)),
            'current_revision': doc.get('current_revision'),
        },
        'spans': spans,
    }


def _persist_trace(conn: sqlite3.Connection, path: Path, doc: dict, digest: str) -> dict:
    receipt_id = doc.get('receipt_id') or doc.get('id') or path.stem
    if conn.execute('SELECT 1 FROM trace_imports WHERE receipt_id=?', (receipt_id,)).fetchone():
        return {'imported': False, 'receipt_id': receipt_id, 'reason': 'duplicate receipt_id'}
    synthetic_only = bool(doc.get('synthetic_only', doc.get('demo', False)))
    trace_id = doc.get('trace_id') or f'trace-{receipt_id}'
    try:
        source_path = str(path.relative_to(ROOT))
    except ValueError:
        source_path = str(path)
    conn.execute(
        'INSERT INTO trace_imports VALUES(?,?,?,?,?)',
        (receipt_id, source_path, utc_now(), 1 if synthetic_only else 0, digest),
    )
    conn.execute(
        'INSERT OR REPLACE INTO traces VALUES(?,?,?,?,?,?,?,?,?)',
        (
            trace_id,
            receipt_id,
            doc.get('label'),
            doc.get('started_at'),
            doc.get('ended_at'),
            doc.get('status', 'unknown'),
            1 if synthetic_only else 0,
            doc.get('job_id'),
            _canonical(doc.get('metadata', {})),
        ),
    )
    for span in doc.get('spans', []):
        conn.execute(
            'INSERT OR REPLACE INTO spans VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (
                span['span_id'],
                trace_id,
                span.get('parent_span_id'),
                span['name'],
                span.get('agent_identity'),
                span.get('tool_action'),
                span.get('started_at'),
                span.get('ended_at'),
                span.get('duration_ms'),
                span.get('status', 'unknown'),
                span.get('error'),
                _canonical(span.get('component_ids', [])),
                _canonical(span.get('source_ids', [])),
                _canonical(span.get('evidence_ids', [])),
                _canonical(span.get('metadata', {})),
            ),
        )
    conn.execute(
        'INSERT INTO trace_cursors VALUES(?,?,?) ON CONFLICT(source_path) DO UPDATE SET '
        'last_receipt_id=excluded.last_receipt_id, updated_at=excluded.updated_at',
        (str(path), receipt_id, utc_now()),
    )
    conn.commit()
    return {
        'imported': True,
        'receipt_id': receipt_id,
        'trace_id': trace_id,
        'spans': len(doc.get('spans', [])),
        'synthetic_only': synthetic_only,
    }


def import_trace_document(conn: sqlite3.Connection, path: Path) -> dict:
    ensure_trace_schema(conn)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    doc = json.loads(raw)
    if _is_workflow_recovery_document(doc):
        doc = _workflow_recovery_to_trace_doc(path, doc)
    return _persist_trace(conn, path, doc, digest)


def list_traces(conn: sqlite3.Connection) -> list[dict]:
    ensure_trace_schema(conn)
    rows = conn.execute('SELECT * FROM traces ORDER BY started_at DESC').fetchall()
    return [dict(row) for row in rows]


def get_trace_cursor(conn: sqlite3.Connection, source_path: str) -> dict | None:
    ensure_trace_schema(conn)
    row = conn.execute('SELECT * FROM trace_cursors WHERE source_path=?', (source_path,)).fetchone()
    return dict(row) if row else None


def get_trace(conn: sqlite3.Connection, trace_id: str) -> dict | None:
    ensure_trace_schema(conn)
    trace = conn.execute('SELECT * FROM traces WHERE trace_id=?', (trace_id,)).fetchone()
    if not trace:
        return None
    spans = conn.execute('SELECT * FROM spans WHERE trace_id=? ORDER BY started_at', (trace_id,)).fetchall()
    return {'trace': dict(trace), 'spans': [dict(row) for row in spans]}


def export_trace_safe(conn: sqlite3.Connection, trace_id: str) -> dict:
    from output_screening import BENIGN_DIAGNOSTIC_MARKER, redact_value

    detail = get_trace(conn, trace_id)
    if not detail:
        return {'error': 'unknown trace', 'diagnostic_marker': BENIGN_DIAGNOSTIC_MARKER}
    redacted, notes = redact_value(detail)
    if isinstance(redacted, dict):
        return {
            **redacted,
            'diagnostic_marker': BENIGN_DIAGNOSTIC_MARKER,
            'screening_notes': sorted(set(notes)),
        }
    return {
        'trace': detail.get('trace'),
        'spans': detail.get('spans', []),
        'diagnostic_marker': BENIGN_DIAGNOSTIC_MARKER,
        'screening_notes': notes,
    }
