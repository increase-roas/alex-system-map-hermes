// LIVE acceptance on the real Langflow engine (pinned 1.12.5 `lfx`). Skipped unless enabled:
//   LANGFLOW_LIVE_ENGINE=1 LANGFLOW_LFX_BIN=<path to lfx> LANGFLOW_CONFIG_DIR=<dir> \
//     node --import ./src/lib/langflow/tests/register.mjs --test src/lib/langflow/tests/live-engine.test.mts
// It goes through the real route handlers into the real engine. It does not use a server port.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';

import { getOrCreateLocalToken } from '../../server/local-auth';
import * as flowsRoute from '../../../app/api/langflow/flows/route';
import * as runsRoute from '../../../app/api/langflow/flows/[flowId]/runs/route';
import { contentHash, type LfFlow } from '../model';

const enabled = process.env.LANGFLOW_LIVE_ENGINE === '1' && !!process.env.LANGFLOW_LFX_BIN;
const tmp = fs.mkdtempSync(path.join(process.env.TMPDIR ?? os.tmpdir(), 'lf-live-'));
const chatEcho = JSON.parse(fs.readFileSync(new URL('../fixtures/chat-echo.json', import.meta.url), 'utf8')) as LfFlow;
const MESSAGE = `live engine check ${new Date().toISOString()}`;

test('LIVE: a saved harmless flow runs on the real Langflow engine and returns the real output', { skip: !enabled && 'set LANGFLOW_LIVE_ENGINE=1 and LANGFLOW_LFX_BIN to run' }, async () => {
  process.env.LOCAL_DATA_DIR = tmp;
  const headers = new Headers({ host: '127.0.0.1:3200', 'x-local-token': getOrCreateLocalToken() });
  const imported = await flowsRoute.POST(new Request('http://127.0.0.1:3200/api/langflow/flows', {
    method: 'POST', headers: new Headers([...headers.entries(), ['content-type', 'application/json']]), body: JSON.stringify(chatEcho),
  }));
  assert.equal(imported.status, 201);
  const { id, hash } = (await imported.json()) as { id: string; hash: string };
  assert.equal(hash, contentHash(chatEcho), 'the stored version is the file we imported');

  const started = await runsRoute.POST(new Request(`http://127.0.0.1:3200/api/langflow/flows/${id}/runs`, {
    method: 'POST',
    headers: new Headers([...headers.entries(), ['content-type', 'application/json'], ['x-browser-session', 'live-session-0001'], ['idempotency-key', `live-${Date.now()}`]]),
    body: JSON.stringify({ input: MESSAGE }),
  }), { params: Promise.resolve({ flowId: id }) });
  assert.equal(started.status, 202);
  const runId = ((await started.json()) as { run: { id: string } }).run.id;

  const deadline = Date.now() + 180_000;
  let record: Record<string, unknown> | undefined;
  while (Date.now() < deadline) {
    const list = await runsRoute.GET(new Request(`http://127.0.0.1:3200/api/langflow/flows/${id}/runs`, {
      headers: new Headers([['host', '127.0.0.1:3200'], ['x-local-token', getOrCreateLocalToken()], ['x-browser-session', 'live-session-0001']]),
    }), { params: Promise.resolve({ flowId: id }) });
    const runs = ((await list.json()) as { runs: Array<Record<string, unknown>> }).runs;
    const found = runs.find((r) => r.id === runId);
    if (found && found.status !== 'running') {
      record = found;
      break;
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  assert.ok(record, 'the run finished before the deadline');
  assert.equal(record.status, 'succeeded', `status ${record.status}: ${record.error ?? ''}`);
  assert.equal(record.output, MESSAGE, 'the engine echoed the message through Chat Input and Chat Output');
  assert.equal(record.flowHash, hash, 'the run records the saved version it used');
  assert.match(String(record.engineVersion), /^lfx \d+\.\d+/, 'the run records the engine that actually ran, read from its own files');
  console.log(`LIVE run ${runId.slice(0, 8)} succeeded in ${Math.round((Date.parse(record.finishedAt) - Date.parse(record.startedAt)) / 1000)}s on engine ${record.engineVersion}`);
});
