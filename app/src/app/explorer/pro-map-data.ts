/**
 * Pro Map v2: a solo operator with an agent team, run at pro level, beside Alex's system in the same layers.
 * Left = published solo patterns (cited). Right = Alex; every status names the file or check that proves it.
 * Layers top down: You, Computers, Agents, Pointers, Orchestration, Gateway, Tools, Systems.
 * Left column = Library (what pointers point to). Right column = Rails (apply to every layer).
 * Built 2026-10-12. Change a status only with a new source.
 */
export type ProStatus = 'ok' | 'partial' | 'gap' | 'reference';
export type ProNode = {
  id: string; label: string; sub: string; status: ProStatus; why: string; sources: string[];
  x: number; y: number; w?: number; h?: number; band?: boolean;
};
export type ProEdge = {
  id: string; source: string; target: string; kind: 'flow' | 'link' | 'bypass'; label?: string;
  sh?: 'ls' | 'rs'; th?: 'l' | 'r';
};

export const OFFSET = 1420;
const SDK = '~/Documents/Codex/master-agent-operations-sdk';
const SOLO = {
  repo: ['https://github.com/alejandrobailo/agents-anywhere', 'https://github.com/nielsmadan/agentic-coding'],
  skills: ['https://everpod.ai/guides/what-are-agent-skills', 'https://fenbs.ai/blog/agent-skills', 'https://www.codemancers.com/blog/how-agent-skills-work'],
  boxes: ['https://dev.to/greeves89/i-built-a-self-hosted-multi-agent-ai-platform-heres-what-i-learned-4a2p', 'https://ilirivezaj.com/projects/multi-agent-ai-framework'],
  gateway: ['https://www.docker.com/blog/mcp-toolkit-gateway-explained/', 'https://www.mrashutoshnigam.in/knowledge-hub/docker-mcp-toolkit/'],
  badge: ['https://signalovernoise.at/guides/the-scoped-service-account-setup-for-ai-agents/', 'https://1password.com/solutions/ai-agent-identity', 'https://1password.com/blog/introducing-1password-credential-broker'],
  fleet: ['https://download.plaud.ai/gyorgysh/myagens'],
  pattern: ['https://appropri8.com/blog/2026/04/30/agent-gateway-pattern-governance-mcp-tool-safety/', 'https://agentgateway.dev/blog/2026-02-21-kill-switch/'],
};
const ref = (why: string, sources: string[]) => ({ status: 'reference' as const, why, sources });

/** Shared geometry, both sides. */
const Y = { title: -110, you: 0, comp: 90, agents: 210, ptr: 330, orch: 470, gw: 600, tools: 730, sys: 850 };
const AG = (i: number) => i * 125;
const AW = 112;
type Item = Omit<ProNode, 'x'> & { dx?: number };

function place(x0: number, items: Item[]): ProNode[] {
  return items.map(({ dx, ...n }) => ({ ...n, x: x0 + (dx ?? 0) }));
}

function bands(s: 'p' | 'y', x0: number, status: ProStatus, why: string, sources: string[], gwLabel: string): ProNode[] {
  const b = (id: string, label: string, y: number, h: number, w = 760, dx = -10): ProNode =>
    ({ id: `${s}_band_${id}`, label, sub: '', x: x0 + dx, y, w, h, band: true, status: id === 'gw' && s === 'y' ? 'partial' : status, why, sources });
  return [
    b('comp', 'Computers: where each agent runs', Y.comp, 100),
    b('agents', 'Agents', Y.agents, 100),
    b('ptr', 'Pointers: the file each agent reads at start', Y.ptr, 120),
    b('orch', '1. Orchestration', Y.orch, 110),
    b('gw', gwLabel, Y.gw, 110),
    b('tools', '3. Tools', Y.tools, 100),
    b('sys', '4. Systems', Y.sys, 100),
    b('lib', 'Library (pointers point here)', Y.ptr, 620, 250, -290),
    b('rails', 'Rails (every layer)', Y.comp, 860, 200, 790),
  ];
}

// ---------------- Solo pro (reference) ----------------
const P = 0;
const proItems: Item[] = [
  { id: 'p_you', label: 'You', sub: 'Goals and approvals', y: Y.you, dx: 310, ...ref('One owner gives goals and approves risky actions from the phone.', SOLO.boxes) },
  { id: 'p_c_laptop', label: 'Your laptop', sub: 'Builder, Research', y: Y.comp + 26, dx: 0, w: 237, ...ref('Interactive agents run on the owner\'s machine.', SOLO.boxes) },
  { id: 'p_c_box', label: 'Always-on box', sub: 'One container per agent', y: Y.comp + 26, dx: 250, w: 362, ...ref('Each background agent gets its own container: own files, own tools, real isolation.', SOLO.boxes) },
  ...['Builder', 'Research', 'Ops', 'Sales', 'Support'].map((name, i): Item => ({
    id: `p_a${i + 1}`, label: `${name} agent`, sub: 'Own badge', y: Y.agents + 26, dx: AG(i), w: AW, ...ref('Each agent has its own identity and tool profile.', SOLO.badge),
  })),
  ...[0, 1, 2, 3, 4].map((i): Item => ({
    id: `p_ptr${i + 1}`, label: 'AGENTS.md', sub: 'Generated from repo', y: Y.ptr + 36, dx: AG(i), w: AW, ...ref('Facts that are always true load every turn; procedures stay in skills.', [...SOLO.skills, ...SOLO.repo]),
  })),
  { id: 'p_lib_repo', label: 'Home repo (git)', sub: 'Rules, skills, MCP config', y: Y.ptr + 36, dx: -270, w: 210, ...ref('One git repo holds the setup and is symlinked into every agent on every machine.', SOLO.repo) },
  { id: 'p_lib_skills', label: 'Skills', sub: '~/.agents/skills, one copy', y: Y.ptr + 176, dx: -270, w: 210, ...ref('One copy of each SKILL.md folder, linked into each app\'s skills folder.', SOLO.skills) },
  { id: 'p_lib_registry', label: 'Tool registry', sub: 'Profile per agent', y: Y.ptr + 316, dx: -270, w: 210, ...ref('Named tool profiles; each agent connects to its own profile.', SOLO.gateway) },
  { id: 'p_lib_memory', label: 'Shared memory', sub: 'One store, all agents', y: Y.ptr + 456, dx: -270, w: 210, ...ref('What one agent learns, the fleet knows.', SOLO.fleet) },
  { id: 'p_lead', label: 'Lead agent', sub: 'Routes and plans', y: Y.orch + 36, dx: 0, w: 230, ...ref('One lead agent picks who does what and plans the steps.', SOLO.fleet) },
  { id: 'p_board', label: 'Task board', sub: 'Runs, retries, schedule', y: Y.orch + 36, dx: 265, w: 200, ...ref('Kanban board and scheduler run the steps.', SOLO.fleet) },
  { id: 'p_review', label: 'Reviewer agent', sub: 'Checks before done', y: Y.orch + 36, dx: 500, w: 230, ...ref('A second agent checks output before it ships.', SOLO.pattern) },
  { id: 'p_g_badge', label: 'Agent badge', sub: '1Password per agent', y: Y.gw + 36, dx: 0, w: 170, ...ref('Service account per agent with one scoped vault; revoke to stop it.', SOLO.badge) },
  { id: 'p_g_profile', label: 'Tool profile', sub: 'Only its tools', y: Y.gw + 36, dx: 187, w: 170, ...ref('The gateway shows each agent only its profile\'s tools.', SOLO.gateway) },
  { id: 'p_g_ask', label: 'Ask on phone', sub: 'Risky = Telegram yes', y: Y.gw + 36, dx: 374, w: 170, ...ref('Approval requests go to the owner\'s phone.', SOLO.boxes) },
  { id: 'p_g_broker', label: 'Key broker', sub: 'Injects keys per call', y: Y.gw + 36, dx: 561, w: 170, ...ref('Keys stay in the keychain or vault and are injected only when a tool runs.', [...SOLO.gateway, ...SOLO.badge]) },
  { id: 'p_t_gateway', label: 'Local MCP gateway', sub: 'Profiles, one door', y: Y.tools + 26, dx: 0, w: 230, ...ref('One local gateway in front of all MCP servers.', SOLO.gateway) },
  { id: 'p_t_conn', label: 'Connectors', sub: 'Composio or MCP', y: Y.tools + 26, dx: 250, w: 230, ...ref('App connectors behind the gateway.', SOLO.gateway) },
  { id: 'p_t_sandbox', label: 'Sandboxes', sub: 'Code runs isolated', y: Y.tools + 26, dx: 500, w: 230, ...ref('Code execution in isolated containers.', SOLO.boxes) },
  ...['Client A', 'Client B', 'Client C'].map((name, i): Item => ({
    id: `p_s${i + 1}`, label: name, sub: 'Own vault, own keys', y: Y.sys + 26, dx: i * 190, w: 170, ...ref('Each client has its own vault and keys, so one cannot reach another.', SOLO.badge),
  })),
  { id: 'p_s_files', label: 'Own files', sub: 'Local, backed up', y: Y.sys + 26, dx: 570, w: 170, ...ref('Owner\'s files.', SOLO.repo) },
  ...([
    ['badge', 'Badge per agent', 'Service account each', SOLO.badge],
    ['vault', 'Vault per agent', 'Blast radius = 1 vault', SOLO.badge],
    ['audit', 'Audit log', 'Every call, with who', SOLO.fleet],
    ['traces', 'Traces and evals', 'Watch every run', SOLO.fleet],
    ['kill', 'Kill switch', 'Revoke one token', SOLO.badge],
    ['sync', 'Config sync', 'Repo + symlinks', SOLO.repo],
  ] as [string, string, string, string[]][]).map(([id, label, sub, src], i): Item => ({
    id: `p_r_${id}`, label, sub, y: Y.comp + 40 + i * 135, dx: 805, w: 170, ...ref(`${label}: ${sub}.`, src),
  })),
];
const pro: ProNode[] = [
  { id: 'p_title', label: 'Solo pro: 1 person + agent team', sub: 'Published setups from people running their own fleets', x: P - 290, y: Y.title, w: 1280, h: 60, band: true, ...ref('A composite of published solo setups; each box links its source.', [...SOLO.repo, ...SOLO.fleet]) },
  ...bands('p', P, 'reference', 'Layer of the solo pro setup.', SOLO.pattern, '2. Gateway: the only door'),
  ...place(P, proItems),
];

// ---------------- Alex (each status cites a source) ----------------
const A = OFFSET;
const AGENTS: [string, string, ProStatus, string, string][] = [
  ['Claude Code', 'Your logins', 'partial', 'Runs with Alex\'s shared Composio logins; Composio guard hook stops spend, send, delete.', '~/.claude/settings.json (PreToolUse composio_guard, SessionStart drift_check)'],
  ['Codex', 'Your logins', 'partial', 'Shared logins; Codex Composio guard.', '~/.agents/tools/guards/codex_composio_guard.py'],
  ['Cursor', 'Your logins', 'partial', 'Shared logins; Cursor Composio guard; also has the raw Orgo MCP (can delete).', '~/.agents/tools/guards/cursor_composio_guard.py'],
  ['ChatGPT', 'No guard', 'gap', 'Gets none of the rule files and has no guard.', 'app/.data/org-map.json (ChatGPT node: gets none of your rule files)'],
  ['Manus', 'No guard', 'partial', 'Own Manus skills, not the shared rules; no Composio guard.', '~/.agents/tools/cards/manus.md'],
  ['Hermes (Javar)', 'No guard', 'partial', 'Runs on Orgo EA; reads its own AGENTS.md there; no Composio guard.', `${SDK} orgo.read_computer EA list_dir /home/orgo/lil-smoove/workspace (2026-10-12)`],
];
const POINTERS: [string, string, ProStatus, string, string][] = [
  ['CLAUDE.md', '~/.claude, 185 skills', 'ok', 'Generated from ~/.agents/instructions; ~/.claude/skills has 185 links into ~/.agents/skills.', '~/.agents/tools/unify/build_instructions.py; ls ~/.claude/skills (185)'],
  ['AGENTS.md', '~/.codex, 132 skills', 'ok', 'Generated from ~/.agents/instructions; config.toml lists 132 [[skills.config]] paths into ~/.agents/skills.', '~/.codex/config.toml (132 skills.config)'],
  ['Cursor rule', '~/.cursor, 184 skills', 'ok', 'Cursor rule generated from ~/.agents/instructions; ~/.cursor/skills has 184 links.', '~/.cursor/rules/agent-routing.mdc; ls ~/.cursor/skills (184)'],
  ['None', 'Gets no rule files', 'gap', 'ChatGPT reads none of the shared rules.', 'app/.data/org-map.json (ChatGPT node)'],
  ['Manus skills', 'Not your shared rules', 'partial', 'Manus uses its own skills, not ~/.agents.', 'app/.data/org-map.json (Manus node: own Manus skills, not your shared rules)'],
  ['Hermes file', 'On Orgo, kept apart', 'partial', 'workspace/AGENTS.md links to /home/orgo/lil-smoove/home/.hermes/AGENTS.md; not built from ~/.agents.', `${SDK} orgo.read_computer EA list_dir (2026-10-12)`],
];
const RAILS: [string, string, string, ProStatus, string, string][] = [
  ['badge', 'Badge per agent', 'Shared logins now', 'gap', 'No separate login per agent.', 'Composio connected accounts (one per app)'],
  ['vault', '1Password', 'One vault for all', 'partial', 'Keys reach apps through Composio and owner routes, but one shared vault, not one per agent.', '~/.agents/tools/connectors/orgo_op.py'],
  ['audit', 'Audit log', 'SDK calls only', 'partial', 'SDK ledger records SDK calls; direct Composio calls are not in it.', `${SDK}/src/master_ops/operations.py`],
  ['traces', 'Observatory', 'Read-only evidence', 'partial', 'Bounded reads and offline evals; no live trace of every call.', 'director-observatory tool card'],
  ['kill', 'Kill switch', 'None yet', 'gap', 'Kill-switch runbook listed as missing.', '~/.agents/docs/gap-audit-2026-10-11.md'],
  ['sync', 'Drift check + CI', 'Every app start', 'ok', 'SessionStart drift check in Claude, Codex, Cursor; agents-home CI on every PR.', '~/.agents/tools/guards/drift_check.py'],
];
const alexItems: Item[] = [
  { id: 'y_you', label: 'You (Alex)', sub: 'Only approver', y: Y.you, dx: 310, status: 'ok', why: 'Approvals come only from Alex in chat.', sources: ['~/.agents/instructions/shared.md'] },
  { id: 'y_c_mac', label: 'MacBook Pro', sub: 'Claude Code, Codex, Cursor, ChatGPT', y: Y.comp + 26, dx: 0, w: 487, status: 'ok', why: 'Seen live: Alexs-MacBook-Pro.local runs these apps.', sources: ['hostname (2026-10-12)'] },
  { id: 'y_c_manus', label: 'Manus cloud', sub: 'Its own computer', y: Y.comp + 26, dx: 500, w: AW, status: 'ok', why: 'Manus runs in its own cloud computer.', sources: ['~/.agents/tools/cards/manus.md'] },
  { id: 'y_c_orgo', label: 'Orgo x7', sub: 'EA = Javar', y: Y.comp + 26, dx: 625, w: AW, status: 'ok', why: '7 Orgo computers listed and read live.', sources: [`${SDK}/docs/evidence/orgo/live-proof-2026-10-12.json`] },
  ...AGENTS.map(([label, sub, status, why, src], i): Item => ({ id: `y_a${i + 1}`, label, sub, status, why, sources: [src], y: Y.agents + 26, dx: AG(i), w: AW })),
  ...POINTERS.map(([label, sub, status, why, src], i): Item => ({ id: `y_ptr${i + 1}`, label, sub, status, why, sources: [src], y: Y.ptr + 36, dx: AG(i), w: AW })),
  { id: 'y_lib_rules', label: 'Rule source', sub: '~/.agents/instructions (6)', y: Y.ptr + 36, dx: -270, w: 210, status: 'ok', why: 'One source; build_instructions.py writes CLAUDE.md, AGENTS.md and the Cursor rule. Git: increase-roas/agents-home with CI.', sources: ['~/.agents/instructions/', '~/.agents/tools/unify/build_instructions.py'] },
  { id: 'y_lib_skills', label: 'Skills (185)', sub: '~/.agents/skills, one copy', y: Y.ptr + 176, dx: -270, w: 210, status: 'ok', why: '185 skill folders, linked into Claude (185) and Cursor (184), listed in Codex config (132).', sources: ['ls ~/.agents/skills (185)', '~/.agents/tools/unify/skill-lifecycle.md'] },
  { id: 'y_lib_passports', label: 'Passports (27)', sub: '+ 25 tool cards', y: Y.ptr + 316, dx: -270, w: 210, status: 'ok', why: '27 connector passports and 25 tool cards (routing rules per app), also served through Composio app rules.', sources: ['~/.agents/registry/connectors/ (27)', '~/.agents/tools/cards/ (25)'] },
  { id: 'y_lib_memory', label: 'Memory', sub: 'Mem0, Director state', y: Y.ptr + 456, dx: -270, w: 210, status: 'partial', why: 'Mem0 via SDK plus Director state files; not one store all agents read.', sources: [`${SDK}/docs/MEMORY.md`, '~/Alex-Director/DIRECTOR_STATE.md'] },
  { id: 'y_director', label: 'Director', sub: 'Routes + plans', y: Y.orch + 36, dx: 0, w: 230, status: 'ok', why: 'Picks the agent and the plan; state in ~/Alex-Director.', sources: ['~/.agents/skills/alex-director/SKILL.md', '~/Alex-Director/DIRECTOR_STATE.md'] },
  { id: 'y_conductor', label: 'Conductor', sub: 'Runs via Codex threads', y: Y.orch + 36, dx: 265, w: 200, status: 'ok', why: 'Runs the plan through the controllers.', sources: ['~/.agents/skills/alex-workflow-conductor/SKILL.md'] },
  { id: 'y_reviewer', label: 'Reviewer', sub: 'Other model checks', y: Y.orch + 36, dx: 500, w: 230, status: 'ok', why: 'Other model family reviews before done.', sources: ['~/Projects/alex-system-map/AGENTS.md'] },
  { id: 'y_g_guard', label: 'Composio guards', sub: 'Stop spend, send, delete', y: Y.gw + 36, dx: 0, w: 170, status: 'partial', why: 'Hooks in Claude Code, Codex and Cursor stop spend, client messages, deletes, DNS, deploys until Alex says yes. Manus, ChatGPT, Hermes have none.', sources: ['~/.agents/tools/guards/composio_guard.py', '~/.agents/tools/guards/codex_composio_guard.py', '~/.agents/tools/guards/cursor_composio_guard.py'] },
  { id: 'y_g_allow', label: 'SDK allowlist', sub: 'Orgo, repairs, reads', y: Y.gw + 36, dx: 187, w: 170, status: 'ok', why: 'Off-list Orgo checks and secret paths refused.', sources: [`${SDK}/src/master_ops/adapters/orgo_fleet.py`] },
  { id: 'y_g_approve', label: 'Your approval', sub: 'Exact yes, Orgo live', y: Y.gw + 36, dx: 374, w: 170, status: 'partial', why: 'Exact-approval gate proven live for Orgo; GHL and Google writes still rely on the guards.', sources: [`${SDK}/docs/evidence/orgo/live-proof-2026-10-12.json`] },
  { id: 'y_g_walls', label: 'Badge + client walls', sub: 'Not built', y: Y.gw + 36, dx: 561, w: 170, status: 'gap', why: 'No per-agent login and no per-agent client list.', sources: ['~/.agents/registry/connectors/ghl.json'] },
  { id: 'y_t_composio', label: 'Composio', sub: '25 cards, keys via 1Password', y: Y.tools + 26, dx: 0, w: 230, status: 'ok', why: 'Main connector hub; every call names its login.', sources: ['~/.agents/tools/cards/composio.md'] },
  { id: 'y_t_orgo', label: 'Orgo route', sub: 'orgo_op.py', y: Y.tools + 26, dx: 250, w: 230, status: 'ok', why: 'Owner route; key read from 1Password at launch.', sources: ['~/.agents/tools/connectors/orgo_op.py'] },
  { id: 'y_t_local', label: 'Local bridges', sub: 'Codex, Claude, Observatory', y: Y.tools + 26, dx: 500, w: 230, status: 'ok', why: 'Local MCP bridges used by the SDK.', sources: [`${SDK}/src/master_ops/capabilities.py`] },
  { id: 'y_s_ghl', label: 'GHL (303)', sub: 'One login sees all', y: Y.sys + 26, dx: 0, w: 170, status: 'gap', why: 'custom_ghl_oauth_crm reaches 303 locations with one login.', sources: ['~/.agents/registry/connectors/ghl.json'] },
  { id: 'y_s_google', label: 'Google, Meta Ads', sub: 'Shared logins', y: Y.sys + 26, dx: 190, w: 170, status: 'ok', why: 'Connected through Composio.', sources: ['~/.agents/registry/connectors/'] },
  { id: 'y_s_orgo', label: 'Orgo (7)', sub: 'Seen live', y: Y.sys + 26, dx: 380, w: 170, status: 'ok', why: '7 computers, uptime and disk read on each.', sources: [`${SDK}/docs/evidence/orgo/live-proof-2026-10-12.json`] },
  { id: 'y_s_files', label: '~/Documents', sub: 'Never iCloud', y: Y.sys + 26, dx: 570, w: 170, status: 'ok', why: 'Agents read ~/Documents, never iCloud (rule merged, agents-home PR #14).', sources: ['~/.agents/instructions/shared.md'] },
  ...RAILS.map(([id, label, sub, status, why, src], i): Item => ({ id: `y_r_${id}`, label, sub, status, why, sources: [src], y: Y.comp + 40 + i * 135, dx: 805, w: 170 })),
];
const alex: ProNode[] = [
  { id: 'y_title', label: 'Yours today', sub: 'Same layers; click any box for the file that proves it', x: A - 290, y: Y.title, w: 1280, h: 60, band: true, status: 'ok', why: 'Every status on this side names its source.', sources: ['app/src/app/explorer/pro-map-data.ts'] },
  ...bands('y', A, 'ok', 'Layer of your system.', ['app/src/app/explorer/pro-map-data.ts'], '2. Gateway (guards + SDK; not the only door yet)'),
  ...place(A, alexItems),
];

export const PRO_NODES: ProNode[] = [...pro, ...alex];

const flow = (a: string, b: string, label?: string): ProEdge => ({ id: `${a}-${b}`, source: a, target: b, kind: 'flow', label });
const link = (a: string, b: string, label: string | undefined, sh: 'ls' | 'rs', th: 'l' | 'r'): ProEdge => ({ id: `${a}-${b}`, source: a, target: b, kind: 'link', label, sh, th });

function side(s: 'p' | 'y', hosts: [string, number[]][], n: number, extra: ProEdge[]): ProEdge[] {
  const e: ProEdge[] = [flow(`${s}_you`, `${s}_band_comp`)];
  for (const [host, idx] of hosts) for (const i of idx) e.push(flow(host, `${s}_a${i}`, i === idx[0] ? 'runs' : undefined));
  for (let i = 1; i <= n; i++) e.push(flow(`${s}_a${i}`, `${s}_ptr${i}`, i === 1 ? 'reads at start' : undefined));
  e.push(flow(`${s}_band_ptr`, `${s}_band_orch`, 'then works through'));
  e.push(flow(`${s}_band_orch`, `${s}_band_gw`, 'tool calls'), flow(`${s}_band_gw`, `${s}_band_tools`), flow(`${s}_band_tools`, `${s}_band_sys`));
  return [...e, ...extra];
}

export const PRO_EDGES: ProEdge[] = [
  ...side('p', [['p_c_laptop', [1, 2]], ['p_c_box', [3, 4, 5]]], 5, [
    flow('p_lead', 'p_board'), flow('p_board', 'p_review'),
    flow('p_g_badge', 'p_g_profile'), flow('p_g_profile', 'p_g_ask'), flow('p_g_ask', 'p_g_broker'),
    link('p_lib_repo', 'p_band_ptr', 'builds', 'rs', 'l'),
    link('p_band_ptr', 'p_lib_skills', 'points to', 'ls', 'r'),
    link('p_band_ptr', 'p_lib_registry', 'points to', 'ls', 'r'),
    link('p_lib_memory', 'p_band_orch', 'recall', 'rs', 'l'),
  ]),
  ...side('y', [['y_c_mac', [1, 2, 3, 4]], ['y_c_manus', [5]], ['y_c_orgo', [6]]], 6, [
    flow('y_director', 'y_conductor'), flow('y_conductor', 'y_reviewer'),
    flow('y_g_guard', 'y_g_allow'), flow('y_g_allow', 'y_g_approve'), flow('y_g_approve', 'y_g_walls'),
    link('y_lib_rules', 'y_band_ptr', 'builds 3 of 6', 'rs', 'l'),
    link('y_band_ptr', 'y_lib_skills', 'points to', 'ls', 'r'),
    link('y_band_ptr', 'y_lib_passports', 'points to', 'ls', 'r'),
    link('y_lib_memory', 'y_band_orch', 'recall', 'rs', 'l'),
    { id: 'y_bypass', source: 'y_band_agents', target: 'y_t_composio', kind: 'bypass', label: '3 agents: no guard', sh: 'ls', th: 'l' },
  ]),
];
