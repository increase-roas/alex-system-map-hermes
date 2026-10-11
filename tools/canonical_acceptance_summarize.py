"""Strict typed summarize for canonical-review-fixes acceptance."""
from __future__ import annotations

import copy
from typing import Any


def _bool_true(block: dict | None, key: str) -> list[str]:
    if not isinstance(block, dict):
        return [f'{key}_block']
    if block.get(key) is not True:
        return [key]
    return []


def _int_eq(block: dict | None, key: str, expected: int) -> list[str]:
    if not isinstance(block, dict):
        return [f'{key}_block']
    val = block.get(key)
    if type(val) is not int or isinstance(val, bool):
        return [f'{key}_type']
    if val != expected:
        return [f'{key}_value']
    return []


def summarize_canonical_cases(cases: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    prod = cases.get('production_inspection') or {}
    failures.extend(_bool_true(prod, 'real_maintained_assets'))
    failures.extend(_int_eq(prod, 'exit', 0))
    clone = cases.get('clone_manifest') or {}
    if not isinstance(clone.get('copy_hashes_at_clone'), dict) or not clone['copy_hashes_at_clone']:
        failures.append('clone_manifest')
    cc = clone.get('components_cloned_count')
    if type(cc) is not int or cc < 1000:
        failures.append('components_cloned_count')
    schema = cases.get('schema_negative') or {}
    failures.extend(_bool_true(schema, 'bad_layer_rejected'))
    failures.extend(_bool_true(schema, 'zero_writes_on_bad'))
    conc = cases.get('concurrent') or {}
    failures.extend(_bool_true(conc, 'one_commit_one_conflict'))
    cross = cases.get('cross_record_concurrent') or {}
    failures.extend(_bool_true(cross, 'single_file_winner'))
    idem = cases.get('idempotent') or {}
    failures.extend(_bool_true(idem, 'idempotent_match'))
    failures.extend(_bool_true(idem, 'payload_collision_rejected'))
    replay = cases.get('replay_after_newer') or {}
    failures.extend(_bool_true(replay, 'returns_original_without_clobber'))
    crash = cases.get('crash_reconcile') or {}
    failures.extend(_bool_true(crash, 'crash_exit_nonzero'))
    failures.extend(_bool_true(crash, 'sha_restored'))
    failures.extend(_bool_true(crash, 'reconcile_idempotent'))
    derived = cases.get('canonical_derived') or {}
    failures.extend(_bool_true(derived, 'xlsx_purpose_updated'))
    failures.extend(_bool_true(derived, 'md_purpose_updated'))
    failures.extend(_bool_true(derived, 'run_proof_snapshotted'))
    meta = cases.get('metadata_doc') or {}
    failures.extend(_bool_true(meta, 'apply_exit_ok'))
    meta_ui = cases.get('metadata_doc_ui') or {}
    failures.extend(_bool_true(meta_ui, 'ui_apply_passed'))
    to = cases.get('timeout_production_path') or {}
    failures.extend(_bool_true(to, 'timeout_triggered'))
    failures.extend(_bool_true(to, 'child_reaped'))
    browser = cases.get('browser') or {}
    failures.extend(_bool_true(browser, 'disk_matches_ui'))
    failures.extend(_bool_true(browser, 'frozen_preview_matches_apply'))
    failures.extend(_int_eq(browser, 'exit', 0))
    if browser.get('overall') != 'passed':
        failures.append('browser_overall')
    build = cases.get('build_quality') or {}
    failures.extend(_int_eq(build, 'build_exit', 0))
    failures.extend(_int_eq(build, 'lint_exit', 0))
    failures.extend(_int_eq(build, 'typecheck_exit', 0))
    orig = cases.get('original_hashes_unchanged') or {}
    failures.extend(_bool_true(orig, 'unchanged'))
    reg = cases.get('strict_types_regression') or {}
    failures.extend(_bool_true(reg, 'saved_baseline_core_pass'))
    flip = cases.get('canonical_field_flips') or {}
    failures.extend(_bool_true(flip, 'each_flip_fails'))
    return not failures, failures


def flip_one_field_baseline(baseline: dict, path: str, bad_value: Any) -> dict:
    mutated = copy.deepcopy(baseline)
    parts = path.split('.')
    cur: Any = mutated
    for part in parts[:-1]:
        cur = cur[parts.index(part)] if part in cur else cur.get(part, {})
        if not isinstance(cur, dict):
            break
    else:
        leaf = parts[-1]
        if isinstance(cur, dict):
            cur[leaf] = bad_value
    return mutated
