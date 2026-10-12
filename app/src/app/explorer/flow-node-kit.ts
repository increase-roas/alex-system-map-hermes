/**
 * Node kit for the Flow Builder tab. The 15 Flowise Agentflow V2 node types (design reference:
 * https://docs.flowiseai.com/using-flowise/agentflowv2, Apache 2.0) plus Alex's own:
 * Judge, Compare, Promote (GEPA loop) and Route to customer (agency-os-kit/tools/route.py).
 * Pure data and checks, no React, so it can be tested with plain Node.
 */
export type FieldKind = 'text' | 'textarea' | 'number' | 'select';
export type Field = { key: string; label: string; kind: FieldKind; options?: string[]; placeholder?: string; required?: boolean };
export type NodeKind = {
  type: string; label: string; group: Group; icon: string; color: string;
  inputs: string[]; outputs: string[]; fields: Field[]; what: string; source: 'agentflow' | 'alex';
};
export type Group = 'Start and end' | 'AI' | 'Tools and data' | 'Logic' | 'People' | 'Improve (GEPA)' | 'Notes';

const model: Field = { key: 'model', label: 'Model', kind: 'select', options: ['claude-haiku-5-5', 'claude-sonnet-5-5', 'claude-opus-5-5'], required: true };

export const KIT: NodeKind[] = [
  { type: 'start', label: 'Start', group: 'Start and end', icon: 'Play', color: '#16a34a', inputs: [], outputs: ['out'], source: 'agentflow',
    what: 'Where the flow begins: a chat message, a form, a webhook or a schedule. Your Input node.',
    fields: [{ key: 'trigger', label: 'Starts on', kind: 'select', options: ['chat message', 'form', 'webhook', 'schedule'], required: true }, { key: 'inputs', label: 'Input fields', kind: 'text', placeholder: 'task, location_id' }] },
  { type: 'llm', label: 'LLM', group: 'AI', icon: 'Brain', color: '#2563eb', inputs: ['in'], outputs: ['out'], source: 'agentflow',
    what: 'One model call with a prompt. Can return structured JSON.',
    fields: [model, { key: 'prompt', label: 'Prompt', kind: 'textarea', required: true }, { key: 'schema', label: 'JSON output fields', kind: 'text', placeholder: 'score, feedback' }] },
  { type: 'agent', label: 'Agent', group: 'AI', icon: 'Bot', color: '#2563eb', inputs: ['in'], outputs: ['out'], source: 'agentflow',
    what: 'A model that can pick and call tools on its own until the job is done.',
    fields: [model, { key: 'instructions', label: 'Instructions', kind: 'textarea', required: true }, { key: 'tools', label: 'Tools it may use', kind: 'text', placeholder: 'ghl.conversations:read, meta.ads:read' }, { key: 'effect', label: 'Most it can do', kind: 'select', options: ['read', 'write', 'send_to_lead', 'send_to_customer', 'spend', 'delete', 'deploy'], required: true }] },
  { type: 'tool', label: 'Tool', group: 'Tools and data', icon: 'Wrench', color: '#9333ea', inputs: ['in'], outputs: ['out'], source: 'agentflow',
    what: 'Runs one specific tool with set inputs (no model deciding).',
    fields: [{ key: 'tool', label: 'Tool', kind: 'text', placeholder: 'GOHIGHLEVEL_LIST_CONTACTS', required: true }, { key: 'card', label: 'Connector card (read first)', kind: 'text', placeholder: '.claude/connector-cards/ghl.md', required: true }, { key: 'effect', label: 'What it does', kind: 'select', options: ['read', 'write', 'send_to_lead', 'send_to_customer', 'spend', 'delete', 'deploy'], required: true }] },
  { type: 'retriever', label: 'Retriever', group: 'Tools and data', icon: 'Database', color: '#9333ea', inputs: ['in'], outputs: ['out'], source: 'agentflow',
    what: 'Looks up matching documents from a knowledge store.',
    fields: [{ key: 'store', label: 'Knowledge store', kind: 'text', placeholder: 'customers/<slug>/objections.md', required: true }, { key: 'k', label: 'How many results', kind: 'number' }] },
  { type: 'http', label: 'HTTP', group: 'Tools and data', icon: 'Globe', color: '#9333ea', inputs: ['in'], outputs: ['out'], source: 'agentflow',
    what: 'Calls a web address (API) directly.',
    fields: [{ key: 'method', label: 'Method', kind: 'select', options: ['GET', 'POST', 'PUT', 'DELETE'], required: true }, { key: 'url', label: 'URL', kind: 'text', required: true }, { key: 'effect', label: 'What it does', kind: 'select', options: ['read', 'write', 'send_to_lead', 'send_to_customer', 'spend', 'delete', 'deploy'], required: true }] },
  { type: 'condition', label: 'Condition', group: 'Logic', icon: 'GitBranch', color: '#d97706', inputs: ['in'], outputs: ['yes', 'no'], source: 'agentflow',
    what: 'If/else on a rule you write. Yes goes one way, no the other.',
    fields: [{ key: 'rule', label: 'If', kind: 'text', placeholder: 'score >= 0.9', required: true }] },
  { type: 'conditionAgent', label: 'Condition Agent', group: 'Logic', icon: 'Split', color: '#d97706', inputs: ['in'], outputs: ['a', 'b', 'c', 'd', 'e'], source: 'agentflow',
    what: 'A model reads the input and picks one of up to 5 paths (like which function a task is).',
    fields: [model, { key: 'paths', label: 'Paths (a to e)', kind: 'text', placeholder: 'lead_follow_up, website, ads, reporting, customer_update', required: true }] },
  { type: 'iteration', label: 'Iteration', group: 'Logic', icon: 'Repeat', color: '#d97706', inputs: ['in'], outputs: ['each', 'done'], source: 'agentflow',
    what: 'Runs the next steps once for every item in a list.',
    fields: [{ key: 'list', label: 'List to go through', kind: 'text', placeholder: 'test cases', required: true }] },
  { type: 'loop', label: 'Loop', group: 'Logic', icon: 'RotateCcw', color: '#d97706', inputs: ['in'], outputs: ['again', 'stop'], source: 'agentflow',
    what: 'Sends the flow back to an earlier step, up to a set number of times. Your hloop node.',
    fields: [{ key: 'max', label: 'Max rounds', kind: 'number', required: true }, { key: 'back_to', label: 'Back to step', kind: 'text', required: true }] },
  { type: 'humanInput', label: 'Human Input', group: 'People', icon: 'UserCheck', color: '#dc2626', inputs: ['in'], outputs: ['yes', 'no'], source: 'agentflow',
    what: 'Stops and waits for a person to approve or reject. Required before spend, send or delete.',
    fields: [{ key: 'who', label: 'Who approves', kind: 'text', placeholder: 'Alex', required: true }, { key: 'question', label: 'Question', kind: 'text', required: true }] },
  { type: 'directReply', label: 'Direct Reply', group: 'Start and end', icon: 'MessageSquare', color: '#16a34a', inputs: ['in'], outputs: [], source: 'agentflow',
    what: 'Sends a fixed answer back and ends the flow.',
    fields: [{ key: 'text', label: 'Reply', kind: 'textarea', required: true }] },
  { type: 'customFunction', label: 'Custom Function', group: 'Tools and data', icon: 'Code', color: '#9333ea', inputs: ['in'], outputs: ['out'], source: 'agentflow',
    what: 'Runs your own small script, like a scorer or a calculator.',
    fields: [{ key: 'command', label: 'Command', kind: 'text', placeholder: 'python3 tools/score_customer.py --all', required: true }, { key: 'effect', label: 'What it does', kind: 'select', options: ['read', 'write', 'send_to_lead', 'send_to_customer', 'spend', 'delete', 'deploy'], required: true }] },
  { type: 'executeFlow', label: 'Execute Flow', group: 'Tools and data', icon: 'Workflow', color: '#9333ea', inputs: ['in'], outputs: ['out'], source: 'agentflow',
    what: 'Runs another saved flow as one step.',
    fields: [{ key: 'flow', label: 'Flow name', kind: 'text', required: true }, { key: 'effect', label: 'Most the other flow can do', kind: 'select', options: ['read', 'write', 'send_to_lead', 'send_to_customer', 'spend', 'delete', 'deploy'], required: true }] },
  { type: 'stickyNote', label: 'Sticky Note', group: 'Notes', icon: 'StickyNote', color: '#ca8a04', inputs: [], outputs: [], source: 'agentflow',
    what: 'A note on the canvas. Does nothing when the flow runs.',
    fields: [{ key: 'text', label: 'Note', kind: 'textarea' }] },
  { type: 'judge', label: 'Judge', group: 'Improve (GEPA)', icon: 'Gavel', color: '#0d9488', inputs: ['in'], outputs: ['score'], source: 'alex',
    what: 'Grades an output: a score 0 to 1 plus written feedback on what was wrong.',
    fields: [{ key: 'checks', label: 'Rule checks', kind: 'text', placeholder: 'uses first name, no price, under 40 words, asks a question', required: true }, { key: 'judge', label: 'Model judge', kind: 'select', options: ['rules only', 'rules + claude'] }] },
  { type: 'compare', label: 'Compare', group: 'Improve (GEPA)', icon: 'Scale', color: '#0d9488', inputs: ['new', 'current'], outputs: ['better', 'not better'], source: 'alex',
    what: 'Compares the new prompt with the current one case by case. Keeps any version that is best on at least one case.',
    fields: [{ key: 'on', label: 'Compare on', kind: 'select', options: ['held-out cases', 'all cases'], required: true }] },
  { type: 'promote', label: 'Promote', group: 'Improve (GEPA)', icon: 'Rocket', color: '#0d9488', inputs: ['in'], outputs: [], source: 'alex',
    what: 'Makes the winning prompt live and saves the old one. Must come after a Human Input yes.',
    fields: [{ key: 'target', label: 'Live prompt file', kind: 'text', placeholder: 'gepa/jobs/<job>/prompt.md', required: true }] },
  { type: 'routeCustomer', label: 'Route to customer', group: 'Logic', icon: 'Route', color: '#d97706', inputs: ['in'], outputs: ['found', 'unknown'], source: 'alex',
    what: 'Finds which customer a task is for (location ID, account ID, website or name) and attaches their IDs. Never guesses.',
    fields: [{ key: 'by', label: 'Match by', kind: 'text', placeholder: 'location_id, ids, website, name', required: true }] },
];

export const KIT_BY_TYPE: Record<string, NodeKind> = Object.fromEntries(KIT.map((k) => [k.type, k]));
export const GROUPS: Group[] = ['Start and end', 'AI', 'Tools and data', 'Logic', 'People', 'Improve (GEPA)', 'Notes'];

export type FlowNode = { id: string; type: 'kit'; position: { x: number; y: number }; data: { kind: string; label: string; values: Record<string, string> } };
export type FlowEdge = { id: string; source: string; target: string; sourceHandle?: string | null; targetHandle?: string | null; label?: string };
export type Flow = { name: string; nodes: FlowNode[]; edges: FlowEdge[] };

export const APPROVAL_EFFECTS = ['spend', 'delete', 'send_to_customer', 'send_to_lead', 'deploy'];
export const MAX_LOOP = 20;
/** What each tool can do. Mirrors agency-os-kit/bots.json. "tool:effect" in an agent's tool list narrows it. */
export const TOOL_EFFECTS: Record<string, string[]> = {
  'ghl.conversations': ['read', 'send_to_lead'], 'ghl.contacts': ['read', 'write', 'delete'], 'ghl.customer_messages': ['read', 'send_to_customer'],
  'meta.ads': ['read', 'write', 'spend'], github: ['read', 'write'], cloudflare: ['read', 'deploy'], dashboard: ['read'],
};
/** Scripts a Custom Function node may run, and what each does. Anything else is unverified and gated. */
export const SCRIPTS: Record<string, string> = {
  'python3 tools/score_customer.py': 'read', 'python3 tools/metrics.py': 'read', 'python3 tools/route.py': 'read',
  'python3 tools/gate.py check': 'read', 'python3 tools/scan_customer.py': 'write', 'python3 tools/draft_update.py': 'write',
  'python3 tools/dashboard.py': 'write', 'python3 gepa/gepa.py loop': 'write', 'python3 gepa/gepa.py report': 'read',
};
export function scriptEffect(command: string): string | null {
  const c = command.trim().replace(/\s+/g, ' ');
  const hit = Object.keys(SCRIPTS).filter((k) => c === k || c.startsWith(k + ' ')).sort((a, b) => b.length - a.length)[0];
  return hit && !/[;&|`$<>]/.test(c) ? SCRIPTS[hit] : null;
}
/** Effects an agent's tool list allows. Unknown tools count as able to do anything that needs approval. */
export function toolEffects(list: string): { effects: string[]; problems: string[] } {
  const effects = new Set<string>(), problems: string[] = [];
  for (const raw of list.split(',').map((t) => t.trim()).filter(Boolean)) {
    const [tool, narrow] = raw.split(':').map((x) => x.trim());
    const can = TOOL_EFFECTS[tool];
    if (!can) { problems.push(`unknown tool ${tool}`); APPROVAL_EFFECTS.forEach((e) => effects.add(e)); continue; }
    if (narrow) { if (!can.includes(narrow)) problems.push(`${tool} cannot ${narrow}`); else effects.add(narrow); }
    else can.forEach((e) => effects.add(e));
  }
  return { effects: [...effects], problems };
}

/**
 * Plain-English problems that make the flow unsafe or broken. Empty list = OK.
 * Checks: one Start; every node reachable from Start; every input and output connected; required settings filled;
 * every cycle passes an Iteration or a Loop with 1 to 20 rounds; Promote and any spend/delete/send-to-customer/deploy
 * Tool only reachable through a Human Input "yes" (no path around it, and never from a "no"); agents with tools
 * only after Route to customer or Human Input; every Tool names the connector card it reads first.
 */
export function checkFlow(flow: Flow): string[] {
  const out: string[] = [];
  const byId = new Map(flow.nodes.map((n) => [n.id, n]));
  const kindOf = (id: string) => byId.get(id)?.data.kind ?? '';
  const name = (id: string) => byId.get(id)?.data.label ?? id;
  const live = flow.nodes.filter((n) => n.data.kind !== 'stickyNote');
  const starts = live.filter((n) => n.data.kind === 'start');
  if (starts.length !== 1) out.push(`Needs exactly one Start node (has ${starts.length}).`);

  for (const e of flow.edges) {
    if (!byId.has(e.source) || !byId.has(e.target)) { out.push(`Arrow ${e.id} points at a missing node.`); continue; }
    const s = KIT_BY_TYPE[kindOf(e.source)], t = KIT_BY_TYPE[kindOf(e.target)];
    if (s && s.outputs.length > 1 && (!e.sourceHandle || !s.outputs.includes(e.sourceHandle))) out.push(`${name(e.source)}: arrow must leave from a named output (${s.outputs.join(', ')}).`);
    if (t && t.inputs.length > 1 && (!e.targetHandle || !t.inputs.includes(e.targetHandle))) out.push(`${name(e.target)}: arrow must enter a named input (${t.inputs.join(', ')}).`);
  }
  const edges = flow.edges.filter((e) => byId.has(e.source) && byId.has(e.target));

  for (const n of live) {
    const k = KIT_BY_TYPE[n.data.kind];
    if (!k) { out.push(`${n.data.label}: unknown node type ${n.data.kind}.`); continue; }
    const into = edges.filter((e) => e.target === n.id), from = edges.filter((e) => e.source === n.id);
    if (k.inputs.length === 1 && !into.length) out.push(`${n.data.label}: nothing flows into it.`);
    for (const h of k.inputs.length > 1 ? k.inputs : []) if (!into.some((e) => e.targetHandle === h)) out.push(`${n.data.label}: input "${h}" is not connected.`);
    if (k.outputs.length && !from.length) out.push(`${n.data.label}: goes nowhere.`);
    const missing = k.fields.filter((f) => f.required && !String(n.data.values[f.key] ?? '').trim()).map((f) => f.label);
    if (missing.length) out.push(`${n.data.label}: fill in ${missing.join(', ')}.`);
    for (const f of k.fields) {
      const v = n.data.values[f.key];
      if (f.kind === 'select' && v && !f.options?.includes(v)) out.push(`${n.data.label}: "${v}" is not a valid choice for ${f.label}.`);
    }
    if (k.type === 'agent' && (n.data.values.tools ?? '').trim()) {
      const { effects, problems } = toolEffects(n.data.values.tools);
      problems.forEach((p) => out.push(`${n.data.label}: ${p}.`));
      const gated = effects.filter((x) => APPROVAL_EFFECTS.includes(x));
      if (gated.length && !gated.includes(n.data.values.effect ?? '')) out.push(`${n.data.label}: says "${n.data.values.effect}" but its tools can ${gated.join(', ')}. Narrow them (tool:read) or set the effect.`);
    }
    if (k.type === 'tool' && n.data.values.tool) {
      const can = TOOL_EFFECTS[n.data.values.tool];
      if (!can) out.push(`${n.data.label}: unknown tool ${n.data.values.tool}; add it to the tool list (bots.json) first.`);
      else if (n.data.values.effect && !can.includes(n.data.values.effect)) out.push(`${n.data.label}: ${n.data.values.tool} cannot ${n.data.values.effect}.`);
    }
    if (k.type === 'customFunction' && n.data.values.command) {
      const eff = scriptEffect(n.data.values.command);
      if (!eff) out.push(`${n.data.label}: "${n.data.values.command}" is not a registered script, so what it does cannot be checked.`);
      else if (n.data.values.effect && n.data.values.effect !== eff) out.push(`${n.data.label}: that script does "${eff}", not "${n.data.values.effect}".`);
    }
    if (k.type === 'executeFlow' && n.data.values.flow) {
      const nested = KNOWN_FLOWS[n.data.values.flow];
      if (!nested) out.push(`${n.data.label}: no saved flow called "${n.data.values.flow}", so what it does cannot be checked.`);
      else {
        const gated = flowEffects(nested()).filter((x) => APPROVAL_EFFECTS.includes(x));
        if (gated.length && !gated.includes(n.data.values.effect ?? '')) out.push(`${n.data.label}: the flow it runs can ${gated.join(', ')}; set the effect to match.`);
      }
    }
    if (k.type === 'http') {
      const m = n.data.values.method, eff = n.data.values.effect;
      if (m === 'DELETE' && eff !== 'delete') out.push(`${n.data.label}: a DELETE call must be marked "delete".`);
      if ((m === 'POST' || m === 'PUT') && eff === 'read') out.push(`${n.data.label}: a ${m} call changes things; it cannot be marked "read".`);
    }
    if (k.type === 'loop') {
      const max = Number(n.data.values.max);
      if (!Number.isInteger(max) || max < 1 || max > MAX_LOOP) out.push(`${n.data.label}: Max rounds must be a whole number from 1 to ${MAX_LOOP}.`);
    }
  }

  const bounded = (id: string) => kindOf(id) === 'iteration' || (kindOf(id) === 'loop' && Number(byId.get(id)!.data.values.max) >= 1 && Number(byId.get(id)!.data.values.max) <= MAX_LOOP);

  // Reachability from Start, optionally refusing to pass certain nodes or edges.
  const start = starts[0]?.id;
  const reach = (blockNode: (id: string) => boolean, blockEdge: (e: FlowEdge) => boolean = () => false) => {
    const seen = new Set<string>();
    if (!start) return seen;
    const stack = [start];
    while (stack.length) {
      const id = stack.pop()!;
      if (seen.has(id)) continue;
      seen.add(id);
      if (id !== start && blockNode(id)) continue;
      for (const e of edges) if (e.source === id && !blockEdge(e)) stack.push(e.target);
    }
    return seen;
  };
  const all = reach(() => false);
  for (const n of live) if (start && !all.has(n.id)) out.push(`${n.data.label}: cannot be reached from Start.`);

  // Approval: these nodes may only be reached through a Human Input "yes".
  const powers = (n: FlowNode) => {
    const declared = n.data.values.effect ?? '';
    const fromTools = n.data.kind === 'agent' ? toolEffects(n.data.values.tools ?? '').effects : [];
    const http = n.data.kind === 'http' && n.data.values.method === 'DELETE' ? ['delete'] : [];
    const unknownTool = n.data.kind === 'tool' && !TOOL_EFFECTS[n.data.values.tool ?? ''] ? APPROVAL_EFFECTS : [];
    const nestedFlow = n.data.kind === 'executeFlow' ? (KNOWN_FLOWS[n.data.values.flow ?? ''] ? flowEffects(KNOWN_FLOWS[n.data.values.flow!]()) : APPROVAL_EFFECTS) : [];
    const script = n.data.kind === 'customFunction' ? (scriptEffect(n.data.values.command ?? '') ? [scriptEffect(n.data.values.command ?? '')!] : APPROVAL_EFFECTS) : [];
    return [declared, ...fromTools, ...http, ...unknownTool, ...nestedFlow, ...script];
  };
  const effectful = ['tool', 'agent', 'http', 'customFunction', 'executeFlow'];
  const needsYes = live.filter((n) => n.data.kind === 'promote' || (effectful.includes(n.data.kind) && powers(n).some((x) => APPROVAL_EFFECTS.includes(x))));
  const aroundYes = reach(() => false, (e) => kindOf(e.source) === 'humanInput' && (e.sourceHandle ?? '') === 'yes');
  for (const n of needsYes) if (aroundYes.has(n.id)) out.push(`${n.data.label}: there is a path to it that skips Alex's "yes".`);
  const fromNo = new Set<string>();
  for (const e of edges) if (kindOf(e.source) === 'humanInput' && e.sourceHandle === 'no') {
    const stack = [e.target];
    while (stack.length) { const id = stack.pop()!; if (fromNo.has(id)) continue; fromNo.add(id); for (const x of edges) if (x.source === id) stack.push(x.target); }
  }
  for (const n of needsYes) if (fromNo.has(n.id)) out.push(`${n.data.label}: a Human Input "no" leads to it.`);

  // Agents with tools only after the customer was FOUND (or a person said yes): no path may skip both.
  const unguarded = reach(() => false, (e) => (kindOf(e.source) === 'routeCustomer' && e.sourceHandle === 'found') || (kindOf(e.source) === 'humanInput' && e.sourceHandle === 'yes'));
  for (const n of live) if (n.data.kind === 'agent' && (n.data.values.tools ?? '').trim() && unguarded.has(n.id))
    out.push(`${n.data.label}: an agent with tools must come after Route to customer "found" (or a Human Input "yes") on every path.`);

  // Iteration restart: going out "done" and coming back into the same Iteration restarts it forever.
  for (const it of live.filter((n) => n.data.kind === 'iteration')) {
    const seen = new Set<string>();
    const stack = edges.filter((x) => x.source === it.id && x.sourceHandle === 'done').map((x) => x.target);
    while (stack.length) {
      const id = stack.pop()!;
      if (seen.has(id) || (kindOf(id) === 'loop' && bounded(id))) continue;
      seen.add(id);
      for (const x of edges) if (x.source === id) stack.push(x.target);
    }
    if (seen.has(it.id)) out.push(`${it.data.label}: its "done" path leads back into it, so it would start over forever.`);
  }

  // Cycles: take out every Iteration and every Loop with a 1 to 20 limit. Any cycle still left could run forever.
  const rest = edges.filter((e) => !bounded(e.source) && !bounded(e.target));
  let index = 0;
  const idx = new Map<string, number>(), low = new Map<string, number>(), onStack = new Set<string>(), st: string[] = [];
  const strong = (v: string) => {
    idx.set(v, index); low.set(v, index); index++; st.push(v); onStack.add(v);
    for (const x of rest) if (x.source === v) {
      if (!idx.has(x.target)) { strong(x.target); low.set(v, Math.min(low.get(v)!, low.get(x.target)!)); }
      else if (onStack.has(x.target)) low.set(v, Math.min(low.get(v)!, idx.get(x.target)!));
    }
    if (low.get(v) === idx.get(v)) {
      const comp: string[] = [];
      let w: string;
      do { w = st.pop()!; onStack.delete(w); comp.push(w); } while (w !== v);
      if (comp.length > 1 || rest.some((x) => x.source === v && x.target === v))
        out.push(`A loop through ${comp.map(name).join(' → ')} has no Iteration or Loop limit, so it could run forever.`);
    }
  };
  for (const node of flow.nodes) if (!bounded(node.id) && !idx.has(node.id)) strong(node.id);
  return [...new Set(out)];
}

let seq = 0;
function n(kind: string, label: string, x: number, y: number, values: Record<string, string> = {}): FlowNode {
  return { id: `${kind}-${++seq}`, type: 'kit', position: { x, y }, data: { kind, label, values } };
}
function e(a: FlowNode, b: FlowNode, sourceHandle?: string, targetHandle?: string, label?: string): FlowEdge {
  return { id: `e-${a.id}-${b.id}-${sourceHandle ?? 'out'}-${targetHandle ?? 'in'}`, source: a.id, target: b.id, sourceHandle: sourceHandle ?? null, targetHandle: targetHandle ?? null, label };
}

export function gepaPreset(): Flow {
  seq = 0;
  const start = n('start', 'Test set (20 to 50 real cases)', 0, 0, { trigger: 'schedule', inputs: 'job, testset.jsonl' });
  const each = n('iteration', 'Each training case', -280, 150, { list: 'train cases' });
  const run = n('llm', 'Run best prompt so far', -560, 300, { model: 'claude-haiku-5-5', prompt: 'candidates/cN.md' });
  const judge = n('judge', 'Judge: score + feedback', -560, 460, { checks: 'uses first name, no price, under 40 words, asks a question', judge: 'rules only' });
  const reflect = n('llm', 'Reflect: rewrite from training feedback', -280, 300, { model: 'claude-sonnet-5-5', prompt: 'Fix what the judge said; keep what worked. Training feedback only.' });
  const runNew = n('llm', 'Run new prompt on held-out cases', -280, 460, { model: 'claude-haiku-5-5', prompt: 'candidates/new.md' });
  const judgeNew = n('judge', 'Judge new prompt', -280, 620, { checks: 'same checks', judge: 'rules only' });
  const runLive = n('llm', 'Run live prompt on held-out cases', 280, 300, { model: 'claude-haiku-5-5', prompt: 'prompt.md (live)' });
  const judgeLive = n('judge', 'Judge live prompt', 280, 460, { checks: 'same checks', judge: 'rules only' });
  const compare = n('compare', 'Compare new vs live', 0, 780, { on: 'held-out cases' });
  const loop = n('loop', 'Another round?', -420, 940, { max: '5', back_to: 'Reflect' });
  const ask = n('humanInput', 'Alex approves?', 160, 940, { who: 'Alex', question: 'Make this prompt live?' });
  const promote = n('promote', 'Promote to live', 160, 1100, { target: 'gepa/jobs/<job>/prompt.md' });
  const stop = n('directReply', 'Keep current prompt', -120, 1100, { text: 'No change made.' });
  const note = n('stickyNote', 'How it works', -900, 0, { text: 'Same loop as agency-os-kit/gepa/gepa.py. Run it there: gepa.py loop --job <job>. Nothing goes live without Alex.' });
  return {
    name: 'GEPA feedback loop',
    nodes: [start, each, run, judge, reflect, runNew, judgeNew, runLive, judgeLive, compare, loop, ask, promote, stop, note],
    edges: [e(start, each), e(each, run, 'each'), e(run, judge), e(judge, each, 'score', undefined, 'next case'), e(each, reflect, 'done'),
      e(reflect, runNew), e(runNew, judgeNew), e(judgeNew, compare, 'score', 'new'),
      e(start, runLive), e(runLive, judgeLive), e(judgeLive, compare, 'score', 'current'),
      e(compare, ask, 'better'), e(compare, loop, 'not better'), e(loop, reflect, 'again'), e(loop, stop, 'stop'),
      e(ask, promote, 'yes'), e(ask, stop, 'no')],
  };
}

export function routingPreset(): Flow {
  seq = 100;
  const start = n('start', 'Incoming task', 0, 0, { trigger: 'webhook', inputs: 'task, location_id' });
  const who = n('routeCustomer', 'Which customer?', 0, 150, { by: 'location_id, ids, website, name' });
  const unknown = n('directReply', 'Stop: customer unclear', 320, 150, { text: 'Could not tell which customer. Add the location ID.' });
  const fn = n('conditionAgent', 'Which function?', 0, 300, { model: 'claude-haiku-5-5', paths: 'lead_follow_up, website, ads, reporting, customer_update' });
  const sales = n('agent', 'Sales agent (lead follow-up)', -520, 470, { model: 'claude-sonnet-5-5', tools: 'ghl.conversations:read, ghl.contacts:read', instructions: 'customers/<slug>/AGENTS.md', effect: 'write' });
  const site = n('agent', 'Hermes site builder (website)', -260, 470, { model: 'claude-sonnet-5-5', tools: 'github:read, github:write, cloudflare:read', instructions: 'customers/<slug>/AGENTS.md', effect: 'write' });
  const ads = n('agent', 'Ads optimizer (ads)', 0, 470, { model: 'claude-sonnet-5-5', tools: 'meta.ads:read', instructions: 'customers/<slug>/AGENTS.md', effect: 'write' });
  const rep = n('agent', 'Reporter (reporting + updates)', 260, 470, { model: 'claude-sonnet-5-5', tools: 'dashboard:read, ghl.customer_messages:read', instructions: 'customers/<slug>/AGENTS.md', effect: 'read' });
  const risky = n('condition', 'Spend, send to customer, delete or deploy?', 0, 630, { rule: 'plan.requires_approval_for is not empty' });
  const ask = n('humanInput', 'Alex approves?', 260, 780, { who: 'Alex', question: 'Approve this action for this customer?' });
  const safe = n('tool', 'Do the safe step (read or write)', -200, 930, { tool: 'ghl.contacts', card: 'connector card for that tool', effect: 'write' });
  const approved = n('tool', 'Do the approved step (gate.py check passed)', 260, 930, { tool: 'meta.ads', card: 'connector card for that tool', effect: 'spend' });
  const no = n('directReply', 'Not approved: saved as draft', 560, 930, { text: 'Saved as a draft for Alex.' });
  const done = n('directReply', 'Report: done, proof, next step', 0, 1080, { text: 'What was done, the proof, and what is next.' });
  return {
    name: 'Lead routing (if/else)',
    nodes: [start, who, unknown, fn, sales, site, ads, rep, risky, ask, safe, approved, no, done],
    edges: [e(start, who), e(who, fn, 'found'), e(who, unknown, 'unknown'), e(fn, sales, 'a'), e(fn, site, 'b'), e(fn, ads, 'c'), e(fn, rep, 'd'), e(fn, rep, 'e'),
      e(sales, risky), e(site, risky), e(ads, risky), e(rep, risky), e(risky, ask, 'yes'), e(risky, safe, 'no'), e(ask, approved, 'yes'), e(ask, no, 'no'),
      e(safe, done), e(approved, done)],
  };
}

/** Every effect any node in a flow can have (declared, from tools, HTTP DELETE). */
export function flowEffects(flow: Flow): string[] {
  const out = new Set<string>();
  for (const n of flow.nodes) {
    if (n.data.values.effect) out.add(n.data.values.effect);
    if (n.data.kind === 'agent') toolEffects(n.data.values.tools ?? '').effects.forEach((e) => out.add(e));
    if (n.data.kind === 'http' && n.data.values.method === 'DELETE') out.add('delete');
    if (n.data.kind === 'promote') out.add('write');
  }
  return [...out];
}

/** Flows an Execute Flow node may run, by name. */
export const KNOWN_FLOWS: Record<string, () => Flow> = { 'GEPA feedback loop': gepaPreset, 'Lead routing (if/else)': routingPreset };
