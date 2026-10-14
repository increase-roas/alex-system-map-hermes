// Langfuse traces: route access, unknown state, row building, redaction, host allowlist. No network: fetch is stubbed.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, before, test } from 'node:test';

import { getOrCreateLocalToken } from '../../server/local-auth';
import * as route from '../../../app/api/langfuse/traces/route';
import { assertAllowedHost, buildTraceRows, clearKeyCache, redactLangfuse } from '../../server/langfuse';

const tmp = fs.mkdtempSync(path.join(process.env.TMPDIR ?? os.tmpdir(), 'lf-traces-'));
const realFetch = globalThis.fetch;
const KEY_ENV = ['LANGFUSE_AGENTS_PUBLIC_KEY', 'LANGFUSE_AGENTS_SECRET_KEY', 'LANGFUSE_LANGFLOW_PUBLIC_KEY', 'LANGFUSE_LANGFLOW_SECRET_KEY'];
const FAKE_PK = 'pk-lf-' + 'a'.repeat(12);
const FAKE_SK = 'sk-lf-' + 'b'.repeat(12);

function req(url: string, opts: { tailnet?: string; token?: boolean } = {}): Request {
  const headers = new Headers({ host: '127.0.0.1:3200' });
  if (opts.tailnet) {
    headers.set('host', 'mac.tailnet.ts.net');
    headers.set('tailscale-user-login', opts.tailnet);
  } else if (opts.token !== false) {
    headers.set('x-local-token', getOrCreateLocalToken());
  }
  return new Request('http://127.0.0.1:3200' + url, { headers });
}

before(() => {
  process.env.LOCAL_DATA_DIR = tmp;
});
after(() => {
  globalThis.fetch = realFetch;
  for (const k of KEY_ENV) delete process.env[k];
});

test('403 for a tailnet viewer and for a local reader without the token', async () => {
  const tailnet = await route.GET(req('/api/langfuse/traces?project=agents', { tailnet: 'stranger@example.com' }));
  assert.equal(tailnet.status, 403);
  assert.ok(typeof (await tailnet.json()).error === 'string');
  const reader = await route.GET(req('/api/langfuse/traces?project=agents', { token: false }));
  assert.equal(reader.status, 403);
});

test('400 for an unknown project', async () => {
  const res = await route.GET(req('/api/langfuse/traces?project=other'));
  assert.equal(res.status, 400);
});

test('unknown state when the keys cannot be read', async () => {
  clearKeyCache();
  for (const k of KEY_ENV) delete process.env[k];
  // A fetch that must not be reached: with no keys there is nothing to send.
  globalThis.fetch = (async () => { throw new Error('network must not be used'); }) as typeof fetch;
  const oldPath = process.env.PATH;
  const oldHome = process.env.HOME;
  process.env.PATH = '/nonexistent';
  try {
    const res = await route.GET(req('/api/langfuse/traces?project=langflow'));
    const body = await res.json();
    assert.equal(res.status, 200);
    assert.equal(body.ok, false);
    assert.equal(body.state, 'unknown');
    assert.equal(typeof body.reason, 'string');
    assert.equal(typeof body.asOf, 'string');
    assert.match(body.note, /few minutes late/);
  } finally {
    process.env.PATH = oldPath;
    process.env.HOME = oldHome;
  }
});

const fixture = [
  { id: 'o1', traceId: 't1', name: 'claude_code.interaction', startTime: '2026-10-14T10:00:00.000Z', endTime: '2026-10-14T10:00:05.000Z', level: 'DEFAULT', isRootObservation: true, parentObservationId: null, totalCost: null },
  { id: 'o2', traceId: 't1', name: 'llm_request', startTime: '2026-10-14T10:00:01.000Z', endTime: '2026-10-14T10:00:04.000Z', level: 'DEFAULT', parentObservationId: 'o1', totalCost: 0.0125 },
  { id: 'o3', traceId: 't1', name: 'tool', startTime: '2026-10-14T10:00:04.000Z', endTime: '2026-10-14T10:00:06.500Z', level: 'ERROR', parentObservationId: 'o1', totalCost: 0.0025 },
  { id: 'o4', traceId: 't2', name: 'flow run', startTime: '2026-10-14T11:00:00.000Z', endTime: null, level: 'DEFAULT', parentObservationId: null },
  { id: 'o5', startTime: '2026-10-14T11:00:00.000Z' },
];

test('rows: error flag, cost sum, duration, root name, newest first', () => {
  const rows = buildTraceRows(fixture);
  assert.deepEqual(rows.map((r) => r.traceId), ['t2', 't1']);
  const t1 = rows[1];
  assert.equal(t1.name, 'claude_code.interaction');
  assert.equal(t1.hasError, true);
  assert.equal(t1.totalCost, 0.015);
  assert.equal(t1.durationMs, 6500);
  assert.equal(t1.observationCount, 3);
  const t2 = rows[0];
  assert.equal(t2.hasError, false);
  assert.equal(t2.totalCost, null);
  assert.equal(t2.durationMs, null); // no end time: unknown, not zero
});

test('rows are capped at 100', () => {
  const many = Array.from({ length: 150 }, (_, i) => ({ traceId: `x${i}`, name: 'n', startTime: new Date(Date.UTC(2026, 9, 14, 0, 0, i)).toISOString() }));
  assert.equal(buildTraceRows(many).length, 100);
});

test('the route builds rows from a stubbed Langfuse answer and never returns the keys', async () => {
  clearKeyCache();
  process.env.LANGFUSE_AGENTS_PUBLIC_KEY = FAKE_PK;
  process.env.LANGFUSE_AGENTS_SECRET_KEY = FAKE_SK;
  const seen: string[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    seen.push(String(input));
    return new Response(JSON.stringify({ data: fixture, meta: {} }), { status: 200, headers: { 'content-type': 'application/json' } });
  }) as typeof fetch;
  const res = await route.GET(req('/api/langfuse/traces?project=agents'));
  const text = await res.text();
  const body = JSON.parse(text);
  assert.equal(body.ok, true);
  assert.equal(body.traces.length, 2);
  assert.equal(body.projectId, 'cmv733aoq01e7ad0mfeqexnrx');
  assert.ok(!text.includes(FAKE_PK) && !text.includes(FAKE_SK));
  assert.ok(seen[0].startsWith('https://us.cloud.langfuse.com/api/public/v2/observations?'));
  assert.match(seen[0], /fromStartTime=/);
});

test('a 401 re-reads the keys once, then reports unknown without echoing them', async () => {
  clearKeyCache();
  process.env.LANGFUSE_LANGFLOW_PUBLIC_KEY = FAKE_PK;
  process.env.LANGFUSE_LANGFLOW_SECRET_KEY = FAKE_SK;
  let calls = 0;
  globalThis.fetch = (async () => { calls += 1; return new Response('{"message":"sk-lf-leak"}', { status: 401 }); }) as typeof fetch;
  const res = await route.GET(req('/api/langfuse/traces?project=langflow'));
  const text = await res.text();
  const body = JSON.parse(text);
  assert.equal(body.ok, false);
  assert.equal(body.state, 'unknown');
  assert.equal(calls, 2);
  assert.ok(!text.includes('sk-lf-'));
});

test('redaction strips key-shaped strings', () => {
  const out = redactLangfuse(`bad ${FAKE_PK} and ${FAKE_SK} and Basic ${Buffer.from('a:b'.repeat(8)).toString('base64')}`);
  assert.ok(!out.includes('pk-lf-') && !out.includes('sk-lf-'));
  assert.ok(!/Basic [A-Za-z0-9+/=]{8,}/.test(out));
});

test('host allowlist: only the Langfuse US cloud over https', () => {
  assert.equal(assertAllowedHost('https://us.cloud.langfuse.com/api/public/v2/observations').hostname, 'us.cloud.langfuse.com');
  for (const bad of ['https://cloud.langfuse.com/api', 'http://us.cloud.langfuse.com/api', 'https://us.cloud.langfuse.com.evil.test/', 'https://evil.test/', 'not a url']) {
    assert.throws(() => assertAllowedHost(bad), /Blocked/);
  }
});
