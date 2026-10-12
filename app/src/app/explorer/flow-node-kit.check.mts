import { KIT, checkFlow, gepaPreset, routingPreset, type Flow } from './flow-node-kit.ts';
let fails = 0;
const assert = (c: unknown, m: string) => { if (!c) { fails++; console.error('FAIL', m); } else console.log('PASS', m); };
const has = (f: Flow, word: string) => checkFlow(f).some((m) => m.includes(word));
const agentflow = ['start','llm','agent','tool','retriever','http','condition','conditionAgent','iteration','loop','humanInput','directReply','customFunction','executeFlow','stickyNote'];
assert(agentflow.every((t) => KIT.some((k) => k.type === t && k.source === 'agentflow')) && KIT.filter((k) => k.source === 'agentflow').length === 15, 'all 15 Agentflow node types');
assert(['judge','compare','promote','routeCustomer'].every((t) => KIT.some((k) => k.type === t)), 'Judge, Compare, Promote, Route to customer');
assert(checkFlow(gepaPreset()).length === 0, 'GEPA preset passes: ' + checkFlow(gepaPreset()).join(' | '));
assert(checkFlow(routingPreset()).length === 0, 'routing preset passes: ' + checkFlow(routingPreset()).join(' | '));
const id = (f: Flow, kind: string, i = 0) => f.nodes.filter((n) => n.data.kind === kind)[i].id;
// approval bypass: an extra arrow around Human Input into Promote
let f = gepaPreset(); f.edges.push({ id: 'x', source: id(f, 'compare'), target: id(f, 'promote'), sourceHandle: 'better' });
assert(has(f, 'skips Alex'), 'Promote reachable around the yes is flagged');
f = gepaPreset(); f.edges.push({ id: 'x2', source: id(f, 'humanInput'), target: id(f, 'promote'), sourceHandle: 'no' });
assert(has(f, '"no" leads'), 'Promote after a "no" is flagged');
f = routingPreset(); f.edges.push({ id: 'x3', source: id(f, 'condition'), target: f.nodes.find((n) => n.data.values.effect === 'spend')!.id, sourceHandle: 'no' });
assert(has(f, 'skips Alex'), 'spend tool reachable from the safe branch is flagged');
// loops
f = gepaPreset(); f.nodes.find((n) => n.data.kind === 'loop')!.data.values.max = '1000000';
assert(has(f, 'from 1 to 20'), 'huge loop limit is flagged');
f = gepaPreset(); f.edges.push({ id: 'cyc', source: id(f, 'compare'), target: id(f, 'llm', 2), sourceHandle: 'not better' });
f.edges.push({ id: 'cyc2', source: id(f, 'judge', 1), target: id(f, 'llm', 1), sourceHandle: 'score' });
assert(has(f, 'could run forever'), 'unbounded cycle is flagged');
// disconnected, missing inputs, settings
f = routingPreset(); f.nodes.push({ id: 'island', type: 'kit', position: { x: 0, y: 0 }, data: { kind: 'directReply', label: 'Island', values: { text: 'x' } } });
assert(has(f, 'cannot be reached'), 'unreachable node is flagged');
f = gepaPreset(); f.edges = f.edges.filter((e) => e.targetHandle !== 'current');
assert(has(f, 'input "current"'), 'Compare without the live baseline is flagged');
f = routingPreset(); f.nodes.find((n) => n.data.kind === 'tool')!.data.values.card = '';
assert(has(f, 'Connector card'), 'Tool without card is flagged');
f = routingPreset(); f.edges = f.edges.filter((e) => e.source !== id(f, 'routeCustomer')); f.edges.push({ id: 'skip', source: id(f, 'start'), target: id(f, 'conditionAgent') });
assert(has(f, 'Route to customer "found"'), 'agent with tools without a customer route is flagged');
f = routingPreset(); f.nodes.push({ ...f.nodes[0], id: 'start-x' });
assert(has(f, 'exactly one Start'), 'two Starts flagged');
// Codex round 2
f = routingPreset(); { const who = id(f, 'routeCustomer'); f.edges = f.edges.map((e) => (e.source === who && e.sourceHandle === 'found' ? { ...e, sourceHandle: 'unknown' } : e.source === who && e.sourceHandle === 'unknown' ? { ...e, sourceHandle: 'found' } : e)); }
assert(has(f, 'Route to customer "found"'), 'agent on the "unknown" branch is flagged');
f = routingPreset(); f.nodes.find((n) => n.data.kind === 'tool')!.data.values.effect = 'launch_rockets';
assert(has(f, 'not a valid choice'), 'made-up effect is flagged');
f = routingPreset(); f.nodes.find((n) => n.data.kind === 'agent')!.data.values.effect = 'spend';
assert(has(f, "skips Alex"), 'agent that can spend before any yes is flagged');
f = gepaPreset(); f.edges.push({ id: 'restart', source: id(f, 'llm', 1), target: id(f, 'iteration') });
assert(has(f, 'start over forever'), 'iteration restart loop is flagged');
f = routingPreset(); f.nodes.find((n) => n.data.kind === 'tool')!.data.values.effect = 'send_to_lead';
assert(has(f, 'skips Alex'), 'texting leads without a yes is flagged');
// Codex round 3
f = routingPreset(); f.nodes.find((n) => n.data.label.startsWith('Ads optimizer'))!.data.values.tools = 'meta.ads';
assert(has(f, 'its tools can spend'), 'agent whose tools can spend but says write is flagged');
f = routingPreset(); { const fn = id(f, 'conditionAgent'); f.nodes.push({ id: 'http-del', type: 'kit', position: { x: 0, y: 0 }, data: { kind: 'http', label: 'Delete contacts', values: { method: 'DELETE', url: 'https://x', effect: 'read' } } }); f.edges.push({ id: 'h', source: id(f, 'agent'), target: 'http-del' }); f.nodes.push({ id: 'end2', type: 'kit', position: { x: 0, y: 0 }, data: { kind: 'directReply', label: 'End', values: { text: 'x' } } }); f.edges.push({ id: 'h2', source: 'http-del', target: 'end2' }); void fn; }
assert(has(f, 'DELETE call must be marked') && has(f, 'skips Alex'), 'HTTP DELETE without approval is flagged');
f = routingPreset(); f.nodes.find((n) => n.data.label.startsWith('Do the safe'))!.data.values.tool = 'meta.ads'; f.nodes.find((n) => n.data.label.startsWith('Do the safe'))!.data.values.effect = 'delete';
assert(has(f, 'meta.ads cannot delete'), 'tool effect it cannot do is flagged');
f = routingPreset(); f.nodes.find((n) => n.data.label.startsWith('Sales agent'))!.data.values.tools = 'mystery.tool';
assert(has(f, 'unknown tool'), 'unknown agent tool is flagged');
// Codex round 4
const addAfter = (f: Flow, kind: string, label: string, values: Record<string, string>) => {
  const nid = `x-${kind}`; f.nodes.push({ id: nid, type: 'kit', position: { x: 0, y: 0 }, data: { kind, label, values } });
  const end = `end-${kind}`; f.nodes.push({ id: end, type: 'kit', position: { x: 0, y: 0 }, data: { kind: 'directReply', label: 'End', values: { text: 'x' } } });
  f.edges.push({ id: `a-${nid}`, source: id(f, 'routeCustomer'), target: nid, sourceHandle: 'found' }, { id: `b-${nid}`, source: nid, target: end });
  return f;
};
f = addAfter(routingPreset(), 'tool', 'Mystery', { tool: 'mystery.api', card: 'x.md', effect: 'read' });
assert(has(f, 'unknown tool mystery.api') && has(f, 'skips Alex'), 'unknown standalone tool is flagged and gated');
f = addAfter(routingPreset(), 'executeFlow', 'Run ghost', { flow: 'Ghost flow', effect: 'read' });
assert(has(f, 'no saved flow called') && has(f, 'skips Alex'), 'nonexistent nested flow is flagged and gated');
f = addAfter(routingPreset(), 'executeFlow', 'Run routing', { flow: 'Lead routing (if/else)', effect: 'read' });
assert(has(f, 'the flow it runs can'), 'nested flow that can spend must say so');
// Codex round 5 + 6
f = addAfter(routingPreset(), 'customFunction', 'Send blast', { script: 'send_everyone.py', effect: 'read' });
assert(has(f, 'not a registered script') && has(f, 'skips Alex'), 'unregistered script is flagged and gated');
f = addAfter(routingPreset(), 'customFunction', 'Score', { script: 'tools/score_customer.py', args: '--all', effect: 'read' });
assert(!has(f, 'Score:'), 'registered read-only script passes');
f = addAfter(routingPreset(), 'customFunction', 'Sneaky', { script: 'tools/metrics.py', args: 'customers/x\npython3 send.py', effect: 'read' });
assert(has(f, 'not allowed') && has(f, 'skips Alex'), 'newline in arguments is refused and gated');
f = addAfter(routingPreset(), 'customFunction', 'Chain', { script: 'tools/score_customer.py', args: '--all; curl evil', effect: 'read' });
assert(has(f, 'not allowed'), 'shell symbols refused');
f = addAfter(routingPreset(), 'customFunction', 'Gate', { script: 'tools/gate.py check', args: '--plan plan.json --action a.json', effect: 'read' });
assert(has(f, 'it does "write"'), 'gate check is write, not read');
f = addAfter(routingPreset(), 'customFunction', 'GEPA', { script: 'gepa/gepa.py loop', args: '--job speed-to-lead --model claude', effect: 'write' });
assert(has(f, 'it does "spend"') && has(f, 'skips Alex'), 'GEPA with Claude counts as spend and is gated');
f = addAfter(routingPreset(), 'customFunction', 'Odd', { script: 'tools/dashboard.py', args: '--out d.html --rm-rf', effect: 'write' });
assert(has(f, 'does not accept --rm-rf'), 'unknown flag refused');
// Codex round 7: incomplete commands are not OK
for (const [script, args, want] of [['tools/gate.py check', '', 'needs --plan'], ['tools/gate.py check', '--plan p.json', 'needs --action'],
  ['tools/dashboard.py', '--client example-tree-co', 'needs --out'], ['gepa/gepa.py loop', '--rounds 3', 'needs --job'],
  ['tools/metrics.py', '', 'needs a customer folder'], ['tools/score_customer.py', 'customers/x --all', 'use only one of'],
  ['tools/scan_customer.py', '--all --all', 'given twice']] as const) {
  f = addAfter(routingPreset(), 'customFunction', 'Run', { script, args, effect: script === 'tools/metrics.py' || script === 'tools/score_customer.py' ? 'read' : 'write' });
  assert(has(f, want), `${script} "${args}" -> ${want}`);
}
if (fails) process.exit(1);
