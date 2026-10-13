import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';

import { getOrCreateLocalToken } from '../../server/local-auth';
import { decodeHandle, encodeHandle, HandleDecodeError } from '../handles';
import { authorize, loadAccess, resolveCaller } from '../policy';

const tmp = fs.mkdtempSync(path.join(process.env.TMPDIR ?? os.tmpdir(), 'lf-policy-'));
process.env.LOCAL_DATA_DIR = tmp;

const writeAccess = (value: unknown) => {
  fs.mkdirSync(path.join(tmp, 'langflow'), { recursive: true });
  fs.writeFileSync(path.join(tmp, 'langflow', 'access.json'), typeof value === 'string' ? value : JSON.stringify(value));
};
const clearAccess = () => fs.rmSync(path.join(tmp, 'langflow', 'access.json'), { force: true });
const local = (extra: Record<string, string> = {}) => new Headers({ host: '127.0.0.1:3200', ...extra });

test('handles: decode and encode round trip in Langflow form', () => {
  const handle = { dataType: 'ChatInput', id: 'ChatInput-abc', name: 'message', output_types: ['Message'] };
  const encoded = encodeHandle(handle);
  assert.ok(!encoded.includes('"'), 'quotes are replaced');
  assert.deepEqual(decodeHandle(encoded), handle);
});

test('handles: unreadable handles throw a typed error', () => {
  assert.throws(() => decodeHandle('not json'), HandleDecodeError);
  assert.throws(() => decodeHandle(42), HandleDecodeError);
  assert.throws(() => decodeHandle('[1,2]'), HandleDecodeError);
});

test('policy: missing access file gives the owner everything on this Mac and nobody else', () => {
  clearAccess();
  const config = loadAccess(tmp);
  assert.equal(config.loadError, null);
  const caller = resolveCaller(local({ 'x-local-token': 'wrong' }), config);
  assert.equal(caller?.id, 'local-reader', 'a wrong token is read-only, not owner');
  assert.deepEqual(caller?.ops, ['read']);
});

test('policy: loopback with the local token is the owner', () => {
  clearAccess();
  const caller = resolveCaller(local({ 'x-local-token': getOrCreateLocalToken() }), loadAccess(tmp));
  assert.equal(caller?.id, 'owner');
  assert.equal(authorize(caller, 'run', 'any-flow').ok, true);
  assert.equal(authorize(caller, 'save', 'any-flow').ok, true);
});

test('policy: a tailnet device is read-only even when the access file grants more', () => {
  writeAccess({ owner: { ops: ['read', 'save', 'run'], flows: '*' }, tailnet: { 'Alex@Example.com': { ops: ['read', 'run'], flows: '*' } } });
  const config = loadAccess(tmp);
  const caller = resolveCaller(new Headers({ host: 'mac.tailnet.ts.net', 'tailscale-user-login': 'alex@example.com' }), config);
  assert.equal(caller?.network, 'tailnet');
  assert.deepEqual(caller?.ops, ['read'], 'run is dropped for tailnet callers');
  const denied = authorize(caller, 'run', 'flow-1');
  assert.equal(denied.ok, false);
  assert.match((denied as { reason: string }).reason, /read-only/);
});

test('policy: a tailnet login that is not listed is refused', () => {
  writeAccess({ owner: { ops: ['read'], flows: '*' }, tailnet: {} });
  const caller = resolveCaller(new Headers({ host: 'mac.tailnet.ts.net', 'tailscale-user-login': 'stranger@example.com' }), loadAccess(tmp));
  assert.equal(caller, null);
});

test('policy: non-loopback hosts and foreign origins are refused', () => {
  clearAccess();
  const config = loadAccess(tmp);
  assert.equal(resolveCaller(new Headers({ host: '192.168.1.20:3200' }), config), null);
  assert.equal(resolveCaller(local({ origin: 'https://evil.example' }), config), null);
  assert.equal(resolveCaller(local({ origin: 'null' }), config), null);
});

test('policy: a flow allow-list stops the owner from reaching other flows', () => {
  writeAccess({ owner: { ops: ['read', 'save', 'run'], flows: ['flow-a'] }, tailnet: {} });
  const caller = resolveCaller(local({ 'x-local-token': getOrCreateLocalToken() }), loadAccess(tmp));
  assert.equal(authorize(caller, 'run', 'flow-a').ok, true);
  const other = authorize(caller, 'run', 'flow-b');
  assert.equal(other.ok, false);
  assert.match((other as { reason: string }).reason, /Not allowed for this flow/);
});

test('policy: a malformed access file denies everything and says why', () => {
  writeAccess('{ this is not json');
  const config = loadAccess(tmp);
  assert.match(config.loadError ?? '', /unreadable/);
  assert.equal(resolveCaller(local(), config), null);
  clearAccess();
});
