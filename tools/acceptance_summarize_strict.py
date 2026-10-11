"""Fail-closed summarize helpers and table-driven negative controls."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Callable

BENIGN = 'LOCAL-SCREENING-OK'


def _require_bool_true(block: dict | None, key: str) -> list[str]:
    if not isinstance(block, dict):
        return [f'{key}_missing_block']
    if block.get(key) is not True:
        return [key]
    return []


def _require_int_exact(block: dict | None, key: str, expected: int) -> list[str]:
    if not isinstance(block, dict):
        return [f'{key}_missing_block']
    val = block.get(key)
    if type(val) is not int or isinstance(val, bool):
        return [f'{key}_type']
    if val != expected:
        return [f'{key}_value_{val}']
    return []


def _typed_export_block(block: dict | None, *, expect_exit: int | None = None) -> list[str]:
    failures: list[str] = []
    if not isinstance(block, dict):
        return ['missing_block']
    failures.extend(_require_int_exact(block, 'exit', expect_exit) if expect_exit is not None else [])
    for key in ('canary_removed', 'nonempty', 'benign_marker'):
        failures.extend(_require_bool_true(block, key))
    if block.get('json_shape') is not True:
        failures.append('json_shape')
    return failures


def _validate_catalog_export_block(block: dict | None) -> list[str]:
    failures: list[str] = []
    if not isinstance(block, dict):
        return ['catalog_export_missing']
    failures.extend(_require_int_exact(block, 'exit', 0))
    failures.extend(_require_bool_true(block, 'handler_reached'))
    failures.extend(_require_bool_true(block, 'has_diagnostic_marker'))
    failures.extend(_require_bool_true(block, 'canary_removed'))
    if block.get('handler') != 'catalog-export':
        failures.append('catalog_export_handler')
    if not isinstance(block.get('completeness'), dict):
        failures.append('catalog_export_completeness')
    return failures


def _validate_catalog_edit_block(block: dict | None, *, handler: str) -> list[str]:
    failures: list[str] = []
    if not isinstance(block, dict):
        return [f'{handler}_missing']
    failures.extend(_require_int_exact(block, 'exit', 0))
    failures.extend(_require_bool_true(block, 'handler_reached'))
    failures.extend(_require_bool_true(block, 'has_diagnostic_marker'))
    failures.extend(_require_bool_true(block, 'canary_removed'))
    if block.get('handler') != handler:
        failures.append(f'{handler}_identity')
    if block.get('parser_error') is True:
        failures.append(f'{handler}_parser_substitute')
    if handler == 'catalog-edit-state':
        if block.get('path') != 'work/reliability/synthetic-sync-marker.json':
            failures.append('edit_state_path')
        if not isinstance(block.get('document'), dict):
            failures.append('edit_state_document')
        if type(block.get('revision')) is not int or isinstance(block.get('revision'), bool):
            failures.append('edit_state_revision')
    if handler == 'catalog-edit-preview':
        if block.get('valid') is not True:
            failures.append('edit_preview_shape')
        if not isinstance(block.get('preview'), dict):
            failures.append('edit_preview_document')
    if handler == 'catalog-edit-apply':
        if not isinstance(block.get('applied_revision'), int) or isinstance(block.get('applied_revision'), bool):
            failures.append('edit_apply_revision')
        if block.get('restored') is not True:
            failures.append('edit_apply_restored')
    return failures


def _validate_catalog_edit_error_block(block: dict | None, *, kind: str) -> list[str]:
    failures: list[str] = []
    if not isinstance(block, dict):
        return [f'{kind}_missing']
    failures.extend(_require_int_exact(block, 'exit', 1))
    failures.extend(_require_bool_true(block, 'handler_reached'))
    failures.extend(_require_bool_true(block, 'has_diagnostic_marker'))
    failures.extend(_require_bool_true(block, 'handler_error'))
    if block.get('parser_error') is True:
        failures.append(f'{kind}_parser_substitute')
    if block.get('error_kind') != kind:
        failures.append(f'{kind}_label')
    if kind == 'edit_canary_input_error':
        failures.extend(_require_bool_true(block, 'canary_removed'))
        failures.extend(_require_bool_true(block, 'request_had_canary'))
    if kind == 'edit_stale_revision_error':
        if block.get('request_had_canary') is True:
            failures.append('stale_error_unexpected_canary')
    return failures


def _browser_core_checks(browser: dict) -> list[str]:
    failures: list[str] = []
    if browser.get('overall') != 'passed':
        failures.append('browser_served_restart')
    failures.extend(_require_int_exact(browser, 'exit', 0))
    failures.extend(_require_bool_true(browser, 'served_process_restarted'))
    restart = browser.get('restart_stop') or {}
    failures.extend(_require_bool_true(restart, 'listenerReleased'))
    failures.extend(_require_bool_true(restart, 'portRefusedObserved'))
    failures.extend(_require_bool_true(browser, 'build_id_stable'))
    failures.extend(_require_bool_true(browser, 'ui_a_history_ok'))
    failures.extend(_require_bool_true(browser, 'ui_b_no_history'))
    failures.extend(_require_bool_true(browser, 'ui_t2_downstream_blocked_ok'))
    failures.extend(_require_bool_true(browser, 'ui_a_affected_output_ok'))
    return failures


def _catalog_core_checks(catalog: dict) -> list[str]:
    failures: list[str] = []
    failures.extend(_validate_catalog_export_block(catalog.get('export')))
    failures.extend(_validate_catalog_edit_block(catalog.get('edit_state'), handler='catalog-edit-state'))
    failures.extend(_validate_catalog_edit_block(catalog.get('edit_preview'), handler='catalog-edit-preview'))
    failures.extend(_validate_catalog_edit_block(catalog.get('edit_apply'), handler='catalog-edit-apply'))
    failures.extend(
        _validate_catalog_edit_error_block(catalog.get('edit_stale_revision_error'), kind='edit_stale_revision_error')
    )
    failures.extend(
        _validate_catalog_edit_error_block(catalog.get('edit_canary_input_error'), kind='edit_canary_input_error')
    )
    failures.extend(_require_bool_true(catalog, 'runtime_path_ok'))
    failures.extend(_require_bool_true(catalog, 'fixture_restored'))
    if not isinstance(catalog.get('isolated_db'), str) or not catalog['isolated_db']:
        failures.append('catalog_isolated_db')
    return failures


def _node_core_checks(node: dict) -> list[str]:
    failures: list[str] = []
    failures.extend(_require_int_exact(node, 'exit', 0))
    failures.extend(_require_bool_true(node, 'init_ok'))
    failures.extend(_require_bool_true(node, 'read_source_intended_error'))
    nonzero = node.get('nonzero_exit')
    if type(nonzero) is not int or isinstance(nonzero, bool) or nonzero == 0:
        failures.append('node_bridge_nonzero_exit')
    for key in (
        'benign',
        'screened',
        'nonempty',
        'read_source_benign',
        'nonzero_json_rejected',
        'invalid_command_json_stdout',
    ):
        failures.extend(_require_bool_true(node, key))
    return failures


def summarize_emitted_boundaries_core(cases: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    plain = cases.get('diagnostic_plain_token') or {}
    for key in ('raw_detected', 'screened_absent', 'nested_absent', 'benign_marker_in_entry'):
        failures.extend(_require_bool_true(plain, key))

    apply = cases.get('python_apply_export') or {}
    failures.extend(_require_int_exact(apply, 'exit', 0))
    for key in ('has_diagnostic_marker', 'has_job_id', 'nonempty_screening_notes', 'no_token_leak'):
        failures.extend(_require_bool_true(apply, key))

    failures.extend(_catalog_core_checks(cases.get('python_catalog_export') or {}))
    failures.extend(_node_core_checks(cases.get('node_bridge') or {}))
    failures.extend(_browser_core_checks(cases.get('browser') or {}))

    recovery = cases.get('recovery_regression') or {}
    if recovery.get('overall') != 'passed':
        failures.append('recovery_regression_overall')
    failures.extend(_require_int_exact(recovery, 'exit', 0))

    return not failures, failures


def summarize_emitted_boundaries(cases: dict[str, Any]) -> tuple[bool, list[str]]:
    ok, failures = summarize_emitted_boundaries_core(cases)
    failures.extend(_validate_negative_control_report(cases.get('summarize_negative_controls'), EMITTED_BOUNDARIES_FLIPS))
    return not failures, failures


def summarize_recovery_real_paths_core(cases: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    dep = cases.get('recovery_dependency') or {}
    for key in ('corrected_task_blocked', 'blockers_include_t1', 'next_not_corrected_downstream', 'diagnostic_marker'):
        failures.extend(_require_bool_true(dep, key))

    emit = cases.get('emission_boundaries') or {}
    failures.extend(_require_bool_true(emit, 'raw_event_contains_canary'))
    failures.extend(_require_bool_true(emit, 'raw_trace_label_contains_canary'))
    for key in (
        'events_export',
        'trace_list_export',
        'trace_get_export',
        'list_jobs_export',
        'recover_export',
        'read_source_error_boundary',
        'diagnose_text',
    ):
        failures.extend(
            f'emit_{key}_{f}'
            for f in _typed_export_block(emit.get(key), expect_exit=None if key == 'read_source_error_boundary' else 0)
        )
        block = emit.get(key) or {}
        failures.extend(_require_int_exact(block, 'exit', 1 if key == 'read_source_error_boundary' else 0))

    failures.extend(_require_bool_true(emit, 'stderr_read_source_screened'))

    node = cases.get('node_bridge') or {}
    failures.extend(_node_core_checks(node))
    for key in ('benign_required', 'screened_required', 'nonempty_required', 'canary_removed'):
        failures.extend(_require_bool_true(node, key))

    browser = cases.get('browser') or {}
    if browser.get('overall') != 'passed':
        failures.append('browser_required_overall')
    failures.extend(_require_int_exact(browser, 'exit', 0))

    return not failures, failures


def summarize_recovery_real_paths(cases: dict[str, Any]) -> tuple[bool, list[str]]:
    ok, failures = summarize_recovery_real_paths_core(cases)
    failures.extend(_validate_negative_control_report(cases.get('summarize_negative_controls'), RECOVERY_REAL_PATHS_FLIPS))
    return not failures, failures


def _flip_path_key(path: list[str]) -> str:
    return '.'.join(path)


def _flip_specs(flips: list[tuple[list[str], Any]]) -> list[dict[str, Any]]:
    return [
        {'path': _flip_path_key(path), 'value_type': type(value).__name__, 'flip_value': value}
        for path, value in flips
    ]


def _flip_lookup(flips: list[tuple[list[str], Any]]) -> dict[str, Any]:
    return {_flip_path_key(path): value for path, value in flips}


def _validate_negative_control_report(
    controls: dict | None,
    flips: list[tuple[list[str], Any]],
) -> list[str]:
    expected_count = len(flips)
    expected_paths = ['.'.join(path) for path, _ in flips]
    expected_specs = _flip_specs(flips)
    if not isinstance(controls, dict):
        return ['summarize_negative_controls_missing']
    if controls.get('baseline_core_pass') is not True:
        return ['summarize_negative_controls_baseline']
    if controls.get('count') != expected_count:
        return ['summarize_negative_controls_count_field']
    cases = controls.get('cases')
    if not isinstance(cases, list) or len(cases) == 0:
        return ['summarize_negative_controls_empty']
    if len(cases) != expected_count:
        return ['summarize_negative_controls_count']
    if controls.get('all_must_fail') is not True:
        return ['summarize_negative_controls']
    reported_paths = [row.get('path') for row in cases if isinstance(row, dict)]
    if len(reported_paths) != expected_count:
        return ['summarize_negative_controls_paths']
    if len(set(reported_paths)) != expected_count:
        return ['summarize_negative_controls_duplicate_paths']
    if sorted(reported_paths) != sorted(expected_paths):
        return ['summarize_negative_controls_path_set']
    expected_by_path = _flip_lookup(flips)
    for row in cases:
        if not isinstance(row, dict):
            return ['summarize_negative_controls_row_shape']
        path = row.get('path')
        if path not in expected_by_path:
            return [f'summarize_negative_control_unknown_path_{path}']
        expected_value = expected_by_path[path]
        if row.get('must_fail') is not True:
            return [f"summarize_negative_control_must_fail_{path}"]
        if row.get('passed') is not False:
            return [f"summarize_negative_control_passed_{path}"]
        if not row.get('failures_on_mutated'):
            return [f"summarize_negative_control_no_cause_{path}"]
        if row.get('value_type') != type(expected_value).__name__:
            return [f"summarize_negative_control_row_type_{path}"]
        if row.get('flip_value') != expected_value:
            return [f"summarize_negative_control_row_flip_value_{path}"]
    spec_paths = controls.get('expected_flip_specs')
    if spec_paths != expected_specs:
        return ['summarize_negative_controls_expected_specs']
    return []


def _flip_case(base: dict[str, Any], path: list[str], value: Any) -> dict[str, Any]:
    c = copy.deepcopy(base)
    cur: Any = c
    for key in path[:-1]:
        cur = cur.setdefault(key, {})
    cur[path[-1]] = value
    return c


def run_summarize_negative_controls(
    base_cases: dict[str, Any],
    core_summarize_fn: Callable[[dict[str, Any]], tuple[bool, list[str]]],
    flips: list[tuple[list[str], Any]],
) -> dict[str, Any]:
    baseline = copy.deepcopy(base_cases)
    baseline.pop('summarize_negative_controls', None)
    baseline_ok, baseline_failures = core_summarize_fn(baseline)
    expected_specs = _flip_specs(flips)
    if not baseline_ok:
        return {
            'baseline_core_pass': False,
            'baseline_failures': baseline_failures,
            'cases': [],
            'all_must_fail': False,
            'count': 0,
            'expected_flip_specs': expected_specs,
            'flip_identities': ['.'.join(p) for p, _ in flips],
        }
    results: list[dict[str, Any]] = []
    for path, value in flips:
        mutated = _flip_case(baseline, path, value)
        ok, flip_failures = core_summarize_fn(mutated)
        results.append(
            {
                'path': _flip_path_key(path),
                'value_type': type(value).__name__,
                'flip_value': value,
                'passed': ok,
                'must_fail': True,
                'failures_on_mutated': flip_failures if not ok else [],
            }
        )
    all_failed = all(r.get('passed') is False for r in results)
    return {
        'baseline_core_pass': True,
        'baseline_failures': [],
        'cases': results,
        'all_must_fail': all_failed,
        'count': len(results),
        'expected_flip_specs': expected_specs,
        'flip_identities': [r['path'] for r in results],
    }


def load_saved_positive_baseline_from_receipt(receipt_path: Path) -> dict[str, Any]:
    receipt = json.loads(receipt_path.read_text())
    suite = receipt['cases']['emitted_boundaries_suite']
    return {
        'diagnostic_plain_token': suite['diagnostic_plain_token'],
        'python_apply_export': suite['python_apply_export'],
        'python_catalog_export': suite['python_catalog_export'],
        'node_bridge': suite['node_bridge'],
        'browser': suite['browser'],
        'recovery_regression': suite['recovery_regression'],
    }


def self_check_two_types_regression(saved_baseline: dict[str, Any] | None = None) -> dict[str, Any]:
    """Pure regression against saved passing baseline (TC02/TC04)."""
    baseline = copy.deepcopy(saved_baseline) if saved_baseline else {}
    baseline_ok, _ = summarize_emitted_boundaries_core(baseline) if baseline else (False, ['empty_baseline'])

    recovery_false = copy.deepcopy(baseline)
    recovery_false['recovery_regression'] = {**(baseline.get('recovery_regression') or {}), 'exit': False}
    recovery_false_rejected, _ = summarize_emitted_boundaries_core(recovery_false)

    generated = run_summarize_negative_controls(baseline, summarize_emitted_boundaries_core, EMITTED_BOUNDARIES_FLIPS)
    controls_valid = not bool(_validate_negative_control_report(generated, EMITTED_BOUNDARIES_FLIPS))

    wrong_type_row = copy.deepcopy(generated)
    if wrong_type_row.get('cases'):
        wrong_type_row['cases'][0] = copy.deepcopy(wrong_type_row['cases'][0])
        wrong_type_row['cases'][0]['value_type'] = 'str'
    wrong_type_rejected = bool(_validate_negative_control_report(wrong_type_row, EMITTED_BOUNDARIES_FLIPS))

    per_flip_fail = []
    for path, value in EMITTED_BOUNDARIES_FLIPS:
        mutated = _flip_case(baseline, path, value)
        ok, _ = summarize_emitted_boundaries_core(mutated)
        per_flip_fail.append({'path': _flip_path_key(path), 'still_passed': ok})

    return {
        'saved_baseline_core_pass': baseline_ok is True,
        'recovery_regression_exit_false_rejected': recovery_false_rejected is False,
        'generated_controls_valid': controls_valid,
        'control_row_wrong_flip_type_rejected': wrong_type_rejected,
        'each_declared_flip_fails': all(not row['still_passed'] for row in per_flip_fail),
        'per_flip_fail': per_flip_fail,
    }


def self_check_strict_validator() -> dict[str, Any]:
    """Direct counterexamples against validator (AB02/AB03)."""
    positive = {
        'diagnostic_plain_token': {
            'raw_detected': True,
            'screened_absent': True,
            'nested_absent': True,
            'benign_marker_in_entry': True,
        },
        'python_apply_export': {
            'exit': 0,
            'has_diagnostic_marker': True,
            'has_job_id': True,
            'nonempty_screening_notes': True,
            'no_token_leak': True,
        },
        'python_catalog_export': {'runtime_path_ok': True, 'fixture_restored': True, 'isolated_db': 'x'},
        'node_bridge': {
            'exit': 0,
            'init_ok': True,
            'read_source_intended_error': True,
            'nonzero_exit': 1,
            'benign': True,
            'screened': True,
            'nonempty': True,
            'read_source_benign': True,
            'nonzero_json_rejected': True,
            'invalid_command_json_stdout': True,
        },
        'browser': {
            'overall': 'passed',
            'exit': 0,
            'served_process_restarted': True,
            'build_id_stable': True,
            'ui_a_history_ok': True,
            'ui_b_no_history': True,
            'ui_t2_downstream_blocked_ok': True,
            'ui_a_affected_output_ok': True,
            'restart_stop': {'listenerReleased': True, 'portRefusedObserved': True},
        },
        'recovery_regression': {'overall': 'passed', 'exit': 0},
    }
    wrong_bool = copy.deepcopy(positive)
    wrong_bool['node_bridge']['screened'] = 'false'
    bool_rejected, _ = summarize_emitted_boundaries_core(wrong_bool)
    wrong_exit = copy.deepcopy(positive)
    wrong_exit['node_bridge']['exit'] = False
    exit_rejected, _ = summarize_emitted_boundaries_core(wrong_exit)
    wrong_nonzero = copy.deepcopy(positive)
    wrong_nonzero['node_bridge']['nonzero_exit'] = '0'
    nonzero_rejected, _ = summarize_emitted_boundaries_core(wrong_nonzero)
    valid_controls = {
        'baseline_core_pass': True,
        'count': len(EMITTED_BOUNDARIES_FLIPS),
        'all_must_fail': True,
        'expected_flip_specs': _flip_specs(EMITTED_BOUNDARIES_FLIPS),
        'cases': [
            {
                'path': _flip_path_key(path),
                'value_type': type(value).__name__,
                'flip_value': value,
                'passed': False,
                'must_fail': True,
                'failures_on_mutated': ['injected_failure'],
            }
            for path, value in EMITTED_BOUNDARIES_FLIPS
        ],
    }
    duplicate_cases = copy.deepcopy(valid_controls)
    duplicate_cases['cases'] = [copy.deepcopy(valid_controls['cases'][0]) for _ in EMITTED_BOUNDARIES_FLIPS]
    duplicate_rejected = bool(_validate_negative_control_report(duplicate_cases, EMITTED_BOUNDARIES_FLIPS))
    recovery_exit_false = copy.deepcopy(positive)
    recovery_exit_false['recovery_regression']['exit'] = False
    recovery_exit_rejected, _ = summarize_emitted_boundaries_core(recovery_exit_false)
    return {
        'wrong_bool_screened_rejected': bool_rejected is False,
        'wrong_exit_false_rejected': exit_rejected is False,
        'wrong_nonzero_string_rejected': nonzero_rejected is False,
        'recovery_regression_exit_false_rejected': recovery_exit_rejected is False,
        'duplicate_control_paths_rejected': duplicate_rejected,
        'positive_controls_valid': not bool(_validate_negative_control_report(valid_controls, EMITTED_BOUNDARIES_FLIPS)),
    }


EMITTED_BOUNDARIES_FLIPS: list[tuple[list[str], Any]] = [
    (['python_apply_export', 'no_token_leak'], False),
    (['node_bridge', 'screened'], False),
    (['node_bridge', 'nonempty'], False),
    (['node_bridge', 'exit'], 9),
    (['browser', 'overall'], 'failed'),
    (['browser', 'served_process_restarted'], False),
    (['browser', 'build_id_stable'], False),
    (['browser', 'restart_stop', 'portRefusedObserved'], False),
    (['recovery_regression', 'exit'], 9),
    (['diagnostic_plain_token', 'screened_absent'], False),
]

RECOVERY_REAL_PATHS_FLIPS: list[tuple[list[str], Any]] = [
    (['emission_boundaries', 'events_export', 'json_shape'], False),
    (['emission_boundaries', 'events_export', 'exit'], 9),
    (['emission_boundaries', 'list_jobs_export', 'benign_marker'], False),
    (['emission_boundaries', 'recover_export', 'canary_removed'], False),
    (['emission_boundaries', 'diagnose_text', 'nonempty'], False),
    (['node_bridge', 'benign'], False),
    (['node_bridge', 'screened'], False),
    (['node_bridge', 'nonempty'], False),
    (['browser', 'overall'], 'partial'),
    (['recovery_dependency', 'corrected_task_blocked'], False),
]
