import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { NextRequest } from 'next/server';
import { middleware } from '../../../middleware';
import { assertMutationAuthorized, getOrCreateLocalToken } from '../../server/local-auth';
process.env.LOCAL_DATA_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'lf-boundary-'));
const token = getOrCreateLocalToken();
function request(method: string, headers: Record<string, string>) {
  return new NextRequest('http://localhost:3200/api/health', { method, headers });
}
test('tailnet identity cannot bypass read-only boundary with a loopback Host and valid token', () => {
  const headers = { host: 'localhost:3200', 'tailscale-user-login': 'reader@example.invalid', 'x-local-token': token };
  assert.equal(middleware(request('POST', headers)).status, 403);
  assert.throws(() => assertMutationAuthorized(request('POST', headers)), (e: unknown) => e instanceof Response && e.status === 403);
});
test('tailnet GET requires a tailnet Host even with a spoofed local Host', () => {
  assert.equal(middleware(request('GET', { host: 'localhost:3200', 'tailscale-user-login': 'reader@example.invalid' })).status, 403);
});
test('tailnet reads pass middleware but every non-read method is refused', () => {
  const headers = { host: 'mac.example.ts.net', 'tailscale-user-login': 'reader@example.invalid' };
  assert.equal(middleware(request('GET', headers)).status, 200);
  for (const method of ['POST','PUT','PATCH','DELETE']) assert.equal(middleware(request(method, headers)).status, 403);
});
test('cross-site local requests cannot bootstrap access and local owner still works', () => {
  assert.equal(middleware(request('GET', { host: 'localhost:3200', 'sec-fetch-site': 'cross-site' })).status, 403);
  assert.equal(middleware(request('GET', { host: 'attacker.invalid' })).status, 403);
  assert.doesNotThrow(() => assertMutationAuthorized(request('POST', { host: 'localhost:3200', 'x-local-token': token })));
});

test('remote health response never exposes the local token or runtime paths', async () => {
  const { GET } = await import('../../../app/api/health/route');
  for (const headers of [
    { host: 'mac.example.ts.net', 'tailscale-user-login': 'reader@example.invalid' },
    { host: 'localhost:3200', 'tailscale-user-login': 'reader@example.invalid' },
    { host: 'attacker.invalid' },
  ]) {
    const res = await GET(request('GET', headers));
    assert.equal(res.headers.get('cache-control'), 'no-store');
    assert.deepEqual(await res.json(), { ok: true, loopback_only: false });
  }
});
