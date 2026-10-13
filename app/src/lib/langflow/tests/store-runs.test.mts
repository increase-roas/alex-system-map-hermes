import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { test } from 'node:test';

import { contentHash, type LfFlow } from '../model';
import { createFlow, listFlows, listHistory, readFlow, saveFlow, StoreConflictError } from '../store';
import { beginRun, hashSession, listRuns, stopRun, type RunRecord } from '../runs';
import type { RunnerConfig } from '../runner';

const root = fs.mkdtempSync(path.join(process.env.TMPDIR ?? os.tmpdir(), 'lf-store-'));
const chatEcho = (): LfFlow => JSON.parse(fs.readFileSync(new URL('../fixtures/chat-echo.json', import.meta.url), 'utf8')) as LfFlow;

function fakeLfx(body: string): string {
  const file = path.join(root, `fake-lfx-${randomUUID()}.sh`);
  fs.writeFileSync(file, `#!/bin/sh\n${body}\n`, { mode: 0o755 });
  return file;
}
const cfg = (lfxBin: string | null, timeoutMs = 30_000): RunnerConfig => ({ lfxBin, configDir: null, timeoutMs });

async function until<T>(read: () => T | undefined, ms = 10_000): Promise<T> {
  const started = Date.now();
  for (;;) {
    const v = read();
    if (v !== undefined) return v;
    if (Date.now() - started > ms) throw new Error('timed out waiting');
    await new Promise((r) => setTimeout(r, 50));
  }
}

test('store: create, read and list a flow; the hash matches the saved content', () => {
  const flow = chatEcho();
  const made = createFlow(flow, root);
  const read = readFlow(made.id, root);
  assert.ok(read);
  assert.equal(read.hash, contentHash(flow));
  const listed = listFlows(root).find((f) => f.id === made.id);
  assert.equal(listed?.nodeCount, 2);
});

test('store: a save with a stale hash is refused and the current hash is returned', () => {
  const made = createFlow(chatEcho(), root);
  const edited = { ...chatEcho(), name: 'changed elsewhere' };
  saveFlow(made.id, edited, made.hash, root);
  assert.throws(() => saveFlow(made.id, { ...edited, name: 'stale edit' }, made.hash, root), (err: unknown) => {
    return err instanceof StoreConflictError && err.currentHash === contentHash(edited);
  });
});

test('store: every save keeps the previous version so it can be rolled back', () => {
  const original = chatEcho();
  const made = createFlow(original, root);
  saveFlow(made.id, { ...original, name: 'v2' }, made.hash, root);
  const history = listHistory(made.id, root);
  assert.equal(history.length, 1);
  const previous = JSON.parse(fs.readFileSync(path.join(root, 'langflow', 'history', made.id, history[0]), 'utf8')) as LfFlow;
  assert.equal(previous.name, original.name, 'history holds the version before the save');
});

test('store: ids that are not plain identifiers never reach the disk', () => {
  assert.equal(readFlow('../../etc/passwd', root), null);
  assert.equal(readFlow('abc', root), null, 'too short to be an id');
});

test('runs: a second request for the same owner and flow is refused while one is running', async () => {
  const flowId = randomUUID();
  const flow = chatEcho();
  const bin = fakeLfx('sleep 30');
  const snapshot = JSON.stringify(flow);
  const base = { ownerId: 'owner', sessionNonce: 'sess-1', flowId, flowName: 'Chat echo', flowHash: contentHash(flow), flowUpdatedAt: 'now', flowSnapshot: snapshot, input: 'hi', engineVersion: '1.12.5' };
  const first = beginRun({ ...base, idempotencyKey: 'k-1', config: cfg(bin) }, root);
  assert.equal(first.kind, 'created');
  const second = beginRun({ ...base, idempotencyKey: 'k-2', config: cfg(bin) }, root);
  assert.equal(second.kind, 'busy');
  assert.equal(second.record.id, first.record.id, 'the running record is returned, no new run starts');
  assert.equal(stopRun(first.record.id, 'someone-else'), false, 'only the owner of a run can stop it');
  assert.equal(stopRun(first.record.id, 'owner'), true);
  const finished = await until(() => {
    const r = listRuns({ ownerId: 'owner', sessionNonce: 'sess-1', flowId }, root).find((x) => x.id === first.record.id);
    return r && r.status !== 'running' ? r : undefined;
  });
  assert.equal(finished.status, 'stopped');
  const repeat = beginRun({ ...base, idempotencyKey: 'k-1', config: cfg(bin) }, root);
  assert.equal(repeat.kind, 'duplicate', 'the same Idempotency-Key returns the first run');
  assert.equal(repeat.record.id, first.record.id);
});

test('runs: a finished run records the flow version it ran, the output, and no secrets', async () => {
  const flowId = randomUUID();
  const flow = chatEcho();
  // Built at runtime so the source never holds a key-shaped literal. The value is a fake canary.
  const canary = ['sk', 'FAKEcanaryKEY0123456789abcdef'].join('-');
  const bin = fakeLfx(`echo '{"success": true, "result": "reply ${canary} done"}'`);
  const begun = beginRun({ ownerId: 'owner', sessionNonce: 's', flowId, flowName: 'Chat echo', flowHash: contentHash(flow), flowUpdatedAt: 'then', flowSnapshot: JSON.stringify(flow), input: 'hello', idempotencyKey: null, engineVersion: '1.12.5', config: cfg(bin) }, root);
  assert.equal(begun.kind, 'created');
  const done = await until(() => {
    const r = listRuns({ ownerId: 'owner', sessionNonce: 's', flowId }, root).find((x) => x.id === begun.record.id);
    return r && r.status !== 'running' ? r : undefined;
  });
  assert.equal(done.status, 'succeeded');
  assert.equal(done.flowHash, contentHash(flow));
  assert.equal(done.engineVersion, '1.12.5');
  assert.ok(done.output?.includes('[redacted key]'), done.output ?? '');
  assert.ok(!done.output?.includes('FAKEcanaryKEY'));
  assert.ok(!done.output?.includes(canary));
  const pinned = fs.readFileSync(path.join(root, 'langflow', 'run-inputs', `${begun.record.id}.json`), 'utf8');
  assert.equal(contentHash(JSON.parse(pinned) as LfFlow), done.flowHash, 'the copy that ran matches the recorded version');
});

test('runs: a history is only visible to the browser session that made it', async () => {
  const flowId = randomUUID();
  const flow = chatEcho();
  const bin = fakeLfx('echo \'{"success": true, "result": "ok"}\'');
  const base = { ownerId: 'owner', flowId, flowName: 'Chat echo', flowHash: contentHash(flow), flowUpdatedAt: 'then', flowSnapshot: JSON.stringify(flow), input: 'x', idempotencyKey: null, engineVersion: '1.12.5', config: cfg(bin) };
  const a = beginRun({ ...base, sessionNonce: 'session-A' }, root);
  await until(() => {
    const r = listRuns({ ownerId: 'owner', sessionNonce: 'session-A', flowId }, root).find((x) => x.id === a.record.id);
    return r && r.status !== 'running' ? r : undefined;
  });
  const seenByB = listRuns({ ownerId: 'owner', sessionNonce: 'session-B', flowId }, root);
  assert.equal(seenByB.length, 0, 'session B does not see session A runs');
  const seenByA = listRuns({ ownerId: 'owner', sessionNonce: 'session-A', flowId }, root);
  assert.equal(seenByA.length, 1);
  assert.equal(seenByA[0].sessionHash, hashSession('session-A'));
  const stored = fs.readFileSync(path.join(root, 'langflow', 'runs.json'), 'utf8');
  assert.ok(!stored.includes('session-A'), 'raw browser session ids are never stored');
});

test('runs: a run still marked running after a backend restart becomes unknown, not succeeded', () => {
  const ghost: RunRecord = {
    id: randomUUID(), flowId: 'flow-ghost', flowName: 'Ghost', flowHash: 'h', flowUpdatedAt: 'then', ownerId: 'owner',
    sessionHash: hashSession('s'), idempotencyKey: null, status: 'running', engine: 'lfx', engineVersion: '1.12.5',
    input: 'x', output: null, error: null, errorCode: null, startedAt: new Date().toISOString(), finishedAt: null,
  };
  const file = path.join(root, 'langflow', 'runs.json');
  const existing = fs.existsSync(file) ? (JSON.parse(fs.readFileSync(file, 'utf8')) as RunRecord[]) : [];
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify([...existing, ghost]));
  const seen = listRuns({ ownerId: 'owner', sessionNonce: 's', flowId: 'flow-ghost' }, root);
  assert.equal(seen[0].status, 'unknown');
  assert.equal(seen[0].errorCode, 'backend_restarted');
});

test('runs: a snapshot that does not match the claimed version is refused before anything runs', () => {
  const flow = chatEcho();
  assert.throws(() => beginRun({ ownerId: 'owner', sessionNonce: 's', flowId: randomUUID(), flowName: 'x', flowHash: 'not-the-hash', flowUpdatedAt: 'then', flowSnapshot: JSON.stringify(flow), input: 'x', idempotencyKey: null, engineVersion: '1.12.5', config: cfg(null) }, root), /does not match/);
});
