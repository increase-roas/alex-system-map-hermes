/** V2 audit, 2026-10-12. Applied AFTER inherited details; V1 and y_ remain unchanged.
 * These are reference examples, not installed hooks or observed live deployments.
 */
import type { FullDetail, ProNode } from './pro-map-data';
import type { Example } from './pro-map-examples';

const D = 'https://code.claude.com/docs/en/';
const S = {
  hooks: D + 'hooks', memory: D + 'memory', permissions: D + 'permissions',
  sub: D + 'sub-agents', mcp: D + 'mcp', monitor: D + 'monitoring-usage',
  checkpoint: D + 'checkpointing', skills: D + 'skills', costs: D + 'costs',
  sdkPermissions: D + 'agent-sdk/permissions', python: D + 'agent-sdk/python',
  sessions: D + 'agent-sdk/sessions', sdkSub: D + 'agent-sdk/subagents',
  system: D + 'agent-sdk/modifying-system-prompts',
  harness: 'https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents',
  evals: 'https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents',
  vault: 'https://platform.claude.com/docs/en/managed-agents/vaults',
  webhooks: 'https://platform.claude.com/docs/en/managed-agents/webhooks',
  managed: 'https://platform.claude.com/docs/en/managed-agents/multiagent-orchestration',
  dreaming: 'https://claude.com/blog/new-in-claude-managed-agents',
};
type Correction = Pick<ProNode, 'sub' | 'why' | 'sources'> & {
  label?: string; badge?: string; detail: FullDetail;
};
const example = (title: string, file: string, why: string, code: string): Example => ({ title, file, why, code, tone: 'good' });
const detail = (plain: string[], examples?: Example[]): FullDetail => ({ plain, examples });

const budget = 'max_budget_usd stops on a client-side cost estimate. It can exceed the threshold; leave headroom. It is not a hard billing ceiling.';
const mods = 'Claude Code mods with tool.check can replace ask decisions and non-managed hook blocks. Deny protection depends on managed controls and Team/Enterprise policy; elsewhere a mod can override a deny. Audit installed mods and organization policy (2.1.292+).';
const permissionOrder = 'SDK order: hooks, deny rules, ask rules, permission mode, allow rules, then canUseTool (Python: can_use_tool) for unresolved approval. Ask rules route to the callback; dontAsk denies instead. The host must implement its own approval UI.';
const baseline = 'Resumed job: read progress and recent git history, inspect git status/diff and actual files, then run the existing smoke test BEFORE new work. Record baseline failure as BLOCKED; do not overwrite unrelated edits.';
const terminal = 'Approval pending: wait without executing. Denied: report BLOCKED, do not bypass. Tool/check failed: repair within approved scope and recheck. Budget/turn/retry cap or interruption: preserve state, reconcile uncertain writes, report BLOCKED with the unmet check; stopping is not passing.';
const limits = [
  'CLAUDE.md under 200 lines and SKILL.md under 500 lines are recommendations, not parser-enforced limits.',
  'Auto-memory startup reads only the first 200 lines or 25 KB of MEMORY.md; topic files are read on demand. This is a loading cutoff, unlike the writing recommendations.',
  'Use short indexes and linked references. Our archive/working-set layout is custom, not a product-enforced file cap.',
];
const trace = [
  'OpenTelemetry is optional. prompt.id correlates ONE prompt and its events until the next prompt; session.id spans the conversation. Keep both plus timestamps and tool-use IDs.',
  'Trace is diagnosis, not full replay: prompts/tool details may be redacted, outputs or exporter payloads may be truncated, and delivery/retention can leave gaps. Check your collector configuration and saved transcript.',
  'A received-webhook log proves only events received. It cannot recover a webhook that never arrived. Reconcile against the authoritative session/event API when available; otherwise mark missing evidence.',
  'A custom receipt writer must redact secrets, record check commands/exit codes and final file hashes, and join them to the session/prompt. Built-in telemetry does not create this evidence package.',
];

/** Syntax-complete, read-only SDK example. No paid request is run by this map. */
const sdkCode = `import asyncio
from pathlib import Path
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

async def main():
    options = ClaudeAgentOptions(
        cwd=str(Path.cwd()),
        setting_sources=["project"],
        system_prompt={"type": "preset", "preset": "claude_code",
                       "append": "Read project instructions before decisions. Stay read-only. Report unmet checks as BLOCKED."},
        tools=["Read", "Glob", "Grep", "Agent"],
        allowed_tools=["Read", "Glob", "Grep", "Agent"],
        disallowed_tools=["Bash", "Edit", "Write", "mcp__*"],
        agents={"researcher": AgentDefinition(
            description="Read-only research when an independent lookup helps",
            prompt="Read the assigned files. Return findings with paths and limits. Do not edit.",
            tools=["Read", "Glob", "Grep"], model="haiku")},
        max_turns=8,
        max_budget_usd=2.00,  # Estimate threshold, can exceed; NOT a billing ceiling.
    )
    async for message in query(prompt="Read CLAUDE.md and summarize this project. Use a helper only if needed.", options=options):
        if hasattr(message, "result"):
            print({"result": message.result,
                   "is_error": getattr(message, "is_error", None),
                   "subtype": getattr(message, "subtype", None),
                   "terminal_reason": getattr(message, "terminal_reason", None),
                   "estimated_cost_usd": getattr(message, "total_cost_usd", None)})
            # A success subtype alone is not proof. Inspect terminal_reason and verify acceptance.

if __name__ == "__main__":
    asyncio.run(main())`;
const sdkExample = example('Lead agent with one optional helper (Python)', 'agent.py',
  'Custom read-only host. Requires claude-agent-sdk and configured authentication. Running it makes paid API requests; the map does not run it.', sdkCode);

/** Pure helper used by the illustrated Stop hook, kept exportable for offline failure checks. */
export const V2_FINISH_CHECK_PY = `#!/usr/bin/env python3
import json, os, subprocess, sys, uuid
from datetime import datetime, timezone
from pathlib import Path

def receipt_matches(path, expected):
    try:
        saved = json.loads(path.read_text())
        return all(saved.get(key) == expected[key] for key in
                   ("run_id", "session_id", "checked_at", "command", "status", "exit_code"))
    except (OSError, ValueError, AttributeError, KeyError):
        return False

def main():
    payload, target, active = {}, None, False
    receipt = {"status": "BLOCKED", "run_id": uuid.uuid4().hex,
               "session_id": None, "checked_at": datetime.now(timezone.utc).isoformat(),
               "command": os.environ.get("FINISH_CHECK", "npm test"), "exit_code": "not_run"}
    reason = "Check did not run."
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("Hook input must be an object")
        active = payload.get("stop_hook_active") is True
        if not isinstance(payload.get("session_id"), str) or not payload["session_id"]:
            raise ValueError("Missing session identity")
        receipt["session_id"] = payload["session_id"]
        root_value = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd")
        if not isinstance(root_value, str) or not root_value:
            raise ValueError("Missing project path")
        root = Path(root_value).resolve()
        target = root / "work" / "finish-status.json"
        # FINISH_CHECK is trusted setup, never text copied from a customer.
        result = subprocess.run(receipt["command"], shell=True, cwd=root,
                                capture_output=True, text=True, timeout=60)
        receipt["exit_code"] = result.returncode
        receipt["status"] = "PASS" if result.returncode == 0 else "BLOCKED"
        reason = "Check passed." if result.returncode == 0 else "Acceptance check failed."
    except subprocess.TimeoutExpired:
        receipt["exit_code"], reason = "timeout", "Check timed out; outcome is not PASS."
    except (OSError, ValueError, TypeError) as error:
        reason = "Check infrastructure failed: " + type(error).__name__
    receipt["reason"] = reason
    stored = False
    if target is not None:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name("finish-status." + receipt["run_id"] + ".tmp")
            temporary.write_text(json.dumps(receipt) + "\\n")
            temporary.replace(target)
            stored = receipt_matches(target, receipt)
        except (OSError, ValueError, TypeError):
            stored = False
    if not stored:
        receipt["status"] = "BLOCKED"
        reason += " No verified current receipt. Reject any older PASS file."
    summary = receipt["status"] + ": " + reason + " Run " + receipt["run_id"]
    # systemMessage is a user notification, NOT a forced final model answer.
    if receipt["status"] == "PASS" or active:
        print(json.dumps({"systemMessage": summary + " Supervisor must verify this run receipt."}))
    else:
        print(json.dumps({"decision": "block", "reason": summary +
                          " Repair within scope, then rerun. Missing/stale proof is BLOCKED."}))

if __name__ == "__main__":
    main()
`;
const stopSettings = JSON.stringify({ hooks: { Stop: [{ hooks: [{ type: 'command', command: 'python3 "${CLAUDE_PROJECT_DIR}/.claude/hooks/finish-line.py"', timeout: 70 }] }] } }, null, 2);
const stopExamples = [
  example('Project-wide finish line', '.claude/settings.json', 'Custom Stop hook. The test command must already exist and pass when the work is correct.', stopSettings),
  example('The check', '.claude/hooks/finish-line.py', 'Runs the real check even at the repeat cap. An exit that allows stopping is not PASS. When storage works the current receipt records failure; otherwise the warning rejects missing or stale proof. Supervisor review is required.', V2_FINISH_CHECK_PY),
];


const corrections: Record<string, Correction> = {};
function put(ids: string[], sub: string, why: string, sources: string[], d: FullDetail, label?: string) {
  for (const id of ids) corrections[id] = { sub, why, sources, detail: d, ...(label ? { label } : {}) };
}

put(['p_you'], 'One goal, scope and check; no success guarantee',
  'Give the agent the outcome, account/file boundary and a real check. A goal instruction cannot guarantee the check will pass.', [S.harness, S.hooks], detail([
    'Say what done looks like, what may be touched, who may approve consequential actions, and which existing command/readback proves the result.',
    'If a test, approval, budget or interruption blocks completion, require a BLOCKED report with exact unmet acceptance instead of a success claim.',
  ], [example('A bounded request', 'In the chat', 'Illustrative task prompt with a real finish condition and honest terminal state.', 'Goal: correct this project report in the approved files only.\nDone means: run the existing smoke check and cite final file/readback evidence.\nIf approval, failure or a budget limit prevents completion: report BLOCKED with the missing check.')]));

put(['p_l1', 'p_l2', 'p_lib_mcp'], 'Built-in: project config, not isolation',
  'A project .mcp.json selects project servers; it does not remove local/user, managed or plugin-provided servers or restrict a credential to one client.', [S.mcp, S.permissions], detail([
    'Local and user MCP definitions also exist. Inspect /mcp, managed server policy and active plugins before using client tools.',
    'A local server can use network credentials to reach production. Location of its process is not an account boundary.',
    'Custom client boundary: verify account/location and credential permissions, tool allowlists and environment restrictions. A per-client folder or token name alone proves none of these.',
  ], [example('One remote server, one local server', '.mcp.json', 'Illustrative project servers only. Replace the URL and configure environment credentials; approve and verify /mcp.',
    JSON.stringify({mcpServers: {crm: {type: 'http', url: 'https://mcp.example.com/mcp', headers: {Authorization: 'Bearer ${GHL_ACME_TOKEN}'}}, local: {command: 'python3', args: ['./tools/local_mcp.py']}}}, null, 2))]));

put(['p_g5'], 'Managed Agents only: vault selection',
  'Vaults control credential availability and inject credentials without showing secret values to the agent. They do not narrow the API permissions inside a stored token.', [S.vault], detail([
    'Managed Agents only. Selecting a client vault is not proof that its GHL token can access only that client.',
    'Check the token scope and API account separately; use least-privileged credentials and verify the target before mutations.',
  ]), 'Vault credentials');
put(['p_goal', 'p_check'], 'Built-in /goal; custom check and caps',
  'A finish condition guides continued work, not a promise of success. Recheck before a cap exit; failed or unrun acceptance remains BLOCKED.', [S.hooks, S.python], detail([
    '/goal is real: a session-scoped prompt-based Stop hook. A model judgment is not a substitute for test output.',
    'Custom Stop checks can request another attempt. Retry, turn, budget and interrupt limits can end work before acceptance passes.', terminal,
    'The sample rechecks even at the repeat cap. A capped failure only notifies the user; it cannot force the model to revise its final answer. A supervisor must match the latest run ID, session, time, command and outcome; missing or stale receipts are BLOCKED. Infrastructure/storage failures also return a BLOCKED warning, and an old PASS file is not evidence.',
  ], [example('One-off finish line', 'In the chat', 'Built-in session condition; supply real acceptance evidence.', '/goal Run the existing acceptance check. If blocked by limits or approval, report BLOCKED with the missing proof, not done.'), ...stopExamples]));

put(['p_rulegate'], 'Custom: read-first enforcement', 'Covered calls require a successful full card read; the tested implementation is attached by pro-map-guardrail-cards.', [S.hooks, S.permissions], detail(['Custom script and scope are shown on this card.']), 'Read card, then call');

put(['p_aftercheck'], 'Custom checks; built-in FileChanged available',
  'PostToolUse Edit|Write sees only successful matching tools, not Bash edits or failed calls. Current FileChanged hooks watch named files regardless of who changed them; keep a final acceptance check.', [S.hooks], detail([
    'FileChanged is supported in current docs. Its matcher seeds literal filenames, not recursive regex/glob coverage. Dynamic paths require watchPaths; a wildcard alone does not discover all project files.',
    'FileChanged has no decision control. watchPaths changes what is watched; systemMessage is a brief terminal notification, not model/SDK-stream feedback. Save a receipt and rerun the actual test at Stop for the repair loop.',
    'Use PostToolUseFailure for failed tool calls. An after-edit failure does not roll back a file or revoke an already-executed external write.',
    'This sample watches package.json only, including Bash/external edits. The quick check saves work/quick-check-status.json, not the watched file. The Stop example reruns npm test; failed-tool additionalContext reaches the model on its next request.', terminal,
    'PreToolUse is a separate before-call control for protected actions. A watcher or testing hook is not approval enforcement.',
  ], [example('Watch one file after any writer', '.claude/settings.json', 'Scoped package.json watcher saves a receipt. Failed-tool context is separate; final Stop reruns the test. Save the shown scripts; npm test must exist.', JSON.stringify({hooks: {FileChanged: [{matcher: 'package.json', hooks: [{type: 'command', command: 'python3 "${CLAUDE_PROJECT_DIR}/.claude/hooks/quick-check.py"', timeout: 70}]}], PostToolUseFailure: [{matcher: 'Edit|Write|Bash', hooks: [{type: 'command', command: 'python3 "${CLAUDE_PROJECT_DIR}/.claude/hooks/tool-failure.py"'}]}]}}, null, 2)),
    example('The check script', '.claude/hooks/quick-check.py', 'Custom watcher receipt and terminal notification only, not model feedback. No rewrite to package.json; the final Stop reruns the test.', `import json, subprocess, sys
from pathlib import Path
payload = json.load(sys.stdin)
root = Path(payload["cwd"]).resolve()
try:
    result = subprocess.run(["npm", "test"], cwd=root, capture_output=True, text=True, timeout=60)
    passed = result.returncode == 0
    code = result.returncode
except subprocess.TimeoutExpired:
    passed, code = False, "timeout"
receipt = root / "work" / "quick-check-status.json"
receipt.parent.mkdir(parents=True, exist_ok=True)
receipt.write_text(json.dumps({"status": "PASS" if passed else "BLOCKED", "command": "npm test", "exit_code": code}) + "\\n")
print(json.dumps({"systemMessage": "Scoped watcher check: " + ("PASS" if passed else "BLOCKED") + ". Final Stop must rerun acceptance."}))`),
    example('Failed tool model feedback', '.claude/hooks/tool-failure.py', 'PostToolUseFailure feedback reaches the next model request, not an already-failed call. StopFailure is a different API-error event and cannot continue the model through output.', `import json, sys
payload = json.load(sys.stdin)
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "PostToolUseFailure", "additionalContext":
    "Tool failed. Inspect current files/remote state before retry. Repair only within approved scope; rerun final acceptance. Report BLOCKED at limits."}}))`), ...stopExamples]));

put(['p_g1'], 'Custom PreToolUse: ask before a covered call',
  'PreToolUse can deny or ask before the matched call executes. This example asks for one exact direct send tool; it is not a rule-reading proof or a batch-wide policy.', [S.hooks, S.permissions], detail([
    'Register a matcher for the real tool name from /mcp. The sample does not cover another server alias, Composio batches or Bash wrappers.',
    'A hook permissionDecision ask does not execute the call. Code presents an approval prompt; an SDK host needs its own can_use_tool UI. Pending/denied approval never becomes a successful send.',
    'Test with a fake tool before relying on it. onFailure:block requires 2.1.295+; installed mods and managed policy affect authority.', mods,
    'After-call checks are separate. Edit|Write PostToolUse misses Bash and failed calls; use scoped FileChanged/PostToolUseFailure plus final acceptance.',
  ], [example('Hook setup for a direct send', '.claude/settings.json', 'Replace the exact tool name; the ask rule provides a separate permission layer. No sample sends a message.', JSON.stringify({permissions: {ask: ['mcp__ghl__send_sms']}, hooks: {PreToolUse: [{matcher: 'mcp__ghl__send_sms', hooks: [{type: 'command', command: 'python3 "${CLAUDE_PROJECT_DIR}/.claude/hooks/ask-send.py"', onFailure: 'block'}]}]}}, null, 2)),
    example('Before-call approval script', '.claude/hooks/ask-send.py', 'Runs on every covered call, no fake read marker or cached approval. It only requests approval; no tool execution.', `import json, sys
payload = json.load(sys.stdin)
if payload.get("tool_name") == "mcp__ghl__send_sms":
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "ask",
        "permissionDecisionReason": "Customer send requires owner approval for this exact action."}}))`)]));

put(['p_g2', 'p_g3', 'p_x2', 'p_lib_settings'], 'Built-in permissions; SDK UI is custom',
  'Code interactive approvals and SDK callbacks are different host interfaces. Permissions control calls, not whether task acceptance passed.', [S.permissions, S.sdkPermissions], detail([
    permissionOrder, mods, terminal,
    'allowed_tools creates allow rules, not a complete availability whitelist. Use disallowed_tools to remove/deny tools and list helper tools explicitly.',
  ], [example('SDK approval host (Python)', 'approval.py', 'Complete custom terminal host. Authentication and SDK required; running query is paid. Uses streaming input so callbacks remain available; unattended input denies.', `import asyncio
from claude_agent_sdk import (query, ClaudeAgentOptions, HookMatcher,
                              PermissionResultAllow, PermissionResultDeny)

async def can_use_tool(tool_name, tool_input, context):
    # Do not print tool_input: it may contain secrets or client data.
    try:
        answer = await asyncio.to_thread(input, f"Approve {tool_name}? [yes/no] ")
    except EOFError:
        answer = "no"
    if answer.strip().lower() == "yes":
        return PermissionResultAllow(updated_input=tool_input)
    return PermissionResultDeny(message="BLOCKED: approval denied or not given")

async def keep_open(payload, tool_use_id, context):
    return {"continue_": True}

async def prompts():
    yield {"type": "user", "message": {"role": "user", "content":
           "Ask approval to run printf audit-check. Do not modify files."}}

async def main():
    options = ClaudeAgentOptions(
        tools=["Bash"], setting_sources=[],
        settings='{"permissions":{"ask":["Bash"]}}',
        permission_mode="default", can_use_tool=can_use_tool,
        system_prompt="Request only the given read-only command. Do not change files.",
        hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[keep_open])]},
        max_turns=3, max_budget_usd=0.50)  # Estimate can exceed this amount.
    async for message in query(prompt=prompts(), options=options):
        if hasattr(message, "result"):
            print({"result": message.result,
                   "terminal_reason": getattr(message, "terminal_reason", None),
                   "is_error": getattr(message, "is_error", None)})

if __name__ == "__main__":
    asyncio.run(main())`)]));
put(['p_g4', 'p_x4'], 'Built-in managed policy; audit mods',
  'Managed controls and credential revocation are stronger than an agent reminder. A deny rule is not universally immune to installed mods.', [S.permissions], detail([mods,
    'Inventory installed mods and managed policy before treating a deny rule as the kill switch. Revoking the credential at the source is distinct from telling the model to stop.',
    'No rule here promises reversal of an action already completed.',
  ]));

put(['p_ckpt'], 'Built-in rewind; custom semantic handoff',
  'PreCompact is for compaction, NOT /clear. Save semantic progress explicitly; session resume, handoff and rollback solve different problems.', [S.hooks, S.checkpoint, S.sessions, S.harness], detail([
    'Semantic handoff: your reviewed note records goal, scope, current files, completed checks, blockers and next action. A copied transcript alone cannot infer correct task progress.',
    'Session resume: restore conversation by its session ID, then check actual progress/files and the existing smoke baseline. A new-session handoff reads approved notes instead.',
    'Rollback: Code rewind restores eligible file-tool edits, not Bash edits, most subagent edits or external operations. Use scoped backups/git and reconcile external changes separately.',
    'PreCompact can save pointers to already-written semantic notes, but it does not fire on /clear. Update progress before clearing when you intend to resume later.',
    'Reload only compact|resume for this SAME explicitly selected job. Do not automatically inject an old job on clear, startup or unrelated session.', baseline,
  ], [example('Resume the selected job only', '.claude/settings.json', 'Custom handoff reload, deliberately no clear matcher. Select JOB_PROGRESS_FILE explicitly for the intended job.', JSON.stringify({hooks: {SessionStart: [{matcher: 'compact|resume', hooks: [{type: 'command', command: 'python3 "${CLAUDE_PROJECT_DIR}/.claude/hooks/load-progress.py"'}]}]}}, null, 2)),
    example('Selected progress loader', '.claude/hooks/load-progress.py', 'Only reads an existing selected note inside this project. Missing selection injects no stale job.', `import json, os, sys
from pathlib import Path
payload = json.load(sys.stdin)
selected = os.environ.get("JOB_PROGRESS_FILE")
if payload.get("source") in ("compact", "resume") and selected:
    root = Path(payload["cwd"]).resolve()
    note = (root / selected).resolve()
    if note.is_relative_to(root) and note.is_file():
        print("Selected job handoff. Reconcile current files and smoke baseline before new work.\\n" + note.read_text())`)]));

put(['p_lead', 'p_load', 'p_plan'], 'Built-in startup; optional custom router/SDK',
  'Session instructions and system prompt precede model decisions. A router has its own instructions before selecting the target; project context is then loaded before work planning.', [S.memory, S.system, S.harness, S.python], detail([
    'Claude Code loads session instructions before the first model decision. Target-project selection is not an instruction-free first thought.',
    'A custom external router first loads its own system prompt and rules, selects the project, then starts/continues a worker with the target context. The router cannot pretend it already loaded that unknown project.',
    'SDK: setting_sources=["project"] explicitly loads project settings/instructions; use the claude_code system_prompt preset plus append for a Code-style worker. A custom system prompt must deliberately supply needed instructions.', baseline,
    'One agent is the default. The SDK and a lead with 3-5 helpers are optional implementation choices, not requirements for ordinary Claude Code work.',
  ], [sdkExample]));
put(['p_plan1', 'p_plan2'], 'Optional: long-job progress and baseline',
  'Keep semantic progress outside conversation context and reconcile it before resuming work.', [S.harness, S.sessions], detail([baseline,
    'Update progress with the actual check command/result, scope, blocker and next action. Never reuse an old PASS as proof for changed files.',
    'Commit only when authorized by the owning workflow; this reference pattern does not authorize a commit in this audit.',
  ]));
put(['p_self', 'p_helpers', 'p_a1', 'p_a2', 'p_a3'], 'Optional helpers: own prompt and context',
  'Custom non-fork subagents inherit loaded CLAUDE.md instructions; built-in Explore/Plan skip them. A fork inherits the conversation instead.', [S.sub, S.sdkSub], detail([
    'Custom helpers have their own system prompt and task message. Loaded CLAUDE.md hierarchy is inherited unless omitClaudeMd changes it; managed policy still applies. Explore/Plan skip CLAUDE.md and startup git status.',
    'Fork mode is on by default in interactive Code (2.1.232+), off by default in non-interactive -p and SDK. Forks carry parent conversation; fresh helpers do not.',
    'Delegate only independent jobs with disjoint files/records and explicit scope. Shared writes or dependencies run sequentially. Review returned evidence, not a helper success claim.',
    'No fixed helper count is required; start with one agent. Auto memory and previously invoked skills do not simply transfer to fresh non-fork helpers.',
  ], [example('The helper as a file', '.claude/agents/researcher.md', 'Custom read-only helper. Restart if this creates the first agents directory in an already-open session.', '---\nname: researcher\ndescription: Read-only independent source lookup\ntools: Read, Glob, Grep\nmodel: haiku\n---\nRead only the assigned files. Return paths, findings and gaps. Do not edit.')]));
put(['p_a4'], 'Managed Agents only: hosted orchestration',
  'This card describes Managed Agents hosted helpers, not a local Code subagent or the SDK by itself.', [S.managed], detail([
    'Managed Agents only: hosted session/runtime orchestration is a separate product.',
    'Hosting your own SDK process is a different optional deployment, with its own credentials, environment and policy.',
  ]));

put(['p_ui2', 'p_ui3'], 'Separate app/integration, not the Code/SDK agent',
  'The Claude app, Claude Code and a custom SDK host are separate surfaces. A Slack integration does not prove a shared session, hooks or project files.', [D + 'desktop', D + 'slack'], detail([
    'Claude app Projects/skills are not automatically the same runtime as Claude Code project files or SDK settings.',
    'When the app launches a Code session, check that specific Code session and its environment. Do not assume every chat, phone conversation or Slack entry point inherits Code hooks and tools.',
    'Verify the integration mode, session identity, filesystem and permission model before describing it as the same agent.',
  ]));
put(['p_x3', 'p_rep2'], 'Optional telemetry; custom receipts',
  'Trace supports diagnosis, not guaranteed replay. prompt.id is per prompt; cost totals and artifact evidence need separate handling.', [S.monitor, S.python, S.webhooks], detail([...trace, budget,
    'SDK streaming/resume cost results can be cumulative. Read the latest total rather than summing cumulative results. Inspect terminal_reason before assuming a success subtype means success.',
  ], [sdkExample, example('Turn the trace on', 'launch environment', 'Requires a working collector; detail logging may expose sensitive inputs. These switches are optional.', 'export CLAUDE_CODE_ENABLE_TELEMETRY=1\nexport OTEL_METRICS_EXPORTER=otlp\nexport OTEL_LOGS_EXPORTER=otlp\nexport OTEL_EXPORTER_OTLP_PROTOCOL=grpc\nexport OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317\nclaude')]));
put(['p_x8'], 'Optional: estimated cost threshold', budget, [S.python, S.costs], detail([
    budget, 'Separate billing/spend policy from estimated per-call stop controls. Resumed-session totals and current-call budget accounting are not the same.',
    'Use fewer helpers or cheaper models only when the task checks still pass; stop on budget exhaustion with BLOCKED, not a fabricated success.',
  ], [sdkExample]));
put(['p_evidence'], 'Custom writer: actual check receipts',
  'The map recommends a custom evidence writer. Neither telemetry nor a built-in hook automatically assembles final artifact proof.', [S.hooks, S.evals], detail([
    'Custom receipts join command, exit code, timestamp, target identity, file hashes and evidence pointers to session/prompt IDs. Redact secrets before writing.',
    'A transcript can show an attempted tool call without proving the desired result. Read back changed records/files and run the requested acceptance checks.',
    'Written example, configured hook and seen-working behavior are separate proof levels.',
  ]));
put(['p_small', 'p_lib_limits'], 'Recommendations vs actual loading cutoffs',
  'Keep instruction files focused. 200/500-line writing guidance is not an enforced file-size limit.', [S.memory, S.skills], detail(limits));
corrections.p_lib_limits.sources.push(S.sub, S.python);
corrections.p_lib_limits.detail = {
  plain: limits,
  limits: [
    'Writing recommendations: CLAUDE.md under 200 lines; SKILL.md body under 500 lines. Not parser-enforced cutoffs.',
    'Auto-memory startup cutoff: first 200 lines or 25 KB of MEMORY.md. Topic files load on demand.',
    'Current Code subagent defaults: nesting depth 3, concurrent limit 20. Version/configuration and documented exceptions matter; these are not required helper counts.',
    'Fork-mode default: on in interactive Code 2.1.232+, off in -p and SDK unless enabled.',
    'AGENTS.md automatic fallback: Code 2.1.277+, plus enabled support and Project instructions setting. CLAUDE.md above/at cwd suppresses default fallback.',
    budget,
  ],
  decide: [{ if: 'A long procedure repeats', then: 'Skill with focused reference links' },
    { if: 'A fact must load on every project turn', then: 'Short project instructions; keep their cost visible in /context' },
    { if: 'A hard permission boundary is needed', then: 'Execution controls, not line-count advice' }],
};
corrections.p_small.detail = {
  plain: [...limits, 'Keep raw logs/history on disk. Working instructions link to selected evidence and scoped references; memory does not need the whole archive.'],
  examples: [example('Small working set, searchable archive', 'Illustrative repo layout', 'Custom organization, not a built-in hard file cap.', 'CLAUDE.md                 short project instructions\n.claude/skills/check/SKILL.md  focused procedure\n.claude/skills/check/references/  linked detail\nwork/progress.md           selected semantic handoff\nevidence/                 check receipts\narchive/                  raw history, searched when needed')],
};
put(['p_ptr1'], 'Built-in project instructions; size guidance',
  'CLAUDE.md supplies persistent project context, not deterministic enforcement. Keep useful commands, scope and gotchas, with short links to procedures.', [S.memory, S.harness], {
    ...detail(['Create CLAUDE.md at the project root. State purpose, scope, existing test commands and what the agent would otherwise get wrong.', ...limits,
      'Root/ancestor instructions load at startup. Subdirectory instructions load when working there. Imports add their content to context; paths are relative to the importing file.',
      baseline, 'Review changes as code. Permission rules/hooks are separate from textual instructions; audit their actual coverage and mods.']),
    build: ['Choose an owner; verify each test command exists.', 'Put routine procedures in skills and keep project-wide facts here.', 'Use /context to inspect actual loaded instructions.'],
    examples: [example('Good: focused project instructions', 'CLAUDE.md', 'Illustrative project; use the existing smoke command, not an invented passing script.', '# Acme project\nThis repo holds the client website and integration tests.\n\n## Commands\n- npm test: existing smoke test; run before new work on a resumed job and before claiming completion.\n\n## Scope and gotchas\n- Confirm account/location before any API mutation.\n- No customer messages or production changes without owner approval.\n- Normalize phone comparisons to the documented format.\n- Report unmet checks as BLOCKED.\n\n## Long jobs\nRead work/progress.md and recent git history, inspect git status/diff, then run the existing smoke baseline.\nUpdate semantic progress before handoff or /clear.\n\n@docs/project-conventions.md')],
  });
put(['p_lib_skills'], 'Built-in discovery; procedures load when invoked',
  'Create a SKILL.md with frontmatter and task steps. Skill instructions guide the model; they do not enforce approvals or guarantee a result.', [S.skills], {
    ...detail(['Make .claude/skills/project-smoke/SKILL.md for this project, or ~/.claude/skills/ for personal reusable skills.',
      'At startup Claude sees available skill metadata; invoking a skill loads its body. Keep detailed references one link away.',
      'Use /project-smoke explicitly to test this sample. Keep scripts/templates/references in the skill directory and refer to ${CLAUDE_SKILL_DIR} in shell commands.',
      'Build a representative test case and compare results after revisions. Gotchas reduce recurrence, not promise never again.', ...limits]),
    build: ['Give a clear name and description describing when to use it.', 'Put the real test command and evidence requirements in the body.', 'Save the file, invoke the skill and inspect what actually loaded.'],
    examples: [example('A real-shaped SKILL.md', '.claude/skills/project-smoke/SKILL.md', 'Complete illustrative manual skill; substitute an existing project test command.', '---\nname: project-smoke\ndescription: Verify the existing project smoke baseline and final result. Use when starting or finishing project work.\ndisable-model-invocation: true\n---\n# Project smoke check\n1. Read CLAUDE.md, selected work/progress.md, git status/diff and recent git history.\n2. Run the existing npm test command before new work when resuming.\n3. On failure, report BLOCKED with command and output; do not hide a baseline failure.\n4. After authorized changes, rerun the same check and inspect changed artifacts.\n5. Report actual evidence, not just a successful tool invocation.\n\n## References\nSee [test scope](references/test-scope.md) when interpreting coverage.\n\n## Gotchas\nTests cover selected cases; they do not guarantee future behavior.')],
  });
put(['p_ptr2'], 'Built-in fallback: version 2.1.277+',
  'AGENTS.md fallback is real, version/settings dependent, and skipped by default when CLAUDE.md exists in the working directory or above.', [S.memory], detail([
    'Claude Code 2.1.277+ supports project AGENTS.md fallback. Check /config Project instructions and whether its built-in plugin is enabled; older provider/version exceptions require update or import.',
    'An explicit CLAUDE.md with @AGENTS.md is the compatibility route when fallback is unavailable. Do not delete this feature as a hallucination.',
    'Reading AGENTS.md in one product does not prove every app or custom SDK host reads it.',
  ], [example('Explicit import when fallback is unavailable', 'CLAUDE.md', 'One deliberate source of project instructions, with documented import behavior.', '@AGENTS.md')]));
put(['p_e5', 'p_testset'], 'Custom learning: reduce recurrence, not guarantee',
  'Keep a focused gotcha and regression case from an observed failure. Tests reduce recurrence; they cannot promise never again.', [S.skills, S.evals], detail([
    'Connect failed check/report evidence to a proposed lesson, then a regression case and reviewed future instructions.',
    'Keep the test representative and rerun it after changes. Changed tools, data and permissions can create new failures outside its coverage.',
    'Review proposals before altering shared instructions; learning is not self-authorized production change.',
  ]));
put(['p_e6'], 'Managed Agents only: optional dreaming',
  'Dreaming here is a Managed Agents feature, not built-in scheduled memory maintenance in every Code or SDK session.', [S.dreaming], detail([
    'Managed Agents only. Do not imply Code/SDK automatically run the same upkeep.',
    'A separate custom review job is optional and needs its own sources, permissions and verification.',
  ]));
put(['p_t1', 'p_t2'], 'Local process can reach production',
  'Local MCP and Bash tools run on the host but can contact production services through network access and credentials.', [S.mcp, S.permissions], detail([
    'Local is a process location, not a sandbox or safe account. Verify target identity and permissions before each consequential call.',
    'A server may wrap remote APIs. File-change hooks cannot verify remote CRM writes: use explicit readback and final acceptance.', terminal,
  ]));
put(['p_result'], 'Tool result: success, failure or uncertain write',
  'Read the execution result before another call, helper combination or final checking. Reconcile uncertain writes before retry.', [S.python, S.harness], detail([terminal,
    'Tools report outcomes, not task acceptance. Pass the actual result and evidence to the lead; combine only after the helper result arrives.',
  ]));
put(['p_combine'], 'Optional: AFTER helper results',
  'Review returned results and evidence after execution. More helper work is optional; no helper success claim replaces final acceptance.', [S.sdkSub, S.evals], detail([
    'Combine only completed, relevant findings. Check the evidence and conflicts before final acceptance.',
    'Blocked/failed/interrupted helper work is reported as such; do not silently treat missing results as finished.',
  ]));
put(['p_rep1'], 'Answer with PASS evidence or BLOCKED',
  'Report what was proven, the actual acceptance result and unresolved blockers. A stopped run is not a successful run.', [S.harness, S.evals], detail([terminal,
    'Give exact evidence pointers for completed items. Missing checks, denied approvals and uncertain writes stay explicit.',
  ]));
put(['p_toolload'], 'Built-in /context and /mcp; inspect loaded tools',
  'Inspect actual context and tool availability rather than assuming every connected tool definition loads in full on every call.', [S.mcp, S.costs], detail([
    'Tool search/deferred loading can reduce initial context. Disable unused servers only within authorized scope; confirm active user, local, project, managed and plugin servers.',
  ]));

const bandText: Record<string, string> = {
  p_band_ask: 'Built-in prompt correlation: prompt.id is per prompt, not per whole job. Events can be missing or redacted.',
  p_band_client: 'Project selection follows session/router instructions. A project MCP file or vault does not prove credential/account isolation.',
  p_band_front: 'Built-in instructions plus custom systemprompt/system_prompt precede work decisions. Resumed jobs reconcile progress/git and run the existing smoke baseline.',
  p_band_delegate: 'Optional helpers use their own prompt; custom agents inherit CLAUDE.md, Explore/Plan skip it, forks inherit conversation.',
  p_band_gw: 'Built-in Code rules/hooks and custom SDK UI differ. Pending approval waits; denied approval reports BLOCKED. Installed mods and managed policy affect enforcement.',
  p_band_run: 'Read actual tool results, including failures and uncertain writes. FileChanged watches scoped files; remote writes require readback.',
  p_band_verify: 'Custom final acceptance: recheck before cap; only actual passing evidence permits PASS. Failed, interrupted or unrun checks stay BLOCKED.',
  p_band_report: 'Report evidence and blockers. Optional telemetry estimates cost; it is neither a billing cap nor a complete replay.',
  p_band_learn: 'Optional learning follows check/report evidence, proposes a regression/lesson, and updates reviewed future instructions. Managed Agents dreaming is separate.',
};

/** Replace, do not concatenate: inherited V1 contradictions must not remain in V2 popups. */
export function correctV2Node(n: ProNode): ProNode {
  if (!n.id.startsWith('p_')) return n;
  const c = corrections[n.id];
  if (c) return { ...n, ...c, how: undefined, sources: [...new Set(c.sources)] };
  if (bandText[n.id]) return { ...n, trace: bandText[n.id], why: bandText[n.id], sources: [S.hooks, S.memory, S.permissions, S.python] };
  return n;
}

/** Sticky notes for corrected V2 cards must not reuse titles/text from inherited V1 examples. */
export const V2_CORRECTED_IDS = Object.keys(corrections);
export const V2_STICKY = [
  { ids: ['p_goal', 'p_check', 'p_aftercheck'], title: 'The check', text: 'Save the Python script at the shown path and ensure the existing test is real. At the repeat cap it rechecks and warns the user on failure; it cannot force a revised final answer. Match the latest run receipt; missing, stale or unwritable proof is BLOCKED.', src: S.hooks },
  { ids: ['p_g1'], title: 'Before-call approval script', text: 'Register the verified tool name and test before relying on it. This asks before this direct tool only, not every alias or wrapper. Audit mods and managed controls.', src: S.permissions },
  { ids: ['p_lead', 'p_load', 'p_plan', 'p_rep2', 'p_x3', 'p_x8'], title: sdkExample.title, text: 'Install the SDK and authenticate separately. The full async main is syntax-complete, but running query is paid. tools limits availability; allowed_tools alone does not. MCP tools are denied in this read-only sample.', src: S.python },
  { ids: ['p_ckpt'], title: 'Selected progress loader', text: 'Explicitly select JOB_PROGRESS_FILE for the same job. No clear/startup reload. Reconcile current files and the smoke baseline before new work.', src: S.hooks },
  { ids: ['p_lib_skills'], title: 'A real-shaped SKILL.md', text: 'Create linked reference files in the skill folder. The sample test command must already exist; invoke /project-smoke and verify actual results.', src: S.skills },
  { ids: ['p_lib_mcp', 'p_l1', 'p_l2'], title: 'One remote server, one local server', text: 'Replace the URL and set the environment credential separately. Provide tools/local_mcp.py (not included). Project servers need approval and a working /mcp connection; other server scopes remain possible.', src: S.mcp },
  { ids: ['p_g2', 'p_g3', 'p_x2', 'p_lib_settings'], title: 'SDK approval host (Python)', text: 'Complete custom streaming-input host. Do not also auto-allow gated tools. EOF denies; terminal interruption still needs a BLOCKED report. Running query is paid.', src: S.sdkPermissions },
];
