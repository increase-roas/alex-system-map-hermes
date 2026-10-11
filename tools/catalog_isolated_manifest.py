"""Exact required isolated-catalog file set and full content-hash validation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable, Optional

from catalog_io import EXPECTED_COUNTS

ROOT = Path(__file__).resolve().parents[1]

ISOLATED_TOP_REL = (
    'data',
    'views',
    'docs/COMPONENT_INDEX.md',
    'components',
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def production_component_ids(catalog_root: Path | None = None) -> list[str]:
    root = catalog_root or ROOT
    payload = json.loads((root / 'data' / 'components.json').read_text(encoding='utf-8'))
    records = payload.get('records') or []
    ids = [r['id'] for r in records if isinstance(r, dict) and r.get('id')]
    if len(ids) != EXPECTED_COUNTS['components']:
        raise ValueError(f'expected {EXPECTED_COUNTS["components"]} component ids, got {len(ids)}')
    return ids


def required_relative_paths(catalog_root: Path | None = None) -> list[str]:
    root = (catalog_root or ROOT).resolve()
    paths: set[str] = set()
    for top in ISOLATED_TOP_REL:
        src = root / top
        if src.is_file():
            paths.add(top)
        elif src.is_dir() and top == 'components':
            for cid in production_component_ids(root):
                paths.add(f'components/{cid}.md')
        elif src.is_dir():
            for fp in src.rglob('*'):
                if fp.is_file():
                    paths.add(fp.relative_to(root).as_posix())
    missing_src = [p for p in sorted(paths) if not (root / p).is_file()]
    if missing_src:
        raise RuntimeError(f'production missing required paths ({len(missing_src)}): {missing_src[:8]}')
    return sorted(paths)


def content_manifest(
    catalog_root: Path,
    rel_paths: list[str],
    *,
    deadline_check: Optional[Callable[[str], None]] = None,
) -> dict[str, dict]:
    root = catalog_root.resolve()
    out: dict[str, dict] = {}
    for i, rel in enumerate(rel_paths):
        if deadline_check and i % 64 == 0:
            deadline_check(f'content_manifest:{catalog_root.name}')
        fp = root / rel
        if not fp.is_file():
            out[rel] = {'present': False}
            continue
        raw = fp.read_bytes()
        out[rel] = {
            'present': True,
            'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest(),
        }
    return out


def manifest_aggregate_sha256(manifest: dict[str, dict]) -> str:
    lines = []
    for rel in sorted(manifest):
        row = manifest[rel]
        if not row.get('present'):
            lines.append(f'{rel}:MISSING')
        else:
            lines.append(f"{rel}:{row['sha256']}:{row['bytes']}")
    return hashlib.sha256('\n'.join(lines).encode()).hexdigest()


def validate_isolated_against_production(
    production_root: Path,
    isolated_root: Path,
    *,
    rel_paths: list[str] | None = None,
    expected_manifest: dict[str, dict] | None = None,
    deadline_check: Optional[Callable[[str], None]] = None,
) -> dict:
    production_root = production_root.resolve()
    isolated_root = isolated_root.resolve()
    rel_paths = rel_paths or required_relative_paths(production_root)
    prod_manifest = expected_manifest or content_manifest(
        production_root, rel_paths, deadline_check=deadline_check
    )
    iso_manifest = content_manifest(isolated_root, rel_paths, deadline_check=deadline_check)

    missing: list[str] = []
    extra_component_md: list[str] = []
    hash_mismatch: list[str] = []
    truncated: list[str] = []

    for rel in rel_paths:
        p = prod_manifest.get(rel) or {}
        i = iso_manifest.get(rel) or {}
        if not i.get('present'):
            missing.append(rel)
            continue
        if not p.get('present'):
            hash_mismatch.append(rel)
            continue
        if i['sha256'] != p['sha256']:
            hash_mismatch.append(rel)
        if i['bytes'] != p['bytes']:
            truncated.append(rel)

    comp_dir = isolated_root / 'components'
    if comp_dir.is_dir():
        allowed = {f'{cid}.md' for cid in production_component_ids(production_root)}
        for md in comp_dir.glob('*.md'):
            if md.name not in allowed:
                extra_component_md.append(f'components/{md.name}')

    passed = not missing and not extra_component_md and not hash_mismatch and not truncated
    return {
        'required_path_count': len(rel_paths),
        'missing_paths': missing[:32],
        'missing_path_count': len(missing),
        'extra_component_md': extra_component_md[:32],
        'extra_component_md_count': len(extra_component_md),
        'hash_mismatch_paths': hash_mismatch[:32],
        'hash_mismatch_count': len(hash_mismatch),
        'byte_mismatch_paths': truncated[:32],
        'byte_mismatch_count': len(truncated),
        'production_manifest_sha256': manifest_aggregate_sha256(prod_manifest),
        'isolated_manifest_sha256': manifest_aggregate_sha256(iso_manifest),
        'manifests_equal': manifest_aggregate_sha256(prod_manifest)
        == manifest_aggregate_sha256(iso_manifest),
        'validation_passed': passed,
    }


def prove_isolation_no_production_mutation(
    production_root: Path,
    isolated_root: Path,
    *,
    probe_rel: str = 'data/.isolation-probe.tmp',
) -> dict:
    production_root = production_root.resolve()
    isolated_root = isolated_root.resolve()
    before_paths = required_relative_paths(production_root)[:20]
    before = {rel: sha256_file(production_root / rel) for rel in before_paths}
    probe_iso = isolated_root / probe_rel
    probe_iso.parent.mkdir(parents=True, exist_ok=True)
    probe_iso.write_text('isolated-only-probe\n', encoding='utf-8')
    probe_prod = production_root / probe_rel
    after = {rel: sha256_file(production_root / rel) for rel in before_paths}
    unchanged = before == after
    return {
        'production_probe_absent': not probe_prod.exists(),
        'isolated_probe_written': probe_iso.is_file(),
        'production_sample_unchanged': unchanged,
        'isolation_passed': (not probe_prod.exists()) and probe_iso.is_file() and unchanged,
    }
