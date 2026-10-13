// Runs one saved flow with Langflow's own engine (the `lfx` command from the pinned langflow
// 1.12.5 install). No server, no port: the engine runs as a child process of the dashboard
// backend. Arguments go in as an array (no shell), the environment is minimal (no provider keys),
// and the child is killed when it times out or when a run is stopped.

import { spawn, type ChildProcess } from 'node:child_process';
import fs from 'node:fs';

export const PINNED_LANGFLOW_VERSION = '1.12.5';
const MAX_CAPTURE_BYTES = 2_000_000;

export type RunnerConfig = { lfxBin: string | null; configDir: string | null; timeoutMs: number };

export function runnerConfig(env: NodeJS.ProcessEnv = process.env): RunnerConfig {
  const timeout = Number(env.LANGFLOW_RUN_TIMEOUT_MS);
  return {
    lfxBin: env.LANGFLOW_LFX_BIN || null,
    configDir: env.LANGFLOW_CONFIG_DIR || null,
    timeoutMs: Number.isFinite(timeout) && timeout > 0 ? timeout : 120_000,
  };
}

export type RunOutcome =
  | { status: 'succeeded'; output: string; component: string | null }
  | { status: 'failed'; code: 'not_configured' | 'missing_binary' | 'timeout' | 'engine_error' | 'bad_output' | 'stopped'; message: string };

export type StartedRun = {
  pid: number | null;
  done: Promise<RunOutcome>;
  stop: () => boolean;
};

function failed(code: Extract<RunOutcome, { status: 'failed' }>['code'], message: string): StartedRun {
  return { pid: null, done: Promise.resolve({ status: 'failed', code, message }), stop: () => false };
}

function lastJsonLine(text: string): Record<string, unknown> | null {
  const lines = text.split('\n').map((l) => l.trim()).filter((l) => l.startsWith('{'));
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    try {
      const parsed = JSON.parse(lines[i]) as unknown;
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) return parsed as Record<string, unknown>;
    } catch {
      // keep looking
    }
  }
  return null;
}

export function startLfxRun(args: { flowFile: string; input: string }, config: RunnerConfig): StartedRun {
  if (!config.lfxBin) {
    return failed('not_configured', 'The Langflow engine is not configured. Set LANGFLOW_LFX_BIN to the pinned lfx binary.');
  }
  if (!fs.existsSync(config.lfxBin)) {
    return failed('missing_binary', 'The Langflow engine binary was not found at the configured path.');
  }
  const env: Record<string, string> = {
    PATH: process.env.PATH ?? '/usr/bin:/bin',
    HOME: process.env.HOME ?? '',
    TMPDIR: process.env.TMPDIR ?? '/tmp',
    DO_NOT_TRACK: 'true',
    LANGFLOW_AUTO_LOGIN: 'True',
    LANGFLOW_LOG_LEVEL: 'error',
  };
  if (config.configDir) env.LANGFLOW_CONFIG_DIR = config.configDir;

  let child: ChildProcess;
  try {
    child = spawn(config.lfxBin, ['run', args.flowFile, '--input-value', args.input, '-f', 'json'], {
      // Node's type insists on NODE_ENV; the engine does not read it, so the cast only satisfies the type.
      env: env as NodeJS.ProcessEnv,
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: true,
    });
  } catch {
    return failed('engine_error', 'The Langflow engine could not be started.');
  }

  let stdout = '';
  let stderr = '';
  let timedOut = false;
  let stopped = false;
  const killGroup = () => {
    try {
      if (child.pid) process.kill(-child.pid, 'SIGKILL');
    } catch {
      child.kill('SIGKILL');
    }
  };
  child.stdout?.on('data', (chunk: Buffer) => {
    if (stdout.length < MAX_CAPTURE_BYTES) stdout += chunk.toString('utf8');
  });
  child.stderr?.on('data', (chunk: Buffer) => {
    if (stderr.length < MAX_CAPTURE_BYTES) stderr += chunk.toString('utf8');
  });
  const timer = setTimeout(() => {
    timedOut = true;
    killGroup();
  }, config.timeoutMs);

  const done = new Promise<RunOutcome>((resolve) => {
    child.on('error', () => {
      clearTimeout(timer);
      resolve({ status: 'failed', code: 'engine_error', message: 'The Langflow engine stopped with an error before it finished.' });
    });
    child.on('close', () => {
      clearTimeout(timer);
      if (stopped) {
        resolve({ status: 'failed', code: 'stopped', message: 'Stopped by you. The engine process was killed; the flow may have partly run.' });
        return;
      }
      if (timedOut) {
        resolve({ status: 'failed', code: 'timeout', message: `The run took longer than ${Math.round(config.timeoutMs / 1000)} seconds and was stopped.` });
        return;
      }
      const parsed = lastJsonLine(stdout);
      if (parsed && parsed.success === true) {
        const result = typeof parsed.result === 'string' ? parsed.result : JSON.stringify(parsed.result ?? null);
        resolve({ status: 'succeeded', output: result, component: typeof parsed.component === 'string' ? parsed.component : null });
        return;
      }
      if (parsed && parsed.success === false) {
        const detail = typeof parsed.exception_message === 'string' ? parsed.exception_message : 'The flow reported an error.';
        resolve({ status: 'failed', code: 'engine_error', message: detail });
        return;
      }
      resolve({
        status: 'failed',
        code: 'bad_output',
        message: `The engine finished without a readable result${stderr.trim() ? '.' : ''}`,
      });
    });
  });

  return {
    pid: child.pid ?? null,
    done,
    stop: () => {
      if (stopped || timedOut) return false;
      stopped = true;
      killGroup();
      return true;
    },
  };
}
