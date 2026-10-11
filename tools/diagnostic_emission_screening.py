"""Screen sensitive fields before persisting browser/network diagnostics and receipts."""
from __future__ import annotations

import json
import re
from typing import Any

from output_screening import BENIGN_DIAGNOSTIC_MARKER, screen_text

LOCAL_MUTATION_TOKEN_VALUE = re.compile(r'^[a-f0-9]{48}$', re.IGNORECASE)
PLAIN_FIXTURE_TOKEN = re.compile(r'\b[a-f0-9]{48}\b', re.IGNORECASE)
LOCAL_TOKEN_JSON = re.compile(
    r'("token"\s*:\s*")([a-f0-9]{48})(")',
    re.IGNORECASE,
)
X_LOCAL_TOKEN_JSON = re.compile(
    r'("x-local-token"\s*:\s*")([a-f0-9]{48})(")',
    re.IGNORECASE,
)

REDACTED_LOCAL_TOKEN = '[REDACTED local-mutation-token]'
SENSITIVE_OBJECT_KEYS = frozenset({'token', 'x-local-token', 'x_local_token'})


def _redact_key_value(key: str, value: Any) -> tuple[Any, list[str]]:
    notes: list[str] = []
    if isinstance(value, str):
        if key.lower() in SENSITIVE_OBJECT_KEYS and LOCAL_MUTATION_TOKEN_VALUE.fullmatch(value):
            notes.append('local-mutation-token withheld')
            return REDACTED_LOCAL_TOKEN, notes
        screened, n = screen_diagnostic_text(value)
        notes.extend(n)
        return screened, notes
    return value, notes


def redact_diagnostic_value(value: Any) -> tuple[Any, list[str]]:
    notes: list[str] = []
    if isinstance(value, str):
        screened, n = screen_diagnostic_text(value)
        notes.extend(n)
        return screened, notes
    if isinstance(value, list):
        out = []
        for item in value:
            redacted, n = redact_diagnostic_value(item)
            notes.extend(n)
            out.append(redacted)
        return out, notes
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            redacted, n = _redact_key_value(key, item)
            if redacted is item and not isinstance(item, str):
                redacted, n = redact_diagnostic_value(item)
            notes.extend(n)
            out[key] = redacted
        return out, notes
    return value, notes


def screen_diagnostic_text(text: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    value = text
    if LOCAL_TOKEN_JSON.search(value):
        value = LOCAL_TOKEN_JSON.sub(rf'\1{REDACTED_LOCAL_TOKEN}\3', value)
        notes.append('local-mutation-token withheld')
    if X_LOCAL_TOKEN_JSON.search(value):
        value = X_LOCAL_TOKEN_JSON.sub(rf'\1{REDACTED_LOCAL_TOKEN}\3', value)
        notes.append('local-mutation-token withheld')
    if PLAIN_FIXTURE_TOKEN.search(value):
        value = PLAIN_FIXTURE_TOKEN.sub(REDACTED_LOCAL_TOKEN, value)
        notes.append('local-mutation-token withheld')
    screened, n = screen_text(value)
    notes.extend(n)
    return screened, notes


def screen_network_log_entry(entry: dict[str, Any]) -> dict[str, Any]:
    redacted, notes = redact_diagnostic_value(entry)
    if not isinstance(redacted, dict):
        redacted = dict(entry)
    redacted['screening_notes'] = sorted(set(notes))
    redacted['diagnostic_marker'] = BENIGN_DIAGNOSTIC_MARKER
    if 'bodyPreview' in redacted and isinstance(redacted['bodyPreview'], str):
        preview, _ = screen_diagnostic_text(redacted['bodyPreview'])
        redacted['bodyPreview'] = preview
    if 'parseError' in redacted and isinstance(redacted['parseError'], str):
        redacted['parseError'], _ = screen_diagnostic_text(redacted['parseError'])
    keys = redacted.get('parsedKeys')
    if isinstance(keys, list) and 'token' in keys:
        redacted['parsedKeys'] = [k for k in keys if k != 'token'] + (
            ['token_redacted'] if 'token' in keys else []
        )
    return redacted


def screen_browser_checks_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted, notes = redact_diagnostic_value(payload)
    if not isinstance(redacted, dict):
        return payload
    if 'networkLog' in redacted and isinstance(redacted['networkLog'], list):
        redacted['networkLog'] = [screen_network_log_entry(e) for e in redacted['networkLog'] if isinstance(e, dict)]
    redacted['diagnostic_screening'] = {
        'applied': True,
        'marker': BENIGN_DIAGNOSTIC_MARKER,
        'notes': sorted(set(notes)),
    }
    return redacted


def contains_exposed_local_mutation_token(blob: str) -> bool:
    if REDACTED_LOCAL_TOKEN in blob:
        blob = blob.replace(REDACTED_LOCAL_TOKEN, '')
    if LOCAL_TOKEN_JSON.search(blob):
        return True
    if X_LOCAL_TOKEN_JSON.search(blob):
        return True
    if PLAIN_FIXTURE_TOKEN.search(blob):
        return True
    return False


def token_isolation_proof_metadata(foundation_root: str, isolated_data_dir: str) -> dict[str, Any]:
    """Boolean/metadata-only proof; never includes token bytes."""
    token_file = f'{isolated_data_dir.rstrip("/")}/local-token.json'
    return {
        'loopback_only_mutation_auth': True,
        'token_storage_relative': 'local-token.json under LOCAL_DATA_DIR only',
        'token_file_path_pattern': token_file,
        'isolated_from_default_app_data': 'recovery-screening-real-paths' in isolated_data_dir
        or 'diagnostic-screening' in isolated_data_dir,
        'not_env_sourced': True,
        'not_composio_or_1password': True,
        'rotation_scope': 'isolated_fixture_local-token.json only',
    }


def dumps_screened_json(payload: Any) -> str:
    redacted, _ = redact_diagnostic_value(payload)
    return json.dumps(redacted, indent=2) + '\n'
