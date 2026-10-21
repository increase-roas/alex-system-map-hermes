// Run: node tools/test_local_file_repair_source.cjs
// Execute the real component and effects with a small hook scheduler. No DOM,
// server, AI calls, or copied source-read implementation is involved.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const ts = require('../app/node_modules/typescript');

const filename = path.resolve(__dirname, '../app/src/app/explorer/local-file-repair-panel.tsx');
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const tick = () => new Promise((resolve) => setImmediate(resolve));

function harness() {
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
  const jsx = (type, props) => ({ type, props });
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
  const props = { localToken: '', index: { references: [], files: [] }, finding: null, onOpenFile() {}, onClose() {}, onLockChange() {} };
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
