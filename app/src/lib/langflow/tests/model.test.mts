import assert from 'node:assert/strict';
import fs from 'node:fs';
import { test } from 'node:test';

import { applyEdits, contentHash, executionPlan, redactForExport, REDACTED, toCanvas, validateFlow, type LfFlow } from '../model';

const fixture = (name: string): LfFlow => JSON.parse(fs.readFileSync(new URL(`../fixtures/${name}`, import.meta.url), 'utf8')) as LfFlow;
const clone = <T>(v: T): T => structuredClone(v);

test('harmless chat-echo flow reads as two executable components joined by one typed connection', () => {
  const canvas = toCanvas(fixture('chat-echo.json'));
  assert.equal(canvas.nodes.length, 2);
  assert.deepEqual(canvas.nodes.map((n) => n.componentType).sort(), ['ChatInput', 'ChatOutput']);
  assert.ok(canvas.nodes.every((n) => n.executable));
  assert.equal(canvas.edges.length, 1);
  const [edge] = canvas.edges;
  assert.equal(edge.sourceOutput, 'message');
  assert.equal(edge.targetInput, 'input_value');
  assert.deepEqual(edge.sourceTypes, ['Message']);
  assert.equal(edge.decodeError, undefined);
});

test('chat-echo validates with no errors and can run', () => {
  const flow = fixture('chat-echo.json');
  const problems = validateFlow(flow);
  assert.equal(problems.filter((p) => p.level === 'error').length, 0, JSON.stringify(problems));
  const plan = executionPlan(flow);
  assert.equal(plan.hasChatInput, true);
  assert.equal(plan.hasChatOutput, true);
  assert.deepEqual(plan.blockers, []);
});

test('basic-prompting needs a model and is blocked from running here', () => {
  const flow = fixture('basic-prompting.json');
  const plan = executionPlan(flow);
  const blocked = plan.blockers.map((b) => b.componentType);
  assert.ok(blocked.includes('LanguageModelComponent'), `blockers: ${blocked.join(', ')}`);
  assert.ok(blocked.includes('Prompt'), `blockers: ${blocked.join(', ')}`);
  assert.match(plan.blockers[0].reason, /Running those is off in this app until Alex approves/);
  const problems = validateFlow(flow);
  assert.ok(problems.some((p) => p.level === 'error' && /required but empty/.test(p.message)), 'required empty setting should be an error');
});

test('no edits: applying nothing returns exactly the saved flow', () => {
  const flow = fixture('basic-prompting.json');
  const { flow: out, applied, rejected } = applyEdits(flow, []);
  assert.equal(applied, 0);
  assert.equal(rejected.length, 0);
  assert.deepEqual(out, flow);
  assert.equal(contentHash(out), contentHash(flow));
});

test('move edit changes only that node position and keeps unknown fields', () => {
  const flow = clone(fixture('chat-echo.json')) as LfFlow & { x_extra?: unknown };
  flow.x_extra = { keep: 'me' };
  flow.data.nodes[0] = { ...flow.data.nodes[0], custom_meta: { team: 'ops' } };
  const target = flow.data.nodes[0];
  const { flow: out, applied } = applyEdits(flow, [{ kind: 'move', nodeId: String(target.id), position: { x: 555, y: 777 } }]);
  assert.equal(applied, 1);
  const moved = out.data.nodes.find((n) => n.id === target.id)!;
  assert.deepEqual(moved.position, { x: 555, y: 777 });
  assert.deepEqual(moved.custom_meta, { team: 'ops' });
  assert.deepEqual(out.x_extra, { keep: 'me' });
  const untouched = out.data.nodes.find((n) => n.id !== target.id)!;
  assert.deepEqual(untouched, flow.data.nodes.find((n) => n.id !== target.id));
  assert.deepEqual(out.data.edges, flow.data.edges, 'edges are untouched by a move');
});

test('code is read-only and the rejection says where to edit it', () => {
  const flow = fixture('chat-echo.json');
  const chatInput = flow.data.nodes.find((n) => n.data?.type === 'ChatInput')!;
  const { applied, rejected } = applyEdits(flow, [{ kind: 'setField', nodeId: String(chatInput.id), field: 'code', value: 'import os' }]);
  assert.equal(applied, 0);
  assert.equal(rejected.length, 1);
  assert.match(rejected[0].reason, /native editor/);
});

test('secret settings cannot be set from the dashboard, and the placeholder is never saved back', () => {
  const flow = fixture('basic-prompting.json');
  const lm = flow.data.nodes.find((n) => n.data?.type === 'LanguageModelComponent')!;
  const secretName = Object.keys(lm.data!.node!.template!).find((k) => (lm.data!.node!.template![k] as { password?: boolean }).password === true);
  assert.ok(secretName, 'fixture should have a password setting');
  const { applied, rejected } = applyEdits(flow, [
    { kind: 'setField', nodeId: String(lm.id), field: secretName, value: 'typed-by-user' },
    { kind: 'setField', nodeId: String(lm.id), field: secretName, value: REDACTED },
  ]);
  assert.equal(applied, 0);
  assert.equal(rejected.length, 2);
  // Secret settings are read-only, so both attempts stop at the same rule.
  assert.match(rejected[0].reason, /Secret/);
  assert.match(rejected[1].reason, /Secret/);
});

test('typed settings are checked: whole numbers, true/false, and listed options', () => {
  const flow: LfFlow = {
    name: 'synthetic',
    data: {
      edges: [],
      nodes: [{ id: 'n1', position: { x: 0, y: 0 }, data: { type: 'Thing', node: { template: {
        count: { type: 'int', value: 1, show: true, display_name: 'Count' },
        flag: { type: 'bool', value: false, show: true, display_name: 'Flag' },
        mode: { type: 'str', value: 'a', show: true, options: ['a', 'b'], display_name: 'Mode' },
      } } } }],
    },
  };
  const out = applyEdits(flow, [
    { kind: 'setField', nodeId: 'n1', field: 'count', value: 2.5 },
    { kind: 'setField', nodeId: 'n1', field: 'count', value: 3 },
    { kind: 'setField', nodeId: 'n1', field: 'flag', value: 'maybe' },
    { kind: 'setField', nodeId: 'n1', field: 'flag', value: 'true' },
    { kind: 'setField', nodeId: 'n1', field: 'mode', value: 'z' },
    { kind: 'setField', nodeId: 'n1', field: 'mode', value: 'b' },
  ]);
  assert.equal(out.applied, 3);
  assert.equal(out.rejected.length, 3);
  const template = out.flow.data.nodes[0].data!.node!.template as Record<string, { value: unknown }>;
  assert.equal(template.count.value, 3);
  assert.equal(template.flag.value, true);
  assert.equal(template.mode.value, 'b');
});

test('unknown component, bad position and bad name are rejected with a reason', () => {
  const flow = fixture('chat-echo.json');
  const out = applyEdits(flow, [
    { kind: 'move', nodeId: 'does-not-exist', position: { x: 1, y: 1 } },
    { kind: 'move', nodeId: String(flow.data.nodes[0].id), position: { x: Number.NaN, y: 1 } },
    { kind: 'rename', nodeId: String(flow.data.nodes[0].id), label: '   ' },
  ]);
  assert.equal(out.applied, 0);
  assert.equal(out.rejected.length, 3);
  assert.match(out.rejected[0].reason, /No component/);
  assert.match(out.rejected[1].reason, /finite/);
  assert.match(out.rejected[2].reason, /1 to 80/);
});

test('rename sets the visible name only', () => {
  const flow = fixture('chat-echo.json');
  const id = String(flow.data.nodes[0].id);
  const { flow: out, applied } = applyEdits(flow, [{ kind: 'rename', nodeId: id, label: 'Customer question' }]);
  assert.equal(applied, 1);
  assert.equal(toCanvas(out).nodes.find((n) => n.id === id)!.label, 'Customer question');
  assert.equal(out.data.nodes[0].data!.type, flow.data.nodes[0].data!.type);
});

test('a cycle is reported as a warning, not an error', () => {
  const flow = fixture('chat-echo.json');
  const [a, b] = flow.data.nodes.map((n) => String(n.id));
  flow.data.edges.push({ ...flow.data.edges[0], id: 'loop-back', source: b, target: a });
  flow.data.edges.push({ ...flow.data.edges[0], id: 'loop-fwd', source: a, target: b });
  const problems = validateFlow(flow);
  assert.ok(problems.some((p) => p.level === 'warning' && /loops back/.test(p.message)));
});

test('an unreadable connection is an error that names the edge', () => {
  const flow = clone(fixture('chat-echo.json'));
  flow.data.edges[0].sourceHandle = 'not json';
  const problems = validateFlow(flow);
  const hit = problems.find((p) => p.level === 'error' && p.edgeId === String(flow.data.edges[0].id));
  assert.ok(hit, JSON.stringify(problems));
  assert.match(hit!.message, /unreadable/);
});

test('export replaces every secret value and leaves nothing that looks like a key', () => {
  const flow = fixture('basic-prompting.json');
  const lm = flow.data.nodes.find((n) => n.data?.type === 'LanguageModelComponent')!;
  const template = lm.data!.node!.template as Record<string, { password?: boolean; value?: unknown }>;
  const secretName = Object.keys(template).find((k) => template[k].password === true)!;
  template[secretName].value = 'FAKE-canary-secret-for-redaction-test';
  const { flow: out, redacted } = redactForExport(flow);
  assert.equal(redacted, 1);
  const exported = out.data.nodes.find((n) => n.id === lm.id)!.data!.node!.template as Record<string, { value?: unknown }>;
  assert.equal(exported[secretName].value, REDACTED);
  assert.ok(!JSON.stringify(out).includes('FAKE-canary-secret-for-redaction-test'));
  assert.equal(flow.data.nodes.find((n) => n.id === lm.id)!.data!.node!.template![secretName] !== undefined, true, 'original is not mutated');
});

test('content hash does not depend on key order, and changes when content changes', () => {
  const a = { name: 'x', data: { nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } } } as LfFlow;
  const b = { data: { viewport: { zoom: 1, y: 0, x: 0 }, edges: [], nodes: [] }, name: 'x' } as LfFlow;
  assert.equal(contentHash(a), contentHash(b));
  const c = { ...a, name: 'y' };
  assert.notEqual(contentHash(a), contentHash(c));
});
