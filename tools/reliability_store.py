"""Project-local reliability state: corrections, handoffs (revision 2)."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_PREPARED_CONNECTION_IDS: set[int] = set()

ROOT = Path(__file__).resolve().parents[1]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=8000')
    return prepare_connection(conn)


_SCHEMA_STATEMENTS = (
    '''
    CREATE TABLE IF NOT EXISTS reliability_corrections(
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        supersedes_note TEXT NOT NULL,
        governing_text TEXT NOT NULL,
        active INTEGER NOT NULL,
        history_json TEXT NOT NULL
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS reliability_handoffs(
        operation_id TEXT PRIMARY KEY,
        owner TEXT NOT NULL,
        revision INTEGER NOT NULL,
        checkpoint_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS reliability_requirements(
        requirement_id TEXT PRIMARY KEY,
        documented_path TEXT,
        installed_path TEXT,
        actually_used_evidence TEXT,
        owner TEXT,
        last_verified_at TEXT,
        next_unresolved_step TEXT
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS reliability_recheck_queue(
        output_id TEXT PRIMARY KEY,
        reason TEXT NOT NULL,
        marked_at TEXT NOT NULL
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS reliability_transfer_operations(
        operation_id TEXT PRIMARY KEY,
        digest TEXT NOT NULL,
        result_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    ''',
)


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Apply reliability DDL once per connection. Must run only outside an open transaction."""
    conn_id = id(conn)
    if conn_id in _PREPARED_CONNECTION_IDS:
        return
    for statement in _SCHEMA_STATEMENTS:
        conn.execute(statement)
    _PREPARED_CONNECTION_IDS.add(conn_id)


def prepare_connection(conn: sqlite3.Connection) -> sqlite3.Connection:
    ensure_schema(conn)
    return conn


def save_correction(
    conn: sqlite3.Connection,
    correction_id: str,
    supersedes_note: str,
    governing_text: str,
) -> dict:
    ensure_schema(conn)
    now = utc_now()
    existing = conn.execute('SELECT * FROM reliability_corrections WHERE id=?', (correction_id,)).fetchone()
    if existing:
        conn.execute('UPDATE reliability_corrections SET active=1 WHERE id=?', (correction_id,))
        mark_output_recheck(conn, 'reports/build-supervision-state.json', 'superseded by ' + correction_id)
        conn.commit()
        row = dict(existing)
        row['active'] = 1
        return row
    for row in conn.execute('SELECT id FROM reliability_corrections WHERE active=1').fetchall():
        old = dict(conn.execute('SELECT * FROM reliability_corrections WHERE id=?', (row['id'],)).fetchone())
        history = json.loads(old['history_json'])
        history.append({'deactivated_at': now, 'reason': 'superseded by ' + correction_id})
        conn.execute(
            'UPDATE reliability_corrections SET active=0, history_json=? WHERE id=?',
            (json.dumps(history), row['id']),
        )
    conn.execute(
        'INSERT INTO reliability_corrections VALUES(?,?,?,?,?,?)',
        (correction_id, now, supersedes_note, governing_text, 1, json.dumps([])),
    )
    mark_output_recheck(conn, 'reports/build-supervision-state.json', 'superseded by ' + correction_id)
    conn.commit()
    return {'id': correction_id, 'created_at': now, 'governing_text': governing_text, 'active': True}


def mark_output_recheck(conn: sqlite3.Connection, output_id: str, reason: str) -> None:
    ensure_schema(conn)
    conn.execute(
        'INSERT INTO reliability_recheck_queue VALUES(?,?,?) '
        'ON CONFLICT(output_id) DO UPDATE SET reason=excluded.reason, marked_at=excluded.marked_at',
        (output_id, reason, utc_now()),
    )
    conn.commit()


def list_recheck_queue(conn: sqlite3.Connection) -> list[dict]:
    ensure_schema(conn)
    return [dict(row) for row in conn.execute('SELECT * FROM reliability_recheck_queue ORDER BY output_id')]


def correction_history(conn: sqlite3.Connection) -> list[dict]:
    ensure_schema(conn)
    rows = []
    for row in conn.execute('SELECT * FROM reliability_corrections ORDER BY created_at').fetchall():
        item = dict(row)
        item['history'] = json.loads(item.pop('history_json') or '[]')
        rows.append(item)
    return rows


def recover_decision_with_correction(conn: sqlite3.Connection, presented_note: str) -> dict:
    """Apply active correction over an older conflicting note (recovery path)."""
    ensure_schema(conn)
    corr = active_correction(conn)
    if not corr:
        return {
            'governing_applied': False,
            'next_action': None,
            'affected_outputs_needing_recheck': list_recheck_queue(conn),
            'history_retained': bool(correction_history(conn)),
        }
    governs = presented_note.strip() == corr['supersedes_note'].strip()
    return {
        'governing_applied': governs,
        'next_action': corr['governing_text'] if governs else presented_note,
        'presented_note': presented_note,
        'active_correction_id': corr['id'],
        'affected_outputs_needing_recheck': list_recheck_queue(conn),
        'history_retained': len(correction_history(conn)) >= 1,
        'deactivated_prior_corrections': [
            c['id'] for c in correction_history(conn) if not c.get('active')
        ],
    }


def get_handoff(conn: sqlite3.Connection, operation_id: str) -> dict | None:
    row = conn.execute('SELECT * FROM reliability_handoffs WHERE operation_id=?', (operation_id,)).fetchone()
    return dict(row) if row else None


def transfer_handoff(
    conn: sqlite3.Connection,
    operation_id: str,
    new_owner: str,
    revision: int,
    checkpoint: dict,
) -> dict:
    handoff = get_handoff(conn, operation_id)
    if not handoff:
        return record_handoff(conn, operation_id, new_owner, revision, checkpoint)
    return transfer_handoff_cas(
        conn,
        operation_id,
        handoff['owner'],
        handoff['revision'],
        new_owner,
        revision,
        checkpoint,
    )


def transfer_handoff_cas(
    conn: sqlite3.Connection,
    operation_id: str,
    expected_owner: str,
    expected_revision: int,
    new_owner: str,
    revision: int,
    checkpoint: dict,
    *,
    commit: bool = True,
) -> dict:
    handoff = get_handoff(conn, operation_id)
    if not handoff:
        raise ValueError('missing handoff checkpoint')
    if handoff['owner'] != expected_owner or handoff['revision'] != expected_revision:
        raise ValueError('stale handoff: expected owner/revision mismatch')
    now = utc_now()
    cur = conn.execute(
        'UPDATE reliability_handoffs SET owner=?, revision=?, checkpoint_json=?, created_at=? '
        'WHERE operation_id=? AND owner=? AND revision=?',
        (new_owner, revision, json.dumps(checkpoint), now, operation_id, expected_owner, expected_revision),
    )
    if cur.rowcount != 1:
        raise ValueError('handoff transfer lost race')
    if get_handoff(conn, operation_id)['owner'] != new_owner:
        raise ValueError('handoff owner not updated')
    if commit:
        conn.commit()
    return get_handoff(conn, operation_id) or {}


def merge_recover_packet(engine_packet: dict, rel_conn: sqlite3.Connection, presented_note: str | None) -> dict:
    """Merge engine recover with job-scoped workflow correction governance (not global reliability text)."""
    from job_recovery import merge_job_recover_packet

    _ = rel_conn  # retained for callers; workflow recovery does not use global correction rows
    return merge_job_recover_packet(engine_packet, presented_note)


def find_handoff_for_job(conn: sqlite3.Connection, job_id: str) -> dict | None:
    canonical_id = f'{job_id}-handoff'
    row = conn.execute('SELECT * FROM reliability_handoffs WHERE operation_id=?', (canonical_id,)).fetchone()
    if row:
        return dict(row)
    candidates: list[dict] = []
    for handoff_row in conn.execute('SELECT * FROM reliability_handoffs').fetchall():
        checkpoint = json.loads(handoff_row['checkpoint_json'])
        if checkpoint.get('job_id') == job_id:
            candidates.append(dict(handoff_row))
    if not candidates:
        return None
    return max(candidates, key=lambda item: int(item['revision']))


def advance_handoff_revision_cas(
    conn: sqlite3.Connection,
    operation_id: str,
    expected_revision: int,
    new_revision: int,
    owner: str,
    *,
    commit: bool = True,
    workflow_operation_id: str | None = None,
) -> None:
    if os.environ.get('AGENT_WF_TEST_CAS_FAIL') == '1':
        target = os.environ.get('AGENT_WF_TEST_CAS_FAIL_OP', '')
        if target and workflow_operation_id == target:
            raise ValueError('handoff revision advance lost race')
    cur = conn.execute(
        'UPDATE reliability_handoffs SET revision=? WHERE operation_id=? AND revision=? AND owner=?',
        (new_revision, operation_id, expected_revision, owner),
    )
    if cur.rowcount != 1:
        raise ValueError('handoff revision advance lost race')
    if commit:
        conn.commit()


def advance_handoff_revision(conn: sqlite3.Connection, operation_id: str, revision: int) -> None:
    conn.execute(
        'UPDATE reliability_handoffs SET revision=? WHERE operation_id=?',
        (revision, operation_id),
    )
    conn.commit()


def assert_handoff_owner(conn: sqlite3.Connection, operation_id: str, actor: str) -> None:
    handoff = get_handoff(conn, operation_id)
    if not handoff:
        raise ValueError('missing handoff checkpoint')
    if handoff['owner'] != actor:
        raise ValueError('stale owner: handoff assigned to ' + handoff['owner'])


def active_correction(conn: sqlite3.Connection) -> dict | None:
    ensure_schema(conn)
    row = conn.execute('SELECT * FROM reliability_corrections WHERE active=1 ORDER BY created_at DESC LIMIT 1').fetchone()
    return dict(row) if row else None


def record_handoff(
    conn: sqlite3.Connection,
    operation_id: str,
    owner: str,
    revision: int,
    checkpoint: dict,
    *,
    commit: bool = True,
) -> dict:
    if not checkpoint.get('job_id'):
        raise ValueError('checkpoint job_id required')
    now = utc_now()
    conn.execute(
        'INSERT INTO reliability_handoffs VALUES(?,?,?,?,?) '
        'ON CONFLICT(operation_id) DO NOTHING',
        (operation_id, owner, revision, json.dumps(checkpoint), now),
    )
    if commit:
        conn.commit()
    row = conn.execute('SELECT * FROM reliability_handoffs WHERE operation_id=?', (operation_id,)).fetchone()
    return dict(row) if row else {}


def handoff_exists(conn: sqlite3.Connection, operation_id: str) -> bool:
    return conn.execute('SELECT 1 FROM reliability_handoffs WHERE operation_id=?', (operation_id,)).fetchone() is not None


def lookup_transfer_operation(conn: sqlite3.Connection, operation_id: str) -> tuple[str, dict] | None:
    row = conn.execute(
        'SELECT digest, result_json FROM reliability_transfer_operations WHERE operation_id=?',
        (operation_id,),
    ).fetchone()
    if not row:
        return None
    return row['digest'], json.loads(row['result_json'])


def record_transfer_operation(
    conn: sqlite3.Connection,
    operation_id: str,
    digest: str,
    result: dict,
    *,
    commit: bool = True,
) -> None:
    conn.execute(
        'INSERT INTO reliability_transfer_operations VALUES(?,?,?,?)',
        (operation_id, digest, json.dumps(result), utc_now()),
    )
    if commit:
        conn.commit()


def job_revision_in_tx(conn: sqlite3.Connection, job_id: str) -> int | None:
    row = conn.execute('SELECT revision FROM jobs WHERE id=?', (job_id,)).fetchone()
    return int(row['revision']) if row else None


def upsert_requirement_evidence(
    conn: sqlite3.Connection,
    requirement_id: str,
    *,
    documented_path: str | None = None,
    installed_path: str | None = None,
    actually_used_evidence: str | None = None,
    owner: str,
    next_unresolved_step: str,
) -> None:
    ensure_schema(conn)
    now = utc_now()
    conn.execute(
        'INSERT INTO reliability_requirements VALUES(?,?,?,?,?,?,?) '
        'ON CONFLICT(requirement_id) DO UPDATE SET '
        'documented_path=COALESCE(excluded.documented_path,documented_path), '
        'installed_path=COALESCE(excluded.installed_path,installed_path), '
        'actually_used_evidence=COALESCE(excluded.actually_used_evidence,actually_used_evidence), '
        'owner=excluded.owner, last_verified_at=excluded.last_verified_at, '
        'next_unresolved_step=excluded.next_unresolved_step',
        (
            requirement_id,
            documented_path,
            installed_path,
            actually_used_evidence,
            owner,
            now,
            next_unresolved_step,
        ),
    )
    conn.commit()


def all_requirements(conn: sqlite3.Connection) -> list[dict]:
    ensure_schema(conn)
    return [dict(row) for row in conn.execute('SELECT * FROM reliability_requirements ORDER BY requirement_id')]


def reliability_status_payload() -> dict:
    """UI/API payload: verification report + persisted requirement rows."""
    report_path = ROOT / 'reports/reliability-verification.json'
    report: dict = {}
    if report_path.is_file():
        report = json.loads(report_path.read_text())
    review_path = ROOT / 'reports/independent-reliability-review.json'
    independent = json.loads(review_path.read_text()) if review_path.is_file() else {}
    db_path = ROOT / 'app' / '.data' / 'reliability.sqlite'
    rows: list[dict] = []
    correction = None
    if db_path.is_file():
        conn = connect(db_path)
        rows = all_requirements(conn)
        correction = active_correction(conn)
        conn.close()
    items = report.get('items') or []
    merged = []
    for req_id in ('REL-01', 'REL-02', 'REL-03', 'REL-04', 'REL-05', 'REL-06'):
        item = next((i for i in items if i.get('id') == req_id), None)
        row = next((r for r in rows if r.get('requirement_id') == req_id), None)
        merged.append(
            {
                'id': req_id,
                'owner': (item or {}).get('owner') or (row or {}).get('owner'),
                'last_verified_at': (item or {}).get('last_verified_at') or (row or {}).get('last_verified_at'),
                'status': (item or {}).get('status', 'not-run'),
                'evidence': (item or {}).get('evidence'),
                'next_unresolved_step': (item or {}).get('next_unresolved_step')
                or (row or {}).get('next_unresolved_step')
                or '',
                'documented_path': (row or {}).get('documented_path'),
                'installed_path': (row or {}).get('installed_path'),
                'actually_used_evidence': (row or {}).get('actually_used_evidence'),
            }
        )
    return {
        'delivery_id': report.get('delivery_id'),
        'revision': report.get('revision', 2),
        'acknowledgment': report.get('acknowledgment'),
        'overall_rel_status': report.get('overall_rel_status', 'not-run'),
        'requirements': merged,
        'active_correction': correction,
        'synthetic_sync_trace_e2e': report.get('synthetic_sync_trace_e2e'),
        'browser_proof': report.get('browser_proof'),
        'note': report.get('note'),
        'independent_review_disposition': report.get('independent_review_disposition')
        or independent.get('disposition'),
        'owner_evidence_not_independent_acceptance': report.get('owner_evidence_not_independent_acceptance', True),
        'correction_id': report.get('correction_id'),
    }
