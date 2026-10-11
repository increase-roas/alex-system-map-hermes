"""Interrupting deadlines for isolated catalog clone preparation (process groups + cleanup proof)."""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Callable, Sequence, TypeVar

from subprocess_output import sanitize_diagnostic_text

DEFAULT_PREP_DEADLINE_S = 600
RM_DEADLINE_S = 120
CP_DEADLINE_S = 540

T = TypeVar('T')


class PreparationDeadlineExceeded(RuntimeError):
    pass


class OverallPreparationDeadline:
    """Interrupting wall-clock budget; call check() before/inside long steps."""

    def __init__(self, seconds: float) -> None:
        self.deadline_s = seconds
        self.started = time.monotonic()

    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def remaining(self) -> float:
        return self.deadline_s - self.elapsed()

    def check(self, phase: str) -> None:
        if self.elapsed() > self.deadline_s:
            raise PreparationDeadlineExceeded(f'{phase} exceeded overall preparation deadline {self.deadline_s}s')


def run_under_overall_deadline(deadline: OverallPreparationDeadline, fn: Callable[[], T], *, phase: str) -> T:
    deadline.check(phase)
    out = fn()
    deadline.check(phase)
    return out


def run_group_with_deadline(
    cmd: Sequence[str],
    *,
    cwd: str | Path | None = None,
    timeout_s: float,
    label: str,
    overall: OverallPreparationDeadline | None = None,
) -> dict:
    from subprocess_bounded import drain_stream_bounded, enumerate_process_group, popen_group, terminate_group

    if overall is not None:
        overall.check(label)
        timeout_s = min(timeout_s, max(1.0, overall.remaining()))
    started = time.monotonic()
    proc = popen_group(
        list(cmd),
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    pgid: int | None = None
    try:
        pgid = os.getpgid(proc.pid)
    except OSError:
        pgid = None
    timed_out = False
    combined = ''
    exit_code: int | None = None
    cleanup: dict = {}
    try:
        combined, _ = proc.communicate(timeout=timeout_s)
        exit_code = proc.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
        cleanup = terminate_group(proc, pgid=pgid)
        combined = drain_stream_bounded(proc.stdout)
        exit_code = proc.returncode if proc.returncode is not None else 124
    elapsed = time.monotonic() - started
    enum = enumerate_process_group(pgid) if pgid is not None else {'status': 'skipped', 'pids': None}
    reaped = proc.poll() is not None
    group_clean = enum['status'] == 'ok' and not enum['pids']
    return {
        'label': label,
        'cmd': list(cmd),
        'exit_code': exit_code,
        'timed_out': timed_out,
        'elapsed_seconds': round(elapsed, 3),
        'deadline_seconds': timeout_s,
        'pgid': pgid,
        'child_reaped': reaped,
        'terminate_result': cleanup,
        'enumeration_after': enum,
        'group_clean_verified': group_clean if enum['status'] == 'ok' else False,
        'enumeration_status': enum['status'],
        'stdout_tail_sanitized': sanitize_diagnostic_text(combined or ''),
    }


def remove_tree_bounded(
    dest: Path,
    *,
    timeout_s: float = RM_DEADLINE_S,
    overall: OverallPreparationDeadline | None = None,
) -> dict:
    if not dest.exists():
        return {'removed': False, 'missing': True}
    return run_group_with_deadline(
        ['rm', '-rf', str(dest)],
        timeout_s=timeout_s,
        label='rm_isolated_dest',
        overall=overall,
    )
