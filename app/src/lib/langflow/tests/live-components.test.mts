// LIVE: every component enabled for local runs (tiers.ts EXECUTABLE_COMPONENTS) produces its real output on
// the real engine. Each flow is built only through the dashboard's own save route (addNode, connect,
// setField) and run through the run route, so this also proves the handles, settings and run gate.
// Skipped unless enabled:
//   LANGFLOW_LIVE_ENGINE=1 LANGFLOW_LFX_BIN=<lfx> LANGFLOW_CONFIG_DIR=<dir> \
//     node --import ./src/lib/langflow/tests/register.mjs --test src/lib/langflow/tests/live-components.test.mts
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';

import { getOrCreateLocalToken } from '../../server/local-auth';
import * as flowsRoute from '../../../app/api/langflow/flows/route';
import * as flowRoute from '../../../app/api/langflow/flows/[flowId]/route';
import * as runsRoute from '../../../app/api/langflow/flows/[flowId]/runs/route';
import { EXECUTABLE_COMPONENTS, LOCAL_NOT_ENABLED } from '../tiers';

const enabled = process.env.LANGFLOW_LIVE_ENGINE === '1' && !!process.env.LANGFLOW_LFX_BIN;
const tmp = fs.mkdtempSync(path.join(process.env.TMPDIR ?? os.tmpdir(), 'lf-live-components-'));
const SESSION = 'live-components-0001';
const YEAR = String(new Date().getUTCFullYear());

type Edit = Record<string, unknown>;
/** expect: text the output must contain; a RegExp when the output is random (Mock Data). */
type Case = { component: string; edits: (id: (t: string, n?: number) => string) => Edit[]; input: string; expect: string | RegExp };

const headers = (extra: Record<string, string> = {}) => new Headers({ host: '127.0.0.1:3200', 'x-local-token': getOrCreateLocalToken(), 'content-type': 'application/json', ...extra });
const add = (type: string, nodeId: string, x = 0): Edit => ({ kind: 'addNode', nodeId, componentType: type, position: { x, y: 0 } });
const wire = (from: string, out: string, to: string, input: string, targetLoop = false): Edit => ({ kind: 'connect', nodeId: from, sourceOutput: out, target: to, targetInput: input, ...(targetLoop ? { targetLoop: true } : {}) });
const set = (nodeId: string, field: string, value: unknown): Edit => ({ kind: 'setField', nodeId, field, value });

const SPLIT_INPUT = 'alpha beta gamma delta epsilon zeta';
function splitter(type: string, extra: Edit[] = []): Case {
  return {
    component: type,
    input: SPLIT_INPUT,
    expect: 'epsilon',
    edits: (id) => [
      add('ChatInput', id('ChatInput')), add('TypeConverterComponent', id('TypeConverterComponent'), 300), add(type, id(type), 600), add('ChatOutput', id('ChatOutput'), 900),
      set(id('TypeConverterComponent'), 'output_type', 'JSON'), set(id(type), 'chunk_size', 10), set(id(type), 'chunk_overlap', 0), ...extra,
      wire(id('ChatInput'), 'message', id('TypeConverterComponent'), 'input_data'),
      wire(id('TypeConverterComponent'), 'data_output', id(type), 'data_input'),
      wire(id(type), 'data', id('ChatOutput'), 'input_value'),
    ],
  };
}

const CASES: Case[] = [
  { component: 'ChatInput', input: 'chat echo through the route', expect: 'chat echo through the route', edits: (id) => [add('ChatInput', id('ChatInput')), add('ChatOutput', id('ChatOutput'), 300), wire(id('ChatInput'), 'message', id('ChatOutput'), 'input_value')] },
  { component: 'ChatOutput', input: 'chat output receives it', expect: 'chat output receives it', edits: (id) => [add('ChatInput', id('ChatInput')), add('ChatOutput', id('ChatOutput'), 300), wire(id('ChatInput'), 'message', id('ChatOutput'), 'input_value')] },
  { component: 'CalculatorComponent', input: '2*(3+4)', expect: '14', edits: (id) => [add('ChatInput', id('ChatInput')), add('CalculatorComponent', id('CalculatorComponent'), 300), add('ChatOutput', id('ChatOutput'), 600), wire(id('ChatInput'), 'message', id('CalculatorComponent'), 'expression'), wire(id('CalculatorComponent'), 'result', id('ChatOutput'), 'input_value')] },
  { component: 'CurrentDate', input: 'unused', expect: YEAR, edits: (id) => [add('CurrentDate', id('CurrentDate')), add('ChatOutput', id('ChatOutput'), 300), wire(id('CurrentDate'), 'current_date', id('ChatOutput'), 'input_value')] },
  { component: 'MockDataGenerator', input: 'unused', expect: /^[A-Za-z][A-Za-z ,.]{39,}/, edits: (id) => [add('MockDataGenerator', id('MockDataGenerator')), add('ChatOutput', id('ChatOutput'), 300), wire(id('MockDataGenerator'), 'message_output', id('ChatOutput'), 'input_value')] },
  {
    component: 'ConditionalRouter', input: 'yes', expect: 'ROUTE-TRUE',
    edits: (id) => [
      add('ChatInput', id('ChatInput')), add('ConditionalRouter', id('ConditionalRouter'), 300), add('ChatOutput', id('ChatOutput'), 600),
      set(id('ConditionalRouter'), 'match_text', 'yes'), set(id('ConditionalRouter'), 'true_case_message', 'ROUTE-TRUE'), set(id('ConditionalRouter'), 'false_case_message', 'ROUTE-FALSE'),
      wire(id('ChatInput'), 'message', id('ConditionalRouter'), 'input_text'), wire(id('ConditionalRouter'), 'true_result', id('ChatOutput'), 'input_value'),
    ],
  },
  {
    component: 'Notify', input: 'notify-payload', expect: 'notify-payload',
    edits: (id) => [add('ChatInput', id('ChatInput')), add('Notify', id('Notify'), 300), add('ChatOutput', id('ChatOutput'), 600), set(id('Notify'), 'context_key', 'k1'), wire(id('ChatInput'), 'message', id('Notify'), 'input_value'), wire(id('Notify'), 'result', id('ChatOutput'), 'input_value')],
  },
  {
    component: 'Listen', input: 'listen-payload', expect: 'listen-payload',
    edits: (id) => [
      add('ChatInput', id('ChatInput')), add('Notify', id('Notify'), 300), add('Listen', id('Listen'), 600), add('ChatOutput', id('ChatOutput'), 900),
      set(id('Notify'), 'context_key', 'k1'), set(id('Listen'), 'context_key', 'k1'),
      wire(id('ChatInput'), 'message', id('Notify'), 'input_value'), wire(id('Listen'), 'data', id('ChatOutput'), 'input_value'),
    ],
  },
  {
    component: 'LoopComponent', input: 'loop-item', expect: 'loop-item',
    edits: (id) => [
      add('ChatInput', id('ChatInput')), add('TypeConverterComponent', id('TypeConverterComponent', 1), 300), add('LoopComponent', id('LoopComponent'), 600),
      add('TypeConverterComponent', id('TypeConverterComponent', 2), 900), add('ChatOutput', id('ChatOutput'), 1200),
      set(id('TypeConverterComponent', 1), 'output_type', 'Table'), set(id('TypeConverterComponent', 2), 'output_type', 'JSON'),
      wire(id('ChatInput'), 'message', id('TypeConverterComponent', 1), 'input_data'),
      wire(id('TypeConverterComponent', 1), 'dataframe_output', id('LoopComponent'), 'data'),
      wire(id('LoopComponent'), 'item', id('TypeConverterComponent', 2), 'input_data'),
      wire(id('TypeConverterComponent', 2), 'data_output', id('LoopComponent'), 'item', true),
      wire(id('LoopComponent'), 'done', id('ChatOutput'), 'input_value'),
    ],
  },
  splitter('CharacterTextSplitter', [{ kind: 'setField', nodeId: '', field: 'separator', value: ' ' }]),
  splitter('RecursiveCharacterTextSplitter'),
  splitter('LanguageRecursiveTextSplitter'),
  {
    component: 'HtmlLinkExtractor', input: JSON.stringify({ text: '<a href="/page">x</a>', source: 'https://example.com/' }), expect: 'https://example.com/page',
    edits: (id) => [
      add('ChatInput', id('ChatInput')), add('TypeConverterComponent', id('TypeConverterComponent'), 300), add('HtmlLinkExtractor', id('HtmlLinkExtractor'), 600), add('ChatOutput', id('ChatOutput'), 900),
      set(id('TypeConverterComponent'), 'output_type', 'JSON'), set(id('TypeConverterComponent'), 'auto_parse', true),
      wire(id('ChatInput'), 'message', id('TypeConverterComponent'), 'input_data'),
      wire(id('TypeConverterComponent'), 'data_output', id('HtmlLinkExtractor'), 'data_input'),
      wire(id('HtmlLinkExtractor'), 'data', id('ChatOutput'), 'input_value'),
    ],
  },
  {
    component: 'Prompt Template', input: 'prompt-var-ok', expect: 'Say: prompt-var-ok',
    edits: (id) => [
      add('ChatInput', id('ChatInput')), add('Prompt Template', id('Prompt Template'), 300), add('ChatOutput', id('ChatOutput'), 600),
      set(id('Prompt Template'), 'template', 'Say: {topic}'),
      wire(id('ChatInput'), 'message', id('Prompt Template'), 'topic'), wire(id('Prompt Template'), 'prompt', id('ChatOutput'), 'input_value'),
    ],
  },
  {
    component: 'DynamicCreateData', input: 'unused', expect: '"city"',
    edits: (id) => [add('DynamicCreateData', id('DynamicCreateData')), add('ChatOutput', id('ChatOutput'), 300), set(id('DynamicCreateData'), 'form_fields', [{ field_name: 'city', field_type: 'Text' }]), wire(id('DynamicCreateData'), 'form_data', id('ChatOutput'), 'input_value')],
  },
  {
    component: 'ParserComponent', input: 'parser-input', expect: 'Parsed: parser-input',
    edits: (id) => [
      add('ChatInput', id('ChatInput')), add('TypeConverterComponent', id('TypeConverterComponent'), 300), add('ParserComponent', id('ParserComponent'), 600), add('ChatOutput', id('ChatOutput'), 900),
      set(id('TypeConverterComponent'), 'output_type', 'JSON'), set(id('ParserComponent'), 'pattern', 'Parsed: {text}'),
      wire(id('ChatInput'), 'message', id('TypeConverterComponent'), 'input_data'),
      wire(id('TypeConverterComponent'), 'data_output', id('ParserComponent'), 'input_data'),
      wire(id('ParserComponent'), 'parsed_text', id('ChatOutput'), 'input_value'),
    ],
  },
  {
    component: 'SplitText', input: SPLIT_INPUT, expect: 'epsilon',
    edits: (id) => [
      add('ChatInput', id('ChatInput')), add('SplitText', id('SplitText'), 300), add('ChatOutput', id('ChatOutput'), 600),
      set(id('SplitText'), 'chunk_size', 10), set(id('SplitText'), 'chunk_overlap', 0), set(id('SplitText'), 'separator', ' '),
      wire(id('ChatInput'), 'message', id('SplitText'), 'data_inputs'), wire(id('SplitText'), 'dataframe', id('ChatOutput'), 'input_value'),
    ],
  },
  {
    component: 'TypeConverterComponent', input: 'convert-me', expect: '"text": "convert-me"',
    edits: (id) => [add('ChatInput', id('ChatInput')), add('TypeConverterComponent', id('TypeConverterComponent'), 300), add('ChatOutput', id('ChatOutput'), 600), set(id('TypeConverterComponent'), 'output_type', 'JSON'), wire(id('ChatInput'), 'message', id('TypeConverterComponent'), 'input_data'), wire(id('TypeConverterComponent'), 'data_output', id('ChatOutput'), 'input_value')],
  },
];

function ids(): (t: string, n?: number) => string {
  const made = new Map<string, string>();
  return (t, n = 0) => {
    const key = `${t}#${n}`;
    if (!made.has(key)) made.set(key, `${t}-${randomUUID().replace(/-/g, '').slice(0, 5)}`);
    return made.get(key)!;
  };
}

async function buildAndRun(c: Case): Promise<{ status: string; output: string | null; error: string | null; engine: string; seconds: number }> {
  const made = await flowsRoute.POST(new Request('http://127.0.0.1:3200/api/langflow/flows', { method: 'POST', headers: headers(), body: JSON.stringify({ id: randomUUID(), name: `live ${c.component}`, description: '', data: { nodes: [], edges: [] } }) }));
  assert.equal(made.status, 201);
  const { id, hash } = (await made.json()) as { id: string; hash: string };
  const nid = ids();
  const edits = c.edits(nid).map((e) => (e.kind === 'setField' && e.nodeId === '' ? { ...e, nodeId: nid(c.component) } : e));
  const saved = await flowRoute.PATCH(new Request(`http://127.0.0.1:3200/api/langflow/flows/${id}`, { method: 'PATCH', headers: headers(), body: JSON.stringify({ expectedHash: hash, edits }) }), { params: Promise.resolve({ flowId: id }) });
  const savedBody = (await saved.json()) as Record<string, unknown>;
  assert.equal(saved.status, 200, `${c.component}: save ${JSON.stringify(savedBody).slice(0, 400)}`);
  const started = await runsRoute.POST(new Request(`http://127.0.0.1:3200/api/langflow/flows/${id}/runs`, {
    method: 'POST', headers: headers({ 'x-browser-session': SESSION, 'idempotency-key': `live-${randomUUID()}` }), body: JSON.stringify({ input: c.input }),
  }), { params: Promise.resolve({ flowId: id }) });
  const startedBody = (await started.json()) as { run?: { id: string }; error?: string; blockers?: unknown };
  assert.equal(started.status, 202, `${c.component}: run refused ${JSON.stringify(startedBody).slice(0, 400)}`);
  const runId = startedBody.run!.id;
  const deadline = Date.now() + 170_000;
  while (Date.now() < deadline) {
    const list = await runsRoute.GET(new Request(`http://127.0.0.1:3200/api/langflow/flows/${id}/runs`, { headers: headers({ 'x-browser-session': SESSION }) }), { params: Promise.resolve({ flowId: id }) });
    const run = ((await list.json()) as { runs: Array<Record<string, unknown>> }).runs.find((r) => r.id === runId);
    if (run && run.status !== 'running') {
      return {
        status: String(run.status), output: (run.output as string | null) ?? null, error: (run.error as string | null) ?? null, engine: String(run.engineVersion),
        seconds: Math.round((Date.parse(String(run.finishedAt)) - Date.parse(String(run.startedAt))) / 1000),
      };
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  return { status: 'timeout', output: null, error: 'no result before the deadline', engine: '?', seconds: 170 };
}

test('LIVE: every enabled local component returns its real output on the real engine', { skip: !enabled && 'set LANGFLOW_LIVE_ENGINE=1 and LANGFLOW_LFX_BIN to run', timeout: 3_600_000 }, async () => {
  process.env.LOCAL_DATA_DIR = tmp;
  assert.deepEqual([...new Set(CASES.map((c) => c.component))].sort(), [...EXECUTABLE_COMPONENTS].sort(), 'one live case per enabled component');
  const failures: string[] = [];
  for (const c of CASES) {
    const r = await buildAndRun(c);
    const ok = r.status === 'succeeded' && (typeof c.expect === 'string' ? (r.output ?? '').includes(c.expect) : c.expect.test(r.output ?? ''));
    const shown = (r.output ?? r.error ?? '').replace(/\s+/g, ' ').slice(0, 160);
    console.log(`${ok ? 'PASS' : 'FAIL'} ${c.component}: ${r.status} in ${r.seconds}s on ${r.engine}; expected ${typeof c.expect === 'string' ? `to contain ${JSON.stringify(c.expect)}` : `to match ${String(c.expect)}`}; output: ${shown}`);
    if (!ok) failures.push(c.component);
  }
  console.log(`SUMMARY ${CASES.length - failures.length}/${CASES.length} enabled components produced their real output`);
  assert.deepEqual(failures, []);
});

test('LIVE: local components that are not enabled are refused by the run route with their reason', { skip: !enabled && 'set LANGFLOW_LIVE_ENGINE=1 and LANGFLOW_LFX_BIN to run', timeout: 600_000 }, async () => {
  process.env.LOCAL_DATA_DIR = tmp;
  for (const type of Object.keys(LOCAL_NOT_ENABLED)) {
    const made = await flowsRoute.POST(new Request('http://127.0.0.1:3200/api/langflow/flows', { method: 'POST', headers: headers(), body: JSON.stringify({ id: randomUUID(), name: `off ${type}`, data: { nodes: [], edges: [] } }) }));
    const { id, hash } = (await made.json()) as { id: string; hash: string };
    const nid = ids();
    const saved = await flowRoute.PATCH(new Request(`http://127.0.0.1:3200/api/langflow/flows/${id}`, { method: 'PATCH', headers: headers(), body: JSON.stringify({ expectedHash: hash, edits: [add(type, nid(type)), add('ChatOutput', nid('ChatOutput'), 300)] }) }), { params: Promise.resolve({ flowId: id }) });
    assert.equal(saved.status, 200);
    const started = await runsRoute.POST(new Request(`http://127.0.0.1:3200/api/langflow/flows/${id}/runs`, {
      method: 'POST', headers: headers({ 'x-browser-session': SESSION, 'idempotency-key': `off-${randomUUID()}` }), body: JSON.stringify({ input: 'x' }),
    }), { params: Promise.resolve({ flowId: id }) });
    assert.equal(started.status, 422, `${type} must not start`);
    const detail = await flowRoute.GET(new Request(`http://127.0.0.1:3200/api/langflow/flows/${id}`, { headers: headers() }), { params: Promise.resolve({ flowId: id }) });
    const plan = ((await detail.json()) as { plan: { blockers: Array<{ componentType: string; reason: string }> }; runnable: boolean });
    const blocker = plan.plan.blockers.find((b) => b.componentType === type);
    console.log(`REFUSED ${type}: run HTTP ${started.status}; plan says: ${blocker?.reason}`);
    assert.match(blocker!.reason, /is local but not enabled/);
  }
});
