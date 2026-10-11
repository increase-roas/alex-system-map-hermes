"""Write-once receipt bytes; hashes live in external manifest/history only."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def receipt_bytes(payload: dict) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + '\n').encode()


def write_final_receipt_once(path: Path, payload: dict) -> tuple[Path, str]:
    """Create receipt file exactly once; return path and content sha256."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = receipt_bytes(payload)
    digest = sha256_bytes(data)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(str(path), flags, 0o644)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    return path, digest


def write_or_verify_same_bytes(path: Path, payload: dict) -> tuple[Path, str, bool]:
    """Idempotent: if file exists with same bytes, accept; else exclusive create."""
    data = receipt_bytes(payload)
    digest = sha256_bytes(data)
    if path.is_file():
        existing = path.read_bytes()
        if existing == data:
            return path, digest, True
        raise FileExistsError(f'receipt bytes differ at {path}')
    return *write_final_receipt_once(path, payload), False


def append_manifest(manifest_path: Path, entry: dict) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, sort_keys=True) + '\n'
    with manifest_path.open('a') as handle:
        handle.write(line)


def reconcile_receipt_hash(path: Path, previously_declared_sha256: str | None) -> dict:
    if not path.is_file():
        return {
            'path': str(path),
            'exists': False,
            'actual_sha256': None,
            'previously_declared_sha256': previously_declared_sha256,
            'hash_matches_declared': False,
            'note': 'bytes_not_recoverable',
        }
    actual = sha256_file(path)
    return {
        'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        'exists': True,
        'actual_sha256': actual,
        'previously_declared_sha256': previously_declared_sha256,
        'hash_matches_declared': previously_declared_sha256 == actual if previously_declared_sha256 else None,
    }
