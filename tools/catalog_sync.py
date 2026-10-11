"""Observe allowlisted catalog files; persist fingerprints in SQLite."""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _catalog_root() -> Path:
    from catalog_io import catalog_root

    return catalog_root()


def allowlisted_paths() -> list[str]:
    base = _catalog_root()
    paths = sorted(p.relative_to(base).as_posix() for p in (base / 'data').glob('*.json'))
    overview = 'views/overview.json'
    if (base / overview).is_file() and overview not in paths:
        paths.append(overview)
    for rel_marker in (
        'work/reliability/synthetic-sync-marker.json',
        'work/reliability/editable-fixture.json',
    ):
        if (ROOT / rel_marker).is_file() and rel_marker not in paths:
            paths.append(rel_marker)
    return sorted(paths)


ALLOWLIST = allowlisted_paths()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_watch(conn: sqlite3.Connection) -> None:
    conn.executescript(
        '''
        CREATE TABLE IF NOT EXISTS catalog_watch(
            path TEXT PRIMARY KEY,
            sha256 TEXT,
            bytes INTEGER,
            mtime REAL,
            observed_at TEXT NOT NULL,
            readable INTEGER NOT NULL,
            error TEXT
        );
        '''
    )


def observe_all(conn: sqlite3.Connection) -> list[dict]:
    ensure_watch(conn)
    rows: list[dict] = []
    now = utc_now()
    for relative in allowlisted_paths():
        path = (_catalog_root() if relative.startswith('data/') or relative.startswith('views/') else ROOT) / relative
        entry = {'path': relative, 'observed_at': now}
        try:
            data = path.read_bytes()
            stat = path.stat()
            digest = hashlib.sha256(data).hexdigest()
            conn.execute(
                'INSERT INTO catalog_watch(path,sha256,bytes,mtime,observed_at,readable,error) '
                'VALUES(?,?,?,?,?,1,NULL) '
                'ON CONFLICT(path) DO UPDATE SET sha256=excluded.sha256, bytes=excluded.bytes, '
                'mtime=excluded.mtime, observed_at=excluded.observed_at, readable=1, error=NULL',
                (relative, digest, len(data), stat.st_mtime, now),
            )
            entry.update({'readable': True, 'sha256': digest, 'bytes': len(data), 'mtime': stat.st_mtime})
        except OSError as exc:
            conn.execute(
                'INSERT INTO catalog_watch(path,sha256,bytes,mtime,observed_at,readable,error) '
                'VALUES(?,?,?,?,?,0,?) '
                'ON CONFLICT(path) DO UPDATE SET observed_at=excluded.observed_at, readable=0, error=excluded.error',
                (relative, None, None, None, now, str(exc)),
            )
            entry.update({'readable': False, 'error': str(exc)})
        rows.append(entry)
    conn.commit()
    return rows


def get_sync_status(conn: sqlite3.Connection) -> dict:
    ensure_watch(conn)
    rows = conn.execute('SELECT * FROM catalog_watch ORDER BY path').fetchall()
    items = [dict(row) for row in rows]
    unreadable = [item for item in items if not item.get('readable')]
    last = max((item['observed_at'] for item in items), default=None)
    return {
        'last_observation': last,
        'files': items,
        'unreadable_count': len(unreadable),
        'allowlist': allowlisted_paths(),
    }


def sync_status(conn: sqlite3.Connection) -> dict:
    """Backward-compatible alias for get_sync_status."""
    return get_sync_status(conn)
