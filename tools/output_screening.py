"""Central screening for JSON/text emitted by local_service."""
from __future__ import annotations

import json
import re
from typing import Any

from build_catalog import ASSIGN, SECRET  # noqa: E402

BENIGN_DIAGNOSTIC_MARKER = 'LOCAL-SCREENING-OK'
FAKE_CANARY = re.compile(
    r'(?i)(?:\bFAKE[-_]canary[-_]token[-_][A-Za-z0-9-]+\b|sk-fake-canary-rel06-do-not-use-[A-Za-z0-9]+)'
)


def screen_text(value: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    if FAKE_CANARY.search(value):
        value = FAKE_CANARY.sub('[REDACTED test-canary]', value)
        notes.append('test-canary tokens withheld')
    if SECRET.search(value):
        value = SECRET.sub('[REDACTED credential-shaped value]', value)
        notes.append('credential-shaped values withheld')
    if ASSIGN.search(value):
        value = ASSIGN.sub(lambda m: m.group(1) + '[REDACTED credential-shaped value]', value)
        notes.append('assignment-shaped secrets withheld')
    return value, notes


def redact_value(value: Any) -> tuple[Any, list[str]]:
    notes: list[str] = []
    if isinstance(value, str):
        screened, n = screen_text(value)
        notes.extend(n)
        return screened, notes
    if isinstance(value, list):
        out = []
        for item in value:
            redacted, n = redact_value(item)
            notes.extend(n)
            out.append(redacted)
        return out, notes
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            redacted, n = redact_value(item)
            notes.extend(n)
            out[key] = redacted
        return out, notes
    return value, notes


def export_json_safe(payload: Any) -> dict:
    redacted, notes = redact_value(payload)
    return {'payload': redacted, 'screening_notes': sorted(set(notes))}
