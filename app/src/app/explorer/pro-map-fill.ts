/**
 * Fills every thin Anthropic-side card so none stops at a summary.
 * Sources: Anthropic docs, engineering posts and GitHub demos (re-read 2026-10-12).
 * Values in examples are illustrative unless the card says the file is Anthropic's.
 */
import type { More } from './pro-map-more';

const L = (...lines: string[]) => lines.join('\n');
const S = {
  best: 'https://code.claude.com/docs/en/best-practices',
  code: 'https://claude.com/claude-code',
  skillsExplained: 'https://claude.com/blog/skills-explained',
  harness: 'https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents',
  harnessDesign: 'https://www.anthropic.com/engineering/harness-design-long-running-apps',
  effective: 'https://www.anthropic.com/engineering/building-effective-agents',
  research: 'https://www.anthropic.com/engineering/multi-agent-research-system',
  researchDemo: 'https://github.com/anthropics/claude-agent-sdk-demos/tree/main/research-agent',
  emailDemo: 'https://github.com/anthropics/claude-agent-sdk-demos/tree/main/email-agent',
  sub: 'https://code.claude.com/docs/en/sub-agents',
  sdkSub: 'https://code.claude.com/docs/en/agent-sdk/subagents',
  sdkBlog: 'https://claude.com/blog/building-agents-with-the-claude-agent-sdk',
  managed: 'https://platform.claude.com/docs/en/managed-agents/multiagent-orchestration',
  hosting: 'https://code.claude.com/docs/en/agent-sdk/hosting',
  secure: 'https://code.claude.com/docs/en/agent-sdk/secure-deployment',
  advTools: 'https://www.anthropic.com/engineering/advanced-tool-use',
  tools: 'https://www.anthropic.com/engineering/writing-tools-for-agents',
  mcpProd: 'https://claude.com/blog/building-agents-that-reach-production-systems-with-mcp',
  mcp: 'https://code.claude.com/docs/en/mcp',
  perm: 'https://code.claude.com/docs/en/permissions',
  settings: 'https://code.claude.com/docs/en/settings',
  managedSettings: 'https://code.claude.com/docs/en/managed-settings',
  whatsNew: 'https://code.claude.com/docs/en/whats-new/index',
  plugins: 'https://code.claude.com/docs/en/plugins/overview',
  evals: 'https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents',
  mon: 'https://code.claude.com/docs/en/monitoring-usage',
  mem: 'https://code.claude.com/docs/en/memory',
  managedNew: 'https://claude.com/blog/new-in-claude-managed-agents',
  skillUse: 'https://claude.com/blog/lessons-from-building-claude-code-how-we-use-skills',
  skills: 'https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices',
  steer: 'https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more',
  ctx: 'https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models',
  changelog: 'https://code.claude.com/docs/en/changelog',
  sessions: 'https://claude.com/blog/maximizing-the-value-of-your-claude-code-sessions',
  cost: 'https://claude.com/blog/reducing-cost-and-improving-performance-with-claude-platform',
};

export const PRO_FILL: Record<string, More> = {
  // ---------- 1. You ask ----------
  p_you: {
    plain: ['Say the goal in one line.', 'Say what done looks like (a file, a number, a message drafted).', 'Give Claude a check it can run itself, so it does not stop at "looks done".', 'Add context it cannot guess: which client, which account, what not to touch.'],
    examples: [
      { title: 'Good ask', tone: 'good', file: 'what you type', why: 'Goal, finish line, and a check Claude can run. You can walk away.', code: L('Draft first-reply texts for Acme\'s 12 new leads from today.', 'Done = 12 drafts in drafts/2026-10-12.md, each under 300 characters.', 'Check: run evals/no-price and show me it passes before you say done.') },
      { title: 'Weak ask', tone: 'bad', file: 'what you type', why: 'No finish line and no check, so you become the checker.', code: 'follow up with the leads' },
    ],
    myths: [{ myth: 'Claude knows when it is done.', truth: 'Anthropic: Claude stops when the work looks done. Without a check it can run, you become the verification loop.' }],
    sources: [S.best],
  },

  // ---------- 2. Where you talk ----------
  p_ui1: {
    plain: ['Claude Code works on files and folders: on your computer (terminal, desktop app, editor) or in the cloud (web).', 'It reads the CLAUDE.md of the folder you open, so open the right project.', 'Best for building and running your system: repos, scripts, client folders.'],
    decide: [
      { if: 'The work lives in files or a repo', then: 'Claude Code' },
      { if: 'Thinking, writing, documents, quick questions', then: 'Claude app' },
      { if: 'A team asks questions in a shared channel', then: 'Claude in Slack' },
    ],
    myths: [{ myth: 'Claude Code is only for programmers.', truth: 'It is an agent that works in folders. Anything that lives in files (client notes, reports, sites) works.' }],
    sources: [S.code, S.best],
  },
  p_ui2: {
    plain: ['The chat app on desktop and phone.', 'Projects hold background for one body of work; skills hold how-to that works everywhere.', 'Good for checking in, approving, and work that is not inside a repo.'],
    myths: [{ myth: 'A Project in the app is the same as a skill.', truth: 'Anthropic: Projects say "here is what you need to know". Skills say "here is how to do things". If you copy the same instructions into several Projects, make a skill.' }],
    sources: [S.skillsExplained],
  },
  p_ui3: {
    plain: ['Claude in Slack answers in team channels.', 'Useful when several people need answers from the same place.', 'For a solo operator, it is optional; the lead agent is the same either way.'],
    pictures: [{ kind: 'flow', title: 'Any door, same lead agent', steps: [{ label: 'You ask from a door', many: ['Claude Code', 'Claude app', 'Slack'] }, { label: 'One lead agent' }, { label: 'Same plan, tools and rules' }] }],
    sources: [S.code],
  },

  // ---------- 4. Plan ----------
  p_plan1: {
    pictures: [{ kind: 'flow', title: 'Why the plan goes in a file', steps: [
      { label: 'Lead writes plan.md' },
      { label: 'Work goes on; the conversation fills up' },
      { label: 'Old turns get summarized or cut', tone: 'bad' },
      { label: 'Lead (or a fresh helper) reads plan.md again', tone: 'good' },
      { label: 'Nothing is lost' },
    ] }],
    examples: [{ title: 'A plan file', tone: 'good', file: 'files/plan.md', why: 'Short, checkable, and anyone (or any agent) can pick it up.', code: L('# Plan: Acme weekly report', 'Question: how did Acme do this week?', '1. Pull leads + stages (helper: data)      [ ]', '2. Compare with last week (helper: data)  [ ]', '3. Draft report from template (lead)       [ ]', 'Stop when: report saved to files/reports/ and numbers match GHL.') }],
    myths: [{ myth: 'Saving the plan to memory means MEMORY.md.', truth: 'It means a work file outside the conversation. MEMORY.md is Claude Code\'s notebook about you, not a job plan.' }],
    sources: [S.research, S.researchDemo],
  },
  p_plan2: {
    plain: [
      'Anthropic\'s pattern for jobs that take many sessions: two kinds of session.',
      'Session 1 (initializer): writes a setup script, a progress file (claude-progress.txt), a feature list, and makes the first git commit.',
      'Every later session: read the progress file and git log first, pick ONE unfinished item, build it, test it end to end, commit, update the progress file.',
      'Each new session starts with no memory of the last one. The files and git ARE the memory.',
    ],
    pictures: [{ kind: 'flow', title: 'Every session after the first', steps: [
      { label: 'Read claude-progress.txt + git log' },
      { label: 'Read the feature list; pick one unfinished item' },
      { label: 'Build it' },
      { label: 'Test it like a user would' },
      { label: 'Commit with a clear message', tone: 'good' },
      { label: 'Update claude-progress.txt', tone: 'good' },
    ] }],
    examples: [
      { title: 'Progress file', tone: 'good', file: 'claude-progress.txt', why: 'What a fresh session reads first to know where things stand.', code: L('2026-10-12 session 3', '- Done: lead form posts to GHL (tested with fake lead)', '- Next: first-reply text within 5 minutes', '- Known issue: phone numbers without +1 are rejected') },
      { title: 'Feature list as JSON', tone: 'good', file: 'feature_list.json', why: 'Anthropic used JSON here because the model is less likely to rewrite JSON than markdown. Agents only flip passes to true after testing.', code: L('[', '  { "description": "New lead gets a first text within 5 minutes",', '    "steps": ["Create fake lead in test sub-account", "Wait 5 min", "Check conversation"],', '    "passes": false }', ']') },
    ],
    myths: [
      { myth: 'The agent remembers yesterday\'s session.', truth: 'A new session starts blank. It knows only what it reads: the progress file, the feature list and git history.' },
      { myth: 'Let it build everything in one go.', truth: 'Anthropic saw agents try to do everything at once and run out of context halfway. One item per session, then commit.' },
    ],
    sources: [S.harness],
  },
  p_plan3: {
    plain: ['Start with the simplest thing that works. Add steps only when results show you need them.', 'Workflow = you decide the steps in code. Agent = the model decides the steps.', 'Use a workflow when the steps are known; use an agent when they are not.'],
    decide: [
      { if: 'Fixed steps, one after another', then: 'Prompt chaining (step 1 output feeds step 2)' },
      { if: 'Different kinds of requests need different handling', then: 'Routing (classify first, then send to the right path)' },
      { if: 'Independent pieces, or several tries to compare', then: 'Parallelization' },
      { if: 'You cannot predict the subtasks ahead of time', then: 'Orchestrator-workers (lead + helpers)' },
      { if: 'Clear criteria and improvement by feedback', then: 'Evaluator-optimizer (one writes, one grades, repeat)' },
    ],
    pictures: [{ kind: 'tree', title: 'Anthropic\'s building blocks', root: { label: 'Pattern', children: [
      { label: 'Chain' }, { label: 'Route' }, { label: 'Parallel' }, { label: 'Orchestrator' }, { label: 'Evaluator' },
    ] } }],
    myths: [{ myth: 'Real pros always use a full multi-agent system.', truth: 'Anthropic: the most successful teams used simple, composable patterns, not complex frameworks. Add complexity only when it clearly improves results.' }],
    sources: [S.effective],
  },

  // ---------- 5. Subagents ----------
  p_a2: {
    plain: ['A builder edits files, so it needs Read, Edit, Write and maybe Bash.', 'Give it only those. No web, no client apps.', 'Its description says when to use it, so the lead picks it for the right jobs.'],
    examples: [{ title: 'Builder helper', tone: 'good', file: '.claude/agents/site-editor.md', why: 'Narrow job, narrow tools.', code: L('---', 'name: site-editor', 'description: Edits the client website in website/. Use for copy, layout or form changes.', 'tools: Read, Edit, Write, Bash', '---', 'Change only files in website/. Run npm run build after edits and fix any error before reporting.') }],
    myths: [{ myth: 'Leaving tools blank keeps it safe.', truth: 'Blank means it inherits every tool. List the tools.' }],
    sources: [S.sub],
  },
  p_a3: {
    plain: ['An ops helper checks things: status, logs, numbers.', 'Read-only tools where possible.', 'It runs on the machine Claude Code runs on, under the same permission rules.'],
    examples: [{ title: 'Read-only ops helper', tone: 'good', file: '.claude/agents/ops-check.md', why: 'Can look, cannot change.', code: L('---', 'name: ops-check', 'description: Checks agent logs and recent errors. Use for "is everything running?".', 'tools: Read, Grep, Glob', '---', 'Report: what ran, what failed, the file and line. Do not fix anything.') }],
    myths: [{ myth: 'A helper sees the whole conversation.', truth: 'Only the handoff text reaches it (a fork is the exception). Put file paths and decisions in the handoff.' }],
    sources: [S.sub, S.sdkSub],
  },
  p_a4: {
    plain: ['Managed Agents: Anthropic hosts the agent, its computer (environment) and each run (session).', 'You define the agent once; start a session per job (per lead, per report).', 'Each session gets only the vaults (keys) you pass it.', 'Anthropic sends your server webhooks when a session needs you.'],
    pictures: [{ kind: 'flow', title: 'Hosted agent pieces', steps: [
      { label: 'Agent', note: 'model, prompt, tools, MCP servers' },
      { label: 'Environment', note: 'the hosted computer it runs in' },
      { label: 'Session per job', note: 'with that client\'s vault' },
      { label: 'Webhooks back to you', note: 'idle, budget reached, finished' },
    ] }],
    decide: [
      { if: 'You do not want to run servers', then: 'Managed Agents' },
      { if: 'You need it on your own machines or network', then: 'Agent SDK in your own container' },
    ],
    myths: [{ myth: 'A cloud agent can reach my laptop.', truth: 'It runs in a hosted container and reaches only what you connect (MCP servers, vault keys).' }],
    sources: [S.managed, S.hosting, S.managedNew],
  },

  // ---------- 7. Tools ----------
  p_k1: {
    plain: ['When there are many tools, do not load them all up front.', 'Claude sees a search tool plus your most-used tools, and looks up the rest when needed.', 'Claude Code and the Agent SDK do this by default for MCP tools.'],
    myths: [{ myth: 'More tools loaded = more capable agent.', truth: 'Too many tool definitions hurt tool choice. Anthropic measured picking accuracy going from 49% to 74% with tool search on.' }],
    sources: [S.advTools],
  },
  p_k2: {
    examples: [
      { title: 'Weak tool', tone: 'bad', file: 'tool definition', why: 'Vague name, vague input. The agent guesses.', code: L('name: search', 'description: Searches.', 'input: user (string)') },
      { title: 'Strong tool', tone: 'good', file: 'tool definition', why: 'Says what, when, which inputs, what comes back, and the limit.', code: L('name: ghl_contacts_search', 'description: Find contacts in ONE client\'s GHL sub-account by name, phone or email.', '  Use before creating a contact to avoid duplicates. Returns name, phone,', '  last_message_at. Max 20 per call; use page to get more.', 'input: location_id (string), query (string), page (int, default 1)') },
    ],
    myths: [{ myth: 'The code matters, the description is just a label.', truth: 'The description is what the agent reads to decide. Anthropic\'s tool-testing agent rewrote descriptions and cut task time 40%.' }],
    sources: [S.tools, S.research],
  },
  p_k3: {
    plain: ['Look at the calls the agent always makes together.', 'Turn that chain into one tool named after the job.', 'Fewer, smarter tools mean fewer mistakes and less context.'],
    pictures: [
      { kind: 'flow', title: 'Before: 4 raw calls', steps: [{ label: 'get_contact', tone: 'bad' }, { label: 'get_calendar', tone: 'bad' }, { label: 'create_appointment', tone: 'bad' }, { label: 'send_confirmation', tone: 'bad' }] },
      { kind: 'flow', title: 'After: 1 job-sized tool', steps: [{ label: 'book_estimate(contact, day)', note: 'does all four inside', tone: 'good' }] },
    ],
    myths: [{ myth: 'Wrapping every API endpoint as a tool is thorough.', truth: 'Anthropic: do not wrap your API one-to-one. Group tools around what the agent is trying to get done.' }],
    sources: [S.tools, S.mcpProd],
  },
  p_k4: {
    examples: [
      { title: 'Noisy result', tone: 'bad', file: 'tool returns', why: 'IDs and junk the agent does not need.', code: L('{"uuid":"8f2c...","mime_type":"application/json","256px_image_url":"...",', ' "contact":{"id":"x91","f_name":"Joe","raw":{...500 lines...}}}') },
      { title: 'Clean result', tone: 'good', file: 'tool returns', why: 'Names the agent can act on, and a hint when it was cut.', code: L('{"name":"Joe Smith","phone":"+15175550123","last_message":"Can you come Tuesday?",', ' "note":"Showing 20 of 54. Ask with page=2 for more."}') },
    ],
    myths: [{ myth: 'Return everything, the model will sort it out.', truth: 'Big results eat context and distract. Claude Code caps tool results at 25,000 tokens; return only what drives the next step.' }],
    sources: [S.tools],
  },

  // ---------- 8. Gateway ----------
  p_g2: {
    plain: ['Three lists in settings.json: allow (just do it), ask (check with you), deny (never).', 'Checked deny first, then ask, then allow.', 'Write the narrowest rule that does the job.'],
    myths: [{ myth: 'If I allow something specific, it beats a broad deny.', truth: 'Deny always wins. A narrow allow cannot carve a hole in a deny.' }],
    sources: [S.perm],
  },
  p_g3: {
    plain: ['Anything that matches an ask rule waits for your yes.', 'Your permission mode decides how much else asks: check which mode you are in.', 'Put every send, spend and delete in ask or deny, so it never depends on the mode.'],
    examples: [{ title: 'Ask before anything leaves', tone: 'good', file: '.claude/settings.json', why: 'Client messages and pushes always wait for you.', code: L('{ "permissions": { "ask": [', '  "mcp__ghl__send_sms",', '  "mcp__ghl__send_email",', '  "Bash(git push *)"', '] } }') }],
    myths: [{ myth: 'Claude always asks before risky things.', truth: 'It depends on the mode, and auto mode became the default for new sessions on Pro, Max and Team plans in August 2026. Write ask rules for what must wait for you.' }],
    sources: [S.perm, S.whatsNew],
  },
  p_g4: {
    plain: ['A managed-settings.json in a system folder, set by the admin (you, on your own Mac).', 'On a Mac: /Library/Application Support/ClaudeCode/managed-settings.json.', 'It wins over user and project settings, and can make Claude ignore everyone else\'s permission rules.'],
    examples: [{ title: 'Anthropic\'s example', tone: 'good', file: 'managed-settings.json', why: 'Blocks two reads, turns off bypass mode, and only allows the admin\'s permission rules.', code: L('{', '  "permissions": {', '    "deny": ["Read(./.env)", "Read(./secrets/**)"],', '    "disableBypassPermissionsMode": "disable"', '  },', '  "allowManagedPermissionRulesOnly": true', '}') }],
    myths: [{ myth: 'A project can override the admin file.', truth: 'Managed settings are the top of the stack. Users and projects cannot loosen them.' }],
    sources: [S.managedSettings],
  },

  // ---------- 9. Tool runs ----------
  p_t2: {
    plain: ['Bash lets the agent use the computer like you would: run scripts, move files, call CLIs.', 'Code is precise and reusable, so Anthropic leans on the agent writing code for complex work.', 'Every command still passes the permission rules; the OS-level sandbox can confine writes and network.'],
    examples: [{ title: 'Shell rules', tone: 'good', file: '.claude/settings.json', why: 'Common commands flow; risky ones stop.', code: L('{ "permissions": {', '  "allow": ["Bash(npm run *)", "Bash(git status)"],', '  "ask":   ["Bash(git push *)"],', '  "deny":  ["Bash(rm -rf *)", "Bash(curl *)"]', '} }') }],
    myths: [{ myth: 'Never give an agent Bash.', truth: 'Anthropic treats Bash as a core general-purpose tool. Control it with rules and the sandbox instead of removing it.' }],
    sources: [S.sdkBlog, S.perm],
  },
  p_t3: {
    plain: ['Run the agent in a container so it has its own files, processes and network.', 'Mount only the folders it needs, read-only where possible.', 'Give it no direct internet: route through a proxy that allows only listed sites and adds keys.', 'Log everything at the proxy.'],
    pictures: [{ kind: 'flow', title: 'Anthropic\'s locked-down setup', steps: [
      { label: 'Agent container', note: 'no network of its own' },
      { label: 'Proxy outside it', note: 'allowlist sites, inject keys, log', tone: 'good' },
      { label: 'Only approved APIs', many: ['GHL', 'Google Ads'] },
    ] }],
    examples: [{ title: 'Container with no network', file: 'shell', why: 'From the secure deployment guide: the only way out is the proxy socket you mount.', code: 'docker run --network none -v /run/proxy.sock:/run/proxy.sock:ro my-agent' }],
    myths: [{ myth: 'It is in a container, so it is safe.', truth: 'A container with open internet and keys inside can still leak them. Anthropic adds network limits and keeps keys outside.' }],
    sources: [S.secure, S.hosting],
  },

  // ---------- 10. Lands ----------
  p_l2: {
    pictures: [{ kind: 'files', title: 'Project B: hot tub dealer, same pieces', root: { label: 'bluewater-spas/', children: [
      { label: 'CLAUDE.md', note: 'dealer facts, financing gotchas' },
      { label: '.mcp.json', note: 'only Bluewater\'s servers' },
      { label: '.claude/settings.json', note: 'ask before any price or financing message' },
      { label: 'agent/', note: 'event-driven, like the email-agent demo', children: [{ label: 'listeners/new_chat.ts', note: 'runs when a website chat arrives' }, { label: 'prompts/' }, { label: 'logs/' }] },
      { label: 'evals/', note: 'fake chats + graders' },
      { label: '(no .env)', note: 'keys in vault "bluewater"', tone: 'good' },
      { label: '(plugin) roas-toolkit', note: 'same shared skills as Acme', tone: 'good' },
    ] } }],
    examples: [{ title: 'Listener, shaped like Anthropic\'s email demo', file: 'agent/listeners/new_chat.ts', why: 'Their demo uses config + handler and a small fast model to classify. Adapted from email to chat; the shape is theirs.', code: L(
      'export const config = { id: "new-chat", name: "New website chat", enabled: true, event: "chat_received" };',
      '',
      'export async function handler(chat, context) {',
      '  const sort = await context.callAgent({',
      '    prompt: `Is this a buying question, service issue or spam?\\n${chat.text}`,',
      '    schema: { type: "object", properties: { kind: { type: "string" } }, required: ["kind"] },',
      '    model: "haiku",',
      '  });',
      '  if (sort.kind === "spam") return;',
      '  // draft a reply; staff approve 9 to 5',
      '}',
    ) }],
    sources: [S.emailDemo],
  },
  p_l3: {
    plain: ['After each finished step: commit with a message that says what changed and why.', 'Git is the undo button for agents: roll back a bad change.', 'The next session reads git log to see what happened.'],
    examples: [{ title: 'Useful commit message', tone: 'good', file: 'git log', why: 'A fresh session can understand it without asking.', code: L('Lead form: post to GHL webhook, normalize phone to +1', '', 'Tested with 3 fake leads in the test sub-account; all created.') }],
    myths: [{ myth: 'Commit at the end of the day.', truth: 'Anthropic\'s harness commits after each finished piece, so any bad step can be reverted on its own.' }],
    sources: [S.harness],
  },
  p_l4: {
    examples: [{ title: 'Install the shared plugin in a new client repo', file: 'Claude Code', why: 'Add your marketplace once, then install by name in each repo.', code: L('/plugin marketplace add your-org/roas-plugins', '/plugin install roas-toolkit@roas-plugins') }],
    myths: [{ myth: 'Copy the best client repo for each new client.', truth: 'Copies drift apart. Shared pieces belong in one plugin you update once.' }],
    sources: [S.plugins],
  },

  // ---------- 11. Review ----------
  p_r1: {
    plain: ['One agent builds; a separate agent grades.', 'Agents grading their own work tend to be too easy on it, so the grader is tuned to be skeptical.', 'The grader checks the real thing (for an app, it clicks through it), not just the code.'],
    pictures: [{ kind: 'flow', title: 'Build, grade, fix', steps: [{ label: 'Builder makes it' }, { label: 'Grader checks against the rubric', note: 'own context, skeptical' }, { label: 'Pass?', many: ['yes: done', 'no: specific fixes back to builder'] }] }],
    myths: [{ myth: 'Ask the same agent to double-check its work.', truth: 'Anthropic found a separate evaluator far more reliable than self-review.' }],
    sources: [S.harnessDesign, S.managedNew],
  },
  p_r2: {
    plain: ['After the answer is written, a citation agent matches each claim to the source that backs it.', 'Claims with no source get fixed or cut.'],
    pictures: [{ kind: 'flow', title: 'Last check before you see it', steps: [{ label: 'Draft answer' }, { label: 'Citation agent reads draft + sources' }, { label: 'Every claim tied to a source', tone: 'good' }] }],
    myths: [{ myth: 'If it gave a link, the link supports the claim.', truth: 'Anthropic grades citation accuracy separately: does the cited source actually match the claim?' }],
    sources: [S.research],
  },
  p_r3: {
    examples: [{ title: 'Judge prompt shape', tone: 'good', file: 'grader prompt', why: 'One call, one rubric, scores plus pass/fail: what matched human judgment best for Anthropic.', code: L('Grade this research answer from 0.0 to 1.0 on:', '- factual accuracy (claims match sources)', '- citation accuracy (sources match claims)', '- completeness', '- source quality (primary over secondary)', '- tool efficiency', 'Then: PASS or FAIL.') }],
    myths: [{ myth: 'More judges = fairer grading.', truth: 'Anthropic tried several judges and found one call with one rubric the most consistent.' }],
    sources: [S.research],
  },

  // ---------- 12. Report ----------
  p_rep1: {
    plain: ['Helpers return short summaries, not their whole notes.', 'The lead combines them, decides if more is needed, then answers.', 'The answer comes with sources.'],
    examples: [{ title: 'What you get back', tone: 'good', file: 'answer', why: 'Result first, proof second, next step last.', code: L('Acme this week: 31 leads (+6), 9 booked, 4 sold ($18,400).', 'Source: GHL pipeline "Tree Jobs", pulled 10:02.', 'Flag: 5 leads waited over 1 hour for a first reply.', 'Next: approve the 5 drafted follow-ups?') }],
    myths: [{ myth: 'You get every helper\'s full work back.', truth: 'Only each helper\'s final message returns. That is the point: the lead\'s context stays clean.' }],
    sources: [S.research, S.sdkSub],
  },
  p_rep2: {
    plain: ['Every model call logs its tokens and cost.', 'In the trace: cost_usd on each api_request, joined by prompt.id.', 'In the Agent SDK: the final result carries the run\'s total cost.', 'Set a spend cap so a run can never surprise you.'],
    examples: [{ title: 'Reading cost in the SDK (Python)', file: 'agent.py', why: 'The last message of a run has the total.', code: L('async for m in query(prompt=task, options=options):', '    if type(m).__name__ == "ResultMessage":', '        print("cost:", m.total_cost_usd)') }],
    myths: [{ myth: 'I will notice if it gets expensive.', truth: 'Helpers multiply tokens (about 15 times for multi-agent). Watch cost per run and cap it.' }],
    sources: [S.mon, S.sdkSub, S.research],
  },

  // ---------- 13. Learn ----------
  p_e1: {
    plain: ['Open the transcript of a failed run.', 'Ask: real mistake, or did the check reject a good answer?', 'Write the fix where it belongs: skill gotcha, tool description, or the check.'],
    examples: [{ title: 'Where transcripts live', file: 'paths', why: 'Claude Code keeps session logs; Anthropic\'s demo writes one per run.', code: L('~/.claude/projects/<project>/<session>.jsonl    Claude Code sessions', 'logs/session_<time>/transcript.txt               research-agent demo', 'logs/session_<time>/tool_calls.jsonl             every tool call, by agent') }],
    myths: [{ myth: 'The score tells you what went wrong.', truth: 'Only the transcript does. Anthropic reads them regularly.' }],
    sources: [S.evals, S.researchDemo],
  },
  p_e2: {
    plain: ['Claude writes it itself when you correct it or state a preference.', 'Say "remember X" and it goes there.', 'Open /memory to read, edit or delete.'],
    myths: [{ myth: 'Auto memory is where my rules go.', truth: 'Memory is learnings. Rules go in CLAUDE.md ("add this to CLAUDE.md"). Must-never goes in hooks or deny.' }],
    sources: [S.mem],
  },
  p_e3: {
    plain: ['Before changing a skill or prompt: write 5 to 20 test tasks from real work.', 'Run them on the current version and note the score.', 'Change one thing, re-run, compare. Keep it only if the score goes up.'],
    pictures: [{ kind: 'flow', title: 'Change safely', steps: [{ label: 'Tests from real work' }, { label: 'Score the current version' }, { label: 'Change one thing' }, { label: 'Score again' }, { label: 'Better? keep. Worse? undo.', tone: 'good' }] }],
    myths: [{ myth: 'It feels better, so it is better.', truth: 'Anthropic: build evals first, then write the skill. The score decides.' }],
    sources: [S.skills, S.evals],
  },
  p_e4: {
    plain: ['Change CLAUDE.md, skills and settings through a pull request.', 'Someone (or a reviewer agent) reads the change.', 'After merge, watch whether behavior actually changed.'],
    examples: [{ title: 'Instruction change as a PR', file: 'pull request', why: 'Treat instructions like code: reviewed, revertable, owned.', code: L('Title: weekly-report skill: add gotcha for "Job Sold" stage', 'Why: 3 reports counted won deals from the wrong field (transcripts linked)', 'Test: evals/weekly-report 7/10 -> 10/10') }],
    myths: [{ myth: 'Edit CLAUDE.md live whenever something goes wrong.', truth: 'Anthropic: review it like code, prune it regularly, and check that behavior actually shifts.' }],
    sources: [S.steer, S.best],
  },
  p_e5: {
    examples: [{ title: 'A gotchas section that grew', tone: 'good', file: 'SKILL.md', why: 'Each line is a real failure that will not happen twice.', code: L('## Gotchas', '- "Won" is the stage Job Sold, not the status field. (2026-09-14)', '- GHL returns 100 rows per page; always paginate. (2026-09-20)', '- Acme\'s Sunday leads come from Angi; tag them before counting. (2026-10-02)') }],
    myths: [{ myth: 'Lessons go in one big lessons file.', truth: 'Anthropic puts the lesson inside the skill it is about, where it loads exactly when needed.' }],
  },
  p_e6: {
    pictures: [{ kind: 'flow', title: 'Between sessions', steps: [{ label: 'Past sessions + memory stores' }, { label: 'Dreaming reviews them on a schedule' }, { label: 'Finds repeat mistakes and shared habits' }, { label: 'Updates memory, or proposes changes for you to approve', tone: 'good' }] }],
    myths: [{ myth: 'Dreaming is part of Claude Code.', truth: 'It is a Managed Agents feature (research preview since May 2026).' }],
  },

  // ---------- Library ----------
  p_lib_limits: {
    plain: ['Most limits are guidance: past them, Claude follows instructions less well.', 'A few are hard cut-offs: MEMORY.md past 200 lines or 25KB is not loaded; a CLAUDE.md over 4 MiB is skipped.'],
    myths: [{ myth: 'If it loads, it gets followed.', truth: 'Loaded and followed are different. Long files lower adherence even when every line loads.' }],
  },
  p_lib_mcp: {
    plain: ['Add a server with claude mcp add, or write it in .mcp.json.', 'Pick the scope: just you in this project, the whole team (committed .mcp.json), or you in every project.', 'Secrets go in as ${VARIABLE}, never typed into the file.'],
    decide: [
      { if: 'Only you, only this project', then: 'Local scope (the default)' },
      { if: 'Everyone working on this repo', then: 'Project scope: .mcp.json committed to git' },
      { if: 'You, in every project', then: 'User scope' },
    ],
    myths: [{ myth: 'A server with a url and no type works.', truth: 'Claude Code reads it as a local server and skips it. Remote needs "type": "http".' }],
    sources: [S.mcp],
  },
  p_lib_settings: {
    plain: ['Settings stack: the higher one wins.', 'Personal tweaks for one project go in .claude/settings.local.json (not committed).', 'Team rules go in .claude/settings.json (committed).'],
    pictures: [{ kind: 'flow', title: 'Who wins (top beats bottom)', steps: [
      { label: 'Managed settings', note: 'admin, cannot be overridden', tone: 'good' },
      { label: 'Command line flags' },
      { label: '.claude/settings.local.json', note: 'you, this project' },
      { label: '.claude/settings.json', note: 'team, this project' },
      { label: '~/.claude/settings.json', note: 'you, every project' },
    ] }],
    myths: [{ myth: 'My personal settings file can loosen a team deny.', truth: 'Deny rules are checked first wherever they come from, and managed settings sit on top of everything.' }],
    sources: [S.settings, S.perm],
  },

  // ---------- Rails ----------
  p_x1: {
    plain: ['Each agent gets only the tools its job needs.', 'Read-only by default; write tools only for builders.', 'Client-facing agents never get delete or spend tools.'],
    examples: [{ title: 'Tools per agent', tone: 'good', file: 'Anthropic research demo', why: 'From their demo: the lead only delegates; each helper gets a short list.', code: L('lead:          Task', 'researcher:    WebSearch, Write', 'data-analyst:  Glob, Read, Bash, Write', 'report-writer: Skill, Write, Glob, Read, Bash') }],
    myths: [{ myth: 'Give every agent every tool so it is never stuck.', truth: 'More tools = more ways to go wrong and more context used. Anthropic\'s own lead agent gets one tool.' }],
    sources: [S.researchDemo, S.sub],
  },
  p_x2: {
    plain: ['Every tool call passes the same gate: hooks, then rules, then you if needed.', 'Hooks are code, so they never forget.', 'Rules are lists, so they are easy to read.'],
    myths: [{ myth: 'A hook can approve something a deny rule blocks.', truth: 'No. Deny and ask rules are checked no matter what a hook returns.' }],
    sources: [S.perm],
  },
  p_x5: {
    plain: ['A fixed set of real test tasks, kept in the repo.', 'Run before every change to skills, prompts or tools.', 'Several runs per task; read the failures.'],
    myths: [{ myth: 'Evals are only for big AI labs.', truth: 'Anthropic: start early with a small set. Twenty real cases beats none.' }],
    sources: [S.evals],
  },
  p_x6: {
    plain: ['CLAUDE.md, rules, skills, agents, settings.json and .mcp.json all live in the repo.', 'Changes go through review.', 'Personal stuff stays out: CLAUDE.local.md and settings.local.json are not committed.'],
    myths: [{ myth: 'CLAUDE.md is my private notes.', truth: 'The project CLAUDE.md is a shared, checked-in file. Personal notes go in CLAUDE.local.md.' }],
    sources: [S.mem, S.steer],
  },
  p_x7: {
    plain: ['Skim the weekly What\'s new digest; it lists what changes how you work.', 'Check the changelog when something behaves differently.', 'When a new model ships, re-test and remove old workarounds.'],
    myths: [{ myth: 'Set it up once and it stays best practice.', truth: 'Anthropic deleted over 80% of Claude Code\'s own system prompt for Claude 5 models. What was needed last year can now hurt.' }],
    sources: [S.whatsNew, S.changelog, S.ctx],
  },
  p_x8: {
    examples: [{ title: 'Cap and cheaper helpers (Python)', tone: 'good', file: 'agent.py', why: 'A hard spend limit for the whole run, helpers on a smaller model like Anthropic\'s demo.', code: L('options = ClaudeAgentOptions(', '    max_budget_usd=2.00,', '    agents={"researcher": AgentDefinition(..., model="haiku")},', ')') }],
    sources: [S.sdkSub, S.researchDemo],
  },
  p_x10: {
    examples: [{ title: 'Session habits', file: 'Claude Code commands', why: 'Straight from Anthropic\'s best practices.', code: L('/clear      new task, fresh start', '/compact    part of the task is done; keep the essentials', '/context    see what is loaded', '/rewind     go back to before a bad turn', 'Esc         stop Claude mid-action and redirect') }],
    sources: [S.best, S.sessions],
  },
};

const EXTRA: Record<string, More> = {
  p_x11: {
    plain: [
      'Work ledger: claude-progress.txt + feature_list.json + git log. Answers "what is done and what is next". Every new session reads it first.',
      'Action ledger: the trace (every model call, tool decision, result and cost under one prompt.id) plus a per-agent tool log written by hooks. Answers "who did what, when".',
      'Event ledger: your own log of every webhook and trigger you receive. Anthropic says webhooks can be dropped, so this is the only complete record.',
      'Who-for: in Managed Agents the vault ties each action to the client it was done for.',
      'Managed Agents keeps every step and shows which agent did what, in what order, and why in the Console.',
    ],
    pictures: [{ kind: 'tree', title: 'Three ledgers', root: { label: 'The ledger', children: [
      { label: 'Work', note: 'progress file, feature list, git log', tone: 'good' },
      { label: 'Actions', note: 'trace by prompt.id, tool_calls.jsonl', tone: 'good' },
      { label: 'Events', note: 'your own log of webhooks', tone: 'good' },
    ] } }],
    examples: [
      { title: 'Action ledger line (Anthropic research demo)', tone: 'good', file: 'logs/session_<time>/tool_calls.jsonl', why: 'Written by PreToolUse and PostToolUse hooks; every call tagged with the agent that made it.', code: L('{"event":"tool_call_start","agent_id":"RESEARCHER-1","tool_name":"WebSearch",...}', '{"event":"tool_call_complete","success":true,"output_size":15234}') },
      { title: 'Work ledger', tone: 'good', file: 'claude-progress.txt + git log', why: 'What a new session reads before touching anything.', code: L('$ cat claude-progress.txt', '- Done: lead form posts to GHL (tested)', '- Next: first reply within 5 minutes', '$ git log --oneline -3', 'a1c2 Lead form: normalize phone to +1', '9f0e Add fake-lead evals', '7b3d Initial setup') },
    ],
    decide: [
      { if: 'You need to know what is finished', then: 'Work ledger (progress file + git)' },
      { if: 'You need to know what an agent did and what it cost', then: 'Action ledger (trace + tool log)' },
      { if: 'You need to prove an event arrived (new lead, approval)', then: 'Your own event log' },
    ],
    myths: [{ myth: 'One ledger file can hold everything.', truth: 'Anthropic splits it: work state lives with the code, actions live in the trace, events live in your own log. Each answers a different question.', fix: 'Keep three: progress file + git for work, telemetry + hook log for actions, an append-only log for every webhook. Link them by session or prompt.id.' }],
    sources: [S.harness, S.mon, S.researchDemo, S.managedNew, 'https://platform.claude.com/docs/en/managed-agents/webhooks', 'https://platform.claude.com/docs/en/managed-agents/vaults'],
  },
  p_x3: {
    plain: ['Turn on telemetry with a few environment variables and send it to a collector.', 'Every event from one request shares a prompt.id: filter by it to replay the whole run.', 'Tool inputs are hidden unless you turn on tool detail logging.', 'For your own SDK agents, copy Anthropic\'s demo: hooks before and after every tool call, written to a log per agent.'],
    myths: [{ myth: 'The chat history is my trace.', truth: 'Chat shows words. The trace shows every model call, tool decision, result, time and cost, joined by one ID.' }],
    sources: [S.mon, S.researchDemo],
  },
  p_x4: {
    myths: [{ myth: 'Telling the agent "stop" in chat is a kill switch.', truth: 'A real switch works without the agent\'s cooperation: a deny rule, a revoked key, or an archived session.' }],
    decide: [
      { if: 'One tool is misbehaving', then: 'Deny that tool name' },
      { if: 'One client\'s agent must stop', then: 'Revoke that client\'s vault credential' },
      { if: 'Everything on your Mac must stop doing X', then: 'Deny in managed-settings.json' },
    ],
  },
  p_x2: {
    pictures: [{ kind: 'flow', title: 'The gate every call passes', steps: [{ label: 'PreToolUse hooks', note: 'code checks' }, { label: 'Deny rules' }, { label: 'Ask rules', note: 'your yes' }, { label: 'Allow rules' }, { label: 'Tool runs', tone: 'good' }] }],
  },
  p_x5: {
    examples: [{ title: 'A tiny eval set in the repo', tone: 'good', file: 'evals/', why: 'Small and real beats big and imaginary.', code: L('evals/', '  no-price/        case + grader: never quote a price', '  books-visit/     case + grader: asks for a site visit', '  spam-ignored/    case + grader: no reply to spam', '  angry-lead/      case + grader: hands off to a human') }],
  },
  p_x6: {
    pictures: [{ kind: 'files', title: 'In git vs not', root: { label: 'repo/', children: [
      { label: 'CLAUDE.md', note: 'committed', tone: 'good' },
      { label: '.claude/settings.json', note: 'committed', tone: 'good' },
      { label: '.claude/skills/  agents/  rules/', note: 'committed', tone: 'good' },
      { label: '.mcp.json', note: 'committed, secrets as ${VAR}', tone: 'good' },
      { label: 'CLAUDE.local.md', note: 'personal, not committed', tone: 'neutral' },
      { label: '.claude/settings.local.json', note: 'personal, not committed', tone: 'neutral' },
    ] } }],
  },
  p_ui2: {
    decide: [{ if: 'Background for one body of work', then: 'A Project' }, { if: 'How-to you use across work', then: 'A skill' }],
  },
};

type ArrKey = 'plain' | 'pictures' | 'examples' | 'decide' | 'myths' | 'build' | 'pros' | 'noobs' | 'limits' | 'sources';
const KEYS: ArrKey[] = ['plain', 'pictures', 'examples', 'decide', 'myths', 'build', 'pros', 'noobs', 'limits', 'sources'];
for (const [id, extra] of Object.entries(EXTRA)) {
  const base: More = PRO_FILL[id] ?? {};
  const merged: Record<string, unknown[]> = {};
  for (const k of KEYS) {
    const all = [...((base[k] as unknown[] | undefined) ?? []), ...((extra[k] as unknown[] | undefined) ?? [])];
    if (all.length) merged[k] = all;
  }
  PRO_FILL[id] = merged as More;
}
