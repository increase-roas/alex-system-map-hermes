/* Read-only checks: transpile map data in memory; never load app routes or call an API. */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const cp = require('node:child_process');
const ts = require('typescript');
const root = __dirname;
function loader(baseline = false) {
  const cache = new Map();
  return function load(name) {
    const file = path.resolve(root, name.endsWith('.ts') ? name : name + '.ts');
    if (cache.has(file)) return cache.get(file).exports;
    const rel = 'app/src/app/explorer/' + path.basename(file);
    const source = baseline ? cp.execFileSync('git', ['show', 'HEAD:' + rel], { cwd: root, encoding: 'utf8' }) : fs.readFileSync(file, 'utf8');
    const module = { exports: {} }; cache.set(file, module);
    const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
    vm.runInNewContext(js, { module, exports: module.exports, require: (id) => id.startsWith('.') ? load(path.resolve(path.dirname(file), id)) : require(id) }, { filename: file });
    return module.exports;
  };
}
const load = loader();
const { PRO_NODES: nodes, PRO_EDGES: edges, GRADES } = load('pro-map-all');
const errors = []; const check = (ok, msg) => { if (!ok) errors.push(msg); };
const ids = new Set(nodes.map(n => n.id));
check(ids.size === nodes.length, 'Duplicate node ID');
check(new Set(edges.map(e => e.id)).size === edges.length, 'Duplicate edge ID');
for (const e of edges) check(ids.has(e.source) && ids.has(e.target), 'Missing edge endpoint: ' + e.id);
for (const n of nodes) check([n.x,n.y,n.w ?? 130,n.h ?? 100].every(Number.isFinite), 'Invalid geometry: ' + n.id);
const node = id => nodes.find(n => n.id === id);
for (const job of load('pro-map-jobs').JOBS) for (const beat of job.beats) {
 for (const id of beat.ids) check(ids.has(id), 'Walkthrough references missing card: ' + id);
 for (const pair of beat.path ?? []) for (const id of pair) check(ids.has(id), 'Walkthrough path references missing card: ' + id);
}
const edge = (s,t) => edges.some(e => e.source === s && e.target === t);
check(edges.some(e => e.target === 'p_result'), 'p_result has no incoming arrow');
check(node('p_combine').y > node('p_result').y, 'p_combine must follow result');
check(node('h_result').y > node('h_term').y && node('h_result').y > node('h_code').y, 'Hermes results must follow execution cards');
check(edge('h_hook','h_humanapprove') && edge('h_humanapprove','h_band_run'), 'Hermes hook approval must have its own human gate');
check(edges.some(e => e.target === 'p_e1' || e.target === 'p_band_learn'), 'Learning has no incoming arrow');
check(edges.some(e => (e.source === 'p_e4' || e.source === 'p_band_learn') && (e.target === 'p_load' || e.target === 'p_band_front')), 'Learning has no next-session connection');
const before = loader(true)('pro-map-data').PRO_NODES.filter(n => n.id.startsWith('y_') && n.id !== 'y_title');
const now = load('pro-map-data').PRO_NODES.filter(n => n.id.startsWith('y_') && n.id !== 'y_title');
check(JSON.stringify(before) === JSON.stringify(now), 'Alex y_ cards or their merged details changed');
const originalV1 = loader(true)('pro-map-all').PRO_NODES.filter(n => n.id.startsWith('o_') && n.id !== 'o_title');
check(JSON.stringify(originalV1) === JSON.stringify(nodes.filter(n => n.id.startsWith('o_') && n.id !== 'o_title')), 'Original v1 cards or sticky notes changed');
for (const id of ['o_title','p_title','h_title','y_title']) {
 const g = GRADES[id]; check(g?.proof?.length === 5, id + ': needs five rubric proof rows');
 for (const p of g?.proof ?? []) check(p.why && (p.check || p.sources?.length), id + ': missing proof for ' + p.area);
 check(node(id).y + node(id).h < 0, id + ': title overlaps first row');
}
const { STICKY } = load('pro-map-sticky');
const mismatches = [];
for (const note of STICKY) for (const id of note.ids.filter(id => /^(p_|h_)/.test(id))) {
 if (note.title && node(id) && !node(id).detail?.examples?.some(e => e.title === note.title)) mismatches.push(id + ': ' + note.title);
}
check(!mismatches.length, 'Unmatched sticky example titles: ' + mismatches.join('; '));
// Render the actual title component in memory. No server, screenshots or app routes.
const panelSource = fs.readFileSync(path.join(root, 'pro-map-panel.tsx'), 'utf8');
const titleSource = panelSource.slice(0, panelSource.indexOf('const nodeTypes')) + '\nexport { Band };';
const titleModule = { exports: {} };
const titleJS = ts.transpileModule(titleSource, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
vm.runInNewContext(titleJS, { module: titleModule, exports: titleModule.exports, require: id => id === '@xyflow/react' ? { Handle: () => null, Position: { Top:'top', Bottom:'bottom', Left:'left', Right:'right' } } : id.startsWith('.') ? load(id) : require(id) });
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
for (const id of ['o_title','p_title','h_title','y_title']) {
 const html = renderToStaticMarkup(React.createElement(titleModule.exports.Band, {data: node(id)}));
 check((html.match(/<li /g) ?? []).length === 5, id + ': title does not render five proof rows');
 check(html.includes('data-testid="map-grade"'), id + ': grade is not rendered');
 for (const proof of GRADES[id].proof) for (const url of proof.sources ?? []) check(html.includes('href="' + url + '"'), id + ': source link not rendered');
}
let pythonExamples = 0; let shellExamples = 0; let jsonExamples = 0;
for (const n of nodes.filter(n => /^(p_|h_)/.test(n.id))) for (const e of n.detail?.examples ?? []) {
 if (e.tone === 'bad') continue;
 if (/\.py$/.test(e.file ?? '')) {
  pythonExamples++;
  const r = cp.spawnSync('python3', ['-B', '-c', 'import ast,sys; compile(ast.parse(sys.stdin.read()), "example", "exec")'], {input:e.code,encoding:'utf8'});
  check(r.status === 0, n.id + ' / ' + e.title + ': Python syntax: ' + r.stderr.trim());
 }
 if (/\.sh$/.test(e.file ?? '')) {
  shellExamples++;
  const r = cp.spawnSync('bash', ['-n'], {input:e.code,encoding:'utf8'});
  check(r.status === 0, n.id + ' / ' + e.title + ': shell syntax: ' + r.stderr.trim());
 }
 if (/\.json$/.test(e.file ?? '')) {
  jsonExamples++;
  try { JSON.parse(e.code); } catch(err) { check(false,n.id + ' / ' + e.title + ': JSON syntax: ' + err.message); }
 }
}
// Displayed guard code must be the exact bytes exercised by offline tests.
const guardCode = load('pro-map-guardrail-code').GUARD_CODE;
for (const name of ['asset_guard.py', 'read_gate.py', 'hermes_guard.py']) {
 check(guardCode[name] === fs.readFileSync(path.join(root,'pro-map-guardrails',name),'utf8'), 'Displayed hook differs: ' + name);
}
for (const id of ['p_rulegate','p_lib_skills','p_lib_mcp','p_lib_settings','p_ptr4','h_rulegate']) {
 check(node(id).detail?.examples?.some(e => e.code === guardCode[id.startsWith('h_') ? 'hermes_guard.py' : 'asset_guard.py']), 'Missing runnable setup guard: ' + id);
}
check(node('p_rulegate').detail.examples.some(e => e.code === guardCode['read_gate.py']), 'Missing read-first gate script');
const guardReceipt = JSON.parse(fs.readFileSync(path.join(root,'pro-map-guardrails','test-receipt.json'),'utf8'));
check(guardReceipt.status === 'PASS' && guardReceipt.results.length === 3, 'Guard fixtures did not all pass');
for (const result of guardReceipt.results) {
 for (const [file, expected] of [[result.script,result.script_sha256],[result.test,result.test_sha256]]) {
  const actual = require('node:crypto').createHash('sha256').update(fs.readFileSync(path.join(root,'pro-map-guardrails',file))).digest('hex');
  check(actual === expected, 'Guard receipt is stale: ' + file);
 }
}
const registrationReceipt = JSON.parse(fs.readFileSync(path.join(root,'pro-map-guardrails','registration-receipt.json'),'utf8'));
check(registrationReceipt.status === 'PASS' && registrationReceipt.checks >= 37, 'Displayed registration commands not verified');
for (const [file, expected] of Object.entries(registrationReceipt.hashes)) {
 const actual = require('node:crypto').createHash('sha256').update(fs.readFileSync(path.join(root,'pro-map-guardrails',file))).digest('hex');
 check(actual === expected, 'Registration receipt is stale: ' + file);
}
let finishHookCases = 0;
if (process.argv.includes('--exercise-hooks')) {
 // Deliberately confined fixtures. No npm command, API or real customer is called.
 const fixture = path.join(root, '.audit-backup', 'finish-hook-fixture');
 fs.mkdirSync(fixture, {recursive:true});
 const code = load('pro-map-v2-corrections').V2_FINISH_CHECK_PY;
 for (const [command, active, expected, blocked] of [['exit 0',false,'PASS',false],['exit 1',false,'BLOCKED',true],['exit 1',true,'BLOCKED',false],['exit 0',true,'PASS',false]]) {
  const input = JSON.stringify({cwd:fixture,stop_hook_active:active,session_id:'offline-map-audit'});
  const wrapped = 'import io,sys\nsys.stdin = io.StringIO(' + JSON.stringify(input) + ')\n' + code;
  const r = cp.spawnSync('python3', ['-B','-c', wrapped], {encoding:'utf8',cwd:fixture,env:{...process.env,CLAUDE_PROJECT_DIR:fixture,FINISH_CHECK:command}});
  check(r.status === 0, 'Finish hook fixture failed: ' + r.stderr);
  const receipt = JSON.parse(fs.readFileSync(path.join(fixture,'work','finish-status.json'),'utf8'));
  const output = r.stdout.trim() ? JSON.parse(r.stdout) : {};
  check(receipt.status === expected, 'Finish hook reports wrong outcome at retry cap');
  check((output.decision === 'block') === blocked, 'Finish hook continuation is wrong');
  finishHookCases++;
 }
 const valid = JSON.stringify({cwd:fixture,stop_hook_active:false,session_id:'offline-map-audit'});
 const failingProcess = 'import subprocess\ndef fail(*a, **k): raise OSError("offline fixture")\nsubprocess.run = fail\n';
 const failingWrite = 'from pathlib import Path\ndef fail(*a, **k): raise OSError("offline fixture")\nPath.write_text = fail\n';
 for (const [input, prefix] of [['not JSON',''],['[]',''],['{}',''],[valid,failingProcess],[valid,failingWrite]]) {
  const wrapped = 'import io,sys\nsys.stdin = io.StringIO(' + JSON.stringify(input) + ')\n' + prefix + code;
  const r = cp.spawnSync('python3', ['-B','-c',wrapped], {encoding:'utf8',cwd:fixture,env:{...process.env,CLAUDE_PROJECT_DIR:fixture,FINISH_CHECK:'exit 0'}});
  check(r.status === 0, 'Infrastructure exception escaped: ' + r.stderr);
  const output = r.stdout.trim() ? JSON.parse(r.stdout) : {};
  check(output.decision === 'block' && output.reason?.includes('BLOCKED'), 'Infrastructure failure did not report BLOCKED');
  finishHookCases++;
 }
 const definitions = code.replace('if __name__ == "__main__":','if False:');
 const staleCheck = definitions + '\nfrom pathlib import Path\np = Path("work/finish-status.json")\nexpected = json.loads(p.read_text())\nexpected["run_id"] = "wrong-run"\nassert not receipt_matches(p, expected)\nassert not receipt_matches(Path("missing-receipt.json"), expected)\n';
 const stale = cp.spawnSync('python3',['-B','-c',staleCheck],{encoding:'utf8',cwd:fixture});
 check(stale.status === 0,'Missing/stale receipt rejection failed: ' + stale.stderr);
 finishHookCases += 2;
}
const result = { checkedAt: new Date().toISOString(), nodes: nodes.length, edges: edges.length, pythonExamples, shellExamples, jsonExamples, finishHookCases, guardTestsPassed: guardReceipt.passed, guardTestsSkipped: guardReceipt.skipped, registrationChecks: registrationReceipt.checks, checks: ['IDs and edge endpoints', 'finite positions', 'V2 result/combine and learning connections', 'Alex cards and merged details unchanged from HEAD', 'five evidence rows on each title', 'titles clear first row', 'sticky example title matches', 'actual title component renders five rows and source links', 'Python, shell and JSON example syntax', 'Guard scripts exactly match displayed code', 'Hash-bound offline test and displayed registration receipts'], errors };
console.log(JSON.stringify(result, null, 2));
process.exitCode = errors.length ? 1 : 0;
