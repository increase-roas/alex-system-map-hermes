// Setting editors: which settings are editable, how each type is checked, and that an untouched or
// re-saved setting leaves the saved file byte for byte the same. Templates come from real engine entries
// (fixtures/component-index.subset.json).
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
import { componentTemplate, loadCatalog, resetCatalogCache } from '../catalog';
import { applyEdits, contentHash, promptVariables, REDACTED, toCanvas, type CanvasField, type EditContext, type FlowEdit, type JsonValue, type LfFlow } from '../model';
import { runnerConfig } from '../runner';

const SUBSET = fileURLToPath(new URL('../fixtures/component-index.subset.json', import.meta.url));
const tmp = fs.mkdtempSync(path.join(process.env.TMPDIR ?? os.tmpdir(), 'lf-settings-'));
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
const ID: Record<string, string> = {};
function flowWith(...types: string[]): LfFlow {
  const edits: FlowEdit[] = types.map((t, i) => {
    ID[t] = `${t}-n${String(i).padStart(4, '0')}`;
    return { kind: 'addNode', nodeId: ID[t], componentType: t, position: { x: i * 300, y: 0 } };
  });
  const { flow, rejected } = applyEdits({ id: randomUUID(), name: 'settings', data: { nodes: [], edges: [] } }, edits, ctx());
  assert.deepEqual(rejected, []);
  return flow;
}
const field = (flow: LfFlow, type: string, name: string): CanvasField => toCanvas(flow).nodes.find((n) => n.id === ID[type])!.fields.find((f) => f.name === name)!;
const set = (type: string, name: string, value: JsonValue): FlowEdit => ({ kind: 'setField', nodeId: ID[type], field: name, value });
const rawValue = (flow: LfFlow, type: string, name: string) => ((flow.data.nodes.find((n) => n.id === ID[type])!.data!.node!.template as Record<string, { value: unknown }>)[name]).value;

test('editors: each setting type gets the right editor, and read-only ones say why', () => {
  const flow = flowWith('ConditionalRouter', 'TypeConverterComponent', 'LanguageModelComponent', 'Prompt Template', 'DynamicCreateData', 'CSVAgent', 'CalculatorComponent');
  const expect: Array<[string, string, string]> = [
    ['CalculatorComponent', 'expression', 'text'],
    ['ConditionalRouter', 'max_iterations', 'number'],
    ['ConditionalRouter', 'case_sensitive', 'bool'],
    ['ConditionalRouter', 'operator', 'select'],
    ['TypeConverterComponent', 'output_type', 'select'],
    ['LanguageModelComponent', 'system_message', 'multiline'],
    ['LanguageModelComponent', 'temperature', 'number'],
    ['Prompt Template', 'template', 'multiline'],
    ['DynamicCreateData', 'form_fields', 'json'],
    ['CSVAgent', 'pandas_kwargs', 'json'],
  ];
  for (const [type, name, editor] of expect) {
    const f = field(flow, type, name);
    assert.equal(f.editor, editor, `${type}.${name}`);
    assert.equal(f.editable, true, `${type}.${name}`);
  }
  assert.ok(field(flow, 'LanguageModelComponent', 'temperature').range, 'slider carries its range');
  assert.deepEqual(field(flow, 'DynamicCreateData', 'form_fields').columns, ['field_name', 'field_type']);
  const secret = field(flow, 'LanguageModelComponent', 'api_key');
  assert.equal(secret.editable, false);
  assert.match(secret.readOnlyReason!, /never stores secrets/);
  assert.match(field(flow, 'LanguageModelComponent', 'model').readOnlyReason!, /Model picker/);
  const code = field(flow, 'CalculatorComponent', 'code');
  assert.equal(code.editable, false);
  assert.equal(code.value, null, 'the code text is not sent to the panel');
  assert.match(code.summary!, /^\d+ lines of Python$/);
});

test('round trip: saving every editable setting back unchanged leaves the file byte for byte the same', () => {
  const types = loadCatalog(runnerConfig({})).ok ? ['ChatInput', 'ChatOutput', 'CalculatorComponent', 'CurrentDate', 'LanguageModelComponent', 'TypeConverterComponent', 'LoopComponent', 'Prompt Template', 'ParserComponent', 'ConditionalRouter', 'DynamicCreateData', 'CSVAgent'] : [];
  const flow = flowWith(...types);
  const edits: FlowEdit[] = [];
  for (const node of toCanvas(flow).nodes) {
    for (const f of node.fields.filter((x) => x.editable)) {
      edits.push({ kind: 'setField', nodeId: node.id, field: f.name, value: f.value });
    }
  }
  assert.ok(edits.length >= 40, `checked ${edits.length} settings`);
  const { flow: out, applied, rejected } = applyEdits(flow, edits, ctx());
  assert.deepEqual(rejected.map((r) => r.reason), []);
  assert.equal(applied, edits.length);
  assert.equal(contentHash(out), contentHash(flow));
  assert.equal(JSON.stringify(out), JSON.stringify(flow), 'same bytes, same key order');
});

test('numbers, sliders, choices and switches are checked', () => {
  const flow = flowWith('ConditionalRouter', 'LanguageModelComponent', 'TypeConverterComponent');
  const { min, max } = field(flow, 'LanguageModelComponent', 'temperature').range!;
  const ok = applyEdits(flow, [set('ConditionalRouter', 'max_iterations', '7'), set('LanguageModelComponent', 'temperature', max), set('TypeConverterComponent', 'output_type', 'JSON'), set('ConditionalRouter', 'case_sensitive', 'false')], ctx());
  assert.deepEqual(ok.rejected, []);
  assert.equal(rawValue(ok.flow, 'ConditionalRouter', 'max_iterations'), 7);
  assert.equal(rawValue(ok.flow, 'LanguageModelComponent', 'temperature'), max);
  assert.equal(rawValue(ok.flow, 'TypeConverterComponent', 'output_type'), 'JSON');
  assert.equal(rawValue(ok.flow, 'ConditionalRouter', 'case_sensitive'), false);
  const bad: Array<[FlowEdit, RegExp]> = [
    [set('ConditionalRouter', 'max_iterations', 2.5), /whole number/],
    [set('LanguageModelComponent', 'temperature', max + 1), new RegExp(`from ${min} to ${max}`)],
    [set('TypeConverterComponent', 'output_type', 'XML'), /must be one of: Message, JSON, Table/],
    [set('ConditionalRouter', 'case_sensitive', 'maybe'), /true or false/],
    [set('ConditionalRouter', 'max_iterations', { a: 1 }), /single value/],
    [set('LanguageModelComponent', 'api_key', 'sk-not-real'), /never stores secrets/],
    [set('LanguageModelComponent', 'api_key', REDACTED), /never stores secrets/],
  ];
  for (const [edit, reason] of bad) {
    const r = applyEdits(flow, [edit], ctx());
    assert.equal(r.applied, 0, JSON.stringify(edit));
    assert.match(r.rejected[0].reason, reason);
  }
});

test('JSON settings: objects for dictionaries, rows with known columns for tables', () => {
  const flow = flowWith('DynamicCreateData', 'CSVAgent');
  const rows = [{ field_name: 'city', field_type: 'Text' }];
  const ok = applyEdits(flow, [set('DynamicCreateData', 'form_fields', rows), set('CSVAgent', 'pandas_kwargs', { sep: ';', encoding: 'utf-8' })], ctx());
  assert.deepEqual(ok.rejected, []);
  assert.deepEqual(rawValue(ok.flow, 'DynamicCreateData', 'form_fields'), rows);
  assert.deepEqual(rawValue(ok.flow, 'CSVAgent', 'pandas_kwargs'), { sep: ';', encoding: 'utf-8' });
  const bad: Array<[FlowEdit, RegExp]> = [
    [set('DynamicCreateData', 'form_fields', { field_name: 'x' }), /list of rows/],
    [set('DynamicCreateData', 'form_fields', [1, 2]), /list of rows/],
    [set('DynamicCreateData', 'form_fields', [{ colour: 'red' }]), /no column named "colour". Columns: field_name, field_type/],
    [set('CSVAgent', 'pandas_kwargs', ['sep']), /JSON object/],
    [set('CSVAgent', 'pandas_kwargs', 'sep=;'), /JSON object/],
  ];
  for (const [edit, reason] of bad) {
    const r = applyEdits(flow, [edit], ctx());
    assert.equal(r.applied, 0, JSON.stringify(edit));
    assert.match(r.rejected[0].reason, reason);
  }
});

test('prompt: each {variable} becomes a message input like Langflow, and goes away when removed', () => {
  assert.deepEqual(promptVariables('Hi {name}, about {topic} and {name}. {{escaped}}'), ['name', 'topic']);
  assert.deepEqual(promptVariables('{{a}} and {b}', true), ['a']);
  const flow = flowWith('Prompt Template', 'ChatInput');
  const first = applyEdits(flow, [set('Prompt Template', 'template', 'Say: {topic}')], ctx());
  assert.deepEqual(first.rejected, []);
  const node = first.flow.data.nodes.find((n) => n.id === ID['Prompt Template'])!;
  const topic = (node.data!.node!.template as Record<string, Record<string, unknown>>).topic;
  assert.deepEqual(topic.input_types, ['Message']);
  assert.deepEqual((node.data!.node!.custom_fields as { template: string[] }).template, ['topic']);
  const canvasNode = toCanvas(first.flow).nodes.find((n) => n.id === ID['Prompt Template'])!;
  assert.ok(canvasNode.inputs.some((p) => p.name === 'topic'), 'the variable can be connected on the canvas');

  const renamed = applyEdits(first.flow, [set('Prompt Template', 'template', 'Hello {name}')], ctx());
  const tpl = renamed.flow.data.nodes.find((n) => n.id === ID['Prompt Template'])!.data!.node!.template as Record<string, unknown>;
  assert.equal(tpl.topic, undefined, 'the old variable input is removed');
  assert.ok(tpl.name);

  const wired = applyEdits(first.flow, [{ kind: 'connect', nodeId: ID.ChatInput, sourceOutput: 'message', target: ID['Prompt Template'], targetInput: 'topic' }], ctx());
  assert.deepEqual(wired.rejected, []);
  const blocked = applyEdits(wired.flow, [set('Prompt Template', 'template', 'No variables now')], ctx());
  assert.match(blocked.rejected[0].reason, /"\{topic\}" is still connected. Disconnect it/);
  assert.match(applyEdits(flow, [set('Prompt Template', 'template', 'Hi {first name}')], ctx()).rejected[0].reason, /not a usable variable name/);
  assert.match(applyEdits(flow, [set('Prompt Template', 'template', 'Hi {code}')], ctx()).rejected[0].reason, /clashes with the existing setting "code"/);
});

test('route: JSON settings travel through the save route; a bad table row saves nothing', async () => {
  const flow = flowWith('DynamicCreateData');
  const headers = new Headers({ host: '127.0.0.1:3200', 'content-type': 'application/json', 'x-local-token': getOrCreateLocalToken() });
  const made = await flowsRoute.POST(new Request('http://127.0.0.1:3200/api/langflow/flows', { method: 'POST', headers, body: JSON.stringify(flow) }));
  assert.equal(made.status, 201);
  const { id, hash } = (await made.json()) as { id: string; hash: string };
  const patch = async (edits: unknown[]) => {
    const res = await flowRoute.PATCH(new Request(`http://127.0.0.1:3200/api/langflow/flows/${id}`, { method: 'PATCH', headers, body: JSON.stringify({ expectedHash: hash, edits }) }), { params: Promise.resolve({ flowId: id }) });
    return { status: res.status, body: (await res.json()) as Record<string, unknown> };
  };
  const bad = await patch([set('DynamicCreateData', 'form_fields', [{ nope: 1 }])]);
  assert.equal(bad.status, 422);
  const good = await patch([set('DynamicCreateData', 'form_fields', [{ field_name: 'city', field_type: 'Text' }])]);
  assert.equal(good.status, 200);
  assert.equal(good.body.applied, 1);
});
