"""Resolve canonical reference targets and validate component contract."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from catalog_io import catalog_root

CATEGORY_VALUES = frozenset({'documented_current', 'historical', 'planned', 'unresolved'})
EVIDENCE_LEVEL_VALUES = frozenset({'reported', 'configured', 'tested', 'unverified'})
OBSERVED_CONDITION_VALUES = frozenset({'working', 'failing', 'blocked', 'unknown'})
COMPONENT_RECORD_KEYS = frozenset(
    {
        'id',
        'name',
        'layer_id',
        'kind',
        'aliases',
        'purpose',
        'boundary',
        'category',
        'evidence_level',
        'observed_condition',
        'observed_at',
        'evidence_ids',
        'source_record_ids',
        'source_categories_preserved',
        'fit',
        'account_reference',
        'resource_type',
        'source_observed_at',
        'provider_status',
    }
)
REQUIRED_COMPONENT_FIELDS = frozenset(
    {
        'id',
        'name',
        'layer_id',
        'kind',
        'aliases',
        'purpose',
        'boundary',
        'category',
        'evidence_level',
        'observed_condition',
        'observed_at',
        'evidence_ids',
        'source_record_ids',
        'source_categories_preserved',
    }
)


def _read_records_table(path: Path, field: str = 'records') -> list[dict]:
    doc = json.loads(path.read_text())
    rows = doc.get(field)
    if not isinstance(rows, list):
        raise ValueError(f'{path.name} must contain array {field}')
    return [r for r in rows if isinstance(r, dict)]


@lru_cache(maxsize=8)
def _indexes_for_root(root_s: str) -> dict[str, set[str]]:
    root = Path(root_s)
    layers_path = root / 'data' / 'layers.json'
    evidence_path = root / 'data' / 'evidence.json'
    source_records_path = root / 'data' / 'source-records.json'
    layer_ids = {str(r.get('id')) for r in _read_records_table(layers_path) if r.get('id')}
    evidence_ids = {str(r.get('id')) for r in _read_records_table(evidence_path) if r.get('id')}
    source_ids = {str(r.get('id')) for r in _read_records_table(source_records_path) if r.get('id')}
    return {
        'layer_ids': layer_ids,
        'evidence_ids': evidence_ids,
        'source_record_ids': source_ids,
    }


def reference_indexes() -> dict[str, set[str]]:
    return _indexes_for_root(str(catalog_root().resolve()))


def clear_reference_cache() -> None:
    _indexes_for_root.cache_clear()


def validate_component_record_contract(before: dict, after: dict) -> None:
    """Validate full maintained component shape for writes (schemas/components.schema.json)."""
    extra = set(after) - COMPONENT_RECORD_KEYS
    if extra:
        raise ValueError(f'unknown component fields not allowed: {sorted(extra)}')
    missing = REQUIRED_COMPONENT_FIELDS - set(after)
    if missing:
        raise ValueError(f'missing required component fields: {sorted(missing)}')
    category = after.get('category')
    if not isinstance(category, str):
        raise ValueError('category must be string enum')
    if category not in CATEGORY_VALUES:
        raise ValueError('category must be documented_current|historical|planned|unresolved')
    evidence_level = after.get('evidence_level')
    if not isinstance(evidence_level, str):
        raise ValueError('evidence_level must be string enum')
    if evidence_level not in EVIDENCE_LEVEL_VALUES:
        raise ValueError('evidence_level invalid')
    cond = after.get('observed_condition')
    if not isinstance(cond, str):
        raise ValueError('observed_condition must be string enum')
    if cond not in OBSERVED_CONDITION_VALUES:
        raise ValueError('observed_condition must be string enum working|failing|blocked|unknown')
    observed_at = after.get('observed_at')
    if observed_at is not None and not isinstance(observed_at, str):
        raise ValueError('observed_at must be string or null')
    if not isinstance(after.get('source_categories_preserved'), bool):
        raise ValueError('source_categories_preserved must be boolean')
    aliases = after.get('aliases')
    if not isinstance(aliases, list):
        raise ValueError('aliases must be array')
    seen_aliases: set[str] = set()
    for item in aliases:
        if not isinstance(item, str) or not item.strip():
            raise ValueError('aliases entries must be nonempty strings')
        if item in seen_aliases:
            raise ValueError('aliases must be unique')
        seen_aliases.add(item)
    evidence_ids = after.get('evidence_ids')
    if not isinstance(evidence_ids, list):
        raise ValueError('evidence_ids must be array')
    seen_evidence: set[str] = set()
    source_record_ids = after.get('source_record_ids')
    if not isinstance(source_record_ids, list):
        raise ValueError('source_record_ids must be array')
    seen_sources: set[str] = set()
    indexes = reference_indexes()
    layer = after.get('layer_id')
    if not isinstance(layer, str) or layer not in indexes['layer_ids']:
        raise ValueError('layer_id not in canonical layers table')
    for item in evidence_ids:
        if not isinstance(item, str) or not item.strip():
            raise ValueError('evidence_ids entries must be strings')
        if item in seen_evidence:
            raise ValueError('evidence_ids must be unique')
        seen_evidence.add(item)
        if item not in indexes['evidence_ids']:
            raise ValueError(f'evidence id not found: {item}')
    for item in source_record_ids:
        if not isinstance(item, str) or not item.strip():
            raise ValueError('source_record_ids entries must be strings')
        if item in seen_sources:
            raise ValueError('source_record_ids must be unique')
        seen_sources.add(item)
        if item not in indexes['source_record_ids']:
            raise ValueError(f'source_record id not found: {item}')
    if not isinstance(after.get('purpose'), str):
        raise ValueError('purpose must be string')
    if not isinstance(after.get('boundary'), str):
        raise ValueError('boundary must be string')
    if 'fit' in after:
        fit = after.get('fit')
        if fit is None or not isinstance(fit, str):
            raise ValueError('fit must be string when present')
    kind = after.get('kind')
    if not isinstance(kind, str) or not kind.strip():
        raise ValueError('kind must be nonempty string')
    name = after.get('name')
    if not isinstance(name, str) or not name.strip():
        raise ValueError('name must be nonempty string')
    if after.get('id') != before.get('id'):
        raise ValueError('record id mismatch')


def audit_existing_component_violations(limit: int = 20) -> dict:
    """Read-only inventory of records that already violate contract (no mutation)."""
    root = catalog_root()
    path = root / 'data' / 'components.json'
    wrapper = json.loads(path.read_text())
    records = wrapper.get('records') or []
    violations: list[dict] = []
    for rec in records:
        if not isinstance(rec, dict):
            violations.append({'id': None, 'reason': 'non-object record'})
            continue
        rid = rec.get('id')
        try:
            validate_component_record_contract(rec, rec)
        except ValueError as exc:
            violations.append({'id': rid, 'reason': str(exc)})
    sample = violations[:limit]
    return {
        'record_count': len(records),
        'violation_count': len(violations),
        'sample_violations': sample,
        'note': 'Existing source violations reported only; catalog not auto-modified to pass.',
    }
