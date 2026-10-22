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
const guidance = { schema_version:1, retrieved_at:'2026-10-21T10:00:00Z', expires_at:'2099-01-01', route:'official reader', sources:[{id:'doc-one',url:'https://code.claude.com/docs/en/hooks',title:'Hooks reference',publisher:'Anthropic',content_sha256:'sha256-proof',version:null,publication_date:null,crawl_status:'cached',retrieved_at:'2026-10-21T10:00:00Z',passages:[{id:'p-one',text:'Exit code 2 blocks the action.'}],target_ids:[target.id]}], coverage:[{target_id:target.id,source_ids:['doc-one'],status:'available',limitations:[]}],limitations:[] };
const rationales = [{target_id:target.id,diagnosis:'The hook currently allows the unsafe action.',recommendation:'Use the documented blocking exit code.',practice_kind:'native_contract',applicability:'This target is a command hook.',guidance_evidence:[{source_id:'doc-one',passage_id:'p-one',quote:'Exit code 2 blocks the action.'}],alternatives:[{option:'Print a warning',why_rejected:'A warning does not stop the action.'}],limitations:['Runtime hook execution remains untested.']}];
const guidance_assessment = {status:'passed',findings:[{target_id:target.id,status:'supported',reason:'The candidate uses the documented exit code.'}],limitations:[]};
const plan = { guidance, rationales, guidance_assessment, proposal_target_ids:[target.id], schema_version: 1, plan_id: 'plan-one', digest: 'digest-one', created_at: 'today', expires_at: '2099-01-01', intent: 'fix', targets: [target], operations: [{ step_id: 'step-one', target_id: target.id, adapter_id: 'skills', adapter_version: '1', action: 'patch', public_diff: '-old\n+new', checks: [check] }], checks: [check], limitations: [] };
async function proposed(proposal = plan) { const h = harness(); h.render(); h.reads[0].resolve({ schema_version: 1, targets: [target], limitations: ['Bounded registry'] }); await tick(); let tree = h.render(); nodes(tree,n => n.type === 'input' && n.props.type === 'checkbox')[0].props.onChange(); tree = h.render(); nodes(tree,n => n.type === 'textarea')[0].props.onChange({ target: { value: 'fix' } }); button(h.render(), 'Review & fix').props.onClick(); h.reads[1].resolve(proposal); await tick(); return h; }
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
  h.reads.find(r => r.url === '/api/repairs/jobs/plan-one').resolve({code:'record_unavailable',error:'Repair operation unavailable; inspect the recorded safe status.'},404); await tick();
  assert.equal(h.storage.get('universal-repair-job'),'plan-one');
  assert.match(text(h.render()),/Waiting for.*original job|Original job lookup pending/);
  assert.equal(h.reads.filter(r => r.options.method === 'POST').length,0);
});
for (const code of ['plan_expired', 'checks_not_passed', 'guidance_required', 'guidance_stale', 'guidance_invalid']) test(`definitive pre-job ${code} rejection permits fresh proposal`, async () => {
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

const durable = (status, extra = {}) => ({schema_version:1,job_id:'original-job',plan_id:'original-job',digest:'d',status,steps:[],events:[],unknown_effect:null,updated_at:'today',...extra});
for (const status of ['unknown', 'blocked']) test(`${status} job preserves recovery ID and blocks replacement approval`, async () => {
  const h = harness('original-job'); h.render(); h.render(); h.reads[0].resolve({targets:[target],limitations:[]});
  h.reads.find(r => r.url.endsWith('/jobs/original-job')).resolve(durable(status,{unknown_effect:status === 'unknown' ? 'uncertain write' : null})); await tick();
  const tree = h.render(); assert.equal(button(tree,'Review & fix').props.disabled,true); assert.equal(button(tree,'Select all matching targets').props.disabled,true);
  assert.equal(h.storage.get('universal-repair-job'),'original-job');
});
for (const outcome of ['success','failure']) test(`source navigation ignores late ${outcome}, including busy cleanup`, async () => {
  const h = await proposed(); button(h.render(),'Read current source').props.onClick(); const old = h.reads.at(-1);
  const props = {requestedSource:{fileId:target.id,path:'/next',nonce:1}}; h.render(props); h.render(props);
  button(h.render(props),'Read current source').props.onClick(); const current = h.reads.at(-1);
  if (outcome === 'success') old.resolve({target,snapshot:'STALE_PREVIOUS_SOURCE'}); else old.resolve({code:'analysis_context_changed',error:'STALE_ERROR'},409);
  await tick(); let tree = h.render(props); assert.doesNotMatch(text(tree),/STALE_PREVIOUS_SOURCE|STALE_ERROR|Source or native version changed/); assert.equal(button(tree,'Read current source').props.disabled,true);
  current.resolve({target,snapshot:'CURRENT_SOURCE'}); await tick(); tree = h.render(props); assert.match(text(tree),/CURRENT_SOURCE/);
});
for (const status of ['queued','preflight','applying','undoing']) test(`orphan ${status} offers same-job recovery without apply`, async () => {
  const h = harness('original-job'); h.render(); h.render(); h.reads.find(r => r.url.endsWith('/jobs/original-job')).resolve(durable(status)); await tick();
  button(h.render(),'Recover recorded job').props.onClick(); const read = h.reads.at(-1); assert.equal(read.url,'/api/repairs/jobs/original-job'); assert.deepEqual(JSON.parse(read.options.body),{action:'resume'});
  assert.equal(h.storage.get('universal-repair-job'),'original-job'); assert.equal(h.reads.filter(r=>r.options.body && JSON.parse(r.options.body).action === 'apply').length,0);
});
test('AI no proposals shows failed stage and checks without stale warning or approval', async () => {
  const h = await proposed(); nodes(h.render(),n=>n.type==='textarea')[0].props.onChange({target:{value:'try again'}}); button(h.render(),'Review & fix').props.onClick();
  h.reads.at(-1).resolve({code:'ai_no_proposals',error:'AI returned no repair proposals.',diagnostics:{stage:'proposal_validation',reason:'empty_proposals'},checks:[{...check,status:'failed',evidence:['No proposed behavior was tested.']}],limitations:['No repair plan was created.']},422); await tick();
  const tree = h.render(); assert.match(text(tree),/proposal validation/); assert.match(text(tree),/simulated behavior\s*:\s*failed/); assert.match(text(tree),/No repair plan was created/); assert.doesNotMatch(text(tree),/Source or native version changed/); assert.equal(button(tree,'Approve tested bundle'),undefined);
});
test('non-stale conflict does not claim source changed', async () => {
  const h = await proposed(); nodes(h.render(),n=>n.type==='textarea')[0].props.onChange({target:{value:'retry'}}); button(h.render(),'Review & fix').props.onClick(); h.reads.at(-1).resolve({code:'ai_unavailable',error:'Model unavailable'},409); await tick(); assert.doesNotMatch(text(h.render()),/Source or native version changed/);
});
test('selecting 143 targets keeps selection visible and blocks request above batch limit', async () => {
  const h = harness(); h.render(); h.reads[0].resolve({targets:Array.from({length:143},(_,i)=>({...target,id:`target-${i}`})),limitations:[]}); await tick(); button(h.render(),'Select all matching targets').props.onClick(); nodes(h.render(),n=>n.type==='textarea')[0].props.onChange({target:{value:'fix'}}); const tree=h.render(); assert.match(text(tree),/143\s+selected/); assert.match(text(tree),/at most\s+16/); assert.equal(button(tree,'Review & fix').props.disabled,true); button(tree,'Review & fix').props.onClick(); assert.equal(h.reads.length,1);
});
test('actual CLI missing-job envelope keeps original browser recovery pending', async () => {
  const { execFile } = require('node:child_process');
  const { promisify } = require('node:util');
  const state = fs.mkdtempSync(path.join(require('node:os').tmpdir(),'repair-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-'));
  try {
    const result = await promisify(execFile)('python3',['-B','-c',"import json,sys; from unittest.mock import patch; import universal_repairs; sys.argv=['universal_repairs.py','--state',sys.argv[1]]; from io import StringIO;\nwith patch('sys.stdin',StringIO(json.dumps({'action':'job','job_id':'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}))), patch('universal_repairs.default_registry', return_value=None): universal_repairs.main()",state],{cwd:path.resolve(__dirname),env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});
    const envelope = JSON.parse(result.stdout); assert.equal(envelope.status,404); assert.equal(envelope.code,'record_unavailable');
    const h=harness('aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'); h.render(); h.render(); h.reads.find(r=>r.url.endsWith('/jobs/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')).resolve(envelope.data ?? {error:envelope.error,code:envelope.code},envelope.status); await tick();
    assert.match(text(h.render()),/Original job lookup pending/); assert.equal(h.storage.get('universal-repair-job'),'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'); assert.equal(button(h.render(),'Review & fix').props.disabled,true); assert.equal(h.reads.filter(r=>r.options.method==='POST').length,0);
  } finally { fs.rmSync(state,{recursive:true,force:true}); }
});

test('researched preview explains why before targets, with captured official link and honest provenance', async () => {
  const h = await proposed({...plan,targets:[target,{...target,id:'generated-copy'}]}); const tree=h.render(); const copy=text(tree);
  for (const value of [rationales[0].diagnosis,rationales[0].recommendation,rationales[0].applicability,'Print a warning','A warning does not stop','Exit code 2 blocks the action.','Version unknown','cached','not confirmed','Documentary support','Runtime hook execution remains untested.']) assert.ok(copy.includes(value),value);
  const link=nodes(tree,n=>n.type==='a' && n.props.href===guidance.sources[0].url)[0]; assert.ok(link); assert.match(text(link),/Hooks reference/);
  assert.ok(copy.indexOf(rationales[0].diagnosis)<copy.indexOf('Affected targets'));
  assert.equal(button(tree,'Approve tested bundle').props.disabled,false,'generated copies need no invented rationale');
});
for (const extra of [{proposal_target_ids:undefined},{guidance:undefined,rationales:undefined,guidance_assessment:undefined},{guidance_assessment:{...guidance_assessment,status:'failed'}},{rationales:[]}]) test('unresearched or unsupported plan has no approval action',async()=>{
 const h=await proposed({...plan,...extra}); assert.equal(button(h.render(),'Approve tested bundle'),undefined); assert.match(text(h.render()),/fresh researched review|Research.*not ready/i);
});
for(const status of ['failed','unavailable']) test(`failed review exposes ${status} documentary assessment and captured sources`,async()=>{
 const h=await proposed(); nodes(h.render(),n=>n.type==='textarea')[0].props.onChange({target:{value:'retry'}}); button(h.render(),'Review & fix').props.onClick();
 h.reads.at(-1).resolve({code:'ai_no_proposals',error:'No source-backed repair.',guidance:{...guidance,coverage:[{...guidance.coverage[0],status:'unavailable',limitations:['Partial field coverage']} ]},rationales,guidance_assessment:{status,findings:[{target_id:target.id,status:'unsupported',reason:'This field is not documented.'}],limitations:['Source retrieval did not establish support.']}},422); await tick();
 const tree=h.render(); assert.match(text(tree),/This field is not documented/); assert.match(text(tree),/Partial field coverage/); assert.match(text(tree),new RegExp(`Documentary support.*${status}`)); assert.ok(nodes(tree,n=>n.type==='a'&&n.props.href===guidance.sources[0].url).length); assert.equal(button(tree,'Approve tested bundle'),undefined);
});
