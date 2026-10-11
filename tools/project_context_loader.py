#!/usr/bin/env python3
"""Fresh-agent context loading per docs/AGENT_PROTOCOL.md (project entrypoint, not Cursor runtime)."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ENTRY_DOCS = [
    'START_HERE.md',
    'docs/CURSOR_HANDOFF.md',
    'docs/AGENT_PROTOCOL.md',
    'docs/WORKFLOW_CONTRACT.md',
    'docs/BUILD_SUPERVISION.md',
    'docs/RELIABILITY_ADDENDUM.md',
]


def parse_skills_from_docs() -> list[str]:
    text = (ROOT / 'docs/SKILLS.md').read_text(encoding='utf-8', errors='replace')
    paths = re.findall(r'\(\.\./(skills/[^)]+/SKILL\.md)\)', text)
    return sorted(set(paths))


def load_fresh_agent_context() -> dict:
    loaded_docs = []
    for rel in ENTRY_DOCS:
        path = ROOT / rel
        loaded_docs.append(
            {
                'path': rel,
                'present': path.is_file(),
                'bytes': path.stat().st_size if path.is_file() else 0,
            }
        )
    supervision = json.loads((ROOT / 'reports/build-supervision-state.json').read_text())
    admission = json.loads((ROOT / 'reports/reliability-addendum-admission.json').read_text())
    build_text = (ROOT / 'docs/BUILD_SUPERVISION.md').read_text(encoding='utf-8', errors='replace').lower()
    skill_paths = parse_skills_from_docs()
    skills = []
    for rel in skill_paths:
        p = ROOT / rel
        skills.append({'path': rel, 'exists': p.is_file(), 'bytes': p.stat().st_size if p.is_file() else 0})
    return {
        'entrypoint': 'tools/project_context_loader.py',
        'protocol': 'docs/AGENT_PROTOCOL.md#fresh-agent-entry',
        'loaded_docs': loaded_docs,
        'all_entry_docs_present': all(d['present'] for d in loaded_docs),
        'supervision_revision': supervision.get('revision'),
        'reliability_addendum_revision': admission.get('revision'),
        'build_supervision_acknowledges_revision_2': 'revision 2' in build_text,
        'required_skills_from_skills_md': skills,
        'all_listed_skills_present': all(s['exists'] for s in skills),
        'recovered_next_action': supervision.get('next_action'),
        'cursor_agent_runtime_auto_skill_selection': {
            'status': 'UNVERIFIED',
            'reason': 'docs/SKILLS.md: automatic selection needs fresh Cursor runtime receipt; out of scope for local verifier',
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='Print JSON context bundle')
    args = parser.parse_args()
    payload = load_fresh_agent_context()
    print(json.dumps(payload, indent=2))
    return 0 if payload['all_entry_docs_present'] and payload['all_listed_skills_present'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
