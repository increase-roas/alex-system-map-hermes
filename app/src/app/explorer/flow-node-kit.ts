/**
 * Node kit for the Flow Builder tab. The 15 Flowise Agentflow V2 node types (design reference:
 * https://docs.flowiseai.com/using-flowise/agentflowv2, Apache 2.0) plus Alex's own:
 * Judge, Compare, Promote (GEPA loop) and Route to customer (agency-os-kit/tools/route.py).
 * Pure data and checks, no React, so it can be tested with plain Node.
 */
export type FieldKind = 'text' | 'textarea' | 'number' | 'select';
export type Field = { key: string; label: string; kind: FieldKind; options?: string[]; placeholder?: string };
export type NodeKind = {
  type: string; label: string; group: Group; icon: string; color: string;
  inputs: string[]; outputs: string[]; fields: Field[]; what: string; source: 'agentflow' | 'alex';
};
export type Group = 'Start and end' | 'AI' | 'Tools and data' | 'Logic' | 'People' | 'Improve (GEPA)' | 'Notes';

const model: Field = { key: 'model', label: 'Model', kind: 'select', options: ['claude-haiku-5-5', 'claude-sonnet-5-5', 'claude-opus-5-5'] };

export const KIT: NodeKind[] = [
  { type: 'start', label: 'Start', group: 'Start and end', icon: 'Play', color: '#16a34a', inputs: [], outputs: ['out'], source: 'agentflow',
    what: 'Where the flow begins: a chat message, a form, a webhook or a schedule. Your Input node.',
    fields: [{ key: 'trigger', label: 'Starts on', kind: 'select', options: ['chat message', 'form', 'webhook', 'schedule'] }, { key: 'inputs', label: 'Input fields', kind: 'text', placeholder: 'task, location_id' }] },
  { type: 'llm', label: 'LLM', group: 'AI', icon: 'Brain', color: '#2563eb', inputs: ['in'], outputs: ['out'], source: 'agentflow',
    what: 'One model call with a prompt. Can return structured JSON.',
    fields: [model, { key: 'prompt', label: 'Prompt', kind: 'textarea' }, { key: 'schema', label: 'JSON output fields', kind: 'text', placeholder: 'score, feedback' }] },
  { type: 'agent', label: 'Agent', group: 'AI', icon: 'Bot', color: '#2563eb', inputs: ['in'], outputs: ['out'], source: 'agentflow',
    what: 'A model that can pick and call tools on its own until the job is done.',
    fields: [model, { key: 'instructions', label: 'Instructions', kind: 'textarea' }, { key: 'tools', label: 'Tools it may use', kind: 'text', placeholder: 'ghl.conversations, meta.ads' }] },
  { type: 'tool', label: 'Tool', group: 'Tools and data', icon: 'Wrench', color: '#9333ea', inputs: ['in'], outputs: ['out'], source: 'agentflow',
    what: 'Runs one specific tool with set inputs (no model deciding).',
    fields: [{ key: 'tool', label: 'Tool', kind: 'text', placeholder: 'GOHIGHLEVEL_LIST_CONTACTS' }, { key: 'card', label: 'Connector card (read first)', kind: 'text', placeholder: '.claude/connector-cards/ghl.md' }] },
  { type: 'retriever', label: 'Retriever', group: 'Tools and data', icon: 'Database', color: '#9333ea', inputs: ['in'], outputs: ['out'], source: 'agentflow',
    what: 'Looks up matching documents from a knowledge store.',
    fields: [{ key: 'store', label: 'Knowledge store', kind: 'text', placeholder: 'customers/<slug>/objections.md' }, { key: 'k', label: 'How many results', kind: 'number' }] },
  { type: 'http', label: 'HTTP', group: 'Tools and data', icon: 'Globe', color: '#9333ea', inputs: ['in'], outputs: ['out'], source: 'agentflow',
    what: 'Calls a web address (API) directly.',
    fields: [{ key: 'method', label: 'Method', kind: 'select', options: ['GET', 'POST', 'PUT', 'DELETE'] }, { key: 'url', label: 'URL', kind: 'text' }] },
  { type: 'condition', label: 'Condition', group: 'Logic', icon: 'GitBranch', color: '#d97706', inputs: ['in'], outputs: ['yes', 'no'], source: 'agentflow',
    what: 'If/else on a rule you write. Yes goes one way, no the other.',
    fields: [{ key: 'rule', label: 'If', kind: 'text', placeholder: 'score >= 0.9' }] },
  { type: 'conditionAgent', label: 'Condition Agent', group: 'Logic', icon: 'Split', color: '#d97706', inputs: ['in'], outputs: ['a', 'b', 'c', 'd', 'e'], source: 'agentflow',
    what: 'A model reads the input and picks one of up to 5 paths (like which function a task is).',
    fields: [model, { key: 'paths', label: 'Paths (a to e)', kind: 'text', placeholder: 'lead_follow_up, website, ads, reporting, customer_update' }] },
  { type: 'iteration', label: 'Iteration', group: 'Logic', icon: 'Repeat', color: '#d97706', inputs: ['in'], outputs: ['each', 'done'], source: 'agentflow',
    what: 'Runs the next steps once for every item in a list.',
    fields: [{ key: 'list', label: 'List to go through', kind: 'text', placeholder: 'test cases' }] },
  { type: 'loop', label: 'Loop', group: 'Logic', icon: 'RotateCcw', color: '#d97706', inputs: ['in'], outputs: ['again', 'stop'], source: 'agentflow',
    what: 'Sends the flow back to an earlier step, up to a set number of times. Your hloop node.',
    fields: [{ key: 'max', label: 'Max rounds', kind: 'number' }, { key: 'back_to', label: 'Back to step', kind: 'text' }] },
  { type: 'humanInput', label: 'Human Input', group: 'People', icon: 'UserCheck', color: '#dc2626', inputs: ['in'], outputs: ['yes', 'no'], source: 'agentflow',
    what: 'Stops and waits for a person to approve or reject. Required before spend, send or delete.',
    fields: [{ key: 'who', label: 'Who approves', kind: 'text', placeholder: 'Alex' }, { key: 'question', label: 'Question', kind: 'text' }] },
  { type: 'directReply', label: 'Direct Reply', group: 'Start and end', icon: 'MessageSquare', color: '#16a34a', inputs: ['in'], outputs: [], source: 'agentflow',
    what: 'Sends a fixed answer back and ends the flow.',
    fields: [{ key: 'text', label: 'Reply', kind: 'textarea' }] },
  { type: 'customFunction', label: 'Custom Function', group: 'Tools and data', icon: 'Code', color: '#9333ea', inputs: ['in'], outputs: ['out'], source: 'agentflow',
    what: 'Runs your own small script, like a scorer or a calculator.',
    fields: [{ key: 'command', label: 'Command', kind: 'text', placeholder: 'python3 tools/score_customer.py' }] },
  { type: 'executeFlow', label: 'Execute Flow', group: 'Tools and data', icon: 'Workflow', color: '#9333ea', inputs: ['in'], outputs: ['out'], source: 'agentflow',
    what: 'Runs another saved flow as one step.',
    fields: [{ key: 'flow', label: 'Flow name', kind: 'text' }] },
  { type: 'stickyNote', label: 'Sticky Note', group: 'Notes', icon: 'StickyNote', color: '#ca8a04', inputs: [], outputs: [], source: 'agentflow',
    what: 'A note on the canvas. Does nothing when the flow runs.',
    fields: [{ key: 'text', label: 'Note', kind: 'textarea' }] },
  { type: 'judge', label: 'Judge', group: 'Improve (GEPA)', icon: 'Gavel', color: '#0d9488', inputs: ['in'], outputs: ['score'], source: 'alex',
    what: 'Grades an output: a score 0 to 1 plus written feedback on what was wrong.',
    fields: [{ key: 'checks', label: 'Rule checks', kind: 'text', placeholder: 'uses first name, no price, under 40 words, asks a question' }, { key: 'judge', label: 'Model judge', kind: 'select', options: ['rules only', 'rules + claude'] }] },
  { type: 'compare', label: 'Compare', group: 'Improve (GEPA)', icon: 'Scale', color: '#0d9488', inputs: ['new', 'current'], outputs: ['better', 'not better'], source: 'alex',
    what: 'Compares the new prompt with the current one case by case. Keeps any version that is best on at least one case.',
    fields: [{ key: 'on', label: 'Compare on', kind: 'select', options: ['held-out cases', 'all cases'] }] },
  { type: 'promote', label: 'Promote', group: 'Improve (GEPA)', icon: 'Rocket', color: '#0d9488', inputs: ['in'], outputs: [], source: 'alex',
    what: 'Makes the winning prompt live and saves the old one. Must come after a Human Input yes.',
    fields: [{ key: 'target', label: 'Live prompt file', kind: 'text', placeholder: 'gepa/jobs/<job>/prompt.md' }] },
  { type: 'routeCustomer', label: 'Route to customer', group: 'Logic', icon: 'Route', color: '#d97706', inputs: ['in'], outputs: ['found', 'unknown'], source: 'alex',
    what: 'Finds which customer a task is for (location ID, account ID, website or name) and attaches their IDs. Never guesses.',
    fields: [{ key: 'by', label: 'Match by', kind: 'text', placeholder: 'location_id, ids, website, name' }] },
];

export const KIT_BY_TYPE: Record<string, NodeKind> = Object.fromEntries(KIT.map((k) => [k.type, k]));
export const GROUPS: Group[] = ['Start and end', 'AI', 'Tools and data', 'Logic', 'People', 'Improve (GEPA)', 'Notes'];

export type FlowNode = { id: string; type: 'kit'; position: { x: number; y: number }; data: { kind: string; label: string; values: Record<string, string> } };
export type FlowEdge = { id: string; source: string; target: string; sourceHandle?: string | null; targetHandle?: string | null; label?: string };
export type Flow = { name: string; nodes: FlowNode[]; edges: FlowEdge[] };

/** Plain-English problems that would make the flow unsafe or broken. Empty list = OK. */
export function checkFlow(flow: Flow): string[] {
  const out: string[] = [];
  const kind = (id: string) => flow.nodes.find((n) => n.id === id)?.data.kind;
  const name = (id: string) => flow.nodes.find((n) => n.id === id)?.data.label ?? id;
  const starts = flow.nodes.filter((n) => n.data.kind === 'start');
  if (starts.length !== 1) out.push(`Needs exactly one Start node (has ${starts.length}).`);
  for (const n of flow.nodes) {
    const k = KIT_BY_TYPE[n.data.kind];
    if (!k) { out.push(`${n.data.label}: unknown node type ${n.data.kind}.`); continue; }
    if (k.type === 'stickyNote') continue;
    const into = flow.edges.filter((e) => e.target === n.id);
    const from = flow.edges.filter((e) => e.source === n.id);
    if (k.inputs.length && !into.length) out.push(`${n.data.label}: nothing flows into it.`);
    if (k.outputs.length && !from.length) out.push(`${n.data.label}: goes nowhere.`);
    if (k.type === 'loop' && !(Number(n.data.values.max) > 0)) out.push(`${n.data.label}: set Max rounds so it cannot run forever.`);
    if (k.type === 'promote' && !into.some((e) => kind(e.source) === 'humanInput' && (e.sourceHandle ?? 'yes') === 'yes'))
      out.push(`${n.data.label}: must come right after a Human Input "yes".`);
    if (k.type === 'tool' && !n.data.values.card) out.push(`${n.data.label}: name the connector card it must read first.`);
  }
  for (const e of flow.edges) {
    if (!kind(e.source) || !kind(e.target)) out.push(`Arrow ${e.id} points at a missing node.`);
    const src = KIT_BY_TYPE[kind(e.source) ?? ''];
    if (src && src.outputs.length > 1 && e.sourceHandle && !src.outputs.includes(e.sourceHandle)) out.push(`${name(e.source)}: no output called ${e.sourceHandle}.`);
  }
  return out;
}

let seq = 0;
function n(kind: string, label: string, x: number, y: number, values: Record<string, string> = {}): FlowNode {
  return { id: `${kind}-${++seq}`, type: 'kit', position: { x, y }, data: { kind, label, values } };
}
function e(a: FlowNode, b: FlowNode, sourceHandle?: string, targetHandle?: string, label?: string): FlowEdge {
  return { id: `e-${a.id}-${b.id}-${sourceHandle ?? 'out'}`, source: a.id, target: b.id, sourceHandle: sourceHandle ?? null, targetHandle: targetHandle ?? null, label };
}

export function gepaPreset(): Flow {
  seq = 0;
  const start = n('start', 'Test set (20 to 50 real cases)', 0, 0, { trigger: 'schedule', inputs: 'job, testset.jsonl' });
  const each = n('iteration', 'Each training case', 0, 150, { list: 'train cases' });
  const run = n('llm', 'Run candidate prompt', -260, 300, { model: 'claude-haiku-5-5', prompt: 'candidates/cN.md' });
  const judge = n('judge', 'Judge: score + feedback', -260, 460, { checks: 'uses first name, no price, under 40 words, asks a question', judge: 'rules only' });
  const reflect = n('llm', 'Reflect: rewrite the prompt from the feedback', 260, 300, { model: 'claude-sonnet-5-5', prompt: 'Fix what the judge said; keep what worked.' });
  const compare = n('compare', 'Compare new vs current', 260, 460, { on: 'held-out cases' });
  const loop = n('loop', 'Another round?', 560, 460, { max: '5', back_to: 'Each training case' });
  const ask = n('humanInput', 'Alex approves?', 260, 620, { who: 'Alex', question: 'Make this prompt live?' });
  const promote = n('promote', 'Promote to live', 260, 780, { target: 'gepa/jobs/<job>/prompt.md' });
  const stop = n('directReply', 'Keep current prompt', 560, 620, { text: 'No change made.' });
  const note = n('stickyNote', 'How it works', -560, 0, { text: 'Same loop as agency-os-kit/gepa/gepa.py. Run it there: gepa.py loop --job <job>. Nothing goes live without Alex.' });
  return {
    name: 'GEPA feedback loop',
    nodes: [start, each, run, judge, reflect, compare, loop, ask, promote, stop, note],
    edges: [e(start, each), e(each, run, 'each'), e(run, judge), e(judge, each, 'score', undefined, 'next case'), e(each, reflect, 'done'),
      e(reflect, compare, undefined, 'new'), e(compare, ask, 'better'), e(compare, loop, 'not better'), e(loop, reflect, 'again'),
      e(loop, stop, 'stop'), e(ask, promote, 'yes'), e(ask, stop, 'no')],
  };
}

export function routingPreset(): Flow {
  seq = 100;
  const start = n('start', 'Incoming task', 0, 0, { trigger: 'webhook', inputs: 'task, location_id' });
  const who = n('routeCustomer', 'Which customer?', 0, 150, { by: 'location_id, ids, website, name' });
  const unknown = n('directReply', 'Stop: customer unclear', 320, 150, { text: 'Could not tell which customer. Add the location ID.' });
  const fn = n('conditionAgent', 'Which function?', 0, 300, { model: 'claude-haiku-5-5', paths: 'lead_follow_up, website, ads, reporting, customer_update' });
  const sales = n('agent', 'Sales agent (lead follow-up)', -520, 470, { tools: 'ghl.conversations, ghl.contacts', instructions: 'customers/<slug>/AGENTS.md' });
  const site = n('agent', 'Hermes site builder (website)', -260, 470, { tools: 'github, cloudflare' });
  const ads = n('agent', 'Ads optimizer (ads)', 0, 470, { tools: 'meta.ads' });
  const rep = n('agent', 'Reporter (reporting + updates)', 260, 470, { tools: 'dashboard, ghl.conversations' });
  const risky = n('condition', 'Spend, send or delete?', 0, 630, { rule: 'needs_alex_yes == true' });
  const ask = n('humanInput', 'Alex approves?', 260, 780, { who: 'Alex' });
  const tool = n('tool', 'Do it with the customer\'s IDs', 0, 930, { tool: 'from the plan', card: 'connector card for that tool' });
  const no = n('directReply', 'Not approved: saved as draft', 520, 930, { text: 'Saved as a draft for Alex.' });
  const done = n('directReply', 'Report: done, proof, next step', 0, 1080, { text: 'What was done, the proof, and what is next.' });
  return {
    name: 'Lead routing (if/else)',
    nodes: [start, who, unknown, fn, sales, site, ads, rep, risky, ask, tool, no, done],
    edges: [e(start, who), e(who, fn, 'found'), e(who, unknown, 'unknown'), e(fn, sales, 'a'), e(fn, site, 'b'), e(fn, ads, 'c'), e(fn, rep, 'd'), e(fn, rep, 'e'),
      e(sales, risky), e(site, risky), e(ads, risky), e(rep, risky), e(risky, ask, 'yes'), e(risky, tool, 'no'), e(ask, tool, 'yes'), e(ask, no, 'no'), e(tool, done)],
  };
}
