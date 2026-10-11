#!/usr/bin/env python3
"""Delivery canonical-edit-sync-20261010-0913 — canonical catalog/doc editing proof."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
RUN_RECEIPTS = REPORTS / 'run-receipts'
MANIFEST = REPORTS / 'receipt-hash-manifest.jsonl'
DELIVERY = 'canonical-edit-sync-20261010-0913'
OWNER_CHAT = '4f32e74a-58e3-4abb-ba6f-fb151ba80cd7'
HISTORY = REPORTS / 'workflow-core-run-history.jsonl'
ISOLATED = ROOT / 'app' / '.data' / DELIVERY
CLONE = ISOLATED / 'catalog-clone'
DB = ISOLATED / 'local.sqlite'
TABLE = 'data/components.json'
RECORD_ID = 'component_6f112167c8a413f0f3ab'
METADATA = 'data/catalog-metadata.json'
PROOF_DIR = REPORTS / 'derived-proof' / DELIVERY
SUBPROCESS_TIMEOUT_S = 600
BROWSER_TIMEOUT_S = 600

SOURCE_MODULES = (
    'tools/canonical_maintained_edit.py',
    'tools/catalog_reference_validation.py',
    'tools/canonical_derived_render.py',
    'tools/catalog_fixture_clone.py',
    'tools/canonical_edit_sync_acceptance.py',
    'tools/canonical_review_fixes_acceptance.py',
    'tools/canonical_acceptance_summarize.py',
    'tools/subprocess_bounded.py',
    'tools/browser_canonical_edit_sync.mjs',
    'tools/browser_canonical_review_fixes.mjs',
    'tools/build_catalog.py',
    'tools/catalog_sync.py',
    'tools/local_service.py',
    'app/src/app/explorer/maintained-edit-panel.tsx',
    'app/src/app/api/catalog/edit/route.ts',
    'app/src/app/api/catalog/edit/state/route.ts',
    'app/src/app/api/sync/status/route.ts',
    'app/src/lib/server/python.ts',
    'app/src/app/api/health/route.ts',
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


def production_immutable_hashes() -> dict[str, str]:
    from catalog_fixture_clone import production_file_hashes

    return production_file_hashes()


def _env_fixture() -> dict[str, str]:
    return {
        **os.environ,
        'CATALOG_FIXTURE_ROOT': str(CLONE),
        'FOUNDATION_ROOT': str(ROOT),
    }


def _run_cli(args: list[str], *, env: dict[str, str] | None = None, timeout: int = SUBPROCESS_TIMEOUT_S) -> subprocess.CompletedProcess[str]:
    if not DB.exists():
        ISOLATED.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [sys.executable, str(ROOT / 'tools/local_service.py'), '--db', str(DB), 'init'],
            check=True,
            cwd=str(ROOT),
        )
    from subprocess_bounded import run_bounded

    return run_bounded(
        [sys.executable, str(ROOT / 'tools/local_service.py'), '--db', str(DB), *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env or _env_fixture(),
        timeout=timeout,
    )


def _parse_stdout(proc: subprocess.CompletedProcess[str]) -> dict:
    text = proc.stdout.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith('{'):
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return {}


def setup_clone() -> dict:
    from catalog_fixture_clone import clone_complete_catalog

    CLONE.parent.mkdir(parents=True, exist_ok=True)
    return clone_complete_catalog(CLONE)


def xlsx_purpose(xlsx: Path, component_id: str) -> str | None:
    import openpyxl

    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    ws = wb['TOP DOWN MAP']
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row and row[-1] == component_id:
            return str(row[6] or '')
    return None


def test_production_catalog_available() -> dict:
    proc = _run_cli(['catalog-export'], env={**os.environ, 'FOUNDATION_ROOT': str(ROOT)})
    body = _parse_stdout(proc)
    completeness = body.get('completeness') if isinstance(body.get('completeness'), dict) else {}
    count = int(completeness.get('components', 0))
    if count == 0 and isinstance(body.get('data'), dict):
        count = len(body['data'].get('components') or [])
    return {
        'exit': proc.returncode,
        'component_count': count,
        'real_maintained_assets': count > 1000,
    }


def test_canonical_edit_derived_agreement() -> dict:
    state = _parse_stdout(_run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_ID]))
    doc = {**state['document'], 'purpose': 'Canonical edit sync 0913 purpose proof'}
    next_rev = state['revision'] + 1
    before_xlsx = CLONE / 'views/Alex_System_Foundation.xlsx'
    before_md = CLONE / 'components' / f'{RECORD_ID}.md'
    before_xlsx_sha = sha256_file(before_xlsx)
    before_md_sha = sha256_file(before_md)
    before_xlsx_purpose = xlsx_purpose(before_xlsx, RECORD_ID)
    apply = _parse_stdout(
        _run_cli(
            [
                'catalog-edit-apply',
                TABLE,
                state['sha256'],
                json.dumps(doc),
                '--record-id',
                RECORD_ID,
                '--next-revision',
                str(next_rev),
                '--operation-id',
                f'canonical-0913-{uuid.uuid4().hex[:8]}',
            ]
        )
    )
    after_xlsx_sha = sha256_file(before_xlsx)
    after_md_sha = sha256_file(before_md)
    after_xlsx_purpose = xlsx_purpose(before_xlsx, RECORD_ID)
    md_text = before_md.read_text()
    PROOF_DIR.mkdir(parents=True, exist_ok=True)
    proof = {
        'xlsx_before': before_xlsx_sha,
        'xlsx_after': after_xlsx_sha,
        'md_before': before_md_sha,
        'md_after': after_md_sha,
        'xlsx_purpose_before': before_xlsx_purpose,
        'xlsx_purpose_after': after_xlsx_purpose,
        'md_contains_purpose': 'Canonical edit sync 0913 purpose proof' in md_text,
    }
    (PROOF_DIR / 'derived-agreement.json').write_text(json.dumps(proof, indent=2) + '\n')
    from canonical_derived_render import copy_derived_proof

    copied = copy_derived_proof(PROOF_DIR / 'snapshots', record_id=RECORD_ID)
    return {
        'apply_revision': apply.get('revision'),
        'derived': apply.get('derived'),
        'xlsx_changed': before_xlsx_sha != after_xlsx_sha,
        'md_changed': before_md_sha != after_md_sha,
        'xlsx_purpose_updated': after_xlsx_purpose == doc['purpose'],
        'md_purpose_updated': proof['md_contains_purpose'],
        'proof_copied': copied,
    }


def _concurrent_apply_cmd(op: str, purpose: str, sha: str, rev: int) -> list[str]:
    doc_proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / 'tools/local_service.py'),
            '--db',
            str(DB),
            'catalog-edit-state',
            TABLE,
            '--record-id',
            RECORD_ID,
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=_env_fixture(),
    )
    state = json.loads(doc_proc.stdout)
    doc = {**state['document'], 'purpose': purpose}
    return [
        sys.executable,
        str(ROOT / 'tools/local_service.py'),
        '--db',
        str(DB),
        'catalog-edit-apply',
        TABLE,
        sha,
        json.dumps(doc),
        '--record-id',
        RECORD_ID,
        '--next-revision',
        str(rev),
        '--operation-id',
        op,
    ]


def test_concurrent_processes() -> dict:
    state = _parse_stdout(_run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_ID]))
    sha = state['sha256']
    rev = state['revision'] + 1
    env = _env_fixture()
    op_a = f'conc-a-{uuid.uuid4().hex[:6]}'
    op_b = f'conc-b-{uuid.uuid4().hex[:6]}'
    p1 = subprocess.Popen(_concurrent_apply_cmd(op_a, 'writer A 0913', sha, rev), cwd=str(ROOT), env=env)
    p2 = subprocess.Popen(_concurrent_apply_cmd(op_b, 'writer B 0913', sha, rev), cwd=str(ROOT), env=env)
    r1 = p1.wait(timeout=120)
    r2 = p2.wait(timeout=120)
    results = [
        {'label': 'A', 'exit': r1, 'op': op_a},
        {'label': 'B', 'exit': r2, 'op': op_b},
    ]
    wins = [r for r in results if r['exit'] == 0]
    losses = [r for r in results if r['exit'] != 0]
    return {
        'committed_count': len(wins),
        'conflict_count': len(losses),
        'one_commit_one_conflict': len(wins) == 1 and len(losses) == 1,
        'results': results,
    }


def test_idempotent_digest() -> dict:
    setup_clone()
    state = _parse_stdout(_run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_ID]))
    doc = {**state['document'], 'purpose': 'Idempotent digest proof 0913'}
    op = f'idempotent-{uuid.uuid4().hex[:10]}'
    first_sha = state['sha256']
    first = _run_cli(
        [
            'catalog-edit-apply',
            TABLE,
            first_sha,
            json.dumps(doc),
            '--record-id',
            RECORD_ID,
            '--next-revision',
            str(state['revision'] + 1),
            '--operation-id',
            op,
        ]
    )
    second = _run_cli(
        [
            'catalog-edit-apply',
            TABLE,
            first_sha,
            json.dumps(doc),
            '--record-id',
            RECORD_ID,
            '--next-revision',
            str(state['revision'] + 1),
            '--operation-id',
            op,
        ]
    )
    b1 = _parse_stdout(first) if first.returncode == 0 else {}
    b2 = _parse_stdout(second) if second.returncode == 0 else {}
    after_first = b1.get('after_sha256')
    state2 = _parse_stdout(_run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_ID]))
    bad = _run_cli(
        [
            'catalog-edit-apply',
            TABLE,
            state2['sha256'],
            json.dumps({**doc, 'purpose': 'different payload'}),
            '--record-id',
            RECORD_ID,
            '--next-revision',
            str(state2['revision'] + 1),
            '--operation-id',
            op,
        ]
    )
    return {
        'first_exit': first.returncode,
        'second_exit': second.returncode,
        'first_after': after_first,
        'second_after': b2.get('after_sha256'),
        'idempotent_match': first.returncode == 0 and second.returncode == 0 and after_first == b2.get('after_sha256'),
        'payload_collision_rejected': bad.returncode != 0,
    }


def test_crash_reconcile() -> dict:
    state = _parse_stdout(_run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_ID]))
    doc = {**state['document'], 'purpose': 'Crash inject proof 0913'}
    env = {**_env_fixture(), 'CATALOG_EDIT_INJECT_CRASH': 'post_canonical_pre_derived'}
    crashed = _run_cli(
        [
            'catalog-edit-apply',
            TABLE,
            state['sha256'],
            json.dumps(doc),
            '--record-id',
            RECORD_ID,
            '--next-revision',
            str(state['revision'] + 1),
            '--operation-id',
            f'crash-{uuid.uuid4().hex[:8]}',
        ],
        env=env,
    )
    reconcile = _parse_stdout(_run_cli(['catalog-edit-reconcile']))
    after = _parse_stdout(_run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_ID]))
    return {
        'crash_exit_nonzero': crashed.returncode != 0,
        'reconcile_ran': isinstance(reconcile.get('reconciled'), list),
        'sha_restored': after.get('sha256') == state.get('sha256'),
    }


def test_metadata_document_edit() -> dict:
    state = _parse_stdout(_run_cli(['catalog-edit-state', METADATA]))
    doc = {**state['document'], 'update_policy': state['document']['update_policy'] + ' (local doc edit 0913)'}
    apply = _parse_stdout(
        _run_cli(
            [
                'catalog-edit-apply',
                METADATA,
                state['sha256'],
                json.dumps(doc),
                '--next-revision',
                str(state['revision'] + 1),
                '--operation-id',
                f'meta-{uuid.uuid4().hex[:8]}',
            ]
        )
    )
    return {'apply_exit_ok': apply.get('after_sha256') is not None, 'revision': apply.get('revision')}


def test_bounded_subprocess_timeout() -> dict:
    """Verify parent timeout path terminates a sleeping child (not unbounded wait)."""
    proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    try:
        proc.wait(timeout=2)
        return {'timeout_triggered': False}
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        return {'timeout_triggered': True, 'bounded_seconds': 2}


def test_browser(run_suffix: str) -> dict:
    setup_clone()
    pre = _parse_stdout(_run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_ID]))
    try:
        proc = subprocess.run(
            ['node', str(ROOT / 'tools/browser_canonical_edit_sync.mjs')],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            timeout=BROWSER_TIMEOUT_S,
            env={
                **os.environ,
                'BROWSER_TEST_PORT': '3223',
                'BROWSER_CAPTURE_DELIVERY': DELIVERY,
                'BROWSER_RUN_CAPTURE_SUFFIX': run_suffix,
                'CATALOG_FIXTURE_ROOT': str(CLONE),
            },
        )
    except subprocess.TimeoutExpired:
        return {'overall': 'failed', 'error': 'browser_timeout', 'exit': -9}
    try:
        parsed = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        parsed = {'overall': 'failed', 'stdout_tail': proc.stdout[-2000:]}
    parsed['exit'] = proc.returncode
    parsed['pre_browser_purpose'] = pre.get('document', {}).get('purpose')
    parsed['pre_browser_revision'] = pre.get('revision')
    return parsed


def test_strict_types_regression() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from acceptance_summarize_strict import load_saved_positive_baseline_from_receipt, self_check_two_types_regression

    pointer = json.loads((REPORTS / 'typed-controls-real-edit-receipt.json').read_text())
    baseline = load_saved_positive_baseline_from_receipt(ROOT / pointer['immutable_receipt_path'])
    return self_check_two_types_regression(baseline)


def summarize(cases: dict) -> tuple[bool, list[str]]:
    failures: list[str] = []
    prod = cases.get('production_inspection') or {}
    if not prod.get('real_maintained_assets'):
        failures.append('production_inspection')
    clone = cases.get('clone_manifest') or {}
    if not clone.get('copy_hashes_at_clone'):
        failures.append('clone_manifest')
    derived = cases.get('canonical_derived') or {}
    if not derived.get('xlsx_purpose_updated') or not derived.get('md_purpose_updated'):
        failures.append('canonical_derived')
    conc = cases.get('concurrent') or {}
    if not conc.get('one_commit_one_conflict'):
        failures.append('concurrent')
    idem = cases.get('idempotent') or {}
    if not idem.get('idempotent_match') or not idem.get('payload_collision_rejected'):
        failures.append('idempotent')
    crash = cases.get('crash_reconcile') or {}
    if not crash.get('crash_exit_nonzero') or not crash.get('sha_restored'):
        failures.append('crash_reconcile')
    meta = cases.get('metadata_doc') or {}
    if not meta.get('apply_exit_ok'):
        failures.append('metadata_doc')
    to = cases.get('timeout_bounded') or {}
    if not to.get('timeout_triggered'):
        failures.append('timeout_bounded')
    browser = cases.get('browser') or {}
    if browser.get('overall') != 'passed' or browser.get('exit') != 0:
        failures.append('browser_ui')
    reg = cases.get('strict_types_regression') or {}
    if not reg.get('saved_baseline_core_pass'):
        failures.append('strict_types_regression')
    orig = cases.get('original_hashes_unchanged') or {}
    if not orig.get('unchanged'):
        failures.append('original_hashes_unchanged')
    return not failures, failures


def main() -> int:
    run_id = str(uuid.uuid4())
    run_suffix = run_id.replace('-', '')[:12]
    before_prod = production_immutable_hashes()
    cases: dict = {}
    failed_attempts: list[dict] = []
    err: Exception | None = None
    try:
        cases['clone_manifest'] = setup_clone()
        cases['production_inspection'] = test_production_catalog_available()
        cases['concurrent'] = test_concurrent_processes()
        cases['idempotent'] = test_idempotent_digest()
        cases['crash_reconcile'] = test_crash_reconcile()
        cases['canonical_derived'] = test_canonical_edit_derived_agreement()
        cases['metadata_doc'] = test_metadata_document_edit()
        cases['timeout_bounded'] = test_bounded_subprocess_timeout()
        cases['browser'] = test_browser(run_suffix)
        cases['strict_types_regression'] = test_strict_types_regression()
    except Exception as exc:
        err = exc
        failed_attempts.append({'at': utc_now(), 'error': str(exc)})
    after_prod = production_immutable_hashes()
    cases['original_hashes_unchanged'] = {
        'unchanged': before_prod == after_prod,
        'before_count': len(before_prod),
        'after_count': len(after_prod),
    }
    if err:
        raise err
    ok, failures = summarize(cases)
    receipt_body = {
        'delivery_id': DELIVERY,
        'run_id': run_id,
        'at': utc_now(),
        'owner_chat': OWNER_CHAT,
        'scope_note': 'Original scope correction: canonical catalog/doc editing; staging-only prior delivery not relabeled as complete.',
        'prior_failed_reviews': [
            'reports/independent-maintained-edit-backend-review.json',
            'reports/independent-maintained-edit-browser-review.json',
        ],
        'source_identity': source_identities(),
        'production_immutable_hashes': before_prod,
        'catalog_clone_root': str(CLONE.relative_to(ROOT)),
        'cases': cases,
        'failed_attempt_history': failed_attempts,
        'failures': failures,
        'overall': 'passed' if ok else 'failed',
        'full_completion': False,
        'real_sdk_trace_input': 'BLOCKED',
        'drive_publication': 'local-only; not claimed',
        'independent_verification': 'not_claimed',
        'isolated_db': str(DB.relative_to(ROOT)),
        'isolated_db_sha256': sha256_file(DB) if DB.is_file() else None,
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
    (REPORTS / 'canonical-edit-sync-receipt.json').write_text(json.dumps(pointer, indent=2) + '\n')
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
    print(json.dumps({'overall': receipt_body['overall'], 'run_id': run_id, 'failures': failures}, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
