"""Pure no-write guard checks before expensive regression runs."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _stage_under_data(name: str) -> Path:
    root = ROOT / 'app' / '.data' / name
    root.mkdir(parents=True, exist_ok=True)
    return root


def run_four_guard_boundary_regression() -> dict[str, Any]:
    """Exact four TS09/TS11 boundary controls; must all pass before producer."""
    import sys

    sys.path.insert(0, str(ROOT / 'tools'))
    from canonical_transaction_evidence import recompute_manifest_sha256, verify_evidence_contract, verify_stage_dir
    from canonical_transaction_invariants import _verify_control_inventory
    from canonical_transaction_registry import FOUR_GUARD_BOUNDARY_IDS, expected_control_ids
    from canonical_transaction_spec import RECORD_A_MD_REL, REQUIRED_EVIDENCE_STAGES, SCHEMA_NEGATIVE_LABELS as LABELS

    results: dict[str, bool] = {}

    unrelated = {
        'complete': True,
        'expected_control_count': len(expected_control_ids()),
        'inventory': [
            {
                'control_id': 'so.exit_a:missing',
                'invariant_id': 'so.exit_a',
                'path': 'same_op_concurrent.exit_a',
                'mutation': 'missing',
                'still_passed': False,
                'intended_rejection': True,
                'failures': ['unrelated failure'],
                'targets_path': True,
            }
        ],
    }
    results[FOUR_GUARD_BOUNDARY_IDS[0]] = bool(_verify_control_inventory({'control_coverage': unrelated}))

    integer_target = {
        'complete': True,
        'expected_control_count': len(expected_control_ids()),
        'inventory': [
            {
                'control_id': 'so.exit_a:missing',
                'invariant_id': 'so.exit_a',
                'path': 'same_op_concurrent.exit_a',
                'mutation': 'missing',
                'still_passed': False,
                'intended_rejection': True,
                'failures': ['same_op_concurrent.exit_a: expected int got NoneType'],
                'targets_path': 1,
            }
        ],
    }
    results[FOUR_GUARD_BOUNDARY_IDS[1]] = bool(_verify_control_inventory({'control_coverage': integer_target}))

    omitted_md = _stage_under_data('_guard_omitted_md_manifest')
    st = omitted_md / 'stage'
    try:
        if st.exists():
            shutil.rmtree(st)
        st.mkdir()
        body = {
            'files': {'data/components.json': {'sha256': 'a' * 64, 'bytes': 1}},
            'absent': [],
            'journal': {'present': False, 'bytes_sha256': None},
            'derived': {
                'views/Alex_System_Foundation.xlsx': {'sha256': 'b' * 64, 'bytes': 1},
                'docs/COMPONENT_INDEX.md': {'sha256': 'c' * 64, 'bytes': 1},
            },
        }
        body['manifest_sha256'] = recompute_manifest_sha256(body)
        (st / 'manifest.json').write_text(json.dumps({'manifest': body}))
        (st / 'data__components.json').write_text('{}')
        key = RECORD_A_MD_REL.replace('/', '__')
        (st / key).write_text('# md')
        results[FOUR_GUARD_BOUNDARY_IDS[2]] = bool(verify_stage_dir(st))
    finally:
        shutil.rmtree(omitted_md, ignore_errors=True)

    idx = {'run_id': 'rid', 'root': 'app/.data/x/evidence/rid', 'cases': {'unexpected_case': []}}
    root = ROOT / 'app' / '.data' / 'x' / 'evidence' / 'rid'
    results[FOUR_GUARD_BOUNDARY_IDS[3]] = bool(
        verify_evidence_contract(idx, REQUIRED_EVIDENCE_STAGES, expected_run_id='rid', evidence_run_root=root)
    )

    return {'controls': results, 'all_passed': all(results.values())}


def run_pure_guard_mocks() -> list[str]:
    import sys

    sys.path.insert(0, str(ROOT / 'tools'))
    from canonical_transaction_evidence import recompute_manifest_sha256, verify_evidence_contract, verify_stage_dir
    from canonical_transaction_invariants import generate_control_coverage, validate_passing_baseline
    from canonical_transaction_spec import RECORD_A_MD_REL, REQUIRED_EVIDENCE_STAGES, SCHEMA_NEGATIVE_LABELS as LABELS

    failures: list[str] = []

    four = run_four_guard_boundary_regression()
    if not four['all_passed']:
        for cid, ok in four['controls'].items():
            if not ok:
                failures.append(f'guard boundary {cid} did not reject as required')

    if 'duplicate_source_refs' not in LABELS:
        failures.append('schema label duplicate_source_refs missing from spec')

    minimal_baseline = {
        'crash_stages': {'stages': {}},
        'same_op_concurrent': {'final_after_sha256': '0' * 64, 'canonical_components_sha256': 'f' * 64},
        'evidence_index': {'cases': {'x': ['y']}, 'run_id': 'r', 'root': 'app/.data/x/evidence/r'},
    }
    ok, _ = validate_passing_baseline(minimal_baseline)
    if ok:
        failures.append('guard: unrelated final_after_sha256 must fail baseline')

    cov = generate_control_coverage(False, {})
    if cov.get('complete'):
        failures.append('guard: baseline_invalid must not complete controls')

    guard_root = _stage_under_data('_guard_mock_stage')
    stage = guard_root / 'stage'
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    try:
        fake_manifest = {
            'manifest': {
                'files': {},
                'absent': ['data/components.json'],
                'journal': {'bytes_sha256': None, 'present': False},
                'derived': {'views/Alex_System_Foundation.xlsx': None},
                'manifest_sha256': 'dead' * 16,
            }
        }
        (stage / 'manifest.json').write_text(json.dumps(fake_manifest))
        (stage / 'views__Alex_System_Foundation.xlsx.absent').write_text('')
        (stage / 'data__components.json.absent').write_text('')
        if not verify_stage_dir(stage):
            failures.append('guard: forged manifest_sha256 must fail verify_stage_dir')
    finally:
        shutil.rmtree(guard_root, ignore_errors=True)

    return failures
