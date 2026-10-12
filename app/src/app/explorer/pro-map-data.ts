/**
 * Pro Map: the layered "agent gateway" pattern big shops publish, beside Alex's system in the same shape.
 * Pro side = reference (published patterns, cited). Alex side = each status names the file that proves it.
 * Built 2026-10-12. Update a status only with a new source.
 */
export type ProStatus = 'ok' | 'partial' | 'gap' | 'reference';
export type ProNode = {
  id: string; label: string; sub: string; status: ProStatus; why: string; sources: string[];
  x: number; y: number; w?: number; h?: number; band?: boolean;
};
export type ProEdge = { id: string; source: string; target: string; kind: 'flow' | 'rail' | 'bypass'; label?: string };

const PRO_REFS = [
  'https://aws.amazon.com/blogs/opensource/governing-ai-assets-at-scale-with-mcp-gateway-and-registry/',
  'https://appropri8.com/blog/2026/04/30/agent-gateway-pattern-governance-mcp-tool-safety/',
  'https://agentgateway.dev/blog/2026-02-21-kill-switch/',
  'https://genaimaturity.net/whitepapers/agentic-ai-reference-architecture-2026',
];
const R = (why: string, extra: string[] = []) => ({ status: 'reference' as const, why, sources: [...extra, ...PRO_REFS] });

const SDK = '~/Documents/Codex/master-agent-operations-sdk';
// Column geometry (px). Pro starts at x=0, Alex's map at x=OFFSET.
const C = [0, 150, 300, 450, 600];
export const OFFSET = 1150;

function side(prefix: 'p' | 'y', x0: number) {
  const X = (i: number) => x0 + C[i];
  return { X, id: (s: string) => `${prefix}_${s}` };
}

const p = side('p', 0);
const y = side('y', OFFSET);

export const PRO_NODES: ProNode[] = [
  // ---------- Pro (reference) ----------
  { id: 'p_title', label: 'How big shops run it', sub: 'Published gateway pattern', x: p.X(0), y: -90, w: 990, h: 56, band: true, ...R('Composite of published reference maps; no single company shows its internal map.') },
  { id: 'p_band_agents', label: 'Agents', sub: '', x: p.X(0) - 20, y: 100, w: 740, h: 86, band: true, status: 'reference', why: 'Each agent with its own identity.', sources: PRO_REFS },
  { id: 'p_band_tools', label: '3. Tools', sub: '', x: p.X(0) - 20, y: 520, w: 740, h: 86, band: true, status: 'reference', why: 'Connectors and tool servers.', sources: PRO_REFS },
  { id: 'p_band_sys', label: '4. Systems', sub: '', x: p.X(0) - 20, y: 640, w: 740, h: 86, band: true, status: 'reference', why: 'Where the work lands.', sources: PRO_REFS },
  { id: 'p_band_rails', label: 'Rails (every layer)', sub: '', x: p.X(0) + 800, y: 100, w: 170, h: 626, band: true, status: 'reference', why: 'Cross-cutting controls.', sources: PRO_REFS },
  { id: 'p_people', label: 'People', sub: 'Owners and approvers', x: p.X(2), y: 0, ...R('Humans give goals and approve risky actions.') },
  { id: 'p_a1', label: 'Sales agent', sub: 'Own badge', x: p.X(0), y: 120, ...R('Each agent runs with its own identity.') },
  { id: 'p_a2', label: 'Support agent', sub: 'Own badge', x: p.X(1), y: 120, ...R('Each agent runs with its own identity.') },
  { id: 'p_a3', label: 'Ops agent', sub: 'Own badge', x: p.X(2), y: 120, ...R('Each agent runs with its own identity.') },
  { id: 'p_a4', label: 'Coding agent', sub: 'Own badge', x: p.X(3), y: 120, ...R('Each agent runs with its own identity.') },
  { id: 'p_a5', label: 'Research agent', sub: 'Own badge', x: p.X(4), y: 120, ...R('Each agent runs with its own identity.') },
  { id: 'p_band_orch', label: '1. Orchestration', sub: '', x: p.X(0) - 20, y: 220, w: 740, h: 110, band: true, ...R('Decides who does what, in what order.') },
  { id: 'p_router', label: 'Router', sub: 'Picks which agent', x: p.X(0), y: 270, ...R('Routes each request to the right specialist.') },
  { id: 'p_planner', label: 'Planner', sub: 'Breaks job into steps', x: p.X(1) + 40, y: 270, ...R('Turns a goal into ordered steps.') },
  { id: 'p_orch', label: 'Orchestrator', sub: 'Runs steps, retries', x: p.X(3) - 40, y: 270, ...R('Runs the steps with budgets, retries and handoffs.') },
  { id: 'p_checker', label: 'Checker', sub: 'Grades the work', x: p.X(4), y: 270, ...R('Evaluates output before it counts as done.') },
  { id: 'p_band_gw', label: '2. Gateway: the only door', sub: '', x: p.X(0) - 20, y: 370, w: 740, h: 110, band: true, ...R('Every tool call passes here; nothing goes around it.') },
  { id: 'p_who', label: 'Who is asking', sub: 'Checks the badge', x: p.X(0), y: 420, ...R('Authenticates the agent (JWT, OAuth, IdP).') },
  { id: 'p_allowed', label: 'Allowed?', sub: 'Tool, client, limits', x: p.X(1) + 40, y: 420, ...R('Policy check per agent, tool, arguments and tenant.') },
  { id: 'p_human', label: 'Needs a human?', sub: 'Risky = ask first', x: p.X(3) - 40, y: 420, ...R('Approval router: run now, auto-approve, or wait for a person.') },
  { id: 'p_broker', label: 'Tool broker', sub: 'Holds the keys', x: p.X(4), y: 420, ...R('Maps tool names to backends; agents never see keys.') },
  { id: 'p_mcp', label: 'MCP servers', sub: 'Grouped by task', x: p.X(0) + 40, y: 540, ...R('Tool servers behind the gateway.') },
  { id: 'p_api', label: 'Internal APIs', sub: 'Company systems', x: p.X(2), y: 540, ...R('Internal services behind the gateway.') },
  { id: 'p_sandbox', label: 'Sandboxes', sub: 'Run code safely', x: p.X(4) - 40, y: 540, ...R('Isolated code execution.') },
  { id: 'p_cA', label: 'Client A', sub: 'Own keys, own space', x: p.X(0), y: 660, ...R('Per-client walls: one client cannot reach another.', ['https://airbyte.com/agentic-data/ai-agents-for-agencies']) },
  { id: 'p_cB', label: 'Client B', sub: 'Own keys, own space', x: p.X(1) + 20, y: 660, ...R('Per-client walls.', ['https://pipeworks.ai/blog/case-study-agency-manages-50-clients']) },
  { id: 'p_cC', label: 'Client C', sub: 'Own keys, own space', x: p.X(3) - 20, y: 660, ...R('Per-client walls.') },
  { id: 'p_own', label: 'Own systems', sub: 'Files, finance', x: p.X(4), y: 660, ...R('The company\'s own systems.') },
  { id: 'p_r_badge', label: 'Badge per agent', sub: 'Okta, Entra login', x: p.X(4) + 215, y: 120, ...R('Identity provider issues each agent its own login.') },
  { id: 'p_r_registry', label: 'Registry', sub: 'Tools, owners, risk', x: p.X(4) + 215, y: 230, ...R('Catalog of allowed tools with risk tiers.') },
  { id: 'p_r_vault', label: 'Secrets vault', sub: 'Agents never see keys', x: p.X(4) + 215, y: 340, ...R('Keys live in a vault the gateway uses.') },
  { id: 'p_r_audit', label: 'Audit log', sub: 'Every call, even denied', x: p.X(4) + 215, y: 450, ...R('Who called what, with which arguments, when.') },
  { id: 'p_r_traces', label: 'Traces and evals', sub: 'Datadog, Langfuse', x: p.X(4) + 215, y: 560, ...R('OpenTelemetry traces and evaluations.') },
  { id: 'p_r_kill', label: 'Kill switch', sub: 'Pull one badge', x: p.X(4) + 215, y: 670, ...R('Revoke one agent\'s badge to stop only that agent.', ['https://agentgateway.dev/blog/2026-02-21-kill-switch/']) },

  // ---------- Alex (each status cites a source) ----------
  { id: 'y_title', label: 'Yours today', sub: 'Same layers, status from files', x: y.X(0), y: -90, w: 990, h: 56, band: true, status: 'ok', why: 'Each box below names the file that proves its color.', sources: ['app/src/app/explorer/pro-map-data.ts'] },
  { id: 'y_band_agents', label: 'Agents', sub: '', x: y.X(0) - 20, y: 100, w: 740, h: 86, band: true, status: 'ok', why: 'Your agents.', sources: ['app/src/app/explorer/pro-map-data.ts'] },
  { id: 'y_band_tools', label: '3. Tools', sub: '', x: y.X(0) - 20, y: 520, w: 740, h: 86, band: true, status: 'ok', why: 'Connectors and tool servers.', sources: ['app/src/app/explorer/pro-map-data.ts'] },
  { id: 'y_band_sys', label: '4. Systems', sub: '', x: y.X(0) - 20, y: 640, w: 740, h: 86, band: true, status: 'ok', why: 'Where the work lands.', sources: ['app/src/app/explorer/pro-map-data.ts'] },
  { id: 'y_band_rails', label: 'Rails (every layer)', sub: '', x: y.X(0) + 800, y: 100, w: 170, h: 626, band: true, status: 'ok', why: 'Cross-cutting controls.', sources: ['app/src/app/explorer/pro-map-data.ts'] },
  { id: 'y_you', label: 'You (Alex)', sub: 'Only approver', x: y.X(2), y: 0, status: 'ok', why: 'Approvals come only from Alex in chat.', sources: ['~/.agents/instructions/shared.md'] },
  { id: 'y_a1', label: 'Claude', sub: 'Your logins', x: y.X(0), y: 120, status: 'partial', why: 'Runs with Alex\'s shared Composio logins, no own badge.', sources: ['Composio connected accounts: one login per app (COMPOSIO_SEARCH_TOOLS, 2026-10-12)'] },
  { id: 'y_a2', label: 'Codex', sub: 'Your logins', x: y.X(1), y: 120, status: 'partial', why: 'Same shared logins.', sources: ['~/.codex/AGENTS.md'] },
  { id: 'y_a3', label: 'Cursor', sub: 'Your logins', x: y.X(2), y: 120, status: 'partial', why: 'Same shared logins; also has the raw Orgo MCP (can delete).', sources: ['~/.agents/tools/connectors/orgo_op.py (mentions npx orgo-mcp-server for Cursor)'] },
  { id: 'y_a4', label: 'Manus', sub: 'Your logins', x: y.X(3), y: 120, status: 'partial', why: 'Same shared logins.', sources: ['~/.agents/tools/cards/manus.md'] },
  { id: 'y_a5', label: 'Hermes', sub: 'On 7 Orgo computers', x: y.X(4), y: 120, status: 'partial', why: 'Agents live on Orgo computers; no per-agent badge at the gateway.', sources: [`${SDK}/docs/evidence/orgo/live-proof-2026-10-12.json`] },
  { id: 'y_band_orch', label: '1. Orchestration', sub: '', x: y.X(0) - 20, y: 220, w: 740, h: 110, band: true, status: 'ok', why: 'Director routes and plans, Conductor runs, Reviewer checks.', sources: ['~/.agents/skills/alex-director', '~/.agents/skills/alex-workflow-conductor'] },
  { id: 'y_director', label: 'Director', sub: 'Router + planner', x: y.X(0), y: 270, w: 270, status: 'ok', why: 'Does both router and planner jobs: picks the agent and the plan.', sources: ['~/.agents/skills/alex-director/SKILL.md'] },
  { id: 'y_conductor', label: 'Conductor', sub: 'Runs the plan', x: y.X(3) - 40, y: 270, status: 'ok', why: 'Orchestrator: runs steps through the controllers.', sources: ['~/.agents/skills/alex-workflow-conductor/SKILL.md'] },
  { id: 'y_reviewer', label: 'Reviewer', sub: 'Checks the proof', x: y.X(4), y: 270, status: 'ok', why: 'Checker: other model family reviews before done.', sources: ['AGENTS.md (Done needs the reviewer)'] },
  { id: 'y_band_gw', label: '2. SDK gateway (can be skipped today)', sub: '', x: y.X(0) - 20, y: 370, w: 740, h: 110, band: true, status: 'partial', why: 'The rule to use the SDK is an instruction, not enforced; agents can call Composio directly.', sources: ['~/.agents/instructions/shared.md'] },
  { id: 'y_badge', label: 'Badge check', sub: 'Not built', x: y.X(0), y: 420, status: 'gap', why: 'SDK cannot tell agents apart; all share Alex\'s logins.', sources: ['Composio connected accounts (one per app)'] },
  { id: 'y_allow', label: 'Allowlist', sub: 'Orgo, repairs, reads', x: y.X(1) + 40, y: 420, status: 'ok', why: 'Fixed allowlists for Orgo reads and SDK repairs; off-list refused.', sources: [`${SDK}/src/master_ops/adapters/orgo_fleet.py`, `${SDK}/tests/test_orgo_fleet.py`] },
  { id: 'y_approve', label: 'Your approval', sub: 'Orgo changes, sends', x: y.X(3) - 40, y: 420, status: 'partial', why: 'Exact-approval gate proven live for Orgo; not yet for GHL or Google writes.', sources: [`${SDK}/docs/evidence/orgo/live-proof-2026-10-12.json`] },
  { id: 'y_walls', label: 'Client walls', sub: 'Not built', x: y.X(4), y: 420, status: 'gap', why: 'No per-agent list of allowed client accounts.', sources: ['~/.agents/registry/connectors/ghl.json'] },
  { id: 'y_composio', label: 'Composio', sub: 'Keys from 1Password', x: y.X(0) + 40, y: 540, status: 'ok', why: 'Main connector hub; agents use it directly today.', sources: ['~/.agents/registry/connectors/'] },
  { id: 'y_orgo', label: 'Orgo route', sub: 'orgo_op.py', x: y.X(2), y: 540, status: 'ok', why: 'Owner route, key from 1Password at launch; SDK uses it.', sources: ['~/.agents/tools/connectors/orgo_op.py'] },
  { id: 'y_local', label: 'Local tools', sub: 'Mac, bridges', x: y.X(4) - 40, y: 540, status: 'ok', why: 'Local bridges (Codex, Claude, Observatory).', sources: [`${SDK}/src/master_ops/capabilities.py`] },
  { id: 'y_ghl', label: 'GHL (303)', sub: 'One login sees all', x: y.X(0), y: 660, status: 'gap', why: 'custom_ghl_oauth_crm reaches 303 locations with one login.', sources: ['~/.agents/registry/connectors/ghl.json'] },
  { id: 'y_google', label: 'Google, Ads', sub: 'Shared logins', x: y.X(1) + 20, y: 660, status: 'ok', why: 'Connected through Composio.', sources: ['~/.agents/registry/connectors/'] },
  { id: 'y_orgo7', label: 'Orgo (7)', sub: 'Seen live', x: y.X(3) - 20, y: 660, status: 'ok', why: '7 computers listed, uptime and disk read on each.', sources: [`${SDK}/docs/evidence/orgo/live-proof-2026-10-12.json`] },
  { id: 'y_files', label: 'Your files', sub: '~/Documents', x: y.X(4), y: 660, status: 'ok', why: 'Agents read ~/Documents, never iCloud (rule merged, PR #14).', sources: ['~/.agents/instructions/shared.md'] },
  { id: 'y_r_badge', label: 'Badge per agent', sub: 'Shared logins now', x: y.X(4) + 215, y: 120, status: 'gap', why: 'No separate login per agent.', sources: ['Composio connected accounts'] },
  { id: 'y_r_registry', label: 'Passports', sub: 'Registry', x: y.X(4) + 215, y: 230, status: 'ok', why: 'Connector passports plus SDK catalog.', sources: ['~/.agents/registry/connectors/', '~/.agents/registry/sdk/operations.json'] },
  { id: 'y_r_vault', label: '1Password vault', sub: 'Via Composio', x: y.X(4) + 215, y: 340, status: 'ok', why: 'Keys reach apps through Composio and owner routes only.', sources: ['~/.agents/tools/connectors/orgo_op.py'] },
  { id: 'y_r_audit', label: 'Audit log', sub: 'SDK calls only', x: y.X(4) + 215, y: 450, status: 'partial', why: 'SDK ledger records SDK calls; direct Composio calls are not in it.', sources: [`${SDK}/src/master_ops/operations.py`] },
  { id: 'y_r_traces', label: 'Observatory', sub: 'Read-only', x: y.X(4) + 215, y: 560, status: 'partial', why: 'Bounded reads and offline evals; no live traces of every call.', sources: ['director-observatory tool card'] },
  { id: 'y_r_kill', label: 'Kill switch', sub: 'None yet', x: y.X(4) + 215, y: 670, status: 'gap', why: 'Listed as missing in the gap audit (kill-switch runbook).', sources: ['~/.agents/docs/gap-audit-2026-10-11.md'] },
];

const flow = (a: string, b: string, label?: string): ProEdge => ({ id: `${a}-${b}`, source: a, target: b, kind: 'flow', label });

export const PRO_EDGES: ProEdge[] = [
  flow('p_people', 'p_band_agents'), flow('p_band_agents', 'p_band_orch', 'every request'),
  flow('p_router', 'p_planner'), flow('p_planner', 'p_orch'), flow('p_orch', 'p_checker'),
  flow('p_band_orch', 'p_band_gw', 'every tool call'),
  flow('p_who', 'p_allowed'), flow('p_allowed', 'p_human'), flow('p_human', 'p_broker'),
  flow('p_band_gw', 'p_band_tools'), flow('p_band_tools', 'p_band_sys'),

  flow('y_you', 'y_band_agents'), flow('y_band_agents', 'y_band_orch', 'every request'),
  flow('y_director', 'y_conductor'), flow('y_conductor', 'y_reviewer'),
  flow('y_band_orch', 'y_band_gw', 'SDK calls'),
  flow('y_badge', 'y_allow'), flow('y_allow', 'y_approve'), flow('y_approve', 'y_walls'),
  flow('y_band_gw', 'y_band_tools'), flow('y_band_tools', 'y_band_sys'),
  { id: 'y_bypass', source: 'y_band_agents', target: 'y_composio', kind: 'bypass', label: 'agents can skip the SDK' },
];
