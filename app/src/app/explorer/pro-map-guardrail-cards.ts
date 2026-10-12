/** Offline-tested reference hooks, NOT installed guardrails. Only p_/h_ change. */
import type { ProNode } from './pro-map-data';
import type { Example } from './pro-map-examples';
import { GUARD_CODE } from './pro-map-guardrail-code';
import { CLAUDE_GUARD_SETTINGS, READ_GATE_POLICY, HERMES_GUARD_SETTINGS, HERMES_GUARD_POLICY } from './pro-map-guardrail-config';

const CC = 'https://code.claude.com/docs/en/';
const HH = 'https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks';
const BEST = 'https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices';
const ex = (title: string, file: string, why: string, code: string): Example => ({ title, file, why, code, tone: 'good' });
const assetScript = ex('Tested setup checker', '.claude/hooks/asset_guard.py', 'Full custom Python script, not installed by this map. Python 3; no jq. Save the exact file before registering it.', GUARD_CODE['asset_guard.py']);
const settings = ex('Register the guardrails', '.claude/settings.json', 'Merge hooks into your existing settings, do not replace other settings. Requires supported onFailure:block behavior (2.1.295+). Save BOTH Python scripts and the policy below; register/review hooks before testing.', CLAUDE_GUARD_SETTINGS);
const gateScript = ex('Tested read-first gate', '.claude/hooks/read_gate.py', 'Only successful full Read earns a session marker. Missing, stale, partial or failed reads do not. Policy and state must be protected from the agent for tamper resistance.', GUARD_CODE['read_gate.py']);
const policy = ex('Exact connector routes', '.claude/guard-policy.json', 'Example route names, not a live Composio schema claim. Match /mcp names and the actual tool input schema. Unknown routes are blocked; add every action deliberately.', READ_GATE_POLICY);
const setupLimits = [
  'Custom agency checks using built-in hooks. The stricter writing rules here are Alex policy, not automatic Anthropic validation.',
  'Before Write/Edit: validate the proposed file. After tools and before stopping: rescan disk. The after-check can ask for repair, not undo a write. Bash, external editors and other file-writing tools do not get the same pre-write check.',
  'Before use: replace every /absolute/path placeholder, create each non-empty connector card, and export READ_GATE_STATE_DIR pointing at an existing private 0700 directory outside the project. The hook process must own it.',
  'Protect the hook commands, scripts, policy and state outside agent-writable access for real enforcement. Restrict unguarded shell/API routes separately. Project hooks alone are not a tamper-proof security boundary.',
  'Use a dedicated runtime state directory for a supervised job. Retain it while any related session is active; archive/retire it only after closure. Shared long-lived state needs cleanup planning, and full scans need latency measurement.',
  'Stop can request repair only within runtime limits. A forced/interrupted stop is not a passing check. Have the supervisor run the scan again before accepting completion.',
];
const readSteps = [
  '1. Before every covered connector call, look up its card. Missing card: BLOCK. Unknown route or unknown batch action: BLOCK.',
  '2. Read the complete card with Read. A pre-read snapshot and a successful PostToolUse result must agree before the gate records it.',
  '3. Retry the call. It is allowed past THIS gate only if every action has a current read marker for this session, project, policy and card contents.',
  '4. Repeated attempts alone never unlock the gate. Another session or an edited card must read again. The first successful read stays valid until the session, card or policy changes. It proves delivery, not comprehension or permission to send/spend.',
  '5. Check accounts, client scope and approvals separately. Only explicitly configured direct MCP and batch routes are supported; arbitrary code and shell wrappers need their own restriction.',
];
const testCommand = ex('Run the offline guard tests', 'Terminal, from app/', 'Harmless sample payloads; no model or connector calls. These tests exercise scripts, not an installed Claude or Hermes session.', 'python3 -B src/app/explorer/pro-map-guardrails/test_asset_guard.py\npython3 -B src/app/explorer/pro-map-guardrails/test_read_gate.py\npython3 -B src/app/explorer/pro-map-guardrails/test_hermes_guard.py\npython3 -B src/app/explorer/pro-map-guardrails/bundle.py --check');

export function withGuardrails(n: ProNode): ProNode {
  if (n.id === 'p_rulegate') return {
    ...n, label: 'Read card, then call', sub: 'Custom gate: every batch action', badge: 'Blocks',
    why: 'A real before-call gate: no successful full card read means no covered connector call. Tested sample inputs, not installed state.',
    sources: [CC + 'hooks', CC + 'mcp', CC + 'permissions'], how: undefined,
    detail: { plain: [...readSteps, ...setupLimits], examples: [settings, policy, gateScript, assetScript, testCommand] },
  };
  const setup: Record<string, { label: string; sub: string; plain: string[]; src: string[] }> = {
    p_lib_skills: { label: 'Skills + setup check', sub: 'Custom: rejects bad skill files', src: [CC + 'skills', BEST], plain: [
      'Check .claude/skills/<name>/SKILL.md: frontmatter name at most 64 characters, folder equals name, description says what it does plus Use when, body at most 500 lines, references only one link deep.',
      'The exact Use when wording and hard 500-line cutoff are custom policy. Checking a description is not proof it is useful: try the skill on a representative job too.',
    ] },
    p_lib_mcp: { label: 'Connectors + setup check', sub: 'Custom: config and card required', src: [CC + 'mcp'], plain: [
      'Check each named .mcp.json server: supported transport, required fields, environment placeholders for credentials, and a non-empty .claude/connector-cards/<server>.md.',
      'A strict allowed format can reject inline credentials in covered fields, not detect every possible secret hidden in arbitrary text. Defining a server does not prove its token has the right client access.',
      'Create the card first, then add the connector. Set environment values outside git; never paste real keys into this template. Test the actual /mcp connection separately.',
    ] },
    p_lib_settings: { label: 'Settings + setup check', sub: 'Custom: checks JSON and hook shape', src: [CC + 'settings', CC + 'hooks'], plain: [
      'Validate JSON and the supported hook-entry shape before saving. This is a focused checker, not a full validator for every current or future Claude setting.',
      'Review the loaded configuration through /hooks after an external edit or start a new session. A valid file is not evidence its hook is running.',
    ] },
    p_ptr4: { label: 'Rules + setup check', sub: 'Custom: explicit scope required', src: [CC + 'memory'], plain: [
      'Require paths for file-scoped rules, or scope: global for an intentionally global rule. scope: global is our checker convention; Claude ignores that field and reads rules without paths globally.',
      'The same checker requires explicit name, description and tools in .claude/agents/*.md. Anthropic permits omitted tools; requiring an explicit list is our narrower policy.',
    ] },
  };
  if (setup[n.id]) {
    const c = setup[n.id];
    return { ...n, label: c.label, sub: c.sub, badge: 'Checks edits', sources: [...new Set([...n.sources, ...c.src, CC + 'hooks'])],
      detail: { ...n.detail, plain: [...c.plain, ...setupLimits, ...(n.detail?.plain ?? [])], examples: [...(n.detail?.examples ?? []), settings, assetScript, gateScript, policy, testCommand] } };
  }
  if (n.id === 'p_x2') return { ...n, label: 'Guards keep checking', sub: 'Custom: setup, calls, finish', why: 'Custom setup checks, read-first call gate and final checks. Protect their configuration and cover every permitted route.',
    detail: { ...n.detail, plain: [...setupLimits, ...(n.detail?.plain ?? [])] } };
  if (n.id === 'h_rulegate') return {
    ...n, label: 'Read card, then call', sub: 'Custom: restricted tested gate', badge: 'Blocks',
    why: 'Custom Hermes shell-hook adapter checks supported connector calls and native setup files. Tested offline; not installed in Javar.',
    sources: [HH, 'https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp', 'https://hermes-agent.nousresearch.com/docs/user-guide/features/skills'],
    detail: { plain: [
      'Hermes has different event names and native files. This is a separate script, not a Claude settings file copied into Hermes.',
      'Register and consent to every event/command in the active profile. Use per-job state and retire it only after all related sessions close. Unapproved unattended shell hooks can be skipped; fail_closed is useful only once registered.',
      'Successful full read_file results are checked before a session/card marker is recorded. Unknown routes and unsupported aggregate execution are blocked rather than silently checking only the first action.',
      'This restricted adapter allows local read_file, checked write_file for native skill/config assets, and exact connector routes. It blocks terminal, execute_code, patch, skill_manage, delegation and aggregate calls. It is NOT a drop-in policy for the whole Hermes map; extend and test those routes before normal agency use.',
      'Python standard-library mode accepts JSON-formatted YAML. General YAML needs PyYAML in the exact Python interpreter that runs the hook. No dependency is installed by this map.',
      'Native skills and the selected profile config are scanned. Claude rules paths and .claude/agents/*.md are not native Hermes configuration; their checks are not claimed here.',
      'A final pre_verify request is bounded and only runs for qualifying edited-code turns. It is not an always-on completion guarantee. Run the scan at the covered tool boundary too; protect policy and state.',
      'Client/account authorization and send/spend approval are separate. These fixtures prove the displayed script decisions, not live installation or every Hermes execution route.',
    ], examples: [
      ex('Register Hermes guardrails', '$HERMES_HOME/config.yaml', 'JSON is valid YAML. Replace every absolute path with the selected profile and private state paths, save the script/policy, and approve each hook interactively. This template does not install anything.', HERMES_GUARD_SETTINGS),
      ex('Hermes connector policy', '$HERMES_HOME/guard-policy.json', 'Replace the example route with the exact Hermes tool name; this is not a shipped GitHub tool guarantee. Paths and server configuration belong to this active profile, not the default profile by accident.', HERMES_GUARD_POLICY),
      ex('Tested Hermes guard script', '$HERMES_HOME/agent-hooks/hermes_guard.py', 'Complete custom adapter. Dependencies and supported formats are documented in the script; not a built-in feature.', GUARD_CODE['hermes_guard.py']), testCommand,
    ] },
  };
  if (['h_lib_skills', 'h_lib_config'].includes(n.id)) return {
    ...n, sub: 'Built-in files; custom checks', badge: 'See read-first gate',
    detail: { ...n.detail, plain: ['The Read card, then call card contains the tested custom setup checker and hook registration. It scans supported native Hermes files; it is not installed by displaying this map.', ...(n.detail?.plain ?? [])] },
  };
  return n;
}

export const GUARD_STICKY = [
  { ids: ['p_rulegate', 'p_lib_skills', 'p_lib_mcp', 'p_lib_settings', 'p_ptr4'], title: settings.title, text: 'Save both scripts and policy first. Merge hook arrays instead of replacing existing guards; protect those files, verify hooks are loaded and run the offline tests before a real job.', src: CC + 'hooks' },
  { ids: ['p_rulegate', 'p_lib_skills', 'p_lib_mcp', 'p_lib_settings', 'p_ptr4'], title: policy.title, text: 'Replace absolute card paths and the example action name with your verified tool names and full batch schema. Export READ_GATE_STATE_DIR before starting Claude. Unknown actions block by design; a retry is never proof the card was read.', src: CC + 'mcp' },
  { ids: ['h_rulegate'], title: 'Register Hermes guardrails', text: 'Consent is required for each event and command. Verify registration in the active profile; unapproved headless hooks may be skipped even with fail_closed.', src: HH },
];
