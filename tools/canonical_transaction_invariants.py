"""Invariant validation, control coverage, and full acceptance (registry-driven)."""
from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

from canonical_transaction_registry import (
    COUNTEREXAMPLE_REGISTRY,
    FULL_ACCEPTANCE_COUNTEREXAMPLES,
    MUTATION_VARIANTS,
    RELATION_REGISTRY,
    SCALAR_REGISTRY,
    all_controlled_entries,
    control_row_spec_by_id,
    expected_control_ids,
)
from canonical_transaction_spec import (
    COMPONENTS_TABLE_REL,
    EDIT_CRASH_STAGES,
    REQUIRED_EVIDENCE_STAGES,
    REVISION_RECORD_KEY,
    SCHEMA_NEGATIVE_LABELS,
)

HEX64 = re.compile(r'^[a-f0-9]{64}$')

ROOT = Path(__file__).resolve().parents[1]

CASES_ONLY_KEYS = frozenset({'negative_controls', 'validation', 'control_coverage', 'spec'})


def _get(obj: Any, path: str) -> Any:
    cur: Any = obj
    for part in path.split('.'):
        if isinstance(cur, list) and part.isdigit():
            idx = int(part)
            cur = cur[idx] if idx < len(cur) else None
            continue
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _cases_only(cases: dict) -> dict:
    return {k: v for k, v in cases.items() if k not in CASES_ONLY_KEYS}


def _set_path(obj: dict, path: str, value: Any) -> None:
    parts = path.split('.')
    cur: Any = obj
    for i, part in enumerate(parts[:-1]):
        nxt = parts[i + 1]
        if isinstance(cur, dict):
            if part not in cur:
                cur[part] = [] if nxt.isdigit() else {}
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit():
            cur = cur[int(part)]
    last = parts[-1]
    if isinstance(cur, dict):
        cur[last] = value
    elif isinstance(cur, list) and last.isdigit():
        cur[int(last)] = value


def _del_path(obj: dict, path: str) -> None:
    parts = path.split('.')
    cur: Any = obj
    for part in parts[:-1]:
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit():
            cur = cur[int(part)]
        else:
            return
    last = parts[-1]
    if isinstance(cur, dict) and last in cur:
        del cur[last]


def _validate_scalar_entry(cases: dict, entry: dict[str, Any]) -> str | None:
    path = entry['path']
    kind = entry['kind']
    val = _get(cases, path)
    expected = entry.get('expected')
    if kind == 'int':
        if type(val) is not int:
            return f'{path}: expected int got {type(val).__name__}'
        if expected is not None and val != expected:
            return f'{path}: expected {expected} got {val}'
    elif kind == 'nonzero_int':
        if type(val) is not int or val == 0:
            return f'{path}: expected nonzero int'
    elif kind == 'bool':
        if val is not True and val is not False:
            return f'{path}: expected bool got {type(val).__name__}'
        if expected is not None and val != expected:
            return f'{path}: expected {expected} got {val}'
    elif kind == 'hash':
        if type(val) is not str or not HEX64.match(val):
            return f'{path}: expected 64-char hex sha256'
    return None


def _check_schema_labels(cases: dict) -> list[str]:
    errors: list[str] = []
    rows = _get(cases, 'schema_negatives.cases')
    if not isinstance(rows, list):
        return ['schema_negatives.cases: must be list']
    labels = [r.get('label') for r in rows if isinstance(r, dict)]
    for required in SCHEMA_NEGATIVE_LABELS:
        if required not in labels:
            errors.append(f'schema_negatives missing label {required}')
    if len(labels) != len(SCHEMA_NEGATIVE_LABELS):
        errors.append(f'schema_negatives.cases: expected cardinality {len(SCHEMA_NEGATIVE_LABELS)} got {len(labels)}')
    return errors


def _check_crash_stage_map(cases: dict) -> list[str]:
    errors: list[str] = []
    stages = _get(cases, 'crash_stages.stages')
    if not isinstance(stages, dict) or not stages:
        return ['crash_stages.stages: required non-empty map']
    for name in EDIT_CRASH_STAGES:
        if name not in stages:
            errors.append(f'crash_stages.stages missing {name}')
    return errors


def _check_hash_canonical_binding(cases: dict) -> list[str]:
    errors: list[str] = []
    canon = _get(cases, 'same_op_concurrent.canonical_components_sha256')
    final = _get(cases, 'same_op_concurrent.final_after_sha256')
    a = _get(cases, 'same_op_concurrent.after_hash_a')
    b = _get(cases, 'same_op_concurrent.after_hash_b')
    if type(canon) is not str or not HEX64.match(canon):
        errors.append('same_op_concurrent.canonical_components_sha256: required sha256')
    else:
        if a != canon:
            errors.append('same_op_concurrent.after_hash_a must equal canonical_components_sha256')
        if b != canon:
            errors.append('same_op_concurrent.after_hash_b must equal canonical_components_sha256')
        if final != canon:
            errors.append('same_op_concurrent.final_after_sha256 must equal canonical_components_sha256')
    if _get(cases, 'same_op_concurrent.response_hashes_match_canonical') is not True:
        errors.append('same_op_concurrent.response_hashes_match_canonical: expected True')
    return errors


def _manifest_components_sha(manifest: dict) -> str | None:
    files = manifest.get('files') or {}
    comp = files.get(COMPONENTS_TABLE_REL) or {}
    sha = comp.get('sha256')
    if type(sha) is not str:
        return None
    return sha


def _evidence_root_for_cases(cases: dict, evidence_run_root: Path | None) -> Path | None:
    idx = _get(cases, 'evidence_index') or {}
    root_rel = idx.get('root')
    if root_rel:
        return (ROOT / root_rel).resolve()
    if evidence_run_root is not None:
        return evidence_run_root.resolve()
    return None


def validate_relation_bindings(cases: dict, evidence_root: Path) -> list[str]:
    from canonical_transaction_evidence import load_stage_manifest, read_revision_from_stage

    errors: list[str] = []
    base = evidence_root

    so_final = load_stage_manifest(base, 'same_op_concurrent', 'final')
    if so_final is None:
        errors.append('relation: missing evidence same_op_concurrent/final manifest')
    else:
        disk_canon = _manifest_components_sha(so_final)
        if disk_canon is None:
            errors.append('relation: same_op final evidence missing components sha256')
        canon = _get(cases, 'same_op_concurrent.canonical_components_sha256')
        if disk_canon != canon:
            errors.append('relation: same_op canonical_components_sha256 must match saved final bytes')

    oplog_final = load_stage_manifest(base, 'post_oplog_rollback_retry', 'after_retry')
    if oplog_final is None:
        errors.append('relation: missing evidence post_oplog_rollback_retry/after_retry manifest')
    else:
        disk = _manifest_components_sha(oplog_final)
        retry_sha = _get(cases, 'post_oplog_rollback_retry.retry_after_sha256')
        if disk != retry_sha:
            errors.append('relation: post_oplog retry_after_sha256 must match after_retry components hash')
        rev_case = _get(cases, 'post_oplog_rollback_retry.final_revision')
        if type(rev_case) is not int:
            errors.append('relation: post_oplog final_revision required int')
        else:
            stage_dir = base / 'post_oplog_rollback_retry' / 'after_retry'
            on_disk, err = read_revision_from_stage(stage_dir, REVISION_RECORD_KEY)
            if err:
                errors.append(f'relation: post_oplog {err}')
            elif on_disk != rev_case:
                errors.append('relation: post_oplog final_revision must match after_retry revision sidecar')

    replay_ok = _get(cases, 'replay_after_newer.same_result_hash')
    b1 = _get(cases, 'replay_after_newer.first_after_sha256')
    b2 = _get(cases, 'replay_after_newer.replay_after_sha256')
    if replay_ok is True and b1 != b2:
        errors.append('relation: replay same_result_hash requires first/replay after_sha256 equality')
    rev_case = _get(cases, 'replay_after_newer.final_revision')
    if type(rev_case) is not int:
        errors.append('relation: replay final_revision required int')
    else:
        stage_dir = base / 'replay_after_newer' / 'after_replay'
        on_disk, err = read_revision_from_stage(stage_dir, REVISION_RECORD_KEY)
        if err:
            errors.append(f'relation: replay {err}')
        elif on_disk != rev_case:
            errors.append('relation: replay final_revision must match after_replay revision sidecar')

    crash = _get(cases, 'crash_stages.stages') or {}
    for stage_name in EDIT_CRASH_STAGES:
        row = crash.get(stage_name)
        if not isinstance(row, dict):
            errors.append(f'relation: crash_stages.stages.{stage_name} required')
            continue
        if row.get('revision_restored') is True and row.get('sha_restored') is not True:
            errors.append(f'relation: crash_stages.stages.{stage_name} sha_restored required when revision_restored')
        if row.get('sha_restored') is not True:
            continue
        before_m = load_stage_manifest(base, f'crash_stage_{stage_name}', 'before_crash')
        first_m = load_stage_manifest(base, f'crash_stage_{stage_name}', 'first_recovered')
        if before_m is None or first_m is None:
            errors.append(f'relation: crash_stage_{stage_name} missing before/first evidence manifest')
            continue
        b_sha = _manifest_components_sha(before_m)
        f_sha = _manifest_components_sha(first_m)
        if b_sha is None or f_sha is None:
            errors.append(f'relation: crash_stage_{stage_name} missing components hash in evidence')
        elif b_sha != f_sha:
            errors.append(f'relation: crash_stage_{stage_name} first_recovered components must match before_crash')
        sha_before = row.get('sha_before')
        sha_after = row.get('sha_after')
        if type(sha_before) is not str or type(sha_after) is not str:
            errors.append(f'relation: crash_stages.stages.{stage_name} sha_before/sha_after required')
        elif sha_after != sha_before:
            errors.append(f'relation: crash_stages.stages.{stage_name} sha_after must equal sha_before when restored')

    return errors


def validate_passing_baseline(
    cases: dict,
    *,
    evidence_run_root: Path | None = None,
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    c = _cases_only(cases)

    failures.extend(_check_crash_stage_map(c))
    failures.extend(_check_schema_labels(c))
    failures.extend(_check_hash_canonical_binding(c))

    for entry in SCALAR_REGISTRY:
        err = _validate_scalar_entry(c, entry)
        if err:
            failures.append(err)

    evidence = _get(c, 'evidence_index')
    if not isinstance(evidence, dict) or not evidence.get('cases'):
        failures.append('evidence_index.cases: required non-empty case map')
    root = _evidence_root_for_cases(c, evidence_run_root)
    if root is not None and root.is_dir():
        failures.extend(validate_relation_bindings(c, root))
    return not failures, failures


def _mutate_kind_for_entry(entry: dict[str, Any]) -> str:
    kind = entry.get('kind')
    if kind != 'relation':
        return kind
    last = entry.get('path', '').split('.')[-1]
    if last.endswith('_sha256') or last in ('sha_before', 'sha_after', 'canonical_components_sha256'):
        return 'hash'
    if last in ('final_revision',) or last.endswith('_revision'):
        return 'int'
    if last.endswith('_exit') or last == 'crash_exit':
        return 'nonzero_int'
    return 'bool'


def _mutate_missing(c: dict, path: str) -> None:
    _del_path(c, path)


def _mutate_wrongtype(c: dict, path: str, kind: str) -> None:
    if kind in ('int', 'nonzero_int'):
        _set_path(c, path, True)
    elif kind == 'bool':
        _set_path(c, path, 1)
    elif kind == 'hash':
        _set_path(c, path, True)
    else:
        _set_path(c, path, None)


def _mutate_invalid(c: dict, path: str, kind: str, expected: Any) -> None:
    if kind == 'nonzero_int':
        _set_path(c, path, 0)
    elif kind == 'int':
        if expected is None:
            _set_path(c, path, None)
        else:
            _set_path(c, path, expected + 99)
    elif kind == 'bool':
        _set_path(c, path, not expected if isinstance(expected, bool) else False)
    elif kind == 'hash':
        _set_path(c, path, None)
    else:
        _set_path(c, path, 'invalid')


def _path_targeted(failures: list[str], path: str) -> bool:
    return any(path in f or f.startswith(path) for f in failures)


def _failures_intent_matches(failures: list[Any], path: str) -> bool:
    if not failures or not all(isinstance(f, str) and f.strip() for f in failures):
        return False
    last = path.split('.')[-1]
    prefix = path.split('.')[0] if '.' in path else path
    for msg in failures:
        if path in msg or msg.startswith(path):
            return True
        if last and last in msg:
            return True
        if msg.startswith('relation:') and prefix in msg:
            return True
        if msg.startswith('control ') and path in msg:
            return True
        if 'evidence_index.cases' in path and 'evidence_index.cases' in msg:
            return True
        if 'control_coverage' in path and 'control_coverage' in msg:
            return True
    return False


def generate_control_coverage(baseline_valid: bool, cases: dict) -> dict:
    expected_ids = expected_control_ids()
    inventory: list[dict] = []
    if not baseline_valid:
        return {
            'complete': False,
            'skipped': 'baseline_invalid',
            'inventory': inventory,
            'expected_control_count': len(expected_ids),
            'coverage_table': [],
        }
    base = _cases_only(cases)
    idx0 = cases.get('evidence_index') or {}
    evidence_run_root = (ROOT / idx0.get('root', '')).resolve() if idx0.get('root') else None
    for entry in all_controlled_entries():
        inv_id = entry['id']
        path = entry['path']
        kind = _mutate_kind_for_entry(entry)
        expected = entry.get('expected')
        for mutation in MUTATION_VARIANTS:
            control_id = f'{inv_id}:{mutation}'
            mutated = copy.deepcopy(base)
            if mutation == 'missing':
                _mutate_missing(mutated, path)
            elif mutation == 'wrongtype':
                _mutate_wrongtype(mutated, path, kind)
            else:
                _mutate_invalid(mutated, path, kind, expected)
            passed, fails = validate_passing_baseline(mutated, evidence_run_root=evidence_run_root)
            inventory.append(
                {
                    'control_id': control_id,
                    'invariant_id': inv_id,
                    'path': path,
                    'mutation': mutation,
                    'still_passed': passed,
                    'failures': fails,
                    'targets_path': True if (not passed and _path_targeted(fails, path)) else False,
                    'intended_rejection': not passed
                    and _path_targeted(fails, path)
                    and _failures_intent_matches(fails, path),
                }
            )
    for cx in COUNTEREXAMPLE_REGISTRY:
        mutated = copy.deepcopy(base)
        _set_path(mutated, cx['path'], cx['value'])
        passed, fails = validate_passing_baseline(mutated, evidence_run_root=evidence_run_root)
        inventory.append(
            {
                'control_id': cx['id'],
                'invariant_id': cx['id'],
                'path': cx['path'],
                'mutation': 'counterexample',
                'still_passed': passed,
                'failures': fails,
                'targets_path': True if _path_targeted(fails, cx['path']) else False,
                'intended_rejection': (not passed)
                and _path_targeted(fails, cx['path'])
                and _failures_intent_matches(fails, cx['path']),
            }
        )
    probe_cases = copy.deepcopy(cases)
    probe_cases['control_coverage'] = {
        'complete': True,
        'inventory': list(inventory),
        'expected_control_count': len(expected_ids),
    }
    idx0 = probe_cases.get('evidence_index') or {}
    evidence_run_root = (ROOT / idx0.get('root', 'app/.data')).resolve()
    expected_run_id = str(idx0.get('run_id', ''))
    for cx_id, path, bad in FULL_ACCEPTANCE_COUNTEREXAMPLES:
        mutated = copy.deepcopy(probe_cases)
        if cx_id == 'cx.extra_evidence_case':
            idx = mutated.setdefault('evidence_index', {})
            idx.setdefault('cases', {})
            idx['cases']['unexpected_case'] = []
        else:
            _set_path(mutated, path, bad)
        sub_errors: list[str] = []
        if path.startswith('control_coverage'):
            sub_errors.extend(_verify_control_inventory(mutated))
        if path.startswith('evidence_index'):
            from canonical_transaction_evidence import verify_evidence_contract

            idx = _get(mutated, 'evidence_index') or {}
            sub_errors.extend(
                verify_evidence_contract(
                    idx,
                    REQUIRED_EVIDENCE_STAGES,
                    expected_run_id=expected_run_id,
                    evidence_run_root=evidence_run_root,
                )
            )
        inventory.append(
            {
                'control_id': cx_id,
                'invariant_id': cx_id,
                'path': path,
                'mutation': 'full_acceptance_probe',
                'still_passed': not sub_errors,
                'failures': sub_errors,
                'targets_path': True if sub_errors else False,
                'intended_rejection': bool(sub_errors) and _failures_intent_matches(sub_errors, path),
            }
        )
    got_ids = [row['control_id'] for row in inventory]
    complete = (
        len(inventory) == len(expected_ids)
        and set(got_ids) == set(expected_ids)
        and all(row['intended_rejection'] for row in inventory)
    )
    return {
        'complete': complete,
        'inventory': inventory,
        'expected_control_count': len(expected_ids),
        'coverage_table': inventory,
        'missing_control_ids': sorted(set(expected_ids) - set(got_ids)),
        'extra_control_ids': sorted(set(got_ids) - set(expected_ids)),
    }


def _verify_control_inventory(cases: dict) -> list[str]:
    errors: list[str] = []
    expected_ids = expected_control_ids()
    row_specs = control_row_spec_by_id()
    controls = cases.get('control_coverage') or {}
    inventory = controls.get('inventory')
    if not isinstance(inventory, list) or len(inventory) == 0:
        errors.append('control_coverage.inventory: required nonempty list')
        return errors
    if controls.get('expected_control_count') != len(expected_ids):
        errors.append('control_coverage.expected_control_count mismatch registry')
    got = [row.get('control_id') for row in inventory if isinstance(row, dict)]
    if len(got) != len(set(got)):
        errors.append('control_coverage.inventory: duplicate control_id')
    missing = set(expected_ids) - set(got)
    extra = set(got) - set(expected_ids)
    if missing:
        errors.append(f'control_coverage missing ids: {sorted(missing)[:5]}...')
    if extra:
        errors.append(f'control_coverage extra ids: {sorted(extra)[:5]}...')
    allowed_mutations = set(MUTATION_VARIANTS) | {'counterexample', 'full_acceptance_probe'}
    for row in inventory:
        if not isinstance(row, dict):
            errors.append('control_coverage row must be object')
            continue
        cid = row.get('control_id')
        spec = row_specs.get(cid or '')
        if not spec:
            errors.append(f'control {cid}: unknown control_id')
            continue
        if row.get('path') != spec['path']:
            errors.append(f'control {cid}: path mismatch expected {spec["path"]}')
        if row.get('mutation') != spec['mutation']:
            errors.append(f'control {cid}: mutation mismatch expected {spec["mutation"]}')
        if row.get('mutation') not in allowed_mutations:
            errors.append(f'control {cid}: fabricated mutation label')
        if row.get('still_passed') is not False:
            errors.append(f'control {cid}: still_passed must be exactly False')
        if row.get('intended_rejection') is not True:
            errors.append(f'control {cid}: intended_rejection must be exactly True')
        fails = row.get('failures')
        path = row.get('path') or spec['path']
        if not isinstance(fails, list) or len(fails) == 0:
            errors.append(f'control {cid}: failures must be nonempty list')
        elif not _failures_intent_matches(fails, path):
            errors.append(f'control {cid}: failures do not name intended invariant/path')
        if row.get('targets_path') is not True:
            errors.append(f'control {cid}: targets_path must be exactly True')
        elif row.get('mutation') in MUTATION_VARIANTS and not _path_targeted(fails if isinstance(fails, list) else [], path):
            errors.append(f'control {cid}: targets_path inconsistent with failures')
    if controls.get('complete') is not True:
        errors.append('control_coverage.complete: expected True after strict inventory')
    return errors


def _verify_full_dict_counterexamples(cases: dict, expected_run_id: str, evidence_run_root: Path) -> list[str]:
    errors: list[str] = []
    base_ok, _ = validate_passing_baseline(_cases_only(cases))
    if not base_ok:
        return errors
    for cx_id, path, bad in FULL_ACCEPTANCE_COUNTEREXAMPLES:
        mutated = copy.deepcopy(cases)
        if cx_id == 'cx.extra_evidence_case':
            idx = mutated.setdefault('evidence_index', {})
            idx.setdefault('cases', {})
            idx['cases']['unexpected_case'] = []
        else:
            _set_path(mutated, path, bad)
        sub_errors: list[str] = []
        if path.startswith('control_coverage'):
            sub_errors.extend(_verify_control_inventory(mutated))
        if path.startswith('evidence_index'):
            from canonical_transaction_evidence import verify_evidence_contract

            idx = _get(mutated, 'evidence_index') or {}
            sub_errors.extend(
                verify_evidence_contract(
                    idx,
                    REQUIRED_EVIDENCE_STAGES,
                    expected_run_id=expected_run_id,
                    evidence_run_root=evidence_run_root,
                )
            )
        if not sub_errors:
            errors.append(f'full acceptance counterexample {cx_id} must fail')
    return errors


def validate_full_acceptance(cases: dict, evidence_run_root: Path) -> tuple[bool, list[str]]:
    from canonical_transaction_evidence import verify_evidence_contract

    ok, fails = validate_passing_baseline(cases, evidence_run_root=evidence_run_root)
    errors = list(fails)
    if not ok:
        errors.insert(0, 'baseline_invariants_failed')
    evidence_index = _get(cases, 'evidence_index') or {}
    expected_run_id = evidence_run_root.name
    errors.extend(
        verify_evidence_contract(
            evidence_index,
            REQUIRED_EVIDENCE_STAGES,
            expected_run_id=expected_run_id,
            evidence_run_root=evidence_run_root,
        )
    )
    errors.extend(validate_relation_bindings(_cases_only(cases), evidence_run_root.resolve()))
    errors.extend(_verify_control_inventory(cases))
    if ok:
        errors.extend(_verify_full_dict_counterexamples(cases, expected_run_id, evidence_run_root))
    return not errors, errors
