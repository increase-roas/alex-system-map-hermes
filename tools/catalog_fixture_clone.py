"""Clone production catalog tree for isolated destructive edit tests."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CLONE_PATHS = (
    'data',
    'views',
    'docs/COMPONENT_INDEX.md',
)

SNAPSHOT_CANDIDATE_REL = (
    'app/.data/browser-sync-recovery-20261010-1249/catalog-clone',
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def production_file_hashes() -> dict[str, str]:
    import sys

    sys.path.insert(0, str(ROOT / 'tools'))
    from catalog_io import checked_sha256_map
    from catalog_isolated_manifest import required_relative_paths, sha256_file

    rels = required_relative_paths(ROOT)
    out: dict[str, str] = {}
    for rel in rels:
        out[rel] = sha256_file(ROOT / rel)
    for rel, digest in checked_sha256_map().items():
        if rel in out and out[rel] != digest:
            raise RuntimeError(f'production digest drift vs checked map for {rel}')
    return out


def preserve_partial_clone_evidence(partial_root: Path, report_path: Path) -> dict | None:
    import sys

    sys.path.insert(0, str(ROOT / 'tools'))
    from catalog_io import EXPECTED_COUNTS

    if not partial_root.is_dir():
        return None
    comp = partial_root / 'components'
    md_count = sum(1 for _ in comp.glob('*.md')) if comp.is_dir() else 0
    evidence = {
        'at': utc_now(),
        'partial_dest': str(partial_root),
        'component_md_count': md_count,
        'expected_component_md': EXPECTED_COUNTS['components'],
        'incomplete': md_count < EXPECTED_COUNTS['components'],
        'note': 'Preserved before replacement; sole partial failure record retained on disk.',
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(evidence, indent=2) + '\n')
    return evidence


def verify_complete_clone(candidate: Path, *, expected_manifest: dict | None = None, deadline_check=None) -> dict:
    import sys

    sys.path.insert(0, str(ROOT / 'tools'))
    from catalog_isolated_manifest import required_relative_paths, validate_isolated_against_production

    candidate = candidate.resolve()
    rel_paths = required_relative_paths(ROOT)
    validation = validate_isolated_against_production(
        ROOT,
        candidate,
        rel_paths=rel_paths,
        expected_manifest=expected_manifest,
        deadline_check=deadline_check,
    )
    return {
        'path': str(candidate),
        'required_path_count': validation['required_path_count'],
        'validation': validation,
        'complete': validation['validation_passed'] is True,
    }


def reconcile_clone(
    dest_root: Path,
    *,
    expected_manifest: dict | None = None,
    deadline_check=None,
) -> dict:
    import sys

    sys.path.insert(0, str(ROOT / 'tools'))
    from catalog_isolated_manifest import (
        prove_isolation_no_production_mutation,
        required_relative_paths,
        validate_isolated_against_production,
    )

    dest_root = dest_root.resolve()
    rel_paths = required_relative_paths(ROOT)
    validation = validate_isolated_against_production(
        ROOT,
        dest_root,
        rel_paths=rel_paths,
        expected_manifest=expected_manifest,
        deadline_check=deadline_check,
    )
    isolation = prove_isolation_no_production_mutation(ROOT, dest_root)
    probe = dest_root / 'data' / '.isolation-probe.tmp'
    if probe.is_file():
        probe.unlink()
    passed = validation['validation_passed'] and isolation['isolation_passed']
    return {
        **validation,
        'isolation': isolation,
        'reconciliation_passed': passed,
    }


def _bounded_copy_tree(
    src: Path,
    dst: Path,
    *,
    timeout_s: float,
    label: str,
    overall,
) -> dict:
    from catalog_preparation_bounded import remove_tree_bounded, run_group_with_deadline

    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        rm = remove_tree_bounded(dst, overall=overall)
        if rm.get('timed_out') or rm.get('exit_code') not in (0, None):
            raise RuntimeError(f'failed clearing {dst}: {rm}')
    if src.is_file():
        cmd = ['cp', '-c', str(src), str(dst)]
    else:
        cmd = ['cp', '-cR', str(src), str(dst)]
    return run_group_with_deadline(cmd, timeout_s=timeout_s, label=label, overall=overall)


def clone_complete_catalog(dest_root: Path, *, preparation_deadline_s: float = 600) -> dict:
    from catalog_isolated_manifest import content_manifest, required_relative_paths
    from catalog_preparation_bounded import (
        CP_DEADLINE_S,
        OverallPreparationDeadline,
        remove_tree_bounded,
        run_group_with_deadline,
    )

    dest_root = dest_root.resolve()
    overall = OverallPreparationDeadline(preparation_deadline_s)
    rel_paths = required_relative_paths(ROOT)
    expected_manifest = content_manifest(ROOT, rel_paths, deadline_check=overall.check)
    partial_report = ROOT / 'reports' / 'catalog-prep-partial-evidence-20261010-1320.json'
    partial_src = ROOT / 'app/.data/browser-build-bound-correction-20261010-1320/catalog-clone'
    partial_evidence = preserve_partial_clone_evidence(partial_src, partial_report)

    steps: list[dict] = []
    snapshot_used: dict | None = None
    method = 'production_cp_cR_bounded'

    overall.check('snapshot_verify')
    for rel in SNAPSHOT_CANDIDATE_REL:
        cand = (ROOT / rel).resolve()
        if not cand.is_dir():
            continue
        verified = verify_complete_clone(cand, expected_manifest=expected_manifest, deadline_check=overall.check)
        if verified.get('complete'):
            snapshot_used = verified
            break

    dest_parent = dest_root.parent
    dest_parent.mkdir(parents=True, exist_ok=True)
    if dest_root.exists():
        steps.append(remove_tree_bounded(dest_root, overall=overall))

    per_cp_budget = min(CP_DEADLINE_S, max(30.0, overall.remaining() - 20))

    if snapshot_used:
        method = 'verified_snapshot_cp_cR_bounded'
        src = Path(snapshot_used['path'])
        steps.append(
            run_group_with_deadline(
                ['cp', '-cR', str(src), str(dest_root)],
                timeout_s=per_cp_budget,
                label='cp_snapshot_catalog_clone',
                overall=overall,
            )
        )
        step = steps[-1]
        if step.get('timed_out') or step.get('exit_code') not in (0, None):
            raise RuntimeError(f'snapshot copy failed: {step}')
    else:
        dest_root.mkdir(parents=True, exist_ok=True)
        for rel in CLONE_PATHS:
            src = ROOT / rel
            dst = dest_root / rel
            if not src.exists():
                raise RuntimeError(f'missing required production clone source: {rel}')
            steps.append(_bounded_copy_tree(src, dst, timeout_s=per_cp_budget, label=f'cp_production_{rel}', overall=overall))
            step = steps[-1]
            if step.get('timed_out') or step.get('exit_code') not in (0, None):
                raise RuntimeError(f'production copy failed for {rel}: {step}')
        comp_src = ROOT / 'components'
        comp_dst = dest_root / 'components'
        if not comp_src.is_dir():
            raise RuntimeError('missing production components directory')
        steps.append(
            _bounded_copy_tree(comp_src, comp_dst, timeout_s=per_cp_budget, label='cp_production_components', overall=overall)
        )
        step = steps[-1]
        if step.get('timed_out') or step.get('exit_code') not in (0, None):
            raise RuntimeError(f'components copy failed: {step}')

    overall.check('reconcile')
    reconciliation = reconcile_clone(dest_root, expected_manifest=expected_manifest, deadline_check=overall.check)
    if not reconciliation.get('reconciliation_passed'):
        raise RuntimeError(f'clone reconciliation failed: {reconciliation}')

    manifest = {
        'cloned_at': utc_now(),
        'dest_root': str(dest_root),
        'production_binding': 'CATALOG_FIXTURE_ROOT',
        'preparation_method': method,
        'preparation_elapsed_seconds': round(overall.elapsed(), 3),
        'preparation_deadline_seconds': preparation_deadline_s,
        'preparation_steps': steps,
        'partial_evidence_preserved': partial_evidence,
        'snapshot_source': snapshot_used,
        'required_path_count': reconciliation['required_path_count'],
        'production_manifest_sha256': reconciliation['production_manifest_sha256'],
        'isolated_manifest_sha256': reconciliation['isolated_manifest_sha256'],
        'reconciliation': reconciliation,
        'components_cloned_count': len(
            [p for p in required_relative_paths(ROOT) if p.startswith('components/')]
        ),
    }
    (dest_root / 'data' / '.clone-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    rev_sidecar = dest_root / 'data' / '.maintained-revisions.json'
    if rev_sidecar.is_file():
        rev_sidecar.unlink()
    return manifest
