#!/usr/bin/env python3
"""Builds a throwaway Claude Code project that runs the Pro Map guardrails live.
Touches nothing outside ~/Projects/pro-map-live-test and ~/.pro-map-live-state."""
import json, os, shutil, stat, sys
from pathlib import Path

SRC = Path(sys.argv[1])            # pro-map-guardrails folder
P = Path.home() / "Projects" / "pro-map-live-test"
STATE = Path.home() / ".pro-map-live-state"
if P.exists():
    shutil.rmtree(P)
if STATE.exists():
    shutil.rmtree(STATE)
(P / ".claude" / "hooks").mkdir(parents=True)
(P / ".claude" / "connector-cards").mkdir(parents=True)
(P / ".claude" / "skills").mkdir(parents=True)
STATE.mkdir(mode=0o700)
os.chmod(STATE, 0o700)
for f in ("asset_guard.py", "read_gate.py"):
    shutil.copy2(SRC / f, P / ".claude" / "hooks" / f)

# Tiny local MCP server: one tool, logs every real execution to calls.log
(P / "demo_server.py").write_text('''import json, sys, pathlib
LOG = pathlib.Path(__file__).with_name("calls.log")
def send(m): sys.stdout.write(json.dumps(m) + "\\n"); sys.stdout.flush()
for line in sys.stdin:
    m = json.loads(line); mid = m.get("id"); meth = m.get("method")
    if meth == "initialize":
        send({"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": m["params"].get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {}}, "serverInfo": {"name": "demo", "version": "1"}}})
    elif meth == "tools/list":
        send({"jsonrpc": "2.0", "id": mid, "result": {"tools": [{"name": "echo_note", "description": "Echo a short note back.", "inputSchema": {"type": "object", "properties": {"note": {"type": "string"}}, "required": ["note"]}}]}})
    elif meth == "tools/call":
        note = m["params"].get("arguments", {}).get("note", "")
        with LOG.open("a") as f: f.write(note + "\\n")
        send({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": "echo: " + note}]}})
    elif mid is not None:
        send({"jsonrpc": "2.0", "id": mid, "result": {}})
''')
(P / ".mcp.json").write_text(json.dumps({"mcpServers": {"demo": {"type": "stdio", "command": "python3", "args": [str(P / "demo_server.py")]}}}, indent=2))
card = P / ".claude" / "connector-cards" / "demo.md"
card.write_text("# demo connector card\n\nTool: echo_note. Use only for test notes. Never send client data.\n")

hook = lambda c, t=10, block=True: {"type": "command", "command": c, "timeout": t, **({"onFailure": "block"} if block else {})}
asset = lambda ev: hook(f'python3 -B "${{CLAUDE_PROJECT_DIR}}/.claude/hooks/asset_guard.py" --root "${{CLAUDE_PROJECT_DIR}}" --event {ev}', 30, ev != "Stop")
read = hook(f'python3 -B "${{CLAUDE_PROJECT_DIR}}/.claude/hooks/read_gate.py" --project "${{CLAUDE_PROJECT_DIR}}" --policy "${{CLAUDE_PROJECT_DIR}}/.claude/guard-policy.json" --state-dir "{STATE}"')
settings = {"hooks": {
    "PreToolUse": [{"matcher": "^(Write|Edit)$", "hooks": [asset("PreToolUse")]}, {"matcher": "^(Read|mcp__.*)$", "hooks": [read]}],
    "PostToolUse": [{"matcher": "^Read$", "hooks": [read]}, {"hooks": [asset("PostToolUse")]}],
    "PostToolUseFailure": [{"matcher": "^Read$", "hooks": [read]}],
    "PermissionDenied": [{"matcher": "^Read$", "hooks": [read]}],
    "Stop": [{"hooks": [asset("Stop")]}],
}}
(P / ".claude" / "settings.json").write_text(json.dumps(settings, indent=2))
policy = {"version": 1, "project_root": "${CLAUDE_PROJECT_DIR}",
          "servers": {"demo": [str(card)]}, "direct_tools": ["mcp__demo__echo_note"], "batches": {}}
(P / ".claude" / "guard-policy.json").write_text(json.dumps(policy, indent=2))
print("built", P)
