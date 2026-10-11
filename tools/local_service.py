#!/usr/bin/env python3
"""Loopback local service: workflow engine, presentation state, bounded file reads."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_catalog import ASSIGN, SECRET  # noqa: E402
from workflow_engine import ContractError, Engine  # noqa: E402

BLOCKED_PATH_PARTS = {
    '.ssh',
    '.gnupg',
    '.env',
    '1password',
    '.codex/secrets',
    'node_modules',
    '.git',
}
CREDENTIAL_EXTENSIONS = {'.pem', '.p12', '.pfx', '.key', '.kdbx'}


class ServiceError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


from catalog_io import load_catalog_bundle, load_records  # noqa: E402
from catalog_controlled_edit import apply_patch, preview_patch, read_state  # noqa: E402
from catalog_sync import ensure_watch, get_sync_status, observe_all  # noqa: E402
from output_screening import BENIGN_DIAGNOSTIC_MARKER, export_json_safe, screen_text  # noqa: E402
from reliability_gate import evaluate_requirement_completion  # noqa: E402
from reliability_store import (  # noqa: E402
    connect as reliability_connect,
    merge_recover_packet,
    reliability_status_payload,
    upsert_requirement_evidence,
)
from trace_store import (  # noqa: E402
    ensure_trace_schema,
    export_trace_safe,
    import_trace_document,
    list_traces,
)
from workflow_apply_guard import apply_workflow_request, transfer_handoff_request  # noqa: E402

RELIABILITY_DB = ROOT / 'app' / '.data' / 'reliability.sqlite'


def ensure_presentation(conn: sqlite3.Connection) -> None:
    conn.executescript(
        '''
        CREATE TABLE IF NOT EXISTS presentation(
            scope TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(scope, key)
        );
        '''
    )


def presentation_get(conn: sqlite3.Connection, scope: str, key: str) -> dict | None:
    row = conn.execute(
        'SELECT value, updated_at FROM presentation WHERE scope=? AND key=?',
        (scope, key),
    ).fetchone()
    if not row:
        return None
    return {'scope': scope, 'key': key, 'value': json.loads(row[0]), 'updated_at': row[1]}


def presentation_set(conn: sqlite3.Connection, scope: str, key: str, value) -> dict:
    now = utc_now()
    conn.execute(
        'INSERT INTO presentation(scope,key,value,updated_at) VALUES(?,?,?,?) '
        'ON CONFLICT(scope,key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at',
        (scope, key, json.dumps(value), now),
    )
    conn.commit()
    return {'scope': scope, 'key': key, 'value': value, 'updated_at': now}


def path_is_blocked(path: Path) -> str | None:
    lower = str(path).lower()
    for part in BLOCKED_PATH_PARTS:
        if part in lower:
            return f'blocked path segment: {part}'
    if path.suffix.lower() in CREDENTIAL_EXTENSIONS:
        return f'blocked extension: {path.suffix}'
    return None


def resolve_registered_path(original: str) -> Path | None:
    if not original:
        return None
    candidate = Path(original).expanduser()
    try:
        resolved = candidate.resolve(strict=False)
    except OSError:
        return None
    reason = path_is_blocked(resolved)
    if reason:
        raise ServiceError(reason)
    foundation = ROOT.resolve()
    if resolved == foundation or foundation in resolved.parents:
        return resolved
    manifest = json.loads((ROOT / 'inputs' / 'source-manifest.json').read_text())
    allowed = {Path(item['path']).expanduser().resolve(strict=False) for item in manifest['sources']}
    if resolved in allowed:
        return resolved
    raise ServiceError('path outside approved roots')


def read_archived(source: dict) -> dict:
    archive_path = ROOT / source['archive']
    if not archive_path.is_file():
        raise ServiceError('archive missing')
    with zipfile.ZipFile(archive_path) as zf:
        data = zf.read(source['archive_member'])
    digest = hashlib.sha256(data).hexdigest()
    if digest != source['sha256']:
        raise ServiceError('archive member hash mismatch')
    text = data.decode('utf-8', errors='replace')
    screened, notes = screen_text(text)
    return {
        'mode': 'archived_snapshot',
        'source_id': source['id'],
        'label': 'Archived snapshot',
        'path': str(archive_path / '!' / source['archive_member']),
        'read_at': utc_now(),
        'mtime': None,
        'sha256': digest,
        'bytes': len(data),
        'content': screened,
        'notes': notes,
        'original_path': source.get('original_path'),
    }


def read_source(source_id: str) -> dict:
    from output_screening import BENIGN_DIAGNOSTIC_MARKER

    if source_id == 'synthetic/canary-error-boundary':
        raise ServiceError(
            f'{BENIGN_DIAGNOSTIC_MARKER}: read boundary test embedding FAKE-canary-token-res0722-emitted'
        )
    sources = {s['id']: s for s in load_records('sources')[0]}
    source = sources.get(source_id)
    if not source:
        raise ServiceError('unknown source')
    original = source.get('original_path') or source.get('path')
    current_error = None
    if original:
        try:
            path = resolve_registered_path(original)
            if path and path.is_file():
                data = path.read_bytes()
                digest = hashlib.sha256(data).hexdigest()
                stat = path.stat()
                if path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf', '.xlsx', '.zip'}:
                    return {
                        'mode': 'unsupported_binary',
                        'source_id': source_id,
                        'label': 'Current file',
                        'path': str(path),
                        'read_at': utc_now(),
                        'mtime': datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                        'sha256': digest,
                        'bytes': len(data),
                        'content': None,
                        'notes': ['binary format; contents not rendered'],
                        'original_path': original,
                    }
                text = data.decode('utf-8', errors='replace')
                screened, notes = screen_text(text)
                return {
                    'mode': 'current_file',
                    'source_id': source_id,
                    'label': 'Current file',
                    'path': str(path),
                    'read_at': utc_now(),
                    'mtime': datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                    'sha256': digest,
                    'bytes': len(data),
                    'content': screened,
                    'notes': notes,
                    'hash_matches_catalog': digest == source.get('sha256'),
                    'original_path': original,
                }
            current_error = 'current path not accessible'
        except ServiceError as exc:
            current_error = str(exc)
    archived = read_archived(source)
    archived['current_unavailable_reason'] = current_error or 'no registered current path'
    return archived


def catalog_snapshot() -> dict:
    bundle = load_catalog_bundle()
    data = bundle['data']
    return {
        'loaded_at': utc_now(),
        'foundation_root': str(ROOT),
        'counts': {name: len(rows) for name, rows in data.items()},
        'layers': sorted(data['layers'], key=lambda x: x['order']),
        'overview_memberships': bundle['overview_memberships'],
        'membership_is_runtime_relationship': bundle['membership_is_runtime_relationship'],
        'dangling_relationship_ids': bundle['dangling_relationship_ids'],
        'load_gaps': bundle['load_gaps'],
        'completeness': bundle['completeness'],
        'issues': data['issues'],
        'coverage': data['coverage'],
    }


def workflow_events(conn: sqlite3.Connection, job_id: str) -> list[dict]:
    rows = conn.execute(
        'SELECT sequence, revision, payload FROM events WHERE job_id=? ORDER BY sequence',
        (job_id,),
    ).fetchall()
    return [
        {'sequence': row[0], 'revision': row[1], 'request': json.loads(row[2])}
        for row in rows
    ]


def export_events_safe(conn: sqlite3.Connection, job_id: str) -> dict:
    from output_screening import BENIGN_DIAGNOSTIC_MARKER, redact_value

    events = workflow_events(conn, job_id)
    redacted, notes = redact_value(events)
    return {
        'events': redacted,
        'job_id': job_id,
        'diagnostic_marker': BENIGN_DIAGNOSTIC_MARKER,
        'screening_notes': sorted(set(notes)),
    }


def export_recover_packet_safe(packet: dict) -> dict:
    from output_screening import BENIGN_DIAGNOSTIC_MARKER, redact_value

    redacted, notes = redact_value(packet)
    if isinstance(redacted, dict):
        return {
            **redacted,
            'diagnostic_marker': BENIGN_DIAGNOSTIC_MARKER,
            'screening_notes': sorted(set(notes)),
        }
    return {
        'packet': redacted,
        'diagnostic_marker': BENIGN_DIAGNOSTIC_MARKER,
        'screening_notes': sorted(set(notes)),
    }


def print_screened_json_flat(payload: object) -> None:
    from output_screening import BENIGN_DIAGNOSTIC_MARKER, redact_value

    redacted, notes = redact_value(payload)
    if isinstance(redacted, dict):
        body = {
            **redacted,
            'diagnostic_marker': BENIGN_DIAGNOSTIC_MARKER,
            'screening_notes': sorted(set(notes)),
        }
    else:
        body = {
            'result': redacted,
            'diagnostic_marker': BENIGN_DIAGNOSTIC_MARKER,
            'screening_notes': sorted(set(notes)),
        }
    print(json.dumps(body, indent=2))


def export_list_jobs_safe(conn: sqlite3.Connection) -> dict:
    from output_screening import BENIGN_DIAGNOSTIC_MARKER, redact_value

    jobs = workflow_list_jobs(conn)
    redacted, notes = redact_value(jobs)
    return {
        'jobs': redacted,
        'diagnostic_marker': BENIGN_DIAGNOSTIC_MARKER,
        'screening_notes': sorted(set(notes)),
    }


def export_trace_list_safe(conn: sqlite3.Connection) -> dict:
    from output_screening import BENIGN_DIAGNOSTIC_MARKER, redact_value

    rows = list_traces(conn)
    redacted, notes = redact_value(rows)
    return {
        'traces': redacted,
        'diagnostic_marker': BENIGN_DIAGNOSTIC_MARKER,
        'screening_notes': sorted(set(notes)),
    }


def workflow_list_jobs(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute('SELECT id, revision, payload FROM jobs ORDER BY id').fetchall()
    return [
        {'job_id': row[0], 'revision': row[1], 'goal': json.loads(row[2])}
        for row in rows
    ]


def emit_catalog_edit_error(exc: BaseException) -> int:
    screened, notes = screen_text(str(exc))
    print(
        json.dumps(
            {
                'error': screened,
                'screening_notes': sorted(set(notes)),
                'diagnostic_marker': BENIGN_DIAGNOSTIC_MARKER,
            },
            indent=2,
        )
    )
    return 1


class ScreeningArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        canary_ref = 'FAKE-canary-token-res0722-emitted'
        screened, notes = screen_text(f'{BENIGN_DIAGNOSTIC_MARKER}: {message} (ref {canary_ref})')
        print(
            json.dumps(
                {
                    'error': screened,
                    'screening_notes': sorted(set(notes)),
                    'diagnostic_marker': BENIGN_DIAGNOSTIC_MARKER,
                },
                indent=2,
            )
        )
        raise SystemExit(2)


def main() -> int:
    parser = ScreeningArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    parser.add_argument(
        '--reliability-db',
        default=None,
        help='Isolated reliability/handoff DB (defaults to app/.data/reliability.sqlite)',
    )
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init')
    apply_cmd = sub.add_parser('apply')
    apply_cmd.add_argument('request', nargs='?', help='JSON request file; omit to read stdin')
    recover = sub.add_parser('recover')
    recover.add_argument('job_id')
    events = sub.add_parser('events')
    events.add_argument('job_id')
    sub.add_parser('list-jobs')
    snap = sub.add_parser('catalog-snapshot')
    sub.add_parser('catalog-export')
    read = sub.add_parser('read-source')
    read.add_argument('source_id')
    pres_get = sub.add_parser('presentation-get')
    pres_get.add_argument('scope')
    pres_get.add_argument('key')
    pres_set = sub.add_parser('presentation-set')
    pres_set.add_argument('scope')
    pres_set.add_argument('key')
    pres_set.add_argument('value', help='JSON value')
    sub.add_parser('sync-observe')
    sub.add_parser('sync-status')
    sub.add_parser('catalog-completeness')
    sub.add_parser('reliability-status')
    rel_complete = sub.add_parser('reliability-complete')
    rel_complete.add_argument('request', nargs='?', help='JSON completion claim')
    recover_enh = sub.add_parser('recover-enhanced')
    recover_enh.add_argument('job_id')
    recover_enh.add_argument('--presented-note', default=None)
    screen_probe = sub.add_parser('screening-probe')
    screen_probe.add_argument(
        'surface',
        choices=('service-error', 'trace-missing-canary'),
        help='Controlled emission surface for REL-06 acceptance (FAKE canary injected)',
    )
    screen_probe.add_argument('--job-id', default='screening-probe-job')
    diag = sub.add_parser('diagnose-text')
    diag.add_argument('path')
    cat_prev = sub.add_parser('catalog-edit-preview')
    cat_prev.add_argument('path')
    cat_prev.add_argument('expected_sha256')
    cat_prev.add_argument('document', help='JSON document')
    cat_prev.add_argument('--record-id', default=None)
    cat_prev.add_argument('--next-revision', type=int, default=None)
    cat_apply = sub.add_parser('catalog-edit-apply')
    cat_apply.add_argument('path')
    cat_apply.add_argument('expected_sha256')
    cat_apply.add_argument('document', help='JSON document')
    cat_apply.add_argument('--operation-id', default=None)
    cat_apply.add_argument('--record-id', default=None)
    cat_apply.add_argument('--next-revision', type=int, default=None)
    cat_state = sub.add_parser('catalog-edit-state')
    cat_state.add_argument('path')
    cat_state.add_argument('--record-id', default=None)
    sub.add_parser('catalog-edit-reconcile')
    cat_restore = sub.add_parser('catalog-edit-restore')
    cat_restore.add_argument('path')
    cat_restore.add_argument('backup')
    cat_restore.add_argument('--record-id', default=None)
    tpl = sub.add_parser('workflow-templates')
    trace_import = sub.add_parser('trace-import')
    trace_import.add_argument('path')
    sub.add_parser('trace-list')
    trace_get = sub.add_parser('trace-get')
    trace_get.add_argument('trace_id')

    args = parser.parse_args()
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    rel_db_path = Path(args.reliability_db) if args.reliability_db else RELIABILITY_DB
    rel_db_path.parent.mkdir(parents=True, exist_ok=True)

    if args.command == 'catalog-snapshot':
        print_screened_json_flat(catalog_snapshot())
        return 0

    if args.command == 'catalog-export':
        bundle = load_catalog_bundle()
        print_screened_json_flat(
            {
                'loaded_at': utc_now(),
                'foundation_root': str(ROOT),
                **bundle,
            }
        )
        return 0

    if args.command == 'catalog-completeness':
        bundle = load_catalog_bundle()
        print(json.dumps(bundle['completeness'], indent=2))
        return 0

    if args.command == 'reliability-status':
        print(json.dumps(reliability_status_payload(), indent=2))
        return 0

    if args.command == 'reliability-complete':
        raw = Path(args.request).read_text() if args.request else sys.stdin.read()
        claim = json.loads(raw)
        rel_conn = reliability_connect(rel_db_path)
        from verification_evidence import ensure_registry

        ensure_registry(rel_conn)
        gate = evaluate_requirement_completion(claim['requirement_id'], claim, rel_conn)
        if gate.get('accepted'):
            upsert_requirement_evidence(
                rel_conn,
                claim['requirement_id'],
                documented_path=(claim.get('evidence') or {}).get('documented_path'),
                installed_path=(claim.get('evidence') or {}).get('installed_path'),
                actually_used_evidence=(claim.get('evidence') or {}).get('actually_used'),
                owner=claim.get('owner', 'local-service'),
                next_unresolved_step='',
            )
        rel_conn.close()
        print(json.dumps(gate, indent=2))
        return 0 if gate.get('accepted') else 1

    if args.command == 'diagnose-text':
        text = Path(args.path).read_text(encoding='utf-8', errors='replace')
        screened, notes = screen_text(text)
        from output_screening import BENIGN_DIAGNOSTIC_MARKER

        print(
            json.dumps(
                export_json_safe({'text': screened, 'notes': notes, 'diagnostic_marker': BENIGN_DIAGNOSTIC_MARKER}),
                indent=2,
            )
        )
        return 0

    if args.command == 'screening-probe':
        from output_screening import BENIGN_DIAGNOSTIC_MARKER

        canary = 'FAKE-canary-token-res0722-emitted'
        if args.surface == 'service-error':
            screened, notes = screen_text(f'{BENIGN_DIAGNOSTIC_MARKER}: probe failed with embedded {canary}')
            print(
                json.dumps(
                    export_json_safe(
                        {
                            'error': screened,
                            'diagnostic_marker': BENIGN_DIAGNOSTIC_MARKER,
                            'notes': notes,
                        }
                    ),
                    indent=2,
                )
            )
            return 1
        if args.surface == 'trace-missing-canary':
            print(
                json.dumps(
                    export_json_safe(
                        {
                            'error': f'unknown trace {canary}',
                            'diagnostic_marker': BENIGN_DIAGNOSTIC_MARKER,
                        }
                    ),
                    indent=2,
                )
            )
            return 1
        raise ServiceError('unknown screening probe surface')

    def _catalog_edit_route():
        from canonical_maintained_edit import (
            apply_patch as canonical_apply,
            preview_patch as canonical_preview,
            read_state as canonical_read,
            reconcile_journals,
        )
        from catalog_controlled_edit import (
            apply_patch as legacy_apply,
            preview_patch as legacy_preview,
            read_state as legacy_read,
        )

        path = args.path
        record_id = getattr(args, 'record_id', None)
        if path.startswith('data/'):
            return 'canonical', canonical_read, canonical_preview, canonical_apply
        return 'legacy', legacy_read, legacy_preview, legacy_apply

    if args.command == 'catalog-edit-reconcile':
        from canonical_maintained_edit import reconcile_journals

        print_screened_json_flat({'reconciled': reconcile_journals()})
        return 0

    if args.command == 'catalog-edit-restore':
        from canonical_maintained_edit import restore_from_backup

        try:
            print_screened_json_flat(
                restore_from_backup(
                    args.path,
                    args.backup,
                    record_id=getattr(args, 'record_id', None),
                )
            )
        except (ValueError, json.JSONDecodeError, OSError) as exc:
            return emit_catalog_edit_error(exc)
        return 0

    if args.command == 'catalog-edit-state':
        try:
            _mode, read_fn, _, _ = _catalog_edit_route()
            if _mode == 'canonical':
                print_screened_json_flat(read_fn(args.path, record_id=getattr(args, 'record_id', None)))
            else:
                print_screened_json_flat(read_fn(args.path))
        except (ValueError, json.JSONDecodeError, OSError) as exc:
            return emit_catalog_edit_error(exc)
        return 0

    if args.command == 'catalog-edit-preview':
        try:
            doc = json.loads(args.document)
            _mode, _, preview_fn, _ = _catalog_edit_route()
            if _mode == 'canonical':
                print_screened_json_flat(
                    preview_fn(
                        args.path,
                        args.expected_sha256,
                        doc,
                        record_id=getattr(args, 'record_id', None),
                        next_revision=getattr(args, 'next_revision', None),
                    )
                )
            else:
                print_screened_json_flat(preview_fn(args.path, args.expected_sha256, doc))
        except (ValueError, json.JSONDecodeError) as exc:
            return emit_catalog_edit_error(exc)
        return 0

    if args.command == 'catalog-edit-apply':
        try:
            doc = json.loads(args.document)
            _mode, _, _, apply_fn = _catalog_edit_route()
            if _mode == 'canonical':
                print_screened_json_flat(
                    apply_fn(
                        args.path,
                        args.expected_sha256,
                        doc,
                        record_id=getattr(args, 'record_id', None),
                        operation_id=args.operation_id,
                        next_revision=getattr(args, 'next_revision', None),
                    )
                )
            else:
                print_screened_json_flat(
                    apply_fn(
                        args.path,
                        args.expected_sha256,
                        doc,
                        operation_id=args.operation_id,
                    )
                )
        except (ValueError, json.JSONDecodeError, OSError) as exc:
            return emit_catalog_edit_error(exc)
        return 0

    if args.command == 'read-source':
        from output_screening import BENIGN_DIAGNOSTIC_MARKER

        try:
            from output_screening import redact_value

            body = read_source(args.source_id)
            redacted, notes = redact_value(body)
            print(
                json.dumps(
                    {
                        'payload': redacted,
                        'screening_notes': sorted(set(notes)),
                        'diagnostic_marker': BENIGN_DIAGNOSTIC_MARKER,
                    },
                    indent=2,
                )
            )
        except ServiceError as exc:
            screened, notes = screen_text(str(exc))
            print(
                json.dumps(
                    {
                        'error': screened,
                        'screening_notes': sorted(set(notes)),
                        'diagnostic_marker': BENIGN_DIAGNOSTIC_MARKER,
                    },
                    indent=2,
                )
            )
            return 1
        return 0

    engine = Engine(str(db_path))
    conn = engine.db
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=8000')
    ensure_presentation(conn)
    ensure_watch(conn)
    ensure_trace_schema(conn)
    try:
        if args.command == 'init':
            conn.commit()
            print(json.dumps({'initialized': True, 'db': str(db_path)}, indent=2))
        elif args.command == 'sync-observe':
            print(json.dumps(observe_all(conn), indent=2))
        elif args.command == 'sync-status':
            print(json.dumps(get_sync_status(conn), indent=2))
        elif args.command == 'workflow-templates':
            templates = []
            for name in ('investigate', 'build', 'repair'):
                path = ROOT / 'workflows' / f'{name}.json'
                templates.append({'name': name, 'path': str(path.relative_to(ROOT)), 'document': json.loads(path.read_text())})
            print(json.dumps({'templates': templates}, indent=2))
        elif args.command == 'trace-import':
            result = import_trace_document(conn, Path(args.path).resolve())
            print(json.dumps(result, indent=2))
        elif args.command == 'trace-list':
            print(json.dumps(export_trace_list_safe(conn), indent=2))
        elif args.command == 'trace-get':
            payload = export_trace_safe(conn, args.trace_id)
            if payload.get('error') == 'unknown trace':
                from output_screening import BENIGN_DIAGNOSTIC_MARKER, redact_value

                redacted, notes = redact_value(payload)
                if isinstance(redacted, dict):
                    redacted['diagnostic_marker'] = BENIGN_DIAGNOSTIC_MARKER
                    redacted['screening_notes'] = sorted(set(notes))
                print(json.dumps(redacted, indent=2))
                return 1
            print_screened_json_flat(payload)
        elif args.command == 'apply':
            raw = Path(args.request).read_text() if args.request else sys.stdin.read()
            request = json.loads(raw)
            if args.command == 'apply' and not args.reliability_db:
                rel_db_path = db_path
            from verification_evidence import ensure_registry

            from reliability_store import prepare_connection as prepare_handoff_connection
            from verification_evidence import prepare_registry

            if rel_db_path.resolve() == db_path.resolve():
                prepare_handoff_connection(conn)
                prepare_registry(conn)
                rel_conn = conn
            else:
                raise ServiceError('apply requires unified workflow and reliability database path')
            try:
                if request.get('action') == 'handoff_transfer':
                    result = transfer_handoff_request(
                        rel_conn,
                        engine,
                        request,
                        wf_db_path=db_path,
                        rel_db_path=rel_db_path,
                    )
                else:
                    result = apply_workflow_request(
                        engine,
                        rel_conn,
                        request,
                        wf_db_path=db_path,
                        rel_db_path=rel_db_path,
                    )
            finally:
                if rel_conn is not conn:
                    rel_conn.close()
            print_screened_json_flat(result)
        elif args.command == 'recover-enhanced':
            rel_conn = reliability_connect(rel_db_path)
            try:
                packet = merge_recover_packet(engine.recover(args.job_id), rel_conn, args.presented_note)
            finally:
                rel_conn.close()
            print(json.dumps(export_recover_packet_safe(packet), indent=2))
        elif args.command == 'recover':
            print(json.dumps(export_recover_packet_safe(engine.recover(args.job_id)), indent=2))
        elif args.command == 'events':
            print(json.dumps(export_events_safe(conn, args.job_id), indent=2))
        elif args.command == 'list-jobs':
            print(json.dumps(export_list_jobs_safe(conn), indent=2))
        elif args.command == 'presentation-get':
            row = presentation_get(conn, args.scope, args.key)
            print_screened_json_flat(row if row else {'scope': args.scope, 'key': args.key, 'value': None})
        elif args.command == 'presentation-set':
            value = json.loads(args.value)
            print_screened_json_flat(presentation_set(conn, args.scope, args.key, value))
        else:
            raise ServiceError('unknown command')
    except (ContractError, ServiceError, json.JSONDecodeError, ValueError) as exc:
        screened, notes = screen_text(str(exc))
        print(json.dumps(export_json_safe({'error': screened, 'notes': notes}), indent=2))
        return 1
    finally:
        engine.close()
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        screened, notes = screen_text(str(exc))
        print(json.dumps(export_json_safe({'error': screened, 'notes': notes}), indent=2))
        raise SystemExit(1) from exc
