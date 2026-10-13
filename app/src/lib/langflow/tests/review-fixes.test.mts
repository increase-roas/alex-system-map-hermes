// Regression tests for the findings of the 2026-10-13 security and correctness reviews of the nodes work.
// Each test names the finding it pins down.
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
import { builtinCodeHash, componentTemplate, resetCatalogCache } from '../catalog';
import { applyEdits, executionPlan, redactForExport, REDACTED, stripSecretsForImport, toCanvas, validateFlow, type EditContext, type FlowEdit, type LfFlow, type RunContext } from '../model';
import { queueEditInto } from '../queue';
import { screenText } from '../redact';
import { runnerConfig } from '../runner';
import { runBlockReason, tierOf } from '../tiers';

const SUBSET = fileURLToPath(new URL('../fixtures/component-index.subset.json', import.meta.url));
const tmp = fs.mkdtempSync(path.join(process.env.TMPDIR ?? os.tmpdir(), 'lf-review-'));
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
const engine = (): RunContext => ({ builtinCodeHash: (t) => builtinCodeHash(runnerConfig({}), t) });
const empty = (): LfFlow => ({ id: randomUUID(), name: 'review', description: '', data: { nodes: [], edges: [] } });
const add = (type: string, id: string): FlowEdit => ({ kind: 'addNode', nodeId: `${type}-${id}`, componentType: type, position: { x: 0, y: 0 } });
const wire = (from: string, out: string, to: string, input: string, targetLoop = false): FlowEdit => ({ kind: 'connect', nodeId: from, sourceOutput: out, target: to, targetInput: input, ...(targetLoop ? { targetLoop: true } : {}) });
const headers = () => new Headers({ host: '127.0.0.1:3200', 'content-type': 'application/json', 'x-local-token': getOrCreateLocalToken() });

async function importFlow(flow: LfFlow) {
  const res = await flowsRoute.POST(new Request('http://127.0.0.1:3200/api/langflow/flows', { method: 'POST', headers: headers(), body: JSON.stringify(flow) }));
  return { status: res.status, body: (await res.json()) as Record<string, unknown> };
}
async function patch(id: string, body: unknown) {
  const res = await flowRoute.PATCH(new Request(`http://127.0.0.1:3200/api/langflow/flows/${id}`, { method: 'PATCH', headers: headers(), body: JSON.stringify(body) }), { params: Promise.resolve({ flowId: id }) });
  return { status: res.status, body: (await res.json()) as Record<string, unknown> };
}

/** Import an empty flow, then add components through the save route (import refuses flows with errors). */
async function setup(edits: FlowEdit[]): Promise<{ id: string; hash: string }> {
  const made = await importFlow(empty());
  assert.equal(made.status, 201);
  const saved = await patch(made.body.id as string, { expectedHash: made.body.hash, edits });
  assert.equal(saved.status, 200, JSON.stringify(saved.body));
  return { id: made.body.id as string, hash: saved.body.hash as string };
}

// ---- security review ----

test('security C1: a real component labelled as a note is not skipped; only node.type noteNode is a note (engine rule)', () => {
  const flow = structuredClone(chatEcho);
  const disguised = applyEdits(empty(), [add('CurrentDate', 'zzzzz')], ctx()).flow.data.nodes[0];
  disguised.data!.type = 'note';
  (disguised.data!.node!.template!.code as { value: string }).value += '\n# payload';
  flow.data.nodes.push(disguised);
  const plan = executionPlan(flow, engine());
  assert.ok(plan.blockers.some((b) => b.nodeId === disguised.id), 'the disguised node blocks the run');
  assert.ok(validateFlow(flow).some((p) => p.level === 'error' && p.nodeId === disguised.id && /labelled as a note but is a real component/.test(p.message)));
  const canvasNode = toCanvas(flow).nodes.find((n) => n.id === disguised.id)!;
  assert.equal(canvasNode.isNote, false);
  // A real note (node.type noteNode) is still a note.
  const real = structuredClone(chatEcho);
  real.data.nodes.push({ id: 'note-abcde', type: 'noteNode', position: { x: 0, y: 0 }, data: { type: 'note', node: { description: 'hi' } } });
  assert.deepEqual(executionPlan(real, engine()).blockers, []);
});

test('security H1: the code check compares the full sha256, not a 48-bit prefix', () => {
  const full = builtinCodeHash(runnerConfig({}), 'ChatInput')!;
  assert.equal(full.length, 64);
});

test('security M1: values under secret-looking keys in JSON settings are refused, stripped on import, hidden on display and export', async () => {
  const flow = applyEdits(empty(), [add('CSVAgent', 'aaaaa'), add('DynamicCreateData', 'bbbbb')], ctx()).flow;
  const refused = applyEdits(flow, [{ kind: 'setField', nodeId: 'CSVAgent-aaaaa', field: 'pandas_kwargs', value: { storage_options: { token: 'opaque-value-123' } } }], ctx());
  assert.match(refused.rejected[0].reason, /never stores secrets/);
  const tableRow = applyEdits(flow, [{ kind: 'setField', nodeId: 'DynamicCreateData-bbbbb', field: 'form_fields', value: [{ field_name: 'Authorization', field_type: 'Text' }] }], ctx());
  assert.deepEqual(tableRow.rejected, [], 'a field merely named after a secret, with no secret value, is fine');

  const withSecret = structuredClone(flow);
  const kw = withSecret.data.nodes.find((n) => n.id === 'CSVAgent-aaaaa')!.data!.node!.template!.pandas_kwargs as { value: unknown };
  kw.value = { headers: [{ key: 'Authorization', value: 'Bearer abcdefghijklmnop' }], api_key: 'not-a-real-key-1', sep: ';' };
  const shown = toCanvas(withSecret).nodes.find((n) => n.id === 'CSVAgent-aaaaa')!.fields.find((f) => f.name === 'pandas_kwargs')!.value as Record<string, unknown>;
  assert.equal(shown.api_key, REDACTED);
  assert.equal((shown.headers as Array<{ value: string }>)[0].value, REDACTED);
  assert.equal(shown.sep, ';');
  assert.equal((kw.value as { api_key: string }).api_key, 'not-a-real-key-1', 'display redaction never changes the stored flow');
  const exported = redactForExport(withSecret);
  assert.ok(exported.redacted >= 2);
  assert.ok(!JSON.stringify(exported.flow).includes('not-a-real-key-1'));
  const stripped = stripSecretsForImport(withSecret);
  assert.equal(stripped.removed, 2);
  assert.ok(!JSON.stringify(stripped.flow).includes('abcdefghijklmnop'));

  // Import strips them: a harmless flow carrying the same JSON setting on Chat Output.
  const echo = structuredClone(chatEcho);
  const out = echo.data.nodes.find((n) => n.data?.type === 'ChatOutput')!;
  out.data!.node!.template!.extra_kwargs = { type: 'dict', show: true, display_name: 'Extra', value: structuredClone(kw.value) };
  const made = await importFlow(echo);
  assert.equal(made.status, 201, JSON.stringify(made.body));
  assert.equal(made.body.secretsRemoved, 2);
  const res = await exportRoute.GET(new Request(`http://127.0.0.1:3200/api/langflow/flows/${made.body.id}/export`, { headers: headers() }), { params: Promise.resolve({ flowId: made.body.id as string }) });
  const text = await res.text();
  assert.ok(!text.includes('abcdefghijklmnop') && !text.includes('not-a-real-key-1'));
  assert.equal(screenText('Authorization: Bearer abcdefghijklmnop'), 'Authorization: Bearer [redacted]');
});

test('security M2 and L2: deeply nested JSON values and oversized add batches are refused before the model', async () => {
  const { id, hash } = await setup([add('CSVAgent', 'aaaaa')]);
  let deep: unknown = {};
  for (let i = 0; i < 40; i += 1) deep = { a: deep };
  assert.equal((await patch(id, { expectedHash: hash, edits: [{ kind: 'setField', nodeId: 'CSVAgent-aaaaa', field: 'pandas_kwargs', value: deep }] })).status, 422);
  const many = Array.from({ length: 101 }, (_, i) => ({ kind: 'addNode', nodeId: `CurrentDate-${String(i).padStart(5, '0')}`, componentType: 'CurrentDate', position: { x: 0, y: 0 } }));
  const tooMany = await patch(id, { expectedHash: hash, edits: many });
  assert.equal(tooMany.status, 422);
  assert.match(String(tooMany.body.error), /at most 100 components per save/);
});

test('security L1: prompts with too many variables are refused', () => {
  const flow = applyEdits(empty(), [add('Prompt Template', 'ppppp')], ctx()).flow;
  const text = Array.from({ length: 101 }, (_, i) => `{v${i}}`).join(' ');
  const r = applyEdits(flow, [{ kind: 'setField', nodeId: 'Prompt Template-ppppp', field: 'template', value: text }], ctx());
  assert.match(r.rejected[0].reason, /more than 100 \{variables\}/);
});

// ---- correctness review ----

test('correctness H1: a Message output can feed a loop back (loop_types), and the canvas port carries those types', () => {
  const r = applyEdits(empty(), [
    add('LoopComponent', 'lllll'), add('ParserComponent', 'ppppp'),
    wire('LoopComponent-lllll', 'item', 'ParserComponent-ppppp', 'input_data'),
    wire('ParserComponent-ppppp', 'parsed_text', 'LoopComponent-lllll', 'item', true),
  ], ctx());
  assert.deepEqual(r.rejected, []);
  const item = toCanvas(r.flow).nodes.find((n) => n.componentType === 'LoopComponent')!.outputs.find((o) => o.name === 'item')!;
  assert.deepEqual(item.loopTypes, ['Message']);
});

test('correctness H2: a newer prompt value keeps its place, so a connection to its new variable still follows it', () => {
  const setPrompt = (text: string): FlowEdit => ({ kind: 'setField', nodeId: 'Prompt Template-ppppp', field: 'template', value: text });
  let list: FlowEdit[] = [add('ChatInput', 'iiiii'), add('Prompt Template', 'ppppp'), setPrompt('Hi {name}'), wire('ChatInput-iiiii', 'message', 'Prompt Template-ppppp', 'name')];
  list = queueEditInto(list, setPrompt('Hi {name}!'));
  assert.equal(list.length, 4);
  assert.equal(list[2].kind, 'setField');
  assert.equal(list[3].kind, 'connect');
  assert.deepEqual(applyEdits(empty(), list, ctx()).rejected, []);
  assert.equal(queueEditInto(list, add('CurrentDate', 'ddddd')).length, 5, 'structural edits are never merged');
});

test('correctness M3: a loop feedback is not a cycle, whatever order the wires are made in', () => {
  const feedbackFirst = applyEdits(empty(), [
    add('LoopComponent', 'lllll'), add('TypeConverterComponent', 'ttttt'),
    wire('TypeConverterComponent-ttttt', 'data_output', 'LoopComponent-lllll', 'item', true),
    wire('LoopComponent-lllll', 'item', 'TypeConverterComponent-ttttt', 'input_data'),
  ], ctx());
  assert.deepEqual(feedbackFirst.rejected, []);
  assert.ok(!validateFlow(feedbackFirst.flow).some((p) => /loops back on itself/.test(p.message)), 'a valid loop gets no cycle warning');
});

test('correctness M4: empty, hex, exponent and boolean values are not numbers', () => {
  const flow = applyEdits(empty(), [add('ConditionalRouter', 'ccccc')], ctx()).flow;
  for (const value of ['', '  ', '0x10', '1e3', true]) {
    const r = applyEdits(flow, [{ kind: 'setField', nodeId: 'ConditionalRouter-ccccc', field: 'max_iterations', value }], ctx());
    assert.equal(r.applied, 0, JSON.stringify(value));
    assert.match(r.rejected[0].reason, /whole number/);
  }
  assert.equal(applyEdits(flow, [{ kind: 'setField', nodeId: 'ConditionalRouter-ccccc', field: 'max_iterations', value: ' 12 ' }], ctx()).applied, 1);
});

test('correctness M6: a null value is refused with a reason and an index, not as an unreadable batch', async () => {
  const made = await setup([add('CSVAgent', 'aaaaa')]);
  const r = await patch(made.id, { expectedHash: made.hash, edits: [{ kind: 'setField', nodeId: 'CSVAgent-aaaaa', field: 'pandas_kwargs', value: null }] });
  assert.equal(r.status, 422);
  const rejected = r.body.rejected as Array<{ index: number; reason: string }>;
  assert.equal(rejected[0].index, 0);
  assert.match(rejected[0].reason, /JSON object/);
});

test('correctness L7: names like "constructor" are unknown, not object internals', () => {
  assert.equal(tierOf('constructor'), 'unknown');
  assert.equal(tierOf('toString'), 'unknown');
  assert.match(runBlockReason('constructor', 'x')!, /is not in the checked component list/);
});

test('correctness L8: switching to double brackets resyncs the prompt variables', () => {
  const base = applyEdits(empty(), [add('Prompt Template', 'ppppp'), { kind: 'setField', nodeId: 'Prompt Template-ppppp', field: 'template', value: 'Hi {a} and {{b}}' }], ctx()).flow;
  const custom = (f: LfFlow) => (f.data.nodes[0].data!.node!.custom_fields as { template: string[] }).template;
  assert.deepEqual(custom(base), ['a']);
  const flipped = applyEdits(base, [{ kind: 'setField', nodeId: 'Prompt Template-ppppp', field: 'use_double_brackets', value: true }], ctx());
  assert.deepEqual(flipped.rejected, []);
  assert.deepEqual(custom(flipped.flow), ['b']);
});

test('security L3: engine error text loses the home folder path', async () => {
  const { stripLocalPaths } = await import('../redact');
  assert.equal(stripLocalPaths('cannot open /Users/someone/.venvs/x/run.json', '/Users/someone'), 'cannot open ~/.venvs/x/run.json');
  assert.equal(stripLocalPaths('no paths here', '/Users/someone'), 'no paths here');
  assert.equal(stripLocalPaths('/a/b', '/'), '/a/b', 'a root home is never stripped');
});
