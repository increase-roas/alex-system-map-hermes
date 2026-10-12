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
assert(has(f, 'before an agent with tools'), 'agent with tools without a customer route is flagged');
f = routingPreset(); f.nodes.push({ ...f.nodes[0], id: 'start-x' });
assert(has(f, 'exactly one Start'), 'two Starts flagged');
if (fails) process.exit(1);
