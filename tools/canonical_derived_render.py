"""Regenerate Markdown/map/XLSX from canonical JSON via build_catalog.render."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from catalog_io import catalog_root

ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_catalog_derived(record_id: str | None = None) -> None:
    import os

    import build_catalog

    if record_id:
        os.environ['CATALOG_RENDER_ONLY_COMPONENT_IDS'] = record_id
    else:
        os.environ.pop('CATALOG_RENDER_ONLY_COMPONENT_IDS', None)
    build_catalog.render()
    os.environ.pop('CATALOG_RENDER_ONLY_COMPONENT_IDS', None)


def snapshot_derived_hashes(table: str, record_id: str | None) -> dict:
    root = catalog_root()
    out: dict = {
        'catalog_root': str(root),
        'table': table,
        'record_id': record_id,
        'drive_publication': 'local-only; not registered Drive update',
    }
    xlsx = root / 'views' / 'Alex_System_Foundation.xlsx'
    index_md = root / 'docs' / 'COMPONENT_INDEX.md'
    if xlsx.is_file():
        out['xlsx_sha256'] = sha256_file(xlsx)
        out['xlsx_path'] = str(xlsx.relative_to(root))
    if index_md.is_file():
        out['component_index_sha256'] = sha256_file(index_md)
    if record_id:
        md = root / 'components' / f'{record_id}.md'
        if md.is_file():
            body = md.read_bytes()
            out['component_markdown_path'] = str(md.relative_to(root))
            out['component_markdown_sha256'] = hashlib.sha256(body).hexdigest()
            out['component_markdown_bytes'] = len(body)
    overview = root / 'views' / 'overview.json'
    if overview.is_file():
        out['overview_sha256'] = sha256_file(overview)
    return out


def copy_derived_proof(dest_dir: Path, *, record_id: str | None = None) -> dict:
    dest_dir.mkdir(parents=True, exist_ok=True)
    root = catalog_root()
    copied: dict[str, str] = {}
    rels = [
        'data/components.json',
        'data/.maintained-revisions.json',
        'views/Alex_System_Foundation.xlsx',
        'docs/COMPONENT_INDEX.md',
        'views/overview.json',
    ]
    if record_id:
        rels.append(f'components/{record_id}.md')
    for rel in rels:
        src = root / rel
        if src.is_file():
            dst = dest_dir / rel.replace('/', '__')
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
            copied[rel] = sha256_file(dst)
    return copied


def copy_full_run_snapshot(dest_dir: Path) -> dict:
    """After final browser edits: canonical, metadata, revisions, all component MD, index, xlsx."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    root = catalog_root()
    manifest: dict[str, str] = {}
    rels = [
        'data/components.json',
        'data/catalog-metadata.json',
        'data/.maintained-revisions.json',
        'views/Alex_System_Foundation.xlsx',
        'docs/COMPONENT_INDEX.md',
        'views/overview.json',
    ]
    for rel in rels:
        src = root / rel
        if src.is_file():
            dst = dest_dir / rel.replace('/', '__')
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
            manifest[rel] = sha256_file(dst)
    md_count = 0
    comp_dir = root / 'components'
    if comp_dir.is_dir():
        for md in sorted(comp_dir.glob('*.md')):
            rel = f'components/{md.name}'
            dst = dest_dir / 'components' / md.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(md.read_bytes())
            manifest[rel] = sha256_file(dst)
            md_count += 1
    manifest['_component_markdown_count'] = str(md_count)
    (dest_dir / 'content_hash_manifest.json').write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )
    return {'files': manifest, 'component_markdown_count': md_count}
