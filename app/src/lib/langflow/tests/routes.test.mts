// Calls the real Next.js route handlers with synthetic requests. No port is opened, so this runs in
// the sandbox. It proves the HTTP contract: status codes, version checks, tailnet denial, run gate,
// duplicate clicks and stop. It does not prove the browser, the network path or Tailscale.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { after, before, test } from 'node:test';

import { getOrCreateLocalToken } from '../../server/local-auth';
import * as statusRoute from '../../../app/api/langflow/status/route';
import * as flowsRoute from '../../../app/api/langflow/flows/route';
import * as flowRoute from '../../../app/api/langflow/flows/[flowId]/route';
import * as exportRoute from '../../../app/api/langflow/flows/[flowId]/export/route';
import * as runsRoute from '../../../app/api/langflow/flows/[flowId]/runs/route';
import * as stopRoute from '../../../app/api/langflow/runs/[runId]/stop/route';

const tmp = fs.mkdtempSync(path.join(process.env.TMPDIR ?? os.tmpdir(), 'lf-routes-'));
const chatEcho = JSON.parse(fs.readFileSync(new URL('../fixtures/chat-echo.json', import.meta.url), 'utf8')) as Record<string, unknown>;
const BASE = 'http://127.0.0.1:3200';

type Opts = { body?: unknown; raw?: string; tailnet?: string; token?: boolean; session?: string; headers?: Record<string, string> };
function req(method: string, pathname: string, opts: Opts = {}): Request {
  const headers = new Headers({ host: '127.0.0.1:3200', ...(opts.headers ?? {}) });
  if (opts.tailnet) {
    headers.set('host', 'mac.tailnet.ts.net');
    headers.set('tailscale-user-login', opts.tailnet);
  } else if (opts.token !== false) {
    headers.set('x-local-token', getOrCreateLocalToken());
  }
  if (opts.session) headers.set('x-browser-session', opts.session);
  let body: string | undefined;
  if (opts.raw !== undefined) body = opts.raw;
  else if (opts.body !== undefined) body = JSON.stringify(opts.body);
  if (body !== undefined) headers.set('content-type', 'application/json');
  return new Request(BASE + pathname, { method, headers, body });
}
const params = <T extends Record<string, string>>(v: T) => ({ params: Promise.resolve(v) });
const json = async (res: Response) => ({ status: res.status, body: (await res.json()) as Record<string, unknown> });

const SESSION = 'session-test-0001';
let flowId = '';
let hash = '';

before(() => {
  process.env.LOCAL_DATA_DIR = tmp;
  fs.mkdirSync(path.join(tmp, 'langflow'), { recursive: true });
});
after(() => {
  delete process.env.LANGFLOW_LFX_BIN;
});

test('status: a tailnet device that is not listed is refused; the owner sees save and run', async () => {
  const stranger = await json(await statusRoute.GET(req('GET', '/api/langflow/status', { tailnet: 'stranger@example.com' })));
  assert.equal(stranger.status, 403);
  const owner = await json(await statusRoute.GET(req('GET', '/api/langflow/status')));
  assert.equal(owner.status, 200);
  assert.equal(owner.body.caller.canSave, true);
  assert.equal(owner.body.caller.canRun, true);
  const reader = await json(await statusRoute.GET(req('GET', '/api/langflow/status', { token: false })));
  assert.equal(reader.status, 200);
  assert.equal(reader.body.caller.canSave, false, 'no token means read only');
});

test('import: bad input is refused with a reason; only the owner can import', async () => {
  assert.equal((await json(await flowsRoute.POST(req('POST', '/api/langflow/flows', { raw: 'not json' })))).status, 422);
  assert.equal((await json(await flowsRoute.POST(req('POST', '/api/langflow/flows', { body: { hello: 1 } })))).status, 422);
  assert.equal((await json(await flowsRoute.POST(req('POST', '/api/langflow/flows', { body: chatEcho, token: false })))).status, 403);
  assert.equal((await json(await flowsRoute.POST(req('POST', '/api/langflow/flows', { body: chatEcho, tailnet: 'alex@example.com' })))).status, 403);
  const made = await json(await flowsRoute.POST(req('POST', '/api/langflow/flows', { body: chatEcho })));
  assert.equal(made.status, 201);
  flowId = made.body.id as string;
  hash = made.body.hash as string;
  assert.ok(flowId.length >= 8);
});

test('import: a flow with a broken connection is refused, not saved', async () => {
  const broken = structuredClone(chatEcho) as { data: { edges: Array<{ sourceHandle: string }> } };
  broken.data.edges[0].sourceHandle = 'broken';
  const res = await json(await flowsRoute.POST(req('POST', '/api/langflow/flows', { body: broken })));
  assert.equal(res.status, 422);
  assert.match(res.body.error, /errors that must be fixed/);
});

test('import: secret values are removed on the way in and reported', async () => {
  const withSecret = structuredClone(chatEcho) as { data: { nodes: Array<{ data: { node: { template: Record<string, unknown> } } }> } };
  withSecret.data.nodes[1].data.node.template.api_key = { type: 'str', password: true, value: 'FAKE-canary-route-secret', show: true, display_name: 'Key' };
  const made = await json(await flowsRoute.POST(req('POST', '/api/langflow/flows', { body: withSecret })));
  assert.equal(made.status, 201);
  assert.equal(made.body.secretsRemoved, 1);
  const exported = await exportRoute.GET(req('GET', `/api/langflow/flows/${made.body.id}/export`), params({ flowId: made.body.id as string }));
  const text = await exported.text();
  assert.ok(!text.includes('FAKE-canary-route-secret'));
  assert.equal(exported.headers.get('x-secrets-redacted'), '0');
});

test('list and detail: the saved flow is shown with its version and no secret values', async () => {
  const list = await json(await flowsRoute.GET(req('GET', '/api/langflow/flows')));
  assert.equal(list.status, 200);
  assert.ok((list.body.flows as Array<{ id: string }>).some((f) => f.id === flowId));
  const detail = await flowRoute.GET(req('GET', `/api/langflow/flows/${flowId}`), params({ flowId }));
  const body = await json(detail);
  assert.equal(body.status, 200);
  assert.equal(body.body.hash, hash);
  assert.equal(body.body.runnable, true);
  assert.equal(body.body.canvas.nodes.length, 2);
  assert.equal(body.body.caller.canSave, true);
});

test('save: a stale version is refused; a valid move saves; a refused edit saves nothing', async () => {
  const stale = await json(await flowRoute.PATCH(req('PATCH', `/api/langflow/flows/${flowId}`, { body: { expectedHash: 'stale', edits: [] } }), params({ flowId })));
  assert.equal(stale.status, 409);
  assert.equal(stale.body.currentHash, hash);

  const moved = await json(await flowRoute.PATCH(req('PATCH', `/api/langflow/flows/${flowId}`, {
    body: { expectedHash: hash, edits: [{ kind: 'move', nodeId: ((chatEcho.data as { nodes: Array<{ id: string }> }).nodes[0]).id, position: { x: 300, y: 300 } }] },
  }), params({ flowId })));
  assert.equal(moved.status, 200);
  assert.equal(moved.body.applied, 1);
  assert.notEqual(moved.body.hash, hash);
  hash = moved.body.hash as string;

  const codeNode = ((chatEcho.data as { nodes: Array<{ id: string; data: { type: string } }> }).nodes.find((n) => n.data.type === 'ChatInput'))!;
  const refused = await json(await flowRoute.PATCH(req('PATCH', `/api/langflow/flows/${flowId}`, {
    body: { expectedHash: hash, edits: [{ kind: 'move', nodeId: codeNode.id, position: { x: 1, y: 1 } }, { kind: 'setField', nodeId: codeNode.id, field: 'code', value: 'import os' }] },
  }), params({ flowId })));
  assert.equal(refused.status, 422);
  assert.match(refused.body.rejected[0].reason, /native editor/);
  const after = await json(await flowRoute.GET(req('GET', `/api/langflow/flows/${flowId}`), params({ flowId })));
  assert.equal(after.body.hash, hash, 'nothing from the refused save was written');
});

test('save: malformed edits are refused before they reach the model', async () => {
  const res = await json(await flowRoute.PATCH(req('PATCH', `/api/langflow/flows/${flowId}`, {
    body: { expectedHash: hash, edits: [{ kind: 'move', nodeId: 'x' }] },
  }), params({ flowId })));
  assert.equal(res.status, 422);
});

test('tailnet: a listed device can read but not save or run', async () => {
  const fs2 = path.join(tmp, 'langflow', 'access.json');
  fs.writeFileSync(fs2, JSON.stringify({ owner: { ops: ['read', 'save', 'run', 'stop'], flows: '*' }, tailnet: { 'alex@example.com': { ops: ['read', 'run', 'save'], flows: '*' } } }));
  try {
    const read = await json(await flowRoute.GET(req('GET', `/api/langflow/flows/${flowId}`, { tailnet: 'alex@example.com' }), params({ flowId })));
    assert.equal(read.status, 200);
    assert.equal(read.body.caller.canSave, false);
    const save = await json(await flowRoute.PATCH(req('PATCH', `/api/langflow/flows/${flowId}`, { tailnet: 'alex@example.com', body: { expectedHash: hash, edits: [] } }), params({ flowId })));
    assert.equal(save.status, 403);
    assert.match(save.body.error, /read-only/);
    const run = await json(await runsRoute.POST(req('POST', `/api/langflow/flows/${flowId}/runs`, { tailnet: 'alex@example.com', session: SESSION, body: { input: 'hi' } }), params({ flowId })));
    assert.equal(run.status, 403);
  } finally {
    fs.rmSync(fs2, { force: true });
  }
});

test('runs: the run gate refuses missing session, empty message, unrunnable and unconfigured runs', async () => {
  const noSession = await json(await runsRoute.POST(req('POST', `/api/langflow/flows/${flowId}/runs`, { body: { input: 'hi' } }), params({ flowId })));
  assert.equal(noSession.status, 422);
  const empty = await json(await runsRoute.POST(req('POST', `/api/langflow/flows/${flowId}/runs`, { session: SESSION, body: { input: '   ' } }), params({ flowId })));
  assert.equal(empty.status, 422);

  const withCalc = structuredClone(chatEcho) as { data: { nodes: Array<Record<string, unknown>> } };
  withCalc.data.nodes.push({ id: 'CalculatorComponent-zz9', type: 'genericNode', position: { x: 0, y: 400 }, data: { type: 'CalculatorComponent', display_name: 'Calculator', node: { template: {} } } });
  const calcFlow = await json(await flowsRoute.POST(req('POST', '/api/langflow/flows', { body: withCalc })));
  assert.equal(calcFlow.status, 201);
  const blocked = await json(await runsRoute.POST(req('POST', `/api/langflow/flows/${calcFlow.body.id}/runs`, { session: SESSION, body: { input: 'hi' } }), params({ flowId: calcFlow.body.id as string })));
  assert.equal(blocked.status, 422);
  assert.match(blocked.body.blockers[0].reason, /Running those is off in this app until Alex approves/);

  delete process.env.LANGFLOW_LFX_BIN;
  const unconfigured = await json(await runsRoute.POST(req('POST', `/api/langflow/flows/${flowId}/runs`, { session: SESSION, body: { input: 'hi' } }), params({ flowId })));
  assert.equal(unconfigured.status, 503);
});

test('runs: a harmless run returns a real result, a repeat click returns the same run, and history is per session', async () => {
  const bin = path.join(tmp, `fake-lfx-${randomUUID()}.sh`);
  fs.writeFileSync(bin, '#!/bin/sh\necho \'{"result": "echo: hello from the route test", "type": "message", "component": "Chat Output", "success": true}\'\n', { mode: 0o755 });
  process.env.LANGFLOW_LFX_BIN = bin;
  const key = `key-${randomUUID()}`;
  const started = await json(await runsRoute.POST(req('POST', `/api/langflow/flows/${flowId}/runs`, { session: SESSION, headers: { 'idempotency-key': key }, body: { input: 'hello from the route test' } }), params({ flowId })));
  assert.equal(started.status, 202);
  const runId = started.body.run.id as string;
  assert.equal(started.body.run.flowHash, hash, 'the run records the saved version it used');

  let record: Record<string, unknown> | undefined;
  for (let i = 0; i < 200 && !record; i += 1) {
    const list = await json(await runsRoute.GET(req('GET', `/api/langflow/flows/${flowId}/runs`, { session: SESSION }), params({ flowId })));
    const found = (list.body.runs as Array<Record<string, unknown>>).find((r) => r.id === runId);
    if (found && found.status !== 'running') record = found;
    else await new Promise((r) => setTimeout(r, 100));
  }
  assert.ok(record, 'run finished');
  assert.equal(record.status, 'succeeded');
  assert.equal(record.output, 'echo: hello from the route test');

  const repeat = await json(await runsRoute.POST(req('POST', `/api/langflow/flows/${flowId}/runs`, { session: SESSION, headers: { 'idempotency-key': key }, body: { input: 'hello again' } }), params({ flowId })));
  assert.equal(repeat.status, 200);
  assert.equal(repeat.body.duplicate, true);
  assert.equal(repeat.body.run.id, runId, 'the same key returns the first run, not a second one');

  const otherSession = await json(await runsRoute.GET(req('GET', `/api/langflow/flows/${flowId}/runs`, { session: 'session-other-0002' }), params({ flowId })));
  assert.equal(otherSession.body.runs.length, 0, 'another browser session sees none of these runs');
});

test('runs: a second click while a run is going is refused, and Stop ends it', async () => {
  const bin = path.join(tmp, `fake-slow-${randomUUID()}.sh`);
  fs.writeFileSync(bin, '#!/bin/sh\nsleep 30\n', { mode: 0o755 });
  process.env.LANGFLOW_LFX_BIN = bin;
  const first = await json(await runsRoute.POST(req('POST', `/api/langflow/flows/${flowId}/runs`, { session: SESSION, headers: { 'idempotency-key': `k-${randomUUID()}` }, body: { input: 'slow one' } }), params({ flowId })));
  assert.equal(first.status, 202);
  const second = await json(await runsRoute.POST(req('POST', `/api/langflow/flows/${flowId}/runs`, { session: SESSION, headers: { 'idempotency-key': `k-${randomUUID()}` }, body: { input: 'second click' } }), params({ flowId })));
  assert.equal(second.status, 409);
  assert.equal(second.body.run.id, first.body.run.id, 'the running record is returned; no second run starts');

  const tailnetStop = await json(await stopRoute.POST(req('POST', `/api/langflow/runs/${first.body.run.id}/stop`, { tailnet: 'alex@example.com' }), params({ runId: first.body.run.id as string })));
  assert.equal(tailnetStop.status, 403);
  const stopped = await json(await stopRoute.POST(req('POST', `/api/langflow/runs/${first.body.run.id}/stop`), params({ runId: first.body.run.id as string })));
  assert.equal(stopped.status, 200);

  let final: string | undefined;
  for (let i = 0; i < 200 && !final; i += 1) {
    const list = await json(await runsRoute.GET(req('GET', `/api/langflow/flows/${flowId}/runs`, { session: SESSION }), params({ flowId })));
    const r = (list.body.runs as Array<Record<string, unknown>>).find((x) => x.id === first.body.run.id);
    if (r && r.status !== 'running') final = r.status as string;
    else await new Promise((res) => setTimeout(res, 100));
  }
  assert.equal(final, 'stopped', 'the run record says stopped, after the process is actually killed');
  delete process.env.LANGFLOW_LFX_BIN;
});

test('stop and unknown ids: malformed or missing ids get a plain 404', async () => {
  assert.equal((await json(await stopRoute.POST(req('POST', '/api/langflow/runs/not-a-run/stop'), params({ runId: 'not-a-run' })))).status, 404);
  assert.equal((await json(await flowRoute.GET(req('GET', '/api/langflow/flows/does-not-exist-123'), params({ flowId: 'does-not-exist-123' })))).status, 404);
  assert.equal((await json(await flowRoute.GET(req('GET', '/api/langflow/flows/..%2F..%2Fetc'), params({ flowId: '../../etc' })))).status, 404);
});
