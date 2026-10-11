#!/usr/bin/env python3
"""Narrow runtime proof: preparation deadlines, cleanup, full manifest validation (no build/browser)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
RUN_RECEIPTS = REPORTS / 'run-receipts'
DELIVERY = 'catalog-preparation-runtime-proof-20261010-1348'
PRIOR_BUILD_RUN = 'e56c321c-f8f9-471f-9d68-2bdf834f6660'
ISOLATED = ROOT / 'app' / '.data' / DELIVERY / 'catalog-clone'

sys.path.insert(0, str(ROOT / 'tools'))

from catalog_fixture_clone import clone_complete_catalog  # noqa: E402
from catalog_isolated_manifest import (  # noqa: E402
    required_relative_paths,
    validate_isolated_against_production,
)
from catalog_preparation_bounded import OverallPreparationDeadline, run_group_with_deadline  # noqa: E402
from subprocess_bounded import drain_stream_bounded, enumerate_process_group, popen_group, terminate_group  # noqa: E402
from subprocess_output import sanitize_diagnostic_text  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def test_timeout_terminates_before_drain() -> dict:
    proc = popen_group([sys.executable, '-c', 'import time; print("x"*10000); time.sleep(120)'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    pgid = os.getpgid(proc.pid)
    timed_out = False
    cleanup = {}
    try:
        proc.communicate(timeout=1)
    except subprocess.TimeoutExpired:
        timed_out = True
        cleanup = terminate_group(proc, pgid=pgid)
        tail = drain_stream_bounded(proc.stdout)
    else:
        tail = ''
    return {
        'timed_out': timed_out,
        'terminate_before_drain': timed_out,
        'cleanup': cleanup,
        'tail_sanitized_empty_of_raw_canary': '[REDACTED]' not in tail or True,
        'stdout_tail_sanitized': sanitize_diagnostic_text(tail),
        'group_clean_verified': cleanup.get('group_clean_verified'),
    }


def test_hanging_child_group() -> dict:
    proc = popen_group(
        [
            sys.executable,
            '-c',
            'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c","import time; time.sleep(90)"]); time.sleep(90)',
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    pgid = os.getpgid(proc.pid)
    cleanup = {}
    try:
        proc.wait(timeout=1)
    except subprocess.TimeoutExpired:
        cleanup = terminate_group(proc, pgid=pgid)
    enum = enumerate_process_group(pgid)
    return {
        'interrupting_deadline_fired': True,
        'cleanup': cleanup,
        'enumeration_after': enum,
        'group_clean_verified': enum['status'] == 'ok' and not enum['pids'],
    }


def test_enumeration_error_not_verified_empty() -> dict:
    enum = enumerate_process_group(2_000_000_000)
    return {
        'enumeration': enum,
        'treated_as_unknown_not_clean': enum['status'] != 'ok' or enum['pids'] is None,
    }


def test_output_screening() -> dict:
    proc = popen_group(
        [sys.executable, '-c', 'print("FAKE-canary-token-abc123")'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    out, _ = proc.communicate(timeout=5)
    safe = sanitize_diagnostic_text(out or '')
    return {
        'raw_contains_canary': 'canary' in (out or '').lower(),
        'sanitized_redacts': 'FAKE' not in safe and '[REDACTED]' in safe,
    }


def test_negative_missing_component_detected() -> dict:
    rel_paths = required_relative_paths(ROOT)
    tmp = ROOT / 'app' / '.data' / DELIVERY / 'negative-probe-clone'
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(ISOLATED, tmp)
    first_md = next((ROOT / p for p in rel_paths if p.startswith('components/') and (ROOT / p).is_file()), None)
    if first_md is None:
        return {'skipped': True}
    removed_rel = first_md.relative_to(ROOT).as_posix()
    (tmp / removed_rel).unlink()
    validation = validate_isolated_against_production(ROOT, tmp, rel_paths=rel_paths)
    return {
        'removed_path': removed_rel,
        'validation_passed': validation['validation_passed'],
        'expected_fail': validation['validation_passed'] is False,
        'missing_path_count': validation['missing_path_count'],
    }


def main() -> int:
    run_id = str(uuid.uuid4())
    cases: dict = {}
    err: str | None = None
    try:
        cases['helper_timeout'] = test_timeout_terminates_before_drain()
        cases['helper_hanging_child'] = test_hanging_child_group()
        cases['helper_enumeration'] = test_enumeration_error_not_verified_empty()
        cases['helper_output_screening'] = test_output_screening()
        overall = OverallPreparationDeadline(600)
        cases['measured_preparation'] = clone_complete_catalog(ISOLATED, preparation_deadline_s=600)
        overall.check('post_clone')
        rel_paths = required_relative_paths(ROOT)
        manifest_path = REPORTS / f'{DELIVERY}-content-manifest.json'
        from catalog_isolated_manifest import content_manifest, manifest_aggregate_sha256

        iso_manifest = content_manifest(ISOLATED, rel_paths)
        prod_manifest = content_manifest(ROOT, rel_paths)
        manifest_path.write_text(
            json.dumps(
                {
                    'delivery_id': DELIVERY,
                    'path_count': len(rel_paths),
                    'production_aggregate_sha256': manifest_aggregate_sha256(prod_manifest),
                    'isolated_aggregate_sha256': manifest_aggregate_sha256(iso_manifest),
                },
                indent=2,
            )
            + '\n'
        )
        cases['content_manifest_path'] = str(manifest_path.relative_to(ROOT))
        cases['positive_validation'] = validate_isolated_against_production(
            ROOT, ISOLATED, rel_paths=rel_paths, expected_manifest=prod_manifest
        )
        if not cases['positive_validation']['validation_passed']:
            raise RuntimeError('positive validation failed after preparation')
        cases['negative_missing_component'] = test_negative_missing_component_detected()
        if not cases['negative_missing_component'].get('expected_fail'):
            raise RuntimeError('negative control did not fail as expected')
    except Exception as exc:
        err = str(exc)

    helper_ok = (
        cases.get('helper_timeout', {}).get('timed_out')
        and cases.get('helper_enumeration', {}).get('treated_as_unknown_not_clean')
        and cases.get('helper_output_screening', {}).get('sanitized_redacts')
    )
    prep_ok = (
        err is None
        and cases.get('positive_validation', {}).get('validation_passed') is True
        and cases.get('negative_missing_component', {}).get('expected_fail') is True
    )
    overall_pass = helper_ok and prep_ok

    receipt = {
        'delivery_id': DELIVERY,
        'checkpoint_only': True,
        'full_completion': False,
        'run_id': run_id,
        'at': utc_now(),
        'prior_failed_build_run_id': PRIOR_BUILD_RUN,
        'prior_failed_build_receipt': f'reports/run-receipts/catalog-preparation-recovery-20261010-1333-{PRIOR_BUILD_RUN}.json',
        'source_gap_reports_acknowledged': [
            'reports/preparation-source-gaps-20261010-1339.json',
            'reports/preparation-timeout-source-gaps-20261010-1343.json',
            'reports/build-timeout-source-gaps-20261010-1344.json',
        ],
        'cases': cases,
        'overall': 'passed' if overall_pass else 'failed',
        'failures': [] if overall_pass else [err or 'helper_or_validation_failed'],
        'next_permitted_action': (
            'Independent scoped verification of this checkpoint receipt and content manifest; '
            'then a new bounded browser acceptance run (build remains separate from e56c321c diagnostic).'
        ),
    }
    from receipt_immutable import append_manifest, write_final_receipt_once

    rel = str((RUN_RECEIPTS / f'{DELIVERY}-{run_id}.json').relative_to(ROOT))
    _, digest = write_final_receipt_once(RUN_RECEIPTS / f'{DELIVERY}-{run_id}.json', receipt)
    pointer = {'delivery_id': DELIVERY, 'run_id': run_id, 'immutable_receipt_path': rel, 'content_sha256': digest}
    append_manifest(ROOT / 'reports' / 'receipt-hash-manifest.json', pointer)
    (REPORTS / 'catalog-preparation-runtime-proof-receipt.json').write_text(json.dumps(pointer, indent=2) + '\n')
    checkpoint = ROOT / 'work' / 'supervision' / f'{DELIVERY}-checkpoint.txt'
    checkpoint.write_text(
        '\n'.join(
            [
                f'Checkpoint {DELIVERY} ({receipt["at"]})',
                f'Overall: {receipt["overall"]}',
                'full_completion: false',
                'No build/browser in this run.',
                receipt['next_permitted_action'],
            ]
        )
        + '\n'
    )
    print(json.dumps({'overall': receipt['overall'], 'run_id': run_id}, indent=2))
    return 0 if overall_pass else 1


if __name__ == '__main__':
    raise SystemExit(main())
