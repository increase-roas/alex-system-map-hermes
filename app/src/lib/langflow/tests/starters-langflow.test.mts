// Starter flows and "Open in Langflow".
// Unit part: a fake Langflow on a loopback port stands in for the real one. LIVE part (LANGFLOW_LIVE_ENGINE=1):
// each starter runs on the real engine; with LANGFLOW_SERVER_LIVE=1 a flow is sent to the real Langflow on this Mac.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';
import { after, before, test } from 'node:test';

import { getOrCreateLocalToken } from '../../server/local-auth';
import * as startersRoute from '../../../app/api/langflow/starters/route';
import * as langflowRoute from '../../../app/api/langflow/flows/[flowId]/langflow/route';
import * as runsRoute from '../../../app/api/langflow/flows/[flowId]/runs/route';
import * as flowRoute from '../../../app/api/langflow/flows/[flowId]/route';
import { resetCatalogCache } from '../catalog';
import { langflowServer, sendToLangflow } from '../langflow-server';
import type { LfFlow } from '../model';
import { STARTERS } from '../starters';
import { createFlow } from '../store';

const SUBSET = fileURLToPath(new URL('../fixtures/component-index.subset.json', import.meta.url));
const tmp = fs.mkdtempSync(path.join(process.env.TMPDIR ?? os.tmpdir(), 'lf-starters-'));
const chatEcho = JSON.parse(fs.readFileSync(new URL('../fixtures/chat-echo.json', import.meta.url), 'utf8')) as LfFlow;
const live = process.env.LANGFLOW_LIVE_ENGINE === '1' && !!process.env.LANGFLOW_LFX_BIN;
const liveServer = process.env.LANGFLOW_SERVER_LIVE === '1';
let savedIndex: string | undefined;
let savedServer: string | undefined;

before(() => {
  savedIndex = process.env.LANGFLOW_COMPONENT_INDEX;
  savedServer = process.env.LANGFLOW_SERVER_URL;
  if (!live) process.env.LANGFLOW_COMPONENT_INDEX = SUBSET;
  process.env.LOCAL_DATA_DIR = tmp;
  resetCatalogCache();
});
after(() => {
  if (savedIndex === undefined) delete process.env.LANGFLOW_COMPONENT_INDEX;
  else process.env.LANGFLOW_COMPONENT_INDEX = savedIndex;
  if (savedServer === undefined) delete process.env.LANGFLOW_SERVER_URL;
  else process.env.LANGFLOW_SERVER_URL = savedServer;
  resetCatalogCache();
});

type Opts = { tailnet?: string; token?: boolean; headers?: Record<string, string> };
function req(method: string, pathname: string, body?: unknown, opts: Opts = {}): Request {
  const headers = new Headers({ host: '127.0.0.1:3200', 'content-type': 'application/json', ...(opts.headers ?? {}) });
  if (opts.tailnet) {
    headers.set('host', 'mac.tailnet.ts.net');
    headers.set('tailscale-user-login', opts.tailnet);
  } else if (opts.token !== false) headers.set('x-local-token', getOrCreateLocalToken());
  return new Request(`http://127.0.0.1:3200${pathname}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
}
const params = (flowId: string) => ({ params: Promise.resolve({ flowId }) });
const json = async (res: Response) => ({ status: res.status, body: (await res.json()) as Record<string, unknown> });

/** A stand-in for Langflow: auto_login, then POST /api/v1/flows/. Records what it received. */
async function fakeLangflow(mode: 'ok' | 'login-required' = 'ok'): Promise<{ url: string; received: unknown[]; close: () => Promise<void> }> {
  const received: unknown[] = [];
  const server = http.createServer((rq, rs) => {
    let data = '';
    rq.on('data', (c) => { data += c; });
    rq.on('end', () => {
      if (rq.url === '/health') return void rs.end('{"status":"ok"}');
      if (rq.url === '/api/v1/auto_login') {
        rs.statusCode = mode === 'ok' ? 200 : 400;
        return void rs.end(mode === 'ok' ? '{"access_token":"fake-session","token_type":"bearer"}' : '{"detail":"auto login disabled"}');
      }
      if (rq.url === '/api/v1/flows/' && rq.method === 'POST') {
        assert.equal(rq.headers.authorization, 'Bearer fake-session');
        received.push(JSON.parse(data));
        rs.statusCode = 201;
        return void rs.end(JSON.stringify({ id: 'lf-flow-123' }));
      }
      rs.statusCode = 404;
      rs.end('{}');
    });
  });
  await new Promise<void>((r) => server.listen(0, '127.0.0.1', () => r()));
  const { port } = server.address() as { port: number };
  return { url: `http://127.0.0.1:${port}`, received, close: () => new Promise((r) => server.close(() => r())) };
}

test('langflow server: only a loopback address is accepted', () => {
  assert.equal(langflowServer({}).url, 'http://127.0.0.1:7860');
  assert.equal(langflowServer({ LANGFLOW_SERVER_URL: 'http://localhost:9000/x' }).url, 'http://localhost:9000');
  for (const bad of ['https://langflow.example.com', 'http://192.168.1.5:7860', 'http://mac.tailnet.ts.net', 'not a url', 'file:///etc/passwd']) {
    assert.equal(langflowServer({ LANGFLOW_SERVER_URL: bad }).url, null, bad);
  }
});

test('send: the flow arrives with secrets emptied, a clear name and its editor address', async () => {
  const fake = await fakeLangflow();
  try {
    const flow = structuredClone(chatEcho);
    const out = flow.data.nodes.find((n) => n.data?.type === 'ChatOutput')!;
    out.data!.node!.template!.api_key = { type: 'str', password: true, show: true, value: 'FAKE-canary-send' };
    out.data!.node!.template!.extra = { type: 'dict', show: true, value: { token: ['FAKE-canary-nested'] } };
    const r = await sendToLangflow(flow, 'My flow (from dashboard)', { url: fake.url });
    assert.ok(r.ok);
    if (r.ok) assert.equal(r.url, `${fake.url}/flow/lf-flow-123`);
    const sent = JSON.stringify(fake.received[0]);
    assert.ok(!sent.includes('FAKE-canary'), 'no secret leaves the dashboard');
    assert.equal((fake.received[0] as { name: string }).name, 'My flow (from dashboard)');
    assert.equal((fake.received[0] as { data: { nodes: unknown[] } }).data.nodes.length, 2);
  } finally {
    await fake.close();
  }
});

test('send: a stopped Langflow or one that needs a login gets a clear reason', async () => {
  const stopped = await sendToLangflow(chatEcho, 'x', { url: 'http://127.0.0.1:9' });
  assert.equal(stopped.ok, false);
  if (!stopped.ok) assert.match(stopped.reason, /isn't running on this Mac/);
  const fake = await fakeLangflow('login-required');
  try {
    const r = await sendToLangflow(chatEcho, 'x', { url: fake.url });
    assert.equal(r.ok, false);
    if (!r.ok) assert.match(r.reason, /LANGFLOW_AUTO_LOGIN=True/);
  } finally {
    await fake.close();
  }
});

test('routes: starters and open-in-Langflow are owner only (tailnet and token-less get 403)', async () => {
  const stored = createFlow({ ...structuredClone(chatEcho), id: randomUUID() });
  for (const opts of [{ tailnet: 'alex@example.com' }, { tailnet: 'stranger@example.com' }, { token: false }] as Opts[]) {
    assert.equal((await startersRoute.POST(req('POST', '/api/langflow/starters', { key: 'router' }, opts))).status, 403, JSON.stringify(opts));
    assert.equal((await langflowRoute.POST(req('POST', `/api/langflow/flows/${stored.id}/langflow`, {}, opts), params(stored.id))).status, 403, JSON.stringify(opts));
  }
  const list = await json(await startersRoute.GET(req('GET', '/api/langflow/starters', undefined, { token: false })));
  assert.equal(list.status, 200, 'anyone who may read can see the starter list');
  assert.equal((list.body.starters as unknown[]).length, 4);
  assert.equal((await startersRoute.POST(req('POST', '/api/langflow/starters', { key: 'nope' }))).status, 422);
});

test('route: open in Langflow sends the saved flow to the configured local Langflow', async () => {
  const fake = await fakeLangflow();
  process.env.LANGFLOW_SERVER_URL = fake.url;
  try {
    const stored = createFlow({ ...structuredClone(chatEcho), id: randomUUID(), name: 'Echo' });
    const r = await json(await langflowRoute.POST(req('POST', `/api/langflow/flows/${stored.id}/langflow`, {}), params(stored.id)));
    assert.equal(r.status, 201);
    assert.equal(r.body.url, `${fake.url}/flow/lf-flow-123`);
    assert.equal((fake.received[0] as { name: string }).name, 'Echo (from dashboard)');
  } finally {
    delete process.env.LANGFLOW_SERVER_URL;
    await fake.close();
  }
});

test('starters: each one builds without errors from engine templates', async () => {
  if (!live) process.env.LANGFLOW_COMPONENT_INDEX = SUBSET;
  for (const s of STARTERS.filter((x) => live || x.key !== 'chunker')) {
    // The test index has no SplitText; the chunker is covered by the LIVE test.
    const made = await json(await startersRoute.POST(req('POST', '/api/langflow/starters', { key: s.key })));
    assert.equal(made.status, 201, `${s.key}: ${JSON.stringify(made.body)}`);
    const detail = await json(await flowRoute.GET(req('GET', `/api/langflow/flows/${made.body.id}`), params(made.body.id as string)));
    assert.deepEqual((detail.body.problems as Array<{ level: string }>).filter((p) => p.level === 'error'), [], s.key);
  }
});

async function runOnce(id: string, input: string): Promise<{ status: string; output: string }> {
  const started = await json(await runsRoute.POST(req('POST', `/api/langflow/flows/${id}/runs`, { input }, { headers: { 'x-browser-session': 'starters-session-01', 'idempotency-key': `st-${randomUUID()}` } }), params(id)));
  assert.equal(started.status, 202, JSON.stringify(started.body));
  const runId = (started.body.run as { id: string }).id;
  for (let i = 0; i < 240; i += 1) {
    const list = await json(await runsRoute.GET(req('GET', `/api/langflow/flows/${id}/runs`, undefined, { headers: { 'x-browser-session': 'starters-session-01' } }), params(id)));
    const r = (list.body.runs as Array<{ id: string; status: string; output: string | null; error: string | null }>).find((x) => x.id === runId);
    if (r && r.status !== 'running') return { status: r.status, output: r.output ?? r.error ?? '' };
    await new Promise((res) => setTimeout(res, 500));
  }
  return { status: 'timeout', output: '' };
}

test('LIVE starters: each one runs on the real engine and gives the expected answer', { skip: !live && 'set LANGFLOW_LIVE_ENGINE=1 and LANGFLOW_LFX_BIN', timeout: 600_000 }, async () => {
  delete process.env.LANGFLOW_COMPONENT_INDEX;
  resetCatalogCache();
  const cases: Array<[string, string, RegExp]> = [
    ['reply-template', 'Jordan', /^Hi Jordan, thanks for reaching out!/],
    ['router', 'what is the price?', /^Pricing: our plans start at \$99\/month\.$/],
    ['router', 'hello there', /^Thanks! A teammate will reply shortly\.$/],
    ['chunker', 'First point about the offer.\nSecond point about timing.\nThird point about next steps.', /- First point about the offer\.\n- Second point about timing\.\n- Third point about next steps\./],
    ['dated-note', 'Called 3 leads, 1 booked.', new RegExp(`^Note \\(Current date and time in UTC: ${new Date().getUTCFullYear()}-\\d\\d-\\d\\d \\d\\d:\\d\\d:\\d\\d UTC\\): Called 3 leads, 1 booked\\.$`)],
  ];
  for (const [key, input, expect] of cases) {
    const made = await json(await startersRoute.POST(req('POST', '/api/langflow/starters', { key })));
    assert.equal(made.status, 201);
    const r = await runOnce(made.body.id as string, input);
    console.log(`LIVE starter ${key} (${JSON.stringify(input)}): ${r.status}: ${r.output.replace(/\n/g, ' / ')}`);
    assert.equal(r.status, 'succeeded');
    assert.match(r.output, expect);
  }
});

test('LIVE Langflow: open in Langflow creates the flow in the real Langflow on this Mac', { skip: !liveServer && 'set LANGFLOW_SERVER_LIVE=1 with Langflow running', timeout: 60_000 }, async () => {
  const stored = createFlow({ ...structuredClone(chatEcho), id: randomUUID(), name: 'Live handoff check' });
  const r = await json(await langflowRoute.POST(req('POST', `/api/langflow/flows/${stored.id}/langflow`, {}), params(stored.id)));
  assert.equal(r.status, 201, JSON.stringify(r.body));
  const base = langflowServer().url!;
  const login = (await (await fetch(`${base}/api/v1/auto_login`)).json()) as { access_token: string };
  const got = await fetch(`${base}/api/v1/flows/${r.body.langflowId}`, { headers: { authorization: `Bearer ${login.access_token}` } });
  const flow = (await got.json()) as { name: string; data: { nodes: unknown[]; edges: unknown[] } };
  assert.equal(got.status, 200);
  assert.equal(flow.name, 'Live handoff check (from dashboard)');
  assert.equal(flow.data.nodes.length, 2);
  assert.equal(flow.data.edges.length, 1);
  const page = await fetch(String(r.body.url));
  assert.equal(page.status, 200, 'the editor page opens');
  const del = await fetch(`${base}/api/v1/flows/${r.body.langflowId}`, { method: 'DELETE', headers: { authorization: `Bearer ${login.access_token}` } });
  console.log(`LIVE Langflow handoff: created ${r.body.langflowId} with 2 components and 1 connection, editor page HTTP ${page.status}, test copy deleted (HTTP ${del.status})`);
});
