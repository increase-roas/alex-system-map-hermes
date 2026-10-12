/**
 * Pro Map v4: top to bottom = the order a request actually happens (13 steps).
 * Left = Anthropic's own published way; every box links an Anthropic page (no other vendors).
 * Right = Alex, same 13 steps; every status names the file or check that proves it.
 * Every band says what the trace records at that step. Click a box for "how to build it" + sources.
 * Built 2026-10-12. Change a status only with a new source.
 */
import { PRO_DETAILS, type ProDetail } from './pro-map-details';
import { PRO_EXAMPLES, type ProExamples } from './pro-map-examples';
import { PRO_MORE, type More } from './pro-map-more';
import { PRO_FILL } from './pro-map-fill';
import { FIXES } from './pro-map-fixes';

export type FullDetail = ProDetail & ProExamples & Pick<More, 'myths'>;

export type ProStatus = 'ok' | 'partial' | 'gap' | 'reference';
export type ProNode = {
  badge?: string;
  id: string; label: string; sub: string; status: ProStatus; why: string; sources: string[];
  how?: string[]; trace?: string; tag?: string; detail?: FullDetail;
  x: number; y: number; w?: number; h?: number; band?: boolean;
};
export type ProEdge = {
  id: string; source: string; target: string; kind: 'flow' | 'link' | 'bypass' | 'loop'; label?: string;
  sh?: 'ls' | 'rs'; th?: 'l' | 'r'; offset?: number;
};

export const OFFSET = 1420;
const SDK = '~/Documents/Codex/master-agent-operations-sdk';
const MCR = '~/Projects/master-connector-repo/system';
const ORG = 'app/.data/org-map.json';

/** Anthropic sources only (checked 2026-10-12). */
const ANT = {
  mem: 'https://code.claude.com/docs/en/memory',
  steer: 'https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more',
  ctx: 'https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models',
  skills: 'https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices',
  skillUse: 'https://claude.com/blog/lessons-from-building-claude-code-how-we-use-skills',
  sub: 'https://code.claude.com/docs/en/sub-agents',
  subBlog: 'https://claude.com/blog/subagents-in-claude-code',
  research: 'https://www.anthropic.com/engineering/multi-agent-research-system',
  harness: 'https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents',
  harnessDesign: 'https://www.anthropic.com/engineering/harness-design-long-running-apps',
  patterns: 'https://claude.com/blog/multi-agent-coordination-patterns',
  effective: 'https://www.anthropic.com/engineering/building-effective-agents',
  managed: 'https://platform.claude.com/docs/en/managed-agents/multiagent-orchestration',
  hosting: 'https://code.claude.com/docs/en/agent-sdk/hosting',
  tools: 'https://www.anthropic.com/engineering/writing-tools-for-agents',
  mcpProd: 'https://claude.com/resources/articles/building-agents-that-reach-production-systems-with-mcp',
  mcp: 'https://code.claude.com/docs/en/mcp',
  perm: 'https://code.claude.com/docs/en/permissions',
  hooks: 'https://code.claude.com/docs/en/hooks',
  mon: 'https://code.claude.com/docs/en/monitoring-usage',
  evals: 'https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents',
  code: 'https://claude.com/claude-code',
  context: 'https://support.claude.com/en/articles/14553240-give-claude-context-claude-md-and-better-prompts',
};

/** The 13 steps, in the order they happen. */
/** v6 (Codex review 2026-10-12): one chat, top down. The lead reads its files first, picks the client early, helpers are optional, results loop back. */
const STEPS = ['ask', 'ui', 'front', 'client', 'plan', 'delegate', 'know', 'gw', 'run', 'verify', 'report', 'learn'] as const;
type Step = (typeof STEPS)[number];
const BAND_H: Partial<Record<Step, number>> = { front: 125, client: 110, delegate: 115, gw: 125, learn: 125 };
const Y = {} as Record<string, number>;
let cursor = 0;
for (const s of STEPS) { Y[s] = cursor; cursor += (BAND_H[s] ?? 100) + 30; }
const BOTTOM = cursor;
type YMap = Record<string, number>;
function yLayout(steps: readonly string[], bandH: Record<string, number>): { y: YMap; bottom: number } {
  const y: YMap = {}; let c = 0;
  for (const st of steps) { y[st] = c; c += (bandH[st] ?? 100) + 30; }
  return { y, bottom: c };
}
/** Version 2 (middle map) has its own order: the lead identifies the project BEFORE loading its files (Codex spec 2026-10-12). */
const P_STEPS = ['ask', 'ui', 'client', 'front', 'plan', 'delegate', 'know', 'gw', 'run', 'verify', 'report', 'learn'] as const;
const P_BAND_H = { client: 125, front: 130, plan: 110, delegate: 245, gw: 125, run: 115, verify: 115, learn: 125 };
const PY = yLayout(P_STEPS, P_BAND_H);
const ROW_W = 750;

type Spec = { id: string; label: string; sub: string; why: string; sources: string[]; status?: ProStatus; how?: string[] };
function row(x0: number, step: string, specs: Spec[], def: ProStatus): ProNode[] {
  const sp = ROW_W / specs.length;
  const w = Math.min(230, sp - 14);
  return specs.map((s, i) => ({ ...s, status: s.status ?? def, x: x0 + i * sp + (sp - w) / 2, y: Y[step] + 30, w }));
}
function column(x0: number, top: number, specs: Spec[], def: ProStatus): ProNode[] {
  const gap = (BOTTOM - top - 90) / specs.length;
  return specs.map((s, i) => ({ ...s, status: s.status ?? def, x: x0, y: top + 34 + i * gap, w: 210 }));
}

type StepInfo = { label: string; tag: string; trace: string; status: ProStatus };
function bands(s: 'p' | 'y', x0: number, info: Record<string, StepInfo>, sources: string[], libTitle: string, railTitle: string,
  steps: readonly string[] = STEPS, y: YMap = Y, bottom = BOTTOM, bandH: Record<string, number> = BAND_H as Record<string, number>, libStep = 'front', railX = 790): ProNode[] {
  const out: ProNode[] = steps.map((step, i) => ({
    id: `${s}_band_${step}`, label: `${i + 1}. ${info[step].label}`, sub: '', tag: info[step].tag, trace: info[step].trace,
    why: `Step ${i + 1} of ${steps.length}.`, status: info[step].status, sources,
    x: x0 - 10, y: y[step], w: ROW_W + 20, h: bandH[step] ?? 100, band: true,
  }));
  out.push(
    { id: `${s}_band_lib`, label: libTitle, sub: '', why: 'Setup and reference: files the agent reads or you set up once.', status: s === 'p' ? 'reference' : 'ok', sources, x: x0 - 290, y: y[libStep], w: 250, h: bottom - y[libStep] - 30, band: true },
    { id: `${s}_band_rails`, label: railTitle, sub: '', why: 'These apply at every step.', status: s === 'p' ? 'reference' : 'partial', sources, x: x0 + railX, y: y.ui, w: 200, h: bottom - y.ui - 30, band: true },
  );
  return out;
}

// ======================= Anthropic's way =======================
const P = 0;
const ref = 'reference' as const;
const PRO_STEPS: Record<string, StepInfo> = {
  ask: { label: 'Request starts', tag: 'trace starts: prompt.id', status: ref, trace: 'A user_prompt event starts the trace (or a webhook or schedule starts a session). Every later event for this request carries the same prompt.id.' },
  ui: { label: 'Where you talk: choose one', tag: 'session.id', status: ref, trace: 'session.id: one per conversation.' },
  front: { label: 'Load the right instructions', tag: 'files loaded', status: ref, trace: 'Which CLAUDE.md, rules and the first 200 lines of MEMORY.md loaded at start (/context shows them). A resumed job also reads its progress file and git log.' },
  client: { label: 'Lead identifies the project', tag: 'project + vault', status: ref, trace: 'Which project folder the work runs in (its CLAUDE.md, .mcp.json, settings) and, in Managed Agents, which client vault the session started with.' },
  plan: { label: 'Decide how to do the work', tag: 'plan + progress file', status: ref, trace: 'For big jobs: the plan file, the progress file and git commits that show each update.' },
  delegate: { label: 'Work alone OR use helpers', tag: 'per-agent transcript', status: ref, trace: 'If helpers run: each works in its own context, reads its own startup files, and returns only a summary; hooks see which one by name (agent_type).' },
  know: { label: 'Find information and choose a tool', tag: 'tool name + inputs', status: ref, trace: 'The tool picked and, if tool detail logging is on, its inputs.' },
  gw: { label: 'Check permission before the call', tag: 'tool_decision', status: ref, trace: 'tool_decision event: accepted or rejected, and who decided (a rule, a hook, or you).' },
  run: { label: 'Run the tool and read the result', tag: 'tool_result', status: ref, trace: 'tool_result event: which tool, success or failure, how long it took. The agent reads the result and picks the next tool, or moves on to checking.' },
  verify: { label: 'Check the result', tag: 'check output + scores', status: ref, trace: 'The pass or fail of the check (tests, build, eval) and, if a separate reviewer ran, its grader scores.' },
  report: { label: 'Answer you', tag: 'answer + total cost', status: ref, trace: 'The final answer, plus total tokens and cost for that prompt.id.' },
  learn: { label: 'Optional upkeep: during or after work', tag: 'memory + files updated', status: ref, trace: 'Memory can update mid-task; transcripts get read later and skills, evals and instructions get updated in git.' },
};

const proNodes: ProNode[] = [
  ...row(P, 'ask', [{ id: 'p_trigger', label: 'Or an event starts it', sub: 'New lead, schedule, webhook', why: 'Not every run starts with you typing. A new lead or a schedule can start the agent.', sources: ['https://platform.claude.com/docs/en/managed-agents/webhooks'] }, { id: 'p_you', label: 'You', sub: 'One goal, plain words', why: 'You give the lead agent the goal and the context it cannot guess. Your message is the start of the trace.', sources: [ANT.context, ANT.mon], how: ['Say the goal and what done looks like', 'Give the context Claude cannot guess', 'Give it a way to check its own work'] }], ref),
  ...row(P, 'ui', [
    { id: 'p_ui1', label: 'Claude Code', sub: 'Terminal, desktop, web', why: 'Where you talk to the lead agent while it works on your files.', sources: [ANT.code] },
    { id: 'p_ui2', label: 'Claude app', sub: 'Capabilities depend on the mode', why: 'Same lead agent from the app; you can check in from your phone.', sources: [ANT.code] },
    { id: 'p_ui3', label: 'Slack', sub: 'Claude in team chat', why: 'Ask from the team chat; the work still goes to one lead agent.', sources: [ANT.code] },
  ], ref),
  ...row(P, 'front', [{
    id: 'p_lead', label: 'Lead receives the request', sub: 'Identifies the project before loading its files', sources: [ANT.research, ANT.subBlog, ANT.effective],
    why: 'Anthropic\'s research system: the lead agent thinks through the approach, saves its plan, spins up subagents with specific tasks, combines what they return, decides if more work is needed, then answers you.',
    how: ['You talk to one agent; it hands work to subagents', 'Each subagent gets a clear goal, output format, tools to use and where to stop', 'Start simple: add agents only when one agent is not enough'],
  }], ref),
  ...row(P, 'plan', [
    { id: 'p_plan1', label: 'Plan written to a file', sub: 'Big jobs only; not MEMORY.md', why: 'The lead writes its plan to a file outside the conversation so it survives when the context window fills up.', sources: [ANT.research] },
    { id: 'p_plan2', label: 'Progress file + git', sub: 'claude-progress.txt, commits', why: 'For long jobs the first session sets up the project; every later session makes one step of progress and leaves notes.', sources: [ANT.harness], how: ['First session: setup script, progress file, first git commit', 'Every later session: one step, commit with a clear message, update the progress file'] },
    { id: 'p_plan3', label: 'Pick the pattern', sub: 'Workflow or orchestrator', why: 'Known steps = a fixed workflow. Steps you cannot predict = orchestrator with workers.', sources: [ANT.effective, ANT.patterns] },
  ], ref),
  ...row(P, 'agents', [
    { id: 'p_a1', label: 'Research subagent', sub: 'Own context, returns summary', why: 'Works in its own context window and hands back a short summary, so the lead stays clean.', sources: [ANT.sub, ANT.subBlog], how: ['File: .claude/agents/<name>.md (markdown + YAML frontmatter)', 'Required: name and description (when to use it)', 'Optional: tools, model'] },
    { id: 'p_a2', label: 'Build subagent', sub: 'Only the tools it needs', why: 'List its tools. Leave the list out and it gets every tool.', sources: [ANT.sub] },
    { id: 'p_a3', label: 'Ops subagent', sub: 'Runs on your computer', why: 'Claude Code subagents run on the machine Claude Code runs on.', sources: [ANT.sub] },
    { id: 'p_a4', label: 'Hosted helper option', sub: 'Anthropic-hosted sandbox', why: 'Agents can also run in a hosted container (Agent SDK hosting, Managed Agents) instead of your computer.', sources: [ANT.hosting, ANT.managed] },
  ], ref),
  ...row(P, 'ptr', [
    { id: 'p_ptr1', label: 'CLAUDE.md', sub: 'Always loaded at start', sources: [ANT.mem, ANT.steer, ANT.ctx], why: 'The startup file. Keep it light: what Claude would get wrong without it.', how: ['Under 200 lines per file; longer files lower how well it follows them', 'Commands, gotchas, conventions; not a manual', 'Root file always loads; a subfolder CLAUDE.md loads when Claude works there', 'Give it an owner and review changes like code'] },
    { id: 'p_ptr2', label: 'AGENTS.md', sub: 'Read when no CLAUDE.md', sources: [ANT.mem], why: 'Claude Code reads AGENTS.md as the project instructions when the repo has no CLAUDE.md, so one file works for other coding agents too.', how: ['Default: AGENTS.md only when there is no CLAUDE.md', 'A setting can make it read both', 'Not read: AGENTS.local.md, AGENTS.override.md, anything under a .agents/ folder', 'Same size rule: under 200 lines'] },
    { id: 'p_ptr3', label: '@ imports', sub: 'The pointer itself', sources: [ANT.mem], why: 'A line like @docs/git.md inside CLAUDE.md pulls that file in.', how: ['Relative or absolute paths, up to 4 hops deep', 'Loads at launch, so it does not save context', 'Inside backticks it is just text, not an import'] },
    { id: 'p_ptr4', label: 'Rules folder', sub: '.claude/rules/*.md', sources: [ANT.mem, ANT.steer], why: 'Rules split by topic; some load only for certain files.', how: ['One topic per file', 'paths: in the frontmatter = loads only when Claude touches matching files', 'Symlinks allowed for rules shared across projects', 'Personal rules: ~/.claude/rules/'] },
    { id: 'p_ptr5', label: 'How instruction links work', sub: 'Markdown, not JSON', sources: [ANT.mem, ANT.skills, ANT.mcp, ANT.perm], why: 'Pointers are plain markdown: @path lines in CLAUDE.md and links inside SKILL.md. JSON is only for settings: settings.json (permissions, hooks) and .mcp.json (tool servers). Anthropic describes no reverse pointers (no back-link from a file to who uses it). Instead: keep links one level deep from SKILL.md, and keep MEMORY.md as an index that points to topic files.' },
  ], ref),
  ...column(P - 270, Y.ptr, [
    { id: 'p_lib_which', label: 'Which one do I use?', sub: 'CLAUDE.md, skill, hook, MCP...', why: 'One chart for where anything belongs.', sources: ['https://code.claude.com/docs/en/features-overview'] },
    { id: 'p_lib_limits', label: 'Every size limit', sub: 'Lines, KB, counts', why: 'Every line, size and count rule Anthropic publishes, in one place.', sources: [ANT.mem, ANT.skills] },
    { id: 'p_lib_skills', label: 'Skills', sub: '.claude/skills/<name>/SKILL.md', sources: [ANT.skills, ANT.skillUse], why: 'How-to procedures. Only the name and description load at start; the rest loads when used.', how: ['name: lowercase and hyphens, up to 64 characters', 'description: up to 1024 characters, third person, what it does and when to use it', 'Body under 500 lines; SKILL.md is the table of contents', 'Reference files one level deep from SKILL.md', 'Build evals first, then write the skill'] },
    { id: 'p_lib_memory', label: 'Auto memory', sub: 'MEMORY.md index + topic files', sources: [ANT.mem], why: 'Claude saves what it learns while working.', how: ['Lives in ~/.claude/projects/<project>/memory/', 'MEMORY.md: one line per memory; first 200 lines or 25KB load', 'Details go in topic files read when needed'] },
    { id: 'p_lib_plugins', label: 'Plugins', sub: 'The box the pieces ship in', why: 'Skills, agents, hooks and tool servers packaged as one install.', sources: ['https://code.claude.com/docs/en/plugins/overview'] },
    { id: 'p_lib_mcp', label: 'Tool servers', sub: '.mcp.json in the repo', sources: [ANT.mcp], why: 'Which tools this project gets.', how: ['Project scope: .mcp.json at the repo root, committed to git', 'Everyone on the project gets the same tools', 'You approve project servers before they are used'] },
    { id: 'p_lib_settings', label: 'Settings', sub: 'settings.json', sources: [ANT.perm, ANT.hooks, ANT.steer], why: 'Where the gateway rules live.', how: ['Permission rules: allow, ask, deny', 'Hooks registered here', 'Managed settings: set by the admin, cannot be loosened'] },
    { id: 'p_lib_evals', label: 'Evals', sub: 'Test tasks + graders', sources: [ANT.evals], why: 'How you know a change made things better.', how: ['Task = one test with inputs and success criteria', 'Graders: code checks, a model judge, a human', 'Read the transcripts to trust the scores'] },
  ], ref),
  ...row(P, 'know', [
    { id: 'p_k0', label: 'Agentic search', sub: 'Folders and grep first', why: 'How agents get the info: they search files themselves before anyone builds a vector database.', sources: ['https://claude.com/blog/building-agents-with-the-claude-agent-sdk'] },
    { id: 'p_k1', label: 'Tool search', sub: 'Loads tools on demand', why: 'With many tools, Claude Code searches tool definitions and loads only the ones it needs.', sources: [ANT.mcp] },
    { id: 'p_k2', label: 'Tool description', sub: 'The tool\'s manual', why: 'The description is how the agent knows when and how to use the tool.', sources: [ANT.tools], how: ['Write it like onboarding a new teammate', 'Clear names, grouped by service', 'Say what every input means'] },
    { id: 'p_k3', label: 'One tool per job', sub: 'Not one per API call', why: 'Combine steps into tools that match a task, instead of wrapping every endpoint.', sources: [ANT.tools] },
    { id: 'p_k4', label: 'Short, clear results', sub: 'Errors say how to fix', why: 'Return what the agent needs, not raw dumps; errors say what to change.', sources: [ANT.tools] },
  ], ref),
  ...row(P, 'gw', [
    { id: 'p_g1', label: 'PreToolUse hook', sub: 'Your code checks each call', sources: [ANT.perm, ANT.hooks], why: 'Your script sees every call before it runs.', how: ['Runs before the permission prompt, on every call', 'Can block, force a prompt, or let it through', 'Cannot override deny or ask rules'] },
    { id: 'p_g2', label: 'Permission rules', sub: 'deny, then ask, then allow', sources: [ANT.perm], why: 'The allowlist.', how: ['Checked in that order; first match wins', 'A narrower allow cannot beat a deny', 'Deny a bare tool name and Claude never sees the tool'] },
    { id: 'p_g3', label: 'Ask you', sub: 'Prompt for risky calls', sources: [ANT.perm], why: 'Calls that match an ask rule wait for your yes.' },
    { id: 'p_g5', label: 'Only this client\'s keys', sub: 'Vault picked at start', why: 'The agent uses a key without ever seeing it.', sources: ['https://platform.claude.com/docs/en/managed-agents/vaults'] },
    { id: 'p_g6', label: 'Customer text is data', sub: 'Not instructions', why: 'A lead\'s message can try to give the agent orders. Stack defenses.', sources: ['https://code.claude.com/docs/en/agent-sdk/secure-deployment'] },
    { id: 'p_g4', label: 'Managed settings', sub: 'Admin rules on top', sources: [ANT.perm], why: 'Rules set by the admin that a user or project cannot loosen.' },
  ], ref),
  ...row(P, 'run', [
    { id: 'p_t1', label: 'MCP server', sub: 'Connector to the app', why: 'Agents reach real systems through MCP servers; remote servers for production systems.', sources: [ANT.mcpProd, ANT.mcp] },
    { id: 'p_t2', label: 'Bash and code', sub: 'On the agent\'s computer', why: 'Shell commands, checked by the same rules.', sources: [ANT.perm] },
    { id: 'p_t4', label: 'Choose a tool connection', sub: 'API, CLI or MCP', why: 'Anthropic\'s answer to "only MCP?": no. Three paths (API, CLI, MCP), each with its place, plus your own functions as SDK tools.', sources: [ANT.mcpProd] },
    { id: 'p_t3', label: 'Where agents run', sub: 'Your computer or hosted', why: 'Runs in an isolated container Anthropic or you host.', sources: [ANT.hosting, ANT.managed] },
  ], ref),
  ...row(P, 'land', [
    { id: 'p_l1', label: 'Project A', sub: 'Own repo, CLAUDE.md, .mcp.json', why: 'Each project carries its own instructions and its own tool servers, so an agent working in A only has A\'s tools.', sources: [ANT.mem, ANT.mcp] },
    { id: 'p_l2', label: 'Project B', sub: 'Own repo, CLAUDE.md, .mcp.json', why: 'Same, separate from A.', sources: [ANT.mem, ANT.mcp] },
    { id: 'p_l4', label: 'New client in one move', sub: 'Plugin + repo + vault', why: 'Shared know-how once, client facts per repo, keys per vault.', sources: ['https://code.claude.com/docs/en/plugins/overview'] },
    { id: 'p_l3', label: 'Result saved (git)', sub: 'A possible output', why: 'Commit progress with clear messages; git lets you roll back a bad change.', sources: [ANT.harness] },
  ], ref),
  ...row(P, 'review', [
    { id: 'p_r1', label: 'Separate reviewer', sub: 'Optional extra layer', why: 'A separate agent grades the work; agents judging their own work tend to be too easy on it.', sources: [ANT.harnessDesign] },
    { id: 'p_r2', label: 'Citation check', sub: 'Claims match sources', why: 'A citation agent ties every claim to its source before the answer goes out.', sources: [ANT.research] },
    { id: 'p_r4', label: 'Sandbox + fake leads', sub: 'Test before real clients', why: 'A copy world with fake leads and graded test cases before the agent touches a real client.', sources: ['https://platform.claude.com/docs/en/test-and-evaluate/develop-tests'] },
    { id: 'p_r3', label: 'Model judge', sub: 'Rubric, 0 to 1, pass/fail', why: 'One judge call with a rubric: accuracy, citations, completeness, source quality, tool efficiency.', sources: [ANT.research] },
  ], ref),
  ...row(P, 'report', [
    { id: 'p_rep1', label: 'Lead answers you', sub: 'From checked results', why: 'The lead combines the summaries and returns the result with sources.', sources: [ANT.research] },
    { id: 'p_rep2', label: 'Cost and tokens', sub: 'Per prompt.id', why: 'Every model call logs tokens and cost against the same prompt.id.', sources: [ANT.mon] },
  ], ref),
  ...row(P, 'learn', [
    { id: 'p_e1', label: 'Read transcripts', sub: 'Why it passed or failed', why: 'Anthropic reads transcripts regularly; that is how you know the graders are right.', sources: [ANT.evals] },
    { id: 'p_e5', label: 'Gotchas grow', sub: 'Each failure added to its skill', why: 'Every skill has a Gotchas section that grows as Claude hits new failures.', sources: [ANT.skillUse] },
    { id: 'p_e2', label: 'Auto memory', sub: 'Claude saves what it learned', why: 'Learnings land in MEMORY.md and topic files.', sources: [ANT.mem, ANT.ctx] },
    { id: 'p_e6', label: 'Dreaming', sub: 'Reviews past sessions', why: 'A scheduled pass reviews past sessions and memory, finds patterns and cleans memory up.', sources: ['https://claude.com/blog/new-in-claude-managed-agents'] },
    { id: 'p_e3', label: 'Evals before changes', sub: 'Test on real tasks', why: 'Build evals first, then change the skill or instructions and re-run.', sources: [ANT.skills, ANT.evals] },
    { id: 'p_e4', label: 'Update the files', sub: 'CLAUDE.md, skills, reviewed', why: 'Instruction changes go through review like code, with an owner.', sources: [ANT.steer] },
  ], ref),
  ...column(P + 800, Y.ui, [
    { id: 'p_x1', label: 'Fewest tools', sub: 'Each subagent lists its own', why: 'Give each subagent only the tools it needs.', sources: [ANT.sub] },
    { id: 'p_x2', label: 'Rules + hooks', sub: 'Every call checked', why: 'Deny, ask, allow, plus hooks, on every call.', sources: [ANT.perm] },
    { id: 'p_x3', label: 'Trace + transcripts', sub: 'Their version of a ledger', why: 'Prompts, model calls, decisions and tool results, joined by prompt.id.', sources: [ANT.mon] },
    { id: 'p_x4', label: 'Kill switch', sub: 'Deny rule pulls a tool', why: 'A deny rule on a tool name takes the tool away from the next call, even mid-session; managed settings push it to everyone.', sources: [ANT.perm] },
    { id: 'p_x5', label: 'Evals', sub: 'Before every change', why: 'Changes are tested on fixed tasks first.', sources: [ANT.evals] },
    { id: 'p_x7', label: 'Stay current', sub: 'Changelog, weekly digest', why: 'How they keep up: the changelog, the weekly digest, progress files and timestamps.', sources: ['https://code.claude.com/docs/en/changelog'] },
    { id: 'p_x8', label: 'Cost controls', sub: 'Caps, cache, cheaper helpers', why: 'Spend caps, prompt caching, cheaper models for simple work.', sources: ['https://claude.com/blog/reducing-cost-and-improving-performance-with-claude-platform'] },
    { id: 'p_x9', label: 'A schedule starts it', sub: 'Routines, deployments', why: 'Everything that runs on its own timer.', sources: ['https://claude.com/blog/introducing-routines-in-claude-code'] },
    { id: 'p_x10', label: 'Short sessions', sub: '/clear, /compact, subagents', why: 'Keep each session short and on one job.', sources: ['https://code.claude.com/docs/en/best-practices'] },
    { id: 'p_x6', label: 'In git, reviewed', sub: 'Instructions are code', why: 'CLAUDE.md, rules, skills and .mcp.json live in the repo and get reviewed.', sources: [ANT.steer, ANT.mcp] },
  ], ref).map((n) => ({ ...n, w: 170, x: P + 805 })),
];
const proExtra: ProNode[] = [
  { id: 'p_load', label: 'Load instructions', sub: 'Project rules, skills, memory; progress if resuming', status: ref, why: 'Once the project is known, the lead loads that project\'s CLAUDE.md and rules, the skill list, the first 200 lines of MEMORY.md, and, if it is resuming a job, the progress file and git log.', sources: [ANT.mem], x: 0, y: 0 },
  { id: 'p_plan', label: 'Choose the next action', sub: 'Answer, work alone, or delegate', status: ref, why: 'The lead decides: answer straight away, do the work itself, or hand parts to helpers.', sources: [ANT.effective], x: 0, y: 0 },
  { id: 'p_helpers', label: 'Optional helpers', sub: 'Each gets a task and its own instructions', status: ref, why: 'Only when it helps: each helper gets a clear handoff, loads its own instructions, works in its own context, and returns a summary.', sources: [ANT.sub, ANT.research], x: 0, y: 0 },
  { id: 'p_combine', label: 'Lead combines results', sub: 'Reviews helper findings first', status: ref, why: 'The lead reads every helper summary, decides if more helper work is needed, then moves on to checking.', sources: [ANT.research], x: 0, y: 0 },
  { id: 'p_small', label: 'Keep working files small', sub: 'Big archive, small working set', status: ref, why: 'Self-improving without bloat: raw history stays on disk and gets searched; only short, capped files load into the agent.', sources: [ANT.mem, ANT.skillUse], x: 0, y: 0 },
  { id: 'p_aftercheck', label: 'After-edit check', sub: 'A hook runs a quick test', status: ref, why: 'Right after an edit, a PostToolUse hook runs a focused check and hands any failure back to the agent, so problems are caught while it is still working.', sources: [ANT.hooks], x: 0, y: 0 },
  { id: 'p_result', label: 'Read the tool result', sub: 'More work, or ready to check?', status: ref, why: 'After every tool call the agent reads the result and decides: call another tool, or check the work.', sources: ['https://claude.com/blog/building-agents-with-the-claude-agent-sdk'], x: 0, y: 0 },
  { id: 'p_self', label: 'Lead does the work', sub: 'No helpers needed', status: ref, why: 'In one chat the lead usually does the work itself. Helpers are for big reading jobs or work that splits into independent parts.', sources: ['https://code.claude.com/docs/en/features-overview', ANT.effective], x: 0, y: 0 },
  { id: 'p_check', label: 'Runs the check you gave it', sub: 'Tests, build, eval', status: ref, why: 'The first verification is the check from your ask. Claude runs it, reads the result, and keeps working until it passes.', sources: ['https://code.claude.com/docs/en/best-practices'], x: 0, y: 0 },
];

const PRO_LAYOUT: Record<string, string[]> = {
  ask: ['p_you', 'p_trigger', 'p_x9'],
  ui: ['p_ui1', 'p_ui2', 'p_ui3'],
  client: ['p_lead', 'p_l1', 'p_l2', 'p_g5'],
  front: ['p_load', 'p_ptr1', 'p_ptr2', 'p_ptr3', 'p_ptr4'],
  plan: ['p_plan', 'p_plan1', 'p_plan2'],
  delegate: ['p_self', 'p_helpers', 'p_a1', 'p_a2', 'p_a3', 'p_combine'],
  know: ['p_k0', 'p_k1', 'p_k2'],
  gw: ['p_g1', 'p_g2', 'p_g3', 'p_g4'],
  run: ['p_t1', 'p_t2', 'p_l3', 'p_result', 'p_aftercheck'],
  verify: ['p_check', 'p_r1', 'p_r2', 'p_r3'],
  report: ['p_rep1', 'p_rep2'],
  learn: ['p_e1', 'p_e5', 'p_e2', 'p_e6', 'p_e3', 'p_e4'],
};
const PRO_LIB = ['p_lib_which', 'p_lib_limits', 'p_small', 'p_ptr5', 'p_lib_skills', 'p_lib_memory', 'p_lib_plugins', 'p_lib_mcp', 'p_lib_settings', 'p_plan3', 'p_k3', 'p_k4', 'p_t4', 'p_t3', 'p_a4', 'p_l4', 'p_lib_evals', 'p_r4'];
const PRO_RAILS = ['p_x1', 'p_x2', 'p_g6', 'p_x3', 'p_x4', 'p_x5', 'p_x7', 'p_x8', 'p_x10', 'p_x6'];

/** Places every card by id; throws if a card is missing or left unplaced, so nothing is silently dropped. */
function relayout(nodes: ProNode[], x0: number, rows: Record<string, string[]>, lib: string[], rails: string[],
  steps: readonly string[] = STEPS, y: YMap = Y, bottom = BOTTOM, libStep = 'front', railX = 805, rowOff: Record<string, number> = {}): ProNode[] {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const out = new Map<string, ProNode>();
  const get = (id: string) => { const n = byId.get(id); if (!n) throw new Error(`Pro Map layout: unknown card ${id}`); return n; };
  for (const step of steps) {
    const ids = rows[step];
    const sp = ROW_W / ids.length;
    const w = Math.min(230, sp - 14);
    ids.forEach((id, i) => out.set(id, { ...get(id), x: x0 + i * sp + (sp - w) / 2, y: y[step] + 30 + (rowOff[step] ?? 0), w }));
  }
  const col = (ids: string[], top: number, x: number, w: number) => {
    const gap = (bottom - top - 90) / ids.length;
    ids.forEach((id, i) => out.set(id, { ...get(id), x, y: top + 34 + i * gap, w }));
  };
  col(lib, y[libStep], x0 - 270, 210);
  col(rails, y.ui, x0 + railX, 170);
  const left = nodes.filter((n) => !out.has(n.id)).map((n) => n.id);
  if (left.length) throw new Error(`Pro Map layout: unplaced cards ${left.join(', ')}`);
  return nodes.map((n) => out.get(n.id) as ProNode);
}

const BADGES: Record<string, string> = { p_plan1: 'Long jobs only', p_plan2: 'Long jobs only', p_r1: 'When useful', p_r2: 'When useful', p_r3: 'When useful' };

/** Dashed box around the optional helper branch in step 6 (middle map). */
function helperGroup(nodes: ProNode[]): ProNode[] {
  const ids = ['p_helpers', 'p_a1', 'p_a2', 'p_a3'];
  const g = nodes.filter((n) => ids.includes(n.id));
  const x1 = Math.min(...g.map((n) => n.x)) - 6;
  const x2 = Math.max(...g.map((n) => n.x + (n.w ?? 130))) + 6;
  const y1 = Math.min(...g.map((n) => n.y)) - 26;
  return [...nodes, { id: 'p_grp_helpers', label: 'Optional: hand out tasks', sub: '', band: true, status: ref, why: 'Only when it helps. Helpers load their own instructions and use the same tool loop.', sources: [ANT.sub], x: x1, y: y1, w: x2 - x1, h: 205 }];
}

const pro: ProNode[] = [
  { id: 'p_title', label: 'Version 2: Codex review, 12 steps (one chat)', sub: 'One chat, start to finish, top to bottom. Claude Code, the app and SDK agents each use these pieces; they are not one product.', x: P - 290, y: -110, w: 1280, h: 60, band: true, status: ref, why: 'Every box links the Anthropic page it comes from.', sources: [ANT.steer, ANT.research] },
  ...bands('p', P, PRO_STEPS, [ANT.mon, ANT.steer], 'Library: setup + reference', 'Rules throughout', P_STEPS, PY.y, PY.bottom,
    P_BAND_H, 'client', 850),
  ...helperGroup(relayout([...proNodes, ...proExtra], P, PRO_LAYOUT, PRO_LIB, PRO_RAILS, P_STEPS, PY.y, PY.bottom, 'client', 865, { delegate: 34 })
    .map((n) => (BADGES[n.id] ? { ...n, badge: BADGES[n.id] } : n))),
];

// ======================= Alex (each status cites a source) =======================
const A = OFFSET;
const YOUR_STEPS: Record<Step, StepInfo> = {
  ask: { label: 'You ask', tag: 'no shared trace id', status: 'partial', trace: 'Nothing central: each app keeps its own chat history.' },
  ui: { label: 'Where you talk', tag: 'each app\'s own history', status: 'partial', trace: 'Each app has its own history; no session ID shared across apps.' },
  front: { label: 'Lead starts and reads its files: no lead; each app reads its own', tag: 'drift check at start', status: 'partial', trace: 'No lead agent. Each app reads its own generated file; drift_check runs at every Claude, Codex and Cursor start.' },
  client: { label: 'Picks the client: nothing picks one; one login sees all', tag: 'not logged', status: 'gap', trace: 'No step picks a client: one GHL login reaches all 303 accounts, and nothing records which client a run was for.' },
  plan: { label: 'Plans', tag: 'Director state + ledger', status: 'ok', trace: 'Director state file and the mission ledger (~/Alex-Director).' },
  delegate: { label: 'Hands work to agents (you, by opening each app)', tag: 'Codex threads, SDK ledger', status: 'partial', trace: 'Codex threads through the bridge; Orgo reads in the SDK ledger. Other agents: their own app history.' },
  know: { label: 'Finds the tool and reads how to use it', tag: 'not logged', status: 'ok', trace: 'Composio searches and app-card reads are not logged centrally.' },
  gw: { label: 'Gateway checks the call', tag: 'guard decisions.jsonl', status: 'partial', trace: 'Guard decisions in ~/.agents/runtime/composio-guard/decisions.jsonl (Claude, Codex, Cursor only).' },
  run: { label: 'Tool runs; result back to the agent', tag: 'SDK receipts only', status: 'partial', trace: 'SDK ledger receipts for SDK calls; direct Composio calls are not in it.' },
  verify: { label: 'Verifies the result', tag: 'review packets', status: 'ok', trace: 'Review packets in ~/Projects/alex-system-map/reviews/.' },
  report: { label: 'Answers you', tag: 'completed missions', status: 'partial', trace: 'Completed missions in ~/Alex-Director/ledger-history/completed-missions-2026-10.md.' },
  learn: { label: 'Learns (needs your yes)', tag: 'lessons + tune-ups', status: 'partial', trace: 'lessons.md (65), tune-up snapshots and proposals in master-connector-repo/system.' },
};
type Row5 = [string, string, ProStatus, string, string];
const UIS: Row5[] = [
  ['Claude app', 'Claude Code', 'ok', 'You talk to Claude Code directly.', 'hostname (2026-10-12): MacBook Pro'],
  ['Codex app', 'Codex threads', 'ok', 'You talk to Codex directly; the Conductor also drives Codex threads.', '~/.agents/skills/alex-workflow-conductor/SKILL.md'],
  ['Cursor', 'Editor chat', 'ok', 'You talk to Cursor directly.', '~/.cursor/rules/agent-routing.mdc'],
  ['ChatGPT', 'Chat app', 'ok', 'You talk to ChatGPT directly.', `${ORG} (ChatGPT node)`],
  ['Manus app', 'Manus tasks', 'ok', 'You talk to Manus directly.', '~/.agents/tools/cards/manus.md'],
  ['Telegram', 'To Javar', 'ok', 'You text Javar on Telegram; he texts contacts only with your approval.', '~/Documents/ChatGPT/Build (javar_text_contact, owner-approved texts from Telegram)'],
];
const AGENTS: Row5[] = [
  ['Claude Code', 'MacBook Pro', 'partial', 'Runs on the MacBook with your shared Composio logins; Composio guard hook stops spend, send, delete.', '~/.claude/settings.json (PreToolUse composio_guard, SessionStart drift_check)'],
  ['Codex', 'MacBook Pro', 'partial', 'Runs on the MacBook; shared logins; Codex Composio guard.', '~/.agents/tools/guards/codex_composio_guard.py'],
  ['Cursor', 'MacBook Pro', 'partial', 'Runs on the MacBook; shared logins; Cursor Composio guard; also has the raw Orgo MCP (can delete).', '~/.agents/tools/guards/cursor_composio_guard.py'],
  ['ChatGPT', 'OpenAI cloud', 'gap', 'Gets none of the rule files and has no guard.', `${ORG} (ChatGPT node: gets none of your rule files)`],
  ['Manus', 'Manus cloud', 'partial', 'Runs in Manus\'s own computer; own skills, not the shared rules; no Composio guard.', '~/.agents/tools/cards/manus.md'],
  ['Hermes (Javar)', 'Orgo EA', 'partial', 'Runs on Orgo EA (one of 7 Orgo computers); reads its own AGENTS.md there; no Composio guard.', `${SDK}/docs/evidence/orgo/live-proof-2026-10-12.json`],
];
const POINTERS: Row5[] = [
  ['CLAUDE.md', '~/.claude, 185 skills', 'ok', 'Generated from ~/.agents/instructions; ~/.claude/skills has 185 links into ~/.agents/skills.', '~/.agents/tools/unify/build_instructions.py; ls ~/.claude/skills (185)'],
  ['AGENTS.md', '~/.codex, 132 skills', 'ok', 'Generated from ~/.agents/instructions; config.toml lists 132 [[skills.config]] paths into ~/.agents/skills.', '~/.codex/config.toml (132 skills.config)'],
  ['Cursor rule', '~/.cursor, 184 skills', 'ok', 'Cursor rule generated from ~/.agents/instructions; ~/.cursor/skills has 184 links.', '~/.cursor/rules/agent-routing.mdc; ls ~/.cursor/skills (184)'],
  ['None', 'Gets no rule files', 'gap', 'ChatGPT reads none of the shared rules.', `${ORG} (ChatGPT node)`],
  ['Manus skills', 'Not your shared rules', 'partial', 'Manus uses its own skills, not ~/.agents.', `${ORG} (Manus node: own Manus skills, not your shared rules)`],
  ['Hermes file', 'On Orgo, kept apart', 'partial', 'workspace/AGENTS.md links to /home/orgo/lil-smoove/home/.hermes/AGENTS.md; not built from ~/.agents.', `${SDK} orgo.read_computer EA list_dir (2026-10-12)`],
];
const spec = (prefix: string) => ([label, sub, status, why, src]: Row5, i: number): Spec => ({ id: `${prefix}${i + 1}`, label, sub, status, why, sources: [src] });

const alexNodes: ProNode[] = [
  ...row(A, 'ask', [{ id: 'y_you', label: 'You (Alex)', sub: 'Only approver', status: 'ok', why: 'Approvals come only from you in chat.', sources: ['~/.agents/instructions/shared.md'] }], 'ok'),
  ...row(A, 'ui', UIS.map(spec('y_ui')), 'ok'),
  ...row(A, 'front', [{ id: 'y_front', label: 'No front door', sub: 'You open each app yourself', status: 'gap', why: 'There is no one agent you talk to that hands the work out. The Director plans and routes, but only inside Codex; you still open Claude, Cursor, Manus, ChatGPT and Telegram yourself.', sources: ['~/.agents/skills/alex-director/SKILL.md'] }], 'gap'),
  ...row(A, 'plan', [
    { id: 'y_director', label: 'Director', sub: 'Routes, plans, dispatches', status: 'ok', why: 'Picks the agent and the plan, dispatches Codex threads through the bridge; state in ~/Alex-Director.', sources: ['~/.agents/skills/alex-director/SKILL.md', '~/Alex-Director/DIRECTOR_STATE.md'] },
    { id: 'y_conductor', label: 'Conductor', sub: 'Runs via Codex threads', status: 'ok', why: 'Runs the plan through the controllers.', sources: ['~/.agents/skills/alex-workflow-conductor/SKILL.md'] },
    { id: 'y_missions', label: 'Missions', sub: '21 on the board', status: 'ok', why: '7 Dynamite / Natural Sanitation, 7 Personal / system, 7 parked.', sources: [`${ORG} (missions)`] },
  ], 'ok'),
  ...row(A, 'agents', AGENTS.map(spec('y_a')), 'partial'),
  ...row(A, 'ptr', POINTERS.map(spec('y_ptr')), 'ok'),
  ...column(A - 270, Y.ptr, [
    { id: 'y_lib_rules', label: 'Rule source', sub: '~/.agents/instructions (6)', status: 'ok', why: 'One source; build_instructions.py writes CLAUDE.md, AGENTS.md and the Cursor rule. Git: increase-roas/agents-home with CI.', sources: ['~/.agents/instructions/', '~/.agents/tools/unify/build_instructions.py'] },
    { id: 'y_lib_skills', label: 'Skills (185)', sub: '~/.agents/skills, one copy', status: 'ok', why: '185 skill folders, linked into Claude (185) and Cursor (184), listed in Codex config (132).', sources: ['ls ~/.agents/skills (185)', '~/.agents/tools/unify/skill-lifecycle.md'] },
    { id: 'y_lib_guides', label: 'Tool cards (25)', sub: '+ 27 passports', status: 'ok', why: 'Each app has a routing card (which login, which tool, what needs approval) and a passport (docs, fixes). Cards reach every AI through Composio app rules. Your passports point back to the cards: Anthropic has no reverse pointers, so this is your own addition.', sources: ['~/.agents/tools/cards/ (25)', '~/.agents/registry/connectors/ (27)'] },
    { id: 'y_lib_memory', label: 'Memory', sub: 'Mem0, Director state', status: 'partial', why: 'Mem0 via the SDK plus Director state files; not one store every agent reads.', sources: [`${SDK}/docs/MEMORY.md`, '~/Alex-Director/DIRECTOR_STATE.md'] },
    { id: 'y_lib_lessons', label: 'Lessons (65) + evals', sub: 'system/lessons.md', status: 'ok', why: '65 lessons, plus golden and held-out test tasks.', sources: [`${MCR}/lessons.md`, `${MCR}/evals/golden-tasks.md`] },
  ], 'ok'),
  ...row(A, 'know', [
    { id: 'y_k1', label: 'Find the tool', sub: 'COMPOSIO_SEARCH_TOOLS', status: 'ok', why: 'Agent searches Composio by task in plain words.', sources: ['~/.agents/tools/cards/composio.md'] },
    { id: 'y_k2', label: 'Read the app card', sub: 'GET_APP_RULES first', status: 'ok', why: 'Before the first call to an app, the agent reads its card through CUSTOM_IR_NOTES_GET_APP_RULES. Only agents that follow your shared rules do this.', sources: ['~/.agents/instructions/shared.md', '~/.agents/tools/cards/'] },
    { id: 'y_k3', label: 'Call, named login', sub: 'MULTI_EXECUTE + account', status: 'ok', why: 'Every Composio call names its login; the guard refuses multi-login toolkits with no login named.', sources: ['~/.agents/tools/guards/composio_guard.py'] },
    { id: 'y_k4', label: 'Example: GHL', sub: 'Workflows = GHL Command', status: 'ok', why: 'The GHL card routes workflow edits to custom_ghl_command_builder and CRM work to custom_ghl_oauth_crm (the OAuth app cannot edit workflows, tested 2026-10-11).', sources: ['~/.agents/tools/cards/ghl.md', '~/.agents/registry/connectors/ghl.json'] },
  ], 'ok'),
  ...row(A, 'gw', [
    { id: 'y_g1', label: 'Composio guards', sub: 'Stop spend, send, delete', status: 'partial', why: 'Hooks in Claude Code, Codex and Cursor stop spend, client messages, deletes, DNS, deploys until you say yes. Manus, ChatGPT, Hermes have none.', sources: ['~/.agents/tools/guards/composio_guard.py', '~/.agents/tools/guards/codex_composio_guard.py', '~/.agents/tools/guards/cursor_composio_guard.py'] },
    { id: 'y_g2', label: 'SDK allowlist', sub: 'Orgo, repairs, reads', status: 'ok', why: 'Off-list Orgo checks and secret paths refused.', sources: [`${SDK}/src/master_ops/adapters/orgo_fleet.py`] },
    { id: 'y_g3', label: 'Your approval', sub: 'Exact yes, Orgo live', status: 'partial', why: 'Exact-approval gate proven live for Orgo; GHL and Google writes still rely on the guards.', sources: [`${SDK}/docs/evidence/orgo/live-proof-2026-10-12.json`] },
    { id: 'y_g4', label: 'Badge + client walls', sub: 'Not built', status: 'gap', why: 'No per-agent login and no per-agent client list.', sources: ['~/.agents/registry/connectors/ghl.json'] },
  ], 'partial'),
  ...row(A, 'run', [
    { id: 'y_t_composio', label: 'Composio', sub: '25 cards, keys via 1Password', status: 'ok', why: 'Main connector hub; every call names its login.', sources: ['~/.agents/tools/cards/composio.md'] },
    { id: 'y_t_orgo', label: 'Orgo route', sub: 'orgo_op.py', status: 'ok', why: 'Owner route; key read from 1Password at launch.', sources: ['~/.agents/tools/connectors/orgo_op.py'] },
    { id: 'y_t_local', label: 'Local bridges', sub: 'Codex, Claude, Observatory', status: 'ok', why: 'Local MCP bridges used by the SDK.', sources: [`${SDK}/src/master_ops/capabilities.py`] },
  ], 'ok'),
  ...row(A, 'land', [
    { id: 'y_l1', label: 'Dynamite / Nat. San.', sub: '7 missions', status: 'partial', why: '7 missions; some need you, some on watch.', sources: [`${ORG} (missions, Dynamite Lighting / Natural Sanitation)`] },
    { id: 'y_l2', label: 'ROAS clients (GHL)', sub: '303, one login sees all', status: 'gap', why: 'custom_ghl_oauth_crm reaches 303 client locations with one login; no wall per client.', sources: ['~/.agents/registry/connectors/ghl.json'] },
    { id: 'y_l3', label: 'Personal / system', sub: '7 missions', status: 'partial', why: '7 system missions (connector consolidation, Orgo route, shared brain, setup parity).', sources: [`${ORG} (missions, Personal / system)`] },
    { id: 'y_l4', label: 'Google, Meta Ads', sub: 'Shared logins', status: 'ok', why: 'Connected through Composio.', sources: ['~/.agents/registry/connectors/'] },
    { id: 'y_l5', label: 'Orgo (7)', sub: 'Seen live', status: 'ok', why: '7 computers, uptime and disk read on each.', sources: [`${SDK}/docs/evidence/orgo/live-proof-2026-10-12.json`] },
    { id: 'y_l6', label: '~/Documents', sub: 'Never iCloud', status: 'ok', why: 'Agents read ~/Documents, never iCloud (rule merged, agents-home PR #14).', sources: ['~/.agents/instructions/shared.md'] },
  ], 'ok'),
  ...row(A, 'review', [
    { id: 'y_reviewer', label: 'Reviewer', sub: 'Other model checks', status: 'ok', why: 'A different model family reviews before done.', sources: ['~/Projects/alex-system-map/AGENTS.md'] },
    { id: 'y_packets', label: 'Review packets', sub: 'Saved per change', status: 'ok', why: 'Each reviewed change leaves a packet.', sources: ['~/Projects/alex-system-map/reviews/'] },
  ], 'ok'),
  ...row(A, 'report', [
    { id: 'y_rep1', label: 'Each app replies', sub: 'No one combined report', status: 'partial', why: 'Results come back in whichever app did the work.', sources: [`${ORG}`] },
    { id: 'y_rep2', label: 'Mission ledger', sub: 'Completed missions', status: 'ok', why: 'Finished missions are written to the ledger.', sources: ['~/Alex-Director/ledger-history/completed-missions-2026-10.md'] },
    { id: 'y_rep3', label: 'SDK receipts', sub: 'SDK calls only', status: 'partial', why: 'SDK ledger records SDK calls; direct Composio calls are not in it.', sources: [`${SDK}/src/master_ops/operations.py`] },
  ], 'partial'),
  ...row(A, 'learn', [
    { id: 'y_e1', label: 'Correction or failure', sub: 'You correct, a task fails', status: 'partial', why: 'Lessons start when you correct an agent or a task fails; there is no trace of every run yet.', sources: ['~/.agents/skills/capture-lessons/SKILL.md'] },
    { id: 'y_e2', label: 'capture-lessons', sub: 'Writes lessons.md', status: 'ok', why: 'Turns evidence into 1 to 5 lessons, updating matches instead of duplicating. Only agents with the shared skills run it.', sources: ['~/.agents/skills/capture-lessons/SKILL.md', `${MCR}/lessons.md`] },
    { id: 'y_e3', label: 'Weekly tune-up', sub: 'Tests on golden tasks', status: 'ok', why: 'Merges lessons, checks drift, tests changes on golden tasks; last snapshot 2026-10-12 00:12.', sources: ['~/.agents/skills/weekly-tuneup/SKILL.md', `${MCR}/snapshots/2026-10-12_0012_tuneup`] },
    { id: 'y_e4', label: 'Your yes, then update', sub: 'Proposal to rules/skills', status: 'partial', why: 'Writes a proposal for your approval before rules or skills change. Latest proposal file: 2026-10-01.', sources: [`${MCR}/proposals/`] },
  ], 'partial'),
  ...column(A + 800, Y.ui, [
    { id: 'y_x1', label: 'Badge per agent', sub: 'Shared logins now', status: 'gap', why: 'No separate login per agent.', sources: ['Composio connected accounts (one per app)'] },
    { id: 'y_x2', label: 'Guards', sub: '3 of 6 agents', status: 'partial', why: 'Claude, Codex, Cursor guarded; Manus, ChatGPT, Hermes not.', sources: ['~/.agents/tools/guards/'] },
    { id: 'y_x3', label: 'Trace', sub: 'Observatory, read-only', status: 'partial', why: 'Bounded reads and offline evals; no one ID that follows a request across apps.', sources: ['director-observatory tool card'] },
    { id: 'y_x4', label: 'Kill switch', sub: 'None yet', status: 'gap', why: 'Kill-switch runbook listed as missing.', sources: ['~/.agents/docs/gap-audit-2026-10-11.md'] },
    { id: 'y_x5', label: '1Password', sub: 'One vault for all', status: 'partial', why: 'Keys reach apps through Composio and owner routes, but one shared vault, not one per agent.', sources: ['~/.agents/tools/connectors/orgo_op.py'] },
    { id: 'y_x6', label: 'Drift check + CI', sub: 'Every app start', status: 'ok', why: 'SessionStart drift check in Claude, Codex, Cursor; agents-home CI on every PR; weekly docs-freshness check.', sources: ['~/.agents/tools/guards/drift_check.py', '~/.agents/.github/workflows/docs-freshness.yml'] },
  ], 'ok').map((n) => ({ ...n, w: 170, x: A + 805 })),
];
const YOUR_LAYOUT: Record<Step, string[]> = {
  ask: ['y_you'],
  ui: ['y_ui1', 'y_ui2', 'y_ui3', 'y_ui4', 'y_ui5', 'y_ui6'],
  front: ['y_front', 'y_ptr1', 'y_ptr2', 'y_ptr3', 'y_ptr4', 'y_ptr5', 'y_ptr6'],
  client: ['y_l1', 'y_l2', 'y_l3', 'y_l4', 'y_l5', 'y_l6'],
  plan: ['y_director', 'y_conductor', 'y_missions'],
  delegate: ['y_a1', 'y_a2', 'y_a3', 'y_a4', 'y_a5', 'y_a6'],
  know: ['y_k1', 'y_k2', 'y_k3', 'y_k4'],
  gw: ['y_g1', 'y_g2', 'y_g3', 'y_g4'],
  run: ['y_t_composio', 'y_t_orgo', 'y_t_local'],
  verify: ['y_reviewer', 'y_packets'],
  report: ['y_rep1', 'y_rep2', 'y_rep3'],
  learn: ['y_e1', 'y_e2', 'y_e3', 'y_e4'],
};
const YOUR_LIB = ['y_lib_rules', 'y_lib_skills', 'y_lib_guides', 'y_lib_memory', 'y_lib_lessons'];
const YOUR_RAILS = ['y_x1', 'y_x2', 'y_x3', 'y_x4', 'y_x5', 'y_x6'];

const alex: ProNode[] = [
  { id: 'y_title', label: 'Yours today', sub: 'Same 12 steps; click any box for the file that proves it', x: A - 290, y: -110, w: 1280, h: 60, band: true, status: 'ok', why: 'Every status on this side names its source.', sources: ['app/src/app/explorer/pro-map-data.ts'] },
  ...bands('y', A, YOUR_STEPS, ['app/src/app/explorer/pro-map-data.ts'], 'Library: setup + reference', 'Rails (every step)'),
  ...relayout(alexNodes, A, YOUR_LAYOUT, YOUR_LIB, YOUR_RAILS),
];

const cat = <T,>(...xs: (T[] | undefined)[]): T[] | undefined => {
  const out = xs.flatMap((x) => x ?? []);
  return out.length ? out : undefined;
};
export const PRO_NODES: ProNode[] = [...pro, ...alex].map((n) => {
  const d = PRO_DETAILS[n.id];
  const ex = PRO_EXAMPLES[n.id];
  const mo = PRO_MORE[n.id];
  const fi = PRO_FILL[n.id];
  if (!d && !ex && !mo && !fi && !n.how) return n;
  const detail: FullDetail = {
    limits: cat(d?.limits, mo?.limits, fi?.limits),
    build: cat(d?.build ?? n.how, mo?.build, fi?.build),
    pros: cat(d?.pros, mo?.pros, fi?.pros),
    noobs: cat(d?.noobs, mo?.noobs, fi?.noobs),
    extra: d?.extra,
    plain: cat(ex?.plain, mo?.plain, fi?.plain),
    pictures: cat(ex?.pictures, mo?.pictures, fi?.pictures),
    examples: cat(ex?.examples, mo?.examples, fi?.examples),
    decide: cat(ex?.decide, mo?.decide, fi?.decide),
    myths: cat(mo?.myths, fi?.myths)?.map((m) => ({ ...m, fix: m.fix ?? FIXES[m.myth] })),
  };
  return { ...n, detail, sources: [...new Set([...n.sources, ...(d?.sources ?? []), ...(ex?.sources ?? []), ...(mo?.sources ?? []), ...(fi?.sources ?? [])])] };
});

const flow = (a: string, b: string, label?: string): ProEdge => ({ id: `${a}-${b}`, source: a, target: b, kind: 'flow', label });
const link = (a: string, b: string, label: string | undefined, sh: 'ls' | 'rs', th: 'l' | 'r'): ProEdge => ({ id: `${a}-${b}`, source: a, target: b, kind: 'link', label, sh, th });
const chain = (ids: string[]) => ids.slice(1).map((id, i) => flow(ids[i], id));
const STEP_LABELS: Partial<Record<Step, string>> = { front: 'which client?', client: 'plans', plan: 'does the work', delegate: 'needs a tool', know: 'calls it', gw: 'allowed', run: 'done? check it', verify: 'passed', report: 'every run feeds' };
const loop = (a: string, b: string, label: string): ProEdge => ({ id: `${a}-${b}-loop`, source: a, target: b, kind: 'loop', label, sh: 'rs', th: 'r' });
function spine(s: 'p' | 'y', from: Step): ProEdge[] {
  const i0 = STEPS.indexOf(from);
  return STEPS.slice(i0, -1).map((st, i) => flow(`${s}_band_${st}`, `${s}_band_${STEPS[i0 + i + 1]}`, STEP_LABELS[st]));
}

export const PRO_EDGES: ProEdge[] = [
  // Middle map (Codex spec): exact arrows, no automatic spine.
  flow('p_you', 'p_band_ui', 'Choose your interface'),
  ...[1, 2, 3].map((i) => flow(`p_ui${i}`, 'p_lead', i === 2 ? 'Request' : undefined)),
  { ...flow('p_trigger', 'p_lead', 'Starts a request'), sh: 'ls', th: 'l', offset: 20 },
  { ...flow('p_x9', 'p_lead'), sh: 'ls', th: 'l', offset: 35 },
  flow('p_lead', 'p_load', 'Project identified'),
  flow('p_load', 'p_plan', 'Context ready'),
  flow('p_plan', 'p_self'),
  flow('p_plan', 'p_helpers'),
  { ...flow('p_plan', 'p_check', 'Can answer without tools'), sh: 'ls', th: 'l', offset: 30 },
  flow('p_self', 'p_band_know', 'Needs information or action'),
  flow('p_helpers', 'p_band_know', 'Helpers use this same tool loop'),
  flow('p_band_know', 'p_band_gw', 'Proposed call'),
  flow('p_band_gw', 'p_band_run', 'Allowed'),
  flow('p_band_run', 'p_check', 'Ready to check'),
  { ...flow('p_band_run', 'p_combine', 'Helper task finished'), sh: 'rs', th: 'r', offset: 45 },
  { ...flow('p_combine', 'p_check', 'Combined result ready'), sh: 'rs', th: 'r', offset: 60 },
  flow('p_check', 'p_rep1', 'Passed'),
  { ...flow('p_rep1', 'p_you', 'Answer'), sh: 'rs', th: 'r', offset: 75 },
  { ...loop('p_result', 'p_band_know', 'More work'), offset: 15 },
  { ...loop('p_check', 'p_band_know', 'Needs correction'), offset: 30 },
  { ...loop('p_combine', 'p_helpers', 'Need more helper work'), sh: undefined, th: undefined },
  link('p_band_front', 'p_lib_skills', 'skill list', 'ls', 'r'),
  link('p_band_front', 'p_lib_memory', 'MEMORY.md', 'ls', 'r'),
  link('p_band_learn', 'p_lib_memory', 'saves', 'ls', 'r'),
  link('p_band_know', 'p_lib_mcp', 'tool definitions', 'ls', 'r'),
  link('p_band_gw', 'p_lib_settings', 'rules from', 'ls', 'r'),

  // Alex: no lead, so you open each app yourself.
  flow('y_you', 'y_band_ui', 'asks'),
  flow('y_band_ui', 'y_front'),
  { id: 'y_skip_front', source: 'y_band_ui', target: 'y_band_delegate', kind: 'bypass', label: 'you open each app yourself', sh: 'rs', th: 'r' },
  ...spine('y', 'front'),
  loop('y_band_run', 'y_band_know', 'result back: next tool?'),
  ...chain(['y_e1', 'y_e2', 'y_e3', 'y_e4']),
  link('y_band_report', 'y_you', 'each app answers', 'rs', 'r'),
  link('y_lib_rules', 'y_band_front', 'builds 3 of 6', 'rs', 'l'),
  link('y_band_front', 'y_lib_skills', 'points to', 'ls', 'r'),
  link('y_band_know', 'y_lib_guides', 'reads card', 'ls', 'r'),
  link('y_lib_memory', 'y_band_plan', 'recall', 'rs', 'l'),
  link('y_band_learn', 'y_lib_lessons', 'saves lessons', 'ls', 'r'),
  { id: 'y_bypass', source: 'y_band_delegate', target: 'y_t_composio', kind: 'bypass', label: '3 agents: no guard', sh: 'ls', th: 'l' },
];
