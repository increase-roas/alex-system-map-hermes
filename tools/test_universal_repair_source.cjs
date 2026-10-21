const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const ts = require(process.env.LOCAL_REPAIR_TYPESCRIPT || '../app/node_modules/typescript');
const filename = path.resolve(__dirname, '../app/src/app/explorer/repair-targets-panel.tsx');
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { target: ts.ScriptTarget.ES2017, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
const tick = () => new Promise(resolve => setImmediate(resolve));
function harness(saved = null) {
  let cursor = 0; const slots = [], effects = [], reads = [], storage = new Map(saved ? [['universal-repair-job', saved]] : []);
  const hooks = { useState(initial) { const i = cursor++; if (!(i in slots)) slots[i] = typeof initial === 'function' ? initial() : initial; return [slots[i], value => { slots[i] = typeof value === 'function' ? value(slots[i]) : value; }]; }, useRef(initial) { const i = cursor++; return slots[i] ??= { current: initial }; }, useEffect(run, deps) { const i = cursor++; const old = effects[i]; if (!old || deps.some((v,j) => !Object.is(v, old.deps[j]))) { old?.cleanup?.(); effects[i] = { run, deps, pending: true }; } } };
  const jsx = (type, props) => typeof type === 'function' ? type(props) : { type, props };
  const context = { exports: {}, AbortController, Error, Date, JSON, Set, setTimeout: () => 1, clearTimeout() {}, window: { localStorage: { getItem: k => storage.get(k) ?? null, setItem: (k,v) => storage.set(k,v), removeItem: k => storage.delete(k) } }, require(name) { if (name === 'react') return hooks; if (name === 'react/jsx-runtime') return { jsx, jsxs: jsx, Fragment: 'fragment' }; if (name === '@/components/ui/button') return { Button: 'button' }; throw Error(name); }, fetch(url, options) { return new Promise((resolve,reject) => { reads.push({ url, options, resolve: (body, status = 200) => resolve({ ok: status < 400, status, json: async () => body }), reject }); options.signal?.addEventListener('abort', () => reject(Object.assign(Error('aborted'), { name: 'AbortError' }))); }); } };
  vm.runInNewContext(compiled, context, { filename });
  return { reads, storage, render(props = {}) { cursor = 0; const tree = context.exports.RepairTargetsPanel({ localToken: 'token', ...props }); for (const e of effects) if (e?.pending) { e.pending = false; e.cleanup = e.run(); } return tree; }, unmount() { for (const e of effects) e?.cleanup?.(); } };
}
function nodes(n, predicate) { if (!n || typeof n !== 'object') return []; if (Array.isArray(n)) return n.flatMap(x => nodes(x,predicate)); return [...(predicate(n) ? [n] : []), ...nodes(n.props?.children,predicate)]; }
function text(n) { if (n == null || typeof n === 'boolean') return ''; if (Array.isArray(n)) return n.map(text).join(' '); return typeof n === 'object' ? text(n.props?.children) : String(n); }
const button = (tree, name) => nodes(tree,n => n.type === 'button' && text(n) === name)[0];
const target = { id: 'skill:one', adapter_id: 'skills', category: 'skill', owner: 'Skill owner', scope: 'remote', identity: { object_id: 'actual-object' }, capabilities: ['propose','apply','undo'], observed_at: '2026-10-21T10:00:00Z', evidence: ['readback:1'], limitations: ['Runtime discovery separate'] };
const check = { kind: 'simulated_behavior', status: 'passed', runner_id: 'model', evidence: ['case:1'], limitations: ['Simulation only'] };
const plan = { schema_version: 1, plan_id: 'plan-one', digest: 'digest-one', created_at: 'today', expires_at: '2099-01-01', intent: 'fix', targets: [target], operations: [{ step_id: 'step-one', target_id: target.id, adapter_id: 'skills', adapter_version: '1', action: 'patch', public_diff: '-old\n+new', checks: [check] }], checks: [check], limitations: [] };
async function proposed() { const h = harness(); h.render(); h.reads[0].resolve({ schema_version: 1, targets: [target], limitations: ['Bounded registry'] }); await tick(); let tree = h.render(); nodes(tree,n => n.type === 'input' && n.props.type === 'checkbox')[0].props.onChange(); tree = h.render(); nodes(tree,n => n.type === 'textarea')[0].props.onChange({ target: { value: 'fix' } }); button(h.render(), 'Review & fix').props.onClick(); h.reads[1].resolve(plan); await tick(); return h; }
test('registered objects, evidence and immutable proposal appear before one ID-only approval', async () => { const h = await proposed(); let tree = h.render(); for (const value of ['actual-object','Simulation only','-old','+new','simulated behavior','Runtime discovery separate']) assert.ok(text(tree).includes(value), value); button(tree,'Approve tested bundle').props.onClick(); button(tree,'Approve tested bundle').props.onClick(); assert.equal(h.reads.length,3); const request = JSON.parse(h.reads[2].options.body); assert.deepEqual(request,{ action:'apply', plan_id:'plan-one', digest:'digest-one' }); assert.equal(h.reads[0].options.headers['X-Local-Token'],'token'); });
test('changing intent invalidates the displayed frozen proposal', async () => { const h = await proposed(); nodes(h.render(),n => n.type === 'textarea')[0].props.onChange({target:{value:'different'}}); assert.equal(button(h.render(),'Approve tested bundle'),undefined); });
test('restored durable job shows pending receipt and never says all targets verified', async () => { const h = harness('job-one'); h.render(); h.render(); const read = h.reads.find(r => r.url.endsWith('/jobs/job-one')); assert.ok(read); read.resolve({ schema_version:1, job_id:'job-one', plan_id:'plan-one', digest:'digest-one', status:'completed', steps:[{step_id:'s',target_id:target.id,phase:'done', receipt:{ok:false,state:'pending',evidence:['timeout'],checks:[],limitations:['publication pending']}}],events:[],unknown_effect:null,updated_at:'today' }); await tick(); const tree = h.render(); assert.match(text(tree),/pending/); assert.doesNotMatch(text(tree),/All targets verified/); });
test('unmount catches expected aborts without surfacing an error', async () => { const h = harness(); h.render(); h.unmount(); await tick(); });
test('opening current source invalidates a previous tested proposal', async () => { const h = await proposed(); button(h.render(),'Read current source').props.onClick(); assert.equal(button(h.render(),'Approve tested bundle'),undefined); });
test('no checks cannot be presented as an approvable tested bundle', async () => { const h = harness(); h.render(); h.reads[0].resolve({schema_version:1,targets:[target],limitations:[]}); await tick(); nodes(h.render(),n => n.type === 'input' && n.props.type === 'checkbox')[0].props.onChange(); nodes(h.render(),n => n.type === 'textarea')[0].props.onChange({target:{value:'fix'}}); button(h.render(),'Review & fix').props.onClick(); h.reads[1].resolve({...plan,checks:[],operations:[{...plan.operations[0],checks:[]}]}); await tick(); assert.equal(button(h.render(),'Approve tested bundle').props.disabled,true); });
test('a late proposal cannot replace a requested different source', async () => { const h = harness(); h.render(); h.reads[0].resolve({schema_version:1,targets:[target],limitations:[]}); await tick(); nodes(h.render(),n => n.type === 'input' && n.props.type === 'checkbox')[0].props.onChange(); nodes(h.render(),n => n.type === 'textarea')[0].props.onChange({target:{value:'fix'}}); button(h.render(),'Review & fix').props.onClick(); h.render({ requestedSource:{ fileId:'other',path:'/other',nonce:1 } }); h.reads[1].resolve(plan); await tick(); assert.equal(button(h.render({requestedSource:{fileId:'other',path:'/other',nonce:1}}),'Approve tested bundle'),undefined); });
test('applied job stores only its durable ID and shows each receipt', async () => { const h = await proposed(); button(h.render(),'Approve tested bundle').props.onClick(); h.reads[2].resolve({schema_version:1,job_id:'saved-job',plan_id:'plan-one',digest:'digest-one',status:'completed',steps:[{step_id:'s',target_id:target.id,phase:'written',receipt:{ok:true,state:'byte_verified',evidence:['source bytes read'],checks:[check],limitations:['runtime not checked']}}],events:[],unknown_effect:null,updated_at:'today'}); await tick(); const tree = h.render(); assert.deepEqual([...h.storage.entries()],[['universal-repair-job','saved-job']]); assert.match(text(tree),/runtime not checked/); assert.doesNotMatch(text(tree),/All targets verified/); assert.ok(button(tree,'Undo reviewed bundle')); });
test('uncertain effect offers reconciliation and no resume or undo', async () => { const h = harness('uncertain-job'); h.render(); h.render(); h.reads.find(r => r.url.endsWith('/jobs/uncertain-job')).resolve({schema_version:1,job_id:'uncertain-job',plan_id:'plan-one',digest:'digest-one',status:'unknown',steps:[{step_id:'s',target_id:target.id,phase:'write',receipt:{ok:false,state:'unknown',evidence:[],checks:[],limitations:[]}}],events:[],unknown_effect:'remote timeout',updated_at:'today'}); await tick(); const tree = h.render(); assert.ok(button(tree,'Reconcile current state')); assert.equal(button(tree,'Resume recorded job'),undefined); assert.equal(button(tree,'Undo reviewed bundle'),undefined); button(tree,'Reconcile current state').props.onClick(); const request = h.reads.at(-1); assert.equal(request.url,'/api/repairs/jobs/uncertain-job'); assert.deepEqual(JSON.parse(request.options.body),{action:'reconcile'}); });

test('lost approval response recovers original job after close and reopen without another apply', async () => {
  const h = await proposed(); button(h.render(),'Approve tested bundle').props.onClick();
  assert.deepEqual([...h.storage.entries()],[['universal-repair-job','plan-one']], 'record recovery ID before server effect and response');
  assert.equal(h.reads[2].options.keepalive,true);
  // The fixture server accepted and performed this one request, but its response is lost.
  h.reads[2].reject(new Error('response lost after server effect')); await tick(); h.unmount();
  const reopened = harness(h.storage.get('universal-repair-job')); reopened.render(); reopened.render();
  const lookup = reopened.reads.find(r => r.url === '/api/repairs/jobs/plan-one'); assert.ok(lookup);
  lookup.resolve({schema_version:1,job_id:'plan-one',plan_id:'plan-one',digest:'digest-one',status:'completed',steps:[],events:[],unknown_effect:null,updated_at:'today'});
  await tick(); assert.match(text(reopened.render()),/plan-one/);
  assert.equal(reopened.reads.filter(r => r.options.method === 'POST').length,0,'reopening must not create a second effect');
});
test('transient missing job keeps recovery ID and visibly waits for original job', async () => {
  const h = harness('plan-one'); h.render(); h.render();
  h.reads.find(r => r.url === '/api/repairs/jobs/plan-one').resolve({error:'not yet visible'},404); await tick();
  assert.equal(h.storage.get('universal-repair-job'),'plan-one');
  assert.match(text(h.render()),/Waiting for.*original job|Original job lookup pending/);
  assert.equal(h.reads.filter(r => r.options.method === 'POST').length,0);
});
for (const code of ['plan_expired', 'checks_not_passed']) test(`definitive pre-job ${code} rejection permits fresh proposal`, async () => {
  const h = await proposed(); button(h.render(),'Approve tested bundle').props.onClick();
  assert.equal(h.storage.get('universal-repair-job'),'plan-one');
  h.reads[2].resolve({code,error:'Repair operation unavailable; inspect the recorded safe status.'},409); await tick();
  const tree = h.render(); assert.equal(h.storage.has('universal-repair-job'),false);
  assert.doesNotMatch(text(tree),/Original job lookup pending/);
  assert.match(text(tree),/No job was created/);
  assert.equal(button(tree,'Review & fix').props.disabled,false);
});
test('ambiguous approval rejection retains original recovery ID', async () => {
  const h = await proposed(); button(h.render(),'Approve tested bundle').props.onClick();
  h.reads[2].resolve({code:'record_unavailable',error:'Operation unavailable'},409); await tick();
  assert.equal(h.storage.get('universal-repair-job'),'plan-one');
  assert.match(text(h.render()),/Original job lookup pending/);
});
