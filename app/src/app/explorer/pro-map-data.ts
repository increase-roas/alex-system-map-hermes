/**
 * Pro Map v3: a solo operator with an agent team, run at pro level, beside Alex's system in the same layers.
 * Left = published solo patterns (cited). Right = Alex; every status names the file or check that proves it.
 * Layers top down: Customers, You, Where you talk, Front door, Agents (+ computer), Pointers, Orchestration,
 * Gateway, Tool know-how, Tools, Systems, Self-improving loop.
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
const MCR = '~/Projects/master-connector-repo/system';
const ORG = 'app/.data/org-map.json';
const SOLO = {
  repo: ['https://github.com/alejandrobailo/agents-anywhere', 'https://github.com/nielsmadan/agentic-coding'],
  skills: ['https://everpod.ai/guides/what-are-agent-skills', 'https://fenbs.ai/blog/agent-skills', 'https://www.codemancers.com/blog/how-agent-skills-work'],
  boxes: ['https://dev.to/greeves89/i-built-a-self-hosted-multi-agent-ai-platform-heres-what-i-learned-4a2p', 'https://ilirivezaj.com/projects/multi-agent-ai-framework'],
  gateway: ['https://www.docker.com/blog/mcp-toolkit-gateway-explained/', 'https://www.mrashutoshnigam.in/knowledge-hub/docker-mcp-toolkit/', 'https://www.docker.com/blog/dynamic-mcps-stop-hardcoding-your-agents-world/'],
  badge: ['https://signalovernoise.at/guides/the-scoped-service-account-setup-for-ai-agents/', 'https://1password.com/solutions/ai-agent-identity', 'https://1password.com/blog/introducing-1password-credential-broker'],
  fleet: ['https://download.plaud.ai/gyorgysh/myagens'],
  lead: ['https://www.anthropic.com/engineering/building-effective-agents', 'https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/', 'https://download.plaud.ai/gyorgysh/myagens'],
  tools: ['https://www.anthropic.com/engineering/writing-tools-for-agents', 'https://claude.com/resources/articles/building-agents-that-reach-production-systems-with-mcp'],
  pattern: ['https://appropri8.com/blog/2026/04/30/agent-gateway-pattern-governance-mcp-tool-safety/', 'https://agentgateway.dev/blog/2026-02-21-kill-switch/'],
};
const ref = (why: string, sources: string[]) => ({ status: 'reference' as const, why, sources });

/** Shared geometry, both sides. */
const Y = { title: -110, cust: 0, you: 130, ui: 220, front: 350, agents: 480, ptr: 610, orch: 760, gw: 900, know: 1040, tools: 1180, sys: 1310, evo: 1440 };
const AG = (i: number) => i * 125;
const AW = 112;
const CH = (i: number) => i * 187;   // 4 chips per row
type Item = Omit<ProNode, 'x'> & { dx?: number };

function place(x0: number, items: Item[]): ProNode[] {
  return items.map(({ dx, ...n }) => ({ ...n, x: x0 + (dx ?? 0) }));
}

function bands(s: 'p' | 'y', x0: number, status: ProStatus, why: string, sources: string[], labels: Record<string, string>, override: Record<string, ProStatus> = {}): ProNode[] {
  const b = (id: string, label: string, y: number, h: number, w = 760, dx = -10): ProNode =>
    ({ id: `${s}_band_${id}`, label, sub: '', x: x0 + dx, y, w, h, band: true, status: override[id] ?? status, why, sources });
  return [
    b('cust', 'Customers and projects', Y.cust, 100),
    b('ui', 'Where you talk to the AI', Y.ui, 100),
    b('front', labels.front, Y.front, 100),
    b('agents', 'Agents (and the computer each runs on)', Y.agents, 100),
    b('ptr', 'Pointers: the file each agent reads at start', Y.ptr, 120),
    b('orch', '1. Orchestration', Y.orch, 110),
    b('gw', labels.gw, Y.gw, 110),
    b('know', labels.know, Y.know, 110),
    b('tools', '3. Tools', Y.tools, 100),
    b('sys', '4. Systems', Y.sys, 100),
    b('evo', labels.evo, Y.evo, 120),
    b('lib', 'Library (pointers point here)', Y.ptr, 950, 250, -290),
    b('rails', 'Rails (every layer)', Y.ui, 1340, 200, 790),
  ];
}

// ---------------- Solo pro (reference) ----------------
const P = 0;
const proItems: Item[] = [
  ...['Client A', 'Client B', 'Client C'].map((name, i): Item => ({ id: `p_cu${i + 1}`, label: name, sub: 'Own workspace + board', y: Y.cust + 26, dx: CH(i), w: 170, ...ref('Each client is its own workspace with its own vault and project board.', [...SOLO.badge, ...SOLO.fleet]) })),
  { id: 'p_cu4', label: 'Own products', sub: 'Internal projects', y: Y.cust + 26, dx: CH(3), w: 170, ...ref('The owner\'s own products run as projects on the same board.', SOLO.fleet) },
  { id: 'p_you', label: 'You', sub: 'One person', y: Y.you, dx: 310, ...ref('One owner gives goals and approves risky actions.', SOLO.boxes) },
  { id: 'p_ui_phone', label: 'Phone chat', sub: 'Telegram: ask + approve', y: Y.ui + 26, dx: 120, w: 220, ...ref('One chat thread on the phone: ask for work, get approval requests, tap yes.', SOLO.boxes) },
  { id: 'p_ui_panel', label: 'Web panel', sub: 'Board, approvals, logs', y: Y.ui + 26, dx: 400, w: 220, ...ref('A private web panel to watch the board, approvals and logs.', SOLO.fleet) },
  { id: 'p_lead', label: 'Lead agent (front door)', sub: 'Talks to you, hands work out', y: Y.front + 30, dx: 220, w: 300, ...ref('You talk to one agent. It splits the job and hands pieces to the specialists, then reports back (orchestrator-workers / manager pattern).', SOLO.lead) },
  ...[['Builder', 'Laptop'], ['Research', 'Laptop'], ['Ops', 'Always-on box'], ['Sales', 'Always-on box'], ['Support', 'Always-on box']].map(([name, host], i): Item => ({
    id: `p_a${i + 1}`, label: `${name} agent`, sub: host, y: Y.agents + 26, dx: AG(i), w: AW, ...ref(`Runs on: ${host}. Own badge and tool profile; background agents each get their own container.`, [...SOLO.badge, ...SOLO.boxes]),
  })),
  ...[0, 1, 2, 3, 4].map((i): Item => ({ id: `p_ptr${i + 1}`, label: 'AGENTS.md', sub: 'Generated from repo', y: Y.ptr + 36, dx: AG(i), w: AW, ...ref('Facts that are always true load every turn; procedures stay in skills.', [...SOLO.skills, ...SOLO.repo]) })),
  { id: 'p_lib_repo', label: 'Home repo (git)', sub: 'Rules, skills, MCP config', y: Y.ptr + 36, dx: -270, w: 210, ...ref('One git repo holds the setup and is symlinked into every agent on every machine.', SOLO.repo) },
  { id: 'p_lib_skills', label: 'Skills', sub: '~/.agents/skills, one copy', y: Y.ptr + 206, dx: -270, w: 210, ...ref('One copy of each SKILL.md folder, linked into each app\'s skills folder.', SOLO.skills) },
  { id: 'p_lib_guides', label: 'Tool guides', sub: 'How to use each tool', y: Y.ptr + 376, dx: -270, w: 210, ...ref('Every tool carries a clear description and a guide; tools grouped by intent, not one per API endpoint.', SOLO.tools) },
  { id: 'p_lib_memory', label: 'Shared memory', sub: 'One store, all agents', y: Y.ptr + 546, dx: -270, w: 210, ...ref('What one agent learns, the fleet knows.', SOLO.fleet) },
  { id: 'p_lib_lessons', label: 'Lessons + evals', sub: 'Proven fixes, test tasks', y: Y.ptr + 716, dx: -270, w: 210, ...ref('Lessons and evaluation tasks that decide what gets promoted.', SOLO.fleet) },
  { id: 'p_board', label: 'Task board', sub: 'Plans into tasks', y: Y.orch + 36, dx: 0, w: 230, ...ref('The lead agent puts work on a kanban board.', SOLO.fleet) },
  { id: 'p_sched', label: 'Scheduler', sub: 'Runs, retries, failover', y: Y.orch + 36, dx: 265, w: 200, ...ref('Scheduler runs tasks, retries and fails over between models.', SOLO.fleet) },
  { id: 'p_review', label: 'Reviewer agent', sub: 'Checks before done', y: Y.orch + 36, dx: 500, w: 230, ...ref('A second agent checks output before it ships.', SOLO.pattern) },
  { id: 'p_g_badge', label: 'Agent badge', sub: '1Password per agent', y: Y.gw + 36, dx: CH(0), w: 170, ...ref('Service account per agent with one scoped vault; revoke to stop it.', SOLO.badge) },
  { id: 'p_g_profile', label: 'Tool profile', sub: 'Only its tools', y: Y.gw + 36, dx: CH(1), w: 170, ...ref('The gateway shows each agent only its profile\'s tools.', SOLO.gateway) },
  { id: 'p_g_ask', label: 'Ask on phone', sub: 'Risky = Telegram yes', y: Y.gw + 36, dx: CH(2), w: 170, ...ref('Approval requests go to the owner\'s phone.', SOLO.boxes) },
  { id: 'p_g_broker', label: 'Key broker', sub: 'Injects keys per call', y: Y.gw + 36, dx: CH(3), w: 170, ...ref('Keys stay in the vault and are injected only when a tool runs.', [...SOLO.gateway, ...SOLO.badge]) },
  { id: 'p_k1', label: 'Find the tool', sub: 'Search its profile', y: Y.know + 36, dx: CH(0), w: 170, ...ref('The agent searches only the tools in its profile.', SOLO.gateway) },
  { id: 'p_k2', label: 'Read its guide', sub: 'Description + skill', y: Y.know + 36, dx: CH(1), w: 170, ...ref('The tool description and its skill say when and how to use it.', SOLO.tools) },
  { id: 'p_k3', label: 'Call by intent', sub: 'Few, well-named tools', y: Y.know + 36, dx: CH(2), w: 170, ...ref('One intent-level tool beats chaining many raw API calls.', SOLO.tools) },
  { id: 'p_k4', label: 'Short result', sub: 'Trimmed, stable shape', y: Y.know + 36, dx: CH(3), w: 170, ...ref('Results come back compact so the agent stays on track.', SOLO.tools) },
  { id: 'p_t_gateway', label: 'Local MCP gateway', sub: 'Profiles, one door', y: Y.tools + 26, dx: 0, w: 230, ...ref('One local gateway in front of all MCP servers.', SOLO.gateway) },
  { id: 'p_t_conn', label: 'Connectors', sub: 'Composio or MCP', y: Y.tools + 26, dx: 250, w: 230, ...ref('App connectors behind the gateway.', SOLO.gateway) },
  { id: 'p_t_sandbox', label: 'Sandboxes', sub: 'Code runs isolated', y: Y.tools + 26, dx: 500, w: 230, ...ref('Code execution in isolated containers.', SOLO.boxes) },
  ...['Client A', 'Client B', 'Client C'].map((name, i): Item => ({ id: `p_s${i + 1}`, label: `${name} apps`, sub: 'Own vault, own keys', y: Y.sys + 26, dx: CH(i), w: 170, ...ref('Each client\'s apps use that client\'s own keys, so one cannot reach another.', SOLO.badge) })),
  { id: 'p_s_files', label: 'Own files', sub: 'Local, backed up', y: Y.sys + 26, dx: CH(3), w: 170, ...ref('Owner\'s files.', SOLO.repo) },
  { id: 'p_e1', label: 'Every run traced', sub: 'Steps, tools, cost', y: Y.evo + 36, dx: CH(0), w: 170, ...ref('Every run leaves a trace.', SOLO.fleet) },
  { id: 'p_e2', label: 'Scored', sub: 'Evals on test tasks', y: Y.evo + 36, dx: CH(1), w: 170, ...ref('Runs are scored against test tasks.', SOLO.fleet) },
  { id: 'p_e3', label: 'Lesson saved', sub: 'What worked, what broke', y: Y.evo + 36, dx: CH(2), w: 170, ...ref('Fixes become lessons.', SOLO.fleet) },
  { id: 'p_e4', label: 'Skill updated', sub: 'Proven = promoted', y: Y.evo + 36, dx: CH(3), w: 170, ...ref('The skills library grows as procedures prove themselves.', SOLO.fleet) },
  ...([
    ['badge', 'Badge per agent', 'Service account each', SOLO.badge],
    ['vault', 'Vault per agent', 'Blast radius = 1 vault', SOLO.badge],
    ['audit', 'Audit log', 'Every call, with who', SOLO.fleet],
    ['traces', 'Traces and evals', 'Watch every run', SOLO.fleet],
    ['kill', 'Kill switch', 'Revoke one token', SOLO.badge],
    ['sync', 'Config sync', 'Repo + symlinks', SOLO.repo],
  ] as [string, string, string, string[]][]).map(([id, label, sub, src], i): Item => ({
    id: `p_r_${id}`, label, sub, y: Y.ui + 40 + i * 220, dx: 805, w: 170, ...ref(`${label}: ${sub}.`, src),
  })),
];
const pro: ProNode[] = [
  { id: 'p_title', label: 'Solo pro: 1 person + agent team', sub: 'Published setups from people running their own fleets', x: P - 290, y: Y.title, w: 1280, h: 60, band: true, ...ref('A composite of published solo setups; each box links its source.', [...SOLO.repo, ...SOLO.fleet]) },
  ...bands('p', P, 'reference', 'Layer of the solo pro setup.', SOLO.pattern, {
    front: 'Front door: one agent you talk to', gw: '2. Gateway: the only door', know: 'How an agent knows to use a tool a certain way', evo: 'Self-improving loop',
  }),
  ...place(P, proItems),
];

// ---------------- Alex (each status cites a source) ----------------
const A = OFFSET;
const UIS: [string, string, ProStatus, string, string][] = [
  ['Claude app', 'Claude Code', 'ok', 'You talk to Claude Code directly.', 'hostname (2026-10-12): MacBook Pro'],
  ['Codex app', 'Codex threads', 'ok', 'You talk to Codex directly; the Conductor also drives Codex threads.', '~/.agents/skills/alex-workflow-conductor/SKILL.md'],
  ['Cursor', 'Editor chat', 'ok', 'You talk to Cursor directly.', '~/.cursor/rules/agent-routing.mdc'],
  ['ChatGPT', 'Chat app', 'ok', 'You talk to ChatGPT directly.', `${ORG} (ChatGPT node)`],
  ['Manus app', 'Manus tasks', 'ok', 'You talk to Manus directly.', '~/.agents/tools/cards/manus.md'],
  ['Telegram', 'To Javar', 'ok', 'You text Javar on Telegram; he texts contacts only with your approval.', '~/Documents/ChatGPT/Build (javar_text_contact, owner-approved texts from Telegram)'],
];
const AGENTS: [string, string, ProStatus, string, string][] = [
  ['Claude Code', 'MacBook Pro', 'partial', 'Runs on the MacBook with Alex\'s shared Composio logins; Composio guard hook stops spend, send, delete.', '~/.claude/settings.json (PreToolUse composio_guard, SessionStart drift_check)'],
  ['Codex', 'MacBook Pro', 'partial', 'Runs on the MacBook; shared logins; Codex Composio guard.', '~/.agents/tools/guards/codex_composio_guard.py'],
  ['Cursor', 'MacBook Pro', 'partial', 'Runs on the MacBook; shared logins; Cursor Composio guard; also has the raw Orgo MCP (can delete).', '~/.agents/tools/guards/cursor_composio_guard.py'],
  ['ChatGPT', 'OpenAI cloud', 'gap', 'Gets none of the rule files and has no guard.', `${ORG} (ChatGPT node: gets none of your rule files)`],
  ['Manus', 'Manus cloud', 'partial', 'Runs in Manus\'s own computer; own skills, not the shared rules; no Composio guard.', '~/.agents/tools/cards/manus.md'],
  ['Hermes (Javar)', 'Orgo EA', 'partial', 'Runs on Orgo EA (one of 7 Orgo computers); reads its own AGENTS.md there; no Composio guard.', `${SDK}/docs/evidence/orgo/live-proof-2026-10-12.json`],
];
const POINTERS: [string, string, ProStatus, string, string][] = [
  ['CLAUDE.md', '~/.claude, 185 skills', 'ok', 'Generated from ~/.agents/instructions; ~/.claude/skills has 185 links into ~/.agents/skills.', '~/.agents/tools/unify/build_instructions.py; ls ~/.claude/skills (185)'],
  ['AGENTS.md', '~/.codex, 132 skills', 'ok', 'Generated from ~/.agents/instructions; config.toml lists 132 [[skills.config]] paths into ~/.agents/skills.', '~/.codex/config.toml (132 skills.config)'],
  ['Cursor rule', '~/.cursor, 184 skills', 'ok', 'Cursor rule generated from ~/.agents/instructions; ~/.cursor/skills has 184 links.', '~/.cursor/rules/agent-routing.mdc; ls ~/.cursor/skills (184)'],
  ['None', 'Gets no rule files', 'gap', 'ChatGPT reads none of the shared rules.', `${ORG} (ChatGPT node)`],
  ['Manus skills', 'Not your shared rules', 'partial', 'Manus uses its own skills, not ~/.agents.', `${ORG} (Manus node: own Manus skills, not your shared rules)`],
  ['Hermes file', 'On Orgo, kept apart', 'partial', 'workspace/AGENTS.md links to /home/orgo/lil-smoove/home/.hermes/AGENTS.md; not built from ~/.agents.', `${SDK} orgo.read_computer EA list_dir (2026-10-12)`],
];
const RAILS: [string, string, string, ProStatus, string, string][] = [
  ['badge', 'Badge per agent', 'Shared logins now', 'gap', 'No separate login per agent.', 'Composio connected accounts (one per app)'],
  ['vault', '1Password', 'One vault for all', 'partial', 'Keys reach apps through Composio and owner routes, but one shared vault, not one per agent.', '~/.agents/tools/connectors/orgo_op.py'],
  ['audit', 'Audit log', 'SDK calls only', 'partial', 'SDK ledger records SDK calls; direct Composio calls are not in it.', `${SDK}/src/master_ops/operations.py`],
  ['traces', 'Observatory', 'Read-only evidence', 'partial', 'Bounded reads and offline evals; no live trace of every call.', 'director-observatory tool card'],
  ['kill', 'Kill switch', 'None yet', 'gap', 'Kill-switch runbook listed as missing.', '~/.agents/docs/gap-audit-2026-10-11.md'],
  ['sync', 'Drift check + CI', 'Every app start', 'ok', 'SessionStart drift check in Claude, Codex, Cursor; agents-home CI on every PR; weekly docs-freshness check.', '~/.agents/tools/guards/drift_check.py; ~/.agents/.github/workflows/docs-freshness.yml'],
];
const alexItems: Item[] = [
  { id: 'y_cu1', label: 'Dynamite / Nat. Sanitation', sub: '7 missions', y: Y.cust + 26, dx: CH(0), w: 170, status: 'partial', why: '7 missions; some need you, some on watch.', sources: [`${ORG} (missions, project Dynamite Lighting / Natural Sanitation)`] },
  { id: 'y_cu2', label: 'Increase ROAS clients', sub: '303 GHL accounts', y: Y.cust + 26, dx: CH(1), w: 170, status: 'partial', why: 'Client sub-accounts reached through one GHL login; no per-client workspace.', sources: ['~/.agents/registry/connectors/ghl.json'] },
  { id: 'y_cu3', label: 'Personal / system', sub: '7 missions', y: Y.cust + 26, dx: CH(2), w: 170, status: 'partial', why: '7 system missions (connector consolidation, Orgo route, shared brain, setup parity).', sources: [`${ORG} (missions, project Personal / system)`] },
  { id: 'y_cu4', label: 'Parked', sub: '7 missions', y: Y.cust + 26, dx: CH(3), w: 170, status: 'ok', why: 'Parked missions, kept for later.', sources: [`${ORG} (Parked missions)`] },
  { id: 'y_you', label: 'You (Alex)', sub: 'Only approver', y: Y.you, dx: 310, status: 'ok', why: 'Approvals come only from Alex in chat.', sources: ['~/.agents/instructions/shared.md'] },
  ...UIS.map(([label, sub, status, why, src], i): Item => ({ id: `y_ui${i + 1}`, label, sub, status, why, sources: [src], y: Y.ui + 26, dx: AG(i), w: AW })),
  ...AGENTS.map(([label, sub, status, why, src], i): Item => ({ id: `y_a${i + 1}`, label, sub, status, why, sources: [src], y: Y.agents + 26, dx: AG(i), w: AW })),
  ...POINTERS.map(([label, sub, status, why, src], i): Item => ({ id: `y_ptr${i + 1}`, label, sub, status, why, sources: [src], y: Y.ptr + 36, dx: AG(i), w: AW })),
  { id: 'y_lib_rules', label: 'Rule source', sub: '~/.agents/instructions (6)', y: Y.ptr + 36, dx: -270, w: 210, status: 'ok', why: 'One source; build_instructions.py writes CLAUDE.md, AGENTS.md and the Cursor rule. Git: increase-roas/agents-home with CI.', sources: ['~/.agents/instructions/', '~/.agents/tools/unify/build_instructions.py'] },
  { id: 'y_lib_skills', label: 'Skills (185)', sub: '~/.agents/skills, one copy', y: Y.ptr + 206, dx: -270, w: 210, status: 'ok', why: '185 skill folders, linked into Claude (185) and Cursor (184), listed in Codex config (132).', sources: ['ls ~/.agents/skills (185)', '~/.agents/tools/unify/skill-lifecycle.md'] },
  { id: 'y_lib_guides', label: 'Tool cards (25)', sub: '+ 27 passports', y: Y.ptr + 376, dx: -270, w: 210, status: 'ok', why: 'Each app has a routing card (which login, which tool, what needs approval) and a passport (docs, fixes). Cards are served to every AI through Composio app rules.', sources: ['~/.agents/tools/cards/ (25)', '~/.agents/registry/connectors/ (27)'] },
  { id: 'y_lib_memory', label: 'Memory', sub: 'Mem0, Director state', y: Y.ptr + 546, dx: -270, w: 210, status: 'partial', why: 'Mem0 via SDK plus Director state files; not one store all agents read.', sources: [`${SDK}/docs/MEMORY.md`, '~/Alex-Director/DIRECTOR_STATE.md'] },
  { id: 'y_lib_lessons', label: 'Lessons (65)', sub: 'system/lessons.md + evals', y: Y.ptr + 716, dx: -270, w: 210, status: 'ok', why: '65 lessons, plus golden and held-out test tasks.', sources: [`${MCR}/lessons.md`, `${MCR}/evals/golden-tasks.md`] },
  { id: 'y_director', label: 'Director', sub: 'Routes, plans, dispatches', y: Y.orch + 36, dx: 0, w: 230, status: 'ok', why: 'Picks the agent and the plan, dispatches Codex threads through the bridge; state in ~/Alex-Director. Not your front door: you still open each app yourself.', sources: ['~/.agents/skills/alex-director/SKILL.md', '~/Alex-Director/DIRECTOR_STATE.md'] },
  { id: 'y_conductor', label: 'Conductor', sub: 'Runs via Codex threads', y: Y.orch + 36, dx: 265, w: 200, status: 'ok', why: 'Runs the plan through the controllers.', sources: ['~/.agents/skills/alex-workflow-conductor/SKILL.md'] },
  { id: 'y_reviewer', label: 'Reviewer', sub: 'Other model checks', y: Y.orch + 36, dx: 500, w: 230, status: 'ok', why: 'Other model family reviews before done.', sources: ['~/Projects/alex-system-map/AGENTS.md'] },
  { id: 'y_g_guard', label: 'Composio guards', sub: 'Stop spend, send, delete', y: Y.gw + 36, dx: CH(0), w: 170, status: 'partial', why: 'Hooks in Claude Code, Codex and Cursor stop spend, client messages, deletes, DNS, deploys until Alex says yes. Manus, ChatGPT, Hermes have none.', sources: ['~/.agents/tools/guards/composio_guard.py', '~/.agents/tools/guards/codex_composio_guard.py', '~/.agents/tools/guards/cursor_composio_guard.py'] },
  { id: 'y_g_allow', label: 'SDK allowlist', sub: 'Orgo, repairs, reads', y: Y.gw + 36, dx: CH(1), w: 170, status: 'ok', why: 'Off-list Orgo checks and secret paths refused.', sources: [`${SDK}/src/master_ops/adapters/orgo_fleet.py`] },
  { id: 'y_g_approve', label: 'Your approval', sub: 'Exact yes, Orgo live', y: Y.gw + 36, dx: CH(2), w: 170, status: 'partial', why: 'Exact-approval gate proven live for Orgo; GHL and Google writes still rely on the guards.', sources: [`${SDK}/docs/evidence/orgo/live-proof-2026-10-12.json`] },
  { id: 'y_g_walls', label: 'Badge + client walls', sub: 'Not built', y: Y.gw + 36, dx: CH(3), w: 170, status: 'gap', why: 'No per-agent login and no per-agent client list.', sources: ['~/.agents/registry/connectors/ghl.json'] },
  { id: 'y_k1', label: 'Find the tool', sub: 'COMPOSIO_SEARCH_TOOLS', y: Y.know + 36, dx: CH(0), w: 170, status: 'ok', why: 'Agent searches Composio by task in plain words.', sources: ['~/.agents/tools/cards/composio.md'] },
  { id: 'y_k2', label: 'Read the app card', sub: 'GET_APP_RULES first', y: Y.know + 36, dx: CH(1), w: 170, status: 'ok', why: 'Before the first call to an app, the agent reads its card through CUSTOM_IR_NOTES_GET_APP_RULES. Only agents that follow your shared rules do this.', sources: ['~/.agents/instructions/shared.md', '~/.agents/tools/cards/'] },
  { id: 'y_k3', label: 'Call, named login', sub: 'MULTI_EXECUTE + account', y: Y.know + 36, dx: CH(2), w: 170, status: 'ok', why: 'Every Composio call names its login; the guard refuses multi-login toolkits with no login named.', sources: ['~/.agents/tools/guards/composio_guard.py'] },
  { id: 'y_k4', label: 'Example: GHL', sub: 'Workflows = GHL Command', y: Y.know + 36, dx: CH(3), w: 170, status: 'ok', why: 'The GHL card routes workflow edits to custom_ghl_command_builder and CRM work to custom_ghl_oauth_crm (the OAuth app cannot edit workflows, tested 2026-10-11).', sources: ['~/.agents/tools/cards/ghl.md', '~/.agents/registry/connectors/ghl.json'] },
  { id: 'y_t_composio', label: 'Composio', sub: '25 cards, keys via 1Password', y: Y.tools + 26, dx: 0, w: 230, status: 'ok', why: 'Main connector hub; every call names its login.', sources: ['~/.agents/tools/cards/composio.md'] },
  { id: 'y_t_orgo', label: 'Orgo route', sub: 'orgo_op.py', y: Y.tools + 26, dx: 250, w: 230, status: 'ok', why: 'Owner route; key read from 1Password at launch.', sources: ['~/.agents/tools/connectors/orgo_op.py'] },
  { id: 'y_t_local', label: 'Local bridges', sub: 'Codex, Claude, Observatory', y: Y.tools + 26, dx: 500, w: 230, status: 'ok', why: 'Local MCP bridges used by the SDK.', sources: [`${SDK}/src/master_ops/capabilities.py`] },
  { id: 'y_s_ghl', label: 'GHL (303)', sub: 'One login sees all', y: Y.sys + 26, dx: CH(0), w: 170, status: 'gap', why: 'custom_ghl_oauth_crm reaches 303 locations with one login.', sources: ['~/.agents/registry/connectors/ghl.json'] },
  { id: 'y_s_google', label: 'Google, Meta Ads', sub: 'Shared logins', y: Y.sys + 26, dx: CH(1), w: 170, status: 'ok', why: 'Connected through Composio.', sources: ['~/.agents/registry/connectors/'] },
  { id: 'y_s_orgo', label: 'Orgo (7)', sub: 'Seen live', y: Y.sys + 26, dx: CH(2), w: 170, status: 'ok', why: '7 computers, uptime and disk read on each.', sources: [`${SDK}/docs/evidence/orgo/live-proof-2026-10-12.json`] },
  { id: 'y_s_files', label: '~/Documents', sub: 'Never iCloud', y: Y.sys + 26, dx: CH(3), w: 170, status: 'ok', why: 'Agents read ~/Documents, never iCloud (rule merged, agents-home PR #14).', sources: ['~/.agents/instructions/shared.md'] },
  { id: 'y_e1', label: 'Correction or failure', sub: 'You correct, a task fails', y: Y.evo + 36, dx: CH(0), w: 170, status: 'partial', why: 'Lessons start when you correct an agent or a task fails; there is no trace of every run yet.', sources: ['~/.agents/skills/capture-lessons/SKILL.md'] },
  { id: 'y_e2', label: 'capture-lessons', sub: 'Writes lessons.md', y: Y.evo + 36, dx: CH(1), w: 170, status: 'ok', why: 'Turns evidence into 1 to 5 lessons, updating matches instead of duplicating. Only agents with the shared skills run it.', sources: ['~/.agents/skills/capture-lessons/SKILL.md', `${MCR}/lessons.md`] },
  { id: 'y_e3', label: 'Weekly tune-up', sub: 'Tests on golden tasks', y: Y.evo + 36, dx: CH(2), w: 170, status: 'ok', why: 'Merges lessons, checks drift, tests changes on golden tasks; last snapshot 2026-10-12 00:12.', sources: ['~/.agents/skills/weekly-tuneup/SKILL.md', `${MCR}/snapshots/2026-10-12_0012_tuneup`] },
  { id: 'y_e4', label: 'Your yes, then update', sub: 'Proposal to rules/skills', y: Y.evo + 36, dx: CH(3), w: 170, status: 'partial', why: 'Writes a proposal for your approval before rules or skills change. Latest proposal file: 2026-10-01.', sources: [`${MCR}/proposals/`] },
  ...RAILS.map(([id, label, sub, status, why, src], i): Item => ({ id: `y_r_${id}`, label, sub, status, why, sources: [src], y: Y.ui + 40 + i * 220, dx: 805, w: 170 })),
];
const alex: ProNode[] = [
  { id: 'y_title', label: 'Yours today', sub: 'Same layers; click any box for the file that proves it', x: A - 290, y: Y.title, w: 1280, h: 60, band: true, status: 'ok', why: 'Every status on this side names its source.', sources: ['app/src/app/explorer/pro-map-data.ts'] },
  ...bands('y', A, 'ok', 'Layer of your system.', ['app/src/app/explorer/pro-map-data.ts'], {
    front: 'Front door: none yet, you open each app yourself', gw: '2. Gateway (guards + SDK; not the only door yet)', know: 'How your agents know to use a tool a certain way', evo: 'Self-improving loop (needs your yes)',
  }, { front: 'gap', gw: 'partial', evo: 'partial' }),
  ...place(A, alexItems),
];

export const PRO_NODES: ProNode[] = [...pro, ...alex];

const flow = (a: string, b: string, label?: string): ProEdge => ({ id: `${a}-${b}`, source: a, target: b, kind: 'flow', label });
const link = (a: string, b: string, label: string | undefined, sh: 'ls' | 'rs', th: 'l' | 'r'): ProEdge => ({ id: `${a}-${b}`, source: a, target: b, kind: 'link', label, sh, th });
const chain = (ids: string[]) => ids.slice(1).map((id, i) => flow(ids[i], id));

function lower(s: 'p' | 'y', n: number): ProEdge[] {
  const e: ProEdge[] = [];
  for (let i = 1; i <= n; i++) e.push(flow(`${s}_a${i}`, `${s}_ptr${i}`, i === 1 ? 'reads at start' : undefined));
  e.push(flow(`${s}_band_ptr`, `${s}_band_orch`, 'then works through'), flow(`${s}_band_orch`, `${s}_band_gw`, 'tool calls'),
    flow(`${s}_band_gw`, `${s}_band_know`), flow(`${s}_band_know`, `${s}_band_tools`), flow(`${s}_band_tools`, `${s}_band_sys`),
    flow(`${s}_band_sys`, `${s}_band_evo`, 'every run feeds'));
  return e;
}

export const PRO_EDGES: ProEdge[] = [
  // Solo pro: you talk to ONE agent, it hands work out.
  flow('p_band_cust', 'p_you', 'asks'), flow('p_you', 'p_band_ui'),
  flow('p_ui_phone', 'p_lead'), flow('p_ui_panel', 'p_lead'),
  ...[1, 2, 3, 4, 5].map((i) => flow('p_lead', `p_a${i}`, i === 3 ? 'hands out work' : undefined)),
  ...lower('p', 5),
  ...chain(['p_board', 'p_sched', 'p_review']), ...chain(['p_g_badge', 'p_g_profile', 'p_g_ask', 'p_g_broker']),
  ...chain(['p_k1', 'p_k2', 'p_k3', 'p_k4']), ...chain(['p_e1', 'p_e2', 'p_e3', 'p_e4']),
  link('p_lib_repo', 'p_band_ptr', 'builds', 'rs', 'l'),
  link('p_band_ptr', 'p_lib_skills', 'points to', 'ls', 'r'),
  link('p_band_know', 'p_lib_guides', 'reads guide', 'ls', 'r'),
  link('p_lib_memory', 'p_band_orch', 'recall', 'rs', 'l'),
  link('p_band_evo', 'p_lib_lessons', 'saves + promotes', 'ls', 'r'),

  // Alex: you talk to EACH app directly; no front door yet.
  flow('y_band_cust', 'y_you', 'asks'),
  ...[1, 2, 3, 4, 5, 6].map((i) => flow('y_you', `y_ui${i}`)),
  ...[1, 2, 3, 4, 5, 6].map((i) => flow(`y_ui${i}`, `y_a${i}`, i === 1 ? 'each app, separately' : undefined)),
  ...lower('y', 6),
  ...chain(['y_director', 'y_conductor', 'y_reviewer']), ...chain(['y_g_guard', 'y_g_allow', 'y_g_approve', 'y_g_walls']),
  ...chain(['y_k1', 'y_k2', 'y_k3', 'y_k4']), ...chain(['y_e1', 'y_e2', 'y_e3', 'y_e4']),
  link('y_lib_rules', 'y_band_ptr', 'builds 3 of 6', 'rs', 'l'),
  link('y_band_ptr', 'y_lib_skills', 'points to', 'ls', 'r'),
  link('y_band_know', 'y_lib_guides', 'reads card', 'ls', 'r'),
  link('y_lib_memory', 'y_band_orch', 'recall', 'rs', 'l'),
  link('y_band_evo', 'y_lib_lessons', 'saves lessons', 'ls', 'r'),
  { id: 'y_bypass', source: 'y_band_agents', target: 'y_t_composio', kind: 'bypass', label: '3 agents: no guard', sh: 'ls', th: 'l' },
];
