#!/usr/bin/env python3
"""Delivery recovery-screening-real-paths-20261010-0738 — strict APP02 browser + APP04 real emission boundaries."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
RUN_RECEIPTS = REPORTS / 'run-receipts'
MANIFEST = REPORTS / 'receipt-hash-manifest.jsonl'
TEST_ROOT = ROOT / 'app' / '.data' / 'recovery-screening-real-paths-0738'
DELIVERY = 'recovery-screening-real-paths-20261010-0738'
HISTORY = REPORTS / 'workflow-core-run-history.jsonl'
OWNER_CHAT = '4f32e74a-58e3-4abb-ba6f-fb151ba80cd7'
CANARY = 'FAKE-canary-token-res0722-emitted'
SK_CANARY = 'sk-fake-canary-rel06-do-not-use-000000000000000000000000'
BENIGN = 'LOCAL-SCREENING-OK'

SOURCE_MODULES = (
    'tools/job_recovery.py',
    'tools/local_service.py',
    'tools/output_screening.py',
    'tools/trace_store.py',
    'tools/recovery_screening_real_paths_acceptance.py',
    'tools/browser_recovery_screening.mjs',
    'tools/node_bridge_screen_probe.ts',
    'app/src/lib/server/paths.ts',
    'app/src/lib/server/python.ts',
    'app/src/app/api/health/route.ts',
    'app/src/app/api/workflow/route.ts',
    'app/src/app/explorer/workflow-panel.tsx',
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_identities() -> dict[str, str]:
    return {p: sha256_file(ROOT / p) for p in SOURCE_MODULES if (ROOT / p).is_file()}


def run_cli(db: Path, *args: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'tools/local_service.py'), '--db', str(db), *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_apply(db: Path, body: dict) -> tuple[int, str]:
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
        input=json.dumps({**body, 'actor_owner': 'owner-a'}),
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        return proc.returncode or 1, proc.stderr or proc.stdout
    err = payload.get('error') or (payload.get('payload') or {}).get('error')
    return proc.returncode or (1 if err else 0), str(err or '')


def fresh_db(name: str) -> Path:
    TEST_ROOT.mkdir(parents=True, exist_ok=True)
    db = TEST_ROOT / f'{name}.sqlite'
    if db.exists():
        db.unlink()
    run_cli(db, 'init')
    return db


def test_recovery_dependency_eligibility() -> dict:
    db = fresh_db('dep-chain')
    job = 'dep-job'
    op = f'{job}-handoff'
    stale = 'downstream-only-next'
    run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 0,
            'operation_id': f'{job}-create',
            'action': 'create',
            'payload': {
                'goal': 'dep',
                'scope': ['l'],
                'constraints': [],
                'owner': 'owner-a',
                'acceptance': ['check'],
            },
        },
    )
    for tid, deps, rev, op_id in (
        ('t1', [], 1, f'{job}-add-t1'),
        ('t2', ['t1'], 2, f'{job}-add-t2'),
    ):
        run_apply(
            db,
            {
                'job_id': job,
                'expected_revision': rev,
                'operation_id': op_id,
                'action': 'add_task',
                'handoff_operation_id': op,
                'payload': {
                    'id': tid,
                    'goal': tid,
                    'owner': 'owner-a',
                    'acceptance': ['check'],
                    'deps': deps,
                    'next_action': stale if tid == 't2' else 'upstream work',
                },
            },
        )
    run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 3,
            'operation_id': f'{job}-correct-t2',
            'action': 'correct',
            'handoff_operation_id': op,
            'payload': {'id': 'c2', 'task_id': 't2', 'reason': 'fix downstream'},
        },
    )
    _, out, _ = run_cli(db, 'recover-enhanced', job)
    pkt = json.loads(out)
    npa = pkt.get('next_permitted_action') or {}
    cg = pkt.get('correction_governed_task') or {}
    return {
        'corrected_task_blocked': cg.get('actionable') is False,
        'blockers_include_t1': 't1' in (cg.get('blockers') or []),
        'next_not_corrected_downstream': npa.get('task_id') != 't2' or npa.get('task_id') == 't1',
        'diagnostic_marker': pkt.get('diagnostic_marker') == BENIGN,
    }


def test_emission_boundaries_with_stored_canaries() -> dict:
    db = fresh_db('emit')
    job = 'ev-job'
    run_apply(
        db,
        {
            'job_id': job,
            'expected_revision': 0,
            'operation_id': 'ev-create',
            'action': 'create',
            'payload': {
                'goal': 'g',
                'scope': ['l'],
                'constraints': [],
                'owner': 'owner-a',
                'acceptance': ['check'],
            },
        },
    )
    conn = sqlite3.connect(db)
    conn.execute(
        'INSERT INTO events(job_id, revision, payload) VALUES (?,?,?)',
        (job, 99, json.dumps({'operation_id': CANARY, 'action': 'update', 'note': SK_CANARY})),
    )
    conn.commit()
    raw_event = conn.execute('SELECT payload FROM events WHERE job_id=? ORDER BY sequence DESC LIMIT 1', (job,)).fetchone()[0]
    conn.close()

    fixture = ROOT / 'work/reliability/res0738-canary-fixture.txt'
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(f'fixture {CANARY}\n')
    code_diag, out_diag, err_diag = run_cli(db, 'diagnose-text', str(fixture))

    code_read, out_read, err_read = run_cli(db, 'read-source', 'synthetic/canary-error-boundary')

    code_ev, out_ev, _ = run_cli(db, 'events', job)
    code_lj, out_lj, _ = run_cli(db, 'list-jobs')
    code_rec, out_rec, _ = run_cli(db, 'recover-enhanced', job)

    doc = {
        'receipt_id': 'res0738-trace',
        'trace_id': 'trace-res0738-canary',
        'synthetic_only': True,
        'label': CANARY,
        'spans': [{'span_id': 's1', 'name': 'n', 'metadata': {'k': SK_CANARY}}],
    }
    tmp = ROOT / 'work/reliability/res0738-trace-temp.json'
    tmp.write_text(json.dumps(doc) + '\n')
    run_cli(db, 'trace-import', str(tmp))
    conn = sqlite3.connect(db)
    conn.execute('UPDATE traces SET label=? WHERE trace_id=?', (f'list-{CANARY}', 'trace-res0738-canary'))
    conn.commit()
    raw_label = conn.execute('SELECT label FROM traces WHERE trace_id=?', ('trace-res0738-canary',)).fetchone()[0]
    conn.close()
    code_tl, out_tl, _ = run_cli(db, 'trace-list')
    code_tg, out_tg, _ = run_cli(db, 'trace-get', 'trace-res0738-canary')
    tmp.unlink(missing_ok=True)

    def check(blob: str, *, exit_code: int, require_benign: bool) -> dict:
        parsed_ok = False
        try:
            parsed = json.loads(blob)
            parsed_ok = isinstance(parsed, dict) and len(parsed) > 0
        except json.JSONDecodeError:
            parsed_ok = False
        return {
            'exit': exit_code,
            'canary_removed': CANARY not in blob and SK_CANARY not in blob,
            'nonempty': len(blob.strip()) > 20,
            'benign_marker': BENIGN in blob if require_benign else True,
            'json_shape': parsed_ok,
        }

    return {
        'raw_event_contains_canary': CANARY in raw_event,
        'raw_trace_label_contains_canary': CANARY in raw_label,
        'events_export': check(out_ev, exit_code=code_ev, require_benign=True),
        'trace_list_export': check(out_tl, exit_code=code_tl, require_benign=True),
        'trace_get_export': check(out_tg, exit_code=code_tg, require_benign=True),
        'list_jobs_export': check(out_lj, exit_code=code_lj, require_benign=True),
        'recover_export': check(out_rec, exit_code=code_rec, require_benign=True),
        'read_source_error_boundary': check(out_read + err_read, exit_code=code_read, require_benign=True),
        'diagnose_text': check(out_diag + err_diag, exit_code=code_diag, require_benign=True),
        'stderr_read_source_screened': CANARY not in err_read,
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
        parsed = {'parse_error': True, 'stdout': proc.stdout[-2000:], 'stderr': proc.stderr[-1000:]}
    blob = proc.stdout + proc.stderr
    return {
        **parsed,
        'exit': proc.returncode,
        'parsed': parsed,
        'benign_required': parsed.get('benign') is True,
        'screened_required': parsed.get('screened') is True,
        'nonempty_required': parsed.get('nonempty') is True,
        'canary_removed': CANARY not in blob and SK_CANARY not in blob,
        'read_source_intended_error': parsed.get('read_source_intended_error') is True,
        'init_ok': parsed.get('init_ok') is True,
        'nonzero_exit': parsed.get('nonzero_exit'),
    }


def test_browser_required() -> dict:
    proc = subprocess.run(
        ['node', str(ROOT / 'tools/browser_recovery_screening.mjs')],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=300000,
        env={
            **os.environ,
            'BROWSER_TEST_PORT': '3202',
            'BROWSER_CAPTURE_DELIVERY': DELIVERY,
            'BROWSER_RUN_CAPTURE_SUFFIX': uuid.uuid4().hex[:8],
        },
    )
    try:
        parsed = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        parsed = {
            'overall': 'failed',
            'parse_error': True,
            'stdout_tail': proc.stdout[-3000:],
            'stderr_tail': proc.stderr[-2000:],
        }
    parsed['exit'] = proc.returncode
    return parsed


def summarize(cases: dict) -> tuple[bool, list[str]]:
    sys.path.insert(0, str(ROOT / 'tools'))
    from acceptance_summarize_strict import summarize_recovery_real_paths

    return summarize_recovery_real_paths(cases)


def main() -> int:
    run_id = str(uuid.uuid4())
    cases = {
        'recovery_dependency': test_recovery_dependency_eligibility(),
        'emission_boundaries': test_emission_boundaries_with_stored_canaries(),
        'node_bridge': test_node_bridge(),
        'browser': test_browser_required(),
        'prior_attempts_preserved': [
            'reports/run-receipts/recovery-emitted-screening-20261010-0722-a7b9637c-ed4d-430e-80dd-a10b7d5e22ad.json',
            'reports/independent-recovery-browser-review.json',
        ],
        'independent_ack': {
            'browser_review': 'reports/independent-recovery-browser-review.json (07:35:34)',
            'screening_review': 'reports/independent-recovery-screening-review.json (pending path in supervisor queue)',
            'controlled_producer_scope': 'local action only; prior acceptance preserved',
        },
    }
    sys.path.insert(0, str(ROOT / 'tools'))
    from acceptance_summarize_strict import (
        RECOVERY_REAL_PATHS_FLIPS,
        run_summarize_negative_controls,
        summarize_recovery_real_paths,
        summarize_recovery_real_paths_core,
    )

    cases['summarize_negative_controls'] = run_summarize_negative_controls(
        cases, summarize_recovery_real_paths_core, RECOVERY_REAL_PATHS_FLIPS
    )
    ok, failures = summarize(cases)
    sys.path.insert(0, str(ROOT / 'tools'))
    from diagnostic_emission_screening import (  # noqa: E402
        contains_exposed_local_mutation_token,
        screen_browser_checks_payload,
    )

    cases = screen_browser_checks_payload(cases)
    if contains_exposed_local_mutation_token(json.dumps(cases)):
        ok = False
        failures = list(dict.fromkeys(failures + ['diagnostic_token_leak_in_receipt_cases']))
    receipt_body = {
        'delivery_id': DELIVERY,
        'run_id': run_id,
        'at': utc_now(),
        'owner_chat': OWNER_CHAT,
        'source_identity': source_identities(),
        'cases': cases,
        'failures': failures,
        'independent_verification': 'not_claimed',
        'overall': 'passed' if ok else 'failed',
        'intentional_failed_attempt_recorded': not ok,
    }
    if not ok:
        fail_path = REPORTS / 'workflow-core-failures' / f'{DELIVERY}-{run_id[:8]}.json'
        fail_path.parent.mkdir(parents=True, exist_ok=True)
        fail_path.write_text(json.dumps(cases, indent=2) + '\n')
        receipt_body['failure_artifacts_preserved'] = [
            {'path': str(fail_path.relative_to(ROOT)), 'sha256': sha256_file(fail_path)}
        ]

    sys.path.insert(0, str(ROOT / 'tools'))
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
    (REPORTS / 'recovery-screening-real-paths-receipt.json').write_text(json.dumps(pointer, indent=2) + '\n')
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
