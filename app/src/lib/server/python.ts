import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

import { ensureLocalDataDir, foundationRoot, localDataDir, localServiceScript, sqlitePath } from './paths';

const CANARY_PATTERN =
  /\bFAKE[-_]canary[-_]token[-_][A-Za-z0-9-]+\b|sk-fake-canary-rel06-do-not-use-[A-Za-z0-9]+/gi;
const PLAIN_FIXTURE_TOKEN = /\b[a-f0-9]{48}\b/gi;

function screenServiceText(value: string): string {
  return value
    .replace(CANARY_PATTERN, '[REDACTED test-canary]')
    .replace(PLAIN_FIXTURE_TOKEN, '[REDACTED local-mutation-token]')
    .replace(/sk-[A-Za-z0-9]{20,}/g, '[REDACTED credential-shaped value]')
    .replace(/(api[_-]?key\s*[:=]\s*)[^\s'"]+/gi, '$1[REDACTED credential-shaped value]');
}

function screenParsedValue(value: unknown): unknown {
  if (typeof value === 'string') {
    return screenServiceText(value);
  }
  if (Array.isArray(value)) {
    return value.map((item) => screenParsedValue(item));
  }
  if (value && typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const [key, item] of Object.entries(value)) {
      if (key === 'token' && typeof item === 'string' && /^[a-f0-9]{48}$/i.test(item)) {
        out[key] = '[REDACTED local-mutation-token]';
        continue;
      }
      out[key] = screenParsedValue(item);
    }
    return out;
  }
  return value;
}

export class LocalServiceError extends Error {
  constructor(
    message: string,
    readonly exitCode: number | null,
    readonly payload?: unknown,
  ) {
    super(message);
    this.name = 'LocalServiceError';
  }
}

const LOCAL_SERVICE_TIMEOUT_MS = 120_000;

export async function runLocalService(
  command: string[],
  input?: string,
): Promise<unknown> {
  ensureLocalDataDir();
  const args = [localServiceScript(), '--db', sqlitePath(), ...command];
  return new Promise((resolve, reject) => {
    const child = spawn('python3', args, {
      stdio: ['pipe', 'pipe', 'pipe'],
      env: {
        ...process.env,
        FOUNDATION_ROOT: foundationRoot(),
        ...(process.env.CATALOG_FIXTURE_ROOT
          ? { CATALOG_FIXTURE_ROOT: process.env.CATALOG_FIXTURE_ROOT }
          : {}),
      },
    });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });
    const timer = setTimeout(() => {
      child.kill('SIGKILL');
      reject(new LocalServiceError('local service deadline exceeded', null));
    }, LOCAL_SERVICE_TIMEOUT_MS);
    child.on('error', (err) => {
      clearTimeout(timer);
      reject(err);
    });
    child.on('close', (code) => {
      clearTimeout(timer);
      const exitCode = code ?? 1;
      const trimmed = stdout.trim();
      if (!trimmed) {
        reject(
          new LocalServiceError(
            screenServiceText(stderr) || 'empty local service response',
            exitCode,
            { stderr: screenServiceText(stderr) },
          ),
        );
        return;
      }
      try {
        const payload = screenParsedValue(JSON.parse(trimmed)) as Record<string, unknown>;
        const nestedError =
          payload?.error ??
          (payload?.payload && typeof payload.payload === 'object'
            ? (payload.payload as { error?: string }).error
            : undefined);
        if (nestedError) {
          reject(
            new LocalServiceError(screenServiceText(String(nestedError)), exitCode, {
              ...payload,
              error: screenServiceText(String(nestedError)),
            }),
          );
          return;
        }
        if (exitCode !== 0) {
          reject(
            new LocalServiceError('local service exited nonzero', exitCode, payload),
          );
          return;
        }
        resolve(payload);
      } catch {
        reject(
          new LocalServiceError('invalid JSON from local service', exitCode, {
            stdout: screenServiceText(stdout.slice(0, 4000)),
            stderr: screenServiceText(stderr.slice(0, 4000)),
          }),
        );
      }
    });
    if (input) {
      child.stdin.write(input);
    }
    child.stdin.end();
  });
}

const INIT_MARKER = '.service-initialized';

export async function ensureServiceInitialized(): Promise<void> {
  ensureLocalDataDir();
  const marker = `${localDataDir()}/${INIT_MARKER}`;
  if (!fs.existsSync(marker) || !fs.existsSync(sqlitePath())) {
    await runLocalService(['init']);
    await runLocalService(['sync-observe']);
    fs.writeFileSync(marker, new Date().toISOString());
  }
  const traceRows = await runLocalService(['trace-list']);
  const traceCount = Array.isArray(traceRows)
    ? traceRows.length
    : Array.isArray((traceRows as { traces?: unknown[] })?.traces)
      ? (traceRows as { traces: unknown[] }).traces.length
      : Array.isArray((traceRows as { payload?: { traces?: unknown[] } })?.payload?.traces)
        ? (traceRows as { payload: { traces: unknown[] } }).payload.traces.length
        : 0;
  if (traceCount === 0) {
    const fixture = path.join(foundationRoot(), 'examples', 'agent-trace-fixture.json');
    if (fs.existsSync(fixture)) {
      await runLocalService(['trace-import', fixture]);
    }
  }
}
