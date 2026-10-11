#!/usr/bin/env python3
"""Load the Director's own sanitized export into the map's trace store.

Source: inputs/real-traces/director-controller/receipts.jsonl (exported by the Director itself).
Builds one trace per mission and imports it with tools/local_service.py trace-import.
Re-runnable: a new record count gives a new receipt_id, and the mission trace is refreshed.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Live file kept by the Director's own trace writer (scripts/export-trace-receipts.py); the old
# one-time copy inside this project is only a fallback.
LIVE_SRC = Path.home() / 'Alex-Director' / 'inputs' / 'real-traces' / 'director-controller' / 'receipts.jsonl'
SRC = LIVE_SRC if LIVE_SRC.exists() else ROOT / 'inputs' / 'real-traces' / 'director-controller' / 'receipts.jsonl'
OUT = ROOT / 'inputs' / 'real-traces' / '_trace-docs'
DB = ROOT / 'app' / '.data' / 'local.sqlite'


def ms(a, b):
    try:
        return int((datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() * 1000)
    except Exception:
        return None


def build_missions():
    missions = defaultdict(list)
    for i, line in enumerate(SRC.read_text().splitlines()):
        if not line.strip():
            continue
        rec = json.loads(line)
        ts = rec.get('timestamps') or {}
        start = ts.get('created_at')
        end = ts.get('completed_at') or ts.get('failed_at')
        status = rec.get('status') or 'unknown'
        key = hashlib.sha256(line.encode()).hexdigest()[:12]
        missions[rec.get('mission') or 'unlabeled'].append({
            'span_id': f'director-{key}-{i}',
            'parent_span_id': None,
            'name': rec.get('action') or 'controller write (action not recorded)',
            'agent_identity': 'Director controller',
            'tool_action': rec.get('action'),
            'started_at': start,
            'ended_at': end,
            'duration_ms': ms(start, end) if start and end else None,
            'status': status,
            'error': 'failed (reason withheld by export)' if status == 'failed' else None,
            'component_ids': [], 'source_ids': [], 'evidence_ids': [],
            'metadata': {'observed': True, 'export_line': i + 1},
        })
    return missions


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for mission, spans in sorted(build_missions().items()):
        spans.sort(key=lambda s: s['started_at'] or s['ended_at'] or '')
        failed = sum(1 for s in spans if s['status'] == 'failed')
        starts = [s['started_at'] for s in spans if s['started_at']]
        ends = [s['ended_at'] for s in spans if s['ended_at']]
        slug = re.sub(r'[^A-Za-z0-9._-]+', '-', mission)[:90]
        doc = {
            'receipt_id': f'director-{slug}-n{len(spans)}',
            'trace_id': f'trace-director-{slug}',
            'label': f'Director: {mission} ({len(spans)} writes' + (f', {failed} failed)' if failed else ')'),
            'synthetic_only': False,
            'started_at': min(starts) if starts else None,
            'ended_at': max(ends) if ends else None,
            'status': 'failed' if failed == len(spans) else ('partial' if failed else 'completed'),
            'job_id': None,
            'metadata': {'producer': 'Director sanitized export (real, observed)', 'mission': mission},
            'spans': spans,
        }
        path = OUT / f'{slug}.json'
        path.write_text(json.dumps(doc, indent=1))
        run = subprocess.run(
            [sys.executable, str(ROOT / 'tools' / 'local_service.py'), '--db', str(DB), 'trace-import', str(path)],
            capture_output=True, text=True,
        )
        results.append({'mission': mission, 'spans': len(spans), 'ok': run.returncode == 0,
                        'out': (run.stdout or run.stderr).strip()[-200:]})
    print(json.dumps({'missions': len(results), 'spans': sum(r['spans'] for r in results),
                      'failed_imports': [r for r in results if not r['ok']][:5]}, indent=1))


if __name__ == '__main__':
    main()
