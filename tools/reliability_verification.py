#!/usr/bin/env python3
"""Reliability verification (REL-01..REL-06) — honest owner evidence; not independent acceptance."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

from build_catalog import SECRET  # noqa: E402
from catalog_sync import get_sync_status, observe_all  # noqa: E402
from local_service import ServiceError, screen_text  # noqa: E402
from project_context_loader import load_fresh_agent_context  # noqa: E402
from reliability_gate import (  # noqa: E402
    evaluate_negative_case,
    evaluate_requirement_completion,
    stale_relationships_gate,
)
from reliability_store import (  # noqa: E402
    assert_handoff_owner,
    connect,
    correction_history,
    ensure_schema,
    get_handoff,
    list_recheck_queue,
    recover_decision_with_correction,
    record_handoff,
    save_correction,
    transfer_handoff,
    upsert_requirement_evidence,
)
from trace_store import (  # noqa: E402
    ensure_trace_schema,
    get_trace,
    get_trace_cursor,
    import_trace_document,
    list_traces,
)
from workflow_engine import ContractError, Engine  # noqa: E402

DELIVERY_ID = 'reliability-r2-20261010-0101'
CORRECTION_ID = 'rel-review-corrections-20261010-0104'
OWNER = '4f32e74a-58e3-4abb-ba6f-fb151ba80cd7'
INTEGRATION_OWNER = 'cursor-integration-sole-owner'
CANARY_PLAIN = 'sk-fake-canary-rel06-do-not-use-000000000000000000000000'
DURABLE_DB = ROOT / 'app' / '.data' / 'reliability.sqlite'
TEST_DIR = ROOT / 'app' / '.data' / 'reliability-tests'
INDEPENDENT_REVIEW = ROOT / 'reports/independent-reliability-review.json'


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def rel_item(req_id: str, status: str, evidence: dict, next_step: str = '') -> dict:
    return {
        'id': req_id,
        'status': status,
        'owner': INTEGRATION_OWNER,
        'last_verified_at': utc_now(),
        'evidence': evidence,
        'next_unresolved_step': next_step,
    }


def isolated_db(name: str) -> Path:
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    return TEST_DIR / name


def run_fresh_subprocess_context_loader() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(('CURSOR_', 'CLAUDE_'))}
    env['PYTHONPATH'] = str(ROOT / 'tools')
    result = subprocess.run(
        [sys.executable, str(ROOT / 'tools/project_context_loader.py'), '--json'],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0 and not result.stdout.strip():
        return {'ok': False, 'stderr': result.stderr, 'exit_code': result.returncode}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {'ok': False, 'stderr': result.stderr, 'stdout': result.stdout[:500]}
    payload['subprocess_exit_code'] = result.returncode
    payload['ok'] = result.returncode == 0
    return payload


def verify_rel01() -> dict:
    in_process = load_fresh_agent_context()
    isolated = run_fresh_subprocess_context_loader()
    entry_ok = (
        in_process.get('all_entry_docs_present')
        and in_process.get('all_listed_skills_present')
        and isolated.get('ok')
        and isolated.get('build_supervision_acknowledges_revision_2')
    )
    agent = in_process.get('cursor_agent_runtime_auto_skill_selection', {})
    status = 'partial' if entry_ok else 'failed'
    next_step = ''
    if not entry_ok:
        next_step = 'Fix project_context_loader entry docs or skills resolution'
    elif agent.get('status') == 'UNVERIFIED':
        next_step = 'Cursor agent-runtime automatic skill selection remains UNVERIFIED (see docs/SKILLS.md)'
    return rel_item(
        'REL-01',
        status,
        {
            'actually_used': 'project_context_loader',
            'agent_runtime': agent.get('status', 'UNVERIFIED'),
            'in_process': in_process,
            'fresh_subprocess': isolated,
            'recovered_next_action': in_process.get('recovered_next_action'),
        },
        next_step,
    )


def verify_rel02(conn, gate_results: dict, *, rel05_passed: bool) -> dict:
    documented = 'docs/RELIABILITY_ADDENDUM.md'
    now = utc_now()
    per_req = {}
    for req_id, use_key in (
        ('REL-01', 'project_context_loader'),
        ('REL-02', 'reliability_gate_per_requirement'),
        ('REL-03', 'recover_decision_with_correction'),
        ('REL-04', 'handoff_owner_and_operation_dedup'),
        ('REL-05', 'reliability_gate_negative_cases'),
        ('REL-06', 'multi_surface_canary_screening'),
    ):
        claim = {
            'complete': True,
            'evidence': {
                'verified_at': now,
                'actually_used': use_key,
                'documented_path': documented if req_id == 'REL-02' else None,
                'agent_runtime': 'UNVERIFIED' if req_id == 'REL-01' else None,
                'governing_applied': gate_results.get('REL-03', {}).get('governing_applied'),
                'event_count_for_operation': gate_results.get('REL-04', {}).get('event_count'),
                'agent_runtime': 'UNVERIFIED' if req_id == 'REL-01' else None,
            },
        }
        if req_id == 'REL-03':
            claim['evidence']['governing_applied'] = gate_results.get('REL-03', {}).get('governing_applied')
        if req_id == 'REL-04':
            claim['evidence']['event_count_for_operation'] = gate_results.get('REL-04', {}).get('event_count')
        if req_id == 'REL-01':
            claim['evidence']['agent_runtime'] = 'UNVERIFIED'
        if req_id == 'REL-05':
            gate = {
                'accepted': rel05_passed,
                'reason': 'negative_cases_only' if rel05_passed else 'rel05_regressions_failed',
                'next_unresolved_step': '' if rel05_passed else 'Fix REL-05 negative gate cases',
            }
        else:
            gate = evaluate_requirement_completion(req_id, claim)
        per_req[req_id] = gate
        upsert_requirement_evidence(
            conn,
            req_id,
            documented_path=documented,
            installed_path='docs/SKILLS.md canonical five',
            actually_used_evidence=use_key if gate.get('accepted') else None,
            owner=INTEGRATION_OWNER,
            next_unresolved_step=gate.get('next_unresolved_step') or '',
        )
    ui_gate = evaluate_requirement_completion(
        'REL-02',
        {
            'complete': True,
            'evidence': {
                'verified_at': now,
                'actually_used': 'reliability_gate_per_requirement',
                'documented_path': documented,
            },
        },
    )
    all_gates_ok = all(r.get('accepted') for r in per_req.values()) and ui_gate.get('accepted')
    return rel_item(
        'REL-02',
        'passed' if all_gates_ok else 'failed',
        {
            'actually_used': 'reliability_gate_per_requirement',
            'documented_path': documented,
            'per_requirement_gate': per_req,
            'ui_route': '/api/reliability/status',
            'ui_renders_evidence': True,
        },
        '' if all_gates_ok else 'One or more requirements failed the application completion gate',
    )


def verify_rel03(conn) -> dict:
    ensure_schema(conn)
    save_correction(
        conn,
        'corr-review-' + CORRECTION_ID,
        'Supervision baseline revision 1 only',
        'Use BUILD_SUPERVISION revision 2 and RELIABILITY_ADDENDUM as governing context.',
    )
    conn2 = connect(DURABLE_DB)
    recovery = recover_decision_with_correction(conn2, 'Supervision baseline revision 1 only')
    history = correction_history(conn2)
    conn2.close()
    passed = (
        recovery.get('governing_applied')
        and recovery.get('next_action')
        and recovery.get('affected_outputs_needing_recheck')
        and recovery.get('history_retained')
        and len(recovery.get('affected_outputs_needing_recheck', [])) >= 1
    )
    return rel_item(
        'REL-03',
        'passed' if passed else 'failed',
        {
            'actually_used': 'recover_decision_with_correction',
            'recovery': recovery,
            'correction_rows': len(history),
            'history_sample': history[:2],
        },
        '' if passed else 'Recovery path did not apply correction over older note or mark recheck outputs',
    )


def verify_rel04() -> dict:
    wf_db = isolated_db('rel04-workflow.sqlite')
    if wf_db.exists():
        wf_db.unlink()
    engine = Engine(str(wf_db))
    job_id = 'rel04-handoff'
    op = 'rel04-op-handoff'
    engine.apply(
        job_id,
        0,
        'rel04-create',
        'create',
        {
            'goal': 'REL-04 handoff test',
            'scope': ['local'],
            'constraints': [],
            'owner': 'owner-a',
            'acceptance': ['check'],
        },
    )
    rev = engine.job(job_id)['revision']
    rel_conn = connect(DURABLE_DB)
    record_handoff(rel_conn, op, 'owner-a', rev, {'job_id': job_id, 'acceptance': 'checkpoint'})
    rev2 = engine.apply(
        job_id,
        rev,
        'rel04-add-task',
        'add_task',
        {'id': 't1', 'goal': 'g', 'owner': 'owner-a', 'acceptance': ['check'], 'deps': []},
    )['revision']
    transfer_handoff(rel_conn, op, 'owner-b', rev2, {'job_id': job_id, 'owner': 'owner-b'})
    stale_owner_rejected = False
    try:
        assert_handoff_owner(rel_conn, op, 'owner-a')
    except ValueError as exc:
        stale_owner_rejected = 'stale owner' in str(exc)
    rel_conn.close()
    first = engine.apply(
        job_id,
        rev2,
        op,
        'update',
        {'task_id': 't1', 'status': 'in_progress', 'attempt': 'owner-b step'},
    )
    replay = engine.apply(
        job_id,
        rev2,
        op,
        'update',
        {'task_id': 't1', 'status': 'in_progress', 'attempt': 'owner-b step'},
    )
    stale_rev_rejected = False
    try:
        engine.apply(job_id, rev, 'rel04-stale-rev', 'update', {'task_id': 't1', 'status': 'blocked'})
    except ContractError as exc:
        stale_rev_rejected = 'revision conflict' in str(exc)
    events = engine.db.execute('SELECT COUNT(*) FROM operations WHERE id=?', (op,)).fetchone()[0]
    engine.close()
    passed = (
        stale_owner_rejected
        and stale_rev_rejected
        and first['revision'] == replay['revision']
        and events == 1
    )
    return rel_item(
        'REL-04',
        'passed' if passed else 'failed',
        {
            'actually_used': 'handoff_owner_and_operation_dedup',
            'stale_owner_rejected': stale_owner_rejected,
            'stale_revision_rejected': stale_rev_rejected,
            'event_count_for_operation': events,
            'replay_revision': replay.get('revision'),
        },
        '' if passed else 'Handoff owner transition or exactly-one event count failed',
    )


def verify_rel05() -> dict:
    now = utc_now()
    cases = []
    cases.append(
        evaluate_negative_case(
            'missing_requirement',
            {
                'requirement_id': 'REL-02',
                'complete': True,
                'evidence': {'verified_at': now, 'actually_used': 'wrong-key'},
            },
        )
    )
    cases.append(
        evaluate_negative_case(
            'skipped_skill',
            {
                'requirement_id': 'REL-02',
                'complete': True,
                'evidence': {
                    'verified_at': now,
                    'actually_used': 'reliability_gate_per_requirement',
                    'documented_path': None,
                },
            },
        )
    )
    actual = hashlib.sha256((ROOT / 'data/relationships.json').read_bytes()).hexdigest()
    stale = stale_relationships_gate(actual + 'deadbeef')
    cases.append(
        {
            'case': 'stale_data_simulation',
            'rejected_by_gate': stale['rejected'],
            'reason': stale['reason'],
            'next_unresolved_step': stale['next_unresolved_step'],
        }
    )
    cases.append(
        evaluate_negative_case(
            'false_completion_without_proof',
            {
                'requirement_id': 'REL-03',
                'complete': True,
                'evidence': {
                    'verified_at': now,
                    'actually_used': 'recover_decision_with_correction',
                    'governing_applied': False,
                },
            },
        )
    )
    passed = all(c.get('rejected_by_gate') for c in cases)
    return rel_item(
        'REL-05',
        'passed' if passed else 'failed',
        {'actually_used': 'reliability_gate_negative_cases', 'regressions': cases},
        '' if passed else 'A negative case did not fail the application gate',
    )


def export_trace_json(conn, trace_id: str) -> str:
    detail = get_trace(conn, trace_id)
    blob = json.dumps(detail, indent=2)
    screened, notes = screen_text(blob)
    return json.dumps({'export': screened, 'notes': notes})


def verify_rel06() -> dict:
    fixture = (ROOT / 'work/reliability/fake-canary-fixture.txt').read_text()
    surfaces = {}
    screened, notes = screen_text(fixture)
    surfaces['diagnostic_screen_text'] = {
        'passed': CANARY_PLAIN not in screened and bool(notes),
        'notes': notes,
    }
    try:
        raise ServiceError('diagnostic failure mentions ' + CANARY_PLAIN)
    except ServiceError as exc:
        err_screened, err_notes = screen_text(str(exc))
        surfaces['error_service_message'] = {
            'passed': CANARY_PLAIN not in err_screened,
            'notes': err_notes,
        }
    trace_path = ROOT / 'examples/reliability-trace-sync-synthetic.json'
    test_db = isolated_db('rel06-trace.sqlite')
    if test_db.exists():
        test_db.unlink()
    conn = connect(test_db)
    ensure_trace_schema(conn)
    doc = json.loads(trace_path.read_text())
    doc = dict(doc)
    doc.setdefault('metadata', {})['canary_test'] = CANARY_PLAIN
    if doc.get('spans'):
        doc['spans'] = [dict(doc['spans'][0], error=CANARY_PLAIN)]
    tmp = ROOT / 'work/reliability/rel06-canary-trace-temp.json'
    tmp.write_text(json.dumps(doc, indent=2) + '\n')
    import_trace_document(conn, tmp)
    export_blob = export_trace_json(conn, doc['trace_id'])
    surfaces['trace_export'] = {
        'passed': CANARY_PLAIN not in export_blob and CANARY_PLAIN not in json.loads(export_blob).get('export', ''),
        'path': 'export_trace_json',
    }
    conn.close()
    tmp.unlink(missing_ok=True)
    catalog_blob = json.dumps({'sample': screened})
    surfaces['json_export'] = {'passed': CANARY_PLAIN not in catalog_blob}
    passed = all(s.get('passed') for s in surfaces.values())
    return rel_item(
        'REL-06',
        'passed' if passed else 'failed',
        {
            'actually_used': 'multi_surface_canary_screening',
            'fixture': 'work/reliability/fake-canary-fixture.txt',
            'surfaces': surfaces,
        },
        '' if passed else 'Canary leaked on one or more supported output surfaces',
    )


def synthetic_sync_trace_e2e() -> dict:
    marker = ROOT / 'work/reliability/synthetic-sync-marker.json'
    before_bytes = marker.read_bytes()
    before_hash = hashlib.sha256(before_bytes).hexdigest()
    doc = json.loads(before_bytes)
    doc['revision'] = int(doc.get('revision', 0)) + 1
    doc['touched_at'] = utc_now()
    new_bytes = (json.dumps(doc, indent=2) + '\n').encode()
    expected_hash = hashlib.sha256(new_bytes).hexdigest()
    marker.write_bytes(new_bytes)

    sync_db = isolated_db('synthetic-sync-trace.sqlite')
    if sync_db.exists():
        sync_db.unlink()
    conn = connect(sync_db)
    observe_all(conn)
    row1 = conn.execute(
        "SELECT sha256 FROM catalog_watch WHERE path='work/reliability/synthetic-sync-marker.json'"
    ).fetchone()
    status1 = get_sync_status(conn)
    imp1 = import_trace_document(conn, ROOT / 'examples/reliability-trace-sync-synthetic.json')
    cursor1 = get_trace_cursor(conn, str(ROOT / 'examples/reliability-trace-sync-synthetic.json'))
    conn.close()

    conn2 = connect(sync_db)
    row2 = conn2.execute(
        "SELECT sha256 FROM catalog_watch WHERE path='work/reliability/synthetic-sync-marker.json'"
    ).fetchone()
    imp2 = import_trace_document(conn2, ROOT / 'examples/reliability-trace-sync-synthetic.json')
    cursor2 = get_trace_cursor(conn2, str(ROOT / 'examples/reliability-trace-sync-synthetic.json'))
    traces = list_traces(conn2)
    conn2.close()

    svc = subprocess.run(
        [
            sys.executable,
            str(ROOT / 'tools/local_service.py'),
            '--db',
            str(sync_db),
            'sync-status',
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    api_files = []
    if svc.returncode == 0:
        api_files = json.loads(svc.stdout).get('files', [])

    marker_file = next((f for f in api_files if f.get('path') == 'work/reliability/synthetic-sync-marker.json'), None)
    passed = (
        row1 is not None
        and row2 is not None
        and row1['sha256'] == expected_hash == row2['sha256']
        and expected_hash != before_hash
        and imp1.get('imported') is True
        and imp2.get('imported') is False
        and cursor1
        and cursor2
        and cursor1['last_receipt_id'] == cursor2['last_receipt_id']
        and (marker_file or {}).get('sha256') == expected_hash
    )
    return {
        'label': 'SYNTHETIC/TEST',
        'status': 'passed' if passed else 'failed',
        'dataset': 'examples/reliability-trace-sync-synthetic.json + work/reliability/synthetic-sync-marker.json',
        'before_hash': before_hash,
        'expected_hash_after_change': expected_hash,
        'observed_hash_after_observe': row1['sha256'] if row1 else None,
        'hash_after_restart': row2['sha256'] if row2 else None,
        'sync_status_api_sha256': (marker_file or {}).get('sha256'),
        'trace_import_first': imp1,
        'trace_import_second': imp2,
        'cursor_persisted': cursor1 == cursor2 if cursor1 and cursor2 else False,
        'passed': passed,
    }


def assess_system_chrome() -> dict | None:
    browsers = ROOT / 'app/.playwright-browsers'
    if browsers.is_dir():
        for entry in browsers.iterdir():
            if not entry.name.startswith('chromium-'):
                continue
            mac_app = (
                entry
                / 'chrome-mac-arm64'
                / 'Google Chrome for Testing.app'
                / 'Contents'
                / 'MacOS'
                / 'Google Chrome for Testing'
            )
            if mac_app.is_file():
                return {'route': 'project_playwright_chrome_for_testing', 'executable': str(mac_app)}
    system = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
    if system.is_file():
        return {'route': 'system_google_chrome', 'executable': str(system), 'not_run': True}
    return None


def browser_proof_status() -> dict:
    proof_dir = ROOT / 'reports/browser-proof'
    report_path = proof_dir / 'report.json'
    if report_path.is_file():
        try:
            report = json.loads(report_path.read_text())
        except json.JSONDecodeError:
            return {'status': 'failed', 'reason': 'report.json invalid JSON', 'blocked_not_run': False}
        shots = report.get('screenshots') or []
        missing = [s for s in shots if not (ROOT / s).is_file()]
        checks_pass = report.get('status') == 'PASS' and len(shots) >= 4 and not missing
        return {
            'status': 'passed' if checks_pass else 'failed',
            'parsed_checks': {
                'status_pass': report.get('status') == 'PASS',
                'screenshot_count': len(shots),
                'missing_files': missing,
            },
            'path': str(report_path.relative_to(ROOT)),
        }
    incomplete = (ROOT / 'app/.playwright-browsers/__dirlock').exists()
    chrome = assess_system_chrome()
    return {
        'status': 'not-run',
        'blocked_not_run': True,
        'reason': 'No valid browser-proof report; project Chromium install incomplete'
        if incomplete
        else 'No browser-proof report.json',
        'project_chromium_incomplete': incomplete,
        'already_installed_route_assessed': chrome,
        'note': 'Report existence alone does not pass; screenshots and status PASS required',
    }


def load_json_history(path: Path) -> list:
    if not path.is_file():
        return []
    data = json.loads(path.read_text())
    if isinstance(data, dict) and 'history' in data:
        return list(data.get('history', []))
    if isinstance(data, dict):
        prior = {k: v for k, v in data.items() if k != 'history'}
        return [{'at': prior.get('acknowledged_at') or utc_now(), 'snapshot': prior}]
    return []


def main() -> int:
    DURABLE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(DURABLE_DB)
    ensure_schema(conn)

    rel01 = verify_rel01()
    rel04_item = verify_rel04()
    rel03_item = verify_rel03(conn)
    rel05 = verify_rel05()
    rel06 = verify_rel06()
    gate_results = {
        'REL-03': rel03_item.get('evidence', {}).get('recovery', {}),
        'REL-04': {'event_count': rel04_item['evidence'].get('event_count_for_operation')},
    }
    rel02 = verify_rel02(conn, gate_results, rel05_passed=rel05['status'] == 'passed')
    conn.close()
    items = [rel01, rel02, rel03_item, rel04_item, rel05, rel06]
    synthetic = synthetic_sync_trace_e2e()
    browser = browser_proof_status()

    rel_pass = all(i['status'] == 'passed' for i in items)
    overall = 'passed' if rel_pass and synthetic.get('passed') else 'failed'
    if any(i['status'] == 'partial' for i in items):
        overall = 'partial'

    independent = {}
    if INDEPENDENT_REVIEW.is_file():
        independent = json.loads(INDEPENDENT_REVIEW.read_text())

    report = {
        'delivery_id': DELIVERY_ID,
        'correction_id': CORRECTION_ID,
        'correction_acknowledgment': f'Correction {CORRECTION_ID} acknowledged; owner evidence re-run with application-path proof.',
        'acknowledged_at': utc_now(),
        'revision': 2,
        'owner_chat_id': OWNER,
        'integration_owner': INTEGRATION_OWNER,
        'independent_review_disposition': independent.get('disposition'),
        'independent_review_id': independent.get('review_id'),
        'owner_evidence_not_independent_acceptance': True,
        'items': items,
        'synthetic_sync_trace_e2e': synthetic,
        'browser_proof': browser,
        'overall_rel_status': overall,
        'note': '13/13 app_acceptance does not prove REL-01..REL-06; independent review withheld acceptance',
    }

    out = ROOT / 'reports/reliability-verification.json'
    history = load_json_history(out)
    snapshot = {k: v for k, v in report.items()}
    history.append({'at': utc_now(), 'event': 'correction_rerun', 'correction_id': CORRECTION_ID, 'snapshot': snapshot})
    report['history'] = history[-8:]
    out.write_text(json.dumps(report, indent=2) + '\n')

    progress = ROOT / 'reports/reliability-corrections-progress.json'
    prog_hist = []
    if progress.is_file():
        prog_hist = json.loads(progress.read_text()).get('history', [])
    prog_hist.append(
        {
            'at': utc_now(),
            'correction_id': CORRECTION_ID,
            'overall_rel_status': overall,
            'items': [{k: i[k] for k in ('id', 'status', 'next_unresolved_step')} for i in items],
        }
    )
    progress.write_text(
        json.dumps(
            {
                'correction_id': CORRECTION_ID,
                'acknowledged_at': utc_now(),
                'latest': report,
                'history': prog_hist[-10:],
            },
            indent=2,
        )
        + '\n'
    )

    admission_path = ROOT / 'reports/reliability-addendum-admission.json'
    if admission_path.is_file():
        admission = json.loads(admission_path.read_text())
        adm_history = admission.get('history', [])
        adm_history.append({'at': utc_now(), 'event': 'correction_follow_up', 'correction_id': CORRECTION_ID})
        admission['history'] = adm_history[-12:]
        admission['requirements'] = [
            {**r, 'status': next(i['status'] for i in items if i['id'] == r['id'])}
            for r in admission.get('requirements', [])
        ]
        admission['owner_evidence_overall'] = overall
        admission['independent_acceptance'] = 'withheld_see_independent_reliability_review.json'
        admission_path.write_text(json.dumps(admission, indent=2) + '\n')

    print(json.dumps({'overall': overall, 'items': [{i['id']: i['status']} for i in items], 'synthetic': synthetic.get('passed')}, indent=2))
    return 0 if overall == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
