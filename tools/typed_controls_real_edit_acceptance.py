#!/usr/bin/env python3
"""Delivery typed-controls-real-edit-20261010-0831."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
RUN_RECEIPTS = REPORTS / 'run-receipts'
MANIFEST = REPORTS / 'receipt-hash-manifest.jsonl'
DELIVERY = 'typed-controls-real-edit-20261010-0831'
OWNER_CHAT = '4f32e74a-58e3-4abb-ba6f-fb151ba80cd7'
HISTORY = REPORTS / 'workflow-core-run-history.jsonl'
BASELINE_POINTER = REPORTS / 'actual-ui-valid-baseline-receipt.json'
PRESERVED_BROWSER_RUNNER_SHA = '444c0182cc189fe62239bdc1e7efb1a0ca2c01f1b4463067cd00a0d7c6e1d633'

SOURCE_MODULES = (
    'tools/acceptance_summarize_strict.py',
    'tools/typed_controls_real_edit_acceptance.py',
    'tools/catalog_screening_probe.py',
    'tools/catalog_controlled_edit.py',
    'tools/catalog_io.py',
    'tools/local_service.py',
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


def load_preserved_browser_and_recovery() -> tuple[dict, dict]:
    pointer = json.loads(BASELINE_POINTER.read_text())
    receipt_path = ROOT / pointer['immutable_receipt_path']
    receipt = json.loads(receipt_path.read_text())
    suite = receipt['cases']['emitted_boundaries_suite']
    browser = suite['browser']
    runner_sha = sha256_file(ROOT / 'tools/browser_recovery_screening.mjs')
    if runner_sha != PRESERVED_BROWSER_RUNNER_SHA:
        raise RuntimeError('browser runner changed; rerun browser acceptance before preserving proof')
    browser['preservation'] = {
        'source_receipt': pointer['immutable_receipt_path'],
        'source_run_id': pointer['run_id'],
        'runner_sha256_unchanged': True,
    }
    return browser, suite.get('recovery_regression') or {}


def run_backend_cases() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    import emitted_boundaries_served_restart_acceptance as eb
    from catalog_screening_probe import test_catalog_export_and_injected_canary
    from acceptance_summarize_strict import (
        EMITTED_BOUNDARIES_FLIPS,
        RECOVERY_REAL_PATHS_FLIPS,
        run_summarize_negative_controls,
        self_check_strict_validator,
        summarize_emitted_boundaries,
        summarize_emitted_boundaries_core,
        summarize_recovery_real_paths,
        summarize_recovery_real_paths_core,
    )
    import recovery_screening_real_paths_acceptance as rr

    browser, recovery_regression = load_preserved_browser_and_recovery()
    catalog = test_catalog_export_and_injected_canary('typed-controls-0831-catalog')
    emitted = {
        'diagnostic_plain_token': eb.test_diagnostic_plain_token_screening(),
        'python_apply_export': eb.test_python_apply_export_screened(),
        'python_catalog_export': catalog,
        'node_bridge': eb.test_node_bridge(),
        'browser': browser,
        'recovery_regression': recovery_regression,
    }
    emitted['summarize_negative_controls'] = run_summarize_negative_controls(
        emitted, summarize_emitted_boundaries_core, EMITTED_BOUNDARIES_FLIPS
    )
    ok, failures = summarize_emitted_boundaries(emitted)
    emitted['summarize_ok'] = ok
    emitted['summarize_failures'] = failures
    emitted['core_baseline_pass'] = emitted['summarize_negative_controls'].get('baseline_core_pass')

    recovery_base = {
        'recovery_dependency': rr.test_recovery_dependency_eligibility(),
        'emission_boundaries': rr.test_emission_boundaries_with_stored_canaries(),
        'node_bridge': rr.test_node_bridge(),
        'browser': {'overall': 'passed', 'exit': 0},
    }
    recovery_controls = run_summarize_negative_controls(
        recovery_base, summarize_recovery_real_paths_core, RECOVERY_REAL_PATHS_FLIPS
    )
    rec_ok, _ = summarize_recovery_real_paths({**recovery_base, 'summarize_negative_controls': recovery_controls})

    validator_self_check = self_check_strict_validator()
    self_ok = all(
        validator_self_check.get(k) is True
        for k in (
            'wrong_bool_screened_rejected',
            'wrong_exit_false_rejected',
            'wrong_nonzero_string_rejected',
            'duplicate_control_paths_rejected',
            'positive_controls_valid',
        )
    )

    return {
        'emitted_boundaries_suite': emitted,
        'recovery_negative_controls': {'controls': recovery_controls, 'positive_summarize_ok': rec_ok},
        'validator_self_check': validator_self_check,
        'validator_self_check_ok': self_ok,
        'catalog_handler_binding': {
            'isolated_db': catalog.get('isolated_db'),
            'fixture_root': catalog.get('fixture_root'),
            'fixture_root_sha256': catalog.get('fixture_root_sha256'),
            'edit_file_sha256_before': catalog.get('edit_file_sha256_before'),
            'edit_apply_sha256_after': (catalog.get('edit_apply') or {}).get('sha256_after_apply'),
            'edit_apply_sha256_restored': (catalog.get('edit_apply') or {}).get('sha256_restored'),
            'handlers': {
                'export': (catalog.get('export') or {}).get('handler'),
                'edit_state': (catalog.get('edit_state') or {}).get('handler'),
                'edit_preview': (catalog.get('edit_preview') or {}).get('handler'),
                'edit_apply': (catalog.get('edit_apply') or {}).get('handler'),
            },
        },
    }


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
    if controls.get('all_must_fail') is not True:
        failures.append('recovery_negative_controls')
    if not rec.get('positive_summarize_ok'):
        failures.append('recovery_positive_summarize')
    if not cases.get('validator_self_check_ok'):
        failures.append('validator_self_check')
    return not failures, failures


def main() -> int:
    run_id = str(uuid.uuid4())
    cases = run_backend_cases()
    cases['independent_reviews_ack'] = [
        'reports/independent-actual-ui-baseline-backend-review.json',
        'reports/independent-actual-ui-baseline-browser-review.json',
    ]
    cases['browser_rework'] = 'preserved_from_actual_ui_valid_baseline_receipt'
    cases['real_sdk_trace_input'] = 'BLOCKED'
    ok, failures = summarize_delivery(cases)

    sys.path.insert(0, str(ROOT / 'tools'))
    from diagnostic_emission_screening import contains_exposed_local_mutation_token, screen_browser_checks_payload

    cases = screen_browser_checks_payload(cases)
    if contains_exposed_local_mutation_token(json.dumps(cases)):
        ok = False
        failures = list(dict.fromkeys(failures + ['receipt_token_leak']))

    browser = (cases.get('emitted_boundaries_suite') or {}).get('browser') or {}
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
        'catalog_handler_binding': cases.get('catalog_handler_binding'),
        'served_pid_identities_preserved': {
            'before': browser.get('served_pid_before'),
            'after': browser.get('served_pid_after'),
            'preservation': (browser.get('preservation') or {}),
        },
        'validator_self_check': cases.get('validator_self_check'),
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
    (REPORTS / 'typed-controls-real-edit-receipt.json').write_text(json.dumps(pointer, indent=2) + '\n')
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
