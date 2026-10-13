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
    const [input, output] = chatEcho.data.nodes.map((n) => String(n.id));
    const edits: unknown[] = [
      { kind: 'addNode', nodeId: 'CurrentDate-abcde', componentType: 'CurrentDate', position: { x: 0, y: 0 } },
      { kind: 'deleteNode', nodeId: input },
      { kind: 'disconnect', edgeId: String(chatEcho.data.edges[0].id) },
      { kind: 'connect', nodeId: input, sourceOutput: 'message', target: output, targetInput: 'input_value' },
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

// ---- connect, disconnect, deleteNode ----

const add = (type: string, id: string): FlowEdit => ({ kind: 'addNode', nodeId: `${type}-${id}`, componentType: type, position: { x: 0, y: 0 } });
const wire = (from: string, out: string, to: string, input: string, targetLoop = false): FlowEdit => ({ kind: 'connect', nodeId: from, sourceOutput: out, target: to, targetInput: input, ...(targetLoop ? { targetLoop: true } : {}) });

test('connect: rebuilding the fixture connection gives the exact bytes Langflow wrote', () => {
  const original = structuredClone(chatEcho);
  const edge = original.data.edges[0];
  const stripped = structuredClone(original);
  stripped.data.edges = [];
  // Langflow copies the input's accepted types into the handle when the connection is made. This export's
  // template was updated after that, so set the field back to the types recorded in the handle.
  const target = stripped.data.nodes.find((n) => n.id === edge.target)!;
  const recorded = (edge.data as { targetHandle: { inputTypes: string[] } }).targetHandle.inputTypes;
  (target.data!.node!.template!.input_value as { input_types: string[] }).input_types = recorded;
  const { flow, rejected } = applyEdits(stripped, [wire(String(edge.source), 'message', String(edge.target), 'input_value')]);
  assert.deepEqual(rejected, []);
  const made = flow.data.edges[0];
  assert.equal(made.sourceHandle, edge.sourceHandle);
  assert.equal(made.targetHandle, edge.targetHandle);
  assert.equal(made.id, edge.id);
  assert.deepEqual(made.data, edge.data);
});

test('connect: compatible types connect; the canvas shows ports and the typed connection', () => {
  const { flow, rejected } = applyEdits(empty(), [
    add('ChatInput', 'aaaaa'), add('CalculatorComponent', 'bbbbb'), add('ChatOutput', 'ccccc'),
    wire('ChatInput-aaaaa', 'message', 'CalculatorComponent-bbbbb', 'expression'),
    wire('CalculatorComponent-bbbbb', 'result', 'ChatOutput-ccccc', 'input_value'),
  ], ctx());
  assert.deepEqual(rejected, []);
  const canvas = toCanvas(flow);
  const calc = canvas.nodes.find((n) => n.componentType === 'CalculatorComponent')!;
  assert.deepEqual(calc.outputs.map((o) => [o.name, o.types]), [['result', ['JSON']]]);
  assert.deepEqual(calc.inputs.map((i) => i.name), ['expression']);
  assert.equal(canvas.edges.length, 2);
  assert.deepEqual(canvas.edges.map((e) => `${e.sourceOutput}->${e.targetInput}`), ['message->expression', 'result->input_value']);
  assert.ok(canvas.edges.every((e) => !e.decodeError && !e.targetLoop));
  assert.ok(calc.fields.find((f) => f.name === 'expression')!.connected, 'the connected input is marked');
});

test('connect: mismatched types, self links, settings, unknown ports, second links, duplicates and cycles are refused', () => {
  const base = applyEdits(empty(), [
    add('ChatInput', 'aaaaa'), add('CalculatorComponent', 'bbbbb'), add('ConditionalRouter', 'ccccc'), add('CurrentDate', 'ddddd'),
    add('TypeConverterComponent', 'eeeee'), add('TypeConverterComponent', 'fffff'),
    wire('ChatInput-aaaaa', 'message', 'ConditionalRouter-ccccc', 'input_text'),
    wire('TypeConverterComponent-eeeee', 'message_output', 'TypeConverterComponent-fffff', 'input_data'),
  ], ctx());
  assert.deepEqual(base.rejected, []);
  const cases: Array<[FlowEdit, RegExp]> = [
    [wire('CalculatorComponent-bbbbb', 'result', 'ConditionalRouter-ccccc', 'match_text'), /Types do not match: "Calculator" → "result" sends JSON, but "If-Else" → "match_text" takes Message/],
    [wire('ChatInput-aaaaa', 'message', 'ChatInput-aaaaa', 'input_value'), /cannot connect to itself/],
    [wire('ChatInput-aaaaa', 'message', 'CurrentDate-ddddd', 'timezone'), /is a setting, not an input/],
    [wire('ChatInput-aaaaa', 'nope', 'ConditionalRouter-ccccc', 'match_text'), /has no output named "nope"/],
    [wire('ChatInput-aaaaa', 'message', 'ConditionalRouter-ccccc', 'nope'), /has no input named "nope"/],
    [wire('ChatInput-aaaaa', 'message', 'Missing-zzzzz', 'x'), /No component with id "Missing-zzzzz"/],
    [wire('ChatInput-aaaaa', 'message', 'ConditionalRouter-ccccc', 'input_text'), /already exists/],
    [wire('CurrentDate-ddddd', 'current_date', 'ConditionalRouter-ccccc', 'input_text'), /already has a connection and takes only one/],
    [wire('TypeConverterComponent-fffff', 'message_output', 'TypeConverterComponent-eeeee', 'input_data'), /loop back on itself/],
    [wire('ChatInput-aaaaa', 'message', 'CalculatorComponent-bbbbb', 'expression', true), /no loop output/],
  ];
  for (const [edit, reason] of cases) {
    const { flow, applied, rejected } = applyEdits(base.flow, [edit], ctx());
    assert.equal(applied, 0, JSON.stringify(edit));
    assert.match(rejected[0]?.reason ?? '', reason, JSON.stringify(edit));
    assert.equal(contentHash(flow), contentHash(base.flow), 'a refused edit changes nothing');
  }
});

test('connect: a loop feedback lands on the loop output, like Langflow loops', () => {
  const { flow, rejected } = applyEdits(empty(), [
    add('LoopComponent', 'lllll'), add('TypeConverterComponent', 'ttttt'),
    wire('LoopComponent-lllll', 'item', 'TypeConverterComponent-ttttt', 'input_data'),
    wire('TypeConverterComponent-ttttt', 'data_output', 'LoopComponent-lllll', 'item', true),
  ], ctx());
  assert.deepEqual(rejected, []);
  const feedback = toCanvas(flow).edges.find((e) => e.targetLoop)!;
  assert.equal(feedback.targetInput, 'item');
  assert.equal(feedback.target, 'LoopComponent-lllll');
  const decoded = flow.data.edges[1].data as { targetHandle: Record<string, unknown> };
  assert.deepEqual(Object.keys(decoded.targetHandle).sort(), ['dataType', 'id', 'name', 'output_types']);
});

test('disconnect and deleteNode: connections and components go away cleanly', () => {
  const built = applyEdits(empty(), [
    add('ChatInput', 'aaaaa'), add('ChatOutput', 'ccccc'), add('CurrentDate', 'ddddd'),
    wire('ChatInput-aaaaa', 'message', 'ChatOutput-ccccc', 'input_value'),
  ], ctx());
  const edgeId = String(built.flow.data.edges[0].id);
  const cut = applyEdits(built.flow, [{ kind: 'disconnect', edgeId }]);
  assert.equal(cut.applied, 1);
  assert.equal(cut.flow.data.edges.length, 0);
  assert.equal(cut.flow.data.nodes.length, 3, 'disconnect keeps both components');
  assert.match(applyEdits(built.flow, [{ kind: 'disconnect', edgeId: 'nope' }]).rejected[0].reason, /not in this flow/);

  const removed = applyEdits(built.flow, [{ kind: 'deleteNode', nodeId: 'ChatInput-aaaaa' }]);
  assert.equal(removed.applied, 1);
  assert.deepEqual(removed.flow.data.nodes.map((n) => n.id), ['ChatOutput-ccccc', 'CurrentDate-ddddd']);
  assert.equal(removed.flow.data.edges.length, 0, 'its connections are dropped with it');
  assert.match(applyEdits(built.flow, [{ kind: 'deleteNode', nodeId: 'nope' }]).rejected[0].reason, /No component/);
});

test('route: a type mismatch is refused and nothing is saved; a valid connect, disconnect and delete save', async () => {
  const imported = await importFlow(empty());
  const setup = await patch(imported.id, { expectedHash: imported.hash, edits: [add('ChatInput', 'aaaaa'), add('CalculatorComponent', 'bbbbb'), add('ConditionalRouter', 'ccccc')] });
  assert.equal(setup.status, 200, 'saving a flow that still has empty required settings is allowed; only runs are gated');
  const id = imported.id;
  const hash = setup.body.hash as string;
  const bad = await patch(id, { expectedHash: hash, edits: [wire('CalculatorComponent-bbbbb', 'result', 'ConditionalRouter-ccccc', 'input_text')] });
  assert.equal(bad.status, 422);
  assert.match((bad.body.rejected as Array<{ reason: string; kind: string }>)[0].reason, /Types do not match/);
  const same = await json(await flowRoute.GET(req('GET', `/api/langflow/flows/${id}`, undefined), params(id)));
  assert.equal(same.body.hash, hash);

  const good = await patch(id, { expectedHash: hash, edits: [wire('ChatInput-aaaaa', 'message', 'ConditionalRouter-ccccc', 'input_text')] });
  assert.equal(good.status, 200);
  const detail = await json(await flowRoute.GET(req('GET', `/api/langflow/flows/${id}`, undefined), params(id)));
  const edges = (detail.body.canvas as { edges: Array<{ id: string }> }).edges;
  assert.equal(edges.length, 1);
  const cut = await patch(id, { expectedHash: good.body.hash, edits: [{ kind: 'disconnect', edgeId: edges[0].id }, { kind: 'deleteNode', nodeId: 'CalculatorComponent-bbbbb' }] });
  assert.equal(cut.status, 200);
  assert.equal(cut.body.applied, 2);
});

test('route: malformed connect, disconnect and delete shapes are refused', async () => {
  const { id, hash } = await importFlow(empty());
  for (const edit of [
    { kind: 'connect', nodeId: 'a', sourceOutput: 'x', target: 'b' },
    { kind: 'connect', nodeId: 'a', sourceOutput: 'x', target: 'b', targetInput: '' },
    { kind: 'connect', nodeId: 'a', sourceOutput: 'x', target: 'b', targetInput: 'y', targetLoop: 'yes' },
    { kind: 'disconnect' },
    { kind: 'disconnect', edgeId: 5 },
    { kind: 'deleteNode' },
  ]) {
    assert.equal((await patch(id, { expectedHash: hash, edits: [edit] })).status, 422, JSON.stringify(edit));
  }
});
