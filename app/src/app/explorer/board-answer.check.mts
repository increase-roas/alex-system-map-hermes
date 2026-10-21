// Round-trip test for the "Waiting on you" panel. Uses synthetic TEMP board data and pinned native board.py.
// Needs `npm run build` first. Run from the repo root: node app/src/app/explorer/board-answer.check.mts
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import net from 'node:net';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, before, test } from 'node:test';

const APP = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..', '..', '..');
const NATIVE = path.resolve(APP, '..', 'tools', 'fixtures', 'board-answer');
// OS-assigned free port, so the test can never reach a running dashboard.
const PORT = await new Promise<number>((resolve, reject) => {
  const probe = net.createServer().listen(0, '127.0.0.1', () => {
    const { port } = probe.address() as net.AddressInfo;
    probe.close(() => resolve(port));
  }).on('error', reject);
});
const BASE = `http://127.0.0.1:${PORT}`;
// Unique per run: the server must prove it serves OUR temp board before we take its token or POST.
const FIXTURE = `test-q-${crypto.randomBytes(6).toString('hex')}`;
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'board-test-'));
const boardDir = path.join(root, 'board');
// Separate synthetic home/sentinel: no test or backend needs the user's board.
const fixtureHome = path.join(root, 'home');
const untouched = path.join(fixtureHome, '.agents', 'board', 'tasks.json');
let server;
let exited = false;
let serverOutput = '';

before(async () => {
  fs.mkdirSync(boardDir);
  fs.mkdirSync(path.dirname(untouched), { recursive: true });
  fs.writeFileSync(untouched, JSON.stringify({ missions: {}, tickets: [] }));
  const provenance = JSON.parse(fs.readFileSync(path.join(NATIVE, 'provenance.json'), 'utf8'));
  for (const [relative, entry] of Object.entries(provenance.files)) {
    assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(NATIVE, relative))).digest('hex'), entry.sha256);
  }
  const board = { missions: { fixture: { title: 'Disposable dashboard test', status: 'draft' } }, tickets: [
    { id: FIXTURE, mission: 'fixture', title: 'Map header layout',
      status: 'blocked', blocked_on: 'alex', owner: 'claude-code:test', need: 'dashboard-ok: Which layout do you prefer for the map header, the left one or the top one?',
      updated: '2026-10-14T00:00:00Z', progressed: '2026-10-14T00:00:00Z', proof: [] },
    { id: 'test-gate-1', mission: 'fixture', title: 'Raise ad budget',
      status: 'blocked', blocked_on: 'alex', owner: 'claude-code:test', need: 'dashboard-ok: Spend $50 more per day?',
      updated: '2026-10-14T00:00:00Z', progressed: '2026-10-14T00:00:00Z', proof: [] },
  ] };
  fs.writeFileSync(path.join(boardDir, 'tasks.json'), JSON.stringify(board, null, 1));
  fs.writeFileSync(path.join(boardDir, 'progress.md'), '');
  server = spawn(path.join(APP, 'node_modules', '.bin', 'next'), ['start', '--hostname', '127.0.0.1', '-p', String(PORT)], {
    cwd: APP,
    env: { ...process.env, HOME: fixtureHome, AGENTS_BOARD_DIR: boardDir,
      AGENTS_BOARD_SCRIPT: path.join(NATIVE, 'board', 'board.py'), AGENTS_BOARD_COMMIT: '0',
      AGENTS_BOARD_NO_COMMIT: '1', AGENTS_BOARD_REMOTE: '0', PYTHONDONTWRITEBYTECODE: '1',
      LOCAL_DATA_DIR: path.join(root, 'data') },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  server.stdout.on('data', (d) => { serverOutput += d; });
  server.stderr.on('data', (d) => { serverOutput += d; });
  server.on('exit', () => { exited = true; });
  for (let i = 0; i < 60; i++) {
    if (exited) throw new Error('test server exited before it was ready: ' + serverOutput);
    try {
      const res = await fetch(`${BASE}/api/board`);
      if (res.ok && (await res.json()).waiting.some((w) => w.id === FIXTURE)) return;
    } catch {}
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error('server did not start: ' + serverOutput);
});

after(() => {
  server?.kill();
  fs.rmSync(root, { recursive: true, force: true });
});

const view = async () => (await fetch(`${BASE}/api/board`)).json();
const post = (body, token) =>
  fetch(`${BASE}/api/board/answer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { 'X-Local-Token': token } : {}) },
    body: JSON.stringify(body),
  });

test('lists waiting questions and marks gates', async () => {
  const v = await view();
  const q = v.waiting.find((w) => w.id === FIXTURE);
  const g = v.waiting.find((w) => w.id === 'test-gate-1');
  assert.equal(q.gate, false);
  assert.equal(q.answerable, true);
  assert.equal(g.gate, true);
});

test('rejects a POST without the local token', async () => {
  const res = await post({ id: FIXTURE, text: 'blue' });
  assert.equal(res.status, 401);
});

test('refuses to answer a gate item', async () => {
  const { token } = await view();
  const res = await post({ id: 'test-gate-1', text: 'yes' }, token);
  assert.equal(res.status, 403);
  const t = JSON.parse(fs.readFileSync(path.join(boardDir, 'tasks.json'), 'utf8')).tickets.find((x) => x.id === 'test-gate-1');
  assert.equal(t.status, 'blocked');
  assert.equal(t.answers, undefined);
});

test('answer round-trips through board.py', async () => {
  const before = fs.statSync(untouched).mtimeMs;
  const { token } = await view();
  const res = await post({ id: FIXTURE, text: 'Blue please' }, token);
  assert.equal(res.status, 200, await res.clone().text());
  const t = JSON.parse(fs.readFileSync(path.join(boardDir, 'tasks.json'), 'utf8')).tickets.find((x) => x.id === FIXTURE);
  assert.equal(t.status, 'open');
  assert.equal(t.answers.at(-1).text, 'Blue please');
  assert.match(t.answers.at(-1).source, /^dashboard \(Alex\) \d{4}-\d\d-\d\dT/);
  assert.match(fs.readFileSync(path.join(boardDir, 'progress.md'), 'utf8'), new RegExp(FIXTURE));
  const v = await view();
  assert.ok(!v.waiting.some((w) => w.id === FIXTURE));
  assert.equal(v.answered[0].answer.text, 'Blue please');
  assert.equal(fs.statSync(untouched).mtimeMs, before, 'separate board sentinel must not change');
  assert.ok(!serverOutput.includes('Blue please'), 'answer text must not reach server logs');
});

test('never treats an unrelated server as the test server', async () => {
  // Occupy a port with a fake server that answers /api/board without our fixture.
  const fake = net.createServer((sock) => {
    sock.end('HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{"waiting":[],"token":"x"}');
  });
  await new Promise<void>((r) => fake.listen(0, '127.0.0.1', () => r()));
  const { port } = fake.address() as net.AddressInfo;
  const body = await (await fetch(`http://127.0.0.1:${port}/api/board`)).json();
  assert.ok(!body.waiting.some((w) => w.id === FIXTURE), 'fake server must fail the fixture-identity check');
  fake.close();
});
