#!/usr/bin/env python3
"""Delivery browser-build-bound-correction-20261010-1320 — bounded build + 1249 browser scope."""
from __future__ import annotations

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
DELIVERY = 'catalog-preparation-recovery-20261010-1333'
PRIOR_DELIVERY = 'browser-build-bound-correction-20261010-1320'
BUILD_DEADLINE_S = 600
ACCEPTANCE_OVERALL_DEADLINE_S = 3600
PREPARATION_DEADLINE_S = 600
OWNER_CHAT = '4f32e74a-58e3-4abb-ba6f-fb151ba80cd7'
ISOLATED = ROOT / 'app' / '.data' / DELIVERY
CLONE = ISOLATED / 'catalog-clone'
DB = ISOLATED / 'local.sqlite'
APP = ROOT / 'app'
BROWSER_TIMEOUT_S = 900

SOURCE_MODULES = (
    'app/src/app/explorer/maintained-edit-panel.tsx',
    'app/src/lib/server/python.ts',
    'tools/browser_sync_recovery.mjs',
    'tools/browser_sync_recovery_acceptance.py',
    'tools/browser_sync_recovery_summarize.py',
    'tools/bounded_npm_build.py',
    'tools/node_process_bounded.mjs',
    'tools/canonical_derived_render.py',
    'tools/subprocess_bounded.py',
    'tools/catalog_fixture_clone.py',
    'tools/catalog_preparation_bounded.py',
    'tools/catalog_preparation_recovery_acceptance.py',
    'tools/catalog_sync.py',
    'tools/local_service.py',
)

sys.path.insert(0, str(ROOT / 'tools'))
import canonical_edit_sync_acceptance as ces  # noqa: E402
from browser_sync_recovery_summarize import flip_baseline_field, summarize_browser_sync_recovery  # noqa: E402

ces.DELIVERY = DELIVERY
ces.ISOLATED = ISOLATED
ces.CLONE = CLONE
ces.DB = DB


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_identities() -> dict:
    out: dict = {'modules': {}}
    for rel in SOURCE_MODULES:
        fp = ROOT / rel
        if fp.is_file():
            out['modules'][rel] = sha256_file(fp)
    bid = APP / '.next' / 'BUILD_ID'
    if bid.is_file():
        out['build_id_sha256'] = sha256_file(bid)
    return out


def prior_failed_attempts() -> list[dict]:
    out: list[dict] = []
    for path in sorted(REPORTS.glob('workflow-core-failures/*browser*.json')):
        out.append({'path': str(path.relative_to(ROOT)), 'sha256': sha256_file(path)})
    for note, rid, delivery in (
        ('transaction_final_guards', '86b6ee03-b7cb-4b96-81f1-de847391eacc', 'transaction-final-four-guards-20261010-1240'),
        ('enforcement_0828', '40ded520-af4a-4452-9da5-4cab8b320d7a', 'canonical-transaction-enforcement-20261010-0828'),
        ('review_fixes_1044', 'ae094cc8-5a7f-425e-9f4b-5deb31afeec8', 'canonical-review-fixes-20261010-1044'),
        ('browser_sync_1249_build_timeout', '955300be-c21b-4676-92eb-30f1e7436f1d', 'browser-sync-recovery-20261010-1249'),
        (
            'acceptance_prep_partial_600s',
            'acceptance-supervisory-cutoff-20261010-1324',
            'browser-build-bound-correction-20261010-1320',
        ),
    ):
        out.append({'note': note, 'run_id': rid, 'delivery': delivery})
    return out


def test_build_quality() -> dict:
    from bounded_npm_build import run_npm_build_bounded
    from subprocess_bounded import run_bounded

    env = {**os.environ, 'NEXT_TELEMETRY_DISABLED': '1'}
    build_out = run_npm_build_bounded(
        app_dir=APP,
        reports_dir=REPORTS,
        delivery_id=DELIVERY,
        timeout_s=BUILD_DEADLINE_S,
    )
    build_id_path = APP / '.next' / 'BUILD_ID'
    panel = ROOT / 'app/src/app/explorer/maintained-edit-panel.tsx'
    result = {
        **build_out,
        'lint_exit': None,
        'typecheck_exit': None,
        'build_id_sha256': sha256_file(build_id_path) if build_id_path.is_file() else None,
        'panel_source_sha256_at_build': sha256_file(panel) if panel.is_file() else None,
        'build_diagnosis_closed': 'reports/browser-sync-build-wait-diagnosis.json root_cause_unknown',
    }
    if build_out.get('build_exit') != 0:
        return result
    lint = run_bounded(['npm', 'run', 'lint'], cwd=str(APP), timeout=600, env=env)
    tsc = run_bounded(['npx', 'tsc', '-p', 'tsconfig.json', '--noEmit'], cwd=str(APP), timeout=600, env=env)
    result['lint_exit'] = lint.returncode
    result['typecheck_exit'] = tsc.returncode
    result['build_id_sha256'] = sha256_file(build_id_path) if build_id_path.is_file() else None
    return result


def test_timeout_production_path() -> dict:
    from subprocess_bounded import popen_group, terminate_group

    proc = popen_group(
        [sys.executable, '-c', 'import time; time.sleep(120)'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    reaped = False
    remaining: list[int] = []
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        cleanup = terminate_group(proc)
        reaped = cleanup.get('leader_reaped') and cleanup.get('group_clean_verified')
    return {
        'timeout_triggered': True,
        'child_reaped': reaped,
        'terminate_result': cleanup,
    }


def test_preparation_group_cleanup() -> dict:
    """Leader exits while child sleeps — group terminate must not leave children."""
    from subprocess_bounded import popen_group, terminate_group

    proc = popen_group(
        [sys.executable, '-c', 'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c","import time; time.sleep(90)"]); time.sleep(90)'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        proc.wait(timeout=1)
    except subprocess.TimeoutExpired:
        cleanup = terminate_group(proc)
        return {
            'interrupting_deadline_fired': True,
            'child_reaped': cleanup.get('leader_reaped'),
            'terminate_result': cleanup,
            'group_clean': cleanup.get('group_clean_verified'),
        }
    return {'interrupting_deadline_fired': False, 'group_clean': False}


def test_browser() -> dict:
    from subprocess_bounded import popen_group, terminate_group

    env = {
        **os.environ,
        'BROWSER_TEST_PORT': '3229',
        'BROWSER_CAPTURE_DELIVERY': DELIVERY,
        'CATALOG_FIXTURE_ROOT': str(CLONE),
        'SKIP_BROWSER_BUILD': '1',
    }
    proc = popen_group(
        ['node', str(ROOT / 'tools/browser_sync_recovery.mjs')],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    timed_out = False
    remaining: list[int] = []
    try:
        stdout, stderr = proc.communicate(timeout=BROWSER_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        timed_out = True
        from subprocess_bounded import drain_stream_bounded

        cleanup = terminate_group(proc)
        stdout = drain_stream_bounded(proc.stdout)
        stderr = drain_stream_bounded(proc.stderr)
        remaining = cleanup.get('enumeration', {}).get('pids') if cleanup else []
    else:
        stdout = stdout or ''
        stderr = stderr or ''
    try:
        parsed = json.loads(stdout) if stdout.strip() else {}
    except json.JSONDecodeError:
        parsed = {'overall': 'failed', 'stdout_tail': stdout[-2000:]}
    if (proc.returncode or 0) != 0 and parsed.get('overall') != 'passed':
        parsed['stderr_tail'] = stderr[-1500:]
    parsed['exit'] = proc.returncode
    parsed['browser_timed_out'] = timed_out
    parsed['remaining_pids_after_timeout'] = remaining
    return parsed


def test_final_run_snapshot(browser: dict) -> dict:
    from canonical_derived_render import copy_full_run_snapshot, render_catalog_derived

    render_catalog_derived(None)
    snap_dir = REPORTS / 'derived-proof' / DELIVERY / f'run-{browser.get("delivery", DELIVERY)}'
    copied = copy_full_run_snapshot(snap_dir)
    return {
        'snapshotted': True,
        'snapshot_dir': str(snap_dir.relative_to(ROOT)),
        'component_markdown_count': copied.get('component_markdown_count'),
        'content_hash_manifest': copied.get('files'),
        'final_component_purpose': browser.get('final_component_purpose'),
        'final_metadata_policy': browser.get('final_metadata_policy'),
    }


def test_negative_controls(positive: dict) -> dict:
    flips = [
        ('browser.late_response_mode_switch_passed', False),
        ('browser.disk_auto_sync_passed', False),
        ('browser.port_refused_after_stop', False),
        ('final_run_snapshot.component_markdown_count', 0),
        ('build_quality.build_exit', 1),
        ('four_guard_regression.all_passed', False),
    ]
    per = []
    for path, bad in flips:
        mutated = flip_baseline_field(positive, path, bad)
        ok, fails = summarize_browser_sync_recovery(mutated)
        per.append({'path': path, 'still_passed': ok, 'failures': fails})
    return {'each_intended_failure': all(not row['still_passed'] for row in per), 'per_flip': per}


def main() -> int:
    import time

    from canonical_transaction_guard_mocks import run_four_guard_boundary_regression

    acceptance_started = time.monotonic()
    four_guard = run_four_guard_boundary_regression()
    if not four_guard.get('all_passed'):
        print(json.dumps({'overall': 'failed', 'guard': four_guard}, indent=2))
        return 2

    run_id = str(uuid.uuid4())
    before_prod = ces.production_immutable_hashes()
    pre_sources = source_identities()
    cases: dict = {'four_guard_regression': four_guard}
    failed_attempts = prior_failed_attempts()
    err: Exception | None = None
    try:
        from catalog_fixture_clone import clone_complete_catalog

        prep_started = time.monotonic()
        cases['catalog_preparation'] = clone_complete_catalog(CLONE, preparation_deadline_s=PREPARATION_DEADLINE_S)
        cases['clone_manifest'] = cases['catalog_preparation']
        prep_recon = cases['catalog_preparation'].get('reconciliation') or {}
        if prep_recon.get('reconciliation_passed') is not True:
            raise RuntimeError(f'catalog preparation prerequisite failed: {prep_recon}')
        if time.monotonic() - prep_started > PREPARATION_DEADLINE_S:
            raise RuntimeError('catalog preparation exceeded interrupting deadline')
        cases['build_quality'] = test_build_quality()
        if cases['build_quality'].get('build_exit') != 0:
            raise RuntimeError(
                f"npm build did not exit 0: timed_out={cases['build_quality'].get('build_timed_out')} "
                f"log={cases['build_quality'].get('build_log_path')}"
            )
        if time.monotonic() - acceptance_started > ACCEPTANCE_OVERALL_DEADLINE_S:
            raise RuntimeError('acceptance overall deadline exceeded before browser')
        cases['preparation_group_cleanup'] = test_preparation_group_cleanup()
        cases['timeout_production_path'] = test_timeout_production_path()
        cases['browser'] = test_browser()
        cases['final_run_snapshot'] = test_final_run_snapshot(cases['browser'])
        cases['source_build_binding'] = {
            'pre_post_sources_stable': True,
            'served_build_id_before': cases['browser'].get('build_id_before'),
            'served_build_id_after': cases['browser'].get('build_id_after'),
            'pre_source_modules': pre_sources.get('modules'),
        }
        cases['negative_controls'] = test_negative_controls(cases)
        post_sources = source_identities()
        cases['source_build_binding']['post_source_modules'] = post_sources.get('modules')
        cases['source_build_binding']['pre_post_sources_stable'] = (
            pre_sources.get('modules') == post_sources.get('modules')
        )
        cases['source_identity'] = post_sources
    except Exception as exc:
        err = exc
        failed_attempts.append({'at': utc_now(), 'error': str(exc)})
    after_prod = ces.production_immutable_hashes()
    cases['original_hashes_unchanged'] = {
        'unchanged': before_prod == after_prod,
        'before_count': len(before_prod),
        'after_count': len(after_prod),
    }
    ok, failures = summarize_browser_sync_recovery(cases) if not err else (False, [str(err)])
    receipt = {
        'delivery_id': DELIVERY,
        'prior_delivery_id': PRIOR_DELIVERY,
        'prior_transaction_acceptance': 'reports/independent-transaction-final-guards-review.json run 86b6ee03',
        'run_id': run_id,
        'at': utc_now(),
        'owner_chat': OWNER_CHAT,
        'milestone_scope': 'bounded build correction then browser/sync/restart proof (1249 scope)',
        'build_diagnosis_acknowledged': [
            'reports/build-supervisory-cutoff-20261010-1316.json',
            'reports/browser-sync-build-wait-diagnosis.json',
            'reports/browser-sync-build-drift-20261010-1304.json',
            'reports/successor-build-probe-20261010-1308.json',
            'reports/acceptance-supervisory-cutoff-20261010-1324.json',
            'reports/acceptance-phase-20261010-1323.json',
        ],
        'prior_reviews_acknowledged': [
            'reports/independent-canonical-review-fixes-browser.json',
            'reports/independent-canonical-review-fixes-browser.md',
            'work/supervision/browser-sync-recovery-20261010-1249.txt',
        ],
        'owner_verification': 'passed' if ok else 'failed',
        'independent_verification': 'not_claimed',
        'full_completion': False,
        'real_sdk_trace_input': 'BLOCKED',
        'broader_gates_still_pending': [
            'full_visual_matrix',
            'REL-01_fresh_session',
            'agent_tracing_import',
            'whole_edit_promotion',
        ],
        'source_identity': cases.get('source_identity', pre_sources),
        'cases': cases,
        'failures': failures,
        'overall': 'passed' if ok else 'failed',
        'failed_attempt_history': failed_attempts,
        'evidence_root': str((ISOLATED / 'evidence').relative_to(ROOT)) if (ISOLATED / 'evidence').exists() else None,
        'next_permitted_action': 'Scoped independent browser/backend review of this receipt; then visual/REL-01/tracing gates.',
    }
    if not ok:
        fail_path = REPORTS / 'workflow-core-failures' / f'{DELIVERY}-{run_id[:8]}.json'
        fail_path.parent.mkdir(parents=True, exist_ok=True)
        fail_path.write_text(json.dumps(cases, indent=2) + '\n')
        receipt['failure_artifact'] = str(fail_path.relative_to(ROOT))
    from receipt_immutable import append_manifest, write_final_receipt_once

    rel = str((RUN_RECEIPTS / f'{DELIVERY}-{run_id}.json').relative_to(ROOT))
    _, digest = write_final_receipt_once(RUN_RECEIPTS / f'{DELIVERY}-{run_id}.json', receipt)
    pointer = {'delivery_id': DELIVERY, 'run_id': run_id, 'immutable_receipt_path': rel, 'content_sha256': digest}
    append_manifest(MANIFEST, pointer)
    (REPORTS / 'catalog-preparation-recovery-receipt.json').write_text(json.dumps(pointer, indent=2) + '\n')
    (REPORTS / 'browser-sync-recovery-receipt.json').write_text(json.dumps(pointer, indent=2) + '\n')
    checkpoint = ROOT / 'work' / 'supervision' / f'{DELIVERY}-checkpoint.txt'
    checkpoint.write_text(
        '\n'.join(
            [
                f'Owner checkpoint {DELIVERY} ({receipt["at"]})',
                'Receipt: reports/catalog-preparation-recovery-receipt.json',
                f'Run: {run_id}',
                f'Overall: {receipt["overall"]}',
                'full_completion: false',
                receipt['next_permitted_action'],
                f'Failures: {failures}',
            ]
        )
        + '\n'
    )
    print(json.dumps({'overall': receipt['overall'], 'run_id': run_id, 'failures': failures}, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
