#!/usr/bin/env python3
"""Delivery canonical-review-fixes-20261010-1044 — independent review gap closure."""
from __future__ import annotations

import copy
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
MANIFEST = REPORTS / 'receipt-hash-manifest.json'
HISTORY = REPORTS / 'workflow-core-run-history.jsonl'
DELIVERY = 'canonical-review-fixes-20261010-1044'
OWNER_CHAT = '4f32e74a-58e3-4abb-ba6f-fb151ba80cd7'
ISOLATED = ROOT / 'app' / '.data' / DELIVERY
CLONE = ISOLATED / 'catalog-clone'
DB = ISOLATED / 'local.sqlite'
TABLE = 'data/components.json'
RECORD_ID = 'component_6f112167c8a413f0f3ab'
RECORD_ID_B = 'component_03a7517e6d7e423c9fd6'
METADATA = 'data/catalog-metadata.json'
BROWSER_TIMEOUT_S = 600
APP = ROOT / 'app'

sys.path.insert(0, str(ROOT / 'tools'))
import canonical_edit_sync_acceptance as ces  # noqa: E402
from canonical_acceptance_summarize import summarize_canonical_cases  # noqa: E402

ces.DELIVERY = DELIVERY
ces.ISOLATED = ISOLATED
ces.CLONE = CLONE
ces.DB = DB
ces.PROOF_DIR = REPORTS / 'derived-proof' / DELIVERY


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def setup_clone() -> dict:
    from catalog_reference_validation import clear_reference_cache

    clear_reference_cache()
    return ces.setup_clone()


def prior_failed_attempts() -> list[dict]:
    out = []
    for path in sorted(REPORTS.glob(f'workflow-core-failures/{DELIVERY}-*.json')):
        out.append({'path': str(path.relative_to(ROOT)), 'sha256': sha256_file(path)})
    return out


def test_schema_negative() -> dict:
    setup_clone()
    state = ces._parse_stdout(ces._run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_ID]))
    before_sha = sha256_file(CLONE / 'data' / 'components.json')
    bad = {**state['document'], 'layer_id': 'layer_0999'}
    proc = ces._run_cli(
        [
            'catalog-edit-apply',
            TABLE,
            state['sha256'],
            json.dumps(bad),
            '--record-id',
            RECORD_ID,
            '--next-revision',
            str(state['revision'] + 1),
            '--operation-id',
            f'bad-layer-{uuid.uuid4().hex[:8]}',
        ]
    )
    after_sha = sha256_file(CLONE / 'data' / 'components.json')
    return {
        'bad_layer_rejected': proc.returncode != 0,
        'zero_writes_on_bad': before_sha == after_sha,
        'stderr_has_layer': 'layer' in (proc.stderr or proc.stdout or '').lower(),
    }


def test_cross_record_concurrent() -> dict:
    setup_clone()
    state_a = ces._parse_stdout(ces._run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_ID]))
    state_b = ces._parse_stdout(ces._run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_ID_B]))
    sha = state_a['sha256']
    assert sha == state_b['sha256']
    env = ces._env_fixture()
    doc_a = {**state_a['document'], 'purpose': 'Cross A 1044'}
    doc_b = {**state_b['document'], 'purpose': 'Cross B 1044'}
    cmd = [sys.executable, str(ROOT / 'tools/local_service.py'), '--db', str(DB)]
    from subprocess_bounded import popen_group, terminate_group

    p1 = popen_group(
        cmd
        + [
            'catalog-edit-apply',
            TABLE,
            sha,
            json.dumps(doc_a),
            '--record-id',
            RECORD_ID,
            '--next-revision',
            '1',
            '--operation-id',
            f'cross-a-{uuid.uuid4().hex[:6]}',
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(ROOT),
        env=env,
    )
    p2 = popen_group(
        cmd
        + [
            'catalog-edit-apply',
            TABLE,
            sha,
            json.dumps(doc_b),
            '--record-id',
            RECORD_ID_B,
            '--next-revision',
            '1',
            '--operation-id',
            f'cross-b-{uuid.uuid4().hex[:6]}',
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(ROOT),
        env=env,
    )
    r1 = p1.wait(timeout=120)
    r2 = p2.wait(timeout=120)
    wins = sum(1 for r in (r1, r2) if r == 0)
    data = json.loads((CLONE / 'data' / 'components.json').read_text())
    pa = next(r for r in data['records'] if r['id'] == RECORD_ID)['purpose']
    pb = next(r for r in data['records'] if r['id'] == RECORD_ID_B)['purpose']
    return {
        'exit_a': r1,
        'exit_b': r2,
        'single_file_winner': wins == 1,
        'purposes': {RECORD_ID: pa, RECORD_ID_B: pb},
    }


def test_replay_after_newer() -> dict:
    setup_clone()
    state = ces._parse_stdout(ces._run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_ID]))
    op1 = f'replay1-{uuid.uuid4().hex[:8]}'
    doc1 = {**state['document'], 'purpose': 'Replay first 1044'}
    first = ces._run_cli(
        [
            'catalog-edit-apply',
            TABLE,
            state['sha256'],
            json.dumps(doc1),
            '--record-id',
            RECORD_ID,
            '--next-revision',
            str(state['revision'] + 1),
            '--operation-id',
            op1,
        ]
    )
    state2 = ces._parse_stdout(ces._run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_ID]))
    doc2 = {**state2['document'], 'purpose': 'Replay second newer 1044'}
    ces._run_cli(
        [
            'catalog-edit-apply',
            TABLE,
            state2['sha256'],
            json.dumps(doc2),
            '--record-id',
            RECORD_ID,
            '--next-revision',
            str(state2['revision'] + 1),
            '--operation-id',
            f'replay2-{uuid.uuid4().hex[:8]}',
        ]
    )
    retry = ces._run_cli(
        [
            'catalog-edit-apply',
            TABLE,
            state['sha256'],
            json.dumps(doc1),
            '--record-id',
            RECORD_ID,
            '--next-revision',
            str(state['revision'] + 1),
            '--operation-id',
            op1,
        ]
    )
    final = ces._parse_stdout(ces._run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_ID]))
    b1 = ces._parse_stdout(first)
    b2 = ces._parse_stdout(retry)
    return {
        'returns_original_without_clobber': retry.returncode == 0 and b1.get('after_sha256') == b2.get('after_sha256'),
        'disk_keeps_newer': final['document']['purpose'] == doc2['purpose'],
    }


def test_crash_extended() -> dict:
    setup_clone()
    state = ces._parse_stdout(ces._run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_ID]))
    doc = {**state['document'], 'purpose': 'Crash extended 1044'}
    env = {**ces._env_fixture(), 'CATALOG_EDIT_INJECT_CRASH': 'post_rename_pre_derived'}
    crashed = ces._run_cli(
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
    rec1 = ces._parse_stdout(ces._run_cli(['catalog-edit-reconcile']))
    after1 = ces._parse_stdout(ces._run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_ID]))
    rec2 = ces._parse_stdout(ces._run_cli(['catalog-edit-reconcile']))
    after2 = ces._parse_stdout(ces._run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_ID]))
    return {
        'crash_exit_nonzero': crashed.returncode != 0,
        'sha_restored': after1.get('sha256') == state.get('sha256'),
        'reconcile_idempotent': after2.get('sha256') == after1.get('sha256'),
        'reconcile_ran': isinstance(rec1.get('reconciled'), list),
    }


def test_derived_with_run_snapshots(run_suffix: str) -> dict:
    out = ces.test_canonical_edit_derived_agreement()
    snap_dir = ces.PROOF_DIR / f'run-{run_suffix}'
    from canonical_derived_render import copy_derived_proof

    copied = copy_derived_proof(snap_dir, record_id=RECORD_ID)
    out['run_proof_snapshotted'] = bool(copied)
    out['run_snapshot_dir'] = str(snap_dir.relative_to(ROOT))
    out['run_snapshot_hashes'] = copied
    return out


def test_timeout_production_path() -> dict:
    from subprocess_bounded import popen_group, terminate_group

    proc = popen_group(
        [sys.executable, '-c', 'import time; time.sleep(120)'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    reaped = False
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        terminate_group(proc)
        reaped = proc.poll() is not None
    return {'timeout_triggered': True, 'child_reaped': reaped}


def test_build_quality() -> dict:
    env = {**os.environ, 'NEXT_TELEMETRY_DISABLED': '1'}
    build = subprocess.run(
        ['npm', 'run', 'build'],
        cwd=str(APP),
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
    )
    lint = subprocess.run(
        ['npm', 'run', 'lint'],
        cwd=str(APP),
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
    )
    tsc = subprocess.run(
        ['npx', 'tsc', '-p', 'tsconfig.json', '--noEmit'],
        cwd=str(APP),
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
    )
    build_id_path = APP / '.next' / 'BUILD_ID'
    return {
        'build_exit': build.returncode,
        'lint_exit': lint.returncode,
        'typecheck_exit': tsc.returncode,
        'build_id_sha256': sha256_file(build_id_path) if build_id_path.is_file() else None,
        'build_log_tail': (build.stdout or '')[-500:],
    }


def test_browser(run_suffix: str) -> dict:
    setup_clone()
    proc = subprocess.run(
        ['node', str(ROOT / 'tools/browser_canonical_review_fixes.mjs')],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=BROWSER_TIMEOUT_S,
        env={
            **os.environ,
            'BROWSER_TEST_PORT': '3224',
            'BROWSER_CAPTURE_DELIVERY': DELIVERY,
            'BROWSER_RUN_CAPTURE_SUFFIX': run_suffix,
            'CATALOG_FIXTURE_ROOT': str(CLONE),
            'SKIP_BROWSER_BUILD': '1',
        },
    )
    try:
        parsed = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        parsed = {'overall': 'failed', 'stdout_tail': proc.stdout[-2000:]}
    parsed['exit'] = proc.returncode
    return parsed


def _set_path(obj: dict, dotted: str, value) -> dict:
    out = copy.deepcopy(obj)
    parts = dotted.split('.')
    cur = out
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value
    return out


def test_canonical_field_flips(positive: dict) -> dict:
    flips = [
        ('browser.disk_matches_ui', False),
        ('browser.frozen_preview_matches_apply', False),
        ('idempotent.idempotent_match', False),
        ('cross_record_concurrent.single_file_winner', False),
        ('schema_negative.zero_writes_on_bad', False),
        ('build_quality.build_exit', 1),
    ]
    per = []
    for path, bad in flips:
        mutated = _set_path(positive, path, bad)
        ok, fails = summarize_canonical_cases(mutated)
        per.append({'path': path, 'still_passed': ok, 'failures': fails})
    return {'each_flip_fails': all(not row['still_passed'] for row in per), 'per_flip': per}


def main() -> int:
    run_id = str(uuid.uuid4())
    run_suffix = run_id.replace('-', '')[:12]
    before_prod = ces.production_immutable_hashes()
    cases: dict = {}
    failed_attempts = prior_failed_attempts()
    err: Exception | None = None
    try:
        cases['clone_manifest'] = setup_clone()
        cases['production_inspection'] = ces.test_production_catalog_available()
        cases['schema_negative'] = test_schema_negative()
        cases['concurrent'] = ces.test_concurrent_processes()
        cases['cross_record_concurrent'] = test_cross_record_concurrent()
        cases['idempotent'] = ces.test_idempotent_digest()
        cases['replay_after_newer'] = test_replay_after_newer()
        cases['crash_reconcile'] = test_crash_extended()
        cases['canonical_derived'] = test_derived_with_run_snapshots(run_suffix)
        cases['metadata_doc'] = ces.test_metadata_document_edit()
        cases['timeout_production_path'] = test_timeout_production_path()
        cases['build_quality'] = test_build_quality()
        cases['browser'] = test_browser(run_suffix)
        cases['metadata_doc_ui'] = {
            'ui_apply_passed': cases['browser'].get('metadata_ui_passed') is True,
            'metadata_revision': cases['browser'].get('metadata_ui_revision'),
        }
        cases['strict_types_regression'] = ces.test_strict_types_regression()
        cases['canonical_field_flips'] = test_canonical_field_flips(cases)
    except Exception as exc:
        err = exc
        failed_attempts.append({'at': utc_now(), 'error': str(exc)})
    after_prod = ces.production_immutable_hashes()
    cases['original_hashes_unchanged'] = {
        'unchanged': before_prod == after_prod,
        'before_count': len(before_prod),
        'after_count': len(after_prod),
    }
    if err:
        raise err
    ok, failures = summarize_canonical_cases(cases)
    receipt_body = {
        'delivery_id': DELIVERY,
        'run_id': run_id,
        'at': utc_now(),
        'owner_chat': OWNER_CHAT,
        'scope_note': 'Independent review gap closure for canonical edit/sync; owner not independent acceptance.',
        'prior_reviews': [
            'reports/independent-canonical-edit-backend-review.json',
            'reports/independent-canonical-edit-browser-review.json',
        ],
        'prior_owner_receipt': 'reports/canonical-edit-sync-receipt.json',
        'source_identity': ces.source_identities(),
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
    (REPORTS / 'canonical-review-fixes-receipt.json').write_text(json.dumps(pointer, indent=2) + '\n')
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
