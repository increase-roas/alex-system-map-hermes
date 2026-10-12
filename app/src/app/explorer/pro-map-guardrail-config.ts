/** Copyable registration snippets. Nothing here is installed or executed by the map. */
const asset = (event: string) => ({ type: 'command', command: `python3 -B "\${CLAUDE_PROJECT_DIR}/.claude/hooks/asset_guard.py" --root "\${CLAUDE_PROJECT_DIR}" --event ${event}`, timeout: 30, ...(event === 'Stop' ? {} : { onFailure: 'block' }) });
const read = { type: 'command', command: 'python3 -B "${CLAUDE_PROJECT_DIR}/.claude/hooks/read_gate.py" --project "${CLAUDE_PROJECT_DIR}" --policy "${CLAUDE_PROJECT_DIR}/.claude/guard-policy.json" --state-dir "${READ_GATE_STATE_DIR:?Set a private runtime-owned state directory}"', timeout: 10, onFailure: 'block' };
export const CLAUDE_GUARD_SETTINGS = JSON.stringify({hooks: {
  PreToolUse: [{matcher: '^(Write|Edit)$', hooks: [asset('PreToolUse')]}, {matcher: '^(Read|mcp__.*)$', hooks: [read]}],
  PostToolUse: [{matcher: '^Read$', hooks: [read]}, {hooks: [asset('PostToolUse')]}],
  PostToolUseFailure: [{matcher: '^Read$', hooks: [read]}],
  PermissionDenied: [{matcher: '^Read$', hooks: [read]}],
  Stop: [{hooks: [asset('Stop')]}],
}}, null, 2);
export const READ_GATE_POLICY = JSON.stringify({version: 1, project_root: '${CLAUDE_PROJECT_DIR}',
  servers: {ghl: ['/absolute/path/to/project/.claude/connector-cards/ghl.md'],
    composio: ['/absolute/path/to/project/.claude/connector-cards/composio.md']},
  direct_tools: ['mcp__ghl__contacts_list'],
  batches: {'mcp__composio__COMPOSIO_MULTI_EXECUTE_TOOL': {
    actions_key: 'tools', action_name_key: 'tool_slug', arguments_key: 'arguments', optional_fields: {session_id: 'string'},
    actions: {GHL_LIST_CONTACTS: ['/absolute/path/to/project/.claude/connector-cards/ghl.md']},
  }},
}, null, 2);
const hermesCommand = 'python3 -B "/absolute/path/to/profile/agent-hooks/hermes_guard.py" --policy "/absolute/path/to/profile/guard-policy.json"';
export const HERMES_GUARD_SETTINGS = JSON.stringify({hooks: {
  pre_tool_call: [{command: hermesCommand, timeout: 10, fail_closed: true}],
  post_tool_call: [{command: hermesCommand, timeout: 10}],
  pre_verify: [{command: hermesCommand, timeout: 10}],
}}, null, 2);
export const HERMES_GUARD_POLICY = JSON.stringify({
  home: '/absolute/path/to/profile', profile: 'default', cards_dir: '/absolute/path/to/profile/connector-cards',
  state_dir: '/absolute/path/to/private-runtime-state',
  routes: {mcp__github__get_issue: {server: 'github', card: 'github.md'}},
}, null, 2);
