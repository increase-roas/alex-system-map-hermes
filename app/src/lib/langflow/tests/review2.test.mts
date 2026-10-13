// Regression tests for the other-family alex-reviewer findings of 2026-10-13
// (reviews/receipts/2026-10-13-langflow-nodes/review-langflow-nodes-20261013T1750Z.md).
// F1: secrets nested in lists and objects. F2: every editable default of every current component re-saves.
// All secret values here are fake canaries.
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
import * as exportRoute from '../../../app/api/langflow/flows/[flowId]/export/route';
import { componentTemplate, loadCatalog, resetCatalogCache } from '../catalog';
import { applyEdits, contentHash, toCanvas, type EditContext, type FlowEdit, type JsonValue, type LfFlow } from '../model';
import { runnerConfig } from '../runner';
import { createFlow, flowFilePath } from '../store';

const SUBSET = fileURLToPath(new URL('../fixtures/component-index.subset.json', import.meta.url));
const tmp = fs.mkdtempSync(path.join(process.env.TMPDIR ?? os.tmpdir(), 'lf-review2-'));
const chatEcho = JSON.parse(fs.readFileSync(new URL('../fixtures/chat-echo.json', import.meta.url), 'utf8')) as LfFlow;
const live = !!process.env.LANGFLOW_LFX_BIN && fs.existsSync(process.env.LANGFLOW_LFX_BIN);
let savedIndexEnv: string | undefined;

function useIndex(file: string | undefined) {
  if (file === undefined) delete process.env.LANGFLOW_COMPONENT_INDEX;
  else process.env.LANGFLOW_COMPONENT_INDEX = file;
  resetCatalogCache();
}
before(() => {
  savedIndexEnv = process.env.LANGFLOW_COMPONENT_INDEX;
  useIndex(SUBSET);
  process.env.LOCAL_DATA_DIR = tmp;
});
after(() => useIndex(savedIndexEnv));

const ctx = (): EditContext => ({ template: (t) => componentTemplate(runnerConfig(), t) });
const empty = (): LfFlow => ({ id: randomUUID(), name: 'review2', description: '', data: { nodes: [], edges: [] } });
const headers = () => new Headers({ host: '127.0.0.1:3200', 'content-type': 'application/json', 'x-local-token': getOrCreateLocalToken() });
const params = (flowId: string) => ({ params: Promise.resolve({ flowId }) });

// ---- F1 ----

const CANARIES = ['CANARY-F1-LIST', 'CANARY-F1-NESTED', 'CANARY-F1-ROWVALUE', 'CANARY-F1-DEEPLIST', 'CANARY-F1-SIBLING'];
const NUMBER_CANARY = 987654321;
const nestedSecrets = (): JsonValue => ({
  token: [CANARIES[0]],
  credentials: { inner: { v: CANARIES[1] } },
  headers: [{ key: 'Authorization', value: { scheme: 'Bearer', parts: [CANARIES[2]] } }],
  api_key: [[CANARIES[3]]],
  rows: [{ name: 'X-Secret', value: CANARIES[4] }],
  password: NUMBER_CANARY,
  sep: ';',
});
const leaked = (text: string) => [...CANARIES, String(NUMBER_CANARY)].filter((c) => text.includes(c));

test('F1: a secret nested in a list or object under a secret-looking key is refused on edit', () => {
  const flow = applyEdits(empty(), [{ kind: 'addNode', nodeId: 'CSVAgent-aaaaa', componentType: 'CSVAgent', position: { x: 0, y: 0 } }], ctx()).flow;
  const one = (value: JsonValue) => applyEdits(flow, [{ kind: 'setField', nodeId: 'CSVAgent-aaaaa', field: 'pandas_kwargs', value }], ctx());
  for (const value of [
    { token: ['x-canary'] },
    { token: { inner: 'x-canary' } },
    { headers: [{ key: 'Authorization', value: { parts: ['x-canary'] } }] },
    { api_key: [['x-canary']] },
    { password: 1234 },
    nestedSecrets(),
  ] as JsonValue[]) {
    const r = one(value);
    assert.equal(r.applied, 0, JSON.stringify(value));
    assert.match(r.rejected[0].reason, /never stores secrets/);
  }
  const benign = { sep: ';', encoding: 'utf-8', nested: { list: [1, 'a', { b: true }] } };
  const ok = one(benign);
  assert.deepEqual(ok.rejected, [], 'benign nested values still save');
  const again = applyEdits(ok.flow, [{ kind: 'setField', nodeId: 'CSVAgent-aaaaa', field: 'pandas_kwargs', value: benign }], ctx());
  assert.equal(contentHash(again.flow), contentHash(ok.flow), 'benign value round-trips unchanged');
});

test('F1: nested secrets are removed on import before the file reaches disk, and the count is reported', async () => {
  const flow = structuredClone(chatEcho);
  const out = flow.data.nodes.find((n) => n.data?.type === 'ChatOutput')!;
  out.data!.node!.template!.extra_kwargs = { type: 'dict', show: true, display_name: 'Extra', value: nestedSecrets() };
  const res = await flowsRoute.POST(new Request('http://127.0.0.1:3200/api/langflow/flows', { method: 'POST', headers: headers(), body: JSON.stringify(flow) }));
  const body = (await res.json()) as { id: string; secretsRemoved: number };
  assert.equal(res.status, 201);
  // 7 leaves: the 5 string canaries, the number, and "Bearer", which sits inside the Authorization row's value.
  assert.equal(body.secretsRemoved, 7);
  const onDisk = fs.readFileSync(flowFilePath(body.id), 'utf8');
  assert.deepEqual(leaked(onDisk), [], 'no canary on disk');
  assert.ok(onDisk.includes('"sep": ";"'), 'the benign sibling is kept');
});

test('F1: a file that already holds nested secrets never shows them in read, dry run or export responses', async () => {
  // Simulates a flow file put on disk by hand (bypassing import).
  const flow = structuredClone(chatEcho);
  const out = flow.data.nodes.find((n) => n.data?.type === 'ChatOutput')!;
  out.data!.node!.template!.extra_kwargs = { type: 'dict', show: true, display_name: 'Extra', value: nestedSecrets() };
  const stored = createFlow(flow);
  assert.equal(leaked(fs.readFileSync(flowFilePath(stored.id), 'utf8')).length, 6, 'the canaries are really in the file');

  const read = await flowRoute.GET(new Request(`http://127.0.0.1:3200/api/langflow/flows/${stored.id}`, { headers: headers() }), params(stored.id));
  assert.equal(read.status, 200);
  assert.deepEqual(leaked(await read.text()), [], 'read response');

  const inputId = String(flow.data.nodes.find((n) => n.data?.type === 'ChatInput')!.id);
  const dry = await flowRoute.PATCH(new Request(`http://127.0.0.1:3200/api/langflow/flows/${stored.id}`, {
    method: 'PATCH', headers: headers(), body: JSON.stringify({ expectedHash: stored.hash, dryRun: true, edits: [{ kind: 'move', nodeId: inputId, position: { x: 1, y: 2 } }] }),
  }), params(stored.id));
  assert.equal(dry.status, 200);
  assert.deepEqual(leaked(await dry.text()), [], 'dry run response');

  const exp = await exportRoute.GET(new Request(`http://127.0.0.1:3200/api/langflow/flows/${stored.id}/export`, { headers: headers() }), params(stored.id));
  const text = await exp.text();
  assert.deepEqual(leaked(text), [], 'export');
  assert.ok(text.includes('[redacted]'));

  const field = toCanvas(flow).nodes.find((n) => n.componentType === 'ChatOutput')!.fields.find((f) => f.name === 'extra_kwargs')!;
  assert.deepEqual(leaked(JSON.stringify(field.value)), [], 'canvas value');
  assert.equal((field.value as { sep: string }).sep, ';');
});

// ---- F2 ----

function sweep(types: string[]): { flow: LfFlow; edits: FlowEdit[] } {
  const adds: FlowEdit[] = types.map((t, i) => ({ kind: 'addNode', nodeId: `${t}-${String(i).padStart(5, '0')}`, componentType: t, position: { x: i * 10, y: 0 } }));
  const { flow, rejected } = applyEdits(empty(), adds, ctx());
  assert.deepEqual(rejected, []);
  const edits: FlowEdit[] = [];
  for (const node of toCanvas(flow).nodes) {
    for (const f of node.fields.filter((x) => x.editable)) edits.push({ kind: 'setField', nodeId: node.id, field: f.name, value: f.value });
  }
  return { flow, edits };
}

function assertSweep(types: string[]): number {
  const { flow, edits } = sweep(types);
  const { flow: out, applied, rejected } = applyEdits(flow, edits, ctx());
  assert.deepEqual(rejected.map((r) => `${r.edit.kind === 'setField' ? `${r.edit.nodeId}.${r.edit.field}` : ''}: ${r.reason}`), []);
  assert.equal(applied, edits.length);
  assert.equal(JSON.stringify(out), JSON.stringify(flow), 'byte for byte the same');
  return edits.length;
}

test('F2: an optional number can be left empty or cleared; a required one cannot', () => {
  const flow = applyEdits(empty(), [{ kind: 'addNode', nodeId: 'ConditionalRouter-ccccc', componentType: 'ConditionalRouter', position: { x: 0, y: 0 } }], ctx()).flow;
  const field = (flow.data.nodes[0].data!.node!.template as Record<string, Record<string, unknown>>).max_iterations;
  const cleared = applyEdits(flow, [{ kind: 'setField', nodeId: 'ConditionalRouter-ccccc', field: 'max_iterations', value: '' }], ctx());
  assert.deepEqual(cleared.rejected, []);
  assert.equal((cleared.flow.data.nodes[0].data!.node!.template as Record<string, { value: unknown }>).max_iterations.value, '');
  field.required = true;
  const refused = applyEdits(flow, [{ kind: 'setField', nodeId: 'ConditionalRouter-ccccc', field: 'max_iterations', value: '' }], ctx());
  assert.match(refused.rejected[0].reason, /whole number/);
});

test('F2: "no value" sent back for a setting without a value changes nothing', () => {
  const flow = applyEdits(empty(), [{ kind: 'addNode', nodeId: 'CalculatorComponent-aaaaa', componentType: 'CalculatorComponent', position: { x: 0, y: 0 } }], ctx()).flow;
  delete (flow.data.nodes[0].data!.node!.template as Record<string, Record<string, unknown>>).expression.value;
  const r = applyEdits(flow, [{ kind: 'setField', nodeId: 'CalculatorComponent-aaaaa', field: 'expression', value: null }], ctx());
  assert.deepEqual(r.rejected, []);
  assert.equal(JSON.stringify(r.flow), JSON.stringify(flow));
});

test('F2: every editable default of every component in the test index re-saves byte for byte', () => {
  const cat = loadCatalog(runnerConfig());
  assert.ok(cat.ok);
  assert.ok(assertSweep(cat.catalog.components.map((c) => c.type)) >= 40);
});

test('F2 LIVE: every editable default of all 63 installed components re-saves byte for byte', { skip: !live && 'set LANGFLOW_LFX_BIN to the real lfx' }, () => {
  useIndex(undefined);
  try {
    const cat = loadCatalog(runnerConfig());
    assert.ok(cat.ok);
    assert.equal(cat.catalog.components.length, 63);
    const checked = assertSweep(cat.catalog.components.map((c) => c.type));
    console.log(`LIVE F2 sweep: lfx ${cat.catalog.engine.lfxVersion}, 63 components, ${checked} editable settings re-saved byte for byte, 0 refused`);
  } finally {
    useIndex(SUBSET);
  }
});
