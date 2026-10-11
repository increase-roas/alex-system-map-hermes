"""Immutable per-case filesystem evidence for canonical transaction regression."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from canonical_transaction_spec import REQUIRED_EVIDENCE_DERIVED_RELS

ROOT = Path(__file__).resolve().parents[1]
JOURNAL_DIR = ROOT / 'app' / '.data' / 'catalog-edit-journal'
DATA_ROOT = (ROOT / 'app' / '.data').resolve()

CANONICAL_FILES = (
    'data/components.json',
    'data/catalog-metadata.json',
    'data/.maintained-revisions.json',
    'data/.catalog-edit-operations.jsonl',
)
DERIVED_FILES = (
    'views/Alex_System_Foundation.xlsx',
    'docs/COMPONENT_INDEX.md',
)

JOURNAL_BYTES_ALGORITHM = 'sha256_utf8_newline_join_sorted_raw_journal_files'


def storage_key(rel_path: str) -> str:
    return rel_path.replace('/', '__')


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def recompute_manifest_sha256(manifest_body: dict) -> str:
    body = {k: v for k, v in manifest_body.items() if k != 'manifest_sha256'}
    return sha256_bytes(json.dumps(body, sort_keys=True, separators=(',', ':')).encode())


def journal_raw_bundle(clone_root: Path, journal_dir: Path | None = None) -> dict[str, Any]:
    base = journal_dir or JOURNAL_DIR
    from_stage_copy = journal_dir is not None
    raw_files: list[tuple[str, bytes]] = []
    if base.is_dir():
        for journal in sorted(base.glob('*.json')):
            if journal.name == '_manifest.json':
                continue
            if not from_stage_copy:
                try:
                    entry = json.loads(journal.read_text())
                except (OSError, json.JSONDecodeError):
                    continue
                if entry.get('catalog_root') != str(clone_root):
                    continue
            raw_files.append((journal.name, journal.read_bytes()))
    combined = b'\n'.join(blob for _, blob in raw_files) if raw_files else b''
    return {
        'present': bool(raw_files),
        'file_names': [name for name, _ in raw_files],
        'entry_count': len(raw_files),
        'bytes_sha256': sha256_bytes(combined) if combined else None,
        'algorithm': JOURNAL_BYTES_ALGORITHM,
    }


def capture_state(clone_root: Path, *, record_a_md: str | None = None, journal_dir: Path | None = None) -> dict[str, Any]:
    manifest: dict[str, Any] = {'files': {}, 'absent': [], 'journal': journal_raw_bundle(clone_root, journal_dir)}
    for rel in CANONICAL_FILES:
        path = clone_root / rel
        if path.is_file():
            manifest['files'][rel] = {'sha256': sha256_file(path), 'bytes': path.stat().st_size}
        else:
            manifest['absent'].append(rel)
    derived: dict[str, Any] = {}
    for rel in DERIVED_FILES:
        path = clone_root / rel
        if path.is_file():
            derived[rel] = {'sha256': sha256_file(path), 'bytes': path.stat().st_size}
        else:
            derived[rel] = None
    if record_a_md:
        md = clone_root / record_a_md
        derived[record_a_md] = {'sha256': sha256_file(md), 'bytes': md.stat().st_size} if md.is_file() else None
    manifest['derived'] = derived
    manifest['manifest_sha256'] = recompute_manifest_sha256(manifest)
    return manifest


def _copy_journals_raw(clone_root: Path, dest_journals: Path) -> dict[str, Any]:
    dest_journals.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for journal in sorted(JOURNAL_DIR.glob('*.json')):
        try:
            entry = json.loads(journal.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if entry.get('catalog_root') != str(clone_root):
            continue
        target = dest_journals / journal.name
        shutil.copy2(journal, target)
        copied.append(journal.name)
    bundle = journal_raw_bundle(clone_root, dest_journals)
    manifest = {
        'algorithm': JOURNAL_BYTES_ALGORITHM,
        'files': {name: {'sha256': sha256_file(dest_journals / name)} for name in copied},
        'bytes_sha256': bundle['bytes_sha256'],
        'sorted_names': sorted(copied),
    }
    (dest_journals / '_manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return manifest


def load_stage_manifest(evidence_root: Path, case: str, stage: str) -> dict | None:
    manifest_path = evidence_root / case / stage / 'manifest.json'
    if not manifest_path.is_file():
        return None
    on_disk = json.loads(manifest_path.read_text())
    return on_disk.get('manifest') or {}


def stage_sidecar_path(stage_dir: Path, rel: str) -> Path:
    return stage_dir / storage_key(rel)


def read_revision_from_stage(stage_dir: Path, record_key: str) -> tuple[int | None, str | None]:
    from canonical_transaction_spec import REVISIONS_SIDEcar_REL

    path = stage_sidecar_path(stage_dir, REVISIONS_SIDEcar_REL)
    if not path.is_file():
        return None, f'missing revision sidecar {path.name}'
    try:
        revs = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None, f'unreadable revision sidecar {path.name}'
    entry = revs.get(record_key)
    if not isinstance(entry, dict) or 'revision' not in entry:
        return None, f'revision key missing in sidecar: {record_key}'
    rev = entry['revision']
    if type(rev) is not int:
        return None, f'revision not int for {record_key}'
    return rev, None


def verify_stage_dir(stage_dir: Path, *, expected_manifest: dict | None = None) -> list[str]:
    errors: list[str] = []
    try:
        resolved = stage_dir.resolve()
        resolved.relative_to(DATA_ROOT)
    except (ValueError, OSError):
        errors.append(f'evidence stage outside allowed data root: {stage_dir}')
        return errors
    if stage_dir.is_symlink():
        errors.append(f'symlink evidence stage not allowed: {stage_dir}')

    manifest_path = stage_dir / 'manifest.json'
    if not manifest_path.is_file():
        return [f'missing manifest.json in {stage_dir}']
    on_disk = json.loads(manifest_path.read_text())
    recorded = on_disk.get('manifest') or {}
    recorded_sha = recorded.get('manifest_sha256')
    recomputed = recompute_manifest_sha256(recorded)
    if recorded_sha != recomputed:
        errors.append('manifest_sha256 not recomputable from recorded manifest body')

    for rel in CANONICAL_FILES:
        key = storage_key(rel)
        src_path = stage_dir / key
        absent_marker = stage_dir / f'{key}.absent'
        if rel in (recorded.get('absent') or []):
            if src_path.is_file():
                errors.append(f'unexpected file for absent {rel}')
            if not absent_marker.is_file():
                errors.append(f'missing absent marker for canonical {rel}')
            continue
        if not src_path.is_file():
            errors.append(f'missing copied file {key}')
            continue
        expect = (recorded.get('files') or {}).get(rel, {}).get('sha256')
        actual = sha256_file(src_path)
        if not expect:
            errors.append(f'missing recorded sha256 for {rel}')
        elif actual != expect:
            errors.append(f'hash mismatch {key}')

    derived = recorded.get('derived') or {}
    for rel in REQUIRED_EVIDENCE_DERIVED_RELS:
        if rel not in derived:
            errors.append(f'required derived manifest entry missing: {rel}')
    for rel, meta in derived.items():
        key = storage_key(rel)
        src_path = stage_dir / key
        absent_marker = stage_dir / f'{key}.absent'
        if meta is None:
            if src_path.is_file():
                errors.append(f'unexpected derived file {key} (recorded absent)')
            if not absent_marker.is_file():
                errors.append(f'missing absent marker for derived {rel}')
            continue
        if not src_path.is_file():
            errors.append(f'missing derived file {key}')
            continue
        actual = sha256_file(src_path)
        if actual != meta.get('sha256'):
            errors.append(f'derived hash mismatch {key}')

    journal_meta = recorded.get('journal') or {}
    journal_present = bool(journal_meta.get('present')) or int(journal_meta.get('entry_count') or 0) > 0
    if journal_meta.get('bytes_sha256'):
        journal_present = True
    journals = stage_dir / 'journals'
    if journal_present:
        if not journals.is_dir():
            errors.append('journal recorded present but journals directory missing')
        else:
            jman_path = journals / '_manifest.json'
            if not jman_path.is_file():
                errors.append('journals present but missing journals/_manifest.json')
            else:
                jman = json.loads(jman_path.read_text())
                recomputed = journal_raw_bundle(Path('/'), journals)
                actual_bundle = recomputed.get('bytes_sha256')
                if jman.get('bytes_sha256') != actual_bundle:
                    errors.append('journal bytes_sha256 not recomputable from raw copies')
                if journal_meta.get('bytes_sha256') != actual_bundle:
                    errors.append('stage manifest journal bytes_sha256 mismatch journals bundle')
                manifest_names = sorted((jman.get('files') or {}).keys())
                disk_names = sorted(
                    p.name for p in journals.iterdir() if p.is_file() and p.name != '_manifest.json'
                )
                if manifest_names != disk_names:
                    errors.append('journal manifest file names/cardinality mismatch raw directory')
                for name, meta in (jman.get('files') or {}).items():
                    fp = journals / name
                    if not fp.is_file() or sha256_file(fp) != meta.get('sha256'):
                        errors.append(f'journal file hash mismatch {name}')
                sorted_manifest = jman.get('sorted_names')
                if sorted_manifest is not None and sorted(sorted_manifest) != manifest_names:
                    errors.append('journal sorted_names inconsistent with files map')

    proj_path = stage_dir / 'journal_projection.json'
    if proj_path.is_file():
        proj = json.loads(proj_path.read_text())
        if proj != journal_meta:
            errors.append('journal_projection.json must match manifest journal section')

    if expected_manifest and recorded_sha != expected_manifest.get('manifest_sha256'):
        errors.append('manifest_sha256 drift')
    return errors


class EvidenceStore:
    def __init__(self, root: Path, clone_root: Path, run_id: str) -> None:
        self.root = root / run_id
        self.clone_root = clone_root
        self.run_id = run_id
        self.root.mkdir(parents=True, exist_ok=True)
        self._saved: dict[str, list[str]] = {}

    def _stage_dir(self, case: str, stage: str) -> Path:
        return self.root / case / stage

    def save_stage(self, case: str, stage: str, *, record_a_md: str | None = None) -> dict[str, Any]:
        dest = self._stage_dir(case, stage)
        if dest.exists():
            raise FileExistsError(f'refuse overwrite evidence {dest}')
        dest.mkdir(parents=True)
        manifest = capture_state(self.clone_root, record_a_md=record_a_md)
        for rel in CANONICAL_FILES:
            src = self.clone_root / rel
            key = storage_key(rel)
            if src.is_file():
                shutil.copy2(src, dest / key)
            else:
                (dest / f'{key}.absent').write_text('', encoding='utf-8')
        _copy_journals_raw(self.clone_root, dest / 'journals')
        journal_projection = manifest['journal']
        (dest / 'journal_projection.json').write_text(json.dumps(journal_projection, indent=2, sort_keys=True) + '\n')
        for rel in DERIVED_FILES:
            src = self.clone_root / rel
            key = storage_key(rel)
            if src.is_file():
                shutil.copy2(src, dest / key)
            else:
                (dest / f'{key}.absent').write_text('', encoding='utf-8')
        if record_a_md:
            src = self.clone_root / record_a_md
            key = storage_key(record_a_md)
            if src.is_file():
                shutil.copy2(src, dest / key)
            else:
                (dest / f'{key}.absent').write_text('', encoding='utf-8')
        rel_handle = str(dest.relative_to(ROOT))
        out = {'relative_path': rel_handle, 'manifest': manifest}
        (dest / 'manifest.json').write_text(json.dumps(out, indent=2, sort_keys=True) + '\n')
        verify_errors = verify_stage_dir(dest)
        if verify_errors:
            raise RuntimeError(f'evidence verify failed after save {case}/{stage}: {verify_errors}')
        self._saved.setdefault(case, []).append(stage)
        out['verify_ok'] = True
        return out

    def case_index(self) -> dict[str, Any]:
        cases: dict[str, list[str]] = {}
        for case, stages in sorted(self._saved.items()):
            cases[case] = sorted(stages)
        for case_dir in sorted(self.root.iterdir()):
            if not case_dir.is_dir():
                continue
            stages = sorted(p.name for p in case_dir.iterdir() if p.is_dir())
            cases[case_dir.name] = stages
        return {'run_id': self.run_id, 'root': str(self.root.relative_to(ROOT)), 'cases': cases}


def verify_evidence_contract(
    evidence_index: dict,
    required_stages: dict[str, tuple[str, ...]],
    *,
    expected_run_id: str,
    evidence_run_root: Path,
) -> list[str]:
    errors: list[str] = []
    run_id = evidence_index.get('run_id')
    if run_id != expected_run_id:
        errors.append(f'evidence_index.run_id must equal {expected_run_id}')
    root_rel = evidence_index.get('root', '')
    if not root_rel.startswith('app/.data/'):
        errors.append('evidence root must stay under app/.data/')
    try:
        allowed_root = (ROOT / root_rel).resolve()
        allowed_root.relative_to(DATA_ROOT)
    except (ValueError, OSError):
        errors.append('evidence root resolves outside app/.data')
        return errors
    expected_resolved = evidence_run_root.resolve()
    if allowed_root != expected_resolved:
        errors.append(f'evidence root {allowed_root} != expected run root {expected_resolved}')
    if allowed_root.is_symlink():
        errors.append('evidence run root symlink not allowed')

    cases = evidence_index.get('cases') or {}
    required_cases = set(required_stages.keys())
    indexed_cases = set(cases.keys())
    if indexed_cases != required_cases:
        missing_cases = sorted(required_cases - indexed_cases)
        extra_cases = sorted(indexed_cases - required_cases)
        if missing_cases:
            errors.append(f'evidence_index.cases missing required cases: {missing_cases}')
        if extra_cases:
            errors.append(f'evidence_index.cases extra unexpected cases: {extra_cases}')
    for case, stages_required in required_stages.items():
        required_stage_set = set(stages_required)
        have = set(cases.get(case) or [])
        if have != required_stage_set:
            missing_st = sorted(required_stage_set - have)
            extra_st = sorted(have - required_stage_set)
            if missing_st:
                errors.append(f'missing evidence stages {case}: {missing_st}')
            if extra_st:
                errors.append(f'extra evidence stages {case}: {extra_st}')
        for stage in stages_required:
            stage_dir = allowed_root / case / stage
            if not stage_dir.is_dir():
                errors.append(f'missing evidence dir {case}/{stage}')
                continue
            errors.extend(verify_stage_dir(stage_dir))
    return errors
