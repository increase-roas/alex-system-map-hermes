"""Single exhaustive declarative invariant registry (validation, controls, coverage)."""
from __future__ import annotations

from typing import Any

from canonical_transaction_spec import EDIT_CRASH_STAGES, SCHEMA_NEGATIVE_LABELS

# kind: int | bool | hash | nonzero_int | relation
# controls: if True, generate missing/wrongtype/invalid variants
# relation: named saved-byte binding evaluated when evidence_index.root is set


def _crash_fields(stage: str) -> list[dict[str, Any]]:
    p = f'crash_stages.stages.{stage}'
    return [
        {'id': f'crash.{stage}.crash_exit', 'path': f'{p}.crash_exit', 'kind': 'nonzero_int', 'controls': True},
        {'id': f'crash.{stage}.recovery_idempotent', 'path': f'{p}.recovery_state_idempotent', 'kind': 'bool', 'expected': True, 'controls': True},
        {'id': f'crash.{stage}.sha_before', 'path': f'{p}.sha_before', 'kind': 'hash', 'controls': True},
        {'id': f'crash.{stage}.sha_after', 'path': f'{p}.sha_after', 'kind': 'hash', 'controls': True},
        {'id': f'crash.{stage}.revision_restored', 'path': f'{p}.revision_restored', 'kind': 'bool', 'expected': True, 'controls': True},
        {'id': f'crash.{stage}.sha_restored', 'path': f'{p}.sha_restored', 'kind': 'bool', 'expected': True, 'controls': True},
    ]


def _schema_row_fields(i: int) -> list[dict[str, Any]]:
    p = f'schema_negatives.cases.{i}'
    return [
        {'id': f'schema.row{i}.rejected', 'path': f'{p}.rejected', 'kind': 'bool', 'expected': True, 'controls': True},
        {'id': f'schema.row{i}.zero_effect', 'path': f'{p}.zero_effect', 'kind': 'bool', 'expected': True, 'controls': True},
        {'id': f'schema.row{i}.reason_matches', 'path': f'{p}.reason_matches', 'kind': 'bool', 'expected': True, 'controls': True},
    ]


SCALAR_REGISTRY: list[dict[str, Any]] = [
    {'id': 'so.exit_a', 'path': 'same_op_concurrent.exit_a', 'kind': 'int', 'expected': 0, 'controls': True},
    {'id': 'so.exit_b', 'path': 'same_op_concurrent.exit_b', 'kind': 'int', 'expected': 0, 'controls': True},
    {'id': 'so.committed_rows', 'path': 'same_op_concurrent.committed_ledger_rows', 'kind': 'int', 'expected': 1, 'controls': True},
    {'id': 'so.invalidated_rows', 'path': 'same_op_concurrent.invalidated_ledger_rows', 'kind': 'int', 'expected': 0, 'controls': True},
    {'id': 'so.final_revision', 'path': 'same_op_concurrent.final_revision', 'kind': 'int', 'expected': 1, 'controls': True},
    {'id': 'so.final_after_sha256', 'path': 'same_op_concurrent.final_after_sha256', 'kind': 'hash', 'controls': True},
    {'id': 'so.after_hash_a', 'path': 'same_op_concurrent.after_hash_a', 'kind': 'hash', 'controls': True},
    {'id': 'so.after_hash_b', 'path': 'same_op_concurrent.after_hash_b', 'kind': 'hash', 'controls': True},
    {'id': 'so.canonical_sha', 'path': 'same_op_concurrent.canonical_components_sha256', 'kind': 'hash', 'controls': True},
    {'id': 'so.one_commit', 'path': 'same_op_concurrent.one_commit', 'kind': 'bool', 'expected': True, 'controls': True},
    {'id': 'so.response_bind', 'path': 'same_op_concurrent.response_hashes_match_canonical', 'kind': 'bool', 'expected': True, 'controls': True},
    {'id': 'distop.exit_winner', 'path': 'distinct_op_same_record.exit_winner', 'kind': 'int', 'expected': 0, 'controls': True},
    {'id': 'distop.exit_loser', 'path': 'distinct_op_same_record.exit_loser', 'kind': 'int', 'expected': 1, 'controls': True},
    {'id': 'distop.rev_delta', 'path': 'distinct_op_same_record.winner_revision_delta', 'kind': 'int', 'expected': 1, 'controls': True},
    {'id': 'distop.loser_committed', 'path': 'distinct_op_same_record.loser_committed_rows', 'kind': 'int', 'expected': 0, 'controls': True},
    {'id': 'distop.loser_journal', 'path': 'distinct_op_same_record.loser_journal_rows', 'kind': 'int', 'expected': 0, 'controls': True},
    {'id': 'distop.loser_zero', 'path': 'distinct_op_same_record.loser_zero_effects', 'kind': 'bool', 'expected': True, 'controls': True},
    {'id': 'rollback.idempotent', 'path': 'rollback_preserves.recovery_state_idempotent', 'kind': 'bool', 'expected': True, 'controls': True},
    {'id': 'rollback.b_crash_exit', 'path': 'rollback_preserves.b_crash_exit', 'kind': 'nonzero_int', 'controls': True},
    {'id': 'dual.both', 'path': 'dual_lock.both_committed', 'kind': 'bool', 'expected': True, 'controls': True},
    {'id': 'dual.comp_exit', 'path': 'dual_lock.component_exit', 'kind': 'int', 'expected': 0, 'controls': True},
    {'id': 'dual.meta_exit', 'path': 'dual_lock.metadata_exit', 'kind': 'int', 'expected': 0, 'controls': True},
    {'id': 'dual.comp_rev', 'path': 'dual_lock.component_revision', 'kind': 'int', 'expected': 1, 'controls': True},
    {'id': 'dual.meta_rev', 'path': 'dual_lock.metadata_revision', 'kind': 'int', 'expected': 1, 'controls': True},
    {'id': 'distinctrec.both', 'path': 'distinct_records.both_preserved', 'kind': 'bool', 'expected': True, 'controls': True},
    {'id': 'schema.all_zero', 'path': 'schema_negatives.all_rejected_with_zero_effect', 'kind': 'bool', 'expected': True, 'controls': True},
    {'id': 'schema.missing_next', 'path': 'schema_negatives.missing_next_revision_rejected', 'kind': 'bool', 'expected': True, 'controls': True},
    {'id': 'restore.rev_before', 'path': 'restore_handler.revision_before_restore', 'kind': 'int', 'expected': 2, 'controls': True},
    {'id': 'restore.rev_after', 'path': 'restore_handler.revision_after_restore', 'kind': 'int', 'expected': 3, 'controls': True},
    {'id': 'restore.monotonic', 'path': 'restore_handler.monotonic_revision', 'kind': 'bool', 'expected': True, 'controls': True},
    {'id': 'rcrash.crash_exit', 'path': 'restore_crash_and_recovery.crash_exit', 'kind': 'nonzero_int', 'controls': True},
    {'id': 'rint.crash_exit', 'path': 'restore_recovery_interrupt.restore_crash_exit', 'kind': 'nonzero_int', 'controls': True},
    {'id': 'rint.rec_exit', 'path': 'restore_recovery_interrupt.recovery_interrupt_exit', 'kind': 'nonzero_int', 'controls': True},
    {'id': 'rint.injector', 'path': 'restore_recovery_interrupt.injector_fired', 'kind': 'bool', 'expected': True, 'controls': True},
    {'id': 'rint.idempotent', 'path': 'restore_recovery_interrupt.second_reconcile_idempotent', 'kind': 'bool', 'expected': True, 'controls': True},
    {'id': 'rint.monotonic', 'path': 'restore_recovery_interrupt.monotonic_revision', 'kind': 'bool', 'expected': True, 'controls': True},
    {'id': 'rint.completed', 'path': 'restore_recovery_interrupt.recovery_completed_after_retry', 'kind': 'bool', 'expected': True, 'controls': True},
    {'id': 'oplog.committed_retry', 'path': 'post_oplog_rollback_retry.committed_after_retry', 'kind': 'bool', 'expected': True, 'controls': True},
    {'id': 'oplog.invalidated', 'path': 'post_oplog_rollback_retry.invalidated_count_after_rollback', 'kind': 'int', 'expected': 1, 'controls': True},
    {'id': 'oplog.final_revision', 'path': 'post_oplog_rollback_retry.final_revision', 'kind': 'int', 'expected': 1, 'controls': True},
    {'id': 'oplog.retry_sha', 'path': 'post_oplog_rollback_retry.retry_after_sha256', 'kind': 'hash', 'controls': True},
    {'id': 'collision.second', 'path': 'changed_payload_collision.second_rejected', 'kind': 'bool', 'expected': True, 'controls': True},
    {'id': 'replay.disk_newer', 'path': 'replay_after_newer.disk_keeps_newer', 'kind': 'bool', 'expected': True, 'controls': True},
    {'id': 'replay.retry_ok', 'path': 'replay_after_newer.retry_exit_zero', 'kind': 'bool', 'expected': True, 'controls': True},
    {'id': 'replay.same_hash', 'path': 'replay_after_newer.same_result_hash', 'kind': 'bool', 'expected': True, 'controls': True},
    {'id': 'replay.first_sha', 'path': 'replay_after_newer.first_after_sha256', 'kind': 'hash', 'controls': True},
    {'id': 'replay.replay_sha', 'path': 'replay_after_newer.replay_after_sha256', 'kind': 'hash', 'controls': True},
    {'id': 'replay.final_revision', 'path': 'replay_after_newer.final_revision', 'kind': 'int', 'controls': True},
    {'id': 'pure.legitimate', 'path': 'schema_pure.legitimate_passes', 'kind': 'bool', 'expected': True, 'controls': True},
    {'id': 'pure.fit_absent', 'path': 'schema_pure.fit_absent_allowed', 'kind': 'bool', 'expected': True, 'controls': True},
    {'id': 'pure.null_fit', 'path': 'schema_pure.null_fit_rejects', 'kind': 'bool', 'expected': True, 'controls': True},
]

RELATION_REGISTRY: list[dict[str, Any]] = [
    {'id': 'rel.so.canonical_disk', 'path': 'same_op_concurrent.canonical_components_sha256', 'kind': 'relation', 'relation': 'same_op_canonical_matches_final_evidence', 'controls': True},
    {'id': 'rel.oplog.retry_sha_disk', 'path': 'post_oplog_rollback_retry.retry_after_sha256', 'kind': 'relation', 'relation': 'oplog_retry_sha_matches_after_retry_evidence', 'controls': True},
    {'id': 'rel.oplog.rev_disk', 'path': 'post_oplog_rollback_retry.final_revision', 'kind': 'relation', 'relation': 'oplog_final_revision_matches_after_retry_sidecar', 'controls': True},
    {'id': 'rel.replay.hash_pair', 'path': 'replay_after_newer.same_result_hash', 'kind': 'relation', 'relation': 'replay_same_result_requires_matching_hashes', 'controls': True},
    {'id': 'rel.replay.rev_disk', 'path': 'replay_after_newer.final_revision', 'kind': 'relation', 'relation': 'replay_final_revision_matches_after_replay_sidecar', 'controls': True},
]

for _st in EDIT_CRASH_STAGES:
    SCALAR_REGISTRY.extend(_crash_fields(_st))
    RELATION_REGISTRY.append(
        {
            'id': f'rel.crash.{_st}.restore_disk',
            'path': f'crash_stages.stages.{_st}.sha_restored',
            'kind': 'relation',
            'relation': 'crash_stage_restore_matches_evidence',
            'relation_stage': _st,
            'controls': True,
        }
    )

for _i in range(len(SCHEMA_NEGATIVE_LABELS)):
    SCALAR_REGISTRY.extend(_schema_row_fields(_i))

COUNTEREXAMPLE_REGISTRY: list[dict[str, Any]] = [
    {'id': 'cx.crash_stages_empty', 'path': 'crash_stages.stages', 'value': {}},
    {'id': 'cx.after_hash_a_null', 'path': 'same_op_concurrent.after_hash_a', 'value': None},
    {'id': 'cx.invalidated_one', 'path': 'same_op_concurrent.invalidated_ledger_rows', 'value': 1},
    {'id': 'cx.rint_monotonic_false', 'path': 'restore_recovery_interrupt.monotonic_revision', 'value': False},
    {'id': 'cx.rint_completed_false', 'path': 'restore_recovery_interrupt.recovery_completed_after_retry', 'value': False},
    {'id': 'cx.dual_meta_zero', 'path': 'dual_lock.metadata_revision', 'value': 0},
    {'id': 'cx.dual_meta_exit_false', 'path': 'dual_lock.metadata_exit', 'value': 1},
    {'id': 'cx.rollback_crash_zero', 'path': 'rollback_preserves.b_crash_exit', 'value': 0},
    {'id': 'cx.restore_crash_zero', 'path': 'restore_crash_and_recovery.crash_exit', 'value': 0},
    {'id': 'cx.oplog_committed_false', 'path': 'post_oplog_rollback_retry.committed_after_retry', 'value': False},
    {'id': 'cx.oplog_retry_sha_null', 'path': 'post_oplog_rollback_retry.retry_after_sha256', 'value': None},
    {'id': 'cx.schema_missing_next_false', 'path': 'schema_negatives.missing_next_revision_rejected', 'value': False},
    {'id': 'cx.collision_false', 'path': 'changed_payload_collision.second_rejected', 'value': False},
    {'id': 'cx.final_hash_unrelated', 'path': 'same_op_concurrent.final_after_sha256', 'value': '0' * 64},
    {'id': 'cx.oplog_rev_99', 'path': 'post_oplog_rollback_retry.final_revision', 'value': 99},
    {'id': 'cx.replay_hash_false', 'path': 'replay_after_newer.same_result_hash', 'value': False},
    {'id': 'cx.replay_first_sha_null', 'path': 'replay_after_newer.first_after_sha256', 'value': None},
    {'id': 'cx.replay_final_rev_null', 'path': 'replay_after_newer.final_revision', 'value': None},
    {'id': 'cx.crash_rev_not_restored', 'path': 'crash_stages.stages.pending_before_rename.revision_restored', 'value': False},
]

FULL_ACCEPTANCE_COUNTEREXAMPLES: tuple[tuple[str, str, object], ...] = (
    ('cx.control_inventory_empty', 'control_coverage.inventory', []),
    ('cx.control_required_zero', 'control_coverage.expected_control_count', 0),
    ('cx.evidence_wrong_run', 'evidence_index.run_id', 'wrong-run'),
    ('cx.extra_evidence_case', 'evidence_index.cases.__extra_case__', []),
)

# Pure boundary probes (guard mocks + acceptance self-check); not mutation inventory rows.
FOUR_GUARD_BOUNDARY_IDS: tuple[str, ...] = (
    'guard.unrelated_failure_rejects',
    'guard.integer_targets_path_rejects',
    'guard.omitted_required_md_manifest_rejects',
    'guard.extra_evidence_case_rejects',
)

MUTATION_VARIANTS: tuple[str, ...] = ('missing', 'wrongtype', 'invalid')


def all_controlled_entries() -> list[dict[str, Any]]:
    return [e for e in SCALAR_REGISTRY + RELATION_REGISTRY if e.get('controls')]


def expected_control_ids() -> list[str]:
    ids: list[str] = []
    for entry in all_controlled_entries():
        for variant in MUTATION_VARIANTS:
            ids.append(f"{entry['id']}:{variant}")
    for cx in COUNTEREXAMPLE_REGISTRY:
        ids.append(cx['id'])
    for cx_id, _, _ in FULL_ACCEPTANCE_COUNTEREXAMPLES:
        ids.append(cx_id)
    return ids


def control_row_spec_by_id() -> dict[str, dict[str, str]]:
    specs: dict[str, dict[str, str]] = {}
    for entry in all_controlled_entries():
        for variant in MUTATION_VARIANTS:
            cid = f"{entry['id']}:{variant}"
            specs[cid] = {'path': entry['path'], 'mutation': variant, 'invariant_id': entry['id']}
    for cx in COUNTEREXAMPLE_REGISTRY:
        specs[cx['id']] = {'path': cx['path'], 'mutation': 'counterexample', 'invariant_id': cx['id']}
    for cx_id, path, _ in FULL_ACCEPTANCE_COUNTEREXAMPLES:
        specs[cx_id] = {'path': path, 'mutation': 'full_acceptance_probe', 'invariant_id': cx_id}
    return specs
