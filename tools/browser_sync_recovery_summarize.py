"""Strict acceptance summarize for browser-sync-recovery delivery."""
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


def summarize_browser_sync_recovery(cases: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    prep = cases.get('catalog_preparation') or cases.get('clone_manifest') or {}
    recon = prep.get('reconciliation') or {}
    if recon.get('reconciliation_passed') is not True:
        failures.append('catalog_preparation_reconciliation')
    if recon.get('validation_passed') is not True:
        failures.append('catalog_preparation_validation')
    if recon.get('manifests_equal') is not True:
        failures.append('catalog_preparation_manifest_mismatch')
    iso = recon.get('isolation') or {}
    if iso.get('isolation_passed') is not True:
        failures.append('catalog_preparation_isolation')
    if isinstance(recon.get('missing_path_count'), int) and recon.get('missing_path_count') != 0:
        failures.append('catalog_preparation_missing_paths')
    if isinstance(recon.get('extra_component_md_count'), int) and recon.get('extra_component_md_count') != 0:
        failures.append('catalog_preparation_extra_paths')
    prep_cleanup = cases.get('preparation_group_cleanup') or {}
    if prep_cleanup.get('group_clean') is not True:
        failures.append('preparation_group_cleanup')

    build = cases.get('build_quality') or {}
    failures.extend(_int_eq(build, 'build_exit', 0))
    if build.get('build_timed_out') is True:
        failures.append('build_timed_out')
    if build.get('used_process_group_bounded_helper') is not True:
        failures.append('build_not_bounded_helper')
    if build.get('build_exit') == 0:
        failures.extend(_int_eq(build, 'lint_exit', 0))
        failures.extend(_int_eq(build, 'typecheck_exit', 0))
    if not build.get('build_id_sha256'):
        failures.append('build_id_sha256')

    browser = cases.get('browser') or {}
    for key in (
        'late_response_mode_switch_passed',
        'draft_blocks_stale_preview_apply',
        'disk_auto_sync_passed',
        'malformed_json_shows_lkg',
        'frozen_preview_matches_apply',
        'component_edit_disk_derived_match',
        'metadata_edit_disk_match',
        'metadata_ui_passed',
        'port_refused_after_stop',
        'restart_pid_changed',
        'persisted_after_restart_fresh_fetch',
        'runtime_fixture_matches',
        'server_stop_reaped',
    ):
        failures.extend(_bool_true(browser, key))
    failures.extend(_int_eq(browser, 'exit', 0))
    if browser.get('overall') != 'passed':
        failures.append('browser_overall')

    snap = cases.get('final_run_snapshot') or {}
    failures.extend(_bool_true(snap, 'snapshotted'))
    md_count = snap.get('component_markdown_count')
    if type(md_count) is not int or md_count < 2351:
        failures.append('final_snapshot_component_md_count')
    manifest = snap.get('content_hash_manifest') or {}
    if not isinstance(manifest, dict) or not manifest.get('data/components.json'):
        failures.append('final_snapshot_canonical_hash')
    if not manifest.get('data/catalog-metadata.json'):
        failures.append('final_snapshot_metadata_hash')

    to = cases.get('timeout_production_path') or {}
    failures.extend(_bool_true(to, 'timeout_triggered'))
    failures.extend(_bool_true(to, 'child_reaped'))

    guards = cases.get('four_guard_regression') or {}
    failures.extend(_bool_true(guards, 'all_passed'))

    orig = cases.get('original_hashes_unchanged') or {}
    failures.extend(_bool_true(orig, 'unchanged'))

    neg = cases.get('negative_controls') or {}
    failures.extend(_bool_true(neg, 'each_intended_failure'))

    bind = cases.get('source_build_binding') or {}
    failures.extend(_bool_true(bind, 'pre_post_sources_stable'))
    if bind.get('served_build_id_before') != bind.get('served_build_id_after'):
        failures.append('build_id_changed_unexpectedly')

    return not failures, failures


def flip_baseline_field(baseline: dict, path: str, bad: Any) -> dict:
    out = copy.deepcopy(baseline)
    parts = path.split('.')
    cur: Any = out
    for part in parts[:-1]:
        cur = cur[part]
    cur[parts[-1]] = bad
    return out
