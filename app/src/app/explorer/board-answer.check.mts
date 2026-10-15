// Round-trip test for the "Waiting on you" panel. Runs against a TEMP copy of the board, never the live one.
// Needs `npm run build` first. Run from the repo root: node app/src/app/explorer/board-answer.check.mts
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, before, test } from 'node:test';

const APP = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..', '..', '..');
const LIVE = path.join(os.homedir(), '.agents', 'board', 'tasks.json');
const PORT = 3190 + Math.floor(Math.random() * 50);
const BASE = `http://127.0.0.1:${PORT}`;
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'board-test-'));
const boardDir = path.join(root, 'board');
let server;
let serverOutput = '';

before(async () => {
  fs.mkdirSync(boardDir);
  const board = JSON.parse(fs.readFileSync(LIVE, 'utf8'));
  board.tickets.push(
    { id: 'test-q-1', mission: Object.keys(board.missions)[0], title: 'Map header layout',
      status: 'blocked', blocked_on: 'alex', owner: 'claude-code:test', need: 'Which layout do you prefer for the map header, the left one or the top one?',
      updated: '2026-10-14T00:00:00Z', progressed: '2026-10-14T00:00:00Z', proof: [] },
    { id: 'test-gate-1', mission: Object.keys(board.missions)[0], title: 'Raise ad budget',
      status: 'blocked', blocked_on: 'alex', owner: 'claude-code:test', need: 'Spend $50 more per day?',
      updated: '2026-10-14T00:00:00Z', progressed: '2026-10-14T00:00:00Z', proof: [] },
  );
  fs.writeFileSync(path.join(boardDir, 'tasks.json'), JSON.stringify(board, null, 1));
  fs.writeFileSync(path.join(boardDir, 'progress.md'), '');
  server = spawn(path.join(APP, 'node_modules', '.bin', 'next'), ['start', '--hostname', '127.0.0.1', '-p', String(PORT)], {
    cwd: APP,
    env: { ...process.env, AGENTS_BOARD_DIR: boardDir, LOCAL_DATA_DIR: path.join(root, 'data') },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  server.stdout.on('data', (d) => { serverOutput += d; });
  server.stderr.on('data', (d) => { serverOutput += d; });
  for (let i = 0; i < 60; i++) {
    try { if ((await fetch(`${BASE}/api/board`)).ok) return; } catch {}
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error('server did not start');
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
  const q = v.waiting.find((w) => w.id === 'test-q-1');
  const g = v.waiting.find((w) => w.id === 'test-gate-1');
  assert.equal(q.gate, false);
  assert.equal(q.answerable, true);
  assert.equal(g.gate, true);
});

test('rejects a POST without the local token', async () => {
  const res = await post({ id: 'test-q-1', text: 'blue' });
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
  const before = fs.statSync(LIVE).mtimeMs;
  const { token } = await view();
  const res = await post({ id: 'test-q-1', text: 'Blue please' }, token);
  assert.equal(res.status, 200, await res.clone().text());
  const t = JSON.parse(fs.readFileSync(path.join(boardDir, 'tasks.json'), 'utf8')).tickets.find((x) => x.id === 'test-q-1');
  assert.equal(t.status, 'open');
  assert.equal(t.answers.at(-1).text, 'Blue please');
  assert.match(t.answers.at(-1).source, /^dashboard \(Alex\) \d{4}-\d\d-\d\dT/);
  assert.match(fs.readFileSync(path.join(boardDir, 'progress.md'), 'utf8'), /test-q-1/);
  const v = await view();
  assert.ok(!v.waiting.some((w) => w.id === 'test-q-1'));
  assert.equal(v.answered[0].answer.text, 'Blue please');
  assert.equal(fs.statSync(LIVE).mtimeMs, before, 'live board must not change');
  assert.ok(!serverOutput.includes('Blue please'), 'answer text must not reach server logs');
});
