#!/usr/bin/env python3
"""Delivery emitted-boundaries-served-restart-20261010-0754."""
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
DELIVERY = 'emitted-boundaries-served-restart-20261010-0754'
OWNER_CHAT = '4f32e74a-58e3-4abb-ba6f-fb151ba80cd7'
HISTORY = REPORTS / 'workflow-core-run-history.jsonl'
BENIGN = 'LOCAL-SCREENING-OK'
CANARY = 'FAKE-canary-token-res0722-emitted'

SOURCE_MODULES = (
    'tools/diagnostic_emission_screening.py',
    'tools/diagnostic_emission_screening.mjs',
    'tools/emitted_boundaries_served_restart_acceptance.py',
    'tools/browser_recovery_screening.mjs',
    'tools/local_service.py',
    'tools/node_bridge_screen_probe.ts',
    'app/src/lib/server/python.ts',
    'tools/recovery_screening_real_paths_acceptance.py',
    'tools/diagnostic_screening_acceptance.py',
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


def test_diagnostic_plain_token_screening() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from diagnostic_emission_screening import (
        contains_exposed_local_mutation_token,
        redact_diagnostic_value,
        screen_diagnostic_text,
    )

    fake = 'a' * 48
    raw = f'boundary note token {fake} end'
    screened, _ = screen_diagnostic_text(raw)
    redacted, _ = redact_diagnostic_value({'error': raw, 'canary': CANARY})
    blob = json.dumps(redacted)
    return {
        'raw_detected': contains_exposed_local_mutation_token(raw),
        'screened_absent': fake not in screened and not contains_exposed_local_mutation_token(screened),
        'nested_absent': fake not in blob and CANARY not in blob,
        'benign_marker_in_entry': BENIGN in blob or '[REDACTED' in blob,
    }


def test_python_apply_export_screened() -> dict:
    db = ROOT / 'app' / '.data' / 'emitted-boundaries-0754-apply.sqlite'
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()
    subprocess.run(
        [sys.executable, str(ROOT / 'tools/local_service.py'), '--db', str(db), 'init'],
        check=True,
        capture_output=True,
        cwd=str(ROOT),
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / 'tools/local_service.py'),
            '--db',
            str(db),
            '--reliability-db',
            str(db),
            'apply',
        ],
        input=json.dumps(
            {
                'job_id': 'apply-screen-0754',
                'expected_revision': 0,
                'operation_id': 'apply-screen-create',
                'action': 'create',
                'actor_owner': 'owner-a',
                'payload': {
                    'goal': 'screen export',
                    'scope': ['l'],
                    'constraints': [],
                    'owner': 'owner-a',
                    'acceptance': ['check'],
                },
            }
        ),
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    try:
        body = json.loads(proc.stdout)
    except json.JSONDecodeError:
        body = {}
    sys.path.insert(0, str(ROOT / 'tools'))
    from diagnostic_emission_screening import contains_exposed_local_mutation_token

    return {
        'exit': proc.returncode,
        'has_diagnostic_marker': body.get('diagnostic_marker') == BENIGN,
        'has_job_id': bool(body.get('job_id')),
        'nonempty_screening_notes': isinstance(body.get('screening_notes'), list),
        'no_token_leak': not contains_exposed_local_mutation_token(proc.stdout),
    }


def test_node_bridge() -> dict:
    proc = subprocess.run(
        ['node', str(ROOT / 'tools/node_bridge_screen_probe.mjs')],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=120,
    )
    try:
        parsed = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        parsed = {'parse_error': True}
    parsed['exit'] = proc.returncode
    return parsed


def test_browser_served_restart(run_suffix: str) -> dict:
    proc = subprocess.run(
        ['node', str(ROOT / 'tools/browser_recovery_screening.mjs')],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=300000,
        env={
            **os.environ,
            'BROWSER_TEST_PORT': '3203',
            'BROWSER_CAPTURE_DELIVERY': DELIVERY,
            'BROWSER_RUN_CAPTURE_SUFFIX': run_suffix,
        },
    )
    try:
        parsed = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        parsed = {'overall': 'failed', 'parse_error': True}
    parsed['exit'] = proc.returncode
    return parsed


def test_recovery_regression() -> dict:
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'tools/recovery_screening_real_paths_acceptance.py')],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=600,
        env={**os.environ, 'BROWSER_TEST_PORT': '3204'},
    )
    try:
        parsed = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        parsed = {'overall': 'failed'}
    parsed['exit'] = proc.returncode
    return parsed


def summarize(cases: dict) -> tuple[bool, list[str]]:
    sys.path.insert(0, str(ROOT / 'tools'))
    from acceptance_summarize_strict import summarize_emitted_boundaries

    return summarize_emitted_boundaries(cases)


def main() -> int:
    run_id = str(uuid.uuid4())
    run_suffix = run_id.replace('-', '')[:12]
    sys.path.insert(0, str(ROOT / 'tools'))
    from catalog_screening_probe import test_catalog_export_and_injected_canary

    cases = {
        'diagnostic_plain_token': test_diagnostic_plain_token_screening(),
        'python_apply_export': test_python_apply_export_screened(),
        'python_catalog_export': test_catalog_export_and_injected_canary('emitted-boundaries-0754-catalog'),
        'node_bridge': test_node_bridge(),
        'browser': test_browser_served_restart(run_suffix),
        'recovery_regression': test_recovery_regression(),
        'independent_reviews_ack': [
            'reports/independent-diagnostic-backend-review.json',
            'reports/independent-diagnostic-browser-review.json',
        ],
        'remaining_requirements': [
            'independent review on this receipt',
            'maintained editing/CAS/derived views/full sync/browser matrix',
            'REL-01 fresh session',
            'real SDK trace input BLOCKED',
        ],
        'real_sdk_trace_input': 'BLOCKED',
    }
    sys.path.insert(0, str(ROOT / 'tools'))
    from acceptance_summarize_strict import (
        EMITTED_BOUNDARIES_FLIPS,
        run_summarize_negative_controls,
        summarize_emitted_boundaries,
        summarize_emitted_boundaries_core,
    )

    cases['summarize_negative_controls'] = run_summarize_negative_controls(
        cases, summarize_emitted_boundaries_core, EMITTED_BOUNDARIES_FLIPS
    )
    ok, failures = summarize(cases)
    sys.path.insert(0, str(ROOT / 'tools'))
    from diagnostic_emission_screening import contains_exposed_local_mutation_token, screen_browser_checks_payload

    cases = screen_browser_checks_payload(cases)
    if contains_exposed_local_mutation_token(json.dumps(cases)):
        ok = False
        failures = list(dict.fromkeys(failures + ['receipt_token_leak']))

    capture_path = cases.get('browser', {}).get('network_log_immutable_path')
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
        'network_capture_binding': {
            'suffix': run_suffix,
            'path': capture_path,
            'sha256': cases.get('browser', {}).get('network_log_sha256'),
        },
        'served_pid_identities': {
            'before': cases.get('browser', {}).get('served_pid_before'),
            'after': cases.get('browser', {}).get('served_pid_after'),
            'restarted': cases.get('browser', {}).get('served_process_restarted'),
        },
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
    receipt_body['receipt_immutability'] = {'immutable_path': immutable_rel}
    _, digest = write_final_receipt_once(RUN_RECEIPTS / f'{DELIVERY}-{run_id}.json', receipt_body)
    pointer = {
        'delivery_id': DELIVERY,
        'run_id': run_id,
        'immutable_receipt_path': immutable_rel,
        'content_sha256': digest,
    }
    append_manifest(MANIFEST, pointer)
    (REPORTS / 'emitted-boundaries-served-restart-receipt.json').write_text(json.dumps(pointer, indent=2) + '\n')
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
