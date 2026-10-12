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
  overview: `${D}/user-guide/features/overview`,
  ccPerm: 'https://code.claude.com/docs/en/permissions',
  ccMem: 'https://code.claude.com/docs/en/memory',
  ccSdk: 'https://code.claude.com/docs/en/agent-sdk/overview',
  ccHooks: 'https://code.claude.com/docs/en/hooks',
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

const STEP_INFO: Record<Step, { label: string; tag: string; trace: string; src: string[] }> = {
  ask: { label: 'Request starts', tag: 'saved to the session', trace: 'Every conversation is saved as a session in a local database (state.db), searchable later.', src: [H.sessions] },
  ui: { label: 'Where you talk', tag: 'one session per chat', trace: 'Chat apps go through the gateway, which keeps each chat as its own session until /new. The CLI talks to the agent directly.', src: [H.msg, H.arch] },
  client: { label: 'Which agent and which folder', tag: 'profile + workdir', trace: 'The profile (its own home folder) and the working folder decide which identity, memory and project files load.', src: [H.profiles, H.ctx] },
  front: { label: 'Build the system prompt', tag: '/context shows it', trace: 'Project files are scanned, then the prompt is built: SOUL.md first, project rules, then skills index and memory snapshots. /context lists what loaded.', src: [H.prompt, H.ctx] },
  plan: { label: 'The loop decides the next move', tag: 'progress (configurable)', trace: 'Tool progress shows in the terminal, and in chat apps if that platform\'s display setting turns it on.', src: [H.arch, H.msg] },
  delegate: { label: 'Optional: hand out tasks', tag: 'child summaries', trace: 'Each child starts without the chat history; only its final summary comes back to the parent.', src: [H.deleg] },
  know: { label: 'Find information and choose a tool', tag: 'tool + args', trace: 'Tool name and arguments pass through hooks (pre_tool_call sees them).', src: [H.tools, H.hooks] },
  gw: { label: 'Safety checks before it runs', tag: 'approvals + hook blocks', trace: 'Approval decisions (smart, manual or your reply) and any hook block message.', src: [H.sec, H.hooks] },
  run: { label: 'Run it and read the result', tag: 'tool result', trace: 'The result goes back into the loop, and the model picks the next move.', src: [H.arch] },
  verify: { label: 'Check the result (with /goal)', tag: 'gates + judge verdict', trace: 'Gates run first; then the judge returns done, continue, wait or blocked.', src: [H.goals] },
  report: { label: 'Answer you', tag: 'reply + files', trace: 'The reply lands in the same chat; files go as native attachments.', src: [H.deliver] },
  learn: { label: 'Optional: learn for next time', tag: 'memory + skills', trace: 'Memory writes save to disk now; the prompt snapshot refreshes next session.', src: [H.mem, H.skills] },
};

function bands(): ProNode[] {
  const out: ProNode[] = STEPS.map((step, i) => ({
    id: `h_band_${step}`, label: `${i + 1}. ${STEP_INFO[step].label}`, sub: '', tag: STEP_INFO[step].tag, trace: STEP_INFO[step].trace,
    why: `Step ${i + 1} of 12 in Hermes Agent.`, status: hw, sources: STEP_INFO[step].src, x: HX - 10, y: Y[step], w: ROW_W + 20, h: BAND_H[step] ?? 100, band: true,
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
  h_rulegate: {
    plain: [
      'Same idea as Claude Code: each connector gets a short rules file, each repeat job gets a skill with the if/else inside.',
      'Hermes has no rules/ folder. Folder rules come from AGENTS.md files, and subfolder ones are picked up as the agent works there.',
      'A connector call is not a folder, so use a pre_tool_call hook as the gate: first call to that connector this session is blocked, with its rules in the block message; the agent reads them and retries.',
      'Only hooks you configured and approved run. Set the hook to fail closed so a crashed script still blocks.',
      'Skills are the same open format (agentskills.io), so the website-build, ad-copy, ghl-workflow-edit and hot-leads skills work here too.',
    ],
    pictures: [{ kind: 'flow', title: 'Read-first gate in Hermes', steps: [
      { label: 'Agent calls a GHL tool' },
      { label: 'pre_tool_call hook: rules read this session?', many: ['no: block, message carries the GHL rules', 'yes: allow'], tone: 'bad' },
      { label: 'Agent reads the rules, retries' },
      { label: 'Allowed; later calls pass', tone: 'good' },
    ] }],
    examples: [{ title: 'Shape of the gate hook', file: '~/.hermes/profiles/javar/config.yaml', why: 'Shape only: confirm the exact keys and the block output format on the hooks page for your version.', code: L(
      'hooks:',
      '  pre_tool_call:',
      '    - command: ~/.hermes/hooks/read-rules-first.sh',
      '      timeout: 10',
      '      fail_closed: true') }],
    myths: [{ myth: 'Putting connector rules in AGENTS.md means Javar reads them before every call.', truth: 'AGENTS.md is read at start, and long files get cut. Nothing forces a re-read right before a risky call.', fix: 'Keep a short rules file per connector and gate the first call with a pre_tool_call hook.' }],
  },
  h_soul: {
    plain: [
      'SOUL.md is WHO the agent is: personality, tone, how it talks, what it avoids. It is the very first thing in the prompt (slot 1) and replaces the built-in identity.',
      'It lives only in the agent\'s home folder (~/.hermes/SOUL.md, or that profile\'s home). Hermes never reads a SOUL.md from your project folder.',
      'Hermes writes a starter SOUL.md if none exists and never overwrites yours. Empty or unreadable means it falls back to the built-in identity.',
      'Project rules do NOT go here; those go in AGENTS.md. Facts about you go in USER.md (memory).',
      'Helpers made with delegate_task do not get SOUL.md: they run with the built-in default identity (they do get the project files).',
    ],
    pictures: [{ kind: 'flow', title: 'Simplified order the prompt is built in', caption: 'Simplified from the Hermes prompt-assembly page (stable, then context, then volatile). Not an exact trace.', steps: [
      { label: 'SOUL.md + tool guidance', note: 'who it is (slot 1)', tone: 'good' },
      { label: 'Project file + platform hints', note: '.hermes.md, AGENTS.md chain, CLAUDE.md or .cursorrules; "you are on Telegram"' },
      { label: 'Skills index, MEMORY.md, USER.md', note: 'snapshot taken at session start' },
      { label: 'Time, session and model line' },
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
      'One kind of project file is picked, first match wins: .hermes.md, then AGENTS.override.md, then AGENTS.md, then CLAUDE.md, then .cursorrules.',
      'AGENTS.md loads as a chain from the git root down to the working folder (outside git, only the working folder); more are picked up from subfolders as it works. Other file types have their own discovery rules.',
      'Every file is scanned for prompt-injection text before it loads. Files over the size cap get cut (70% head, 20% tail).',
      'So the agency repo we designed works for Hermes too: one AGENTS.md at the top, one per client folder.',
    ],
    myths: [{ myth: 'If I have both AGENTS.md and CLAUDE.md, Hermes reads both.', truth: 'First match wins, so with AGENTS.md present, CLAUDE.md is not loaded.', fix: 'Put shared rules in AGENTS.md and make CLAUDE.md point to it, so every agent reads the same rules.' }],
  },
  h_mem: {
    plain: [
      'Two small files the agent writes itself with the memory tool: MEMORY.md (its notes: environment, conventions, tool quirks) and USER.md (you: preferences, style).',
      'Default limits: MEMORY.md 2,200 characters, USER.md 1,375 (memory_char_limit and user_char_limit in config.yaml). Small on purpose.',
      'Both load as a frozen snapshot at session start. A save mid-chat hits the disk now; the prompt snapshot refreshes next session, while the memory tool itself shows the current state.',
      'For history, the agent uses session_search across past chats instead of loading it.',
      'You can make memory writes wait for your approval.',
    ],
    myths: [{ myth: 'Memory means the agent remembers everything.', truth: 'It keeps a few thousand characters of notes plus searchable old sessions.', fix: 'Keep durable facts short, let session_search find history, and run /new at natural breaks so new notes load.' }],
  },
  h_loop: {
    plain: [
      'The harness is the loop around the model: build the prompt, call the model, run any tool calls, feed the results back, repeat until there is a final answer, then save the session.',
      'It also handles retries, fallback models, compression and saving.',
      'Tool progress is shown in the terminal, and in chat apps when that platform\'s setting turns it on. You can stop a run, but actions already finished are not undone.',
      'What helps it finish jobs: a completion contract (outcome, proof, stop rules), /goal with test gates, execute_code (many tool calls in one turn) and delegate_task (fresh helpers for side work).',
    ],
    pictures: [{ kind: 'flow', title: 'One turn of the Hermes loop', caption: 'From the Hermes architecture page. /goal adds the gates-and-judge step after the answer.', steps: [
      { label: 'Message in', note: 'CLI direct, or chat app through the gateway, cron, webhook' },
      { label: 'Build the system prompt', note: 'SOUL, project file, skills, memory' },
      { label: 'Call the model', note: 'any provider' },
      { label: 'Tool calls?', many: ['yes: run the tool, add the result, loop', 'no: final answer'] },
      { label: 'If /goal is set', many: ['gates fail: failure fed back, loop', 'judge: done, continue, wait, blocked'] },
      { label: 'Save to the session database', tone: 'good' },
    ] }],
  },
  h_goal: {
    plain: [
      '/goal sets a standing objective. After every turn a judge decides: done, continue, wait (parked on a background process) or blocked.',
      'The judge uses your main model by default; you can point it at a cheaper model.',
      'Gates are stronger than the judge: /goal gate add <command> adds a shell command that must pass before the goal can be done. A failing gate feeds its output back so the agent fixes the real failure.',
      'Default budget: 20 continuation turns, then it pauses and asks you to /goal resume or /goal clear.',
      'Gates block completion while your checks fail; passing checks do not prove anything you did not test. The judge can still misjudge prose.',
      'In chat apps, adding a gate needs a configured gateway admin.',
      'A failing gate retries (3 times by default, 5-minute command timeout) and then the goal pauses.',
    ],
    examples: [{ title: 'Finish line with a real test gate', file: 'In the Hermes chat', why: 'The gate must pass before the judge is even asked.', code: L(
      '/goal Oak Ridge test form routes a fake lead into the GHL test sub-account',
      '/goal gate add python3 checks/oak_ridge_form_test.py') }],
    decide: [
      { if: 'The check is a command you can run', then: 'Add it as a gate' },
      { if: 'The agent is waiting on a long job', then: 'The judge can return wait; /goal unwait resumes' },
      { if: 'It hit 20 turns', then: '/goal resume to keep going, or /goal clear' },
    ],
    myths: [{ myth: 'The judge runs my tests.', truth: 'The judge reads the agent\'s last reply. Only gates run commands.', fix: 'Add your test as a /goal gate so a red test blocks "done".' }],
  },
  h_deleg: {
    plain: [
      'delegate_task starts child agents without the chat history. They know the goal and context the parent writes, plus the workspace project files (AGENTS.md and so on), but not SOUL.md.',
      'Only each child\'s final summary comes back, so the parent chat stays small.',
      'Children inherit the parent\'s tools minus blocked ones: no asking you questions (clarify), no memory writes, no scheduling.',
      'Flat by default. A child can only hand out work if it is given the orchestrator role AND max_spawn_depth is raised.',
      'How many at once: the delegation page says 10 by default (configurable); the features overview page says 3. Check your config.',
      'A top-level delegate_task returns a handle right away; the summaries arrive later. A child can also come back with a budget or stall failure, so the parent must check the outcome.',
      '/review starts a background reviewer helper that checks a piece of work against the loaded skills and project rules.',
    ],
    myths: [{ myth: 'A helper knows everything the main chat knows.', truth: 'It has the project files but none of the chat history and no SOUL.md.', fix: 'Have the parent pass the client, the files that matter and the finish line in the delegate_task context.' }],
  },
  h_approve: {
    plain: [
      'Before running a shell command, Hermes checks it against a list of dangerous patterns.',
      'Default mode is smart: a helper model auto-approves low-risk commands, auto-denies clearly dangerous ones, and asks you when unsure. Manual mode always asks. Off turns checks off (docs: trusted places only).',
      'Cron, single-query and webhook runs deny dangerous commands by default, since nobody is there to answer.',
      'Container backends (Docker, Modal, Daytona and others) skip these checks, because commands run isolated from your machine.',
      'Who can talk to the bot at all is a separate gate: allowlists or DM pairing. By default everyone else is denied.',
    ],
    myths: [{ myth: 'Approval prompts protect my GHL clients.', truth: 'They cover dangerous shell commands. A tool call to an API (MCP, Composio) is not a shell command.', fix: 'Add a pre_tool_call hook that blocks spend, send, delete and wrong-client calls before any tool runs.' }],
  },
  h_hook: {
    plain: [
      'Hermes has four hook systems: gateway hooks (logging, alerts), plugin hooks (code), shell hooks (scripts listed in config.yaml) and outbound webhooks.',
      'A pre_tool_call hook can block a tool call. Any block beats any approve.',
      'A plugin pre_tool_call hook that times out or crashes blocks the tool (fails closed). A shell hook can be set to fail closed too; check the hooks page for your version.',
      'Only hooks that are configured, consented to and matching run; an unapproved hook is skipped, so fail_closed alone protects nothing until the hook is registered.',
      'Your map shows Javar without a Composio guard (not re-checked today). If that is still true, this is where a client lock and spend guard would go.',
    ],
    examples: [{ title: 'Shape of a blocking shell hook', file: '~/.hermes/profiles/javar/config.yaml', why: 'Shape only: confirm the exact keys on the hooks page for your Hermes version.', code: L(
      'hooks:',
      '  pre_tool_call:',
      '    - command: ~/.hermes/hooks/client-lock.sh',
      '      timeout: 10',
      '      fail_closed: true') }],
    myths: [{ myth: 'Hooks only log things.', truth: 'Control hooks can block, and transform hooks can change arguments.', fix: 'Put your must-never rules in a pre_tool_call hook, not only in SOUL.md or AGENTS.md.' }],
  },
  h_compress: {
    plain: [
      'When a chat gets long, Hermes summarizes the middle turns (lossy) and keeps going. /compress does it on demand.',
      'On Telegram a chat is one session that never resets on its own, even across restarts. It can run for weeks.',
      'The Hermes docs say that gets expensive and the learning loop barely fires. Run /new at natural boundaries: a finished task, a topic change, the start of a day.',
      'Name it (/new oak-ridge-routing) so you can /resume it later.',
    ],
    myths: [{ myth: 'One endless Telegram chat with the bot is fine.', truth: 'Compression keeps re-summarizing a growing history, new memory never reaches the prompt snapshot, and session_search rarely gets used.', fix: '/new at the end of each job or each day; the agent starts small and reloads fresh memory.' }],
  },
  h_skills: {
    plain: [
      'Skills are procedures that load only when needed (progressive disclosure), in the agentskills.io format.',
      'The agent writes and edits its own skills with skill_manage when it figures out a non-trivial workflow.',
      'write_approval: true stages every skill change in ~/.hermes/pending for you to review first.',
      'After turns, a background review can apply memory and skill updates; approval settings can make it wait for your review first.',
      'The curator is separate upkeep: agent-created skills unused 14 days go stale, 30 days get archived (recoverable). Pinned skills and skills used by cron jobs are skipped.',
    ],
    myths: [{ myth: 'Self-written skills are always improvements.', truth: 'They are drafts from one session.', fix: 'Turn on write_approval and keep a few real test jobs to rerun before accepting big skill changes.' }],
  },
  h_profile: {
    plain: [
      'A profile is a separate Hermes home: its own config.yaml, .env, SOUL.md, memory, sessions, skills and cron jobs.',
      'One profile per bot (Javar, Javante). Bot Mode turns profiles into named bots with their own chats that can message each other.',
      'Recommendation (ours, not the docs): clients are folders, not profiles. The bot works in clients/oak-ridge-tree/ and that folder\'s AGENTS.md loads.',
    ],
    myths: [{ myth: 'Each client needs its own Hermes profile.', truth: 'A profile is an agent identity with its own memory and keys. Clients are projects.', fix: 'Recommendation: one profile per bot, one folder (with AGENTS.md) per client, and a hook that locks each job to its client.' }],
  },
  h_x_vs: {
    plain: [
      'Same idea in both: a project rules file, skills, small memory, helpers with fresh context, hooks that can block, compression, and a /goal command (Claude Code\'s is a built-in Stop hook; Hermes credits Codex CLI for its version).',
      'Hermes adds: the SOUL.md identity file, a messaging gateway on 20+ apps, built-in cron, any model provider, and self-written skills with a curator.',
      'Claude Code adds: permission rules (deny, ask, allow) on every tool, auto memory with a 200-line index, and the Agent SDK to build your own agent.',
      'Hermes can import a Claude Code or Codex setup in one command. It is a partial move: instructions become memory, credentials are not copied, and permissions do not carry over the same way.',
    ],
  },
};

const ask: Spec[] = [
  { id: 'h_you', label: 'You message it', sub: 'Chat app or CLI', why: 'You talk to it wherever it lives; it can run on a cloud machine you never log into.', sources: [H.docs, H.msg] },
  { id: 'h_goal', label: 'Optional: set a /goal', sub: 'Finish line + test gates', why: 'Keeps working across turns until gates pass and the judge says done, or it waits, gets blocked, or hits the 20-turn budget.', sources: [H.goals], badge: 'Optional', detail: DET.h_goal },
  { id: 'h_cron', label: 'Or a schedule or webhook', sub: 'Built-in cron', why: 'Cron jobs run in a fresh session, can attach skills, and deliver results to any chat. A webhook can fire a job right away.', sources: [H.cron] },
];
const ui: Spec[] = [
  { id: 'h_gateway', label: 'Gateway (chat apps)', sub: 'One process, 20+ apps', why: 'One background process connects every chat platform, keeps a session per chat, and ticks the cron scheduler every 60 seconds. The CLI does not go through it.', sources: [H.msg, H.arch] },
  { id: 'h_auth', label: 'Who may talk', sub: 'Allowlist or DM pairing', why: 'By default the gateway denies anyone not allowlisted or paired. Admin vs regular user controls slash commands.', sources: [H.msg, H.sec] },
  { id: 'h_session', label: 'One chat = one session', sub: 'Survives restarts', why: 'A messaging chat is one continuous session until /new, even across reboots. In groups, each person gets their own session by default.', sources: [H.mem, H.sessions] },
];
const client: Spec[] = [
  { id: 'h_profile', label: 'Profile = one agent', sub: 'Own SOUL, memory, keys', why: 'Each profile is its own home folder: config, secrets, SOUL.md, memory, sessions, skills, cron.', sources: [H.profiles], detail: DET.h_profile },
  { id: 'h_workdir', label: 'Working folder', sub: 'Picks the project rules', why: 'AGENTS.md loads as a chain from the git root down to the working folder (outside git, just the working folder). Cron jobs load none unless you set workdir.', sources: [H.ctx, H.cron] },
  { id: 'h_bots', label: 'Bot Mode', sub: 'Named bots, own chats', why: 'Profiles become named bots with their own role, model, memory and skills; they share group chats and message each other.', sources: [H.bots], badge: 'Optional' },
];
const front: Spec[] = [
  { id: 'h_scan', label: 'File injection scan', sub: 'Before files load', why: 'Project files are checked for prompt-injection text before they enter the prompt.', sources: [H.sec, H.ctx] },
  { id: 'h_soul', label: 'SOUL.md', sub: 'Who it is (slot 1)', why: 'The identity file: first thing in the prompt, from the agent home only.', sources: [H.soul, H.soulGuide, H.which, H.prompt], detail: DET.h_soul },
  { id: 'h_ctx', label: 'Project file', sub: 'AGENTS.md, first match wins', why: '.hermes.md, AGENTS.override.md, AGENTS.md, CLAUDE.md or .cursorrules: the first kind found is used.', sources: [H.ctx], detail: DET.h_ctx },
  { id: 'h_mem', label: 'MEMORY.md + USER.md', sub: 'Small, frozen at start', why: 'Agent notes and your profile (default limits 2,200 and 1,375 characters), snapshotted at session start.', sources: [H.mem, H.config, H.which], detail: DET.h_mem },
  { id: 'h_skillidx', label: 'Skills index', sub: 'Names now, body on demand', why: 'Only the skills list is in the prompt; a skill\'s full text loads when it is used.', sources: [H.skills, H.prompt] },
];
const plan: Spec[] = [
  { id: 'h_loop', label: 'The agent loop', sub: 'Model, tools, repeat', why: 'Build prompt, call model, run tools, feed results back, until a final answer; then save the session.', sources: [H.arch], detail: DET.h_loop },
  { id: 'h_contract', label: 'Completion contract', sub: 'Outcome, proof, stop rules', why: 'Spell out what done looks like, what proof to show and when to stop; it makes the goal judge stricter.', sources: [H.goals] },
  { id: 'h_todo', label: 'todo + clarify', sub: 'Track steps, ask if unsure', why: 'Built-in toolsets for a step list and for asking you a question mid-task.', sources: [H.tools] },
];
const delegate: Spec[] = [
  { id: 'h_self', label: 'Does it itself', sub: 'Simple jobs', why: 'Without delegation, the main agent calls its tools directly.', sources: [H.arch] },
  { id: 'h_deleg', label: 'delegate_task', sub: 'Fresh child, summary back', why: 'Children get no chat history (but do get project files), inherit the parent\'s tools minus blocked ones, and return only a summary.', sources: [H.deleg, H.overview], detail: DET.h_deleg },
  { id: 'h_kanban', label: 'Kanban board', sub: 'Bots share a task board', why: 'A lasting task board that coordinates several Hermes profiles.', sources: [H.kanban], badge: 'When useful' },
];
const know: Spec[] = [
  { id: 'h_toolsets', label: 'Toolsets', sub: 'On or off per platform', why: 'Tools come in groups (web, terminal, file, browser, memory, delegation and more) you enable per platform.', sources: [H.tools] },
  { id: 'h_mcp', label: 'MCP servers', sub: 'Outside tools, filtered', why: 'Connect MCP servers and filter which of their tools the agent sees.', sources: [H.mcp] },
  { id: 'h_toolsearch', label: 'Tool Search', sub: 'Tool details on demand', why: 'Opt-in: MCP and plugin tools (and chosen built-ins) are swapped for 3 bridge tools, and schemas load only when needed.', sources: [H.toolSearch] },
  { id: 'h_ssearch', label: 'session_search', sub: 'Search past chats', why: 'Full-text search across saved past sessions (pruned ones are gone), no model calls, returns the real messages.', sources: [H.sessions] },
];
const gw: Spec[] = [
  { id: 'h_approve', label: 'Dangerous command check', sub: 'Smart mode by default', why: 'Risky shell commands: low-risk auto-approved, dangerous auto-denied, unsure ones ask you. Cron and webhook runs deny by default.', sources: [H.sec], detail: DET.h_approve },
  { id: 'h_hook', label: 'pre_tool_call hook', sub: 'Can block tool calls', why: 'Your hook sees every tool call first and can block it; plugin hooks fail closed on timeout.', sources: [H.hooks], detail: DET.h_hook },
  { id: 'h_rulegate', label: 'Read-first gate', sub: 'Connector rules before the call', why: 'A pre_tool_call hook blocks the first call to a connector each session, with that connector\'s rules in the message; the agent reads them and retries.', sources: [H.hooks, H.ctx, H.skills], detail: DET.h_rulegate },
  { id: 'h_box', label: 'Container backend', sub: 'Isolates shell commands', why: 'Docker, Modal, Daytona and others run commands away from your machine; the docs recommend it for production gateways. It does not police API calls.', sources: [H.sec, H.tools] },
];
const run: Spec[] = [
  { id: 'h_term', label: 'Terminal backends', sub: 'Local, Docker, SSH, cloud', why: 'Commands run where you choose: your machine, a container, a remote server or a cloud sandbox.', sources: [H.tools] },
  { id: 'h_code', label: 'execute_code', sub: 'Many steps, one turn', why: 'The agent writes a Python script that calls its tools; only the printed result enters the chat.', sources: [H.code] },
  { id: 'h_result', label: 'Result back to the loop', sub: 'Next tool, or answer', why: 'Each tool result is added and the model picks the next move.', sources: [H.arch] },
  { id: 'h_lsp', label: 'Lint after writes', sub: 'Trusted git folders', why: 'After file writes, real language servers report problems in trusted git workspaces; otherwise a syntax-only check. It does not block the write.', sources: [H.lsp] },
  { id: 'h_ckpt', label: 'Checkpoints + /rollback', sub: 'Opt-in snapshots', why: 'Snapshots before file writes and destructive commands; /rollback normally keeps your own hand edits.', sources: [H.ckpt], badge: 'Opt-in' },
];
const verify: Spec[] = [
  { id: 'h_gate', label: 'Goal gates: your tests', sub: '/goal gate add <command>', why: 'Shell commands that must pass before the judge is asked; a failure is fed back so the agent fixes it. No gates set: straight to the judge.', sources: [H.goals] },
  { id: 'h_judge', label: 'Goal judge', sub: 'done, continue, wait, blocked', why: 'After gates pass, a judge (your main model by default) reads the reply against the goal.', sources: [H.goals] },
  { id: 'h_review', label: '/review', sub: 'Background reviewer', why: 'A helper that checks the work against the loaded skills and project rules.', sources: [H.deleg], badge: 'Optional' },
];
const report: Spec[] = [
  { id: 'h_reply', label: 'Reply in the same chat', sub: 'Files as attachments', why: 'The final answer lands in the chat; charts, PDFs and sheets arrive as native attachments.', sources: [H.deliver] },
  { id: 'h_paused', label: 'Or paused / blocked', sub: 'Tells you why', why: 'With /goal: the judge said blocked, gates kept failing, or the turn budget ran out. You /goal resume or /goal clear. (Waiting is different: it resumes by itself when the background job ends.)', sources: [H.goals] },
];
const learn: Spec[] = [
  { id: 'h_memtool', label: 'memory tool', sub: 'Saves short facts', why: 'The agent adds, replaces or removes memory entries; you can require approval.', sources: [H.mem, H.config] },
  { id: 'h_bgreview', label: 'Background review', sub: 'Updates memory, skills', why: 'After turns, a background review can apply memory and skill updates; approval settings can make it wait for you.', sources: [H.mem, H.skills, H.config] },
  { id: 'h_skills', label: 'Writes its own skills', sub: 'skill_manage', why: 'After a hard workflow it saves the steps as a skill for next time.', sources: [H.skills], detail: DET.h_skills },
  { id: 'h_wapprove', label: 'write_approval', sub: 'You review changes', why: 'Skill and memory writes can be staged for your review before they land.', sources: [H.skills, H.config] },
  { id: 'h_curator', label: 'Curator', sub: 'Stale, then archived', why: 'Agent-created skills: unused 14 days = stale, 30 = archived (recoverable). Pinned and cron-used skills are skipped.', sources: [H.curator] },
  { id: 'h_new', label: '/new at boundaries', sub: 'Fresh memory loads', why: 'The prompt\'s memory snapshot refreshes in a new session, so reset at the end of a job or a day.', sources: [H.mem, H.sessions] },
];
const lib: Spec[] = [
  { id: 'h_lib_home', label: '~/.hermes', sub: 'One home per agent', why: 'config.yaml, .env, SOUL.md, memories/, skills/, sessions (state.db), cron jobs.', sources: [H.which, H.profiles] },
  { id: 'h_lib_config', label: 'config.yaml', sub: 'Model, tools, hooks, approvals', why: 'Provider and model, enabled toolsets, hooks, approvals, memory limits, delegation and goal limits.', sources: [H.config, H.sec] },
  { id: 'h_lib_env', label: '.env + secrets', sub: 'Credentials stored separately', why: 'Keys live in the profile .env with tight file permissions, or in a secrets manager.', sources: [H.sec] },
  { id: 'h_lib_skills', label: 'skills/', sub: 'agentskills.io format', why: 'Your skills plus Skills Hub installs, in the same open format other agents use.', sources: [H.skills] },
  { id: 'h_lib_plugins', label: 'hooks/ + plugins/', sub: 'Gateway hooks, plugins', why: 'hooks/ holds gateway hooks (HOOK.yaml + handler.py); shell hooks are listed in config.yaml; plugins add tools and hooks.', sources: [H.hooks] },
  { id: 'h_lib_import', label: 'Import Claude Code', sub: 'Partial, one command', why: 'Brings in a ~/.claude or ~/.codex setup; instructions become memory, credentials are not copied.', sources: [H.importer] },
];
const rails: Spec[] = [
  { id: 'h_x_model', label: 'Any model', sub: 'Portal, OpenRouter, more', why: 'Works with Nous Portal, OpenRouter, OpenAI, Anthropic, Google or any compatible endpoint.', sources: [H.docs] },
  { id: 'h_x_iso', label: 'Separate histories', sub: 'Search can reach old chats', why: 'Sessions keep separate conversation state, but session_search and profile memory can bring old info into a new chat.', sources: [H.sec, H.sessions] },
  { id: 'h_x_seen', label: 'Progress you can stop', sub: 'Display is configurable', why: 'Tool progress shows if that platform\'s setting is on; stopping a run does not undo finished actions.', sources: [H.msg, H.arch] },
  { id: 'h_compress', label: 'Compression', sub: 'Long chat gets summarized', why: 'Middle turns get summarized when the chat passes a threshold; /compress does it on demand.', sources: [H.arch, H.sessions, H.mem], detail: DET.h_compress },
  { id: 'h_dash', label: 'Web dashboard', sub: 'Sessions, logs, analytics', why: 'Browser panel for config, keys, MCP servers, pairing, sessions, logs, analytics, cron and skills.', sources: [H.dash] },
  { id: 'h_x_vs', label: 'vs Claude Code', sub: 'Same ideas, different files', why: 'What matches and what differs between Hermes and Claude Code.', sources: [H.importer, H.ctx, H.soul, H.goals, H.ccPerm, H.ccMem, H.ccSdk, H.ccHooks], detail: DET.h_x_vs },
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
  flow('h_you', 'h_gateway', 'chat app'),
  { ...flow('h_you', 'h_profile', 'CLI: direct'), sh: 'ls', th: 'l', offset: 25 },
  { ...flow('h_cron', 'h_profile', 'fresh session'), sh: 'rs', th: 'r', offset: 30 },
  flow('h_gateway', 'h_profile', 'routes to the bot'),
  flow('h_profile', 'h_soul', 'its home loads'),
  flow('h_workdir', 'h_ctx', 'project rules'),
  flow('h_band_front', 'h_loop', 'prompt ready'),
  flow('h_loop', 'h_self'),
  flow('h_loop', 'h_deleg'),
  flow('h_self', 'h_band_know', 'needs a tool'),
  flow('h_deleg', 'h_band_know', 'children use the same loop'),
  { ...loop('h_deleg', 'h_loop', 'summary back'), sh: undefined, th: undefined },
  flow('h_band_know', 'h_band_gw', 'tool call'),
  flow('h_band_gw', 'h_band_run', 'allowed'),
  { ...loop('h_result', 'h_loop', 'next move'), offset: 15 },
  { ...flow('h_loop', 'h_reply', 'no tool, no goal: answer'), sh: 'ls', th: 'l', offset: 40 },
  { ...flow('h_loop', 'h_gate', 'turn done, goal active'), sh: 'rs', th: 'r', offset: 60 },
  flow('h_gate', 'h_judge', 'gates pass'),
  { ...loop('h_gate', 'h_loop', 'gate failed'), offset: 45 },
  { ...loop('h_judge', 'h_loop', 'continue (or wait, then resume)'), offset: 30 },
  flow('h_judge', 'h_reply', 'done'),
  flow('h_judge', 'h_paused', 'blocked'),
  flow('h_gate', 'h_paused', 'gates kept failing'),
  flow('h_band_report', 'h_band_learn', 'after'),
  link('h_band_front', 'h_lib_home', 'reads', 'ls', 'r'),
  link('h_band_gw', 'h_lib_config', 'rules from', 'ls', 'r'),
];
