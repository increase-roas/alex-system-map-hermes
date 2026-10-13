// Run history and the duplicate-click guard.
//
// - Each run records the flow version it actually ran (hash + the exact bytes copied to run-inputs/).
// - One run per owner per flow at a time. A second request gets the running record back (409).
// - Idempotency-Key: a repeated request with the same key returns the first run, never a second one.
// - Histories are scoped to the owner and, when given, to the browser session (hashed, never raw).
// - A run that was still "running" when the backend restarted becomes "unknown", not "succeeded".
// - Stop kills the engine process. The UI only offers Stop because this path is verified in tests.

import { createHash, randomUUID } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

import { localDataDir } from '../server/paths';
import { contentHash } from './model';
import { clip, screenText } from './redact';
import { startLfxRun, type RunnerConfig, type RunOutcome, type StartedRun } from './runner';

export type RunStatus = 'running' | 'succeeded' | 'failed' | 'stopped' | 'unknown';

export type RunRecord = {
  id: string;
  flowId: string;
  flowName: string;
  flowHash: string;
  flowUpdatedAt: string;
  ownerId: string;
  sessionHash: string;
  idempotencyKey: string | null;
  status: RunStatus;
  engine: 'lfx';
  engineVersion: string;
  input: string;
  output: string | null;
  error: string | null;
  errorCode: string | null;
  startedAt: string;
  finishedAt: string | null;
};

export type BeginInput = {
  ownerId: string;
  sessionNonce: string | null;
  flowId: string;
  flowName: string;
  flowHash: string;
  flowUpdatedAt: string;
  flowSnapshot: string;
  input: string;
  idempotencyKey: string | null;
  config: RunnerConfig;
  engineVersion: string;
};

export type BeginResult =
  | { kind: 'created'; record: RunRecord }
  | { kind: 'duplicate'; record: RunRecord }
  | { kind: 'busy'; record: RunRecord };

type ActiveEntry = { runId: string; ownerId: string; key: string; run: StartedRun };
type Registry = { byRun: Map<string, ActiveEntry>; byKey: Map<string, string> };

const KEEP_RUNS = 300;
const OUTPUT_CHARS = 4000;

// Kept on globalThis so an HMR reload in development does not forget runs that are still going.
const g = globalThis as typeof globalThis & { __langflowRuns?: Registry };
function registry(): Registry {
  g.__langflowRuns ??= { byRun: new Map(), byKey: new Map() };
  return g.__langflowRuns;
}

function rootDir(root?: string): string {
  return root ?? localDataDir();
}

function runsFile(root?: string): string {
  return path.join(rootDir(root), 'langflow', 'runs.json');
}

export function hashSession(nonce: string | null): string {
  if (!nonce) return 'no-session';
  return createHash('sha256').update(nonce).digest('hex').slice(0, 32);
}

function readRuns(root?: string): RunRecord[] {
  const file = runsFile(root);
  if (!fs.existsSync(file)) return [];
  try {
    const parsed = JSON.parse(fs.readFileSync(file, 'utf8')) as unknown;
    if (Array.isArray(parsed)) return parsed as RunRecord[];
    throw new Error('not an array');
  } catch {
    // Never silently discard run history: keep the damaged file for inspection.
    fs.renameSync(file, `${file}.corrupt-${Date.now()}`);
    return [];
  }
}

function writeRuns(list: RunRecord[], root?: string): void {
  const file = runsFile(root);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const kept = list.slice(-KEEP_RUNS);
  const tmp = `${file}.${process.pid}.${randomUUID()}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(kept, null, 2) + '\n', { mode: 0o600 });
  fs.renameSync(tmp, file);
}

function statusFor(outcome: RunOutcome): RunStatus {
  if (outcome.status === 'succeeded') return 'succeeded';
  return outcome.code === 'stopped' ? 'stopped' : 'failed';
}

function finishRun(runId: string, outcome: RunOutcome, root?: string): void {
  const reg = registry();
  const entry = reg.byRun.get(runId);
  if (!entry) return;
  reg.byRun.delete(runId);
  if (reg.byKey.get(entry.key) === runId) reg.byKey.delete(entry.key);
  const list = readRuns(root);
  const record = list.find((r) => r.id === runId);
  if (!record) return;
  record.status = statusFor(outcome);
  record.finishedAt = new Date().toISOString();
  if (outcome.status === 'succeeded') {
    record.output = screenText(clip(outcome.output, OUTPUT_CHARS));
    record.error = null;
    record.errorCode = null;
  } else {
    record.output = null;
    record.error = screenText(clip(outcome.message, 1000));
    record.errorCode = outcome.code;
  }
  writeRuns(list, root);
}

export function beginRun(input: BeginInput, root?: string): BeginResult {
  const list = readRuns(root);
  const sessionHash = hashSession(input.sessionNonce);
  if (input.idempotencyKey) {
    const existing = list.find((r) => r.ownerId === input.ownerId && r.idempotencyKey === input.idempotencyKey);
    if (existing) return { kind: 'duplicate', record: existing };
  }
  const reg = registry();
  const key = `${input.ownerId}|${input.flowId}`;
  const busyId = reg.byKey.get(key);
  if (busyId) {
    const busy = list.find((r) => r.id === busyId);
    if (busy) return { kind: 'busy', record: busy };
  }
  if (contentHash(JSON.parse(input.flowSnapshot)) !== input.flowHash) {
    throw new Error('flow snapshot does not match the version being run');
  }
  const runId = randomUUID();
  const inputsDir = path.join(rootDir(root), 'langflow', 'run-inputs');
  fs.mkdirSync(inputsDir, { recursive: true });
  const flowFile = path.join(inputsDir, `${runId}.json`);
  fs.writeFileSync(flowFile, input.flowSnapshot, { mode: 0o600 });

  const record: RunRecord = {
    id: runId,
    flowId: input.flowId,
    flowName: input.flowName,
    flowHash: input.flowHash,
    flowUpdatedAt: input.flowUpdatedAt,
    ownerId: input.ownerId,
    sessionHash,
    idempotencyKey: input.idempotencyKey,
    status: 'running',
    engine: 'lfx',
    engineVersion: input.engineVersion,
    input: screenText(clip(input.input, 300)),
    output: null,
    error: null,
    errorCode: null,
    startedAt: new Date().toISOString(),
    finishedAt: null,
  };
  list.push(record);
  writeRuns(list, root);

  const run = startLfxRun({ flowFile, input: input.input }, input.config);
  reg.byRun.set(runId, { runId, ownerId: input.ownerId, key, run });
  reg.byKey.set(key, runId);
  void run.done.then((outcome) => finishRun(runId, outcome, root));
  return { kind: 'created', record };
}

export function stopRun(runId: string, ownerId: string): boolean {
  const entry = registry().byRun.get(runId);
  if (!entry || entry.ownerId !== ownerId) return false;
  return entry.run.stop();
}

export function listRuns(
  query: { ownerId: string; sessionNonce: string | null; flowId?: string },
  root?: string,
): RunRecord[] {
  const list = readRuns(root);
  const reg = registry();
  let changed = false;
  for (const record of list) {
    if (record.status === 'running' && !reg.byRun.has(record.id)) {
      record.status = 'unknown';
      record.finishedAt = null;
      record.error = 'The dashboard backend restarted while this run was going, so the result is unknown. Check the flow in Langflow before running it again.';
      record.errorCode = 'backend_restarted';
      changed = true;
    }
  }
  if (changed) writeRuns(list, root);
  const sessionHash = query.sessionNonce ? hashSession(query.sessionNonce) : null;
  return list
    .filter((r) => r.ownerId === query.ownerId)
    .filter((r) => (sessionHash ? r.sessionHash === sessionHash : true))
    .filter((r) => (query.flowId ? r.flowId === query.flowId : true))
    .sort((a, b) => b.startedAt.localeCompare(a.startedAt))
    .slice(0, 50);
}

export function findRun(runId: string, ownerId: string, root?: string): RunRecord | null {
  return readRuns(root).find((r) => r.id === runId && r.ownerId === ownerId) ?? null;
}
