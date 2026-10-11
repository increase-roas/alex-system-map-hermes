/** Bounded child-process helpers for browser acceptance runners. */
import { spawn } from 'node:child_process';

export function spawnGroup(cmd, args, opts = {}) {
  return spawn(cmd, args, { ...opts, detached: true, stdio: opts.stdio ?? 'pipe' });
}

export async function terminateGroup(proc, { graceMs = 1500, killMs = 15000 } = {}) {
  if (!proc?.pid) return { reaped: true };
  const done = new Promise((resolve) => {
    proc.once('close', () => resolve(true));
    proc.once('exit', () => resolve(true));
  });
  try {
    process.kill(-proc.pid, 'SIGTERM');
  } catch {
    try {
      proc.kill('SIGTERM');
    } catch {
      return { reaped: true };
    }
  }
  const grace = Promise.race([done, new Promise((r) => setTimeout(() => r(false), graceMs))]);
  if (await grace) return { reaped: true };
  try {
    process.kill(-proc.pid, 'SIGKILL');
  } catch {
    proc.kill('SIGKILL');
  }
  const killed = Promise.race([done, new Promise((r) => setTimeout(() => r(false), killMs))]);
  return { reaped: await killed };
}

export async function runWithDeadline(cmd, args, opts, deadlineMs) {
  const proc = spawnGroup(cmd, args, opts);
  return new Promise((resolve, reject) => {
    const timer = setTimeout(async () => {
      await terminateGroup(proc);
      reject(new Error(`${cmd} deadline ${deadlineMs}ms`));
    }, deadlineMs);
    proc.on('close', (code) => {
      clearTimeout(timer);
      resolve(code);
    });
    proc.on('error', (err) => {
      clearTimeout(timer);
      reject(err);
    });
  });
}
