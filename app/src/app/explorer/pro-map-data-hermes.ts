/**
 * Version 4 (far right): Hermes Agent by Nous Research, same 12 steps top down.
 * Every card links the Hermes docs page (or the GitHub repo) it comes from. Checked 2026-10-12.
 * ids are prefixed h_. Status 'hermes' = "Hermes way" (documented behavior, not Alex's setup).
 */
import type { FullDetail, ProEdge, ProNode, ProStatus } from './pro-map-data';

const D = 'https://hermes-agent.nousresearch.com/docs';
const H = {
  docs: `${D}/`,
  repo: 'https://github.com/NousResearch/hermes-agent',
  soul: `${D}/user-guide/features/personality`,
  soulGuide: `${D}/guides/use-soul-with-hermes`,
  which: `${D}/user-guide/which-file-does-what`,
  ctx: `${D}/user-guide/features/context-files`,
  prompt: `${D}/developer-guide/prompt-assembly`,
  mem: `${D}/user-guide/features/memory`,
  skills: `${D}/user-guide/features/skills`,
  curator: `${D}/user-guide/features/curator`,
  arch: `${D}/developer-guide/architecture`,
  tools: `${D}/user-guide/features/tools`,
  toolSearch: `${D}/user-guide/features/tool-search`,
  code: `${D}/user-guide/features/code-execution`,
  deleg: `${D}/user-guide/features/delegation`,
  kanban: `${D}/user-guide/features/kanban`,
  goals: `${D}/user-guide/features/goals`,
  cron: `${D}/user-guide/features/cron`,
  hooks: `${D}/user-guide/features/hooks`,
  sec: `${D}/user-guide/security`,
  sessions: `${D}/user-guide/sessions`,
  ckpt: `${D}/user-guide/checkpoints-and-rollback`,
  msg: `${D}/user-guide/messaging`,
  profiles: `${D}/user-guide/profiles`,
  bots: `${D}/user-guide/bot-mode`,
  mcp: `${D}/user-guide/features/mcp`,
  lsp: `${D}/user-guide/features/lsp`,
  deliver: `${D}/user-guide/features/deliverable-mode`,
  dash: `${D}/user-guide/features/web-dashboard`,
  importer: `${D}/user-guide/import-from-other-agents`,
  config: `${D}/user-guide/configuration`,
};
const L = (...lines: string[]) => lines.join('\n');
const hw = 'hermes' as ProStatus;

export const HX = 2950;
const ROW_W = 750;
const STEPS = ['ask', 'ui', 'client', 'front', 'plan', 'delegate', 'know', 'gw', 'run', 'verify', 'report', 'learn'] as const;
type Step = (typeof STEPS)[number];
const BAND_H: Partial<Record<Step, number>> = { front: 120, gw: 115, learn: 115, verify: 110 };
const Y = {} as Record<Step, number>;
let cur = 0;
for (const s of STEPS) { Y[s] = cur; cur += (BAND_H[s] ?? 100) + 30; }
const BOTTOM = cur;

type Spec = { id: string; label: string; sub: string; why: string; sources: string[]; badge?: string; detail?: FullDetail };
const node = (s: Spec, x: number, y: number, w: number): ProNode => ({ ...s, status: hw, x, y, w });
function row(step: Step, specs: Spec[]): ProNode[] {
  const sp = ROW_W / specs.length;
  const w = Math.min(230, sp - 14);
  return specs.map((s, i) => node(s, HX + i * sp + (sp - w) / 2, Y[step] + 30, w));
}
function column(x: number, top: number, specs: Spec[], w: number): ProNode[] {
  const gap = (BOTTOM - top - 90) / specs.length;
  return specs.map((s, i) => node(s, x, top + 34 + i * gap, w));
}

const STEP_INFO: Record<Step, { label: string; tag: string; trace: string }> = {
  ask: { label: 'Request starts', tag: 'saved to the session', trace: 'Every conversation is saved as a session in a local database (state.db), searchable later.' },
  ui: { label: 'Where you talk: the gateway', tag: 'one session per chat', trace: 'The gateway routes each platform chat to its own session; a chat stays one session across restarts until /new.' },
  client: { label: 'Which agent and which folder', tag: 'profile + workdir', trace: 'The profile (its own home folder) and the working folder decide which identity, memory and project files load.' },
  front: { label: 'Build the system prompt', tag: '/context shows it', trace: 'SOUL.md first, then the project file, then the skills index and the MEMORY.md and USER.md snapshots. /context lists what loaded.' },
  plan: { label: 'The loop decides the next move', tag: 'tool calls visible', trace: 'Every tool call is shown to you as it happens (spinner in the terminal, progress messages in chat).' },
  delegate: { label: 'Work alone OR hand out tasks', tag: 'child summaries', trace: 'Each child agent starts fresh; only its final summary comes back into the parent session.' },
  know: { label: 'Find information and choose a tool', tag: 'tool + args', trace: 'Tool name and arguments pass through hooks (pre_tool_call sees them).' },
  gw: { label: 'Safety checks before it runs', tag: 'approvals + hook blocks', trace: 'Dangerous-command prompts, your approve or deny, and any hook block message.' },
  run: { label: 'Run it and read the result', tag: 'tool result', trace: 'The result goes back into the loop; long chats get their middle turns summarized (compression).' },
  verify: { label: 'Check the result', tag: 'judge verdict', trace: 'With /goal set, a judge model decides done, continue or blocked after every turn.' },
  report: { label: 'Answer you', tag: 'reply + files', trace: 'The reply lands in the same chat; files go as native attachments.' },
  learn: { label: 'Learn for next time', tag: 'memory + skills', trace: 'Memory writes hit the disk right away but show up in the prompt from the next session.' },
};

function bands(): ProNode[] {
  const out: ProNode[] = STEPS.map((step, i) => ({
    id: `h_band_${step}`, label: `${i + 1}. ${STEP_INFO[step].label}`, sub: '', tag: STEP_INFO[step].tag, trace: STEP_INFO[step].trace,
    why: `Step ${i + 1} of 12 in Hermes Agent.`, status: hw, sources: [H.arch], x: HX - 10, y: Y[step], w: ROW_W + 20, h: BAND_H[step] ?? 100, band: true,
  }));
  out.push(
    { id: 'h_title', label: 'Version 4: Hermes Agent (Nous Research), 12 steps', sub: 'Same 12 steps as version 2. Every box links the Hermes docs page it comes from.', x: HX - 290, y: -110, w: 1280, h: 60, band: true, status: hw, why: 'Hermes is a ready-made agent you configure. Claude Code is Anthropic\'s; the Agent SDK is the kit to build your own.', sources: [H.docs, H.repo] },
    { id: 'h_band_lib', label: 'Setup: the ~/.hermes folder', sub: '', why: 'Files you set up once per agent (profile).', status: hw, sources: [H.which, H.profiles], x: HX - 290, y: Y.client, w: 250, h: BOTTOM - Y.client - 30, band: true },
    { id: 'h_band_rails', label: 'True at every step', sub: '', why: 'These apply the whole time.', status: hw, sources: [H.arch], x: HX + 790, y: Y.ui, w: 200, h: BOTTOM - Y.ui - 30, band: true },
  );
  return out;
}

// ---------- detail cards ----------
const DET: Record<string, FullDetail> = {
  h_soul: {
    plain: [
      'SOUL.md is WHO the agent is: personality, tone, how it talks, what it avoids. It is the very first thing in the prompt (slot 1) and replaces the built-in identity.',
      'It lives only in the agent\'s home folder (~/.hermes/SOUL.md, or that profile\'s home). Hermes never reads a SOUL.md from your project folder.',
      'Hermes writes a starter SOUL.md if none exists and never overwrites yours. Empty or unreadable means it falls back to the built-in identity.',
      'Project rules do NOT go here; those go in AGENTS.md. Facts about you go in USER.md (memory).',
      'Helpers made with delegate_task do not get SOUL.md: they run with the built-in default identity.',
    ],
    pictures: [{ kind: 'flow', title: 'The order the prompt is built in', caption: 'From the Hermes prompt-assembly and personality pages.', steps: [
      { label: 'SOUL.md', note: 'who it is (slot 1)', tone: 'good' },
      { label: 'Tool and model guidance' },
      { label: 'Project file', note: '.hermes.md, AGENTS.md, CLAUDE.md or .cursorrules (first found wins)' },
      { label: 'Skills index, MEMORY.md, USER.md', note: 'snapshot taken at session start' },
      { label: 'Time and platform hints', note: 'for example "you are on Telegram"' },
    ] }],
    examples: [{ title: 'A SOUL.md for an agency ops bot', file: '~/.hermes/profiles/javar/SOUL.md', why: 'Voice and standing behavior only. No client facts, no tool steps.', code: L(
      'You are Javar, the ops assistant for Increase ROAS.',
      'Talk like a sharp teammate: short, direct, answer first.',
      'Never pretend something worked. Say: written, configured, or seen working.',
      'If a request would spend money or message a client, stop and ask Alex first.') }],
    decide: [
      { if: 'It is about tone, voice or personality', then: 'SOUL.md' },
      { if: 'It is about a project or client (folders, rules, never-dos)', then: 'AGENTS.md in that folder' },
      { if: 'It is a fact about you', then: 'Tell the agent; it saves it to USER.md' },
      { if: 'It is a step-by-step procedure', then: 'A skill' },
    ],
    myths: [{ myth: 'SOUL.md is where all the rules go.', truth: 'SOUL.md is identity and style. The Hermes docs say to move project instructions into AGENTS.md and keep SOUL.md focused on identity.', fix: 'Keep SOUL.md to a few lines of voice and standing behavior; put client rules in each client folder\'s AGENTS.md.' }],
  },
  h_ctx: {
    plain: [
      'The project file holds the rules for the folder the agent works in.',
      'Only ONE kind loads per session, first match wins: .hermes.md, then AGENTS.override.md, then AGENTS.md, then CLAUDE.md, then .cursorrules.',
      'AGENTS.md and CLAUDE.md are read from the starting folder, and from subfolders as the agent works in them.',
      'Every file is scanned for prompt-injection text before it loads. Files over the size cap get cut (70% head, 20% tail).',
      'So the agency repo we designed works for Hermes too: one AGENTS.md at the top, one per client folder.',
    ],
    myths: [{ myth: 'If I have both AGENTS.md and CLAUDE.md, Hermes reads both.', truth: 'First match wins, so with AGENTS.md present, CLAUDE.md is not loaded.', fix: 'Put shared rules in AGENTS.md and make CLAUDE.md point to it, so every agent reads the same rules.' }],
  },
  h_mem: {
    plain: [
      'Two small files the agent writes itself with the memory tool: MEMORY.md (its notes: environment, conventions, tool quirks) and USER.md (you: preferences, style).',
      'Hard caps: MEMORY.md about 2,200 characters, USER.md about 1,375. Small on purpose.',
      'Both load as a frozen snapshot at session start. A save mid-chat hits the disk now but only shows up in the next session.',
      'For history, the agent uses session_search across past chats instead of loading it.',
      'You can make memory writes wait for your approval.',
    ],
    myths: [{ myth: 'Memory means the agent remembers everything.', truth: 'It keeps a few thousand characters of notes plus searchable old sessions.', fix: 'Keep durable facts short, let session_search find history, and run /new at natural breaks so new notes load.' }],
  },
  h_loop: {
    plain: [
      'The harness is the loop around the model: build the prompt, call the model, run any tool calls, feed the results back, repeat until there is a final answer, then save the session.',
      'It also handles retries, fallback models, compression and saving.',
      'Every tool call is shown as it happens, and you can interrupt it mid-flight.',
      'Three things help it finish jobs: /goal (keeps going until a judge says done), execute_code (many tool calls in one turn) and delegate_task (fresh helpers for side work).',
    ],
    pictures: [{ kind: 'flow', title: 'One turn of the Hermes loop', caption: 'From the Hermes architecture page.', steps: [
      { label: 'Message in', note: 'CLI, Telegram, cron, webhook' },
      { label: 'Build the system prompt', note: 'SOUL, project file, skills, memory' },
      { label: 'Call the model', note: 'any provider' },
      { label: 'Tool calls?', many: ['yes: run the tool, add the result, loop', 'no: final answer'] },
      { label: 'Save to the session database', tone: 'good' },
    ] }],
  },
  h_goal: {
    plain: [
      '/goal sets a standing objective. After every turn a small judge model decides: done, continue or blocked.',
      'If continue, Hermes feeds itself the next step automatically.',
      'Default budget: 20 continuation turns, then it pauses and asks you to /goal resume or /goal clear.',
      'Same idea as Claude Code\'s /goal: a finish line the agent cannot skip.',
    ],
    examples: [{ title: 'Finish line for a client job', file: 'In Telegram', why: 'A concrete check the judge can see in the reply.', code: L('/goal Oak Ridge test form submits, the fake lead appears in the GHL test sub-account, and you paste the contact ID') }],
    myths: [{ myth: 'The judge runs my tests.', truth: 'The judge reads the agent\'s last reply and decides whether the goal is met.', fix: 'Write the goal so the reply must include proof (a test result, an ID, a screenshot), and have the agent run the real check.' }],
  },
  h_deleg: {
    plain: [
      'delegate_task starts child agents with a fresh, empty context. They know only the goal and context the parent writes for them.',
      'Only each child\'s final summary comes back, so the parent chat stays small.',
      'Children inherit the parent\'s tools; the model cannot give a child more tools than the parent has.',
      'Flat by default: children cannot start their own children unless you raise max_spawn_depth.',
      'The delegation page says up to 10 run at once by default (configurable).',
    ],
    myths: [{ myth: 'A helper knows everything the main chat knows.', truth: 'It starts with zero history and without SOUL.md.', fix: 'Have the parent pass the client, the files that matter and the finish line in the delegate_task context.' }],
  },
  h_approve: {
    plain: [
      'Before running a command, Hermes checks it against a list of dangerous patterns. A match needs your explicit approval.',
      'Running inside a container backend (Docker, Modal, Daytona and others) skips these prompts, because the container is the safety wall.',
      'approvals.mode: off turns the prompts off. The docs say only in trusted places like CI or containers.',
      'Who can talk to the bot at all is a separate gate: allowlists or DM pairing. By default everyone else is denied.',
    ],
    myths: [{ myth: 'Approval prompts protect my GHL clients.', truth: 'They cover dangerous shell commands. A tool call to an API (MCP, Composio) is not a shell command.', fix: 'Add a pre_tool_call hook that blocks spend, send, delete and wrong-client calls before any tool runs.' }],
  },
  h_hook: {
    plain: [
      'Hermes has four hook systems: gateway hooks (logging, alerts), plugin hooks (code), shell hooks (scripts listed in config.yaml) and outbound webhooks.',
      'A shell pre_tool_call hook can block a tool call. Any block beats any approve.',
      'If a plugin pre_tool_call hook times out or crashes, Hermes blocks the tool (fails closed).',
      'This is where Javar\'s client lock and spend guard belong, since he has no Composio guard today.',
    ],
    examples: [{ title: 'Shape of a blocking hook', file: '~/.hermes/profiles/javar/config.yaml', why: 'Shape only: check the hooks page for the exact keys your Hermes version uses.', code: L(
      'hooks:',
      '  pre_tool_call:',
      '    - command: ~/.hermes/hooks/client-lock.sh',
      '      timeout: 10') }],
    myths: [{ myth: 'Hooks only log things.', truth: 'Control hooks can block, and transform hooks can change arguments.', fix: 'Put your must-never rules in a pre_tool_call hook, not only in SOUL.md or AGENTS.md.' }],
  },
  h_compress: {
    plain: [
      'When a chat gets long, Hermes summarizes the middle turns (lossy) and keeps going. /compress does it on demand.',
      'On Telegram a chat is one session that never resets on its own, even across restarts. It can run for weeks.',
      'The Hermes docs say that gets expensive and the learning loop barely fires. Run /new at natural boundaries: a finished task, a topic change, the start of a day.',
      'Name it (/new oak-ridge-routing) so you can /resume it later.',
    ],
    myths: [{ myth: 'One endless Telegram chat with the bot is fine.', truth: 'Compression keeps re-summarizing a growing history, new memory stays invisible, and session_search rarely gets used.', fix: '/new at the end of each job or each day; the agent starts small and reloads fresh memory.' }],
  },
  h_skills: {
    plain: [
      'Skills are procedures that load only when needed (progressive disclosure), in the agentskills.io format.',
      'The agent writes and edits its own skills with skill_manage when it figures out a non-trivial workflow.',
      'write_approval: true stages every skill change in ~/.hermes/pending for you to review first.',
      'The curator marks skills unused for 14 days as stale and archives them at 30. It never deletes.',
    ],
    myths: [{ myth: 'Self-written skills are always improvements.', truth: 'They are drafts from one session.', fix: 'Turn on write_approval and keep a few real test jobs to rerun before accepting big skill changes.' }],
  },
  h_profile: {
    plain: [
      'A profile is a separate Hermes home: its own config.yaml, .env, SOUL.md, memory, sessions, skills and cron jobs.',
      'One profile per bot (Javar, Javante). Bot Mode turns profiles into named bots with their own chats that can message each other.',
      'Clients are folders, not profiles: the bot works in clients/oak-ridge-tree/ and that folder\'s AGENTS.md loads.',
    ],
    myths: [{ myth: 'Each client needs its own Hermes profile.', truth: 'A profile is an agent identity with its own memory and keys. Clients are projects.', fix: 'One profile per bot, one folder (with AGENTS.md) per client, and a hook that locks each job to its client.' }],
  },
  h_x_vs: {
    plain: [
      'Same idea in both: a project rules file, skills, small memory, helpers with fresh context, hooks that can block, a /goal finish line, compression.',
      'Hermes adds: the SOUL.md identity file, a messaging gateway on 20+ apps, built-in cron, any model provider, and self-written skills with a curator.',
      'Claude Code adds: permission rules (deny, ask, allow) on every tool, auto memory with a 200-line index, and the Agent SDK to build your own agent.',
      'Hermes can import a Claude Code or Codex setup in one command (instructions, allowlists, MCP servers, skills, memories).',
    ],
  },
};

const ask: Spec[] = [
  { id: 'h_you', label: 'You message it', sub: 'Telegram, CLI, desktop', why: 'You talk to it wherever it lives; it can run on a cloud machine you never log into.', sources: [H.docs, H.msg] },
  { id: 'h_goal', label: 'Set a /goal', sub: 'Keeps going until done', why: 'A judge checks every turn: done, continue or blocked. 20-turn budget by default.', sources: [H.goals], detail: DET.h_goal },
  { id: 'h_cron', label: 'Or a schedule or webhook', sub: 'Built-in cron', why: 'Cron jobs run in a fresh session, can attach skills, and deliver results to any chat. A webhook can fire a job right away.', sources: [H.cron] },
];
const ui: Spec[] = [
  { id: 'h_gateway', label: 'Gateway', sub: 'One process, 20+ apps', why: 'One background process connects every platform, keeps a session per chat, and ticks the cron scheduler every 60 seconds.', sources: [H.msg] },
  { id: 'h_auth', label: 'Who may talk', sub: 'Allowlist or DM pairing', why: 'By default the gateway denies anyone not allowlisted or paired. Admin vs regular user controls slash commands.', sources: [H.msg, H.sec] },
  { id: 'h_session', label: 'One chat = one session', sub: 'Survives restarts', why: 'A messaging chat is one continuous session until /new, even across reboots.', sources: [H.mem, H.sessions] },
];
const client: Spec[] = [
  { id: 'h_profile', label: 'Profile = one agent', sub: 'Own SOUL, memory, keys', why: 'Each profile is its own home folder: config, secrets, SOUL.md, memory, sessions, skills, cron.', sources: [H.profiles], detail: DET.h_profile },
  { id: 'h_workdir', label: 'Working folder', sub: 'Picks the project rules', why: 'Project files load from where the agent starts. Cron jobs load none unless you set workdir.', sources: [H.ctx, H.cron] },
  { id: 'h_bots', label: 'Bot Mode', sub: 'Named bots, own chats', why: 'Profiles become named bots with their own role, model, memory and skills; they share group chats and message each other.', sources: [H.bots], badge: 'Optional' },
];
const front: Spec[] = [
  { id: 'h_soul', label: 'SOUL.md', sub: 'Who it is (slot 1)', why: 'The identity file: first thing in the prompt, from the agent home only.', sources: [H.soul, H.soulGuide, H.which, H.prompt], detail: DET.h_soul },
  { id: 'h_ctx', label: 'Project file', sub: 'AGENTS.md, first match wins', why: '.hermes.md, AGENTS.md, CLAUDE.md or .cursorrules: only one kind loads, after an injection scan.', sources: [H.ctx], detail: DET.h_ctx },
  { id: 'h_mem', label: 'MEMORY.md + USER.md', sub: 'Small, frozen at start', why: 'Agent notes (about 2,200 chars) and your profile (about 1,375 chars), snapshotted at session start.', sources: [H.mem, H.which], detail: DET.h_mem },
  { id: 'h_skillidx', label: 'Skills index', sub: 'Names now, body on demand', why: 'Only the skills list is in the prompt; a skill\'s full text loads when it is used.', sources: [H.skills, H.prompt] },
];
const plan: Spec[] = [
  { id: 'h_loop', label: 'The agent loop', sub: 'Model, tools, repeat', why: 'Build prompt, call model, run tools, feed results back, until a final answer; then save the session.', sources: [H.arch], detail: DET.h_loop },
  { id: 'h_todo', label: 'todo + clarify', sub: 'Track steps, ask if unsure', why: 'Built-in toolsets for a step list and for asking you a question mid-task.', sources: [H.tools] },
  { id: 'h_code', label: 'execute_code', sub: 'Many steps, one turn', why: 'The agent writes a Python script that calls its tools; only the printed result enters the chat.', sources: [H.code] },
];
const delegate: Spec[] = [
  { id: 'h_self', label: 'Does it itself', sub: 'Most jobs', why: 'Most turns are the main agent calling tools directly.', sources: [H.arch] },
  { id: 'h_deleg', label: 'delegate_task', sub: 'Fresh child, summary back', why: 'Children start empty, inherit the parent\'s tools, and return only a summary.', sources: [H.deleg], detail: DET.h_deleg },
  { id: 'h_kanban', label: 'Kanban board', sub: 'Bots share a task board', why: 'A lasting task board that coordinates several Hermes profiles.', sources: [H.kanban], badge: 'When useful' },
];
const know: Spec[] = [
  { id: 'h_toolsets', label: 'Toolsets', sub: 'On or off per platform', why: 'Tools come in groups (web, terminal, file, browser, memory, delegation and more) you enable per platform.', sources: [H.tools] },
  { id: 'h_mcp', label: 'MCP servers', sub: 'Outside tools, filtered', why: 'Connect MCP servers and filter which of their tools the agent sees.', sources: [H.mcp] },
  { id: 'h_toolsearch', label: 'Tool Search', sub: 'Tool details on demand', why: 'Opt-in: MCP and plugin tools are swapped for 3 bridge tools, and schemas load only when needed.', sources: [H.toolSearch] },
  { id: 'h_ssearch', label: 'session_search', sub: 'Search past chats', why: 'Full-text search across every past session, no model calls, returns the real messages.', sources: [H.sessions] },
];
const gw: Spec[] = [
  { id: 'h_approve', label: 'Dangerous command check', sub: 'You approve risky ones', why: 'Commands matching dangerous patterns need your approval, unless running inside a container.', sources: [H.sec], detail: DET.h_approve },
  { id: 'h_hook', label: 'pre_tool_call hook', sub: 'Can block, fails closed', why: 'Your hook sees every tool call first and can block it.', sources: [H.hooks], detail: DET.h_hook },
  { id: 'h_box', label: 'Container backend', sub: 'The box is the wall', why: 'Docker, Modal, Daytona and others isolate commands from the host; the docs recommend it for production gateways.', sources: [H.sec, H.tools] },
  { id: 'h_scan', label: 'File injection scan', sub: 'Before project files load', why: 'Project files are checked for prompt-injection text before they enter the prompt.', sources: [H.sec, H.ctx] },
];
const run: Spec[] = [
  { id: 'h_term', label: 'Terminal backends', sub: 'Local, Docker, SSH, cloud', why: 'Commands run where you choose: your machine, a container, a remote server or a cloud sandbox.', sources: [H.tools] },
  { id: 'h_result', label: 'Result back to the loop', sub: 'Next tool, or answer', why: 'Each tool result is added and the model picks the next move.', sources: [H.arch] },
  { id: 'h_ckpt', label: 'Checkpoints + /rollback', sub: 'Opt-in snapshots', why: 'Snapshots before file writes and destructive commands; /rollback restores only files Hermes changed.', sources: [H.ckpt], badge: 'Opt-in' },
  { id: 'h_compress', label: 'Compression', sub: 'Long chat gets summarized', why: 'Middle turns get summarized when the chat passes a threshold; /compress does it on demand.', sources: [H.arch, H.sessions, H.mem], detail: DET.h_compress },
];
const verify: Spec[] = [
  { id: 'h_judge', label: 'Goal judge', sub: 'done, continue, blocked', why: 'With /goal set, a small model checks each reply against the goal.', sources: [H.goals] },
  { id: 'h_lsp', label: 'Post-write lint', sub: 'Real language servers', why: 'File writes and patches get a lint check from real language servers (pyright, gopls, rust-analyzer and others).', sources: [H.lsp] },
  { id: 'h_yourcheck', label: 'Your own check', sub: 'Not built in', why: 'Hermes does not know your tests. Have the agent run them, require proof in the /goal, or run them from a hook.', sources: [H.goals, H.hooks] },
];
const report: Spec[] = [
  { id: 'h_reply', label: 'Reply in the same chat', sub: 'Files as attachments', why: 'Charts, PDFs and sheets arrive as native attachments on the platform.', sources: [H.deliver] },
  { id: 'h_dash', label: 'Web dashboard', sub: 'Sessions, logs, analytics', why: 'Browser panel for config, keys, MCP servers, pairing, sessions, logs, analytics, cron and skills.', sources: [H.dash] },
];
const learn: Spec[] = [
  { id: 'h_memtool', label: 'memory tool', sub: 'Saves short facts', why: 'The agent adds, replaces or removes memory entries; you can require approval.', sources: [H.mem] },
  { id: 'h_skills', label: 'Writes its own skills', sub: 'skill_manage', why: 'After a hard workflow it saves the steps as a skill for next time.', sources: [H.skills], detail: DET.h_skills },
  { id: 'h_wapprove', label: 'write_approval', sub: 'You review changes', why: 'Skill and memory writes can be staged for your review before they land.', sources: [H.skills, H.mem] },
  { id: 'h_curator', label: 'Curator', sub: 'Stale, then archived', why: 'Tracks skill use: unused 14 days = stale, 30 = archived. Never deletes.', sources: [H.curator] },
  { id: 'h_new', label: '/new at boundaries', sub: 'Fresh memory loads', why: 'New memory only shows up in a new session, so reset at the end of a job or a day.', sources: [H.mem, H.sessions] },
];
const lib: Spec[] = [
  { id: 'h_lib_home', label: '~/.hermes', sub: 'One home per agent', why: 'config.yaml, .env, SOUL.md, memories/, skills/, sessions (state.db), cron jobs.', sources: [H.which, H.profiles] },
  { id: 'h_lib_config', label: 'config.yaml', sub: 'Model, tools, hooks, approvals', why: 'Provider and model, enabled toolsets, hooks, approvals, delegation and goal limits.', sources: [H.config] },
  { id: 'h_lib_env', label: '.env + secrets', sub: 'Keys stay out of chat', why: 'Keys live in the profile .env with tight file permissions, or in a secrets manager.', sources: [H.sec] },
  { id: 'h_lib_skills', label: 'skills/', sub: 'agentskills.io format', why: 'Your skills plus Skills Hub installs, in the same open format other agents use.', sources: [H.skills] },
  { id: 'h_lib_plugins', label: 'hooks/ + plugins/', sub: 'Extend without code edits', why: 'Gateway hooks, plugin hooks, shell hooks and plugins live in the home folder.', sources: [H.hooks] },
  { id: 'h_lib_import', label: 'Import Claude Code', sub: 'One command', why: 'Brings in a ~/.claude or ~/.codex setup: instructions, allowlists, MCP servers, skills, memories.', sources: [H.importer] },
];
const rails: Spec[] = [
  { id: 'h_x_model', label: 'Any model', sub: 'Portal, OpenRouter, more', why: 'Works with Nous Portal, OpenRouter, OpenAI, Anthropic, Google or any compatible endpoint.', sources: [H.docs] },
  { id: 'h_x_iso', label: 'Sessions isolated', sub: 'No peeking across', why: 'Sessions cannot read each other\'s data or state.', sources: [H.sec] },
  { id: 'h_x_seen', label: 'You see every call', sub: 'Interrupt any time', why: 'Every tool call is shown via callbacks and can be cancelled mid-flight.', sources: [H.arch] },
  { id: 'h_x_vs', label: 'vs Claude Code', sub: 'Same ideas, different files', why: 'What matches and what differs between Hermes and Claude Code.', sources: [H.importer, H.ctx, H.soul], detail: DET.h_x_vs },
];

export const H_NODES: ProNode[] = [
  ...bands(),
  ...row('ask', ask), ...row('ui', ui), ...row('client', client), ...row('front', front), ...row('plan', plan),
  ...row('delegate', delegate), ...row('know', know), ...row('gw', gw), ...row('run', run), ...row('verify', verify),
  ...row('report', report), ...row('learn', learn),
  ...column(HX - 270, Y.client, lib, 210),
  ...column(HX + 805, Y.ui, rails, 170),
];

const flow = (a: string, b: string, label?: string): ProEdge => ({ id: `${a}-${b}`, source: a, target: b, kind: 'flow', label });
const loop = (a: string, b: string, label: string): ProEdge => ({ id: `${a}-${b}-loop`, source: a, target: b, kind: 'loop', label, sh: 'rs', th: 'r' });
const link = (a: string, b: string, label: string, sh: 'ls' | 'rs', th: 'l' | 'r'): ProEdge => ({ id: `${a}-${b}`, source: a, target: b, kind: 'link', label, sh, th });

export const H_EDGES: ProEdge[] = [
  flow('h_you', 'h_gateway', 'message'),
  { ...flow('h_cron', 'h_profile', 'fresh session'), sh: 'rs', th: 'r', offset: 30 },
  flow('h_gateway', 'h_profile', 'routes to the bot'),
  flow('h_profile', 'h_soul', 'its home loads'),
  flow('h_workdir', 'h_ctx', 'project rules'),
  flow('h_band_front', 'h_loop', 'prompt ready'),
  flow('h_loop', 'h_self'),
  flow('h_loop', 'h_deleg'),
  flow('h_self', 'h_band_know', 'needs a tool'),
  flow('h_deleg', 'h_band_know', 'children use the same loop'),
  flow('h_band_know', 'h_band_gw', 'tool call'),
  flow('h_band_gw', 'h_band_run', 'allowed'),
  flow('h_band_run', 'h_band_verify', 'answer drafted'),
  flow('h_judge', 'h_reply', 'done'),
  { ...loop('h_result', 'h_band_know', 'more work'), offset: 15 },
  { ...loop('h_judge', 'h_band_know', 'continue'), offset: 30 },
  flow('h_band_report', 'h_band_learn', 'after'),
  link('h_band_front', 'h_lib_home', 'reads', 'ls', 'r'),
  link('h_band_gw', 'h_lib_config', 'rules from', 'ls', 'r'),
];
