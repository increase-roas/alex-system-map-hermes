"""Explicit required contract for canonical transaction proof (TS05/09/11)."""
from __future__ import annotations

EDIT_CRASH_STAGES: tuple[str, ...] = (
    'pending_before_rename',
    'post_rename_pre_derived',
    'post_derived_pre_revision',
    'committed_before_oplog',
    'post_oplog_pre_journal_commit',
)

SCHEMA_NEGATIVE_LABELS: tuple[str, ...] = (
    'missing_evidence_ids',
    'integer_alias',
    'object_observed_condition',
    'null_source_record_ids',
    'null_purpose',
    'null_boundary',
    'duplicate_aliases',
    'duplicate_evidence',
    'duplicate_source_refs',
    'null_fit',
)

REQUIRED_CASES: tuple[str, ...] = (
    'rollback_preserves',
    'dual_lock',
    'distinct_records',
    'same_op_concurrent',
    'distinct_op_same_record',
    'changed_payload_collision',
    'post_oplog_rollback_retry',
    'replay_after_newer',
    'restore_handler',
    'restore_crash_and_recovery',
    'restore_recovery_interrupt',
    'schema_negatives',
    'schema_pure',
)

# Per-case required evidence stage directory names (saved before clone reset).
REQUIRED_EVIDENCE_STAGES: dict[str, tuple[str, ...]] = {
    'rollback_preserves': ('before_crash', 'interrupted', 'first_recovered', 'after_second_recovery'),
    'dual_lock': ('final',),
    'distinct_records': ('first_overlap', 'final'),
    'same_op_concurrent': ('final',),
    'distinct_op_same_record': ('final',),
    'changed_payload_collision': ('final',),
    'post_oplog_rollback_retry': ('before_reconcile', 'after_rollback', 'after_retry'),
    'replay_after_newer': ('after_first_commit', 'after_newer_commit', 'after_replay'),
    'restore_handler': ('final',),
    'restore_crash_and_recovery': ('interrupted', 'first_recovered', 'second_recovered'),
    'restore_recovery_interrupt': (
        'before_restore',
        'interrupted_restore',
        'interrupted_recovery',
        'first_recovered',
        'second_recovered',
    ),
    'schema_negatives': ('final',),
}

for _stage in EDIT_CRASH_STAGES:
    REQUIRED_EVIDENCE_STAGES[f'crash_stage_{_stage}'] = (
        'before_crash',
        'interrupted',
        'first_recovered',
        'second_recovered',
    )

# Independent-review counterexamples (invalid-value regressions).
COUNTEREXAMPLE_INVALID: tuple[tuple[str, object], ...] = (
    ('crash_stages.stages', {}),
    ('same_op_concurrent.after_hash_a', None),
    ('same_op_concurrent.invalidated_ledger_rows', 1),
    ('restore_recovery_interrupt.monotonic_revision', False),
    ('restore_recovery_interrupt.recovery_completed_after_retry', False),
    ('dual_lock.metadata_revision', 0),
    ('post_oplog_rollback_retry.committed_after_retry', False),
    ('schema_negatives.missing_next_revision_rejected', False),
    ('changed_payload_collision.second_rejected', False),
)

EVIDENCE_ROOT_PREFIX = 'app/.data/'

RECORD_A_ID = 'component_6f112167c8a413f0f3ab'
COMPONENTS_TABLE_REL = 'data/components.json'
REVISIONS_SIDEcar_REL = 'data/.maintained-revisions.json'
REVISION_RECORD_KEY = f'{COMPONENTS_TABLE_REL}#{RECORD_A_ID}'
RECORD_A_MD_REL = f'components/{RECORD_A_ID}.md'

# Every regression evidence stage saves clone state with record MD; manifest must declare these derived paths.
REQUIRED_EVIDENCE_DERIVED_RELS: tuple[str, ...] = (
    'views/Alex_System_Foundation.xlsx',
    'docs/COMPONENT_INDEX.md',
    RECORD_A_MD_REL,
)
