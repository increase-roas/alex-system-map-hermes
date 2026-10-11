"""Catalog export/edit screening via isolated fixtures and real CLI paths."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENIGN = 'LOCAL-SCREENING-OK'
CANARY = 'FAKE-canary-token-res0722-emitted'
EDIT_REL = 'work/reliability/synthetic-sync-marker.json'


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_minimal_catalog_fixture(fixture_root: Path, *, inject_canary: bool) -> None:
    data = fixture_root / 'data'
    views = fixture_root / 'views'
    data.mkdir(parents=True, exist_ok=True)
    views.mkdir(parents=True, exist_ok=True)
    probe_note = f'catalog probe {CANARY}' if inject_canary else 'catalog probe clean'
    (data / 'components.json').write_text(
        json.dumps({'records': [{'id': 'catalog-probe-component', 'label': probe_note}]}, indent=2) + '\n'
    )
    for name in (
        'relationships',
        'sources',
        'evidence',
        'issues',
        'coverage',
        'source-records',
        'layers',
        'table-index',
    ):
        (data / f'{name}.json').write_text(json.dumps({'records': []}, indent=2) + '\n')
    (views / 'overview.json').write_text(
        json.dumps({'memberships': [], 'membership_is_runtime_relationship': False}, indent=2) + '\n'
    )


def _run_cli(args: list[str], *, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    merged = {**os.environ, **(env or {})}
    return subprocess.run(
        [sys.executable, str(ROOT / 'tools/local_service.py'), *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=merged,
    )


def _parse_body(proc: subprocess.CompletedProcess[str]) -> dict:
    try:
        body = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    return body


def _handler_result(
    proc: subprocess.CompletedProcess[str],
    *,
    handler: str,
    expect_exit: int,
) -> dict:
    body = _parse_body(proc)
    combined = f'{proc.stdout}{proc.stderr}'
    parser_error = proc.returncode == 2 and isinstance(body.get('error'), str)
    return {
        'handler': handler,
        'exit': proc.returncode,
        'handler_reached': proc.returncode != 2,
        'parser_error': parser_error,
        'has_diagnostic_marker': body.get('diagnostic_marker') == BENIGN,
        'canary_removed': CANARY not in combined,
        'handler_error': proc.returncode != 0 and proc.returncode != 2,
        'error': body.get('error'),
        'screening_notes': body.get('screening_notes'),
    }


def _ensure_isolated_db(db_suffix: str) -> Path:
    db = ROOT / 'app' / '.data' / f'catalog-edit-{db_suffix}.sqlite'
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()
    init = _run_cli(['--db', str(db), 'init'])
    if init.returncode != 0:
        raise RuntimeError(f'catalog probe db init failed: {init.stderr}')
    return db


def test_catalog_export_and_injected_canary(db_suffix: str = 'catalog-screen-probe') -> dict:
    fixture_root = ROOT / 'app' / '.data' / f'catalog-fixture-{db_suffix}'
    if fixture_root.exists():
        shutil.rmtree(fixture_root)
    _write_minimal_catalog_fixture(fixture_root, inject_canary=True)
    isolated_db = _ensure_isolated_db(db_suffix)

    export_proc = _run_cli(
        ['--db', str(isolated_db), 'catalog-export'],
        env={'CATALOG_FIXTURE_ROOT': str(fixture_root)},
    )
    export_body = _parse_body(export_proc)
    export_block = _handler_result(export_proc, handler='catalog-export', expect_exit=0)
    export_block['completeness'] = export_body.get('completeness')
    runtime_ok = (
        export_block['exit'] == 0
        and export_block['handler_reached'] is True
        and export_block['has_diagnostic_marker'] is True
        and export_block['canary_removed'] is True
        and isinstance(export_block.get('completeness'), dict)
    )

    edit_path = ROOT / EDIT_REL
    backup = edit_path.read_bytes()
    backup_sha = _sha256_bytes(backup)
    base_doc = json.loads(backup)
    on_disk_doc = {**base_doc, 'note': f"{base_doc.get('note', '')} stored-{CANARY}"}
    edit_path.write_text(json.dumps(on_disk_doc, indent=2) + '\n')
    fixture_restored = False
    state_block = preview_block = apply_block = stale_block = canary_block = {}
    try:
        state_proc = _run_cli(['--db', str(isolated_db), 'catalog-edit-state', EDIT_REL])
        state_body = _parse_body(state_proc)
        state_block = _handler_result(state_proc, handler='catalog-edit-state', expect_exit=0)
        state_block['path'] = state_body.get('path')
        state_block['document'] = state_body.get('document')
        state_block['revision'] = state_body.get('revision')

        current_sha = _sha256_bytes(edit_path.read_bytes())
        preview_doc = {
            **on_disk_doc,
            'revision': int(on_disk_doc.get('revision', 0)) + 1,
            'note': 'preview request clean note for controlled edit probe',
        }
        preview_proc = _run_cli(
            [
                '--db',
                str(isolated_db),
                'catalog-edit-preview',
                EDIT_REL,
                current_sha,
                json.dumps(preview_doc),
            ]
        )
        preview_body = _parse_body(preview_proc)
        preview_block = _handler_result(preview_proc, handler='catalog-edit-preview', expect_exit=0)
        preview_block['preview'] = preview_body.get('preview') or preview_body
        preview_block['valid'] = preview_body.get('valid') is True
        preview_block['error'] = preview_body.get('error')

        apply_proc = _run_cli(
            [
                '--db',
                str(isolated_db),
                'catalog-edit-apply',
                EDIT_REL,
                current_sha,
                json.dumps(preview_doc),
            ]
        )
        apply_body = _parse_body(apply_proc)
        apply_block = _handler_result(apply_proc, handler='catalog-edit-apply', expect_exit=0)
        apply_block['applied_revision'] = apply_body.get('revision')
        after_apply_sha = _sha256_bytes(edit_path.read_bytes())
        edit_path.write_bytes(backup)
        fixture_restored = _sha256_bytes(edit_path.read_bytes()) == backup_sha
        apply_block['restored'] = fixture_restored
        apply_block['sha256_before'] = backup_sha
        apply_block['sha256_after_apply'] = after_apply_sha
        apply_block['sha256_restored'] = _sha256_bytes(edit_path.read_bytes())

        stale_proc = _run_cli(
            [
                '--db',
                str(isolated_db),
                'catalog-edit-preview',
                EDIT_REL,
                '0' * 64,
                json.dumps(preview_doc),
            ]
        )
        stale_block = _handler_result(stale_proc, handler='catalog-edit-preview', expect_exit=1)
        stale_block['error_kind'] = 'edit_stale_revision_error'
        stale_block['error'] = _parse_body(stale_proc).get('error')

        canary_err_proc = _run_cli(
            [
                '--db',
                str(isolated_db),
                'catalog-edit-preview',
                EDIT_REL,
                _sha256_bytes(edit_path.read_bytes()),
                json.dumps({**base_doc, 'revision': int(base_doc.get('revision', 0)) + 1, 'note': f'bad {CANARY}'}),
            ]
        )
        canary_block = _handler_result(canary_err_proc, handler='catalog-edit-preview', expect_exit=1)
        canary_block['error_kind'] = 'edit_canary_input_error'
        canary_block['request_had_canary'] = True
        canary_block['error'] = _parse_body(canary_err_proc).get('error')
    finally:
        if not fixture_restored:
            edit_path.write_bytes(backup)
            fixture_restored = _sha256_bytes(edit_path.read_bytes()) == backup_sha

    return {
        'exit': export_proc.returncode,
        'has_diagnostic_marker': export_block['has_diagnostic_marker'],
        'canary_removed_runtime': export_block['canary_removed'],
        'runtime_path_ok': runtime_ok,
        'export': export_block,
        'edit_state': state_block,
        'edit_preview': preview_block,
        'edit_apply': apply_block,
        'edit_stale_revision_error': stale_block,
        'edit_canary_input_error': canary_block,
        'edit_state_canary_removed': state_block['canary_removed'] and state_block['exit'] == 0,
        'edit_preview_canary_removed': preview_block['canary_removed'] and preview_block['exit'] == 0,
        'edit_error_boundary_canary_removed': canary_block['canary_removed'] and canary_block['exit'] == 1,
        'fixture_root': str(fixture_root.relative_to(ROOT)),
        'fixture_root_sha256': _sha256_bytes((fixture_root / 'data' / 'components.json').read_bytes()),
        'isolated_db': str(isolated_db.relative_to(ROOT)),
        'isolated_db_sha256_before': _sha256_bytes(b''),
        'edit_file_sha256_before': backup_sha,
        'fixture_restored': fixture_restored,
    }
