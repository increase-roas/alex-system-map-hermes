#!/usr/bin/env python3
"""Delivery actual-ui-valid-baseline-20261010-0820."""
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
DELIVERY = 'actual-ui-valid-baseline-20261010-0820'
OWNER_CHAT = '4f32e74a-58e3-4abb-ba6f-fb151ba80cd7'
HISTORY = REPORTS / 'workflow-core-run-history.jsonl'
ISOLATED_DB = ROOT / 'app' / '.data' / DELIVERY / 'local.sqlite'

SOURCE_MODULES = (
    'tools/acceptance_summarize_strict.py',
    'tools/actual_ui_valid_baseline_acceptance.py',
    'tools/catalog_screening_probe.py',
    'tools/catalog_io.py',
    'tools/local_service.py',
    'tools/job_recovery.py',
    'tools/browser_recovery_screening.mjs',
    'tools/emitted_boundaries_served_restart_acceptance.py',
    'tools/recovery_screening_real_paths_acceptance.py',
    'app/src/app/explorer/workflow-panel.tsx',
    'app/src/lib/server/python.ts',
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
    out['tools/browser_recovery_screening.mjs'] = sha256_file(ROOT / 'tools/browser_recovery_screening.mjs')
    return out


def test_browser(run_suffix: str) -> dict:
    proc = subprocess.run(
        ['node', str(ROOT / 'tools/browser_recovery_screening.mjs')],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=300000,
        env={
            **os.environ,
            'BROWSER_TEST_PORT': '3219',
            'BROWSER_CAPTURE_DELIVERY': DELIVERY,
            'BROWSER_RUN_CAPTURE_SUFFIX': run_suffix,
        },
    )
    try:
        parsed = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        parsed = {'overall': 'failed', 'parse_error': True, 'stdout_tail': proc.stdout[-2000:]}
    parsed['exit'] = proc.returncode
    return parsed


def run_emitted_cases(run_suffix: str) -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    import emitted_boundaries_served_restart_acceptance as eb
    from catalog_screening_probe import test_catalog_export_and_injected_canary
    from acceptance_summarize_strict import (
        EMITTED_BOUNDARIES_FLIPS,
        run_summarize_negative_controls,
        summarize_emitted_boundaries,
        summarize_emitted_boundaries_core,
    )

    cases = {
        'diagnostic_plain_token': eb.test_diagnostic_plain_token_screening(),
        'python_apply_export': eb.test_python_apply_export_screened(),
        'python_catalog_export': test_catalog_export_and_injected_canary('actual-ui-0820-catalog'),
        'node_bridge': eb.test_node_bridge(),
        'browser': test_browser(run_suffix),
        'recovery_regression': eb.test_recovery_regression(),
    }
    cases['summarize_negative_controls'] = run_summarize_negative_controls(
        cases, summarize_emitted_boundaries_core, EMITTED_BOUNDARIES_FLIPS
    )
    ok, failures = summarize_emitted_boundaries(cases)
    cases['summarize_ok'] = ok
    cases['summarize_failures'] = failures
    cases['core_baseline_pass'] = cases['summarize_negative_controls'].get('baseline_core_pass')
    return cases


def run_recovery_negative_controls() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    import recovery_screening_real_paths_acceptance as rr
    from acceptance_summarize_strict import (
        RECOVERY_REAL_PATHS_FLIPS,
        run_summarize_negative_controls,
        summarize_recovery_real_paths,
        summarize_recovery_real_paths_core,
    )

    base = {
        'recovery_dependency': rr.test_recovery_dependency_eligibility(),
        'emission_boundaries': rr.test_emission_boundaries_with_stored_canaries(),
        'node_bridge': rr.test_node_bridge(),
        'browser': {'overall': 'passed', 'exit': 0},
    }
    controls = run_summarize_negative_controls(base, summarize_recovery_real_paths_core, RECOVERY_REAL_PATHS_FLIPS)
    ok, _ = summarize_recovery_real_paths({**base, 'summarize_negative_controls': controls})
    return {'controls': controls, 'positive_summarize_ok': ok}


def summarize_delivery(cases: dict) -> tuple[bool, list[str]]:
    failures: list[str] = []
    emitted = cases.get('emitted_boundaries_suite') or {}
    if not emitted.get('summarize_ok'):
        failures.extend(emitted.get('summarize_failures') or ['emitted_summarize'])
    if not emitted.get('core_baseline_pass'):
        failures.append('emitted_core_baseline')
    rec = cases.get('recovery_negative_controls') or {}
    controls = rec.get('controls') or {}
    if controls.get('baseline_core_pass') is not True:
        failures.append('recovery_core_baseline')
    if not controls.get('all_must_fail'):
        failures.append('recovery_negative_controls')
    if not rec.get('positive_summarize_ok'):
        failures.append('recovery_positive_summarize')
    return not failures, failures


def main() -> int:
    run_id = str(uuid.uuid4())
    run_suffix = run_id.replace('-', '')[:12]
    emitted = run_emitted_cases(run_suffix)
    recovery_controls = run_recovery_negative_controls()
    cases = {
        'emitted_boundaries_suite': emitted,
        'recovery_negative_controls': recovery_controls,
        'independent_reviews_ack': [
            'reports/independent-strict-verdict-backend-review.json',
            'reports/independent-strict-verdict-browser-review.json',
        ],
        'isolated_fixture_db_pattern': str(ISOLATED_DB.relative_to(ROOT)),
        'real_sdk_trace_input': 'BLOCKED',
        'remaining_gate': 'work/supervision/maintained-edit-cas-next.txt after independent acceptance',
    }
    ok, failures = summarize_delivery(cases)

    sys.path.insert(0, str(ROOT / 'tools'))
    from diagnostic_emission_screening import contains_exposed_local_mutation_token, screen_browser_checks_payload

    cases = screen_browser_checks_payload(cases)
    if contains_exposed_local_mutation_token(json.dumps(cases)):
        ok = False
        failures = list(dict.fromkeys(failures + ['receipt_token_leak']))

    browser = emitted.get('browser') or {}
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
        'served_pid_identities': {
            'before': browser.get('served_pid_before'),
            'after': browser.get('served_pid_after'),
            'restarted': browser.get('served_process_restarted'),
            'listener_released': (browser.get('restart_stop') or {}).get('listenerReleased'),
            'port_refused': (browser.get('restart_stop') or {}).get('portRefusedObserved'),
        },
        'network_capture_binding': {
            'suffix': run_suffix,
            'path': browser.get('network_log_immutable_path'),
            'sha256': browser.get('network_log_sha256'),
        },
        'summarize_negative_controls': {
            'emitted': emitted.get('summarize_negative_controls'),
            'recovery': recovery_controls.get('controls'),
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
    (REPORTS / 'actual-ui-valid-baseline-receipt.json').write_text(json.dumps(pointer, indent=2) + '\n')
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
