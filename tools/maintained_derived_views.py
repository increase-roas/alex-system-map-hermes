"""Regenerate derived Markdown/meta for explicitly editable maintained records."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DERIVED_DIR = ROOT / 'work' / 'maintained' / 'derived'


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def regenerate_derived_views(relative: str, document: dict, *, source_sha256: str) -> dict:
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    slug = Path(relative).name.replace('.json', '')
    md_path = DERIVED_DIR / f'{slug}.md'
    meta_path = DERIVED_DIR / f'{slug}.meta.json'
    md_body = '\n'.join(
        [
            f'# Maintained record: {relative}',
            '',
            f'- Revision: **{document.get("revision")}**',
            f'- Label: {document.get("label", "—")}',
            f'- Updated at: {document.get("updated_at") or utc_now()}',
            '',
            '## Note',
            '',
            str(document.get('note') or '(no note)'),
            '',
            'Derived view only; canonical JSON is the fact store.',
            '',
        ]
    )
    md_path.write_text(md_body + '\n', encoding='utf-8')
    meta = {
        'source_path': relative,
        'source_sha256': source_sha256,
        'revision': document.get('revision'),
        'derived_at': utc_now(),
        'markdown_path': str(md_path.relative_to(ROOT)),
        'markdown_sha256': sha256_bytes(md_body.encode()),
        'drive_publication': 'local-only; not registered Drive update',
    }
    meta_path.write_text(json.dumps(meta, indent=2) + '\n')
    return meta
