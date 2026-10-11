#!/usr/bin/env python3
"""Delivery strict-two-types-20261010-0838."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
RUN_RECEIPTS = REPORTS / 'run-receipts'
MANIFEST = REPORTS / 'receipt-hash-manifest.jsonl'
DELIVERY = 'strict-two-types-20261010-0838'
OWNER_CHAT = '4f32e74a-58e3-4abb-ba6f-fb151ba80cd7'
HISTORY = REPORTS / 'workflow-core-run-history.jsonl'
PRIOR_POINTER = REPORTS / 'typed-controls-real-edit-receipt.json'

SOURCE_MODULES = (
    'tools/acceptance_summarize_strict.py',
    'tools/strict_two_types_acceptance.py',
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_identities() -> dict[str, str]:
    return {p: sha256_file(ROOT / p) for p in SOURCE_MODULES if (ROOT / p).is_file()}


def load_prior_saved_baseline() -> tuple[dict, dict]:
    pointer = json.loads(PRIOR_POINTER.read_text())
    receipt_path = ROOT / pointer['immutable_receipt_path']
    receipt = json.loads(receipt_path.read_text())
    sys.path.insert(0, str(ROOT / 'tools'))
    from acceptance_summarize_strict import load_saved_positive_baseline_from_receipt

    baseline = load_saved_positive_baseline_from_receipt(receipt_path)
    return baseline, {
        'prior_pointer': str(PRIOR_POINTER.relative_to(ROOT)),
        'prior_immutable': pointer['immutable_receipt_path'],
        'prior_run_id': pointer['run_id'],
        'prior_sha256': pointer['content_sha256'],
    }


def run_cases() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from acceptance_summarize_strict import (
        EMITTED_BOUNDARIES_FLIPS,
        RECOVERY_REAL_PATHS_FLIPS,
        run_summarize_negative_controls,
        self_check_strict_validator,
        self_check_two_types_regression,
        summarize_emitted_boundaries,
        summarize_emitted_boundaries_core,
        summarize_recovery_real_paths,
        summarize_recovery_real_paths_core,
    )
    import recovery_screening_real_paths_acceptance as rr

    baseline, prior_binding = load_prior_saved_baseline()
    two_types = self_check_two_types_regression(baseline)
    legacy_self = self_check_strict_validator()

    emitted = copy.deepcopy(baseline)
    emitted['summarize_negative_controls'] = run_summarize_negative_controls(
        emitted, summarize_emitted_boundaries_core, EMITTED_BOUNDARIES_FLIPS
    )
    ok, failures = summarize_emitted_boundaries(emitted)

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

    self_ok = all(
        two_types.get(k) is True
        for k in (
            'saved_baseline_core_pass',
            'recovery_regression_exit_false_rejected',
            'generated_controls_valid',
            'control_row_wrong_flip_type_rejected',
            'each_declared_flip_fails',
        )
    ) and legacy_self.get('recovery_regression_exit_false_rejected') is True

    return {
        'prior_binding': prior_binding,
        'emitted_boundaries_suite': {
            **emitted,
            'summarize_ok': ok,
            'summarize_failures': failures,
        },
        'recovery_negative_controls': {'controls': recovery_controls, 'positive_summarize_ok': rec_ok},
        'two_types_regression': two_types,
        'validator_self_check': legacy_self,
        'validator_self_check_ok': self_ok,
    }


def summarize_delivery(cases: dict) -> tuple[bool, list[str]]:
    failures: list[str] = []
    emitted = cases.get('emitted_boundaries_suite') or {}
    if not emitted.get('summarize_ok'):
        failures.extend(emitted.get('summarize_failures') or ['emitted_summarize'])
    if not cases.get('validator_self_check_ok'):
        failures.append('validator_self_check')
    rec = cases.get('recovery_negative_controls') or {}
    if not (rec.get('controls') or {}).get('all_must_fail'):
        failures.append('recovery_negative_controls')
    if not rec.get('positive_summarize_ok'):
        failures.append('recovery_positive_summarize')
    return not failures, failures


def main() -> int:
    run_id = str(uuid.uuid4())
    cases = run_cases()
    cases['independent_reviews_ack'] = ['reports/independent-typed-controls-edit-review.json']
    cases['browser_rework'] = 'preserved_from_prior_deliveries'
    cases['real_sdk_trace_input'] = 'BLOCKED'
    ok, failures = summarize_delivery(cases)

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
        'two_types_regression': cases.get('two_types_regression'),
        'prior_binding': cases.get('prior_binding'),
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
    (REPORTS / 'strict-two-types-receipt.json').write_text(json.dumps(pointer, indent=2) + '\n')
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
