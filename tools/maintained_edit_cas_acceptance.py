#!/usr/bin/env python3
"""Delivery maintained-edit-cas-20261010-0844."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
import urllib.parse
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
RUN_RECEIPTS = REPORTS / 'run-receipts'
MANIFEST = REPORTS / 'receipt-hash-manifest.jsonl'
DELIVERY = 'maintained-edit-cas-20261010-0844'
OWNER_CHAT = '4f32e74a-58e3-4abb-ba6f-fb151ba80cd7'
HISTORY = REPORTS / 'workflow-core-run-history.jsonl'
STAGING = 'work/maintained/staging-catalog-record.json'
FIXTURE = 'work/reliability/editable-fixture.json'
ISOLATED_DB = ROOT / 'app' / '.data' / DELIVERY / 'local.sqlite'

SOURCE_MODULES = (
    'tools/catalog_controlled_edit.py',
    'tools/maintained_derived_views.py',
    'tools/maintained_edit_cas_acceptance.py',
    'tools/browser_maintained_edit_cas.mjs',
    'app/src/app/api/catalog/edit/route.ts',
    'app/src/app/api/catalog/edit/state/route.ts',
    'app/src/app/explorer/maintained-edit-panel.tsx',
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_identities() -> dict[str, str]:
    out = {p: sha256_file(ROOT / p) for p in SOURCE_MODULES if (ROOT / p).is_file()}
    build_id = ROOT / 'app' / '.next' / 'BUILD_ID'
    if build_id.is_file():
        out['app/.next/BUILD_ID'] = sha256_file(build_id)
    return out


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    db = ISOLATED_DB
    db.parent.mkdir(parents=True, exist_ok=True)
    if not db.exists():
        subprocess.run(
            [sys.executable, str(ROOT / 'tools/local_service.py'), '--db', str(db), 'init'],
            check=True,
            cwd=str(ROOT),
        )
    return subprocess.run(
        [sys.executable, str(ROOT / 'tools/local_service.py'), '--db', str(db), *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )


def reset_staging() -> tuple[bytes, dict]:
    path = ROOT / STAGING
    backup = path.read_bytes()
    doc = json.loads(backup)
    doc = {**doc, 'revision': 0, 'label': 'SYNTHETIC staging maintained catalog record', 'note': 'reset for CAS test'}
    path.write_text(json.dumps(doc, indent=2) + '\n')
    return backup, doc


def restore_staging(backup: bytes) -> None:
    (ROOT / STAGING).write_bytes(backup)


def test_concurrent_stale_writers() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from catalog_controlled_edit import apply_patch, read_state

    backup, base = reset_staging()
    try:
        state = read_state(STAGING)
        doc_a = {**base, 'revision': 1, 'note': 'writer A', 'updated_at': utc_now()}
        doc_b = {**base, 'revision': 1, 'note': 'writer B', 'updated_at': utc_now()}
        sha = state['sha256']
        results: list[dict] = []

        run_tag = uuid.uuid4().hex[:10]

        def worker(label: str, doc: dict, op: str) -> None:
            try:
                apply_patch(STAGING, sha, doc, operation_id=op)
                results.append({'label': label, 'ok': True})
            except ValueError as exc:
                results.append({'label': label, 'ok': False, 'error': str(exc)})

        with ThreadPoolExecutor(max_workers=2) as pool:
            fa = pool.submit(worker, 'A', doc_a, f'op-a-{run_tag}')
            fb = pool.submit(worker, 'B', doc_b, f'op-b-{run_tag}')
            fa.result()
            fb.result()
        winners = [r for r in results if r.get('ok')]
        losers = [r for r in results if not r.get('ok')]
        final = read_state(STAGING)
        return {
            'committed_count': len(winners),
            'conflict_count': len(losers),
            'one_commit_one_conflict': len(winners) == 1 and len(losers) == 1,
            'final_revision': final['revision'],
            'results': results,
        }
    finally:
        restore_staging(backup)


def test_idempotent_operation_id() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from catalog_controlled_edit import apply_patch, read_state

    backup, base = reset_staging()
    try:
        state = read_state(STAGING)
        doc = {**base, 'revision': 1, 'note': 'idempotent op', 'updated_at': utc_now()}
        op = f'idempotent-{uuid.uuid4().hex[:12]}'
        first = apply_patch(STAGING, state['sha256'], doc, operation_id=op)
        second = apply_patch(STAGING, 'deadbeef', doc, operation_id=op)
        return {
            'first_after_sha': first.get('after_sha256'),
            'second_after_sha': second.get('after_sha256'),
            'idempotent_match': first.get('after_sha256') == second.get('after_sha256'),
        }
    finally:
        restore_staging(backup)


def test_api_preview_apply_derived() -> dict:
    backup, base = reset_staging()
    try:
        state_proc = _run_cli(['catalog-edit-state', STAGING])
        state = json.loads(state_proc.stdout)
        next_doc = {**base, 'revision': 1, 'note': 'API CAS path', 'updated_at': utc_now()}
        preview = _run_cli(
            ['catalog-edit-preview', STAGING, state['sha256'], json.dumps(next_doc)],
        )
        preview_body = json.loads(preview.stdout)
        apply = _run_cli(
            [
                'catalog-edit-apply',
                STAGING,
                state['sha256'],
                json.dumps(next_doc),
                '--operation-id',
                'api-0844-op',
            ]
        )
        apply_body = json.loads(apply.stdout)
        meta_path = ROOT / 'work/maintained/derived/staging-catalog-record.meta.json'
        meta = json.loads(meta_path.read_text()) if meta_path.is_file() else {}
        derived = apply_body.get('derived') if isinstance(apply_body.get('derived'), dict) else {}
        derived_sha = derived.get('source_sha256') or meta.get('source_sha256')
        return {
            'preview_exit': preview.returncode,
            'preview_has_diff': isinstance(preview_body.get('diff'), list) and len(preview_body['diff']) > 0,
            'apply_exit': apply.returncode,
            'after_sha256': apply_body.get('after_sha256'),
            'derived_revision': meta.get('revision'),
            'lineage_ok': meta.get('revision') == 1 and derived_sha == apply_body.get('after_sha256'),
        }
    finally:
        restore_staging(backup)


def test_symlink_escape_rejected() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from catalog_controlled_edit import read_state

    path = ROOT / STAGING
    backup = path.read_bytes()
    outside = Path('/tmp') / f'{DELIVERY}-outside-target.json'
    outside.write_text('{"outside": true}\n')
    try:
        path.unlink(missing_ok=True)
        path.symlink_to(outside)
        rejected = False
        err = None
        try:
            read_state(STAGING)
        except ValueError as exc:
            rejected = True
            err = str(exc)
        return {'symlink_escape_rejected': rejected, 'error': err}
    finally:
        path.unlink(missing_ok=True)
        path.write_bytes(backup)
        outside.unlink(missing_ok=True)


def test_backup_restore_lkg() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from catalog_controlled_edit import apply_patch, read_state, restore_from_backup

    backup, base = reset_staging()
    try:
        state = read_state(STAGING)
        doc = {**base, 'revision': 1, 'note': 'backup proof', 'updated_at': utc_now()}
        applied = apply_patch(STAGING, state['sha256'], doc, operation_id='backup-0844')
        before_sha = applied['before_sha256']
        after_sha = applied['after_sha256']
        (ROOT / STAGING).write_text('{"corrupted": true}\n')
        restored = restore_from_backup(STAGING, applied['backup'])
        return {
            'backup_path_ok': (ROOT / applied['backup']).is_file(),
            'restored_sha256': restored['sha256'],
            'backup_restores_pre_apply_snapshot': restored['sha256'] == before_sha,
            'committed_after_sha256': after_sha,
            'before_sha256': before_sha,
        }
    finally:
        restore_staging(backup)


def test_negative_malformed() -> dict:
    backup, base = reset_staging()
    try:
        state = json.loads(_run_cli(['catalog-edit-state', STAGING]).stdout)
        bad_rev = {**base, 'revision': 99}
        bad = _run_cli(['catalog-edit-preview', STAGING, state['sha256'], json.dumps(bad_rev)])
        canary = {**base, 'revision': 1, 'note': 'FAKE-canary-token-res0722-emitted'}
        canary_proc = _run_cli(['catalog-edit-preview', STAGING, state['sha256'], json.dumps(canary)])
        return {
            'bad_revision_rejected': bad.returncode != 0,
            'canary_rejected': canary_proc.returncode != 0,
        }
    finally:
        restore_staging(backup)


def test_served_restart_api_persistence() -> dict:
    import urllib.error
    import urllib.request

    port = '3221'
    base = f'http://127.0.0.1:{port}'
    isolated = ROOT / 'app' / '.data' / f'{DELIVERY}-restart'
    db = isolated / 'local.sqlite'
    isolated.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        'PORT': port,
        'LOCAL_DATA_DIR': str(isolated),
        'WORKFLOW_SQLITE_PATH': str(db),
        'FOUNDATION_ROOT': str(ROOT),
    }
    backup, base_doc = reset_staging()
    server = None
    try:
        if not db.exists():
            subprocess.run(
                [sys.executable, str(ROOT / 'tools/local_service.py'), '--db', str(db), 'init'],
                check=True,
                cwd=str(ROOT),
            )
        server = subprocess.Popen(
            ['npx', 'next', 'start', '-H', '127.0.0.1', '-p', port],
            cwd=str(ROOT / 'app'),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        time.sleep(6)
        token = None
        pid_before = None
        health = None
        for _ in range(120):
            if server.poll() is not None:
                err = (server.stderr.read() if server.stderr else b'').decode()[-2000:]
                return {'overall': 'failed', 'error': 'server exited early', 'stderr_tail': err}
            try:
                with urllib.request.urlopen(f'{base}/api/health', timeout=3) as resp:
                    health = json.loads(resp.read().decode())
                    token = health.get('token')
                    pid_before = (health.get('process') or {}).get('pid')
                    break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.5)
        if not token:
            err = (server.stderr.read() if server.stderr else b'').decode()[-2000:]
            return {'overall': 'failed', 'error': 'health timeout', 'stderr_tail': err}
        state = json.loads(
            urllib.request.urlopen(
                f'{base}/api/catalog/edit/state?path={urllib.parse.quote(STAGING)}',
                timeout=30,
            ).read()
        )
        next_doc = {
            **base_doc,
            'revision': int(state.get('revision', 0)) + 1,
            'note': 'restart persistence API proof',
            'updated_at': utc_now(),
        }
        req = urllib.request.Request(
            f'{base}/api/catalog/edit',
            data=json.dumps(
                {
                    'path': STAGING,
                    'expected_sha256': state['sha256'],
                    'document': next_doc,
                    'operation_id': f'restart-{uuid.uuid4().hex[:10]}',
                }
            ).encode(),
            headers={'Content-Type': 'application/json', 'X-Local-Token': token},
            method='POST',
        )
        applied = json.loads(urllib.request.urlopen(req, timeout=120).read())
        server.terminate()
        try:
            server.wait(timeout=20)
        except subprocess.TimeoutExpired:
            server.kill()
        server = subprocess.Popen(
            ['npx', 'next', 'start', '-H', '127.0.0.1', '-p', port],
            cwd=str(ROOT / 'app'),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        time.sleep(6)
        pid_after = None
        for _ in range(120):
            if server.poll() is not None:
                break
            try:
                with urllib.request.urlopen(f'{base}/api/health', timeout=3) as resp:
                    health = json.loads(resp.read().decode())
                    pid_after = (health.get('process') or {}).get('pid')
                    break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.5)
        state2 = json.loads(
            urllib.request.urlopen(
                f'{base}/api/catalog/edit/state?path={urllib.parse.quote(STAGING)}',
                timeout=30,
            ).read()
        )
        meta_path = ROOT / 'work/maintained/derived/staging-catalog-record.meta.json'
        meta = json.loads(meta_path.read_text()) if meta_path.is_file() else {}
        return {
            'pid_before': pid_before,
            'pid_after_restart': pid_after,
            'restart_pid_changed': pid_before != pid_after,
            'revision_after_restart': state2.get('revision'),
            'sha_after_restart': state2.get('sha256'),
            'matches_apply': state2.get('sha256') == applied.get('after_sha256'),
            'derived_revision': meta.get('revision'),
            'persisted_after_restart': state2.get('revision') == next_doc['revision'],
        }
    finally:
        restore_staging(backup)
        derived = ROOT / 'work/maintained/derived'
        for name in ('staging-catalog-record.md', 'staging-catalog-record.meta.json'):
            p = derived / name
            if p.is_file():
                p.unlink()
        if server:
            server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()


def test_browser_ui(run_suffix: str) -> dict:
    proc = subprocess.run(
        ['node', str(ROOT / 'tools/browser_maintained_edit_cas.mjs')],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=600,
        env={
            **os.environ,
            'BROWSER_TEST_PORT': '3220',
            'BROWSER_CAPTURE_DELIVERY': DELIVERY,
            'BROWSER_RUN_CAPTURE_SUFFIX': run_suffix,
        },
    )
    try:
        parsed = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        parsed = {'overall': 'failed', 'stdout_tail': proc.stdout[-1500:]}
    parsed['exit'] = proc.returncode
    return parsed


def test_strict_types_regression() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from acceptance_summarize_strict import self_check_two_types_regression

    pointer = json.loads((REPORTS / 'typed-controls-real-edit-receipt.json').read_text())
    receipt = json.loads((ROOT / pointer['immutable_receipt_path']).read_text())
    from acceptance_summarize_strict import load_saved_positive_baseline_from_receipt

    baseline = load_saved_positive_baseline_from_receipt(ROOT / pointer['immutable_receipt_path'])
    return self_check_two_types_regression(baseline)


def summarize_cases(cases: dict) -> tuple[bool, list[str]]:
    failures: list[str] = []
    conc = cases.get('concurrent') or {}
    if not conc.get('one_commit_one_conflict'):
        failures.append('concurrent_cas')
    idem = cases.get('idempotent') or {}
    if not idem.get('idempotent_match'):
        failures.append('idempotent_operation')
    api = cases.get('api_derived') or {}
    if api.get('apply_exit') != 0 or not api.get('lineage_ok'):
        failures.append('api_derived')
    sym = cases.get('symlink_escape') or {}
    if not sym.get('symlink_escape_rejected'):
        failures.append('symlink_escape')
    bak = cases.get('backup_restore_lkg') or {}
    if not bak.get('backup_restores_pre_apply_snapshot') or not bak.get('backup_path_ok'):
        failures.append('backup_restore_lkg')
    neg = cases.get('negative') or {}
    if not neg.get('bad_revision_rejected') or not neg.get('canary_rejected'):
        failures.append('negative_paths')
    restart = cases.get('served_restart') or {}
    if not restart.get('persisted_after_restart') or not restart.get('matches_apply'):
        failures.append('served_restart')
    browser = cases.get('browser') or {}
    if browser.get('overall') != 'passed' or browser.get('exit') != 0:
        failures.append('browser_ui')
    reg = cases.get('strict_types_regression') or {}
    if not reg.get('saved_baseline_core_pass') or not reg.get('each_declared_flip_fails'):
        failures.append('strict_types_regression')
    return not failures, failures


def main() -> int:
    run_id = str(uuid.uuid4())
    run_suffix = run_id.replace('-', '')[:12]
    cases = {
        'concurrent': test_concurrent_stale_writers(),
        'idempotent': test_idempotent_operation_id(),
        'api_derived': test_api_preview_apply_derived(),
        'symlink_escape': test_symlink_escape_rejected(),
        'backup_restore_lkg': test_backup_restore_lkg(),
        'negative': test_negative_malformed(),
        'browser': test_browser_ui(run_suffix),
        'served_restart': test_served_restart_api_persistence(),
        'strict_types_regression': test_strict_types_regression(),
        'real_sdk_trace_input': 'BLOCKED',
        'drive_publication': 'local-only; not claimed',
    }
    ok, failures = summarize_cases(cases)
    receipt_body = {
        'delivery_id': DELIVERY,
        'run_id': run_id,
        'at': utc_now(),
        'owner_chat': OWNER_CHAT,
        'source_identity': source_identities(),
        'cases': cases,
        'failures': failures,
        'overall': 'passed' if ok else 'failed',
        'independent_verification': 'not_claimed',
        'isolated_db': str(ISOLATED_DB.relative_to(ROOT)),
        'isolated_db_sha256': sha256_file(ISOLATED_DB) if ISOLATED_DB.is_file() else None,
    }
    if not ok:
        fail_path = REPORTS / 'workflow-core-failures' / f'{DELIVERY}-{run_id[:8]}.json'
        fail_path.parent.mkdir(parents=True, exist_ok=True)
        fail_path.write_text(json.dumps(cases, indent=2) + '\n')
        receipt_body['failure_artifacts_preserved'] = [
            {'path': str(fail_path.relative_to(ROOT)), 'sha256': sha256_file(fail_path)}
        ]

    from receipt_immutable import append_manifest, write_final_receipt_once

    immutable_rel = str((RUN_RECEIPTS / f'{DELIVERY}-{run_id}.json').relative_to(ROOT))
    _, digest = write_final_receipt_once(RUN_RECEIPTS / f'{DELIVERY}-{run_id}.json', receipt_body)
    pointer = {
        'delivery_id': DELIVERY,
        'run_id': run_id,
        'immutable_receipt_path': immutable_rel,
        'content_sha256': digest,
    }
    append_manifest(MANIFEST, pointer)
    (REPORTS / 'maintained-edit-cas-receipt.json').write_text(json.dumps(pointer, indent=2) + '\n')
    with HISTORY.open('a') as handle:
        handle.write(
            json.dumps(
                {
                    'delivery_id': DELIVERY,
                    'run_id': run_id,
                    'at': receipt_body['at'],
                    'overall': receipt_body['overall'],
                    'immutable_receipt': immutable_rel,
                    'content_sha256': digest,
                }
            )
            + '\n'
        )
    print(
        json.dumps(
            {
                'overall': receipt_body['overall'],
                'delivery_id': DELIVERY,
                'run_id': run_id,
                'failures': failures,
                'immutable_content_sha256': digest,
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
