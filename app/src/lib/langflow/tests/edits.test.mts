// Structural edits (add, delete, connect, disconnect) on the model and through the save route.
// Templates come from a real-entry subset of the engine index (fixtures/component-index.subset.json).
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';
import { after, before, test } from 'node:test';

import { getOrCreateLocalToken } from '../../server/local-auth';
import * as flowsRoute from '../../../app/api/langflow/flows/route';
import * as flowRoute from '../../../app/api/langflow/flows/[flowId]/route';
import { componentTemplate, resetCatalogCache } from '../catalog';
import { applyEdits, contentHash, toCanvas, type EditContext, type FlowEdit, type LfFlow } from '../model';
import { runnerConfig } from '../runner';

const SUBSET = fileURLToPath(new URL('../fixtures/component-index.subset.json', import.meta.url));
const tmp = fs.mkdtempSync(path.join(process.env.TMPDIR ?? os.tmpdir(), 'lf-edits-'));
const chatEcho = JSON.parse(fs.readFileSync(new URL('../fixtures/chat-echo.json', import.meta.url), 'utf8')) as LfFlow;
let savedIndexEnv: string | undefined;

before(() => {
  savedIndexEnv = process.env.LANGFLOW_COMPONENT_INDEX;
  process.env.LANGFLOW_COMPONENT_INDEX = SUBSET;
  process.env.LOCAL_DATA_DIR = tmp;
  resetCatalogCache();
});
after(() => {
  if (savedIndexEnv === undefined) delete process.env.LANGFLOW_COMPONENT_INDEX;
  else process.env.LANGFLOW_COMPONENT_INDEX = savedIndexEnv;
  resetCatalogCache();
});

const ctx = (): EditContext => ({ template: (t) => componentTemplate(runnerConfig({}), t) });
const empty = (): LfFlow => ({ id: randomUUID(), name: 'empty', description: '', data: { nodes: [], edges: [] } });

type Opts = { tailnet?: string; token?: boolean };
function req(method: string, pathname: string, body: unknown, opts: Opts = {}): Request {
  const headers = new Headers({ host: '127.0.0.1:3200', 'content-type': 'application/json' });
  if (opts.tailnet) {
    headers.set('host', 'mac.tailnet.ts.net');
    headers.set('tailscale-user-login', opts.tailnet);
  } else if (opts.token !== false) {
    headers.set('x-local-token', getOrCreateLocalToken());
  }
  return new Request(`http://127.0.0.1:3200${pathname}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
}
const params = (flowId: string) => ({ params: Promise.resolve({ flowId }) });
const json = async (res: Response) => ({ status: res.status, body: (await res.json()) as Record<string, unknown> });

async function importFlow(flow: LfFlow): Promise<{ id: string; hash: string }> {
  const made = await json(await flowsRoute.POST(req('POST', '/api/langflow/flows', flow)));
  assert.equal(made.status, 201, JSON.stringify(made.body));
  return { id: made.body.id as string, hash: made.body.hash as string };
}
async function patch(id: string, body: unknown, opts: Opts = {}) {
  return json(await flowRoute.PATCH(req('PATCH', `/api/langflow/flows/${id}`, body, opts), params(id)));
}

// ---- addNode ----

test('addNode: the engine template is copied in with Langflow\'s node shape and id style', () => {
  const { flow, applied, rejected } = applyEdits(empty(), [{ kind: 'addNode', nodeId: 'CalculatorComponent-aB3x9', componentType: 'CalculatorComponent', position: { x: 10, y: 20 } }], ctx());
  assert.deepEqual(rejected, []);
  assert.equal(applied, 1);
  const node = flow.data.nodes[0];
  assert.equal(node.id, 'CalculatorComponent-aB3x9');
  assert.equal(node.type, 'genericNode');
  assert.deepEqual(node.position, { x: 10, y: 20 });
  assert.equal(node.data?.type, 'CalculatorComponent');
  assert.equal(node.data?.id, node.id);
  assert.deepEqual(node.data?.node, componentTemplate(runnerConfig({}), 'CalculatorComponent'), 'the saved template is the engine\'s, unchanged');
  const canvas = toCanvas(flow);
  assert.equal(canvas.nodes[0].label, 'Calculator', 'label falls back to the template display name');
});

test('addNode: unknown, legacy, badly named, duplicate or unplaced components are refused with a reason', () => {
  const cases: Array<[FlowEdit, RegExp]> = [
    [{ kind: 'addNode', nodeId: 'NoSuch-abcde', componentType: 'NoSuch', position: { x: 0, y: 0 } }, /not a current component/],
    [{ kind: 'addNode', nodeId: 'CrewAIAgentComponent-abcde', componentType: 'CrewAIAgentComponent', position: { x: 0, y: 0 } }, /not a current component/],
    [{ kind: 'addNode', nodeId: 'Calc-abcde', componentType: 'CalculatorComponent', position: { x: 0, y: 0 } }, /must look like "CalculatorComponent-"/],
    [{ kind: 'addNode', nodeId: 'CalculatorComponent-ab', componentType: 'CalculatorComponent', position: { x: 0, y: 0 } }, /must look like/],
    [{ kind: 'addNode', nodeId: 'CalculatorComponent-abcde', componentType: 'CalculatorComponent', position: { x: Number.NaN, y: 0 } }, /finite position/],
  ];
  for (const [edit, reason] of cases) {
    const { applied, rejected } = applyEdits(empty(), [edit], ctx());
    assert.equal(applied, 0, edit.nodeId);
    assert.match(rejected[0].reason, reason);
  }
  const twice = applyEdits(empty(), [
    { kind: 'addNode', nodeId: 'CurrentDate-abcde', componentType: 'CurrentDate', position: { x: 0, y: 0 } },
    { kind: 'addNode', nodeId: 'CurrentDate-abcde', componentType: 'CurrentDate', position: { x: 0, y: 0 } },
  ], ctx());
  assert.match(twice.rejected[0].reason, /already used/);
  const noEngine = applyEdits(empty(), [{ kind: 'addNode', nodeId: 'CurrentDate-abcde', componentType: 'CurrentDate', position: { x: 0, y: 0 } }]);
  assert.match(noEngine.rejected[0].reason, /not a current component/, 'without the engine nothing can be added');
});

test('addNode: names with spaces get Langflow-style ids', () => {
  const { rejected } = applyEdits(empty(), [{ kind: 'addNode', nodeId: 'Prompt Template-Zz9Yy', componentType: 'Prompt Template', position: { x: 0, y: 0 } }], ctx());
  assert.deepEqual(rejected, []);
});

test('route addNode: saves for the owner; a dry run previews and writes nothing; a refused add saves nothing', async () => {
  const { id, hash } = await importFlow(empty());
  const add = { kind: 'addNode', nodeId: 'CurrentDate-q1w2e', componentType: 'CurrentDate', position: { x: 0, y: 0 } };
  const preview = await patch(id, { expectedHash: hash, edits: [add], dryRun: true });
  assert.equal(preview.status, 200);
  assert.equal(preview.body.dryRun, true);
  assert.equal((preview.body.canvas as { nodes: unknown[] }).nodes.length, 1);
  assert.equal(preview.body.hash, hash, 'a dry run leaves the saved version alone');

  const refused = await patch(id, { expectedHash: hash, edits: [add, { kind: 'addNode', nodeId: 'NoSuch-abcde', componentType: 'NoSuch', position: { x: 0, y: 0 } }] });
  assert.equal(refused.status, 422);
  assert.equal((refused.body.rejected as Array<{ index: number }>)[0].index, 1, 'the refusal points at the edit that failed');
  const stillEmpty = await json(await flowRoute.GET(req('GET', `/api/langflow/flows/${id}`, undefined), params(id)));
  assert.equal(stillEmpty.body.hash, hash, 'all or nothing: the good add was not saved either');

  const saved = await patch(id, { expectedHash: hash, edits: [add] });
  assert.equal(saved.status, 200);
  assert.equal(saved.body.applied, 1);
});

test('route: malformed structural edits are refused before they reach the model', async () => {
  const { id, hash } = await importFlow(empty());
  for (const edit of [
    { kind: 'addNode', nodeId: 'CurrentDate-abcde', componentType: 'CurrentDate' },
    { kind: 'addNode', nodeId: 'CurrentDate-abcde', componentType: 7, position: { x: 0, y: 0 } },
    { kind: 'addNode', nodeId: 'CurrentDate-abcde', componentType: 'x'.repeat(121), position: { x: 0, y: 0 } },
  ]) {
    assert.equal((await patch(id, { expectedHash: hash, edits: [edit] })).status, 422);
  }
  assert.equal((await patch(id, { expectedHash: hash, edits: [], dryRun: 'yes' })).status, 422);
});

test('route: tailnet and token-less callers get 403 on structural edits and dry runs', async () => {
  const { id, hash } = await importFlow(structuredClone(chatEcho));
  const access = path.join(tmp, 'langflow', 'access.json');
  fs.mkdirSync(path.dirname(access), { recursive: true });
  fs.writeFileSync(access, JSON.stringify({ owner: { ops: ['read', 'save', 'run', 'stop'], flows: '*' }, tailnet: { 'alex@example.com': { ops: ['read', 'save', 'run'], flows: '*' } } }));
  try {
    const edits: unknown[] = [
      { kind: 'addNode', nodeId: 'CurrentDate-abcde', componentType: 'CurrentDate', position: { x: 0, y: 0 } },
    ];
    for (const edit of edits) {
      for (const dryRun of [false, true]) {
        const listed = await patch(id, { expectedHash: hash, edits: [edit], dryRun }, { tailnet: 'alex@example.com' });
        assert.equal(listed.status, 403, `listed tailnet ${(edit as { kind: string }).kind} dryRun=${dryRun}`);
        assert.match(String(listed.body.error), /read-only/);
        const stranger = await patch(id, { expectedHash: hash, edits: [edit], dryRun }, { tailnet: 'stranger@example.com' });
        assert.equal(stranger.status, 403);
        const reader = await patch(id, { expectedHash: hash, edits: [edit], dryRun }, { token: false });
        assert.equal(reader.status, 403);
      }
    }
    const after = await json(await flowRoute.GET(req('GET', `/api/langflow/flows/${id}`, undefined), params(id)));
    assert.equal(after.body.hash, hash, 'nothing was written');
  } finally {
    fs.rmSync(access, { force: true });
  }
});

test('content hash is stable: an add then nothing else changes exactly one node', () => {
  const base = empty();
  const { flow } = applyEdits(base, [{ kind: 'addNode', nodeId: 'CurrentDate-abcde', componentType: 'CurrentDate', position: { x: 0, y: 0 } }], ctx());
  assert.notEqual(contentHash(flow), contentHash(base));
  assert.deepEqual({ ...flow, data: { ...flow.data, nodes: [] } }, base);
});
