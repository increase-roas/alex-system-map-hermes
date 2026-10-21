// Run: node tools/test_local_file_repair_source.cjs
// Execute the real component and effects with a small hook scheduler. No DOM,
// server, AI calls, or copied source-read implementation is involved.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const ts = require(process.env.LOCAL_REPAIR_TYPESCRIPT || '../app/node_modules/typescript');

const filename = path.resolve(__dirname, '../app/src/app/explorer/local-file-repair-panel.tsx');
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const tick = () => new Promise((resolve) => setImmediate(resolve));

function harness(overrides = {}) {
  let cursor = 0;
  const slots = [], effects = [], reads = [], writes = [];
  const hooks = {
    useState(initial) {
      const i = cursor++;
      if (!(i in slots)) slots[i] = initial;
      return [slots[i], (value) => { slots[i] = typeof value === 'function' ? value(slots[i]) : value; writes.push(i); }];
    },
    useRef(initial) { const i = cursor++; return slots[i] ??= { current: initial }; },
    useEffect(run, deps) {
      const i = cursor++;
      const previous = effects[i];
      if (!previous || deps.some((value, j) => !Object.is(value, previous.deps[j]))) {
        previous?.cleanup?.();
        effects[i] = { deps, run, pending: true };
      }
    },
  };
  const jsx = (type, props) => typeof type === 'function' ? type(props) : ({ type, props });
  const context = {
    exports: {}, AbortController, Error,
    require(name) {
      if (name === 'react') return hooks;
      if (name === 'react/jsx-runtime') return { jsx, jsxs: jsx, Fragment: 'fragment' };
      if (name === '@/components/ui/button') return { Button: 'button' };
      throw new Error(`Unexpected import: ${name}`);
    },
    fetch(url, options) {
      let resolve, reject;
      const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
      const read = { url, options, aborted: false, resolve: (data) => resolve({ ok: true, json: async () => data }), reject };
      options?.signal?.addEventListener('abort', () => {
        read.aborted = true;
        reject(new Error('transport aborted'));
      });
      reads.push(read);
      return promise;
    },
  };
  vm.runInNewContext(compiled, context, { filename });
  const props = { localToken: '', index: { references: [], files: [] }, finding: null, onOpenFile() {}, onClose() {}, onLockChange() {}, ...overrides };
  return {
    reads, writes,
    render(fileId = 'A') {
      cursor = 0;
      const tree = context.exports.LocalFileRepairPanel({ ...props, fileId });
      for (const effect of effects) if (effect?.pending) { effect.pending = false; effect.cleanup = effect.run(); }
      return tree;
    },
    unmount() { for (const effect of effects) effect?.cleanup?.(); },
  };
}
function visibleText(node) {
  if (node == null || typeof node === 'boolean') return '';
  if (Array.isArray(node)) return node.map(visibleText).join(' ');
  if (typeof node === 'object') return visibleText(node.props?.children);
  return String(node);
}
const source = (id) => ({ file_id: id, path: `/source/${id}`, content: `content ${id}`, editable: false, reason: `read ${id}`, source_file_ids: [] });

test('pending cleanup leaves source transport running and discards late success', async () => {
  const panel = harness();
  panel.render();
  panel.unmount();
  assert.equal(panel.reads[0].aborted, false, 'unmount must not reject the source transport');
  const before = panel.writes.length;
  panel.reads[0].resolve(source('A'));
  await tick();
  assert.equal(panel.writes.length, before, 'late source must not update an unmounted panel');
});

test('late read failures do not update an unmounted panel', async () => {
  const panel = harness();
  panel.render();
  panel.unmount();
  const before = panel.writes.length;
  panel.reads[0].reject(new Error('obsolete read failed'));
  await tick();
  assert.equal(panel.writes.length, before);
});

test('switching files ignores the previous read and displays the current source', async () => {
  const panel = harness();
  panel.render('A');
  panel.render('B');
  panel.reads[1].resolve(source('B'));
  await tick();
  panel.reads[0].resolve(source('A'));
  await tick();
  const text = visibleText(panel.render('B'));
  assert.match(text, /\/source\/B/);
  assert.doesNotMatch(text, /\/source\/A|Opening the current source/);
});

test('an obsolete failure cannot replace the current source with an error', async () => {
  const panel = harness();
  panel.render('A');
  panel.render('B');
  panel.reads[1].resolve(source('B'));
  await tick();
  panel.reads[0].reject(new Error('obsolete failure'));
  await tick();
  const text = visibleText(panel.render('B'));
  assert.match(text, /\/source\/B/);
  assert.doesNotMatch(text, /obsolete failure|Source repair request failed/);
});

test('a current source read failure remains visible', async () => {
  const panel = harness();
  panel.render();
  panel.reads[0].reject(new Error('source permission denied'));
  await tick();
  const text = visibleText(panel.render());
  assert.match(text, /Source repair request failed/);
  assert.match(text, /source permission denied/);
  assert.doesNotMatch(text, /Opening the current source/);
});

function nodes(node, predicate) {
  if (!node || typeof node !== 'object') return [];
  if (Array.isArray(node)) return node.flatMap((child) => nodes(child, predicate));
  return [...(predicate(node) ? [node] : []), ...nodes(node.props?.children, predicate)];
}
function button(tree, label) { return nodes(tree, (n) => n.type === 'button' && visibleText(n) === label)[0]; }
const checks = (status = 'passed') => ({ status, checked_at: 'today', model: 'native', limitations: ['Simulated choices only'], cases: [{ id: 'preserve', scenario: 'Keep protected scope', purpose: 'preserve', choices: { A: 'Keep scope', B: 'Expand scope', C: 'Ignore scope' }, expected: 'A', before: 'B', after: status === 'passed' ? 'A' : 'B', status, rationale: 'Keep the cited scope', evidence: [{ file_id: 'A', line: 2, quote: 'Protected scope' }] }] });
const preview = (status = 'passed') => ({ repair_id: 'repair', proposal_sha256: 'proposal', path: '/source/A', diff: '-old\n+new', before_sha256: 'old', after_sha256: 'new', checks: checks(status), distribution: { status: 'ready', targets: [{ path: '/copy/AGENTS.md', before_sha256: 'old', after_sha256: 'new', diff: '-copy old\n+copy new', kind: 'generated', requires_new_session: true }], limitations: ['Only dependent copies'] } });
async function proposed(status = 'passed') {
  const panel = harness({ localToken: 'test' });
  panel.render();
  panel.reads[0].resolve({ ...source('A'), editable: true, sha256: 'old' });
  await tick(); panel.render();
  panel.reads[1].resolve({ status: 'proposed', summary: 'Fix', rationale: 'Reason', conflicts: [], limitations: [], context_files: [{ file_id: 'A', path: '/source/A', sha256: 'old', applicability: { role: 'canonical', scope: 'project only', activation: 'when loaded', limitations: ['No blanket authority'] } }], model: 'native', generated_at: 'today', proposed_content: 'new text', checks: checks(status), preview: preview(status) });
  await tick();
  return panel;
}
test('checked preview shows scenarios, choices, outcomes, scope and affected-copy diff', async () => {
  const panel = await proposed();
  const tree = panel.render(); const text = visibleText(tree);
  for (const expected of ['Keep protected scope', 'Keep scope', 'Expand scope', 'Ignore scope', 'Before: B', 'After: A', 'Expected: A', 'project only', 'when loaded', 'No blanket authority', '/copy/AGENTS.md', '-copy old', 'Simulated choices only']) assert.ok(text.includes(expected), expected);
  assert.equal(button(tree, 'Approve proposed fix').props.disabled, false);
});
for (const status of ['failed', 'unavailable']) test(`${status} checks cannot offer an approvable AI proposal`, async () => {
  const panel = await proposed(status); const tree = panel.render();
  assert.ok(visibleText(tree).includes(status));
  assert.ok(!button(tree, 'Approve proposed fix') || button(tree, 'Approve proposed fix').props.disabled);
});
test('manual editing invalidates the checked preview and labels manual preview untested', async () => {
  const panel = await proposed();
  nodes(panel.render(), (n) => n.type === 'textarea')[0].props.onChange({ target: { value: 'manual text' } });
  let tree = panel.render();
  assert.equal(button(tree, 'Approve proposed fix'), undefined);
  button(tree, 'Preview exact change').props.onClick();
  panel.reads[2].resolve({ ...preview(), checks: null }); await tick(); tree = panel.render();
  assert.match(visibleText(tree), /Manual draft.*not.*AI/i);
});
for (const [distribution, pushed, verified] of [['verified', true, true], ['not_needed', true, true], ['pending', true, false], ['verified', false, false], [undefined, true, false]]) {
  test(`result ${distribution}/${pushed} reports truthful verification`, async () => {
    const panel = await proposed(); button(panel.render(), 'Approve proposed fix').props.onClick();
    panel.reads[2].resolve({ repair_id: 'repair', state: 'applied', path: '/source/A', current_sha256: 'new', source_verified: true, pushed, generated_follow_up: distribution === 'pending', message: 'Recorded', distribution: distribution && { status: distribution, targets: [{ path: '/copy/AGENTS.md', status: distribution, sha256: 'new', reason: 'Readback checked' }], message: 'Copy readback' } });
    await tick(); const text = visibleText(panel.render());
    assert.equal(text.includes('Repair verified'), verified);
    assert.match(text, /already-running|running agent/);
    if (distribution) { assert.match(text, /Readback checked/); assert.match(text, /Copy readback/); }
  });
}

test('Undo displays restored source and each copy readback without claiming active adoption', async () => {
  const panel = await proposed(); button(panel.render(), 'Approve proposed fix').props.onClick();
  panel.reads[2].resolve({ repair_id: 'repair', state: 'applied', path: '/source/A', source_verified: true, pushed: true, distribution: { status: 'verified', targets: [], message: 'Copies checked' } });
  await tick(); button(panel.render(), 'Undo this source change').props.onClick();
  panel.reads[3].resolve({ repair_id: 'repair', state: 'undone', path: '/source/A', source_verified: true, pushed: true, current_sha256: 'old', distribution: { status: 'verified', targets: [{ path: '/copy/AGENTS.md', status: 'verified', sha256: 'old', reason: 'Exact preimage restored' }], message: 'Restored copies checked' } });
  await tick(); const tree = panel.render(); const text = visibleText(tree);
  assert.match(text, /Undo verified/); assert.match(text, /Exact preimage restored/); assert.match(text, /already-running agent/);
  assert.equal(button(tree, 'Undo this source change'), undefined);
});

for (const sourceVerified of [false, undefined]) test(`source readback ${sourceVerified} cannot claim verified`, async () => {
  const panel = await proposed(); button(panel.render(), 'Approve proposed fix').props.onClick();
  panel.reads[2].resolve({ repair_id: 'repair', state: 'applied', path: '/source/A', current_sha256: 'new', source_verified: sourceVerified, pushed: true, generated_follow_up: false, message: 'Published', distribution: { status: 'verified', targets: [], message: 'Copies checked' } });
  await tick(); const text = visibleText(panel.render());
  assert.doesNotMatch(text, /Repair verified/);
  assert.match(text, /follow-up pending/);
  assert.match(text, /Source readback/);
});

test('repair adapter preserves actionable 422 preview validation responses', async () => {
  const { EventEmitter } = require('node:events');
  const adapterPath = path.resolve(__dirname, '../app/src/lib/server/local-file-repairs.ts');
  const adapter = ts.transpileModule(fs.readFileSync(adapterPath, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  const expected = { status: 422, code: 'native_projection_failed', error: 'Generated output exceeds the 64 KiB byte ceiling; shorten this rule source.' };
  const context = {
    exports: {}, process, Buffer, setTimeout, clearTimeout,
    require(name) {
      if (name === 'node:path') return { default: path };
      if (name === './local-files') return { localFileIndex: async () => ({}) };
      if (name === './paths') return { ensureLocalDataDir() {}, foundationRoot: () => '/fixture', localDataDir: () => '/fixture/state' };
      if (name === 'node:child_process') return { spawn() {
        const child = new EventEmitter(); child.stdout = new EventEmitter(); child.stdin = new EventEmitter(); child.kill = () => {};
        child.stdin.end = () => { child.stdout.emit('data', Buffer.from(JSON.stringify(expected))); child.emit('close', 0); };
        return child;
      } };
      throw new Error(`Unexpected adapter import: ${name}`);
    },
  };
  vm.runInNewContext(adapter, context, { filename: adapterPath });
  const result = await context.exports.runLocalFileRepair({ action: 'preview', file_id: 'A', expected_sha256: 'old', new_content: 'candidate' });
  assert.deepEqual(JSON.parse(JSON.stringify(result)), expected);
});
