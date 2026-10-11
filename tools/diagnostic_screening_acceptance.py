#!/usr/bin/env python3
"""Delivery diagnostic-screening-20261010-0747 — screen diagnostics before persistence."""
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
DELIVERY = 'diagnostic-screening-20261010-0747'
OWNER_CHAT = '4f32e74a-58e3-4abb-ba6f-fb151ba80cd7'
HISTORY = REPORTS / 'workflow-core-run-history.jsonl'
CANARY = 'FAKE-canary-token-res0722-emitted'
BENIGN = 'LOCAL-SCREENING-OK'
ISOLATED_DIRS = (
    ROOT / 'app' / '.data' / 'recovery-screening-real-paths-20261010-0738',
    ROOT / 'app' / '.data' / 'recovery-screening-real-paths-0738',
)

SOURCE_MODULES = (
    'tools/diagnostic_emission_screening.py',
    'tools/diagnostic_emission_screening.mjs',
    'tools/sanitize_exposed_diagnostic_artifacts.py',
    'tools/diagnostic_screening_acceptance.py',
    'tools/browser_recovery_screening.mjs',
    'tools/recovery_screening_real_paths_acceptance.py',
    'app/src/lib/server/local-auth.ts',
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


def test_screening_unit() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from diagnostic_emission_screening import (
        contains_exposed_local_mutation_token,
        redact_diagnostic_value,
        screen_diagnostic_text,
        screen_network_log_entry,
    )

    fake_token = 'f' * 48
    raw_health = json.dumps(
        {
            'ok': True,
            'token': fake_token,
            'canary_probe': CANARY,
            'local_token_hint': 'Send X-Local-Token for mutations',
        }
    )
    screened_text, notes = screen_diagnostic_text(raw_health)
    entry = screen_network_log_entry(
        {
            'label': 'health-test',
            'status': 200,
            'contentType': 'application/json',
            'bodyPreview': raw_health[:500],
            'parsedKeys': ['ok', 'token', 'canary_probe'],
        }
    )
    nested_error = f'failed with {CANARY} and token {fake_token}'
    redacted, _ = redact_diagnostic_value({'networkLog': [entry], 'error': nested_error})
    blob = json.dumps(redacted)
    leak_detects_raw = contains_exposed_local_mutation_token(nested_error)
    return {
        'text_canary_removed': CANARY not in screened_text,
        'text_token_redacted': fake_token not in screened_text,
        'text_benign_shape': 'local_token_hint' in screened_text,
        'entry_marker': entry.get('diagnostic_marker') == BENIGN,
        'entry_token_key_redacted': 'token_redacted' in (entry.get('parsedKeys') or []),
        'plain_text_token_detected_in_raw': leak_detects_raw,
        'plain_text_token_absent_after_screen': fake_token not in blob
        and not contains_exposed_local_mutation_token(blob),
        'notes_nonempty': len(notes) > 0,
    }


def test_token_isolation_metadata() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from diagnostic_emission_screening import token_isolation_proof_metadata

    isolated = str(ISOLATED_DIRS[0])
    proof = token_isolation_proof_metadata(str(ROOT), isolated)
    token_files = [d / 'local-token.json' for d in ISOLATED_DIRS]
    return {
        **proof,
        'isolated_token_file_exists': any(p.is_file() for p in token_files),
        'default_app_token_path': str(ROOT / 'app' / '.data' / 'local-token.json'),
        'default_app_token_is_separate_file': True,
        'rotation_authorized_scope': 'isolated_fixture_dirs_only',
    }


def run_sanitize() -> dict:
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'tools/sanitize_exposed_diagnostic_artifacts.py')],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    try:
        parsed = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        parsed = {'parse_error': True}
    parsed['exit'] = proc.returncode
    return parsed


def rotate_isolated_fixture_tokens() -> dict:
    rotated: list[str] = []
    for directory in ISOLATED_DIRS:
        token_path = directory / 'local-token.json'
        if token_path.is_file():
            before = sha256_file(token_path)
            token_path.unlink()
            rotated.append(str(token_path.relative_to(ROOT)))
            after = None
        else:
            before = None
            after = None
    return {
        'rotated_paths': rotated,
        'rotation_kind': 'delete_fixture_token_file_for_next_loopback_create',
        'not_default_app_token': True,
    }


def run_recovery_regression() -> dict:
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'tools/recovery_screening_real_paths_acceptance.py')],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=600,
        env={**os.environ, 'BROWSER_TEST_PORT': '3202'},
    )
    try:
        parsed = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        parsed = {'overall': 'failed', 'parse_error': True}
    parsed['exit'] = proc.returncode
    return parsed


def assert_amended_artifacts_clean() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from diagnostic_emission_screening import contains_exposed_local_mutation_token

    paths = list(ROOT.glob('reports/browser-proof/recovery-screening-real-paths-20261010-0738/network-log.json'))
    paths += list(ROOT.glob('reports/workflow-core-failures/recovery-screening-real-paths-20261010-0738-*.json'))
    paths += list(ROOT.glob('reports/run-receipts/recovery-screening-real-paths-20261010-0738-*.json'))
    dirty: list[str] = []
    for path in paths:
        if path.is_file() and contains_exposed_local_mutation_token(path.read_text(encoding='utf-8', errors='replace')):
            dirty.append(str(path.relative_to(ROOT)))
    amendment_log = REPORTS / 'diagnostic-sanitization-amendments.jsonl'
    return {
        'paths_checked': len(paths),
        'paths_still_exposing_token': dirty,
        'amendment_log_exists': amendment_log.is_file(),
        'clean': len(dirty) == 0,
    }


def summarize(cases: dict) -> tuple[bool, list[str]]:
    failures: list[str] = []
    unit = cases['screening_unit']
    for key in (
        'text_canary_removed',
        'text_token_redacted',
        'entry_marker',
        'plain_text_token_detected_in_raw',
        'plain_text_token_absent_after_screen',
    ):
        if not unit.get(key):
            failures.append(f'screening_unit_{key}')
    if not cases['artifact_hygiene'].get('clean'):
        failures.append('artifact_hygiene')
    recovery = cases['recovery_regression']
    if recovery.get('overall') != 'passed' or recovery.get('exit') != 0:
        failures.append('recovery_regression')
    return not failures, failures


def main() -> int:
    run_id = str(uuid.uuid4())
    cases = {
        'token_isolation': test_token_isolation_metadata(),
        'screening_unit': test_screening_unit(),
        'sanitize_run': run_sanitize(),
        'artifact_hygiene': assert_amended_artifacts_clean(),
        'fixture_token_rotation': rotate_isolated_fixture_tokens(),
        'recovery_regression': run_recovery_regression(),
        'prior_owner_receipt_preserved': {
            'path': 'reports/recovery-screening-real-paths-receipt.json',
            'note': '0738 owner pass not independently accepted; history preserved',
        },
        'supervisor_finding': 'reports/supervisor-diagnostic-token-finding.json',
        'independent_verification': 'not_claimed',
        'remaining_requirements': [
            'independent backend+browser review on diagnostic-screening receipt',
            'maintained editing/CAS/derived views/full sync/browser matrix',
            'REL-01 fresh session',
            'real SDK trace input BLOCKED',
        ],
    }
    ok, failures = summarize(cases)
    sys.path.insert(0, str(ROOT / 'tools'))
    from diagnostic_emission_screening import contains_exposed_local_mutation_token, screen_browser_checks_payload

    cases = screen_browser_checks_payload(cases)
    if contains_exposed_local_mutation_token(json.dumps(cases)):
        ok = False
        failures = list(dict.fromkeys(failures + ['receipt_cases_token_leak']))

    amendment_manifest = REPORTS / 'diagnostic-sanitization-amendments.jsonl'
    receipt_body = {
        'delivery_id': DELIVERY,
        'run_id': run_id,
        'at': utc_now(),
        'owner_chat': OWNER_CHAT,
        'source_identity': source_identities(),
        'cases': cases,
        'failures': failures,
        'overall': 'passed' if ok else 'failed',
        'sanitized_artifact_amendment_manifest': str(amendment_manifest.relative_to(ROOT)),
        'token_scope_proof_metadata_only': cases['token_isolation'],
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
    (REPORTS / 'diagnostic-screening-receipt.json').write_text(json.dumps(pointer, indent=2) + '\n')
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
