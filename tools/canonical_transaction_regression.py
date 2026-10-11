#!/usr/bin/env python3
"""Focused canonical transaction/schema regression — not full project acceptance."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
RUN_RECEIPTS = REPORTS / 'run-receipts'
MANIFEST = REPORTS / 'receipt-hash-manifest.json'
DELIVERY = 'transaction-final-four-guards-20261010-1240'
PRIOR_DELIVERY = 'canonical-transaction-enforcement-20261010-0828'
OWNER_CHAT = '4f32e74a-58e3-4abb-ba6f-fb151ba80cd7'
ISOLATED = ROOT / 'app' / '.data' / DELIVERY
CLONE = ISOLATED / 'catalog-clone'
DB = ISOLATED / 'local.sqlite'
TABLE = 'data/components.json'
METADATA = 'data/catalog-metadata.json'
RECORD_A = 'component_6f112167c8a413f0f3ab'
RECORD_B = 'component_03a7517e6d7e423c9fd6'
SCHEMA_REL = 'schemas/components.schema.json'
TIMEOUT_S = 600

SOURCE_MODULES = (
    'tools/canonical_maintained_edit.py',
    'tools/catalog_reference_validation.py',
    'tools/canonical_transaction_regression.py',
    'tools/canonical_transaction_evidence.py',
    'tools/canonical_transaction_invariants.py',
    'tools/canonical_transaction_registry.py',
    'tools/canonical_transaction_guard_mocks.py',
    'tools/canonical_transaction_spec.py',
    'tools/subprocess_bounded.py',
    'tools/catalog_fixture_clone.py',
    'tools/local_service.py',
)

RECORD_A_MD = f'components/{RECORD_A}.md'
RUN_EVIDENCE: Any = None

BROADER_GATES_PENDING = [
    'browser_full_ui_races_and_LKG',
    'automatic_sync_observer_DOM_proof',
    'full_2351_derived_final_byte_lineage',
    'canonical_acceptance_summarize_aggregate',
    'production_path_timeout_hang_cleanup',
    'REL-01_fresh_session',
    'real_sdk_trace_input',
    'full_visual_matrix',
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_identity() -> dict[str, Any]:
    out: dict[str, Any] = {'modules': {}, 'schema': {}}
    for p in SOURCE_MODULES:
        fp = ROOT / p
        if fp.is_file():
            out['modules'][p] = sha256_file(fp)
    schema = ROOT / SCHEMA_REL
    if schema.is_file():
        out['schema'][SCHEMA_REL] = sha256_file(schema)
    return out


def _env(extra: dict[str, str] | None = None) -> dict[str, str]:
    base = {**os.environ, 'CATALOG_FIXTURE_ROOT': str(CLONE), 'FOUNDATION_ROOT': str(ROOT)}
    if extra:
        base.update(extra)
    return base


def _parse_stdout(text: str) -> dict:
    text = text.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith('{'):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {}


def run_cli(args: list[str], *, env: dict | None = None, crash: str | None = None) -> subprocess.CompletedProcess[str]:
    from subprocess_bounded import run_bounded

    if not DB.parent.exists():
        DB.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [sys.executable, str(ROOT / 'tools/local_service.py'), '--db', str(DB), 'init'],
            check=True,
            cwd=str(ROOT),
        )
    merged = dict(env or _env())
    if crash:
        merged['CATALOG_EDIT_INJECT_CRASH'] = crash
    return run_bounded(
        [sys.executable, str(ROOT / 'tools/local_service.py'), '--db', str(DB), *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=merged,
        timeout=TIMEOUT_S,
    )


def setup_clone() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from catalog_fixture_clone import clone_complete_catalog
    from catalog_reference_validation import clear_reference_cache

    clear_reference_cache()
    barrier_root = ROOT / 'app' / '.data' / 'catalog-edit-locks' / 'barriers'
    if barrier_root.is_dir():
        shutil.rmtree(barrier_root)
    return clone_complete_catalog(CLONE)


def apply_record(record_id: str, purpose: str, *, op: str | None = None, crash: str | None = None, extra_env: dict | None = None) -> dict:
    state = _parse_stdout(run_cli(['catalog-edit-state', TABLE, '--record-id', record_id], env=_env(extra_env)).stdout)
    doc = {**state['document'], 'purpose': purpose}
    proc = run_cli(
        [
            'catalog-edit-apply',
            TABLE,
            state['sha256'],
            json.dumps(doc),
            '--record-id',
            record_id,
            '--next-revision',
            str(state['revision'] + 1),
            '--operation-id',
            op or f'op-{uuid.uuid4().hex[:10]}',
        ],
        crash=crash,
        env=_env(extra_env),
    )
    return {'exit': proc.returncode, 'body': _parse_stdout(proc.stdout), 'stderr': proc.stderr}


def revision_of(record_id: str) -> int:
    st = _parse_stdout(run_cli(['catalog-edit-state', TABLE, '--record-id', record_id]).stdout)
    return int(st.get('revision', -1))


def ops_log_rows() -> list[dict]:
    path = CLONE / 'data' / '.catalog-edit-operations.jsonl'
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text().splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def ledger_snapshot(operation_id: str | None = None) -> dict:
    rows = ops_log_rows()
    if operation_id:
        rows = [r for r in rows if r.get('operation_id') == operation_id]
    committed = [r for r in rows if r.get('status') == 'committed']
    invalidated = [r for r in rows if r.get('status') == 'invalidated']
    commits_after_invalidation = 0
    saw_invalidated = False
    for row in rows:
        if row.get('status') == 'invalidated':
            saw_invalidated = True
        if row.get('status') == 'committed' and saw_invalidated:
            commits_after_invalidation += 1
    latest = rows[-1] if rows else None
    return {
        'row_count': len(rows),
        'committed_count': len(committed),
        'invalidated_count': len(invalidated),
        'commits_after_invalidation': commits_after_invalidation,
        'latest_status': latest.get('status') if latest else None,
        'latest_after_sha256': latest.get('after_sha256') if latest and latest.get('status') == 'committed' else None,
        'rows_sha256': sha256_file(CLONE / 'data' / '.catalog-edit-operations.jsonl')
        if (CLONE / 'data' / '.catalog-edit-operations.jsonl').is_file()
        else None,
    }


def persistent_state_snapshot() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from canonical_transaction_evidence import capture_state, journal_raw_bundle

    manifest = capture_state(CLONE, record_a_md=RECORD_A_MD)
    revs = CLONE / 'data' / '.maintained-revisions.json'
    revs_doc = json.loads(revs.read_text()) if revs.is_file() else {}
    journal = journal_raw_bundle(CLONE)
    return {
        'components_sha256': manifest['files'].get('data/components.json', {}).get('sha256'),
        'revisions_sha256': manifest['files'].get('data/.maintained-revisions.json', {}).get('sha256'),
        'metadata_sha256': manifest['files'].get('data/catalog-metadata.json', {}).get('sha256'),
        'ledger_sha256': manifest['files'].get('data/.catalog-edit-operations.jsonl', {}).get('sha256'),
        'revision_record_a': revs_doc.get(f'{TABLE}#{RECORD_A}', {}).get('revision'),
        'revision_record_b': revs_doc.get(f'{TABLE}#{RECORD_B}', {}).get('revision'),
        'journal_bytes_sha256': journal.get('bytes_sha256'),
        'journal_entry_count': journal.get('entry_count'),
        'derived': manifest.get('derived'),
        'manifest_sha256': manifest.get('manifest_sha256'),
    }


def save_evidence(case: str, stage: str) -> dict | None:
    if RUN_EVIDENCE is None:
        return None
    return RUN_EVIDENCE.save_stage(case, stage, record_a_md=RECORD_A_MD)


def journal_rows_for_operation(operation_id: str) -> list[dict]:
    sys.path.insert(0, str(ROOT / 'tools'))
    from canonical_transaction_evidence import journal_raw_bundle

    bundle = journal_raw_bundle(CLONE)
    return [e for e in bundle.get('entries', []) if e.get('operation_id') == operation_id]


def state_unchanged(before: dict, after: dict) -> bool:
    return before == after


def reconcile_twice_state_proof() -> dict:
    before = persistent_state_snapshot()
    rec1 = _parse_stdout(run_cli(['catalog-edit-reconcile']).stdout)
    mid = persistent_state_snapshot()
    rec2 = _parse_stdout(run_cli(['catalog-edit-reconcile']).stdout)
    after = persistent_state_snapshot()
    return {
        'first_actions': rec1.get('reconciled') or rec1.get('actions') or rec1,
        'second_actions': rec2.get('reconciled') or rec2.get('actions') or rec2,
        'state_after_first': mid,
        'state_after_second': after,
        'second_reconcile_no_persistent_change': state_unchanged(mid, after),
    }


def _barrier_env(group: str, slot: str, count: str = '2') -> dict[str, str]:
    return {
        'CATALOG_EDIT_BARRIER_GROUP': group,
        'CATALOG_EDIT_BARRIER_SLOT': slot,
        'CATALOG_EDIT_BARRIER_COUNT': count,
    }


def _apply_cmd(table: str, sha: str, doc: dict, *, record_id: str | None, next_rev: int, op: str) -> list[str]:
    cmd = [
        sys.executable,
        str(ROOT / 'tools/local_service.py'),
        '--db',
        str(DB),
        'catalog-edit-apply',
        table,
        sha,
        json.dumps(doc),
        '--next-revision',
        str(next_rev),
        '--operation-id',
        op,
    ]
    if record_id:
        cmd.extend(['--record-id', record_id])
    return cmd


def launch_overlapping(cmd_a: list[str], cmd_b: list[str], *, env_a: dict, env_b: dict) -> tuple[dict, dict]:
    from subprocess_bounded import popen_group

    p1 = popen_group(cmd_a, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(ROOT), env=env_a)
    p2 = popen_group(cmd_b, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(ROOT), env=env_b)
    e1 = p1.wait(timeout=TIMEOUT_S)
    e2 = p2.wait(timeout=TIMEOUT_S)
    out_a = p1.stdout.read() if p1.stdout else ''
    out_b = p2.stdout.read() if p2.stdout else ''
    return (
        {'exit': e1, 'body': _parse_stdout(out_a), 'stderr': p1.stderr.read() if p1.stderr else ''},
        {'exit': e2, 'body': _parse_stdout(out_b), 'stderr': p2.stderr.read() if p2.stderr else ''},
    )


def test_audit_inventory() -> dict:
    sys.path.insert(0, str(ROOT / 'tools'))
    from catalog_reference_validation import audit_existing_component_violations

    return audit_existing_component_violations(limit=5)


def test_rollback_preserves_nonzero_revision() -> dict:
    setup_clone()
    apply_record(RECORD_A, 'Txn regression A rev1')
    apply_record(RECORD_A, 'Txn regression A rev2')
    rev_a_before = revision_of(RECORD_A)
    state_b = _parse_stdout(run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_B]).stdout)
    save_evidence('rollback_preserves', 'before_crash')
    crashed = apply_record(
        RECORD_B,
        'Txn regression B crash',
        op=f'crash-b-{uuid.uuid4().hex[:8]}',
        crash='post_rename_pre_derived',
    )
    save_evidence('rollback_preserves', 'interrupted')
    _parse_stdout(run_cli(['catalog-edit-reconcile']).stdout)
    save_evidence('rollback_preserves', 'first_recovered')
    proof = reconcile_twice_state_proof()
    rev_a_still = revision_of(RECORD_A)
    save_evidence('rollback_preserves', 'after_second_recovery')
    return {
        'rev_a_before_b_edit': rev_a_before,
        'rev_a_after_reconcile': rev_a_still,
        'a_revision_preserved': rev_a_still == rev_a_before == 2,
        'b_crash_exit': crashed['exit'],
        'b_revision_restored': revision_of(RECORD_B) == int(state_b.get('revision', 0)),
        'recovery_state_idempotent': proof['second_reconcile_no_persistent_change'],
        'state_after_first_recovery': proof['state_after_first'],
        'state_after_second_recovery': proof['state_after_second'],
    }


def test_component_and_metadata_under_one_lock() -> dict:
    setup_clone()
    group = f'dual-{uuid.uuid4().hex[:8]}'
    st_a = _parse_stdout(run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_A]).stdout)
    doc_a = {**st_a['document'], 'purpose': 'Dual lock component 0730'}
    st_m = _parse_stdout(run_cli(['catalog-edit-state', METADATA]).stdout)
    doc_m = {**st_m['document'], 'update_policy': st_m['document']['update_policy'] + ' dual-lock 0730'}
    env_base = _env()
    r1, r2 = launch_overlapping(
        _apply_cmd(TABLE, st_a['sha256'], doc_a, record_id=RECORD_A, next_rev=1, op=f'dual-a-{group[:6]}'),
        _apply_cmd(METADATA, st_m['sha256'], doc_m, record_id=None, next_rev=1, op=f'dual-m-{group[:6]}'),
        env_a={**env_base, **_barrier_env(group, '0')},
        env_b={**env_base, **_barrier_env(group, '1')},
    )
    revs = json.loads((CLONE / 'data' / '.maintained-revisions.json').read_text())
    meta = json.loads((CLONE / 'data' / 'catalog-metadata.json').read_text())
    comp = json.loads((CLONE / 'data' / 'components.json').read_text())
    rec = next(r for r in comp['records'] if r['id'] == RECORD_A)
    save_evidence('dual_lock', 'final')
    return {
        'barrier_group': group,
        'component_exit': r1['exit'],
        'metadata_exit': r2['exit'],
        'component_revision': revs.get(f'{TABLE}#{RECORD_A}', {}).get('revision'),
        'metadata_revision': revs.get(f'{METADATA}#__file__', {}).get('revision'),
        'both_committed': r1['exit'] == 0 and r2['exit'] == 0,
        'component_purpose': rec.get('purpose'),
        'metadata_policy_contains': 'dual-lock 0730' in str(meta.get('update_policy', '')),
    }


def test_distinct_records_both_preserved() -> dict:
    setup_clone()
    group = f'dist-{uuid.uuid4().hex[:8]}'
    st_a = _parse_stdout(run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_A]).stdout)
    st_b = _parse_stdout(run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_B]).stdout)
    doc_a = {**st_a['document'], 'purpose': 'Distinct A 0730'}
    doc_b = {**st_b['document'], 'purpose': 'Distinct B 0730'}
    env_base = _env()
    r1, r2 = launch_overlapping(
        _apply_cmd(TABLE, st_a['sha256'], doc_a, record_id=RECORD_A, next_rev=1, op=f'da-{group[:6]}'),
        _apply_cmd(TABLE, st_b['sha256'], doc_b, record_id=RECORD_B, next_rev=1, op=f'db-{group[:6]}'),
        env_a={**env_base, **_barrier_env(group, '0')},
        env_b={**env_base, **_barrier_env(group, '1')},
    )
    exit_a_first = r1['exit']
    exit_b_first = r2['exit']
    save_evidence('distinct_records', 'first_overlap')
    stale_retry = False
    if r1['exit'] != 0:
        stale_retry = True
        st_a2 = _parse_stdout(run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_A]).stdout)
        doc_a2 = {**st_a2['document'], 'purpose': 'Distinct A 0730'}
        r1['exit'] = run_cli(
            [
                'catalog-edit-apply',
                TABLE,
                st_a2['sha256'],
                json.dumps(doc_a2),
                '--record-id',
                RECORD_A,
                '--next-revision',
                str(st_a2['revision'] + 1),
                '--operation-id',
                f'da-retry-{group[:6]}',
            ]
        ).returncode
    if r2['exit'] != 0:
        stale_retry = True
        st_b2 = _parse_stdout(run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_B]).stdout)
        doc_b2 = {**st_b2['document'], 'purpose': 'Distinct B 0730'}
        r2['exit'] = run_cli(
            [
                'catalog-edit-apply',
                TABLE,
                st_b2['sha256'],
                json.dumps(doc_b2),
                '--record-id',
                RECORD_B,
                '--next-revision',
                str(st_b2['revision'] + 1),
                '--operation-id',
                f'db-retry-{group[:6]}',
            ]
        ).returncode
    data = json.loads((CLONE / 'data' / 'components.json').read_text())
    pa = next(r for r in data['records'] if r['id'] == RECORD_A)['purpose']
    pb = next(r for r in data['records'] if r['id'] == RECORD_B)['purpose']
    save_evidence('distinct_records', 'final')
    return {
        'barrier_group': group,
        'exit_a': r1['exit'],
        'exit_b_first_attempt': exit_b_first,
        'stale_sha_retry_used': stale_retry,
        'overlapping_launched': True,
        'purpose_a': pa,
        'purpose_b': pb,
        'both_preserved': r1['exit'] == 0 and r2['exit'] == 0 and pa == 'Distinct A 0730' and pb == 'Distinct B 0730',
        'exit_a_first_attempt': exit_a_first,
    }


def test_same_op_concurrent() -> dict:
    setup_clone()
    state = _parse_stdout(run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_A]).stdout)
    doc = {**state['document'], 'purpose': 'Same op concurrent 0730'}
    op = f'same-op-{uuid.uuid4().hex[:8]}'
    group = f'same-{uuid.uuid4().hex[:6]}'
    cmd = _apply_cmd(TABLE, state['sha256'], doc, record_id=RECORD_A, next_rev=1, op=op)
    env_base = _env()
    before = persistent_state_snapshot()
    r1, r2 = launch_overlapping(
        cmd,
        cmd,
        env_a={**env_base, **_barrier_env(group, '0')},
        env_b={**env_base, **_barrier_env(group, '1')},
    )
    after = persistent_state_snapshot()
    ledger = ledger_snapshot(op)
    body = r1['body'] if r1['exit'] == 0 else r2['body']
    canonical_sha = sha256_file(CLONE / 'data' / 'components.json')
    after_a = r1['body'].get('after_sha256')
    after_b = r2['body'].get('after_sha256')
    save_evidence('same_op_concurrent', 'final')
    return {
        'operation_id': op,
        'exit_a': r1['exit'],
        'exit_b': r2['exit'],
        'after_hash_a': after_a,
        'after_hash_b': after_b,
        'after_hash_match': after_a == after_b,
        'canonical_components_sha256': canonical_sha,
        'response_hashes_match_canonical': after_a == canonical_sha and after_b == canonical_sha,
        'committed_ledger_rows': ledger['committed_count'],
        'invalidated_ledger_rows': ledger['invalidated_count'],
        'one_commit': ledger['committed_count'] == 1 and ledger['invalidated_count'] == 0,
        'final_revision': revision_of(RECORD_A),
        'final_after_sha256': body.get('after_sha256'),
    }


def test_distinct_op_same_record() -> dict:
    setup_clone()
    state = _parse_stdout(run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_A]).stdout)
    group = f'conf-{uuid.uuid4().hex[:6]}'
    win_op = f'win-{group}'
    lose_op = f'lose-{group}'
    doc_win = {**state['document'], 'purpose': 'Distinct op winner 0730'}
    doc_lose = {**state['document'], 'purpose': 'Distinct op loser 0730'}
    rev_before = revision_of(RECORD_A)
    env_base = _env()
    r_win, r_lose = launch_overlapping(
        _apply_cmd(TABLE, state['sha256'], doc_win, record_id=RECORD_A, next_rev=1, op=win_op),
        _apply_cmd(TABLE, state['sha256'], doc_lose, record_id=RECORD_A, next_rev=1, op=lose_op),
        env_a={**env_base, **_barrier_env(group, '0')},
        env_b={**env_base, **_barrier_env(group, '1')},
    )
    purpose = _parse_stdout(run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_A]).stdout)['document']['purpose']
    if r_win['exit'] == 0:
        exit_winner, exit_loser, loser_op = r_win['exit'], r_lose['exit'], lose_op
    else:
        exit_winner, exit_loser, loser_op = r_lose['exit'], r_win['exit'], win_op
    loser_rows = [r for r in ops_log_rows() if r.get('operation_id') == loser_op]
    loser_committed = sum(1 for r in loser_rows if r.get('status') == 'committed')
    loser_journals = journal_rows_for_operation(loser_op)
    rev_after = revision_of(RECORD_A)
    save_evidence('distinct_op_same_record', 'final')
    return {
        'exit_winner': exit_winner,
        'exit_loser': exit_loser,
        'winner_revision_delta': rev_after - rev_before,
        'loser_committed_rows': loser_committed,
        'loser_journal_rows': len(loser_journals),
        'purpose_on_disk': purpose,
        'loser_zero_effects': loser_committed == 0 and len(loser_journals) == 0 and rev_after - rev_before == 1,
    }


def test_changed_payload_collision() -> dict:
    setup_clone()
    state = _parse_stdout(run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_A]).stdout)
    op = f'collision-{uuid.uuid4().hex[:8]}'
    doc1 = {**state['document'], 'purpose': 'Collision first 0730'}
    first = run_cli(
        [
            'catalog-edit-apply',
            TABLE,
            state['sha256'],
            json.dumps(doc1),
            '--record-id',
            RECORD_A,
            '--next-revision',
            '1',
            '--operation-id',
            op,
        ]
    )
    doc2 = {**state['document'], 'purpose': 'Collision changed payload 0730'}
    second = run_cli(
        [
            'catalog-edit-apply',
            TABLE,
            state['sha256'],
            json.dumps(doc2),
            '--record-id',
            RECORD_A,
            '--next-revision',
            '1',
            '--operation-id',
            op,
        ]
    )
    save_evidence('changed_payload_collision', 'final')
    return {
        'first_exit_zero': first.returncode == 0,
        'second_rejected': second.returncode != 0,
        'revision_still_one': revision_of(RECORD_A) == 1,
        'purpose_unchanged_by_collision': _parse_stdout(
            run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_A]).stdout
        )['document']['purpose']
        == 'Collision first 0730',
    }


def test_post_oplog_rollback_retry() -> dict:
    setup_clone()
    state = _parse_stdout(run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_A]).stdout)
    op = f'post-oplog-{uuid.uuid4().hex[:8]}'
    doc = {**state['document'], 'purpose': 'Post oplog retry 0730'}
    crashed = run_cli(
        [
            'catalog-edit-apply',
            TABLE,
            state['sha256'],
            json.dumps(doc),
            '--record-id',
            RECORD_A,
            '--next-revision',
            '1',
            '--operation-id',
            op,
        ],
        crash='post_oplog_pre_journal_commit',
    )
    save_evidence('post_oplog_rollback_retry', 'before_reconcile')
    rec1 = _parse_stdout(run_cli(['catalog-edit-reconcile']).stdout)
    mid = persistent_state_snapshot()
    ledger_after_rollback = ledger_snapshot(op)
    save_evidence('post_oplog_rollback_retry', 'after_rollback')
    retry = run_cli(
        [
            'catalog-edit-apply',
            TABLE,
            state['sha256'],
            json.dumps(doc),
            '--record-id',
            RECORD_A,
            '--next-revision',
            '1',
            '--operation-id',
            op,
        ]
    )
    after = persistent_state_snapshot()
    ledger_final = ledger_snapshot(op)
    body = _parse_stdout(retry.stdout)
    save_evidence('post_oplog_rollback_retry', 'after_retry')
    return {
        'crash_exit_nonzero': crashed.returncode != 0,
        'reconcile_actions': rec1.get('reconciled') or rec1,
        'ledger_after_rollback': ledger_after_rollback,
        'retry_exit_zero': retry.returncode == 0,
        'invalidated_after_rollback': ledger_after_rollback['invalidated_count'] >= 1,
        'invalidated_count_after_rollback': ledger_after_rollback['invalidated_count'],
        'committed_after_retry': ledger_final['latest_status'] == 'committed'
        and ledger_final['commits_after_invalidation'] == 1,
        'final_revision': revision_of(RECORD_A),
        'state_after_reconcile': mid,
        'state_after_retry': after,
        'retry_after_sha256': body.get('after_sha256'),
    }


def test_replay_after_newer() -> dict:
    setup_clone()
    state = _parse_stdout(run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_A]).stdout)
    op1 = f'replay-{uuid.uuid4().hex[:8]}'
    doc1 = {**state['document'], 'purpose': 'Replay first 0730'}
    first = run_cli(
        [
            'catalog-edit-apply',
            TABLE,
            state['sha256'],
            json.dumps(doc1),
            '--record-id',
            RECORD_A,
            '--next-revision',
            '1',
            '--operation-id',
            op1,
        ]
    )
    save_evidence('replay_after_newer', 'after_first_commit')
    st2 = _parse_stdout(run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_A]).stdout)
    doc2 = {**st2['document'], 'purpose': 'Replay newer 0730'}
    run_cli(
        [
            'catalog-edit-apply',
            TABLE,
            st2['sha256'],
            json.dumps(doc2),
            '--record-id',
            RECORD_A,
            '--next-revision',
            str(st2['revision'] + 1),
            '--operation-id',
            f'replay2-{uuid.uuid4().hex[:6]}',
        ]
    )
    save_evidence('replay_after_newer', 'after_newer_commit')
    retry = run_cli(
        [
            'catalog-edit-apply',
            TABLE,
            state['sha256'],
            json.dumps(doc1),
            '--record-id',
            RECORD_A,
            '--next-revision',
            '1',
            '--operation-id',
            op1,
        ]
    )
    final = _parse_stdout(run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_A]).stdout)
    b1 = _parse_stdout(first.stdout)
    b2 = _parse_stdout(retry.stdout)
    save_evidence('replay_after_newer', 'after_replay')
    return {
        'retry_exit_zero': retry.returncode == 0,
        'same_result_hash': b1.get('after_sha256') == b2.get('after_sha256'),
        'first_after_sha256': b1.get('after_sha256'),
        'replay_after_sha256': b2.get('after_sha256'),
        'disk_keeps_newer': final['document']['purpose'] == 'Replay newer 0730',
        'final_revision': final.get('revision'),
    }


def test_crash_stages_matrix() -> dict:
    stages = (
        'pending_before_rename',
        'post_rename_pre_derived',
        'post_derived_pre_revision',
        'committed_before_oplog',
        'post_oplog_pre_journal_commit',
    )
    outcomes: dict[str, dict] = {}
    for stage in stages:
        setup_clone()
        apply_record(RECORD_A, f'Prestage {stage}')
        state = _parse_stdout(run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_A]).stdout)
        before_rev = state['revision']
        save_evidence(f'crash_stage_{stage}', 'before_crash')
        crashed = apply_record(RECORD_A, f'Crash at {stage}', op=f'crash-{stage[:8]}', crash=stage)
        save_evidence(f'crash_stage_{stage}', 'interrupted')
        _parse_stdout(run_cli(['catalog-edit-reconcile']).stdout)
        save_evidence(f'crash_stage_{stage}', 'first_recovered')
        _parse_stdout(run_cli(['catalog-edit-reconcile']).stdout)
        after = _parse_stdout(run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_A]).stdout)
        state_after_first = persistent_state_snapshot()
        _parse_stdout(run_cli(['catalog-edit-reconcile']).stdout)
        state_after_second = persistent_state_snapshot()
        save_evidence(f'crash_stage_{stage}', 'second_recovered')
        outcomes[stage] = {
            'crash_exit': crashed['exit'],
            'revision_restored': after.get('revision') == before_rev,
            'sha_before': state['sha256'],
            'sha_after': after.get('sha256'),
            'sha_restored': after.get('sha256') == state['sha256'],
            'recovery_state_idempotent': state_after_first == state_after_second,
            'state_after_first_recovery': state_after_first,
            'state_after_second_recovery': state_after_second,
        }
    return {
        'stages': outcomes,
        'all_restored': all(v['sha_restored'] and v['revision_restored'] for v in outcomes.values()),
        'all_recovery_idempotent': all(v['recovery_state_idempotent'] for v in outcomes.values()),
    }


def test_restore_handler() -> dict:
    setup_clone()
    apply_record(RECORD_A, 'Restore baseline 0730')
    second = apply_record(RECORD_A, 'Restore after edit 0730')
    rev_before_restore = revision_of(RECORD_A)
    backup = second['body'].get('backup')
    if not backup:
        return {'restore_ok': False, 'error': 'missing backup path'}
    restored = run_cli(['catalog-edit-restore', TABLE, backup, '--record-id', RECORD_A])
    body = _parse_stdout(restored.stdout)
    state = _parse_stdout(run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_A]).stdout)
    save_evidence('restore_handler', 'final')
    return {
        'restore_exit': restored.returncode,
        'restored_flag': body.get('restored') is True,
        'purpose_after': state['document'].get('purpose'),
        'purpose_is_baseline': state['document'].get('purpose') == 'Restore baseline 0730',
        'revision_before_restore': rev_before_restore,
        'revision_after_restore': state.get('revision'),
        'monotonic_revision': int(state.get('revision', 0)) == rev_before_restore + 1,
        'handler_monotonic_flag': body.get('monotonic') is True,
    }


def test_restore_crash_and_recovery() -> dict:
    setup_clone()
    apply_record(RECORD_A, 'Restore crash baseline 0730')
    second = apply_record(RECORD_A, 'Restore crash edited 0730')
    rev_before = revision_of(RECORD_A)
    backup = second['body'].get('backup')
    crashed = run_cli(
        ['catalog-edit-restore', TABLE, backup, '--record-id', RECORD_A],
        crash='restore_mid_write',
    )
    mid = persistent_state_snapshot()
    save_evidence('restore_crash_and_recovery', 'interrupted')
    rec1 = _parse_stdout(run_cli(['catalog-edit-reconcile']).stdout)
    after_rec1 = persistent_state_snapshot()
    save_evidence('restore_crash_and_recovery', 'first_recovered')
    rec2 = _parse_stdout(run_cli(['catalog-edit-reconcile']).stdout)
    after_rec2 = persistent_state_snapshot()
    state = _parse_stdout(run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_A]).stdout)
    save_evidence('restore_crash_and_recovery', 'second_recovered')
    return {
        'crash_exit': crashed.returncode,
        'reconcile_restore_completed': any(
            (a.get('action') == 'restore_completed' for a in (rec1.get('reconciled') or []))
        ),
        'purpose_is_baseline': state['document'].get('purpose') == 'Restore crash baseline 0730',
        'monotonic_after_recovery': int(state.get('revision', 0)) == rev_before + 1,
        'never_rolled_back_revision': int(state.get('revision', 0)) >= rev_before,
        'state_mid_crash': mid,
        'state_after_first_reconcile': after_rec1,
        'state_after_second_reconcile': after_rec2,
        'second_reconcile_idempotent': state_unchanged(after_rec1, after_rec2),
    }


def test_restore_recovery_interrupt() -> dict:
    setup_clone()
    apply_record(RECORD_A, 'Restore interrupt baseline 0730')
    second = apply_record(RECORD_A, 'Restore interrupt edited 0730')
    rev_before = revision_of(RECORD_A)
    backup = second['body'].get('backup')
    save_evidence('restore_recovery_interrupt', 'before_restore')
    crashed = run_cli(
        ['catalog-edit-restore', TABLE, backup, '--record-id', RECORD_A],
        crash='restore_post_canonical_pre_revision',
    )
    save_evidence('restore_recovery_interrupt', 'interrupted_restore')
    rec1 = run_cli(['catalog-edit-reconcile'], crash='reconcile_mid_restore')
    injector_fired = 'reconcile_mid_restore' in (rec1.stderr or '') + (rec1.stdout or '')
    save_evidence('restore_recovery_interrupt', 'interrupted_recovery')
    rec1b = run_cli(['catalog-edit-reconcile']) if rec1.returncode != 0 else rec1
    after1 = persistent_state_snapshot()
    save_evidence('restore_recovery_interrupt', 'first_recovered')
    _parse_stdout(run_cli(['catalog-edit-reconcile']).stdout)
    after2 = persistent_state_snapshot()
    save_evidence('restore_recovery_interrupt', 'second_recovered')
    state = _parse_stdout(run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_A]).stdout)
    return {
        'restore_crash_exit': crashed.returncode,
        'recovery_interrupt_exit': rec1.returncode,
        'injector_fired': injector_fired and rec1.returncode != 0,
        'purpose_is_baseline': state['document'].get('purpose') == 'Restore interrupt baseline 0730',
        'monotonic_revision': int(state.get('revision', 0)) == rev_before + 1,
        'second_reconcile_idempotent': state_unchanged(after1, after2),
        'recovery_completed_after_retry': rec1b.returncode == 0,
    }


def test_schema_negatives() -> dict:
    setup_clone()
    state = _parse_stdout(run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_A]).stdout)
    before = persistent_state_snapshot()

    def try_apply(mutator: Callable[[dict], None], label: str, *, expect_sub: str | None = None) -> dict:
        doc = copy.deepcopy(state['document'])
        mutator(doc)
        proc = run_cli(
            [
                'catalog-edit-apply',
                TABLE,
                state['sha256'],
                json.dumps(doc),
                '--record-id',
                RECORD_A,
                '--next-revision',
                str(state['revision'] + 1),
                '--operation-id',
                f'neg-{label}-{uuid.uuid4().hex[:6]}',
            ]
        )
        after = persistent_state_snapshot()
        err = proc.stderr + proc.stdout
        reason_matches = expect_sub in err if expect_sub else proc.returncode != 0
        return {
            'label': label,
            'rejected': proc.returncode != 0,
            'zero_effect': before == after,
            'reason_matches': reason_matches,
        }

    cases = [
        (lambda d: d.pop('evidence_ids'), 'missing_evidence_ids', 'evidence_ids'),
        (lambda d: d.__setitem__('aliases', [1]), 'integer_alias', 'aliases'),
        (lambda d: d.__setitem__('observed_condition', {'bad': True}), 'object_observed_condition', 'observed_condition must be string'),
        (lambda d: d.__setitem__('source_record_ids', None), 'null_source_record_ids', 'source_record_ids'),
        (lambda d: d.__setitem__('purpose', None), 'null_purpose', 'purpose must be string'),
        (lambda d: d.__setitem__('boundary', None), 'null_boundary', 'boundary must be string'),
        (lambda d: d.__setitem__('aliases', ['dup', 'dup']), 'duplicate_aliases', 'unique'),
        (
            lambda d: d.__setitem__(
                'evidence_ids',
                (d.get('evidence_ids') or []) + [(d.get('evidence_ids') or ['ev_dup'])[0]],
            ),
            'duplicate_evidence',
            'unique',
        ),
        (
            lambda d: (
                lambda ids: d.__setitem__('source_record_ids', ids + [ids[0]])
            )(
                list(d.get('source_record_ids') or [])
                or [
                    json.loads((CLONE / 'data' / 'source-records.json').read_text())['records'][0]['id']
                ]
            ),
            'duplicate_source_refs',
            'unique',
        ),
        (lambda d: d.__setitem__('fit', None), 'null_fit', 'fit must be string when present'),
    ]
    results = [try_apply(fn, label, expect_sub=sub) for fn, label, sub in cases]
    missing_next = run_cli(
        [
            'catalog-edit-apply',
            TABLE,
            state['sha256'],
            json.dumps(state['document']),
            '--record-id',
            RECORD_A,
            '--operation-id',
            f'neg-no-rev-{uuid.uuid4().hex[:6]}',
        ]
    )
    after_all = persistent_state_snapshot()
    save_evidence('schema_negatives', 'final')
    return {
        'cases': results,
        'all_rejected_with_zero_effect': all(r['rejected'] and r['zero_effect'] and r['reason_matches'] for r in results),
        'missing_next_revision_rejected': missing_next.returncode != 0,
        'inventory_unchanged': before['components_sha256'] == after_all['components_sha256'],
    }


def test_schema_pure_legitimate_control() -> dict:
    setup_clone()
    sys.path.insert(0, str(ROOT / 'tools'))
    from catalog_reference_validation import validate_component_record_contract

    state = _parse_stdout(run_cli(['catalog-edit-state', TABLE, '--record-id', RECORD_A]).stdout)
    doc = state['document']
    try:
        validate_component_record_contract(doc, doc)
        ok = True
        err = None
    except ValueError as exc:
        ok = False
        err = str(exc)
    dup_alias_doc = {**doc, 'aliases': ['dup-pure-0730', 'dup-pure-0730']}
    try:
        validate_component_record_contract(doc, dup_alias_doc)
        dup_fail = False
    except ValueError:
        dup_fail = True
    null_purpose = {**doc, 'purpose': None}
    try:
        validate_component_record_contract(doc, null_purpose)
        null_fail = False
    except ValueError:
        null_fail = True
    no_fit = {k: v for k, v in doc.items() if k != 'fit'}
    try:
        validate_component_record_contract(no_fit, no_fit)
        fit_absent_ok = True
    except ValueError:
        fit_absent_ok = False
    null_fit = {**doc, 'fit': None}
    try:
        validate_component_record_contract(doc, null_fit)
        null_fit_fail = False
    except ValueError:
        null_fit_fail = True
    return {
        'legitimate_passes': ok,
        'duplicate_alias_rejects': dup_fail,
        'null_purpose_rejects': null_fail,
        'fit_absent_allowed': fit_absent_ok,
        'null_fit_rejects': null_fit_fail,
        'error': err,
    }


def main() -> int:
    global RUN_EVIDENCE
    run_id = str(uuid.uuid4())
    sys.path.insert(0, str(ROOT / 'tools'))
    from canonical_transaction_guard_mocks import run_four_guard_boundary_regression, run_pure_guard_mocks

    four_guard = run_four_guard_boundary_regression()
    guard_failures = run_pure_guard_mocks()
    if guard_failures:
        fail_path = REPORTS / 'workflow-core-failures' / f'{DELIVERY}-guard-{run_id[:8]}.json'
        fail_path.write_text(json.dumps({'guard_failures': guard_failures}, indent=2) + '\n')
        print('guard mocks failed:', guard_failures, file=sys.stderr)
        return 2
    from canonical_transaction_evidence import EvidenceStore
    from canonical_transaction_invariants import (
        generate_control_coverage,
        validate_full_acceptance,
        validate_passing_baseline,
    )
    from canonical_transaction_spec import REQUIRED_EVIDENCE_STAGES

    evidence_root = ROOT / 'app' / '.data' / DELIVERY / 'evidence'
    RUN_EVIDENCE = EvidenceStore(evidence_root, CLONE, run_id)
    failed_attempts: list[dict] = []
    for p in sorted(REPORTS.glob('workflow-core-failures/canonical-transaction*.json')):
        failed_attempts.append({'path': str(p.relative_to(ROOT)), 'sha256': sha256_file(p)})
    for pointer in (
        REPORTS / 'canonical-transaction-schema-receipt.json',
        REPORTS / 'canonical-transaction-correction-receipt.json',
        REPORTS / 'canonical-transaction-proof-receipt.json',
    ):
        if pointer.is_file():
            failed_attempts.append({'prior_pointer': str(pointer.relative_to(ROOT)), 'sha256': sha256_file(pointer)})
    failed_attempts.append(
        {
            'note': 'historical_owner_pass_with_independent_defects',
            'run_id': '7126aeb3-c121-4c48-b3d3-1bf888fcf8fb',
            'delivery': 'canonical-transaction-proof-20261010-0743',
        }
    )
    failed_attempts.append(
        {
            'note': 'owner_pass_independent_ts09_ts11_failed_guard_mocks_post_receipt',
            'run_id': '246af411-a713-435c-b872-ae32c044ab6c',
            'delivery': 'canonical-transaction-enforcement-20261010-0816',
        }
    )
    failed_attempts.append(
        {
            'note': 'owner_failed_control_invalid_nonzero',
            'run_id': '69b8e37b-3f91-4350-8125-4f2ccc94ca3e',
            'delivery': 'canonical-transaction-enforcement-20261010-0816',
        }
    )
    failed_attempts.append(
        {
            'note': 'owner_pass_independent_relation_guards_residual',
            'run_id': '40ded520-af4a-4452-9da5-4cab8b320d7a',
            'delivery': 'canonical-transaction-enforcement-20261010-0828',
        }
    )
    for rid in ('b2194176', '8aff89eb', '57bc53b6', '63725caa'):
        failed_attempts.append({'note': 'intermediate_proof_run', 'run_id_prefix': rid})
    cases: dict = {'four_guard_regression': four_guard}
    err: Exception | None = None
    try:
        cases['source_inventory_audit'] = test_audit_inventory()
        cases['schema_pure'] = test_schema_pure_legitimate_control()
        cases['rollback_preserves'] = test_rollback_preserves_nonzero_revision()
        cases['dual_lock'] = test_component_and_metadata_under_one_lock()
        cases['distinct_records'] = test_distinct_records_both_preserved()
        cases['same_op_concurrent'] = test_same_op_concurrent()
        cases['distinct_op_same_record'] = test_distinct_op_same_record()
        cases['changed_payload_collision'] = test_changed_payload_collision()
        cases['post_oplog_rollback_retry'] = test_post_oplog_rollback_retry()
        cases['replay_after_newer'] = test_replay_after_newer()
        cases['crash_stages'] = test_crash_stages_matrix()
        cases['restore_handler'] = test_restore_handler()
        cases['restore_crash_and_recovery'] = test_restore_crash_and_recovery()
        cases['restore_recovery_interrupt'] = test_restore_recovery_interrupt()
        cases['schema_negatives'] = test_schema_negatives()
        cases['evidence_index'] = RUN_EVIDENCE.case_index()
        cases['validation'] = {'baseline': validate_passing_baseline(cases)}
        baseline_ok, baseline_failures = cases['validation']['baseline']
        cases['control_coverage'] = generate_control_coverage(baseline_ok, cases)
        cases['spec'] = {'required_evidence_stages': REQUIRED_EVIDENCE_STAGES}
        cases['final_effect_snapshot'] = persistent_state_snapshot()
    except Exception as exc:
        err = exc
        failed_attempts.append({'at': utc_now(), 'error': str(exc)})
    ok, failures = (
        validate_full_acceptance(cases, evidence_root / run_id) if not err else (False, ['exception'])
    )
    if err:
        failures.append(str(err))
    receipt = {
        'delivery_id': DELIVERY,
        'prior_delivery_id': PRIOR_DELIVERY,
        'run_id': run_id,
        'at': utc_now(),
        'owner_chat': OWNER_CHAT,
        'milestone_scope': 'TS09/TS11 four final guard boundaries only (failure intent, targets_path bool, required derived set, exact evidence index)',
        'prior_reviews_acknowledged': [
            'reports/independent-transaction-relations-review.json',
            'reports/independent-transaction-relations-review.md',
        ],
        'ts03_ts07_ts08': 'preserved_verified_implementation_not_reworked',
        'owner_verification': 'passed' if ok else 'failed',
        'independent_verification': 'not_claimed',
        'source_identity': source_identity(),
        'cases': cases,
        'failures': failures,
        'overall': 'passed' if ok else 'failed',
        'full_completion': False,
        'broader_gates_still_pending': BROADER_GATES_PENDING,
        'failed_attempt_history': failed_attempts,
        'evidence_root': str((evidence_root / run_id).relative_to(ROOT)),
        'isolated_clone': str(CLONE.relative_to(ROOT)),
        'next_permitted_action': 'Scoped independent review of this four-guard receipt; broader browser/draft/sync/LKG/derived/cleanup/fresh-agent/trace/visual gates remain next.',
    }
    if not ok:
        fail_path = REPORTS / 'workflow-core-failures' / f'{DELIVERY}-{run_id[:8]}.json'
        fail_path.write_text(json.dumps(cases, indent=2) + '\n')
        receipt['failure_artifact'] = str(fail_path.relative_to(ROOT))
    from receipt_immutable import append_manifest, write_final_receipt_once

    rel = str((RUN_RECEIPTS / f'{DELIVERY}-{run_id}.json').relative_to(ROOT))
    _, digest = write_final_receipt_once(RUN_RECEIPTS / f'{DELIVERY}-{run_id}.json', receipt)
    pointer = {'delivery_id': DELIVERY, 'run_id': run_id, 'immutable_receipt_path': rel, 'content_sha256': digest}
    append_manifest(MANIFEST, pointer)
    receipt_name = 'transaction-final-four-guards-receipt.json'
    (REPORTS / receipt_name).write_text(json.dumps(pointer, indent=2) + '\n')
    (REPORTS / 'canonical-transaction-enforcement-receipt.json').write_text(json.dumps(pointer, indent=2) + '\n')
    (REPORTS / 'canonical-transaction-evidence-receipt.json').write_text(json.dumps(pointer, indent=2) + '\n')
    checkpoint = ROOT / 'work' / 'supervision' / f'{DELIVERY}-checkpoint.txt'
    checkpoint.write_text(
        '\n'.join(
            [
                f'Owner checkpoint {DELIVERY} ({receipt["at"]})',
                'Receipt: reports/transaction-final-four-guards-receipt.json',
                f'Run: {run_id}',
                f'Overall: {receipt["overall"]}',
                'full_completion: false',
                'Next: independent verification; broader gates pending.',
                f'Failures: {failures}',
            ]
        )
        + '\n'
    )
    print(json.dumps({'overall': receipt['overall'], 'run_id': run_id, 'failures': failures}, indent=2))
    if err:
        raise err
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
