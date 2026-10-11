"""Bounded npm/next build with process-group deadline and sanitized log capture."""
from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from subprocess_output import sanitize_diagnostic_text


def run_npm_build_bounded(
    *,
    app_dir: Path,
    reports_dir: Path,
    delivery_id: str,
    timeout_s: float = 600,
) -> dict:
    from subprocess_bounded import drain_stream_bounded, popen_group, terminate_group

    env = {**dict(os.environ), 'NEXT_TELEMETRY_DISABLED': '1'}
    log_dir = reports_dir / 'build-capture'
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    log_path = log_dir / f'{delivery_id}-build-{stamp}.log'
    proc = popen_group(
        ['npm', 'run', 'build'],
        cwd=str(app_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    pgid = None
    try:
        pgid = os.getpgid(proc.pid)
    except OSError:
        pgid = None
    timed_out = False
    combined = ''
    cleanup: dict = {}
    try:
        combined, _ = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        cleanup = terminate_group(proc, pgid=pgid)
        combined = drain_stream_bounded(proc.stdout)
        safe_partial = sanitize_diagnostic_text(combined or '')
        log_path.write_text(safe_partial + '\n[build_deadline_exceeded]\n', encoding='utf-8')
    exit_code = proc.returncode if proc.returncode is not None else (124 if timed_out else 1)
    safe = sanitize_diagnostic_text(combined or '')
    if not timed_out:
        log_path.write_text(safe, encoding='utf-8')
    enum = cleanup.get('enumeration') if cleanup else None
    reaped = proc.poll() is not None
    group_clean = bool(cleanup.get('group_clean_verified')) if cleanup else reaped
    tail = safe[-1200:] if safe else ''
    return {
        'build_exit': exit_code,
        'build_timed_out': timed_out,
        'build_deadline_seconds': timeout_s,
        'child_reaped_after_timeout': reaped and group_clean,
        'terminate_result': cleanup,
        'build_log_path': str(log_path),
        'build_phase_tail_sanitized': tail,
        'used_process_group_bounded_helper': True,
    }
