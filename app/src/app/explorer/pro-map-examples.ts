/**
 * Examples, pictures, plain steps and if/then rules for the Anthropic side of the Pro Map.
 * File formats follow Anthropic's docs (re-read 2026-10-12). Client names are made up.
 * Anything Anthropic does not publish (agency repo layout, rule line counts) is labeled as our layout or our reading.
 */
export type TreeNode = { label: string; note?: string; tone?: 'good' | 'bad' | 'neutral'; children?: TreeNode[] };
export type FlowStep = { label: string; note?: string; many?: string[]; tone?: 'good' | 'bad' | 'neutral' };
export type Picture =
  | { kind: 'tree'; title: string; caption?: string; root: TreeNode }
  | { kind: 'files'; title: string; caption?: string; root: TreeNode }
  | { kind: 'flow'; title: string; caption?: string; steps: FlowStep[] };
export type Example = { title: string; why: string; file?: string; code: string; tone?: 'good' | 'bad' };
export type Rule = { if: string; then: string };
export type ProExamples = { plain?: string[]; pictures?: Picture[]; examples?: Example[]; decide?: Rule[]; sources?: string[] };

const L = (...lines: string[]) => lines.join('\n');
const S = {
  mem: 'https://code.claude.com/docs/en/memory',
  steer: 'https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more',
  skills: 'https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices',
  hooks: 'https://code.claude.com/docs/en/hooks-guide',
  perm: 'https://code.claude.com/docs/en/permissions',
  mcp: 'https://code.claude.com/docs/en/mcp',
  mcpProd: 'https://claude.com/blog/building-agents-that-reach-production-systems-with-mcp',
  cloudflare: 'https://developers.cloudflare.com/agents/model-context-protocol/guides/remote-mcp-server/',
  sub: 'https://code.claude.com/docs/en/sub-agents',
  sdkSub: 'https://code.claude.com/docs/en/agent-sdk/subagents',
  sdkBlog: 'https://claude.com/blog/building-agents-with-the-claude-agent-sdk',
  research: 'https://www.anthropic.com/engineering/multi-agent-research-system',
  harness: 'https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents',
  hosting: 'https://code.claude.com/docs/en/agent-sdk/hosting',
};

const loadFlow: Picture = {
  kind: 'flow', title: 'What loads, and when', caption: 'Top = always loaded. Lower = only when needed. This is why small files win.',
  steps: [
    { label: 'Session starts', many: ['CLAUDE.md (root)', 'Rules with no paths', 'Skill names + descriptions', 'MEMORY.md (first 200 lines)'] },
    { label: 'Claude works inside website/', many: ['website/CLAUDE.md', 'Rules with paths: website/**'] },
    { label: 'A skill is used', many: ['That SKILL.md body'] },
    { label: 'It needs a detail', many: ['One reference file', 'One memory topic file'] },
  ],
};

export const PRO_EXAMPLES: Record<string, ProExamples> = {
  // ---------------- CLAUDE.md ----------------
  p_ptr1: {
    plain: [
      'Make a file called CLAUDE.md in the top folder of the project.',
      'Line 1 to 3: what this project is, in plain words.',
      'Then the commands it needs (how to run, how to test).',
      'Spend most of the file on gotchas: the things Claude would get wrong without being told.',
      'Keep it under 200 lines. Steps go in a skill. "Never do X" goes in a hook or deny rule.',
    ],
    pictures: [loadFlow],
    examples: [
      {
        title: 'Good: one local service client', tone: 'good', file: 'acme-tree-service/CLAUDE.md',
        why: 'Short. Says what the project is, the commands, then mostly gotchas. Brand voice is pulled in with an import instead of pasted.',
        code: L(
          '# Acme Tree Service: leads, sales, website, dashboard',
          'GHL sub-account + website + dashboard + the lead responder agent for Acme.',
          '',
          '## Commands',
          '- npm run dev: dashboard on localhost:3000',
          '- npm run test: run before saying anything is done',
          '',
          '## Gotchas',
          '- Acme pipeline is "Tree Jobs", not the default GHL pipeline.',
          '- Phone numbers must be +1 format (E.164). GHL rejects others.',
          '- Never quote prices. The owner prices on site visits.',
          '- website/ deploys on every push to main.',
          '',
          '## More',
          '- Brand voice: @docs/brand-voice.md',
        ),
      },
      {
        title: 'Bad: the kitchen sink', tone: 'bad', file: 'CLAUDE.md',
        why: 'Every marked line belongs somewhere else (Anthropic\'s list of common mistakes).',
        code: L(
          '# Project',
          'You are a helpful assistant. Write clean code.     <- obvious, delete',
          'ALWAYS run prettier after every edit.              <- make it a hook',
          'NEVER delete contacts.                             <- make it a deny rule',
          '## How to deploy (32 steps)                        <- make it a skill',
          '## Our whole API (400 lines)                       <- path-scoped rule',
        ),
      },
      {
        title: 'Big project: one per folder', file: 'repo layout',
        why: 'The root file always loads. A folder\'s CLAUDE.md loads only when Claude works in that folder.',
        code: L(
          'CLAUDE.md              always loaded',
          'website/CLAUDE.md      loads when working in website/',
          'dashboard/CLAUDE.md    loads when working in dashboard/',
        ),
      },
    ],
    decide: [
      { if: 'Claude needs it in every session and it is short', then: 'CLAUDE.md' },
      { if: 'It only matters in some folders', then: 'A rule with paths:, or that folder\'s own CLAUDE.md' },
      { if: 'It is a set of steps', then: 'A skill' },
      { if: 'It must happen every time, or must never happen', then: 'A hook or a permission rule' },
      { if: 'It is personal and should not be committed', then: 'CLAUDE.local.md or ~/.claude/rules/' },
    ],
    sources: [S.mem, S.steer],
  },

  // ---------------- AGENTS.md ----------------
  p_ptr2: {
    plain: [
      'Use AGENTS.md when more than one AI app works in the same project (Codex, Cursor, Claude Code).',
      'Write it exactly like a CLAUDE.md: what the project is, commands, gotchas, under 200 lines.',
      'Claude Code reads it when there is no CLAUDE.md.',
      'If Claude needs extras, add a tiny CLAUDE.md that imports AGENTS.md and adds a few lines.',
    ],
    examples: [
      {
        title: 'Type 1: AGENTS.md only (every app reads it)', tone: 'good', file: 'AGENTS.md',
        why: 'One file, every coding agent. Simplest setup when nothing is app-specific.',
        code: L(
          '# Acme Tree Service',
          'Lead gen + sales system for Acme (GHL sub-account, website, dashboard).',
          '',
          '## Commands',
          '- npm run test before any commit',
          '',
          '## Gotchas',
          '- Pipeline is "Tree Jobs". Phone numbers in +1 format.',
        ),
      },
      {
        title: 'Type 2: shared AGENTS.md + thin CLAUDE.md', tone: 'good', file: 'CLAUDE.md',
        why: 'Shared rules live once in AGENTS.md. Claude-only extras sit on top, so nothing is copied twice.',
        code: L(
          '@AGENTS.md',
          '',
          '## Claude Code only',
          '- Use the researcher subagent for web research.',
          '- Use the weekly-report skill for any numbers request.',
        ),
      },
      {
        title: 'Type 3: one per folder', file: 'repo layout',
        why: 'Same as CLAUDE.md: a folder file adds rules only for that part of the project.',
        code: L('AGENTS.md            whole project', 'website/AGENTS.md    website only'),
      },
      {
        title: 'Not read by Claude Code', tone: 'bad', file: 'these are skipped',
        why: 'Claude Code ignores these names. Your ~/.agents folder works only because a script copies the rules out into CLAUDE.md and AGENTS.md.',
        code: L('AGENTS.local.md', 'AGENTS.override.md', '.agents/anything.md'),
      },
    ],
    decide: [
      { if: 'Only Claude Code uses the project', then: 'CLAUDE.md' },
      { if: 'Several AI apps use the same project', then: 'AGENTS.md (type 1)' },
      { if: 'Several apps AND Claude needs extras', then: 'AGENTS.md + thin CLAUDE.md that imports it (type 2)' },
    ],
    sources: [S.mem],
  },

  // ---------------- imports ----------------
  p_ptr3: {
    plain: ['Type @ and a file path on its own line inside CLAUDE.md.', 'That file gets read in at startup as if it were pasted there.', 'Use it to keep CLAUDE.md tidy, not to save space.'],
    pictures: [{
      kind: 'tree', title: 'Hops: up to 4 deep', caption: 'Each arrow is one hop. A 5th hop is not followed.',
      root: { label: 'CLAUDE.md', children: [
        { label: '@docs/brand-voice.md', note: 'hop 1', tone: 'good', children: [{ label: '@docs/words-we-avoid.md', note: 'hop 2', tone: 'good' }] },
        { label: '@AGENTS.md', note: 'hop 1', tone: 'good' },
      ] },
    }],
    examples: [{
      title: 'Import lines', file: 'CLAUDE.md',
      why: 'Paths are relative to the file that has the import. In backticks it would be plain text, not an import.',
      code: L('- Brand voice: @docs/brand-voice.md', '- Shared team rules: @~/.claude/team-rules.md'),
    }],
    sources: [S.mem],
  },

  // ---------------- rules ----------------
  p_ptr4: {
    plain: [
      'Make a folder .claude/rules/ in the project.',
      'One file per topic: website.md, ghl.md, security.md.',
      'At the top, add paths: with the folders it applies to. Then it only loads when Claude touches those files.',
      'No paths = always loaded, same as CLAUDE.md.',
    ],
    pictures: [{
      kind: 'files', title: 'A set of rules for one client project', caption: 'Only security.md loads every session. The rest load when Claude works in their folders.',
      root: { label: '.claude/rules/', children: [
        { label: 'security.md', note: 'no paths: always loaded', tone: 'neutral' },
        { label: 'website.md', note: 'paths: website/**', tone: 'good' },
        { label: 'dashboard.md', note: 'paths: dashboard/**', tone: 'good' },
        { label: 'ghl.md', note: 'paths: integrations/ghl/**', tone: 'good' },
      ] },
    }],
    examples: [
      {
        title: 'Path-scoped rule', tone: 'good', file: '.claude/rules/website.md',
        why: 'Loads only when Claude edits the website, so it costs nothing during dashboard work.',
        code: L(
          '---',
          'paths:',
          '  - "website/**"',
          '---',
          '# Website rules',
          '- One H1 per page; meta description under 160 characters.',
          '- Phone number comes from site.config.ts, never typed by hand.',
          '- Forms post to the GHL webhook in .env (GHL_FORM_WEBHOOK).',
        ),
      },
      {
        title: 'Path-scoped rule for an integration', tone: 'good', file: '.claude/rules/ghl.md',
        why: 'Gotchas for one app, loaded only when that code is touched.',
        code: L(
          '---',
          'paths:',
          '  - "integrations/ghl/**"',
          '---',
          '# GHL rules',
          '- Always pass the client locationId; never search across locations.',
          '- Paginate: GHL returns at most 100 rows per page.',
        ),
      },
      {
        title: 'Personal rule for every project', file: '~/.claude/rules/style.md',
        why: 'Your own preferences, applied everywhere you work.',
        code: L('# How I like answers', '- Answer first, then the reason.', '- No em dashes.'),
      },
    ],
    decide: [
      { if: 'It applies everywhere and is short', then: 'CLAUDE.md' },
      { if: 'It applies only to some folders', then: 'Rule with paths:' },
      { if: 'It applies to every project you touch', then: '~/.claude/rules/' },
      { if: 'It is steps to follow', then: 'Skill, not a rule' },
      { if: 'Breaking it would hurt (delete, send, spend)', then: 'Hook or deny rule, not a rule file' },
      { if: 'How long can a rule be?', then: 'Anthropic publishes no line limit for rules. Our reading: rules with no paths share the same budget as CLAUDE.md (under 200 lines together); path-scoped rules can be longer because they only load when needed.' },
    ],
    sources: [S.mem, S.steer],
  },

  // ---------------- pointers ----------------
  p_ptr5: {
    pictures: [{
      kind: 'tree', title: 'The 3 kinds of pointer (all plain text)', caption: 'JSON is only for settings and tool servers, never for pointers.',
      root: { label: 'Pointers', children: [
        { label: '@docs/x.md', note: 'in CLAUDE.md, loads at start', tone: 'good' },
        { label: 'See reference/api.md', note: 'in SKILL.md, read when needed', tone: 'good' },
        { label: '- [GHL quirks](project_ghl.md)', note: 'in MEMORY.md, read when needed', tone: 'good' },
      ] },
    }],
    sources: [S.mem, S.skills],
  },

  // ---------------- skills ----------------
  p_lib_skills: {
    plain: [
      'Make a folder: .claude/skills/weekly-report/ (or ~/.claude/skills/ for every project).',
      'Inside it, a SKILL.md: a short header (name + when to use it) and the steps.',
      'Put long details in separate files next to it and link each one straight from SKILL.md.',
      'Add a Gotchas section and grow it every time Claude trips.',
    ],
    pictures: [
      {
        kind: 'tree', title: 'Good: one level deep', caption: 'Every file is linked straight from SKILL.md, so Claude reads the whole file it needs and skips the rest.',
        root: { label: 'SKILL.md', note: 'overview + links', tone: 'good', children: [
          { label: 'metrics.md', note: 'reference/', tone: 'good' },
          { label: 'ghl-fields.md', note: 'reference/', tone: 'good' },
          { label: 'report.md', note: 'templates/', tone: 'good' },
          { label: 'pull_week.py', note: 'scripts/', tone: 'good' },
        ] },
      },
      {
        kind: 'tree', title: 'Bad: too deep', caption: 'Claude may only skim files that are linked from other linked files, and miss the real answer.',
        root: { label: 'SKILL.md', tone: 'bad', children: [{ label: 'advanced.md', tone: 'bad', children: [{ label: 'details.md', note: 'the actual info, buried', tone: 'bad' }] }] },
      },
      {
        kind: 'files', title: 'The skill folder', root: { label: '.claude/skills/weekly-report/', children: [
          { label: 'SKILL.md', note: 'under 500 lines' },
          { label: 'reference/', children: [{ label: 'metrics.md', note: 'table of contents if 100+ lines' }, { label: 'ghl-fields.md' }] },
          { label: 'templates/report.md' },
          { label: 'scripts/pull_week.py', note: 'code Claude runs instead of rewriting' },
        ] },
      },
    ],
    examples: [{
      title: 'A real-shaped SKILL.md', tone: 'good', file: '.claude/skills/weekly-report/SKILL.md',
      why: 'Description says when to use it with trigger words. Steps are short. Details are one link away. Gotchas at the bottom.',
      code: L(
        '---',
        'name: weekly-report',
        'description: Builds the weekly lead and sales report for one client from their GHL',
        '  sub-account. Use when asked for a weekly report, lead numbers, close rate, or',
        '  "how did we do this week" for a client.',
        '---',
        '# Weekly report',
        '1. Run scripts/pull_week.py for the client locationId.',
        '2. Count new leads, booked, won, lost; compare with last week.',
        '3. Fill templates/report.md.',
        '',
        'Metric definitions: see reference/metrics.md',
        'GHL field names: see reference/ghl-fields.md',
        '',
        '## Gotchas',
        '- "Won" is the stage Job Sold, not the status field.',
        '- GHL returns 100 rows per page; always paginate.',
      ),
    }],
    decide: [
      { if: 'You repeat the same steps', then: 'Make a skill' },
      { if: 'It is background facts about one client', then: 'That project\'s CLAUDE.md, not a skill' },
      { if: 'It connects to an app', then: 'MCP or a tool; the skill says how to use it' },
      { if: 'Several agents need the same know-how', then: 'One skill they all load, not copies in each agent' },
    ],
    sources: [S.skills],
  },

  // ---------------- memory ----------------
  p_lib_memory: {
    plain: [
      'Claude makes and fills this itself in ~/.claude/projects/<project>/memory/.',
      'MEMORY.md is the table of contents: one short line per memory with a link.',
      'Each link goes to a small topic file with the detail.',
      'You can open it with /memory and edit or delete lines.',
    ],
    pictures: [{
      kind: 'tree', title: 'Index on top, detail below', caption: 'Only MEMORY.md loads at start (first 200 lines or 25KB). Topic files are opened when needed.',
      root: { label: 'MEMORY.md', note: 'loaded every session', tone: 'good', children: [
        { label: 'user_role.md', note: 'who you are' },
        { label: 'feedback_testing.md', note: 'a correction you gave' },
        { label: 'project_ghl.md', note: 'context not in the code' },
        { label: 'reference_dashboards.md', note: 'where outside things live' },
      ] },
    }],
    examples: [
      {
        title: 'Good index', tone: 'good', file: 'memory/MEMORY.md',
        why: 'One line each. The detail lives in the linked file, so the index stays far under 200 lines.',
        code: L(
          '- [Role](user_role.md): agency owner; approves every client message',
          '- [Testing](feedback_testing.md): run tests before saying done',
          '- [GHL](project_ghl.md): pipeline names differ per client',
          '- [Dashboards](reference_dashboards.md): where each client dashboard lives',
        ),
      },
      {
        title: 'A topic file', tone: 'good', file: 'memory/feedback_testing.md',
        why: 'Short and specific. The modified date is added by Claude Code so you can see how fresh it is.',
        code: L(
          '---',
          'name: feedback_testing',
          'description: Run the test suite before claiming a task is done',
          'modified: 2026-10-12T14:03:00Z',
          '---',
          'Corrected twice for saying done before tests ran.',
          'Always run npm run test and show the result.',
        ),
      },
      {
        title: 'Bad: everything inline', tone: 'bad', file: 'memory/MEMORY.md',
        why: 'Past line 200 (or 25KB) nothing loads. Claude Code will tell Claude to rewrite it as an index.',
        code: L('# Memory (640 lines)', 'Full notes about every client, every call, every fix...', '...line 201 onward is never seen'),
      },
    ],
    decide: [
      { if: 'A rule you want followed', then: 'CLAUDE.md (you write it)' },
      { if: 'Something Claude learned from you', then: 'Auto memory (Claude writes it)' },
      { if: 'A subagent needs memory', then: 'Give it its own memory folder; it does not see the main one' },
    ],
    sources: [S.mem],
  },

  // ---------------- tool servers ----------------
  p_lib_mcp: {
    examples: [{
      title: 'One remote server, one local server', file: '.mcp.json',
      why: 'The remote entry needs type http. The secret comes from an environment variable, never typed in the file. Each client project lists only its own servers.',
      code: L(
        '{',
        '  "mcpServers": {',
        '    "ghl": {',
        '      "type": "http",',
        '      "url": "https://mcp.example.com/ghl",',
        '      "headers": { "Authorization": "Bearer ${GHL_ACME_TOKEN}" }',
        '    },',
        '    "files": {',
        '      "command": "npx",',
        '      "args": ["-y", "@modelcontextprotocol/server-filesystem", "./data"]',
        '    }',
        '  }',
        '}',
      ),
    }],
    sources: [S.mcp],
  },

  // ---------------- settings, permissions, hooks ----------------
  p_lib_settings: {
    examples: [{
      title: 'Permissions + one hook in one file', file: '.claude/settings.json',
      why: 'Allow the safe stuff, ask before risky stuff, deny what must never happen; the hook formats every edited file.',
      code: L(
        '{',
        '  "permissions": {',
        '    "allow": ["Bash(npm run test *)"],',
        '    "ask": ["Bash(git push *)", "mcp__ghl__send_sms"],',
        '    "deny": ["Bash(rm -rf *)", "Read(./.env)", "mcp__ghl__delete_contact"]',
        '  },',
        '  "hooks": {',
        '    "PostToolUse": [',
        '      { "matcher": "Edit|Write",',
        '        "hooks": [{ "type": "command",',
        '          "command": "jq -r \'.tool_input.file_path\' | xargs npx prettier --write" }] }',
        '    ]',
        '  }',
        '}',
      ),
    }],
    sources: [S.perm, S.hooks],
  },
  p_g1: {
    plain: [
      'A hook is a small script that runs automatically at a moment you pick (before a tool, after an edit, when Claude needs you).',
      'You list it in .claude/settings.json.',
      'Before a tool runs, the script gets the call as JSON. Exit code 2 = block it, and your message goes back to Claude.',
      'Exit 0 = no opinion; the normal permission check continues.',
    ],
    pictures: [{
      kind: 'flow', title: 'Where hooks sit in one tool call',
      steps: [
        { label: 'Claude wants to run a tool' },
        { label: 'PreToolUse hooks', note: 'your scripts can block it (exit 2)' },
        { label: 'Permission rules', note: 'deny, then ask, then allow' },
        { label: 'Ask you', note: 'only if a rule says ask' },
        { label: 'Tool runs' },
        { label: 'PostToolUse hooks', note: 'format, log, notify' },
      ],
    }],
    examples: [
      {
        title: 'Block a dangerous command', tone: 'good', file: '.claude/hooks/block-drop.sh',
        why: 'From Anthropic\'s guide. stderr becomes Claude\'s feedback; exit 2 stops the call.',
        code: L(
          '#!/bin/bash',
          'INPUT=$(cat)',
          'COMMAND=$(echo "$INPUT" | jq -r \'.tool_input.command\')',
          'if echo "$COMMAND" | grep -q "drop table"; then',
          '  echo "Blocked: dropping tables is not allowed" >&2',
          '  exit 2',
          'fi',
          'exit 0',
        ),
      },
      {
        title: 'Hold every client text for approval', tone: 'good', file: '.claude/settings.json',
        why: 'Our example for your business: any SMS tool on the GHL server goes through your check script first.',
        code: L(
          '{ "hooks": { "PreToolUse": [',
          '  { "matcher": "mcp__ghl__.*sms.*",',
          '    "hooks": [{ "type": "command", "command": ".claude/hooks/needs-approval.sh" }] }',
          '] } }',
        ),
      },
      {
        title: 'Format after every edit', file: '.claude/settings.json',
        why: 'Runs every time, so you never rely on Claude remembering.',
        code: L(
          '{ "hooks": { "PostToolUse": [',
          '  { "matcher": "Edit|Write",',
          '    "hooks": [{ "type": "command", "command": "jq -r \'.tool_input.file_path\' | xargs npx prettier --write" }] }',
          '] } }',
        ),
      },
      {
        title: 'Log every shell command', file: '.claude/settings.json',
        why: 'A cheap audit log.',
        code: L(
          '{ "hooks": { "PostToolUse": [',
          '  { "matcher": "Bash",',
          '    "hooks": [{ "type": "command", "command": "jq -r \'.tool_input.command\' >> ~/.claude/command-log.txt" }] }',
          '] } }',
        ),
      },
      {
        title: 'Ping you when Claude is waiting (Mac)', file: '~/.claude/settings.json',
        why: 'No matcher = fires on every notification.',
        code: L(
          '{ "hooks": { "Notification": [',
          '  { "matcher": "",',
          '    "hooks": [{ "type": "command", "command": "osascript -e \'display notification \\"Claude needs you\\" with title \\"Claude Code\\"\'" }] }',
          '] } }',
        ),
      },
    ],
    decide: [
      { if: 'It must happen every single time', then: 'Hook' },
      { if: 'It must never happen', then: 'Deny rule; add a hook if the check needs logic' },
      { if: 'It needs judgment', then: 'CLAUDE.md or a skill' },
    ],
    sources: [S.hooks, S.perm, S.steer],
  },
  p_g2: {
    examples: [{
      title: 'Allow, ask, deny', file: '.claude/settings.json',
      why: 'Checked deny first, then ask, then allow. A deny always wins.',
      code: L(
        '{',
        '  "permissions": {',
        '    "allow": ["Bash(npm run test *)", "Read(./website/**)"],',
        '    "ask": ["Bash(git push *)", "mcp__ghl__send_sms"],',
        '    "deny": ["Bash(rm -rf *)", "Read(./.env)", "mcp__ghl__delete_contact"]',
        '  }',
        '}',
      ),
    }],
    sources: [S.perm],
  },

  // ---------------- MCP server ----------------
  p_t1: {
    plain: [
      'An MCP server is a translator between an AI and an app like GHL. The AI says "find contact Joe"; the server makes the GHL API call and hands back a short answer.',
      'Local server: runs on your laptop. Only AI apps on that laptop can use it. Laptop off = gone.',
      'Remote server: runs on the internet at a web address (https://...). Any agent anywhere can use it: Claude on your phone, a cloud agent, ChatGPT, Cursor. It has a login so only approved agents get in.',
      '"Production systems" just means the real apps your business runs on (GHL, Stripe, Google Ads), not test copies.',
      'Composio is a company that runs remote servers for you. Building your own means you host it somewhere, for example Cloudflare.',
    ],
    pictures: [
      { kind: 'flow', title: 'Remote: works from anywhere', steps: [
        { label: 'Any agent', many: ['Claude on phone', 'Cloud agent', 'Cursor', 'ChatGPT'] },
        { label: 'Remote MCP server', note: 'https://... with a login', tone: 'good' },
        { label: 'GHL API' },
        { label: 'Client sub-account' },
      ] },
      { kind: 'flow', title: 'Local: this laptop only', steps: [
        { label: 'Claude Code on your laptop' },
        { label: 'Local MCP server', note: 'a program on the same laptop', tone: 'neutral' },
        { label: 'The app' },
      ] },
    ],
    examples: [{
      title: 'Build your own remote server (Cloudflare example)', file: 'steps',
      why: 'Hosting example from Cloudflare\'s docs, not Anthropic. Anthropic\'s part: build it remote, few tools grouped by job, standard login.',
      code: L(
        '1. Start from Cloudflare\'s remote MCP server template (Workers).',
        '2. Add a few job-sized tools: find_lead, book_appointment, weekly_numbers.',
        '   Each one calls the GHL API inside.',
        '3. Turn on login (OAuth) so only approved agents connect.',
        '4. Deploy. You get a URL like https://ghl-mcp.yourco.workers.dev/mcp',
        '5. Add that URL to .mcp.json (type http) or as a connector in Claude.',
      ),
    }],
    decide: [
      { if: 'Only you, only on this laptop', then: 'Local is fine' },
      { if: 'Phone, cloud agents, teammates or other AI apps need it', then: 'Remote' },
      { if: 'It touches client accounts', then: 'Remote, with a separate login or token per client' },
    ],
    sources: [S.mcpProd, S.mcp, S.cloudflare],
  },

  // ---------------- API vs CLI vs MCP ----------------
  p_t4: {
    decide: [
      { if: 'One agent AND one app AND a one-off job', then: 'Direct API call in a script' },
      { if: 'It runs on your computer or a container AND a good CLI exists (gh, wrangler, gcloud)', then: 'CLI' },
      { if: 'Agents in different places OR other people\'s agents need it', then: 'Remote MCP server' },
      { if: 'The agent has to sift lots of data (rows, logs)', then: 'Code execution: the agent writes code that calls the tools and returns only the summary' },
      { if: 'It is your own function that only your agent app uses', then: 'Agent SDK custom tool (in-process)' },
      { if: '10 or more tools', then: 'Turn on tool search' },
      { if: 'You serve many clients or apps', then: 'All three: API as the base, CLI for local, MCP for cloud agents' },
      { if: 'Always, whichever path', then: 'Add a skill that says when and how to use it' },
    ],
    pictures: [{
      kind: 'tree', title: 'How mature integrations are built', caption: 'The API is the base; CLI and MCP sit on top of it.',
      root: { label: 'Your API', tone: 'good', children: [
        { label: 'CLI', note: 'local computers, containers' },
        { label: 'Remote MCP server', note: 'phone, web, cloud agents' },
        { label: 'SDK custom tools', note: 'inside your own agent app' },
      ] },
    }],
    sources: [S.mcpProd],
  },

  // ---------------- agentic search ----------------
  p_k0: {
    plain: [
      'In plain words: instead of building a search engine, the agent looks through folders itself, the way you would in Finder.',
      'Nothing to install and nothing to host. Claude Code already has the tools (Read, Grep, Glob, Bash).',
      'Step 1: put information in files with clear names in clear folders.',
      'Step 2: say in CLAUDE.md where things live ("client notes are in clients/<name>/").',
      'Step 3: the agent searches by words, opens only the files that match, and answers.',
      'Only if that gets too slow on huge data do you add vector search later.',
    ],
    pictures: [{
      kind: 'flow', title: 'What happens when you ask',
      steps: [
        { label: '"What did Acme say about stump grinding?"' },
        { label: 'Agent searches the folders', note: 'grep -ril "stump" clients/acme/' },
        { label: '3 files match', many: ['calls/2026-09-14.md', 'notes.md', 'quotes/q-118.md'] },
        { label: 'Reads only those 3' },
        { label: 'Answers with where it found it' },
      ],
    }],
    examples: [
      {
        title: 'Good: findable', tone: 'good', file: 'folders',
        why: 'Names say what is inside, so searches hit.',
        code: L('clients/acme/notes.md', 'clients/acme/calls/2026-09-14.md', 'clients/acme/quotes/q-118.md'),
      },
      {
        title: 'Bad: unfindable', tone: 'bad', file: 'folders',
        why: 'Anthropic\'s own bad example looks like this.',
        code: L('docs/file1.md', 'docs/file2.md', 'misc/new folder (3)/stuff.md'),
      },
    ],
    sources: [S.sdkBlog, S.skills],
  },

  // ---------------- lead agent ----------------
  p_lead: {
    plain: [
      'Install the Agent SDK (pip install claude-agent-sdk).',
      'Write the lead\'s job in a prompt, and list its helpers with the agents option.',
      'Allow the Agent tool so it can hand work out, and set a spend cap.',
      'Run it with query(). Host it in a container if it must run without your laptop.',
    ],
    pictures: [{
      kind: 'flow', title: 'Pros always do this, top down', caption: 'Each box is a rule from Anthropic\'s research system.',
      steps: [
        { label: 'You ask one question' },
        { label: 'Lead plans first', note: 'how hard? which tools? how many helpers?' },
        { label: 'Saves the plan to memory', note: 'survives a full context window' },
        { label: 'Hands out 3 to 5 tasks at once', many: ['Goal', 'Output format', 'Tools + sources', 'When to stop'] },
        { label: 'Helpers search in parallel', many: ['Helper 1', 'Helper 2', 'Helper 3'] },
        { label: 'Summaries come back', note: 'not their full notes' },
        { label: 'Lead combines; more needed?', note: 'if yes, send more helpers' },
        { label: 'Citation check', note: 'every claim matched to a source' },
        { label: 'Answer to you' },
      ],
    }],
    examples: [{
      title: 'Lead agent with one helper (Python)', file: 'agent.py',
      why: 'Same shape as the SDK docs. The helper\'s description tells the lead when to use it.',
      code: L(
        'from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition',
        '',
        'options = ClaudeAgentOptions(',
        '    allowed_tools=["Read", "Grep", "Glob", "Agent"],',
        '    agents={',
        '        "researcher": AgentDefinition(',
        '            description="Web research. Use when a question needs current facts with sources.",',
        '            prompt="Research one question. Start broad, then narrow. Return findings with links.",',
        '            tools=["WebSearch", "WebFetch", "Read"],',
        '        ),',
        '    },',
        '    max_budget_usd=2.00,',
        ')',
        '',
        'async for message in query(prompt="Compare 3 CRMs for tree services", options=options):',
        '    print(message)',
      ),
    }],
    sources: [S.sdkSub, S.research],
  },

  // ---------------- research helper ----------------
  p_a1: {
    examples: [
      {
        title: 'The helper as a file', tone: 'good', file: '.claude/agents/researcher.md',
        why: 'Name and description load at start; the rest is its own instructions. Tools limited to what research needs.',
        code: L(
          '---',
          'name: researcher',
          'description: Web research specialist. Use when a question needs current facts',
          '  from the web with sources.',
          'tools: WebSearch, WebFetch, Read',
          'model: sonnet',
          '---',
          'Research one question and return findings with links.',
          '- Start with 2 or 3 short, broad searches, then narrow.',
          '- Run searches at the same time when they do not depend on each other.',
          '- Prefer primary sources (official docs, the company\'s own site).',
          '- Return 5 to 10 findings, each with its URL, then what you could not find.',
        ),
      },
      {
        title: 'Good handoff from the lead', tone: 'good', file: 'what the lead sends',
        why: 'Goal, format, sources, stop point: the four things Anthropic says every handoff needs.',
        code: L(
          'Goal: find the 3 most used CRMs by US tree service companies in 2026.',
          'Format: table with name, price per month, GHL-like features, source URL.',
          'Sources: vendor sites and industry surveys; skip forums.',
          'Stop: after 15 tool calls or when you have 3 solid answers.',
        ),
      },
      {
        title: 'Bad handoff', tone: 'bad', file: 'what the lead sends',
        why: 'Too vague: helpers repeat each other and leave gaps.',
        code: 'research CRMs',
      },
    ],
    sources: [S.sub, S.research],
  },

  // ---------------- plan saved ----------------
  p_plan1: {
    plain: [
      'It writes the plan to a file outside its own head, then reads it back when needed.',
      'Claude API: the memory tool gives Claude a /memories folder it can create, read and edit files in; you choose where that folder really lives.',
      'Claude Code or Agent SDK: a normal file in the project (a plan or progress file), committed to git.',
      'Managed Agents: hosted memory stores.',
      'Anthropic does not publish the exact code its research system uses; the pattern is write it down, read it back.',
    ],
    sources: [S.research, S.harness],
  },

};
