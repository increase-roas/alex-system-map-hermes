"""Sanitized subprocess diagnostic text (no secrets/canary tokens)."""
from __future__ import annotations

import re

CANARY = re.compile(
    r'\b(FAKE[-_]canary[-_]token[-_][A-Za-z0-9-]+|sk-[A-Za-z0-9]{20,}|[a-f0-9]{48})\b',
    re.I,
)


def sanitize_diagnostic_text(text: str, *, max_len: int = 1200) -> str:
    if not text:
        return ''
    safe = CANARY.sub('[REDACTED]', text)
    if len(safe) > max_len:
        return safe[-max_len:]
    return safe
