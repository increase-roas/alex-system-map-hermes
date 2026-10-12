/* Execute the displayed Claude registration commands against isolated fixture files. */
const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const vm = require('node:vm');
const ts = require('typescript');
const source = fs.readFileSync(path.join(__dirname,'..','pro-map-guardrail-config.ts'),'utf8');
const mod = {exports:{}};
vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{module:mod,exports:mod.exports});
const settings = JSON.parse(mod.exports.CLAUDE_GUARD_SETTINGS);
const fixture = fs.mkdtempSync(path.join(__dirname,'registration-fixture-'));
const project = path.join(fixture,'project with spaces');
const state = path.join(fixture,'private-state');
fs.mkdirSync(state,{mode:0o700});
const hooksDir = path.join(project,'.claude','hooks');
const cardsDir = path.join(project,'.claude','connector-cards');
fs.mkdirSync(hooksDir,{recursive:true}); fs.mkdirSync(cardsDir,{recursive:true});
for (const name of ['asset_guard.py','read_gate.py']) fs.copyFileSync(path.join(__dirname,name),path.join(hooksDir,name));
const card = path.join(cardsDir,'ghl.md');
const text = '# Fixture connector\nNo real account or actions.\n';
fs.writeFileSync(card,text);fs.writeFileSync(path.join(cardsDir,'composio.md'),text);
const policy = JSON.parse(mod.exports.READ_GATE_POLICY);
const replacePaths = obj => typeof obj === 'string' ? obj.replace('/absolute/path/to/project',project) : Array.isArray(obj) ? obj.map(replacePaths) : obj && typeof obj === 'object' ? Object.fromEntries(Object.entries(obj).map(([k,v])=>[k,replacePaths(v)])) : obj;
fs.writeFileSync(path.join(project,'.claude','guard-policy.json'),JSON.stringify(replacePaths(policy)));
fs.writeFileSync(path.join(project,'.claude','settings.json'),JSON.stringify(settings));
let checks = 0;
const assert = (v,msg) => { if(!v) throw new Error(msg); checks++; };
const run = (event,tool,input={},response) => {
 const payload = {hook_event_name:event,tool_name:tool,tool_input:input,cwd:project,session_id:'registration-fixture',tool_use_id:tool==='Read'?'read-card':'call',...(response?{tool_response:response}:{})};
 const outputs=[];
 for(const group of settings.hooks[event]??[]) if(!group.matcher||new RegExp(group.matcher).test(tool)) for(const h of group.hooks) {
  const r=cp.spawnSync(h.command,{shell:true,cwd:project,env:{...process.env,CLAUDE_PROJECT_DIR:project,READ_GATE_STATE_DIR:state,PYTHONDONTWRITEBYTECODE:'1'},input:JSON.stringify(payload),encoding:'utf8',timeout:30000});
  assert(r.status===0,`${event}/${tool} script failed: ${r.stderr}`);outputs.push(JSON.parse(r.stdout));
 }
 assert(outputs.length>0,'No displayed hook matched '+event+'/'+tool);
 return outputs;
};
const denied = out=>out.some(o=>o.hookSpecificOutput?.permissionDecision==='deny'||o.decision==='block');
assert(denied(run('PreToolUse','mcp__ghl__contacts_list')),'Unread call passed');
assert(denied(run('PreToolUse','mcp__ghl__contacts_list')),'Retry alone passed');
assert(!denied(run('PreToolUse','Read',{file_path:card})),'Read blocked');
assert(!denied(run('PostToolUse','Read',{file_path:card},{type:'text',file:{filePath:card,content:text,numLines:text.split('\n').length,startLine:1,totalLines:text.split('\n').length}})),'Successful Read processing blocked');
assert(!denied(run('PreToolUse','mcp__ghl__contacts_list')),'Read receipt did not unlock exact route');
assert(denied(run('PreToolUse','Write',{file_path:path.join(project,'.claude','skills','bad','SKILL.md'),content:'# missing frontmatter'})),'Bad skill Write passed');
assert(!denied(run('Stop','')),'Valid fixture failed final scan');
const bad = path.join(project,'.claude','skills','bad','SKILL.md');fs.mkdirSync(path.dirname(bad),{recursive:true});fs.writeFileSync(bad,'# made by another writer');
assert(denied(run('PostToolUse','Bash',{command:'fixture-only'})),'After-tool scan missed bad external edit');
assert(denied(run('Stop','')),'Stop scan missed bad external edit');

const hermesHome = path.join(fixture,'hermes profile with spaces');
const hermesState = path.join(fixture,'hermes-private-state');
fs.mkdirSync(path.join(hermesHome,'agent-hooks'),{recursive:true});
fs.mkdirSync(path.join(hermesHome,'connector-cards'),{recursive:true});
fs.mkdirSync(hermesState,{mode:0o700});
fs.copyFileSync(path.join(__dirname,'hermes_guard.py'),path.join(hermesHome,'agent-hooks','hermes_guard.py'));
const hcard = path.join(hermesHome,'connector-cards','github.md');fs.writeFileSync(hcard,text);
const rewriteHermes = obj => typeof obj === 'string' ? obj.replaceAll('/absolute/path/to/profile',hermesHome).replaceAll('/absolute/path/to/private-runtime-state',hermesState) : Array.isArray(obj) ? obj.map(rewriteHermes) : obj && typeof obj === 'object' ? Object.fromEntries(Object.entries(obj).map(([k,v])=>[k,rewriteHermes(v)])) : obj;
const hsettings = rewriteHermes(JSON.parse(mod.exports.HERMES_GUARD_SETTINGS));
fs.writeFileSync(path.join(hermesHome,'config.yaml'),JSON.stringify({...hsettings,mcp_servers:{github:{url:'https://example.invalid/mcp'}}}));
fs.writeFileSync(path.join(hermesHome,'guard-policy.json'),JSON.stringify(rewriteHermes(JSON.parse(mod.exports.HERMES_GUARD_POLICY))));
const hrun = (event,tool,args,extra={}) => {
 const payload={hook_event_name:event,tool_name:tool,tool_input:args,session_id:'hermes-registration',cwd:hermesHome,profile:'default',extra:{tool_call_id:tool==='read_file'?'read1':'call1',...extra}};
 return hsettings.hooks[event].map(h=>{
  const r=cp.spawnSync(h.command,{shell:true,cwd:hermesHome,env:{...process.env,HERMES_HOME:hermesHome,PYTHONDONTWRITEBYTECODE:'1'},input:JSON.stringify(payload),encoding:'utf8',timeout:15000});
  assert([0,2].includes(r.status),'Displayed Hermes hook command failed: '+r.stderr);
  return JSON.parse(r.stdout);
 });
};
assert(hrun('pre_tool_call','mcp__github__get_issue',{}).some(o=>o.action==='block'),'Hermes unread route passed');
assert(!hrun('pre_tool_call','read_file',{path:hcard}).some(o=>o.action==='block'),'Hermes card Read blocked');
hrun('post_tool_call','read_file',{path:hcard},{status:'success',result:JSON.stringify({content:text.trimEnd().split('\n').map((l,i)=>`${i+1}|${l}`).join('\n'),total_lines:text.trimEnd().split('\n').length,file_size:Buffer.byteLength(text),truncated:false})});
assert(!hrun('pre_tool_call','mcp__github__get_issue',{}).some(o=>o.action==='block'),'Hermes full Read did not unlock route');
assert(hrun('pre_tool_call','mcp__github__get_issue',{actions:[{tool:'other'}]}).some(o=>o.action==='block'),'Hermes unsupported batch passed');
const hashes = Object.fromEntries(['../pro-map-guardrail-config.ts','asset_guard.py','read_gate.py','hermes_guard.py','check_registration.cjs'].map(name => [name,require('node:crypto').createHash('sha256').update(fs.readFileSync(path.join(__dirname,name))).digest('hex')]));
const finalReceipt={status:'PASS',checks,hashes,scope:'Displayed Claude and Hermes registration commands, offline fixtures; not native runtime installation'};
fs.writeFileSync(path.join(__dirname,'registration-receipt.json'),JSON.stringify(finalReceipt,null,2)+'\n');
console.log(JSON.stringify(finalReceipt));
