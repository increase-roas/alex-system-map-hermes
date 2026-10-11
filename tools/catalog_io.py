"""Resilient catalog JSON reads with hash verification and completeness checks."""
from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def catalog_root() -> Path:
    override = os.environ.get('CATALOG_FIXTURE_ROOT')
    if override:
        return Path(override)
    return ROOT

EXPECTED_COUNTS = {
    'components': 2351,
    'relationships': 59,
    'coverage': 2377,
    'overview_memberships': 2351,
}


class CatalogLoadError(OSError):
    pass


@lru_cache(maxsize=1)
def checked_sha256_map() -> dict[str, str]:
    report = ROOT / 'reports' / 'independent-foundation-graph.json'
    try:
        payload = json.loads(report.read_text())
    except OSError:
        return {}
    checked = payload.get('checked_sha256')
    return dict(checked) if isinstance(checked, dict) else {}


def sha256_path(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _verify_file_digest(relative: str, digest: str) -> dict | None:
    expected = checked_sha256_map().get(relative)
    if expected and digest != expected:
        return {
            'file': relative,
            'error': 'sha256 mismatch',
            'expected_sha256': expected,
            'actual_sha256': digest,
        }
    return None


def load_records(name: str) -> tuple[list[dict], dict | None]:
    relative = f'data/{name}.json'
    path = catalog_root() / relative
    gap: dict | None = None
    try:
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        payload = json.loads(raw)
        records = payload['records']
        gap = _verify_file_digest(relative, digest)
        expected_count = EXPECTED_COUNTS.get(name)
        if expected_count is not None and len(records) != expected_count:
            count_gap = {
                'file': relative,
                'error': f'expected {expected_count} records, got {len(records)}',
            }
            gap = count_gap if gap is None else {**gap, **count_gap}
        return records, gap
    except OSError as exc:
        expected = checked_sha256_map().get(relative)
        return [], {
            'file': relative,
            'error': str(exc),
            'expected_sha256': expected,
        }


def load_object(relative: str) -> tuple[dict | list | None, dict | None]:
    path = catalog_root() / relative
    try:
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        payload = json.loads(raw)
        gap = _verify_file_digest(relative, digest)
        if relative == 'views/overview.json' and isinstance(payload, dict):
            memberships = payload.get('memberships', [])
            expected = EXPECTED_COUNTS['overview_memberships']
            if len(memberships) != expected:
                membership_gap = {
                    'file': relative,
                    'error': f'expected {expected} memberships, got {len(memberships)}',
                }
                gap = membership_gap if gap is None else {**gap, **membership_gap}
        return payload, gap
    except OSError as exc:
        return None, {'file': relative, 'error': str(exc)}


def load_catalog_bundle(*, strict: bool = False) -> dict:
    names = [
        'components',
        'relationships',
        'sources',
        'evidence',
        'issues',
        'coverage',
        'source-records',
        'layers',
        'table-index',
    ]
    gaps: list[dict] = []
    data: dict[str, list] = {}
    for name in names:
        rows, gap = load_records(name)
        data[name] = rows
        if gap:
            gaps.append(gap)
    overview, overview_gap = load_object('views/overview.json')
    if overview_gap:
        gaps.append(overview_gap)
    if not isinstance(overview, dict):
        gaps.append({'file': 'views/overview.json', 'error': 'overview unavailable'})
        memberships: list = []
        membership_flag = False
    else:
        memberships = overview.get('memberships', [])
        membership_flag = bool(overview.get('membership_is_runtime_relationship', False))
    component_ids = {c['id'] for c in data['components']}
    dangling = [
        rel['id']
        for rel in data['relationships']
        if rel.get('source_id') not in component_ids or rel.get('target_id') not in component_ids
    ]
    if dangling:
        gaps.append(
            {
                'file': 'data/relationships.json',
                'error': f'{len(dangling)} dangling relationship endpoints',
                'dangling_relationship_ids': dangling[:20],
            }
        )
    completeness = {
        'components': len(data['components']),
        'relationships': len(data['relationships']),
        'coverage': len(data['coverage']),
        'overview_memberships': len(memberships),
        'expected': dict(EXPECTED_COUNTS),
        'load_gaps': len(gaps),
        'dangling_relationships': len(dangling),
        'complete': (
            len(gaps) == 0
            and len(data['relationships']) == EXPECTED_COUNTS['relationships']
            and len(data['coverage']) == EXPECTED_COUNTS['coverage']
            and len(memberships) == EXPECTED_COUNTS['overview_memberships']
            and len(data['components']) == EXPECTED_COUNTS['components']
        ),
    }
    if strict and not completeness['complete']:
        raise CatalogLoadError(json.dumps({'gaps': gaps, 'completeness': completeness}, indent=2))
    return {
        'data': data,
        'overview_memberships': memberships,
        'membership_is_runtime_relationship': membership_flag,
        'dangling_relationship_ids': dangling,
        'load_gaps': gaps if gaps else [],
        'completeness': completeness,
    }
