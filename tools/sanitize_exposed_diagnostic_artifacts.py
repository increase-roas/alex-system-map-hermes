#!/usr/bin/env python3
"""Redact exposed local mutation tokens from project synthetic diagnostic captures only."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

from diagnostic_emission_screening import (  # noqa: E402
    contains_exposed_local_mutation_token,
    redact_diagnostic_value,
    screen_diagnostic_text,
)

AMENDMENT_ID = 'diagnostic-screening-20261010-0747'
AMENDMENT_LOG = ROOT / 'reports' / 'diagnostic-sanitization-amendments.jsonl'

GLOB_PATTERNS = (
    'reports/browser-proof/recovery-screening-real-paths-20261010-0738/network-log.json',
    'reports/workflow-core-failures/recovery-screening-real-paths-20261010-0738-*.json',
    'reports/run-receipts/recovery-screening-real-paths-20261010-0738-*.json',
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sanitize_json_file(path: Path) -> dict | None:
    if not path.is_file():
        return None
    before_bytes = path.read_bytes()
    before_sha = sha256_bytes(before_bytes)
    try:
        payload = json.loads(before_bytes.decode('utf-8'))
    except json.JSONDecodeError:
        text = before_bytes.decode('utf-8', errors='replace')
        if not contains_exposed_local_mutation_token(text):
            return None
        screened, _ = screen_diagnostic_text(text)
        after_bytes = screened.encode('utf-8')
    else:
        redacted, _ = redact_diagnostic_value(payload)
        after_bytes = (json.dumps(redacted, indent=2) + '\n').encode('utf-8')
    after_sha = sha256_bytes(after_bytes)
    if after_sha == before_sha:
        return None
    path.write_bytes(after_bytes)
    record = {
        'amendment_id': AMENDMENT_ID,
        'at': utc_now(),
        'path': str(path.relative_to(ROOT)),
        'reason': 'post-hoc redaction of isolated local-mutation-token from synthetic test capture',
        'content_sha256_before': before_sha,
        'content_sha256_after': after_sha,
        'immutable_bytes_amended': True,
        'unsanitized_backup_in_reports': False,
    }
    AMENDMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with AMENDMENT_LOG.open('a') as handle:
        handle.write(json.dumps(record, sort_keys=True) + '\n')
    return record


def main() -> int:
    amended: list[dict] = []
    for pattern in GLOB_PATTERNS:
        for path in sorted(ROOT.glob(pattern)):
            rec = sanitize_json_file(path)
            if rec:
                amended.append(rec)
    print(
        json.dumps(
            {
                'amendment_id': AMENDMENT_ID,
                'files_amended_count': len(amended),
                'paths': [a['path'] for a in amended],
                'amendment_log': str(AMENDMENT_LOG.relative_to(ROOT)),
            },
            indent=2,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
