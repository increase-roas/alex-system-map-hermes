"""Bounded subprocess helpers (process groups, TimeoutExpired without .process)."""
from __future__ import annotations

import os
import select
import signal
import subprocess
import time
from typing import Sequence

from subprocess_output import sanitize_diagnostic_text

PGREP_ENUM_TIMEOUT_S = 5.0
PIPE_DRAIN_TIMEOUT_S = 2.0
WAIT_AFTER_TERM_S = 15.0


def popen_group(cmd: Sequence[str], **kwargs) -> subprocess.Popen[str]:
    return subprocess.Popen(
        list(cmd),
        start_new_session=True,
        **kwargs,
    )


def enumerate_process_group(pgid: int) -> dict:
    """Never treat enumeration failure as verified-empty."""
    try:
        out = subprocess.run(
            ['pgrep', '-g', str(pgid)],
            capture_output=True,
            text=True,
            timeout=PGREP_ENUM_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return {'status': 'timeout', 'pids': None}
    except OSError as exc:
        return {'status': 'error', 'pids': None, 'error': type(exc).__name__}
    pids = [int(x) for x in (out.stdout or '').split() if x.isdigit()]
    if out.returncode not in (0, 1):
        return {'status': 'error', 'pids': None, 'exit_code': out.returncode}
    return {'status': 'ok', 'pids': pids}


def drain_stream_bounded(stream, *, timeout_s: float = PIPE_DRAIN_TIMEOUT_S) -> str:
    if stream is None:
        return ''
    chunks: list[str] = []
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            ready, _, _ = select.select([stream], [], [], 0.1)
        except (ValueError, OSError):
            break
        if not ready:
            continue
        try:
            piece = stream.read(4096)
        except (ValueError, OSError):
            break
        if not piece:
            break
        chunks.append(piece)
    return sanitize_diagnostic_text(''.join(chunks))


def terminate_group(
    proc: subprocess.Popen | None,
    *,
    pgid: int | None = None,
) -> dict:
    """SIGTERM/SIGKILL process group; enumerate survivors (unknown on enum failure)."""
    result: dict = {
        'leader_reaped': False,
        'enumeration': {'status': 'skipped', 'pids': None},
        'group_clean_verified': False,
    }
    if proc is None:
        return result
    if pgid is None:
        try:
            pgid = os.getpgid(proc.pid)
        except OSError:
            pgid = None
    if pgid is not None:
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(pgid, sig)
            except (ProcessLookupError, PermissionError, OSError):
                pass
            enum = enumerate_process_group(pgid)
            result['enumeration'] = enum
            if enum['status'] == 'ok' and not enum['pids']:
                break
    if proc.poll() is None:
        try:
            proc.terminate()
        except OSError:
            pass
        try:
            proc.wait(timeout=WAIT_AFTER_TERM_S)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except OSError:
                pass
            proc.wait(timeout=WAIT_AFTER_TERM_S)
    result['leader_reaped'] = proc.poll() is not None
    if pgid is not None and result['enumeration'].get('status') == 'ok':
        result['group_clean_verified'] = not result['enumeration']['pids']
    return result


def run_bounded(
    cmd: Sequence[str],
    *,
    timeout: float,
    **kwargs,
) -> subprocess.CompletedProcess[str]:
    if kwargs.get('capture_output'):
        kwargs.pop('capture_output', None)
        kwargs.setdefault('stdout', subprocess.PIPE)
        kwargs.setdefault('stderr', subprocess.PIPE)
        kwargs.setdefault('text', True)
    proc = popen_group(cmd, **kwargs)
    pgid = None
    try:
        pgid = os.getpgid(proc.pid)
    except OSError:
        pgid = None
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return subprocess.CompletedProcess(list(cmd), proc.returncode or 0, stdout, stderr)
    except subprocess.TimeoutExpired:
        terminate_group(proc, pgid=pgid)
        drain_stream_bounded(proc.stdout)
        drain_stream_bounded(proc.stderr)
        raise
