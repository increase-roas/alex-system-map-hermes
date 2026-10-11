#!/usr/bin/env python3
"""Owner acceptance for consolidated-local-corrections-20261010-0550 (not independent)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
DELIVERY = 'consolidated-local-corrections-20261010-0550'
DEFAULT_DB = ROOT / 'app/.data/local.sqlite'


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_py(args: list[str], input_text: str | None = None) -> tuple[int, dict | str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'tools/local_service.py'), *args],
        input=input_text,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=120,
    )
    if proc.returncode != 0 and not proc.stdout.strip():
        return proc.returncode, proc.stderr.strip() or 'nonzero exit'
    try:
        return proc.returncode, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.returncode, proc.stdout


def main() -> int:
    findings: dict[str, dict] = {}
    history: list[dict] = []

    # APP-REVIEW-01: gate rejects failed independent report as proof
    failed_report = REPORTS / 'independent-app-path-review.json'
    bad_claim = {
        'requirement_id': 'REL-02',
        'complete': True,
        'requirement_set': ['REL-01', 'REL-02', 'REL-03', 'REL-04', 'REL-05', 'REL-06'],
        'evidence': {
            'verified_at': '2026-10-10T12:00:00',
            'actually_used': 'reliability_gate_per_requirement',
            'documented_path': 'docs/RELIABILITY_ADDENDUM.md',
            'proof_path': str(failed_report.relative_to(ROOT)),
            'proof_sha256': sha256_file(failed_report),
            'skills_verified': True,
        },
    }
    code, gate = run_py(['--db', str(DEFAULT_DB), 'reliability-complete'], json.dumps(bad_claim))
    findings['APP-REVIEW-01'] = {
        'gate_rejects_failed_independent_proof': code != 0 and isinstance(gate, dict) and not gate.get('accepted'),
        'gate_reason': gate.get('reason') if isinstance(gate, dict) else str(gate),
    }

    # APP-REVIEW-03: omission bypass closed (add_task without handoff fields)
    wf_db = ROOT / 'app/.data/reliability-tests/consolidated-handoff.sqlite'
    wf_db.parent.mkdir(parents=True, exist_ok=True)
    if wf_db.exists():
        wf_db.unlink()
    run_py(['--db', str(wf_db), 'init'])
    create = {
        'job_id': 'consolidated-job',
        'expected_revision': 0,
        'operation_id': 'consolidated-create',
        'action': 'create',
        'actor_owner': 'owner-a',
        'payload': {
            'goal': 'consolidated',
            'scope': ['local'],
            'constraints': [],
            'owner': 'owner-a',
            'acceptance': ['x'],
        },
    }
    run_py(['--db', str(wf_db), 'apply'], json.dumps(create))
    omit = {
        'job_id': 'consolidated-job',
        'expected_revision': 1,
        'operation_id': 'consolidated-omit-handoff',
        'action': 'add_task',
        'payload': {'id': 't-omit', 'goal': 'g', 'owner': 'owner-a', 'acceptance': ['c'], 'deps': []},
    }
    code_omit, omit_result = run_py(['--db', str(wf_db), 'apply'], json.dumps(omit))
    findings['APP-REVIEW-03'] = {
        'omit_handoff_rejected': code_omit != 0,
        'error': omit_result.get('error') if isinstance(omit_result, dict) else omit_result,
    }

    # APP-REVIEW-04: trace-get top-level trace/spans
    trace_db = ROOT / 'app/.data/reliability-tests/consolidated-trace.sqlite'
    if trace_db.exists():
        trace_db.unlink()
    run_py(['--db', str(trace_db), 'init'])
    fixture = ROOT / 'examples/agent-trace-fixture.json'
    if fixture.is_file():
        run_py(['--db', str(trace_db), 'trace-import', str(fixture)])
        _, exported = run_py(['--db', str(trace_db), 'trace-get', 'trace-local-map-read'])
        findings['APP-REVIEW-04'] = {
            'trace_top_level_shape': isinstance(exported, dict)
            and 'trace' in exported
            and 'spans' in exported
            and isinstance(exported.get('spans'), list),
            'span_count': len(exported.get('spans', [])) if isinstance(exported, dict) else 0,
        }
    else:
        findings['APP-REVIEW-04'] = {'trace_top_level_shape': False, 'reason': 'missing fixture'}

    # Controlled-edit schema + preview screening (fixture-only)
    from catalog_controlled_edit import preview_patch, read_state

    rel_path = 'work/reliability/editable-fixture.json'
    state = read_state(rel_path)
    doc = dict(state['document'])
    doc['revision'] = int(doc.get('revision', 0)) + 1
    doc['updated_at'] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    preview = preview_patch(rel_path, state['sha256'], doc)
    findings['CONTROLLED-EDIT'] = {
        'preview_has_after_sha': bool(preview.get('after_sha256')),
        'invalid_revision_rejected': False,
    }
    try:
        preview_patch(rel_path, state['sha256'], {'revision': -1})
    except ValueError:
        findings['CONTROLLED-EDIT']['invalid_revision_rejected'] = True

    # Run existing app-path suite
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'tools/app_path_corrections_acceptance.py')],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=180,
    )
    app_path = json.loads(proc.stdout) if proc.stdout.strip() else {'error': proc.stderr}
    findings['app_path_suite'] = app_path

    source_identity = {
        'delivery_id': DELIVERY,
        'git_commit': None,
        'source_sha256': {
            'tools/workflow_apply_guard.py': sha256_file(ROOT / 'tools/workflow_apply_guard.py'),
            'tools/reliability_gate.py': sha256_file(ROOT / 'tools/reliability_gate.py'),
            'tools/trace_store.py': sha256_file(ROOT / 'tools/trace_store.py'),
            'app/src/lib/graph/build-graph.ts': sha256_file(ROOT / 'app/src/lib/graph/build-graph.ts'),
            'tools/browser_acceptance.mjs': sha256_file(ROOT / 'tools/browser_acceptance.mjs'),
        },
        'next_build_id': sha256_file(ROOT / 'app/package.json')[:16],
    }

    browser_report_path = REPORTS / 'browser-proof' / 'report.json'
    browser = {'status': 'not_run', 'note': 'run browser_original_milestone or browser_acceptance separately'}
    if browser_report_path.is_file():
        browser = json.loads(browser_report_path.read_text())

    history.append(
        {
            'check': 'reliability_shows_evidence_existence_only',
            'status': 'FAIL',
            'preserved': True,
            'note': 'Prior browser milestone used count-only assertion; superseded by reliability_evidence_nonempty/readable',
        }
    )

    passed_ids = [k for k, v in findings.items() if isinstance(v, dict) and all(
        val for key, val in v.items() if key.endswith('_rejected') or key.endswith('_shape') or key.endswith('_proof')
    )]

    receipt = {
        'delivery_id': DELIVERY,
        'owner_chat': '4f32e74a-58e3-4abb-ba6f-fb151ba80cd7',
        'at': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        'source_identity': source_identity,
        'findings': findings,
        'failure_history_preserved': history,
        'browser_proof': browser,
        'real_sdk_tracing': {'status': 'BLOCKED', 'doc': 'docs/REAL_TRACE_INPUT.md'},
        'rel_01_fresh_context': 'UNVERIFIED',
        'owner_pass_not_independent_acceptance': True,
        'overall': 'partial',
    }
    out = REPORTS / 'consolidated-local-corrections-receipt.json'
    out.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
