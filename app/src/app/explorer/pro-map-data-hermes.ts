import { withGuardrails } from './pro-map-guardrail-cards';
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
  promptCode: 'https://github.com/NousResearch/hermes-agent/blob/main/agent/system_prompt.py',
  contextCode: 'https://github.com/NousResearch/hermes-agent/blob/main/agent/prompt_builder.py',
  loopCode: 'https://github.com/NousResearch/hermes-agent/blob/main/agent/conversation_loop.py',
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
const BAND_H: Partial<Record<Step, number>> = { ask: 155, ui: 155, client: 155, front: 310, plan: 155, delegate: 155, know: 310, gw: 460, run: 310, verify: 310, report: 310, learn: 310 };
const Y = {} as Record<Step, number>;
let cur = 0;
for (const s of STEPS) { Y[s] = cur; cur += (BAND_H[s] ?? 100) + 30; }
const BOTTOM = cur;

type Spec = { id: string; label: string; sub: string; why: string; sources: string[]; badge?: string; detail?: FullDetail };
// Visible classification: extension points are built-in; their agency policies are custom.
const CUSTOM = new Set(['h_rulegate', 'h_contract', 'h_skillgate', 'h_mcpgate']);
const REFERENCE = new Set(['h_x_vs']);
const node = (s: Spec, x: number, y: number, w: number): ProNode => ({
  ...s, sub: `${CUSTOM.has(s.id) ? 'Custom' : REFERENCE.has(s.id) ? 'Comparison' : 'Built-in'}: ${s.sub}`,
  status: hw, x, y, w,
});
function row(step: Step, specs: Spec[]): ProNode[] {
  const columns = Math.min(3, specs.length);
  const sp = ROW_W / columns;
  const w = Math.min(230, sp - 14);
  return specs.map((s, i) => node(s, HX + (i % columns) * sp + (sp - w) / 2, Y[step] + 40 + Math.floor(i / columns) * 145, w));
}
function column(x: number, top: number, specs: Spec[], w: number): ProNode[] {
  const gap = (BOTTOM - top - 90) / specs.length;
  return specs.map((s, i) => node(s, x, top + 34 + i * gap, w));
}

const STEP_INFO: Record<Step, { label: string; tag: string; trace: string; src: string[] }> = {
  ask: { label: 'Request starts', tag: 'saved to the session', trace: 'Every conversation is saved as a session in a local database (state.db), searchable later.', src: [H.sessions] },
  ui: { label: 'Where you talk', tag: 'one session per chat', trace: 'Chat apps go through the gateway, which keeps each chat as its own session until /new. The CLI talks to the agent directly.', src: [H.msg, H.arch] },
  client: { label: 'Which agent and which folder', tag: 'profile + workdir', trace: 'The profile (its own home folder) and the working folder decide which identity, memory and project files load.', src: [H.profiles, H.ctx] },
  front: { label: 'Build the system prompt', tag: '/context shows it', trace: 'Prompt order: SOUL and stable guidance, project context, skills index, memory/profile, then runtime hints. Project scanning occurs before injection; /context shows loaded files. This is grouping, not a tool execution trace.', src: [H.prompt, H.promptCode, H.ctx] },
  plan: { label: 'The loop decides the next move', tag: 'progress (configurable)', trace: 'Tool progress shows in the terminal, and in chat apps if that platform\'s display setting turns it on.', src: [H.arch, H.msg] },
  delegate: { label: 'Optional: hand out tasks', tag: 'child summaries', trace: 'Each child starts without the chat history; only its final summary comes back to the parent.', src: [H.deleg] },
  know: { label: 'Find information and choose a tool', tag: 'tool + args', trace: 'Tool name and arguments pass through hooks (pre_tool_call sees them).', src: [H.tools, H.hooks] },
  gw: { label: 'Safety checks before it runs', tag: 'approvals + hook blocks', trace: 'Approval decisions (smart, manual or your reply) and any hook block message.', src: [H.sec, H.hooks] },
  run: { label: 'Run it and read the result', tag: 'tool result', trace: 'The result goes back into the loop, and the model picks the next move.', src: [H.arch] },
  verify: { label: 'Check before finishing', tag: 'code evidence; optional goal gates', trace: 'Edited code can get a bounded evidence nudge and registered pre_verify policy. With /goal active, command gates precede the judge verdict: done, continue, wait or blocked.', src: [H.hooks, H.goals, H.loopCode] },
  report: { label: 'Answer or report why it stopped', tag: 'reply, partial result or wait', trace: 'The active surface gets the reply or stop status. Supported gateways can upload eligible existing files; file creation alone is not delivery proof.', src: [H.deliver] },
  learn: { label: 'Optional: learn for next time', tag: 'memory + skills', trace: 'Memory writes can save now or wait for consent; prompt snapshots refresh on new sessions or rebuilds. Learning is not proof the job succeeded.', src: [H.mem, H.skills] },
};

function bands(): ProNode[] {
  const out: ProNode[] = STEPS.map((step, i) => ({
    id: `h_band_${step}`, label: `${i + 1}. ${STEP_INFO[step].label}`, sub: '', tag: STEP_INFO[step].tag, trace: STEP_INFO[step].trace,
    why: `Group ${i + 1} of 12 in this explanatory map, not a guaranteed linear runtime pipeline.`, status: hw, sources: STEP_INFO[step].src, x: HX - 10, y: Y[step], w: ROW_W + 20, h: BAND_H[step] ?? 100, band: true,
  }));
  out.push(
    { id: 'h_title', label: 'Version 4: Hermes Agent (Nous Research), 12 steps', sub: 'Documented Hermes behavior, not installed state. Built-in and Custom labels separate shipped features from proposed policy.', x: HX - 290, y: -110, w: 1280, h: 60, band: true, status: hw, why: 'Hermes is a ready-made agent you configure. Claude Code is Anthropic\'s; the Agent SDK is the kit to build your own.', sources: [H.docs, H.repo] },
    { id: 'h_band_lib', label: 'Setup: the ~/.hermes folder', sub: '', why: 'Files you set up once per agent (profile).', status: hw, sources: [H.which, H.profiles], x: HX - 290, y: Y.client, w: 250, h: BOTTOM - Y.client - 30, band: true },
    { id: 'h_band_rails', label: 'True at every step', sub: '', why: 'These apply the whole time.', status: hw, sources: [H.arch], x: HX + 790, y: Y.ui, w: 200, h: BOTTOM - Y.ui - 30, band: true },
  );
  return out;
}

// ---------- detail cards ----------
const DET: Record<string, FullDetail> = {
  // h_rulegate's complete tested examples are attached by withGuardrails.
  h_soul: {
    plain: [
      'SOUL.md is WHO the agent is: personality, tone, how it talks, what it avoids. It is the very first thing in the prompt (slot 1) and replaces the built-in identity.',
      'It lives only in HERMES_HOME/SOUL.md (the active profile home), not in the project folder.',
      'Hermes writes a starter SOUL.md if none exists and never overwrites yours. Empty or unreadable means it falls back to the built-in identity.',
      'Project rules do NOT go here; those go in AGENTS.md. Facts about you go in USER.md (memory).',
      'delegate_task children do not get SOUL.md: they use the default identity plus the supplied brief and workspace project files. Cron is different: it retains the profile SOUL even when project context is skipped.',
    ],
    pictures: [{ kind: 'flow', title: 'Simplified order the prompt is built in', caption: 'Current agent/system_prompt.py resolves conflicting older examples in the docs: stable, context, then volatile. Not an exact runtime trace.', steps: [
      { label: 'SOUL.md + tool guidance', note: 'who it is (slot 1)', tone: 'good' },
      { label: 'Project context + workspace/platform hints', note: '.hermes.md, AGENTS.md chain, CLAUDE.md or .cursorrules; "you are on Telegram"' },
      { label: 'Skills index, MEMORY.md, USER.md', note: 'cached; refreshes on a rebuild' },
      { label: 'Time, profile/model and runtime hints' },
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
      'The first non-empty project type wins: .hermes.md / HERMES.md, then the AGENTS chain (per directory AGENTS.override.md before AGENTS.md), then CLAUDE.md, then .cursorrules / .cursor/rules/*.mdc. Empty or unreadable candidates can fall through.',
      'AGENTS.md loads as a chain from the git root down to the working folder (outside git, only the working folder); more are picked up from subfolders as it works. Other file types have their own discovery rules.',
      'Project files are scanned before loading and matching threats block them; the scanner is not a complete security boundary. User-authored SOUL warns but loads on a match; distribution-owned SOUL can be blocked. Oversized files retain 70% head and 20% tail.',
      'Recommended structure: root AGENTS.md plus client-folder AGENTS.md. Confirm the active workdir and loaded chain with /context; this map is not an installation check.',
    ],
    myths: [{ myth: 'If I have both AGENTS.md and CLAUDE.md, Hermes reads both.', truth: 'The first non-empty project type wins; an AGENTS chain takes priority over CLAUDE.md.', fix: 'Put shared rules in AGENTS.md and make CLAUDE.md point to it, so every agent reads the same rules.' }],
  },
  h_mem: {
    plain: [
      'Two small files the agent writes itself with the memory tool: MEMORY.md (its notes: environment, conventions, tool quirks) and USER.md (you: preferences, style).',
      'Default limits: MEMORY.md 2,200 characters, USER.md 1,375 (memory.memory_char_limit and memory.user_char_limit in config.yaml). Small on purpose.',
      'Both load as a frozen snapshot at session start. A save mid-chat hits the disk now; the prompt refreshes on a new session or a prompt rebuild such as compression; the memory tool shows current disk state.',
      'For history, the agent uses session_search across past chats instead of loading it.',
      'You can make memory writes wait for your approval.',
    ],
    myths: [{ myth: 'Memory means the agent remembers everything.', truth: 'It keeps a few thousand characters of notes plus searchable old sessions.', fix: 'Keep durable facts short, let session_search find history, and run /new at natural breaks so new notes load.' }],
  },
  h_loop: {
    plain: [
      'The harness is the loop around the model: build the prompt, call the model, run any tool calls, feed the results back, repeat until there is a final answer, then save the session. A final answer is not independent proof that the requested outcome happened.',
      'It also handles retries, fallback models, compression and saving. Exhausted retries, iteration limits and interruption can end a turn without the job being complete.',
      'For edited code, a built-in verify-on-stop guard can nudge for fresh verification evidence. Registered pre_verify policy hooks run afterward and can request another step; nudges are bounded by agent.max_verify_nudges (default 3), not an unlimited completion guarantee.',
      'Tool progress is shown in the terminal, and in chat apps when that platform\'s setting turns it on. You can stop a run, but actions already finished are not undone.',
      'What helps it finish jobs: a completion contract (outcome, proof, stop rules), /goal with test gates, execute_code (many tool calls in one turn) and delegate_task (fresh helpers for side work).',
    ],
    pictures: [{ kind: 'flow', title: 'One turn of the Hermes loop', caption: 'From the Hermes architecture page. /goal adds the gates-and-judge step after the answer.', steps: [
      { label: 'Message in', note: 'CLI direct, or chat app through the gateway, cron, webhook' },
      { label: 'Build the system prompt', note: 'SOUL, project file, skills, memory' },
      { label: 'Call the model', note: 'any provider' },
      { label: 'Tool calls?', many: ['yes: run the tool, add the result, loop', 'no: final answer'] },
      { label: 'Edited code: verify-on-stop, then registered pre_verify', note: 'bounded missing-evidence or custom-policy nudges' },
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
      'Judge errors treat the verdict as continue, not done; the continuation budget is the backstop. A wait can release on a process exit, watched pattern or timer; PID/session waits are capped at 30 minutes.',
      'User messages take priority. Pause and clear stop future continuations, not the in-flight turn; use /stop to interrupt current work. No stop undoes completed side effects.',
    ],
    examples: [{ title: 'Finish line with a real test gate', file: 'In the Hermes chat', why: 'Prerequisites: implement checks/oak_ridge_form_test.py, select the authorized test sub-account and workdir, and approve test writes. In messaging, gate addition needs a configured gateway admin. Send each slash command separately; /goal starts work immediately. This is not a supplied test script.', code: L(
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
      'Children inherit the parent\'s tools minus blocked ones: no asking you questions (clarify), no memory writes, no scheduling, no send_message or start_chat. This is not general filesystem or account isolation.',
      'Flat by default. A child can only hand out work if it is given the orchestrator role AND max_spawn_depth is raised.',
      'Current delegation defaults: 10 concurrent children, 250 tool-calling iterations per child, depth 1 (flat); one-shot sessions separately cap total children at 2. The older overview says 3; use the dedicated page and runtime config.',
      'On surfaces with later delivery, top-level delegate_task returns a handle and posts a completion later; stateless endpoints run synchronously. Inspect exit_reason, truncated and schema_valid when present, not just status completed.',
      '/review starts a full-tool background reviewer with the last 10 user/assistant messages, loaded-skill names and project files. It can run tools, so it is not read-only by guarantee.',
      'No wall-clock child timeout by default; stale progress and iteration limits still stop children. /stop returns interrupted partial results; a running child lost on process restart becomes unknown, not resumed execution.',
      'Children must finish owned background commands before returning. Their leftover processes end at teardown; a process ID does not transfer ownership. Workspaces are shared unless supported opt-in isolation is enabled.',
    ],
    myths: [{ myth: 'A helper knows everything the main chat knows.', truth: 'It has the project files but none of the chat history and no SOUL.md.', fix: 'Have the parent pass the client, the files that matter and the finish line in the delegate_task context.' }],
  },
  h_approve: {
    plain: [
      'Before running a shell command, Hermes checks it against a list of dangerous patterns.',
      'Default mode is smart: a helper model auto-approves low-risk commands, auto-denies clearly dangerous ones, and asks you when unsure. Manual mode asks for dangerous-pattern matches, not every tool call. Off turns checks off (docs: trusted places only).',
      'Cron, single-query and webhook runs deny dangerous commands by default, since nobody is there to answer.',
      'Docker, Singularity, Modal, Daytona and Vercel Sandbox skip dangerous-command checks. Isolation does not protect mounted files or forwarded credentials, and it does not authorize API side effects; local and SSH retain the checks.',
      'Who can talk to the bot at all is a separate gate: allowlists or DM pairing. By default everyone else is denied.',
    ],
    myths: [{ myth: 'Approval prompts protect my GHL clients.', truth: 'They cover dangerous shell commands. A tool call to an API (MCP, Composio) is not a shell command.', fix: 'Add a pre_tool_call hook that blocks spend, send, delete and wrong-client calls before any tool runs.' }],
  },
  h_hook: {
    plain: [
      'Built-in extension points, custom policy code: gateway hooks, Python plugin hooks, shell hooks and outbound webhooks have different trust and control rules.',
      'Gateway hooks are trusted by placement in hooks/ and loaded at gateway startup; they are not a consented pre-tool blocking gate. Outbound webhooks only notify and cannot block.',
      'pre_tool_call can return block, modify, or approve. approve asks the human approval gate; it is not auto-allow. A block beats an earlier approval request.',
      'Python pre_tool_call callback errors/timeouts block. Shell hooks fail open by default; fail_closed: true blocks spawn errors, timeout, invalid output and ordinary failing exits. Exit 2 blocks even without block JSON.',
      'Shell consent is keyed by event and exact command string, not script contents. Headless runs can skip new unapproved hooks; editing an approved script does not revoke consent. Safe mode skips plugin/shell registration, not the trusted-by-placement gateway hook loader.',
    ],
    examples: [{ title: 'Shape of a blocking shell hook', file: '$HERMES_HOME/agent-hooks/block-all.py', why: 'Demonstration only: blocks every matched call, not a client policy. Save as an executable script, configure its command, approve it and inspect hermes hooks list before relying on it. Do not install indiscriminately.', code: L(
      '#!/usr/bin/env python3',
      'import json, sys',
      'json.load(sys.stdin)',
      'print(json.dumps({"action": "block", "message": "Demonstration policy: call blocked."}))',
      'sys.exit(2)') }],
    myths: [{ myth: 'fail_closed protects even an unapproved hook.', truth: 'A hook that never registered cannot intercept a call.', fix: 'Check consent, matcher and registration; use hermes hooks doctor after script edits.' }],
  },
  h_compress: {
    plain: [
      'Built-in compression summarizes older middle turns and preserves selected beginning/recent turns. It is lossy; /compress requests it manually.',
      'Compression rebuilds the system prompt, so current memory can reload then as well as on a new session. A mid-turn memory save does not immediately rewrite the cached prompt.',
      'Gateway chats persist across restarts by default until /new or /reset. An optional session-reset-policy plugin can add time-based resets.',
      'Use /new at a finished task or topic boundary to start with smaller context; name it, for example /new oak-ridge-routing, for later /resume.',
      'Compression is not deletion: stored session history remains searchable until it is pruned.',
    ],
    myths: [{ myth: 'Only /new can refresh a memory snapshot.', truth: 'Compression-triggered prompt rebuilds can refresh it too.', fix: 'Use /new for a clean task boundary, not as the only possible refresh path.' }],
  },
  h_skills: {
    plain: [
      'Skills are procedures that load only when needed (progressive disclosure), in the agentskills.io format.',
      'The agent writes and edits its own skills with skill_manage when it figures out a non-trivial workflow.',
      'skills.write_approval: true stages every skill_manage write under the active home pending/skills/. memory.write_approval is a separate setting: foreground CLI writes prompt inline; other memory writes are staged.',
      'After turns, a background review may save memory and skills. Separate write-approval settings can require review; background memory replacements/removals are staged even when its gate is off.',
      'Curator runs on inactivity checks, not cron: default weekly interval and 2-hour idle minimum. Managed skills become stale after 14 days, archived after 30. Pinned and cron-referenced skills (including paused jobs) are skipped; consolidation is off by default.',
    ],
    myths: [{ myth: 'Self-written skills are always improvements.', truth: 'They are drafts from one session.', fix: 'Turn on skills.write_approval and keep a few real test jobs to rerun before accepting big skill changes.' }],
  },
  h_profile: {
    plain: [
      'A profile is a separate Hermes home with config.yaml, .env, SOUL.md, memory, sessions, skills and cron jobs. Root OAuth can be shared, and local tool subprocesses normally retain the OS-user HOME: profiles are not security sandboxes.',
      'One profile per bot (Javar, Javante). Bot Mode turns profiles into named bots with their own chats that can message each other.',
      'Recommendation (ours, not the docs): clients are folders, not profiles. The bot works in clients/oak-ridge-tree/ and that folder\'s AGENTS.md loads.',
    ],
    myths: [{ myth: 'Each client needs its own Hermes profile.', truth: 'A profile separates agent state, but may share OAuth and host CLI credentials. A client folder is a recommended project layout, not enforced isolation.', fix: 'Recommendation: one profile per bot, one folder (with AGENTS.md) per client, and a hook that locks each job to its client.' }],
  },
  h_x_vs: {
    plain: [
      'Both support project instructions, skills, helper agents, hooks and context compression. The files, commands and permission semantics are not interchangeable.',
      'Hermes has a built-in /goal loop with command gates and a model judge; it credits Codex CLI for the design. A Claude Code Stop hook is an extension point, not the same built-in /goal command.',
      'Hermes includes SOUL.md identity, a messaging gateway, cron, provider choice, skill writing and curator upkeep. These documented features do not prove a configured bot uses them.',
      'Claude Code has its own permission rules, memory and Agent SDK. Imported instructions do not transfer permissions or make Claude-specific tools available in Hermes.',
      'The Hermes importer previews a partial migration: Claude Bash allow/deny rules map to Hermes command allow/deny settings, MCP definitions have secret fields stripped, and skills/instructions can migrate. Credentials are never imported; this is not full permission equivalence.',
    ],
  },
};

const ask: Spec[] = [
  { id: 'h_you', label: 'You message it', sub: 'Chat app or CLI', why: 'You talk to it wherever it lives; it can run on a cloud machine you never log into.', sources: [H.docs, H.msg] },
  { id: 'h_goal', label: 'Optional: set a /goal', sub: 'Finish line + test gates', why: 'Keeps working across turns until gates pass and the judge says done, or it waits, gets blocked, or hits the 20-turn continuation budget.', sources: [H.goals], badge: 'Optional', detail: DET.h_goal },
  { id: 'h_cron', label: 'Or a schedule or webhook', sub: 'Cron; webhooks separate', why: 'Cron runs fresh sessions with attached skills and configured delivery targets; the gateway or another scheduler must be running. Inbound webhooks are a separately configured trigger, not cron itself.', sources: [H.cron] },
];
const ui: Spec[] = [
  { id: 'h_gateway', label: 'Gateway (chat apps)', sub: 'One process, 20+ apps', why: 'A gateway process connects configured messaging adapters, routes chat sessions, and ticks its cron scheduler (default 60 seconds). The CLI does not go through it.', sources: [H.msg, H.arch] },
  { id: 'h_auth', label: 'Who may talk', sub: 'Allowlist or DM pairing', why: 'By default the gateway denies anyone not allowlisted or paired. Admin vs regular user controls slash commands.', sources: [H.msg, H.sec] },
  { id: 'h_session', label: 'One chat = one session', sub: 'Survives restarts', why: 'By default, gateway conversation routing persists until /new or /reset, across restarts; an optional reset-policy plugin can change this. In groups, each person gets their own session by default.', sources: [H.mem, H.sessions] },
];
const client: Spec[] = [
  { id: 'h_profile', label: 'Profile = one agent', sub: 'Own SOUL, memory, keys', why: 'Each profile has its own Hermes home and state. OAuth and local CLI credentials can still be shared; a profile is not an account-security sandbox.', sources: [H.profiles], detail: DET.h_profile },
  { id: 'h_workdir', label: 'Working folder', sub: 'Picks the project rules', why: 'AGENTS.md loads as a chain from the git root down to the working folder (outside git, just the working folder). Cron skips project files unless its absolute, existing workdir is set; its SOUL identity still loads.', sources: [H.ctx, H.cron] },
  { id: 'h_bots', label: 'Bot Mode', sub: 'Named bots, own chats', why: 'Profiles become named bots with their own role, model, memory and skills; they share group chats and message each other.', sources: [H.bots], badge: 'Optional' },
];
const front: Spec[] = [
  { id: 'h_scan', label: 'File injection scan', sub: 'Before files load', why: 'Project files are scanned before injection; matches can block loading. Own SOUL warns and loads, distributed SOUL may block. This is not proof that arbitrary files are safe.', sources: [H.sec, H.ctx] },
  { id: 'h_soul', label: 'SOUL.md', sub: 'Who it is (slot 1)', why: 'The identity file: first thing in the prompt, from the agent home only.', sources: [H.soul, H.soulGuide, H.which, H.prompt, H.promptCode], detail: DET.h_soul },
  { id: 'h_ctx', label: 'Project file', sub: 'First non-empty project type', why: '.hermes.md / HERMES.md, AGENTS chain with per-directory overrides, CLAUDE.md or Cursor rules: first non-empty project type wins.', sources: [H.ctx, H.contextCode], detail: DET.h_ctx },
  { id: 'h_skillidx', label: 'Skills index', sub: 'Names now, body on demand', why: 'A compact skills index loads in the prompt; full bodies usually load on demand. Explicitly preloaded skills are an exception.', sources: [H.skills, H.prompt, H.promptCode] },
  { id: 'h_mem', label: 'MEMORY.md + USER.md', sub: 'Bounded snapshot; rebuild refreshes', why: 'Agent notes and user profile (default 2,200 and 1,375 characters under memory.*); cached until a new session or prompt rebuild, including compression.', sources: [H.mem, H.config, H.which], detail: DET.h_mem },
];
const plan: Spec[] = [
  { id: 'h_loop', label: 'The agent loop', sub: 'Model, tools, repeat', why: 'Build prompt, call model, run tools, feed results back, until a final answer; then save the session. A final answer is not independent proof that the requested outcome happened.', sources: [H.arch, H.hooks, H.loopCode], detail: DET.h_loop },
  { id: 'h_contract', label: 'Completion contract', sub: 'Your outcome, proof, stop rules', why: 'Spell out what done looks like, what proof to show and when to stop; it makes the goal judge stricter.', sources: [H.goals] },
  { id: 'h_todo', label: 'todo + clarify', sub: 'Track steps, ask if unsure', why: 'Built-in toolsets for a step list and for asking you a question mid-task.', sources: [H.tools] },
];
const delegate: Spec[] = [
  { id: 'h_self', label: 'Does it itself', sub: 'Simple jobs', why: 'Without delegation, the main agent calls its tools directly.', sources: [H.arch] },
  { id: 'h_deleg', label: 'delegate_task', sub: 'Fresh child, summary back', why: 'Children get the supplied brief and project context, not parent history or SOUL. They inherit restricted tools, usually return later, and can stop incomplete; the parent verifies their result.', sources: [H.deleg, H.overview], detail: DET.h_deleg },
  { id: 'h_kanban', label: 'Kanban board', sub: 'Bots share a task board', why: 'A lasting task board that coordinates several Hermes profiles.', sources: [H.kanban], badge: 'When useful' },
];
const know: Spec[] = [
  { id: 'h_toolsets', label: 'Toolsets', sub: 'On or off per platform', why: 'Tools come in groups (web, terminal, file, browser, memory, delegation and more) you enable per platform.', sources: [H.tools] },
  { id: 'h_mcp', label: 'MCP servers', sub: 'Outside tools, filtered', why: 'Connect MCP servers and filter which of their tools the agent sees.', sources: [H.mcp] },
  { id: 'h_toolsearch', label: 'Tool Search', sub: 'Auto; schemas on demand', why: 'Automatic by default: eligible MCP/plugin tools and curated cold built-ins defer schemas behind tool_search, tool_describe and tool_call. Listings scale to catalog size; hooks see the real tool name, and granted toolsets still bound access.', sources: [H.toolSearch] },
  { id: 'h_ssearch', label: 'session_search', sub: 'Search past chats', why: 'Full-text search across saved past sessions (pruned ones are gone), no model calls, returns the real messages.', sources: [H.sessions] },
];
const gw: Spec[] = [
  { id: 'h_approve', label: 'Dangerous command check', sub: 'Smart mode by default', why: 'For dangerous-pattern shell matches, smart mode judges risk and may approve, deny or ask. Unattended modes default to deny; container backends bypass this shell check, not all policy hooks.', sources: [H.sec], detail: DET.h_approve },
  { id: 'h_hook', label: 'pre_tool_call hook', sub: 'Can block tool calls', why: 'Registered matching pre-tool hooks can block, rewrite arguments or request human approval. Python callback errors/timeouts block; shell failure blocking requires fail_closed. Consent can prevent registration.', sources: [H.hooks], detail: DET.h_hook },
  { id: 'h_rulegate', label: 'Read-first gate', sub: 'Custom restricted adapter', why: 'Tested native hook examples are attached by withGuardrails. Not a shipped client policy or proof of installation.', sources: [H.hooks, H.ctx, H.skills] },
  { id: 'h_box', label: 'Container backend', sub: 'Isolates shell commands', why: 'Container backends isolate command execution and bypass dangerous-command checks. Mounted files, network access and forwarded credentials still matter; they do not enforce client/API permissions.', sources: [H.sec, H.tools] },
  { id: 'h_humanapprove', label: 'Wait for your approval', sub: 'A hook requests a human decision', why: 'A pre_tool_call approve result requests human approval; it is not an automatic allow. Denial or timeout returns a blocked result. This is separate from dangerous-shell-command classification.', sources: [H.hooks, H.sec] },
  { id: 'h_skillgate', label: 'New skill check', sub: 'Proposed, not built: skill rules before a skill saves', why: 'Built-in today: skills.write_approval stages every skill_manage write for your review (Hermes skills docs). Proposed, not built: a pre_tool_call hook on skill_manage and on file writes into skills/ that runs your skill rules (a name, a description that says when to use it, a size cap, no keys) and blocks a skill that fails. The tested guard (hermes_guard.py, checked 2026-10-12) blocks skill_manage outright, checks only skill structure on direct writes, and does not scan skill bodies for keys.', sources: [H.skills, H.hooks, '~/.agents/tools/unify/skill-lifecycle.md'] },
  { id: 'h_mcpgate', label: 'Connectors only through Composio', sub: 'Proposed, not built: one MCP entry, locked config', why: 'Built-in today: Hermes reads MCP servers from mcp_servers in config.yaml and can filter their tools (Hermes MCP docs). Proposed, not built: Composio as the only entry, a pre_tool_call hook that blocks config.yaml or .env writes adding another server, and config.yaml locked outside the agent. The tested guard (hermes_guard.py, checked 2026-10-12) accepts a config with another server and with empty hooks, so an agent edit could remove its own guard. Claude Code solves the same problem with admin-managed settings.', sources: [H.mcp, H.hooks, H.config, '~/.agents/tools/cards/composio.md', 'https://code.claude.com/docs/en/managed-settings'] },
];
const run: Spec[] = [
  { id: 'h_term', label: 'Terminal backends', sub: 'Local, Docker, SSH, cloud', why: 'Commands run where you choose: your machine, a container, a remote server or a cloud sandbox.', sources: [H.tools] },
  { id: 'h_code', label: 'execute_code', sub: 'Many steps, one turn', why: 'Python batches a restricted tool set, not arbitrary MCP or delegation calls. Local calls can reuse a session kernel; stdout plus errors/output paths return to chat. Timeout and tool-call caps stop a script; finished effects remain.', sources: [H.code] },
  { id: 'h_result', label: 'Result back to the loop', sub: 'Next tool, or answer', why: 'Each tool result is added and the model picks the next move.', sources: [H.arch] },
  { id: 'h_lsp', label: 'Lint after writes', sub: 'Trusted git folders', why: 'After file writes, real language servers report problems in trusted git workspaces; otherwise a syntax-only check. It does not block the write.', sources: [H.lsp] },
  { id: 'h_ckpt', label: 'Checkpoints + /rollback', sub: 'Opt-in snapshots', why: 'Snapshots before file writes and destructive commands; /rollback normally keeps your own hand edits.', sources: [H.ckpt], badge: 'Opt-in' },
];
const verify: Spec[] = [
  { id: 'h_finishcheck', label: 'Before a coding turn ends', sub: 'Evidence nudge + hook', why: 'After code edits, verify-on-stop can nudge for missing fresh verification. Registered pre_verify policies can then request continuation; default maximum 3 verification nudges. This is distinct from /goal gates and not proof every requirement passed.', sources: [H.hooks, H.loopCode] },
  { id: 'h_gate', label: 'Goal gates: your tests', sub: '/goal gate add <command>', why: 'Shell commands that must pass before the judge is asked; a failure is fed back so the agent fixes it. No gates set: straight to the judge.', sources: [H.goals] },
  { id: 'h_judge', label: 'Goal judge', sub: 'done, continue, wait, blocked', why: 'After gates pass, a judge (your main model by default) reads the reply against the goal.', sources: [H.goals] },
  { id: 'h_review', label: '/review', sub: 'Background reviewer', why: 'A full-tool background reviewer with recent user/assistant messages, skill names and project files. Findings still need verification; it is not guaranteed read-only.', sources: [H.deleg], badge: 'Optional' },
];
const report: Spec[] = [
  { id: 'h_stop', label: 'Stopped or failed', sub: 'Partial result, not done', why: 'A stop, provider/tool failure or iteration limit can end work incomplete. Report the actual error and partial effects; interruption does not roll them back. Lost running children after restart have unknown outcomes.', sources: [H.arch, H.deleg, H.sec] },
  { id: 'h_reply', label: 'Reply in the same chat', sub: 'Files as attachments', why: 'Replies return on the active surface. In supported gateways, existing files of supported types mentioned by absolute/home-relative path outside code blocks can upload as attachments; delivery is not guaranteed by producing a file.', sources: [H.deliver] },
  { id: 'h_wait', label: 'Waiting on background work', sub: 'Process, pattern or timer', why: 'Goal wait parks without consuming turns. A process exit, watched event or time barrier releases it; /goal unwait is the manual override. It is not completion.', sources: [H.goals] },
  { id: 'h_paused', label: 'Or paused / blocked', sub: 'Tells you why', why: 'A blocked verdict, gate retry exhaustion or continuation budget pauses the goal. /goal resume resets the counter; /goal clear drops it. Waiting has separate process/pattern/time release and /goal unwait override.', sources: [H.goals] },
];
const learn: Spec[] = [
  { id: 'h_memtool', label: 'memory tool', sub: 'Saves short facts', why: 'The agent adds, replaces or removes memory entries; you can require approval.', sources: [H.mem, H.config] },
  { id: 'h_bgreview', label: 'Background review', sub: 'Updates memory, skills', why: 'After turns, review may save memory or skills. Separate memory.write_approval and skills.write_approval control saves; background memory replacements/removals are staged even with the memory gate off.', sources: [H.mem, H.skills, H.config] },
  { id: 'h_skills', label: 'Writes its own skills', sub: 'skill_manage', why: 'After a hard workflow it saves the steps as a skill for next time.', sources: [H.skills], detail: DET.h_skills },
  { id: 'h_wapprove', label: 'write_approval', sub: 'You review changes', why: 'Skill and memory writes can be staged for your review before they land.', sources: [H.skills, H.mem, H.config] },
  { id: 'h_curator', label: 'Curator', sub: 'Stale, then archived', why: 'Inactivity-triggered upkeep, not cron. Default weekly/2-hour-idle checks mark managed skills stale at 14 days and archive at 30; pinned and cron-referenced skills are skipped. Consolidation is opt-in.', sources: [H.curator] },
  { id: 'h_new', label: '/new at boundaries', sub: 'Fresh memory loads', why: 'Recommended task boundary: a new session reloads current memory and reduces history. Compression can also refresh the prompt. No reset undoes completed work.', sources: [H.mem, H.sessions] },
];
const lib: Spec[] = [
  { id: 'h_lib_home', label: '~/.hermes', sub: 'One home per agent', why: 'config.yaml, .env, SOUL.md, memories/, skills/, sessions (state.db), cron jobs.', sources: [H.which, H.profiles] },
  { id: 'h_lib_config', label: 'config.yaml', sub: 'Model, tools, hooks, approvals', why: 'Provider and model, enabled toolsets, hooks, approvals, memory limits, delegation and goal limits.', sources: [H.config, H.sec] },
  { id: 'h_lib_env', label: '.env + secrets', sub: 'Credentials stored separately', why: 'Keys live in the profile .env with tight file permissions, or in a secrets manager.', sources: [H.sec] },
  { id: 'h_lib_skills', label: 'skills/', sub: 'agentskills.io format', why: 'Your skills plus Skills Hub installs, in the same open format other agents use.', sources: [H.skills] },
  { id: 'h_lib_plugins', label: 'hooks/ + plugins/', sub: 'Gateway hooks, plugins', why: 'hooks/ holds gateway hooks (HOOK.yaml + handler.py); shell hooks are listed in config.yaml; plugins add tools and hooks.', sources: [H.hooks] },
  { id: 'h_lib_import', label: 'Import Claude Code', sub: 'Partial, one command', why: 'Brings in a ~/.claude or ~/.codex setup; supported instructions can become memory; review the migration preview and categories. Do not assume credentials or permissions transfer.', sources: [H.importer] },
];
const rails: Spec[] = [
  { id: 'h_x_model', label: 'Model provider choice', sub: 'Portal, OpenRouter, more', why: 'Works with Nous Portal, OpenRouter, OpenAI, Anthropic, Google or any compatible endpoint.', sources: [H.docs] },
  { id: 'h_x_iso', label: 'Separate histories', sub: 'Search can reach old chats', why: 'Sessions keep separate conversation state, but session_search and profile memory can bring old info into a new chat.', sources: [H.sec, H.sessions] },
  { id: 'h_x_seen', label: 'Progress you can stop', sub: 'Display is configurable', why: 'Tool progress shows if that platform\'s setting is on; stopping a run does not undo finished actions.', sources: [H.msg, H.arch] },
  { id: 'h_compress', label: 'Compression', sub: 'Long chat gets summarized', why: 'Older middle turns are summarized when context crosses a threshold; /compress requests it. Prompt rebuild can reload memory; database history is not deleted.', sources: [H.arch, H.sessions, H.mem], detail: DET.h_compress },
  { id: 'h_dash', label: 'Web dashboard', sub: 'Sessions, logs, analytics', why: 'Browser panel for config, keys, MCP servers, pairing, sessions, logs, analytics, cron and skills.', sources: [H.dash] },
  { id: 'h_x_vs', label: 'vs Claude Code', sub: 'Same ideas, different files', why: 'What matches and what differs between Hermes and Claude Code.', sources: [H.importer, H.ctx, H.soul, H.goals, H.ccPerm, H.ccMem, H.ccSdk, H.ccHooks], detail: DET.h_x_vs },
];

export const H_NODES: ProNode[] = [
  ...bands(),
  ...row('ask', ask), ...row('ui', ui), ...row('client', client), ...row('front', front), ...row('plan', plan),
  ...row('delegate', delegate), ...row('know', know), ...row('gw', gw),
  ...row('run', [...run.filter((n) => !['h_ckpt', 'h_result'].includes(n.id)), run.find((n) => n.id === 'h_result')!]), ...row('verify', verify),
  ...row('report', report), ...row('learn', learn),
  ...column(HX - 270, Y.client, lib, 210),
  ...column(HX + 805, Y.ui, [...rails, run.find((n) => n.id === 'h_ckpt')!], 170),
].map(withGuardrails);

const flow = (a: string, b: string, label?: string): ProEdge => ({ id: `${a}-${b}`, source: a, target: b, kind: 'flow', label });
const loop = (a: string, b: string, label: string): ProEdge => ({ id: `${a}-${b}-loop`, source: a, target: b, kind: 'loop', label, sh: 'rs', th: 'r' });
const link = (a: string, b: string, label: string, sh: 'ls' | 'rs', th: 'l' | 'r'): ProEdge => ({ id: `${a}-${b}`, source: a, target: b, kind: 'link', label, sh, th });

export const H_EDGES: ProEdge[] = [
  flow('h_you', 'h_gateway', 'chat app'),
  { ...flow('h_you', 'h_profile', 'CLI: direct'), sh: 'ls', th: 'l', offset: 25 },
  { ...flow('h_cron', 'h_profile', 'fresh session'), sh: 'rs', th: 'r', offset: 30 },
  flow('h_gateway', 'h_auth', 'check caller'),
  flow('h_auth', 'h_session', 'authorized'),
  { ...flow('h_auth', 'h_stop', 'caller denied; no agent run'), sh: 'ls', th: 'l', offset: 90 },
  flow('h_session', 'h_profile', 'resolve profile'),
  flow('h_goal', 'h_contract', 'optional contract'),
  flow('h_contract', 'h_loop', 'goal shapes the turn'),
  flow('h_profile', 'h_soul', 'identity from home'),
  flow('h_profile', 'h_workdir', 'resolve working folder'),
  flow('h_workdir', 'h_scan', 'scan project files'),
  flow('h_scan', 'h_ctx', 'accepted content only'),
  flow('h_soul', 'h_ctx', 'stable before context'),
  flow('h_ctx', 'h_skillidx', 'context before index'),
  flow('h_skillidx', 'h_mem', 'index before memory'),

  flow('h_mem', 'h_loop', 'runtime hints then prompt ready'),
  flow('h_loop', 'h_self'),
  flow('h_loop', 'h_deleg'),
  flow('h_self', 'h_band_know', 'needs a tool'),
  flow('h_deleg', 'h_band_know', 'children use the same loop'),
  { ...loop('h_deleg', 'h_loop', 'summary back'), sh: undefined, th: undefined },
  flow('h_band_know', 'h_band_gw', 'tool call'),
  flow('h_band_gw', 'h_band_run', 'allowed; shell backend matters'),
  { ...loop('h_hook', 'h_loop', 'blocked reason returned'), offset: 20 },
  { ...loop('h_approve', 'h_loop', 'denied or timed out'), offset: 25 },
  flow('h_hook', 'h_humanapprove', 'requests human approval'),
  flow('h_humanapprove', 'h_band_run', 'approved'),
  { ...loop('h_humanapprove', 'h_loop', 'denied or timed out'), offset: 40 },
  flow('h_term', 'h_result', 'success or tool error'),
  flow('h_code', 'h_result', 'batched result or error'),
  link('h_ckpt', 'h_term', 'opt-in snapshot before writes', 'ls', 'r'),
  { ...loop('h_result', 'h_loop', 'next move'), offset: 15 },
  { ...flow('h_loop', 'h_finishcheck', 'final-answer candidate'), sh: 'rs', th: 'r', offset: 60 },
  { ...loop('h_finishcheck', 'h_loop', 'bounded verification nudge'), offset: 50 },
  flow('h_finishcheck', 'h_reply', 'turn accepted; no goal'),
  flow('h_finishcheck', 'h_gate', 'turn accepted; goal active'),
  flow('h_gate', 'h_judge', 'gates pass'),
  { ...loop('h_gate', 'h_loop', 'gate failed'), offset: 45 },
  { ...loop('h_judge', 'h_loop', 'continue; judge error also continues'), offset: 30 },
  flow('h_judge', 'h_wait', 'wait'),
  { ...loop('h_wait', 'h_loop', 'barrier released or unwait'), offset: 35 },
  { ...flow('h_loop', 'h_paused', 'continuation budget or goal pause'), sh: 'rs', th: 'r', offset: 80 },
  { ...flow('h_loop', 'h_stop', 'stop, failure or iteration limit'), sh: 'ls', th: 'l', offset: 55 },
  { ...loop('h_paused', 'h_loop', '/goal resume (counter resets)'), offset: 65 },
  flow('h_judge', 'h_reply', 'done'),
  flow('h_judge', 'h_paused', 'blocked'),
  flow('h_gate', 'h_paused', 'gates kept failing'),
  flow('h_band_report', 'h_band_learn', 'after'),
  link('h_band_front', 'h_lib_home', 'reads', 'ls', 'r'),
  link('h_band_gw', 'h_lib_config', 'rules from', 'ls', 'r'),
  link('h_lib_skills', 'h_skillgate', 'new skill is checked', 'rs', 'l'),
  link('h_lib_config', 'h_mcpgate', 'only Composio is added', 'rs', 'l'),
];
